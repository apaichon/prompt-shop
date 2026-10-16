# General conversation and store-tool routing — 16 October 2026

The user reported a connected voice session that did not answer, then clarified the
utterance was “hello” and explicitly requested general conversation, meal/menu
ideas and AI selection of when to match store items and shelves.

## Diagnosis ledger

1. Ranked hypotheses: microphone/transport failure; speech-boundary failure;
   conversational restrictions/audio gating; provider/model failure. All three
   services were ready. A real Chromium synthetic “Hello” microphone probe received
   `ready`, a new-turn marker and input transcription, but zero audio and no completed
   reply before the socket closed. That rules out absent capture/transport for this
   reproduction. No shopper microphone recording was made.
2. Independently called the actual private pinned Laya model with the synthetic
   text `Hello`: it abstained with confidence 0.4076 and margin 0.0725. The existing
   host and Go gateway allowed non-catalog speech only for a confident `out_of_scope`
   label. Therefore this greeting could never unlock audio. The old instruction also
   prohibited unrelated conversation. This explains why the earlier whole-milk
   lookup passed while the user's greeting failed; that test did not cover chat.
3. Added a model-selected `response_mode` to the existing classification tool and
   trusted private registration event. `conversation` permits chat after the real
   classification attempt/ACK, including abstention. `catalog` preserves search and
   route gates. Invalid modes fail; missing legacy mode defaults to catalog. Catalog
   calls close earlier chat permission, and new turns reset permission. Laya's four
   labels, weights, thresholds, schema and HTTP inference are unchanged. Mode is a
   conversation/tool decision, not successful classification or catalog authority.
4. Updated instructions for general questions, greetings, meal ideas and transition
   to ingredient/product lookup. Meal ingredients are suggestions; availability and
   shelf facts require store tools. Multiple ingredients are located one at a time.
   A new-turn transport marker now shows Listening rather than falsely saying the
   first utterance interrupted a response. Updated copy invites chat/meal ideas.
5. A real provider/pinned-Laya candidate probe of “Hello” completed with 108,480 bytes
   of native audio and greeting captions, no error/backlog/socket close and no false
   interruption status. The same previously failing synthetic input was used.
6. One continuous real Chromium microphone → Go → ADK → Gemini → Laya session then
   completed four spoken turns: greeting, “What is two plus two?”, “Suggest a simple
   egg dish for dinner”, and “Where is the whole milk?”. Each produced native audio
   (99,362 / 199,200 / 498,240 / 144,002 bytes). Output captions matched the general
   answer and meal suggestion. Only the last turn emitted catalog results; its
   whole-milk card, route and stored Aisle 2 / Shelf 3 captions matched. No protocol
   error, playback backlog or socket close occurred. Source: TASK-0003 candidate
   based on main `a800704`; real pinned Laya weights, local seeded PostgreSQL and
   configured Gemini model/voice. This is one synthetic flow, not physical-device
   listening, 30-trial latency, frozen classifier accuracy or cloud acceptance.

The browser probe prints only counters/booleans and does not persist captions or
provider audio. Synthetic microphone WAVs remain temporary test assets. General
native model speech still needs factual/safety evaluation; prompts and mode gating
do not constitute a semantic guarantee against invented spoken store facts.

## Manual check

Refresh http://localhost:8080 after restarting, start a fresh voice session and allow
microphone access. Say Hello; expect a spoken greeting. Ask a general question, then
for a meal idea; expect useful conversational replies. Ask where to find one
ingredient or whole milk; expect a current catalog card, stored shelf and route.
Listen to the entire response. Keep the original frozen QA cases unchanged.
