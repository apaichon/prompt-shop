"""Session flags the embedding router reads during classify_intent."""
import contextvars

router_state = contextvars.ContextVar("embedding_router_state", default=None)
