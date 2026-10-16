const {chromium}=require('@playwright/test');
if(!process.env.NATIVE_VOICE_WAV)throw new Error('Set NATIVE_VOICE_WAV to the synthetic four-turn WAV; this opt-in check calls the configured real provider.');
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream',`--use-file-for-fake-audio-capture=${process.env.NATIVE_VOICE_WAV}%noloop`]});
 const context=await browser.newContext({permissions:['microphone'],viewport:{width:1440,height:1100}});
 const page=await context.newPage();
 await page.addInitScript(()=>{
  window.__avatarOpen=false;
  window.__playout={turns:[],current:null,lastInput:0};
  const NativeWorklet=window.AudioWorkletNode;
  window.AudioWorkletNode=class extends NativeWorklet {constructor(...args){super(...args);this.port.addEventListener('message',({data})=>{
    if(!(data instanceof ArrayBuffer))return;const samples=new Int16Array(data);let sum=0;for(const n of samples)sum+=n*n;
    if(Math.sqrt(sum/Math.max(1,samples.length))>=500)window.__playout.lastInput=performance.now();
  });this.port.start();}};
  const NativeSocket=window.WebSocket;
  window.WebSocket=class extends NativeSocket {constructor(...args){super(...args);this.addEventListener('message',({data})=>{
    if(typeof data!=='string')return;let e;try{e=JSON.parse(data)}catch{return}
    if(e.type==='audio_start'){const t={turn:e.turn_id,first_playout_ms:null,gaps_ms:[],lastEnd:null};window.__playout.turns.push(t);window.__playout.current=t;}
    if(e.type==='interrupted')window.__playout.current=null;
  });}};
  const NativeContext=window.AudioContext;
  window.AudioContext=class extends NativeContext {createBufferSource(){const source=super.createBufferSource(),start=source.start.bind(source),context=this;
    source.start=(when=0,...rest)=>{const t=window.__playout.current,at=Math.max(context.currentTime,when);
      if(t){if(t.first_playout_ms===null)t.first_playout_ms=performance.now()-window.__playout.lastInput+(at-context.currentTime)*1000;
        if(t.lastEnd!==null)t.gaps_ms.push(Math.max(0,(at-t.lastEnd)*1000));t.lastEnd=at+(source.buffer?.duration??0);}
      return start(when,...rest);};return source;}};
  new MutationObserver(()=>{if(document.querySelector('.desktop-voice .assistant-avatar[data-pose="3"], .desktop-voice .assistant-avatar[data-pose="4"]'))window.__avatarOpen=true;}).observe(document,{subtree:true,attributes:true,attributeFilter:['data-pose']});
 });
 const turns={}, errors=[], counts={};let closed=false,route=false,lastTurn=null,earlyCatalog=false;
 page.on('websocket',ws=>{
  ws.on('close',()=>closed=true);
  ws.on('framereceived',({payload})=>{
   if(Buffer.isBuffer(payload)){if(lastTurn)turns[lastTurn].audio_bytes+=payload.length;return;}
   let e;try{e=JSON.parse(payload);}catch{return;}
   counts[e.type]=(counts[e.type]||0)+1; if(e.turn_id){lastTurn=e.turn_id; turns[lastTurn]??={audio_bytes:0,complete:false,text:''};}
   if(e.type==='output_transcript')turns[e.turn_id].text+=' '+e.text;
   if(e.type==='turn_complete')turns[e.turn_id].complete=true;
   if(e.type==='candidates' && Object.keys(turns).length<4)earlyCatalog=true;
   if(e.type==='route')route=e.product.id==='milk-whole-1l';
   if(e.type==='error')errors.push(e.code);
  });
 });
 try{
  await page.goto(process.env.NATIVE_VOICE_ORIGIN||'http://localhost:8080');await require('./auth.cjs').signIn(page);
  await page.getByRole('button',{name:'Start voice',exact:true}).first().click();
  const deadline=Date.now()+110000;
  while(Date.now()<deadline&&!closed&&!(route&&Object.values(turns).filter(t=>t.complete&&t.audio_bytes).length>=4))await page.waitForTimeout(200);
  const responses=Object.values(turns).filter(t=>t.complete&&t.audio_bytes);
  const text=await page.locator('body').innerText();
  const result={completed_audio_turns:responses.length,audio_bytes_by_turn:responses.map(t=>t.audio_bytes),
    greeting:!!responses[0]&&/hello|hi\b|help|welcome/i.test(responses[0].text),
    general_answer:!!responses[1]&&/four|\b4\b/i.test(responses[1].text),
    meal_suggestion:!!responses[2]&&/omelet|egg|scrambl|frittata/i.test(responses[2].text),
    milk_route:route,route_visible:text.includes('Route found'),
    stored_location_captions:!!responses[3]&&/aisle\s*2/i.test(responses[3].text)&&/shelf\s*3/i.test(responses[3].text),
    early_catalog:earlyCatalog,error_codes:errors,websocket_closed:closed,audio_backlog:text.includes('Audio could not keep up.')};
  result.event_counts=counts; result.permission_message=text.includes('permissions'); result.disconnected_message=text.includes('Voice disconnected'); result.dependency_message=text.includes('temporarily unavailable'); result.avatar_open_seen=await page.evaluate(()=>window.__avatarOpen);
  const end=page.locator('.desktop-voice').getByRole('button',{name:'End voice',exact:true}); if(await end.isVisible())await end.click();
  await page.waitForTimeout(100);
  result.avatar_stopped=await page.locator('.desktop-voice .assistant-avatar').getAttribute('data-pose')==='0';
  result.playout=await page.evaluate(()=>window.__playout.turns.map(({turn,first_playout_ms,gaps_ms})=>({turn,first_playout_ms,gaps_ms})));console.log(JSON.stringify(result));
  if(!result.avatar_open_seen||!result.avatar_stopped)process.exitCode=1;
  if(responses.length<4||!result.general_answer||!result.meal_suggestion||!route||earlyCatalog||result.websocket_closed||errors.length||result.audio_backlog)process.exitCode=1;
 }finally{await context.close();await browser.close();}
})().catch(e=>{console.error(e.name+': '+e.message.split('\n')[0]);process.exitCode=1;});
