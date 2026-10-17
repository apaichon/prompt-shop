import { test, expect, type Page, type WebSocketRoute } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import map from '../fixtures/store-map.json' with { type: 'json' };
import search from '../fixtures/search-response.json' with { type: 'json' };
import route from '../fixtures/route-response.json' with { type: 'json' };
import events from '../fixtures/live-events.json' with { type: 'json' };

async function fixture(page: Page, options: { denied?: boolean; realAudio?: boolean; devices?: boolean } = {}) {
  let searches = 0, tickets = 0;
  const messages: (string | Buffer)[] = [];
  let socket: WebSocketRoute | undefined;
  if (!options.realAudio) await page.addInitScript(({ denied, devices }) => {
    const metrics = { opened: 0, stopped: 0, played: 0, flushed: 0, capture: false, muted: false, constraints: null as any, sink: "", tones: 0, closed: 0 };
    (window as any).__audio = metrics;
    const track = { enabled: true, onended: null, stop() { metrics.stopped++; } };
    Object.defineProperty(navigator, 'mediaDevices', { value: { async enumerateDevices(){return devices?[{kind:'audioinput',deviceId:'usb-mic',label:'USB microphone'},{kind:'audiooutput',deviceId:'headset',label:'Headphones'}]:[];}, async getUserMedia(constraints:any) {
      metrics.constraints=constraints;
      metrics.opened++; if (denied) throw new DOMException('Denied', 'NotAllowedError');
      return { getTracks: () => [track], getAudioTracks: () => [track] };
    } } });
    class Node { connect() {} disconnect() {} }
    (window as any).AudioContext = class {
      state = 'running'; currentTime = 0; destination = {}; audioWorklet = { async addModule() {} };
      async resume() {} async close() { this.state = 'closed'; metrics.closed++; }
      createOscillator(){return Object.assign(new Node(),{frequency:{value:0},onended:null,start(){metrics.tones++;},stop(){}});}
      createMediaStreamSource() { return new Node(); }
      createGain() { return Object.assign(new Node(), { gain: { value: 0 } }); }
      createBuffer(_channels: number, length: number) { return { getChannelData: () => new Float32Array(length) }; }
      createBufferSource() { const source:any=Object.assign(new Node(), { buffer: null, onended: null, start() { metrics.played++; }, stop() { metrics.flushed++; } }); (window as any).__drain=()=>source.onended?.(); return source; }
    };
    if(devices)(window as any).AudioContext.prototype.setSinkId=async(id:string)=>{metrics.sink=id;};
    (window as any).AudioWorkletNode = class extends Node {
      constructor(){super();(window as any).__captureNode=this;}
      port = { onmessage: null, postMessage(value: string) { metrics.capture = value === 'start'; }, close() {} };
    };
  }, { denied: options.denied ?? false, devices: options.devices ?? false });
  await page.route('**/api/**', async (request) => {
    const path = new URL(request.request().url()).pathname;
    if(path.startsWith('/api/backoffice/')){await request.fulfill({status:401,json:{error:{code:'AUTH_REQUIRED',message:'Log in',retryable:false},request_id:'fixture'}});return}
    let body: unknown;
    if(path === '/api/auth/session') body = {enabled:false};
    else if (path === '/api/products') body = {catalog_version:1,products:[],total:0,page:1,page_size:12,categories:[]};
    else if (path === '/api/store-map') body = map;
    else if (path === '/api/search') { searches++; body = search; }
    else if (path === '/api/routes') body = route;
    else if (path === '/api/voice/sessions') { tickets++; body = { session_id: 'fixture-session', ticket_expires_at: new Date(Date.now() + 30000).toISOString(), ws_path: '/ws/voice' }; }
    else throw new Error(`Unexpected API ${path}`);
    await request.fulfill({ status: path === '/api/voice/sessions' ? 201 : 200, json: body });
  });
  await page.routeWebSocket('**/ws/voice', (ws) => { socket = ws; ws.onMessage((message) => messages.push(message)); });
  const send = (type: string, extras = {}) => socket!.send(JSON.stringify({ type, ...events.find((e) => e.type === type), ...extras }));
  await page.goto('/');
  await expect(page.getByRole('img', { name: /floor map/i })).toBeVisible();
  return {
    send, messages, searches: () => searches, tickets: () => tickets,
    binary: () => socket!.send(Buffer.alloc(3200)),
    async start(scope = page.locator('.desktop-voice')) {
      socket = undefined;
      await scope.getByRole('button', { name: /Start voice|Restart voice/ }).click();
      await expect.poll(() => !!socket).toBe(true);
      send('ready', { expires_at: new Date(Date.now() + 600000).toISOString() });
      await expect(scope.getByText('Listening', { exact: true })).toBeVisible();
    }
  };
}

