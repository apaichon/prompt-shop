// PCM conversion adapted from Monti Jarvis; see /MONTI-LICENSE.txt.
// Streaming weighted averaging retains fractional source frames at 44.1 kHz.
class PcmCapture extends AudioWorkletProcessor {
  constructor() {
    super();
    this.ratio = sampleRate / 16000;
    this.sum = 0; this.weight = 0; this.offset = 0;
    this.frame = new ArrayBuffer(3200);
    this.view = new DataView(this.frame);
    this.enabled = false;
    this.port.onmessage = ({ data }) => {
      this.enabled = data === 'start';
      this.sum = 0; this.weight = 0; this.offset = 0;
    };
  }
  process(inputs) {
    const samples = inputs[0]?.[0];
    if (!this.enabled || !samples) return true;
    for (const sample of samples) {
      let left = 1;
      while (left > 1e-9) {
        const take = Math.min(left, this.ratio - this.weight);
        this.sum += sample * take; this.weight += take; left -= take;
        if (this.weight >= this.ratio - 1e-9) {
          const value = Math.max(-1, Math.min(1, this.sum / this.ratio));
          this.view.setInt16(this.offset, Math.round(value < 0 ? value * 32768 : value * 32767), true);
          this.offset += 2; this.sum = 0; this.weight = 0;
          if (this.offset === 3200) {
            this.port.postMessage(this.frame, [this.frame]);
            this.frame = new ArrayBuffer(3200); this.view = new DataView(this.frame); this.offset = 0;
          }
        }
      }
    }
    return true;
  }
}
registerProcessor('pcm-capture', PcmCapture);
