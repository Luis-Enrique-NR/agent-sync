"""Redaction helpers used before JSON state or audit data is persisted."""

from __future__ import annotations

import json
import re
from typing import Any

_REDACTED = "[REDACTED]"
_SENSITIVE_KEY = re.compile(
    r"(?:^|[_-])(?:password|passwd|secret|token|authorization_token|api[_-]?key|"
    r"access[_-]?token|refresh[_-]?token|private[_-]?key|real[_-]?value|phone|"
    r"telephone|mobile|email|e-mail|address|location|latitude|longitude|"
    r"meeting[_-]?point)(?:$|[_-])",
    re.IGNORECASE,
)
_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_UUID = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)
_ISO_DATE = re.compile(
    r"\b\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)?\b"
)
_PHONE = re.compile(r"(?<![\w-])(?:\+?\d[\d .()\-]{8,}\d)(?![\w-])")


def sanitize_text(value: str, *, max_length: int = 12_000) -> str:
    """Redact common contact values while preserving useful tool context."""

    protected: dict[str, str] = {}

    def protect(match: re.Match[str]) -> str:
        marker = f"__AGENTSYNC_PROTECTED_{len(protected)}__"
        protected[marker] = match.group(0)
        return marker

    redacted = _UUID.sub(protect, value)
    redacted = _ISO_DATE.sub(protect, redacted)
    redacted = _EMAIL.sub(_REDACTED, redacted)
    redacted = _PHONE.sub(_REDACTED, redacted)
    for marker, original in protected.items():
        redacted = redacted.replace(marker, original)
    return redacted[:max_length]


def sanitize_for_persistence(
    value: Any,
    *,
    max_depth: int = 8,
    max_items: int = 200,
    max_string_length: int = 12_000,
) -> Any:
    """Return JSON-safe data with sensitive keys and values removed.

    This is a defense-in-depth boundary, not a replacement for the private vault.
    The function is intentionally deterministic so the same state can be safely
    retried during an idempotent persistence operation.
    """

    if max_depth < 0:
        return _REDACTED
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return sanitize_text(value, max_length=max_string_length)
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= max_items:
                result["_truncated"] = True
                break
            key_text = str(key)
            if _SENSITIVE_KEY.search(key_text) and key_text.lower() != "value_ref":
                result[key_text] = _REDACTED
            else:
                result[key_text] = sanitize_for_persistence(
                    item,
                    max_depth=max_depth - 1,
                    max_items=max_items,
                    max_string_length=max_string_length,
                )
        return result
    if isinstance(value, (list, tuple, set, frozenset)):
        return [
            sanitize_for_persistence(
                item,
                max_depth=max_depth - 1,
                max_items=max_items,
                max_string_length=max_string_length,
            )
            for item in list(value)[:max_items]
        ]
    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError):
        return _REDACTED
    return value
