# Prompt Shop demo and proposal package

Preparation draft, 14 October 2026. The code source checkpoint is v0.1.0 at 50054b23cfe3336d019fee8da0db474da27940e0. The accepted deployment URL, runtime image digests and recorded native demo remain pending. Task 8's [release preparation PR](https://github.com/apaichon/prompt-shop/pull/10) is open; a source tag or local fixture cannot establish deployed acceptance.

The user supplied the AI Builder Cup submission PDF on 14 October. The proposal follows its 16-page structure and branding, including its required editable PowerPoint, public repository, three-minute demo video and final product links. Team details, exact cutoff and destination still need confirmation. The repository is currently private; this task does not change its visibility or upload a submission.

| Material | Purpose |
|---|---|
| [Proposal content](PROPOSAL.md) | Editable text and the template section mapping |
| PowerPoint proposal (local only) | Editable proposal slides following the supplied PDF |
| PDF proposal (local only) | Review copy of the same slides |
| [Walkthrough](WALKTHROUGH.md) | Planned three-minute English voice and backoffice story |
| [Reviewer setup](REVIEWER-SETUP.md) | Access, sample data, release identity and first run |
| [Runbook](RUNBOOK.md) | Bounded presenter recovery and operator handoff |
| [Recording and rehearsal](RECORDING.md) | Actual audio/video, screenshots, playback and evidence capture |
| [Provenance](PROVENANCE.md) | Architecture, source reuse and license references |
| [Submission checklist](SUBMISSION-CHECKLIST.md) | Required format, links and user review gates |
| [Rehearsal record template](rehearsal.example.json) | Blank identity/observations/assets index, never a pass |

The proposal uses a local backoffice QA screenshot as a labelled prototype illustration. It contains no recorded deployed demonstration or measured production benchmark. Replace it with accepted-release screenshots before final submission. The original PDF has flattened graphics, so its branding is preserved as images while new text, tables and process/architecture diagrams are editable. Arial replaces the PDF's embedded Google Sans Flex, which is unavailable in the authoring runtime; slide dimensions and section order remain the same.

On 17 October, after accepted Task 8 release evidence, follow [TEST-0011](../sdlc/07-tests/TEST-0011.md), record the actual rehearsal and replace all pending proposal fields. Submission is planned for 18 October, Asia/Bangkok, but the exact cutoff is unconfirmed. Offline document verification cannot pass TEST-0011.

At the user’s request, generated proposal files stay local and ignored by git: `output/pptx/Prompt-Shop-AI-Builder-Cup-Proposal.pptx` and `output/pdf/Prompt-Shop-AI-Builder-Cup-Proposal.pdf`. The repository retains proposal text and preparation guides, while PR #11 excludes both binaries.
