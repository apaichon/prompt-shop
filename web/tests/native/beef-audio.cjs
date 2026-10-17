// Opt-in beef clarification, injected post-result noise, and clicked selection.
// No shopper transcripts or recorded microphone data are persisted.
const {chromium}=require('@playwright/test');
const fs=require('node:fs');
if(!process.env.NATIVE_VOICE_WAV)throw new Error('Set NATIVE_VOICE_WAV to a synthetic single-item request');
(async()=>{
 const browser=await chromium.launch({...(process.env.NATIVE_BROWSER_EXECUTABLE?{executablePath:process.env.NATIVE_BROWSER_EXECUTABLE}:{}),...(process.env.NATIVE_AUDIBLE==='1'?{ignoreDefaultArgs:['--mute-audio']}:{}),args:['--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream',`--use-file-for-fake-audio-capture=${process.env.NATIVE_VOICE_WAV}%noloop`]});
 const page=await browser.newPage({permissions:['microphone',...(process.env.NATIVE_STATIC_DIR?['local-network-access']:[])],viewport:{width:390,height:900}});
 await page.addInitScript(({noise})=>{
  window.__noiseUntil=0;window.__injected=0;
  if(noise){
   const Worklet=window.AudioWorkletNode;
   window.AudioWorkletNode=class extends Worklet{constructor(...args){super(...args);this.port.addEventListener('message',({data})=>{if(data instanceof ArrayBuffer&&performance.now()<window.__noiseUntil){new Int16Array(data).fill(2000);window.__injected++}});this.port.start()}};
   const Socket=window.WebSocket;
   window.WebSocket=class extends Socket{constructor(...args){super(...args);this.addEventListener('message',({data})=>{if(typeof data==='string'){try{if(JSON.parse(data).type==='candidates')window.__noiseUntil=performance.now()+140}catch{}}})}};
  }
  window.__played=0;const Native=window.AudioContext;
  window.AudioContext=class extends Native{createBufferSource(){const source=super.createBufferSource(),start=source.start.bind(source);source.start=(...args)=>{window.__played++;return start(...args)};return source}};
 },{noise:process.env.NATIVE_NOISE_AFTER_RESULT==='1'});
 if(process.env.NATIVE_STATIC_DIR){
  const path=require('node:path'),root=path.resolve(process.env.NATIVE_STATIC_DIR);
  await page.route('**/*',async route=>{
   const url=new URL(route.request().url());
   if(url.origin!==(process.env.NATIVE_VOICE_ORIGIN||'http://localhost:8080')||url.pathname.startsWith('/api/')||url.pathname.startsWith('/ws/'))return route.continue();
   const file=path.resolve(root,'.'+decodeURIComponent(url.pathname==='/'?'/index.html':url.pathname));
   if(!file.startsWith(root+path.sep))return route.abort();
   try{await route.fulfill({path:file});}catch{await route.abort();}
  });
 }
 let route=null,candidates=[],candidateCount=0,inputCaption=false,outputCaption=false,bytes=0,pcmEnergy=0,pcmSamples=0,complete=false,captions='',closed=false;const errors=[];
 page.on('websocket',ws=>{ws.on('close',()=>closed=true);ws.on('framereceived',({payload})=>{
  if(Buffer.isBuffer(payload)){bytes+=payload.length;for(let i=0;i+1<payload.length;i+=2){const sample=payload.readInt16LE(i);pcmEnergy+=sample*sample;pcmSamples++}return}
  let e;try{e=JSON.parse(payload)}catch{return}
  if(e.type==='candidates'){candidates=e.candidates;candidateCount=candidates.length;}
  if(e.type==='input_transcript')inputCaption=true;
  if(e.type==='output_transcript')outputCaption=true;
  if(e.type==='route')route=e;
  if(e.type==='output_transcript')captions+=' '+e.text;
  if(e.type==='turn_complete')complete=true;
  if(e.type==='error')errors.push(e.code);
 })});
 try{
  await page.goto(process.env.NATIVE_VOICE_ORIGIN||'http://localhost:8080');await require('./auth.cjs').signIn(page);
  await page.getByRole('region',{name:'Voice controls'}).getByRole('button',{name:'Start voice',exact:true}).click();
  const deadline=Date.now()+40000;
  while(Date.now()<deadline&&!closed&&!(complete&&candidateCount&&bytes))await page.waitForTimeout(100);
  const normalized=(text)=>text.toLowerCase().replace(/\b(one|two|three|four|five|six|seven|eight|nine|ten)\b/g,w=>String(['one','two','three','four','five','six','seven','eight','nine','ten'].indexOf(w)+1)).replace(/\s+/g,' ');
  const report={input:'synthetic spoken microphone; real Chromium capture/playout; Gemini Live and embedding API',
   injected_noise_frames:await page.evaluate(()=>window.__injected),ui_caption_present:await page.locator('.assistant-bubble strong').count()>0,candidate_count:candidateCount,input_caption:inputCaption,output_caption:outputCaption,complete,audio_bytes:bytes,audio_rms:Math.round(Math.sqrt(pcmEnergy/Math.max(1,pcmSamples))),playout_started:await page.evaluate(()=>window.__played>0),
   error_codes:errors,closed};
  const passed=complete&&bytes&&report.audio_rms>=10&&report.playout_started&&report.ui_caption_present&&candidateCount===2&&inputCaption&&outputCaption&&!errors.length&&!closed;
  if(passed&&process.env.NATIVE_CHOOSE_BEEF==='1'){
   const chosen=candidates.find(p=>p.name==='Beef steak');if(!chosen)throw new Error('Missing beef steak candidate');
   await page.waitForTimeout(500);
   complete=false;bytes=0;pcmEnergy=0;pcmSamples=0;captions='';
   await page.getByRole('button',{name:'Show route to Beef steak',exact:true}).click();
   const choiceDeadline=Date.now()+25000;
   while(Date.now()<choiceDeadline&&!closed&&!(complete&&route&&bytes))await page.waitForTimeout(100);
   report.selection={complete,audio_bytes:bytes,audio_rms:Math.round(Math.sqrt(pcmEnergy/Math.max(1,pcmSamples))),expected_route:route?.product.id===chosen.id,
    map_visible:await page.getByTestId('route-path').isVisible(),selected_aisles:await page.locator('.aisle.selected').count(),
    spoken_aisle:!!route&&normalized(captions).includes(normalized(route.product.aisle.label)),spoken_shelf:!!route&&normalized(captions).includes(normalized(route.product.shelf.label))};
   const r=report.selection;if(!r.complete||r.audio_rms<10||!r.expected_route||!r.map_visible||r.selected_aisles!==1||!r.spoken_aisle||!r.spoken_shelf||errors.length||closed)process.exitCode=1;
  }
  report.closed=closed;
  await page.screenshot({path:process.env.NATIVE_SCREENSHOT_PATH||'tmp/native-beef.png',fullPage:true});
  console.log(JSON.stringify(report));if(process.env.NATIVE_REPORT_PATH)fs.writeFileSync(process.env.NATIVE_REPORT_PATH,JSON.stringify(report,null,2)+'\n');
  if(!passed||(process.env.NATIVE_NOISE_AFTER_RESULT==='1'&&!report.injected_noise_frames))process.exitCode=1;
  const stop=page.getByRole('region',{name:'Voice controls'}).getByRole('button',{name:'End voice',exact:true});if(await stop.isVisible())await stop.click();
 }finally{await browser.close()}
})().catch(e=>{console.error(e.name+': '+e.message.split('\n')[0]);process.exitCode=1});
