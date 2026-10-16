import asyncio
import logging
import secrets
from collections.abc import Awaitable, Callable

import httpx

from .protocol import tool_error

Classifier = Callable[[str], Awaitable[dict]]


class ToolHost:
    def __init__(self, setup, send, classify: Classifier, client: httpx.AsyncClient):
        self.setup, self.send, self.classify, self.client = setup, send, classify, client
        self.turn = setup.turn_id
        self.attempt = None
        self.classified = False
        self.audio_allowed = False
        self.ack = asyncio.Event()
        self.tasks = set()
        self.closed = False
        self.failed = False
        self.counts = {}
        self.flows = set()

    def begin(self, turn):
        if not isinstance(turn, str) or not turn.startswith("turn-") or int(turn[5:]) <= int(self.turn[5:]):
            raise ValueError("nonmonotonic turn")
        for task in tuple(self.tasks):
            task.cancel()
        self.turn, self.attempt = turn, None
        self.classified = self.audio_allowed = self.failed = False
        self.counts = {}
        self.flows = set()
        self.ack = asyncio.Event()

    def fail(self, turn):
        if turn == self.turn:
            self.failed = True
            self.audio_allowed = False

    def acknowledge(self, event):
        if (event.get("session_id") == self.setup.session_id and event.get("turn_id") == self.turn
                and self.attempt is not None and event.get("classification_attempt_id") == self.attempt):
            self.ack.set()

    async def call(self, name, args):
        turn = self.turn
        # Cancel our own bounded operation, never ADK's caller/runner task.
        task = asyncio.create_task(self._call(name, args, turn))
        self.tasks.add(task)
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            caller = asyncio.current_task()
            if task.cancelled() and turn != self.turn and not self.closed and not caller.cancelling():
                return tool_error("STALE_SELECTION")
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            raise
        finally:
            self.tasks.discard(task)

    async def _call(self, name, args, turn):
        try:
            if self.closed or self.failed or turn != self.turn or turn == "turn-0":
                return tool_error("STALE_SELECTION")
            count = self.counts.get(name, 0)
            if count >= (2 if name == "search_catalog" else 1):
                return tool_error("RATE_LIMITED")
            self.counts[name] = count + 1
            if name == "classify_intent":
                response_mode = args.get("response_mode", "catalog")
                if not isinstance(response_mode, str) or response_mode not in {"conversation", "catalog"}:
                    return tool_error("INVALID_REQUEST")
                self.attempt = secrets.token_urlsafe(24)
                try:
                    async with asyncio.timeout(1.2):
                        result = await self.classify(args["text"])
                except (TimeoutError, httpx.HTTPError):
                    result = {"schema_version": "intent-v1", "intent": None, "confidence": None,
                              "margin": None, "abstained": True, "reason": "unavailable", "model_revision": "unavailable"}
                validate_classification(result)
                if turn != self.turn or self.failed:
                    return tool_error("STALE_SELECTION")
                await self.send({"type": "classification_completed", "session_id": self.setup.session_id,
                    "turn_id": turn, "classification_attempt_id": self.attempt,
                    "response_mode": response_mode, "result": result})
                # ACK is mandatory before crossing from WS metadata to HTTP callbacks.
                async with asyncio.timeout(.75):
                    await self.ack.wait()
                if turn != self.turn or self.failed:
                    return tool_error("STALE_SELECTION")
                self.classified = True
                # Laya's four shopping labels are advisory, including abstention.
                # A conversation has no store facts to verify before replying.
                self.audio_allowed = response_mode == "conversation"
                return result
            if not self.classified or not self.ack.is_set():
                return tool_error("CLASSIFICATION_REQUIRED")
            self.audio_allowed = False
            envelope = {"session_id": self.setup.session_id, "turn_id": turn,
                "call_id": secrets.token_urlsafe(24), "classification_attempt_id": self.attempt, "args": args}
            async with asyncio.timeout(1.5):
                response = await self.client.post("http://127.0.0.1:8002/internal/tools/" + name,
                    headers={"Authorization": "Bearer " + self.setup.tool_capability}, json=envelope)
                if response.is_error:
                    # Diagnose status only, never a raw provider/tool body or URL.
                    logging.getLogger(__name__).warning(
                        "voice_tool_failure tool=%s status=%d",
                        name if name in {"search_catalog", "get_product_route"} else "unknown",
                        response.status_code)
                response.raise_for_status()
                result = response.json()
            if turn != self.turn or self.closed or self.failed:
                return tool_error("STALE_SELECTION")
            if "error" not in result:
                if name == "get_product_route" or result.get("ambiguous") or not result.get("candidates"):
                    self.audio_allowed = True
            return result
        except asyncio.CancelledError:
            raise
        except (ValueError, TimeoutError, httpx.HTTPError):
            return tool_error("DEPENDENCY_UNAVAILABLE")

    async def close(self):
        self.closed = True
        pending = tuple(t for t in self.tasks if t is not asyncio.current_task())
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)


def validate_classification(result):
    expected = {"schema_version", "intent", "confidence", "margin", "abstained", "reason", "model_revision"}
    if not isinstance(result, dict) or set(result) != expected or result["schema_version"] != "intent-v1":
        raise ValueError("invalid classification")
    if type(result["abstained"]) is not bool or not isinstance(result["model_revision"], str):
        raise ValueError("invalid classification")
    if result["intent"] not in (None, "find_item", "select_item", "repeat_directions", "out_of_scope"):
        raise ValueError("invalid classification")
    for key in ("confidence", "margin"):
        n = result[key]
        if n is not None and (type(n) not in (int, float) or not 0 <= n <= 1):
            raise ValueError("invalid classification")
    if not result["abstained"] and (result["intent"] is None or result["confidence"] is None or
            result["confidence"] < .7 or result["margin"] is None or result["margin"] < .15):
        raise ValueError("invalid classification")
