# Three-minute walkthrough

Planned script for the accepted deployment. The AI Builder Cup template requests a three-minute demo. Rehearse to 180 seconds while preserving actual model audio and failures. These time slots are a production plan, not measured response latency.

Before starting, confirm the exact accepted URL/revision/images, presenter browser/network and enabled English locale in the rehearsal record. Record only the presenter's deliberate sample conversation. Use the approved normal hostname and current database. Prepare maintainer access privately, and keep sign-in/password entry off camera.

| Time | Presenter action and proposed words | Required observation |
|---|---|---|
| 0:00-0:15 | Open shopper `/`. “Prompt Shop helps a shopper find an item in a sample hypermarket. Directions start at the entrance.” Show the recorded-demo designation and accepted revision caption. | Sample-store notice and entrance origin are visible. |
| 0:15-0:55 | Select **Start voice**, grant microphone access and say “Where is milk?” When clarification arrives, speak a current returned choice, for example “Whole milk, please” if it is offered. | Actual ADK-managed Gemini Live 3.8 responds audibly. Real Laya participates. Verified candidates appear, spoken selection resolves the current product, and the selected card/map/text agree with stored facts. |
| 0:55-1:15 | While directions play, interrupt with “Wait, repeat the directions.” | Earlier playback stops and current directions resume without stale card or map updates. |
| 1:15-1:30 | Ask for a deliberately absent item confirmed during rehearsal. | Truthful not-found/clarification response. A dependency/tool failure remains an error, never a fabricated not-found result. |
| 1:30-1:40 | Select **End voice**. Introduce the maintainer view on the same hostname. | Microphone and playback stop. No hidden listening continues. |
| 1:40-2:20 | In an already authenticated `/backoffice` tab, select **+ New item**. Save a designated rehearsal item with English alias and an existing mapped shelf using **Save as draft**, then **Publish item**. | Draft remains hidden until explicit publication. Show the stored shelf and successful server response. |
| 2:20-2:45 | Return to shopper `/`, type the unique rehearsal alias and select **Find item**, then **Show route**. | The new published product appears without portal redeployment. Its stored shelf matches route/map/text. |
| 2:45-2:55 | Return to backoffice, select **Log out** and show the login view. | Maintainer editing is unavailable. Attach the separate direct-write-after-logout denial observation from the rehearsal. |
| 2:55-3:00 | “This demo uses sample store data. The proposal links the source, walkthrough and verified release.” | Closing links match the actual recorded revision. |

For the baseline seed, Whole milk 1 L is product `milk-whole-1l` at `a02-s03` (Aisle 2, Shelf 3). Read the accepted catalog before rehearsal: this source example never overrides current tool/database facts. Seed ambiguity contains four milk products; show up to three returned choices and speak a current visible choice, without promising a fixed ranking.

Use a separate item such as a unique `rehearsal-...` ID and alias, approved by the maintainer. Record its ID/shelf/state before and after publication. Do not edit seeded items, frozen prompt/evaluation inputs or acceptance holdouts. Archive only that rehearsal item after evidence capture if the maintainer approves cleanup; preserve the record and audit.

If the core native flow fails, stop the take, record the failed attempt and use the accurately labelled backup from the same accepted release. Typed recovery is available to explain usability but does not satisfy native voice acceptance. Repeat the affected evidence if source, runtime bundle or catalog/map changes.