for (const width of [320, 390, 768, 1280, 1440]) test(`typed flow, map and accessibility at ${width}px`, async ({ page }) => {
  await page.setViewportSize({ width, height: 900 });
  const f = await fixture(page);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({path:`test-results/idle-${width}.png`,fullPage:true});
  expect(f.tickets()).toBe(0);
  await page.getByRole('textbox', { name: 'Item name' }).fill('milk');
  await page.getByRole('textbox', { name: 'Item name' }).press('Enter');
  await expect(page.getByRole('heading', { name: '1 match found' })).toBeFocused();
  await page.getByRole('button', { name: 'Show route to Whole milk 1 L' }).focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('#route-heading')).toBeFocused();
  await expect(page.getByText(route.steps[0], { exact: true })).toBeVisible();
  await expect(page.getByTestId('route-path')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.screenshot({ path: `test-results/customer-${width}.png`, fullPage: true });
  await page.getByRole('link', { name: 'Backoffice' }).click();
  await expect(page.getByRole('heading', { name: 'Catalog workspace' })).toBeVisible();
  await page.reload(); await expect(page.getByRole('heading', { name: 'Catalog workspace' })).toBeVisible();
});

test('captions are escaped and never become facts; voice choice, interruption and Stop', async ({ page }) => {
  const f = await fixture(page); await f.start();
  await page.getByRole('textbox', { name: 'Item name' }).focus();
  f.send('input_transcript', { text: '<img src=x onerror=alert(1)>' });
  f.send('output_transcript', { text: 'Milk in imaginary aisle 99' });
  f.send('navigate', { type: 'navigate', url: 'https://other.test' });
  await expect(page.locator('.desktop-voice .captions')).toContainText('<img src=x onerror=alert(1)>');
  expect(f.searches()).toBe(0); await expect(page.locator('.product-card')).toHaveCount(0);
  await expect(page.locator('.captions img')).toHaveCount(0);
  f.send('candidates'); await expect(page.locator('.product-card')).toHaveCount(1);
  await expect(page.getByRole('textbox', { name: 'Item name' })).toBeFocused();
  // Spoken selection arrives as a newer verified route, preserving keyboard focus.
  f.send('interrupted', { turn_id: 'turn-2', generation_id: 'generation-2' });
  f.send('route', { turn_id: 'turn-2' });
  await expect(page.getByTestId('route-path')).toBeVisible();
  await expect(page.getByRole('textbox', { name: 'Item name' })).toBeFocused();
  f.send('audio_start', { turn_id: 'turn-2', generation_id: 'generation-2' }); f.binary();
  await expect.poll(() => page.evaluate(() => (window as any).__audio.played)).toBe(1);
  f.send('interrupted', { turn_id: 'turn-2', generation_id: 'generation-2' }); f.binary();
  await expect.poll(() => page.evaluate(() => (window as any).__audio.flushed)).toBe(1);
  await page.getByRole('button', { name: 'Mute mic', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Unmute mic', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await page.getByRole('button', { name: 'Mute sound', exact: true }).click();
  await page.getByRole('button', { name: 'End voice' }).click();
  f.send('candidates', { turn_id: 'turn-9', candidates: [] });
  await expect(page.locator('.product-card')).toHaveCount(1);
  await expect(page.getByTestId('route-path')).toBeVisible();
  expect(await page.evaluate(() => (window as any).__audio.capture)).toBe(false);
  expect(await page.evaluate(() => (window as any).__audio.stopped)).toBeGreaterThan(0);
});

test('clicked voice choice sends identity and focuses verified directions', async ({ page }) => {
  const f = await fixture(page); await f.start(); f.send('candidates');
  await page.getByRole('button', { name: 'Show route to Whole milk 1 L' }).click();
  await expect.poll(() => f.messages.some((m) => typeof m === 'string' && JSON.parse(m).type === 'select')).toBe(true);
  const selection = JSON.parse(f.messages.find((m) => typeof m === 'string' && JSON.parse(m).type === 'select') as string);
  expect(selection).toMatchObject({ search_id: 'search-1', product_id: 'milk-whole-1l', session_id: 'fixture-session' });
  f.send('route', { turn_id: 'turn-2' }); await expect(page.locator('#route-heading')).toBeFocused();
});

test('mobile modal traps keyboard focus, restores launcher and stops capture on Escape', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 900 }); await page.emulateMedia({ reducedMotion: 'reduce' });
  const f = await fixture(page); const launcher = page.getByRole('button', { name: 'Open voice assistant', exact: true });
  await launcher.click(); const dialog = page.getByRole('dialog'); await f.start(dialog);
  for (let n = 0; n < 10; n++) { await page.keyboard.press('Tab'); expect(await page.evaluate(() => !!document.activeElement?.closest('dialog'))).toBe(true); }
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.screenshot({ path: 'test-results/mobile-voice.png', fullPage: true });
  await page.keyboard.press('Escape'); await expect(dialog).not.toBeVisible(); await expect(launcher).toBeFocused();
  f.send('route', { turn_id: 'turn-99' }); await expect(launcher).toBeFocused();
  expect(await page.evaluate(() => (window as any).__audio.capture)).toBe(false);
  expect(await page.evaluate(() => (window as any).__audio.stopped)).toBeGreaterThan(0);
});

