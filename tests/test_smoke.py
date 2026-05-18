"""Smoke tests — verify the bootstrap modules import without side effects.

Real coverage lands with PR 1 (extract/politeness) and PR 2 (queue/feeds).
"""

from __future__ import annotations


def test_main_module_imports():
    """main.py must import — including instantiating the Agent at module scope."""
    import main  # noqa: F401


def test_spider_server_imports():
    """spider_server.py builds an app with a /health route."""
    import spider_server

    app = spider_server.build_app()
    routes = [(r.method, r.resource.canonical) for r in app.router.routes()]
    assert ("GET", "/health") in routes


def test_health_route_returns_ok():
    """/health is the readiness probe for k3s and must return 200 + {ok:true}."""
    import asyncio

    from aiohttp.test_utils import TestClient, TestServer

    import spider_server

    async def _go():
        async with TestServer(spider_server.build_app()) as server, TestClient(server) as client:
            resp = await client.get("/health")
            assert resp.status == 200
            body = await resp.json()
            assert body["ok"] is True
            assert body["service"] == "spider-http"

    asyncio.run(_go())
