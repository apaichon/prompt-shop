"""Fixed denominators, separate cold/fault suites and fail-closed evidence."""
import math
from .contracts import require, number, intent_contract, load_frozen


def distribution(values):
    values = sorted(values)
    if not values:
        return {"count": 0, "p50_ms": None, "p95_ms": None, "max_ms": None}
    require(all(number(v) and v >= 0 for v in values), "invalid timing sample")
    rank = lambda p: values[math.ceil(p*len(values))-1]
    return {"count": len(values), "p50_ms": rank(.5), "p95_ms": rank(.95), "max_ms": values[-1]}


def assess_series(rows, expected_ids, limit_ms):
    expected = set(expected_ids)
    require(len(rows) == len(expected) and {row["id"] for row in rows} == expected, "missing/duplicate/substituted trials")
    require(all(row["suite"] == "warm_normal" for row in rows), "cold/setup/fault trials mixed into warm denominator")
    failures, values = [], []
    for row in rows:
        if row.get("status") != "completed" or not number(row.get("duration_ms")) or row["duration_ms"] < 0:
            failures.append(row["id"])
        else:
            values.append(row["duration_ms"])
    summary = distribution(values)
    summary.update({"trials": len(rows), "failures": failures, "threshold_ms": limit_ms,
                    "status": "pass" if not failures and summary["p95_ms"] is not None and summary["p95_ms"] <= limit_ms else "fail"})
    # The successful-only percentile is descriptive whenever any normal trial failed.
    summary["percentile_scope"] = "all_trials" if not failures else "completed_only_not_acceptance"
    return summary


def assess_voice(rows, queries):
    require(len(rows) == 30 and {r["id"] for r in rows} == {q["id"] for q in queries}, "voice must retain all 30 frozen trials exactly once")
    timings = {"actionable_audio": [], "verified_card": []}
    factual_failures, correct, errors = [], 0, []
    bound = {q["id"]: q["expected_product_id"] for q in queries}
    published_ids = {p["id"] for p in load_frozen()[1]["products"] if p["state"] == "published"}
    for row in rows:
        require(row["suite"] == "warm_normal", "voice setup/cold/fault exclusion must be prospective")
        end = row.get("last_voiced_sample_ms")
        require(number(end) and end >= 0, "last voiced microphone sample timestamp required")
        require(row.get("speech_end_source") == "client_capture_clock_qa_vad", "speech end cannot be tool/caption/server timestamp")
        for name, field in (("actionable_audio", "first_actionable_audible_ms"), ("verified_card", "first_verified_card_render_ms")):
            stamp = row.get(field)
            completed = row.get("status") == "completed" and number(stamp) and stamp >= end
            timings[name].append({"id": row["id"], "suite": "warm_normal", "status": "completed" if completed else "failed", "duration_ms": stamp-end if completed else None})
        require(isinstance(row.get("candidate_ids"), list) and len(row["candidate_ids"]) <= 3, "voice candidate cap invalid")
        require(all(isinstance(i, str) and i in published_ids for i in row["candidate_ids"]) and len(set(row["candidate_ids"])) == len(row["candidate_ids"]), "voice candidates unknown/inactive/duplicated")
        correct += int(bound[row["id"]] is not None and bound[row["id"]] in row["candidate_ids"] and row.get("status") == "completed")
        if row.get("heard_complete_answer") is not True or row.get("spoken_locations_match_tools") is not True or row.get("ui_locations_match_tools") is not True:
            factual_failures.append(row["id"])
        if row.get("native_audio_observed") is not True or row.get("real_laya_before_catalog") is not True:
            errors.append(row["id"])
    ids = [q["id"] for q in queries]
    audio = assess_series(timings["actionable_audio"], ids, 5000)
    cards = assess_series(timings["verified_card"], ids, 8000)
    complete_bindings = all(bound.values())
    return {"status": "pass" if complete_bindings and correct >= 27 and not factual_failures and not errors and audio["status"] == cards["status"] == "pass" else "fail",
            "trials": 30, "correct": correct, "factual_failures": factual_failures, "native_or_classification_failures": errors,
            "complete_expected_bindings": complete_bindings, "actionable_audio": audio, "verified_card": cards}


def assess_intent(rows, corpus, revision):
    require(len(rows) == 40 and {r["id"] for r in rows} == {q["id"] for q in corpus}, "intent denominator must be all 40 distinct cases")
    expected = {q["id"]: q["expected_intent"] for q in corpus}
    labels = sorted(set(expected.values()))
    confusion = {label: {actual: 0 for actual in labels+["abstention_or_error"]} for label in labels}
    correct, coverage, invalid, provenance_failures = 0, 0, [], []
    durations = []
    for row in rows:
        require(row["suite"] == "warm_normal", "intent cold/fault cases require separate reporting")
        if row.get("real_checkpoint_observed") is not True or row.get("adk_classify_intent_observed") is not True:
            provenance_failures.append(row["id"])
        actual = "abstention_or_error"
        if row.get("status") == "completed":
            try:
                intent_contract(row["result"], revision)
                if not row["result"]["abstained"]:
                    actual = row["result"]["intent"]
                    coverage += 1
            except (ValueError, KeyError, TypeError):
                invalid.append(row["id"])
        confusion[expected[row["id"]]][actual] += 1
        correct += int(actual == expected[row["id"]])
        if number(row.get("duration_ms")) and row["duration_ms"] >= 0:
            durations.append(row["duration_ms"])
    return {"status": "pass" if correct >= 36 and not invalid and not provenance_failures and len(durations) == 40 and max(durations) <= 1200 else "fail",
            "trials": 40, "correct": correct, "coverage": coverage/40, "confusion": confusion, "invalid_results": invalid,
            "provenance_failures": provenance_failures, "timing": distribution(durations), "per_class_accuracy": {label: confusion[label][label]/10 for label in labels}}
