import { describe, expect, it, vi, afterEach } from 'vitest';
import { get } from 'svelte/store';
import { Api, ApiError } from '../../src/lib/api';
import { Portal } from '../../src/lib/portal';
import { eventSchema, mapSchema, routeSchema, routeMatchesMap, searchSchema, type VoiceEvent } from '../../src/lib/contracts';
import { EventGate } from '../../src/lib/voice/gate';
import { VoiceClient } from '../../src/lib/voice/client';
import type { AudioEngine } from '../../src/lib/voice/audio';
import map from '../fixtures/store-map.json';
import route from '../fixtures/route-response.json';
import search from '../fixtures/search-response.json';
import events from '../fixtures/live-events.json';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const event = (type: string, extras = {}) => eventSchema.parse({ ...events.find((e) => e.type === type), ...extras });
const deferred = <T>() => { let resolve!: (value: T) => void; const promise = new Promise<T>((r) => { resolve = r; }); return { promise, resolve }; };
const response = (body: unknown, status = 200, headers = {}) => new Response(JSON.stringify(body), { status, headers });

describe('factual contracts and map safety', () => {
  it('accepts foundation public fixtures and the gateway opaque search ID', () => {
    expect(searchSchema.parse(search).candidates).toHaveLength(1);
    expect(mapSchema.parse(map).nodes.length).toBeGreaterThan(1);
    expect(routeMatchesMap(routeSchema.parse(route), mapSchema.parse(map))).toBe(true);
    expect(event('candidates', { search_id: 'A_b-09opaque' })).toBeTruthy();
  });
  it('rejects arbitrary actions, missing facts, excessive candidates and mismatched geometry', () => {
    expect(eventSchema.safeParse({ type: 'navigate', session_id: 'fixture-session', url: 'https://other.test' }).success).toBe(false);
    expect(searchSchema.safeParse({ ...search, candidates: [{ name: 'made up' }] }).success).toBe(false);
    expect(searchSchema.safeParse({ ...search, candidates: Array(4).fill(search.candidates[0]) }).success).toBe(false);
    expect(routeMatchesMap({ ...routeSchema.parse(route), map_version: 99 }, mapSchema.parse(map))).toBe(false);
    expect(routeMatchesMap({ ...routeSchema.parse(route), points: [{ x: 99, y: 99 }] }, mapSchema.parse(map))).toBe(false);
  });
});

describe('session, turn and generation gates', () => {
  it('allows a new-turn interruption marker, then its valid audio; rejects old events', () => {
    const gate = new EventGate(); gate.start('fixture-session');
    expect(gate.accept(event('interrupted')).newTurn).toBe(true);
    expect(gate.accept(event('audio_start')).accepted).toBe(true);
    gate.accept(event('interrupted', { turn_id: 'turn-2', generation_id: 'generation-2' }));
    expect(gate.accept(event('candidates')).accepted).toBe(false);
    expect(gate.accept(event('audio_start')).accepted).toBe(false);
    expect(gate.accept(event('audio_start', { turn_id: 'turn-2', generation_id: 'generation-2' })).accepted).toBe(true);
  });
  it('invalidates same-turn interruption output and everything after Stop', () => {
    const gate = new EventGate(); gate.start('fixture-session'); gate.accept(event('audio_start'));
    gate.accept(event('interrupted'));
    expect(gate.accept(event('route')).accepted).toBe(false);
    expect(gate.accept(event('audio_start')).accepted).toBe(false);
    gate.stop(); expect(gate.accept(event('ready')).accepted).toBe(false);
    gate.start('different-session'); expect(gate.accept(event('candidates')).accepted).toBe(false);
  });
  it('blocks old audio while waiting for a server turn after explicit selection', () => {
    const gate = new EventGate(); gate.start('fixture-session'); gate.accept(event('audio_start'));
    gate.anticipateTurn(); expect(gate.generation).toBeNull();
    expect(gate.accept(event('route')).accepted).toBe(false);
  });
});

