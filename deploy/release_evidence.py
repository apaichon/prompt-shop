"""Frozen QA recomputation and owner-reviewed release evidence qualification."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys

from release_contracts import CHECKS, RECOVERY_CHECKS, digest
from staging import require

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def utc(value):
    require(isinstance(value, str), "UTC timestamp required")
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(stamp.tzinfo is not None and stamp.utcoffset().total_seconds() == 0, "timestamp must carry UTC offset")
    return stamp


def read_json(path):
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 2_000_000, "bounded regular JSON file required")
    value = json.loads(path.read_text())
    require(isinstance(value, dict), "JSON object required")
    return value


def reviewed(directory, check, subject):
    require(isinstance(check, dict) and set(check) == {"status", "reviewer", "artifact", "sha256"}, "review check fields differ")
    require(check["status"] == "pass" and isinstance(check["reviewer"], str) and check["reviewer"].strip(), "reviewed evidence missing")
    require(isinstance(check["artifact"], str) and re.fullmatch(r"[A-Za-z0-9_-]+\.json", check["artifact"]), "single redacted JSON artifact name required")
    require(isinstance(check["sha256"], str) and re.fullmatch(r"[0-9a-f]{64}", check["sha256"]), "artifact digest missing")
    path = directory / check["artifact"]
    value = read_json(path)
    require(hashlib.sha256(path.read_bytes()).hexdigest() == check["sha256"], "review artifact changed")
    require(value.get("schema_version") == "release-check-v1" and value.get("environment") == "deployed" and value.get("subject") == subject and value.get("verdict") == "pass", "artifact identity/verdict differs")
    require(value.get("reviewer") == check["reviewer"], "artifact reviewer differs")
    stamp = utc(value.get("observed_at"))
    require(stamp <= datetime.now(timezone.utc), "future evidence timestamp")
    return value


def checks(c, r, directory, operation):
    required = CHECKS if operation == "promote" else RECOVERY_CHECKS
    subject = {"project_id": c["project_id"], "region": c["region"], "service": c["service"],
               "candidate_revision": r["candidate_revision"], "source_commit": r["source_commit"],
               "known_good_revision": r["known_good"]["revision"], "origin": c["public_origin"]}
    results = {}
    for name in sorted(required):
        value = reviewed(directory, r["checks"][name], subject)
        require(value.get("check") == name, "artifact check name differs")
        facts = value.get("facts", {})
        if name == "baseline_qualification":
            require(facts.get("bundle") == r["known_good"] and facts.get("native_voice_and_backoffice_verified") is True, "baseline qualified bundle differs")
        elif name == "schema_compatibility":
            require(facts.get("additive_only") is True and facts.get("rollback_database_writes") is False and isinstance(facts.get("current_schema_version"), str) and facts["current_schema_version"] and isinstance(facts.get("baseline_schema_version"), str) and facts["baseline_schema_version"], "reviewed schema compatibility missing")
        elif name == "same_origin_access":
            require(facts.get("verified_browser_origin") == c["public_origin"] and facts.get("candidate_revision") == r["candidate_revision"] and facts.get("actual_native_session_verified") is True, "candidate tag/origin access has not been qualified")
        elif name == "five_user_load":
            require(type(facts.get("simultaneous_live_sessions")) is int and facts["simultaneous_live_sessions"] >= 5 and facts.get("typed_and_admin_requests_observed") is True and facts.get("bounds_and_recovery_verified") is True, "separate five-user load evidence missing")
        elif name == "optional_languages":
            require(isinstance(facts.get("offered"), list) and set(facts["offered"]) <= {"th-TH", "zh-CN", "ja-JP"} and facts.get("all_offered_smoke_passed") is True, "offered optional locales not qualified")
        else:
            require(facts.get("verified") is True, "reviewed check facts incomplete")
        results[name] = {"reviewer": r["checks"][name]["reviewer"], "sha256": r["checks"][name]["sha256"]}
    return results


def qa(c, lock, r, directory):
    from tests.qa.contracts import load_frozen
    from tests.qa.report import release_report
    observations = read_json(directory / r["qa_observations"])
    http_run = read_json(directory / r["qa_http_run"])
    candidate = observations.get("candidate", {})
    require(candidate.get("commit") == r["source_commit"] == lock["source_commit"] and candidate.get("deployment_id") == r["candidate_revision"] and candidate.get("origin") == c["public_origin"], "QA belongs to a different candidate/origin/source")
    frozen = load_frozen()
    report = release_report(*frozen, observations, http_run, directory / r["qa_artifacts"], expected_model=c["gemini_model"])
    require(report["recommendation"] == "READY_FOR_OWNER_REVIEW", "TASK-0006 acceptance incomplete or failed")
    return {"frozen_inputs": report["frozen_inputs"], "observations_sha256": digest(observations), "http_sha256": digest(http_run),
            "model_revision": candidate["laya_revision"], "device": candidate["device"], "network": candidate["network"]}


SMOKE_FACTS = {"https_ready", "native_gemini_adk", "real_laya", "audible_grounded_answer", "verified_card_and_route",
               "spoken_selection", "protected_backoffice", "fresh_session_on_target", "old_socket_restart", "no_secret_or_content_logs"}


def smoke(c, r, directory, proof, revision, source, images, model_revision, operation_hash):
    subject = {"project_id": c["project_id"], "region": c["region"], "service": c["service"],
               "revision": revision, "source_commit": source, "origin": c["public_origin"], "operation_sha256": operation_hash}
    value = reviewed(directory, proof, subject)
    facts = value.get("facts", {})
    require(value.get("check") == "native_release_smoke" and set(facts) == SMOKE_FACTS | {"images", "model_revision"}, "full native/backoffice smoke facts required")
    require(all(facts[name] is True for name in SMOKE_FACTS) and facts["images"] == images and facts["model_revision"] == model_revision, "smoke bundle/model/flow differs")
    return value
