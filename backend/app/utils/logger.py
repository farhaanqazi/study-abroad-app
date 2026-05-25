from __future__ import annotations

import json
import logging
import time
from contextlib import contextmanager
from typing import Any, Iterator

from app.core.logging_config import LOG_JSON_ENABLED, request_id_ctx_var
from app.utils.log_sanitizer import sanitize_fields, sanitize_text


def set_request_id_context(request_id: str):
    return request_id_ctx_var.set(request_id)


def reset_request_id_context(token) -> None:
    request_id_ctx_var.reset(token)


class StructuredLogger:
    def __init__(self, name: str = "app") -> None:
        self._logger = logging.getLogger(name)

    def debug(self, message: str, **fields: Any) -> None:
        self._log(logging.DEBUG, message, **fields)

    def info(self, message: str, **fields: Any) -> None:
        self._log(logging.INFO, message, **fields)

    def warn(self, message: str, **fields: Any) -> None:
        self._log(logging.WARNING, message, **fields)

    def error(self, message: str, **fields: Any) -> None:
        self._log(logging.ERROR, message, **fields)

    def critical(self, message: str, **fields: Any) -> None:
        self._log(logging.CRITICAL, message, **fields)

    @contextmanager
    def track_operation(self, operation: str, **fields: Any) -> Iterator[None]:
        start = time.monotonic()
        self.info(
            f"{operation} started",
            event="operation_start",
            operation=operation,
            **fields,
        )
        try:
            yield
        except Exception as exc:
            duration_ms = int((time.monotonic() - start) * 1000)
            self.error(
                f"{operation} failed",
                event="operation_failure",
                operation=operation,
                duration_ms=duration_ms,
                error_type=type(exc).__name__,
                error_message=str(exc),
                **fields,
            )
            raise
        else:
            duration_ms = int((time.monotonic() - start) * 1000)
            self.info(
                f"{operation} succeeded",
                event="operation_success",
                operation=operation,
                duration_ms=duration_ms,
                **fields,
            )

    def _log(self, level: int, message: str, **fields: Any) -> None:
        exc_info = fields.pop("exc_info", None)
        event = fields.pop("event", None)

        sanitized_fields = sanitize_fields(fields)
        if event:
            sanitized_fields["event"] = sanitize_text(str(event))

        safe_message = sanitize_text(str(message))

        request_id = request_id_ctx_var.get()
        extra: dict[str, Any] = {"request_id": request_id}
        extra.update(sanitized_fields)

        if sanitized_fields and not LOG_JSON_ENABLED:
            safe_message = f"{safe_message} | {self._format_fields(sanitized_fields)}"

        self._logger.log(level, safe_message, extra=extra, exc_info=exc_info)

    @staticmethod
    def _format_fields(fields: dict[str, Any]) -> str:
        return json.dumps(fields, separators=(",", ":"), default=str)


app_logger = StructuredLogger()
