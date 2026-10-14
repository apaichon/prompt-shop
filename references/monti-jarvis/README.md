# Selected Monti Jarvis code

This is a **selective source copy for adaptation**, not a runnable application or a full repository clone. The user requested reuse from `/Users/apaichon/Projects/libra/monti/monti-jarvis` for the Prompt Shop proof of concept. The source repository was not changed.

[MANIFEST.json](MANIFEST.json) records the exact source file hashes, copied hashes, line spans for excerpts, source version, and intended use. Preserve [LICENSE](LICENSE) and source attribution when adapting code. Local source contents, including any pre-existing local edits, are identified by hashes; this snapshot does not claim a clean upstream Git revision.

| Selected source | Intended use | Adaptation needed |
|---|---|---|
| `portal/svelte.config.js`, `package.json`, `tsconfig.json`, `src/app.html` | Static SvelteKit portal build foundation | Create one `/` and `/backoffice` app; pin/install only used packages, generate a new lockfile, add SPA route options; source package.json is a version reference |
| `portal/src/lib/voice/mic.ts` | Microphone availability and permission recovery | Replace Monti/tenant links and copy; connect to bounded native Live session |
| `portal/src/lib/voice/transcript.ts` | Small transcript merge utility | Use for native Live transcript side channels; keep turn/cancellation boundaries |
| `portal/src/lib/voice/montiVoice.ts` | PCM16k input, PCM24k playback queue, transcripts and interruption | Replace ticket-in-URL and source endpoint with DES-0001 cookie ticket/WSS; adapt binary input frames and output envelopes; remove cart updates; qualify audio capture on demo device |
| `excerpts/gemini-live-protocol.go.txt` | AUDIO setup, tool responses and all-part server events | Remove workforce/tenant types; require 3.8 and explicit BLOCKING catalog tools; add current-turn validation, tool cancellation and resource bounds |
| `excerpts/interactive-voice-panel.svelte.txt` | Voice states, captions, elapsed timer, typed composer and mobile focus | Explicit Start only; modal focus trap only when mobile drawer is open; clear session/turn state; remove commerce/login coupling |
| `excerpts/product-presentation.ts.txt` | Validated tool-result presentation and request sequencing | Consume Go-validated candidate/route events atomically; add session/turn checks; route instead of cart action |
| `portal/src/lib/styles/tokens.css` | Small visual token palette | Keep only used tokens; verify contrast and responsive spacing |
| `excerpts/product-card.svelte.txt` | Product image/name/category and result focus treatment | Convert to shelf-finder result/selection; remove variants, price and cart concepts; provide local styles/types |
| `excerpts/backoffice-catalog.ts.txt` | Catalog list/edit/save/draft/publish UI logic | Wire new DTOs, aliases and shelf picker, protected API, validation and conflict states |
| `excerpts/catalog-api.ts.txt` | Catalog list/create/update request patterns | Replace source tenant endpoints and commerce models; use server session/CSRF contract |
| `excerpts/catalog-validation.go.txt` | Input normalization and safe field checks | Use Prompt Shop types/errors and validate shelf references; copied excerpt is not a complete Go package |
| `go/shoppingweb/serve.go` and test | Same-origin static SPA serving | Integrate with Fiber via an adapter or small port; register API/health first and preserve API 404s; change source branding |
| `go/security/redact.go` and test | Existing credential-redaction helper | Use as defense in depth; structured allowlisted logs remain primary and never contain shopper audio/transcripts |

`.txt` snippets intentionally preserve exact source fragments and are **not standalone compilable files**. Related source imports, commerce models and styles are not pulled in recursively. The implementation tasks own adapting only the necessary behavior into `web/` and `internal/`.

## Excluded

No `.env`, credentials, source database records, compiled binaries, `.git`, `node_modules`, build outputs, customer accounts, payments, checkout, hotel booking, billing, KYC, Redis, MinIO, ClickHouse, NATS or LiveKit deployment is copied. The source `Store` and Gemini Live relay are coupled to other services; importing them wholesale would enlarge this prototype.

## Gemini Live 3.8 migration

The source defaults to `gemini-2.5-flash-native-audio-latest` in `internal/env/env.go` and `internal/live/relay.go`; that default is not reused. Require `gemini-3.8-live`, AUDIO responses and native audio in both directions. Remove unsupported thinking/affective options and never set `proactive_audio:false`. Explicitly set BLOCKING for catalog/route tool declarations and process every audio/transcription part. See [DES-0001](../../docs/sdlc/03-designs/DES-0001.md) and [Google's model reference](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-live).

These source fragments are adaptation references, not a ready Gemini 3.8 implementation. The source relay's allow-all Origin check, platform tool executor, URL ticket and verbose provider error logging are not approved Prompt Shop behavior. Use the design's origin validation, cookie ticket, read-only allowlist and metadata-only logs. Source audio helper behavior still requires actual device/model qualification.

## Verification on 13 October 2026

- All 20 copied files/excerpts match their recorded source bytes or line spans.
- Existing standalone Go tests for static serving and credential redaction passed using the copied files.
- These checks do **not** verify a running Prompt Shop portal, live speech, database integration or GCP deployment. Those remain proposed work in [the MVP plan](../../docs/MVP-PLAN.md).

## ADK integration boundary

The browser patterns feed the public Go gateway, which bridges to the private Python ADK runtime. The old Go Gemini relay fragments remain protocol references only; ADK owns the provider connection. The prototype also requires private Laya intent classification through an ADK tool. See the [reference study](../../docs/REFERENCE-STUDY.md) for the source-to-feature mapping.
