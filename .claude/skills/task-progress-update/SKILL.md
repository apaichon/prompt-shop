---
name: task-progress-update
description: Use whenever changing the status of any SDLC artifact. Applies status propagation across linked docs (replacement for manual frontmatter edits).
---

# Task Progress Update

## Usage
`task-progress-update <artifact-id> <new-status> [optional note]`

## Steps
1. Locate the artifact file by ID (search `docs/sdlc/**/*.md`).
2. Read its frontmatter and body.
3. Set the new `status:` and bump `updated:` to today.
4. If a note is provided, append `> note: <text>` to the body.
5. Invoke `node scripts/sdlc-propagate.js <file>` to apply propagation rules.
6. Re-export the graph: `node scripts/sdlc-graph.js`.
7. Print a summary of which files were touched.
