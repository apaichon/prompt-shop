"""Release preflight, read-only capture, named promotion/rollback and final evidence.

Default operations are offline. Only --execute changes existing service traffic.
No creation, IAM mutation, secret reads, database rollback or automatic retry.
"""
import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from staging import require, validate_config, validate_lock
from release_contracts import target, validate_release, source_audit, digest, revision_view, service_view, iam_view, identity, ready, revision_name
from release_evidence import read_json, checks, qa, smoke, utc, reviewed
from release_ops import Cloud, inspect, traffic_command, execute, arguments


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    require(not path.is_symlink(), "output symlink forbidden")
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as temp:
        json.dump(value, temp, indent=2, allow_nan=False)
        temp.write("\n")
        temp.flush()
        os.fsync(temp.fileno())
        temporary = Path(temp.name)
    temporary.chmod(0o600)
    temporary.replace(path)
    descriptor = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def audit(root, tag, config=None):
    failures = []
    try:
        source = source_audit(root, tag)
        if source["status"] != "pass": failures.append("required integrated build inputs missing")
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError):
        source = {"status": "blocked", "tag": tag}
        failures.append("source tag/build identity unqualified")
    if shutil.which("gcloud") is None: failures.append("gcloud unavailable")
    if config is None:
        failures.append("cloud deployment configuration absent")
    else:
        try: validate_config(read_json(config), render=True)
        except (ValueError, OSError, KeyError, TypeError): failures.append("cloud deployment configuration incomplete")
    # Source audit does not run or infer native/deployed acceptance.
    failures.append("actual candidate/baseline/QA/release evidence required by plan")
    return {"schema_version": "release-audit-v1", "source": source, "status": "blocked", "blockers": failures,
            "scope": "Source/tooling inventory; no cloud commands, provider smoke or deployment performed."}


def load_inputs(config, images, release, operation):
    c, lock, r = read_json(config), read_json(images), read_json(release)
    target(c)
    if operation in ("promote", "verify"):
        validate_config(c, render=True)
        validate_lock(lock, c)
    # Emergency rollback does not wait for a working candidate or new QA.
    validate_release(c, r)
    return c, lock, r


def make_plan(root, c, lock, r, captures, evidence, operation):
    require(operation in ("promote", "rollback"), "named operation required")
    target(c)
    validate_release(c, r)
    age = (datetime.now(timezone.utc)-utc(captures.get("captured_at"))).total_seconds()
    require(0 <= age <= 300, "cloud snapshot stale or future; recollect before mutation")
    view = inspect(c, lock, r, captures, operation)
    verified = checks(c, r, evidence, operation)
    source, acceptance = None, None
    if operation == "promote":
        validate_config(c, render=True)
        validate_lock(lock, c)
        require(lock["source_commit"] == r["source_commit"], "candidate image/source differs")
        source = source_audit(root, r["git_tag"], r["source_commit"])
        require(source["status"] == "pass", "source integration/build inputs incomplete")
        acceptance = qa(c, lock, r, evidence)
    revision = r["candidate_revision"] if operation == "promote" else r["known_good"]["revision"]
    return {"schema_version": "release-plan-v1", "operation": operation, "created_at": datetime.now(timezone.utc).isoformat(),
            "context_sha256": digest({"config": c, "images": lock, "release": r}), "expected_state_sha256": digest(view),
            "target_revision": revision, "command": traffic_command(c, revision), "source": source, "qa": acceptance,
            "reviewed_checks": verified, "state": "QUALIFIED_OFFLINE_PLAN", "effect": "No cloud change has been executed."}


