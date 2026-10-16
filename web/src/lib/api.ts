import type { z } from 'zod';
import { errorSchema, mapSchema, routeSchema, searchSchema, ticketSchema, type Product } from './contracts';

export class ApiError extends Error {
  constructor(public code: string, public product?: Product, public retryAfter = 0) { super(code); }
}
export const recovery: Record<string, string> = {
  INVALID_REQUEST: 'Enter one item name, up to 200 characters.',
  LANGUAGE_DISABLED: 'English is available for this store.',
  RATE_LIMITED: 'A few too many requests. Please wait a moment and try again.',
  PRODUCT_NOT_FOUND: 'This item is no longer available. Try a new search.',
  ROUTE_UNAVAILABLE: 'The shelf is known, but a walking route is not available.',
  STALE_SELECTION: 'That selection has expired. Please search or ask again.',
  SESSION_EXPIRED: 'Your voice session ended. Start a new session or type an item.',
  IDLE_TIMEOUT: 'Voice stopped after a minute of inactivity. Restart when you’re ready.',
  TURN_TIMEOUT: 'That reply took too long. I’m still listening — please ask again.',
  SETUP_TIMEOUT: 'Voice took too long to connect. You can restart or type an item.',
  SESSION_TICKET_INVALID: 'The voice connection expired. Please start again.',
  CLASSIFICATION_ABSTAINED: 'I couldn’t understand that request. Try another phrase or type the item.',
  CLASSIFIER_TIMEOUT: 'Voice couldn’t understand that in time. Try another phrase or type the item.',
  CLASSIFIER_BUSY: 'Voice is busy. Try again or type the item.',
  FORBIDDEN: 'Voice cannot connect from this page. Please use the store’s approved portal.',
  DEPENDENCY_UNAVAILABLE: 'The service is temporarily unavailable. Please try again.',
  INVALID_RESPONSE: 'The store returned an incomplete response. Please try again.',
  CLIENT_TOO_SLOW: 'Audio could not keep up. Voice stopped; restart or type an item.'
};
export function errorMessage(error: unknown): string {
  return recovery[error instanceof ApiError ? error.code : 'DEPENDENCY_UNAVAILABLE'] ?? recovery.DEPENDENCY_UNAVAILABLE;
}
export class Api {
  constructor(private fetcher: typeof fetch = (...args) => fetch(...args)) {}
  async request<T>(path: string, schema: z.ZodType<T>, body?: unknown, signal?: AbortSignal): Promise<T> {
    const timeout = AbortSignal.timeout(10000);
    let response: Response;
    try {
      response = await this.fetcher(path, {
        method: body === undefined ? 'GET' : 'POST', credentials: 'same-origin', cache: 'no-store',
        headers: body === undefined ? { Accept: 'application/json' } : { Accept: 'application/json', 'Content-Type': 'application/json' },
        body: body === undefined ? undefined : JSON.stringify(body),
        signal: signal ? AbortSignal.any([signal, timeout]) : timeout
      });
    } catch (error) { if (signal?.aborted) throw error; throw new ApiError('DEPENDENCY_UNAVAILABLE'); }
    const raw = await response.text();
    if (raw.length > 1_000_000) throw new ApiError('INVALID_RESPONSE');
    let value: unknown;
    try { value = JSON.parse(raw); } catch { throw new ApiError('INVALID_RESPONSE'); }
    if (!response.ok) {
      const parsed = errorSchema.safeParse(value);
      const delay = Number(response.headers.get('Retry-After'));
      throw new ApiError(parsed.success ? parsed.data.error.code : 'DEPENDENCY_UNAVAILABLE',
        parsed.success ? parsed.data.error.details?.product : undefined, Number.isFinite(delay) ? Math.min(3600, Math.max(0, delay)) : 0);
    }
    const parsed = schema.safeParse(value);
    if (!parsed.success) throw new ApiError('INVALID_RESPONSE');
    return parsed.data;
  }
  map(signal?: AbortSignal) { return this.request('/api/store-map', mapSchema, undefined, signal); }
  search(query: string, signal?: AbortSignal) { return this.request('/api/search', searchSchema, { query, language: 'en-US' }, signal); }
  route(product_id: string, signal?: AbortSignal) { return this.request('/api/routes', routeSchema, { product_id, origin_node_id: 'entrance' }, signal); }
  ticket(signal?: AbortSignal) { return this.request('/api/voice/sessions', ticketSchema, { language: 'en-US' }, signal); }
}
