import asyncio
import base64
import contextlib
import json
import time
from pathlib import Path
import jsonschema

import httpx
import pytest
from google.genai import live, types

from prompt_shop_live.host import ToolHost
from prompt_shop_live.protocol import APP, Setup
from prompt_shop_live.queue import BoundedLiveRequestQueue, QueueOverflow
from prompt_shop_live.runtime import Runtime
from prompt_shop_live.tools import BlockingTool


def setup(sid="session-a"):
    return Setup(type="setup", session_id=sid, language="en-US", turn_id="turn-0", tool_capability="x" * 43)


async def classifier(text):
    return {"schema_version": "intent-v1", "intent": "find_item", "confidence": .9,
            "margin": .5, "abstained": False, "reason": None, "model_revision": "contract-fixture"}


async def test_queue_counts_actual_dequeues_and_closes_full_queue():
    queue = BoundedLiveRequestQueue()
    for _ in range(10):
        queue.send_realtime(types.Blob(data=b"\0" * 3200, mime_type="audio/pcm;rate=16000"))
    with pytest.raises(QueueOverflow):
        queue.send_realtime(types.Blob(data=b"00", mime_type="audio/pcm;rate=16000"))
    assert queue.pending_pcm == 32000
    await queue.get()
    assert queue.pending_pcm == 28800
    queue.close()
    assert queue.pending_pcm == 0 and (await queue.get()).close
    with pytest.raises(RuntimeError):
        queue.send_content(types.Content(parts=[types.Part(text="late")]))


async def test_ack_must_match_before_catalog_dispatch_and_stale_calls_cancel():
    sent, requests = [], []
    async def send(event):
        sent.append(event)
    async def transport(request):
        requests.append(request)
        return httpx.Response(200, json={"candidates": [], "ambiguous": False})
    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        host = ToolHost(setup(), send, classifier, client)
        host.begin("turn-1")
        assert "error" in await host.call("search_catalog", {"query": "milk"})
        task = asyncio.create_task(host.call("classify_intent", {"text": "milk"}))
        await asyncio.sleep(.01)
        event = sent[-1]
        host.acknowledge({**event, "session_id": "wrong"})
        assert not task.done()
        host.acknowledge(event)
        assert (await task)["intent"] == "find_item"
        await host.call("search_catalog", {"query": "milk"})
        assert len(requests) == 1
        envelope = json.loads(requests[0].content)
        assert envelope["classification_attempt_id"] == event["classification_attempt_id"]
        assert requests[0].url.host == "127.0.0.1"
        host.begin("turn-2")
        task = asyncio.create_task(host.call("classify_intent", {"text": "oats"}))
        await asyncio.sleep(.01)
        host.begin("turn-3")
        assert (await task)["error"]["code"] == "STALE_SELECTION"
        assert not host.tasks
        await host.close()


async def test_extra_tool_arguments_rejected():
    class Host:
        async def call(self, *_):
            pytest.fail("invalid args reached host")
    result = await BlockingTool("search_catalog", Host()).run_async(args={"query": "milk", "url": "https://evil"}, tool_context=None)
    assert result["error"]["code"] == "INVALID_REQUEST"


