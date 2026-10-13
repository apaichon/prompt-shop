import { test, expect, type Page, type WebSocketRoute } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import map from '../fixtures/store-map.json' with { type: 'json' };
import search from '../fixtures/search-response.json' with { type: 'json' };
import route from '../fixtures/route-response.json' with { type: 'json' };
import events from '../fixtures/live-events.json' with { type: 'json' };

async function fixture(page: Page, options: { denied?: boolean; realAudio?: boolean } = {}) {
  let searches = 0, tickets = 0;
  const messages: (string | Buffer)[] = [];
  let socket: WebSocketRoute | undefined;
  if (!options.realAudio) await page.addInitScript(({ denied }) => {
    const metrics = { opened: 0, stopped: 0, played: 0, flushed: 0, capture: false, muted: false };
    (window as any).__audio = metrics;
    const track = { enabled: true, onended: null, stop() { metrics.stopped++; } };
    Object.defineProperty(navigator, 'mediaDevices', { value: { async getUserMedia() {
      metrics.opened++; if (denied) throw new DOMException('Denied', 'NotAllowedError');
      return { getTracks: () => [track], getAudioTracks: () => [track] };
    } } });
    class Node { connect() {} disconnect() {} }
    (window as any).AudioContext = class {
      state = 'running'; currentTime = 0; destination = {}; audioWorklet = { async addModule() {} };
      async resume() {} async close() { this.state = 'closed'; }
      createMediaStreamSource() { return new Node(); }
      createGain() { return Object.assign(new Node(), { gain: { value: 0 } }); }
      createBuffer(_channels: number, length: number) { return { getChannelData: () => new Float32Array(length) }; }
      createBufferSource() { return Object.assign(new Node(), { buffer: null, onended: null, start() { metrics.played++; }, stop() { metrics.flushed++; } }); }
    };
    (window as any).AudioWorkletNode = class extends Node {
      port = { onmessage: null, postMessage(value: string) { metrics.capture = value === 'start'; }, close() {} };
    };
  }, { denied: options.denied ?? false });
  await page.route('**/api/**', async (request) => {
    const path = new URL(request.request().url()).pathname;
    let body: unknown;
    if (path === '/api/store-map') body = map;
    else if (path === '/api/search') { searches++; body = search; }
    else if (path === '/api/routes') body = route;
    else if (path === '/api/voice/sessions') { tickets++; body = { session_id: 'fixture-session', ticket_expires_at: new Date(Date.now() + 30000).toISOString(), ws_path: '/ws/voice' }; }
    else throw new Error(`Unexpected API ${path}`);
    await request.fulfill({ status: path === '/api/voice/sessions' ? 201 : 200, json: body });
  });
  await page.routeWebSocket('**/ws/voice', (ws) => { socket = ws; ws.onMessage((message) => messages.push(message)); });
  const send = (type: string, extras = {}) => socket!.send(JSON.stringify({ ...events.find((e) => e.type === type), ...extras }));
  await page.goto('/');
  await expect(page.getByRole('img', { name: /floor map/i })).toBeVisible();
  return {
    send, messages, searches: () => searches, tickets: () => tickets,
    binary: () => socket!.send(Buffer.alloc(3200)),
    async start(scope = page.locator('.desktop-voice')) {
      await scope.getByRole('button', { name: /Start voice|Restart voice/ }).click();
      await expect.poll(() => !!socket).toBe(true);
      send('ready', { expires_at: new Date(Date.now() + 300000).toISOString() });
      await expect(scope.getByText('Listening', { exact: true })).toBeVisible();
    }
  };
}

for (const width of [320, 768, 1280]) test(`typed flow, map and accessibility at ${width}px`, async ({ page }) => {
  await page.setViewportSize({ width, height: 900 });
  const f = await fixture(page);
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
  const f = await fixture(page); const launcher = page.getByRole('button', { name: 'Rather ask? Open voice assistant' });
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
  expect(f.messages.filter(Buffer.isBuffer).every((m) => m.length === 3200)).toBe(true);
  await page.getByRole('button', { name: 'End voice' }).click();
  await context.close();
});
