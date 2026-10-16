import { AudioDevices, AudioDeviceError, type AudioSelection } from './devices';
import { writable } from 'svelte/store';
import { Api, ApiError, errorMessage, recovery } from '../api';
import { eventSchema, type VoiceEvent } from '../contracts';
import { BrowserAudio, type AudioEngine } from './audio';
import { InputActivity } from './activity';
import { EventGate } from './gate';
import { mergeTranscriptChunk } from './transcript';

export type VoicePhase = 'idle' | 'connecting' | 'listening' | 'thinking' | 'speaking' | 'interrupted' | 'error';
export interface VoiceState {
  phase: VoicePhase; message: string; active: boolean; micMuted: boolean; soundMuted: boolean;
  speakerMode: boolean; micHeld: boolean; remaining: number; input: string; output: string; outputLevel: number;
}
const initial = (): VoiceState => ({ phase: 'idle', message: '', active: false, micMuted: false, soundMuted: false, speakerMode: false, micHeld: false, remaining: 300, input: '', output: '', outputLevel: 0 });
export class VoiceClient {
  readonly devices = new AudioDevices(() => { if(this.state.active)this.stop('A selected audio device disconnected. Check Audio settings, then start voice again.'); });
  private state = initial();
  private store = writable(this.state);
  subscribe = this.store.subscribe;
  private gate = new EventGate();
  private nonce = 0;
  private socket?: WebSocket;
  private audio?: AudioEngine;
  private abort?: AbortController;
  private timer?: ReturnType<typeof setInterval>;
  private ready = false;
  private lastSpeech = 0;
  private inputActivity = new InputActivity();
  private expires = 0;
  private setupDeadline = 0;
  private lastPing = 0;
  private pongDeadline = 0;
  private audioFinished = false;
  private audioDrained = true;
  private cooldown = 0;
  private playingReply = false;
  private speakerTailUntil = 0;

  // Network completion and local playout are independent. A gap between PCM
  // chunks must not reopen the microphone while the provider is still speaking.
  private updateSpeakerHold() {
    const micHeld = this.state.speakerMode && (this.playingReply || Date.now() < this.speakerTailUntil);
    if (micHeld !== this.state.micHeld) this.patch({ micHeld });
    return micHeld;
  }
  private finishPlayout() {
    if (this.playingReply && this.audioFinished && this.audioDrained) {
      this.playingReply = false;
      this.speakerTailUntil = Date.now() + 250;
    }
    this.updateSpeakerHold();
  }
  private flushAudio() {
    this.audio?.flush(); this.audioFinished = true; this.audioDrained = true;
    this.finishPlayout();
  }
  toggleSpeakerMode() {
    this.patch({ speakerMode: !this.state.speakerMode });
    this.inputActivity.reset(); this.updateSpeakerHold();
  }
  interrupt() {
    if (!this.ready || !this.state.speakerMode || !this.state.micHeld) return;
    this.flushAudio(); this.gate.anticipateTurn(); this.inputActivity.reset();
    this.lastSpeech = Date.now(); this.callbacks.turn();
    this.patch({ phase: 'listening', outputLevel: 0, message: 'Reply stopped. Speak when the microphone resumes.' });
  }

  constructor(private callbacks: { event: (event: VoiceEvent) => void; turn: () => void },
    private api = new Api(), private makeAudio: (selection: AudioSelection) => AudioEngine = selection => new BrowserAudio(selection),
    private makeSocket: (url: string, protocol: string) => WebSocket = (url, protocol) => new WebSocket(url, protocol),
    private origin: () => string = () => window.location.origin) {}
  private patch(patch: Partial<VoiceState>) { this.state = { ...this.state, ...patch }; this.store.set(this.state); }

