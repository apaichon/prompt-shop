"""Server-owned Gemini settings, captured once when a runtime starts."""
from dataclasses import dataclass
import os
import re

DEFAULT_MODEL = "gemini-3.8-live"


@dataclass(frozen=True)
class LiveSettings:
    model: str = DEFAULT_MODEL
    voice: str | None = None

    def __post_init__(self):
        if not isinstance(self.model, str) or not re.fullmatch(r"(?:models/)?[A-Za-z0-9][A-Za-z0-9._-]{0,127}", self.model):
            raise ValueError("GEMINI_MODEL must be a model ID, optionally prefixed with models/")
        if self.voice is not None and (not isinstance(self.voice, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", self.voice)):
            raise ValueError("GEMINI_VOICE must be a prebuilt voice name or empty for the provider default")

    @classmethod
    def from_env(cls):
        return cls(model=os.environ.get("GEMINI_MODEL", DEFAULT_MODEL),
                   voice=os.environ.get("GEMINI_VOICE") or None)
