"""Sitemap.xml and sitemap_index.xml parsing.

Public surface:
- sitemap_parse(http, url, max_urls, queue, redis) -> dict with discovered URLs
"""

from __future__ import annotations

from typing import Any
from xml.etree import ElementTree as ET

from .log import log
from .security import is_safe_external_url
from .state import enqueue as state_enqueue


async def sitemap_parse(
    http: Any,
    url: str,
    max_urls: int = 1000,
    queue: bool = False,
    redis: Any | None = None,
) -> dict[str, Any]:
    """Parse a sitemap.xml or sitemap_index.xml and optionally enqueue URLs.

    Recurses one level into sitemap indices. Returns dict with:
    {url, urls: [...], queued: bool, count}
    """
    urls: list[str] = []
    errors = []

    async def _fetch_and_parse(sitemap_url: str, depth: int = 0) -> None:
        """Recursively fetch and parse sitemaps."""
        if depth > 1 or len(urls) >= max_urls:
            return

        try:
            async with (
                http.get(
                    sitemap_url,
                    timeout=30,
                    allow_redirects=True,  # aiohttp's kwarg name (httpx uses follow_redirects — different API)
                ) as resp
            ):
                if resp.status != 200:
                    errors.append(f"HTTP {resp.status} from {sitemap_url}")
                    return
                content = await resp.text()
        except Exception as e:
            errors.append(f"{type(e).__name__}: {e}")
            return

        try:
            root = ET.fromstring(content)
        except ET.ParseError as e:
            errors.append(f"XML parse error: {e}")
            return

        # Detect namespace
        ns = {}
        if root.tag.startswith("{"):
            ns_uri = root.tag.split("}")[0][1:]
            ns["ns"] = ns_uri

        # Check if it's a sitemap_index (contains sitemaps)
        index_sitemaps = root.findall(".//ns:sitemap/ns:loc" if ns else ".//sitemap/loc", ns)
        if index_sitemaps:
            # It's an index; recurse into child sitemaps
            for loc_elem in index_sitemaps:
                if loc_elem.text:
                    child_url = loc_elem.text.strip()
                    if is_safe_external_url(child_url):
                        await _fetch_and_parse(child_url, depth=depth + 1)

        # Check if it's a regular sitemap (contains URLs)
        entries = root.findall(".//ns:url/ns:loc" if ns else ".//url/loc", ns)
        for loc_elem in entries:
            if loc_elem.text and len(urls) < max_urls:
                url_str = loc_elem.text.strip()
                if is_safe_external_url(url_str) and url_str not in urls:
                    urls.append(url_str)

    # Parse the initial sitemap
    await _fetch_and_parse(url)

    # Optionally enqueue discovered URLs
    queued_count = 0
    if queue and redis and urls:
        for discovered_url in urls:
            try:
                await state_enqueue(redis, discovered_url, source="sitemap")
                queued_count += 1
            except Exception as e:
                log("sitemap.enqueue_error", error=str(e), url=discovered_url)

    log(
        "sitemap.parse",
        url=url,
        count=len(urls),
        errors=len(errors),
        queued=queued_count if queue else 0,
    )

    return {
        "url": url,
        "urls": urls,
        "count": len(urls),
        "queued": queued_count if queue else 0,
        "errors": errors if errors else None,
    }
