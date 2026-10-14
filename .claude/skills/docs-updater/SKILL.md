---
name: docs-updater
description: Use when adding a new agent or skill to keep README.md and CLAUDE.md / AGENTS.md rosters in sync.
---

# Docs Updater

## Steps
1. Walk `.claude/agents/*.md` and `.claude/skills/*/SKILL.md`. Read names and descriptions.
2. Walk `AGENTS.md` and the agents under `agents/` for Codex (if present).
3. Regenerate the "Roster" section in `README.md` and the equivalent in `CLAUDE.md` / `AGENTS.md`. Do not touch other sections.
4. Print a diff summary.
