from contextlib import asynccontextmanager
import os

from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.models.google_llm import Gemini
from google.genai import Client, types
from pydantic import PrivateAttr

from .config import LiveSettings


def run_config(settings: LiveSettings):
    speech = None
    if settings.voice is not None:
        speech = types.SpeechConfig(voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=settings.voice)))
    return RunConfig(streaming_mode=StreamingMode.BIDI,
        response_modalities=["AUDIO"], save_live_blob=False,
        speech_config=speech,
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        realtime_input_config=types.RealtimeInputConfig(
            automatic_activity_detection=types.AutomaticActivityDetection(disabled=True)),
        session_resumption=None, custom_metadata=None)


class ObservedGemini(Gemini):
    """Keep ADK's provider implementation; observe its completed handshake."""
    _ready = PrivateAttr()
    _settings = PrivateAttr()

    def __init__(self, ready, *, settings: LiveSettings):
        client = Client(api_key=os.environ["GOOGLE_API_KEY"], vertexai=False,
                        http_options=types.HttpOptions(api_version="v1alpha"))
        # Version-qualified GenAI 2.30.1 transport hook. Contract tests exercise
        # the real SDK connect path and assert these options reach ws_connect.
        client._api_client._websocket_ssl_ctx.update(max_queue=1, max_size=65536,
                                                    write_limit=32768, close_timeout=1)
        super().__init__(model=settings.model, client=client)
        self._ready = ready
        self._settings = settings

    @asynccontextmanager
    async def connect(self, llm_request):
        if llm_request.model != self._settings.model:
            raise RuntimeError("unexpected model")
        try:
            async with super().connect(llm_request) as connection:
                await self._ready()
                yield connection
        finally:
            await self.aclose()

    async def aclose(self):
        await self.client.aio.aclose()
        self.client.close()
