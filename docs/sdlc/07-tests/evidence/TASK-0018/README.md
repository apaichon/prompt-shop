# Bakery catalog/search diagnosis — 17 October 2026

The shopper gallery and backoffice use the same PostgreSQL host/port/database
with separate least-privilege logins. Shopper API reports120published products,
including15Bakery. Fully paginated backoffice reports122rows, including those
same15published bakery IDs and two nonpublished example rows. No missing bakery
rows were found. Backoffice pages contain50items; filters/pagination can hide a
row without deleting it.

Direct API reproduction: bagel/blueberry muffin/burger bun/cinnamon roll/croissant
returned zero candidates, while the plural display names and chocolate cake worked.
The new seeded full-name test also reproduced Low-fat milk failing because query
punctuation was split while names/aliases retained it.

The actual authenticated public WebSocket → ADK/Gemini → real Laya → Go catalog
probe uses the same six synthetic requests in each run. Before: five misses,
chocolate cake passed. After:6/6complete audio replies and expected routes, zero
errors/disconnects; first returned audio1215–1664ms, verified route609–1072ms.
See native-before.json and native-after.json for raw counters/timings. These are
text-control inputs with actual native audio output, not microphone transcription,
physical acoustics or thirty-trial speech latency acceptance. No provider model,
voice, classifier threshold or catalog data changed.

Fix: preserve exact/prefix/token priority, then known noun equivalence with every
query token required. Exact categories return bounded choices, never an invented
category shelf. Indexed names/aliases use the same punctuation normalization as
queries. Unknown names still need exact words or operator-authored aliases; no
arbitrary stemming or fuzzy semantic claim.

Verification: Go catalog tests pass under race instrumentation against the running
read-only PostgreSQL principal, including15gallery/search/route comparisons and
five singular bakery requests. Unit coverage checks all120published seed names,
known noun forms, ambiguity/caps/order and unsupported modifier rejection. Go vet
passes. Data reset/mutation was not used.

Rerun: from web, set NATIVE_VOICE_TEST=1, NATIVE_VOICE_SCENARIO=bakery and point
NATIVE_ACCOUNTS_FILE privately to the demo handout; run tests/native/conversation.cjs.
Do not capture auth bodies, provider keys, cookies, transcripts or real audio.

A separate synthetic spoken “Where is a bagel?” WAV traversed actual Chromium
capture/worklet → Go → ADK/Gemini/Laya → route and browser playout. PASS: one
complete160320byte native reply, correct bagel route, one shelf fetch, no error
or disconnect, first scheduled playout1699.6ms from the last detected input and
zero scheduled audio gaps. Speaker mode was on. See native-microphone.json. This
qualifies this synthetic microphone path, not physical room/acoustic behavior.
