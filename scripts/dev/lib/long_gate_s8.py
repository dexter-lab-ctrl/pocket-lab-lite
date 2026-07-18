#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sqlite3
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
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise GateError(f"{method} {path} failed: {type(exc).__name__}") from exc

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


def database_state(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise GateError("SQLite database file is unavailable")
    uri = f"file:{path}?mode=ro"
    with sqlite3.connect(uri, uri=True, timeout=5) as conn:
        quick = str(conn.execute("PRAGMA quick_check").fetchone()[0])
        run_count = int(conn.execute("SELECT COUNT(*) FROM security_scan_runs").fetchone()[0])
        version = int(conn.execute("SELECT COALESCE(MAX(version),0) FROM schema_migrations").fetchone()[0])
    return {"quick_check": quick, "security_run_count": run_count, "schema_version": version}


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


def run_quick_scan(api: Api, timeout: float) -> dict[str, Any]:
    submitted = api.post("/api/lite/security/check", {"profile": "quick"})
    expected_run = str(submitted.get("run_id") or "")

    def terminal(payload: dict[str, Any]) -> bool:
        status = str(payload.get("status") or "").lower()
        same = not expected_run or str(payload.get("run_id") or "") == expected_run
        return same and status in TERMINAL_SCAN

    progress = poll(
        "Quick Safety Check", timeout, 2.0, lambda: api.get("/api/lite/security/progress"), terminal
    )
    if str(progress.get("status") or "").lower() not in {"succeeded", "degraded"}:
        raise GateError(f"Quick Safety Check ended with {progress.get('status')}")
    return {
        "run_id": progress.get("run_id"),
        "status": progress.get("status"),
        "percent": progress.get("percent") or progress.get("current_percent"),
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
            if not restored.get("rollback_available") or restored.get("parity", {}).get("matched") is not True:
                raise GateError("Restore did not retain rollback or pass parity")
            return {
                "state_b_scan": state_b_scan,
                "preview_id": preview.get("preview_id"),
                "restore_id": restore_id,
                "rollback_available": restored.get("rollback_available"),
                "parity_matched": restored.get("parity", {}).get("matched"),
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
            submitted_restore = api.post(
                f"/api/lite/recovery/database/backups/{fault_backup_id}/restore",
                {
                    "backup_id": fault_backup_id,
                    "preview_id": preview["preview_id"],
                    "confirm": True,
                    "gate_fail_after_replace": True,
                },
            )
            restore_id = str(submitted_restore.get("restore_id") or "")
            failed = wait_restore(api, restore_id, args.operation_timeout, "failed")
            rollback = failed.get("rollback") or {}
            if rollback.get("status") != "completed":
                raise GateError("Injected restore failure did not complete automatic rollback")
            progress = api.get("/api/lite/security/progress")
            if str(progress.get("run_id") or "") != str(marker_scan.get("run_id") or ""):
                raise GateError("Rollback did not restore the pre-failure Security state")
            state = database_state(db_path)
            return {
                "restore_id": restore_id,
                "rollback_status": rollback.get("status"),
                "marker_run_restored": True,
                "database": state,
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
