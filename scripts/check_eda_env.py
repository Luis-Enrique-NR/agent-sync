"""Diagnóstico rápido del entorno EDA local — ``python scripts/check_eda_env.py``.

Verifica Python, SQLite, Redis (opcional), feature flags y estado de
dependencias.  Salida formateada con prefijos ``[ENV_OK]``,
``[ENV_WARN]``, ``[ENV_ERROR]``.
"""

from __future__ import annotations

import os
import socket
import sys
from pathlib import Path
from textwrap import dedent

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

EXIT_OK = 0
EXIT_WARN = 0
EXIT_ERROR = 1

OK = "[ENV_OK]    "
WARN = "[ENV_WARN]  "
ERR = "[ENV_ERROR] "

errors: list[str] = []
warnings: list[str] = []


def _check(label: str, condition: bool, err_msg: str, warn_msg: str | None = None) -> None:
    if condition:
        print(f"{OK}{label}")
    elif warn_msg:
        print(f"{WARN}{warn_msg}")
        warnings.append(warn_msg)
    else:
        print(f"{ERR}{err_msg}")
        errors.append(err_msg)


# ── 1. Python version ──────────────────────────────────────────────────

major, minor = sys.version_info[:2]
_check(
    f"Python {major}.{minor}",
    (major, minor) >= (3, 11),
    "Python 3.11+ required",
)

# ── 2. SQLite ──────────────────────────────────────────────────────────

try:
    from persistence.database import init_db
    init_db()
    db_path = BACKEND / "agentsync.db"
    _check(
        f"SQLite initialized ({db_path.name})",
        db_path.exists(),
        "SQLite agentsync.db not created",
    )
except Exception as exc:
    print(f"{ERR}SQLite init failed: {exc}")
    errors.append(str(exc))

# ── 3. Redis (opcional) ────────────────────────────────────────────────

try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2)
    result = sock.connect_ex(("localhost", 6379))
    sock.close()
    if result == 0:
        try:
            import redis as _redis
            r = _redis.Redis(host="localhost", port=6379, socket_connect_timeout=2)
            r.ping()
            print(f"{OK}Redis available (localhost:6379 — PONG)")
        except Exception:
            print(f"{WARN}Redis port open but PING failed")
    else:
        print(f"{WARN}Redis not available on localhost:6379 (tests will skip)")
except Exception:
    print(f"{WARN}Redis check skipped — no socket available")

# ── 4. Dependencies ────────────────────────────────────────────────────

deps = [
    "langgraph", "openai", "pydantic", "sqlmodel", "aiosqlite",
    "fastapi", "httpx", "redis", "pytest",
]
for dep in deps:
    try:
        __import__(dep)
    except ImportError:
        print(f"{ERR}Missing dependency: {dep}")
        errors.append(f"Missing: {dep}")

if not any("Missing" in e for e in errors):
    print(f"{OK}All {len(deps)} dependencies installed")

# ── 5. Feature flags ───────────────────────────────────────────────────

matchmaking = os.getenv("MATCHMAKING_ENABLED", "false").lower()
_check(
    f"MATCHMAKING_ENABLED={matchmaking}",
    matchmaking == "false",
    "MATCHMAKING_ENABLED must be 'false' in this phase",
    f"MATCHMAKING_ENABLED={matchmaking} (should be 'false')",
)

# ── 6. Key packages import check ───────────────────────────────────────

try:
    from eda.handlers import NegotiationHandler  # noqa: F401
    from eda.consumer import consume_forever  # noqa: F401
    from persistence.repository import write_audit  # noqa: F401
    print(f"{OK}Core EDA modules import correctly")
except ImportError as exc:
    print(f"{ERR}EDA import failed: {exc}")
    errors.append(str(exc))

# ── 7. Trace log directory ─────────────────────────────────────────────

log_dir = Path(__file__).resolve().parent.parent / "logs"
log_dir.mkdir(parents=True, exist_ok=True)
trace_file = log_dir / "eda_e2e_trace.log"
_check(
    f"Trace log directory exists ({log_dir})",
    log_dir.is_dir(),
    "logs/ directory not found",
)
if not trace_file.exists():
    trace_file.write_text("# EDA trace log — awaiting first E2E run\n", encoding="utf-8")
print(f"{OK}Trace log ready ({trace_file})")

# ── Verdict ────────────────────────────────────────────────────────────

print()
if not errors:
    print("=" * 60)
    print("  [ENV_OK] Entorno EDA correctamente configurado")
    if warnings:
        print(f"  ({len(warnings)} warning(s) — no bloquean)")
    print("=" * 60)
    sys.exit(EXIT_OK)
else:
    print("=" * 60)
    print(f"  [ENV_ERROR] {len(errors)} error(s) detectados:")
    for e in errors:
        print(f"    - {e}")
    print("=" * 60)
    sys.exit(EXIT_ERROR)
