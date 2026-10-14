---
id: REQ-XXXX
type: requirement
title: <one-line title>
status: proposed
owner: pm-agent
created: YYYY-MM-DD
updated: YYYY-MM-DD
risk: low
risk_notes: ""
tags: []
priority: should
source: ""
advances: []
acceptance_criteria:
  - "Given … when … then …"
implements: []
designed_by: []
verified_by: []
deployed_in: []
blocks: []
blocked_by: []
related: []
---

# Requirement: <title>

## Outcome

State the observable user or business result. Use a measurable form such as: **Increase/decrease `<metric>` from `<baseline>` to `<target>` by `<date>`**.

## 5W1H canvas

| Dimension | Question | Answer |
|---|---|---|
| **Who** | Who needs this, uses it, approves it, or is affected? | <actors and stakeholders> |
| **What** | What capability, behavior, or constraint is required? | <required result, not a solution> |
| **When** | When is it triggered, needed, or considered complete? | <trigger, frequency, deadline> |
| **Where** | Where does it apply in the journey, system, or environment? | <touchpoints and boundaries> |
| **Why** | Why does it matter, and what problem or opportunity does it address? | <value and evidence> |
| **How** | How will success be observed without prescribing implementation? | <measurement and acceptance approach> |

## 5W1H graph

Keep every node short and consistent with the canvas above.

```mermaid
flowchart LR
    WHY["Why<br/><value or problem>"] --> WHAT["What<br/><required capability>"]
    WHO["Who<br/><actor or stakeholder>"] --> WHAT
    WHEN["When<br/><trigger or timing>"] --> WHAT
    WHERE["Where<br/><scope or touchpoint>"] --> WHAT
    WHAT --> HOW["How<br/><success evidence>"]
    HOW --> OUTCOME["Outcome<br/><metric and target>"]
```

## Requirement workflow

```mermaid
flowchart LR
    NEED["Evidence / need"] --> DRAFT["Draft 5W1H"]
    DRAFT --> REVIEW["Stakeholder review"]
    REVIEW -->|changes| DRAFT
    REVIEW -->|approved| DESIGN["Design and task decomposition"]
    DESIGN --> VERIFY["Verify acceptance criteria"]
    VERIFY --> OUTCOME["Measure outcome"]
```

## Context and evidence

<problem evidence, current behavior, baseline, and relevant links>

## Acceptance criteria

- [ ] Given <starting context>, when <event or action>, then <observable result>.
- [ ] The outcome metric has an owner, baseline, target, and measurement date.
- [ ] Scope and non-goals are explicit.

## Scope

- **In scope:** <included behavior>
- **Out of scope:** <excluded behavior>
- **Dependencies:** <other artifacts, teams, systems, or decisions>

## Notes

<decisions, open questions, and follow-up links>
