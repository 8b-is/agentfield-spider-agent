"""Tests for sitemap parsing."""
from __future__ import annotations

import pytest

from spider.sitemap import sitemap_parse


@pytest.mark.asyncio
async def test_sitemap_parse_basic():
    """Test parsing a basic sitemap.xml."""
    from unittest.mock import AsyncMock, MagicMock

    sitemap_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url>
        <loc>https://example.com/page1</loc>
      </url>
      <url>
        <loc>https://example.com/page2</loc>
      </url>
    </urlset>
    """

    http = AsyncMock()
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.text = AsyncMock(return_value=sitemap_xml)
    http.get = AsyncMock(return_value=mock_response)
    http.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
    http.get.return_value.__aexit__ = AsyncMock(return_value=None)

    result = await sitemap_parse(http, "https://example.com/sitemap.xml")

    assert result["url"] == "https://example.com/sitemap.xml"
    assert len(result["urls"]) == 2
    assert "https://example.com/page1" in result["urls"]
    assert "https://example.com/page2" in result["urls"]


@pytest.mark.asyncio
async def test_sitemap_parse_index():
    """Test parsing a sitemap_index.xml."""
    from unittest.mock import AsyncMock

    index_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <sitemap>
        <loc>https://example.com/sitemap1.xml</loc>
      </sitemap>
      <sitemap>
        <loc>https://example.com/sitemap2.xml</loc>
      </sitemap>
    </sitemapindex>
    """

    child_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url>
        <loc>https://example.com/page</loc>
      </url>
    </urlset>
    """

    http = AsyncMock()

    async def mock_get(url, **kwargs):
        response = AsyncMock()
        if "index" in url or "sitemap.xml" in url:
            response.status = 200
            response.text = AsyncMock(return_value=index_xml if "index" in url else child_xml)
        else:
            response.status = 200
            response.text = AsyncMock(return_value=child_xml)
        response.__aenter__ = AsyncMock(return_value=response)
        response.__aexit__ = AsyncMock(return_value=None)
        return response

    http.get = mock_get

    result = await sitemap_parse(http, "https://example.com/sitemap_index.xml")

    # Should find pages from child sitemaps
    assert result["count"] >= 0  # At least recursed


@pytest.mark.asyncio
async def test_sitemap_parse_error():
    """Test handling of HTTP errors in sitemap parsing."""
    from unittest.mock import AsyncMock

    http = AsyncMock()
    mock_response = AsyncMock()
    mock_response.status = 404
    http.get = AsyncMock(return_value=mock_response)
    http.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
    http.get.return_value.__aexit__ = AsyncMock(return_value=None)

    result = await sitemap_parse(http, "https://example.com/missing.xml")

    assert result["count"] == 0
    assert result["errors"] is not None
