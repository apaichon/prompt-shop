// Opt-in real-provider login welcome check. No trace, HAR, screenshot or raw speech.
const {chromium}=require('@playwright/test');
const fs=require('node:fs'),path=require('node:path');
(async()=>{
 if(process.env.NATIVE_WELCOME_TEST!=='1')throw new Error('Set NATIVE_WELCOME_TEST=1 to test the configured real provider');
 const handout=process.env.NATIVE_ACCOUNTS_FILE;if(!handout)throw new Error('Private account handout required');
 const username=process.env.NATIVE_USERNAME||'demo02';const line=fs.readFileSync(handout,'utf8').split(/\r?\n/).find(l=>l.startsWith(username+'  '));if(!line)throw new Error('Test account unavailable');const password=line.trim().split(/\s+/)[1];
 const origin=process.env.NATIVE_VOICE_ORIGIN||'http://localhost:8080';if(new URL(origin).hostname!=='localhost')throw new Error('Local welcome smoke only');
 const browser=await chromium.launch();const context=await browser.newContext({permissions:process.env.NATIVE_STATIC_DIR?['local-network-access']:[],viewport:{width:1440,height:1000}});const page=await context.newPage();
 await page.addInitScript(()=>{
  window.__welcomeProbe={microphone_requests:0,played_chunks:0,closed_contexts:0};const m=window.__welcomeProbe;
  const media=navigator.mediaDevices;if(media?.getUserMedia){const get=media.getUserMedia.bind(media);media.getUserMedia=(...a)=>{m.microphone_requests++;return get(...a);};}
  const Context=window.AudioContext;window.AudioContext=class extends Context{
   createBufferSource(){const source=super.createBufferSource(),start=source.start.bind(source);source.start=(...a)=>{m.played_chunks++;return start(...a);};return source;}
   close(){m.closed_contexts++;return super.close();}
  };
 });
 // Fulfilled candidate HTML needs local-network permission, matching the existing audio harness.
 if(process.env.NATIVE_STATIC_DIR){const root=path.resolve(process.env.NATIVE_STATIC_DIR);await page.route('**/*',async r=>{const u=new URL(r.request().url());if(u.origin!==origin||u.pathname.startsWith('/api/')||u.pathname.startsWith('/ws/'))return r.continue();const file=path.resolve(root,'.'+decodeURIComponent(u.pathname==='/'?'/index.html':u.pathname));if(!file.startsWith(root+path.sep))return r.abort();try{await r.fulfill({path:file});}catch{await r.abort();}});}
 let socket_errors=0;
 let stage='open',pageErrors=0;page.on('pageerror',()=>pageErrors++);
 let tickets=0,sockets=0,closed=0,audioBytes=0,complete=false,text='',catalogEvents=0;const errors=[];
 page.on('request',r=>{if(new URL(r.url()).pathname==='/api/voice/sessions')tickets++;});
 page.on('websocket',ws=>{sockets++;ws.on('socketerror',()=>socket_errors++);ws.on('close',()=>closed++);ws.on('framereceived',({payload})=>{if(Buffer.isBuffer(payload)){audioBytes+=payload.length;return;}try{const e=JSON.parse(payload);if(e.type==='turn_complete')complete=true;if(e.type==='output_transcript')text+=' '+e.text;if(e.type==='route'||e.type==='candidates')catalogEvents++;if(e.type==='error')errors.push(e.code);}catch{}});});
 const check=(value,message)=>{if(!value)throw new Error(message);};
 try{
  await page.goto(origin);stage='failed-login';await page.getByLabel('Username',{exact:true}).fill(username);await page.getByLabel('Password',{exact:true}).fill('invalid-welcome-test-only');await page.getByRole('button',{name:'Sign in',exact:true}).click();await page.getByText('Username or password is incorrect.',{exact:true}).waitFor();check(tickets===0,'failed login admitted voice');
  stage='successful-login';await page.getByLabel('Password',{exact:true}).fill(password);const started=Date.now();await page.getByRole('button',{name:'Sign in',exact:true}).click();
  await page.getByRole('region',{name:'Monti welcome'}).waitFor();stage='welcome-playback';await page.getByRole('button',{name:'Dismiss welcome',exact:true}).waitFor({timeout:30000});
  const metrics=await page.evaluate(()=>window.__welcomeProbe);const report={candidate_static_assets:!!process.env.NATIVE_STATIC_DIR,elapsed_ms:Date.now()-started,failed_login_voice_tickets:0,tickets,sockets,closed_sockets:closed,complete,audio_bytes:audioBytes,greeting_words:/hi\b|hello|welcome/i.test(text),assistant_name:/mont[iy]/i.test(text),catalog_events:catalogEvents,error_codes:errors,...metrics};
  check(metrics.microphone_requests===0,'welcome requested microphone');check(complete&&audioBytes>0&&metrics.played_chunks>0&&report.greeting_words,'welcome did not audibly complete');check(tickets===1&&sockets===1&&closed===1,'welcome transport not released');check(!errors.length&&catalogEvents===0,'welcome entered catalog/error path');check(await page.locator('.desktop-voice').getByRole('button',{name:'Start voice',exact:true}).isVisible(),'microphone action was replaced');
  await page.evaluate(()=>window.dispatchEvent(new Event('focus')));await page.waitForTimeout(300);check(tickets===1,'focus replayed welcome');
  console.log(JSON.stringify(report));if(process.env.NATIVE_REPORT_PATH)fs.writeFileSync(process.env.NATIVE_REPORT_PATH,JSON.stringify(report,null,2)+'\n');
  await page.getByRole('button',{name:'Sign out',exact:true}).click();await page.getByRole('heading',{name:'Welcome back',exact:true}).waitFor();
 }catch(e){console.log(JSON.stringify({stage,page_errors:pageErrors,socket_errors,tickets,sockets,closed_sockets:closed,audio_bytes:audioBytes,complete,error_codes:errors,play_welcome:await page.getByRole('button',{name:'Play welcome',exact:true}).isVisible().catch(()=>false),metrics:await page.evaluate(()=>window.__welcomeProbe).catch(()=>null)}));throw e;}finally{await context.close();await browser.close();}
})().catch(e=>{console.error(e.name+': '+e.message.split('\n')[0]);process.exitCode=1;});
