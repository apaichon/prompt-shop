# Prompt Shop customer portal

TASK-0004 supplies the static SvelteKit customer shell, typed search, authoritative candidate cards, entrance-to-shelf map and native PCM voice client. Backoffice is a shell placeholder; TASK-0009 owns its protected route. The frontend has no provider keys or environment variables.

From `web/`, with Node 22.17 or newer:

```sh
rtk proxy npm ci
rtk proxy npm run check
rtk proxy npm test
rtk proxy npm run build
rtk proxy npx playwright install chromium
rtk proxy npm run test:browser
rtk proxy npm run preview
```

`build/` is the deployment artifact, including the SPA fallback `index.html`, PCM worklet and license notice. The Go server must serve that directory with SPA fallback for non-API paths. `/api/*` and `/ws/voice` must remain Go routes on the same origin; API errors must never fall through to HTML. Local preview alone shows an unavailable-service state. Only tests intercept requests with fixtures; no fabricated catalog is shipped in the application. TASK-0001 static wiring and TASK-0005 container build consume this output after integration.

Use HTTPS or localhost for microphone access. Start voice explicitly requests permission and opens a fresh cookie-backed session through `POST /api/voice/sessions`; `prompt-shop.voice.v1` is the WebSocket subprotocol. Capture starts after `ready`, streams 100ms PCM16LE mono 16kHz binary frames, and output plays PCM16LE mono 24kHz. Stop, drawer close, navigation, hidden page, timeout or transport failure releases microphone tracks and audio resources. Restart is manual, with no replay. Outgoing backlog is capped at 32KB and scheduled output at one second.

`src/lib/contracts.ts` validates public DTOs/events at runtime. `api.ts` provides same-origin JSON requests and safe error messages. `portal.ts` owns selection/request epochs and map-version retry; captions never initiate catalog requests. `voice/gate.ts` rejects stale session/turn/generation events. Cards and directions only come from validated backend results. The server remains responsible for authorization, candidate membership and catalog truth.

## Integration handoff

- TASK-0002: GET `/api/store-map`, POST `/api/search`, POST `/api/routes`; the canonical origin is `entrance`. A 422 `ROUTE_UNAVAILABLE` preserves known shelf labels without drawing a route. A map-version mismatch reloads the map and retries the route once, then refuses incompatible geometry.
- TASK-0003: gateway search IDs may contain mixed-case base64url characters; product IDs remain lowercase. Its new-turn `interrupted` marker names the upcoming generation, while same-turn interruption cancels that generation. Newer turns may select from the current candidate set. Classifier recovery uses the existing normalized `error` event shape with `CLASSIFICATION_ABSTAINED`, `CLASSIFIER_TIMEOUT`, or `CLASSIFIER_BUSY`; the current TASK-0003 gateway normalizes dependency errors instead, so distinct classifier UI messages require that backend mapping before integrated acceptance.
- TASK-0009: add `src/routes/backoffice/+page.svelte`; it takes precedence over the placeholder catch-all. Reuse the root layout and styling. Extend the shared API client only through serialized frontend ownership; auth and CSRF remain server requirements.
- TASK-0005: build with the checked-in package lock and copy `web/build/` into the Go static root. Add the web check/unit/build/browser commands above to the integrated CI workflow; workflow ownership stays with TASK-0005.

The test suite uses foundation fixtures from TASK-0001 commit `a564571`. Browser tests cover 320/768/1280px, keyboard focus, axe accessibility, escaped captions, current facts, cancellation, mute/Stop, denied permission and a real Chromium worklet with a simulated microphone. They do not prove Gemini/Laya inference, audible provider response, deployed cookie admission, latency, or real backend integration. Manual screen-reader testing is still required; see TEST-0009. Screenshots and failure traces are generated in ignored `test-results/`.
