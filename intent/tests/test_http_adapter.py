import asyncio
from pathlib import Path
import json
import time
import httpx
import pytest
from intent_service.app import create_app, Settings
from intent_service.worker import Engine
from tools.intent import Classifier, ENDPOINT
from fakes import TinyModel,success
from test_worker import ready

TOKEN = "task10-synthetic-private-token-only-12345"


@pytest.mark.asyncio
async def test_authenticated_service_fixed_body_unicode_and_no_browser_access():
    app=create_app(Settings(TOKEN,Path("synthetic-only")),engine_factory=lambda root:Engine(root,factory=TinyModel))
    async with app.router.lifespan_context(app):
        await ready(app.state.engine)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://127.0.0.1:8003") as client:
            assert (await client.get("/healthz")).status_code==200
            assert (await client.post("/classify",json={"text":"sample"})).status_code==401
            assert (await client.post("/classify",headers={"X-Internal-Token":"wrong"},json={"text":"sample"})).status_code==401
            headers={"X-Internal-Token":TOKEN,"Content-Type":"application/json"}
            bad=[b'{"text":"a","text":"b"}',b'{"text":"a","model":"foreign"}',b'{"text":"a","url":"https://example.test"}',b'{"text":null}',b'{"text":true}',b'{"text":""}',b'{"text":"a","schema":"foreign"}',b'x'*2049]
            for body in bad:
                response=await client.post("/classify",headers=headers,content=body)
                assert response.status_code==400 and TOKEN not in response.text and len(response.content)<100
            response=await client.post("/classify",headers=dict(headers,Origin="https://browser.example.test"),json={"text":"sample"})
            assert response.status_code==403
            assert (await client.post("/classify",headers={"X-Internal-Token":TOKEN},content='sample')).status_code==400
            response=await client.post("/classify",headers=headers,json={"text":"ก"*300})
            assert response.json()["intent"]=="find_item"
            assert "sample" not in response.text and TOKEN not in response.text
            assert (await client.get("/classify",headers=headers)).status_code==405
            assert (await client.get("/admin",headers=headers)).status_code==404
            adapter=Classifier(TOKEN,transport=httpx.ASGITransport(app=app))
            assert (await adapter("sample"))["intent"]=="find_item"
        assert app.state.engine.active is None and not app.state.engine.jobs
    assert app.state.engine.process is None


@pytest.mark.asyncio
@pytest.mark.parametrize("mode",["pin","extra","malformed","duplicate","redirect","oversize","bad_type","invalid_score","intent_array"])
async def test_adapter_rejects_untrusted_results_without_retry(mode):
    calls=[]
    def handle(request):
        calls.append(request)
        assert str(request.url)==ENDPOINT and set(json.loads(request.content))=={"text"}
        value=success()
        if mode=="pin": value["model_revision"]="f"*40
        if mode=="extra": value["product_id"]="untrusted"
        if mode=="invalid_score": value["confidence"]=float('nan')
        if mode=="intent_array": value["intent"]=[]
        if mode=="duplicate": return httpx.Response(200,headers={"Content-Type":"application/json"},content=b'{"intent":null,"intent":"find_item"}')
        if mode=="malformed": return httpx.Response(200,headers={"Content-Type":"application/json"},content=b'not-json')
        if mode=="oversize": return httpx.Response(200,headers={"Content-Type":"application/json"},content=b'x'*2049)
        if mode=="bad_type": return httpx.Response(200,headers={"Content-Type":"text/plain"},content=b'{}')
        if mode=="redirect": return httpx.Response(307,headers={"Location":"https://example.test"})
        return httpx.Response(200,content=json.dumps(value),headers={"Content-Type":"application/json"})
    value=await Classifier(TOKEN,transport=httpx.MockTransport(handle))("synthetic text")
    assert value["abstained"] and value["reason"]=="error" and len(calls)==1


@pytest.mark.asyncio
async def test_adapter_timeout_cancellation_and_bad_input():
    count=0
    async def stall(request):
        nonlocal count
        count+=1;await asyncio.sleep(3);return httpx.Response(200,json=success())
    adapter=Classifier(TOKEN,transport=httpx.MockTransport(stall))
    start=time.monotonic();value=await adapter("synthetic")
    assert value["reason"]=="timeout" and time.monotonic()-start<1.35 and count==1
    task=asyncio.create_task(adapter("synthetic"));await asyncio.sleep(.02);task.cancel()
    with pytest.raises(asyncio.CancelledError): await task
    for bad in [None,[],"", "x"*301]: assert (await adapter(bad))["reason"]=="error"
    assert count==2


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["disconnected_body", "slow_body"])
async def test_body_disconnect_and_deadline_never_enqueue_inference(mode):
    app = create_app(Settings(TOKEN, Path("synthetic-only")), engine_factory=lambda root: Engine(root, factory=TinyModel))
    async with app.router.lifespan_context(app):
        await ready(app.state.engine)
        messages = []
        scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "POST", "scheme": "http",
                 "path": "/classify", "raw_path": b"/classify", "query_string": b"", "root_path": "",
                 "headers": [(b"content-type", b"application/json"), (b"x-internal-token", TOKEN.encode())]}
        received = 0
        async def receive():
            nonlocal received
            received += 1
            if received == 1:
                return {"type": "http.request", "body": b'{"text":"synthetic', "more_body": True}
            if mode == "slow_body": await asyncio.sleep(3)
            return {"type": "http.disconnect"}
        async def send(message): messages.append(message)
        started = time.monotonic()
        await app(scope, receive, send)
        value = json.loads(next(m["body"] for m in messages if m["type"] == "http.response.body"))
        assert value["reason"] == ("error" if mode == "disconnected_body" else "timeout")
        assert value["abstained"] and value["confidence"] is None
        assert time.monotonic()-started < 1.35
        assert app.state.engine.active is None and not app.state.engine.jobs