test('microphone denial leaves typed search usable without reload', async ({ page }) => {
  const f = await fixture(page, { denied: true });
  await page.getByRole('button', { name: 'Start voice' }).click();
  await expect(page.getByRole('alert')).toContainText('permissions'); expect(f.tickets()).toBe(0);
  await page.getByRole('button', { name: 'Milk', exact: true }).click();
  await expect(page.locator('.product-card')).toHaveCount(1);
});

test('no-match and classifier recovery are distinct and cannot invent locations', async ({ page }) => {
  const f = await fixture(page); await f.start();
  f.send('candidates', { candidates: [] }); await expect(page.getByText(/No matching items/)).toBeVisible();
  for (const [code, message] of [['CLASSIFIER_TIMEOUT', 'in time'], ['CLASSIFIER_BUSY', 'busy'], ['CLASSIFICATION_ABSTAINED', 'another phrase']]) {
    f.send('error', { code }); await expect(page.locator('.desktop-voice .voice-notice')).toContainText(message);
    await expect(page.locator('.product-card')).toHaveCount(0);
  }
});

test('real Chromium worklet captures bounded PCM only after ready and stops on End', async ({ browser }) => {
  const context = await browser.newContext({ permissions: ['microphone'] });
  const page = await context.newPage(); const f = await fixture(page, { realAudio: true });
  await f.start();
  await expect.poll(() => f.messages.filter(Buffer.isBuffer).length).toBeGreaterThan(2);
  expect(f.messages.filter(Buffer.isBuffer).every((m) => m.length === 640)).toBe(true);
  await page.getByRole('button', { name: 'End voice' }).click();
  await context.close();
});

test('mobile minimize and desktop resize retain one voice controller; Close ends it', async ({page}) => {
  await page.setViewportSize({width:390,height:900});
  const f=await fixture(page); const launcher=page.getByRole('button',{name:'Open voice assistant',exact:true});
  await launcher.click(); const dialog=page.getByRole('dialog'); await f.start(dialog);
  await dialog.getByRole('button',{name:'Minimize'}).click();
  await expect(dialog).not.toBeVisible(); await expect(launcher).toBeFocused();
  await expect(page.locator('.mobile-voice-dock')).toContainText('Mic on');
  expect(await page.evaluate(()=>(window as any).__audio.capture)).toBe(true);
  await launcher.click(); await expect(dialog.getByRole('button',{name:'End voice',exact:true})).toBeVisible();
  await page.setViewportSize({width:1280,height:900}); await expect(dialog).not.toBeVisible();
  await expect(page.locator('.desktop-voice').getByRole('button',{name:'End voice',exact:true})).toBeFocused();
  expect(f.tickets()).toBe(1); expect(await page.evaluate(()=>(window as any).__audio.opened)).toBe(1);
  await page.locator('.desktop-voice').getByRole('button',{name:'End voice',exact:true}).click();
  expect(await page.evaluate(()=>(window as any).__audio.capture)).toBe(false);
});

test('missing avatar falls back without stopping microphone or typed lookup',async({page})=>{
  await page.route('**/avatar/monti/atlas.webp',r=>r.abort());
  const f=await fixture(page); await expect(page.locator('.desktop-voice .avatar-fallback')).toBeVisible();
  expect(f.tickets()).toBe(0); await f.start();
  await page.getByRole('button',{name:'End voice',exact:true}).click();
  await page.getByRole('button',{name:'Milk',exact:true}).click();
  await expect(page.locator('.product-card')).toHaveCount(1);
});