def sanitized(c, lock, r, captures, operation):
    # Reconstruct only reviewed contract fields. Omit arbitrary labels, logs,
    # literal secrets, principal email addresses and all unsupported env fields.
    view = inspect(c, lock, r, captures, operation)
    service = captures["service"]
    s = {"apiVersion": "serving.knative.dev/v1", "kind": "Service", "metadata": {
        "name": c["service"], "namespace": c["project_number"], "resourceVersion": view["service"]["resource_version"],
        "labels": {"cloud.googleapis.com/location": c["region"]}, "annotations": {"run.googleapis.com/invoker-iam-disabled": "false"}},
        "status": {key: service["status"][key] for key in ("conditions", "latestCreatedRevisionName", "latestReadyRevisionName", "url")}}
    s["status"]["conditions"] = [{"type": "Ready", "status": "True" if view["service"]["ready"] else "False"}]
    s["status"]["traffic"] = [{"revisionName": row["revision"], "percent": row["percent"], **({"tag": row["tag"]} if row["tag"] else {})} for row in view["service"]["traffic"]]
    def safe_revision(value):
        return {"apiVersion": value["apiVersion"], "kind": "Revision", "metadata": {
            "name": value["metadata"]["name"], "namespace": c["project_number"],
            "labels": {"serving.knative.dev/service": c["service"]}, "annotations": {
                key: value["metadata"]["annotations"][key] for key in ("run.googleapis.com/cloudsql-instances", "autoscaling.knative.dev/maxScale", "autoscaling.knative.dev/minScale", "run.googleapis.com/execution-environment", "run.googleapis.com/cpu-throttling", "run.googleapis.com/container-dependencies")}},
            "spec": {key: value["spec"][key] for key in ("serviceAccountName", "containerConcurrency", "timeoutSeconds", "containers")},
            "status": {"conditions": [{"type": "Ready", "status": "True"}]}}
    # Container exports were validated; keep only approved fields/probe routes.
    def trim(value):
        value = safe_revision(value)
        value["spec"]["containers"] = [{key: row[key] for key in ("name", "image", "env", "resources")}
            | {"startupProbe": {"httpGet": row["startupProbe"]["httpGet"]}}
            | ({"livenessProbe": {"httpGet": row["livenessProbe"]["httpGet"]}} if row.get("livenessProbe") else {})
            | ({"ports": row["ports"]} if row.get("ports") else {}) for row in value["spec"]["containers"]]
        return value
    bindings = []
    for b in captures["iam"].get("bindings", []):
        members = sorted(set(b.get("members", [])) & {"allUsers", "allAuthenticatedUsers"})
        if members: bindings.append({"role": b["role"], "members": members, **({"condition": {"present": True}} if b.get("condition") else {})})
    return {"schema_version": "cloud-snapshot-v1", "captured_at": datetime.now(timezone.utc).isoformat(), "service": s,
            "candidate": trim(captures["candidate"]) if operation != "rollback" else None,
            "known_good": trim(captures["known_good"]), "iam": {"bindings": bindings, "etag": view["access"]["etag"]}}


def fault_capture(c, r, name, cloud=None):
    revision_name(c, name)
    require(name not in (r["candidate_revision"], r["known_good"]["revision"]), "isolated failing revision must differ from candidate/baseline")
    raw = (cloud or Cloud()).call(arguments(c, ["run", "revisions", "describe", name]))
    metadata = identity(c, raw, name, "Revision")
    require(metadata.get("labels", {}).get("serving.knative.dev/service") == c["service"], "fault revision service differs")
    return {"apiVersion": raw["apiVersion"], "kind": "Revision", "captured_at": datetime.now(timezone.utc).isoformat(),
            "metadata": {"name": name, "namespace": c["project_number"], "labels": {"serving.knative.dev/service": c["service"]}},
            "status": {"conditions": [{"type": "Ready", "status": "True" if ready(raw) else "False"}]}}


