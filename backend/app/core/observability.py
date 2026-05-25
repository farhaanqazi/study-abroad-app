"""Structured logging + correlation-id plumbing for the async worker stack.

This module owns the *structlog* configuration used by the ARQ worker and the
transactional-outbox machinery. It renders JSON to stdout so logs are
machine-parseable in any aggregator, and it threads a correlation id through a
``contextvar`` so a single request / worker job id appears on every log line
emitted while that context is active — without passing the id around manually.

NO ``print`` statements anywhere in the worker stack: ``get_logger`` is the only
sanctioned output channel.
"""

from __future__ import annotations

import contextlib
import logging
import sys
import uuid
from contextvars import ContextVar
from typing import Any, Iterator, Optional

import structlog

# Correlation id for the *current* async context. Bound per-request (by the API
# layer) or per-job (by the worker) and read back into every log event via the
# ``_inject_correlation_id`` processor below.
_correlation_id: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)

_CONFIGURED = False


def get_correlation_id() -> Optional[str]:
    """Return the correlation id bound to the current context, if any."""
    return _correlation_id.get()


def bind_correlation_id(correlation_id: Optional[str] = None) -> str:
    """Bind a correlation id to the current async context.

    If none is supplied a fresh UUID4 hex is generated. Returns the bound id so
    callers can echo it back (e.g. in an HTTP response header). Subsequent log
    lines in this context automatically carry ``correlation_id``.
    """
    cid = correlation_id or uuid.uuid4().hex
    _correlation_id.set(cid)
    return cid


def clear_correlation_id() -> None:
    """Reset the correlation id for the current context."""
    _correlation_id.set(None)


@contextlib.contextmanager
def correlation_scope(correlation_id: Optional[str] = None) -> Iterator[str]:
    """Context manager that binds a correlation id for its duration.

    Used by the worker to scope a job: ``with correlation_scope(job_id): ...``.
    Restores the previous value on exit so nested scopes behave.
    """
    token = _correlation_id.set(correlation_id or uuid.uuid4().hex)
    try:
        yield _correlation_id.get()  # type: ignore[misc]
    finally:
        _correlation_id.reset(token)


def _inject_correlation_id(
    _logger: Any, _method: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """structlog processor: stamp the active correlation id onto every event."""
    cid = _correlation_id.get()
    if cid is not None:
        event_dict.setdefault("correlation_id", cid)
    return event_dict


def configure_logging(*, level: int = logging.INFO, json: bool = True) -> None:
    """Configure structlog (idempotent).

    Renders JSON by default. Routes stdlib ``logging`` through structlog too, so
    third-party libraries (arq, sqlalchemy, asyncpg) share the same JSON sink.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        _inject_correlation_id,
        timestamper,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    renderer: Any = (
        structlog.processors.JSONRenderer()
        if json
        else structlog.dev.ConsoleRenderer(colors=False)
    )

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Bridge stdlib logging into structlog's renderer so library logs are JSON.
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared_processors,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                renderer,
            ],
        )
    )
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

    _CONFIGURED = True


def get_logger(name: Optional[str] = None) -> structlog.stdlib.BoundLogger:
    """Return a configured structlog logger. Configures on first use."""
    if not _CONFIGURED:
        configure_logging()
    return structlog.get_logger(name)
