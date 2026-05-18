"""Tests for crawl module."""

from __future__ import annotations

import pytest

from spider.crawl import (
    _extract_links,
    _same_domain,
    crawl_start,
    crawl_status,
)


@pytest.mark.asyncio
async def test_crawl_start():
    """Test crawl job creation."""
    from unittest.mock import AsyncMock

    redis = AsyncMock()
    redis.hset = AsyncMock()
    redis.delete = AsyncMock()
    redis.lpush = AsyncMock()
    redis.sadd = AsyncMock()

    job_id = await crawl_start(
        redis,
        "https://example.com",
        max_depth=2,
        max_pages=10,
    )

    assert job_id
    assert redis.hset.called
    assert redis.lpush.called
    assert redis.sadd.called


@pytest.mark.asyncio
async def test_crawl_status():
    """Test fetching crawl status."""
    from unittest.mock import AsyncMock

    redis = AsyncMock()
    redis.hgetall = AsyncMock(
        return_value={
            b"status": b"queued",
            b"seed_url": b"https://example.com",
            b"pages_fetched": b"0",
            b"pages_queued": b"1",
            b"error_count": b"0",
            b"started_at": b"123.45",
        }
    )

    status = await crawl_status(redis, "job-123")

    assert status["job_id"] == "job-123"
    assert status["status"] == "queued"
    assert status["pages_fetched"] == 0


@pytest.mark.asyncio
async def test_crawl_status_not_found():
    """Test status for non-existent job."""
    from unittest.mock import AsyncMock

    redis = AsyncMock()
    redis.hgetall = AsyncMock(return_value={})

    status = await crawl_status(redis, "nonexistent")

    assert status["status"] == "not_found"


def test_extract_links():
    """Test HTML link extraction."""
    html = """
    <html>
    <a href="/page1">Page 1</a>
    <a href="https://other.com">Other</a>
    <a href="javascript:void(0)">JS Link</a>
    </html>
    """

    links = _extract_links(html, "https://example.com")

    assert "https://example.com/page1" in links
    assert "https://other.com" in links
    # JS and mailto links should be filtered out


def test_same_domain():
    """Test domain comparison."""
    assert _same_domain("https://example.com/page1", "https://example.com/page2")
    assert _same_domain("https://example.com", "http://example.com")
    assert not _same_domain("https://example.com", "https://other.com")
