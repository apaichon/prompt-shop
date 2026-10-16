"""Allowlisted failure categories; never render provider exception payloads."""
import httpx
from google.genai.errors import APIError
from starlette.websockets import WebSocketDisconnect
from websockets.exceptions import ConnectionClosed
from .queue import QueueOverflow


def failure_reason(error):
    if isinstance(error, QueueOverflow): return "input_backlog"
    if isinstance(error, (TimeoutError, httpx.TimeoutException)): return "timeout"
    if isinstance(error, WebSocketDisconnect): return "bridge_closed"
    if isinstance(error, ConnectionClosed): return "provider_connection_closed"
    if isinstance(error, APIError): return "provider_api_error"
    if isinstance(error, httpx.HTTPError): return "tool_transport_error"
    if isinstance(error, ValueError): return "invalid_stream"
    if isinstance(error, RuntimeError): return "provider_stream_error"
    return "internal_error"


def provider_status(error):
    code = getattr(error, "code", None) if isinstance(error, APIError) else None
    return code if type(code) is int and 100 <= code <= 599 else 0
