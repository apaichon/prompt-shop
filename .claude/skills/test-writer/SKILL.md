---
name: test-writer
description: Use when generating a TEST-XXXX artifact and the corresponding test code for a task.
---

# Test Writer

## Steps
1. Read the target task and its linked requirements / design.
2. Run `node scripts/next-id.js test`.
3. Copy `docs/sdlc/_templates/test.md` to `docs/sdlc/07-tests/<ID>-<slug>.md`.
4. Fill `target:`, `implements:`, `test_type:`, and write Setup/Steps/Expected.
5. Write the actual test code in the project's test location.
6. Append the new TEST ID to the task's `verified_by:` list.
