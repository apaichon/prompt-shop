# TASK-0005 offline preparation evidence — 2026-10-14

Scope: deployment configuration/build preparation in `feature/TASK-0005-staging`, based on `origin/develop` c57cd6f. Builder: GPT/Codex, acting as devops-agent. No cloud action, runtime image publication, real model call or public access change occurred. This is not TEST-0010 acceptance.

| Executed check | Observed result |
|---|---|
| `rtk proxy python3 -m unittest discover -s deploy/tests -v` | 13 tests passed; secret placement and versions, separate import identity, private ports, resource/startup bounds, candidate traffic, authorization/config rejection, scoped IAM, model integrity, committed context and three-build inputs |
| `rtk proxy python3 deploy/check_docker_context.py` | Passed using a real local Docker scratch build/export with synthetic files. Required production files included; env/generated/reference/recording/local config excluded. Unique test container/image removed. |
| `hadolint --failure-threshold warning` through local Docker, for all three Dockerfiles | Passed. The intent ENV has one documented DL3064 false-positive suppression for the boolean `TOKENIZERS_PARALLELISM`; it contains no secret. |
| `actionlint` through local Docker | Passed on `.github/workflows/deployment-config.yml`. No credential-bearing CI job. |
| `staging.py provision-plan` and `render`, synthetic config/digests | Exit0; generated command plan and valid JSON outputs. Commands were not executed against Google Cloud. |
| `staging.py render` with unchanged example configuration | Exit1: `project_id required`; no runnable manifest output. |
| Upstream registry manifest resolution | Five real immutable base digests recorded in `deploy/images.example.json`; resolution alone is not a vulnerability/build check. |
| Backend-only Docker build | **Blocked**: local engine stalled at metadata fetch for `golang:1.26.9-bookworm@sha256:d9c68c2c51161e12fd77e4c6320687c9cd86e1af1e3ad6e6cd63ff970641453c`; wrapper timed out after240s. No compiled image result. Temporary context used committed foundation a564571 plus the proposed root Dockerfile, no modified foundation worktree. |
| `git diff --check` | Passed. |

The image build did not reach Go compilation. Dockerfile lint and scratch-context success cannot substitute for building/running the three real application images. ADK and Laya full builds additionally lack the committed TASK-0010 adapter/service/model bundle; portal build inputs and shared server registration are not integrated. No fixture model is packaged for staging.

Open prerequisites: approved cloud project/number/billing, region, SQL tier/storage, budget and verified notification recipient, audience/access mechanism, cleanup/retention date, authenticated cloud tooling, merged integration source, actual Gemini access, three registry digests and measured native audio/Laya/persistence/shutdown evidence. Source/runtime/model/secret-version fields must be recorded from the actual candidate later.

Assigned Grok peer review and design signatures are pending. This builder's review is CHANGES_REQUESTED; TASK-0005 and TEST-0010 remain blocked. No success deployment record or SemVer release tag was fabricated.
