"""Tests for spider.errors outcome mapping."""

from __future__ import annotations

from spider.errors import (
    RobotsBlockedError,
    SpiderEmptyContentError,
    SpiderFetchError,
    SSRFBlockedError,
    outcome_from_exception,
)


def test_outcome_from_ssrf_blocked() -> None:
    base = {"id": "abc", "url": "http://example.com"}
    out = outcome_from_exception(base, SSRFBlockedError("denied"), ms=12)
    assert out["status"] == "blocked-by-ssrf-gate"
    assert out["error"] == "denied"
    assert out["ms"] == 12


def test_outcome_from_robots_blocked() -> None:
    out = outcome_from_exception({}, RobotsBlockedError(), ms=1)
    assert out["status"] == "blocked-by-robots"


def test_outcome_from_generic_exception() -> None:
    out = outcome_from_exception({"url": "x"}, RuntimeError("boom"), ms=5)
    assert out["status"] == "error"
    assert "RuntimeError" in out["error"]


def test_outcome_from_fetch_error() -> None:
    out = outcome_from_exception({}, SpiderFetchError("timeout"), ms=99)
    assert out["status"] == "error"
    assert out["error"] == "timeout"


def test_outcome_from_empty_content() -> None:
    out = outcome_from_exception({"url": "https://example.com"}, SpiderEmptyContentError(), ms=3)
    assert out["status"] == "empty"
    assert "error" not in out
