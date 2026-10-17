import asyncio
import json

import httpx
import pytest

from prompt_shop_live.host import ToolHost
from prompt_shop_live.tools import ShopperTool
from test_runtime import classifier, setup, until


@pytest.mark.parametrize("kind", ["unique", "ambiguous", "empty", "search-error", "route-error"])
async def test_find_product_uses_one_classification_and_only_routes_unique_match(kind):
    calls, classifications, inputs = [], [], []

    async def classify_request(text):
        inputs.append(text)
        return await classifier(text)

    async def send(event):
        classifications.append(event)
        host.acknowledge(event)

    async def transport(request):
        calls.append((request.url.path.rsplit("/", 1)[-1], json.loads(request.content)))
        if calls[-1][0] == "search_catalog":
            if kind == "search-error":
                return httpx.Response(503)
            return httpx.Response(200, json={"search_id": "server-id", "candidates":
                [] if kind == "empty" else [{"id": "milk"}, {"id": "oat"}] if kind == "ambiguous" else [{"id": "milk"}],
                "ambiguous": kind == "ambiguous"})
        return httpx.Response(503 if kind == "route-error" else 200, json={"product": {"id": "milk"}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        host = ToolHost(setup(), send, classify_request, client)
        host.begin("turn-1")
        tool = ShopperTool("find_product", host)
        result = await tool.run_async(args={"query": "milk", "text": "Where is milk?"}, tool_context=None)
        assert len([e for e in classifications if e["type"] == "classification_completed"]) == 1
        assert inputs == ["Where is milk?"]
        assert classifications[0]["response_mode"] == "catalog"
        assert [c[0] for c in calls] == (["search_catalog", "get_product_route"] if kind in {"unique", "route-error"} else ["search_catalog"])
        assert host.audio_allowed
        if kind in {"search-error", "route-error"}:
            assert classifications[-1]["type"] == "response_ready"
        if kind in {"unique", "route-error"}:
            assert calls[-1][1]["args"] == {"product_id": "milk", "search_id": "server-id"}
            assert "route" in result
        for _, envelope in calls:
            assert envelope["classification_attempt_id"] == classifications[0]["classification_attempt_id"]
        # No second model flow can switch response mode or repeat callbacks.
        assert (await ShopperTool("begin_conversation", host).run_async(args={"text": "hello"}, tool_context=None))["error"]["code"] == "RATE_LIMITED"
        assert len([e for e in classifications if e["type"] == "classification_completed"]) == 1
        await host.close()


@pytest.mark.parametrize("args", [None, {"query": "milk"},
    {"text": "milk", "query": "x" * 201},
    {"text": "x" * 301, "query": "milk"},
    {"text": "milk", "query": "milk", "url": "https://example.com"}])
async def test_invalid_combined_lookup_rejected_before_host_access(args):
    result = await ShopperTool("find_product", object()).run_async(args=args, tool_context=None)
    assert result["error"]["code"] == "INVALID_REQUEST"


async def test_pending_ambiguous_selection_classifies_without_researching():
    calls = []
    async def send(event):
        host.acknowledge(event)
    async def transport(request):
        calls.append((request.url.path, json.loads(request.content)["args"]))
        return httpx.Response(200, json={"product": {"id": "oat"}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        host = ToolHost(setup(), send, classifier, client)
        host.begin("turn-1")
        result = await ShopperTool("select_product", host).run_async(args={
            "text": "The oat one", "product_id": "oat", "search_id": "pending-server-id"}, tool_context=None)
        assert result["product"]["id"] == "oat" and host.audio_allowed
        assert calls == [("/internal/tools/get_product_route", {"product_id": "oat", "search_id": "pending-server-id"})]
        await host.close()


async def test_barge_in_during_combined_search_cannot_route_under_new_turn():
    calls, pending = [], asyncio.Event()
    async def send(event):
        host.acknowledge(event)
    async def transport(request):
        calls.append(request.url.path)
        pending.set()
        await asyncio.Event().wait()
    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        host = ToolHost(setup(), send, classifier, client)
        host.begin("turn-1")
        task = asyncio.create_task(ShopperTool("find_product", host).run_async(args={"query": "milk", "text": "Where is milk?"}, tool_context=None))
        await asyncio.wait_for(pending.wait(), 1)
        host.begin("turn-2")
        result = await asyncio.wait_for(task, 1)
        assert result["error"]["code"] == "STALE_SELECTION"
        assert calls == ["/internal/tools/search_catalog"]
        assert not host.audio_allowed and not host.classified and not host.flows
        assert (await ShopperTool("begin_conversation", host).run_async(args={"text": "Hello"}, tool_context=None))["acknowledged"] is True
        assert host.audio_allowed
        await host.close()


async def test_conversation_waits_for_classification_ack_before_unlocking_audio():
    sent = []
    async def send(event):
        sent.append(event)
    async with httpx.AsyncClient() as client:
        host = ToolHost(setup(), send, classifier, client)
        host.begin("turn-1")
        task = asyncio.create_task(ShopperTool("begin_conversation", host).run_async(args={"text": "Hello"}, tool_context=None))
        await until(lambda: bool(sent))
        assert not task.done() and not host.audio_allowed
        host.acknowledge(sent[0])
        assert (await task)["acknowledged"] is True
        assert host.audio_allowed and host.counts == {"classify_intent": 1}
        await host.close()


@pytest.mark.parametrize("entries", [[], [{"query":"milk","status":"confirmed","catalog_version":1,"products":[{"id":"milk"}]}]])
async def test_summary_classifies_then_reads_only_current_server_facts(entries):
    calls, classifications = [], []
    async def send(event):
        classifications.append(event)
        host.acknowledge(event)
    async def transport(request):
        calls.append((request.url.path, json.loads(request.content)))
        return httpx.Response(200, json={"entries":entries,"truncated":False})
    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        host=ToolHost(setup(),send,classifier,client);host.begin("turn-1")
        result=await ShopperTool("summarize_items",host).run_async(args={"text":"Yes, summarize my items"},tool_context=None)
        assert result=={"entries":entries,"truncated":False} and host.audio_allowed
        assert len(classifications)==1 and classifications[0]["response_mode"]=="catalog"
        assert len(calls)==1 and calls[0][0]=="/internal/tools/get_conversation_summary" and calls[0][1]["args"]=={}
        assert calls[0][1]["classification_attempt_id"]==classifications[0]["classification_attempt_id"]
        await host.close()

async def test_summary_rejects_model_supplied_products_before_host_access():
    result=await ShopperTool("summarize_items",object()).run_async(args={"text":"recap","products":[{"id":"fake"}]},tool_context=None)
    assert result["error"]["code"]=="INVALID_REQUEST"
