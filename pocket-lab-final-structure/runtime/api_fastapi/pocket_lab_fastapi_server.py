# ruff: noqa: E402
#!/usr/bin/env python3
from __future__ import annotations

import os
import pathlib
import sys

# Allow running this file directly from PM2/Termux without installing the
# repository as a package.
HERE = pathlib.Path(__file__).resolve().parent
RUNTIME_DIR = HERE.parent
PROJECT_DIR = RUNTIME_DIR.parent
for path in (str(RUNTIME_DIR), str(PROJECT_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

try:
    from .main import app as app  # noqa: F401
except ImportError:  # pragma: no cover - direct script execution fallback
    from api_fastapi.main import app as app  # noqa: F401

import uvicorn


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def main() -> int:
    host = os.environ.get("POCKETLAB_API_HOST", "127.0.0.1")
    port = _env_int("POCKETLAB_API_PORT", _env_int("API_PORT", 8080))
    uvicorn.run(
        "api_fastapi.main:app",
        host=host,
        port=port,
        log_level=os.environ.get("POCKETLAB_LOG_LEVEL", "info").lower(),
        proxy_headers=True,
        forwarded_allow_ips="*",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
