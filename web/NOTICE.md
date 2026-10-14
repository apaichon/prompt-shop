# Reuse notice

Selected Monti Jarvis snapshot, source version `2.38.0-rc.10`, snapshot 2026-10-13. Copyright (c) 2026 Apaichon Punopas. MIT license retained verbatim at [static/MONTI-LICENSE.txt](static/MONTI-LICENSE.txt), included in the static build. Original source and snapshot are unchanged. Full provenance and source-line spans remain in [MANIFEST.json](../references/monti-jarvis/MANIFEST.json).

- `src/lib/voice/transcript.ts`: copied transcript merge helper, with attribution comment.
- `src/lib/voice/audio.ts`: adapted permission/secure-context and PCM playback/cancellation patterns. AudioWorklet transport, streaming resampling, bounds and lifecycle are new code.
- `src/routes/+page.svelte` and `src/lib/components/VoicePanel.svelte`: adapted state/timer/caption/mobile modal patterns and modal-only focus wrapping; native dialog, explicit permission, Stop-on-close and typed recovery replace commerce/identity behavior.
- `src/lib/portal.ts`: adapted atomic presentation/request sequencing principles; implementation validates our DTOs and epochs.
- `src/app.css`: palette/spacing/focus token approach informed by source tokens; new layout, assets and colors. No source product imagery, customer data, fonts or provider credentials copied.
- SvelteKit static adapter idea retained; package/configuration rewritten for installed Kit 3, with exact lockfile. No complete source app or commerce dependency imported.

## Snapshot SHA-256

| Reference path | Copied snapshot SHA-256 |
|---|---|
| `portal/src/lib/voice/transcript.ts` | `60db04eafb1d2b65ba522579aa6aadf1d5fb7114322ea05eb6a0964b04e7f2fb` |
| `portal/src/lib/voice/mic.ts` | `087e8e17d3e9a8a6dae4d95393a95f249281f7e5d5b5d66ed1e42a7f4175d369` |
| `portal/src/lib/voice/montiVoice.ts` | `4837f365502a038929815e524cd2ba328ff13efeaa90798444af2ca31e630c9f` |
| `excerpts/interactive-voice-panel.svelte.txt` | `aeacfc1439ecde03a393c72d9368d135d9dc27f52e8fd5e2df44e2984672501b` |
| `excerpts/product-presentation.ts.txt` | `d1cbb91aea73c704d38a5e0d1a051e2b7ebf464b59fd2e18904ca28ff3e3bfa1` |
| `portal/src/lib/styles/tokens.css` | `1b16dc1457022245cd27080a1886319f94d50b95a0e717d42c5d6e305d41dcc5` |

## Test fixture provenance

`tests/fixtures/` copies the six public JSON contract examples verbatim from TASK-0001 commit `a564571`, `data/contracts/`. Dynamic ticket/ready expiry is replaced only by test code. These files are test inputs, never an application fallback or proof of model acceptance.


## TASK-0009 backoffice adaptation

`src/routes/backoffice/` adapts the catalog pagination/editor/draft principles in `excerpts/backoffice-catalog.ts.txt`; backend field/state validation was informed by `excerpts/catalog-validation.go.txt`. Exact excerpt hashes/source-line spans remain in the source MANIFEST. New code uses our single-store IDs, existing shelves, server sessions/CSRF and expected_version rather than source tenant, stock, inventory, payment or image-upload behavior. Original MIT notice remains distributed at static/MONTI-LICENSE.txt. No source secret, account, data store or infrastructure was imported.
