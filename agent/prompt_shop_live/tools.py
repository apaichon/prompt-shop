"""Explicit BLOCKING declarations; credentials exist only in host closures."""
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