def finalize(c, lock, r, evidence, operations, proofs, captures):
    require(len(operations) == 3 and [x.get("operation") for x in operations] == ["promote", "rollback", "promote"], "promotion, rollback rehearsal and final promotion records required")
    require(all(x.get("schema_version") == "release-operation-v1" and x.get("state") == "TRAFFIC_VERIFIED_SMOKE_PENDING" and x.get("project_id") == c["project_id"] and x.get("region") == c["region"] and x.get("service") == c["service"] and x.get("source_commit") == r["source_commit"] for x in operations), "verified operation records differ")
    require(all(x.get("context_sha256") == digest({"config": c, "images": lock, "release": r}) for x in operations), "operation release context differs")
    expected_revisions = [r["candidate_revision"], r["known_good"]["revision"], r["candidate_revision"]]
    require([x.get("target_revision") for x in operations] == expected_revisions, "operation target differs")
    for left, right in zip(operations, operations[1:]):
        require(utc(left["verified_at"]) <= utc(right["started_at"]), "operation chronology invalid")
    require(isinstance(proofs, dict) and set(proofs) == {"post_promotion", "fault_injection", "rollback", "final_promotion"}, "three actual smokes and isolated failing-revision rehearsal required")
    model = qa(c, lock, r, evidence)["model_revision"]
    checks(c, r, evidence, "promote")
    smokes = []
    for index, key in enumerate(("post_promotion", "rollback", "final_promotion")):
        baseline = r["known_good"] if index == 1 else {"revision": r["candidate_revision"], "source_commit": r["source_commit"], "images": lock["images"], "model_revision": model}
        op = operations[index]
        require(op.get("target_source_commit") == baseline["source_commit"] and op.get("images") == baseline["images"], "operation source/image bundle differs")
        require(isinstance(op.get("plan_sha256"), str) and len(op["plan_sha256"]) == 64 and type(op.get("traffic_operation_ms")) in (float, int) and math.isfinite(op["traffic_operation_ms"]) and op["traffic_operation_ms"] >= 0, "operation plan/timing record missing")
        require(utc(op["started_at"]) <= utc(op["verified_at"]) <= datetime.now(timezone.utc), "operation timestamps invalid")
        observed = smoke(c, r, evidence, proofs[key], baseline["revision"], baseline["source_commit"], baseline["images"], baseline["model_revision"], digest(op))
        require(utc(observed["observed_at"]) >= utc(operations[index]["verified_at"]), "smoke predates effective traffic verification")
        if index < 2: require(utc(observed["observed_at"]) <= utc(operations[index+1]["started_at"]), "smoke belongs to a later operation")
        smokes.append(observed)
    recovery = (utc(smokes[1]["observed_at"])-utc(operations[1]["started_at"])).total_seconds()
    require(0 <= recovery <= 900, "full rollback smoke recovery exceeded 15 minutes")
    fault_subject = {"project_id": c["project_id"], "region": c["region"], "service": c["service"],
                     "candidate_revision": r["candidate_revision"], "source_commit": r["source_commit"],
                     "known_good_revision": r["known_good"]["revision"], "origin": c["public_origin"], "operation_sha256": digest(operations[1])}
    fault = reviewed(evidence, proofs["fault_injection"], fault_subject)
    facts = fault.get("facts", {})
    require(fault.get("check") == "rollback_fault_injection" and facts.get("failure_observed") is True and facts.get("test_traffic_isolated") is True and facts.get("ordinary_database_preserved") is True, "actual supervised fault rehearsal missing")
    name = revision_name(c, facts.get("failing_revision"))
    require(name not in (r["candidate_revision"], r["known_good"]["revision"]), "failing revision must be isolated")
    import re, hashlib
    require(isinstance(facts.get("revision_capture"), str) and re.fullmatch(r"[A-Za-z0-9_-]+\.json", facts["revision_capture"]), "fault capture filename invalid")
    fault_path = evidence / facts["revision_capture"]
    fault_view = read_json(fault_path)
    require(hashlib.sha256(fault_path.read_bytes()).hexdigest() == facts.get("revision_capture_sha256"), "fault revision capture hash differs")
    metadata = identity(c, fault_view, name, "Revision")
    require(metadata.get("labels", {}).get("serving.knative.dev/service") == c["service"], "fault capture service differs")
    require(utc(smokes[0]["observed_at"]) <= utc(fault_view["captured_at"]) <= utc(fault["observed_at"]) <= utc(operations[1]["started_at"]), "fault rehearsal chronology invalid")
    captured_at = utc(captures["captured_at"])
    require(0 <= (datetime.now(timezone.utc)-captured_at).total_seconds() <= 300, "final cloud state stale")
    require(captured_at >= utc(smokes[2]["observed_at"]), "final cloud snapshot predates final smoke; recollect after smoke completion")
    view = service_view(c, captures["service"])
    require(view["ready"] and view["percentages"].get(r["candidate_revision"]) == 100, "final normal traffic is not the accepted candidate")
    revision_view(c, captures["candidate"], r["candidate_revision"], lock["images"], c["secrets"])
    iam_view(c, captures["iam"])
    return {"schema_version": "release-result-v1", "state": "ELIGIBLE_FOR_OWNER_DEPLOYMENT_RECORD", "git_tag": r["git_tag"],
            "source_commit": r["source_commit"], "origin": c["public_origin"], "revision": r["candidate_revision"], "images": lock["images"],
            "secret_refs": c["secrets"], "model_revision": model, "rollback_revision": r["known_good"]["revision"], "rollback_recovery_seconds": recovery,
            "operation_hashes": [digest(op) for op in operations], "scope": "Owner-reviewed actual cloud/QA artifacts qualified; SDLC completion still requires recording the real deployment."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    audit_parser = sub.add_parser("audit")
    audit_parser.add_argument("--tag", default="v0.1.0")
    audit_parser.add_argument("--config", type=Path)
    for name in ("plan", "capture", "fault-capture", "execute", "finalize"):
        p = sub.add_parser(name)
        p.add_argument("--config", type=Path, required=True)
        p.add_argument("--images", type=Path, required=True)
        p.add_argument("--release", type=Path, required=True)
        p.add_argument("--operation", choices=("promote", "rollback", "verify") if name == "capture" else ("promote", "rollback"), default="promote")
        if name == "fault-capture": p.add_argument("--failing-revision", required=True)
        if name in ("plan", "execute", "finalize"):
            p.add_argument("--evidence", type=Path, required=True)
            p.add_argument("--captures", type=Path, required=True)
        if name == "execute":
            p.add_argument("--plan", type=Path, required=True)
            p.add_argument("--execute", action="store_true", help="explicitly change existing service traffic")
        if name == "finalize":
            p.add_argument("--operations", nargs=3, type=Path, required=True)
            p.add_argument("--smokes", type=Path, required=True)
    for p in (audit_parser, *[a for a in sub.choices.values() if a is not audit_parser]):
        p.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
        p.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "audit":
            result = audit(args.root, args.tag, args.config)
        else:
            require(not args.out.exists(), "use a new output path; operation history cannot be overwritten")
            if args.command == "execute": require(args.execute, "traffic mutation requires explicit --execute")
            c, lock, r = load_inputs(args.config, args.images, args.release, args.operation)
            if args.command == "capture":
                raw = Cloud().capture(c, r["candidate_revision"], r["known_good"]["revision"])
                result = sanitized(c, lock, r, raw, args.operation)
            elif args.command == "fault-capture":
                result = fault_capture(c, r, args.failing_revision)
            elif args.command == "finalize":
                require(source_audit(args.root, r["git_tag"], r["source_commit"])["status"] == "pass", "final source tag/build inputs unqualified")
                result = finalize(c, lock, r, args.evidence, [read_json(p) for p in args.operations], read_json(args.smokes), read_json(args.captures))
            else:
                fresh = make_plan(args.root, c, lock, r, read_json(args.captures), args.evidence, args.operation)
                if args.command == "plan": result = fresh
                else:
                    require(args.execute, "traffic mutation requires explicit --execute")
                    plan = read_json(args.plan)
                    require(plan.get("schema_version") == "release-plan-v1" and plan.get("context_sha256") == fresh["context_sha256"] and plan.get("expected_state_sha256") == fresh["expected_state_sha256"] and plan.get("qa") == fresh["qa"] and plan.get("reviewed_checks") == fresh["reviewed_checks"] and plan.get("operation") == args.operation, "saved plan/evidence changed")
                    result = execute(c, lock, r, plan, record=lambda value: write(args.out, value))
        write(args.out, result)
        passed = result.get("status") != "blocked" and result.get("state") != "CHANGE_ATTEMPTED_RESULT_UNVERIFIED"
        print(json.dumps({"output": str(args.out), "state": result.get("state", result.get("status", "captured"))}))
        return 0 if passed else 1
    except (ValueError, KeyError, TypeError, IndexError, AttributeError, OSError, subprocess.SubprocessError):
        # Never echo supplied JSON, raw SDK output or exception text.
        print("release_rejected: missing, invalid, stale or unqualified inputs", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
