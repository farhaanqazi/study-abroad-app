"""
Centralized logging configuration for the Beauty Parlour Chatbot application.

This module sets up:
- Console logging
- File logging with rotation
- Request ID injection for all log records
- Separate log files for general logs and error logs
"""

from __future__ import annotations

import contextvars
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.core.config import get_settings


REQUEST_ID_FALLBACK = "--------"
request_id_ctx_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id",
    default=REQUEST_ID_FALLBACK,
)


class RequestIDFilter(logging.Filter):
    """Inject request_id into all log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        request_id = request_id_ctx_var.get()
        record.request_id = request_id or REQUEST_ID_FALLBACK
        return True


class CompactFormatter(logging.Formatter):
    """Formatter that suppresses tracebacks — for app.log.
    Error.log uses the standard formatter which includes tracebacks.
    """

    def formatException(self, ei) -> str:
        # Suppress traceback entirely
        return ""

    def format(self, record: logging.LogRecord) -> str:
        # Don't include traceback in output
        saved_exc = record.exc_info
        record.exc_info = None
        try:
            return super().format(record)
        finally:
            record.exc_info = saved_exc


class CompactFileHandler(RotatingFileHandler):
    """Custom file handler that suppresses tracebacks by overriding emit().
    Used for app.log to prevent exc_info from being written.
    """

    def emit(self, record: logging.LogRecord) -> None:
        # Temporarily remove exc_info to prevent traceback from being written
        saved_exc = record.exc_info
        saved_exc_text = record.exc_text
        record.exc_info = None
        record.exc_text = None
        try:
            super().emit(record)
        finally:
            record.exc_info = saved_exc
            record.exc_text = saved_exc_text


LOG_JSON_ENV = os.getenv("LOG_JSON", "").lower() in {"1", "true", "yes", "json"}
try:
    from pythonjsonlogger import jsonlogger  # type: ignore
except Exception:
    jsonlogger = None

LOG_JSON_ENABLED = LOG_JSON_ENV and jsonlogger is not None


def setup_logging() -> None:
    """
    Configure application-wide logging.

    Logs are written to both console and files with rotation.
    File structure:
    - logs/app.log: All logs (INFO+ in production, DEBUG+ in development)
    - logs/error.log: Error logs only (ERROR+)
    """
    settings = get_settings()

    # Create logs directory (use absolute path relative to project root)
    # This ensures logs are created in the correct location regardless of CWD
    project_root = Path(__file__).resolve().parent.parent.parent
    log_dir = project_root / "logs"
    log_dir.mkdir(exist_ok=True)

    # Determine log level based on environment
    log_level = logging.DEBUG if settings.debug else logging.INFO

    # === FORMATTERS ===
    if LOG_JSON_ENABLED:
        console_formatter = jsonlogger.JsonFormatter(
            fmt="%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        # JSON mode: app.log gets compact JSON, error.log gets full JSON + traceback
        app_log_formatter = jsonlogger.JsonFormatter(
            fmt="%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        error_formatter = jsonlogger.JsonFormatter(
            fmt="%(asctime)s %(levelname)s %(name)s %(module)s %(funcName)s %(lineno)s %(message)s %(request_id)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    else:
        text_format = "%(asctime)s | %(request_id)s | %(levelname)-8s | %(name)s | %(message)s"
        text_error_format = (
            "%(asctime)s | %(request_id)s | %(levelname)-8s | %(name)s | "
            "%(module)s:%(funcName)s:%(lineno)d | %(message)s"
        )
        console_formatter = logging.Formatter(fmt=text_format, datefmt="%Y-%m-%d %H:%M:%S")
        app_log_formatter = CompactFormatter(fmt=text_format, datefmt="%Y-%m-%d %H:%M:%S")
        error_formatter = logging.Formatter(fmt=text_error_format, datefmt="%Y-%m-%d %H:%M:%S")

    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()

    request_id_filter = RequestIDFilter()

    # Console handler — force utf-8 so emoji/non-ASCII chars don't crash on Windows (cp1252)
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(console_formatter)
    console_handler.addFilter(request_id_filter)
    root_logger.addHandler(console_handler)

    # Main log file handler (all logs, NO tracebacks — compact one-liners)
    app_log_handler = CompactFileHandler(
        filename=log_dir / "app.log",
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    app_log_handler.setLevel(log_level)
    app_log_handler.setFormatter(app_log_formatter)
    app_log_handler.addFilter(request_id_filter)
    root_logger.addHandler(app_log_handler)

    # Error log file handler (ERROR+ ONLY, WITH full tracebacks)
    error_log_handler = RotatingFileHandler(
        filename=log_dir / "error.log",
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    error_log_handler.setLevel(logging.ERROR)
    error_log_handler.setFormatter(error_formatter)
    error_log_handler.addFilter(request_id_filter)
    root_logger.addHandler(error_log_handler)

    # Set specific log levels for third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    # In debug mode, show more verbose SQLAlchemy logs
    if settings.debug:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the specified name.

    Args:
        name: Logger name (typically __name__ of the module)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)
