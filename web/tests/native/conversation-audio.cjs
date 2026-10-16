// Opt-in real microphone/playout pipeline with a synthetic 10-utterance WAV.
const {chromium}=require('@playwright/test');
if(!process.env.NATIVE_VOICE_WAV)throw new Error('Set NATIVE_VOICE_WAV to the synthetic conversation WAV');
(async()=>{
 const browser=await chromium.launch({args:['--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream','--use-file-for-fake-audio-capture='+process.env.NATIVE_VOICE_WAV+'%noloop']});
 const page=await browser.newPage({permissions:['microphone'],viewport:{width:1440,height:1000}});
 await page.addInitScript(()=>{
  window.__metrics={lastInput:0,turns:[],current:null};
  const Worklet=window.AudioWorkletNode;
  window.AudioWorkletNode=class extends Worklet{constructor(...a){super(...a);this.port.addEventListener('message',({data})=>{
   if(!(data instanceof ArrayBuffer))return;let sum=0;const pcm=new Int16Array(data);for(const n of pcm)sum+=n*n;
   if(Math.sqrt(sum/Math.max(1,pcm.length))>=500)window.__metrics.lastInput=performance.now();
  });this.port.start();}};
  const Socket=window.WebSocket;
  window.WebSocket=class extends Socket{constructor(...a){super(...a);this.addEventListener('message',({data})=>{if(typeof data!=='string')return;let e;try{e=JSON.parse(data)}catch{return}
   if(e.type==='audio_start'){const t={first_playout_ms:null,max_gap_ms:0,lastEnd:null};window.__metrics.turns.push(t);window.__metrics.current=t;}
   if(e.type==='interrupted')window.__metrics.current=null;
  });}};
  const Context=window.AudioContext;
  window.AudioContext=class extends Context{createBufferSource(){const source=super.createBufferSource(),start=source.start.bind(source),context=this;
   source.start=(when=0,...rest)=>{const t=window.__metrics.current,at=Math.max(when,context.currentTime);
    if(t){if(t.first_playout_ms===null)t.first_playout_ms=performance.now()-window.__metrics.lastInput+(at-context.currentTime)*1000;
     if(t.lastEnd!==null)t.max_gap_ms=Math.max(t.max_gap_ms,(at-t.lastEnd)*1000);t.lastEnd=at+(source.buffer?.duration??0);}
    return start(when,...rest);};return source;}};
 });
 const turns=new Map(),errors=[];let current=null,closed=false,shelfCalls=0;
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
  await page.locator('.desktop-voice').getByRole('button',{name:'Start voice',exact:true}).click();
  const deadline=Date.now()+165000;
  while(Date.now()<deadline&&!closed&&[...turns.values()].filter(t=>t.complete).length<10)await page.waitForTimeout(200);
  await page.waitForTimeout(1000);
  const expected=[null,'milk-whole-1l','milk-whole-1l','jasmine-rice','jasmine-rice','toothpaste',null,'milk-whole-1l',null,'jasmine-rice'];
  const results=[...turns.values()].map((t,i)=>({index:i+1,complete:t.complete,audio_bytes:t.audio_bytes,expected_route:t.route===expected[i]}));
  const report={input:'synthetic spoken microphone; actual Chromium capture/playout',turns:results,closed,error_codes:errors,shelf_requests:shelfCalls,
    playout:await page.evaluate(()=>window.__metrics.turns.map(({lastEnd,...t})=>t))};
  console.log(JSON.stringify(report));
  if(process.env.NATIVE_REPORT_PATH)require('node:fs').writeFileSync(process.env.NATIVE_REPORT_PATH,JSON.stringify(report,null,2)+'\n');
  if(closed||errors.length||results.length!==10||results.some(t=>!t.complete||!t.audio_bytes||!t.expected_route)||shelfCalls!==7)process.exitCode=1;
  const end=page.locator('.desktop-voice').getByRole('button',{name:'End voice',exact:true});if(await end.isVisible())await end.click();
 }finally{await browser.close();}
})().catch(e=>{console.error(e.name+': '+e.message.split('\n')[0]);process.exitCode=1;});
