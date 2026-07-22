#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import statistics
import sys
import time
import uuid


ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "pocket-lab-final-structure" / "runtime"
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * fraction))))
    return ordered[index]


def device(index: int, epoch: int) -> dict:
    online = index % 5 != 0
    return {
        "id": f"device-{index:04d}",
        "name": f"Device {index:04d}",
        "role": "server_host" if index == 0 else "compute",
        "status": "healthy" if index == 0 else "active" if online else "offline",
        "connection": "online" if online or index == 0 else "offline",
        "agent_status": "online" if online else "offline",
        "supervisor_status": "healthy" if online else "unknown",
        "agent_process_status": "online" if online else "stopped",
        "last_seen_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch + index)),
        "is_current": index == 0,
    }


def app_payload(count: int, epoch: int) -> dict:
    apps = []
    for index in range(count):
        updated = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch + index))
        app_id = "photoprism" if index == 0 else f"synthetic-app-{index:03d}"
        apps.append(
            {
                "app_id": app_id,
                "name": "PhotoPrism" if index == 0 else f"Synthetic App {index:03d}",
                "installed": index % 4 != 0 or index == 0,
                "status": "ready" if index % 5 else "review",
                "summary": "Synthetic app lifecycle state.",
                "security": {"status": "protected" if index % 3 else "review"},
                "backup": {"latest_backup_id": f"app-backup-{index:03d}"},
                "actions": {
                    "check_app": {
                        "operation_id": f"check-{index:03d}",
                        "status": "succeeded",
                        "last_ran_at": updated,
                        "last_result": "Protected app",
                    },
                    "backup_app": {
                        "operation_id": f"backup-{index:03d}",
                        "status": "succeeded" if index % 2 else "failed",
                        "last_ran_at": updated,
                        "last_result": "Synthetic backup result.",
                    },
                },
            }
        )
    return {
        "apps": apps,
        "updated_at": time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch + count)
        ),
    }


def recovery_payload(iteration: int, epoch: int) -> dict:
    updated = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch + iteration))
    return {
        "status": "healthy",
        "summary": "Recovery ready",
        "last_backup": {
            "backup_id": f"backup-{iteration:04d}",
            "status": "verified",
            "verification_status": "verified",
            "created_at": updated,
            "verified_at": updated,
            "size_bytes": 1024 + iteration,
        },
        "latest_restore_preview": {
            "preview_id": f"preview-{iteration:04d}",
            "backup_id": f"backup-{iteration:04d}",
            "status": "ready",
            "created_at": updated,
            "summary": "Synthetic restore preview.",
        },
        "maintenance": {"active": False, "status": "idle"},
        "updated_at": updated,
    }


def payload(count: int, epoch: int) -> dict:
    return {
        "status": "healthy",
        "devices": [device(index, epoch) for index in range(count)],
        "remote_access": {"ready": True, "status": "healthy"},
        "latest_invite": None,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch + count)),
    }


def timed(callable_):
    started = time.perf_counter()
    result = callable_()
    return result, (time.perf_counter() - started) * 1000.0


