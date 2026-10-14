"""Fixed intent-v1 validation shared by the private service and isolated tests."""
import math

LABELS = ("find_item", "select_item", "repeat_directions", "out_of_scope")
MODEL_REVISION = "7b928d828b7b0e022f929d9bd2e44165aa270148"
FIELDS = {"schema_version", "intent", "confidence", "margin", "abstained", "reason", "model_revision"}
CONFIDENCE_MIN, MARGIN_MIN = .70, .15


def valid_text(text):
    if not isinstance(text, str) or not 1 <= len(text) <= 300 or not text.strip() or "\0" in text:
        raise ValueError("invalid text")
    return text


def abstain(reason, confidence=None, margin=None):
    if reason not in ("low_confidence", "timeout", "busy", "error"):
        raise ValueError("invalid reason")
    return {"schema_version": "intent-v1", "intent": None, "confidence": confidence,
            "margin": margin, "abstained": True, "reason": reason, "model_revision": MODEL_REVISION}


def validate(value):
    if not isinstance(value, dict) or set(value) != FIELDS or value["schema_version"] != "intent-v1" or value["model_revision"] != MODEL_REVISION:
        raise ValueError("classification identity differs")
    if type(value["abstained"]) is not bool:
        raise ValueError("boolean abstention required")
    for key in ("confidence", "margin"):
        score = value[key]
        if score is not None and (type(score) not in (float, int) or not math.isfinite(score) or not 0 <= score <= 1):
            raise ValueError("invalid score")
    if value["confidence"] is not None and value["margin"] is not None and value["margin"] > value["confidence"]:
        raise ValueError("margin exceeds confidence")
    if value["abstained"]:
        if value["intent"] is not None or value["reason"] not in ("low_confidence", "timeout", "busy", "error"):
            raise ValueError("inconsistent abstention")
        if value["reason"] == "low_confidence":
            if value["confidence"] is None or value["margin"] is None or (value["confidence"] >= CONFIDENCE_MIN and value["margin"] >= MARGIN_MIN):
                raise ValueError("inconsistent low confidence")
        elif value["confidence"] is not None or value["margin"] is not None:
            raise ValueError("failed inference cannot report scores")
    elif value["intent"] not in LABELS or value["reason"] is not None or value["confidence"] is None or value["margin"] is None or value["confidence"] < CONFIDENCE_MIN or value["margin"] < MARGIN_MIN:
        raise ValueError("inconsistent successful classification")
    return value


def decision(raw):
    answer = raw["answers"]["intent"]
    probabilities = answer["probabilities"]
    if answer.get("type") != "choice" or not isinstance(probabilities, dict) or set(probabilities) != set(LABELS):
        raise ValueError("invalid model answer")
    values = list(probabilities.values())
    if any(type(x) not in (float, int) or not math.isfinite(x) or not 0 <= x <= 1 for x in values) or abs(sum(values)-1) > .001:
        raise ValueError("invalid probability vector")
    winner = max(probabilities, key=probabilities.get)
    if answer.get("choice") != winner:
        raise ValueError("inconsistent winner")
    scores = sorted(values, reverse=True)
    confidence, margin = scores[0], scores[0]-scores[1]
    if confidence < CONFIDENCE_MIN or margin < MARGIN_MIN:
        return validate(abstain("low_confidence", confidence, margin))
    return validate({"schema_version": "intent-v1", "intent": winner, "confidence": confidence,
                     "margin": margin, "abstained": False, "reason": None, "model_revision": MODEL_REVISION})