describe('HTTP and asynchronous presentation', () => {
  it('uses same-origin POST, no credentials in URLs, and structured rate limits', async () => {
    const fetcher = vi.fn(async () => response({ error: { code: 'RATE_LIMITED', message: 'wait', retryable: true }, request_id: 'r' }, 429, { 'Retry-After': '12' }));
    await expect(new Api(fetcher).search('milk')).rejects.toMatchObject({ code: 'RATE_LIMITED', retryAfter: 12 });
    expect(fetcher.mock.calls[0]).toMatchObject(['/api/search', { method: 'POST', credentials: 'same-origin', body: '{"query":"milk","language":"en-US"}' }]);
  });
  it('ignores old REST responses after a newer search', async () => {
    const old = deferred<Response>(); let count = 0;
    const api = new Api(vi.fn(() => ++count === 1 ? old.promise : Promise.resolve(response({ ...search, query: 'rice', candidates: [] }))));
    const portal = new Portal(api);
    const pending = portal.search('milk'); await portal.search('rice');
    old.resolve(response(search)); await pending;
    expect(get(portal).query).toBe('rice'); expect(get(portal).candidates).toHaveLength(0); portal.destroy();
  });
  it('retries a stale map and route once, then refuses mismatched overlays', async () => {
    let routeCalls = 0, mapCalls = 0;
    const api = new Api(vi.fn(async (path) => {
      if (path === '/api/search') return response({...search, ambiguous:true});
      if (path === '/api/store-map') { mapCalls++; return response({ ...map, map_version: mapCalls }); }
      routeCalls++; return response({ ...route, map_version: 3 });
    }));
    const portal = new Portal(api); await portal.loadMap(); await portal.search('milk'); await portal.choose(search.candidates[0]);
    expect(mapCalls).toBe(2); expect(routeCalls).toBe(2); expect(get(portal).route).toBeNull();
    expect(get(portal).routeMessage).toContain('Map updated'); expect(get(portal).location?.shelf.label).toBe('Shelf 3'); portal.destroy();
  });
  it('retains truthful location without inventing a route on 422', async () => {
    const api = new Api(vi.fn(async (path) => path === '/api/search' ? response(search) : response({ error: { code: 'ROUTE_UNAVAILABLE', message: 'not mapped', retryable: false, details: { product: route.product } }, request_id: 'r' }, 422)));
    const portal = new Portal(api); await portal.search('milk'); await portal.choose(search.candidates[0]);
    expect(get(portal).location?.shelf.label).toBe('Shelf 3'); expect(get(portal).route).toBeNull(); expect(get(portal).routeMessage).toContain('not available'); portal.destroy();
  });
  it('does not commit a route whose delayed map arrives after Stop', async () => {
    const delayed = deferred<Response>();
    const api = new Api(vi.fn(async (path) => path === '/api/search' ? response(search) : path === '/api/routes' ? response(route) : delayed.promise));
    const portal = new Portal(api); const pending = portal.search('milk');
    await Promise.resolve(); await Promise.resolve(); portal.stopVoice(); delayed.resolve(response(map)); await pending;
    expect(get(portal).route).toBeNull(); portal.destroy();
  });
});

