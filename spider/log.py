"""Tiny structured-log helper.

Same shape as rag-stack's ``log()`` so log lines from the spider agent
are diff-friendly with the existing crawler when both are deployed.
"""

from __future__ import annotations

import logging
from typing import Any

from .errors import SpiderBlockedError, SpiderError

_logger = logging.getLogger("spider")


def log_exception(
    action: str,
    exc: BaseException,
    *,
    level: int = logging.WARNING,
    **fields: Any,
) -> None:
    """Log an exception with structured fields and a short message."""
    err_type = type(exc).__name__
    err_msg = str(exc)
    if isinstance(exc, SpiderError):
        fields.setdefault("spider_error", err_type)
    if isinstance(exc, SpiderBlockedError):
        fields.setdefault("status", exc.status)
    log(action, level=level, error_type=err_type, error=err_msg, **fields)


def log(action: str, **fields: Any) -> None:
    """Emit ``action k1=v1 k2=v2`` style log lines.

    Pass ``level=logging.WARNING`` (etc.) to change severity. String values
    longer than 80 chars are truncated. Whitespace-containing strings are
    quoted. Newlines are flattened to spaces.
    """
    level = int(fields.pop("level", logging.INFO))
    parts = []
    for k, v in fields.items():
        if isinstance(v, str):
            v = v.replace("\n", " ")
            if len(v) > 80:
                v = v[:77] + "..."
            if " " in v or "\t" in v:
                v = f'"{v}"'
        parts.append(f"{k}={v}")
    msg = f"{action:14s} {' '.join(parts)}"
    _logger.log(level, msg)
