from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from .. import deps
from ..db.connection import begin_immediate, connection, database_path, read_connection
from ..db.migrations import apply_migrations
from . import lite_security_evidence as evidence
from . import lite_security_policy as policy

ACTIVE_STATUSES = frozenset({"queued", "accepted", "running", "working", "in_progress"})
TERMINAL_STATUSES = frozenset({"succeeded", "degraded", "failed", "cancelled"})


def _utc() -> str:
    return deps.now_utc_iso()


def _epoch_ms(value: datetime | None = None) -> int:
    return int((value or datetime.now(timezone.utc)).timestamp() * 1000)


def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.environ.get(name, str(default)).strip()
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def _safe_id(prefix: str) -> str:
    return f"{prefix}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"


def _maintenance_root() -> Path:
    root = deps.settings().state_dir / "security" / "maintenance"
    root.mkdir(parents=True, exist_ok=True)
    return root


def maintenance_marker_path() -> Path:
    return _maintenance_root() / "maintenance-state.json"


def orphan_evidence_manifest_path() -> Path:
    return _maintenance_root() / "orphan-evidence-manifest.json"


def _write_json(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    from . import lite_restore_transaction

    return lite_restore_transaction.atomic_write_json(path, payload)


def maintenance_state() -> dict[str, Any]:
    payload = deps.core.read_json_file(maintenance_marker_path(), {})
    if isinstance(payload, dict) and payload.get("active"):
        return policy.redact_value(payload)
    # A journal is durable evidence even if Android/process death occurred before
    # the maintenance marker was flushed. Fail closed for every new writer.
    try:
        from . import lite_restore_transaction

        guard = lite_restore_transaction.guard_status()
    except Exception:
        guard = {"unresolved": False}
    if guard.get("unresolved"):
        return {
            "active": True,
            "operation_id": guard.get("restore_id"),
            "kind": "database_restore",
            "state": guard.get("phase"),
            "summary": guard.get("summary"),
            "writers_stopped": True,
            "api_worker_restart_allowed": guard.get("api_worker_restart_allowed"),
            "sanitized": True,
        }
    return {
        "active": False,
        "state": "ready",
        "summary": "Maintenance is not active.",
        "writers_stopped": False,
        "sanitized": True,
    }


def enter_maintenance(
    *,
    operation_id: str,
    kind: str,
    state: str = "entering_maintenance",
    writers_stopped: bool = False,
) -> dict[str, Any]:
    current = maintenance_state()
    if current.get("active") and current.get("operation_id") != operation_id:
        raise RuntimeError("Another maintenance operation is already active")
    return _write_json(
        maintenance_marker_path(),
        {
            "active": True,
            "operation_id": operation_id,
            "kind": kind,
            "state": state,
            "started_at": current.get("started_at") or _utc(),
            "updated_at": _utc(),
            "writers_stopped": bool(writers_stopped),
            "summary": "Pocket Lab maintenance is in progress.",
            "sanitized": True,
        },
    )


def update_maintenance(
    operation_id: str,
    *,
    state: str,
    writers_stopped: bool | None = None,
    summary: str | None = None,
) -> dict[str, Any]:
    current = maintenance_state()
    if not current.get("active") or current.get("operation_id") != operation_id:
        raise RuntimeError("Maintenance ownership was lost")
    payload = dict(current)
    payload.update({"state": state, "updated_at": _utc()})
    if writers_stopped is not None:
        payload["writers_stopped"] = bool(writers_stopped)
    if summary:
        payload["summary"] = summary
    return _write_json(maintenance_marker_path(), payload)


def leave_maintenance(operation_id: str, *, state: str = "ready", summary: str = "Maintenance completed.") -> dict[str, Any]:
    current = maintenance_state()
    if current.get("active") and current.get("operation_id") not in {None, operation_id}:
        raise RuntimeError("Maintenance ownership was lost")
    payload = {
        "active": False,
        "operation_id": operation_id,
        "kind": current.get("kind"),
        "state": state,
        "started_at": current.get("started_at"),
        "completed_at": _utc(),
        "updated_at": _utc(),
        "writers_stopped": False,
        "summary": summary,
        "sanitized": True,
    }
    return _write_json(maintenance_marker_path(), payload)


def write_blocked_by_maintenance(path: str, method: str) -> bool:
    if str(method or "GET").upper() in {"GET", "HEAD", "OPTIONS"}:
        return False
    state = maintenance_state()
    if not state.get("active"):
        return False
    return True


def worker_command_allowed(subject: str) -> bool:
    state = maintenance_state()
    if not state.get("active"):
        return True
    # The command that created the maintenance marker is already executing.
    # Defer every newly delivered command until the marker is cleared.
    return False


def retention_config() -> dict[str, int]:
    return {
        "max_runs": _bounded_int("POCKETLAB_SECURITY_RETENTION_MAX_RUNS", 200, 20, 100_000),
        "min_per_profile": _bounded_int("POCKETLAB_SECURITY_RETENTION_MIN_PER_PROFILE", 20, 2, 1_000),
        "progress_retention_days": _bounded_int("POCKETLAB_SECURITY_PROGRESS_RETENTION_DAYS", 30, 1, 3_650),
        "progress_max_rows": _bounded_int("POCKETLAB_SECURITY_PROGRESS_MAX_ROWS", 20_000, 100, 10_000_000),
        "failed_retention_days": _bounded_int("POCKETLAB_SECURITY_FAILED_RETENTION_DAYS", 90, 1, 3_650),
        "batch_size": _bounded_int("POCKETLAB_SECURITY_RETENTION_BATCH_SIZE", 50, 1, 1_000),
    }


def _record_maintenance(
    conn: sqlite3.Connection,
    *,
    maintenance_id: str,
    kind: str,
    mode: str,
    status: str,
    requested_at: str,
    summary: str,
    metadata: dict[str, Any],
) -> None:
    conn.execute(
        """
        INSERT INTO security_maintenance_runs(
            maintenance_id, kind, mode, status, requested_at, completed_at,
            summary, metadata_json, sanitized
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
        ON CONFLICT(maintenance_id) DO UPDATE SET
            status=excluded.status,
            completed_at=excluded.completed_at,
            summary=excluded.summary,
            metadata_json=excluded.metadata_json,
            sanitized=1
        """,
        (
            maintenance_id,
            kind,
            mode,
            status,
            requested_at,
            _utc() if status in {"succeeded", "failed", "blocked"} else None,
            summary,
            json.dumps(policy.redact_value(metadata), sort_keys=True, separators=(",", ":")),
        ),
    )


def _protected_run_ids(conn: sqlite3.Connection, config: dict[str, int]) -> tuple[set[str], dict[str, int]]:
    protected: set[str] = set()
    reasons = {
        "active": 0,
        "profile_minimum": 0,
        "snapshot": 0,
        "comparison": 0,
        "recent_failed": 0,
    }

    for row in conn.execute(
        "SELECT run_id FROM security_scan_runs WHERE status IN ('queued','accepted','running','working','in_progress')"
    ):
        protected.add(str(row[0]))
        reasons["active"] += 1

    for row in conn.execute("SELECT latest_run_id FROM security_profile_snapshots"):
        run_id = str(row[0])
        if run_id not in protected:
            reasons["snapshot"] += 1
        protected.add(run_id)

    identities = conn.execute(
        "SELECT DISTINCT profile, app_id FROM security_scan_runs"
    ).fetchall()
    for profile, app_id in identities:
        rows = conn.execute(
            """
            SELECT run_id FROM security_scan_runs
            WHERE profile=? AND (app_id=? OR (app_id IS NULL AND ? IS NULL))
            ORDER BY COALESCE(completed_at_epoch_ms, updated_at_epoch_ms) DESC, run_id DESC
            LIMIT ?
            """,
            (profile, app_id, app_id, config["min_per_profile"]),
        ).fetchall()
        for row in rows:
            run_id = str(row[0])
            if run_id not in protected:
                reasons["profile_minimum"] += 1
            protected.add(run_id)

        comparisons = conn.execute(
            """
            SELECT run_id FROM security_scan_runs
            WHERE profile=?
              AND (app_id=? OR (app_id IS NULL AND ? IS NULL))
              AND status IN ('succeeded','degraded')
            ORDER BY COALESCE(completed_at_epoch_ms, updated_at_epoch_ms) DESC, run_id DESC
            LIMIT 2
            """,
            (profile, app_id, app_id),
        ).fetchall()
        for row in comparisons:
            run_id = str(row[0])
            if run_id not in protected:
                reasons["comparison"] += 1
            protected.add(run_id)

    failed_cutoff = _epoch_ms(datetime.now(timezone.utc) - timedelta(days=config["failed_retention_days"]))
    for row in conn.execute(
        """
        SELECT run_id FROM security_scan_runs
        WHERE status IN ('failed','cancelled') AND updated_at_epoch_ms >= ?
        """,
        (failed_cutoff,),
    ):
        run_id = str(row[0])
        if run_id not in protected:
            reasons["recent_failed"] += 1
        protected.add(run_id)
    return protected, reasons


def _eligible_retention_candidates(
    conn: sqlite3.Connection,
    *,
    protected: set[str],
    excess: int,
    batch_size: int,
) -> list[str]:
    if excess <= 0:
        return []
    rows = conn.execute(
        """
        SELECT run_id FROM security_scan_runs
        WHERE status IN ('succeeded','degraded','failed','cancelled')
        ORDER BY COALESCE(completed_at_epoch_ms, updated_at_epoch_ms) ASC, run_id ASC
        """
    ).fetchall()
    limit = min(excess, batch_size)
    return [str(row[0]) for row in rows if str(row[0]) not in protected][:limit]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def generate_orphan_evidence_manifest() -> dict[str, Any]:
    apply_migrations()
    state_dir = deps.settings().state_dir.resolve(strict=False)
    with read_connection() as conn:
        refs = conn.execute(
            "SELECT relative_path, sha256 FROM security_scan_evidence_refs ORDER BY evidence_ref_id"
        ).fetchall()

    expected: dict[str, str] = {}
    missing = 0
    hash_mismatch = 0
    referenced_existing = 0
    for relative_path, sha256 in refs:
        rel = str(relative_path or "").lstrip("/")
        expected[rel] = str(sha256 or "")
        candidate = (state_dir / rel).resolve(strict=False)
        if state_dir != candidate and state_dir not in candidate.parents:
            missing += 1
            continue
        if not candidate.is_file():
            missing += 1
            continue
        referenced_existing += 1
        if sha256 and _sha256(candidate) != str(sha256):
            hash_mismatch += 1

    evidence_root = deps.settings().state_dir / "security" / "evidence"
    discovered: set[str] = set()
    if evidence_root.exists():
        for path in evidence_root.rglob("*"):
            if path.is_file():
                discovered.add(str(path.relative_to(state_dir)))
    unreferenced = sorted(discovered - set(expected))
    manifest = {
        "generated_at": _utc(),
        "referenced": referenced_existing,
        "referenced_rows": len(refs),
        "unreferenced": len(unreferenced),
        "missing": missing,
        "hash_mismatch": hash_mismatch,
        "unknown_files": len(unreferenced),
        "automatic_deletion_enabled": False,
        "sample_unreferenced": [Path(item).name for item in unreferenced[:20]],
        "sanitized": True,
    }
    return _write_json(orphan_evidence_manifest_path(), manifest)


def run_retention(*, dry_run: bool = True, max_batches: int = 1) -> dict[str, Any]:
    if maintenance_state().get("active"):
        raise RuntimeError("Retention is blocked while maintenance is active")
    apply_migrations()
    config = retention_config()
    maintenance_id = _safe_id("retention")
    requested_at = _utc()
    max_batches = max(1, min(int(max_batches), 100))
    plan: dict[str, Any]

    with connection() as conn:
        total_before = int(conn.execute("SELECT COUNT(*) FROM security_scan_runs").fetchone()[0])
        protected, protected_reasons = _protected_run_ids(conn, config)
        excess = max(0, total_before - config["max_runs"])
        candidates = _eligible_retention_candidates(
            conn,
            protected=protected,
            excess=excess,
            batch_size=config["batch_size"] * max_batches,
        )
        plan = {
            "total_before": total_before,
            "run_cap": config["max_runs"],
            "protected_count": len(protected),
            "protected_reasons": protected_reasons,
            "candidate_count": len(candidates),
            "candidate_run_ids": candidates,
            "batch_size": config["batch_size"],
            "max_batches": max_batches,
        }
        if dry_run:
            _record_maintenance(
                conn,
                maintenance_id=maintenance_id,
                kind="retention",
                mode="dry_run",
                status="succeeded",
                requested_at=requested_at,
                summary="Retention dry-run completed without deleting rows.",
                metadata=plan,
            )
        conn.commit()

    deleted = 0
    progress_result: dict[str, Any] = {"rows_deleted": 0, "status": "dry_run"}
    if not dry_run:
        with begin_immediate() as conn:
            if candidates:
                placeholders = ",".join("?" for _ in candidates)
                cursor = conn.execute(
                    f"DELETE FROM security_scan_runs WHERE run_id IN ({placeholders})",
                    tuple(candidates),
                )
                deleted = max(0, int(cursor.rowcount or 0))
            _record_maintenance(
                conn,
                maintenance_id=maintenance_id,
                kind="retention",
                mode="apply",
                status="running",
                requested_at=requested_at,
                summary="Bounded Security retention is running.",
                metadata={**plan, "runs_deleted": deleted},
            )

        from .lite_security_store import SecuritySQLiteRepository

        repository = SecuritySQLiteRepository()
        progress_result = repository.prune_progress_events(
            retention_days=config["progress_retention_days"],
            max_rows=config["progress_max_rows"],
            min_per_active_run=2,
            batch_size=config["batch_size"],
        )
        with connection() as conn:
            quick_check = str(conn.execute("PRAGMA quick_check").fetchone()[0])
            total_after = int(conn.execute("SELECT COUNT(*) FROM security_scan_runs").fetchone()[0])
            metadata = {
                **plan,
                "runs_deleted": deleted,
                "total_after": total_after,
                "progress": progress_result,
                "quick_check": quick_check,
            }
            _record_maintenance(
                conn,
                maintenance_id=maintenance_id,
                kind="retention",
                mode="apply",
                status="succeeded" if quick_check == "ok" else "failed",
                requested_at=requested_at,
                summary="Bounded Security retention completed." if quick_check == "ok" else "Retention completed but SQLite quick check failed.",
                metadata=metadata,
            )
            conn.commit()
        if quick_check != "ok":
            raise RuntimeError("SQLite quick check failed after retention")
    else:
        with read_connection() as conn:
            quick_check = str(conn.execute("PRAGMA quick_check").fetchone()[0])
            total_after = int(conn.execute("SELECT COUNT(*) FROM security_scan_runs").fetchone()[0])

    orphan_manifest = generate_orphan_evidence_manifest()
    return policy.redact_value(
        {
            "status": "succeeded",
            "maintenance_id": maintenance_id,
            "mode": "dry_run" if dry_run else "apply",
            "config": config,
            "plan": plan,
            "runs_deleted": deleted,
            "total_after": total_after,
            "progress": progress_result,
            "quick_check": quick_check,
            "evidence_files_deleted": 0,
            "orphan_evidence": orphan_manifest,
            "summary": "Retention dry-run completed without changes." if dry_run else "Bounded Security retention completed.",
            "sanitized": True,
        }
    )


def active_security_scan() -> dict[str, Any] | None:
    apply_migrations()
    with read_connection() as conn:
        row = conn.execute(
            """
            SELECT run_id, profile, app_id, status, updated_at
            FROM security_scan_runs
            WHERE status IN ('queued','accepted','running','working','in_progress')
            ORDER BY updated_at_epoch_ms DESC LIMIT 1
            """
        ).fetchone()
    if not row:
        return None
    return {
        "run_id": row[0],
        "profile": row[1],
        "app_id": row[2],
        "status": row[3],
        "updated_at": row[4],
    }


def wal_diagnostics() -> dict[str, Any]:
    apply_migrations()
    db = database_path()
    wal = Path(f"{db}-wal")
    shm = Path(f"{db}-shm")
    warning_bytes = _bounded_int("POCKETLAB_LITE_DB_WAL_WARNING_BYTES", 64 * 1024 * 1024, 1024 * 1024, 8 * 1024 * 1024 * 1024)
    with read_connection() as conn:
        journal_mode = str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower()
    state = maintenance_state()
    return {
        "journal_mode": journal_mode,
        "wal_bytes": wal.stat().st_size if wal.exists() else 0,
        "shm_bytes": shm.stat().st_size if shm.exists() else 0,
        "wal_warning_bytes": warning_bytes,
        "wal_warning": bool(wal.exists() and wal.stat().st_size >= warning_bytes),
        "last_passive_checkpoint_at": deps.core.read_json_file(_maintenance_root() / "wal-status.json", {}).get("last_passive_checkpoint_at"),
        "last_truncate_checkpoint_at": deps.core.read_json_file(_maintenance_root() / "wal-status.json", {}).get("last_truncate_checkpoint_at"),
        "writers_stopped": bool(state.get("writers_stopped")),
        "maintenance_active": bool(state.get("active")),
        "sanitized": True,
    }


def run_wal_checkpoint(*, mode: str = "PASSIVE", operation_id: str | None = None, writers_stopped: bool = False) -> dict[str, Any]:
    apply_migrations()
    checkpoint_mode = str(mode or "PASSIVE").strip().upper()
    if checkpoint_mode not in {"PASSIVE", "TRUNCATE"}:
        raise ValueError("Checkpoint mode must be PASSIVE or TRUNCATE")
    maintenance_id = operation_id or _safe_id("wal")
    requested_at = _utc()
    state = maintenance_state()
    if checkpoint_mode == "TRUNCATE":
        if not state.get("active") or state.get("operation_id") != maintenance_id:
            raise RuntimeError("TRUNCATE checkpoint requires an owned maintenance window")
        if not writers_stopped or not state.get("writers_stopped"):
            raise RuntimeError("TRUNCATE checkpoint requires confirmed writer quiescence")
        if active_security_scan():
            raise RuntimeError("TRUNCATE checkpoint is blocked while a Security scan is active")

    with connection() as conn:
        row = conn.execute(f"PRAGMA wal_checkpoint({checkpoint_mode})").fetchone()
        busy, log_frames, checkpointed_frames = (int(row[0]), int(row[1]), int(row[2]))
        quick_check = str(conn.execute("PRAGMA quick_check").fetchone()[0])
        result = {
            "checkpoint_mode": checkpoint_mode.lower(),
            "checkpoint_busy": busy,
            "checkpoint_log_frames": log_frames,
            "checkpointed_frames": checkpointed_frames,
            "quick_check": quick_check,
            "writers_stopped": bool(writers_stopped),
            "manual_wal_file_deletion": False,
            "completed_at": _utc(),
            "sanitized": True,
        }
        _record_maintenance(
            conn,
            maintenance_id=maintenance_id,
            kind="wal_truncate" if checkpoint_mode == "TRUNCATE" else "wal_passive",
            mode="apply",
            status="succeeded" if quick_check == "ok" else "failed",
            requested_at=requested_at,
            summary=f"{checkpoint_mode.title()} WAL checkpoint completed.",
            metadata=result,
        )
        conn.commit()

    status_path = _maintenance_root() / "wal-status.json"
    previous = deps.core.read_json_file(status_path, {})
    if not isinstance(previous, dict):
        previous = {}
    key = "last_truncate_checkpoint_at" if checkpoint_mode == "TRUNCATE" else "last_passive_checkpoint_at"
    previous.update({key: result["completed_at"], "last_result": result, "sanitized": True})
    _write_json(status_path, previous)
    return {**wal_diagnostics(), **result, "status": "succeeded", "summary": f"{checkpoint_mode.title()} checkpoint completed."}


def maintenance_status() -> dict[str, Any]:
    apply_migrations()
    with read_connection() as conn:
        rows = conn.execute(
            """
            SELECT maintenance_id, kind, mode, status, requested_at, completed_at, summary
            FROM security_maintenance_runs ORDER BY requested_at DESC LIMIT 20
            """
        ).fetchall()
    return {
        "status": "maintenance" if maintenance_state().get("active") else "ready",
        "maintenance": maintenance_state(),
        "wal": wal_diagnostics(),
        "retention": retention_config(),
        "orphan_evidence": deps.core.read_json_file(orphan_evidence_manifest_path(), None),
        "history": [
            {
                "maintenance_id": row[0],
                "kind": row[1],
                "mode": row[2],
                "status": row[3],
                "requested_at": row[4],
                "completed_at": row[5],
                "summary": row[6],
            }
            for row in rows
        ],
        "updated_at": _utc(),
        "sanitized": True,
    }


class LiteMaintenanceModeMiddleware:
    """Fail closed for write requests while a database maintenance window is active."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope.get("type") != "http" or not write_blocked_by_maintenance(
            str(scope.get("path") or ""), str(scope.get("method") or "GET")
        ):
            await self.app(scope, receive, send)
            return
        payload = json.dumps(
            {
                "status": "maintenance_in_progress",
                "summary": "Pocket Lab maintenance is in progress. Write actions are temporarily paused.",
                "retryable": True,
                "sanitized": True,
            },
            separators=(",", ":"),
        ).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 503,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"retry-after", b"5"),
                    (b"content-length", str(len(payload)).encode("ascii")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": payload})
