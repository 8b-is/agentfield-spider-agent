"""Unit tests for fetch_one typed error mapping."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from spider.fetch import fetch_one


@pytest.fixture
def fetch_deps(make_deps):
    deps, page = make_deps()
    return deps, page


@pytest.mark.asyncio
async def test_fetch_one_ssrf_blocked(fetch_deps, monkeypatch) -> None:
    deps, _ = fetch_deps
    monkeypatch.setattr(
        "spider.fetch.is_safe_external_url_with_dns",
        AsyncMock(return_value=False),
    )
    out = await fetch_one(deps, "https://example.com/page")
    assert out["status"] == "blocked-by-ssrf-gate"
    assert out["error"] == "url failed SSRF gate"


@pytest.mark.asyncio
async def test_fetch_one_robots_blocked(fetch_deps, monkeypatch) -> None:
    deps, _ = fetch_deps
    from spider import politeness

    async def _deny(_self: politeness.RobotsCache, _url: str) -> bool:
        return False

    monkeypatch.setattr(politeness.RobotsCache, "allowed", _deny)
    out = await fetch_one(deps, "https://example.com/page")
    assert out["status"] == "blocked-by-robots"
    assert out["error"] == "blocked by robots.txt"


@pytest.mark.asyncio
async def test_fetch_one_empty_content(make_deps, make_page) -> None:
    deps, _ = make_deps(make_page(text="short"))
    out = await fetch_one(deps, "https://example.com/short")
    assert out["status"] == "empty"