def main() -> int:
    parser = argparse.ArgumentParser(description="Deterministic Lite Fleet SQLite benchmark")
    parser.add_argument("--state-dir", type=Path, default=Path.home() / ".pocketlab-dev" / "tmp")
    parser.add_argument("--samples", type=int, default=15)
    args = parser.parse_args()

    run_dir = args.state_dir.expanduser().resolve() / f"sqlite-p3-benchmark-{uuid.uuid4().hex[:8]}"
    run_dir.mkdir(parents=True, exist_ok=False)
    os.environ["POCKETLAB_STATE_DIR"] = str(run_dir / "state")
    os.environ["POCKETLAB_LITE_DB_PATH"] = str(run_dir / "state" / "pocketlab-lite.sqlite3")

    from api_fastapi.db.connection import reset_sqlite_path_cache
    from api_fastapi.services.lite_control_plane_store import ControlPlaneProjectionStore

    reset_sqlite_path_cache()
    store = ControlPlaneProjectionStore()
    store.initialize()
    report: dict[str, object] = {
        "kind": "synthetic-local",
        "database": "isolated",
        "external_services": False,
        "samples": args.samples,
        "fleets": {},
    }

    base_epoch = 1_780_000_000
    for label, count in (("small", 5), ("medium", 50), ("growing", 250)):
        model = payload(count, base_epoch)
        _, rebuild_ms = timed(lambda: store.project_fleet(model))

        # Grow history without changing fleet cardinality.
        history_samples = 30 if label == "growing" else 5
        history_ms: list[float] = []
        for iteration in range(history_samples):
            updated = payload(count, base_epoch + (iteration + 1) * 60)
            _, duration = timed(lambda updated=updated: store.project_fleet(updated))
            history_ms.append(duration)

        for command_index in range(count * 2):
            store.record_command(
                command_id=f"{label}-command-{command_index:05d}",
                subject="pocketlab.commands.node.synthetic.restart_agent",
                status="succeeded" if command_index % 4 else "failed",
                entity_type="device",
                entity_id=f"device-{command_index % count:04d}",
                summary="Synthetic benchmark command lifecycle.",
            )

        store.invalidate_after_database_replacement()
        cold_ms: list[float] = []
        warm_ms: list[float] = []
        prepared = None
        for _ in range(max(3, args.samples)):
            store.invalidate_after_database_replacement()
            prepared, duration = timed(
                lambda: store.prepared_read(
                    domain="fleet",
                    key=label,
                    builder=lambda model=model: model,
                    projector=store.project_fleet,
                    stale_after_ms=60_000,
                    max_stale_ms=120_000,
                )
            )
            cold_ms.append(duration)
            _, duration = timed(
                lambda: store.prepared_read(
                    domain="fleet",
                    key=label,
                    builder=lambda model=model: model,
                    projector=store.project_fleet,
                    stale_after_ms=60_000,
                    max_stale_ms=120_000,
                )
            )
            warm_ms.append(duration)

        rows = store.fleet_rows()
        encoded = json.dumps(prepared.payload if prepared else model, separators=(",", ":")).encode("utf-8")
        report["fleets"][label] = {
            "device_count": count,
            "projection_rebuild_ms": round(rebuild_ms, 3),
            "history_projection_median_ms": round(statistics.median(history_ms), 3),
            "cold_median_ms": round(statistics.median(cold_ms), 3),
            "cold_p95_ms": round(percentile(cold_ms, 0.95), 3),
            "warm_median_ms": round(statistics.median(warm_ms), 3),
            "warm_p95_ms": round(percentile(warm_ms, 0.95), 3),
            "payload_bytes": len(encoded),
            "projection_rows": len(rows),
            "duplicate_device_rows": len(rows) - len({row["device_id"] for row in rows}),
        }

    app_model = app_payload(25, base_epoch + 10_000)
    _, app_rebuild_ms = timed(lambda: store.project_apps(app_model))
    app_cold_ms: list[float] = []
    app_warm_ms: list[float] = []
    app_prepared = None
    for _ in range(max(3, args.samples)):
        store.invalidate_after_database_replacement()
        app_prepared, duration = timed(
            lambda: store.prepared_read(
                domain="apps",
                key="lifecycle-benchmark",
                builder=lambda: app_model,
                projector=store.project_apps,
                stale_after_ms=60_000,
                max_stale_ms=120_000,
            )
        )
        app_cold_ms.append(duration)
        _, duration = timed(
            lambda: store.prepared_read(
                domain="apps",
                key="lifecycle-benchmark",
                builder=lambda: app_model,
                projector=store.project_apps,
                stale_after_ms=60_000,
                max_stale_ms=120_000,
            )
        )
        app_warm_ms.append(duration)
    report["app_lifecycle"] = {
        "app_count": 25,
        "projection_rebuild_ms": round(app_rebuild_ms, 3),
        "cold_median_ms": round(statistics.median(app_cold_ms), 3),
        "cold_p95_ms": round(percentile(app_cold_ms, 0.95), 3),
        "warm_median_ms": round(statistics.median(app_warm_ms), 3),
        "warm_p95_ms": round(percentile(app_warm_ms, 0.95), 3),
        "payload_bytes": len(
            json.dumps(
                app_prepared.payload if app_prepared else app_model,
                separators=(",", ":"),
            ).encode("utf-8")
        ),
        "history_rows": len(store.app_action_history("photoprism", limit=100)["items"]),
    }

    for iteration in range(40):
        store.project_recovery(recovery_payload(iteration, base_epoch + 20_000))
    recovery_model = recovery_payload(40, base_epoch + 20_000)
    _, recovery_rebuild_ms = timed(lambda: store.project_recovery(recovery_model))
    recovery_cold_ms: list[float] = []
    recovery_warm_ms: list[float] = []
    recovery_prepared = None
    for _ in range(max(3, args.samples)):
        store.invalidate_after_database_replacement()
        recovery_prepared, duration = timed(
            lambda: store.prepared_read(
                domain="recovery",
                key="summary-benchmark",
                builder=lambda: recovery_model,
                projector=store.project_recovery,
                stale_after_ms=60_000,
                max_stale_ms=120_000,
            )
        )
        recovery_cold_ms.append(duration)
        _, duration = timed(
            lambda: store.prepared_read(
                domain="recovery",
                key="summary-benchmark",
                builder=lambda: recovery_model,
                projector=store.project_recovery,
                stale_after_ms=60_000,
                max_stale_ms=120_000,
            )
        )
        recovery_warm_ms.append(duration)
    report["recovery_summary"] = {
        "operation_rows": store.recovery_operation_history(limit=100)["count"],
        "projection_rebuild_ms": round(recovery_rebuild_ms, 3),
        "cold_median_ms": round(statistics.median(recovery_cold_ms), 3),
        "cold_p95_ms": round(percentile(recovery_cold_ms, 0.95), 3),
        "warm_median_ms": round(statistics.median(recovery_warm_ms), 3),
        "warm_p95_ms": round(percentile(recovery_warm_ms, 0.95), 3),
        "payload_bytes": len(
            json.dumps(
                recovery_prepared.payload if recovery_prepared else recovery_model,
                separators=(",", ":"),
            ).encode("utf-8")
        ),
    }

    command_write_ms: list[float] = []
    for index in range(200):
        _, duration = timed(
            lambda index=index: store.record_command(
                command_id=f"writer-benchmark-{index:04d}",
                subject="pocketlab.commands.node.synthetic.restart_agent",
                status="succeeded",
                entity_type="device",
                entity_id=f"device-{index % 25:04d}",
                summary="Synthetic command lifecycle.",
            )
        )
        command_write_ms.append(duration)
    report["command_writes"] = {
        "count": len(command_write_ms),
        "median_ms": round(statistics.median(command_write_ms), 3),
        "p95_ms": round(percentile(command_write_ms, 0.95), 3),
        "history_rows": store.command_history(limit=100)["count"],
    }

    report["query_plans"] = store.query_plan_evidence()
    report["sqlite_runtime"] = store.metrics()
    report["run_dir"] = str(run_dir)
    print(json.dumps(report, indent=2, sort_keys=True))
    store.shutdown()
    if os.environ.get("POCKETLAB_KEEP_BENCHMARK_STATE", "0") not in {"1", "true", "yes"}:
        shutil.rmtree(run_dir, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
