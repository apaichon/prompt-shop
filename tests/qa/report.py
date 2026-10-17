"""Evidence qualification, not an automatic deployment or human approval."""
from datetime import datetime, timezone
import ipaddress
import re
from urllib.parse import urlsplit
from .audit import audit_fixture
from .contracts import require, number
from .measurements import assess_series, assess_voice, assess_intent

MANUAL_CHECKS = {
    "import_atomicity": "new rows, same-ID updates, idempotency, row errors and full invalid-batch rollback",
    "voice_native_adk": "configured Gemini Live model with ADK Runner.run_live; PCM 16k input/24k output; no STT/TTS substitute",
    "voice_classification_order": "actual Laya precedes catalog for every semantic turn, including repeat and out-of-scope",
    "voice_grounding": "heard answer and visible card/map agree with current authoritative tool results; no filler timing",
    "voice_interruption": "barge-in clears playback, late events/stale epochs rejected, selection synchronized",
    "voice_permissions": "allow, deny, revoke, unsupported capture and explicit restart without auto-reconnect/replay",
    "voice_failures": "provider quota/outage, database failure, disconnect, setup timeout and session expiry",
    "voice_bounds_privacy": "600s/60s/30s limits, cleanup, private callbacks, bounded audio/tools and no content logs",
    "map_fallbacks": "unmapped/disconnected shelves give truthful location; stale map reload/retry exactly once",
    "map_accessibility": "keyboard, screen reader, color-independent path; 320/360/768/1280px without overflow",
    "auth_sessions": "direct server auth, secure host cookie, rotation, eight-hour absolute expiry, logout/replay",
    "auth_origin_csrf": "trusted origin and session-bound CSRF on every protected write; denial before mutation",
    "backoffice_integrity": "publish/edit-draft/archive affect public reads and stale product IDs; FK rollback/concurrent 409",
    "backoffice_persistence": "more than 50 rows cursor correctly; restart/container/database persistence and revision",
    "classifier_identity": "convaiinnovations/laya pinned revision; weights/config/tokenizer hashes/license; CPU resources",
    "classifier_safety": "advisory only, confidence/margin frozen, abstention contracts, private access, no raw text logs",
    "classifier_failures": "malformed/down/slow/busy/missing-token; inclusive 1200ms deadline, 200ms queue, bounded worker, no retry",
    "cold_and_faults": "prospectively separate cold/setup/fault suites and resource observations, with failures retained",
    "deployed_integration": "one integrated candidate with real public APIs, native audio, actual Laya, restricted database and backoffice",
    "release_review": "feature-freeze decision and peer/high-risk human review recorded by accountable owners",
}


def template(freeze):
    return {"schema_version": "qa-observations-v1", "candidate": {"environment": None, "origin": None,
            "commit": None, "deployment_id": None, "measured_at": None, "device": None, "network": None,
            "native_model": None, "laya_revision": None}, "frozen_inputs": freeze["files"],
            "voice": [], "intent": [], "typed_render": [], "route_render": [], "classification_warm": [],
            "cold_and_faults": [], "manual_checks": {name: {"status": "not_run", "reviewer": None,
            "artifact": None, "sha256": None, "candidate_commit": None, "purpose": purpose} for name, purpose in MANUAL_CHECKS.items()}}


def measured_evidence(observations, queries, intents):
    require(isinstance(observations, dict) and isinstance(observations.get("candidate", {}), dict), "observation/candidate object required")
    results = {}
    ids = [q["id"] for q in queries]
    calls = {
        "voice": lambda: assess_voice(observations.get("voice", []), queries),
        "intent": lambda: assess_intent(observations.get("intent", []), intents, observations.get("candidate", {}).get("laya_revision")),
    }
    for name, limit in (("typed_render", 2000), ("route_render", 2000), ("classification_warm", 1200)):
        def check(name=name, limit=limit):
            rows = observations.get(name, [])
            require(isinstance(rows, list) and all(isinstance(r, dict) for r in rows), "timing rows must be objects")
            require(all(r.get("clock_source") == "client_render_clock" for r in rows) if name != "classification_warm" else all(r.get("real_checkpoint_observed") is True for r in rows), "timing measurement provenance missing")
            return assess_series(rows, ids, limit)
        calls[name] = check
    for name, call in calls.items():
        try:
            results[name] = call()
        except (ValueError, KeyError, TypeError, IndexError):
            # Do not echo supplied observation contents or credentials in exceptions.
            results[name] = {"status": "blocked", "error": "missing_or_invalid_observations"}
    return results