class FakeAudio implements AudioEngine {
  frame?: (frame: ArrayBuffer, voiced: boolean) => void;
  drain?: () => void;
  open = vi.fn<AudioEngine['open']>(async (frame, drain) => { this.frame = frame; this.drain = drain; });
  capture = vi.fn(); microphoneMuted = vi.fn(); speakerMuted = vi.fn(); play = vi.fn(); flush = vi.fn(); close = vi.fn();
}
class Socket {
  readyState = 1; bufferedAmount = 0; binaryType = '';
  onmessage: ((e: { data: unknown }) => void) | null = null; onerror: (() => void) | null = null; onclose: (() => void) | null = null;
  send = vi.fn(); close = vi.fn();
  receive(data: unknown) { this.onmessage?.({ data: typeof data === 'object' && !(data instanceof ArrayBuffer) ? JSON.stringify(data) : data }); }
}
function voiceFixture() {
  const audio = new FakeAudio(), socket = new Socket(), callbacks = { event: vi.fn(), turn: vi.fn() };
  const api = new Api(vi.fn(async () => response({ session_id: 'fixture-session', ticket_expires_at: new Date(Date.now() + 30000).toISOString(), ws_path: '/ws/voice' }, 201)));
  const voice = new VoiceClient(callbacks, api, () => audio, () => socket as unknown as WebSocket, () => 'https://portal.test');
  const ready = () => socket.receive(event('ready', { expires_at: new Date(Date.now() + 600000).toISOString() }));
  return { voice, audio, socket, callbacks, ready };
}
afterEach(() => vi.useRealTimers());
describe('voice lifecycle and bounded transport', () => {
  it('keeps capture and socket alive after a failed turn and rejects its late output', async () => {
    const {voice,audio,socket,callbacks,ready}=voiceFixture(); await voice.start(); ready();
    socket.receive(event('audio_start')); socket.receive(new ArrayBuffer(3200));
    socket.receive(event('error',{code:'TURN_TIMEOUT',message:'unsafe provider detail',retryable:true}));
    expect(get(voice).active).toBe(true); expect(get(voice).phase).toBe('listening');
    expect(get(voice).message).toContain('please ask again'); expect(get(voice).message).not.toContain('unsafe');
    expect(audio.close).not.toHaveBeenCalled(); expect(socket.close).not.toHaveBeenCalled();
    socket.receive(event('audio_start')); socket.receive(new ArrayBuffer(3200)); socket.receive(event('candidates'));
    expect(audio.play).toHaveBeenCalledTimes(1); expect(callbacks.event).not.toHaveBeenCalled();
    socket.receive(event('interrupted',{turn_id:'turn-2',generation_id:'generation-2'}));
    socket.receive(event('audio_start',{turn_id:'turn-2',generation_id:'generation-2'})); socket.receive(new ArrayBuffer(3200));
    expect(audio.play).toHaveBeenCalledTimes(2); expect(get(voice).phase).toBe('speaking');
    voice.stop(); expect(audio.close).toHaveBeenCalledOnce();
  });

  it('ignores an old playback-level callback after Stop', async () => {
    const f=voiceFixture(); let level: (value:number)=>void = () => {};
    f.audio.open.mockImplementationOnce(async (_frame, _drain, _failure, onLevel) => { level=onLevel ?? (() => {}); });
    await f.voice.start(); f.ready(); level(1); expect(get(f.voice).outputLevel).toBe(1);
    f.voice.stop(); level(1); expect(get(f.voice).outputLevel).toBe(0);
  });
  it('shows listening for a new utterance and interruption only for a stopped response', async () => {
    const { voice, socket, ready } = voiceFixture(); await voice.start(); ready();
    socket.receive(event('interrupted'));
    expect(get(voice).phase).toBe('listening'); expect(get(voice).message).toBe('Listening to you…');
    socket.receive(event('audio_start')); socket.receive(new ArrayBuffer(3200));
    socket.receive(event('interrupted'));
    expect(get(voice).phase).toBe('interrupted'); voice.stop();
  });
  it('starts capture after ready only; captions cannot search; Stop invalidates saved callbacks', async () => {
    const { voice, audio, socket, callbacks, ready } = voiceFixture();
    expect(audio.open).not.toHaveBeenCalled(); await voice.start(); expect(audio.capture).not.toHaveBeenCalled(); ready();
    expect(audio.capture).toHaveBeenCalledWith(true);
    socket.receive(event('input_transcript')); expect(get(voice).input).toBe('Whole milk'); expect(callbacks.event).not.toHaveBeenCalled();
    const late = socket.onmessage!; voice.stop(); late({ data: JSON.stringify(event('candidates')) });
    expect(callbacks.event).not.toHaveBeenCalled(); expect(audio.close).toHaveBeenCalled(); expect(get(voice).input).toBe('');
  });
  it('flushes buffered audio on interruption and drops later old binary frames', async () => {
    const { voice, audio, socket, ready } = voiceFixture(); await voice.start(); ready();
    socket.receive(event('audio_start')); socket.receive(new ArrayBuffer(3200)); expect(audio.play).toHaveBeenCalledTimes(1);
    socket.receive(event('interrupted')); socket.receive(new ArrayBuffer(3200)); socket.receive(event('audio_start')); socket.receive(new ArrayBuffer(3200));
    expect(audio.play).toHaveBeenCalledTimes(1); expect(audio.flush).toHaveBeenCalled(); voice.stop();
  });
  it('rejects an outgoing audio backlog and releases resources', async () => {
    const { voice, audio, socket, ready } = voiceFixture(); await voice.start(); ready(); socket.bufferedAmount = 32000;
    audio.frame!(new ArrayBuffer(3200), true); expect(get(voice).active).toBe(false); expect(audio.close).toHaveBeenCalled();
  });
  it('closes on denied microphone, disconnect and output failure without automatic reconnect', async () => {
    const a = voiceFixture(); a.audio.open.mockRejectedValueOnce(new Error('denied')); await a.voice.start(); expect(get(a.voice).phase).toBe('error'); expect(a.audio.close).toHaveBeenCalled();
    const b = voiceFixture(); await b.voice.start(); b.ready(); b.socket.onclose!(); expect(get(b.voice).active).toBe(false);
    const c = voiceFixture(); await c.voice.start(); c.ready(); c.audio.play.mockImplementation(() => { throw new Error('backlog'); }); c.socket.receive(event('audio_start')); c.socket.receive(new ArrayBuffer(3200)); expect(get(c.voice).phase).toBe('error');
  });
  it('handles late microphone resolution after Stop', async () => {
    const f = voiceFixture(), permission = deferred<void>(); f.audio.open.mockImplementationOnce(() => permission.promise);
    const pending = f.voice.start(); f.voice.stop(); permission.resolve(); await pending;
    expect(get(f.voice).active).toBe(false); expect(f.socket.onmessage).toBeNull(); expect(f.audio.close).toHaveBeenCalled();
  });
  it('bounds setup, meaningful idle and session lifetime independently of pongs', async () => {
    vi.useFakeTimers(); const first = voiceFixture(); await first.voice.start(); await vi.advanceTimersByTimeAsync(30001);
    expect(get(first.voice).message).toContain('too long');
    const idle = voiceFixture(); await idle.voice.start(); idle.ready();
    for (let i = 0; i < 6; i++) { await vi.advanceTimersByTimeAsync(10000); idle.socket.receive(event('pong')); }
    expect(get(idle.voice).message).toContain('inactivity');
    const active = voiceFixture(); expect(get(active.voice)).toMatchObject({speakerMode:true,remaining:600}); await active.voice.start(); active.ready();
    expect(get(active.voice).remaining).toBe(600);
    for (let i = 0; i < 60; i++) { active.audio.frame!(new ArrayBuffer(3200), true); active.socket.receive(event('pong')); await vi.advanceTimersByTimeAsync(10000); if(i===29)expect(get(active.voice).active).toBe(true); }
    expect(get(active.voice).message).toContain('session ended');
  });
});

