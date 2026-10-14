# Prompt Shop proposal

Draft for the supplied AI Builder Cup template. Actual release, video, measured benchmarks and team leader are pending.

## 1. Team Details

Team name: Prompt Shop (proposed)

Team leader name: To confirm

Problem: Shoppers need a clear way to find items and shelf directions in a large hypermarket.

## 2. Template instructions

Original template download/edit instructions retained.

## 3. Brief about the idea

Prompt Shop is a voice assistant for finding items in a hypermarket.

A shopper asks in English, clarifies the product by speech and hears directions while the portal highlights the verified shelf and walking path.

Store maintainers update the same catalog through a protected backoffice. Published changes become available to shopper lookup.

Prototype scope: sample store data. Final integrated cloud and native voice acceptance are pending.

## 4. Opportunities

Difference from a text-only catalog or generic chatbot

Spoken clarification and selection lead to directions checked against store records, with a synchronized product card and map.

How the proposed solution addresses the problem

A shopper can ask for an item without knowing its aisle. Staff maintain names, aliases and mapped shelf locations in the same portal.

USP: conversation tied to maintained shelf data

Go validates product and route facts. The classifier advises intent, while authorized maintainers control catalog changes.

## 5. List of features offered by the solution

Proposed demo capabilities

1. Native English audio conversation with spoken clarification and selection.

2. Up to three verified product choices with aisle and shelf information.

3. Walkable route from the sample entrance, plus readable text directions.

4. Explicit start/end, microphone and sound controls, captions and restart recovery.

5. Protected staff login, draft editing and explicit publication in the same portal.

6. Typed lookup remains available when voice cannot run.

Real ADK, Gemini Live 3.8 and Laya evidence remain mandatory for release.

## 6. Process flow diagram or Use-case diagram

Shopper conversation

ADK coordinates native audio and read-only tools. Go validates catalog and route facts.

Authorized maintainer

Drafts stay hidden. Server checks protect writes and reject logged-out sessions.

Shopper: speak item, classify intent, catalog lookup, spoken selection, verified route. Maintainer: login, draft, publish, shopper lookup, logout.

## 7. Wireframes/Mock diagrams of the proposed solution (optional)

Illustrative layout. The customer and backoffice share one portal origin.

The final UI uses current database geometry and verified events. This schematic is a proposal.

Voice controls/captions beside item choices and route text/map. Schematic only.

## 8. Architecture diagram of the proposed solution

Required integration: native PCM, real classification and verified current-turn results.

Svelte and protected backoffice call Go. Go reads Cloud SQL. Private ADK owns Gemini Live audio and calls the private Laya classifier.

## 9. Technologies to be used in the solution

| Layer | Technology | Purpose |
| --- | --- | --- |
| Portal | SvelteKit / TypeScript | Customer and backoffice UI |
| Public backend | Go Fiber | Admission, catalog and route truth |
| Voice runtime | Python Google ADK | Native Gemini Live 3.8 audio |
| Intent service | English Laya | Private advisory classification |
| Persistence | PostgreSQL / Cloud SQL | Catalog, shelves and map |
| Hosting | Docker / Cloud Run | One revision with three containers |

Exact packages, model checkpoint and all image digests will follow the accepted release.

## 10. Estimated implementation cost (optional)

Budget estimate pending approved cloud configuration

Cost drivers: managed PostgreSQL, active Cloud Run sessions, Gemini audio usage, image builds/storage and operational logging.

Planned effort: 43-69 engineering hours for the overall prototype. This is a planning estimate, not logged work or a currency cost.

Proposed per-instance allocation: 4 vCPU and 5 GiB across Go, ADK and Laya. Qualify actual model memory and concurrent load.

Owner must approve region, SQL tier, usage assumptions, billing currency and retention before spend.

## 11. Snapshots of the prototype

Local backoffice prototype with a fixture database. Deployed screenshots are pending.

The catalog editor preserves the stored item and visibility state. Final voice/map capture follows release.

Local Task 9 backoffice screenshot, fixture database, cropped top workspace. Deployed screenshot capture pending.

## 12. Prototype Performance report/Benchmarking

Acceptance targets. No deployed benchmark measurements are available yet.

| Metric | Target | Deployed result |
| --- | --- | --- |
| Actionable audio p95 | <=5 s / 30 turns | Not measured |
| Verified card p95 | <=8 s / 30 turns | Not measured |
| Typed lookup p95 | <=2 s / 30 trials | Not measured |
| Selection-to-route p95 | <=2 s / 30 trials | Not measured |
| Supported item in top 3 | >=27 / 30 prompts | Not measured |
| Laya English intent | >=36 / 40 inputs | Not measured |

Local source checks cover build/unit/fixture behavior. Actual native audio, load and rollback gates remain open.

## 13. Additional Details/Future Development (if any)

After the accepted English prototype

Expand catalog coverage and integrate maintained store data, with review of shelf/map freshness.

Evaluate pgvector retrieval for broader aliases while retaining authoritative product IDs and stored locations.

Add Thai, Mandarin Chinese and Japanese only after locale data, UI and native voice tests pass.

Consider recipes and multi-item routes under separate requirements. Real stock and indoor location need their own data sources.

## 14. Provide links to your:

GitHub Public Repository

https://github.com/apaichon/prompt-shop

Current repository is PRIVATE. Public submission access needs an authorized publication path.

Demo Video Link (3 Minutes)

Pending accepted-release recording and approved sharing link.

Final Product Link

Pending verified HTTPS deployment and reviewer access.

## 15. Release and rehearsal readiness

Release before rehearsal

Complete routing, classifier and gateway integration. Qualify the actual GCP candidate, native English flow and full-bundle rollback.

Rehearsal on 17 October 2026

Record the three-minute walkthrough on the accepted revision. Verify sound, readable maps, backup playback and reviewer sharing.

Submission planned for 18 October, Asia/Bangkok

Exact cutoff, destination and team leader still need confirmation. User reviews the final package before submission.

## 16. Thank you

Original closing branding retained.
