"""Named-revision traffic changes with drift checks and explicit smoke-pending state."""
from datetime import datetime, timezone
import os
import shutil
import subprocess
import time

from release_contracts import digest, service_view, revision_view, iam_view
from staging import require


def arguments(c, words):
    return ["gcloud", *words, "--project="+c["project_id"], "--region="+c["region"], "--quiet", "--verbosity=error", "--format=json"]


def traffic_command(c, revision):
    return arguments(c, ["run", "services", "update-traffic", c["service"], "--to-revisions="+revision+"=100"])


class Cloud:
    """SDK results are transient. No raw stdout/stderr or env values are logged."""
    def call(self, args, timeout=30):
        import json
        require(shutil.which("gcloud") is not None, "gcloud unavailable")
        env = dict(os.environ, CLOUDSDK_CORE_LOG_HTTP="false")
        run = subprocess.run(args, env=env, capture_output=True, timeout=timeout)
        require(run.returncode == 0, "gcloud command failed; inspect protected SDK diagnostics locally")
        try:
            return json.loads(run.stdout)
        except (ValueError, UnicodeDecodeError):
            raise ValueError("gcloud JSON result invalid") from None

    def capture(self, c, candidate, good):
        # No output contains a secret value: qualification precedes persistence.
        return {"service": self.call(arguments(c, ["run", "services", "describe", c["service"]])),
                "candidate": self.call(arguments(c, ["run", "revisions", "describe", candidate])),
                "known_good": self.call(arguments(c, ["run", "revisions", "describe", good])),
                "iam": self.call(arguments(c, ["run", "services", "get-iam-policy", c["service"]]))}


def inspect(c, lock, r, captures, operation):
    require(operation in ("promote", "rollback", "verify"), "snapshot operation invalid")
    service = service_view(c, captures["service"])
    baseline = r["known_good"]
    good = revision_view(c, captures["known_good"], baseline["revision"], baseline["images"], baseline["secrets"])
    candidate = None
    if operation in ("promote", "verify"):
        require(service["ready"], "service is not Ready for promotion")
        candidate = revision_view(c, captures["candidate"], r["candidate_revision"], lock["images"], c["secrets"])
    # A failed candidate does not prevent recovery to the qualified baseline.
    access = iam_view(c, captures["iam"])
    expected = baseline["revision"] if operation == "promote" else r["candidate_revision"]
    require(service["percentages"].get(expected) == 100 and all(percent == 0 for name, percent in service["percentages"].items() if name != expected), "current traffic differs; no implicit overwrite or successful no-op")
    return {"service": service, "baseline": good, "candidate": candidate, "access": access}


def execute(c, lock, r, plan, cloud=None, record=None):
    cloud = cloud or Cloud()
    operation = plan["operation"]
    require(operation in ("promote", "rollback") and plan["context_sha256"] == digest({"config": c, "images": lock, "release": r}), "plan inputs/operation changed")
    started = datetime.now(timezone.utc).isoformat()
    monotonic = time.monotonic()
    live = cloud.capture(c, r["candidate_revision"], r["known_good"]["revision"])
    before = inspect(c, lock, r, live, operation)
    require(digest(before) == plan["expected_state_sha256"], "live service/revision/IAM state drifted; recollect and review")
    target = r["candidate_revision"] if operation == "promote" else r["known_good"]["revision"]
    receipt = {"schema_version": "release-operation-v1", "operation": operation, "project_id": c["project_id"],
               "region": c["region"], "service": c["service"], "target_revision": target, "source_commit": r["source_commit"],
               "plan_sha256": digest(plan), "started_at": started, "state": "CHANGE_ATTEMPTED_VERIFY_PENDING"}
    receipt["target_source_commit"] = r["source_commit"] if operation == "promote" else r["known_good"]["source_commit"]
    receipt["context_sha256"] = plan["context_sha256"]
    if record:
        record(receipt)  # Persist intent before mutation, so process loss cannot erase it.
    try:
        # Never retries, mutates IAM, runs migration, deletes data or follows LATEST.
        cloud.call(traffic_command(c, target), timeout=180)
        after = cloud.capture(c, r["candidate_revision"], r["known_good"]["revision"])
        view = service_view(c, after["service"])
        iam_view(c, after["iam"])
        require(view["percentages"].get(target) == 100 and all(p == 0 for name, p in view["percentages"].items() if name != target), "effective traffic did not reach the exact target")
        bundle = r["known_good"] if operation == "rollback" else {"images": lock["images"], "secrets": c["secrets"]}
        target_export = after["known_good"] if operation == "rollback" else after["candidate"]
        revision_view(c, target_export, target, bundle["images"], bundle["secrets"])
        receipt.update(state="TRAFFIC_VERIFIED_SMOKE_PENDING", after_state_sha256=digest(view), images=bundle["images"])
    except (ValueError, KeyError, TypeError, OSError, subprocess.SubprocessError):
        receipt["state"] = "CHANGE_ATTEMPTED_RESULT_UNVERIFIED"
    receipt.update(verified_at=datetime.now(timezone.utc).isoformat(), traffic_operation_ms=(time.monotonic()-monotonic)*1000)
    if record:
        record(receipt)
    return receipt