test('mobile selection moves the chosen match first while directions keep focus',async({page})=>{
  await page.setViewportSize({width:390,height:900}); await fixture(page);
  await page.route('**/api/search',r=>r.fulfill({json:{...search,ambiguous:true,candidates:[
    {...search.candidates[0],id:'milk-oat-fixture',name:'Oat milk fixture'},
    {...search.candidates[0],id:'milk-skim-fixture',name:'Skim milk fixture'},
    search.candidates[0]]}}));
  await page.getByRole('button',{name:'Milk',exact:true}).click();
  await expect(page.locator('.product-card').first()).toContainText('Oat milk fixture');
  await page.getByRole('button',{name:'Show route to Whole milk 1 L'}).click();
  await expect(page.locator('.product-card').first()).toContainText('Whole milk 1 L');
  await expect(page.locator('#route-heading')).toBeFocused();
  await expect(page.getByRole('button',{name:'Show route to Oat milk fixture'})).not.toBeVisible();
  await page.getByRole('button',{name:'Show all 3 matches'}).click();
  await expect(page.getByRole('button',{name:'Show route to Oat milk fixture'})).toBeVisible();
});

test('mobile voice controls clear the virtual keyboard and retain 44px targets',async({page})=>{
  await page.setViewportSize({width:320,height:900});
  await page.addInitScript(()=>{
    const viewport=Object.assign(new EventTarget(),{height:900,scale:1,offsetTop:0});
    Object.defineProperty(window,'visualViewport',{value:viewport,configurable:true});
    (window as any).__keyboard=(height:number)=>{viewport.height=height;viewport.dispatchEvent(new Event('resize'));};
  });
  await fixture(page); await page.getByRole('textbox',{name:'Item name'}).focus();
  await page.evaluate(()=>(window as any).__keyboard(600));
  await expect(page.locator('.mobile-voice-dock')).toHaveCSS('bottom','300px');
  for(const button of await page.locator('.mobile-voice-dock button').all()){
    const bounds=await button.boundingBox(); expect(bounds!.width).toBeGreaterThanOrEqual(44); expect(bounds!.height).toBeGreaterThanOrEqual(44);
  }
});


test('one timed-out voice turn keeps the microphone and session usable',async({page})=>{
  const f=await fixture(page); await f.start();
  f.send('interrupted');
  f.send('error',{turn_id:'turn-1',code:'TURN_TIMEOUT',message:'private detail must not render',retryable:true});
  await expect(page.locator('.desktop-voice')).toContainText('please ask again');
  await expect(page.getByRole('button',{name:'End voice',exact:true})).toBeVisible();
  expect(await page.evaluate(()=>(window as any).__audio.capture)).toBe(true);
  f.send('candidates');
  await expect(page.locator('.product-card')).toHaveCount(0);
  f.send('interrupted',{turn_id:'turn-2',generation_id:'generation-2'});
  f.send('candidates',{turn_id:'turn-2'});f.send('route',{turn_id:'turn-2'});
  await expect(page.locator('.verified-location')).toContainText('Route found');
  expect(f.tickets()).toBe(1);expect(await page.evaluate(()=>(window as any).__audio.opened)).toBe(1);
  await page.getByRole('button',{name:'End voice',exact:true}).click();
  expect(await page.evaluate(()=>(window as any).__audio.capture)).toBe(false);
});


test('quiet microphone PCM cannot discard a reply without a server turn change',async({page})=>{
  const f=await fixture(page);await f.start();f.send('interrupted');
  f.send('audio_start');f.binary();
  await expect.poll(()=>page.evaluate(()=>(window as any).__audio.played)).toBe(1);
  await page.evaluate(()=>{
    const quiet=new Int16Array(1600).fill(400);
    (window as any).__captureNode.port.onmessage({data:quiet.buffer});
  });
  f.binary();f.send('output_transcript',{text:'The reply is still playing.',final:true});
  await expect.poll(()=>page.evaluate(()=>(window as any).__audio.played)).toBe(2);
  await expect(page.locator('.desktop-voice')).toContainText('The reply is still playing.');
  await page.getByRole('button',{name:'End voice',exact:true}).click();
});


