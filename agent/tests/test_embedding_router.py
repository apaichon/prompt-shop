import json
from pathlib import Path

import httpx
import pytest

from prompt_shop_live.host import ToolHost, validate_classification
from prompt_shop_live.tools import ShopperTool
from test_runtime import setup
from tools.embedding_router import (
    DIMENSIONS, ENDPOINT, PREFIX, EmbeddingRouter, GeminiEmbedder, PROTOTYPE_PATH,
    check_text, classify_text, cosine, decide, embed_texts, eligible_labels, load_prototypes,
)
from tools.intent import MODEL_REVISION, classify_intent, result
from tools.router_state import router_state

ROOT = Path(__file__).parents[1]
REVISION = "gemini-embedding-2@768:0123456789abcdef"
AXES = [
    {"id": "find", "label": "find_item", "text": "where is milk"},
    {"id": "select", "label": "select_item", "text": "the second one"},
    {"id": "repeat", "label": "repeat_directions", "text": "say the route again"},
    {"id": "summary", "label": "summarize", "text": "summarize my items"},
    {"id": "scope", "label": "out_of_scope", "text": "book a hotel"},
]
VECTORS = [
    [1, 0, 0, 0, 0],
    [0, 1, 0, 0, 0],
    [0, 0, 1, 0, 0],
    [0, 0, 0, 1, 0],
    [0, 0, 0, 0, 1],
]


def scored(query, state=None):
    return decide(query, AXES, VECTORS, eligible_labels(state), REVISION)


async def embedder(texts):
    return [VECTORS[0] for _ in texts]


def embedding_result(intent, *, abstained=False):
    if abstained:
        return {"schema_version": "intent-v1", "intent": None, "confidence": .4, "margin": .05,
                "abstained": True, "reason": "low_confidence", "model_revision": REVISION}
    return {"schema_version": "intent-v1", "intent": intent, "confidence": .91, "margin": .4,
            "abstained": False, "reason": None, "model_revision": REVISION}


def classifier_for(intent, *, abstained=False):
    async def classify(text):
        assert check_text(text)
        return embedding_result(intent, abstained=abstained)
    return classify


async def host_for(intent, transport, *, abstained=False, session_results=None, session_route=None):
    events = []

    async def send(event):
        events.append(event)
        host.acknowledge(event)

    client = httpx.AsyncClient(transport=httpx.MockTransport(transport))
    host = ToolHost(setup(), send, classifier_for(intent, abstained=abstained), client)
    host.session_results = session_results
    host.session_route = session_route
    host.begin("turn-1")
    return host, client, events


def test_cosine_and_thresholds():
    assert cosine([1, 0], [1, 0]) == 1
    assert cosine([1, 0], [0, 1]) == 0
    found = scored([1, 0, 0, 0, 0])
    assert found["intent"] == "find_item" and found["abstained"] is False and found["reason"] is None
    for label,index in (("find_item",0),("summarize",3)):
        q=[0,0,0,0,0];q[index]=.90;q[4]=.70
        accepted=scored(q)
        assert accepted["intent"]==label and not accepted["abstained"]
        validate_classification(accepted)
    close = scored([.9, 0, 0, .86, 0])
    assert close["abstained"] is True and close["reason"] == "low_confidence"
    with pytest.raises(ValueError):
        validate_classification(dict(embedding_result("summarize"), margin=.01))
    weak = scored([1, 1, 1, 1, 1])
    assert weak["abstained"] is True and weak["confidence"] < 0.70 and weak["margin"] is not None