describe('real worklet PCM code', () => {
  it.each([16000, 44100, 48000])('resamples %i Hz to bounded 20ms PCM16LE frames without drift', (sampleRate) => {
    let Processor: any; const frames: ArrayBuffer[] = [];
    class Base { port = { onmessage: null as any, postMessage: (frame: ArrayBuffer) => frames.push(frame) }; }
    vm.runInNewContext(readFileSync(new URL('../../static/pcm-capture.js', import.meta.url), 'utf8'), {
      AudioWorkletProcessor: Base, sampleRate, registerProcessor: (_name: string, ctor: unknown) => { Processor = ctor; }, ArrayBuffer, DataView, Math
    });
    const processor = new Processor(); processor.process([[new Float32Array(128).fill(.5)]]); expect(frames).toHaveLength(0);
    processor.port.onmessage({ data: 'start' });
    for (let offset = 0; offset < sampleRate; offset += 128) processor.process([[new Float32Array(Math.min(128, sampleRate - offset)).fill(.5)]]);
    expect(frames).toHaveLength(50); expect(frames.every((f) => f.byteLength === 640)).toBe(true);
    expect(new DataView(frames[0]).getInt16(0, true)).toBe(16384);
    processor.port.onmessage({ data: 'stop' }); processor.process([[new Float32Array(128)]]); expect(frames).toHaveLength(50);
  });
});


