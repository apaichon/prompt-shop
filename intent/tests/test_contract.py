import copy
import json
from pathlib import Path
import math
import pytest
from intent_service.protocol import MODEL_REVISION, LABELS, decision, validate, valid_text, abstain
from intent_service.model import verify_bundle
from tools.intent import result as adapter_result
from fakes import success


@pytest.mark.parametrize("text", ["", " ", None, True, [], "x"*301, "x\0y"])
def test_bad_text_rejected(text):
    with pytest.raises(ValueError): valid_text(text)


def test_unicode_character_bound():
    assert valid_text("ก"*300)=="ก"*300


def test_probability_confidence_and_margin_are_explicit():
    raw={"answers":{"intent":{"type":"choice","choice":"find_item","confidence":.99,"probabilities":dict(zip(LABELS,[.69,.2,.06,.05]))}}}
    result=decision(raw)
    assert result["abstained"] and result["reason"]=="low_confidence" and result["confidence"]==.69
    raw["answers"]["intent"]["probabilities"]=dict(zip(LABELS,[.7,.15,.1,.05]))
    result=decision(raw)
    assert result["intent"]=="find_item" and result["confidence"]==.7 and abs(result["margin"]-.55)<1e-12


@pytest.mark.parametrize("change", ["unknown_label","boolean","nan","sum","wrong_winner"])
def test_malformed_model_probability_vector_rejected(change):
    raw={"answers":{"intent":{"type":"choice","choice":"find_item","probabilities":dict(zip(LABELS,[.8,.1,.05,.05]))}}}
    p=raw["answers"]["intent"]["probabilities"]
    if change=="unknown_label": p["admin_write"]=p.pop("out_of_scope")
    if change=="boolean": p["find_item"]=True
    if change=="nan": p["find_item"]=math.nan
    if change=="sum": p["find_item"]=.99
    if change=="wrong_winner": raw["answers"]["intent"]["choice"]="select_item"
    with pytest.raises(ValueError): decision(raw)


@pytest.mark.parametrize("change", ["extra","foreign_pin","low_margin","abstained_success","reason","boolean_score","intent_array","impossible_margin"])
def test_service_and_adapter_strict_response_agree(change):
    value=success()
    if change=="extra": value["product_id"]="synthetic"
    if change=="foreign_pin": value["model_revision"]="b"*40
    if change=="low_margin": value["margin"]=.1
    if change=="abstained_success": value["abstained"]=True
    if change=="reason": value["reason"]="payment_allowed"
    if change=="boolean_score": value["confidence"]=True
    if change=="intent_array": value["intent"]=[]
    if change=="impossible_margin": value["confidence"]=.7;value["margin"]=.8
    for check in (validate,adapter_result):
        with pytest.raises(ValueError): check(value)


def test_failures_report_no_intent_or_scores():
    for reason in ["error","busy","timeout"]:
        value=abstain(reason); assert adapter_result(value)==value
        value["confidence"]=.8
        with pytest.raises(ValueError): validate(value)


def test_frozen_corpus_thresholds_and_pin():
    root=Path(__file__).resolve().parents[1]
    corpus=(root/"evaluation/corpus.json").read_bytes()
    assert corpus==(root.parent/"tests/fixtures/intent-queries.json").read_bytes()
    values=json.loads(corpus); assert len(values)==40 and all(sum(x["expected_intent"]==label for x in values)==10 for label in LABELS)
    config=json.loads((root/"config/intent-v1.json").read_text()); assert (config["confidence_min"],config["margin_min"])==(.70,.15)
    assert set(config["questions"]["intent"]["criteria"])==set(LABELS)
    assert json.loads((root/"model/manifest.json").read_text())["revision"]==MODEL_REVISION


def test_changed_model_bundle_rejected_before_native_loading(tmp_path):
    root=Path(__file__).resolve().parents[1]
    value=json.loads((root/"model/manifest.json").read_text());value["revision"]="f"*40
    (tmp_path/"manifest.json").write_text(json.dumps(value))
    with pytest.raises(ValueError): verify_bundle(tmp_path)
