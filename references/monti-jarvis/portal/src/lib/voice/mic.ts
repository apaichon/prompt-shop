/**
 * Mic / secure-context helpers for tenant preview voice.
 * Browsers expose navigator.mediaDevices only in a secure context
 * (https:// or http://localhost / http://127.0.0.1 — not http://*.local).
 */

export function micAvailabilityError(): string | null {
  if (typeof window === 'undefined') return 'Microphone unavailable';
  if (!window.isSecureContext) {
    const host = location.hostname || 'this host';
    const port = location.port ? `:${location.port}` : '';
    return (
      `Microphone needs a secure context (HTTPS or localhost). ` +
      `This page is ${location.protocol}//${host}${port} — browsers leave mediaDevices undefined here. ` +
      `Open Preview as http://localhost${port || ':8091'}/tenant/preview ` +
      `(or use HTTPS), not http://${host}.`
    );
  }
  if (!navigator.mediaDevices || typeof navigator.mediaDevices.getUserMedia !== 'function') {
    return (
      'Microphone API unavailable (navigator.mediaDevices missing). ' +
      'Allow microphone for this site, or open Monti on HTTPS/localhost.'
    );
  }
  return null;
}

/** Request mic permission; throws with a clear message on failure. */
export async function requestMicrophone(): Promise<MediaStream> {
  const blocked = micAvailabilityError();
  if (blocked) throw new Error(blocked);

  try {
    return await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true
      }
    });
  } catch (err) {
    const name = err instanceof DOMException ? err.name : '';
    if (name === 'NotAllowedError' || name === 'PermissionDeniedError') {
      throw new Error(
        'Microphone permission denied. Click the lock icon in the address bar, allow mic for this site, then try Start voice again.'
      );
    }
    if (name === 'NotFoundError' || name === 'DevicesNotFoundError') {
      throw new Error('No microphone found. Plug in a mic or check system sound settings.');
    }
    if (name === 'NotReadableError' || name === 'TrackStartError') {
      throw new Error('Microphone is busy (used by another app). Close other apps and try again.');
    }
    const msg = err instanceof Error ? err.message : 'Microphone permission denied';
    throw new Error(msg);
  }
}

/** Localhost URL for the same path (for UI copy / open link). */
export function localhostPreviewHref(extra?: Record<string, string>): string {
  if (typeof window === 'undefined') return 'http://localhost:8091/tenant/preview';
  const port = location.port || '8091';
  const path = location.pathname || '/tenant/preview';
  const u = new URL(`http://localhost:${port}${path}`);
  if (extra) {
    for (const [k, v] of Object.entries(extra)) {
      if (v) u.searchParams.set(k, v);
    }
  }
  return u.toString();
}

/** True when host is not a browser secure-context loopback. */
export function isInsecureCustomHost(): boolean {
  if (typeof window === 'undefined') return false;
  if (window.isSecureContext) return false;
  const h = (location.hostname || '').toLowerCase();
  return h !== 'localhost' && h !== '127.0.0.1' && h !== '[::1]';
}
