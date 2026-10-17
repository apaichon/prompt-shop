---
id: "ROADMAP-0002"
type: "roadmap"
title: "Route voice tool calls with Gemini Embedding 2"
status: "in_progress"
owner: "pm-agent"
created: "2026-10-17"
updated: "2026-10-17"
risk: "medium"
risk_notes: "REQ-0006 and TEST-0002 still require actual Laya. This outcome starts only after the 18 October submission, and only through a new approved requirement."
horizon: "2026-10-20 through 2026-10-31, Asia/Bangkok, after ROADMAP-0001 submission"
outcome: "A finished English shopper sentence is matched with gemini-embedding-2, and that label is what allows the existing catalog, route, or summary tool to run."
success_metrics: ["No Laya process in the demo runtime after the successor gate passes", "At least 36 of 40 frozen English sentences select the correct tool family; abstention counts as a miss", "out_of_scope and abstain perform zero catalog or route calls", "Zero aisle or shelf text comes from the embedding", "Warm embedding decision p95 is reported; the planning target is 500 ms"]
tags: ["voice", "intent", "embeddings"]
related: ["ROADMAP-0001", "REQ-0002", "REQ-0006", "REQ-0007", "DES-0003", "ADR-0002", "TASK-0021"]
---

# Roadmap: Gemini Embedding 2 chooses the tool

## Outcome

Replace the local Laya classifier with `gemini-embedding-2` on the Gemini Developer API. The shopper's finished English sentence is embedded with the documented classification prefix `task: classification | query: {content}`. Cosine similarity against a frozen set of example sentences picks one label. That label is the only thing that may call an existing tool.

The tools stay the ones the voice runtime already has:

| Label | Tool |
|---|---|
| find_item | `search_catalog` |
| select_item | selection, then route, only for a product already in the current results |
| repeat_directions | repeat the current route, only when a route exists |
| summarize | conversation summary |
| out_of_scope or abstain | spoken reply only |

Go still returns the product, aisle, and shelf. The embedding never answers a location.

## Why now

Laya is an 843 MB checkpoint. The reviewed host run held about 1.9 GiB, used 2 CPU threads, took about 8.2 seconds to become ready, and scored a warm p95 of about 267 ms. It accepted 19 of 40 frozen sentences, below the REQ-0006 bar of 36. The decision it makes is one short label on at most 300 characters.

`gemini-embedding-2` is the stable Gemini API embedding model (checked 17 October 2026). It embeds text up to 8,192 tokens. Recommended output sizes are 768, 1,536, and 3,072. This roadmap proposes 768 for a few dozen prototype sentences. The `task_type` parameter is not supported on this model. Both the shopper sentence and every prototype must use the same classification prefix. Embeddings from `gemini-embedding-001` are a different space and cannot be mixed in.

ROADMAP-0001 still submits on 18 October with Laya. This outcome is the next change, not a silent swap inside that submission.

## Milestones

| Order | Milestone | Requirement IDs | Evidence of completion | Target |
|---:|---|---|---|---|
| 1 | Approve a successor to REQ-0006 and an ADR for the embedding router | REQ-0007 and ADR-0002 | Requirement and ADR approved on 17 Oct by the build start; REQ-0006 left unchanged | 20 Oct |
| 2 | Freeze prototypes and a new 40-sentence set, including summarize | same successor | Manifest hash; prototypes embedded once at 768 dimensions with the classification prefix | 22 Oct |
| 3 | Route with session state, cosine similarity, and the current 0.70 / 0.15 abstain rule | same successor | Abstain and out_of_scope do not call search or route; low margin abstains | 24 Oct |
| 4 | Call the existing tools from the winning label | REQ-0002 behavior kept; successor owns the router | find, select, repeat, and summarize each run on a live local session; locations match the catalog | 27 Oct |
| 5 | Measure the new set and remove Laya from the demo runtime | successor plus updated voice tests | At least 36/40 correct tool families; warm p95 recorded; Laya process absent | 31 Oct |

## Scope boundaries

- **In scope:** English text already produced for the voice turn. One Gemini API call to `gemini-embedding-2`. A small frozen prototype list per label. Session state before similarity: a selection requires current results, and a repeat requires a current route. The existing ADK tools and the Go catalog checks. Removing the Laya process after the new gate passes.
- **Out of scope:** Embedding microphone audio, images, or PDFs. Using the embedding as product search or pgvector retrieval. Returning an aisle or shelf from model text. Changing `gemini-3.8-live` or the native voice path. Training a model. Mixing `gemini-embedding-001` vectors. Editing the failed Laya 19/40 evidence into a pass. Replacing Laya inside the 18 October submission before the successor requirement is approved.

## Risks and dependencies

- REQ-0006, TEST-0002, and TEST-0012 still require actual Laya. A code swap before the successor is approved fails those gates. Mitigation: author the successor first and leave the current tests in force.
- The embedding call is remote. It uses the existing Gemini Developer API key, adds a request on every classified turn, and must stay out of logs the same way transcripts do. Mitigation: record latency, status, and token counts only.
- Similarity without session state will treat "the second one" as a new search. Mitigation: milestone 3 applies state before the score.
- 768 dimensions are the low-resource proposal, not a measured quality result. Mitigation: if the 36/40 gate misses, re-embed the same prototypes at 1,536 and rerun the same frozen set.
- API price is per request and was not calculated here. Confirm it on the Gemini embeddings pricing page before the runtime cutover.
- Dates are planning targets in Asia/Bangkok. They start after the 18 October submission.
