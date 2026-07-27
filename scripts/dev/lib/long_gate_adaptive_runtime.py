#!/usr/bin/env python3
"""Phase 4/5 adaptive runtime qualification gate.

Samples only sanitized runtime diagnostics. The common long-gate framework owns
run locking, durable paths, baseline/parity checks, sanitization, checksums, and
final aggregation.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import signal
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable

_STOP = False


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".{path.name}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp"
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True, ensure_ascii=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def append_jsonl(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def percentile(values: Iterable[float], ratio: float) -> float | None:
    clean = sorted(float(value) for value in values if math.isfinite(float(value)))
    if not clean:
        return None
    index = min(len(clean) - 1, max(0, math.ceil(len(clean) * ratio) - 1))
    return clean[index]


def distribution(values: Iterable[float]) -> dict[str, Any]:
    clean = [float(value) for value in values if math.isfinite(float(value))]
    return {
        "count": len(clean),
        "p50": round(percentile(clean, 0.50), 3) if clean else None,
        "p95": round(percentile(clean, 0.95), 3) if clean else None,
        "p99": round(percentile(clean, 0.99), 3) if clean else None,
        "max": round(max(clean), 3) if clean else None,
    }


def fetch_json(base_url: str, path: str, *, timeout: float) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    url = f"{base_url.rstrip('/')}{path}"
    headers = {"Accept": "application/json"}
    token = os.environ.get("POCKETLAB_API_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers, method="GET")
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read(4 * 1024 * 1024 + 1)
            if len(body) > 4 * 1024 * 1024:
                raise RuntimeError("diagnostics_response_too_large")
            payload = json.loads(body.decode("utf-8"))
            if not isinstance(payload, dict):
                raise RuntimeError("diagnostics_response_invalid")
            return payload, {
                "ok": True,
                "status": int(response.status),
                "duration_ms": round((time.monotonic() - started) * 1000.0, 3),
            }
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError, RuntimeError) as exc:
        return None, {
            "ok": False,
            "error_type": type(exc).__name__,
            "duration_ms": round((time.monotonic() - started) * 1000.0, 3),
        }


def safe_sample(payload: dict[str, Any], http: dict[str, Any]) -> dict[str, Any]:
    scheduler = payload.get("projection_scheduler") if isinstance(payload.get("projection_scheduler"), dict) else {}
    adaptive = payload.get("adaptive_runtime") if isinstance(payload.get("adaptive_runtime"), dict) else {}
    if not adaptive and isinstance(scheduler.get("adaptive_runtime"), dict):
        adaptive = scheduler["adaptive_runtime"]
    process_runtime = payload.get("process_runtime") if isinstance(payload.get("process_runtime"), dict) else {}
    hot_path = payload.get("hot_path") if isinstance(payload.get("hot_path"), dict) else {}
    event_loop = payload.get("event_loop") if isinstance(payload.get("event_loop"), dict) else {}
    domain_rows: dict[str, Any] = {}
    raw_domains = adaptive.get("domains") if isinstance(adaptive.get("domains"), dict) else {}
    for domain, row in raw_domains.items():
        if not isinstance(row, dict):
            continue
        domain_rows[str(domain)[:96]] = {
            "cadence_state": str(row.get("cadence_state") or "unknown")[:32],
            "load_state": str(row.get("load_state") or "unknown")[:32],
            "next_reconciliation_seconds": int(row.get("next_reconciliation_seconds") or 0),
            "cpu_budget_remaining_ms": float(row.get("cpu_budget_remaining_ms") or 0.0),
            "cpu_budget_exhausted": bool(row.get("cpu_budget_exhausted")),
            "admitted": int(row.get("admitted") or 0),
            "deferred": int(row.get("deferred") or 0),
            "last_reason": str(row.get("last_reason") or "")[:80],
            "cpu_ms": row.get("cpu_ms") if isinstance(row.get("cpu_ms"), dict) else {},
            "wall_ms": row.get("wall_ms") if isinstance(row.get("wall_ms"), dict) else {},
            "queue_wait_ms": row.get("queue_wait_ms") if isinstance(row.get("queue_wait_ms"), dict) else {},
            "payload_bytes": row.get("payload_bytes") if isinstance(row.get("payload_bytes"), dict) else {},
            "serialization_ms": row.get("serialization_ms") if isinstance(row.get("serialization_ms"), dict) else {},
            "allocation_bytes": row.get("allocation_bytes") if isinstance(row.get("allocation_bytes"), dict) else {},
            "payload_budget_bytes": int(row.get("payload_budget_bytes") or 0),
            "allocation_budget_bytes": int(row.get("allocation_budget_bytes") or 0),
            "serialization_budget_ms": float(row.get("serialization_budget_ms") or 0.0),
        }
    process_rows: dict[str, Any] = {}
    for workload, row in (process_runtime.get("workloads") or {}).items() if isinstance(process_runtime.get("workloads"), dict) else []:
        if not isinstance(row, dict):
            continue
        process_rows[str(workload)[:80]] = {
            "runs": int(row.get("runs") or 0),
            "failed": int(row.get("failed") or 0),
            "timed_out": int(row.get("timed_out") or 0),
            "capacity_deferred": int(row.get("capacity_deferred") or 0),
            "cleanup_degraded": int(row.get("cleanup_degraded") or 0),
            "output_truncated": int(row.get("output_truncated") or 0),
            "active": int(row.get("active") or 0),
        }
    return {
        "captured_at": utc_now(),
        "http": http,
        "scheduler": {
            "status": scheduler.get("status"),
            "queued_domains": int(scheduler.get("queued_domains") or 0),
            "active_domains": int(scheduler.get("active_domains") or 0),
            "active_io": int(scheduler.get("active_io") or 0),
            "active_cpu": int(scheduler.get("active_cpu") or 0),
            "execution_owner": scheduler.get("projection_execution_owner"),
            "is_execution_owner": scheduler.get("is_execution_owner"),
        },
        "adaptive": {
            "profile": adaptive.get("profile"),
            "admitted": int(adaptive.get("admitted") or 0),
            "deferred": int(adaptive.get("deferred") or 0),
            "rejected": int(adaptive.get("rejected") or 0),
            "event_payloads": adaptive.get("event_payloads") if isinstance(adaptive.get("event_payloads"), dict) else {},
            "domains": domain_rows,
        },
        "process_runtime": {
            "max_concurrent": process_runtime.get("max_concurrent"),
            "security_max_concurrent": process_runtime.get("security_max_concurrent"),
            "subprocess_count": int(process_runtime.get("subprocess_count") or 0),
            "subprocess_limit": int(process_runtime.get("subprocess_limit") or 0),
            "memory_rss_bytes": process_runtime.get("memory_rss_bytes"),
            "memory_peak_rss_bytes": process_runtime.get("memory_peak_rss_bytes"),
            "memory_metric_source": process_runtime.get("memory_metric_source"),
            "workloads": process_rows,
        },
        "event_loop": {
            "latest_lag_ms": float(event_loop.get("latest_lag_ms") or 0.0),
            "recent_max_lag_ms": float(event_loop.get("recent_max_lag_ms") or 0.0),
            "monitor_running": bool(event_loop.get("monitor_running")),
        },
        "hot_path": {
            "job_count": int(hot_path.get("job_count") or 0),
            "top_cpu_jobs": (hot_path.get("top_cpu_jobs") or [])[:10] if isinstance(hot_path.get("top_cpu_jobs"), list) else [],
        },
        "sanitized": True,
    }


def evaluate(samples: list[dict[str, Any]], args: argparse.Namespace) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []
    warnings: list[str] = []
    if len(samples) < args.minimum_samples:
        failures.append("insufficient_samples")
        checks.append({"check": "sample_count", "status": "failed", "observed": len(samples), "required": args.minimum_samples})
        return checks, failures, warnings
    http_failures = sum(1 for sample in samples if not sample.get("http", {}).get("ok"))
    checks.append({"check": "diagnostics_http", "status": "passed" if http_failures == 0 else "failed", "failures": http_failures})
    if http_failures:
        failures.append("diagnostics_http_failures")

    api_latency = distribution(
        float(sample.get("http", {}).get("duration_ms") or 0.0)
        for sample in samples if sample.get("http", {}).get("ok")
    )
    api_status = (
        "unavailable" if not api_latency["count"]
        else "failed" if float(api_latency["p99"] or 0.0) > args.api_p99_budget_ms
        else "warning" if float(api_latency["p95"] or 0.0) > args.api_p95_budget_ms
        else "passed"
    )
    checks.append({"check": "diagnostics_api_latency_ms", "status": api_status,
                   "p95_budget": args.api_p95_budget_ms, "p99_budget": args.api_p99_budget_ms, **api_latency})
    if api_status == "failed":
        failures.append("diagnostics_api_latency_p99")
    elif api_status in {"warning", "unavailable"}:
        warnings.append(f"diagnostics_api_latency_{api_status}")

    event_loop_lag = distribution(
        float(sample.get("event_loop", {}).get("latest_lag_ms") or 0.0) for sample in samples
    )
    loop_status = (
        "failed" if float(event_loop_lag["p99"] or 0.0) > args.event_loop_p99_budget_ms
        else "warning" if float(event_loop_lag["p95"] or 0.0) > args.event_loop_p95_budget_ms
        else "passed"
    )
    checks.append({"check": "event_loop_lag_ms", "status": loop_status,
                   "p95_budget": args.event_loop_p95_budget_ms,
                   "p99_budget": args.event_loop_p99_budget_ms, **event_loop_lag})
    if loop_status == "failed":
        failures.append("event_loop_lag_p99")
    elif loop_status == "warning":
        warnings.append("event_loop_lag_p95")

    rss_values = [
        float(sample.get("process_runtime", {}).get("memory_rss_bytes"))
        for sample in samples
        if isinstance(sample.get("process_runtime", {}).get("memory_rss_bytes"), (int, float))
    ]
    rss_summary = distribution(rss_values)
    rss_growth = max(0.0, (rss_values[-1] - rss_values[0])) if len(rss_values) >= 2 else None
    rss_status = (
        "unsupported" if not rss_values
        else "failed" if (float(rss_summary["max"] or 0.0) > args.peak_rss_budget_bytes
                          or float(rss_growth or 0.0) > args.rss_growth_budget_bytes)
        else "passed"
    )
    checks.append({"check": "rss_memory_bytes", "status": rss_status,
                   "growth_bytes": round(rss_growth, 3) if rss_growth is not None else None,
                   "growth_budget_bytes": args.rss_growth_budget_bytes,
                   "peak_budget_bytes": args.peak_rss_budget_bytes, **rss_summary})
    if rss_status == "failed":
        failures.append("rss_memory_budget")
    elif rss_status == "unsupported":
        warnings.append("rss_memory_unsupported")

    queued = [float(sample["scheduler"].get("queued_domains") or 0) for sample in samples]
    queue_summary = distribution(queued)
    queue_failed = bool(queue_summary["p99"] is not None and float(queue_summary["p99"]) > args.queue_depth_budget)
    checks.append({"check": "scheduler_queue_depth", "status": "failed" if queue_failed else "passed", "budget": args.queue_depth_budget, **queue_summary})
    if queue_failed:
        failures.append("scheduler_queue_depth")

    cpu_p99: list[float] = []
    wall_p99: list[float] = []
    queue_wait_p99: list[float] = []
    exhausted_observations = 0
    payload_violations = 0
    allocation_violations = 0
    serialization_violations = 0
    critical_load_observations = 0
    for sample in samples:
        for row in sample.get("adaptive", {}).get("domains", {}).values():
            if row.get("cpu_budget_exhausted"):
                exhausted_observations += 1
            if row.get("load_state") == "critical":
                critical_load_observations += 1
            if isinstance(row.get("cpu_ms"), dict) and row["cpu_ms"].get("p99") is not None:
                cpu_p99.append(float(row["cpu_ms"]["p99"]))
            if isinstance(row.get("wall_ms"), dict) and row["wall_ms"].get("p99") is not None:
                wall_p99.append(float(row["wall_ms"]["p99"]))
            if isinstance(row.get("queue_wait_ms"), dict) and row["queue_wait_ms"].get("p99") is not None:
                queue_wait_p99.append(float(row["queue_wait_ms"]["p99"]))
            payload_max = float((row.get("payload_bytes") or {}).get("max") or 0.0)
            allocation_max = float((row.get("allocation_bytes") or {}).get("max") or 0.0)
            serialization_max = float((row.get("serialization_ms") or {}).get("max") or 0.0)
            if row.get("payload_budget_bytes") and payload_max > float(row["payload_budget_bytes"]):
                payload_violations += 1
            if row.get("allocation_budget_bytes") and allocation_max > float(row["allocation_budget_bytes"]):
                allocation_violations += 1
            if row.get("serialization_budget_ms") and serialization_max > float(row["serialization_budget_ms"]):
                serialization_violations += 1

    for name, values, budget in (
        ("projection_cpu_p99_ms", cpu_p99, args.cpu_p99_budget_ms),
        ("projection_wall_p99_ms", wall_p99, args.wall_p99_budget_ms),
        ("projection_queue_wait_p99_ms", queue_wait_p99, args.queue_wait_p99_budget_ms),
    ):
        observed = max(values) if values else None
        status = "unavailable" if observed is None else "failed" if observed > budget else "passed"
        checks.append({"check": name, "status": status, "observed": round(observed, 3) if observed is not None else None, "budget": budget, "sampled_domains": len(values)})
        if status == "failed":
            failures.append(name)
        elif status == "unavailable":
            warnings.append(f"{name}_unavailable")

    for name, count in (
        ("payload_budget_violations", payload_violations),
        ("allocation_budget_violations", allocation_violations),
        ("serialization_budget_violations", serialization_violations),
    ):
        checks.append({"check": name, "status": "failed" if count else "passed", "count": count})
        if count:
            failures.append(name)

    # Transient budget deferral is allowed; sustained exhaustion is not.
    exhaustion_ratio = exhausted_observations / max(1, len(samples))
    checks.append({
        "check": "sustained_cpu_budget_exhaustion",
        "status": "failed" if exhaustion_ratio > args.max_exhaustion_ratio else "passed",
        "observation_ratio": round(exhaustion_ratio, 4),
        "budget_ratio": args.max_exhaustion_ratio,
    })
    if exhaustion_ratio > args.max_exhaustion_ratio:
        failures.append("sustained_cpu_budget_exhaustion")

    subprocess_saturation = max(
        (int(sample.get("process_runtime", {}).get("subprocess_count") or 0)
         - int(sample.get("process_runtime", {}).get("subprocess_limit") or 0)
         for sample in samples),
        default=0,
    )
    checks.append({"check": "subprocess_limit",
                   "status": "failed" if subprocess_saturation > 0 else "passed",
                   "maximum_over_limit": max(0, subprocess_saturation)})
    if subprocess_saturation > 0:
        failures.append("subprocess_limit_exceeded")

    cleanup_degraded = 0
    for sample in samples:
        cleanup_degraded = max(
            cleanup_degraded,
            max((int(row.get("cleanup_degraded") or 0) for row in sample.get("process_runtime", {}).get("workloads", {}).values()), default=0),
        )
    checks.append({"check": "process_cleanup", "status": "failed" if cleanup_degraded else "passed", "cleanup_degraded": cleanup_degraded})
    if cleanup_degraded:
        failures.append("process_cleanup_degraded")

    event_oversize = max((int(sample.get("adaptive", {}).get("event_payloads", {}).get("oversize_rejections") or 0) for sample in samples), default=0)
    checks.append({"check": "event_payload_budget", "status": "failed" if event_oversize else "passed", "oversize_rejections": event_oversize})
    if event_oversize:
        failures.append("event_payload_oversize_rejections")

    if critical_load_observations:
        warnings.append("critical_load_observed")
    return checks, failures, warnings


def write_result(gate_dir: Path, payload: dict[str, Any]) -> None:
    payload.setdefault("schema_version", 1)
    payload.setdefault("phase5_gate", True)
    payload.setdefault("framework_validation", False)
    payload.setdefault("resume_safe", True)
    payload.setdefault("retryable", True)
    payload.setdefault("sanitized", True)
    payload.setdefault("completed_at", utc_now())
    if payload.get("status") == "failed" and not payload.get("failure_reason"):
        payload["failure_reason"] = "Adaptive runtime acceptance failed."
    atomic_json(gate_dir / "result.json", payload)


def handle_stop(_signum: int, _frame: Any) -> None:
    global _STOP
    _STOP = True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--gate-id", required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--duration-seconds", type=int, default=900)
    parser.add_argument("--sample-interval-seconds", type=float, default=15.0)
    parser.add_argument("--http-timeout", type=float, default=5.0)
    parser.add_argument("--minimum-samples", type=int, default=5)
    parser.add_argument("--queue-depth-budget", type=float, default=12.0)
    parser.add_argument("--cpu-p99-budget-ms", type=float, default=750.0)
    parser.add_argument("--wall-p99-budget-ms", type=float, default=8_000.0)
    parser.add_argument("--queue-wait-p99-budget-ms", type=float, default=20_000.0)
    parser.add_argument("--max-exhaustion-ratio", type=float, default=0.5)
    parser.add_argument("--api-p95-budget-ms", type=float, default=750.0)
    parser.add_argument("--api-p99-budget-ms", type=float, default=2_000.0)
    parser.add_argument("--event-loop-p95-budget-ms", type=float, default=150.0)
    parser.add_argument("--event-loop-p99-budget-ms", type=float, default=400.0)
    parser.add_argument("--rss-growth-budget-bytes", type=float, default=64 * 1024 * 1024)
    parser.add_argument("--peak-rss-budget-bytes", type=float, default=768 * 1024 * 1024)
    args = parser.parse_args(argv)

    gate_dir = Path(args.run_dir).resolve() / "gates" / args.gate_id
    gate_dir.mkdir(parents=True, exist_ok=True)
    samples_path = gate_dir / "samples.jsonl"
    state_path = gate_dir / "state.json"
    started_at = utc_now()
    started = time.monotonic()
    samples: list[dict[str, Any]] = []
    signal.signal(signal.SIGINT, handle_stop)
    signal.signal(signal.SIGTERM, handle_stop)
    try:
        duration = max(1, int(args.duration_seconds))
        interval = max(0.5, float(args.sample_interval_seconds))
        deadline = started + duration
        while not _STOP and time.monotonic() < deadline:
            payload, http = fetch_json(args.base_url, "/api/lite/diagnostics/runtime", timeout=args.http_timeout)
            sample = safe_sample(payload or {}, http)
            samples.append(sample)
            append_jsonl(samples_path, sample)
            atomic_json(state_path, {
                "run_id": args.run_id,
                "gate_id": args.gate_id,
                "status": "running",
                "started_at": started_at,
                "updated_at": utc_now(),
                "sample_count": len(samples),
                "sanitized": True,
            })
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(interval, remaining))

        checks, failures, warnings = evaluate(samples, args)
        if _STOP:
            failures.append("interrupted")
        status = "failed" if failures else "passed"
        result = {
            "run_id": args.run_id,
            "gate_id": args.gate_id,
            "gate": args.gate_id,
            "status": status,
            "started_at": started_at,
            "duration_seconds": round(max(0.0, time.monotonic() - started), 3),
            "sample_count": len(samples),
            "checks": checks,
            "warnings": sorted(set(warnings)),
            "failure_codes": sorted(set(failures)),
            "failure_reason": ", ".join(sorted(set(failures))) if failures else "",
            "evidence": [f"gates/{args.gate_id}/samples.jsonl", f"gates/{args.gate_id}/state.json"],
        }
        write_result(gate_dir, result)
        atomic_json(state_path, {
            "run_id": args.run_id,
            "gate_id": args.gate_id,
            "status": status,
            "started_at": started_at,
            "completed_at": utc_now(),
            "sample_count": len(samples),
            "failure_codes": sorted(set(failures)),
            "sanitized": True,
        })
        return 0 if status == "passed" else 2
    except BaseException as exc:
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            failure = "interrupted"
        else:
            failure = type(exc).__name__
        write_result(gate_dir, {
            "run_id": args.run_id,
            "gate_id": args.gate_id,
            "gate": args.gate_id,
            "status": "failed",
            "started_at": started_at,
            "duration_seconds": round(max(0.0, time.monotonic() - started), 3),
            "sample_count": len(samples),
            "failure_codes": [failure],
            "failure_reason": failure,
            "failed_stage": "sampling",
        })
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