def test_session_state_removes_select_and_repeat_before_similarity():
    selection = [0.2, 0.9, 0, 0, 0]
    blocked = scored(selection, {})
    assert blocked["abstained"] is True and blocked["intent"] is None
    chosen = scored(selection, {"has_results": True})
    assert chosen["intent"] == "select_item" and chosen["abstained"] is False
    repeat = scored([0, 0, 1, 0, 0], {"has_route": False})
    assert repeat["abstained"] is True
    assert scored([0, 0, 1, 0, 0], {"has_route": True})["intent"] == "repeat_directions"
    assert "select_item" not in eligible_labels({})
    assert "repeat_directions" not in eligible_labels({})
    assert eligible_labels({"has_results": True, "has_route": True}) == set(AXES[i]["label"] for i in range(5))


def test_prototypes_and_eval_set_are_frozen_and_disjoint():
    prototypes, revision = load_prototypes()
    assert revision.startswith("gemini-embedding-2@768:")
    raw = PROTOTYPE_PATH.read_text().lower()
    eval_path = ROOT / "tools" / "prototypes" / "embedding-eval-v1.json"
    document = json.loads(eval_path.read_text())
    assert document["model"] == "gemini-embedding-2" and document["dimensions"] == DIMENSIONS
    cases = document["cases"]
    assert len(cases) == 40
    counts = {}
    prototype_text = {item["text"] for item in prototypes}
    seen = set()
    for case in cases:
        assert case["text"] not in prototype_text
        assert case["id"] not in seen
        seen.add(case["id"])
        counts[case["expected_intent"]] = counts.get(case["expected_intent"], 0) + 1
    assert counts == {label: 8 for label in ("find_item", "select_item", "repeat_directions", "summarize", "out_of_scope")}
    blob = (raw + eval_path.read_text().lower())
    assert "aisle" not in blob and "shelf" not in blob


def test_laya_checker_still_rejects_the_embedding_revision_and_summarize():
    base = {"schema_version": "intent-v1", "intent": "find_item", "confidence": .9, "margin": .4,
            "abstained": False, "reason": None, "model_revision": MODEL_REVISION}
    assert result(dict(base))["intent"] == "find_item"
    with pytest.raises(ValueError):
        result(dict(base, intent="summarize"))
    with pytest.raises(ValueError):
        result(dict(base, model_revision=REVISION))


async def test_router_caches_prototypes_and_does_not_log_text(caplog):
    calls = []

    class Fake:
        tokens = None

        async def __call__(self, texts):
            calls.append(list(texts))
            self.tokens = 11
            if len(texts) == len(AXES):
                return VECTORS
            return [[1, 0, 0, 0, 0]]

    router = EmbeddingRouter(AXES, Fake(), REVISION)
    sentence = "Where is whole milk?"
    with caplog.at_level("INFO"):
        first = await router.classify(sentence, {})
        second = await router.classify(sentence, {})
    assert first["intent"] == second["intent"] == "find_item"
    assert set(first) == {"schema_version", "intent", "confidence", "margin", "abstained", "reason", "model_revision"}
    assert len(calls) == 3
    assert all(text.startswith(PREFIX) for batch in calls for text in batch)
    assert sentence not in caplog.text
    assert "tokens=11" in caplog.text
    assert (await router.classify("   ", {}))["reason"] == "error"
    assert (await router.classify("\0milk", {}))["reason"] == "error"


