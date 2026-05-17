"""Reasoner-layer wrapper for the spider agent's skills.

The @app.skill() functions in main.py call into this module so the same
logic is reachable from the HTTP surface (spider_server.py) without
duplication. v1 functions land in PR 3 (AgentField skill wiring).
"""
from __future__ import annotations
