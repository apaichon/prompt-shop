"""Gemini Embedding 2 label router. The Laya adapter stays the default."""
import asyncio
import hashlib
import json
import logging
import math
import os
import time
from pathlib import Path

import httpx

from tools.router_state import router_state

PREFIX = "task: classification | query: "
MODEL = "gemini-embedding-2"
DIMENSIONS = 768
LABELS = ("find_item", "select_item", "repeat_directions", "summarize", "out_of_scope")
CONFIDENCE_MIN = 0.75
MARGIN_MIN = 0.05
FIND_CONFIDENCE_MIN = 0.80
PROTOTYPE_PATH = Path(__file__).with_name("prototypes") / "embedding-v2.json"
ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-2:batchEmbedContents"
log = logging.getLogger("prompt_shop.embedding")
_router = None


def failed(revision, reason="error"):
    return {"schema_version": "intent-v1", "intent": None, "confidence": None, "margin": None,
            "abstained": True, "reason": reason, "model_revision": revision}


def cosine(left, right):
    if len(left) != len(right) or not left:
        raise ValueError("embedding shape")
    dot = norm_left = norm_right = 0.0
    for a, b in zip(left, right):
        dot += a * b
        norm_left += a * a
        norm_right += b * b
    if norm_left <= 0 or norm_right <= 0:
        return 0.0
    score = dot / math.sqrt(norm_left * norm_right)
    if score > 1:
        return 1.0
    if score < -1:
        return -1.0
    return score


def eligible_labels(state):
    labels = set(LABELS)
    if not state or not state.get("has_results"):
        labels.discard("select_item")
    if not state or not state.get("has_route"):
        labels.discard("repeat_directions")
    return labels


def decide(query, prototypes, vectors, eligible, revision):
    if len(prototypes) != len(vectors):
        raise ValueError("embedding count")
    scores = {}
    for prototype, vector in zip(prototypes, vectors):
        label = prototype["label"]
        if label not in eligible:
            continue
        score = cosine(query, vector)
        if label not in scores or score > scores[label]:
            scores[label] = score
    if not scores:
        return failed(revision)
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    best_label = ranked[0][0]
    best = min(1.0, max(0.0, ranked[0][1]))
    second = min(1.0, max(0.0, ranked[1][1])) if len(ranked) > 1 else 0.0
    margin = min(1.0, max(0.0, best - second))
    # A strong find winner may overlap with selection phrasing. A catalog read
    # resolves that ambiguity authoritatively; selection/summary still need a gap.
    strong_find = best_label == "find_item" and best >= FIND_CONFIDENCE_MIN
    if best < CONFIDENCE_MIN or (margin < MARGIN_MIN and not strong_find):
        return {"schema_version": "intent-v1", "intent": None, "confidence": best, "margin": margin,
                "abstained": True, "reason": "low_confidence", "model_revision": revision}
    return {"schema_version": "intent-v1", "intent": ranked[0][0], "confidence": best, "margin": margin,
            "abstained": False, "reason": None, "model_revision": revision}


def check_text(text):
    return isinstance(text, str) and 1 <= len(text) <= 300 and bool(text.strip()) and "\0" not in text


def load_prototypes(path=PROTOTYPE_PATH):
    raw = Path(path).read_bytes()
    document = json.loads(raw)
    if document.get("schema_version") != "embedding-prototypes-v1":
        raise ValueError("prototype schema")
    if document.get("model") != MODEL or document.get("dimensions") != DIMENSIONS or document.get("prefix") != PREFIX:
        raise ValueError("prototype model")
    examples = document.get("examples")
    if not isinstance(examples, list) or not examples:
        raise ValueError("prototype examples")
    seen = set()
    counts = {label: 0 for label in LABELS}
    for example in examples:
        if not isinstance(example, dict) or set(example) != {"id", "label", "text"}:
            raise ValueError("prototype example")
        if example["id"] in seen or example["label"] not in counts or not check_text(example["text"]):
            raise ValueError("prototype example")
        seen.add(example["id"])
        counts[example["label"]] += 1
    if any(count < 3 for count in counts.values()):
        raise ValueError("prototype coverage")
    digest = hashlib.sha256(raw).hexdigest()
    return examples, f"{MODEL}@{DIMENSIONS}:{digest[:16]}"


