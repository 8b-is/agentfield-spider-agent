"""agentfield-spider-agent — AgentField skill surface.

Capability (planned, v1 PR sequence):
- agentfield-spider-agent.fetch(url, sync=True, extract=True) -> dict
- agentfield-spider-agent.feed_add(url, interval_s=3600, name=None) -> dict

This bootstrap commit only exposes a ping skill so CI can verify the
canonical agent shape. Real fetch/feeds land in subsequent PRs:

  PR 1: spider/{browser,extract,fetch,routes,politeness,security}.py
  PR 2: spider/{queue,feeds}.py + /fetch async + /feeds + /jobs
  PR 3: main.py @app.skill('fetch','feed_add') + deploy/k3s/

See README.md for full architecture and CLAUDE.md for the contract.
"""
from __future__ import annotations

import logging
import os

from agentfield import Agent

logger = logging.getLogger("spider-agent")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

app = Agent(
    node_id=os.getenv("AGENT_NODE_ID", "spider-agent"),
    agentfield_server=os.getenv("AGENTFIELD_SERVER", "http://localhost:8080"),
    version="0.0.1",
    description="Spider/crawler agent. CloakBrowser-backed page fetch + RSS feeds.",
    dev_mode=True,
)


@app.skill()
async def ping() -> dict:
    """Liveness probe. Returns immediately, no I/O."""
    return {"ok": True, "service": "spider-agent", "version": "0.0.1"}


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8005")),
        auto_port=False,
    )
