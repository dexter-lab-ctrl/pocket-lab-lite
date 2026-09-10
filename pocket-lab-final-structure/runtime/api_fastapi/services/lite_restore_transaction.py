from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .. import deps
from . import lite_security_policy as policy
from .lite_backup_policy import backup_layout

RESTORE_PHASES = (
    "created",
    "checkpointing",
    "checkpoint_ready",
    "staging",
    "staged",
    "validating_staged",
    "ready_to_promote",
    "promoting",
    "validating_active",
    "post_restore_validation",
    "committed",
    "rollback_started",
    "rollback_validating",
    "rolled_back",
    "rollback_failed",
)
TERMINAL_PHASES = frozenset({"committed", "rolled_back", "rollback_failed"})
UNSAFE_RECOVERY_PHASES = frozenset(
    {
        "promoting",
        "validating_active",
        "rollback_started",
        "rollback_validating",
    }
)
PRE_PROMOTION_PHASES = frozenset(
    {
        "created",
        "checkpointing",
        "checkpoint_ready",
        "staging",
        "staged",
        "validating_staged",
        "ready_to_promote",
    }
)
FAULT_POINTS = frozenset(
    {
        "after_checkpoint",
        "after_staging",
        "after_staged_validation",
        "before_first_promotion",
        "after_first_promotion",
        "after_sqlite_promotion",
        "before_active_validation",
        "during_active_validation",
        "before_commit",
        "during_rollback",
        "after_rollback_promotion",
    }
)
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,119}$")
_SAFE_STAGING_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$")
_GUARD_CACHE_LOCK = threading.Lock()
_GUARD_CACHE_ROOT = ""
_GUARD_CACHE_SIGNATURE: tuple[tuple[str, int, int], ...] = ()
_GUARD_CACHE_VALUE: tuple[dict[str, Any], ...] | None = None


class RestoreTransactionError(RuntimeError):
    """Base restore transaction error with a safe public category."""

    category = "restore_transaction_failed"


class RestoreFaultInjected(RestoreTransactionError):
    category = "test_fault_injected"

    def __init__(self, point: str) -> None:
        self.point = point
        super().__init__(f"Deterministic restore test fault at {point}")


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_id(value: str) -> str:
    text = str(value or "").strip()
    if not _SAFE_ID.fullmatch(text):
        raise RestoreTransactionError("Restore identifier is invalid")
    return text


def restore_transaction_root() -> Path:
    root = deps.settings().state_dir / "security" / "recovery" / "restore-transactions"
    root.mkdir(parents=True, exist_ok=True)
    return root


def restore_transaction_dir(restore_id: str) -> Path:
    return restore_transaction_root() / _safe_id(restore_id)


def restore_journal_path(restore_id: str) -> Path:
    return restore_transaction_dir(restore_id) / "journal.json"


def checkpoint_database_path(restore_id: str) -> Path:
    return restore_transaction_dir(restore_id) / "checkpoint" / "pocketlab-lite.sqlite3"


def staged_database_path(restore_id: str) -> Path:
    return restore_transaction_dir(restore_id) / "staging" / "pocketlab-lite.sqlite3"


def restore_staging_dir(staging_key: str) -> Path:
    """Return the registered restic staging directory for a journal.

    The key is stored in the journal instead of a private absolute path.  The
    resolved destination is still constrained to the configured staging root
    so startup recovery can clean an interrupted restic restore without
    trusting path data from a journal or an API request.
    """
    key = str(staging_key or "").strip()
    if not _SAFE_STAGING_KEY.fullmatch(key):
        raise RestoreTransactionError("Restore staging identifier is invalid")
    root = backup_layout().staging.resolve()
    candidate = (root / key).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise RestoreTransactionError("Restore staging directory is outside the registered staging root") from exc
    return candidate


