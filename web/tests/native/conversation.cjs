// Opt-in native provider check: one public WebSocket session, explicit text turns.
// No transcripts/audio/session identifiers are written to output.
const {chromium}=require('@playwright/test');
(async()=>{
 if(process.env.NATIVE_VOICE_TEST!=='1')throw new Error('Set NATIVE_VOICE_TEST=1 to call the configured real provider');
 const browser=await chromium.launch();
 const page=await browser.newPage({permissions:['microphone'],viewport:{width:1440,height:1000}});
 await page.addInitScript(()=>{const Native=window.WebSocket;window.__probe={};window.WebSocket=class extends Native{constructor(...a){super(...a);window.__probe.socket=this;this.addEventListener('message',e=>{if(typeof e.data==='string'){try{const v=JSON.parse(e.data);if(v.type==='ready')window.__probe.session=v.session_id;}catch{}}});}};});
 let closed=false,current=null,candidates=[];
 const results=[];
 page.on('websocket',ws=>{ws.on('close',()=>closed=true);ws.on('framereceived',({payload})=>{
  if(!current)return;
  if(Buffer.isBuffer(payload)){current.audio_bytes+=payload.length;if(current.first_audio_ms===null)current.first_audio_ms=Date.now()-current.started;return;}
  try{const e=JSON.parse(payload);
   if(e.type==='turn_complete')current.complete=true;
   if(e.type==='candidates'){candidates=e.candidates;current.candidate_count=candidates.length;}
   if(e.type==='route'){current.route_id=e.product.id;current.route_ms=Date.now()-current.started;}
   if(e.type==='error')current.errors.push(e.code);
  }catch{}
 });});
 try{
  await page.goto(process.env.NATIVE_VOICE_ORIGIN||'http://localhost:8080');await require('./auth.cjs').signIn(page);
  // Drive the documented public protocol directly. A silent fake microphone
  // started through the UI would correctly expire after 60s of no speech.
  await page.evaluate(async()=>{
   const response=await fetch('/api/voice/sessions',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({language:'en-US'})});
   if(!response.ok)throw new Error('ticket_failed');
   const socket=new WebSocket(location.origin.replace('http','ws')+'/ws/voice','prompt-shop.voice.v1');
   socket.binaryType='arraybuffer';
   window.__probe.ping=setInterval(()=>{if(window.__probe.session&&socket.readyState===1)socket.send(JSON.stringify({type:'ping',session_id:window.__probe.session}));},20000);
  });
  await page.waitForFunction(()=>window.__probe.session);
  const selection=process.env.NATIVE_VOICE_SCENARIO==='selection';
  const bakery=process.env.NATIVE_VOICE_SCENARIO==='bakery';
  const steps=bakery
   ? [['Where is a bagel?','bagels'],['Where is a blueberry muffin?','blueberry-muffins'],['Find a burger bun.','burger-buns'],['Where is a cinnamon roll?','cinnamon-rolls'],['Where is a croissant?','croissants'],['Where is chocolate cake?','chocolate-cake']]
   : selection
   ? [['Hello.',null],['Where is milk?',null],[null,null]]
   : [['Hello.',null],['Where is whole milk?','milk-whole-1l'],['Repeat those directions.','milk-whole-1l'],['Where is jasmine rice?','jasmine-rice'],['Repeat those directions.','jasmine-rice'],['Where is toothpaste?','toothpaste'],['Thank you.',null],['Where is whole milk?','milk-whole-1l'],['What is two plus two?',null],['Where is jasmine rice?','jasmine-rice']];
  for(let [text,id] of steps){
   if(text===null){if(candidates.length<2)throw new Error("Expected ambiguous milk candidates");text="I choose "+candidates[0].name;id=candidates[0].id;}
   current={index:results.length+1,started:Date.now(),first_audio_ms:null,route_ms:null,audio_bytes:0,complete:false,route_id:null,errors:[]};
   await page.evaluate(text=>{const p=window.__probe;p.socket.send(JSON.stringify({type:'text',session_id:p.session,text}));},text);
   const deadline=Date.now()+25000;
   while(Date.now()<deadline&&!closed&&!current.complete&&!current.errors.length)await page.waitForTimeout(100);
   // Let the bounded last audio chunk drain before the next deliberate turn.
   await page.waitForTimeout(800);
   const {started,route_id,...result}=current;
   result.expected_route=id===null?route_id===null:route_id===id;
   console.log(JSON.stringify({turn:result}));
   results.push(result);current=null;
   if(closed)break;
  }
  const report={input:'public WebSocket text controls; no browser microphone/playout',scenario:bakery?'bakery word forms':selection?'ambiguous selection':'repeated conversation',turns:results,closed};
  console.log(JSON.stringify(report));
  if(process.env.NATIVE_REPORT_PATH)require('node:fs').writeFileSync(process.env.NATIVE_REPORT_PATH,JSON.stringify(report,null,2)+'\n');
  if(results.length!==steps.length||(selection&&results[1]?.candidate_count<2)||closed||results.some(r=>!r.complete||!r.audio_bytes||!r.expected_route||r.errors.length))process.exitCode=1;
  await page.evaluate(()=>{const p=window.__probe;clearInterval(p.ping);p.socket.send(JSON.stringify({type:'stop',session_id:p.session}));p.socket.close();});
 }finally{await browser.close();}
})().catch(e=>{console.error(e.name+': '+e.message.split('\n')[0]);process.exitCode=1;});
