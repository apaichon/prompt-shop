---
name: task-author
description: Use when decomposing an approved requirement and design into an executable TASK-XXXX with a 5W1H workflow and verifiable outcome.
---

# Task Author

1. Read the approved requirement and design. Confirm the design's Pre-Implementation Specs are locked before creating implementation work.
2. Run `node scripts/next-id.js task` and copy `docs/sdlc/_templates/task.md` to `docs/sdlc/05-tasks/<ID>-<slug>.md`.
3. Define one bounded deliverable. Fill `implements:`, `designed_by:`, dependency links, owner, sprint, points, and risk.
4. Complete the 5W1H execution canvas. Make the Mermaid graph, execution workflow, implementation plan, and outcome evidence use the same owner, inputs, change surface, steps, and result.
5. Write a definition of done that is observable and link planned verification through `verified_by:` when test artifacts already exist.
6. Set `created` and `updated` to today's date and `status: proposed`. Do not assign or approve the task while placeholders remain or its outcome cannot be reviewed independently.
7. Print the path, dependencies, owner, and expected outcome.
