import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { get } from 'svelte/store';
import { VoiceClient } from '../../src/lib/voice/client';
import type { AudioEngine } from '../../src/lib/voice/audio';
import type { Api } from '../../src/lib/api';

let clients: VoiceClient[] = [];
beforeEach(() => vi.useFakeTimers());
afterEach(() => { clients.forEach(c => c.stop()); clients = []; vi.useRealTimers(); });
async function session(speakerMode = true) {
  let capture!: (frame: ArrayBuffer, voiced: boolean) => void, drain!: () => void;
  const audio: AudioEngine = {
    open: vi.fn(async (frame, onDrain) => { capture = frame; drain = onDrain; }),
    capture: vi.fn(), microphoneMuted: vi.fn(), speakerMuted: vi.fn(),
    play: vi.fn(), flush: vi.fn(), close: vi.fn()
  };
  const socket = { readyState: 1, bufferedAmount: 0, send: vi.fn(), close: vi.fn(), onmessage: null as any };
  const api = { ticket: async () => ({ session_id: 'test', ticket_expires_at: new Date(Date.now() + 30000).toISOString() }) } as Api;
  const client = new VoiceClient({ event: vi.fn(), turn: vi.fn() }, api, () => audio, () => socket as unknown as WebSocket, () => 'http://localhost');
  clients.push(client);
  if (!speakerMode) client.toggleSpeakerMode();
  const event = (type: string, extras = {}) => socket.onmessage({ data: JSON.stringify({ type, session_id: 'test', ...(['audio_start', 'audio_end', 'interrupted'].includes(type) ? {turn_id:'turn-1',generation_id:'generation-1'} : type === 'error' || type === 'turn_complete' ? {turn_id:'turn-1'} : {}), ...extras }) });
  const ready = () => event('ready', { expires_at: new Date(Date.now() + 600000).toISOString(), input_rate: 16000, output_rate: 24000 });
  await client.start(); ready();
  const pcm = () => capture(new Int16Array(1280).fill(2000).buffer, true); // sustained 80ms, above both VAD thresholds
  const binary = () => socket.onmessage({ data: new ArrayBuffer(640) });
  const reply = (turn = 1) => { event('audio_start', { turn_id: `turn-${turn}`, generation_id: `generation-${turn}` }); binary(); };
  const lastPCM = () => new Int16Array(socket.send.mock.calls.filter(([v]) => v instanceof ArrayBuffer).at(-1)![0]);
  return { client, audio, socket, event, ready, pcm, binary, reply, drain: () => drain(), lastPCM };
}

describe('speaker mode microphone guard', () => {
  it('starts on and retains an explicit off choice across Stop/restart', async () => {
    const s=await session();expect(get(s.client).speakerMode).toBe(true);
    s.client.toggleSpeakerMode();s.client.stop();await s.client.start();s.ready();
    expect(get(s.client).speakerMode).toBe(false);
  });
  it.each(['provider-first', 'drain-first'])('waits for both completion and drain plus acoustic tail (%s)', async order => {
    const s = await session(); s.reply(); const flushes = vi.mocked(s.audio.flush).mock.calls.length;
    s.pcm(); expect([...s.lastPCM()].every(n => n === 0)).toBe(true);
    expect(s.audio.flush).toHaveBeenCalledTimes(flushes);
    if (order === 'provider-first') s.event('audio_end'); else s.drain();
    vi.advanceTimersByTime(500); s.pcm(); expect(s.lastPCM()[0]).toBe(0);
    // A temporary queue drain between chunks is still protected.
    if (order === 'drain-first') { s.binary(); s.drain(); s.event('audio_end'); } else s.drain();
    expect(get(s.client).message).toBe('You can ask another question.');
    vi.advanceTimersByTime(249); s.pcm(); expect(s.lastPCM()[0]).toBe(0);
    vi.advanceTimersByTime(1); s.pcm(); expect(s.lastPCM()[0]).toBe(2000);
    expect(get(s.client).micHeld).toBe(false);
  });
  it('Interrupt seals late output and accepts fresh speech and the next reply on the same session', async () => {
    const s = await session(); s.reply(); s.client.interrupt();
    const played = vi.mocked(s.audio.play).mock.calls.length;
    s.binary(); s.event('audio_start'); s.binary(); expect(s.audio.play).toHaveBeenCalledTimes(played);
    s.pcm(); expect(s.lastPCM()[0]).toBe(0);
    vi.advanceTimersByTime(250); s.pcm(); expect(s.lastPCM()[0]).toBe(2000);
    s.reply(2); expect(s.audio.play).toHaveBeenCalledTimes(played + 1);
    s.pcm(); expect(s.lastPCM()[0]).toBe(0); expect(get(s.client).active).toBe(true);
  });
  it('mute sound releases the guard after the tail and manual microphone mute stays independent', async () => {
    const s = await session(); s.reply(); s.client.muteSpeaker();
    vi.advanceTimersByTime(250); s.pcm(); expect(s.lastPCM()[0]).toBe(2000);
    s.client.muteMicrophone(); s.pcm(); expect(s.lastPCM()[0]).toBe(0);
    expect(get(s.client).micMuted).toBe(true);
    s.client.muteMicrophone(); s.client.muteSpeaker(); s.reply(2);
    s.pcm(); expect(s.lastPCM()[0]).toBe(0);
  });
  it('unmuting sound during the same reply waits for fresh provider completion', async () => {
    const s = await session(); s.reply(); s.client.muteSpeaker();
    vi.advanceTimersByTime(250); s.client.muteSpeaker(); s.binary(); s.drain();
    vi.advanceTimersByTime(500); s.pcm(); expect(s.lastPCM()[0]).toBe(0);
    s.event('audio_end'); vi.advanceTimersByTime(250); s.pcm(); expect(s.lastPCM()[0]).toBe(2000);
  });
  it('timeout clears the guard and Stop/restart retains the choice without stale playback state', async () => {
    const s = await session(); s.reply();
    s.event('error', { code: 'TURN_TIMEOUT', message: 'timeout', retryable: true });
    vi.advanceTimersByTime(250); s.pcm(); expect(s.lastPCM()[0]).toBe(2000);
    s.reply(2); s.client.stop(); expect(get(s.client)).toMatchObject({ speakerMode: true, micHeld: false, active: false });
    await s.client.start(); s.ready(); s.pcm(); expect(s.lastPCM()[0]).toBe(2000);
  });
  it('mode off preserves sustained-speech interruption; enabling during a reply blocks feedback', async () => {
    const s = await session(false); s.reply();
    const before = vi.mocked(s.audio.flush).mock.calls.length;
    s.pcm(); expect(s.lastPCM()[0]).toBe(2000); expect(s.audio.flush).toHaveBeenCalledTimes(before + 1);
    s.reply(2); s.client.toggleSpeakerMode(); s.pcm(); expect(s.lastPCM()[0]).toBe(0);
    s.client.toggleSpeakerMode(); s.pcm(); expect(s.lastPCM()[0]).toBe(2000);
  });
  it('muted sound never holds microphone input when there is no audible playback', async () => {
    const s = await session(); s.client.muteSpeaker(); s.reply();
    s.pcm(); expect(s.lastPCM()[0]).toBe(2000); expect(get(s.client).micHeld).toBe(false);
  });
});
