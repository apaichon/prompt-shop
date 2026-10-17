import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { get } from 'svelte/store';
import { VoiceClient } from '../../src/lib/voice/client';
import type { AudioEngine } from '../../src/lib/voice/audio';
import type { Api } from '../../src/lib/api';
import events from '../fixtures/live-events.json';

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
  const silence=()=>{for(let i=0;i<18;i++)capture(new ArrayBuffer(640),false);};
  return { client, audio, socket, event, ready, pcm, silence, binary, reply, drain: () => drain(), lastPCM };
}

describe('speaker mode microphone guard', () => {
  it('protects a pending lookup from noise before the first reply audio', async () => {
    const s=await session();s.pcm();
    s.event('interrupted');
    s.event('input_transcript',{turn_id:'turn-1',text:'Where is beef?',final:true});
    s.silence();
    const flushes=vi.mocked(s.audio.flush).mock.calls.length;
    s.pcm();
    expect(s.lastPCM()[0]).toBe(0);
    expect(s.audio.flush).toHaveBeenCalledTimes(flushes);
    expect(get(s.client)).toMatchObject({input:'Where is beef?',micHeld:true,phase:'thinking'});
    s.reply();expect(s.audio.play).toHaveBeenCalledOnce();
    s.event('turn_complete');s.drain();vi.advanceTimersByTime(250);
    s.pcm();expect(s.lastPCM()[0]).toBe(2000);
  });

  it('ends noisy listening when the verified item results arrive', async () => {
    const s=await session();s.pcm();s.event('interrupted');
    s.event('candidates',{...events.find(e=>e.type==='candidates'),session_id:'test'});
    expect(get(s.client)).toMatchObject({phase:'thinking',micHeld:true});
    // Sustained non-speech input becomes silence on the wire so Go also ends
    // its active capture; the upcoming reply retains the same turn identity.
    for(let i=0;i<5;i++)s.pcm();
    expect(s.lastPCM()[0]).toBe(0);
    s.reply();expect(s.audio.play).toHaveBeenCalledOnce();
  });
  it.each(['interrupt','timeout','stop'])('releases the pending-reply hold on %s', async action => {
    const s=await session();s.pcm();s.event('interrupted');s.silence();
    expect(get(s.client).micHeld).toBe(true);
    if(action==='interrupt')s.client.interrupt();
    else if(action==='timeout')s.event('error',{code:'TURN_TIMEOUT',message:'timeout',retryable:true});
    else {s.client.stop();await s.client.start();s.ready();}
    vi.advanceTimersByTime(250);s.pcm();
    expect(s.lastPCM()[0]).toBe(2000);
    expect(get(s.client).micHeld).toBe(false);
  });
  it('protects a clicked choice while its route is loading and releases on a stale choice', async () => {
    const s=await session();expect(s.client.select('search-1','beef-steak')).toBe(true);
    s.pcm();expect(s.lastPCM()[0]).toBe(0);
    s.event('error',{code:'STALE_SELECTION',message:'stale',retryable:true});
    s.pcm();expect(s.lastPCM()[0]).toBe(2000);expect(get(s.client).micHeld).toBe(false);
  });
  it('speaker mode off allows another utterance during response preparation', async () => {
    const s=await session(false);s.pcm();s.event('interrupted');s.silence();s.pcm();
    expect(s.lastPCM()[0]).toBe(2000);expect(get(s.client).micHeld).toBe(false);
  });
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
