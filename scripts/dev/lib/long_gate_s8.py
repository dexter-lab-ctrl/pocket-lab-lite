#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

TERMINAL_SCAN = {"succeeded", "degraded", "failed", "cancelled"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def truthy(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class GateError(RuntimeError):
    pass


class ApiTransportError(GateError):
    def __init__(self, method: str, path: str, error_type: str) -> None:
        super().__init__(f"{method} {path} failed: {error_type}")
        self.method = method
        self.path = path
        self.error_type = error_type


class Api:
    def __init__(self, base_url: str, timeout: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.token = (os.environ.get("POCKETLAB_API_TOKEN") or "").strip()

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        body = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = urllib.request.Request(
            f"{self.base_url}{path}", data=body, headers=headers, method=method
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
                if not raw:
                    return {"http_status": response.status}
                value = json.loads(raw.decode("utf-8"))
                if not isinstance(value, dict):
                    raise GateError(f"{path} returned a non-object JSON payload")
                value.setdefault("http_status", response.status)
                return value
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            try:
                detail = json.loads(raw.decode("utf-8")) if raw else {}
            except (UnicodeDecodeError, json.JSONDecodeError):
                detail = {}
            summary = "HTTP request failed"
            if isinstance(detail, dict):
                nested = detail.get("detail")
                if isinstance(nested, dict):
                    summary = str(nested.get("summary") or nested.get("status") or summary)
                else:
                    summary = str(detail.get("summary") or nested or summary)
            raise GateError(f"{method} {path} returned HTTP {exc.code}: {summary}") from exc
        except json.JSONDecodeError as exc:
            raise GateError(f"{method} {path} failed: JSONDecodeError") from exc
        except urllib.error.URLError as exc:
            reason = getattr(exc, "reason", None)
            error_type = type(reason).__name__ if reason is not None else type(exc).__name__
            raise ApiTransportError(method, path, error_type) from exc
        except TimeoutError as exc:
            raise ApiTransportError(method, path, type(exc).__name__) from exc

    def get(self, path: str) -> dict[str, Any]:
        return self.request("GET", path)

    def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.request("POST", path, payload)


def poll(label: str, timeout: float, interval: float, operation: Callable[[], dict[str, Any]], predicate: Callable[[dict[str, Any]], bool]) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last: dict[str, Any] = {}
    while time.monotonic() < deadline:
        try:
            last = operation()
            if predicate(last):
                return last
        except GateError:
            pass
        time.sleep(interval)
    status = str(last.get("status") or last.get("state") or "unknown")
    raise GateError(f"Timed out waiting for {label}; last status was {status}")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def database_state(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise GateError("SQLite database file is unavailable")
    uri = f"file:{path}?mode=ro"
    with sqlite3.connect(uri, uri=True, timeout=5) as conn:
        quick = str(conn.execute("PRAGMA quick_check").fetchone()[0])
        integrity = str(conn.execute("PRAGMA integrity_check").fetchone()[0])
        foreign_key_violations = len(conn.execute("PRAGMA foreign_key_check").fetchall())
        run_count = int(conn.execute("SELECT COUNT(*) FROM security_scan_runs").fetchone()[0])
        version = int(conn.execute("SELECT COALESCE(MAX(version),0) FROM schema_migrations").fetchone()[0])
        revision_row = conn.execute("SELECT revision FROM domain_revisions WHERE domain='security'").fetchone()
        latest_row = conn.execute(
            "SELECT run_id FROM security_scan_runs ORDER BY COALESCE(completed_at_epoch_ms,updated_at_epoch_ms) DESC, run_id DESC LIMIT 1"
        ).fetchone()
        migrations = [list(row) for row in conn.execute(
            "SELECT version,name,checksum FROM schema_migrations ORDER BY version"
        ).fetchall()]
    return {
        "sha256": file_sha256(path),
        "quick_check": quick,
        "integrity_check": integrity,
        "foreign_key_violation_count": foreign_key_violations,
        "security_run_count": run_count,
        "schema_version": version,
        "security_revision": int(revision_row[0]) if revision_row else 0,
        "latest_run_id": str(latest_row[0]) if latest_row else None,
        "migration_contract": migrations,
        "wal_present": path.with_name(path.name + "-wal").exists(),
        "shm_present": path.with_name(path.name + "-shm").exists(),
    }


def state_file_hashes(state_dir: Path) -> dict[str, str]:
    candidates = [state_dir / "security" / "security_state.json"]
    runs = state_dir / "security" / "runs"
    if runs.exists():
        candidates.extend(sorted(runs.glob("*.json")))
    compact = state_dir / "security" / "compact"
    if compact.exists():
        candidates.extend(sorted(compact.rglob("*.json")))
    result: dict[str, str] = {}
    for path in candidates:
        if path.is_file():
            result[path.relative_to(state_dir).as_posix()] = file_sha256(path)
    return result


def configure_worker_fault(point: str | None) -> None:
    env = os.environ.copy()
    env["POCKETLAB_LITE_ENABLE_S8_GATE_FAULTS"] = "1" if point else "0"
    env["POCKETLAB_LITE_S8_FAULT_POINT"] = point or ""
    try:
        result = subprocess.run(
            ["pm2", "restart", "pocket-worker", "--update-env"],
            check=False,
            capture_output=True,
            text=True,
            timeout=45,
            env=env,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise GateError(f"Could not configure the worker restore fault: {type(exc).__name__}") from exc
    if result.returncode != 0:
        raise GateError("Could not restart pocket-worker with the bounded S8 gate environment")
    time.sleep(3)


def recent_maintenance(api: Api, *, kind: str, mode: str | None, after: str, timeout: float) -> dict[str, Any]:
    def match(payload: dict[str, Any]) -> bool:
        for item in payload.get("history") or []:
            if not isinstance(item, dict):
                continue
            if item.get("kind") != kind:
                continue
            if mode is not None and item.get("mode") != mode:
                continue
            if str(item.get("requested_at") or "") < after:
                continue
            if item.get("status") in {"succeeded", "failed", "blocked"}:
                payload["matched"] = item
                return True
        return False

    result = poll(
        f"maintenance {kind}", timeout, 1.0, lambda: api.get("/api/lite/recovery/maintenance"), match
    )
    matched = result.get("matched") or {}
    if matched.get("status") != "succeeded":
        raise GateError(f"Maintenance {kind} finished with {matched.get('status')}")
    return matched


def _scan_requested_epoch_ms(item: dict[str, Any]) -> int:
    raw = item.get("requested_at_epoch_ms")
    try:
        return int(raw or 0)
    except (TypeError, ValueError):
        pass
    raw_iso = str(item.get("requested_at") or "").strip()
    if not raw_iso:
        return 0
    try:
        return int(datetime.fromisoformat(raw_iso.replace("Z", "+00:00")).timestamp() * 1000)
    except ValueError:
        return 0


def _scan_candidates(api: Api) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    progress = api.get("/api/lite/security/progress")
    if isinstance(progress, dict):
        candidates.append(progress)

    summary = api.get("/api/lite/security/summary")
    if isinstance(summary, dict):
        for key in ("scan_progress", "last_run"):
            item = summary.get(key)
            if isinstance(item, dict):
                candidates.append(item)
        profile_latest = summary.get("profile_latest")
        if isinstance(profile_latest, dict):
            quick = profile_latest.get("quick")
            if isinstance(quick, dict):
                candidates.append(quick)
        for item in summary.get("history") or []:
            if isinstance(item, dict):
                candidates.append(item)

    deduped: dict[str, dict[str, Any]] = {}
    for item in candidates:
        run_id = str(item.get("run_id") or "")
        if not run_id:
            continue
        prior = deduped.get(run_id)
        if prior is None or _scan_requested_epoch_ms(item) >= _scan_requested_epoch_ms(prior):
            deduped[run_id] = item
    return sorted(deduped.values(), key=_scan_requested_epoch_ms, reverse=True)


def _find_scan(api: Api, predicate: Callable[[dict[str, Any]], bool]) -> dict[str, Any]:
    last: dict[str, Any] = {}
    for item in _scan_candidates(api):
        last = item
        if predicate(item):
            return item
    return last


def wait_security_idle(api: Api, timeout: float) -> dict[str, Any]:
    idle_timeout = min(
        max(float(os.environ.get("POCKETLAB_S8_GATE_SECURITY_IDLE_TIMEOUT", "120")), 15.0),
        max(timeout, 15.0),
        300.0,
    )

    def idle(payload: dict[str, Any]) -> bool:
        return payload.get("active_scan") is False

    return poll(
        "Security scan idle precondition",
        idle_timeout,
        2.0,
        lambda: api.get("/api/lite/security/progress"),
        idle,
    )


def run_quick_scan(api: Api, timeout: float) -> dict[str, Any]:
    baseline = wait_security_idle(api, timeout)
    baseline_run_id = str(baseline.get("run_id") or "")
    submitted_after_epoch_ms = int(time.time() * 1000)
    expected_run = ""
    submission_recovered = False

    try:
        submitted = api.post("/api/lite/security/check", {"profile": "quick"})
        expected_run = str(submitted.get("run_id") or "")
    except ApiTransportError as exc:
        is_submission_timeout = (
            exc.method == "POST"
            and exc.path == "/api/lite/security/check"
            and "timeout" in exc.error_type.lower()
        )
        if not is_submission_timeout:
            raise

        configured_recovery = float(os.environ.get("POCKETLAB_S8_GATE_SUBMISSION_RECOVERY_TIMEOUT", "90"))
        recovery_timeout = min(max(configured_recovery, api.timeout * 4.0, 30.0), timeout, 180.0)

        def adopted(item: dict[str, Any]) -> bool:
            run_id = str(item.get("run_id") or "")
            profile = str(item.get("profile") or item.get("scan_profile") or "")
            return (
                bool(run_id)
                and run_id != baseline_run_id
                and profile in {"", "quick"}
                and _scan_requested_epoch_ms(item) >= submitted_after_epoch_ms - 5000
            )

        recovered = poll(
            "timed-out Quick Safety Check submission",
            recovery_timeout,
            1.0,
            lambda: _find_scan(api, adopted),
            adopted,
        )
        expected_run = str(recovered.get("run_id") or "")
        submission_recovered = True

    if not expected_run:
        raise GateError("Quick Safety Check submission did not return or expose a run id")

    def terminal(item: dict[str, Any]) -> bool:
        status = str(item.get("status") or "").lower()
        same = str(item.get("run_id") or "") == expected_run
        return same and status in TERMINAL_SCAN

    progress = poll(
        "Quick Safety Check",
        timeout,
        2.0,
        lambda: _find_scan(api, terminal),
        terminal,
    )
    if str(progress.get("status") or "").lower() not in {"succeeded", "degraded"}:
        raise GateError(f"Quick Safety Check ended with {progress.get('status')}")
    return {
        "run_id": progress.get("run_id"),
        "status": progress.get("status"),
        "percent": progress.get("percent") or progress.get("current_percent"),
        "submission_recovered": submission_recovered,
    }


def wait_backup(api: Api, backup_id: str, timeout: float) -> dict[str, Any]:
    result = poll(
        "verified database backup",
        timeout,
        1.0,
        lambda: api.get(f"/api/lite/recovery/database/backups/{backup_id}"),
        lambda item: item.get("status") in {"verified", "failed"},
    )
    if result.get("status") != "verified" or result.get("verification_status") != "verified":
        raise GateError("Database backup did not become verified")
    return result


def wait_preview(api: Api, backup_id: str, timeout: float) -> dict[str, Any]:
    result = poll(
        "database restore preview",
        timeout,
        1.0,
        lambda: api.get("/api/lite/recovery/database"),
        lambda item: isinstance(item.get("latest_restore_preview"), dict)
        and item["latest_restore_preview"].get("backup_id") == backup_id
        and item["latest_restore_preview"].get("status") in {"ready", "blocked"},
    )["latest_restore_preview"]
    if result.get("status") != "ready" or not result.get("restore_allowed"):
        raise GateError("Database restore preview is not ready")
    return result


def wait_restore(api: Api, restore_id: str, timeout: float, expected: str) -> dict[str, Any]:
    result = poll(
        f"database restore {restore_id}",
        timeout,
        1.0,
        lambda: api.get(f"/api/lite/recovery/database/restore/{restore_id}"),
        lambda item: item.get("status") in {"completed", "failed"},
    )
    if result.get("status") != expected:
        raise GateError(f"Restore expected {expected} but finished {result.get('status')}")
    return result


def safe_backup_summary(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "backup_id": item.get("backup_id"),
        "status": item.get("status"),
        "verification_status": item.get("verification_status"),
        "schema_version": item.get("schema_version"),
        "size_bytes": item.get("size_bytes"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--db-path", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--platform", choices=("termux", "ubuntu"), required=True)
    parser.add_argument("--http-timeout", type=float, default=10.0)
    parser.add_argument("--operation-timeout", type=float, default=300.0)
    parser.add_argument("--scan-timeout", type=float, default=1800.0)
    args = parser.parse_args()

    api = Api(args.base_url, args.http_timeout)
    db_path = Path(args.db_path).expanduser().resolve(strict=False)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    allow_apply = truthy("POCKETLAB_S8_GATE_ALLOW_RETENTION_APPLY")
    allow_restore = truthy("POCKETLAB_S8_GATE_ALLOW_RESTORE")
    allow_fault = truthy("POCKETLAB_S8_GATE_ALLOW_FAILED_RESTORE")

    report: dict[str, Any] = {
        "phase": "S8",
        "platform": args.platform,
        "started_at": utc_now(),
        "status": "running",
        "gates": [],
        "sanitized": True,
    }

    def record(name: str, fn: Callable[[], dict[str, Any]]) -> dict[str, Any]:
        started = utc_now()
        try:
            detail = fn()
            item = {"name": name, "status": "passed", "started_at": started, "completed_at": utc_now(), "detail": detail}
        except Exception as exc:
            item = {
                "name": name,
                "status": "failed",
                "started_at": started,
                "completed_at": utc_now(),
                "error_type": type(exc).__name__,
                "summary": str(exc)[:300],
            }
            report["gates"].append(item)
            output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            raise
        report["gates"].append(item)
        output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return detail

    try:
        record(
            "preflight",
            lambda: {
                "health": api.get("/health").get("status", "reachable"),
                "database": database_state(db_path),
                "maintenance_active": bool(api.get("/api/lite/recovery/maintenance").get("maintenance", {}).get("active")),
            },
        )

        def retention_dry() -> dict[str, Any]:
            before = database_state(db_path)
            started = utc_now()
            api.post("/api/lite/recovery/maintenance/retention", {"dry_run": True, "max_batches": 1})
            result = recent_maintenance(api, kind="retention", mode="dry_run", after=started, timeout=args.operation_timeout)
            after = database_state(db_path)
            if before["security_run_count"] != after["security_run_count"]:
                raise GateError("Retention dry-run changed Security run rows")
            return {"before": before, "after": after, "maintenance": result}

        record("gate-1-retention-dry-run", retention_dry)

        def retention_apply() -> dict[str, Any]:
            if not allow_apply:
                raise GateError("Set POCKETLAB_S8_GATE_ALLOW_RETENTION_APPLY=1 for the production retention apply gate")
            started = utc_now()
            api.post("/api/lite/recovery/maintenance/retention", {"dry_run": False, "max_batches": 1})
            result = recent_maintenance(api, kind="retention", mode="apply", after=started, timeout=args.operation_timeout)
            state = database_state(db_path)
            if state["quick_check"] != "ok":
                raise GateError("SQLite quick_check failed after retention")
            return {"database": state, "maintenance": result}

        record("gate-2-retention-apply", retention_apply)

        def wal_gate() -> dict[str, Any]:
            started = utc_now()
            api.post("/api/lite/recovery/maintenance/checkpoint", {"mode": "passive"})
            passive = recent_maintenance(api, kind="wal_passive", mode="apply", after=started, timeout=args.operation_timeout)
            truncate_started = utc_now()
            api.post(
                "/api/lite/recovery/maintenance/checkpoint",
                {"mode": "truncate", "confirm_controlled": True},
            )
            truncate = recent_maintenance(api, kind="wal_truncate", mode="apply", after=truncate_started, timeout=args.operation_timeout)
            maintenance = api.get("/api/lite/recovery/maintenance")
            state = database_state(db_path)
            if state["quick_check"] != "ok":
                raise GateError("SQLite quick_check failed after WAL maintenance")
            return {
                "passive": passive,
                "truncate": truncate,
                "wal": maintenance.get("wal"),
                "manual_wal_file_deletion": False,
                "database": state,
            }

        record("gate-3-wal-maintenance", wal_gate)

        def online_backup_gate() -> dict[str, Any]:
            submitted = api.post("/api/lite/recovery/database/backup", {"reason": "S8 production gate"})
            backup_id = str(submitted.get("backup_id") or "")
            if not backup_id:
                raise GateError("Database backup submission did not return a backup id")
            backup = wait_backup(api, backup_id, args.operation_timeout)
            scan = run_quick_scan(api, args.scan_timeout)
            api.post(f"/api/lite/recovery/database/backups/{backup_id}/verify", {})
            verified = wait_backup(api, backup_id, args.operation_timeout)
            return {"backup": safe_backup_summary(verified), "post_backup_scan": scan}

        backup_detail = record("gate-4-online-backup", online_backup_gate)
        backup_id = str(backup_detail["backup"]["backup_id"])

        def restore_gate() -> dict[str, Any]:
            if not allow_restore:
                raise GateError("Set POCKETLAB_S8_GATE_ALLOW_RESTORE=1 for the destructive production restore gate")
            state_b_scan = run_quick_scan(api, args.scan_timeout)
            api.post(f"/api/lite/recovery/database/backups/{backup_id}/preview", {})
            preview = wait_preview(api, backup_id, args.operation_timeout)
            submitted = api.post(
                f"/api/lite/recovery/database/backups/{backup_id}/restore",
                {"backup_id": backup_id, "preview_id": preview["preview_id"], "confirm": True},
            )
            restore_id = str(submitted.get("restore_id") or "")
            restored = wait_restore(api, restore_id, args.operation_timeout, "completed")
            post_health = {
                "health": api.get("/health").get("status", "reachable"),
                "status": api.get("/api/lite/status").get("status"),
                "summary": api.get("/api/lite/security/summary").get("status"),
                "progress": api.get("/api/lite/security/progress").get("status"),
                "history_count": len(api.get("/api/lite/security/history?limit=2").get("history") or []),
            }
            post_scan = run_quick_scan(api, args.scan_timeout)
            state = database_state(db_path)
            if not restored.get("rollback_available") or restored.get("canonical_parity_matched") is not True:
                raise GateError("Restore did not retain rollback or pass canonical parity")
            return {
                "state_b_scan": state_b_scan,
                "preview_id": preview.get("preview_id"),
                "restore_id": restore_id,
                "rollback_available": restored.get("rollback_available"),
                "parity_matched": restored.get("canonical_parity_matched"),
                "post_restore_health": post_health,
                "post_restore_scan": post_scan,
                "database": state,
            }

        record("gate-5-restore", restore_gate)

        def failed_restore_gate() -> dict[str, Any]:
            if not allow_restore or not allow_fault:
                raise GateError(
                    "Set POCKETLAB_S8_GATE_ALLOW_RESTORE=1 and POCKETLAB_S8_GATE_ALLOW_FAILED_RESTORE=1 for rollback fault qualification"
                )
            submitted_backup = api.post("/api/lite/recovery/database/backup", {"reason": "S8 rollback gate"})
            fault_backup_id = str(submitted_backup.get("backup_id") or "")
            wait_backup(api, fault_backup_id, args.operation_timeout)
            marker_scan = run_quick_scan(api, args.scan_timeout)
            api.post(f"/api/lite/recovery/database/backups/{fault_backup_id}/preview", {})
            preview = wait_preview(api, fault_backup_id, args.operation_timeout)
            fault_configured = False
            configure_worker_fault("after_sqlite_promotion")
            fault_configured = True

            # The worker restart used to enable the bounded restore fault may
            # legitimately update derived Security projections.  The restore
            # transaction checkpoints state only after that restart, so the
            # gate must capture its expected rollback snapshot at the same
            # transaction boundary rather than before fault configuration.
            settled_progress = wait_security_idle(api, args.scan_timeout)
            if str(settled_progress.get("run_id") or "") != str(marker_scan.get("run_id") or ""):
                raise GateError("Worker fault setup changed the pre-failure Security run identity")
            pre_database = database_state(db_path)
            state_dir = db_path.parent
            pre_files = state_file_hashes(state_dir)
            failed: dict[str, Any] = {}
            try:
                submitted_restore = api.post(
                    f"/api/lite/recovery/database/backups/{fault_backup_id}/restore",
                    {
                        "backup_id": fault_backup_id,
                        "preview_id": preview["preview_id"],
                        "confirm": True,
                    },
                )
                restore_id = str(submitted_restore.get("restore_id") or "")
                failed = wait_restore(api, restore_id, args.operation_timeout, "failed")
                if failed.get("phase") != "rolled_back" or failed.get("rollback_status") != "rolled_back":
                    raise GateError("Injected restore failure did not reach a validated rolled_back phase")
                if failed.get("api_worker_restart_allowed") is not True:
                    raise GateError("Worker restart remains blocked because rollback validation did not complete")
                post_database = database_state(db_path)
                post_files = state_file_hashes(state_dir)
                logical_keys = {
                    "quick_check", "integrity_check", "foreign_key_violation_count",
                    "security_run_count", "schema_version", "security_revision",
                    "latest_run_id", "migration_contract",
                }
                if {key: post_database.get(key) for key in logical_keys} != {key: pre_database.get(key) for key in logical_keys}:
                    raise GateError("Rollback did not restore the exact pre-failure SQLite logical state")
                if failed.get("checkpoint_database_hash_matched") is not True:
                    raise GateError("Rollback checkpoint database hash proof is missing")
                if post_files != pre_files:
                    changed = sorted(
                        key
                        for key in set(pre_files) | set(post_files)
                        if pre_files.get(key) != post_files.get(key)
                    )
                    preview_changed = ", ".join(changed[:6])
                    suffix = "" if len(changed) <= 6 else f" (+{len(changed) - 6} more)"
                    raise GateError(
                        "Rollback did not restore the exact pre-failure Security projection files"
                        + (f": {preview_changed}{suffix}" if preview_changed else "")
                    )
                progress = api.get("/api/lite/security/progress")
                if str(progress.get("run_id") or "") != str(marker_scan.get("run_id") or ""):
                    raise GateError("Rollback did not restore the pre-failure Security state")
                recovery = api.get("/api/lite/recovery/database")
                guard = recovery.get("restore_guard") or {}
                if guard.get("unresolved"):
                    raise GateError("Restore guard remained unresolved after validated rollback")
            finally:
                if fault_configured:
                    try:
                        recovery = api.get("/api/lite/recovery/database")
                        guard = recovery.get("restore_guard") or {}
                    except GateError:
                        guard = {}
                    if guard.get("api_worker_restart_allowed") is True:
                        configure_worker_fault(None)
            post_scan = run_quick_scan(api, args.scan_timeout)
            return {
                "restore_id": failed.get("restore_id"),
                "phase": failed.get("phase"),
                "rollback_status": failed.get("rollback_status"),
                "restart_allowed_after_validation": failed.get("api_worker_restart_allowed"),
                "marker_run_restored": True,
                "database_logical_match": True,
                "checkpoint_database_hash_matched": failed.get("checkpoint_database_hash_matched"),
                "state_files_exact_match": True,
                "post_rollback_scan": post_scan,
                "database": database_state(db_path),
            }

        record("gate-6-failed-restore-rollback", failed_restore_gate)

        record(
            "gate-7-cross-platform",
            lambda: {
                "platform": args.platform,
                "termux_compatible": args.platform == "termux",
                "ubuntu_compatible": args.platform == "ubuntu",
                "database": database_state(db_path),
                "api_reachable": bool(api.get("/health")),
            },
        )
    except Exception:
        report["status"] = "failed"
        report["completed_at"] = utc_now()
        output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return 1

    report["status"] = "passed"
    report["completed_at"] = utc_now()
    report["gate_count"] = len(report["gates"])
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"S8 gate report: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