def cleanup_restore_staging(staging_key: str) -> bool:
    """Remove only the registered staging directory for an interrupted restore."""
    target = restore_staging_dir(staging_key)
    if not target.exists():
        return False
    if target.is_symlink() or not target.is_dir():
        raise RestoreTransactionError("Restore staging directory is not a safe directory")
    shutil.rmtree(target)
    return True


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    descriptor = os.open(str(path), flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def atomic_write_json(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    """Durably write a sanitized JSON object with file and parent fsync."""
    clean = policy.redact_value(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(clean, handle, indent=2, sort_keys=True, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
    return clean


def read_journal(restore_id: str) -> dict[str, Any] | None:
    try:
        path = restore_journal_path(restore_id)
    except RestoreTransactionError:
        return None
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return policy.redact_value(payload) if isinstance(payload, dict) else None


def create_journal(
    *,
    restore_id: str,
    backup_id: str,
    preview_id: str,
    target_names: Iterable[str],
    preflight: bool = False,
    snapshot_id: str | None = None,
    manifest_checksum: str | None = None,
    staging_key: str | None = None,
) -> dict[str, Any]:
    restore_id = _safe_id(restore_id)
    stage = "restic_restore" if preflight else "database_restore"
    if staging_key is not None:
        staging_key = str(staging_key).strip()
        if not _SAFE_STAGING_KEY.fullmatch(staging_key):
            raise RestoreTransactionError("Restore staging identifier is invalid")
    if preflight and not staging_key:
        raise RestoreTransactionError("Preflight restore journal requires a staging identifier")
    directory = restore_transaction_dir(restore_id)
    directory.mkdir(parents=True, exist_ok=False)
    now = _utc()
    targets = [str(item)[:120] for item in target_names]
    payload: dict[str, Any] = {
        "journal_version": 1,
        "restore_id": restore_id,
        "backup_id": str(backup_id)[:120],
        "preview_id": str(preview_id)[:120],
        "restore_stage": stage,
        "preflight": bool(preflight),
        "checkpoint_id": f"checkpoint-{restore_id}",
        "phase": "created",
        "status": "running",
        "terminal_status": None,
        "pending_paths": targets,
        "promoted_paths": [],
        "active_hashes": {},
        "staged_hashes": {},
        "checkpoint_hashes": {},
        "checkpoint_metadata": {},
        "rollback_attempt_count": 0,
        "failure_category": None,
        "restore_failure_category": None,
        "rollback_failure_category": None,
        "api_worker_restart_allowed": False,
        "created_at": now,
        "updated_at": now,
        "events": [
            {
                "phase": "created",
                "at": now,
                "summary": "Restore transaction created.",
            }
        ],
        "sanitized": True,
    }
    if snapshot_id:
        payload["snapshot_id"] = str(snapshot_id)[:120]
    if manifest_checksum:
        payload["manifest_checksum"] = str(manifest_checksum)[:128]
    if staging_key:
        payload["staging_key"] = staging_key
    return atomic_write_json(restore_journal_path(restore_id), payload)


def update_journal(
    restore_id: str,
    *,
    phase: str | None = None,
    summary: str | None = None,
    event: bool = True,
    **updates: Any,
) -> dict[str, Any]:
    current = read_journal(restore_id)
    if not current:
        raise RestoreTransactionError("Restore journal is unavailable")
    if phase is not None and phase not in RESTORE_PHASES:
        raise RestoreTransactionError("Restore phase is invalid")
    payload = dict(current)
    if phase is not None:
        payload["phase"] = phase
    if summary is not None:
        payload["summary"] = str(summary)[:240]
    payload.update(updates)
    payload["updated_at"] = _utc()
    if event and (phase is not None or summary):
        events = list(payload.get("events") or [])[-199:]
        events.append(
            {
                "phase": phase or payload.get("phase"),
                "at": payload["updated_at"],
                "summary": str(summary or "Restore transaction updated.")[:240],
            }
        )
        payload["events"] = events
    return atomic_write_json(restore_journal_path(restore_id), payload)


def list_journals(*, include_terminal: bool = True) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in restore_transaction_root().glob("*/journal.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {
                "restore_id": path.parent.name[:120],
                "phase": "rollback_failed",
                "status": "failed",
                "terminal_status": "rollback_failed",
                "failure_category": "restore_journal_unreadable",
                "api_worker_restart_allowed": False,
                "updated_at": _utc(),
                "summary": "Restore journal is unreadable. Database writers remain blocked.",
                "sanitized": True,
            }
        if not isinstance(payload, dict):
            continue
        if not include_terminal and payload.get("phase") in TERMINAL_PHASES:
            continue
        items.append(policy.redact_value(payload))
    return sorted(items, key=lambda item: str(item.get("updated_at") or ""), reverse=True)


def unresolved_journals() -> list[dict[str, Any]]:
    # rollback_failed is terminal for the operation but intentionally remains
    # an unresolved startup/write guard until an operator repairs it.
    return [
        item
        for item in list_journals(include_terminal=True)
        if item.get("phase") not in {"committed", "rolled_back"}
    ]


def _compact_guard_journals() -> list[dict[str, Any]]:
    """Read only the small fail-closed guard contract for scheduler pressure.

    Full journal views contain bounded-but-large checkpoint/hash/event payloads
    and are intentionally hydrated only by explicit recovery/history reads. The
    scheduler asks whether writers must remain fenced on every admission pass;
    recursively redacting every journal there can monopolize the scheduler lock
    on Termux. Parse each journal once per file signature and retain only the
    fields required to enforce the startup/restart guard.
    """
    global _GUARD_CACHE_ROOT, _GUARD_CACHE_SIGNATURE, _GUARD_CACHE_VALUE
    root = restore_transaction_root()
    paths = sorted(root.glob("*/journal.json"), key=lambda item: item.parent.name)
    signature: tuple[tuple[str, int, int], ...] = tuple(
        (
            path.parent.name[:120],
            int(path.stat().st_size),
            int(path.stat().st_mtime_ns),
        )
        for path in paths
        if path.is_file()
    )
    root_key = str(root)
    with _GUARD_CACHE_LOCK:
        if (
            _GUARD_CACHE_VALUE is not None
            and _GUARD_CACHE_ROOT == root_key
            and _GUARD_CACHE_SIGNATURE == signature
        ):
            return [dict(item) for item in _GUARD_CACHE_VALUE]

    compact: list[dict[str, Any]] = []
    for path in paths:
        restore_id = path.parent.name[:120]
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("restore journal is not an object")
            phase = str(payload.get("phase") or "")[:64]
            if phase not in RESTORE_PHASES:
                raise ValueError("restore journal phase is invalid")
            compact.append(
                {
                    "restore_id": str(payload.get("restore_id") or restore_id)[:120],
                    "phase": phase,
                    "api_worker_restart_allowed": bool(
                        payload.get("api_worker_restart_allowed")
                    ),
                    "updated_at": str(payload.get("updated_at") or "")[:64],
                }
            )
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            # An unreadable guard journal is itself an unresolved rollback
            # condition. Never let a malformed journal make writers appear safe.
            compact.append(
                {
                    "restore_id": restore_id,
                    "phase": "rollback_failed",
                    "api_worker_restart_allowed": False,
                    "updated_at": "",
                }
            )
    compact.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
    with _GUARD_CACHE_LOCK:
        _GUARD_CACHE_ROOT = root_key
        _GUARD_CACHE_SIGNATURE = signature
        _GUARD_CACHE_VALUE = tuple(dict(item) for item in compact)
    return [dict(item) for item in compact]


def guard_status() -> dict[str, Any]:
    # This path is queried by projection admission and maintenance readiness;
    # keep it bounded and free of full public-journal redaction/hydration.
    unresolved = [
        item
        for item in _compact_guard_journals()
        if item.get("phase") not in {"committed", "rolled_back"}
    ]
    rollback_failed = [item for item in unresolved if item.get("phase") == "rollback_failed"]
    active = unresolved[0] if unresolved else None
    return {
        "unresolved": bool(unresolved),
        "rollback_failed": bool(rollback_failed),
        "restore_id": active.get("restore_id") if active else None,
        "phase": active.get("phase") if active else "ready",
        "api_worker_restart_allowed": bool(
            not unresolved
            or all(item.get("api_worker_restart_allowed") is True for item in unresolved)
        ),
        "summary": (
            "Recovery needs operator attention. Database writers remain blocked."
            if rollback_failed
            else "Restore recovery is in progress."
            if unresolved
            else "No unresolved restore transaction."
        ),
        "sanitized": True,
    }


def fault_injection_enabled() -> bool:
    return str(os.environ.get("POCKETLAB_LITE_ENABLE_S8_GATE_FAULTS", "0")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def configured_fault_point() -> str | None:
    if not fault_injection_enabled():
        return None
    point = str(os.environ.get("POCKETLAB_LITE_S8_FAULT_POINT", "")).strip()
    if not point:
        return None
    if point not in FAULT_POINTS:
        raise RestoreTransactionError("Configured restore test fault point is invalid")
    return point


def inject_fault(point: str) -> None:
    if point not in FAULT_POINTS:
        raise RestoreTransactionError("Restore test fault point is invalid")
    if configured_fault_point() == point:
        raise RestoreFaultInjected(point)


def safe_failure_category(error: BaseException) -> str:
    if isinstance(error, RestoreFaultInjected):
        return error.category
    text = type(error).__name__.lower()
    if "space" in str(error).lower():
        return "insufficient_space"
    if "checksum" in str(error).lower() or "hash" in str(error).lower():
        return "validation_checksum_failed"
    if "migration" in str(error).lower() or "schema" in str(error).lower():
        return "validation_schema_failed"
    if "integrity" in str(error).lower() or "database" in text or "sqlite" in text:
        return "database_validation_failed"
    if "parity" in str(error).lower() or "projection" in str(error).lower():
        return "canonical_parity_failed"
    if "permission" in text:
        return "filesystem_permission_failed"
    return "restore_operation_failed"


def public_journal_view(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    rollback = payload.get("rollback") if isinstance(payload.get("rollback"), dict) else {}
    return policy.redact_value(
        {
            "restore_id": payload.get("restore_id"),
            "backup_id": payload.get("backup_id"),
            "preview_id": payload.get("preview_id"),
            "checkpoint_id": payload.get("checkpoint_id"),
            "restore_stage": payload.get("restore_stage"),
            "preflight": bool(payload.get("preflight")),
            "phase": payload.get("phase"),
            "status": payload.get("status"),
            "terminal_status": payload.get("terminal_status"),
            "rollback_status": rollback.get("status") or payload.get("rollback_status"),
            "rollback_attempt_count": int(payload.get("rollback_attempt_count") or 0),
            "failure_category": payload.get("failure_category"),
            "failure_stage": payload.get("restore_failure_stage"),
            "validation_checks": payload.get("restore_validation_checks")
            if isinstance(payload.get("restore_validation_checks"), dict)
            else None,
            "canonical_parity_matched": bool(
                isinstance(payload.get("canonical_parity"), dict)
                and payload.get("canonical_parity", {}).get("matched") is True
            ),
            "checkpoint_database_hash_matched": bool(
                isinstance(rollback, dict)
                and rollback.get("checkpoint_database_hash_matched") is True
            ),
            "checkpoint_database_byte_hash_matched": bool(
                isinstance(rollback, dict)
                and rollback.get("checkpoint_database_byte_hash_matched") is True
            ),
            "checkpoint_database_projection_matched": bool(
                isinstance(rollback, dict)
                and rollback.get("checkpoint_database_projection_matched") is True
            ),
            "api_worker_restart_allowed": bool(payload.get("api_worker_restart_allowed")),
            "created_at": payload.get("created_at"),
            "updated_at": payload.get("updated_at"),
            "completed_at": payload.get("completed_at"),
            "summary": payload.get("summary"),
            "sanitized": True,
        }
    )
