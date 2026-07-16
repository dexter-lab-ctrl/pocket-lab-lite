from __future__ import annotations

import errno
import os
from pathlib import Path
from typing import Final

from .. import deps

STORAGE_FAILPOINTS: Final[frozenset[str]] = frozenset(
    {
        "sqlite_lifecycle_write",
        "compatibility_json_write",
        "security_evidence_write",
        "atomic_temp_write",
        "atomic_fsync",
        "atomic_replace",
        "backup_output_write",
    }
)

_TRUE = {"1", "true", "yes", "on"}
_UNSAFE_PARTS = ("/storage/emulated/", "/sdcard/", "/mnt/sdcard/")


def _enabled() -> bool:
    return os.environ.get("POCKETLAB_GATE_FAULT_INJECTION", "").strip().lower() in _TRUE


def _isolated_test_authorized() -> bool:
    """Authorize storage failpoints only inside an explicit isolated gate root.

    This path is intentionally process-local. The public Lite API and frontend
    cannot set these environment variables on a running process. Group 4 runs
    deterministic probes in a dedicated subprocess with a temporary state dir.
    """
    if not _enabled():
        return False
    if os.environ.get("POCKETLAB_GATE_STORAGE_TEST_MODE", "").strip().lower() not in _TRUE:
        return False
    root_text = os.environ.get("POCKETLAB_GATE_ISOLATED_ROOT", "").strip()
    if not root_text:
        return False
    root = Path(root_text).expanduser().resolve(strict=False)
    state = Path(os.environ.get("POCKETLAB_STATE_DIR", str(deps.settings().state_dir))).expanduser().resolve(strict=False)
    normalized = state.as_posix().lower()
    if any(part in normalized for part in _UNSAFE_PARTS):
        return False
    return state == root or root in state.parents


def configured_failpoint() -> str:
    value = os.environ.get("POCKETLAB_GATE_STORAGE_FAILPOINT", "").strip().lower()
    return value if value in STORAGE_FAILPOINTS else ""


def storage_failpoint_active(name: str) -> bool:
    normalized = str(name or "").strip().lower()
    return normalized in STORAGE_FAILPOINTS and normalized == configured_failpoint() and _isolated_test_authorized()


def raise_if_storage_fault(name: str) -> None:
    """Raise a realistic ENOSPC only for an allowlisted isolated gate probe."""
    if storage_failpoint_active(name):
        raise OSError(errno.ENOSPC, "No space left on device")
