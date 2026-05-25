from __future__ import annotations

import re
from typing import Any


REDACTED = "[REDACTED]"

SENSITIVE_KEYS = {
    "password",
    "token",
    "api_key",
    "secret",
    "authorization",
    "credential",
}
SENSITIVE_KEYS_COMPACT = {re.sub(r"[^a-z0-9]", "", key) for key in SENSITIVE_KEYS}

BEARER_TOKEN_RE = re.compile(r"(?i)(Bearer\s+)([A-Za-z0-9\-._~+/]+=*)")
API_KEY_RE = re.compile(
    r"(?i)\b(api[-_]?key|token|secret|authorization|credential)\b\s*[:=]\s*([A-Za-z0-9\-._~+/]{6,})"
)
CARD_NUMBER_RE = re.compile(r"\b(?:\d[ -]*?){13,19}\b")

# PII patterns to redact in log output
PHONE_RE = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")


def sanitize_text(text: str) -> str:
    sanitized = BEARER_TOKEN_RE.sub(r"\1[REDACTED]", text)
    sanitized = API_KEY_RE.sub(lambda m: f"{m.group(1)}=[REDACTED]", sanitized)
    sanitized = CARD_NUMBER_RE.sub("[REDACTED_CARD]", sanitized)
    # PII redaction (phone numbers and emails)
    sanitized = PHONE_RE.sub("[PHONE_REDACTED]", sanitized)
    sanitized = EMAIL_RE.sub("[EMAIL_REDACTED]", sanitized)
    return sanitized


def sanitize_value(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            key_lower = str(key).lower()
            key_compact = re.sub(r"[^a-z0-9]", "", key_lower)
            if key_lower in SENSITIVE_KEYS or key_compact in SENSITIVE_KEYS_COMPACT:
                sanitized[key] = REDACTED
            else:
                sanitized[key] = sanitize_value(item)
        return sanitized
    if isinstance(value, list):
        return [sanitize_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(sanitize_value(item) for item in value)
    if isinstance(value, set):
        return {sanitize_value(item) for item in value}
    if isinstance(value, str):
        return sanitize_text(value)
    return value


def sanitize_fields(fields: dict[str, Any]) -> dict[str, Any]:
    return sanitize_value(fields)
