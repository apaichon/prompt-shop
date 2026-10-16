// Opt-in real microphone/playout pipeline with a synthetic 10-utterance WAV.
const {chromium}=require('@playwright/test');
if(!process.env.NATIVE_VOICE_WAV)throw new Error('Set NATIVE_VOICE_WAV to the synthetic conversation WAV');
const speakerMode=process.env.NATIVE_SPEAKER_MODE==='1';
const injectFeedback=process.env.NATIVE_SPEAKER_FEEDBACK==='1';
if(injectFeedback&&!speakerMode)throw new Error('Synthetic feedback probe requires speaker mode');
(async()=>{
 const browser=await chromium.launch({args:['--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream','--use-file-for-fake-audio-capture='+process.env.NATIVE_VOICE_WAV+'%noloop']});
 const page=await browser.newPage({permissions:['microphone',...(process.env.NATIVE_STATIC_DIR?['local-network-access']:[])],viewport:{width:1440,height:1000}});
 await page.addInitScript(({injectFeedback})=>{
  window.__metrics={lastInput:0,turns:[],current:null,playing:0,tailUntil:0,injected:false,feedback_frames:0,leaked_feedback_frames:0};
  const Worklet=window.AudioWorkletNode;
  window.AudioWorkletNode=class extends Worklet{constructor(...a){super(...a);this.port.addEventListener('message',({data})=>{
   if(!(data instanceof ArrayBuffer))return;let sum=0;const pcm=new Int16Array(data);for(const n of pcm)sum+=n*n;
   if(Math.sqrt(sum/Math.max(1,pcm.length))>=500)window.__metrics.lastInput=performance.now();
   const m=window.__metrics;m.injected=injectFeedback&&(m.playing>0||performance.now()<m.tailUntil);
   if(m.injected){pcm.fill(2000);m.feedback_frames++;}
  });this.port.start();}};
  const Socket=window.WebSocket;
  window.WebSocket=class extends Socket{send(data){const m=window.__metrics;if(m.injected&&data instanceof ArrayBuffer&&new Int16Array(data).some(n=>n!==0))m.leaked_feedback_frames++;return super.send(data);}constructor(...a){super(...a);this.addEventListener('message',({data})=>{if(typeof data!=='string')return;let e;try{e=JSON.parse(data)}catch{return}
   if(e.type==='audio_start'){const t={first_playout_ms:null,max_gap_ms:0,lastEnd:null};window.__metrics.turns.push(t);window.__metrics.current=t;}
   if(e.type==='interrupted')window.__metrics.current=null;
  });}};
  const Context=window.AudioContext;
  window.AudioContext=class extends Context{createBufferSource(){const source=super.createBufferSource(),start=source.start.bind(source),context=this;
   source.start=(when=0,...rest)=>{const t=window.__metrics.current,at=Math.max(when,context.currentTime);
    if(t){if(t.first_playout_ms===null)t.first_playout_ms=performance.now()-window.__metrics.lastInput+(at-context.currentTime)*1000;
     if(t.lastEnd!==null)t.max_gap_ms=Math.max(t.max_gap_ms,(at-t.lastEnd)*1000);t.lastEnd=at+(source.buffer?.duration??0);}
    window.__metrics.playing++;source.addEventListener('ended',()=>{window.__metrics.playing--;if(!window.__metrics.playing)window.__metrics.tailUntil=performance.now()+200;},{once:true});
    return start(when,...rest);};return source;}};
 },{injectFeedback});
 // Optional candidate static assets; API and WebSocket still use the real Go ingress.
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
 const turns=new Map(),errors=[];let current=null,closed=false,shelfCalls=0;const transportErrors=[];
 page.on('console',m=>{if(m.type()==='error'&&m.text().includes('WebSocket connection'))transportErrors.push(m.text().replace(/ws:\/\/[^']+/g,'[local websocket]'));});
 page.on('request',r=>{const u=new URL(r.url());if(u.pathname==='/api/products'&&u.searchParams.has('shelf_id'))shelfCalls++;});
 page.on('websocket',ws=>{ws.on('close',()=>closed=true);ws.on('framereceived',({payload})=>{
  if(Buffer.isBuffer(payload)){if(current)current.audio_bytes+=payload.length;return;}
  let e;try{e=JSON.parse(payload)}catch{return}
  if(e.turn_id){if(!turns.has(e.turn_id))turns.set(e.turn_id,{audio_bytes:0,complete:false,route:null});current=turns.get(e.turn_id);}
  if(e.type==='route')current.route=e.product.id;
  if(e.type==='turn_complete'){current.complete=true;console.log(JSON.stringify({completed_turns:[...turns.values()].filter(t=>t.complete).length,shelf_requests:shelfCalls}));}
  if(e.type==='error')errors.push(e.code);
 });});
 try{
  await page.goto(process.env.NATIVE_VOICE_ORIGIN||'http://localhost:8080');
  if(speakerMode)await page.locator('.desktop-voice').getByRole('button',{name:'Speaker mode off',exact:true}).click();
  await page.locator('.desktop-voice').getByRole('button',{name:'Start voice',exact:true}).click();
  const deadline=Date.now()+165000;
  while(Date.now()<deadline&&!closed&&[...turns.values()].filter(t=>t.complete).length<10)await page.waitForTimeout(200);
  await page.waitForTimeout(1000);
  const expected=[null,'milk-whole-1l','milk-whole-1l','jasmine-rice','jasmine-rice','toothpaste',null,'milk-whole-1l',null,'jasmine-rice'];
  const results=[...turns.values()].map((t,i)=>({index:i+1,complete:t.complete,audio_bytes:t.audio_bytes,expected_route:t.route===expected[i]}));
  const feedback=await page.evaluate(()=>({injected_frames:window.__metrics.feedback_frames,leaked_frames:window.__metrics.leaked_feedback_frames}));
  const ui_status=await page.locator('.desktop-voice .voice-status').innerText();
  const ui_notice=await page.locator('.desktop-voice .voice-notice').innerText().catch(()=>'');
  const report={ui_status,ui_notice,transport_errors:transportErrors,candidate_static_assets:!!process.env.NATIVE_STATIC_DIR,speaker_mode:speakerMode,synthetic_feedback:injectFeedback,feedback,input:'synthetic spoken microphone; actual Chromium capture/playout',turns:results,closed,error_codes:errors,shelf_requests:shelfCalls,
    playout:await page.evaluate(()=>window.__metrics.turns.map(({lastEnd,...t})=>t))};
  console.log(JSON.stringify(report));
  if(process.env.NATIVE_REPORT_PATH)require('node:fs').writeFileSync(process.env.NATIVE_REPORT_PATH,JSON.stringify(report,null,2)+'\n');
  if((injectFeedback&&(!feedback.injected_frames||feedback.leaked_frames))||closed||errors.length||results.length!==10||results.some(t=>!t.complete||!t.audio_bytes||!t.expected_route)||shelfCalls!==7)process.exitCode=1;
  const end=page.locator('.desktop-voice').getByRole('button',{name:'End voice',exact:true});if(await end.isVisible())await end.click();
 }finally{await browser.close();}
})().catch(e=>{console.error(e.name+': '+e.message.split('\n')[0]);process.exitCode=1;});
