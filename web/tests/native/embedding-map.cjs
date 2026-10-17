// Opt-in synthetic microphone -> Gemini Live -> tools -> visible map and playout.
const {chromium}=require('@playwright/test');
const fs=require('node:fs');
if(!process.env.NATIVE_VOICE_WAV)throw new Error('Set NATIVE_VOICE_WAV to a synthetic single-item request');
(async()=>{
 const browser=await chromium.launch({...(process.env.NATIVE_BROWSER_EXECUTABLE?{executablePath:process.env.NATIVE_BROWSER_EXECUTABLE}:{}),...(process.env.NATIVE_AUDIBLE==='1'?{ignoreDefaultArgs:['--mute-audio']}:{}),args:['--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream',`--use-file-for-fake-audio-capture=${process.env.NATIVE_VOICE_WAV}%noloop`]});
 const page=await browser.newPage({permissions:['microphone'],viewport:{width:390,height:900}});
 await page.addInitScript(()=>{
  window.__played=0;const Native=window.AudioContext;
  window.AudioContext=class extends Native{createBufferSource(){const source=super.createBufferSource(),start=source.start.bind(source);source.start=(...args)=>{window.__played++;return start(...args)};return source}};
 });
 let route=null,bytes=0,pcmEnergy=0,pcmSamples=0,complete=false,captions='',closed=false;const errors=[];
 page.on('websocket',ws=>{ws.on('close',()=>closed=true);ws.on('framereceived',({payload})=>{
  if(Buffer.isBuffer(payload)){bytes+=payload.length;for(let i=0;i+1<payload.length;i+=2){const sample=payload.readInt16LE(i);pcmEnergy+=sample*sample;pcmSamples++}return}
  let e;try{e=JSON.parse(payload)}catch{return}
  if(e.type==='route')route=e;
  if(e.type==='output_transcript')captions+=' '+e.text;
  if(e.type==='turn_complete')complete=true;
  if(e.type==='error')errors.push(e.code);
 })});
 try{
  await page.goto(process.env.NATIVE_VOICE_ORIGIN||'http://localhost:8080');await require('./auth.cjs').signIn(page);
  await page.getByRole('region',{name:'Voice controls'}).getByRole('button',{name:'Start voice',exact:true}).click();
  const deadline=Date.now()+40000;
  while(Date.now()<deadline&&!closed&&!(complete&&route&&bytes))await page.waitForTimeout(100);
  const expected=process.env.NATIVE_EXPECTED_PRODUCT||'bagels';
  const normalized=(text)=>text.toLowerCase().replace(/\b(one|two|three|four|five|six|seven|eight|nine|ten)\b/g,w=>String(['one','two','three','four','five','six','seven','eight','nine','ten'].indexOf(w)+1)).replace(/\s+/g,' ');
  const report={input:'synthetic spoken microphone; real Chromium capture/playout; Gemini Live and embedding API',
   complete,audio_bytes:bytes,audio_rms:Math.round(Math.sqrt(pcmEnergy/Math.max(1,pcmSamples))),playout_started:await page.evaluate(()=>window.__played>0),
   expected_route:route?.product.id===expected,map_visible:await page.getByTestId('route-path').isVisible(),
   selected_aisles:await page.locator('.aisle.selected').count(),
   spoken_aisle:!!route&&normalized(captions).includes(normalized(route.product.aisle.label)),
   spoken_shelf:!!route&&normalized(captions).includes(normalized(route.product.shelf.label)),
   error_codes:errors,closed};
  await page.screenshot({path:process.env.NATIVE_SCREENSHOT_PATH||'tmp/native-mobile-map.png',fullPage:true});
  console.log(JSON.stringify(report));if(process.env.NATIVE_REPORT_PATH)fs.writeFileSync(process.env.NATIVE_REPORT_PATH,JSON.stringify(report,null,2)+'\n');
  if(!complete||!bytes||report.audio_rms<10||!report.playout_started||!report.expected_route||!report.map_visible||report.selected_aisles!==1||!report.spoken_aisle||!report.spoken_shelf||errors.length||closed)process.exitCode=1;
  const stop=page.getByRole('region',{name:'Voice controls'}).getByRole('button',{name:'End voice',exact:true});if(await stop.isVisible())await stop.click();
 }finally{await browser.close()}
})().catch(e=>{console.error(e.name+': '+e.message.split('\n')[0]);process.exitCode=1});
