// Mic permission, PCM conversion and cancellable source playback adapted from
// Monti Jarvis. AudioWorklet transport, bounds and lifecycle are new; see NOTICE.md.
export interface AudioEngine {
  open(onFrame: (frame: ArrayBuffer, voiced: boolean) => void, onDrain: () => void, onFailure: () => void, onLevel?: (level: number) => void): Promise<void>;
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
  private analyser?: AnalyserNode;
  private levelFrame?: number;
  private onLevel = (_level: number) => {};
  private lastLevel = 0;

  async open(onFrame: (frame: ArrayBuffer, voiced: boolean) => void, onDrain: () => void, onFailure: () => void, onLevel = (_level: number) => {}) {
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia || !window.AudioContext || !window.AudioWorkletNode) {
      throw new Error('Microphone needs a supported browser on HTTPS or localhost. You can still type an item.');
    }
    this.onDrain = onDrain;
    this.onLevel = onLevel;
    // Resume during the explicit click gesture; never defer until the provider is ready.
    const context = new AudioContext(); this.context = context;
    // The analyser observes only speaker playback, never microphone capture.
    this.analyser = context.createAnalyser?.();
    if (this.analyser) { this.analyser.fftSize = 256; this.analyser.connect(context.destination); }
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
      // Match the Go relay's RMS detector exactly. A more sensitive client
      // would flush valid playback while the server remains on the old turn.
      for (let i = 0; i < view.byteLength; i += 2) { const sample = view.getInt16(i, true); energy += sample * sample; }
      onFrame(data, Math.sqrt(energy / Math.max(1, view.byteLength / 2)) >= 500);
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
    // One small jitter buffer per uninterrupted playout, never per frame.
    this.nextAt = Math.max(context.currentTime + (this.sources.size ? 0 : .06), this.nextAt);
    if (this.nextAt - context.currentTime + duration > 1) throw new Error('Audio backlog');
    const buffer = context.createBuffer(1, frame.byteLength / 2, 24000);
    const channel = buffer.getChannelData(0), view = new DataView(frame);
    for (let i = 0; i < channel.length; i++) channel[i] = view.getInt16(i * 2, true) / 32768;
    const source = context.createBufferSource(); source.buffer = buffer; source.connect(this.analyser ?? context.destination);
    this.sources.add(source);
    source.onended = () => { this.sources.delete(source); source.disconnect(); if (!this.sources.size && !this.closed) { this.stopLevel(); this.onDrain(); } };
    source.start(this.nextAt); this.nextAt += duration;
    this.observeLevel();
  }
  private observeLevel() {
    if (!this.analyser || this.levelFrame !== undefined || typeof requestAnimationFrame !== 'function') return;
    const samples = new Float32Array(this.analyser.fftSize);
    const read = () => {
      this.levelFrame = undefined;
      if (this.closed || this.muted || !this.sources.size || document.hidden || window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) { this.stopLevel(); return; }
      this.analyser!.getFloatTimeDomainData(samples);
      const rms = Math.sqrt(samples.reduce((sum, sample) => sum + sample * sample, 0) / samples.length);
      const level = rms > .075 ? 1 : rms > .012 ? .5 : 0;
      if (level !== this.lastLevel) { this.lastLevel = level; this.onLevel(level); }
      this.levelFrame = requestAnimationFrame(read);
    };
    this.levelFrame = requestAnimationFrame(read);
  }
  private stopLevel() {
    if (this.levelFrame !== undefined) cancelAnimationFrame(this.levelFrame);
    this.levelFrame = undefined; this.lastLevel = 0; this.onLevel(0);
  }
  flush() {
    this.stopLevel();
    for (const source of this.sources) { source.onended = null; try { source.stop(); } catch { /* already stopped */ } source.disconnect(); }
    this.sources.clear(); this.nextAt = this.context?.currentTime ?? 0;
  }
  close() {
    this.closed = true;
    this.capture(false); this.flush();
    this.stream?.getTracks().forEach((track) => { track.onended = null; track.stop(); });
    this.node?.disconnect(); this.node?.port.close(); this.source?.disconnect(); this.silence?.disconnect();
    this.analyser?.disconnect(); this.analyser = undefined;
    void this.context?.close().catch(() => {});
    this.context = undefined; this.stream = undefined; this.node = undefined;
  }
}
