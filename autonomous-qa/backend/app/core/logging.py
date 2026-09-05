"""Structured logging configuration using structlog.

Sensitive fields (api keys, passwords, tokens, cookies, authorization
headers) are redacted before any log line is emitted.
"""
from __future__ import annotations

import logging
import sys
from collections.abc import MutableMapping
from typing import Any

import structlog

from app.core.config import get_settings

_SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "groq_api_key",
    "password",
    "token",
    "access_token",
    "refresh_token",
    "cookie",
    "cookies",
    "authorization",
    "jwt_secret",
    "secret",
}


def _redact_processor(
    _logger: Any, _method_name: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    for key in list(event_dict.keys()):
        if key.lower() in _SENSITIVE_KEYS:
            event_dict[key] = "***REDACTED***"
    return event_dict


def configure_logging() -> None:
    settings = get_settings()
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            _redact_processor,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> Any:
    return structlog.get_logger(name)
