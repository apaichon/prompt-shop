import {afterEach,expect,it,vi} from 'vitest';
import {get} from 'svelte/store';
import {AudioDevices} from '../../src/lib/voice/devices';
afterEach(()=>vi.unstubAllGlobals());
function fixture(supported=true){
 let list=[{kind:'audioinput',deviceId:'mic1',label:'USB microphone'},{kind:'audiooutput',deviceId:'out1',label:'Headphones'}];
 const stop=vi.fn(),close=vi.fn(async()=>{}),sink=vi.fn(async()=>{}),tone={frequency:{value:0},connect:vi.fn(),start:vi.fn(),stop:vi.fn(),onended:null as null|(()=>void)};
 const events=new EventTarget();const media=Object.assign(events,{enumerateDevices:vi.fn(async()=>list),getUserMedia:vi.fn(async()=>({getTracks:()=>[{stop}]})),selectAudioOutput:vi.fn(async()=>list[1])});
 class Context {destination={};currentTime=0;resume=async()=>{};close=close;createOscillator=()=>tone;createGain=()=>({gain:{value:0},connect:vi.fn()});}
 if(supported)Object.assign(Context.prototype,{setSinkId:sink});
 vi.stubGlobal('navigator',{mediaDevices:media});vi.stubGlobal('window',{AudioContext:Context});vi.stubGlobal('AudioContext',Context);
 const removed=vi.fn(),devices=new AudioDevices(removed);const detach=devices.attach();
 return {devices,detach,media,stop,close,sink,tone,removed,remove:()=>{list=[];events.dispatchEvent(new Event('devicechange'));}};
}
it('lists permitted devices, stops permission probe and routes/closes an explicit test',async()=>{
 const f=fixture();await f.devices.refresh();expect(get(f.devices).microphones[0].label).toBe('USB microphone');
 await f.devices.enable();expect(f.stop).toHaveBeenCalledOnce();f.devices.microphone('mic1');f.devices.speaker('out1');
 await f.devices.testSpeaker();expect(f.sink).toHaveBeenCalledWith('out1');expect(f.tone.stop).toHaveBeenCalledWith(.3);f.tone.onended!();expect(f.close).toHaveBeenCalledOnce();
 f.remove();await f.devices.refresh();expect(f.devices.selection()).toEqual({microphoneId:'',speakerId:''});expect(f.removed).toHaveBeenCalledOnce();f.detach();
});
it('cancels late permission without leaving a recording stream or busy UI',async()=>{
 const f=fixture();let resolve!:(v:any)=>void;f.media.getUserMedia.mockImplementation(()=>new Promise(r=>resolve=r));
 const pending=f.devices.enable();f.devices.cancel();resolve({getTracks:()=>[{stop:f.stop}]});await pending;expect(f.stop).toHaveBeenCalledOnce();expect(get(f.devices).busy).toBe(false);f.detach();
});
it('keeps system output on unsupported browsers and retains choices on denied chooser',async()=>{
 const f=fixture(false);await f.devices.refresh();f.devices.speaker('out1');expect(f.devices.selection().speakerId).toBe('');expect(get(f.devices).canSelectSpeaker).toBe(false);f.detach();
 const g=fixture();await g.devices.refresh();g.devices.speaker('out1');g.media.selectAudioOutput.mockRejectedValue(new Error());await g.devices.chooseSpeaker();expect(g.devices.selection().speakerId).toBe('out1');expect(get(g.devices).message).toContain('previous selection');g.detach();
});