test('published gallery filters, locates, shows same-shelf imagery and falls back on missing artwork',async({page})=>{
 await fixture(page);
 const milk=route.product;
 const almond={...milk,id:'almond-milk-1l',name:'Almond milk 1 L'};
 const calls:string[]=[];
 await page.route('**/api/products?**',async r=>{
  const url=new URL(r.request().url());calls.push(url.search);
  const shelf=url.searchParams.get('shelf_id');const category=url.searchParams.get('category');
  await r.fulfill({json:{catalog_version:1,products:shelf?[milk,almond]:category==='Produce'?[]:[milk],total:category==='Produce'&&!shelf?0:shelf?2:1,page:1,page_size:shelf?24:12,categories:[{name:'Dairy',count:1},{name:'Produce',count:1}]}});
 });
 await page.reload();
 const gallery=page.locator('.catalog-browser');
 await expect(gallery.getByRole('heading',{name:milk.name})).toBeVisible();
 await expect(gallery.locator('.product-packshot')).toHaveCount(1);
 await gallery.getByRole('button',{name:'Produce (1 products)',exact:true}).click();
 await expect(gallery.getByText('No products in this category.')).toBeVisible();
 await gallery.getByRole('button',{name:'Dairy (1 products)',exact:true}).click();
 await gallery.getByRole('button',{name:`Show route to ${milk.name}`,exact:true}).click();
 await expect(page.getByTestId('route-path')).toBeVisible();
 const shelf=page.locator('.shelf-display');
 await expect(shelf.getByRole('button',{name:`Show route to ${milk.name}`,exact:true})).toHaveAttribute('aria-pressed','true');
 await expect(shelf.getByRole('button',{name:`Show route to ${almond.name}`,exact:true})).toBeVisible();
 for(const width of [320,390,768,1280,1440]){
  await page.setViewportSize({width,height:900});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 }
 expect((await new AxeBuilder({page}).analyze()).violations).toEqual([]);

 expect(calls.some(c=>c.includes('shelf_id='+milk.shelf.id))).toBe(true);
 await page.route('**/products/*.webp',r=>r.abort());await page.reload();
 await expect(gallery.locator('.product-packshot')).toHaveCount(0);
 await expect(gallery.getByText('Category illustration')).toBeVisible();
});

test('late shelf responses cannot replace a newer selection',async({page})=>{
 await fixture(page);
 const milk=route.product;
 const other={...milk,id:'almond-milk-1l',name:'Almond milk 1 L',shelf:{id:'a02-s01',label:'Shelf 1'}};
 let oldRequest:import('@playwright/test').Route|undefined;
 await page.route('**/api/products?**',async r=>{
  const url=new URL(r.request().url());const shelf=url.searchParams.get('shelf_id');
  if(shelf===milk.shelf.id){oldRequest=r;return;}
  await r.fulfill({json:{catalog_version:1,products:shelf?[other]:[milk,other],total:shelf?1:2,page:1,page_size:shelf?24:12,categories:[{name:'Dairy',count:2}]}});
 });
 await page.route('**/api/routes',async r=>{const id=r.request().postDataJSON().product_id;await r.fulfill({json:{...route,product:id===other.id?other:milk}});});
 await page.reload();const gallery=page.locator('.catalog-browser');
 await gallery.getByRole('button',{name:`Show route to ${milk.name}`,exact:true}).click();
 await expect.poll(()=>!!oldRequest).toBe(true);
 await gallery.getByRole('button',{name:`Show route to ${other.name}`,exact:true}).click();
 await expect(page.locator('.shelf-display .shelf-facing')).toHaveCount(1);
 await oldRequest!.fulfill({json:{catalog_version:1,products:[milk],total:1,page:1,page_size:24,categories:[{name:'Dairy',count:2}]}}).catch(()=>{});
 await expect(page.locator('.shelf-display')).toContainText(other.name);
 await expect(page.locator('.shelf-display .shelf-facing')).toHaveCount(1);
});


test('brief loud capture noise cannot stop playback while sustained speech can',async({page})=>{
 const f=await fixture(page);await page.locator('.desktop-voice').getByRole('button',{name:'Speaker mode on',exact:true}).click();await f.start();f.send('audio_start');f.binary();
 await expect.poll(()=>page.evaluate(()=>(window as any).__audio.played)).toBe(1);
 const before=await page.evaluate(()=>(window as any).__audio.flushed);
 await page.evaluate(()=>{const pcm=new Int16Array(320).fill(1000);(window as any).__captureNode.port.onmessage({data:pcm.buffer});});
 await expect(page.locator('.desktop-voice').getByText('Speaking',{exact:true})).toBeVisible();
 expect(await page.evaluate(()=>(window as any).__audio.flushed)).toBe(before);
 await page.evaluate(()=>{const send=(n:number)=>{const pcm=new Int16Array(320).fill(n);(window as any).__captureNode.port.onmessage({data:pcm.buffer});};send(0);for(let i=0;i<4;i++)send(1000);});
 await expect.poll(()=>page.evaluate(()=>(window as any).__audio.flushed)).toBe(before+1);
 await expect(page.locator('.desktop-voice').getByText('Listening',{exact:true})).toBeVisible();
});


