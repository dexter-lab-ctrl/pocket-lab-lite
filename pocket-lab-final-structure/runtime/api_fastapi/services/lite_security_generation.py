"""Durable cross-process generation fence for Security progress projections."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import uuid
from typing import Any


_MARKER_NAME = "security-progress-generation.json"


def _state_dir() -> Path:
    configured = str(os.environ.get("POCKETLAB_STATE_DIR") or "").strip()
    if configured:
        return Path(configured).expanduser()
    base = str(os.environ.get("POCKETLAB_BASE_DIR") or "").strip()
    if base:
        return Path(base).expanduser() / "state"
    return Path.home() / "pocket-lab-lite" / "state"


def marker_path() -> Path:
    """Return the marker path outside the replaceable SQLite database."""

    return _state_dir() / ".pocketlab-runtime" / _MARKER_NAME


def read_security_progress_generation() -> dict[str, Any] | None:
    """Read one sanitized marker, returning None for absent or invalid data."""

    path = marker_path()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    generation = str(payload.get("generation") or "").strip()
    if not generation:
        return None
    return {
        "generation": generation,
        "reason": str(payload.get("reason") or "database_projection_refresh")[:64],
        "run_id": str(payload.get("run_id") or "")[:160],
        "sqlite_revision": max(0, int(payload.get("sqlite_revision") or 0)),
        "published_at": str(payload.get("published_at") or "")[:64],
        "sanitized": True,
    }


def publish_security_progress_generation(
    *,
    run_id: str,
    sqlite_revision: int,
    published_at: str,
    reason: str = "database_projection_refresh",
) -> dict[str, Any]:
    """Atomically publish the authoritative restored/rolled-back generation."""

    path = marker_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generation": uuid.uuid4().hex,
        "reason": str(reason or "database_projection_refresh")[:64],
        "run_id": str(run_id or "")[:160],
        "sqlite_revision": max(0, int(sqlite_revision or 0)),
        "published_at": str(published_at or "")[:64],
        "sanitized": True,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{_MARKER_NAME}.",
        suffix=".tmp",
        dir=str(path.parent),
        text=True,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)
    return dict(payload)


__all__ = [
    "marker_path",
    "publish_security_progress_generation",
    "read_security_progress_generation",
]
