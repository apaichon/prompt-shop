---
id: "ROADMAP-0001"
type: "roadmap"
title: "Deploy the item-finding voice prototype by 16 October"
status: "proposed"
owner: "pm-agent"
created: "2026-10-13"
updated: "2026-10-17"
risk: "high"
risk_notes: "Three delivery days remain after planning; validate speech and cloud access on day one."
horizon: "2026-10-13 through 2026-10-18, Asia/Bangkok"
outcome: "A deployed English voice demo returns grounded item locations and a walkable route from a known starting point."
success_metrics: ["GCP deployment accepted by 2026-10-16 17:00 Asia/Bangkok (proposed cutoff)", "At least 27 of 30 supported English prompts return the correct item in the first three choices", "Zero fabricated aisle or shelf locations in the acceptance set", "Gemini Live 3.8 native voice: p95 at most 5 seconds to actionable speech and 8 seconds to verified card from user speech end across 30 warm trials", "Submission package ready on 17 October; submit on 18 October"]
related: ["REQ-0001", "REQ-0002", "REQ-0003", "REQ-0004", "REQ-0005", "REQ-0006", "ROADMAP-0002"]
---

# Roadmap: A shopper finds the right shelf quickly

## Outcome
A shopper speaks or types a food/item request, resolves any ambiguity, sees its aisle and shelf, and follows a route from the demo entrance/kiosk. Ship the working prototype to GCP on 16 October 2026. Submission is 18 October. All times use Asia/Bangkok (UTC+7). The 17:00 deployment cutoff is a planning proposal; the user specified the date only.

## Why now
The user set a hard prototype submission date of 18 October and wants cloud deployment finished on 16 October. Planning begins on 13 October; scope must protect two full build days and a deployment day. No existing implementation or measured baseline exists. We will measure response time, task success, and route validity; we cannot yet claim reduced real-store walking time.

## Milestones
| Order | Milestone | Requirement IDs | Evidence | Target |
|---:|---|---|---|---|
| 1 | Scope, contracts, speech feasibility and GCP access | REQ-0001, REQ-0002, REQ-0004 | Approved review pack; Actual ADK gemini-3.8-live native audio/tool round trip and Laya CPU inference pass; cloud prerequisites checked | 13 Oct evening |
| 2 | One item works end to end; cloud skeleton is reachable | REQ-0001, REQ-0002, REQ-0003, REQ-0004 | English query returns seeded shelf and visible route on staging | 14 Oct 18:00 |
| 3 | Complete English flow, protected backoffice and error recovery; freeze features | REQ-0001, REQ-0002, REQ-0003, REQ-0005 | 30-query acceptance run; timeout, ambiguity and microphone-denied checks | 15 Oct 18:00 |
| 4 | Deploy and verify GCP release | REQ-0004 | HTTPS URL, smoke results, rollback rehearsal and release evidence | 16 Oct 17:00 |
| 5 | Rehearse and package | REQ-0004 | Recorded backup demo, README, screenshots, submission checklist | 17 Oct |
| 6 | Submit | REQ-0004 | Submit through the required channel after user review | 18 Oct |

## Scope boundaries
- **Must:** one sample store; 60 products across eight aisles; PostgreSQL item/location data; repeatable seed/import; same-portal protected catalog backoffice; English Gemini Live 3.8 native voice-to-voice through Google ADK; actual Laya intent classification; interactive tool-driven cards/map; spoken clarification/selection and barge-in; visible transcripts and typed fallback; top-three choices; aisle/shelf card; static floor map with walkable routing from an explicit origin; brief spoken location; deployed HTTPS demo.
- **Stretch order:** Thai, Chinese (initial assumption: Mandarin/zh-CN), Japanese; then up to five curated recipe shopping lists. Extra languages do not block the English release. Recipe support is inherited from the original product vision and is explicitly outside the core deadline.
- **Later:** pgvector/semantic retrieval after the main concept works; larger catalogs; multiple stores; full admin suite; live stock/prices; user accounts; personalization; live indoor positioning; AR; guaranteed globally optimal multi-stop routes.

## Risks and dependencies
- Gemini Live model access, PCM streaming, provider quotas and microphone permissions: prove one English request early; typing is recovery, not a substitute for the required voice demonstration.
- Cloud project, billing, IAM, selected region and provider access are not yet confirmed. Owner: user + devops-agent. Resolve on 13 October before cloud-dependent work.
- Map truth: sample data only; each product must map to a valid shelf and walkable node. Do not infer locations from generated text.
- Team capacity: the config describes five agent roles, not five confirmed human engineers. Estimates are provisional; do not claim measured velocity.
- Add languages only after the English acceptance gate is green; cut recipes, vector work and extra languages before weakening core location correctness or cloud deployment.

## Reuse and portal scope update
User requested selective reuse from monti-jarvis and both customer and backoffice in the same portal. REQ-0005 adds minimal protected catalog maintenance; TASK-0009 delivers it. Keep payments, booking, billing, KYC, source runtime data and source infrastructure out. This adds 4–6 provisional engineering hours; protect the deadline by cutting all stretch languages/recipes first.