def release_report(freeze, catalog, queries, intents, observations, http_run=None, artifact_directory=None, *, expected_model="gemini-3.8-live"):
    from .audit import sha256
    require(isinstance(expected_model, str) and re.fullmatch(r"(?:models/)?[A-Za-z0-9][A-Za-z0-9._-]{0,127}", expected_model), "expected Gemini model ID required")
    require(isinstance(observations, dict) and isinstance(observations.get("candidate", {}), dict) and isinstance(observations.get("manual_checks", {}), dict), "observation metadata objects required")
    require(http_run is None or isinstance(http_run, dict) and isinstance(http_run.get("suites", {}), dict), "HTTP run/suites objects required")
    report = {"schema_version": "qa-release-v1", "generated_at": datetime.now(timezone.utc).isoformat(),
              "frozen_inputs": freeze["files"], "fixture": audit_fixture(catalog, queries),
              "measurements": measured_evidence(observations, queries, intents), "expected_native_model": expected_model, "blockers": []}
    blockers = report["blockers"]
    candidate = observations.get("candidate", {})
    parsed = urlsplit(candidate.get("origin") or "")
    local = parsed.hostname == "localhost"
    try:
        local |= ipaddress.ip_address(parsed.hostname or "").is_loopback
    except ValueError:
        pass
    qualified = candidate.get("environment") == "deployed" and parsed.scheme == "https" and parsed.hostname and not local and not parsed.username and not parsed.password and parsed.path in ("", "/") and not parsed.query and not parsed.fragment
    qualified = qualified and bool(re.fullmatch(r"[0-9a-f]{40}", candidate.get("commit") or "")) and all(candidate.get(key) for key in ("deployment_id", "measured_at", "device", "network"))
    actual_model = candidate.get("native_model")
    qualified = qualified and isinstance(actual_model, str) and actual_model.removeprefix("models/") == expected_model.removeprefix("models/") and bool(re.fullmatch(r"[0-9a-f]{40}", candidate.get("laya_revision") or ""))
    if not qualified:
        blockers.append("deployed candidate/model/checkpoint/device/network provenance missing")
    if observations.get("schema_version") != "qa-observations-v1" or observations.get("frozen_inputs") != freeze["files"]:
        blockers.append("observation schema/frozen input identity differs")
    if report["fixture"]["status"] != "pass":
        blockers.append("frozen catalog fixture does not cover all acceptance expectations")
    for name, result in report["measurements"].items():
        if result["status"] != "pass":
            blockers.append(name+" acceptance incomplete or failed")
    http_run = http_run or {}
    if http_run.get("environment") != "deployed" or http_run.get("origin") != candidate.get("origin") or http_run.get("candidate_commit") != candidate.get("commit") or http_run.get("deployment_id") != candidate.get("deployment_id") or http_run.get("frozen_inputs") != freeze["files"]:
        blockers.append("HTTP probes do not belong to the same deployed candidate and frozen inputs")
    for name in ("catalog", "routes", "anonymous"):
        suite = http_run.get("suites", {}).get(name, {})
        if not isinstance(suite, dict) or suite.get("status") != "pass":
            blockers.append(name+" deployed HTTP acceptance incomplete or failed")
    report["manual_checks"] = {}
    for name in MANUAL_CHECKS:
        check = observations.get("manual_checks", {}).get(name, {})
        if not isinstance(check, dict):
            check = {}
        artifact = check.get("artifact")
        digest = check.get("sha256")
        valid = check.get("status") == "pass" and isinstance(check.get("reviewer"), str) and bool(check["reviewer"].strip()) and check.get("candidate_commit") == candidate.get("commit")
        valid = valid and isinstance(artifact, str) and artifact_directory is not None and bool(re.fullmatch(r"[a-zA-Z0-9_-]+\.(json|md|txt)", artifact)) and bool(re.fullmatch(r"[0-9a-f]{64}", digest or ""))
        if valid:
            path = artifact_directory / artifact
            valid = path.is_file() and not path.is_symlink() and path.stat().st_size <= 1_000_000 and sha256(path) == digest
        report["manual_checks"][name] = {"status": "pass" if valid else "blocked"}
        if not valid:
            blockers.append(name+" reviewed evidence missing or invalid")
    separate = observations.get("cold_and_faults")
    if not isinstance(separate, list) or not separate or not all(isinstance(r, dict) and r.get("suite") in ("cold", "setup", "fault") and isinstance(r.get("id"), str) and r["id"] and r.get("status") in ("completed", "failed", "not_available") and (r.get("duration_ms") is None or number(r["duration_ms"]) and r["duration_ms"] >= 0) for r in separate) or len({r["id"] for r in separate}) != len(separate):
        blockers.append("separate cold/fault observations missing")
    report["recommendation"] = "BLOCK_RELEASE" if blockers else "READY_FOR_OWNER_REVIEW"
    report["scope"] = "Evidence qualification only; artifact assertions require owner review. No deployment or approval is performed."
    return report
