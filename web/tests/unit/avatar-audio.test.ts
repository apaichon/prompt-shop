import { afterEach, describe, expect, it, vi } from 'vitest';
import { BrowserAudio } from '../../src/lib/voice/audio';
import { avatarPose } from '../../src/lib/ui-config';

afterEach(() => { vi.unstubAllGlobals(); });

function playbackFixture() {
  let amplitude = 0, reduced = false, next = 0;
  const frames = new Map<number, FrameRequestCallback>();
  const track = { enabled: true, onended: null, stop: vi.fn() };
  const node = () => ({ connect: vi.fn(), disconnect: vi.fn() });
  const analyser = { ...node(), fftSize: 256, getFloatTimeDomainData: (samples: Float32Array) => samples.fill(amplitude) };
  const sources: any[] = [];
  class Context {
    state = 'running'; currentTime = 0; destination = {};
    audioWorklet = { addModule: vi.fn(async () => {}) };
    resume = vi.fn(async () => {}); close = vi.fn(async () => {this.state='closed';});
    createAnalyser = () => analyser;
    createMediaStreamSource = node;
    createGain = () => ({ ...node(), gain: { value: 0 } });
    createBuffer = (_channels: number, length: number) => ({ getChannelData: () => new Float32Array(length) });
    createBufferSource = () => { const source = { ...node(), onended: null as null | (() => void), start: vi.fn(), stop: vi.fn() }; sources.push(source); return source; };
  }
  class Worklet { connect=vi.fn(); disconnect=vi.fn(); port={onmessage:null,postMessage:vi.fn(),close:vi.fn()}; }
  vi.stubGlobal('window', { isSecureContext: true, AudioContext: Context, AudioWorkletNode: Worklet, matchMedia: () => ({matches:reduced}) });
  vi.stubGlobal('document', {hidden:false});
  vi.stubGlobal('navigator', {mediaDevices:{getUserMedia:async()=>({getTracks:()=>[track],getAudioTracks:()=>[track]})}});
  vi.stubGlobal('AudioContext',Context); vi.stubGlobal('AudioWorkletNode',Worklet);
  vi.stubGlobal('requestAnimationFrame',(callback:FrameRequestCallback)=>{frames.set(++next,callback);return next;});
  vi.stubGlobal('cancelAnimationFrame',(id:number)=>frames.delete(id));
  const step = () => { const [id, callback]=[...frames.entries()][0]; frames.delete(id); callback(0); };
  return {audio:new BrowserAudio(),frames,sources,analyser,track,step,setAmplitude:(value:number)=>amplitude=value,setReduced:()=>reduced=true};
}

describe('avatar output follows playback lifecycle',()=>{
  it('observes the speaker only and cancels its loop on mute, drain and close',async()=>{
    const f=playbackFixture(),level=vi.fn(),drain=vi.fn();
    await f.audio.open(vi.fn(),drain,vi.fn(),level);
    expect(f.frames.size).toBe(0); // Opening/capture alone cannot animate a mouth.
    f.audio.capture(true); expect(f.frames.size).toBe(0);
    f.audio.play(new ArrayBuffer(3200)); f.setAmplitude(.1); f.step();
    expect(level).toHaveBeenLastCalledWith(1);
    f.setAmplitude(0); f.step(); expect(level).toHaveBeenLastCalledWith(0);
    f.setAmplitude(.025); f.step(); expect(level).toHaveBeenLastCalledWith(.5);
    f.audio.speakerMuted(true); expect(level).toHaveBeenLastCalledWith(0); expect(f.frames.size).toBe(0);
    expect(f.sources[0].stop).toHaveBeenCalled();
    f.audio.speakerMuted(false); f.audio.play(new ArrayBuffer(3200));
    f.sources.at(-1).onended(); expect(f.frames.size).toBe(0); expect(drain).toHaveBeenCalledOnce();
    f.audio.play(new ArrayBuffer(3200)); f.audio.close();
    expect(f.frames.size).toBe(0); expect(level).toHaveBeenLastCalledWith(0);
    expect(f.analyser.disconnect).toHaveBeenCalled(); expect(f.track.stop).toHaveBeenCalledOnce();
  });
  it('keeps the original one-second output bound and honors reduced motion',async()=>{
    const f=playbackFixture(),level=vi.fn(); await f.audio.open(vi.fn(),vi.fn(),vi.fn(),level);
    f.setReduced(); f.audio.play(new ArrayBuffer(16384)); f.step();
    expect(f.frames.size).toBe(0); expect(level).toHaveBeenLastCalledWith(0);
    f.audio.play(new ArrayBuffer(16384));
    expect(()=>f.audio.play(new ArrayBuffer(16384))).toThrow('Audio backlog');
    f.audio.flush(); f.audio.close(); expect(f.frames.size).toBe(0);
  });
  it('cannot use stale or microphone levels to make idle/listening avatars speak',()=>{
    expect(avatarPose('speaking',0)).toBe(avatarPose('idle',0));
    expect(avatarPose('idle',1)).toBe(avatarPose('idle',0));
    expect(avatarPose('listening',1)).toBe(avatarPose('listening',0));
    expect(avatarPose('speaking',1)).not.toBe(avatarPose('speaking',.5));
  });
});
