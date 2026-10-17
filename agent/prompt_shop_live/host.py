import asyncio
import logging
import os
import secrets
from collections.abc import Awaitable, Callable

import httpx

from tools.router_state import router_state

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
        self.intent = None
        self.abstained = False
        self.label_gate = False
        self.turn_results = None
        self.session_results = None
        self.session_route = None

    def begin(self, turn):
        if not isinstance(turn, str) or not turn.startswith("turn-") or int(turn[5:]) <= int(self.turn[5:]):
            raise ValueError("nonmonotonic turn")
        for task in tuple(self.tasks):
            task.cancel()
        self.turn, self.attempt = turn, None
        self.classified = self.audio_allowed = self.failed = False
        self.intent = None
        self.abstained = False
        self.label_gate = False
        self.turn_results = None
        # Current results and the current route survive the turn so a later
        # selection or repeat can see them. begin() only clears this turn.
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
            if name != "classify_intent" and self.label_gate and not self._label_allows(name, args):
                return tool_error("TOOL_NOT_ALLOWED")
            count = self.counts.get(name, 0)
            if count >= (2 if name == "search_catalog" else 1):
                return tool_error("RATE_LIMITED")
            self.counts[name] = count + 1
            if name == "classify_intent":
                response_mode = args.get("response_mode", "catalog")
                if not isinstance(response_mode, str) or response_mode not in {"conversation", "catalog"}:
                    return tool_error("INVALID_REQUEST")
                self.attempt = secrets.token_urlsafe(24)
                state_token = router_state.set({
                    "has_results": bool(self.session_results and self.session_results.get("ids")),
                    "has_route": self.session_route is not None,
                })
                try:
                    try:
                        async with asyncio.timeout(2.75 if os.environ.get("INTENT_BACKEND") == "embedding" else 1.2):
                            result = await self.classify(args["text"])
                    except (TimeoutError, httpx.HTTPError):
                        result = {"schema_version": "intent-v1", "intent": None, "confidence": None,
                                  "margin": None, "abstained": True, "reason": "unavailable", "model_revision": "unavailable"}
                    validate_classification(result)
                finally:
                    router_state.reset(state_token)
                revision = result["model_revision"]
                embedding = isinstance(revision, str) and revision.startswith("gemini-embedding-2")
                # Go unlocks speech from this mode. Abstain and out of scope must
                # speak without a tool; every other embedding label waits for Go.
                if embedding:
                    spoken_only = result["abstained"] or result["intent"] in (None, "out_of_scope")
                    response_mode = "conversation" if spoken_only else "catalog"
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
                self.intent = result["intent"]
                self.abstained = result["abstained"]
                self.label_gate = embedding
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
                self._remember(name, args, result)
                if name in {"get_product_route", "get_conversation_summary"} or result.get("ambiguous") or not result.get("candidates"):
                    self.audio_allowed = True
            return result
        except asyncio.CancelledError:
            raise
        except (ValueError, TimeoutError, httpx.HTTPError):
            return tool_error("DEPENDENCY_UNAVAILABLE")

    async def allow_response(self, turn):
        # Private bridge metadata precedes audio on the same ordered socket.
        # This releases a clarification/error reply after the bounded flow ends.
        if self.closed or self.failed or turn != self.turn or not self.classified or not self.ack.is_set():
            return
        await self.send({"type": "response_ready", "session_id": self.setup.session_id,
                         "turn_id": turn, "classification_attempt_id": self.attempt})
        if turn == self.turn and not self.failed and not self.closed:
            self.audio_allowed = True

    def _label_allows(self, name, args):
        if self.abstained or self.intent in (None, "out_of_scope"):
            return False
        if self.intent == "summarize":
            return name == "get_conversation_summary"
        if self.intent == "find_item" and name == "search_catalog":
            return True
        if self.intent == "find_item" and name == "get_product_route" and self.turn_results:
            return (args.get("product_id") in self.turn_results["ids"]
                    and args.get("search_id") == self.turn_results["search_id"])
        if self.intent == "select_item" and name == "get_product_route" and self.session_results:
            return (args.get("product_id") in self.session_results["ids"]
                    and args.get("search_id") == self.session_results["search_id"])
        if self.intent == "repeat_directions" and name == "get_product_route" and self.session_route:
            return (args.get("product_id") == self.session_route["product_id"]
                    and args.get("search_id") == self.session_route["search_id"])
        return False

    def _remember(self, name, args, result):
        if name == "search_catalog":
            candidates = result.get("candidates")
            search_id = result.get("search_id")
            if isinstance(candidates, list) and isinstance(search_id, str) and search_id:
                ids = [item["id"] for item in candidates
                       if isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"]]
                remembered = {"search_id": search_id, "ids": ids}
                self.turn_results = remembered
                self.session_results = remembered
                # Go replaces candidate membership on every search, even no match.
                self.session_route = None
        elif name == "get_product_route":
            product_id = args.get("product_id")
            search_id = args.get("search_id")
            if isinstance(product_id, str) and product_id and isinstance(search_id, str) and search_id:
                self.session_route = {"product_id": product_id, "search_id": search_id}

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
    if result["intent"] not in (None, "find_item", "select_item", "repeat_directions", "summarize", "out_of_scope"):
        raise ValueError("invalid classification")
    for key in ("confidence", "margin"):
        n = result[key]
        if n is not None and (type(n) not in (int, float) or not 0 <= n <= 1):
            raise ValueError("invalid classification")
    embedding = result["model_revision"].startswith("gemini-embedding-2@")
    confidence_min, margin_min = (.75, .05) if embedding else (.7, .15)
    strong_find = (embedding and result["intent"] == "find_item"
                   and result["confidence"] is not None and result["confidence"] >= .80)
    if result["abstained"]:
        if result["intent"] is not None or result["reason"] not in {"low_confidence", "timeout", "busy", "error", "unavailable"}:
            raise ValueError("invalid classification")
    elif (result["intent"] is None or result["reason"] is not None or result["confidence"] is None
          or result["confidence"] < confidence_min or result["margin"] is None or (result["margin"] < margin_min and not strong_find)):
        raise ValueError("invalid classification")
