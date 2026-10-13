---
name: incident-responder
description: Use when logging an operations event or incident.
---

# Incident Responder

## Steps
1. Run `node scripts/next-id.js operation`.
2. Copy `docs/sdlc/_templates/operation.md` to `docs/sdlc/09-operations/<ID>-<slug>.md`.
3. Fill `incident_severity:`, summary, timeline.
4. For sev1/sev2: open one or more follow-up tasks tagged `process-improvement`, linked via `related:` on the operation file.
5. If a postmortem is needed, create it as a sibling file and link via `postmortem:`.