test('voice updates never reload or abort an unchanged pending shelf',async({page})=>{
 const f=await fixture(page);let calls=0;let pending:import('@playwright/test').Route|undefined;
 await page.route('**/api/products?**',async r=>{
  if(new URL(r.request().url()).searchParams.has('shelf_id')){calls++;pending=r;return;}
  await r.fallback();
 });
 await f.start();f.send('candidates');f.send('route');
 await expect.poll(()=>calls).toBe(1);
 // New-turn invalidation retains the selected product but dirties object props.
 // Captions and the countdown continue while this shelf response is pending.
 for(let i=0;i<12;i++){
  f.send('interrupted',{turn_id:'turn-'+(i+2),generation_id:'generation-'+(i+2)});
  f.send('output_transcript',{turn_id:'turn-'+(i+2),text:'Directions continue. ',final:false});
  await page.waitForTimeout(100);
 }
 expect(calls).toBe(1);
 await pending!.fulfill({json:{catalog_version:1,products:[route.product],total:1,page:1,page_size:24,categories:[]}});
 await expect(page.locator('.shelf-display .shelf-facing')).toHaveCount(1);
 await page.waitForTimeout(1100);
 expect(calls).toBe(1);
 await page.getByRole('button',{name:'End voice',exact:true}).click();
});


test('speaker mode blocks feedback PCM, offers Interrupt, and retains the choice after End', async ({page}) => {
  const f = await fixture(page);
  const panel = page.locator('.desktop-voice');
  await expect(panel.getByRole('button', {name:'Speaker mode on',exact:true})).toHaveAttribute('aria-pressed','true');
  await f.start(); f.send('audio_start'); f.binary();
  await expect(panel).toContainText('Mic paused for reply');
  await page.evaluate(() => (window as any).__captureNode.port.onmessage({data:new Int16Array(1280).fill(2000).buffer}));
  await expect.poll(() => f.messages.filter(Buffer.isBuffer).length).toBe(1);
  expect(f.messages.filter(Buffer.isBuffer)[0].every(n => n === 0)).toBe(true);
  expect(await page.evaluate(() => (window as any).__audio.flushed)).toBe(0);
  await panel.getByRole('button',{name:'Interrupt',exact:true}).click();
  await expect.poll(() => page.evaluate(() => (window as any).__audio.flushed)).toBe(1);
  f.binary(); await expect.poll(() => page.evaluate(() => (window as any).__audio.played)).toBe(1);
  await expect(panel).toContainText('Microphone on');
  await panel.getByRole('button',{name:'End voice',exact:true}).click();
  await expect(panel.getByRole('button',{name:'Speaker mode on',exact:true})).toHaveAttribute('aria-pressed','true');
});

test('mobile speaker mode has a reachable Interrupt in the minimized dock and shares desktop state', async ({page}) => {
  await page.setViewportSize({width:320,height:900}); const f = await fixture(page);
  await page.getByRole('button',{name:'Open voice assistant',exact:true}).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog.getByRole('button',{name:'Speaker mode on',exact:true})).toHaveAttribute('aria-pressed','true');
  await f.start(dialog); f.send('audio_start'); f.binary();
  await expect(dialog).toContainText('Mic paused for reply');
  await dialog.getByRole('button',{name:'Minimize'}).click();
  const dock = page.locator('.mobile-voice-dock');
  await expect(dock).toContainText('Mic paused');
  for (const width of [320,390,768,1100]) {
    await page.setViewportSize({width,height:900});
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    for (const button of await dock.getByRole('button').all()) {
      const box = await button.boundingBox(); expect(box!.width).toBeGreaterThanOrEqual(44); expect(box!.height).toBeGreaterThanOrEqual(44);
    }
  }
  expect((await new AxeBuilder({page}).analyze()).violations).toEqual([]);
  await page.setViewportSize({width:390,height:900});
  await page.screenshot({path:'test-results/mobile-speaker-mode.png',fullPage:true});
  await dock.getByRole('button',{name:'Interrupt',exact:true}).click();
  await expect(dock).toContainText('Mic on');
  await page.setViewportSize({width:1280,height:900});
  await expect(page.locator('.desktop-voice').getByRole('button',{name:'Speaker mode on',exact:true})).toBeVisible();
  expect(f.tickets()).toBe(1);
});