@pytest.mark.parametrize("mode", ["conversation", "catalog"])
@pytest.mark.parametrize("reason", ["low_confidence", "timeout"])
async def test_conversation_can_reply_after_real_abstention_state_and_ack(mode, reason):
    sent = []
    async def abstaining(text):
        return {"schema_version": "intent-v1", "intent": None, "confidence": .4 if reason == "low_confidence" else None,
                "margin": .07 if reason == "low_confidence" else None, "abstained": True,
                "reason": reason, "model_revision": "contract-fixture"}
    async def send(event):
        sent.append(event)
    async def transport(request):
        return httpx.Response(200, json={"candidates": [{"id": "milk"}], "ambiguous": False})
    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        host = ToolHost(setup(), send, abstaining, client)
        host.begin("turn-1")
        task = asyncio.create_task(BlockingTool("classify_intent", host).run_async(
            args={"text": "Hello", "response_mode": mode}, tool_context=None))
        await until(lambda: bool(sent))
        assert not host.audio_allowed and not task.done()
        assert sent[-1]["response_mode"] == mode and sent[-1]["result"]["abstained"]
        host.acknowledge(sent[-1])
        result = await task
        assert result["intent"] is None and result["reason"] == reason
        assert host.audio_allowed == (mode == "conversation")
        # Entering catalog lookup always restores grounding, even after chat.
        await host.call("search_catalog", {"query": "milk"})
        assert not host.audio_allowed
        host.begin("turn-2")
        assert not host.audio_allowed and not host.classified
        await host.close()


@pytest.mark.parametrize("mode", ["other", "", None, [], {}])
async def test_invalid_response_mode_never_reaches_classifier(mode):
    class Host:
        async def call(self, *_):
            pytest.fail("invalid mode reached host")
    result = await BlockingTool("classify_intent", Host()).run_async(
        args={"text": "Hello", "response_mode": mode}, tool_context=None)
    assert result["error"]["code"] == "INVALID_REQUEST"


class Bridge:
    def __init__(self, sid):
        self.sid = sid
        self.incoming = asyncio.Queue()
        self.output = []
        self.ready = asyncio.Event()
        self.closed = False
        self.audio_times = []

    async def receive(self):
        return await self.incoming.get()

    async def send_json(self, event):
        self.output.append(event)
        if event["type"] == "provider_ready":
            self.ready.set()
        if event["type"] == "classification_completed":
            self.control("classification_registered", turn_id=event["turn_id"], classification_attempt_id=event["classification_attempt_id"])

    async def send_bytes(self, value):
        self.output.append(value)
        self.audio_times.append((time.monotonic(), len(value)))

    async def close(self, **_):
        self.closed = True

    def control(self, kind, **fields):
        self.incoming.put_nowait({"type": "websocket.receive", "text": json.dumps({"type": kind, "session_id": self.sid, **fields})})


class ProviderSocket:
    """Fake network only: actual Runner, Gemini adapter and SDK serialization run."""
    def __init__(self):
        self.received = asyncio.Queue()
        self.sent = []
        self.closed = False

    async def send(self, raw):
        event = json.loads(raw)
        self.sent.append(event)
        if "setup" in event:
            self.push({"setupComplete": {"sessionId": "provider-fixture"}})

    async def recv(self, **_):
        return await self.received.get()

    def push(self, event):
        self.received.put_nowait(json.dumps(event).encode())

    async def close(self):
        self.closed = True


async def until(predicate):
    async with asyncio.timeout(5):
        while not predicate():
            await asyncio.sleep(.01)


