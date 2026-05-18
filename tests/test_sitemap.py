"""Tests for sitemap parsing."""
from __future__ import annotations

import pytest

from spider.sitemap import sitemap_parse


def _mock_http_response(xml_body: str, status: int = 200):
    """Build a MagicMock that mimics aiohttp's `async with session.get(url)`.

    Key gotcha: session.get(url) returns a context manager synchronously
    (NOT a coroutine), so http.get must be a MagicMock, not AsyncMock.
    The response object itself supports `async with` via __aenter__/__aexit__.
    """
    from unittest.mock import AsyncMock, MagicMock

    response = MagicMock()
    response.status = status
    response.text = AsyncMock(return_value=xml_body)
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=None)

    http = MagicMock()
    http.get = MagicMock(return_value=response)
    return http


@pytest.mark.asyncio
async def test_sitemap_parse_basic():
    """Test parsing a basic sitemap.xml."""
    sitemap_xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.com/page1</loc></url>
  <url><loc>https://example.com/page2</loc></url>
</urlset>
"""
    http = _mock_http_response(sitemap_xml)

    result = await sitemap_parse(http, "https://example.com/sitemap.xml")

    assert result["url"] == "https://example.com/sitemap.xml"
    assert len(result["urls"]) == 2
    assert "https://example.com/page1" in result["urls"]
    assert "https://example.com/page2" in result["urls"]


@pytest.mark.asyncio
async def test_sitemap_parse_index():
    """Test parsing a sitemap_index.xml that points at child sitemaps."""
    from unittest.mock import AsyncMock, MagicMock

    index_xml = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://example.com/sitemap1.xml</loc></sitemap>
</sitemapindex>
"""
    child_xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.com/page</loc></url>
</urlset>
"""

    def _resp(body: str):
        r = MagicMock()
        r.status = 200
        r.text = AsyncMock(return_value=body)
        r.__aenter__ = AsyncMock(return_value=r)
        r.__aexit__ = AsyncMock(return_value=None)
        return r

    http = MagicMock()
    def _get(url, **kwargs):
        return _resp(index_xml if "index" in url else child_xml)
    http.get = _get

    result = await sitemap_parse(http, "https://example.com/sitemap_index.xml")

    # Should have recursed into the child sitemap and found the page URL.
    assert "https://example.com/page" in result["urls"]


@pytest.mark.asyncio
async def test_sitemap_parse_error():
    """Test handling of HTTP errors in sitemap parsing."""
    http = _mock_http_response("", status=404)

    result = await sitemap_parse(http, "https://example.com/missing.xml")

    assert result["count"] == 0
    assert result["errors"]
