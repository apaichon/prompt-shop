import { mergeTranscriptChunk } from './transcript';

export type TranscriptMeta = { final?: boolean };

export type VoiceProductFact = {
  product_id: string;
  product_version: number;
  name: string;
  description: string;
  category: string;
  variant_id: string;
  variant_version: number;
  label: string;
  sku: string;
  price_minor: number;
  currency: 'THB';
  available: number;
};

export type VoiceAssistantAction = {
  type: 'show_products';
  source: 'live_catalog';
  query: string;
  products: VoiceProductFact[];
  primary_product_id: string;
  primary_variant_id: string;
  requires_confirmation: true;
};

export type VoiceCallbacks = {
  onStatus: (status: string) => void;
  onTranscript: (role: 'user' | 'assistant', text: string, meta?: TranscriptMeta) => void;
  onAction?: (action: VoiceAssistantAction) => void;
  onLive: (live: boolean) => void;
  onSpeaking?: (speaking: boolean) => void;
  onError: (message: string) => void;
};

type RelayMessage = { type: string; data?: string; text?: string; role?: string; message?: string; code?: string; action?: VoiceAssistantAction };

export class MontiBusinessVoice {
  private socket: WebSocket | null = null;
  private stream: MediaStream | null = null;
  private capture: AudioContext | null = null;
  private playback: AudioContext | null = null;
  private processor: ScriptProcessorNode | null = null;
  private nextPlaybackAt = 0;
  private ready = false;
  private playbackSources = new Set<AudioBufferSourceNode>();
  private userBuffer = '';
  private assistantBuffer = '';
  private assistantFromTranscript = false;
  private paused = false;

