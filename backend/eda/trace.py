"""Shared EDA trace logger — writes to ``logs/eda_e2e_trace.log``.

Every EDA component calls ``trace(step, message)`` to emit a timestamped,
structured entry that survives across process boundaries.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

TRACE_LOG_PATH = Path(__file__).resolve().parent.parent.parent / "logs" / "eda_e2e_trace.log"


def _ensure_trace_file() -> None:
    TRACE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not TRACE_LOG_PATH.exists():
        TRACE_LOG_PATH.write_text("", encoding="utf-8")


def trace(step: str, message: str) -> None:
    """Emit one structured trace line."""
    _ensure_trace_file()
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    line = f"[EDA_TRACE][{stamp}][{step}] {message}\n"
    with TRACE_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(line)