class GeminiEmbedder:
    """One batch embed call. The key stays in the header and out of the log line."""

    def __init__(self, api_key, client=None, timeout=2.0):
        self.api_key = api_key
        self.client = client
        self.timeout = timeout
        self.owns_client = client is None
        self.tokens = None

    async def aclose(self):
        if self.owns_client and self.client is not None:
            await self.client.aclose()
            self.client = None

    async def __call__(self, texts):
        if self.client is None:
            self.client = httpx.AsyncClient(timeout=self.timeout, trust_env=False, follow_redirects=False)
        vectors, self.tokens = await embed_texts(
            texts, api_key=self.api_key, client=self.client, timeout=15.0 if len(texts) > 1 else self.timeout)
        return vectors


async def embed_texts(texts, *, api_key, client=None, dimensions=DIMENSIONS, timeout=1.0):
    if not isinstance(api_key, str) or not api_key:
        raise ValueError("embedding key")
    body = {"requests": [{
        "model": f"models/{MODEL}",
        "content": {"parts": [{"text": text}]},
        "outputDimensionality": dimensions,
    } for text in texts]}
    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient(timeout=timeout, trust_env=False, follow_redirects=False)
    try:
        response = await client.post(
            ENDPOINT,
            headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
            json=body, timeout=timeout,
        )
        if response.status_code != 200:
            raise ValueError("embedding status")
        payload = response.json()
    finally:
        if owns_client:
            await client.aclose()
    rows = payload.get("embeddings") if isinstance(payload, dict) else None
    if not isinstance(rows, list) or len(rows) != len(texts):
        raise ValueError("embedding count")
    vectors = []
    for row in rows:
        values = row.get("values") if isinstance(row, dict) else None
        if (not isinstance(values, list) or len(values) != dimensions
                or not all(type(number) in (int, float) and math.isfinite(number) for number in values)):
            raise ValueError("embedding shape")
        vectors.append([float(number) for number in values])
    usage = payload.get("usageMetadata") if isinstance(payload.get("usageMetadata"), dict) else {}
    tokens = usage.get("totalTokenCount")
    return vectors, tokens if type(tokens) is int else None


class EmbeddingRouter:
    def __init__(self, prototypes, embedder, revision, vectors=None):
        self.prototypes = prototypes
        self.embedder = embedder
        self.revision = revision
        self.vectors = vectors
        self._warm_lock = asyncio.Lock()

    async def warm(self):
        async with self._warm_lock:
            if self.vectors is None:
                vectors = await self.embedder([PREFIX + item["text"] for item in self.prototypes])
                if len(vectors) != len(self.prototypes):
                    raise ValueError("embedding count")
                self.vectors = vectors

    async def classify(self, text, state=None):
        started = time.perf_counter()
        status = "error"
        if hasattr(self.embedder, "tokens"):
            self.embedder.tokens = None
        try:
            if not check_text(text):
                status = "invalid"
                return failed(self.revision)
            await self.warm()
            query = await self.embedder([PREFIX + text])
            if len(query) != 1:
                raise ValueError("embedding count")
            result = decide(query[0], self.prototypes, self.vectors, eligible_labels(state), self.revision)
            status = "abstain" if result["abstained"] else "label"
            return result
        except (TimeoutError, httpx.TimeoutException):
            status = "timeout"
            return failed(self.revision, "timeout")
        except Exception:
            status = "error"
            return failed(self.revision)
        finally:
            elapsed = int((time.perf_counter() - started) * 1000)
            tokens = getattr(self.embedder, "tokens", None)
            if type(tokens) is int:
                log.info("embedding_decision status=%s latency_ms=%d tokens=%d", status, elapsed, tokens)
            else:
                log.info("embedding_decision status=%s latency_ms=%d", status, elapsed)


def default_router():
    global _router
    if _router is None:
        prototypes, revision = load_prototypes()
        _router = EmbeddingRouter(prototypes, GeminiEmbedder(os.environ.get("GOOGLE_API_KEY", "")), revision)
    return _router


async def classify_text(text):
    try:
        async with asyncio.timeout(2.5):
            return await default_router().classify(text, router_state.get())
    except (TimeoutError, httpx.TimeoutException):
        revision = _router.revision if _router is not None else f"{MODEL}@{DIMENSIONS}:unavailable"
        return failed(revision, "timeout")
    except Exception:
        revision = _router.revision if _router is not None else f"{MODEL}@{DIMENSIONS}:unavailable"
        return failed(revision)