it('returns to listening when audio drained before the end marker', async () => {
  const f = voiceFixture(); await f.voice.start(); f.ready();
  f.socket.receive(event('audio_start')); f.socket.receive(new ArrayBuffer(3200)); f.audio.drain!();
  expect(get(f.voice).phase).toBe('speaking'); f.socket.receive(event('audio_end'));
  expect(get(f.voice).phase).toBe('listening'); f.voice.stop();
});
it('ignores an older generation start within the current turn', () => {
  const gate = new EventGate(); gate.start('fixture-session');
  gate.accept(event('audio_start', { generation_id: 'generation-2' }));
  expect(gate.accept(event('audio_start')).accepted).toBe(false);
  expect(gate.generation).toBe('generation-2');
});

it('failed selection send reports failure and still releases microphone and socket', async () => {
  const f = voiceFixture(); await f.voice.start(); f.ready();
  f.socket.send.mockImplementation(() => { throw new Error('closed transport'); });
  expect(f.voice.select('search-1', 'milk-whole-1l')).toBe(false);
  expect(get(f.voice).phase).toBe('error'); expect(f.audio.close).toHaveBeenCalled();
  expect(f.socket.close).toHaveBeenCalled();
});


it('a single loud 20ms frame cannot cancel a reply; sustained speech can',async()=>{
 const f=voiceFixture();f.voice.toggleSpeakerMode();await f.voice.start();f.ready();
 f.socket.receive(event('audio_start'));f.socket.receive(new ArrayBuffer(3200));
 const before=f.audio.flush.mock.calls.length;
 f.audio.frame!(new ArrayBuffer(640),true);
 expect(f.audio.flush.mock.calls.length).toBe(before);
 f.audio.frame!(new ArrayBuffer(640),false);
 expect(get(f.voice).phase).toBe('speaking');
 for(let i=0;i<4;i++)f.audio.frame!(new ArrayBuffer(640),true);
 expect(f.audio.flush.mock.calls.length).toBe(before+1);
 expect(get(f.voice).phase).toBe('listening');f.voice.stop();
});


describe('one-shot native welcome',()=>{
 it.each(['provider-first','drain-first'])('does not capture and waits for completion AND drain (%s)',async order=>{
  const f=voiceFixture();await f.voice.start(f.audio,true);f.ready();
  expect(f.audio.capture).not.toHaveBeenCalled();
  const sent=f.socket.send.mock.calls.map(([v])=>typeof v==='string'?JSON.parse(v):null);
  expect(sent.some(v=>v?.type==='text'&&v.text.includes("I'm Monti"))).toBe(true);
  f.socket.receive(event('audio_start'));f.socket.receive(new ArrayBuffer(640));
  if(order==='provider-first')f.socket.receive(event('turn_complete'));else f.audio.drain!();
  expect(get(f.voice).active).toBe(true);
  if(order==='provider-first')f.audio.drain!();else f.socket.receive(event('turn_complete'));
  expect(get(f.voice).active).toBe(false);expect(f.audio.close).toHaveBeenCalledOnce();expect(f.socket.close).toHaveBeenCalledOnce();
 });
 it('bounds welcome to25seconds and cancels late output after explicit Stop',async()=>{
  vi.useFakeTimers();const f=voiceFixture();await f.voice.start(f.audio,true);f.ready();
  await vi.advanceTimersByTimeAsync(25000);expect(get(f.voice).active).toBe(false);expect(f.audio.capture).not.toHaveBeenCalled();
  const g=voiceFixture();await g.voice.start(g.audio,true);g.ready();const late=g.socket.onmessage!;g.voice.stop();late({data:JSON.stringify(event('audio_start'))});late({data:new ArrayBuffer(640)});expect(g.audio.play).not.toHaveBeenCalled();
 });
 it('keeps recovery visible when the greeting control cannot send or no audio arrives',async()=>{
  const f=voiceFixture();await f.voice.start(f.audio,true);f.socket.send.mockImplementationOnce(()=>{throw new Error('closed')});f.ready();expect(get(f.voice)).toMatchObject({active:false,phase:'error'});expect(get(f.voice).message).toContain('Play welcome');
  const g=voiceFixture();await g.voice.start(g.audio,true);g.ready();g.socket.receive(event('turn_complete'));expect(get(g.voice)).toMatchObject({active:false,phase:'error'});
 });
 it('never admits a provider when prepared output is blocked and closes on a failed greeting turn',async()=>{
  const f=voiceFixture();f.audio.open.mockRejectedValueOnce(new Error('blocked'));await f.voice.start(f.audio,true);expect(f.socket.onmessage).toBeNull();expect(f.audio.close).toHaveBeenCalled();
  const g=voiceFixture();await g.voice.start(g.audio,true);g.ready();g.socket.receive(event('error',{code:'TURN_TIMEOUT',message:'timeout',retryable:true}));expect(get(g.voice).active).toBe(false);expect(get(g.voice).message).toContain('Play welcome');
 });
});


