// Opt-in local browser smoke; never captures credential-bearing traces/HTTP bodies.
const {chromium}=require('@playwright/test');
const {signIn}=require('./auth.cjs');
(async()=>{
 if(process.env.NATIVE_AUTH_TEST!=='1')throw new Error('Set NATIVE_AUTH_TEST=1 for the local shared-auth smoke');
 const origin=process.env.NATIVE_VOICE_ORIGIN||'http://localhost:8080';if(new URL(origin).hostname!=='localhost')throw new Error('Local smoke only');
 const browser=await chromium.launch({args:['--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream']});
 const check=(value,message)=>{if(!value)throw new Error(message);};
 try{
  for(const [username,role]of [['demo02','shopper'],['demo01','admin']]){
   const context=await browser.newContext({permissions:['microphone']});const page=await context.newPage();let readySeconds=0;page.on('websocket',ws=>ws.on('framereceived',({payload})=>{if(typeof payload==='string'){try{const e=JSON.parse(payload);if(e.type==='ready')readySeconds=(Date.parse(e.expires_at)-Date.now())/1000;}catch{}}}));await page.goto(origin);
   await page.getByRole('heading',{name:'Welcome back'}).waitFor();
   check((await page.request.get(origin+'/api/products')).status()===401,'anonymous catalog admitted');
   process.env.NATIVE_USERNAME=username;await signIn(page);await page.getByRole('button',{name:'Sign out',exact:true}).waitFor();
   await page.locator('.catalog-browser .product-card').first().waitFor();
   const identity=await(await page.request.get(origin+'/api/auth/session')).json();check(identity.role===role,'incorrect role');
   const backoffice=await page.request.get(origin+'/api/backoffice/products');check(backoffice.status()===(role==='admin'?200:403),'backoffice role failed');
   if(role==='shopper'){
    const panel=page.locator('.desktop-voice');check(await panel.getByRole('button',{name:'Speaker mode on',exact:true}).getAttribute('aria-pressed')==='true','speaker mode not default on');await panel.getByText('Audio settings',{exact:true}).click();await panel.getByRole('button',{name:'Enable device names',exact:true}).click();
    await page.waitForFunction(()=>document.querySelectorAll('.desktop-voice select option').length>1);
    await panel.getByLabel('Microphone',{exact:true}).selectOption({index:1});
    await panel.getByRole('button',{name:'Start voice',exact:true}).click();await panel.getByText('Listening',{exact:true}).waitFor({timeout:35000});check(readySeconds>598&&readySeconds<=600,'server expiry is not ten minutes');check(/(?:10:00|9:5[0-9]) left/.test(await panel.innerText()),'countdown does not start at ten minutes');
   }else{await page.goto(origin+'/backoffice');await page.getByRole('heading',{name:'Catalog workspace'}).waitFor();}
   await page.getByRole('button',{name:'Sign out',exact:true}).click();await page.getByRole('heading',{name:'Welcome back'}).waitFor();
   check((await page.request.get(origin+'/api/products')).status()===401,'logout replay');
   console.log(JSON.stringify({role,signin:true,catalog:true,backoffice_status:backoffice.status(),voice_ready:role==='shopper',logout:true}));await context.close();
  }
 }finally{await browser.close();}
})().catch(e=>{console.error(e.name+': '+e.message.split('\n')[0]);process.exitCode=1;});