test('audio device choices apply to voice and survive desktop/mobile switching',async({page})=>{
 const f=await fixture(page,{devices:true});const panel=page.locator('.desktop-voice');
 await panel.getByText('Audio settings',{exact:true}).click();await panel.getByRole('button',{name:'Enable device names',exact:true}).click();
 await expect.poll(()=>page.evaluate(()=>(window as any).__audio.stopped)).toBe(1);
 await panel.getByLabel('Microphone',{exact:true}).selectOption('usb-mic');await panel.getByLabel('Speaker',{exact:true}).selectOption('headset');
 await panel.getByRole('button',{name:'Test speaker',exact:true}).click();await expect.poll(()=>page.evaluate(()=>(window as any).__audio.tones)).toBe(1);
 await f.start();await expect(panel.getByLabel('Microphone',{exact:true})).toBeDisabled();
 expect(await page.evaluate(()=>(window as any).__audio.constraints.audio.deviceId)).toEqual({exact:'usb-mic'});expect(await page.evaluate(()=>(window as any).__audio.sink)).toBe('headset');
 await panel.getByRole('button',{name:'End voice',exact:true}).click();await page.setViewportSize({width:390,height:900});await page.getByRole('button',{name:'Open voice assistant',exact:true}).click();const dialog=page.getByRole('dialog');await dialog.getByText('Audio settings',{exact:true}).click();
 await expect(dialog.getByLabel('Microphone',{exact:true})).toHaveValue('usb-mic');await expect(dialog.getByLabel('Speaker',{exact:true})).toHaveValue('headset');expect((await new AxeBuilder({page}).analyze()).violations).toEqual([]);
});

test('logout and authentication loss stop capture and remove shopper content',async({page})=>{
 const f=await fixture(page);let signed=true;
 await page.route('**/api/auth/session',async r=>{
  if(r.request().method()==='DELETE'){signed=false;return r.fulfill({status:204});}
  return r.fulfill({status:signed?200:401,json:signed?{enabled:true,username:'demo02',role:'shopper',expires_at:new Date(Date.now()+3600000).toISOString(),csrf_token:'fixture-csrf'}:{}});
 });
 await page.reload();await f.start();await page.getByRole('button',{name:'Sign out',exact:true}).click();await expect(page.getByRole('heading',{name:'Welcome back'})).toBeVisible();expect(await page.evaluate(()=>(window as any).__audio.capture)).toBe(false);expect(await page.evaluate(()=>(window as any).__audio.stopped)).toBe(1);
 signed=true;await page.reload();await f.start();await page.evaluate(()=>window.dispatchEvent(new Event('shop-auth-required')));await expect(page.getByRole('heading',{name:'Welcome back'})).toBeVisible();expect(await page.evaluate(()=>(window as any).__audio.capture)).toBe(false);
});


for(const width of [320,1440])test(`visual conversation summary preserves confirmed and unresolved items at ${width}px`,async({page})=>{
 await page.setViewportSize({width,height:950});const f=await fixture(page);if(width<1200){await page.getByRole('button',{name:'Open voice assistant',exact:true}).click();await f.start(page.getByRole('dialog',{name:'Voice assistant'}));await page.getByRole('button',{name:/Minimize/}).click();}else await f.start();
 const entries=[{query:'milk',status:'confirmed',catalog_version:1,products:[route.product]}, {query:'unicorn cake',status:'not_found',catalog_version:1,products:[]}, {query:'milk choice',status:'needs_choice',catalog_version:1,products:[route.product,{...route.product,id:'other-milk',name:'Other milk'}]}];
 f.send('summary',{session_id:'fixture-session',turn_id:'turn-1',entries,truncated:false,requested:false});
 await page.getByRole('button',{name:'Show summary',exact:true}).click();const report=page.getByRole('region',{name:'Items and locations'});
 await expect(report).toContainText('1 confirmed item · 2 unresolved requests');await expect(report).toContainText(route.product.shelf.label);await expect(report).toContainText('No catalog match found');await expect(report).toContainText('Choose the product you mean');
 f.send('output_transcript',{text:'Invented item in aisle99'});await expect(report).not.toContainText('Invented');
 f.send('summary',{session_id:'wrong-session',turn_id:'turn-99',entries:[],truncated:false,requested:true});await expect(report).toContainText(route.product.name);
 const scope=width<1200?page.getByRole('region',{name:'Voice controls'}):page.locator('.desktop-voice');await scope.getByRole('button',{name:'End voice',exact:true}).click();await expect(report).toContainText(route.product.name);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);expect((await new AxeBuilder({page}).analyze()).violations).toEqual([]);
 await page.screenshot({path:`test-results/summary-${width}.png`,fullPage:true});
 await report.getByRole('button',{name:`Locate ${route.product.name} from summary`,exact:true}).click();await expect(page.getByTestId('route-path')).toBeVisible();await page.reload();await expect(page.getByRole('heading',{name:'Items and locations'})).toHaveCount(0);
});