async def test_embed_request_uses_prefix_dimensions_and_header_key():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["header"] = request.headers["x-goog-api-key"]
        seen["body"] = json.loads(request.content)
        values = [0.01] * DIMENSIONS
        return httpx.Response(200, json={"embeddings": [{"values": values}], "usageMetadata": {"totalTokenCount": 9}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        vectors, tokens = await embed_texts(
            [PREFIX + "Where is milk?"], api_key="synthetic-key", client=client)
    assert tokens == 9 and len(vectors[0]) == DIMENSIONS
    assert seen["url"] == ENDPOINT and "synthetic-key" not in seen["url"]
    assert seen["header"] == "synthetic-key"
    encoded = json.dumps(seen["body"])
    assert "task_type" not in encoded
    assert seen["body"]["requests"][0]["outputDimensionality"] == DIMENSIONS
    assert seen["body"]["requests"][0]["model"] == "models/gemini-embedding-2"
    embedder = GeminiEmbedder("synthetic-key", client=None)
    assert embedder.tokens is None


async def test_default_backend_stays_on_laya_until_the_flag(monkeypatch):
    monkeypatch.delenv("INTENT_BACKEND", raising=False)
    monkeypatch.setenv("LAYA_INTERNAL_TOKEN", "")
    laya = await classify_intent("Where is milk?")
    assert laya["model_revision"] == MODEL_REVISION and laya["abstained"] is True

    async def fake_embed(texts):
        return [VECTORS[0]]

    router = EmbeddingRouter(AXES, fake_embed, REVISION, VECTORS)
    monkeypatch.setenv("INTENT_BACKEND", "embedding")
    monkeypatch.setattr("tools.embedding_router.default_router", lambda: router)
    embedded = await classify_text("Where is milk?")
    assert embedded["intent"] == "find_item" and embedded["model_revision"] == REVISION
    routed = await classify_intent("Where is milk?")
    assert routed["model_revision"] == REVISION


async def test_out_of_scope_and_abstain_call_no_catalog_route_or_summary():
    calls = []

    async def transport(request):
        calls.append(request.url.path)
        return httpx.Response(200, json={"entries": [], "truncated": False})

    for intent, abstained in (("out_of_scope", False), ("find_item", True)):
        calls.clear()
        host, client, events = await host_for(intent, transport, abstained=abstained)
        try:
            result = await ShopperTool("find_product", host).run_async(
                args={"query": "milk", "text": "Book me a hotel."}, tool_context=None)
            assert result["acknowledged"] is True and host.audio_allowed
            assert events[0]["response_mode"] == "conversation"
            assert calls == []
            summary = await ShopperTool("summarize_items", host).run_async(
                args={"text": "Book me a hotel."}, tool_context=None)
            assert summary["error"]["code"] == "RATE_LIMITED"
            assert calls == []
        finally:
            await host.close()
            await client.aclose()


async def test_label_dispatches_find_select_repeat_and_summary():
    calls = []

    async def transport(request):
        name = request.url.path.rsplit("/", 1)[-1]
        body = json.loads(request.content)
        calls.append((name, body["args"]))
        if name == "search_catalog":
            return httpx.Response(200, json={"search_id": "search-1", "candidates": [{"id": "milk"}], "ambiguous": False})
        if name == "get_conversation_summary":
            return httpx.Response(200, json={"entries": [], "truncated": False})
        return httpx.Response(200, json={"product": {"id": body["args"]["product_id"]}})

    host, client, events = await host_for("find_item", transport)
    try:
        found = await ShopperTool("begin_conversation", host).run_async(args={"text": "Where is milk?"}, tool_context=None)
        assert events[0]["response_mode"] == "catalog"
        assert [name for name, _ in calls] == ["search_catalog", "get_product_route"]
        assert calls[1][1] == {"product_id": "milk", "search_id": "search-1"}
        assert "route" in found and host.session_route["product_id"] == "milk"
    finally:
        await host.close()
        await client.aclose()

    calls.clear()
    host, client, _events = await host_for(
        "select_item", transport, session_results={"search_id": "pending", "ids": ["oat"]})
    try:
        missed = await ShopperTool("find_product", host).run_async(
            args={"query": "oat", "text": "The second one."}, tool_context=None)
        assert missed["acknowledged"] is True and calls == []
        host.flows.clear()
        host.counts.clear()
        # The turn already classified. A second flow is rate limited, so use the host directly.
        refused = await host.call("search_catalog", {"query": "oat"})
        assert refused["error"]["code"] == "TOOL_NOT_ALLOWED" and calls == []
        routed = await host.call("get_product_route", {"product_id": "oat", "search_id": "pending"})
        assert routed["product"]["id"] == "oat"
        assert calls == [("get_product_route", {"product_id": "oat", "search_id": "pending"})]
    finally:
        await host.close()
        await client.aclose()

    calls.clear()
    host, client, _events = await host_for(
        "repeat_directions", transport, session_route={"product_id": "milk", "search_id": "search-1"})
    try:
        repeated = await ShopperTool("find_product", host).run_async(
            args={"query": "milk", "text": "Say the route again."}, tool_context=None)
        assert repeated["product"]["id"] == "milk"
        assert calls == [("get_product_route", {"product_id": "milk", "search_id": "search-1"})]
    finally:
        await host.close()
        await client.aclose()

    calls.clear()
    host, client, _events = await host_for("summarize", transport)
    try:
        summary = await ShopperTool("find_product", host).run_async(
            args={"query": "milk", "text": "Summarize my items."}, tool_context=None)
        assert summary == {"entries": [], "truncated": False}
        assert calls == [("get_conversation_summary", {})]
    finally:
        await host.close()
        await client.aclose()


async def test_host_passes_session_flags_and_keeps_them_across_turns():
    seen = {}

    async def classify(text):
        seen["state"] = router_state.get()
        return embedding_result("find_item")

    async def transport(request):
        return httpx.Response(200, json={"search_id": "search-9", "candidates": [{"id": "milk"}, {"id": "oat"}], "ambiguous": True})

    async def send(event):
        host.acknowledge(event)

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        host = ToolHost(setup(), send, classify, client)
        host.session_results = {"search_id": "old", "ids": ["milk"]}
        host.session_route = {"product_id": "milk", "search_id": "old"}
        host.begin("turn-1")
        assert host.label_gate is False and host.session_results["search_id"] == "old"
        await ShopperTool("find_product", host).run_async(args={"query": "milk", "text": "Where is milk?"}, tool_context=None)
        assert seen["state"] == {"has_results": True, "has_route": True}
        assert host.session_results["ids"] == ["milk", "oat"]
        host.begin("turn-2")
        assert host.session_results["ids"] == ["milk", "oat"]
        assert host.session_route is None
        assert host.label_gate is False and host.turn_results is None
        await host.close()


async def test_empty_search_clears_previous_selection_and_route():
    host, client, events = await host_for("find_item", lambda request: httpx.Response(200, json={
        "search_id": "empty", "candidates": [], "ambiguous": False}),
        session_results={"search_id": "old", "ids": ["milk"]},
        session_route={"product_id": "milk", "search_id": "old"})
    try:
        await ShopperTool("find_product", host).run_async(args={"text":"Find a missing item", "query":"missing"},tool_context=None)
        assert host.session_results == {"search_id":"empty", "ids":[]}
        assert host.session_route is None
    finally:
        await host.close(); await client.aclose()


async def test_missing_selection_ids_release_clarification_on_private_bridge():
    host, client, events = await host_for("select_item", lambda request: pytest.fail("must not call catalog"),
        session_results={"search_id":"current", "ids":["milk"]})
    try:
        result = await ShopperTool("find_product",host).run_async(args={"text":"The blue one", "query":"milk"},tool_context=None)
        assert "choose" in result["next_action"]
        assert events[-1]["type"] == "response_ready"
        assert events[-1]["classification_attempt_id"] == events[0]["classification_attempt_id"]
        assert host.audio_allowed
        host.begin("turn-2")
        await host.allow_response("turn-1")
        assert not host.audio_allowed and len(events)==2
    finally:
        await host.close(); await client.aclose()


def test_strong_find_overlap_searches_catalog_but_does_not_relax_selection():
    prototypes=[{"label":"find_item"},{"label":"select_item"}]
    result=decide([1,0],prototypes,[[.82,.57],[.80,.60]],{"find_item","select_item"},REVISION)
    assert result["intent"]=="find_item" and result["margin"]<.05
    validate_classification(result)
    result=decide([1,0],prototypes,[[.80,.60],[.82,.57]],{"find_item","select_item"},REVISION)
    assert result["abstained"]
