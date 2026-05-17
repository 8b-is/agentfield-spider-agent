"""Chromadb sink for spider fetch outcomes.

Optionally posts successfully fetched pages to a chromadb collection
for RAG indexing. Configured via env variables:

  SPIDER_SINK_CHROMA_URL          e.g., http://localhost:8000
  SPIDER_SINK_COLLECTION          e.g., spider_pages
  SPIDER_SINK_ENABLED             1 = enabled, else disabled
  SPIDER_SINK_EMBEDDINGS          openai (default: sentence-transformers)
  SPIDER_SINK_EMBEDDING_MODEL     for openai: e.g., openai/text-embedding-3-small

Public surface:
- should_sink() -> bool
- sink_fetch_outcome(http, outcome_dict) -> bool (True if sunk, False if skipped/error)
"""
from __future__ import annotations

import hashlib
import os
from typing import Any

import aiohttp

from ..log import log

SINK_ENABLED = os.environ.get("SPIDER_SINK_ENABLED", "").lower() == "1"
SINK_CHROMA_URL = os.environ.get("SPIDER_SINK_CHROMA_URL", "").rstrip("/")
SINK_COLLECTION = os.environ.get("SPIDER_SINK_COLLECTION", "spider_pages")
SINK_EMBEDDINGS_MODE = os.environ.get("SPIDER_SINK_EMBEDDINGS", "sentence-transformers")
SINK_EMBEDDING_MODEL = os.environ.get(
    "SPIDER_SINK_EMBEDDING_MODEL",
    "openai/text-embedding-3-small",
)
SINK_OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY", "")


def should_sink() -> bool:
    """Check if chromadb sink is enabled."""
    return SINK_ENABLED and bool(SINK_CHROMA_URL)


def _make_doc_id(url: str) -> str:
    """Generate stable ID from URL hash."""
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


async def _embed_sentence_transformers(texts: list[str]) -> list[list[float]]:
    """Embed text using sentence-transformers (local, no network)."""
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("all-MiniLM-L6-v2")
        embeddings = model.encode(texts, convert_to_numpy=True).tolist()
        return embeddings
    except Exception as e:
        log("sink.embed_error", mode="sentence-transformers", error=str(e))
        return [[0.0] * 384 for _ in texts]  # Fallback: zero vectors


async def _embed_openrouter(texts: list[str]) -> list[list[float]]:
    """Embed text using OpenRouter's embedding API."""
    if not SINK_OPENROUTER_KEY:
        log("sink.embed_error", mode="openai", error="OPENROUTER_API_KEY not set")
        return [[0.0] * 1536 for _ in texts]  # Fallback

    embeddings = []
    async with aiohttp.ClientSession() as session:
        for text in texts:
            try:
                async with session.post(
                    "https://openrouter.ai/api/v1/embeddings",
                    json={"model": SINK_EMBEDDING_MODEL, "input": text},
                    headers={
                        "Authorization": f"Bearer {SINK_OPENROUTER_KEY}",
                        "HTTP-Referer": "spider-agent",
                    },
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        embedding = data.get("data", [{}])[0].get("embedding")
                        if embedding:
                            embeddings.append(embedding)
                            continue
            except Exception as e:
                log("sink.embed_request_error", model=SINK_EMBEDDING_MODEL, error=str(e))
            # Fallback
            embeddings.append([0.0] * 1536)

    return embeddings


async def _get_embeddings(texts: list[str]) -> list[list[float]]:
    """Get embeddings based on configured mode."""
    if SINK_EMBEDDINGS_MODE == "openai":
        return await _embed_openrouter(texts)
    else:
        return await _embed_sentence_transformers(texts)


async def sink_fetch_outcome(
    http: aiohttp.ClientSession,
    outcome: dict[str, Any],
) -> bool:
    """Post a successful fetch outcome to chromadb. Returns True if sunk.

    Silently skips if:
    - Sink disabled
    - outcome status not "ok"
    - Missing required fields (url, title, text)
    """
    if not should_sink():
        return False

    if outcome.get("status") != "ok":
        return False

    url = outcome.get("url", "").strip()
    title = outcome.get("title", "").strip()
    text = outcome.get("text", "").strip()

    if not url or not text:
        return False

    try:
        doc_id = _make_doc_id(url)
        timestamp = outcome.get("ts", 0)

        # Embed the text
        embeddings = await _get_embeddings([text])
        if not embeddings or not embeddings[0]:
            log("sink.embed_failed", url=url)
            return False

        # POST to chromadb
        chroma_url = f"{SINK_CHROMA_URL}/api/v1/collections/{SINK_COLLECTION}/add"
        payload = {
            "ids": [doc_id],
            "documents": [text],
            "metadatas": [
                {
                    "url": url,
                    "title": title,
                    "ts": timestamp,
                    "status": "ok",
                }
            ],
            "embeddings": embeddings,
        }

        async with http.post(
            chroma_url,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            if resp.status in (200, 201):
                log("sink.ok", url=url, doc_id=doc_id)
                return True
            else:
                text_resp = await resp.text()
                log(
                    "sink.error",
                    url=url,
                    status=resp.status,
                    response=text_resp[:200],
                )
                return False

    except Exception as e:
        # Log but never fail the primary fetch
        log("sink.exception", url=url, error=f"{type(e).__name__}: {e}")
        return False
