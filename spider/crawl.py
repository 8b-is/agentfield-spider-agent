"""Recursive URL crawling with depth and page limits.

Public surface:
- crawl_start(redis, seed_url, max_depth, max_pages, same_domain_only, timeout_seconds) -> job_id
- crawl_status(redis, job_id) -> dict with status, counts, errors
- crawl_iter(deps, redis, job_id) -> one iteration of the crawler loop (called by dispatcher)
"""
from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any
from urllib.parse import urljoin, urlparse

import orjson

from .fetch import FetchDeps, fetch_one
from .log import log
from .security import is_safe_external_url
from .state import enqueue as state_enqueue

# Redis key patterns
_JOB_PREFIX = "crawler:crawl"
_QUEUE_KEY = lambda job_id: f"{_JOB_PREFIX}:{job_id}:queue"
_VISITED_KEY = lambda job_id: f"{_JOB_PREFIX}:{job_id}:visited"
_STATE_KEY = lambda job_id: f"{_JOB_PREFIX}:{job_id}:state"
_RESULTS_KEY = lambda job_id: f"{_JOB_PREFIX}:{job_id}:results"


async def crawl_start(
    redis: Any,
    seed_url: str,
    max_depth: int = 2,
    max_pages: int = 50,
    same_domain_only: bool = True,
    timeout_seconds: int = 600,
) -> str:
    """Start a crawl job. Returns job_id.

    Enqueues the seed URL and creates Redis tracking structures.
    """
    job_id = str(uuid.uuid4())

    # Initialize state
    state_data = {
        "seed_url": seed_url,
        "max_depth": str(max_depth),
        "max_pages": str(max_pages),
        "same_domain_only": "1" if same_domain_only else "0",
        "timeout_seconds": str(timeout_seconds),
        "status": "queued",
        "started_at": str(time.time()),
        "pages_fetched": "0",
        "pages_queued": "1",
        "error_count": "0",
    }
    await redis.hset(_STATE_KEY(job_id), mapping=state_data)

    # Initialize empty results list
    await redis.delete(_RESULTS_KEY(job_id))

    # Enqueue the seed with depth 0
    queue_key = _QUEUE_KEY(job_id)
    await redis.lpush(queue_key, orjson.dumps({"url": seed_url, "depth": 0}).decode("utf-8"))

    # Mark seed as visited
    visited_key = _VISITED_KEY(job_id)
    await redis.sadd(visited_key, seed_url)

    log("crawl.start", job_id=job_id, seed_url=seed_url, max_depth=max_depth, max_pages=max_pages)
    return job_id


async def crawl_status(redis: Any, job_id: str) -> dict[str, Any]:
    """Get current crawl status."""
    state = await redis.hgetall(_STATE_KEY(job_id))
    if not state:
        return {"status": "not_found", "job_id": job_id}

    return {
        "job_id": job_id,
        "status": (state.get(b"status") or b"").decode("utf-8") or "queued",
        "seed_url": (state.get(b"seed_url") or b"").decode("utf-8"),
        "pages_fetched": int((state.get(b"pages_fetched") or b"0").decode("utf-8")),
        "pages_queued": int((state.get(b"pages_queued") or b"0").decode("utf-8")),
        "error_count": int((state.get(b"error_count") or b"0").decode("utf-8")),
        "started_at": float((state.get(b"started_at") or b"0").decode("utf-8")),
    }


def _extract_links(text: str, base_url: str) -> list[str]:
    """Extract hrefs from HTML text. Returns absolute URLs."""
    links = []
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(text, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if href and not href.startswith(("#", "javascript:", "mailto:", "tel:")):
                absolute = urljoin(base_url, href)
                # Drop fragment
                absolute = absolute.split("#")[0]
                if absolute:
                    links.append(absolute)
    except Exception:
        pass
    return links


def _same_domain(url1: str, url2: str) -> bool:
    """Check if two URLs have the same domain."""
    try:
        h1 = urlparse(url1).netloc.lower()
        h2 = urlparse(url2).netloc.lower()
        return h1 == h2
    except Exception:
        return False


async def crawl_iter(
    deps: FetchDeps,
    redis: Any,
    job_id: str,
    max_iters: int = 5,  # Process up to 5 URLs per call
) -> dict[str, Any]:
    """Single iteration: drain up to max_iters URLs from the queue.

    Called by the dispatcher worker. Returns job status after processing.
    """
    state = await redis.hgetall(_STATE_KEY(job_id))
    if not state:
        return {"status": "not_found", "job_id": job_id}

    status_str = (state.get(b"status") or b"queued").decode("utf-8")
    if status_str not in ("queued", "running"):
        return await crawl_status(redis, job_id)

    # Update to "running"
    await redis.hset(_STATE_KEY(job_id), "status", "running")

    seed_url = (state.get(b"seed_url") or b"").decode("utf-8")
    max_depth = int((state.get(b"max_depth") or b"2").decode("utf-8"))
    max_pages = int((state.get(b"max_pages") or b"50").decode("utf-8"))
    same_domain_only = (state.get(b"same_domain_only") or b"1").decode("utf-8") == "1"

    queue_key = _QUEUE_KEY(job_id)
    visited_key = _VISITED_KEY(job_id)
    results_key = _RESULTS_KEY(job_id)

    pages_fetched = int((state.get(b"pages_fetched") or b"0").decode("utf-8"))
    error_count = int((state.get(b"error_count") or b"0").decode("utf-8"))

    for _ in range(max_iters):
        # Check if we've hit the limit
        if pages_fetched >= max_pages:
            await redis.hset(_STATE_KEY(job_id), "status", "completed")
            log("crawl.completed", job_id=job_id, pages_fetched=pages_fetched)
            return await crawl_status(redis, job_id)

        # Pop next URL from queue
        item = await redis.rpop(queue_key)
        if not item:
            # Queue empty
            if not await redis.exists(queue_key):
                await redis.hset(_STATE_KEY(job_id), "status", "completed")
                log("crawl.completed", job_id=job_id, pages_fetched=pages_fetched)
            return await crawl_status(redis, job_id)

        try:
            item_data = orjson.loads(item if isinstance(item, bytes) else item.encode("utf-8"))
            url = item_data.get("url", "")
            depth = item_data.get("depth", 0)
        except Exception:
            error_count += 1
            continue

        # Safety: SSRF gate, URL validation
        if not is_safe_external_url(url):
            error_count += 1
            continue

        # Fetch the URL
        result = await fetch_one(deps, url)
        pages_fetched += 1

        # Store result
        if result.get("status") == "ok":
            await redis.rpush(
                results_key,
                orjson.dumps(result).decode("utf-8"),
            )

            # Extract links and enqueue if depth < max_depth
            if depth < max_depth:
                text = result.get("text", "")
                new_links = _extract_links(text, url)
                for link in new_links:
                    # Apply domain filter
                    if same_domain_only and not _same_domain(link, seed_url):
                        continue
                    # Skip if already visited
                    if await redis.sismember(visited_key, link):
                        continue
                    # Enqueue
                    await redis.sadd(visited_key, link)
                    await redis.lpush(
                        queue_key,
                        orjson.dumps({"url": link, "depth": depth + 1}).decode("utf-8"),
                    )

        else:
            # Non-ok fetch
            if result.get("status") != "empty":
                error_count += 1

    # Update counts
    await redis.hset(
        _STATE_KEY(job_id),
        mapping={
            "pages_fetched": str(pages_fetched),
            "error_count": str(error_count),
            "pages_queued": str(await redis.llen(queue_key)),
        },
    )

    return await crawl_status(redis, job_id)
