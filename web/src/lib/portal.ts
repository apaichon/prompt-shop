import { writable } from 'svelte/store';
import { Api, ApiError, errorMessage } from './api';
import { routeMatchesMap, type StoreMap, type Product, type Route, type VoiceEvent } from './contracts';
import { VoiceClient } from './voice/client';

export interface PortalState {
  map: StoreMap | null; mapError: string; mapLoading: boolean; candidates: Product[];
  route: Route | null; location: Product | null; loading: boolean; searched: boolean; query: string;
  message: string; routeMessage: string; searchID: string | null; source: 'typed' | 'voice';
  focus: 'results-heading' | 'route-heading' | null; focusVersion: number;
}
export class Portal {
  private state: PortalState = { map: null, mapError: '', mapLoading: true, candidates: [], route: null, location: null,
    loading: false, searched: false, query: '', message: '', routeMessage: '', searchID: null, source: 'typed', focus: null, focusVersion: 0 };
  private store = writable(this.state);
  subscribe = this.store.subscribe;
  readonly voice: VoiceClient;
  private epoch = 0;
  private mapEpoch = 0;
  private request?: AbortController;
  private mapRequest?: AbortController;
  private clicked: string | null = null;
  private cooldown = 0;
  private alive = true;
  private voiceActive = false;
  private unsubscribe: () => void;

  constructor(private api = new Api(), voiceFactory = (callbacks: ConstructorParameters<typeof VoiceClient>[0]) => new VoiceClient(callbacks, api)) {
    this.voice = voiceFactory({ event: (event) => { void this.voiceEvent(event); }, turn: () => this.invalidate() });
    this.unsubscribe = this.voice.subscribe((state) => { this.voiceActive = state.active; });
  }
  private patch(patch: Partial<PortalState>) { this.state = { ...this.state, ...patch }; this.store.set(this.state); }
  private invalidate() { this.epoch++; this.request?.abort(); this.request = undefined; this.patch({ loading: false }); }
  private focus(target: PortalState['focus']) { this.patch({ focus: target, focusVersion: this.state.focusVersion + 1 }); }
  async loadMap() {
    this.mapRequest?.abort(); const abort = new AbortController(); this.mapRequest = abort;
    const key = ++this.mapEpoch; this.patch({ mapLoading: true, mapError: '' });
    try {
      const map = await this.api.map(abort.signal);
      if (!this.alive || key !== this.mapEpoch) return;
      this.patch({ map, mapLoading: false,
        ...(this.state.route && !routeMatchesMap(this.state.route, map) ? { route: null, routeMessage: 'Map updated; select your item again.' } : {}) });
    } catch (error) {
      if (this.alive && key === this.mapEpoch && !abort.signal.aborted) this.patch({ mapLoading: false, mapError: errorMessage(error) });
    }
  }
  async search(raw: string) {
    const query = raw.trim();
    if (!query || [...query].length > 200) { this.patch({ message: 'Enter one item name, up to 200 characters.' }); return; }
    if (Date.now() < this.cooldown) { this.patch({ message: 'Please wait before searching again.' }); return; }
    this.stopVoice(); this.clicked = null;
    const key = this.epoch; const abort = new AbortController(); this.request = abort;
    this.patch({ loading: true, message: '', routeMessage: '', query, searched: false, candidates: [], route: null, location: null, searchID: null, source: 'typed' });
    try {
      const result = await this.api.search(query, abort.signal);
      if (!this.current(key)) return;
      this.patch({ candidates: result.candidates, loading: false, searched: true,
        message: result.candidates.length ? (result.ambiguous ? 'Choose the item you mean.' : 'Found in the store catalog.') : 'No matching items. Try another name or ask a store colleague.' });
      this.focus('results-heading');
    } catch (error) {
      if (!this.current(key)) return;
      if (error instanceof ApiError && error.retryAfter) this.cooldown = Date.now() + error.retryAfter * 1000;
      this.patch({ loading: false, message: errorMessage(error) });
    }
  }
  async choose(product: Product) {
    if (!this.state.candidates.some((p) => p.id === product.id)) return;
    if (this.voiceActive && this.state.source === 'voice' && this.state.searchID) {
      if (this.voice.select(this.state.searchID, product.id)) {
        this.clicked = product.id; this.patch({ loading: true, routeMessage: 'Finding directions…' });
        return;
      }
    }
    this.stopVoice(); this.clicked = product.id;
    const key = this.epoch; const abort = new AbortController(); this.request = abort;
    this.patch({ loading: true, location: product, route: null, routeMessage: '' });
    try {
      const route = await this.api.route(product.id, abort.signal);
      if (route.product.id !== product.id) throw new ApiError('INVALID_RESPONSE');
      await this.commitRoute(route, key, abort, true);
    } catch (error) { this.routeError(error, key, product); }
  }
  private current(key: number) { return this.alive && key === this.epoch; }
  private routeError(error: unknown, key: number, product: Product) {
    if (!this.current(key)) return;
    const current = error instanceof ApiError && error.product?.id === product.id ? error.product : product;
    this.patch({ loading: false, route: null, location: current, routeMessage: errorMessage(error) });
    if (this.clicked === product.id) this.focus('route-heading');
  }
  private async commitRoute(route: Route, key: number, abort: AbortController, explicit: boolean) {
    if (!this.current(key)) return;
    let map = this.state.map;
    if (!map || map.map_version !== route.map_version) {
      // Cancel an initial/background map read before loading the route's current map.
      this.mapEpoch++; this.mapRequest?.abort();
      map = await this.api.map(abort.signal);
      if (!this.current(key)) return;
      const retry = await this.api.route(route.product.id, abort.signal);
      if (retry.product.id !== route.product.id) throw new ApiError('INVALID_RESPONSE');
      route = retry;
    }
    if (!this.current(key)) return;
    if (!routeMatchesMap(route, map)) {
      this.patch({ map, mapLoading: false, loading: false, mapError: '', route: null, location: route.product, routeMessage: 'Map updated; try again. No route is shown until the map matches.' });
    } else {
      this.patch({ map, mapLoading: false, mapError: '', route, location: route.product, loading: false, routeMessage: '',
        candidates: this.state.candidates.map((p) => p.id === route.product.id ? route.product : p) });
    }
    if (explicit) this.focus('route-heading');
  }
  private async voiceEvent(event: VoiceEvent) {
    if (event.type === 'candidates') {
      this.invalidate(); this.clicked = null;
      this.patch({ candidates: event.candidates, searchID: event.search_id, source: 'voice', searched: true, query: '',
        route: null, location: null, routeMessage: '', message: event.candidates.length ? 'Say an item name to choose, or select Show route.' : 'No matching items. Try another name or type an item.' });
    } else if (event.type === 'route') {
      if (event.search_id !== this.state.searchID || !this.state.candidates.some((p) => p.id === event.product.id)) return;
      this.invalidate(); const key = this.epoch; const abort = new AbortController(); this.request = abort;
      const { type: _type, session_id: _session, turn_id: _turn, search_id: _search, ...route } = event;
      try { await this.commitRoute(route, key, abort, this.clicked === route.product.id); }
      catch (error) { this.routeError(error, key, route.product); }
    }
  }
  startVoice() { this.invalidate(); this.clicked = null; return this.voice.start(); }
  stopVoice() { this.invalidate(); this.voice.stop(); }
  destroy() { this.alive = false; this.stopVoice(); this.mapEpoch++; this.mapRequest?.abort(); this.unsubscribe(); }
}
