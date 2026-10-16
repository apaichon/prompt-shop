"""Opt-in native Live smoke through the real ADK Runner.

Catalog and classifier are explicit contract fixtures for TEST-0008 only. This
cannot pass integrated Laya/catalog acceptance or the demo-device microphone gate.
"""
import argparse
import asyncio
import importlib.metadata
import json
import os
from pathlib import Path
import wave

import httpx

from .app import quiet_dependencies
from .protocol import Setup
from .runtime import Runtime


async def fixture_classifier(text):
    return {"schema_version": "intent-v1", "intent": "find_item", "confidence": 1.0,
            "margin": 1.0, "abstained": False, "reason": None, "model_revision": "TEST-0008-contract-fixture"}


async def fixture_tools(request):
    call = json.loads(request.content)
    product = {"id": "milk-whole-1l", "name": "Whole milk 1 L", "category": "Dairy",
               "aisle": {"id": "a02", "label": "Aisle 2"}, "shelf": {"id": "a02-s03", "label": "Shelf 3"}, "route_available": True}
    if request.url.path == "/internal/tools/search_catalog":
        return httpx.Response(200, json={"search_id": "smoke-search", "catalog_version": 1,
            "candidates": [product], "ambiguous": False})
    if request.url.path == "/internal/tools/get_product_route" and call["args"] == {"product_id": product["id"], "search_id": "smoke-search"}:
        return httpx.Response(200, json={"product": product, "catalog_version": 1, "map_version": 1,
            "origin_node_id": "entrance", "node_ids": ["entrance", "n02"], "points": [{"x": 0, "y": 0}, {"x": 2, "y": 3}],
            "steps": ["Walk from the entrance to Aisle 2, Shelf 3."], "distance_units": 5})
    return httpx.Response(409, json={"error": {"code": "STALE_SELECTION"}})


class SmokeBridge:
    def __init__(self, output):
        self.input = asyncio.Queue()
        self.ready = asyncio.Event()
        self.complete = asyncio.Event()
        self.audio_bytes = 0
        self.classifications = 0
        self.errors = 0
        self.output = output
        self.sid = "smoke-" + os.urandom(16).hex()

    def control(self, kind, **fields):
        self.input.put_nowait({"type": "websocket.receive", "text": json.dumps({"type": kind, "session_id": self.sid, **fields})})

    async def receive(self):
        return await self.input.get()

    async def send_json(self, event):
        if event["type"] == "provider_ready":
            self.ready.set()
        elif event["type"] == "classification_completed":
            self.classifications += 1
            self.control("classification_registered", turn_id=event["turn_id"], classification_attempt_id=event["classification_attempt_id"])
        elif event["type"] == "turn_complete" and self.audio_bytes:
            self.complete.set()
        elif event["type"] == "error":
            self.errors += 1
            self.complete.set()

    async def send_bytes(self, data):
        self.audio_bytes += len(data)
        if self.output:
            self.output.writeframesraw(data)

    async def close(self, **kwargs):
        self.complete.set()


async def run(args):
    quiet_dependencies()
    if not os.environ.get("GOOGLE_API_KEY"):
        print(json.dumps({"status": "blocked", "reason": "Set GOOGLE_API_KEY in agent/.env"}))
        return 2
    with wave.open(str(args.input_wav), "rb") as source:
        if (source.getnchannels(), source.getsampwidth(), source.getframerate()) != (1, 2, 16000):
            raise ValueError("input must be PCM16LE mono 16 kHz WAV")
        if source.getnframes() > 16000 * 30:
            raise ValueError("input must be at most 30 seconds")
        pcm = source.readframes(source.getnframes())
    output = wave.open(str(args.output_wav), "wb") if args.output_wav else None
    if output:
        output.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
    bridge = SmokeBridge(output)
    calls = []
    async def transport(request):
        calls.append(request.url.path.rsplit("/", 1)[-1])
        return await fixture_tools(request)
    runtime = Runtime(fixture_classifier, client_factory=lambda **kw: httpx.AsyncClient(transport=httpx.MockTransport(transport), **kw))
    setup = Setup(type="setup", session_id=bridge.sid, language="en-US", turn_id="turn-0", tool_capability="smoke-fixture-capability-000000000000000000")
    task = asyncio.create_task(runtime.serve(bridge, setup))
    try:
        await asyncio.wait_for(bridge.ready.wait(), 30)
        bridge.control("begin_turn", turn_id="turn-1")
        for offset in range(0, len(pcm), 3200):
            bridge.input.put_nowait({"type": "websocket.receive", "bytes": pcm[offset:offset + 3200]})
            await asyncio.sleep(.1)
        bridge.control("activity_end", turn_id="turn-1")
        await asyncio.wait_for(bridge.complete.wait(), 30)
    except TimeoutError:
        bridge.errors += 1
    finally:
        bridge.control("stop")
        try:
            await asyncio.wait_for(task, 5)
        except TimeoutError:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        if output:
            output.close()
    ok = not bridge.errors and bridge.audio_bytes > 0 and bridge.classifications == 1 and "get_product_route" in calls
    print(json.dumps({"status": "transport_smoke_pass" if ok else "failed", "model": runtime.settings.model,
        "voice": runtime.settings.voice,
        "adk": importlib.metadata.version("google-adk"), "genai": importlib.metadata.version("google-genai"),
        "runner_invocations": runtime.invocations, "cleanups": runtime.cleanups, "active_sessions": runtime.active,
        "input_pcm_bytes": len(pcm), "output_pcm_bytes": bridge.audio_bytes, "classification_attempts": bridge.classifications,
        "catalog_calls": calls, "classifier_and_catalog": "contract fixtures", "spoken_grounding": "requires human listening",
        "browser_microphone_gate": "not executed"}, indent=2))
    return 0 if ok else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-wav", type=Path, required=True)
    parser.add_argument("--output-wav", type=Path, help="Explicitly save synthetic smoke output for listening; never use shopper audio")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()
