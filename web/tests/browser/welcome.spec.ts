import {test,expect,type Page,type WebSocketRoute} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import map from '../fixtures/store-map.json' with {type:'json'};
async function fixture(page:Page, options:{blocked?:boolean;restored?:boolean;backoffice?:boolean}={}){
 let signed=options.restored??false,tickets=0;const sockets:WebSocketRoute[]=[],messages:string[]=[];
 await page.addInitScript(({blocked})=>{
  const metrics={mic:0,played:0,closed:0,worklets:0,sequence:[] as string[]};(window as any).__welcomeAudio=metrics;(window as any).__blocked=blocked;
  const fetcher=window.fetch.bind(window);window.fetch=(input,init)=>{if(String(input)==='/api/auth/session'&&init?.method==='POST')metrics.sequence.push('login');return fetcher(input,init);};
  const track={enabled:true,onended:null,stop(){}};
  Object.defineProperty(navigator,'mediaDevices',{value:{async getUserMedia(){metrics.mic++;return {getTracks:()=>[track],getAudioTracks:()=>[track]};},async enumerateDevices(){return [];},addEventListener(){},removeEventListener(){}}});
  class Node{connect(){}disconnect(){}}
  const sources:any[]=[];(window as any).__drainWelcome=()=>{const list=sources.splice(0);list.forEach(s=>s.onended?.());};
  (window as any).AudioContext=class{
   state='running';currentTime=0;destination={};audioWorklet={async addModule(){metrics.worklets++;}};
   async resume(){metrics.sequence.push('resume');if((window as any).__blocked)throw new DOMException('blocked','NotAllowedError');}
   async close(){this.state='closed';metrics.closed++;}
   createGain(){return Object.assign(new Node(),{gain:{value:0}});}createMediaStreamSource(){return new Node();}
   createBuffer(_n:number,len:number){return {getChannelData:()=>new Float32Array(len)};}
   createBufferSource(){const s=Object.assign(new Node(),{onended:null,start(){metrics.played++;},stop(){}});sources.push(s);return s;}
  };
  (window as any).AudioWorkletNode=class extends Node{port={onmessage:null,postMessage(){},close(){}};};
 },{blocked:options.blocked??false});
 await page.route('**/api/**',async r=>{
  const path=new URL(r.request().url()).pathname,method=r.request().method();
  if(path==='/api/auth/session'){
   if(method==='POST'){if(r.request().postDataJSON().password!=='fixture-password')return r.fulfill({status:401,json:{}});signed=true;}
   if(method==='DELETE'){signed=false;return r.fulfill({status:204});}
   return r.fulfill({status:signed?200:401,json:signed?{enabled:true,username:'demo01',role:'admin',expires_at:new Date(Date.now()+3600000).toISOString(),csrf_token:'fixture'}:{}});
  }
  expect(signed).toBe(true);
  if(path==='/api/voice/sessions'){tickets++;return r.fulfill({status:201,json:{session_id:'welcome-'+tickets,ticket_expires_at:new Date(Date.now()+30000).toISOString(),ws_path:'/ws/voice'}});}
  if(path==='/api/store-map')return r.fulfill({json:map});
  if(path==='/api/products')return r.fulfill({json:{catalog_version:1,products:[],total:0,page:1,page_size:12,categories:[]}});
  if(path==='/api/backoffice/session')return r.fulfill({json:{csrf_token:'fixture',expires_at:new Date(Date.now()+3600000).toISOString()}});
  if(path==='/api/backoffice/products')return r.fulfill({json:{items:[],next_cursor:null}});
  if(path==='/api/backoffice/shelves')return r.fulfill({json:{items:[]}});
  throw new Error(path);
 });
 await page.routeWebSocket('**/ws/voice',ws=>{sockets.push(ws);ws.onMessage(v=>{if(typeof v==='string')messages.push(v);});});
 await page.goto(options.backoffice?'/backoffice':'/');
 return {tickets:()=>tickets,messages,
  login:async(password='fixture-password')=>{await page.getByLabel('Username',{exact:true}).fill('demo01');await page.getByLabel('Password',{exact:true}).fill(password);await page.getByRole('button',{name:'Sign in',exact:true}).click();},
  async ready(index=0){await expect.poll(()=>sockets.length).toBe(index+1);sockets[index].send(JSON.stringify({type:'ready',session_id:'welcome-'+(index+1),expires_at:new Date(Date.now()+600000).toISOString(),input_rate:16000,output_rate:24000}));},
  reply(index=0){const ws=sockets[index],base={session_id:'welcome-'+(index+1),turn_id:'turn-1'};ws.send(JSON.stringify({...base,type:'audio_start',generation_id:'generation-1'}));ws.send(Buffer.alloc(3200));ws.send(JSON.stringify({...base,type:'audio_end',generation_id:'generation-1'}));ws.send(JSON.stringify({...base,type:'turn_complete'}));}
 };
}

