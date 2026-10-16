// Keep thresholds in sync with internal/voice/activity.go. PCM16 mono 16kHz.
export class InputActivity {
  private onset = 0;
  private silence = 0;
  active = false;
  reset() { this.onset = this.silence = 0; this.active = false; }
  push(bytes: number, voiced: boolean) {
    if (this.active) {
      this.silence = voiced ? 0 : this.silence + bytes;
      const ended = this.silence >= 11200;
      if (ended) this.reset();
      return { started: false, ended };
    }
    if (!voiced) { this.reset(); return { started: false, ended: false }; }
    this.onset += bytes;
    if (this.onset < 2560) return { started: false, ended: false };
    this.active = true; this.onset = 0;
    return { started: true, ended: false };
  }
}
