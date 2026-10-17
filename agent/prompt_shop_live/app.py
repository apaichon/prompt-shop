from contextlib import asynccontextmanager
import asyncio
import importlib
import logging
import os
import secrets

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route, WebSocketRoute

from .protocol import Setup
from .runtime import Runtime


def quiet_dependencies():
    # SDK debug/error messages can include transcript, tool args or HTTP secrets.
    for name in ("google_adk", "google.adk", "google_genai", "google.genai", "httpx", "httpcore", "websockets"):
        logger = logging.getLogger(name)
        logger.setLevel(logging.CRITICAL + 1)
        logger.propagate = False
        logger.handlers = [logging.NullHandler()]


def create_app(classifier=None, *, runtime=None):
    quiet_dependencies()
    secret = os.environ.get("ADK_BRIDGE_SECRET", "")
    if classifier is None:
        try:
            # This module is supplied by TASK-0010. No production fallback/mock.
            classifier = importlib.import_module("tools.intent").classify_intent
        except (ImportError, AttributeError):
            classifier = None
    configured = bool(len(secret) >= 32 and os.environ.get("GOOGLE_API_KEY") and classifier)
    engine = runtime or (Runtime(classifier) if classifier else None)

    async def health(request):
        return JSONResponse({"status": "ok" if configured else "not_ready"}, status_code=200 if configured else 503)

    async def live(ws):
        expected = "Bearer " + secret
        if not configured or ws.query_params or not secrets.compare_digest(ws.headers.get("authorization", ""), expected):
            await ws.close(code=1008)
            return
        await ws.accept()
        try:
            async with asyncio.timeout(30):
                raw = await ws.receive_text()
            if len(raw.encode()) > 4096:
                raise ValueError("oversized setup")
            setup = Setup.model_validate_json(raw)
        except Exception:
            await ws.close(code=1008)
            return
        await engine.serve(ws, setup)

    @asynccontextmanager
    async def lifespan(app):
        # Prototype vectors are cached before the first shopper turn. The key and
        # sentence stay out of this line. A warm failure leaves the process up.
        if os.environ.get("INTENT_BACKEND") == "embedding":
            print("intent_backend=embedding model=gemini-embedding-2", flush=True)
            try:
                router = importlib.import_module("tools.embedding_router")
                await router.default_router().warm()
                print("intent_backend=embedding warm=ready", flush=True)
            except Exception:
                print("intent_backend=embedding warm=error", flush=True)
        try:
            yield
        finally:
            if os.environ.get("INTENT_BACKEND") == "embedding":
                router = importlib.import_module("tools.embedding_router")
                if router._router is not None:
                    await router._router.embedder.aclose()

    app = Starlette(routes=[Route("/healthz", health), WebSocketRoute("/live", live)], lifespan=lifespan)
    app.state.runtime = engine
    return app


app = create_app()
