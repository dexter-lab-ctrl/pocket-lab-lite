#!/usr/bin/env python3
"""Phase 5 Group 3 controlled disruption and recovery gates.

The module reuses Group 2 HTTP, SQLite, PM2, process, result, and evidence
helpers. Destructive actions are precise, checkpointed in gate-local state, and
never repeated automatically after their completion is recorded.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parent))
import long_gate_group2 as g2  # noqa: E402

SCHEMA_VERSION = 1
TERMINAL = {"succeeded", "degraded", "failed", "cancelled", "canceled", "completed"}
TERMINAL_SUCCESS = {"succeeded", "degraded", "completed"}
ALLOWED_PM2 = {"pocket-nats", "pocket-worker", "pocket-api"}
SUBMISSION_SCENARIO = "submission-response-delay"
MAX_DELAY_MS = 30_000


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            value = json.loads(line)
            if isinstance(value, dict):
                rows.append(value)
    except (OSError, json.JSONDecodeError):
        return rows
    return rows


def lifecycle_order_issues(run: dict[str, Any]) -> list[str]:
    ordered = [
        ("requested_at", "requested_at_epoch_ms"),
        ("command_published_at", "command_published_at_epoch_ms"),
        ("accepted_at", "accepted_at_epoch_ms"),
        ("command_received_at", "command_received_at_epoch_ms"),
        ("execution_started_at", "execution_started_at_epoch_ms"),
        ("last_progress_at", "last_progress_at_epoch_ms"),
        ("completed_at", "completed_at_epoch_ms"),
        ("updated_at", "updated_at_epoch_ms"),
    ]
    values: list[tuple[str, int]] = []
    for name, epoch_name in ordered:
        raw = run.get(epoch_name)
        try:
            value = int(raw or 0)
        except (TypeError, ValueError):
            value = 0
        if value > 0:
            values.append((name, value))
    issues: list[str] = []
    for (left_name, left), (right_name, right) in zip(values, values[1:]):
        # updated_at may equal or follow completion; all other known timestamps
        # must not move backwards.
        if right < left:
            issues.append(f"timestamp_regression:{left_name}:{right_name}")
    status = str(run.get("status") or "").lower()
    if status in TERMINAL and run.get("active_key") not in (None, ""):
        issues.append("terminal_active_key_not_cleared")
    if status not in TERMINAL and run.get("completed_at"):
        issues.append("nonterminal_has_completed_at")
    return issues


def duplicate_terminal_success(runs: Iterable[dict[str, Any]], command_id: str) -> bool:
    successes = {
        str(row.get("run_id") or "")
        for row in runs
        if str(row.get("command_id") or "") == str(command_id or "")
        and str(row.get("status") or "").lower() in TERMINAL_SUCCESS
    }
    successes.discard("")
    return len(successes) > 1


def recovery_outcome(run: dict[str, Any] | None, *, restarted_after_claim: bool = False) -> str:
    if not run:
        return "unresolved"
    status = str(run.get("status") or "").lower()
    if status in TERMINAL_SUCCESS:
        return "recovered_and_succeeded"
    if status == "failed":
        code = str(run.get("failure_code") or "").lower()
        if "stale" in code or "recover" in code:
            return "stale_recovered"
        return "recovered_and_failed_truthfully" if restarted_after_claim else "failed_interrupted"
    if status in {"cancelled", "canceled"}:
        return "failed_interrupted"
    return "unresolved"


def pm2_process(snapshot: dict[str, Any], name: str) -> dict[str, Any] | None:
    for item in snapshot.get("processes", []):
        if item.get("name") == name:
            return item
    return None


def restart_delta(before: dict[str, Any] | None, after: dict[str, Any] | None) -> int | None:
    if not before or not after:
        return None
    return int(after.get("restart_count") or 0) - int(before.get("restart_count") or 0)


def process_evidence(snapshot: dict[str, Any], names: Iterable[str]) -> dict[str, Any]:
    return {
        name: pm2_process(snapshot, name)
        for name in names
    }


def run_pm2_action(name: str, action: str, *, timeout: float = 45.0) -> dict[str, Any]:
    if name not in ALLOWED_PM2:
        return {"ok": False, "error_type": "unapproved_process_name", "process": name, "action": action}
    if action not in {"restart", "stop", "start"}:
        return {"ok": False, "error_type": "unapproved_action", "process": name, "action": action}
    command = ["pm2", action, name]
    if action in {"restart", "start"}:
        command.append("--update-env")
    result = g2.run_command(command, timeout=timeout)
    return {
        "timestamp": g2.utc_now(),
        "process": name,
        "action": action,
        "ok": bool(result.get("ok")),
        "error_type": str(result.get("error_type") or ""),
        "exit_code": result.get("exit_code"),
        "sanitized": True,
    }


def wait_for_pm2(name: str, *, online: bool, timeout: float, old_pid: int | None = None, require_pid_change: bool = False) -> dict[str, Any] | None:
    deadline = time.monotonic() + max(1.0, timeout)
    while time.monotonic() <= deadline:
        snapshot = g2.pm2_snapshot()
        item = pm2_process(snapshot, name)
        is_online = bool(item and item.get("status") == "online" and int(item.get("pid") or 0) > 0)
        if is_online == online:
            if require_pid_change and old_pid and int((item or {}).get("pid") or 0) == int(old_pid):
                time.sleep(0.5)
                continue
            return item
        time.sleep(0.5)
    return None


def safe_nats_view(payload: dict[str, Any] | None) -> dict[str, Any]:
    payload = payload or {}
    health = payload.get("durable_consumer_health") if isinstance(payload.get("durable_consumer_health"), dict) else {}
    consumers: dict[str, Any] = {}
    for name, item in health.items():
        if not isinstance(item, dict):
            continue
        consumers[str(name)[:160]] = {
            key: item.get(key)
            for key in (
                "healthy", "task_alive", "subscription_present", "callback_inflight",
                "generation", "recoveries", "last_fetch_at", "last_message_at",
                "last_completed_callback_at", "last_error_type",
            )
        }
    return {
        "timestamp": g2.utc_now(),
        "mode": payload.get("mode"),
        "connected": payload.get("connected"),
        "jetstream_enabled": payload.get("jetstream_enabled"),
        "published": payload.get("published"),
        "received": payload.get("received"),
        "reconnect_pending": payload.get("reconnect_pending"),
        "watchdog_running": payload.get("watchdog_running"),
        "durable_consumer_health": consumers,
        "sanitized": True,
    }


def consumer_summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    view = safe_nats_view(payload)
    health = view.get("durable_consumer_health", {})
    unhealthy = sorted(name for name, item in health.items() if item.get("healthy") is False)
    duplicate = 0
    names = [name.casefold() for name in health]
    duplicate += len(names) - len(set(names))
    worker = next((item for name, item in health.items() if "worker" in name.casefold()), None)
    return {
        "connected": view.get("connected") is True,
        "jetstream_enabled": view.get("jetstream_enabled") is True,
        "healthy": view.get("connected") is True and not unhealthy and (worker is None or worker.get("healthy") is True),
        "unhealthy": unhealthy,
        "duplicate_consumers": duplicate,
        "generation": (worker or {}).get("generation"),
        "recoveries": (worker or {}).get("recoveries"),
        "view": view,
    }


def wait_for_nats(ctx: g2.Context, *, timeout: float, events_path: Path) -> dict[str, Any] | None:
    client = ctx.client(timeout=min(ctx.http_timeout, 5.0))
    deadline = time.monotonic() + max(1.0, timeout)
    last: dict[str, Any] | None = None
    while time.monotonic() <= deadline:
        result = client.request("GET", ctx.proxy_base_url, "/api/nats/status", retry_read=True)
        summary = consumer_summary(result.body)
        last = summary
        g2.append_jsonl(events_path, {"timestamp": g2.utc_now(), "event": "nats.recovery_sample", **summary["view"]})
        g2.ensure_report_budget(ctx.run_dir, ctx.report_limit_bytes)
        if result.ok and summary["healthy"]:
            return summary
        time.sleep(1.0)
    return last


def _columns(connection: sqlite3.Connection) -> set[str]:
    return {str(row[1]) for row in connection.execute("PRAGMA table_info(security_scan_runs)")}


def runs_after(db_path: Path, epoch_ms: int) -> list[dict[str, Any]]:
    connection = g2.sqlite_connect_readonly(db_path)
    if connection is None:
        return []
    try:
        columns = _columns(connection)
        wanted = [
            "run_id", "profile", "status", "active_key", "summary", "requested_at",
            "accepted_at", "started_at", "completed_at", "updated_at",
            "requested_at_epoch_ms", "accepted_at_epoch_ms", "started_at_epoch_ms",
            "completed_at_epoch_ms", "updated_at_epoch_ms", "command_id", "correlation_id",
            "command_published_at", "command_published_at_epoch_ms", "command_received_at",
            "command_received_at_epoch_ms", "execution_started_at", "execution_started_at_epoch_ms",
            "last_progress_at", "last_progress_at_epoch_ms", "delivery_attempt", "revision",
            "evidence_saved", "failure_code", "failure_message",
        ]
        selected = [item for item in wanted if item in columns]
        rows = connection.execute(
            f"SELECT {', '.join(selected)} FROM security_scan_runs WHERE requested_at_epoch_ms >= ? ORDER BY requested_at_epoch_ms ASC",
            (int(epoch_ms),),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def find_new_run(db_path: Path, baseline_ids: set[str], started_ms: int, timeout: float) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    deadline = time.monotonic() + max(1.0, timeout)
    latest: list[dict[str, Any]] = []
    while time.monotonic() <= deadline:
        latest = runs_after(db_path, started_ms - 1000)
        candidates = [row for row in latest if str(row.get("run_id") or "") not in baseline_ids]
        if len(candidates) == 1:
            return candidates[0], candidates
        if len(candidates) > 1:
            return None, candidates
        time.sleep(0.25)
    return None, latest


def wait_for_run(ctx: g2.Context, run_id: str, *, timeout: float, progress_path: Path, lifecycle_path: Path, require_execution: bool = False) -> dict[str, Any] | None:
    client = ctx.client(timeout=min(ctx.http_timeout, 5.0))
    deadline = time.monotonic() + max(1.0, timeout)
    while time.monotonic() <= deadline:
        progress, result = g2.progress_sample(ctx, client)
        g2.append_jsonl(progress_path, progress)
        snapshot = g2.lifecycle_snapshot(ctx.db_path, run_id=run_id)
        run = snapshot.get("run") or {}
        if run:
            g2.append_jsonl(lifecycle_path, {"timestamp": g2.utc_now(), "run": run, "active_count": snapshot.get("active_count"), "sanitized": True})
        g2.ensure_report_budget(ctx.run_dir, ctx.report_limit_bytes)
        if require_execution and (run.get("command_received_at") or run.get("execution_started_at")):
            return run
        status = str(run.get("status") or "").lower()
        if status in TERMINAL:
            return run
        if not result.ok and not run:
            time.sleep(1.0)
        else:
            time.sleep(0.75)
    return None


def wait_terminal(ctx: g2.Context, run_id: str, *, timeout: float, progress_path: Path, lifecycle_path: Path) -> dict[str, Any] | None:
    deadline = time.monotonic() + max(1.0, timeout)
    client = ctx.client(timeout=min(ctx.http_timeout, 5.0))
    while time.monotonic() <= deadline:
        progress, _ = g2.progress_sample(ctx, client)
        g2.append_jsonl(progress_path, progress)
        snapshot = g2.lifecycle_snapshot(ctx.db_path, run_id=run_id)
        run = snapshot.get("run") or {}
        if run:
            g2.append_jsonl(lifecycle_path, {"timestamp": g2.utc_now(), "run": run, "active_count": snapshot.get("active_count"), "sanitized": True})
            if str(run.get("status") or "").lower() in TERMINAL:
                g2.ensure_report_budget(ctx.run_dir, ctx.report_limit_bytes)
                return run
        g2.ensure_report_budget(ctx.run_dir, ctx.report_limit_bytes)
        time.sleep(1.0)
    return None


def submit_quick(ctx: g2.Context, logical_id: str, *, timeout: float, base_url: str | None = None, extra_headers: dict[str, str] | None = None) -> tuple[g2.HttpResult, dict[str, Any]]:
    client = ctx.client(timeout=timeout)
    result = client.request(
        "POST",
        base_url or ctx.proxy_base_url,
        "/api/lite/security/check",
        body={"profile": "quick", "reason": f"phase5 {ctx.gate_id} {logical_id}"},
        retry_read=False,
        extra_headers=extra_headers,
    )
    return result, result.body or {}


def final_independent_scan(ctx: g2.Context, label: str, *, timeout: float, progress_path: Path, lifecycle_path: Path) -> tuple[str, dict[str, Any] | None, float | None]:
    snapshot = g2.lifecycle_snapshot(ctx.db_path)
    if snapshot.get("active_count") not in (0, None):
        return "", None, None
    result, payload = submit_quick(ctx, label, timeout=min(10.0, ctx.http_timeout + 5.0))
    run_id = str(payload.get("run_id") or "")
    if not result.ok or not run_id:
        return "", None, result.time_total
    terminal = wait_terminal(ctx, run_id, timeout=timeout, progress_path=progress_path, lifecycle_path=lifecycle_path)
    return run_id, terminal, result.time_total


def final_health(ctx: g2.Context) -> dict[str, Any]:
    return g2.run_sqlite_tools(ctx.repo_root, ctx.state_dir, ctx.db_path)


def result_failure(ctx: g2.Context, started_at: str, started_monotonic: float, reason: str, stage: str, fields: dict[str, Any]) -> int:
    payload = {
        "run_id": ctx.run_id,
        "gate_id": ctx.gate_id,
        "gate": ctx.gate_id,
        "status": "failed",
        "started_at": started_at,
        "duration_seconds": round(max(0.0, time.monotonic() - started_monotonic), 3),
        "failed_stage": stage,
        "failure_reason": g2.clamp_text(reason),
        "retryable": False,
        "resume_safe": True,
        "sanitized": True,
        **fields,
    }
    g2.write_result(ctx.gate_dir / "result.json", payload)
    return 2


def _activation_path(ctx: g2.Context) -> Path:
    return ctx.state_dir / ".pocketlab-dev" / "gate-faults" / "submission-response-delay.json"


def create_activation(ctx: g2.Context, token: str, delay_ms: int, *, lifetime_seconds: int) -> Path:
    path = _activation_path(ctx)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "scenario": SUBMISSION_SCENARIO,
        "token_sha256": hashlib.sha256(token.encode("utf-8")).hexdigest(),
        "delay_ms": int(delay_ms),
        "expires_at_epoch": time.time() + max(10, lifetime_seconds),
        "run_id": ctx.run_id,
        "created_at": g2.utc_now(),
        "sanitized": True,
    }
    g2.atomic_write_json(path, payload)
    os.chmod(path, 0o600)
    return path


def disable_activation(ctx: g2.Context) -> bool:
    path = _activation_path(ctx)
    try:
        path.unlink(missing_ok=True)
        return not path.exists()
    except OSError:
        return False


def attribute_submission_runs(
    created: list[dict[str, Any]], tracked_run_id: str, follow_run_id: str
) -> dict[str, Any]:
    primary = [row for row in created if str(row.get("run_id") or "") == tracked_run_id]
    follow_up = [row for row in created if str(row.get("run_id") or "") == follow_run_id]
    expected_ids = {value for value in (tracked_run_id, follow_run_id) if value}
    unexpected = [row for row in created if str(row.get("run_id") or "") not in expected_ids]
    return {
        "primary_run_count": len(primary),
        "follow_up_run_count": len(follow_up),
        "unexpected_run_count": len(unexpected),
    }


def run_submission_recovery(args: argparse.Namespace) -> int:
    ctx = g2.common_context(args)
    ctx.gate_dir.mkdir(parents=True, exist_ok=True)
    started_at, started_mono = g2.utc_now(), time.monotonic()
    state_path = ctx.gate_dir / "state.json"
    submissions = ctx.gate_dir / "submissions.jsonl"
    lifecycle = ctx.gate_dir / "lifecycle.jsonl"
    progress = ctx.gate_dir / "progress.jsonl"
    commands = ctx.gate_dir / "commands.jsonl"
    resources = ctx.gate_dir / "resources.jsonl"
    events = ctx.gate_dir / "events.jsonl"
    state = g2.read_json(state_path, {})
    if not state:
        baseline = g2.lifecycle_snapshot(ctx.db_path)
        if baseline.get("active_count") not in (0, None):
            return result_failure(ctx, started_at, started_mono, "An unrelated Security run is already active.", "preflight", {})
        state = {
            "schema_version": 1,
            "run_id": ctx.run_id,
            "gate_id": ctx.gate_id,
            "logical_submission_id": f"submission-{secrets.token_hex(8)}",
            "baseline_ids": [str(row.get("run_id") or "") for row in baseline.get("runs", [])],
            "submission_started_ms": int(time.time() * 1000),
            "client_timeout_observed": False,
            "tracked_run_id": "",
            "activation_created": False,
            "activation_disabled": False,
            "retry_attempted": False,
            "post_recovery_scan_run_id": "",
        }
        g2.atomic_write_json(state_path, state)
    elif state.get("gate_id") != ctx.gate_id:
        return result_failure(ctx, started_at, started_mono, "Resume state belongs to another gate.", "resume", {})

    token = secrets.token_urlsafe(32)
    try:
        if not state.get("tracked_run_id"):
            if state.get("activation_created"):
                # Resume never repeats the write. Rediscover the durable identity
                # from the saved pre-submission baseline and authoritative SQLite.
                disable_activation(ctx)
                state["activation_disabled"] = True
                run, candidates = find_new_run(
                    ctx.db_path, set(state.get("baseline_ids", [])),
                    int(state["submission_started_ms"]), float(args.discovery_timeout_seconds),
                )
                if not run or len(candidates) != 1:
                    g2.atomic_write_json(state_path, state)
                    return result_failure(
                        ctx, started_at, started_mono,
                        "Submission recovery resume could not identify exactly one durable run; refusing to resubmit.",
                        "resume_identity", {**state, "run_count_created": len(candidates)},
                    )
            else:
                create_activation(ctx, token, int(args.response_delay_ms), lifetime_seconds=int(args.run_timeout_seconds) + 60)
                state["activation_created"] = True
                g2.atomic_write_json(state_path, state)
                result, _payload = submit_quick(
                    ctx, str(state["logical_submission_id"]),
                    timeout=float(args.client_timeout_seconds),
                    base_url=ctx.direct_base_url,
                    extra_headers={
                        "X-PocketLab-Gate-Scenario": SUBMISSION_SCENARIO,
                        "X-PocketLab-Gate-Token": token,
                    },
                )
                timed_out = result.error_type == "timeout"
                state["client_timeout_observed"] = timed_out
                g2.append_jsonl(submissions, {
                    "timestamp": g2.utc_now(), "attempt": 1,
                    "client_timeout_observed": timed_out,
                    "http_status": result.status_code, "error_type": result.error_type,
                    "response_delay_ms": int(args.response_delay_ms), "sanitized": True,
                })
                if not timed_out:
                    disable_activation(ctx)
                    state["activation_disabled"] = True
                    g2.atomic_write_json(state_path, state)
                    return result_failure(ctx, started_at, started_mono, "The gate-authorized client timeout did not occur.", "fault_injection", state)
                run, candidates = find_new_run(
                    ctx.db_path, set(state.get("baseline_ids", [])),
                    int(state["submission_started_ms"]), float(args.discovery_timeout_seconds),
                )
                if not run or len(candidates) != 1:
                    disable_activation(ctx)
                    state["activation_disabled"] = True
                    g2.atomic_write_json(state_path, state)
                    return result_failure(ctx, started_at, started_mono, "Durable submission identity was missing or ambiguous after the client timeout.", "discover_durable_run", {**state, "run_count_created": len(candidates)})
            state["tracked_run_id"] = str(run.get("run_id") or "")
            state["command_id"] = str(run.get("command_id") or "")
            state["run_count_created"] = len(candidates)
            g2.atomic_write_json(state_path, state)
            g2.append_jsonl(commands, {
                "timestamp": g2.utc_now(), "run_id": state["tracked_run_id"],
                "command_id": state.get("command_id"),
                "delivery_attempt": run.get("delivery_attempt"), "sanitized": True,
            })

        disable_activation(ctx)
        state["activation_disabled"] = True
        g2.atomic_write_json(state_path, state)
        tracked = str(state.get("tracked_run_id") or "")
        current = g2.lifecycle_snapshot(ctx.db_path, run_id=tracked).get("run") or {}
        if str(current.get("status") or "").lower() not in TERMINAL and not state.get("retry_attempted"):
            retry_result, retry_payload = submit_quick(ctx, str(state["logical_submission_id"]), timeout=min(10.0, ctx.http_timeout + 5.0))
            state["retry_attempted"] = True
            state["retry_result"] = {
                "http_status": retry_result.status_code,
                "ok": retry_result.ok,
                "deduplicated": bool(retry_payload.get("deduplicated")),
                "run_id_matches": str(retry_payload.get("run_id") or "") == tracked,
            }
            g2.append_jsonl(submissions, {"timestamp": g2.utc_now(), "attempt": 2, **state["retry_result"], "sanitized": True})
            g2.atomic_write_json(state_path, state)
        terminal = wait_terminal(ctx, tracked, timeout=float(args.run_timeout_seconds), progress_path=progress, lifecycle_path=lifecycle)
        if not terminal:
            return result_failure(ctx, started_at, started_mono, "The durable run did not reach a terminal state before the recovery deadline.", "wait_terminal", state)
        issues = lifecycle_order_issues(terminal)
        primary_runs = runs_after(ctx.db_path, int(state["submission_started_ms"]) - 1000)
        primary_created = [row for row in primary_runs if str(row.get("run_id") or "") not in set(state.get("baseline_ids", []))]
        same_command = [row for row in primary_created if str(row.get("command_id") or "") == str(terminal.get("command_id") or "")]
        duplicate_success = duplicate_terminal_success(primary_created, str(terminal.get("command_id") or ""))
        residue = g2.wait_for_scanner_cleanup(20)
        follow_id, follow, follow_latency = final_independent_scan(ctx, "post-submission-recovery", timeout=float(args.run_timeout_seconds), progress_path=progress, lifecycle_path=lifecycle)
        state["post_recovery_scan_run_id"] = follow_id
        g2.atomic_write_json(state_path, state)
        g2.append_jsonl(resources, g2.resource_snapshot(db_path=ctx.db_path, state_dir=ctx.state_dir, run_dir=ctx.run_dir))
        health = final_health(ctx)
        progress_issues = g2.progress_regressions(read_jsonl(progress))
        all_runs = runs_after(ctx.db_path, int(state["submission_started_ms"]) - 1000)
        created = [row for row in all_runs if str(row.get("run_id") or "") not in set(state.get("baseline_ids", []))]
        attribution = attribute_submission_runs(created, tracked, follow_id)
        failures: list[str] = []
        if attribution["primary_run_count"] != 1:
            failures.append("primary_run_count")
        if attribution["follow_up_run_count"] != 1:
            failures.append("follow_up_run_count")
        if attribution["unexpected_run_count"] != 0:
            failures.append("unexpected_run_count")
        if len(same_command) != 1:
            failures.append("logical_command_count")
        if duplicate_success:
            failures.append("duplicate_terminal_success")
        if issues:
            failures.extend(issues)
        if progress_issues:
            failures.append("progress_regression")
        if terminal.get("active_key") not in (None, ""):
            failures.append("active_key_not_cleared")
        if residue:
            failures.append("scanner_residue")
        if not follow or str(follow.get("status") or "").lower() not in TERMINAL_SUCCESS:
            failures.append("post_recovery_scan_failed")
        if follow_latency is None or follow_latency >= 5.0:
            failures.append("normal_submission_latency_not_restored")
        if health.get("quick_check") != "ok":
            failures.append("sqlite_quick_check")
        if health.get("matched") is not True:
            failures.append("parity_mismatch")
        if _activation_path(ctx).exists():
            failures.append("fault_injection_still_enabled")
        result = {
            "run_id": ctx.run_id,
            "gate_id": ctx.gate_id,
            "gate": ctx.gate_id,
            "status": "passed" if not failures else "failed",
            "started_at": started_at,
            "duration_seconds": round(time.monotonic() - started_mono, 3),
            "logical_submission_id": state["logical_submission_id"],
            "client_timeout_observed": bool(state.get("client_timeout_observed")),
            "response_delay_ms": int(args.response_delay_ms),
            "durable_run_discovered": bool(tracked),
            "run_id_tracked": tracked,
            "command_id": terminal.get("command_id"),
            "retry_attempted": bool(state.get("retry_attempted")),
            "retry_result": state.get("retry_result"),
            "deduplicated": bool((state.get("retry_result") or {}).get("deduplicated")),
            "run_count_created": len(created),
            "primary_run_count": attribution["primary_run_count"],
            "follow_up_run_count": attribution["follow_up_run_count"],
            "unexpected_run_count": attribution["unexpected_run_count"],
            "logical_execution_count": len(same_command),
            "delivery_attempts": terminal.get("delivery_attempt"),
            "terminal_status": terminal.get("status"),
            "active_key_cleared": terminal.get("active_key") in (None, ""),
            "post_recovery_scan_run_id": follow_id,
            "normal_submission_latency_seconds": follow_latency,
            "fault_injection_disabled": not _activation_path(ctx).exists(),
            "duplicate_terminal_success": duplicate_success,
            "lifecycle_issues": issues,
            "progress_regressions": progress_issues,
            "scanner_residue": residue,
            "sqlite_quick_check": health.get("quick_check"),
            "parity_matched": health.get("matched"),
            "failed_stage": "evaluation" if failures else "",
            "failure_reason": "" if not failures else "Submission recovery requirements failed: " + ", ".join(sorted(set(failures))),
            "retryable": False,
            "resume_safe": True,
            "sanitized": True,
            "evidence_refs": ["gates/submission-recovery/submissions.jsonl", "gates/submission-recovery/lifecycle.jsonl", "gates/submission-recovery/progress.jsonl", "gates/submission-recovery/commands.jsonl", "gates/submission-recovery/resources.jsonl", "gates/submission-recovery/events.jsonl"],
        }
        g2.write_result(ctx.gate_dir / "result.json", result)
        return 0 if not failures else 2
    finally:
        disabled = disable_activation(ctx)
        state = g2.read_json(state_path, state)
        state["activation_disabled"] = disabled
        state["updated_at"] = g2.utc_now()
        g2.atomic_write_json(state_path, state)
        g2.append_jsonl(events, {"timestamp": g2.utc_now(), "event": "fault_injection.cleanup", "disabled": disabled, "sanitized": True})


def _preflight_disruption(ctx: g2.Context, *, allow_run_id: str = "", allow_worker_offline: bool = False) -> tuple[dict[str, Any], dict[str, Any]]:
    lifecycle = g2.lifecycle_snapshot(ctx.db_path)
    active_runs = lifecycle.get("active_runs") or []
    active_ids = {str(item.get("run_id") or "") for item in active_runs}
    active_ids.discard("")
    if active_ids and (not allow_run_id or active_ids != {allow_run_id}):
        raise g2.GateFailure("An unrelated Security run is already active.", stage="preflight", retryable=False)
    pm2 = g2.pm2_snapshot()
    for name in ("pocket-api", "pocket-worker", "pocket-nats"):
        item = pm2_process(pm2, name)
        if name == "pocket-worker" and allow_worker_offline:
            if not item:
                raise g2.GateFailure("Required PM2 process identity is missing: pocket-worker.", stage="preflight", retryable=False)
            continue
        if not item or item.get("status") != "online" or not item.get("pid"):
            raise g2.GateFailure(f"Required PM2 process is not healthy: {name}.", stage="preflight", retryable=False)
    health = final_health(ctx)
    if health.get("quick_check") != "ok" or health.get("matched") is not True:
        raise g2.GateFailure("SQLite health or JSON/SQLite parity failed before disruption.", stage="preflight", retryable=False)
    return lifecycle, pm2


def _scenario_list(value: str, allowed: tuple[str, ...]) -> list[str]:
    if value == "both":
        return list(allowed)
    if value not in allowed:
        raise ValueError(f"scenario must be one of: both, {', '.join(allowed)}")
    return [value]


def wait_for_reconciled_health(
    ctx: g2.Context, *, timeout: float, events_path: Path
) -> dict[str, Any]:
    deadline = time.monotonic() + max(1.0, timeout)
    client = ctx.client(timeout=min(ctx.http_timeout, 5.0))
    while time.monotonic() <= deadline:
        for path in ("/api/lite/security/progress", "/api/lite/security/summary"):
            result = client.request("GET", ctx.proxy_base_url, path, retry_read=True)
            g2.append_jsonl(events_path, {
                "timestamp": g2.utc_now(), "event": "resume.projection_refresh",
                "path": path, "http_status": result.status_code,
                "ok": result.ok, "sanitized": True,
            })
        health = final_health(ctx)
        if health.get("quick_check") != "ok":
            raise g2.GateFailure(
                "SQLite quick check failed during active NATS resume.",
                stage="resume_sqlite_quick_check", retryable=False,
            )
        if health.get("matched") is True:
            return health
        time.sleep(1.0)
    raise g2.GateFailure(
        "JSON/SQLite parity did not recover after the tracked active run reconciled.",
        stage="resume_final_parity", retryable=False,
    )


def reconcile_active_nats_resume(
    ctx: g2.Context, scenario_state: dict[str, Any], state: dict[str, Any],
    state_path: Path, *, args: argparse.Namespace, progress_path: Path,
    lifecycle_path: Path, nats_status_path: Path, events_path: Path,
) -> dict[str, Any] | None:
    tracked_run = str(scenario_state.get("tracked_run_id") or "")
    action = scenario_state.get("action") or {}
    if not tracked_run or not action.get("action_started"):
        return None

    lifecycle = g2.lifecycle_snapshot(ctx.db_path)
    active_ids = {
        str(item.get("run_id") or "")
        for item in (lifecycle.get("active_runs") or [])
        if str(item.get("run_id") or "")
    }
    if active_ids and active_ids != {tracked_run}:
        raise g2.GateFailure(
            "Active NATS resume found an ambiguous or unrelated run identity.",
            stage="resume_identity", retryable=False,
        )
    run = g2.lifecycle_snapshot(ctx.db_path, run_id=tracked_run).get("run") or {}
    if not run:
        raise g2.GateFailure(
            "Active NATS resume could not find the tracked durable run.",
            stage="resume_identity", retryable=False,
        )

    initial = scenario_state.get("process_before") or {}
    before_nats = action.get("process_before") or initial.get("pocket-nats") or {}
    current_nats = pm2_process(g2.pm2_snapshot(), "pocket-nats")
    if not current_nats or current_nats.get("status") != "online":
        raise g2.GateFailure(
            "NATS is not online during active resume.",
            stage="resume_nats_process", retryable=False,
        )
    old_pid = int(before_nats.get("pid") or 0)
    new_pid = int(current_nats.get("pid") or 0)
    if not action.get("action_completed"):
        if old_pid and new_pid and new_pid != old_pid:
            action.update({
                "action_completed": True, "process_after": current_nats,
                "completed_at": g2.utc_now(), "recovered_on_resume": True,
            })
            scenario_state["action"] = action
            g2.atomic_write_json(state_path, state)
        else:
            raise g2.GateFailure(
                "NATS restart state is ambiguous on resume; refusing to restart twice.",
                stage="resume_disruption", retryable=False,
            )

    recovered = wait_for_nats(
        ctx, timeout=float(args.service_recovery_timeout_seconds),
        events_path=nats_status_path,
    )
    if not recovered or not recovered.get("healthy"):
        raise g2.GateFailure(
            "NATS, API, worker, or durable consumer did not recover during resume.",
            stage="resume_nats_recovery", retryable=False,
        )

    if str(run.get("status") or "").lower() not in TERMINAL:
        run = wait_terminal(
            ctx, tracked_run, timeout=float(args.run_timeout_seconds),
            progress_path=progress_path, lifecycle_path=lifecycle_path,
        ) or {}
    if not run or str(run.get("status") or "").lower() not in TERMINAL:
        raise g2.GateFailure(
            "The tracked active run did not reach a truthful terminal state on resume.",
            stage="resume_wait_run", retryable=False,
        )

    wait_for_reconciled_health(
        ctx, timeout=float(args.service_recovery_timeout_seconds),
        events_path=events_path,
    )
    scenario_state["resume_reconciled"] = True
    g2.atomic_write_json(state_path, state)
    return run


def run_nats_restart(args: argparse.Namespace) -> int:
    ctx = g2.common_context(args)
    ctx.gate_dir.mkdir(parents=True, exist_ok=True)
    started_at, started_mono = g2.utc_now(), time.monotonic()
    state_path = ctx.gate_dir / "state.json"
    processes = ctx.gate_dir / "processes.jsonl"
    nats_status = ctx.gate_dir / "nats-status.jsonl"
    consumers = ctx.gate_dir / "consumers.jsonl"
    lifecycle_path = ctx.gate_dir / "lifecycle.jsonl"
    progress_path = ctx.gate_dir / "progress.jsonl"
    resources = ctx.gate_dir / "resources.jsonl"
    events = ctx.gate_dir / "events.jsonl"
    state = g2.read_json(state_path, {}) or {
        "schema_version": 1, "run_id": ctx.run_id, "gate_id": ctx.gate_id,
        "completed_scenarios": [], "scenarios": {},
    }
    failures: list[str] = []
    results: list[dict[str, Any]] = []
    try:
        for scenario in _scenario_list(args.scenario, ("idle", "active")):
            scenario_state = state["scenarios"].setdefault(scenario, {})
            if scenario in state.get("completed_scenarios", []):
                results.append(scenario_state["result"])
                continue
            tracked_run = str(scenario_state.get("tracked_run_id") or "")
            resumed_terminal = None
            if scenario == "active":
                resumed_terminal = reconcile_active_nats_resume(
                    ctx, scenario_state, state, state_path, args=args,
                    progress_path=progress_path, lifecycle_path=lifecycle_path,
                    nats_status_path=nats_status, events_path=events,
                )
            _lifecycle, current_preflight = _preflight_disruption(ctx, allow_run_id=tracked_run)
            if "process_before" not in scenario_state:
                scenario_state["process_before"] = process_evidence(
                    current_preflight, ("pocket-api", "pocket-worker", "pocket-nats")
                )
                g2.atomic_write_json(state_path, state)
            initial = scenario_state["process_before"]
            if "consumer_before" not in scenario_state:
                nats_before_result = ctx.client().request(
                    "GET", ctx.proxy_base_url, "/api/nats/status", retry_read=True
                )
                scenario_state["consumer_before"] = consumer_summary(nats_before_result.body)
                g2.append_jsonl(nats_status, safe_nats_view(nats_before_result.body))
                g2.atomic_write_json(state_path, state)
            before_consumer = scenario_state["consumer_before"]
            terminal: dict[str, Any] | None = resumed_terminal
            delivery_before = scenario_state.get("delivery_attempt_before")
            if scenario == "active" and not tracked_run:
                submit, payload = submit_quick(
                    ctx, f"nats-active-{secrets.token_hex(4)}", timeout=10.0
                )
                tracked_run = str(payload.get("run_id") or "")
                if not submit.ok or not tracked_run:
                    raise g2.GateFailure(
                        "Could not submit the active-scenario Quick scan.", stage="submit"
                    )
                scenario_state["tracked_run_id"] = tracked_run
                g2.atomic_write_json(state_path, state)
            if scenario == "active":
                current_run = g2.lifecycle_snapshot(ctx.db_path, run_id=tracked_run).get("run") or {}
                action = scenario_state.setdefault(
                    "action", {"action_started": False, "action_completed": False, "safe_to_repeat": False}
                )
                if not action.get("action_started"):
                    execution = wait_for_run(
                        ctx, tracked_run,
                        timeout=float(args.execution_evidence_timeout_seconds),
                        progress_path=progress_path, lifecycle_path=lifecycle_path,
                        require_execution=True,
                    )
                    if not execution or not (
                        execution.get("command_received_at") or execution.get("execution_started_at")
                    ):
                        raise g2.GateFailure(
                            "Active NATS restart did not observe durable execution evidence before disruption.",
                            stage="wait_execution",
                        )
                    delivery_before = execution.get("delivery_attempt")
                    scenario_state["delivery_attempt_before"] = delivery_before
                    g2.atomic_write_json(state_path, state)
                elif str(current_run.get("status") or "").lower() in TERMINAL:
                    terminal = current_run
            action = scenario_state.setdefault(
                "action", {"action_started": False, "action_completed": False, "safe_to_repeat": False}
            )
            process_before = action.get("process_before") or initial.get("pocket-nats")
            if not action.get("action_completed"):
                if action.get("action_started"):
                    current = pm2_process(g2.pm2_snapshot(), "pocket-nats")
                    if current and int(current.get("pid") or 0) != int((process_before or {}).get("pid") or 0):
                        action.update({
                            "action_completed": True,
                            "process_after": current,
                            "completed_at": g2.utc_now(),
                        })
                        g2.atomic_write_json(state_path, state)
                    else:
                        raise g2.GateFailure(
                            "NATS restart state is ambiguous on resume; refusing to restart twice.",
                            stage="resume_disruption", retryable=False,
                        )
                else:
                    action.update({
                        "action_started": True,
                        "process_before": initial.get("pocket-nats"),
                        "started_at": g2.utc_now(),
                        "safe_to_repeat": False,
                    })
                    g2.atomic_write_json(state_path, state)
                    action_result = run_pm2_action("pocket-nats", "restart", timeout=float(args.service_recovery_timeout_seconds))
                    g2.append_jsonl(events, {"event": "process.action", **action_result})
                    if not action_result.get("ok"):
                        raise g2.GateFailure(
                            "The precise pocket-nats restart command failed.",
                            stage="restart_nats", retryable=False,
                        )
                    after_nats = wait_for_pm2(
                        "pocket-nats", online=True,
                        timeout=float(args.service_recovery_timeout_seconds),
                        old_pid=int((initial.get("pocket-nats") or {}).get("pid") or 0),
                        require_pid_change=True,
                    )
                    if not after_nats:
                        raise g2.GateFailure(
                            "NATS did not return with a new PID before the recovery deadline.",
                            stage="wait_nats_process", retryable=False,
                        )
                    action.update({
                        "action_completed": True,
                        "process_after": after_nats,
                        "completed_at": g2.utc_now(),
                    })
                    g2.atomic_write_json(state_path, state)
            recovered = wait_for_nats(
                ctx, timeout=float(args.service_recovery_timeout_seconds),
                events_path=nats_status,
            )
            if not recovered or not recovered.get("healthy"):
                raise g2.GateFailure(
                    "NATS, API, worker, or durable consumer did not recover before the deadline.",
                    stage="wait_nats_recovery", retryable=False,
                )
            g2.append_jsonl(consumers, {
                "timestamp": g2.utc_now(), "scenario": scenario,
                "before": before_consumer, "after": recovered, "sanitized": True,
            })
            if scenario == "active" and terminal is None:
                terminal = wait_terminal(
                    ctx, tracked_run, timeout=float(args.run_timeout_seconds),
                    progress_path=progress_path, lifecycle_path=lifecycle_path,
                )
                if not terminal:
                    raise g2.GateFailure(
                        "The active run did not reach a truthful terminal state after NATS recovery.",
                        stage="wait_run_recovery", retryable=False,
                    )
            current = process_evidence(
                g2.pm2_snapshot(), ("pocket-api", "pocket-worker", "pocket-nats")
            )
            g2.append_jsonl(processes, {
                "timestamp": g2.utc_now(), "scenario": scenario,
                "before": initial, "after": current, "sanitized": True,
            })
            follow_id, follow, follow_latency = final_independent_scan(
                ctx, f"post-nats-{scenario}", timeout=float(args.run_timeout_seconds),
                progress_path=progress_path, lifecycle_path=lifecycle_path,
            )
            scenario_failures: list[str] = []
            if int((current.get("pocket-api") or {}).get("pid") or 0) != int((initial.get("pocket-api") or {}).get("pid") or 0):
                scenario_failures.append("api_pid_changed")
            if int((current.get("pocket-worker") or {}).get("pid") or 0) != int((initial.get("pocket-worker") or {}).get("pid") or 0):
                scenario_failures.append("worker_pid_changed")
            if restart_delta(initial.get("pocket-nats"), current.get("pocket-nats")) != 1:
                scenario_failures.append("nats_restart_count_delta")
            if restart_delta(initial.get("pocket-api"), current.get("pocket-api")) != 0:
                scenario_failures.append("api_restart_count_delta")
            if restart_delta(initial.get("pocket-worker"), current.get("pocket-worker")) != 0:
                scenario_failures.append("worker_restart_count_delta")
            if recovered.get("duplicate_consumers"):
                scenario_failures.append("duplicate_consumers")
            if terminal:
                scenario_failures.extend(lifecycle_order_issues(terminal))
                if duplicate_terminal_success(
                    runs_after(ctx.db_path, int(terminal.get("requested_at_epoch_ms") or 0)),
                    str(terminal.get("command_id") or ""),
                ):
                    scenario_failures.append("duplicate_terminal_success")
            if not follow or str(follow.get("status") or "").lower() not in TERMINAL_SUCCESS:
                scenario_failures.append("post_recovery_scan_failed")
            scenario_result = {
                "scenario": scenario,
                "nats_pid_before": (initial.get("pocket-nats") or {}).get("pid"),
                "nats_pid_after": (current.get("pocket-nats") or {}).get("pid"),
                "api_pid_before": (initial.get("pocket-api") or {}).get("pid"),
                "api_pid_after": (current.get("pocket-api") or {}).get("pid"),
                "worker_pid_before": (initial.get("pocket-worker") or {}).get("pid"),
                "worker_pid_after": (current.get("pocket-worker") or {}).get("pid"),
                "nats_restart_count_delta": restart_delta(initial.get("pocket-nats"), current.get("pocket-nats")),
                "api_restart_count_delta": restart_delta(initial.get("pocket-api"), current.get("pocket-api")),
                "worker_restart_count_delta": restart_delta(initial.get("pocket-worker"), current.get("pocket-worker")),
                "consumer_healthy_before": before_consumer.get("healthy"),
                "consumer_healthy_after": recovered.get("healthy"),
                "consumer_generation_before": before_consumer.get("generation"),
                "consumer_generation_after": recovered.get("generation"),
                "duplicate_consumers": recovered.get("duplicate_consumers"),
                "run_id_tracked": tracked_run,
                "delivery_attempt_before": delivery_before,
                "delivery_attempt_after": (terminal or {}).get("delivery_attempt"),
                "terminal_status": (terminal or {}).get("status"),
                "active_key_cleared": not terminal or terminal.get("active_key") in (None, ""),
                "post_recovery_scan_run_id": follow_id,
                "post_recovery_submission_latency_seconds": follow_latency,
                "recovery_outcome": recovery_outcome(terminal) if terminal else "idle_recovered",
                "failures": sorted(set(scenario_failures)),
            }
            failures.extend(f"{scenario}:{item}" for item in scenario_failures)
            results.append(scenario_result)
            scenario_state["result"] = scenario_result
            state["completed_scenarios"].append(scenario)
            g2.atomic_write_json(state_path, state)
            g2.append_jsonl(resources, g2.resource_snapshot(
                db_path=ctx.db_path, state_dir=ctx.state_dir, run_dir=ctx.run_dir
            ))
            g2.ensure_report_budget(ctx.run_dir, ctx.report_limit_bytes)
        health = final_health(ctx)
        progress_issues = g2.progress_regressions(read_jsonl(progress_path))
        if progress_issues:
            failures.append("progress_regression")
        if health.get("quick_check") != "ok":
            failures.append("sqlite_quick_check")
        if health.get("matched") is not True:
            failures.append("parity_mismatch")
        result = {
            "run_id": ctx.run_id, "gate_id": ctx.gate_id, "gate": ctx.gate_id,
            "status": "passed" if not failures else "failed", "started_at": started_at,
            "duration_seconds": round(time.monotonic() - started_mono, 3),
            "scenario": args.scenario, "scenario_results": results,
            "progress_regressions": progress_issues,
            "sqlite_quick_check": health.get("quick_check"),
            "parity_matched": health.get("matched"),
            "failed_stage": "evaluation" if failures else "",
            "failure_reason": "" if not failures else "NATS recovery requirements failed: " + ", ".join(sorted(set(failures))),
            "retryable": False, "resume_safe": True, "sanitized": True,
            "evidence_refs": [
                "gates/nats-restart/processes.jsonl", "gates/nats-restart/nats-status.jsonl",
                "gates/nats-restart/consumers.jsonl", "gates/nats-restart/lifecycle.jsonl",
                "gates/nats-restart/progress.jsonl", "gates/nats-restart/resources.jsonl",
                "gates/nats-restart/events.jsonl",
            ],
        }
        if len(results) == 1:
            result.update(results[0])
            result["scenario_results"] = results
        g2.write_result(ctx.gate_dir / "result.json", result)
        return 0 if not failures else 2
    except g2.GateFailure as exc:
        return result_failure(
            ctx, started_at, started_mono, exc.reason, exc.stage,
            {"scenario": args.scenario, "scenario_results": results},
        )

def run_worker_restart(args: argparse.Namespace) -> int:
    ctx = g2.common_context(args)
    ctx.gate_dir.mkdir(parents=True, exist_ok=True)
    started_at, started_mono = g2.utc_now(), time.monotonic()
    state_path = ctx.gate_dir / "state.json"
    processes = ctx.gate_dir / "processes.jsonl"
    consumers = ctx.gate_dir / "consumers.jsonl"
    scanners = ctx.gate_dir / "scanners.jsonl"
    lifecycle_path = ctx.gate_dir / "lifecycle.jsonl"
    progress_path = ctx.gate_dir / "progress.jsonl"
    resources = ctx.gate_dir / "resources.jsonl"
    events = ctx.gate_dir / "events.jsonl"
    state = g2.read_json(state_path, {}) or {
        "schema_version": 1, "run_id": ctx.run_id, "gate_id": ctx.gate_id,
        "completed_scenarios": [], "scenarios": {},
    }
    failures: list[str] = []
    results: list[dict[str, Any]] = []
    try:
        for scenario in _scenario_list(args.scenario, ("before-claim", "after-claim")):
            scenario_state = state["scenarios"].setdefault(scenario, {})
            if scenario in state.get("completed_scenarios", []):
                results.append(scenario_state["result"])
                continue
            tracked_run = str(scenario_state.get("tracked_run_id") or "")
            action = scenario_state.setdefault(
                "action", {"action_started": False, "action_completed": False, "safe_to_repeat": False}
            )
            start_action = scenario_state.setdefault(
                "worker_start", {"action_started": False, "action_completed": False, "safe_to_repeat": False}
            )
            allow_worker_offline = scenario == "before-claim" and (
                bool(action.get("action_started")) or bool(action.get("action_completed"))
            ) and not bool(start_action.get("action_completed"))
            _lifecycle, current_preflight = _preflight_disruption(
                ctx, allow_run_id=tracked_run, allow_worker_offline=allow_worker_offline
            )
            if "process_before" not in scenario_state:
                scenario_state["process_before"] = process_evidence(
                    current_preflight, ("pocket-api", "pocket-worker", "pocket-nats")
                )
                g2.atomic_write_json(state_path, state)
            initial = scenario_state["process_before"]
            terminal: dict[str, Any] | None = None
            delivery_before = scenario_state.get("delivery_attempt_before")
            scanner_before = scenario_state.get("scanner_children_before") or []
            if scenario == "before-claim":
                process_before = action.get("process_before") or initial.get("pocket-worker")
                if not action.get("action_completed"):
                    if action.get("action_started"):
                        worker = pm2_process(g2.pm2_snapshot(), "pocket-worker")
                        if worker and worker.get("status") != "online":
                            action.update({
                                "action_completed": True, "process_after": worker,
                                "completed_at": g2.utc_now(),
                            })
                            g2.atomic_write_json(state_path, state)
                        else:
                            raise g2.GateFailure(
                                "Worker stop state is ambiguous on resume; refusing to stop twice.",
                                stage="resume_disruption", retryable=False,
                            )
                    else:
                        action.update({
                            "action_started": True,
                            "process_before": initial.get("pocket-worker"),
                            "started_at": g2.utc_now(), "safe_to_repeat": False,
                        })
                        g2.atomic_write_json(state_path, state)
                        action_result = run_pm2_action("pocket-worker", "stop", timeout=float(args.service_recovery_timeout_seconds))
                        g2.append_jsonl(events, {"event": "process.action", **action_result})
                        if not action_result.get("ok"):
                            raise g2.GateFailure(
                                "The precise pocket-worker stop command failed.",
                                stage="stop_worker", retryable=False,
                            )
                        stopped = wait_for_pm2(
                            "pocket-worker", online=False,
                            timeout=float(args.service_recovery_timeout_seconds),
                        )
                        if stopped is None:
                            raise g2.GateFailure(
                                "Worker did not stop before the deadline.",
                                stage="wait_worker_stopped", retryable=False,
                            )
                        action.update({
                            "action_completed": True, "process_after": stopped,
                            "completed_at": g2.utc_now(),
                        })
                        g2.atomic_write_json(state_path, state)
                if not tracked_run and "truthful_rejection" not in scenario_state:
                    submit, payload = submit_quick(
                        ctx, f"worker-before-{secrets.token_hex(4)}", timeout=10.0
                    )
                    if submit.ok and payload.get("run_id"):
                        tracked_run = str(payload.get("run_id"))
                        scenario_state["tracked_run_id"] = tracked_run
                    else:
                        scenario_state["truthful_rejection"] = {
                            "http_status": submit.status_code,
                            "error_type": submit.error_type,
                        }
                    g2.atomic_write_json(state_path, state)
                if not start_action.get("action_completed"):
                    if start_action.get("action_started"):
                        current_worker = pm2_process(g2.pm2_snapshot(), "pocket-worker")
                        if current_worker and current_worker.get("status") == "online" and int(current_worker.get("pid") or 0) != int((process_before or {}).get("pid") or 0):
                            start_action.update({
                                "action_completed": True,
                                "process_after": current_worker,
                                "completed_at": g2.utc_now(),
                            })
                            g2.atomic_write_json(state_path, state)
                        else:
                            raise g2.GateFailure(
                                "Worker start state is ambiguous on resume; refusing to start twice.",
                                stage="resume_worker_start", retryable=False,
                            )
                    else:
                        start_action.update({
                            "action_started": True, "started_at": g2.utc_now(),
                            "safe_to_repeat": False,
                        })
                        g2.atomic_write_json(state_path, state)
                        start_result = run_pm2_action("pocket-worker", "start", timeout=float(args.service_recovery_timeout_seconds))
                        g2.append_jsonl(events, {"event": "process.action", **start_result})
                        if not start_result.get("ok"):
                            raise g2.GateFailure(
                                "Worker could not be restored online.",
                                stage="start_worker", retryable=False,
                            )
                        online = wait_for_pm2(
                            "pocket-worker", online=True,
                            timeout=float(args.service_recovery_timeout_seconds),
                            old_pid=int((process_before or {}).get("pid") or 0),
                            require_pid_change=True,
                        )
                        if not online:
                            raise g2.GateFailure(
                                "Worker did not return with a new PID.",
                                stage="wait_worker_online", retryable=False,
                            )
                        start_action.update({
                            "action_completed": True, "process_after": online,
                            "completed_at": g2.utc_now(),
                        })
                        g2.atomic_write_json(state_path, state)
                recovered = wait_for_nats(
                    ctx, timeout=float(args.service_recovery_timeout_seconds),
                    events_path=consumers,
                )
                if not recovered or not recovered.get("healthy"):
                    raise g2.GateFailure(
                        "Worker durable consumer did not recover.",
                        stage="wait_consumer", retryable=False,
                    )
                if tracked_run:
                    terminal = wait_terminal(
                        ctx, tracked_run, timeout=float(args.run_timeout_seconds),
                        progress_path=progress_path, lifecycle_path=lifecycle_path,
                    )
            else:
                if not tracked_run:
                    submit, payload = submit_quick(
                        ctx, f"worker-after-{secrets.token_hex(4)}", timeout=10.0
                    )
                    tracked_run = str(payload.get("run_id") or "")
                    if not submit.ok or not tracked_run:
                        raise g2.GateFailure(
                            "Could not submit the after-claim Quick scan.", stage="submit"
                        )
                    scenario_state["tracked_run_id"] = tracked_run
                    g2.atomic_write_json(state_path, state)
                current_run = g2.lifecycle_snapshot(ctx.db_path, run_id=tracked_run).get("run") or {}
                if not action.get("action_started"):
                    execution = wait_for_run(
                        ctx, tracked_run,
                        timeout=float(args.execution_evidence_timeout_seconds),
                        progress_path=progress_path, lifecycle_path=lifecycle_path,
                        require_execution=True,
                    )
                    if not execution:
                        raise g2.GateFailure(
                            "Worker restart did not observe command claim/execution evidence.",
                            stage="wait_execution",
                        )
                    delivery_before = execution.get("delivery_attempt")
                    scanner_before = g2.scanner_inventory()
                    scenario_state["delivery_attempt_before"] = delivery_before
                    scenario_state["scanner_children_before"] = scanner_before
                    g2.append_jsonl(scanners, {
                        "timestamp": g2.utc_now(), "scenario": scenario,
                        "phase": "before", "scanners": scanner_before, "sanitized": True,
                    })
                    g2.atomic_write_json(state_path, state)
                elif str(current_run.get("status") or "").lower() in TERMINAL:
                    terminal = current_run
                process_before = action.get("process_before") or initial.get("pocket-worker")
                if not action.get("action_completed"):
                    if action.get("action_started"):
                        current_worker = pm2_process(g2.pm2_snapshot(), "pocket-worker")
                        if current_worker and int(current_worker.get("pid") or 0) != int((process_before or {}).get("pid") or 0):
                            action.update({
                                "action_completed": True,
                                "process_after": current_worker,
                                "completed_at": g2.utc_now(),
                            })
                            g2.atomic_write_json(state_path, state)
                        else:
                            raise g2.GateFailure(
                                "Worker restart state is ambiguous on resume; refusing to restart twice.",
                                stage="resume_disruption", retryable=False,
                            )
                    else:
                        action.update({
                            "action_started": True,
                            "process_before": initial.get("pocket-worker"),
                            "started_at": g2.utc_now(), "safe_to_repeat": False,
                        })
                        g2.atomic_write_json(state_path, state)
                        action_result = run_pm2_action("pocket-worker", "restart", timeout=float(args.service_recovery_timeout_seconds))
                        g2.append_jsonl(events, {"event": "process.action", **action_result})
                        if not action_result.get("ok"):
                            raise g2.GateFailure(
                                "The precise pocket-worker restart command failed.",
                                stage="restart_worker", retryable=False,
                            )
                        online = wait_for_pm2(
                            "pocket-worker", online=True,
                            timeout=float(args.service_recovery_timeout_seconds),
                            old_pid=int((process_before or {}).get("pid") or 0),
                            require_pid_change=True,
                        )
                        if not online:
                            raise g2.GateFailure(
                                "Worker did not return with a new PID.",
                                stage="wait_worker_online", retryable=False,
                            )
                        action.update({
                            "action_completed": True, "process_after": online,
                            "completed_at": g2.utc_now(),
                        })
                        g2.atomic_write_json(state_path, state)
                recovered = wait_for_nats(
                    ctx, timeout=float(args.service_recovery_timeout_seconds),
                    events_path=consumers,
                )
                if not recovered or not recovered.get("healthy"):
                    raise g2.GateFailure(
                        "Worker durable consumer did not recover.",
                        stage="wait_consumer", retryable=False,
                    )
                if terminal is None:
                    terminal = wait_terminal(
                        ctx, tracked_run, timeout=float(args.run_timeout_seconds),
                        progress_path=progress_path, lifecycle_path=lifecycle_path,
                    )
            current = process_evidence(
                g2.pm2_snapshot(), ("pocket-api", "pocket-worker", "pocket-nats")
            )
            scanner_after = g2.wait_for_scanner_cleanup(20)
            g2.append_jsonl(scanners, {
                "timestamp": g2.utc_now(), "scenario": scenario,
                "phase": "after", "scanners": scanner_after, "sanitized": True,
            })
            g2.append_jsonl(processes, {
                "timestamp": g2.utc_now(), "scenario": scenario,
                "before": initial, "after": current, "sanitized": True,
            })
            follow_id, follow, follow_latency = final_independent_scan(
                ctx, f"post-worker-{scenario}", timeout=float(args.run_timeout_seconds),
                progress_path=progress_path, lifecycle_path=lifecycle_path,
            )
            scenario_failures: list[str] = []
            if int((current.get("pocket-api") or {}).get("pid") or 0) != int((initial.get("pocket-api") or {}).get("pid") or 0):
                scenario_failures.append("api_pid_changed")
            if int((current.get("pocket-nats") or {}).get("pid") or 0) != int((initial.get("pocket-nats") or {}).get("pid") or 0):
                scenario_failures.append("nats_pid_changed")
            if int((current.get("pocket-worker") or {}).get("pid") or 0) == int((initial.get("pocket-worker") or {}).get("pid") or 0):
                scenario_failures.append("worker_pid_unchanged")
            if restart_delta(initial.get("pocket-api"), current.get("pocket-api")) != 0:
                scenario_failures.append("api_restart_count_delta")
            if restart_delta(initial.get("pocket-nats"), current.get("pocket-nats")) != 0:
                scenario_failures.append("nats_restart_count_delta")
            if scanner_after:
                scenario_failures.append("scanner_residue")
            if tracked_run:
                if not terminal:
                    scenario_failures.append("unresolved_run")
                else:
                    scenario_failures.extend(lifecycle_order_issues(terminal))
                    if duplicate_terminal_success(
                        runs_after(ctx.db_path, int(terminal.get("requested_at_epoch_ms") or 0)),
                        str(terminal.get("command_id") or ""),
                    ):
                        scenario_failures.append("duplicate_terminal_success")
            if not follow or str(follow.get("status") or "").lower() not in TERMINAL_SUCCESS:
                scenario_failures.append("post_recovery_scan_failed")
            outcome = (
                recovery_outcome(terminal, restarted_after_claim=scenario == "after-claim")
                if tracked_run else "truthful_rejection"
            )
            if outcome == "unresolved":
                scenario_failures.append("unresolved_recovery")
            scenario_result = {
                "scenario": scenario,
                "worker_pid_before": (initial.get("pocket-worker") or {}).get("pid"),
                "worker_pid_after": (current.get("pocket-worker") or {}).get("pid"),
                "worker_restart_count_delta": restart_delta(initial.get("pocket-worker"), current.get("pocket-worker")),
                "api_pid_before": (initial.get("pocket-api") or {}).get("pid"),
                "api_pid_after": (current.get("pocket-api") or {}).get("pid"),
                "nats_pid_before": (initial.get("pocket-nats") or {}).get("pid"),
                "nats_pid_after": (current.get("pocket-nats") or {}).get("pid"),
                "run_id_tracked": tracked_run,
                "command_id": (terminal or {}).get("command_id"),
                "delivery_attempt_before": delivery_before,
                "delivery_attempt_after": (terminal or {}).get("delivery_attempt"),
                "scanner_children_before": scanner_before,
                "scanner_children_after": scanner_after,
                "recovery_outcome": outcome,
                "duplicate_terminal_success": "duplicate_terminal_success" in scenario_failures,
                "active_key_cleared": not terminal or terminal.get("active_key") in (None, ""),
                "post_recovery_scan_run_id": follow_id,
                "post_recovery_submission_latency_seconds": follow_latency,
                "failures": sorted(set(scenario_failures)),
            }
            failures.extend(f"{scenario}:{item}" for item in scenario_failures)
            results.append(scenario_result)
            scenario_state["result"] = scenario_result
            state["completed_scenarios"].append(scenario)
            g2.atomic_write_json(state_path, state)
            g2.append_jsonl(resources, g2.resource_snapshot(
                db_path=ctx.db_path, state_dir=ctx.state_dir, run_dir=ctx.run_dir
            ))
            g2.ensure_report_budget(ctx.run_dir, ctx.report_limit_bytes)
        health = final_health(ctx)
        progress_issues = g2.progress_regressions(read_jsonl(progress_path))
        if progress_issues:
            failures.append("progress_regression")
        if health.get("quick_check") != "ok":
            failures.append("sqlite_quick_check")
        if health.get("matched") is not True:
            failures.append("parity_mismatch")
        result = {
            "run_id": ctx.run_id, "gate_id": ctx.gate_id, "gate": ctx.gate_id,
            "status": "passed" if not failures else "failed", "started_at": started_at,
            "duration_seconds": round(time.monotonic() - started_mono, 3),
            "scenario": args.scenario, "scenario_results": results,
            "progress_regressions": progress_issues,
            "sqlite_quick_check": health.get("quick_check"),
            "parity_matched": health.get("matched"),
            "failed_stage": "evaluation" if failures else "",
            "failure_reason": "" if not failures else "Worker recovery requirements failed: " + ", ".join(sorted(set(failures))),
            "retryable": False, "resume_safe": True, "sanitized": True,
            "evidence_refs": [
                "gates/worker-restart/processes.jsonl", "gates/worker-restart/consumers.jsonl",
                "gates/worker-restart/scanners.jsonl", "gates/worker-restart/lifecycle.jsonl",
                "gates/worker-restart/progress.jsonl", "gates/worker-restart/resources.jsonl",
                "gates/worker-restart/events.jsonl",
            ],
        }
        if len(results) == 1:
            result.update(results[0])
            result["scenario_results"] = results
        g2.write_result(ctx.gate_dir / "result.json", result)
        return 0 if not failures else 2
    except g2.GateFailure as exc:
        worker = pm2_process(g2.pm2_snapshot(), "pocket-worker")
        if not worker or worker.get("status") != "online":
            restore = run_pm2_action("pocket-worker", "start", timeout=float(args.service_recovery_timeout_seconds))
            g2.append_jsonl(events, {"event": "process.cleanup", **restore})
        return result_failure(
            ctx, started_at, started_mono, exc.reason, exc.stage,
            {"scenario": args.scenario, "scenario_results": results},
        )

def add_common(parser: argparse.ArgumentParser) -> None:
    g2.add_common(parser)
    parser.add_argument("--run-timeout-seconds", type=int, default=5400)
    parser.add_argument("--service-recovery-timeout-seconds", type=int, default=120)
    parser.add_argument("--execution-evidence-timeout-seconds", type=int, default=300)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    submission = sub.add_parser("submission-recovery")
    add_common(submission)
    submission.add_argument("--client-timeout-seconds", type=float, default=2.0)
    submission.add_argument("--response-delay-ms", type=int, default=5000)
    submission.add_argument("--discovery-timeout-seconds", type=int, default=30)
    nats = sub.add_parser("nats-restart")
    add_common(nats)
    nats.add_argument("--scenario", default="both")
    worker = sub.add_parser("worker-restart")
    add_common(worker)
    worker.add_argument("--scenario", default="both")
    return parser


def validate_args(args: argparse.Namespace) -> None:
    if args.report_limit_bytes < 1024 * 1024:
        raise ValueError("report limit must be at least 1 MiB")
    if args.run_timeout_seconds < 1 or args.service_recovery_timeout_seconds < 1 or args.execution_evidence_timeout_seconds < 1:
        raise ValueError("recovery timeouts must be positive")
    if args.command == "submission-recovery":
        if args.client_timeout_seconds <= 0:
            raise ValueError("client timeout must be positive")
        if args.response_delay_ms < 1 or args.response_delay_ms > MAX_DELAY_MS:
            raise ValueError(f"response delay must be between 1 and {MAX_DELAY_MS} ms")
        if args.client_timeout_seconds * 1000 >= args.response_delay_ms:
            raise ValueError("client timeout must be shorter than the response delay")
        if args.discovery_timeout_seconds < 1:
            raise ValueError("discovery timeout must be positive")
    elif args.command == "nats-restart":
        _scenario_list(args.scenario, ("idle", "active"))
    elif args.command == "worker-restart":
        _scenario_list(args.scenario, ("before-claim", "after-claim"))


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        validate_args(args)
        if args.command == "submission-recovery":
            return run_submission_recovery(args)
        if args.command == "nats-restart":
            return run_nats_restart(args)
        if args.command == "worker-restart":
            return run_worker_restart(args)
    except KeyboardInterrupt:
        return 75
    except (ValueError, RuntimeError) as exc:
        print(f"ERROR: {g2.clamp_text(exc)}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