@pytest.mark.parametrize("selected_model,selected_voice", [
    (None, None),
    ("gemini-3.9-live-fixture", "Aoede"),
    ("models/gemini-3.8-live-preview-fixture", "Kore"),
])
async def test_actual_runner_sdk_wire_config_multipart_and_cleanup(monkeypatch, selected_model, selected_voice):
    monkeypatch.setenv("GOOGLE_API_KEY", "fixture-key-never-sent")
    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "FALSE")
    for name, value in (("GEMINI_MODEL", selected_model), ("GEMINI_VOICE", selected_voice)):
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)
    sockets = []
    @contextlib.asynccontextmanager
    async def connect(*args, **kwargs):
        assert kwargs["max_queue"] == 1 and kwargs["max_size"] == 65536
        socket = ProviderSocket()
        sockets.append(socket)
        try:
            yield socket
        finally:
            socket.closed = True
    monkeypatch.setattr(live, "ws_connect", connect)
    # Two concurrent real ADK runners must have isolated queue/session lifetimes.
    async def tools(request):
        call = json.loads(request.content)
        if request.url.path.endswith("search_catalog"):
            return httpx.Response(200, json={"search_id": "search-fixture", "candidates": [{"id": "milk"}], "ambiguous": False})
        return httpx.Response(200, json={"product": {"id": "milk"}, "steps": ["Aisle 2, Shelf 3"]})
    def clients(**kwargs):
        return httpx.AsyncClient(transport=httpx.MockTransport(tools), **kwargs)
    runtime = Runtime(classifier, client_factory=clients)
    # An environment change cannot mix settings within the running process.
    monkeypatch.setenv("GEMINI_MODEL", "gemini-changed-after-startup")
    monkeypatch.setenv("GEMINI_VOICE", "Puck")
    a, b = Bridge("session-a"), Bridge("session-b")
    tasks = [asyncio.create_task(runtime.serve(a, setup(a.sid)))]
    try:
        # Fix socket-to-bridge order while keeping both sessions active together.
        await asyncio.wait_for(a.ready.wait(), 10)
        tasks.append(asyncio.create_task(runtime.serve(b, setup(b.sid))))
        await asyncio.wait_for(b.ready.wait(), 10)
        assert runtime.active == 2 and runtime.invocations == 2
        for socket in sockets:
            config = socket.sent[0]["setup"]
            expected_model = selected_model or "gemini-3.8-live"
            assert config["model"] == (expected_model if expected_model.startswith("models/") else "models/" + expected_model)
            assert config["generationConfig"]["responseModalities"] == ["AUDIO"]
            if selected_voice is None:
                assert "speechConfig" not in config["generationConfig"]
            else:
                # The pinned Developer API SDK preserves snake_case inside speechConfig.
                assert config["generationConfig"]["speechConfig"] == {"voice_config": {"prebuilt_voice_config": {"voice_name": selected_voice}}}
            declarations = [d for t in config["tools"] for d in t["functionDeclarations"]]
            assert {d["name"] for d in declarations} == {"classify_intent", "search_catalog", "get_product_route"}
            assert all(d["behavior"] == "BLOCKING" for d in declarations)
            assert all("additional_properties" not in d["parameters"] and "additionalProperties" not in d["parameters"] for d in declarations)
            classification = next(d for d in declarations if d["name"] == "classify_intent")
            assert classification["parameters"]["properties"]["response_mode"]["enum"] == ["conversation", "catalog"]
            assert set(classification["parameters"]["required"]) == {"text", "response_mode"}
            assert "inputAudioTranscription" in config and "outputAudioTranscription" in config
            wire = json.dumps(config)
            for forbidden in ("thinkingConfig", "enableAffectiveDialog", "proactiveAudio", "sessionResumption"):
                assert forbidden not in wire
            assert "capability" not in wire and "x" * 43 not in wire
        a.control("begin_turn", turn_id="turn-1")
        a.incoming.put_nowait({"type": "websocket.receive", "bytes": b"\x01\x01" * 1600})
        a.control("activity_end", turn_id="turn-1")
        await until(lambda: any("realtime_input" in x for x in sockets[0].sent))
        sockets[0].push({"toolCall": {"functionCalls": [{"id": "classify-1", "name": "classify_intent", "args": {"text": "milk"}}]}})
        try:
            await until(lambda: any("tool_response" in x for x in sockets[0].sent))
        except TimeoutError:
            pytest.fail(str({"provider_message_keys": [list(x) for x in sockets[0].sent],
                             "bridge_events": [x.get("type") for x in a.output if isinstance(x, dict)]}))
        assert any(isinstance(x, dict) and x["type"] == "classification_completed" for x in a.output)
        # Input transcription and multiple audio parts must not drop one another;
        # audio before a successful required catalog sequence is deliberately suppressed.
        sockets[0].push({"serverContent": {"modelTurn": {"role": "model", "parts": [
            {"inlineData": {"mimeType": "audio/pcm;rate=24000", "data": base64.b64encode(b"\0" * 20).decode()}},
            {"inlineData": {"mimeType": "audio/pcm;rate=24000", "data": base64.b64encode(b"\0" * 20).decode()}}]},
            "inputTranscription": {"text": "milk", "finished": True}, "turnComplete": True}})
        await until(lambda: any(isinstance(x, dict) and x["type"] == "input_transcript" for x in a.output))
        assert not any(isinstance(x, bytes) for x in a.output)
        sockets[0].push({"toolCall": {"functionCalls": [{"id": "search-1", "name": "search_catalog", "args": {"query": "milk"}}]}})
        await until(lambda: len([x for x in sockets[0].sent if "tool_response" in x]) >= 2)
        sockets[0].push({"toolCall": {"functionCalls": [{"id": "route-1", "name": "get_product_route", "args": {"product_id": "milk", "search_id": "search-fixture"}}]}})
        await until(lambda: len([x for x in sockets[0].sent if "tool_response" in x]) >= 3)
        sockets[0].push({"serverContent": {"modelTurn": {"role": "model", "parts": [
            {"inlineData": {"mimeType": "audio/pcm;rate=24000", "data": base64.b64encode(b"\0" * 20).decode()}},
            {"inlineData": {"mimeType": "audio/pcm;rate=24000", "data": base64.b64encode(b"\0" * 20).decode()}}]},
            "outputTranscription": {"text": "Aisle 2, Shelf 3", "finished": True}, "turnComplete": True}})
        await until(lambda: len([x for x in a.output if isinstance(x, bytes)]) == 2)
        assert not any(isinstance(x, bytes) for x in b.output)
        # Real SDK/Runner receives two seconds of PCM immediately. Downstream
        # must receive all of it at playback speed within the existing bounds.
        await until(lambda: any(isinstance(x, dict) and x["type"] == "audio_end" for x in a.output))
        before = len(a.audio_times)
        for i in range(3):
            sockets[0].push({"serverContent": {"modelTurn": {"role": "model", "parts": [
                {"inlineData": {"mimeType": "audio/pcm;rate=24000", "data": base64.b64encode(b"\0" * 32000).decode()}}]},
                "turnComplete": i == 2}})
        await until(lambda: len(a.audio_times) == before + 6)
        paced = a.audio_times[before:]
        assert sum(size for _, size in paced) == 96000
        assert all(size <= 16384 for _, size in paced)
        # The cumulative lead is bounded to 120ms, plus scheduler tolerance.
        elapsed_audio = 0
        for at, size in paced:
            assert elapsed_audio <= at - paced[0][0] + .15
            elapsed_audio += size / 48000
        assert paced[-1][0] - paced[0][0] >= (96000 - paced[-1][1]) / 48000 - .15
        await until(lambda: len([x for x in a.output if isinstance(x, dict) and x["type"] == "audio_end"]) == 2)
        # Barge-in during a paced multipart event must discard the rest and its
        # obsolete completion without waiting for the entire response to drain.
        before = len(a.audio_times)
        completions = len([x for x in a.output if isinstance(x, dict) and x["type"] == "turn_complete"])
        sockets[0].push({"serverContent": {"modelTurn": {"role": "model", "parts": [
            {"inlineData": {"mimeType": "audio/pcm;rate=24000", "data": base64.b64encode(b"\0" * 48000).decode()}}]},
            "turnComplete": True}})
        await until(lambda: len(a.audio_times) == before + 1)
        a.control("begin_turn", turn_id="turn-2")
        await asyncio.sleep(.5)
        assert len(a.audio_times) == before + 1
        assert len([x for x in a.output if isinstance(x, dict) and x["type"] == "turn_complete"]) == completions
        # Provider confirmation belongs to the cancelled output, not the new
        # gateway turn. Forwarding it as turn-2 blocks that fresh turn in the UI.
        sockets[0].push({"serverContent": {"interrupted": True}})
        await asyncio.sleep(.05)
        assert not any(isinstance(x, dict) and x["type"] == "interrupted" and x["turn_id"] == "turn-2" for x in a.output)
        # The same real Runner can switch from catalog to conversation even
        # when an advisory shopping label does not recognize a greeting.
        sockets[0].push({"toolCall": {"functionCalls": [{"id": "classify-2", "name": "classify_intent", "args": {
            "text": "Hello", "response_mode": "conversation"}}]}})
        await until(lambda: len([x for x in sockets[0].sent if "tool_response" in x]) >= 4)
        sockets[0].push({"serverContent": {"modelTurn": {"role": "model", "parts": [
            {"inlineData": {"mimeType": "audio/pcm;rate=24000", "data": base64.b64encode(b"\0" * 3200).decode()}}]},
            "outputTranscription": {"text": "Hello! How can I help?", "finished": True}, "turnComplete": True}})
        await until(lambda: len([x for x in a.output if isinstance(x, dict) and x["type"] == "turn_complete"]) == completions + 1)
        assert len(a.audio_times) == before + 2
        assert a.output[-1]["turn_id"] == "turn-2"
        # A cancellation of actual current output is still forwarded.
        sockets[0].push({"serverContent": {"modelTurn": {"role": "model", "parts": [
            {"inlineData": {"mimeType": "audio/pcm;rate=24000", "data": base64.b64encode(b"\0" * 3200).decode()}}]}}})
        await until(lambda: len(a.audio_times) == before + 3)
        sockets[0].push({"serverContent": {"interrupted": True}})
        await until(lambda: any(isinstance(x, dict) and x["type"] == "interrupted" and x["turn_id"] == "turn-2" for x in a.output))
        a.control("stop")
        await asyncio.wait_for(tasks[0], 5)
        assert runtime.active == 1
        assert await runtime.sessions.get_session(app_name=APP, user_id=a.sid, session_id=a.sid) is None
        assert await runtime.sessions.get_session(app_name=APP, user_id=b.sid, session_id=b.sid) is not None
        b.control("stop")
        await asyncio.wait_for(tasks[1], 5)
        assert runtime.active == 0 and runtime.cleanups == 2
        assert all(s.closed for s in sockets)
        schema_dir = Path(__file__).parent / "contracts"
        public_schema = json.loads((schema_dir / "live.schema.json").read_text())
        private_schema = json.loads((schema_dir / "private.schema.json").read_text())
        for output in a.output + b.output:
            if not isinstance(output, dict) or output["type"] == "provider_ready":
                continue
            if output["type"] == "classification_completed":
                schema = {**private_schema, "$ref": "#/$defs/classification-completed"}
            else:
                schema = public_schema
            jsonschema.validate(output, schema)

    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def test_private_auth_and_health(monkeypatch):
    from starlette.testclient import TestClient
    from prompt_shop_live.app import create_app
    monkeypatch.setenv("ADK_BRIDGE_SECRET", "s" * 43)
    monkeypatch.setenv("GOOGLE_API_KEY", "fixture-key")
    with TestClient(create_app(classifier)) as client:
        assert client.get("/healthz").json() == {"status": "ok"}
        with pytest.raises(Exception):
            with client.websocket_connect("/live"):
                pytest.fail("unauthenticated private websocket accepted")
    monkeypatch.delenv("GOOGLE_API_KEY")
    with TestClient(create_app(classifier)) as client:
        assert client.get("/healthz").status_code == 503


