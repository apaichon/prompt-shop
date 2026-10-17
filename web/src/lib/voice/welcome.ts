import { BrowserAudio } from './audio';

// Transient ownership handoff from the explicit login gesture to the shopper page.
// No account identifiers, storage or credentials are involved.
let pending: BrowserAudio | undefined;
let cancelCurrent: (() => void) | undefined;
export function prepareWelcome() {
  const audio = new BrowserAudio(undefined, true);
  void audio.prepareOutput();
  return audio;
}
export function queueWelcome(audio: BrowserAudio) { cancelWelcome(); pending = audio; }
export function takeWelcome() { const audio = pending; pending = undefined; return audio; }
export function registerWelcomeCancel(cancel: () => void) {
  cancelCurrent = cancel;
  return () => { if (cancelCurrent === cancel) cancelCurrent = undefined; };
}
export function cancelWelcome() { pending?.close(); pending = undefined; cancelCurrent?.(); }
