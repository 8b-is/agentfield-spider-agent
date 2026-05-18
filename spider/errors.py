"""Domain errors for the spider fetch pipeline.

Flat fetch outcomes use string ``status`` fields (``ok``, ``empty``,
``blocked-by-ssrf-gate``, …). These exceptions let internal code raise
typed failures; ``outcome_from_exception`` maps them back to the dict
shape routes and Redis jobs expect.
"""

from __future__ import annotations

from typing import Any

# Canonical status strings (keep in sync with fetch_one / routes contract).
STATUS_OK = "ok"
STATUS_EMPTY = "empty"
STATUS_ERROR = "error"
STATUS_BLOCKED_SSRF = "blocked-by-ssrf-gate"
STATUS_BLOCKED_ROBOTS = "blocked-by-robots"


class SpiderError(Exception):
    """Base for expected, caller-visible spider failures."""


class SpiderBlockedError(SpiderError):
    """URL rejected before or during fetch (policy / robots)."""

    status: str
    message: str

    def __init__(self, message: str, *, status: str) -> None:
        super().__init__(message)
        self.message = message
        self.status = status

    def __str__(self) -> str:
        return self.message


class SSRFBlockedError(SpiderBlockedError):
    def __init__(self, message: str = "url failed SSRF gate") -> None:
        super().__init__(message, status=STATUS_BLOCKED_SSRF)


class RobotsBlockedError(SpiderBlockedError):
    def __init__(self, message: str = "blocked by robots.txt") -> None:
        super().__init__(message, status=STATUS_BLOCKED_ROBOTS)


class SpiderFetchError(SpiderError):
    """Network, timeout, or page-load failure."""

    status = STATUS_ERROR

    def __init__(self, message: str) -> None:
        super().__init__(message)


class SpiderEmptyContentError(SpiderError):
    """Extracted body below the minimum length threshold."""

    status = STATUS_EMPTY


class SpiderDependencyError(SpiderError):
    """Required optional dependency missing (browser engine, docling, …)."""


class MissingDependencyError(SpiderDependencyError):
    """CloakBrowser binary / package not available."""


class MissingPlaywrightError(SpiderDependencyError):
    """Playwright not installed (Lightpanda CDP client)."""


class DoclingDependencyError(SpiderDependencyError):
    """Docling extra not installed."""


def outcome_from_exception(
    base: dict[str, Any],
    exc: BaseException,
    *,
    ms: int,
    default_status: str = STATUS_ERROR,
) -> dict[str, Any]:
    """Map an exception to a flat fetch-outcome dict."""
    if isinstance(exc, SpiderBlockedError):
        return {**base, "status": exc.status, "error": exc.message, "ms": ms}
    if isinstance(exc, SpiderEmptyContentError):
        return {**base, "status": STATUS_EMPTY, "ms": ms}
    if isinstance(exc, SpiderFetchError):
        return {**base, "status": STATUS_ERROR, "error": str(exc), "ms": ms}
    return {
        **base,
        "status": default_status,
        "error": f"{type(exc).__name__}: {exc}",
        "ms": ms,
    }


__all__ = [
    "STATUS_BLOCKED_ROBOTS",
    "STATUS_BLOCKED_SSRF",
    "STATUS_EMPTY",
    "STATUS_ERROR",
    "STATUS_OK",
    "DoclingDependencyError",
    "MissingDependencyError",
    "MissingPlaywrightError",
    "RobotsBlockedError",
    "SSRFBlockedError",
    "SpiderBlockedError",
    "SpiderDependencyError",
    "SpiderEmptyContentError",
    "SpiderError",
    "SpiderFetchError",
    "outcome_from_exception",
]