  async start() {
    if (this.state.active) return;
    if (Date.now() < this.cooldown) { this.patch({ phase: 'error', message: recovery.RATE_LIMITED }); return; }
    this.stop();
    const token = this.nonce;
    const current = () => token === this.nonce;
    this.devices.cancel();
    const audio = this.makeAudio(this.devices.selection()); this.audio = audio;
    const abort = new AbortController(); this.abort = abort;
    this.setupDeadline = Date.now() + 30000;
    this.patch({ ...initial(), speakerMode: this.state.speakerMode, phase: 'connecting', active: true, message: 'Allow microphone access to begin.' });
    this.timer = setInterval(() => this.tick(), 500);
    try {
      await audio.open((frame, voiced) => { if (current()) this.sendAudio(frame, voiced); },
        () => { if (current()) { this.audioDrained = true; this.finishPlayout(); if (this.audioFinished && this.ready) this.patch({ phase: 'listening', message: 'You can ask another question.' }); } },
        () => { if (current()) this.fail('Audio stopped. Restart voice or type an item.'); },
        (outputLevel) => { if (current()) this.patch({ outputLevel }); });
      if (!current()) { audio.close(); return; }
      const ticket = await this.api.ticket(abort.signal);
      if (!current()) return;
      if (Date.parse(ticket.ticket_expires_at) <= Date.now()) throw new ApiError('SESSION_TICKET_INVALID');
      this.gate.start(ticket.session_id);
      const url = new URL('/ws/voice', this.origin()); url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
      const socket = this.makeSocket(url.href, 'prompt-shop.voice.v1'); this.socket = socket;
      socket.binaryType = 'arraybuffer';
      socket.onmessage = ({ data }) => { if (current()) this.receive(data); };
      socket.onerror = () => { if (current()) this.fail('Voice could not connect. Restart voice or type an item.'); };
      socket.onclose = () => { if (current()) this.fail('Voice disconnected. Restart voice or type an item.'); };
      this.patch({ message: 'Connecting your voice session…' });
    } catch (error) {
      if (!current()) return;
      if (error instanceof ApiError && error.retryAfter) this.cooldown = Date.now() + error.retryAfter * 1000;
      this.fail(error instanceof AudioDeviceError ? error.message : error instanceof ApiError ? errorMessage(error) : 'Microphone or speaker access was not available. Check site permissions, then restart voice or type an item.');
    }
  }
  stop(message = '') {
    // Invalidate the identity before any transport callback or asynchronous cleanup.
    const session = this.gate.session;
    this.audioFinished = false; this.audioDrained = true; this.playingReply = false; this.speakerTailUntil = 0; this.inputActivity.reset();
    this.nonce++; this.gate.stop(); this.ready = false; this.callbacks.turn();
    this.abort?.abort(); this.abort = undefined;
    if (this.timer) clearInterval(this.timer); this.timer = undefined;
    this.audio?.close(); this.audio = undefined;
    const socket = this.socket; this.socket = undefined;
    if (socket) {
      socket.onmessage = null; socket.onclose = null; socket.onerror = null;
      try { if (socket.readyState === 1 && session) socket.send(JSON.stringify({ type: 'stop', session_id: session })); } catch { /* transport already failed */ }
      try { socket.close(); } catch { /* local resources are already released */ }
    }
    this.patch({ ...initial(), speakerMode: this.state.speakerMode, message });
  }
  private fail(message: string) { this.stop(); this.patch({ phase: 'error', message }); }
  muteMicrophone() { const muted = !this.state.micMuted; this.audio?.microphoneMuted(muted); this.patch({ micMuted: muted }); }
  muteSpeaker() {
    const muted = !this.state.soundMuted;
    if (muted) this.flushAudio();
    this.audio?.speakerMuted(muted);
    this.patch({ soundMuted: muted, ...(muted && this.state.phase === 'speaking' ? { phase: 'listening' as const } : {}) });
  }
  select(search_id: string, product_id: string): boolean {
    if (!this.ready || this.socket?.readyState !== 1) return false;
    this.inputActivity.reset(); this.flushAudio(); this.gate.anticipateTurn(); this.lastSpeech = Date.now();
    this.callbacks.turn(); this.patch({ phase: 'thinking', message: 'Finding directions…', input: '', output: '' });
    return this.send({ type: 'select', search_id, product_id });
  }
  private send(event: Record<string, unknown>) {
    if (this.socket?.readyState !== 1 || !this.gate.session) return false;
    try { this.socket.send(JSON.stringify({ ...event, session_id: this.gate.session })); return true; } catch { this.fail('Voice disconnected. Restart voice or type an item.'); return false; }
  }
  private sendAudio(frame: ArrayBuffer, voiced: boolean) {
    if (!this.ready || this.socket?.readyState !== 1) return;
    if (frame.byteLength > 6400 || frame.byteLength % 2 || this.socket.bufferedAmount + frame.byteLength > 32000) { this.fail(recovery.CLIENT_TOO_SLOW); return; }
    const now = Date.now();
    // Send silence to BOTH the server VAD and Gemini while speakers are active.
    // Merely skipping local interruption still lets server VAD cancel the reply.
    const held = this.updateSpeakerHold();
    if (held || this.state.micMuted) frame = new ArrayBuffer(frame.byteLength);
    const speech = voiced && !this.state.micMuted && !held;
    const activity = this.inputActivity.push(frame.byteLength, speech);
    if (activity.started) {
      this.flushAudio(); this.gate.anticipateTurn(); this.callbacks.turn();
      this.patch({ phase: 'listening', input: '', output: '', message: 'Listening to you…' });
    }
    if (this.inputActivity.active && speech) this.lastSpeech = now;
    if (activity.ended) this.patch({ phase: 'thinking', message: 'Thinking…' });
    try { this.socket.send(frame); } catch { this.fail('Voice disconnected. Restart voice or type an item.'); }
  }
  private receive(data: unknown) {
    if (data instanceof ArrayBuffer) {
      if (!this.ready || !this.gate.generation) return;
      try {
        // A sound mute may have flushed an earlier chunk of this generation.
        // Fresh PCM must wait for completion again, even without a new audio_start.
        this.audioFinished = false; this.audioDrained = this.state.soundMuted;
        this.audio?.play(data);
        if (!this.state.soundMuted) {
          this.playingReply = true; this.updateSpeakerHold(); this.patch({ phase: 'speaking' });
        }
      }
      catch { this.fail(recovery.CLIENT_TOO_SLOW); }
      return;
    }
    if (typeof data !== 'string' || data.length > 65536) { this.fail('Voice returned an invalid response. Please restart.'); return; }
    let parsed;
    try { parsed = eventSchema.safeParse(JSON.parse(data)); } catch { return; }
    if (!parsed.success) return; // Unknown actions can never execute UI behavior.
    const event = parsed.data, decision = this.gate.accept(event);
    if (!decision.accepted) return;
    if (decision.flush) this.flushAudio();
    if (decision.newTurn) { this.audioFinished = false; this.callbacks.turn(); this.patch({ input: '', output: '' }); }
    if (!this.ready && !['ready', 'error', 'session_ending'].includes(event.type)) return;
    switch (event.type) {
      case 'ready':
        if (this.ready) { this.fail('Voice connection was reset. Please restart.'); return; }
        this.ready = true; this.expires = Math.min(Date.parse(event.expires_at), Date.now() + 300000);
        this.lastSpeech = this.lastPing = Date.now(); this.pongDeadline = 0; this.inputActivity.reset();
        this.audio?.capture(true); this.patch({ phase: 'listening', message: 'Say hello, ask a question, or find an item.' }); break;
      case 'input_transcript': this.patch({ input: mergeTranscriptChunk(this.state.input, event.text).slice(-8000), phase: event.final ? 'thinking' : 'listening' }); break;
      case 'output_transcript': this.patch({ output: mergeTranscriptChunk(this.state.output, event.text).slice(-8000) }); break;
      case 'audio_start': this.audioFinished = false; break;
      case 'audio_end': this.audioFinished = true; this.finishPlayout(); if (this.audioDrained) this.patch({ phase: 'listening', message: 'You can ask another question.' }); break;
      case 'interrupted':
        this.patch(decision.newTurn
          ? { phase: 'listening', message: 'Listening to you…' }
          : { phase: 'interrupted', message: 'Response stopped. Listening to you…' }); break;
      case 'turn_complete': this.audioFinished = true; this.finishPlayout(); if (this.audioDrained || this.state.phase !== 'speaking') this.patch({ phase: 'listening', message: 'You can ask another question.' }); break;
      case 'error':
        if (event.code === 'TURN_TIMEOUT') {
          this.flushAudio(); this.gate.anticipateTurn(); this.callbacks.turn();
          this.audioFinished = true; this.audioDrained = true;
          this.patch({ phase: 'listening', output: '', outputLevel: 0, message: recovery.TURN_TIMEOUT });
          break;
        }
        if (['STALE_SELECTION', 'CLASSIFICATION_ABSTAINED', 'CLASSIFIER_TIMEOUT', 'CLASSIFIER_BUSY'].includes(event.code)) {
          this.flushAudio(); this.patch({ phase: 'listening', message: recovery[event.code] });
        } else this.fail(recovery[event.code] ?? 'Voice could not complete that request. Restart voice or type an item.');
        break;
      case 'session_ending': this.fail(recovery[event.reason] ?? 'Voice session ended. Restart voice or type an item.'); break;
      case 'pong': this.pongDeadline = 0; break;
      default: this.callbacks.event(event);
    }
  }
  private tick() {
    const now = Date.now();
    if (!this.ready) { if (now >= this.setupDeadline) this.fail(recovery.SETUP_TIMEOUT); return; }
    this.updateSpeakerHold();
    this.patch({ remaining: Math.max(0, Math.ceil((this.expires - now) / 1000)) });
    if (now >= this.expires) { this.fail(recovery.SESSION_EXPIRED); return; }
    if (now - this.lastSpeech >= 60000) { this.fail(recovery.IDLE_TIMEOUT); return; }
    if (this.pongDeadline && now >= this.pongDeadline) { this.fail('Voice disconnected. Restart voice or type an item.'); return; }
    if (now - this.lastPing >= 20000) { this.send({ type: 'ping' }); this.lastPing = now; this.pongDeadline = now + 10000; }
  }
}
