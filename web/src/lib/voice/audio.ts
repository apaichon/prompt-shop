// Mic permission, PCM conversion and cancellable source playback adapted from
// Monti Jarvis. AudioWorklet transport, bounds and lifecycle are new; see NOTICE.md.
export interface AudioEngine {
  open(onFrame: (frame: ArrayBuffer, voiced: boolean) => void, onDrain: () => void, onFailure: () => void): Promise<void>;
  capture(enabled: boolean): void;
  microphoneMuted(muted: boolean): void;
  speakerMuted(muted: boolean): void;
  play(frame: ArrayBuffer): void;
  flush(): void;
  close(): void;
}
export class BrowserAudio implements AudioEngine {
  private context?: AudioContext;
  private stream?: MediaStream;
  private node?: AudioWorkletNode;
  private source?: MediaStreamAudioSourceNode;
  private silence?: GainNode;
  private sources = new Set<AudioBufferSourceNode>();
  private nextAt = 0;
  private muted = false;
  private closed = false;
  private onDrain = () => {};

  async open(onFrame: (frame: ArrayBuffer, voiced: boolean) => void, onDrain: () => void, onFailure: () => void) {
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia || !window.AudioContext || !window.AudioWorkletNode) {
      throw new Error('Microphone needs a supported browser on HTTPS or localhost. You can still type an item.');
    }
    this.onDrain = onDrain;
    // Resume during the explicit click gesture; never defer until the provider is ready.
    const context = new AudioContext(); this.context = context;
    const resumed = context.resume();
    const permission = navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
    // Attach both handlers immediately, including the permission result after Stop.
    const [resume, media] = await Promise.allSettled([resumed, permission]);
    if (media.status === 'fulfilled') {
      if (this.closed) { media.value.getTracks().forEach((track) => track.stop()); return; }
      this.stream = media.value;
    }
    if (resume.status === 'rejected' || media.status === 'rejected') {
      this.close();
      throw new Error('Microphone or speaker access was not available. Check site permissions, then restart voice or type an item.');
    }
    if (this.closed) return;
    await context.audioWorklet.addModule('/pcm-capture.js');
    if (this.closed) return;
    this.node = new AudioWorkletNode(context, 'pcm-capture');
    this.source = context.createMediaStreamSource(this.stream!);
    this.silence = context.createGain(); this.silence.gain.value = 0;
    this.source.connect(this.node); this.node.connect(this.silence); this.silence.connect(context.destination);
    this.node.onprocessorerror = onFailure;
    this.node.port.onmessage = ({ data }) => {
      if (this.closed || !(data instanceof ArrayBuffer)) return;
      const view = new DataView(data); let energy = 0;
      for (let i = 0; i < view.byteLength; i += 2) energy += Math.abs(view.getInt16(i, true));
      onFrame(data, energy / Math.max(1, view.byteLength / 2) > 350);
    };
    this.stream!.getTracks().forEach((track) => { track.onended = onFailure; });
  }
  capture(enabled: boolean) { this.node?.port.postMessage(enabled ? 'start' : 'stop'); }
  microphoneMuted(muted: boolean) { this.stream?.getAudioTracks().forEach((track) => { track.enabled = !muted; }); }
  speakerMuted(muted: boolean) { this.muted = muted; if (muted) this.flush(); }
  play(frame: ArrayBuffer) {
    const context = this.context;
    if (this.closed || this.muted) return;
    if (!context || context.state !== 'running' || !frame.byteLength || frame.byteLength > 16384 || frame.byteLength % 2) throw new Error('Invalid audio output');
    const duration = frame.byteLength / 48000;
    this.nextAt = Math.max(context.currentTime, this.nextAt);
    if (this.nextAt - context.currentTime + duration > 1) throw new Error('Audio backlog');
    const buffer = context.createBuffer(1, frame.byteLength / 2, 24000);
    const channel = buffer.getChannelData(0), view = new DataView(frame);
    for (let i = 0; i < channel.length; i++) channel[i] = view.getInt16(i * 2, true) / 32768;
    const source = context.createBufferSource(); source.buffer = buffer; source.connect(context.destination);
    this.sources.add(source);
    source.onended = () => { this.sources.delete(source); source.disconnect(); if (!this.sources.size && !this.closed) this.onDrain(); };
    source.start(this.nextAt); this.nextAt += duration;
  }
  flush() {
    for (const source of this.sources) { source.onended = null; try { source.stop(); } catch { /* already stopped */ } source.disconnect(); }
    this.sources.clear(); this.nextAt = this.context?.currentTime ?? 0;
  }
  close() {
    this.closed = true;
    this.capture(false); this.flush();
    this.stream?.getTracks().forEach((track) => { track.onended = null; track.stop(); });
    this.node?.disconnect(); this.node?.port.close(); this.source?.disconnect(); this.silence?.disconnect();
    void this.context?.close().catch(() => {});
    this.context = undefined; this.stream = undefined; this.node = undefined;
  }
}
