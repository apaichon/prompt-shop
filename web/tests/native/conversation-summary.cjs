// Opt-in real Gemini/ADK/Laya + Go summary and quiet follow-up check.
// Uses synthetic silence and public text controls with real browser audio playout.
// No transcript, cookie, account, session ID, HAR or raw speech is written.
const {chromium}=require('@playwright/test');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
(async()=>{
 if(process.env.NATIVE_SUMMARY_TEST!=='1')throw new Error('Set NATIVE_SUMMARY_TEST=1 to call the configured real provider');
 const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'monti-summary-')),wav=path.join(tmp,'silence.wav');
 const pcm=Buffer.alloc(16000*2*180),header=Buffer.alloc(44);header.write('RIFF');header.writeUInt32LE(pcm.length+36,4);header.write('WAVEfmt ',8);header.writeUInt32LE(16,16);header.writeUInt16LE(1,20);header.writeUInt16LE(1,22);header.writeUInt32LE(16000,24);header.writeUInt32LE(32000,28);header.writeUInt16LE(2,32);header.writeUInt16LE(16,34);header.write('data',36);header.writeUInt32LE(pcm.length,40);fs.writeFileSync(wav,Buffer.concat([header,pcm]));
 const browser=await chromium.launch({args:['--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream','--use-file-for-fake-audio-capture='+wav+'%noloop']});
 const page=await browser.newPage({permissions:['microphone'],viewport:{width:1440,height:1100}});
 await page.addInitScript(()=>{
  const probe=window.__summaryProbe={complete:0,playing:0,chunks:0,audio:0,requested:0,offers:0,offerTime:0,errors:[],closed:false,media_error:'',entries:[],truncated:false,session:null,socket:null,lastDrain:0};
  const get=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);navigator.mediaDevices.getUserMedia=(...a)=>get(...a).catch(e=>{probe.media_error=e.name;throw e;});
  const Socket=window.WebSocket;window.WebSocket=class extends Socket{
   constructor(...a){super(...a);probe.socket=this;this.addEventListener('close',()=>probe.closed=true);this.addEventListener('message',({data})=>{if(data instanceof ArrayBuffer){probe.audio+=data.byteLength;return;}if(typeof data!=='string')return;let e;try{e=JSON.parse(data);}catch{return;}
    if(e.type==='ready')probe.session=e.session_id;if(e.type==='turn_complete')probe.complete++;if(e.type==='error')probe.errors.push(e.code);if(e.type==='summary'){probe.entries=e.entries;probe.truncated=e.truncated;if(e.requested)probe.requested++;}
   });}
   send(data){if(typeof data==='string'){try{const e=JSON.parse(data);if(e.type==='text'&&e.text.includes('After the quiet pause')){probe.offers++;probe.offerTime=performance.now();}}catch{}}return super.send(data);}
  };
  const Context=window.AudioContext;window.AudioContext=class extends Context{createBufferSource(){const source=super.createBufferSource(),start=source.start.bind(source);source.start=(...a)=>{probe.chunks++;probe.playing++;source.addEventListener('ended',()=>{probe.playing--;if(!probe.playing)probe.lastDrain=performance.now();},{once:true});return start(...a);};return source;}};
 });
 const check=(v,m)=>{if(!v)throw new Error(m);};let stage='login';
 const state=()=>page.evaluate(()=>{const p=window.__summaryProbe;return {complete:p.complete,playing:p.playing,chunks:p.chunks,audio:p.audio,requested:p.requested,offers:p.offers,errors:p.errors,closed:p.closed,entries:p.entries,truncated:p.truncated};});
 async function request(text){const before=(await state()).complete;await page.evaluate(text=>{const p=window.__summaryProbe;p.socket.send(JSON.stringify({type:'text',session_id:p.session,text}));},text);await page.waitForFunction(before=>{const p=window.__summaryProbe;return p.errors.length||p.closed||(p.complete>before&&!p.playing);},before,{timeout:25000});const p=await state();check(!p.errors.length&&!p.closed&&p.complete>before,'native reply incomplete');}
 try{
  await page.goto(process.env.NATIVE_VOICE_ORIGIN||'http://localhost:8080');await require('./auth.cjs').signIn(page);await page.locator('.desktop-voice').getByRole('button',{name:'Start voice',exact:true}).click();stage='voice-ready';await page.waitForFunction(()=>window.__summaryProbe.session);
  stage='first-item';await request('Where is whole milk?');
  stage='second-item';await request('Where is a bagel?');
  stage='summary-request';await request('Summarize all the items I asked about and their locations.');
  let p=await state();check(p.requested===1,'summary tool not called');let ids=p.entries.filter(e=>e.status==='confirmed').flatMap(e=>e.products.map(p=>p.id));check(ids.includes('milk-whole-1l')&&ids.includes('bagels'),'summary missing confirmed items');await page.getByRole('region',{name:'Items and locations'}).getByRole('button',{name:'Locate Bagels from summary',exact:true}).waitFor();
  // Another lookup permits one new quiet offer, while keeping the same connection.
  stage='new-item';await request('Where is jasmine rice?');
  stage='quiet-offer';const before=(await state()).complete;await page.waitForFunction(()=>window.__summaryProbe.offers===1,null,{timeout:15000});const quiet=await page.evaluate(()=>window.__summaryProbe.offerTime-window.__summaryProbe.lastDrain);check(quiet>=9900,'offer interrupted playout/quiet');await page.waitForFunction(before=>{const p=window.__summaryProbe;return p.errors.length||p.closed||(p.complete>before&&!p.playing);},before,{timeout:25000});
  stage='accept-offer';await request('Yes, please summarize them.');p=await state();check(p.requested===2,'acceptance did not call summary tool');ids=p.entries.filter(e=>e.status==='confirmed').flatMap(e=>e.products.map(p=>p.id));check(ids.length===3&&new Set(ids).size===3,'summary lost/duplicated facts');
  stage='no-loop';await page.waitForTimeout(11500);p=await state();check(p.offers===1&&!p.errors.length&&!p.closed,'repeated offer or disconnected conversation');
  await page.locator('.desktop-voice').getByRole('button',{name:'End voice',exact:true}).click();await page.getByRole('region',{name:'Items and locations'}).getByRole('button',{name:'Locate Bagels from summary',exact:true}).waitFor();
  const report={input:'synthetic silence capture + public text controls; actual native provider and Chromium playout',complete_replies:p.complete,summary_requests:p.requested,confirmed_items:ids.length,unique_items:new Set(ids).size,quiet_offer_count:p.offers,quiet_ms_after_playout:Math.round(quiet),native_audio_bytes:p.audio,played_chunks:p.chunks,error_codes:p.errors,connected_until_end:!p.closed,report_retained_after_end:true};
  console.log(JSON.stringify(report));if(process.env.NATIVE_REPORT_PATH)fs.writeFileSync(process.env.NATIVE_REPORT_PATH,JSON.stringify(report,null,2)+'\n');
 }catch(e){const p=await state().catch(()=>({}));console.log(JSON.stringify({stage,complete:p.complete,summary_requests:p.requested,offers:p.offers,error_codes:p.errors,closed:p.closed,media_error:await page.evaluate(()=>window.__summaryProbe.media_error),ui_status:await page.locator('.desktop-voice .voice-status').innerText({timeout:1000}).catch(()=>''),ui_notice:await page.locator('.desktop-voice .voice-notice').innerText({timeout:1000}).catch(()=>'')}));throw e;}finally{await browser.close();fs.rmSync(tmp,{recursive:true,force:true});}
})().catch(e=>{console.error(e.name+': '+e.message.split('\n')[0]);process.exitCode=1;});
