#!/usr/bin/env python3
"""Phase 5 Group 4 storage pressure and Android lifecycle gates.

The module reuses the Group 1-3 run identity, report, HTTP, SQLite, process,
checkpoint, and sanitization contracts. Synthetic storage work is isolated under
the run directory; live storage pressure is capped and requires an independent
activation plus explicit CLI opt-in in the shell orchestrator.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import secrets
import select
import shutil
import sqlite3
import statistics
import sys
import threading
import time
from pathlib import Path
from typing import Any, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parent))
import long_gate_group2 as g2  # noqa: E402
import long_gate_group3 as g3  # noqa: E402

SCHEMA_VERSION = 1
TERMINAL = {"succeeded", "degraded", "failed", "cancelled", "canceled", "completed"}
TERMINAL_SUCCESS = {"succeeded", "degraded", "completed"}
ALLOWED_STORAGE_FAILPOINTS = (
    "sqlite_lifecycle_write",
    "compatibility_json_write",
    "security_evidence_write",
    "atomic_temp_write",
    "atomic_fsync",
    "atomic_replace",
    "backup_output_write",
)
SHARED_STORAGE_PARTS = ("/storage/emulated/", "/sdcard/", "/mnt/sdcard/")
FORBIDDEN_APP_PARTS = ("photoprism/originals", "photoprism/import")


def passive_checkpoint(db_path: Path) -> dict[str, Any]:
    started = time.monotonic()
    try:
        connection = sqlite3.connect(str(db_path), timeout=2.0, isolation_level=None)
        try:
            connection.execute("PRAGMA busy_timeout = 2000")
            row = connection.execute("PRAGMA wal_checkpoint(PASSIVE)").fetchone()
        finally:
            connection.close()
        busy, log_pages, checkpointed_pages = [int(item or 0) for item in (row or (0, 0, 0))[:3]]
        ratio = checkpointed_pages / log_pages if log_pages > 0 else 1.0
        return {
            "timestamp": g2.utc_now(),
            "ok": True,
            "busy": busy,
            "log_pages": log_pages,
            "checkpointed_pages": checkpointed_pages,
            "progress_ratio": round(ratio, 6),
            "latency_seconds": round(time.monotonic() - started, 6),
            "sanitized": True,
        }
    except sqlite3.Error as exc:
        return {
            "timestamp": g2.utc_now(),
            "ok": False,
            "busy": None,
            "log_pages": None,
            "checkpointed_pages": None,
            "progress_ratio": None,
            "latency_seconds": round(time.monotonic() - started, 6),
            "error_type": type(exc).__name__,
            "sanitized": True,
        }


def sqlite_health(db_path: Path) -> dict[str, Any]:
    try:
        connection = sqlite3.connect(str(db_path), timeout=3.0, isolation_level=None)
        try:
            quick = str(connection.execute("PRAGMA quick_check").fetchone()[0])
            journal = str(connection.execute("PRAGMA journal_mode").fetchone()[0]).lower()
            foreign_keys = int(connection.execute("PRAGMA foreign_keys").fetchone()[0])
        finally:
            connection.close()
        return {
            "timestamp": g2.utc_now(),
            "ok": quick.lower() == "ok" and journal == "wal",
            "quick_check": quick,
            "journal_mode": journal,
            "foreign_keys": foreign_keys,
            "sanitized": True,
        }
    except sqlite3.Error as exc:
        return {
            "timestamp": g2.utc_now(),
            "ok": False,
            "quick_check": "unavailable",
            "journal_mode": "unknown",
            "foreign_keys": None,
            "error_type": type(exc).__name__,
            "sanitized": True,
        }


def storage_sizes(db_path: Path) -> dict[str, Any]:
    def size(path: Path) -> int:
        try:
            return int(path.stat().st_size)
        except OSError:
            return 0

    return {
        "timestamp": g2.utc_now(),
        "database_bytes": size(db_path),
        "wal_bytes": size(Path(f"{db_path}-wal")),
        "shm_bytes": size(Path(f"{db_path}-shm")),
        "sanitized": True,
    }


def evaluate_wal_samples(
    checkpoints: list[dict[str, Any]],
    readers: list[dict[str, Any]],
    writers: list[dict[str, Any]],
    storage: list[dict[str, Any]],
    *,
    wal_budget_bytes: int,
    reader_p95_budget: float,
    writer_p95_budget: float,
    contention_retry_budget: int,
) -> tuple[list[str], dict[str, Any]]:
    reader_latencies = [float(item.get("latency_seconds") or 0) for item in readers if item.get("ok")]
    writer_latencies = [float(item.get("latency_seconds") or 0) for item in writers if item.get("ok")]
    reader_failures = sum(1 for item in readers if not item.get("ok"))
    writer_failures = sum(1 for item in writers if not item.get("ok"))
    locked = sum(1 for item in [*readers, *writers] if "locked" in str(item.get("error") or item.get("error_type") or "").lower())
    busy_samples = sum(1 for item in checkpoints if int(item.get("busy") or 0) > 0)
    progress_samples = sum(1 for item in checkpoints if int(item.get("checkpointed_pages") or 0) > 0 or int(item.get("log_pages") or 0) == 0)
    wal_values = [int(item.get("wal_bytes") or 0) for item in storage]
    wal_peak = max(wal_values, default=0)
    wal_final = wal_values[-1] if wal_values else 0
    wal_growth = wal_final - (wal_values[0] if wal_values else 0)
    reader_latency = g2.latency_summary(reader_latencies)
    writer_latency = g2.latency_summary(writer_latencies)
    failures: list[str] = []
    if reader_failures:
        failures.append("reader_failures")
    if writer_failures:
        failures.append("writer_failures")
    if locked > contention_retry_budget:
        failures.append("database_lock_budget_exceeded")
    if checkpoints and progress_samples == 0 and wal_peak > 0:
        failures.append("checkpoint_no_progress")
    if checkpoints and busy_samples == len(checkpoints) and len(checkpoints) >= 3:
        failures.append("checkpoint_busy_sustained")
    if wal_growth > wal_budget_bytes:
        failures.append("wal_growth_budget_exceeded")
    if reader_latency.get("p95") is not None and float(reader_latency["p95"]) > reader_p95_budget:
        failures.append("reader_p95_budget_exceeded")
    if writer_latency.get("p95") is not None and float(writer_latency["p95"]) > writer_p95_budget:
        failures.append("writer_p95_budget_exceeded")
    return failures, {
        "reader_latency": reader_latency,
        "writer_latency": writer_latency,
        "read_failures": reader_failures,
        "write_failures": writer_failures,
        "database_locked_errors": locked,
        "checkpoint_busy_samples": busy_samples,
        "checkpoint_progress_samples": progress_samples,
        "wal_peak_bytes": wal_peak,
        "wal_final_bytes": wal_final,
        "wal_growth_bytes": wal_growth,
    }


@contextlib.contextmanager
def isolated_runtime(ctx: g2.Context, root: Path):
    root = root.resolve()
    state = root / "state"
    db_path = state / "pocketlab-lite.sqlite3"
    state.mkdir(parents=True, exist_ok=True)
    saved = {key: os.environ.get(key) for key in (
        "POCKETLAB_STATE_DIR",
        "POCKETLAB_LITE_DB_PATH",
        "POCKETLAB_LITE_SECURITY_STORE_MODE",
        "POCKETLAB_GATE_FAULT_INJECTION",
        "POCKETLAB_GATE_STORAGE_TEST_MODE",
        "POCKETLAB_GATE_ISOLATED_ROOT",
        "POCKETLAB_GATE_STORAGE_FAILPOINT",
    )}
    os.environ.update({
        "POCKETLAB_STATE_DIR": str(state),
        "POCKETLAB_LITE_DB_PATH": str(db_path),
        "POCKETLAB_LITE_SECURITY_STORE_MODE": "sqlite",
        "POCKETLAB_GATE_ISOLATED_ROOT": str(root),
    })
    runtime = ctx.repo_root / "pocket-lab-final-structure" / "runtime"
    sys.path.insert(0, str(runtime))
    try:
        yield state, db_path
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _isolated_repository(ctx: g2.Context, root: Path):
    with isolated_runtime(ctx, root) as pair:
        from api_fastapi.db.connection import reset_sqlite_path_cache
        from api_fastapi.services import lite_security_store

        reset_sqlite_path_cache()
        lite_security_store._INITIALIZED_DATABASES.clear()
        repository = lite_security_store.SecuritySQLiteRepository(initialize=True)
        yield pair[0], pair[1], repository, lite_security_store


def _wal_isolated(ctx: g2.Context, args: argparse.Namespace, state: dict[str, Any]) -> dict[str, Any]:
    stage_root = ctx.run_dir / "tmp" / "wal-pressure-isolated"
    stage_root.mkdir(parents=True, exist_ok=True)
    checkpoints_path = ctx.gate_dir / "checkpoints.jsonl"
    readers_path = ctx.gate_dir / "readers.jsonl"
    writers_path = ctx.gate_dir / "writers.jsonl"
    storage_path = ctx.gate_dir / "storage.jsonl"
    health_path = ctx.gate_dir / "sqlite-health.jsonl"
    lock = threading.Lock()
    stop = threading.Event()
    elapsed_before = float(state.get("isolated_elapsed_seconds") or 0.0)
    remaining = max(0.0, float(args.duration_seconds) - elapsed_before)
    writer_count = int(state.get("isolated_writer_operations") or 0)
    reader_count = int(state.get("isolated_reader_operations") or 0)
    failures: list[str] = []

    generator = _isolated_repository(ctx, stage_root)
    state_dir, db_path, repository, store = next(generator)

    def append(path: Path, payload: dict[str, Any]) -> None:
        with lock:
            g2.append_jsonl(path, payload)

    def writer() -> None:
        nonlocal writer_count
        index = writer_count
        while not stop.is_set():
            index += 1
            run_id = f"phase5-wal-{ctx.run_id[-24:]}-{index}"
            started = time.monotonic()
            try:
                result = repository.reserve_scan(
                    run_id=run_id,
                    profile="quick",
                    summary="Phase 5 isolated WAL fixture.",
                    requested_at=store.utc_now(),
                    command_id=run_id,
                    correlation_id=run_id,
                )
                if not result.reserved:
                    raise RuntimeError("isolated_reservation_not_created")
                repository.mark_published_and_accepted(run_id, published_at=store.utc_now())
                repository.mark_running(run_id, started_at=store.utc_now(), summary="Isolated WAL fixture running.")
                for percent in (17, 42, 73):
                    repository.record_progress(
                        run_id,
                        status="running",
                        stage=f"fixture-{percent}",
                        percent=percent,
                        message="Isolated WAL fixture progress.",
                        created_at=store.utc_now(),
                    )
                repository.complete_run(
                    run_id,
                    status="succeeded",
                    summary="Isolated WAL fixture completed.",
                    score=100,
                    completed_at=store.utc_now(),
                    evidence_refs=["isolated-fixture"],
                    metadata={"phase5_fixture": True},
                )
                item = {
                    "timestamp": g2.utc_now(),
                    "operation": index,
                    "ok": True,
                    "latency_seconds": round(time.monotonic() - started, 6),
                    "sanitized": True,
                }
                writer_count = index
            except Exception as exc:
                item = {
                    "timestamp": g2.utc_now(),
                    "operation": index,
                    "ok": False,
                    "latency_seconds": round(time.monotonic() - started, 6),
                    "error_type": type(exc).__name__,
                    "error": "database_locked" if "locked" in str(exc).lower() else "writer_failed",
                    "sanitized": True,
                }
                failures.append("writer_failed")
            append(writers_path, item)
            stop.wait(max(0.001, args.writer_interval_ms / 1000.0))

    def reader() -> None:
        nonlocal reader_count
        index = reader_count
        while not stop.is_set():
            index += 1
            started = time.monotonic()
            try:
                payload = repository.get_progress()
                item = {
                    "timestamp": g2.utc_now(),
                    "operation": index,
                    "ok": True,
                    "run_id": str((payload or {}).get("run_id") or ""),
                    "revision": (payload or {}).get("revision"),
                    "latency_seconds": round(time.monotonic() - started, 6),
                    "sanitized": True,
                }
                reader_count = index
            except Exception as exc:
                item = {
                    "timestamp": g2.utc_now(),
                    "operation": index,
                    "ok": False,
                    "latency_seconds": round(time.monotonic() - started, 6),
                    "error_type": type(exc).__name__,
                    "error": "database_locked" if "locked" in str(exc).lower() else "reader_failed",
                    "sanitized": True,
                }
                failures.append("reader_failed")
            append(readers_path, item)
            stop.wait(max(0.001, args.reader_interval_ms / 1000.0))

    writer_thread = threading.Thread(target=writer, name="phase5-wal-writer", daemon=True)
    reader_thread = threading.Thread(target=reader, name="phase5-wal-reader", daemon=True)
    writer_thread.start()
    reader_thread.start()
    started = time.monotonic()
    next_checkpoint = started
    next_health = started
    try:
        while time.monotonic() - started < remaining:
            now = time.monotonic()
            if now >= next_checkpoint:
                append(checkpoints_path, passive_checkpoint(db_path))
                append(storage_path, storage_sizes(db_path))
                next_checkpoint = now + max(1.0, float(args.checkpoint_interval_seconds))
            if now >= next_health:
                append(health_path, sqlite_health(db_path))
                next_health = now + max(1.0, float(args.health_interval_seconds))
            state.update({
                "isolated_elapsed_seconds": elapsed_before + (now - started),
                "isolated_writer_operations": writer_count,
                "isolated_reader_operations": reader_count,
                "isolated_db_label": "run_test_database",
                "updated_at": g2.utc_now(),
            })
            g2.atomic_write_json(ctx.gate_dir / "state.json", state)
            g2.ensure_report_budget(ctx.run_dir, ctx.report_limit_bytes)
            time.sleep(0.1)
    finally:
        stop.set()
        writer_thread.join(timeout=5)
        reader_thread.join(timeout=5)
        try:
            next(generator)
        except StopIteration:
            pass
    final_health = sqlite_health(db_path)
    append(health_path, final_health)
    append(checkpoints_path, passive_checkpoint(db_path))
    append(storage_path, storage_sizes(db_path))
    if args.final_truncate_checkpoint:
        if writer_thread.is_alive() or reader_thread.is_alive():
            raise g2.GateFailure("Final truncate checkpoint refused while isolated writers are active.", stage="isolated-final-checkpoint", retryable=False)
        connection = sqlite3.connect(str(db_path), timeout=3.0, isolation_level=None)
        try:
            row = connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        finally:
            connection.close()
        final_checkpoint_status = {"busy": int(row[0]), "log_pages": int(row[1]), "checkpointed_pages": int(row[2])}
    else:
        final_checkpoint_status = {"status": "not_requested"}
    state.update({
        "isolated_completed": True,
        "isolated_elapsed_seconds": float(args.duration_seconds),
        "isolated_writer_operations": writer_count,
        "isolated_reader_operations": reader_count,
    })
    g2.atomic_write_json(ctx.gate_dir / "state.json", state)
    return {
        "scenario": "isolated",
        "writer_operations": writer_count,
        "reader_operations": reader_count,
        "final_health": final_health,
        "final_checkpoint_status": final_checkpoint_status,
        "internal_failures": sorted(set(failures)),
        "db_path": db_path,
    }


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return g3.read_jsonl(path)


def bounded_parity_reconciliation(
    ctx: g2.Context,
    *,
    timeout_seconds: float = 30.0,
    interval_seconds: float = 2.0,
    evidence_path: Path | None = None,
) -> dict[str, Any]:
    """Wait briefly for compatibility projections without weakening final parity.

    SQLite quick-check remains fail-fast. Parity is retried only while SQLite is
    healthy, and the final unmatched result is returned to the caller to fail.
    """
    deadline = time.monotonic() + max(0.0, timeout_seconds)
    attempt = 0
    last: dict[str, Any] = {}
    while True:
        attempt += 1
        last = g2.run_sqlite_tools(ctx.repo_root, ctx.state_dir, ctx.db_path)
        sample = {
            "timestamp": g2.utc_now(),
            "attempt": attempt,
            "quick_check": last.get("quick_check"),
            "parity_matched": last.get("parity_matched"),
            "mismatch_fields": list(last.get("mismatch_fields") or []),
            "sanitized": True,
        }
        if evidence_path is not None:
            g2.append_jsonl(evidence_path, sample)
        if last.get("quick_check") != "ok":
            return {**last, "reconciliation_attempts": attempt, "reconciliation_status": "sqlite_unhealthy"}
        if last.get("parity_matched") is True:
            return {**last, "reconciliation_attempts": attempt, "reconciliation_status": "matched"}
        if time.monotonic() >= deadline:
            return {**last, "reconciliation_attempts": attempt, "reconciliation_status": "timeout"}
        time.sleep(max(0.1, interval_seconds))


def _wal_live(ctx: g2.Context, args: argparse.Namespace, state: dict[str, Any]) -> dict[str, Any]:
    checkpoints_path = ctx.gate_dir / "checkpoints.jsonl"
    readers_path = ctx.gate_dir / "readers.jsonl"
    writers_path = ctx.gate_dir / "writers.jsonl"
    storage_path = ctx.gate_dir / "storage.jsonl"
    health_path = ctx.gate_dir / "sqlite-health.jsonl"
    progress_path = ctx.gate_dir / "progress.jsonl"
    events_path = ctx.gate_dir / "events.jsonl"
    client = ctx.client()
    tracked = str(state.get("live_run_id") or "")
    if not tracked:
        lifecycle = g2.lifecycle_snapshot(ctx.db_path)
        if int(lifecycle.get("active_count") or 0) > 0:
            raise g2.GateFailure("WAL live observation requires no unrelated active Security run.", stage="live-preflight", retryable=True)
        submit, payload = g2.submit_quick_scan(ctx, client, f"wal-live-{ctx.run_id}", float(args.submission_timeout_seconds))
        g2.append_jsonl(events_path, {"timestamp": g2.utc_now(), "event": "wal.live.submission", **submit.safe_record(endpoint_type="proxy")})
        if not submit.ok:
            raise g2.GateFailure("WAL live Quick scan submission failed.", stage="live-submit", retryable=True)
        tracked = str(payload.get("run_id") or payload.get("command_id") or "")
        if not tracked:
            run, _ = g3.find_new_run(ctx.db_path, set(), g2.epoch_ms() - 5000, 20.0)
            tracked = str((run or {}).get("run_id") or "")
        if not tracked:
            raise g2.GateFailure("WAL live run identity could not be established.", stage="live-submit", retryable=False)
        state["live_run_id"] = tracked
        state["live_submission_completed"] = True
        g2.atomic_write_json(ctx.gate_dir / "state.json", state)
    started = time.monotonic()
    next_checkpoint = started
    terminal: dict[str, Any] | None = None
    while time.monotonic() - started < float(args.duration_seconds):
        progress, http = g2.progress_sample(ctx, client, base_url=ctx.proxy_base_url, endpoint_type="proxy")
        g2.append_jsonl(progress_path, progress)
        g2.append_jsonl(readers_path, {**http.safe_record(endpoint_type="progress"), "run_id": progress.get("run_id"), "revision": progress.get("revision")})
        lifecycle = g2.lifecycle_snapshot(ctx.db_path, run_id=tracked)
        run = lifecycle.get("run") if isinstance(lifecycle.get("run"), dict) else None
        if time.monotonic() >= next_checkpoint:
            g2.append_jsonl(checkpoints_path, passive_checkpoint(ctx.db_path))
            g2.append_jsonl(storage_path, storage_sizes(ctx.db_path))
            g2.append_jsonl(health_path, sqlite_health(ctx.db_path))
            next_checkpoint = time.monotonic() + max(1.0, float(args.checkpoint_interval_seconds))
        if run and str(run.get("status") or "").lower() in TERMINAL:
            terminal = run
            break
        state["live_elapsed_seconds"] = float(state.get("live_elapsed_seconds") or 0) + float(args.reader_interval_ms) / 1000.0
        g2.atomic_write_json(ctx.gate_dir / "state.json", state)
        g2.ensure_report_budget(ctx.run_dir, ctx.report_limit_bytes)
        time.sleep(max(0.2, args.reader_interval_ms / 1000.0))
    if terminal is None:
        terminal = g3.wait_terminal(ctx, tracked, timeout=max(1.0, float(args.run_timeout_seconds)), progress_path=progress_path, lifecycle_path=events_path)
    if not terminal:
        raise g2.GateFailure("WAL live scan did not reach a terminal state.", stage="live-terminal", retryable=False)
    state["live_completed"] = True
    g2.atomic_write_json(ctx.gate_dir / "state.json", state)
    return {
        "scenario": "live",
        "writer_operations": 1,
        "reader_operations": len(_read_jsonl(readers_path)),
        "terminal_status": terminal.get("status"),
        "run_id": tracked,
        "final_health": sqlite_health(ctx.db_path),
        "final_checkpoint_status": {"status": "not_requested"},
        "db_path": ctx.db_path,
    }


def run_wal_pressure(args: argparse.Namespace) -> int:
    ctx = g2.common_context(args)
    ctx.gate_dir.mkdir(parents=True, exist_ok=True)
    started_at = g2.utc_now()
    started_monotonic = time.monotonic()
    state_path = ctx.gate_dir / "state.json"
    state = g2.read_json(state_path, {})
    if state and state.get("gate_id") != ctx.gate_id:
        return g2.gate_failure_result(ctx, started_at, started_monotonic, g2.GateFailure("WAL resume state belongs to another gate.", stage="resume", retryable=False), {})
    if not state:
        state = {"schema_version": SCHEMA_VERSION, "run_id": ctx.run_id, "gate_id": ctx.gate_id, "scenario": args.scenario, "started_at": started_at, "sanitized": True}
        g2.atomic_write_json(state_path, state)
    stages: list[dict[str, Any]] = []
    try:
        for scenario in (["isolated", "live"] if args.scenario == "both" else [args.scenario]):
            if state.get(f"{scenario}_completed"):
                continue
            if scenario == "isolated":
                stages.append(_wal_isolated(ctx, args, state))
            else:
                stages.append(_wal_live(ctx, args, state))
        checkpoints = _read_jsonl(ctx.gate_dir / "checkpoints.jsonl")
        readers = _read_jsonl(ctx.gate_dir / "readers.jsonl")
        writers = _read_jsonl(ctx.gate_dir / "writers.jsonl")
        storage = _read_jsonl(ctx.gate_dir / "storage.jsonl")
        failures, metrics = evaluate_wal_samples(
            checkpoints,
            readers,
            writers,
            storage,
            wal_budget_bytes=int(args.wal_growth_budget_bytes),
            reader_p95_budget=float(args.reader_p95_budget_seconds),
            writer_p95_budget=float(args.writer_p95_budget_seconds),
            contention_retry_budget=int(args.contention_retry_budget),
        )
        if ctx.db_path.exists():
            health = bounded_parity_reconciliation(
                ctx,
                timeout_seconds=30.0,
                evidence_path=ctx.gate_dir / "parity-reconciliation.jsonl",
            )
            if health.get("quick_check") != "ok":
                failures.append("final_sqlite_quick_check")
            if health.get("parity_matched") is not True:
                failures.append("final_parity_mismatch")
        elif args.scenario == "isolated":
            isolated_health = next((item.get("final_health") for item in reversed(stages) if item.get("scenario") == "isolated"), {}) or {}
            health = {
                "quick_check": isolated_health.get("quick_check"),
                "parity_matched": None,
                "parity_status": "not_applicable_isolated",
            }
            if health.get("quick_check") != "ok":
                failures.append("final_isolated_sqlite_quick_check")
        else:
            health = {"quick_check": "unavailable", "parity_matched": None, "parity_status": "production_database_unavailable"}
            failures.extend(["final_sqlite_quick_check", "final_parity_mismatch"])
        read_degraded_count = sum(1 for item in _read_jsonl(ctx.gate_dir / "progress.jsonl") if item.get("read_degraded") is True)
        if read_degraded_count:
            failures.append("progress_read_degraded")
        result = {
            "run_id": ctx.run_id,
            "gate_id": ctx.gate_id,
            "gate": ctx.gate_id,
            "status": "failed" if failures else "passed",
            "scenario": args.scenario,
            "duration_seconds": round(time.monotonic() - started_monotonic, 3),
            "writer_operations": len(writers),
            "reader_operations": len(readers),
            "checkpoint_samples": len(checkpoints),
            **metrics,
            "contention_retries": metrics["database_locked_errors"],
            "read_degraded_count": read_degraded_count,
            "final_checkpoint_status": stages[-1].get("final_checkpoint_status") if stages else {"status": "preserved_on_resume"},
            "sqlite_quick_check": health.get("quick_check"),
            "parity_matched": health.get("parity_matched"),
            "parity_status": health.get("parity_status", "matched" if health.get("parity_matched") is True else "mismatch"),
            "failed_stage": "evaluation" if failures else "",
            "failure_reason": "WAL pressure requirements failed: " + ", ".join(sorted(set(failures))) + "." if failures else "",
            "retryable": False if failures else True,
            "resume_safe": True,
            "sanitized": True,
            "evidence_refs": [
                "gates/wal-pressure/checkpoints.jsonl",
                "gates/wal-pressure/readers.jsonl",
                "gates/wal-pressure/writers.jsonl",
                "gates/wal-pressure/storage.jsonl",
                "gates/wal-pressure/sqlite-health.jsonl",
                "gates/wal-pressure/progress.jsonl",
                "gates/wal-pressure/events.jsonl",
            ],
        }
        g2.write_result(ctx.gate_dir / "result.json", result)
        return 0 if not failures else 2
    except g2.GateFailure as exc:
        return g2.gate_failure_result(ctx, started_at, started_monotonic, exc, {"scenario": args.scenario})


def _safe_run_owned(path: Path, run_dir: Path) -> bool:
    candidate = path.expanduser().resolve(strict=False)
    root = run_dir.expanduser().resolve(strict=False)
    text = candidate.as_posix().lower()
    if candidate == root or root not in candidate.parents:
        return False
    if any(part in text for part in SHARED_STORAGE_PARTS + FORBIDDEN_APP_PARTS):
        return False
    return True


def storage_metrics(path: Path) -> dict[str, Any]:
    usage = shutil.disk_usage(path)
    percent = usage.free / usage.total * 100.0 if usage.total else 0.0
    return {
        "timestamp": g2.utc_now(),
        "total_bytes": int(usage.total),
        "free_bytes": int(usage.free),
        "free_percent": round(percent, 3),
        "sanitized": True,
    }


def safe_allocation_cap(
    *, free_bytes: int, requested_bytes: int, floor_bytes: int, reserve_bytes: int, maximum_bytes: int
) -> int:
    available = max(0, int(free_bytes) - int(floor_bytes) - int(reserve_bytes) - 8 * 1024 * 1024)
    return max(0, min(int(requested_bytes), int(maximum_bytes), available))


def allocate_bounded(path: Path, size_bytes: int, *, chunk_bytes: int = 1024 * 1024) -> int:
    if size_bytes < 0:
        raise ValueError("allocation size cannot be negative")
    path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with path.open("wb") as handle:
        block = b"\0" * min(chunk_bytes, max(1, size_bytes))
        while written < size_bytes:
            length = min(len(block), size_bytes - written)
            handle.write(block[:length])
            written += length
        handle.flush()
        os.fsync(handle.fileno())
    return written


def _set_failpoint(name: str) -> None:
    os.environ["POCKETLAB_GATE_FAULT_INJECTION"] = "1"
    os.environ["POCKETLAB_GATE_STORAGE_TEST_MODE"] = "1"
    os.environ["POCKETLAB_GATE_STORAGE_FAILPOINT"] = name


def _clear_failpoint() -> None:
    os.environ.pop("POCKETLAB_GATE_STORAGE_FAILPOINT", None)
    os.environ.pop("POCKETLAB_GATE_FAULT_INJECTION", None)
    os.environ.pop("POCKETLAB_GATE_STORAGE_TEST_MODE", None)


def _run_deterministic_failpoints(ctx: g2.Context) -> dict[str, Any]:
    root = ctx.run_dir / "tmp" / "low-storage-deterministic"
    root.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    zero_byte = 0
    partial_outputs = 0
    active_key_leaks = 0
    false_accepts = 0
    false_successes = 0
    generator = _isolated_repository(ctx, root)
    state_dir, db_path, repository, store = next(generator)
    from api_fastapi.services import lite_backup_manifest, lite_security, lite_security_evidence

    os.environ["POCKETLAB_GATE_ISOLATED_ROOT"] = str(root)
    baseline_file = state_dir / "security" / "security_state.json"
    baseline_file.parent.mkdir(parents=True, exist_ok=True)
    lite_security_evidence.write_json(baseline_file, {"status": "healthy", "revision": 1})

    def record(name: str, passed: bool, **details: Any) -> None:
        results.append({"timestamp": g2.utc_now(), "failpoint": name, "passed": bool(passed), **details, "sanitized": True})

    try:
        _set_failpoint("sqlite_lifecycle_write")
        run_id = "phase5-low-storage-lifecycle"
        try:
            repository.reserve_scan(run_id=run_id, profile="quick", summary="fixture", command_id=run_id, correlation_id=run_id)
            false_accepts += 1
            record("sqlite_lifecycle_write", False, outcome="unexpected_accept")
        except OSError as exc:
            active = repository.get_active_scan()
            active_key_leaks += 1 if active else 0
            record("sqlite_lifecycle_write", getattr(exc, "errno", None) == 28 and not active, outcome="rejected_before_reservation")
        _clear_failpoint()

        authority_run = "phase5-low-storage-authority"
        reservation = repository.reserve_scan(run_id=authority_run, profile="quick", summary="fixture", command_id=authority_run, correlation_id=authority_run)
        if not reservation.reserved:
            raise RuntimeError("isolated authority fixture could not be reserved")
        repository.mark_published_and_accepted(authority_run, published_at=store.utc_now())
        repository.mark_running(authority_run, started_at=store.utc_now(), summary="fixture running")
        repository.complete_run(authority_run, status="succeeded", summary="fixture completed", score=100, completed_at=store.utc_now(), evidence_refs=["fixture"])
        before = baseline_file.read_bytes()
        _set_failpoint("compatibility_json_write")
        try:
            lite_security_evidence.write_state({"status": "changed", "last_run": {"run_id": authority_run}})
            record("compatibility_json_write", False, outcome="unexpected_write")
        except OSError as exc:
            row = repository.get_run(authority_run)
            intact = baseline_file.read_bytes() == before
            record("compatibility_json_write", getattr(exc, "errno", None) == 28 and bool(row) and intact, sqlite_authority_preserved=bool(row), prior_file_preserved=intact)
        _clear_failpoint()

        evidence_run = "phase5-low-storage-evidence"
        reservation = repository.reserve_scan(run_id=evidence_run, profile="quick", summary="fixture", command_id=evidence_run, correlation_id=evidence_run)
        repository.mark_published_and_accepted(evidence_run, published_at=store.utc_now())
        repository.mark_running(evidence_run, started_at=store.utc_now(), summary="fixture running")
        _set_failpoint("security_evidence_write")
        caught: Exception | None = None
        try:
            lite_security_evidence.write_evidence(evidence_run, "summary.json", {"status": "succeeded"})
        except OSError as exc:
            caught = exc
        _clear_failpoint()
        if caught:
            lite_security.fail_security_run(evidence_run, caught)
        row = repository.get_run(evidence_run) or {}
        if str(row.get("status") or "") in TERMINAL_SUCCESS:
            false_successes += 1
        if row.get("active_key"):
            active_key_leaks += 1
        record("security_evidence_write", bool(caught) and str(row.get("status") or "") == "failed" and not row.get("active_key"), terminal_status=row.get("status"))

        for name in ("atomic_temp_write", "atomic_fsync", "atomic_replace"):
            target = state_dir / "security" / f"atomic-{name}.json"
            lite_security_evidence.write_json(target, {"revision": 1, "valid": True})
            prior = target.read_bytes()
            _set_failpoint(name)
            caught = None
            try:
                lite_security_evidence.write_json(target, {"revision": 2, "valid": False})
            except OSError as exc:
                caught = exc
            _clear_failpoint()
            intact = target.exists() and target.stat().st_size > 0 and target.read_bytes() == prior
            if target.exists() and target.stat().st_size == 0:
                zero_byte += 1
            partials = list(target.parent.glob(f".{target.name}.*.tmp"))
            partial_outputs += len(partials)
            record(name, bool(caught) and intact and not partials, prior_file_preserved=intact, partial_temp_count=len(partials))

        _set_failpoint("backup_output_write")
        caught = None
        try:
            lite_backup_manifest.write_manifest({"backup_id": "phase5-low-storage-backup", "status": "complete"})
        except OSError as exc:
            caught = exc
        _clear_failpoint()
        manifest = lite_backup_manifest.manifest_path("phase5-low-storage-backup")
        complete = manifest.exists()
        partials = list(manifest.parent.glob(f".{manifest.name}.*.tmp"))
        partial_outputs += len(partials)
        record("backup_output_write", bool(caught) and not complete and not partials, corrupt_complete=complete, partial_temp_count=len(partials))
    finally:
        _clear_failpoint()
        try:
            next(generator)
        except StopIteration:
            pass

    for item in results:
        g2.append_jsonl(ctx.gate_dir / "deterministic" / "failpoints.jsonl", item)
    health = sqlite_health(db_path)
    return {
        "results": results,
        "failpoints_requested": len(ALLOWED_STORAGE_FAILPOINTS),
        "failpoints_completed": len(results),
        "failpoints_passed": sum(1 for item in results if item.get("passed")),
        "failpoints_failed": sum(1 for item in results if not item.get("passed")),
        "zero_byte_authoritative_files": zero_byte,
        "partial_outputs": partial_outputs,
        "active_key_leaks": active_key_leaks,
        "false_accepts": false_accepts,
        "false_successes": false_successes,
        "isolated_quick_check": health.get("quick_check"),
    }


def _low_storage_activation_path(ctx: g2.Context) -> Path:
    return ctx.state_dir / ".pocketlab-dev" / "gate-faults" / "low-storage-threshold.json"


def low_storage_test_thresholds(
    *,
    free_bytes: int,
    free_percent: float,
    configured_floor_percent: float,
) -> tuple[int, float]:
    floor_bytes = min(16 * 1024 * 1024 * 1024, int(free_bytes) + 1024 * 1024)
    floor_percent = min(99.9, max(float(configured_floor_percent), float(free_percent) + 0.5))
    return floor_bytes, floor_percent


def create_low_storage_activation(ctx: g2.Context, token: str, *, floor_bytes: int, floor_percent: float, lifetime_seconds: int = 300) -> Path:
    path = _low_storage_activation_path(ctx)
    payload = {
        "schema_version": 1,
        "scenario": "low-storage-threshold",
        "token_sha256": hashlib.sha256(token.encode("utf-8")).hexdigest(),
        "minimum_free_bytes": int(floor_bytes),
        "minimum_free_percent": float(floor_percent),
        "expires_at_epoch": time.time() + max(30, min(900, lifetime_seconds)),
        "sanitized": True,
    }
    g2.atomic_write_json(path, payload)
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return path


def disable_low_storage_activation(ctx: g2.Context) -> bool:
    path = _low_storage_activation_path(ctx)
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    return not path.exists()


def _post_recovery_scan(ctx: g2.Context, label: str, timeout: float, progress_path: Path, lifecycle_path: Path) -> tuple[str, dict[str, Any] | None]:
    run_id, run, _ = g3.final_independent_scan(ctx, label, timeout=timeout, progress_path=progress_path, lifecycle_path=lifecycle_path)
    return run_id, run


def _run_low_storage_live(ctx: g2.Context, args: argparse.Namespace, state: dict[str, Any]) -> dict[str, Any]:
    live_dir = ctx.gate_dir / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    storage_path = live_dir / "storage.jsonl"
    submissions_path = live_dir / "submissions.jsonl"
    lifecycle_path = live_dir / "lifecycle.jsonl"
    progress_path = live_dir / "progress.jsonl"
    events_path = live_dir / "events.jsonl"
    run_owned = ctx.run_dir / "tmp" / "low-storage-live"
    allocation = run_owned / "bounded-allocation.bin"
    reserve = run_owned / "emergency-reserve.bin"
    if not _safe_run_owned(allocation, ctx.run_dir) or not _safe_run_owned(reserve, ctx.run_dir):
        raise g2.GateFailure("Low-storage run-owned paths failed safety validation.", stage="live-path-safety", retryable=False)
    run_owned.mkdir(parents=True, exist_ok=True)

    if ctx.resume and (allocation.exists() or reserve.exists()) and not state.get("live_completed"):
        allocation.unlink(missing_ok=True)
        reserve.unlink(missing_ok=True)
        g2.append_jsonl(events_path, {"timestamp": g2.utc_now(), "event": "storage.interrupted_cleanup", "allocation_removed": not allocation.exists(), "reserve_removed": not reserve.exists(), "sanitized": True})
        state["live_interrupted_cleanup_completed"] = True
        g2.atomic_write_json(ctx.gate_dir / "state.json", state)
        raise g2.GateFailure("Interrupted low-storage allocation was recovered. Start a new explicit run before applying pressure again.", stage="live-resume-cleanup", retryable=True)

    before = storage_metrics(ctx.state_dir)
    g2.append_jsonl(storage_path, {**before, "stage": "before"})
    floor_bytes = int(args.min_free_space_bytes)
    floor_percent = float(args.min_free_space_percent)
    reserve_bytes = int(args.emergency_reserve_bytes)
    requested = int(args.max_allocation_bytes)
    cap = safe_allocation_cap(
        free_bytes=int(before["free_bytes"]),
        requested_bytes=requested,
        floor_bytes=floor_bytes,
        reserve_bytes=reserve_bytes,
        maximum_bytes=int(args.absolute_allocation_cap_bytes),
    )
    if requested <= 0:
        raise g2.GateFailure("Live low-storage requires an explicit positive --max-allocation-bytes value.", stage="live-preflight", retryable=False)
    if cap != requested:
        raise g2.GateFailure(f"Requested allocation exceeds the computed safe cap ({cap} bytes).", stage="live-preflight", retryable=False)
    if int(before["free_bytes"]) < floor_bytes + reserve_bytes + requested + 8 * 1024 * 1024:
        raise g2.GateFailure("Current free storage is already below the live-test safety margin.", stage="live-preflight", retryable=False)
    lifecycle = g2.lifecycle_snapshot(ctx.db_path)
    if int(lifecycle.get("active_count") or 0) > 0:
        raise g2.GateFailure("Live low-storage requires no unrelated active Security run.", stage="live-preflight", retryable=True)
    initial_runs = {str(item.get("run_id") or "") for item in g3.runs_after(ctx.db_path, 0)}
    token = secrets.token_urlsafe(32)
    allocation_removed = False
    reserve_available = False
    activation_disabled = False
    try:
        allocate_bounded(reserve, reserve_bytes)
        reserve_available = reserve.exists() and reserve.stat().st_size == reserve_bytes
        state.update({"live_reserve_created": True, "reserve_bytes": reserve_bytes, "safe_to_repeat": False})
        g2.atomic_write_json(ctx.gate_dir / "state.json", state)
        allocate_bounded(allocation, requested)
        state.update({"live_allocation_created": True, "allocation_bytes": requested, "safe_to_repeat": False})
        g2.atomic_write_json(ctx.gate_dir / "state.json", state)
        threshold = storage_metrics(ctx.state_dir)
        g2.append_jsonl(storage_path, {**threshold, "stage": "threshold"})
        # The gate threshold remains safely above real exhaustion and is scoped to
        # this one loopback request by the activation token. On high-free-space
        # devices the percentage threshold is what deterministically trips the guard.
        test_floor, test_floor_percent = low_storage_test_thresholds(
            free_bytes=int(threshold["free_bytes"]),
            free_percent=float(threshold["free_percent"]),
            configured_floor_percent=floor_percent,
        )
        if test_floor <= int(threshold["free_bytes"]) and test_floor_percent <= float(threshold["free_percent"]):
            raise g2.GateFailure("A safe low-storage test threshold could not be constructed.", stage="live-threshold", retryable=False)
        create_low_storage_activation(ctx, token, floor_bytes=test_floor, floor_percent=test_floor_percent)
        state["live_activation_created"] = True
        g2.atomic_write_json(ctx.gate_dir / "state.json", state)
        client = ctx.client(timeout=float(args.submission_timeout_seconds))
        submission = client.request(
            "POST",
            ctx.direct_base_url,
            "/api/lite/security/check",
            body={"profile": "quick", "reason": f"phase5 {ctx.gate_id} storage guard"},
            extra_headers={
                "X-PocketLab-Gate-Scenario": "low-storage-threshold",
                "X-PocketLab-Gate-Token": token,
            },
        )
        record = submission.safe_record(endpoint_type="direct_api")
        record.update({
            "accepted": bool((submission.body or {}).get("accepted")),
            "reason": str((submission.body or {}).get("reason") or ""),
            "sanitized": True,
        })
        g2.append_jsonl(submissions_path, record)
        after_runs = {str(item.get("run_id") or "") for item in g3.runs_after(ctx.db_path, 0)}
        created = sorted(item for item in after_runs - initial_runs if item)
        progress, progress_http = g2.progress_sample(ctx, client, base_url=ctx.direct_base_url, endpoint_type="direct_api")
        g2.append_jsonl(progress_path, progress)
        if submission.status_code != 507 or record["accepted"] or created:
            raise g2.GateFailure("Low-storage guard did not reject before durable run creation.", stage="live-rejection", retryable=False)
        if not progress_http.ok:
            raise g2.GateFailure("Current Progress was not readable during low-storage rejection.", stage="live-progress", retryable=False)
        state["live_rejection_verified"] = True
        g2.atomic_write_json(ctx.gate_dir / "state.json", state)
    finally:
        activation_disabled = disable_low_storage_activation(ctx)
        allocation.unlink(missing_ok=True)
        allocation_removed = not allocation.exists()
        reserve.unlink(missing_ok=True)
        g2.append_jsonl(events_path, {
            "timestamp": g2.utc_now(),
            "event": "storage.cleanup",
            "activation_disabled": activation_disabled,
            "allocation_removed": allocation_removed,
            "reserve_removed": not reserve.exists(),
            "sanitized": True,
        })
    after_cleanup = storage_metrics(ctx.state_dir)
    g2.append_jsonl(storage_path, {**after_cleanup, "stage": "after_cleanup"})
    post_run, post_state = _post_recovery_scan(ctx, f"low-storage-post-{ctx.run_id}", float(args.run_timeout_seconds), progress_path, lifecycle_path)
    if not post_state or str(post_state.get("status") or "").lower() not in TERMINAL_SUCCESS:
        raise g2.GateFailure("The post-storage Quick scan did not succeed.", stage="live-post-recovery", retryable=False)
    state["live_completed"] = True
    g2.atomic_write_json(ctx.gate_dir / "state.json", state)
    return {
        "free_bytes_before": before["free_bytes"],
        "free_percent_before": before["free_percent"],
        "configured_floor_bytes": floor_bytes,
        "configured_floor_percent": floor_percent,
        "test_floor_bytes": test_floor,
        "test_floor_percent": test_floor_percent,
        "reserve_bytes": reserve_bytes,
        "allocation_bytes": requested,
        "free_bytes_at_threshold": threshold["free_bytes"],
        "submission_status": record.get("reason"),
        "submission_http_status": submission.status_code,
        "command_published": False,
        "run_created": False,
        "progress_readable": True,
        "allocation_removed": allocation_removed,
        "reserve_available": reserve_available,
        "free_bytes_after_cleanup": after_cleanup["free_bytes"],
        "post_recovery_scan_run_id": post_run,
        "fault_injection_disabled": activation_disabled,
    }


def run_low_storage(args: argparse.Namespace) -> int:
    ctx = g2.common_context(args)
    ctx.gate_dir.mkdir(parents=True, exist_ok=True)
    (ctx.gate_dir / "deterministic").mkdir(parents=True, exist_ok=True)
    started_at = g2.utc_now()
    started_monotonic = time.monotonic()
    state_path = ctx.gate_dir / "state.json"
    state = g2.read_json(state_path, {})
    if state and state.get("gate_id") != ctx.gate_id:
        return g2.gate_failure_result(ctx, started_at, started_monotonic, g2.GateFailure("Low-storage resume state belongs to another gate.", stage="resume", retryable=False), {})
    if not state:
        state = {"schema_version": SCHEMA_VERSION, "run_id": ctx.run_id, "gate_id": ctx.gate_id, "scenario": args.scenario, "started_at": started_at, "sanitized": True}
        g2.atomic_write_json(state_path, state)
    deterministic: dict[str, Any] = {}
    live: dict[str, Any] = {}
    failures: list[str] = []
    try:
        scenarios = ["deterministic", "live"] if args.scenario == "both" else [args.scenario]
        if "deterministic" in scenarios and not state.get("deterministic_completed"):
            deterministic = _run_deterministic_failpoints(ctx)
            state["deterministic_completed"] = True
            g2.atomic_write_json(state_path, state)
        elif "deterministic" in scenarios:
            deterministic = {"preserved_on_resume": True}
        if deterministic and deterministic.get("failpoints_failed", 0):
            failures.append("deterministic_failpoint_failure")
        if deterministic and any(deterministic.get(key) for key in ("zero_byte_authoritative_files", "partial_outputs", "active_key_leaks", "false_accepts", "false_successes")):
            failures.append("deterministic_safety_failure")
        if "deterministic" in scenarios and not state.get("deterministic_post_recovery_scan_run_id"):
            progress_path = ctx.gate_dir / "deterministic" / "progress.jsonl"
            lifecycle_path = ctx.gate_dir / "deterministic" / "lifecycle.jsonl"
            post_run, post_state = _post_recovery_scan(ctx, f"low-storage-deterministic-post-{ctx.run_id}", float(args.run_timeout_seconds), progress_path, lifecycle_path)
            if not post_state or str(post_state.get("status") or "").lower() not in TERMINAL_SUCCESS:
                failures.append("deterministic_post_recovery_scan_failed")
            else:
                deterministic["post_recovery_scan_run_id"] = post_run
                state["deterministic_post_recovery_scan_run_id"] = post_run
                g2.atomic_write_json(state_path, state)
        elif state.get("deterministic_post_recovery_scan_run_id"):
            deterministic["post_recovery_scan_run_id"] = state.get("deterministic_post_recovery_scan_run_id")
        if "live" in scenarios:
            live = _run_low_storage_live(ctx, args, state)
        health = bounded_parity_reconciliation(
            ctx,
            timeout_seconds=30.0,
            evidence_path=ctx.gate_dir / "parity-reconciliation.jsonl",
        )
        if health.get("quick_check") != "ok":
            failures.append("final_sqlite_quick_check")
        if health.get("parity_matched") is not True:
            failures.append("final_parity_mismatch")
        result = {
            "run_id": ctx.run_id,
            "gate_id": ctx.gate_id,
            "gate": ctx.gate_id,
            "status": "failed" if failures else "passed",
            "scenario": args.scenario,
            **deterministic,
            **live,
            "fault_injection_disabled": disable_low_storage_activation(ctx) and not os.environ.get("POCKETLAB_GATE_STORAGE_FAILPOINT"),
            "sqlite_quick_check": health.get("quick_check"),
            "parity_matched": health.get("parity_matched"),
            "failed_stage": "evaluation" if failures else "",
            "failure_reason": "Low-storage requirements failed: " + ", ".join(sorted(set(failures))) + "." if failures else "",
            "retryable": False if failures else True,
            "resume_safe": True,
            "sanitized": True,
        }
        g2.write_result(ctx.gate_dir / "result.json", result)
        return 0 if not failures else 2
    except g2.GateFailure as exc:
        disable_low_storage_activation(ctx)
        return g2.gate_failure_result(ctx, started_at, started_monotonic, exc, {"scenario": args.scenario, "fault_injection_disabled": True})


def _android_activation_path(ctx: g2.Context) -> Path:
    return ctx.state_dir / ".pocketlab-dev" / "gate-faults" / "android-lifecycle-diagnostics.json"


def _android_reports_dir(ctx: g2.Context) -> Path:
    return ctx.state_dir / ".pocketlab-dev" / "gate-faults" / "android-lifecycle-reports"


def create_android_activation(ctx: g2.Context, challenge_id: str, *, lifetime_seconds: int) -> Path:
    path = _android_activation_path(ctx)
    g2.atomic_write_json(path, {
        "schema_version": 1,
        "challenge_id": challenge_id,
        "expires_at_epoch": time.time() + max(60, min(7200, lifetime_seconds)),
        "sanitized": True,
    })
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return path


def disable_android_activation(ctx: g2.Context) -> bool:
    try:
        _android_activation_path(ctx).unlink()
    except FileNotFoundError:
        pass
    return not _android_activation_path(ctx).exists()


def android_reports(ctx: g2.Context, challenge_id: str) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    directory = _android_reports_dir(ctx)
    for path in sorted(directory.glob(f"{challenge_id}-*.json")) if directory.exists() else []:
        payload = g2.read_json(path, {})
        if isinstance(payload, dict):
            reports.append(payload)
    return reports


def wait_android_reports(
    ctx: g2.Context,
    challenge_id: str,
    minimum: int,
    timeout: float,
    *,
    label: str = "android",
) -> list[dict[str, Any]]:
    deadline = time.monotonic() + max(1.0, timeout)
    reports = android_reports(ctx, challenge_id)
    last_print = 0.0
    last_count = -1
    while len(reports) < minimum and time.monotonic() < deadline:
        now = time.monotonic()
        if len(reports) != last_count or now - last_print >= 5.0:
            remaining = max(0, int(deadline - now))
            print(
                f"INFO: Android diagnostics label={label} challenge_active={_android_activation_path(ctx).exists()} "
                f"reports={len(reports)}/{minimum} remaining_seconds={remaining}",
                flush=True,
            )
            last_count = len(reports)
            last_print = now
        time.sleep(1)
        reports = android_reports(ctx, challenge_id)
    print(
        f"INFO: Android diagnostics label={label} reports={len(reports)}/{minimum} status="
        f"{'ready' if len(reports) >= minimum else 'timeout'}",
        flush=True,
    )
    return reports


def is_post_terminal_reconciliation(
    report: dict[str, Any],
    *,
    run_id: str,
    baseline_reconciliations: int,
) -> bool:
    return (
        str(report.get("backend_run_id") or "") == run_id
        and int(report.get("backend_reconciliation_count") or 0) > baseline_reconciliations
    )


def wait_post_terminal_frontend_report(
    ctx: g2.Context,
    challenge_id: str,
    run_id: str,
    baseline_reports: list[dict[str, Any]],
    timeout: float,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    baseline_count = len(baseline_reports)
    baseline_reconciliations = max(
        (int(item.get("backend_reconciliation_count") or 0) for item in baseline_reports),
        default=0,
    )
    deadline = time.monotonic() + max(1.0, timeout)
    reports = list(baseline_reports)
    while time.monotonic() < deadline:
        reports = android_reports(ctx, challenge_id)
        for report in reports[baseline_count:]:
            if is_post_terminal_reconciliation(
                report,
                run_id=run_id,
                baseline_reconciliations=baseline_reconciliations,
            ):
                print(
                    f"INFO: Android post-terminal reconciliation observed run_id={run_id} "
                    f"session={str(report.get('frontend_session_id') or '')[:24]}",
                    flush=True,
                )
                return reports, report
        remaining = max(0, int(deadline - time.monotonic()))
        print(
            f"INFO: Waiting for post-terminal frontend reconciliation run_id={run_id} "
            f"reports={len(reports)} remaining_seconds={remaining}",
            flush=True,
        )
        time.sleep(2)
    return reports, None


def operator_checkpoint(
    path: Path,
    stage: str,
    instruction: str,
    *,
    auto_confirm: bool = False,
    timeout_seconds: int = 600,
) -> None:
    record = {"timestamp": g2.utc_now(), "stage": stage, "instruction": instruction[:240], "confirmed": False, "sanitized": True}
    g2.append_jsonl(path, record)
    if not auto_confirm:
        print(instruction, flush=True)
        print(f"Press Enter within {timeout_seconds} seconds after completing this checkpoint.", flush=True)
        readable, _, _ = select.select([sys.stdin], [], [], max(1, int(timeout_seconds)))
        if not readable:
            raise g2.GateFailure("The Android operator checkpoint timed out.", stage=stage, retryable=True)
        sys.stdin.readline()
    record = {**record, "timestamp": g2.utc_now(), "confirmed": True}
    g2.append_jsonl(path, record)


def analyze_frontend_reports(reports: list[dict[str, Any]]) -> dict[str, Any]:
    if not reports:
        return {
            "available": False,
            "simultaneous_sse_and_polling": None,
            "event_source_leak": None,
            "timer_leak": None,
            "listener_leak": None,
            "duplicate_submissions": None,
        }
    simultaneous = any(int(item.get("active_event_source_count") or 0) > 0 and int(item.get("active_poll_timer_count") or 0) > 0 for item in reports)
    event_peak = max(int(item.get("active_event_source_count") or 0) for item in reports)
    timer_peak = max(int(item.get("active_poll_timer_count") or 0) for item in reports)
    listener_peak = max(
        int(item.get("visibility_listener_count") or 0)
        + int(item.get("online_listener_count") or 0)
        + int(item.get("offline_listener_count") or 0)
        for item in reports
    )
    session_ids = sorted({str(item.get("frontend_session_id") or "") for item in reports if item.get("frontend_session_id")})
    return {
        "available": True,
        "frontend_session_ids": session_ids,
        "process_recreated": len(session_ids) > 1,
        "simultaneous_sse_and_polling": simultaneous,
        "event_source_leak": event_peak > 1,
        "timer_leak": timer_peak > 1,
        "listener_leak": listener_peak > 3,
        "duplicate_submissions": max(int(item.get("duplicate_submission_count") or 0) for item in reports),
        "frontend_session_id": str(reports[-1].get("frontend_session_id") or ""),
        "write_actions_blocked_while_stale": any(bool(item.get("write_actions_blocked")) for item in reports),
        "backend_state_reconciled": any(int(item.get("backend_reconciliation_count") or 0) > 0 for item in reports),
        "sse_reconnected": sum(1 for item in reports if item.get("last_sse_opened_at")) >= 1,
        "fallback_polling_resumed": any(item.get("last_poll_started_at") for item in reports),
    }


def _android_instruction(scenario: str, cycle: int = 1) -> tuple[str, str]:
    if scenario == "background-active":
        return "ready_for_background", "Background the Pocket Lab PWA now. Do not close Termux. Wait at least two minutes, then return to the PWA and this terminal."
    if scenario == "process-eviction":
        return "ready_for_process_eviction", "Close or force-stop only the Pocket Lab browser/PWA client, reopen it, and wait for the Safety Center to reconcile. Do not stop Termux."
    if scenario == "network-transition":
        return "ready_for_network_transition", "Temporarily take the client offline or switch its reachable network path, then restore connectivity and reopen Pocket Lab."
    return f"ready_for_resume_cycle_{cycle}", f"Background and resume the Pocket Lab PWA for cycle {cycle}. Do not submit another Safety Check."


def run_android_resume(args: argparse.Namespace) -> int:
    ctx = g2.common_context(args)
    ctx.gate_dir.mkdir(parents=True, exist_ok=True)
    started_at = g2.utc_now()
    started_monotonic = time.monotonic()
    state_path = ctx.gate_dir / "state.json"
    operator_path = ctx.gate_dir / "operator-checkpoints.jsonl"
    frontend_path = ctx.gate_dir / "frontend.jsonl"
    backend_path = ctx.gate_dir / "backend-progress.jsonl"
    network_path = ctx.gate_dir / "network.jsonl"
    events_path = ctx.gate_dir / "events.jsonl"
    state = g2.read_json(state_path, {})
    if state and state.get("gate_id") != ctx.gate_id:
        return g2.gate_failure_result(ctx, started_at, started_monotonic, g2.GateFailure("Android resume state belongs to another gate.", stage="resume", retryable=False), {})
    if not state:
        state = {"schema_version": SCHEMA_VERSION, "run_id": ctx.run_id, "gate_id": ctx.gate_id, "scenario": args.scenario, "scenario_index": 0, "started_at": started_at, "sanitized": True}
        g2.atomic_write_json(state_path, state)
    scenarios = ["background-active", "process-eviction", "network-transition", "repeated-resume"] if args.scenario == "all" else [args.scenario]
    failures: list[str] = []
    duplicate_submissions = 0
    progress_regressions: list[dict[str, Any]] = []
    false_success = False
    run_before = str(state.get("tracked_run_id") or "")
    client = ctx.client()
    baseline_ids = {str(item.get("run_id") or "") for item in g3.runs_after(ctx.db_path, 0)}
    if not run_before:
        lifecycle = g2.lifecycle_snapshot(ctx.db_path)
        if int(lifecycle.get("active_count") or 0) > 0:
            run_before = str((lifecycle.get("active_runs") or [{}])[0].get("run_id") or "")
        else:
            submission, payload = g2.submit_quick_scan(ctx, client, f"android-resume-{ctx.run_id}", float(args.submission_timeout_seconds))
            if not submission.ok:
                return g2.gate_failure_result(ctx, started_at, started_monotonic, g2.GateFailure("Android gate could not start a Quick scan.", stage="scan-submit", retryable=True), {"scenario": args.scenario})
            run_before = str(payload.get("run_id") or payload.get("command_id") or "")
            if not run_before:
                discovered, _ = g3.find_new_run(ctx.db_path, baseline_ids, g2.epoch_ms() - 5000, 30.0)
                run_before = str((discovered or {}).get("run_id") or "")
        if not run_before:
            return g2.gate_failure_result(ctx, started_at, started_monotonic, g2.GateFailure("Android gate could not establish a backend run identity.", stage="scan-discovery", retryable=False), {"scenario": args.scenario})
        state["tracked_run_id"] = run_before
        g2.atomic_write_json(state_path, state)
    challenge = str(state.get("challenge_id") or secrets.token_urlsafe(18))
    state["challenge_id"] = challenge
    create_android_activation(ctx, challenge, lifetime_seconds=int(args.operator_timeout_seconds) * max(2, len(scenarios) + 1))
    initial_progress, _ = g2.progress_sample(ctx, client, base_url=ctx.proxy_base_url, endpoint_type="caddy_proxy")
    g2.append_jsonl(backend_path, initial_progress)
    initial_revision = initial_progress.get("revision") or initial_progress.get("run_revision")
    initial_percent = initial_progress.get("percent")
    try:
        for index, scenario in enumerate(scenarios):
            if index < int(state.get("scenario_index") or 0):
                continue
            cycles = int(args.resume_cycles) if scenario == "repeated-resume" else 1
            for cycle in range(1, cycles + 1):
                minimum_before = len(android_reports(ctx, challenge))
                stage, instruction = _android_instruction(scenario, cycle)
                operator_checkpoint(operator_path, stage, instruction, auto_confirm=bool(args.auto_confirm_operator), timeout_seconds=int(args.operator_timeout_seconds))
                reports = wait_android_reports(
                    ctx,
                    challenge,
                    minimum_before + 1,
                    float(args.frontend_report_timeout_seconds),
                    label=f"{scenario}:cycle-{cycle}",
                )
                if len(reports) < minimum_before + 1:
                    failures.append(f"frontend_diagnostics_missing:{scenario}")
                for report in reports[minimum_before:]:
                    g2.append_jsonl(frontend_path, {**report, "scenario": scenario, "cycle": cycle})
                progress, http = g2.progress_sample(ctx, client, base_url=ctx.proxy_base_url, endpoint_type="caddy_proxy")
                g2.append_jsonl(backend_path, {**progress, "scenario": scenario, "cycle": cycle})
                g2.append_jsonl(network_path, {**http.safe_record(endpoint_type="caddy_proxy"), "scenario": scenario, "cycle": cycle, "online": http.ok})
                if progress.get("run_id") and str(progress.get("run_id")) != run_before:
                    # A newer independent run is only acceptable if the tracked run
                    # is already terminal and no new run was submitted by the gate.
                    tracked = g2.lifecycle_snapshot(ctx.db_path, run_id=run_before).get("run") or {}
                    if str(tracked.get("status") or "").lower() not in TERMINAL:
                        failures.append(f"backend_run_identity_changed:{scenario}")
                state.update({"scenario_index": index, "cycle": cycle, "last_operator_stage": stage, "updated_at": g2.utc_now()})
                g2.atomic_write_json(state_path, state)
            state["scenario_index"] = index + 1
            g2.atomic_write_json(state_path, state)
        pre_terminal_reports = android_reports(ctx, challenge)
        tracked_terminal = g3.wait_terminal(
            ctx,
            run_before,
            timeout=max(1.0, float(args.run_timeout_seconds)),
            progress_path=backend_path,
            lifecycle_path=events_path,
        )
        if not tracked_terminal:
            failures.append("backend_terminal_state_missing")
            tracked_terminal = g2.lifecycle_snapshot(ctx.db_path, run_id=run_before).get("run") or {}
        else:
            print(
                f"INFO: Android tracked backend run reached terminal status={tracked_terminal.get('status')} "
                f"run_id={run_before}",
                flush=True,
            )
        reports, post_terminal_report = wait_post_terminal_frontend_report(
            ctx,
            challenge,
            run_before,
            pre_terminal_reports,
            float(args.frontend_report_timeout_seconds),
        )
        for report in reports[len(pre_terminal_reports):]:
            g2.append_jsonl(frontend_path, {**report, "scenario": "post-terminal", "cycle": 0})
        if post_terminal_report is None:
            failures.append("frontend_post_terminal_reconciliation_missing")

        health = bounded_parity_reconciliation(
            ctx,
            timeout_seconds=30.0,
            evidence_path=ctx.gate_dir / "parity-reconciliation.jsonl",
        )
        if health.get("quick_check") != "ok":
            failures.append("final_sqlite_quick_check")
        if health.get("parity_matched") is not True:
            failures.append("final_parity_mismatch")

        all_progress = _read_jsonl(backend_path)
        progress_regressions = g2.progress_regressions(all_progress)
        after_ids = {str(item.get("run_id") or "") for item in g3.runs_after(ctx.db_path, 0)}
        created = sorted(item for item in after_ids - baseline_ids if item)
        allowed_created = {run_before} if run_before not in baseline_ids else set()
        duplicate_submissions = len([item for item in created if item not in allowed_created])
        tracked = tracked_terminal or g2.lifecycle_snapshot(ctx.db_path, run_id=run_before).get("run") or {}
        terminal_status = str(tracked.get("status") or "").lower()
        false_success = terminal_status in TERMINAL_SUCCESS and not bool(tracked.get("evidence_saved"))
        reports = android_reports(ctx, challenge)
        frontend = analyze_frontend_reports(reports)
        if frontend.get("simultaneous_sse_and_polling") is True:
            failures.append("simultaneous_sse_and_polling")
        if frontend.get("event_source_leak") is True:
            failures.append("event_source_leak")
        if frontend.get("timer_leak") is True:
            failures.append("timer_leak")
        if frontend.get("listener_leak") is True:
            failures.append("listener_leak")
        if int(frontend.get("duplicate_submissions") or 0) > 0 or duplicate_submissions > 0:
            failures.append("duplicate_submission")
        if progress_regressions:
            failures.append("progress_regression")
        if false_success:
            failures.append("false_terminal_success")
        if not frontend.get("backend_state_reconciled"):
            failures.append("backend_state_not_reconciled")
        if args.scenario in {"process-eviction", "all"} and not frontend.get("process_recreated"):
            failures.append("client_process_not_recreated")
        if args.scenario in {"network-transition", "all"} and not frontend.get("write_actions_blocked_while_stale"):
            failures.append("stale_write_block_not_observed")
        result = {
            "run_id": ctx.run_id,
            "gate_id": ctx.gate_id,
            "gate": ctx.gate_id,
            "status": "failed" if failures else "passed",
            "scenario": args.scenario,
            "client_type": "pwa_or_browser",
            "frontend_session_id": frontend.get("frontend_session_id", ""),
            "frontend_session_ids": frontend.get("frontend_session_ids", []),
            "process_recreated": frontend.get("process_recreated"),
            "run_id_before": run_before,
            "run_id_after": str(tracked.get("run_id") or run_before),
            "cached_revision_before": initial_revision,
            "backend_revision_after": tracked.get("revision") or (all_progress[-1].get("revision") if all_progress else None),
            "duplicate_submissions": duplicate_submissions + int(frontend.get("duplicate_submissions") or 0),
            "progress_regressions": len(progress_regressions),
            "false_success_detected": false_success,
            "write_actions_blocked_while_stale": frontend.get("write_actions_blocked_while_stale"),
            "sse_reconnected": frontend.get("sse_reconnected"),
            "fallback_polling_resumed": frontend.get("fallback_polling_resumed"),
            "simultaneous_sse_and_polling": frontend.get("simultaneous_sse_and_polling"),
            "event_source_leak": frontend.get("event_source_leak"),
            "timer_leak": frontend.get("timer_leak"),
            "listener_leak": frontend.get("listener_leak"),
            "backend_state_reconciled": frontend.get("backend_state_reconciled"),
            "terminal_state_truthful": not false_success,
            "post_terminal_frontend_report_observed": post_terminal_report is not None,
            "sqlite_quick_check": health.get("quick_check"),
            "parity_matched": health.get("parity_matched"),
            "parity_reconciliation_attempts": health.get("reconciliation_attempts"),
            "operator_checkpoints_completed": sum(1 for item in _read_jsonl(operator_path) if item.get("confirmed")),
            "initial_percent": initial_percent,
            "failed_stage": "evaluation" if failures else "",
            "failure_reason": "Android lifecycle requirements failed: " + ", ".join(sorted(set(failures))) + "." if failures else "",
            "retryable": False if failures else True,
            "resume_safe": True,
            "sanitized": True,
        }
        g2.write_result(ctx.gate_dir / "result.json", result)
        return 0 if not failures else 2
    except (EOFError, KeyboardInterrupt):
        state["operator_interrupted"] = True
        g2.atomic_write_json(state_path, state)
        raise
    finally:
        disable_android_activation(ctx)
        # Gate-owned reports are copied into evidence before cleanup.
        for path in _android_reports_dir(ctx).glob(f"{challenge}-*.json") if _android_reports_dir(ctx).exists() else []:
            try:
                path.unlink()
            except OSError:
                pass


def add_common(parser: argparse.ArgumentParser) -> None:
    g2.add_common(parser)
    parser.add_argument("--run-timeout-seconds", type=float, default=5400)
    parser.add_argument("--submission-timeout-seconds", type=float, default=10)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    wal = sub.add_parser("wal-pressure")
    add_common(wal)
    wal.add_argument("--scenario", choices=("isolated", "live", "both"), required=True)
    wal.add_argument("--duration-seconds", type=int, required=True)
    wal.add_argument("--writer-interval-ms", type=int, required=True)
    wal.add_argument("--reader-interval-ms", type=int, required=True)
    wal.add_argument("--checkpoint-interval-seconds", type=float, required=True)
    wal.add_argument("--health-interval-seconds", type=float, required=True)
    wal.add_argument("--wal-growth-budget-bytes", type=int, required=True)
    wal.add_argument("--reader-p95-budget-seconds", type=float, required=True)
    wal.add_argument("--writer-p95-budget-seconds", type=float, required=True)
    wal.add_argument("--contention-retry-budget", type=int, required=True)
    wal.add_argument("--final-truncate-checkpoint", action="store_true")

    low = sub.add_parser("low-storage")
    add_common(low)
    low.add_argument("--scenario", choices=("deterministic", "live", "both"), required=True)
    low.add_argument("--min-free-space-bytes", type=int, required=True)
    low.add_argument("--min-free-space-percent", type=float, required=True)
    low.add_argument("--emergency-reserve-bytes", type=int, required=True)
    low.add_argument("--max-allocation-bytes", type=int, required=True)
    low.add_argument("--absolute-allocation-cap-bytes", type=int, required=True)

    android = sub.add_parser("android-resume")
    add_common(android)
    android.add_argument("--scenario", choices=("background-active", "process-eviction", "network-transition", "repeated-resume", "all"), required=True)
    android.add_argument("--operator-timeout-seconds", type=int, required=True)
    android.add_argument("--frontend-report-timeout-seconds", type=int, required=True)
    android.add_argument("--resume-cycles", type=int, required=True)
    android.add_argument("--auto-confirm-operator", action="store_true")
    return parser


def validate_args(args: argparse.Namespace) -> None:
    if args.report_limit_bytes < 1024 * 1024:
        raise ValueError("report limit must be at least 1 MiB")
    if args.run_timeout_seconds < 1 or args.submission_timeout_seconds <= 0:
        raise ValueError("run and submission timeouts must be positive")
    if args.command == "wal-pressure":
        if args.duration_seconds < 1:
            raise ValueError("WAL duration must be positive")
        if args.writer_interval_ms < 10 or args.reader_interval_ms < 10:
            raise ValueError("WAL reader/writer intervals must be at least 10 ms")
        if args.checkpoint_interval_seconds <= 0 or args.health_interval_seconds <= 0:
            raise ValueError("WAL observation intervals must be positive")
        if args.wal_growth_budget_bytes < 0 or args.contention_retry_budget < 0:
            raise ValueError("WAL and contention budgets cannot be negative")
    elif args.command == "low-storage":
        if args.min_free_space_bytes < 16 * 1024 * 1024:
            raise ValueError("minimum free-space floor must be at least 16 MiB")
        if not 0.5 <= args.min_free_space_percent <= 50.0:
            raise ValueError("minimum free-space percent must be between 0.5 and 50")
        if args.emergency_reserve_bytes < 1024 * 1024:
            raise ValueError("emergency reserve must be at least 1 MiB")
        if args.max_allocation_bytes < 0 or args.absolute_allocation_cap_bytes < 1024 * 1024:
            raise ValueError("allocation values are invalid")
    elif args.command == "android-resume":
        if args.operator_timeout_seconds < 30 or args.frontend_report_timeout_seconds < 1:
            raise ValueError("Android operator/report timeouts are too short")
        if not 1 <= args.resume_cycles <= 20:
            raise ValueError("Android resume cycles must be between 1 and 20")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        validate_args(args)
        if args.command == "wal-pressure":
            return run_wal_pressure(args)
        if args.command == "low-storage":
            return run_low_storage(args)
        if args.command == "android-resume":
            return run_android_resume(args)
    except KeyboardInterrupt:
        return 75
    except (ValueError, RuntimeError) as exc:
        print(f"ERROR: {g2.clamp_text(exc)}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
