import type { VoicePhase } from './voice/client';

// Public presentation settings. Provider credentials/model/voice stay in ADK.
export const shopBrand = { name: 'Monti Store', assistant: 'Monti' };
export const avatar = { src: '/avatar/monti/atlas.webp', columns: 3, rows: 2, width: 672, height: 448 };
export function avatarPose(phase: VoicePhase, outputLevel = 0) {
  if (phase === 'speaking' && outputLevel > .05) return outputLevel > .6 ? 4 : 3;
  if (phase === 'listening' || phase === 'interrupted') return 1;
  if (phase === 'connecting' || phase === 'thinking') return 2;
  return phase === 'error' ? 5 : 0;
}