test('quiet offer waits for native completion and drain, then accepting opens the visual summary',async({page})=>{
 await page.clock.install();const f=await fixture(page);await f.start();
 f.send('summary',{session_id:'fixture-session',turn_id:'turn-1',entries:[{query:'milk',status:'confirmed',catalog_version:1,products:[route.product]}],truncated:false,requested:false});
 f.send('audio_start');f.binary();f.send('turn_complete');await expect.poll(()=>page.evaluate(()=>(window as any).__audio.played)).toBe(1);
 await page.clock.fastForward(11000);expect(f.messages.filter(v=>typeof v==='string'&&JSON.parse(v).type==='text')).toHaveLength(0);await page.evaluate(()=>(window as any).__drain());
 await page.clock.fastForward(9000);expect(f.messages.filter(v=>typeof v==='string'&&JSON.parse(v).type==='text')).toHaveLength(0);f.send('pong');await page.clock.fastForward(2000);
 await expect(page.getByRole('button',{name:'Yes, summarize'})).toBeVisible();expect(f.messages.filter(v=>typeof v==='string'&&JSON.parse(v).type==='text')).toHaveLength(1);
 await page.getByRole('button',{name:'Yes, summarize'}).click();await expect(page.getByRole('region',{name:'Items and locations'})).toContainText('1 confirmed item');await expect(page.getByRole('button',{name:'Yes, summarize'})).toHaveCount(0);
});


test('a requested empty summary opens and focuses the report outside the mobile voice dialog',async({page})=>{
 await page.setViewportSize({width:320,height:900});const f=await fixture(page);await page.getByRole('button',{name:'Open voice assistant',exact:true}).click();await f.start(page.getByRole('dialog',{name:'Voice assistant'}));
 f.send('summary',{session_id:'fixture-session',turn_id:'turn-1',entries:[],truncated:false,requested:true});
 await expect(page.getByRole('dialog',{name:'Voice assistant'})).not.toBeVisible();await expect(page.getByRole('heading',{name:'Items and locations'})).toBeFocused();await expect(page.getByText('No items have been looked up yet. Ask Monti to find an item first.')).toBeVisible();await expect(page.getByRole('region',{name:'Voice controls'}).getByRole('button',{name:'End voice',exact:true})).toBeVisible();
});


for(const width of [390,1440]) test(`unique search automatically highlights its verified location at ${width}px`,async({page})=>{
 await page.setViewportSize({width,height:900});await fixture(page);
 await page.getByRole('textbox',{name:'Item name'}).fill('whole milk');
 await page.getByRole('textbox',{name:'Item name'}).press('Enter');
 await expect(page.getByTestId('route-path')).toBeVisible();
 await expect(page.locator('.aisle.selected')).toHaveCount(1);
 await expect(page.locator('.product-card.chosen')).toContainText('Whole milk');
 await expect(page.locator('.destination-strip')).toContainText('Shelf 3');
});

test('a verified voice route reveals the mobile map while voice stays connected',async({page})=>{
 await page.setViewportSize({width:390,height:900});const f=await fixture(page);
 await page.getByRole('button',{name:'Open voice assistant',exact:true}).click();
 const dialog=page.getByRole('dialog',{name:'Voice assistant'});await f.start(dialog);
 f.send('candidates');f.send('route');
 await expect(dialog).not.toBeVisible();await expect(page.getByTestId('route-path')).toBeVisible();
 await expect(page.locator('#route-heading')).toBeFocused();
 await page.getByRole('button',{name:'Open voice assistant',exact:true}).click();
 f.send('interrupted',{turn_id:'turn-2',generation_id:'generation-2'});
 await expect(dialog).toBeVisible();
 await dialog.getByRole('button',{name:'Minimize'}).click();
 await expect(page.getByRole('region',{name:'Voice controls'}).getByRole('button',{name:'End voice',exact:true})).toBeVisible();
 expect(f.tickets()).toBe(1);
});