  async start(ticket: string, callbacks: VoiceCallbacks) {
    this.userBuffer = '';
    this.assistantBuffer = '';
    this.assistantFromTranscript = false;
    this.paused = false;
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
      throw new Error('Microphone needs HTTPS or localhost. You can still use text chat.');
    }
    callbacks.onStatus('Requesting microphone…');
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
    } catch (cause) {
      const message = cause instanceof DOMException && cause.name === 'NotAllowedError'
        ? 'Microphone permission was denied. Text chat is still available.'
        : cause instanceof Error ? cause.message : 'Microphone is unavailable. Text chat is still available.';
      await this.stop(false);
      throw new Error(message);
    }
    this.capture = new AudioContext();
    this.playback = new AudioContext({ sampleRate: 24000 });
    await Promise.all([this.capture.resume(), this.playback.resume()]);
    const source = this.capture.createMediaStreamSource(this.stream);
    this.processor = this.capture.createScriptProcessor(4096, 1, 1);
    const silent = this.capture.createGain();
    silent.gain.value = 0;
    source.connect(this.processor);
    this.processor.connect(silent);
    silent.connect(this.capture.destination);
    const scheme = location.protocol === 'https:' ? 'wss' : 'ws';
    this.socket = new WebSocket(`${scheme}://${location.host}/ws/business-voice?ticket=${encodeURIComponent(ticket)}`);
    this.processor.onaudioprocess = (event) => {
      if (this.paused || !this.ready || this.socket?.readyState !== WebSocket.OPEN || !this.capture) return;
      const samples = resample(event.inputBuffer.getChannelData(0), this.capture.sampleRate, 16000);
      this.socket.send(JSON.stringify({ type: 'audio', data: pcmBase64(samples) }));
    };
    this.socket.onmessage = (event) => {
      let message: RelayMessage;
      try { message = JSON.parse(String(event.data)); } catch { return; }
      if (message.type === 'ready') {
        this.ready = true;
        callbacks.onStatus(message.message || 'Voice connected');
        callbacks.onLive(true);
      } else if (message.type === 'status' || message.type === 'queue_status' || message.type === 'queue_admitted') {
        callbacks.onStatus(message.message || 'Connecting…');
      } else if ((message.type === 'transcript' || message.type === 'input_transcript' || message.type === 'output_transcript') && message.text) {
        // The Go relay emits transcript/role=user; older callers use caller.
        // Keep output transcripts distinct so the model cannot confirm its own action.
        const role = message.type === 'input_transcript' ||
          (message.type === 'transcript' && (message.role === 'user' || message.role === 'caller'))
          ? 'user' : 'assistant';
        if (role === 'user') {
          if (this.assistantBuffer) this.finalize('assistant', callbacks);
          this.userBuffer = mergeTranscriptChunk(this.userBuffer, message.text);
          callbacks.onTranscript('user', this.userBuffer, { final: false });
        } else {
          if (this.userBuffer) this.finalize('user', callbacks);
          this.assistantFromTranscript = true;
          this.assistantBuffer = mergeTranscriptChunk(this.assistantBuffer, message.text);
          callbacks.onTranscript('assistant', this.assistantBuffer, { final: false });
        }
      } else if (message.type === 'text' && message.text) {
        if (!this.assistantFromTranscript) {
          if (this.userBuffer) this.finalize('user', callbacks);
          this.assistantBuffer = mergeTranscriptChunk(this.assistantBuffer, message.text);
          callbacks.onTranscript('assistant', this.assistantBuffer, { final: false });
        }
      } else if (message.type === 'turn_complete') {
        this.finalize('user', callbacks);
        this.finalize('assistant', callbacks);
        this.assistantFromTranscript = false;
      } else if (message.type === 'audio' && message.data) {
        callbacks.onSpeaking?.(true);
        void this.play(message.data, callbacks);
      } else if (message.type === 'assistant_action' && message.action?.type === 'show_products') {
        callbacks.onAction?.(message.action);
      } else if (message.type === 'interrupted') {
        for (const source of this.playbackSources) source.stop();
        this.playbackSources.clear();
        this.nextPlaybackAt = this.playback?.currentTime ?? 0;
        callbacks.onSpeaking?.(false);
        this.finalize('assistant', callbacks);
        this.assistantFromTranscript = false;
      } else if (message.type === 'error') {
        callbacks.onSpeaking?.(false);
        callbacks.onError(message.message || message.code || 'Voice session ended');
      }
    };
    this.socket.onerror = () => {
      callbacks.onSpeaking?.(false);
      callbacks.onError('Voice connection failed. Text chat is still available.');
    };
    this.socket.onclose = () => {
      this.finalize('user', callbacks);
      this.finalize('assistant', callbacks);
      this.ready = false;
      callbacks.onLive(false);
      callbacks.onSpeaking?.(false);
      void this.stop(false);
    };
  }

  async stop(sendEnd = true) {
    if (sendEnd && this.socket?.readyState === WebSocket.OPEN) this.socket.send(JSON.stringify({ type: 'end' }));
    this.ready = false;
    this.processor?.disconnect();
    this.processor = null;
    this.socket?.close();
    this.socket = null;
    this.stream?.getTracks().forEach((track) => track.stop());
    this.stream = null;
    await Promise.allSettled([this.capture?.close(), this.playback?.close()].filter(Boolean) as Promise<void>[]);
    this.capture = null;
    this.playback = null;
    this.nextPlaybackAt = 0;
    this.playbackSources.clear();
    this.userBuffer = '';
    this.assistantBuffer = '';
    this.assistantFromTranscript = false;
    this.paused = false;
  }

  setPaused(paused: boolean) {
    this.paused = paused;
    if (paused) this.flushPlayback();
  }

  notifyCartUpdated() {
    if (!this.ready || this.socket?.readyState !== WebSocket.OPEN) return false;
    try {
      this.socket.send(JSON.stringify({ type: 'cart_updated' }));
      return true;
    } catch {
      return false;
    }
  }

  private finalize(role: 'user' | 'assistant', callbacks: VoiceCallbacks) {
    const text = role === 'user' ? this.userBuffer : this.assistantBuffer;
    if (!text) return;
    callbacks.onTranscript(role, text, { final: true });
    if (role === 'user') this.userBuffer = '';
    else this.assistantBuffer = '';
  }

  private flushPlayback() {
    for (const source of this.playbackSources) {
      try { source.stop(); } catch { /* source may already be ended */ }
    }
    this.playbackSources.clear();
    this.nextPlaybackAt = this.playback?.currentTime ?? 0;
  }

  private async play(encoded: string, callbacks: VoiceCallbacks) {
    if (!this.playback) {
      callbacks.onSpeaking?.(false);
      return;
    }
    const bytes = Uint8Array.from(atob(encoded), (char) => char.charCodeAt(0));
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    const audio = this.playback.createBuffer(1, Math.floor(bytes.byteLength / 2), 24000);
    const channel = audio.getChannelData(0);
    for (let i = 0; i < channel.length; i++) channel[i] = view.getInt16(i * 2, true) / 32768;
    const source = this.playback.createBufferSource();
    source.buffer = audio;
    source.connect(this.playback.destination);
    this.playbackSources.add(source);
    source.onended = () => {
      this.playbackSources.delete(source);
      if (this.playbackSources.size === 0) callbacks.onSpeaking?.(false);
    };
    this.nextPlaybackAt = Math.max(this.nextPlaybackAt, this.playback.currentTime);
    source.start(this.nextPlaybackAt);
    this.nextPlaybackAt += audio.duration;
  }
}

function resample(input: Float32Array, sourceRate: number, targetRate: number) {
  if (sourceRate === targetRate) return input;
  const ratio = sourceRate / targetRate;
  const output = new Float32Array(Math.max(1, Math.floor(input.length / ratio)));
  for (let i = 0; i < output.length; i++) {
    const start = Math.floor(i * ratio);
    const end = Math.min(input.length, Math.floor((i + 1) * ratio));
    let total = 0;
    for (let j = start; j < end; j++) total += input[j];
    output[i] = total / Math.max(1, end - start);
  }
  return output;
}

function pcmBase64(samples: Float32Array) {
  const bytes = new Uint8Array(samples.length * 2);
  const view = new DataView(bytes.buffer);
  for (let i = 0; i < samples.length; i++) {
    const value = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(i * 2, value < 0 ? value * 32768 : value * 32767, true);
  }
  let binary = '';
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary);
}
