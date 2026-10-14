---
name: requirement-author
description: Use when drafting a new requirement (REQ-XXXX) for prompt-shop. Captures its roadmap link, 5W1H context, workflow, outcome, acceptance criteria, and dependency links.
---

# Requirement Author

## Steps
1. Run `node scripts/next-id.js requirement` to get the next REQ ID.
2. Copy `docs/sdlc/_templates/requirement.md` to `docs/sdlc/02-requirements/<ID>-<slug>.md`.
3. Capture the roadmap outcome in `advances:` when one exists. Ask only for missing information needed to complete: Who, What, When, Where, Why, How success is observed, the measurable outcome, scope/non-goals, 3–5 Given/When/Then acceptance criteria, priority, and risk.
4. Fill the 5W1H canvas first, then make the Mermaid 5W1H graph and requirement workflow use the same actors, triggers, capability, evidence, and outcome. Do not leave generic placeholder nodes in an approval-ready requirement.
5. Fill the frontmatter and body. Set `created` and `updated` to today's date.
6. Set `status: proposed`. Before suggesting approval, verify the outcome has a metric or observable state, every acceptance criterion traces to the 5W1H canvas, and scope boundaries are explicit.
7. Print the file path and summarize the intended outcome in one sentence.