describe('quiet summary follow-up',()=>{
 const snapshot={type:'summary',session_id:'fixture-session',turn_id:'turn-1',entries:[{query:'milk',status:'confirmed',catalog_version:1,products:[search.candidates[0]]}],truncated:false,requested:false};
 const texts=(f:ReturnType<typeof voiceFixture>)=>f.socket.send.mock.calls.map(([v])=>typeof v==='string'?JSON.parse(v):null).filter(v=>v?.type==='text');
 async function reply(f:ReturnType<typeof voiceFixture>,turn=1){f.socket.receive(event('audio_start',{turn_id:`turn-${turn}`,generation_id:`generation-${turn}`}));f.socket.receive(new ArrayBuffer(640));f.socket.receive(event('turn_complete',{turn_id:`turn-${turn}`}));}
 it('requires completion, drain and ten quiet seconds; offers once without summarizing or looping on decline',async()=>{
  vi.useFakeTimers();const f=voiceFixture();await f.voice.start();f.ready();f.socket.receive(snapshot);await reply(f);
  await vi.advanceTimersByTimeAsync(12000);expect(texts(f)).toHaveLength(0);f.audio.drain!();
  await vi.advanceTimersByTimeAsync(9999);f.socket.receive(event('pong'));expect(texts(f)).toHaveLength(0);
  await vi.advanceTimersByTimeAsync(501);expect(texts(f)).toHaveLength(1);expect(texts(f)[0].text).toContain('Do not summarize yet');expect(get(f.voice).summaryOffer).toBe(true);
  f.socket.receive(event('interrupted',{turn_id:'turn-2',generation_id:'generation-2'}));await reply(f,2);f.audio.drain!();
  await vi.advanceTimersByTimeAsync(11000);f.socket.receive(event('pong'));expect(texts(f)).toHaveLength(1);
  f.socket.receive(event('interrupted',{turn_id:'turn-3',generation_id:'generation-3'}));f.socket.receive(event('input_transcript',{turn_id:'turn-3',text:'No thanks',final:true}));await reply(f,3);f.audio.drain!();
  await vi.advanceTimersByTimeAsync(11000);f.socket.receive(event('pong'));expect(texts(f)).toHaveLength(1);expect(get(f.voice).summaryOffer).toBe(false);f.voice.stop();
 });
 it('quiet starts after a drained reply, ignores speech/noise and mute time, and only new lookup rearms',async()=>{
  vi.useFakeTimers();const f=voiceFixture();await f.voice.start();f.ready();f.socket.receive(snapshot);await reply(f);f.audio.drain!();await vi.advanceTimersByTimeAsync(6000);
  f.audio.frame!(new ArrayBuffer(640),true);await vi.advanceTimersByTimeAsync(6000);expect(texts(f)).toHaveLength(0);
  f.voice.muteMicrophone();await vi.advanceTimersByTimeAsync(11000);f.socket.receive(event('pong'));expect(texts(f)).toHaveLength(0);f.voice.muteMicrophone();
  await vi.advanceTimersByTimeAsync(10000);expect(texts(f)).toHaveLength(1);f.voice.stop();await vi.advanceTimersByTimeAsync(12000);expect(texts(f)).toHaveLength(1);
 });
 it('never offers on welcome, empty session, incomplete turn, errors or near expiry',async()=>{
  vi.useFakeTimers();const f=voiceFixture();await f.voice.start();f.ready();await reply(f);f.audio.drain!();await vi.advanceTimersByTimeAsync(11000);expect(texts(f)).toHaveLength(0);
  f.socket.receive(snapshot);f.socket.receive(event('error',{code:'TURN_TIMEOUT',message:'timeout',retryable:true}));await vi.advanceTimersByTimeAsync(11000);f.socket.receive(event('pong'));expect(texts(f)).toHaveLength(0);f.voice.stop();
  const g=voiceFixture();await g.voice.start(g.audio,true);g.ready();g.socket.receive(snapshot);await reply(g);g.audio.drain!();await vi.advanceTimersByTimeAsync(11000);expect(texts(g)).toHaveLength(1);expect(texts(g)[0].text).toContain("I'm Monti");
  const h=voiceFixture();await h.voice.start();h.socket.receive(event('ready',{expires_at:new Date(Date.now()+25000).toISOString()}));h.socket.receive(snapshot);await reply(h);h.audio.drain!();await vi.advanceTimersByTimeAsync(11000);expect(texts(h)).toHaveLength(0);h.voice.stop();
 });
 it('sound mute time cannot trigger a quiet offer, and unmute begins a fresh quiet interval',async()=>{
  vi.useFakeTimers();const f=voiceFixture();await f.voice.start();f.ready();f.socket.receive(snapshot);await reply(f);f.audio.drain!();f.voice.muteSpeaker();await vi.advanceTimersByTimeAsync(11000);expect(texts(f)).toHaveLength(0);f.voice.muteSpeaker();await vi.advanceTimersByTimeAsync(10000);expect(texts(f)).toHaveLength(1);f.voice.stop();
 });
 it('requested summary suppresses a redundant quiet offer until another catalog lookup',async()=>{
  vi.useFakeTimers();const f=voiceFixture();await f.voice.start();f.ready();f.socket.receive({...snapshot,requested:true});await reply(f);f.audio.drain!();await vi.advanceTimersByTimeAsync(11000);expect(texts(f)).toHaveLength(0);
  f.socket.receive(event('interrupted',{turn_id:'turn-2',generation_id:'generation-2'}));f.socket.receive({...snapshot,turn_id:'turn-2'});await reply(f,2);f.audio.drain!();await vi.advanceTimersByTimeAsync(11000);expect(texts(f)).toHaveLength(1);f.voice.stop();
 });
 it('explicit summary sends bounded text through the existing session and rejects malformed/stale summary facts',async()=>{
  const f=voiceFixture();expect(f.voice.requestSummary()).toBe(false);await f.voice.start();f.ready();f.socket.receive(snapshot);expect(f.callbacks.event).toHaveBeenCalledOnce();expect(f.voice.requestSummary()).toBe(true);
  expect(texts(f)[0].text).toContain('summarize all');f.socket.receive(snapshot);expect(f.callbacks.event).toHaveBeenCalledOnce();
  expect(eventSchema.safeParse({...snapshot,entries:[{...snapshot.entries[0],status:'not_found'}]}).success).toBe(false);
  f.voice.stop();
 });
});


it('automatically locates one typed match without another click', async () => {
 const fetcher=vi.fn(async(path)=>response(path==='/api/store-map'?map:path==='/api/search'?search:route));
 const portal=new Portal(new Api(fetcher));await portal.loadMap();await portal.search('whole milk');
 expect(get(portal).location?.id).toBe(route.product.id);expect(get(portal).route?.product.id).toBe(route.product.id);
 expect(get(portal).focus).toBe('results-heading');expect(get(portal).loading).toBe(false);
 expect(fetcher.mock.calls.filter(([path])=>path==='/api/routes')).toHaveLength(1);portal.destroy();
});

it('keeps ambiguous typed matches unselected until the shopper chooses', async () => {
 const fetcher=vi.fn(async()=>response({...search,candidates:[search.candidates[0],{...search.candidates[0],id:'other-milk'}],ambiguous:true}));
 const portal=new Portal(new Api(fetcher));await portal.search('milk');
 expect(get(portal).location).toBeNull();expect(get(portal).route).toBeNull();expect(fetcher).toHaveBeenCalledTimes(1);portal.destroy();
});
