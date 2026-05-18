"""Tests for chromadb sink."""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

import pytest

from spider.sinks.chroma import (
    _make_doc_id,
    should_sink,
    sink_fetch_outcome,
)


def test_should_sink_disabled():
    """Test that sink is disabled by default."""
    with patch.dict(os.environ, {"SPIDER_SINK_ENABLED": ""}):
        assert not should_sink()


def test_should_sink_enabled():
    """Test sink enabled when env is set."""
    with patch.dict(os.environ, {
        "SPIDER_SINK_ENABLED": "1",
        "SPIDER_SINK_CHROMA_URL": "http://chromadb:8000",
    }):
        # Need to reimport to get new env
        import importlib

        from spider import sinks
        importlib.reload(sinks.chroma)
        from spider.sinks.chroma import should_sink as should_sink_reloaded
        assert should_sink_reloaded()


def test_make_doc_id():
    """Test document ID generation."""
    id1 = _make_doc_id("https://example.com/page1")
    id2 = _make_doc_id("https://example.com/page1")
    id3 = _make_doc_id("https://example.com/page2")

    assert id1 == id2  # Same URL -> same ID
    assert id1 != id3  # Different URL -> different ID
    assert len(id1) == 64  # SHA256 hex


@pytest.mark.asyncio
async def test_sink_fetch_outcome_not_enabled():
    """Test that sink gracefully skips when disabled."""
    from unittest.mock import MagicMock
    http = MagicMock()

    outcome = {
        "status": "ok",
        "url": "https://example.com/page",
        "title": "Page",
        "text": "Content here",
    }

    with patch.dict(os.environ, {"SPIDER_SINK_ENABLED": ""}):
        # Reimport to disable
        import importlib

        from spider import sinks
        importlib.reload(sinks.chroma)
        from spider.sinks.chroma import sink_fetch_outcome as sink_reloaded
        result = await sink_reloaded(http, outcome)
        assert result is False


@pytest.mark.asyncio
async def test_sink_fetch_outcome_non_ok_status():
    """Test that non-ok outcomes are skipped."""
    http = AsyncMock()

    outcome = {
        "status": "error",
        "url": "https://example.com",
        "error": "timeout",
    }

    result = await sink_fetch_outcome(http, outcome)

    assert result is False
    assert not http.post.called


@pytest.mark.asyncio
async def test_sink_fetch_outcome_missing_fields():
    """Test that outcomes with missing fields are skipped."""
    http = AsyncMock()

    outcome = {
        "status": "ok",
        "url": "https://example.com",
        # Missing text
    }

    result = await sink_fetch_outcome(http, outcome)

    assert result is False
