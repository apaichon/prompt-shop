/** Merge Gemini Live partial or cumulative transcript frames into one turn. */
export function mergeTranscriptChunk(previous: string, chunk: string): string {
  const prior = (previous || '').trim();
  const next = (chunk || '').trim();
  if (!next) return prior;
  if (!prior) return next;
  if (next.startsWith(prior)) return next;
  if (prior.startsWith(next) || (prior.includes(next) && next.length < prior.length)) return prior;
  if (next.includes(prior) && prior.length < next.length) return next;

  for (let size = Math.min(prior.length, next.length, 48); size >= 4; size--) {
    if (prior.slice(-size) === next.slice(0, size)) return prior + next.slice(size);
  }
  const thai = /[\u0E00-\u0E7F]/.test(prior) || /[\u0E00-\u0E7F]/.test(next);
  if (thai) return prior + next;
  const space = !/[\s.,!?;:)]$/.test(prior) && !/^[.,!?;:(]/.test(next);
  return space ? `${prior} ${next}` : prior + next;
}
