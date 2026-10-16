import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

APP = "prompt_shop"
ID = re.compile(r"^[a-zA-Z0-9_-]{1,128}$")


class Setup(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    type: Literal["setup"]
    session_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,128}$")
    language: Literal["en-US"]
    turn_id: str = Field(pattern=r"^turn-(0|[1-9][0-9]*)$")
    tool_capability: str = Field(min_length=32, max_length=128)


def text_arg(args, keys, max_length):
    if not isinstance(args, dict) or set(args) != set(keys):
        raise ValueError("invalid arguments")
    for key in keys:
        if not isinstance(args[key], str) or not 1 <= len(args[key].strip()) <= max_length:
            raise ValueError("invalid arguments")


def tool_error(code):
    return {"error": {"code": code, "message": "Voice tool could not complete; retry or use typed search.", "retryable": True}}
