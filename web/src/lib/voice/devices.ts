import { writable } from 'svelte/store';

export interface AudioSelection { microphoneId: string; speakerId: string }
export interface DeviceOption { id: string; label: string }
interface DeviceState extends AudioSelection {
  microphones: DeviceOption[]; speakers: DeviceOption[];
  canSelectSpeaker: boolean; canChooseSpeaker: boolean; busy: boolean; testing: boolean; message: string;
}
export type SinkContext = AudioContext & { setSinkId?: (id: string) => Promise<void> };
type OutputMedia = MediaDevices & { selectAudioOutput?: () => Promise<MediaDeviceInfo> };
export class AudioDeviceError extends Error {}
export class AudioDevices {
  private state: DeviceState = {microphoneId:'',speakerId:'',microphones:[],speakers:[],canSelectSpeaker:false,canChooseSpeaker:false,busy:false,testing:false,message:''};
  private store = writable(this.state); subscribe = this.store.subscribe;
  private refs = 0; private epoch = 0; private listing = 0;
  private testContext?: AudioContext;
  constructor(private removed: () => void = () => {}) {}
  private patch(value: Partial<DeviceState>) {this.state={...this.state,...value};this.store.set(this.state);}
  selection(): AudioSelection {return {microphoneId:this.state.microphoneId,speakerId:this.state.speakerId};}
  microphone(id: string) {if(!this.state.busy && (!id||this.state.microphones.some(d=>d.id===id)))this.patch({microphoneId:id,message:''});}
  speaker(id: string) {if(!this.state.busy && (!id||this.state.canSelectSpeaker&&this.state.speakers.some(d=>d.id===id)))this.patch({speakerId:id,message:''});}
  private changed = () => {void this.refresh();};
  attach() {
    if(this.refs++===0){
      this.patch({canSelectSpeaker:typeof (window.AudioContext?.prototype as SinkContext)?.setSinkId==='function',canChooseSpeaker:typeof (navigator.mediaDevices as OutputMedia)?.selectAudioOutput==='function'});
      navigator.mediaDevices?.addEventListener?.('devicechange',this.changed);void this.refresh();
    }
    return () => {if(this.refs>0&&--this.refs===0)this.dispose();};
  }
  async refresh() {
    const key=++this.listing;
    if(!navigator.mediaDevices?.enumerateDevices){this.patch({message:'Device selection is unavailable. Use your system sound settings.'});return;}
    try{
      const list=await navigator.mediaDevices.enumerateDevices();if(key!==this.listing||!this.refs)return;
      const options=(kind:MediaDeviceKind)=>list.filter(d=>d.kind===kind&&d.deviceId&&d.deviceId!=='default').map((d,i)=>({id:d.deviceId,label:d.label||`${kind==='audioinput'?'Microphone':'Speaker'} ${i+1}`}));
      const microphones=options('audioinput'),speakers=options('audiooutput');
      const missingMic=!!this.state.microphoneId&&!microphones.some(d=>d.id===this.state.microphoneId);
      const missingSpeaker=!!this.state.speakerId&&!speakers.some(d=>d.id===this.state.speakerId);
      this.patch({microphones,speakers,...(missingMic?{microphoneId:''}:{}),...(missingSpeaker?{speakerId:''}:{})});
      if(missingMic||missingSpeaker){this.patch({message:'A selected device is unavailable. System default is selected; check your devices before starting voice.'});this.removed();}
    }catch{if(key===this.listing)this.patch({message:'Could not list devices. Check browser permissions and try again.'});}
  }
  async enable() {
    if(this.state.busy)return;const key=++this.epoch;this.patch({busy:true,message:''});
    try{
      const stream=await navigator.mediaDevices.getUserMedia({audio:true});stream.getTracks().forEach(t=>t.stop());
      if(key===this.epoch)await this.refresh();
    }catch{if(key===this.epoch)this.patch({message:'Microphone permission was not granted. You can change it in browser settings and retry.'});}
    finally{if(key===this.epoch)this.patch({busy:false});}
  }
  async chooseSpeaker() {
    const media=navigator.mediaDevices as OutputMedia;
    if(this.state.busy||!media?.selectAudioOutput||!this.state.canSelectSpeaker)return;
    const key=++this.epoch;this.patch({busy:true,message:''});
    try{
      const device=await media.selectAudioOutput();if(key!==this.epoch)return;
      await this.refresh();if(key!==this.epoch)return;
      const speakers=this.state.speakers.some(d=>d.id===device.deviceId)?this.state.speakers:[...this.state.speakers,{id:device.deviceId,label:device.label||'Selected speaker'}];
      this.patch({speakers,speakerId:device.deviceId});
    }catch{if(key===this.epoch)this.patch({message:'Speaker selection was cancelled or unavailable. Your previous selection is kept.'});}
    finally{if(key===this.epoch)this.patch({busy:false});}
  }
  async testSpeaker() {
    if(this.state.testing||this.state.busy)return;
    this.patch({testing:true,message:''});
    let context: SinkContext;
    try{
      context=new AudioContext();this.testContext=context;
      await context.resume();
      if(this.testContext!==context)return;
      if(this.state.speakerId){if(!context.setSinkId)throw new Error();await context.setSinkId(this.state.speakerId);}
      if(this.testContext!==context)return;
      const tone=context.createOscillator(),gain=context.createGain();
      tone.frequency.value=440;gain.gain.value=.05;tone.connect(gain);gain.connect(context.destination);
      tone.onended=()=>{if(this.testContext===context)this.stopTest();};
      tone.start();tone.stop(context.currentTime+.3);
    }catch{this.stopTest();this.patch({message:'Could not play the speaker test. Choose an available output or System default.'});}
  }
  stopTest(){const context=this.testContext;this.testContext=undefined;void context?.close().catch(()=>{});this.patch({testing:false});}
  cancel(){this.epoch++;this.patch({busy:false});this.stopTest();}
  private dispose(){this.cancel();this.listing++;if(typeof navigator!=='undefined')navigator.mediaDevices?.removeEventListener?.('devicechange',this.changed);}
  destroy(){this.refs=0;this.dispose();}
}
