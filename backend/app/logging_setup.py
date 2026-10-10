"""Structured logging (JSON in production, readable console in development).

Secrets never reach the logs: request logging records method, path, status,
latency and ids only (no headers, cookies, bodies or query strings), and
``redact`` masks known sensitive keys in event dictionaries.
"""

from __future__ import annotations

import logging
import sys

import structlog

from app.config import settings

SENSITIVE = ("password", "secret", "token", "authorization", "cookie", "api_key", "access_key")


def redact(_, __, event_dict):
    for key in list(event_dict):
        if any(s in key.lower() for s in SENSITIVE):
            event_dict[key] = "***"
    return event_dict


def configure_logging() -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level, force=True)
    for noisy in ("uvicorn.access", "botocore", "urllib3", "s3transfer"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    renderer = (
        structlog.processors.JSONRenderer()
        if settings.is_production
        else structlog.dev.ConsoleRenderer(colors=False)
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            redact,
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