test('fresh login greets once, unlocks output before auth, never captures, and waits for drain',async({page})=>{
 const f=await fixture(page);await f.login('wrong');await expect(page.getByRole('status')).toContainText('incorrect');expect(f.tickets()).toBe(0);expect(await page.evaluate(()=>(window as any).__welcomeAudio.closed)).toBe(1);
 await f.login();const region=page.getByRole('region',{name:'Monti welcome'});await expect(region).toBeVisible();await f.ready();
 await expect.poll(()=>f.messages.some(m=>JSON.parse(m).type==='text')).toBe(true);expect(f.messages.filter(m=>JSON.parse(m).type==='text')).toHaveLength(1);
 const metrics=await page.evaluate(()=>(window as any).__welcomeAudio);expect(metrics.mic).toBe(0);expect(metrics.worklets).toBe(0);expect(metrics.sequence.slice(0,2)).toEqual(['resume','login']);
 f.reply();await expect.poll(()=>page.evaluate(()=>(window as any).__welcomeAudio.played)).toBe(1);await expect(region.getByRole('button',{name:'Skip welcome'})).toBeVisible();
 await page.evaluate(()=>(window as any).__drainWelcome());await expect(region.getByRole('button',{name:'Dismiss welcome'})).toBeVisible();
 await page.evaluate(()=>window.dispatchEvent(new Event('focus')));expect(f.tickets()).toBe(1);
 await page.setViewportSize({width:320,height:900});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);expect((await new AxeBuilder({page}).analyze()).violations).toEqual([]);
 await page.reload();await expect(region).toHaveCount(0);expect(f.tickets()).toBe(1);
});

test('blocked output offers an explicit retry without microphone access or early provider admission',async({page})=>{
 const f=await fixture(page,{blocked:true});await f.login();const play=page.getByRole('button',{name:'Play welcome',exact:true});await expect(play).toBeVisible();expect(f.tickets()).toBe(0);
 await page.evaluate(()=>(window as any).__blocked=false);await play.click();await f.ready();f.reply();await expect.poll(()=>page.evaluate(()=>(window as any).__welcomeAudio.played)).toBe(1);await page.evaluate(()=>(window as any).__drainWelcome());await expect(page.getByRole('button',{name:'Dismiss welcome'})).toBeVisible();expect(await page.evaluate(()=>(window as any).__welcomeAudio.mic)).toBe(0);
});

test('Start voice cancels welcome and explicitly opens microphone for a fresh conversation',async({page})=>{
 const f=await fixture(page);await f.login();await f.ready();await page.locator('.desktop-voice').getByRole('button',{name:'Start voice',exact:true}).click();await expect(page.getByRole('region',{name:'Monti welcome'})).toHaveCount(0);await f.ready(1);await expect(page.locator('.desktop-voice').getByText('Listening',{exact:true})).toBeVisible();expect(await page.evaluate(()=>(window as any).__welcomeAudio.mic)).toBe(1);expect(f.tickets()).toBe(2);await page.getByRole('button',{name:'End voice',exact:true}).click();
});

for(const action of ['logout','navigate','hidden','skip'])test(`welcome cancels on ${action}`,async({page})=>{
 const f=await fixture(page);await f.login();await f.ready();
 if(action==='logout')await page.getByRole('button',{name:'Sign out',exact:true}).click();
 if(action==='navigate')await page.getByRole('link',{name:'Backoffice',exact:true}).click();
 if(action==='hidden')await page.evaluate(()=>{Object.defineProperty(document,'hidden',{value:true,configurable:true});document.dispatchEvent(new Event('visibilitychange'));});
 if(action==='skip')await page.getByRole('button',{name:'Skip welcome',exact:true}).click();
 await expect(page.getByRole('region',{name:'Monti welcome'})).toHaveCount(0);await expect.poll(()=>page.evaluate(()=>(window as any).__welcomeAudio.closed)).toBeGreaterThan(0);expect(await page.evaluate(()=>(window as any).__welcomeAudio.mic)).toBe(0);
});

for(const mode of ['restored','backoffice'])test(`no auto welcome for ${mode} session`,async({page})=>{
 const f=await fixture(page,{restored:mode==='restored',backoffice:mode==='backoffice'});if(mode==='backoffice')await f.login();await expect(page.getByRole('button',{name:'Sign out',exact:true})).toBeVisible();expect(f.tickets()).toBe(0);await expect(page.getByRole('region',{name:'Monti welcome'})).toHaveCount(0);
});