@pytest.mark.parametrize("mode", ["provider_error", "overflow", "disconnect", "stop"])
async def test_all_exit_paths_delete_session_and_release_capacity(monkeypatch, mode):
    monkeypatch.setenv("GOOGLE_API_KEY", "fixture-key")
    class RunnerFixture:
        def __init__(self, **kwargs):
            self.agent = kwargs["agent"]
        async def run_live(self, **kwargs):
            await self.agent.model._ready()
            if mode == "provider_error":
                raise RuntimeError("sensitive provider payload must not escape")
            await asyncio.Event().wait()
            yield  # async generator with deliberately stalled consumption
        async def close(self):
            pass
    runtime = Runtime(classifier, runner_factory=RunnerFixture)
    bridge = Bridge("failure-session")
    task = asyncio.create_task(runtime.serve(bridge, setup(bridge.sid)))
    await asyncio.wait_for(bridge.ready.wait(), 3)
    if mode == "overflow":
        bridge.control("begin_turn", turn_id="turn-1")
        for _ in range(11):
            bridge.incoming.put_nowait({"type": "websocket.receive", "bytes": b"\0" * 3200})
    elif mode == "disconnect":
        bridge.incoming.put_nowait({"type": "websocket.disconnect"})
    elif mode == "stop":
        bridge.control("stop")
    await asyncio.wait_for(task, 3)
    assert runtime.active == 0 and runtime.cleanups == 1
    assert await runtime.sessions.get_session(app_name=APP, user_id=bridge.sid, session_id=bridge.sid) is None
    assert "sensitive provider payload" not in repr(bridge.output)


