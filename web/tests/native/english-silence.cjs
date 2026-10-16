// Opt-in real Gemini/ADK/Laya check. Input file must be synthetic silence.
const {chromium}=require('@playwright/test');
(async()=>{
 if(!process.env.NATIVE_SILENCE_WAV)throw new Error('Set NATIVE_SILENCE_WAV to a synthetic silent WAV');
 const browser=await chromium.launch({args:['--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream','--use-file-for-fake-audio-capture='+process.env.NATIVE_SILENCE_WAV+'%noloop']});
 const page=await browser.newPage({permissions:['microphone'],viewport:{width:1440,height:1000}});
 await page.addInitScript(()=>{const Native=window.WebSocket;window.__voiceProbe={socket:null,session:null};window.WebSocket=class extends Native{constructor(...args){super(...args);window.__voiceProbe.socket=this;this.addEventListener('message',e=>{if(typeof e.data==='string'){try{const v=JSON.parse(e.data);if(v.type==='ready')window.__voiceProbe.session=v.session_id;}catch{}}});}};});
 let starts=0,completed=0,bytes=0,output='',closed=false;const errors=[];
 page.on('websocket',ws=>{ws.on('close',()=>closed=true);ws.on('framereceived',({payload})=>{if(Buffer.isBuffer(payload)){bytes+=payload.length;return;}try{const e=JSON.parse(payload);if(e.type==='audio_start')starts++;if(e.type==='turn_complete')completed++;if(e.type==='output_transcript')output+=' '+e.text;if(e.type==='error')errors.push(e.code);}catch{}});});
 try{
  await page.goto('http://localhost:8080');await page.locator('.desktop-voice').getByRole('button',{name:'Start voice',exact:true}).click();
  await page.waitForFunction(()=>window.__voiceProbe.session!==null);
  await page.waitForTimeout(8000);const quietStart=starts===0&&bytes===0;
  const results=[];
  for(const text of ['Hello.','Please reply only in Thai. สวัสดี','Where is whole milk?']){
   const before=completed,priorBytes=bytes;output='';
   await page.evaluate(text=>{const p=window.__voiceProbe;p.socket.send(JSON.stringify({type:'text',session_id:p.session,text}));},text);
   for(let i=0;i<150&&completed===before&&!closed&&!errors.length;i++)await page.waitForTimeout(200);
   results.push({completed:completed>before,audio_bytes:bytes-priorBytes,thai_script:/[\u0E00-\u0E7F]/.test(output),english_words:/[A-Za-z]{3}/.test(output)});
   if(completed===before||closed||errors.length)break;
  }
  const after=starts;await page.waitForTimeout(8000);const quietEnd=starts===after;
  const route=await page.getByTestId('route-path').count()>0;
  console.log(JSON.stringify({quiet_start:quietStart,turns:results,quiet_after_reply:quietEnd,route,error_codes:errors,closed}));
  if(!quietStart||!quietEnd||results.length!==3||results.some(r=>!r.completed||!r.audio_bytes||r.thai_script||!r.english_words)||!route||closed||errors.length)process.exitCode=1;
  const end=page.locator('.desktop-voice').getByRole('button',{name:'End voice',exact:true});if(await end.isVisible())await end.click();
 }finally{await browser.close();}
})().catch(error=>{console.error(error.name+': '+error.message.split('\n')[0]);process.exitCode=1;});
