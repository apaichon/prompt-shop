# Presenter and operator runbook

Use the accepted deployment and the identity pinned in the rehearsal record. No release or rollback is executed by this document. Keep the responsible operator/contact route in the private rehearsal record, and preserve the accepted backup recording locally before presentation.

| Symptom | Presenter action | Operator evidence/action |
|---|---|---|
| Microphone denied or unavailable | End voice; check browser permission/secure context, then explicitly restart. Explain typed recovery if useful. | Record the separate consent/device case. It cannot count as a passed native demo. |
| Sound muted or blocked | Check **Mute sound** state/output device and use a fresh user gesture to restart. | Verify actual audible output and PCM path on the recorded browser. |
| Setup timeout, quota or dependency error | End the attempt. Record failure; retry only when the owner confirms recovery, using fresh **Start voice**. | Check content-free error/revision/health metrics and actual provider/ADK/Laya availability. No raw transcript/audio/key diagnostic collection. |
| Session expired, idle or network disconnected | Stop capture/playback, show restart notice and start a fresh session explicitly. | Confirm old socket/work/queued output is gone and new session targets accepted revision. No automatic audio replay. |
| Card, speech or map disagrees with stored facts | Stop the demonstration and preserve a redacted failure observation. | Treat as release regression. Check authoritative catalog/map/turn evidence; never narrate an invented shelf as correct. |
| Backoffice session expired or version conflict | Re-authenticate privately; reload current version before resubmitting an intentional edit. | Verify server authorization/CSRF/version handling. Never overwrite a newer product or reveal credentials on camera. |
| Core live demo cannot recover | Play the previously verified backup with “Recorded demo” visible and state its date/revision. | Preserve the failed live attempt separately; a backup cannot pass a failed release gate. |

Expected design limits are setup 30 seconds, session 300 seconds from ready, idle 60 seconds and outer request 360 seconds. Verify actual release behavior in TEST-0004; these limits are configuration requirements, not measured timings. Closing the mobile drawer ends the active voice session.

Rollback belongs to the responsible release operator. Follow the accepted Task 8 runbook and qualified matched Go/ADK/Laya baseline, secret versions and compatible database. [Current preparation PR](https://github.com/apaichon/prompt-shop/pull/10) contains the runbook; pin its accepted successor before rehearsal. Rehearse with isolated test traffic and preserve the ordinary database. Time the full restored English/backoffice smoke from rollback initiation, target <=15 minutes. Traffic rollback does not reverse database writes. Gracefully end old sockets with restart notice and verify fresh sessions on the restored revision. Record final promotion/smoke and capture final state after smoke completion.

After the event, end all voice sessions, log out, verify the rehearsal item's agreed visibility and hand retention/cleanup back to the owner. Do not delete cloud resources or reseed the shared database as presenter cleanup.