@pytest.mark.parametrize("recover_on_retry", [True, False])
async def test_missing_turn_tools_retry_then_recover_without_closing_native_session(monkeypatch, recover_on_retry):
    import prompt_shop_live.runtime as runtime_module
    monkeypatch.setenv("GOOGLE_API_KEY", "fixture-key-never-sent")
    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "FALSE")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.8-live")
    monkeypatch.setattr(runtime_module, "TURN_TOOL_TIMEOUT", .15)
    sockets = []
    @contextlib.asynccontextmanager
    async def connect(*args, **kwargs):
        socket = ProviderSocket()
        sockets.append(socket)
        yield socket
    monkeypatch.setattr(live, "ws_connect", connect)
    runtime = Runtime(classifier)
    bridge = Bridge("turn-recovery")
    task = asyncio.create_task(runtime.serve(bridge, setup(bridge.sid)))
    async def classify(call_id):
        sockets[0].push({"toolCall": {"functionCalls": [{"id": call_id, "name": "classify_intent", "args": {
            "text": "Hello", "response_mode": "conversation"}}]}})
    def reply():
        sockets[0].push({"serverContent": {"modelTurn": {"role": "model", "parts": [
            {"inlineData": {"mimeType": "audio/pcm;rate=24000", "data": base64.b64encode(b"\0" * 3200).decode()}}]},
            "outputTranscription": {"text": "Hello", "finished": True}, "turnComplete": True}})
    try:
        await asyncio.wait_for(bridge.ready.wait(), 5)
        bridge.control("begin_turn", turn_id="turn-1")
        bridge.control("activity_end", turn_id="turn-1")
        sockets[0].push({"serverContent": {"inputTranscription": {"text": "Hello", "finished": True}}})
        # The provider skips the required tool after interruption. Its ungrounded
        # reply is suppressed, then one reminder is sent through actual ADK/SDK.
        reply()
        await until(lambda: any(x.get("realtime_input", {}).get("text") for x in sockets[0].sent))
        assert not bridge.closed and not any(isinstance(x, bytes) for x in bridge.output)
        if recover_on_retry:
            await classify("recovered-1")
            await until(lambda: any("tool_response" in x for x in sockets[0].sent))
            reply()
            await until(lambda: any(isinstance(x, dict) and x["type"] == "turn_complete" for x in bridge.output))
            assert any(isinstance(x, bytes) for x in bridge.output) and not bridge.closed
        else:
            await until(lambda: any(isinstance(x, dict) and x.get("code") == "TURN_TIMEOUT" for x in bridge.output))
            assert not bridge.closed and not any(isinstance(x, bytes) for x in bridge.output)
        # Noise/empty activity must not replay the previous request or terminate
        # the connection. A failed turn cannot later unlock audio or store tools.
        bridge.control("begin_turn", turn_id="turn-2")
        bridge.control("activity_end", turn_id="turn-2")
        await until(lambda: any(isinstance(x, dict) and x.get("code") == "TURN_TIMEOUT" and x.get("turn_id") == "turn-2" for x in bridge.output))
        assert not bridge.closed and runtime.active == 1
        reminders = sum(bool(x.get("realtime_input", {}).get("text")) for x in sockets[0].sent)
        assert reminders == 1
        before = len(bridge.audio_times)
        await classify("late-failed-2")
        reply()
        await asyncio.sleep(.1)
        assert len(bridge.audio_times) == before
        # A fresh spoken request uses the same provider/ADK session successfully.
        bridge.control("begin_turn", turn_id="turn-3")
        await asyncio.sleep(.02)
        expected_responses = len([x for x in sockets[0].sent if "tool_response" in x]) + 1
        await classify("fresh-3")
        await until(lambda: len([x for x in sockets[0].sent if "tool_response" in x]) >= expected_responses)
        reply()
        await until(lambda: len(bridge.audio_times) == before + 1)
        assert len(sockets) == 1 and not bridge.closed
        bridge.control("stop")
        await asyncio.wait_for(task, 5)
        assert runtime.active == 0 and bridge.closed
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.parametrize("interrupt", ["new-turn", "stop"])
async def test_barge_in_during_classification_keeps_actual_adk_runner_alive(monkeypatch, interrupt):
    monkeypatch.setenv("GOOGLE_API_KEY", "fixture-key-never-sent")
    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "FALSE")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.8-live")
    sockets = []
    @contextlib.asynccontextmanager
    async def connect(*args, **kwargs):
        socket = ProviderSocket(); sockets.append(socket); yield socket
    monkeypatch.setattr(live, "ws_connect", connect)
    pending = asyncio.Event()
    async def delayed_classifier(text):
        if text == "pending":
            pending.set()
            await asyncio.Event().wait()
        return await classifier(text)
    runtime = Runtime(delayed_classifier)
    bridge = Bridge("cancel-pending-classifier")
    task = asyncio.create_task(runtime.serve(bridge, setup(bridge.sid)))
    def classify_call(call_id, text):
        sockets[0].push({"toolCall": {"functionCalls": [{"id": call_id, "name": "classify_intent", "args": {
            "text": text, "response_mode": "conversation"}}]}})
    try:
        await asyncio.wait_for(bridge.ready.wait(), 5)
        bridge.control("begin_turn", turn_id="turn-1")
        await asyncio.sleep(.02)
        classify_call("cancel-me", "pending")
        await asyncio.wait_for(pending.wait(), 5)
        if interrupt == "stop":
            bridge.control("stop")
            await asyncio.wait_for(task, 5)
            assert bridge.closed and runtime.active == 0
            return
        bridge.control("begin_turn", turn_id="turn-2")
        await asyncio.sleep(.05)
        assert not bridge.closed and not task.done(), "cancelling one tool killed the ADK connection"
        classify_call("fresh-call", "Hello")
        await until(lambda: any("tool_response" in x and any(r.get("id") == "fresh-call" for r in x["tool_response"]["functionResponses"]) for x in sockets[0].sent))
        sockets[0].push({"serverContent": {"modelTurn": {"role": "model", "parts": [
            {"inlineData": {"mimeType": "audio/pcm;rate=24000", "data": base64.b64encode(b"\0" * 3200).decode()}}]}, "turnComplete": True}})
        await until(lambda: len(bridge.audio_times) == 1)
        assert not bridge.closed and len(sockets) == 1
        bridge.control("stop")
        await asyncio.wait_for(task, 5)
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
