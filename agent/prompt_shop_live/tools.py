"""Bounded model-facing flows and private BLOCKING tool adapters."""
import logging

from google.adk.tools import BaseTool
from google.genai import types

from .protocol import text_arg, tool_error

SCHEMAS = {
    "classify_intent": {
        "text": "Shopper's completed semantic request, at most 300 characters.",
        "response_mode": "conversation for general chat, greetings or meal ideas; catalog for product matching, store availability, ingredients to locate or shelf directions.",
    },
    "search_catalog": {"query": "Single item to find, at most 200 characters."},
    "get_product_route": {"product_id": "An ID from the current candidate set.", "search_id": "Copy exactly from the applicable search_catalog response; never invent or reconstruct this ID."},
}


class BlockingTool(BaseTool):
    def __init__(self, name, host):
        super().__init__(name=name, description={
            "classify_intent": "Record advisory classification for each shopper turn and choose conversation or catalog response mode. General chat and meal suggestions do not need a product lookup.",
            "search_catalog": "Look up authoritative published catalog products. Never invent a result.",
            "get_product_route": "Get authoritative shelf directions for a selected current candidate.",
        }[name])
        self.host = host

    def _get_declaration(self):
        return types.FunctionDeclaration(
            name=self.name, description=self.description, behavior=types.Behavior.BLOCKING,
            parameters=types.Schema(type=types.Type.OBJECT,
                properties={key: types.Schema(type=types.Type.STRING, description=desc,
                    enum=["conversation", "catalog"] if key == "response_mode" else None)
                    for key, desc in SCHEMAS[self.name].items()},
                # Live's parameter-schema subset rejects additional_properties.
                # text_arg still rejects every unknown argument before dispatch.
                required=list(SCHEMAS[self.name])),
        )

    async def run_async(self, *, args, tool_context):
        try:
            if not isinstance(args, dict):
                raise ValueError("invalid arguments")
            args = dict(args)
            if self.name == "classify_intent":
                # Legacy callers fail closed; the current provider declaration
                # requires an explicit choice for every new turn.
                args.setdefault("response_mode", "catalog")
                if not isinstance(args["response_mode"], str) or args["response_mode"] not in {"conversation", "catalog"}:
                    raise ValueError("invalid response mode")
            text_arg(args, SCHEMAS[self.name], 300 if self.name == "classify_intent" else 200)
        except ValueError:
            return tool_error("INVALID_REQUEST")
        return await self.host.call(self.name, args)


LIVE_SCHEMAS = {
    "begin_conversation": {"text": "The completed greeting, general question or recipe request, at most 300 characters."},
    "find_product": {
        "text": "The completed shopper request (including a request to repeat), at most 300 characters.",
        "query": "One concise product/ingredient name to find in the store, at most 200 characters.",
    },
    "select_product": {
        "text": "The shopper's selection, at most 300 characters.",
        "product_id": "Copy the chosen ID exactly from pending candidates.",
        "search_id": "Copy the search ID exactly from those pending candidates.",
    },
}


class ShopperTool(BaseTool):
    """One model call; required local classifier/search/route operations stay bounded."""
    def __init__(self, name, host):
        super().__init__(name=name, description={
            "begin_conversation": "Begin a general conversational reply. Call once, then answer promptly after acknowledgment. Never use for store locations or availability.",
            "find_product": "Find a store product and its verified directions in one operation. Also use for repeated directions. If ambiguous, ask the shopper to choose; if no match, say so.",
            "select_product": "Locate the shopper's choice from pending ambiguous candidates. Use the exact returned product/search IDs.",
        }[name])
        self.host = host

    def _get_declaration(self):
        return types.FunctionDeclaration(name=self.name, description=self.description,
            behavior=types.Behavior.BLOCKING,
            parameters=types.Schema(type=types.Type.OBJECT,
                properties={key: types.Schema(type=types.Type.STRING, description=value)
                            for key, value in LIVE_SCHEMAS[self.name].items()},
                required=list(LIVE_SCHEMAS[self.name])))

    async def run_async(self, *, args, tool_context):
        try:
            text_arg(args, LIVE_SCHEMAS[self.name], 300)
            if self.name == "find_product":
                text_arg({"query": args["query"]}, {"query"}, 200)
        except ValueError:
            logging.getLogger(__name__).warning("voice_flow_rejected flow=%s reason=invalid_args", self.name)
            error = tool_error("INVALID_REQUEST")
            error["error"]["message"] = "Call " + self.name + " with required string fields: " + ", ".join(LIVE_SCHEMAS[self.name]) + "."
            return error
        turn = self.host.turn
        if self.host.flows:
            logging.getLogger(__name__).warning("voice_flow_rejected flow=%s reason=turn_limit", self.name)
            return tool_error("RATE_LIMITED")
        self.host.flows.add(self.name)

        async def call(name, values):
            # begin() may cancel a child while this orchestration awaits it.
            # Never let a later stage capture the next shopper's turn identity.
            if self.host.turn != turn:
                return tool_error("STALE_SELECTION")
            return await BlockingTool(name, self.host).run_async(args=values, tool_context=tool_context)

        if not self.host.classified:
            result = await call("classify_intent", {
                "text": args["text"],
                "response_mode": "conversation" if self.name == "begin_conversation" else "catalog",
            })
            if "error" in result:
                return result
        if self.host.turn != turn or self.host.failed:
            return tool_error("STALE_SELECTION")
        if self.name == "begin_conversation":
            return {"acknowledged": True, "next_action": "Answer the shopper briefly in English now. Do not wait for more speech."}
        if self.name == "select_product":
            return await call("get_product_route", {"product_id": args["product_id"], "search_id": args["search_id"]})
        search = await call("search_catalog", {"query": args["query"]})
        if "error" in search or search.get("ambiguous") or not search.get("candidates"):
            return search
        candidates = search["candidates"]
        if len(candidates) != 1 or not search.get("search_id"):
            return tool_error("INVALID_RESPONSE")
        route = await call("get_product_route", {"product_id": candidates[0]["id"], "search_id": search["search_id"]})
        return {"search": search, "route": route}
