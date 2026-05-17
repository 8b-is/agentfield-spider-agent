"""aiohttp HTTP server — rag-stack-compatible :11700 surface.

Bootstrap commit: only /health. PR 1 adds /fetch/sync. PR 2 adds /fetch,
/feeds*, /jobs.

The HTTP surface and the AgentField surface (main.py) run as two services
in compose / two containers in k3s, sharing the same image. Both call into
the shared `spider/` module so the two surfaces never drift.
"""
from __future__ import annotations

import logging
import os

from aiohttp import web

logger = logging.getLogger("spider-http")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


async def health(request: web.Request) -> web.Response:
    """Liveness probe. Static {ok: true}; no Redis or browser checks yet."""
    return web.json_response({"ok": True, "service": "spider-http"})


def build_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/health", health)
    return app


if __name__ == "__main__":
    port = int(os.getenv("CRAWLER_PORT", "11700"))
    logger.info("spider-http starting on :%d", port)
    web.run_app(build_app(), host="0.0.0.0", port=port, access_log=None)
