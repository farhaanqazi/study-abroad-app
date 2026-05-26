"""Unified structured logging for the whole platform (API + ARQ worker).

This is the single source of truth for logging. It uses **structlog rendered
through the stdlib logging backend**, the canonical recipe that gives one
pipeline for *both* our own ``structlog`` calls and third-party stdlib logs
(uvicorn, sqlalchemy, asyncpg, arq, alembic).

Outputs (so you can debug after the fact):
  * **console** — pretty/coloured in development, JSON in production.
  * **logs/app.log** — rotating JSON, everything at the active level. Machine
    parseable (jq, log shippers).
  * **logs/error.log** — rotating JSON, ERROR+ only, with full tracebacks, for
    fast triage.

Cross-cutting context:
  * ``request_id`` is bound per HTTP request (middleware) and ``correlation_id``
    per worker job; both are stamped onto every log line emitted in that context
    via ``contextvars`` — no manual threading.
  * Secrets/tokens are redacted by a processor; emails/phones are kept for
    debuggability (see :func:`app.utils.log_sanitizer.redact_log_event`).

``get_logger`` is the only sanctioned output channel — never ``print``.
"""

from __future__ import annotations

import contextlib
import logging
import os
import sys
import uuid
from contextvars import ContextVar
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Iterator, Optional

import structlog

from app.utils.log_sanitizer import redact_log_event

# Correlation id for the current async context (worker job ids, or any non-HTTP
# scope). HTTP requests use request_id via contextvars; both are merged onto logs.
_correlation_id: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)

_CONFIGURED = False

# backend/logs — anchored to this file, so it's stable regardless of CWD.
_LOG_DIR = Path(__file__).resolve().parents[2] / "logs"
_MAX_BYTES = 10 * 1024 * 1024  # 10 MB per file
_BACKUP_COUNT = 5


# --------------------------------------------------------------------------- #
# Correlation id (worker jobs / non-request scopes)
# --------------------------------------------------------------------------- #
def get_correlation_id() -> Optional[str]:
    """Return the correlation id bound to the current context, if any."""
    return _correlation_id.get()


def bind_correlation_id(correlation_id: Optional[str] = None) -> str:
    """Bind a correlation id to the current async context (returns the id)."""
    cid = correlation_id or uuid.uuid4().hex
    _correlation_id.set(cid)
    return cid


def clear_correlation_id() -> None:
    """Reset the correlation id for the current context."""
    _correlation_id.set(None)


@contextlib.contextmanager
def correlation_scope(correlation_id: Optional[str] = None) -> Iterator[str]:
    """Bind a correlation id for the duration of a block (e.g. a worker job)."""
    token = _correlation_id.set(correlation_id or uuid.uuid4().hex)
    try:
        yield _correlation_id.get()  # type: ignore[misc]
    finally:
        _correlation_id.reset(token)


# --------------------------------------------------------------------------- #
# Request context (HTTP requests) — bound by middleware via structlog contextvars
# --------------------------------------------------------------------------- #
def bind_request_context(**values: Any) -> None:
    """Bind key/values (e.g. ``request_id``) onto every log line in this context."""
    structlog.contextvars.bind_contextvars(**values)


def clear_request_context() -> None:
    """Clear all contextvars bound for the current request/scope."""
    structlog.contextvars.clear_contextvars()


# --------------------------------------------------------------------------- #
# Processors
# --------------------------------------------------------------------------- #
def _inject_correlation_id(
    _logger: Any, _method: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """Stamp the active correlation id onto every event."""
    cid = _correlation_id.get()
    if cid is not None:
        event_dict.setdefault("correlation_id", cid)
    return event_dict


def _sanitize(_logger: Any, _method: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Redact secrets/tokens from the event dict (keeps emails/phones)."""
    return redact_log_event(event_dict)


def _resolve_json(settings: Any) -> bool:
    """Decide console rendering: JSON in prod or when LOG_JSON is truthy."""
    override = os.getenv("LOG_JSON", "").strip().lower()
    if override in {"1", "true", "yes", "json"}:
        return True
    if override in {"0", "false", "no", "console"}:
        return False
    env = getattr(settings, "environment", "development") if settings else "development"
    return str(env).strip().lower() == "production"


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
def configure_logging(settings: Any = None, *, force: bool = False) -> None:
    """Configure structlog + stdlib logging (idempotent).

    Call once at process startup (API lifespan / worker startup). Safe to call
    again with ``force=True`` to reconfigure (e.g. after settings load).
    """
    global _CONFIGURED
    if _CONFIGURED and not force:
        return

    if settings is None:
        # Avoid a hard import cycle at module import time.
        from app.core.config import get_settings

        settings = get_settings()

    level = logging.DEBUG if getattr(settings, "debug", False) else logging.INFO
    json_console = _resolve_json(settings)

    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)

    # Processors shared by our structlog calls AND foreign (stdlib) records.
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        _inject_correlation_id,
        _sanitize,
        timestamper,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    # structlog → stdlib: end the chain with wrap_for_formatter so records flow
    # to the stdlib handlers below (one set of handlers for everything).
    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    console_renderer: Any = (
        structlog.processors.JSONRenderer()
        if json_console
        else structlog.dev.ConsoleRenderer(colors=sys.stdout.isatty())
    )
    file_renderer = structlog.processors.JSONRenderer()  # files are always JSON

    def _formatter(renderer: Any) -> structlog.stdlib.ProcessorFormatter:
        return structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared_processors,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                renderer,
            ],
        )

    # Console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(_formatter(console_renderer))
    console_handler.setLevel(level)

    # Files (rotating, JSON). Created lazily; never fail boot if the dir can't
    # be made (e.g. read-only FS) — console logging still works.
    handlers: list[logging.Handler] = [console_handler]
    try:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)

        app_file = RotatingFileHandler(
            _LOG_DIR / "app.log", maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8"
        )
        app_file.setFormatter(_formatter(file_renderer))
        app_file.setLevel(level)

        error_file = RotatingFileHandler(
            _LOG_DIR / "error.log", maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8"
        )
        error_file.setFormatter(_formatter(file_renderer))
        error_file.setLevel(logging.ERROR)

        handlers.extend([app_file, error_file])
    except OSError:
        logging.getLogger(__name__).warning("file logging disabled: log dir not writable")

    root = logging.getLogger()
    root.handlers = handlers
    root.setLevel(level)

    # Third-party noise control. Let uvicorn/arq propagate to root (one pipeline)
    # by clearing their own handlers.
    for noisy, lvl in (
        ("uvicorn.access", logging.WARNING),
        ("uvicorn.error", logging.INFO),
        ("httpx", logging.WARNING),
        ("httpcore", logging.WARNING),
        ("sqlalchemy.engine", logging.INFO if getattr(settings, "debug", False) else logging.WARNING),
    ):
        logging.getLogger(noisy).setLevel(lvl)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        lg.handlers = []
        lg.propagate = True

    _CONFIGURED = True


def get_logger(name: Optional[str] = None) -> structlog.stdlib.BoundLogger:
    """Return a configured structlog logger. Configures logging on first use."""
    if not _CONFIGURED:
        configure_logging()
    return structlog.get_logger(name)
