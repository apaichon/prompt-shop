# Reviewer setup

Current state: no accepted deployment URL. Populate [the rehearsal record](rehearsal.example.json) from actual Task 8/TEST-0004 release evidence before sharing these instructions as a working demo.

## Access and identity

The release owner supplies the exact credential-free HTTPS portal origin, approved reviewer access mechanism, final source tag/full commit, Cloud Run revision and the Go/ADK/Laya image digests. Record pinned ADK/GenAI packages, required model `gemini-3.8-live`, Laya checkpoint and schema/catalog/map versions. Verify `/`, `/backoffice`, `/healthz` and `/readyz` through the same approved origin. Health responses alone do not prove a model session.

For private access, complete the approved browser authentication path before testing. Never bypass TLS warnings or switch to an unqualified candidate tag hostname. The voice ticket and WSS require the configured exact Origin. Request maintainer credentials privately from the owner; no credential belongs in this package, URL or screen recording. Shopper access never grants backoffice writes.

Use the presenter/reviewer browser and network recorded in acceptance. Open the live-voice processing notice before selecting **Start voice**, allow microphone access explicitly, and verify audible output. On narrow screens, open the voice assistant drawer first. **End voice** and drawer close stop capture/playback. Keyboard access and textual route instructions accompany the map; review actual manual accessibility evidence rather than assuming a screenshot proves it.

## First run

1. Open shopper `/` on the recorded HTTPS origin. Confirm the sample-store notice, current English locale and entrance starting point.
2. Select **Start voice** and ask for a seeded item. Clarify/select by speech and verify the audible directions against the card, shelf and walkable path. Actual Gemini Live through ADK plus real Laya is required.
3. End voice, then try **Find item** and **Show route** with typing. This independently exercises typed recovery.
4. Authorized maintainers open `/backoffice` on the same origin, log in privately, create a separate rehearsal draft, publish explicitly and verify shopper visibility. Log out and verify editing/direct writes are denied.
5. Open the source/release/evidence and video links in a fresh reviewer session. Record actual access and playback observations.

## Sample-data limits

Source `data/demo-store.json` contains 62 product records: 60 published, one draft and one archived. It defines eight aisles, 32 shelves, 41 walkway nodes and 40 edges. The store is `demo-store`, import `demo-v1`, schema version 1, map entrance node `entrance`. Source-file SHA-256 is `822b40b6464f933e1b605042f364611f97cf1192ed465842eca180fe8be3dbc7`.

These are source counts, not an observed deployed database. Record actual deployed counts/versions/checksum and any approved rehearsal item separately. Maps use sample coordinates and directions from the entrance. The prototype has no real stock/price feed, indoor location tracking or production SLA. English is required. Offer Thai, Mandarin Chinese or Japanese only when the actual enabled locale and corresponding accepted smoke evidence agree. Recipes/vector search remain future work.

## Operator setup references

Reviewers use the deployment, without installing the cloud stack. Operators follow [foundation setup](../TASK-0001-HANDOFF.md), [backoffice runtime setup](../../internal/backoffice/README.md), [ADK runtime notes](../../agent/README.md) and [staging preparation](../../deploy/README.md). These documents include local/fixture procedures that do not establish deployed acceptance. Task 8's current [release PR](https://github.com/apaichon/prompt-shop/pull/10) carries the final release controller/runbook and unresolved integration gates. After integration, link the immutable accepted release guide instead of a moving draft branch.

Do not run disposable test-schema reset commands or development seed imports against the demo database. Only the operator runs reviewed additive migrations/imports and verifies persistence. Changing origin/model/bundle/required-component flags requires new acceptance evidence.
