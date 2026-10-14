"""Private ASGI classifier; authenticated fixed JSON, no content logging."""
import asyncio
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass, field
import hmac
import json
import os
from pathlib import Path

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.requests import ClientDisconnect

from .protocol import MODEL_REVISION, abstain, valid_text
from .worker import Engine


@dataclass(frozen=True)
class Settings:
    token: str = field(repr=False)
    model_root: Path

    def __post_init__(self):
        if not isinstance(self.token, str) or not 32 <= len(self.token) <= 1024 or not self.token.isascii() or any(ord(c) < 33 or ord(c) > 126 for c in self.token):
            raise ValueError("private classifier token configuration invalid")

    @classmethod
    def from_env(cls):
        value = os.environ.get("LAYA_MODEL_PATH", "")
        if not value:
            raise ValueError("offline model path configuration missing")
        return cls(os.environ.get("LAYA_INTERNAL_TOKEN", ""), Path(value))


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def create_app(settings=None, *, engine_factory=Engine):
    @asynccontextmanager
    async def lifespan(app):
        conf = settings or Settings.from_env()
        engine = engine_factory(conf.model_root)
        app.state.settings, app.state.engine = conf, engine
        await engine.start()
        try:
            yield
        finally:
            await engine.close()

    async def health(request):
        engine = request.app.state.engine
        return JSONResponse({"ready": engine.ready, "schema_version": "intent-v1", "model_revision": MODEL_REVISION, "load": engine.load_facts if engine.ready else None}, status_code=200 if engine.ready else 503)

    async def classify(request):
        conf = request.app.state.settings
        supplied = request.headers.get("x-internal-token", "")
        if not hmac.compare_digest(supplied.encode("utf-8"), conf.token.encode("ascii")):
            return JSONResponse({"error": {"code": "UNAUTHORIZED"}}, status_code=401)
        # The private ADK client sends no browser Origin. No CORS/public proxy API.
        if "origin" in request.headers:
            return JSONResponse({"error": {"code": "FORBIDDEN"}}, status_code=403)
        if request.headers.get("content-type", "").split(";")[0].lower() != "application/json":
            return JSONResponse({"error": {"code": "INVALID_REQUEST"}}, status_code=400)
        loop = asyncio.get_running_loop()
        deadline = loop.time()+1.2
        data = bytearray()
        try:
            async with asyncio.timeout_at(deadline):
                async for chunk in request.stream():
                    data.extend(chunk)
                    if len(data) > 2048:
                        raise ValueError("body too large")
                value = json.loads(data, object_pairs_hook=strict_object, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))
                data.clear()
                if not isinstance(value, dict) or set(value) != {"text"}:
                    raise ValueError("fixed text field required")
                text = valid_text(value.pop("text"))
        except TimeoutError:
            return JSONResponse(abstain("timeout"))
        except ClientDisconnect:
            return JSONResponse(abstain("error"))
        except (ValueError, UnicodeError):
            return JSONResponse({"error": {"code": "INVALID_REQUEST"}}, status_code=400)
        finally:
            data.clear()
        task = asyncio.create_task(request.app.state.engine.classify(text, deadline=deadline))
        text = None
        try:
            while not task.done():
                if await request.is_disconnected():
                    task.cancel()
                    with suppress(asyncio.CancelledError): await task
                    return JSONResponse(abstain("error"))
                await asyncio.sleep(.005)
            return JSONResponse(await task)
        finally:
            if not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError): await task

    return Starlette(routes=[Route("/healthz",health,methods=["GET"]),Route("/classify",classify,methods=["POST"])],lifespan=lifespan)


app = create_app()
