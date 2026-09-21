#!/usr/bin/env python3
"""Sanitized PM2 Runtime Contract and stable-convergence evidence for Lite.

This module is intentionally read/observe oriented.  It never bootstraps,
installs, or mutates PM2 process definitions.  The runtime reconciler remains
the owner of desired-state repair while this module turns already-available PM2
and local readiness facts into bounded, schema-versioned evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
import time
from typing import Any, Iterable, Mapping
import urllib.request

try:
    from pocketlab_runtime_registry import (
        LEGACY_LITE_SERVICES,
        PHOTOPRISM_PROCESS,
        ServiceSpec,
        managed_service_specs,
        policy_for,
        policy_match,
    )
except ModuleNotFoundError:  # Package import from FastAPI/tests.
    from .pocketlab_runtime_registry import (
        LEGACY_LITE_SERVICES,
        PHOTOPRISM_PROCESS,
        ServiceSpec,
        managed_service_specs,
        policy_for,
        policy_match,
    )

SCHEMA_VERSION = 1
SCHEMA_ID = "pocketlab.pm2-runtime-contract/v1"
DEFAULT_RESTART_WINDOW_SECONDS = 1800
DEFAULT_STABLE_OBSERVATIONS = 2
DEFAULT_STABLE_OBSERVATION_SECONDS = 15
DEFAULT_LOG_CEILING_BYTES = 64 * 1024 * 1024
DEFAULT_LOG_FILE_CEILING_BYTES = 8 * 1024 * 1024
DEFAULT_LOG_MAX_AGE_SECONDS = 7 * 24 * 60 * 60
DEFAULT_LOG_CLEANUP_INTERVAL_SECONDS = 15 * 60
_MAX_RESTART_EVENTS = 16


@dataclass(frozen=True)
class LogPolicy:
    ceiling_bytes: int = DEFAULT_LOG_CEILING_BYTES
    file_ceiling_bytes: int = DEFAULT_LOG_FILE_CEILING_BYTES
    max_age_seconds: int = DEFAULT_LOG_MAX_AGE_SECONDS
    cleanup_interval_seconds: int = DEFAULT_LOG_CLEANUP_INTERVAL_SECONDS

    @classmethod
    def from_env(cls) -> "LogPolicy":
        def bounded(name: str, default: int, low: int, high: int) -> int:
            try:
                return max(low, min(high, int(os.environ.get(name, default))))
            except (TypeError, ValueError):
                return default

        return cls(
            ceiling_bytes=bounded(
                "POCKETLAB_PM2_LOG_CEILING_BYTES",
                DEFAULT_LOG_CEILING_BYTES,
                8 * 1024 * 1024,
                512 * 1024 * 1024,
            ),
            file_ceiling_bytes=bounded(
                "POCKETLAB_PM2_LOG_FILE_CEILING_BYTES",
                DEFAULT_LOG_FILE_CEILING_BYTES,
                1 * 1024 * 1024,
                64 * 1024 * 1024,
            ),
            max_age_seconds=bounded(
                "POCKETLAB_PM2_LOG_MAX_AGE_SECONDS",
                DEFAULT_LOG_MAX_AGE_SECONDS,
                24 * 60 * 60,
                30 * 24 * 60 * 60,
            ),
            cleanup_interval_seconds=bounded(
                "POCKETLAB_PM2_LOG_CLEANUP_INTERVAL_SECONDS",
                DEFAULT_LOG_CLEANUP_INTERVAL_SECONDS,
                300,
                24 * 60 * 60,
            ),
        )


def now_iso(now: float | None = None) -> str:
    return datetime.fromtimestamp(time.time() if now is None else now, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _atomic_write(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    tmp.replace(path)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_version(value: Any) -> str:
    text = " ".join(str(value or "").strip().split())
    if not text or text.lower() in {"n/a", "na", "unknown", "none", "null"}:
        return "unavailable"
    return text[:120]


def _process_map(processes: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("name") or "").strip(): item
        for item in processes
        if isinstance(item, dict) and str(item.get("name") or "").strip()
    }


def _pm2_env(item: Mapping[str, Any]) -> dict[str, Any]:
    value = item.get("pm2_env")
    return value if isinstance(value, dict) else {}


def _status(item: Mapping[str, Any] | None) -> str:
    if not isinstance(item, Mapping):
        return "missing"
    env = _pm2_env(item)
    return str(env.get("status") or item.get("status") or "unknown").strip().lower()


def _uptime_seconds(item: Mapping[str, Any] | None, now: float) -> int | None:
    if not isinstance(item, Mapping):
        return None
    started_ms = _int(_pm2_env(item).get("pm_uptime"), 0)
    if started_ms <= 0:
        return None
    return max(0, int(now - (started_ms / 1000.0)))


def _timestamp_from_ms(value: Any) -> str | None:
    milliseconds = _int(value, 0)
    if milliseconds <= 0:
        return None
    return now_iso(milliseconds / 1000.0)


def _memory_mb(item: Mapping[str, Any] | None) -> float | None:
    if not isinstance(item, Mapping):
        return None
    monit = item.get("monit") if isinstance(item.get("monit"), dict) else {}
    value = monit.get("memory")
    try:
        return round(max(0.0, float(value)) / (1024.0 * 1024.0), 1)
    except (TypeError, ValueError):
        return None


def _tcp_ready(port: int, timeout: float = 0.6) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout):
            return True
    except OSError:
        return False


def _http_ready(url: str, timeout: float = 1.0) -> bool:
    try:
        request = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310 - fixed loopback URLs only
            return 200 <= int(response.status) < 500
    except Exception:
        return False


def local_health_snapshot() -> dict[str, str]:
    """Cheap semantic readiness probes.  No remote-network probe is performed."""

    return {
        "nats": "ready" if _tcp_ready(4222) else "not_ready",
        "opa": "ready" if _http_ready("http://127.0.0.1:8181/health") else "not_ready",
        "api": (
            "ready"
            if _http_ready("http://127.0.0.1:8080/health")
            and _http_ready("http://127.0.0.1:8080/ready")
            else "not_ready"
        ),
        "caddy": "ready" if _tcp_ready(8443) else "not_ready",
        "photoprism_local": (
            "ready"
            if _http_ready("http://127.0.0.1:2342/apps/photoprism/api/v1/status")
            or _http_ready("http://127.0.0.1:2342/apps/photoprism/")
            else "not_ready"
        ),
        "photoprism_route": (
            "ready"
            if _http_ready("http://127.0.0.1:8443/apps/photoprism/")
            else "not_ready"
        ),
    }


def _core_restart_state(state_root: Path) -> dict[str, Any]:
    state = _read_json(state_root / "core-supervisor" / "state.json")
    policy = state.get("restart_policy") if isinstance(state.get("restart_policy"), dict) else {}
    services = policy.get("services") if isinstance(policy.get("services"), dict) else {}
    return {
        "window_seconds": max(60, _int(policy.get("window_seconds"), DEFAULT_RESTART_WINDOW_SECONDS)),
        "max_restarts_per_window": max(1, _int(policy.get("max_restarts_per_window"), 3)),
        "services": services,
    }


def _update_restart_ledger(
    state_root: Path,
    process_items: Mapping[str, dict[str, Any]],
    specs: Iterable[ServiceSpec],
    *,
    now: float,
) -> dict[str, Any]:
    path = state_root / "runtime" / "restart-ledger.json"
    previous = _read_json(path)
    previous_services = previous.get("services") if isinstance(previous.get("services"), dict) else {}
    window_seconds = max(
        300,
        _int(os.environ.get("POCKETLAB_RUNTIME_RESTART_WINDOW_SECONDS"), DEFAULT_RESTART_WINDOW_SECONDS),
    )
    lower = now - window_seconds
    services: dict[str, Any] = {}

    for spec in specs:
        item = process_items.get(spec.name)
        env = _pm2_env(item or {})
        current_pm2_restarts = max(0, _int(env.get("restart_time"), 0))
        current_started_ms = max(0, _int(env.get("pm_uptime"), 0))
        old = previous_services.get(spec.name) if isinstance(previous_services.get(spec.name), dict) else {}
        old_pm2_restarts = max(0, _int(old.get("pm2_restart_time"), 0))
        old_started_ms = max(0, _int(old.get("pm_uptime_ms"), 0))
        generation = max(0, _int(old.get("restart_generation"), 0))
        events = [
            float(value)
            for value in (old.get("recent_restart_epochs") or [])
            if isinstance(value, (int, float)) and float(value) >= lower
        ]

        delta = 0
        if current_pm2_restarts > old_pm2_restarts:
            delta = current_pm2_restarts - old_pm2_restarts
        elif (
            old_started_ms > 0
            and current_started_ms > old_started_ms
            and current_pm2_restarts <= old_pm2_restarts
        ):
            # PM2 daemon resurrection can reset its local restart counter.  A new
            # process start still advances the Pocket Lab generation once.
            delta = 1
        if delta > 0:
            generation += delta
            events.extend([now] * min(delta, 4))
        events = sorted(events)[-_MAX_RESTART_EVENTS:]

        services[spec.name] = {
            "restart_generation": generation,
            "pm2_restart_time": current_pm2_restarts,
            "pm_uptime_ms": current_started_ms,
            "recent_restart_epochs": events,
            "recent_restarts": len(events),
            "last_restart_at": now_iso(events[-1]) if events else (
                _timestamp_from_ms(current_started_ms) if generation > 0 else None
            ),
        }

    payload = {
        "schema_version": 1,
        "observed_at": now_iso(now),
        "restart_window_seconds": window_seconds,
        "services": services,
        "sanitized": True,
    }
    _atomic_write(path, payload)
    return payload


def _semantic_health(
    spec: ServiceSpec,
    *,
    status: str,
    dependency_states: Mapping[str, str],
    health: Mapping[str, str],
) -> str:
    if status != "online":
        return "not_ready"
    if any(value != "ready" for value in dependency_states.values()):
        return "not_ready"
    if spec.name == "pocket-nats":
        return health.get("nats", "unknown")
    if spec.name == "pocket-opa":
        return health.get("opa", "unknown")
    if spec.name == "pocket-api":
        return health.get("api", "unknown")
    if spec.name == "caddy-proxy":
        # Caddy local liveness is deliberately separate from FastAPI upstream
        # health.  The dependency map below carries API readiness independently.
        return health.get("caddy", "unknown")
    if spec.name == PHOTOPRISM_PROCESS:
        if health.get("photoprism_local") == "ready" and health.get("photoprism_route") == "ready":
            return "ready"
        return "not_ready"
    return "ready"


def _build_service_contracts(
    *,
    processes: Iterable[dict[str, Any]],
    specs: tuple[ServiceSpec, ...],
    state_root: Path,
    now: float,
    health: Mapping[str, str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    items = _process_map(processes)
    ledger = _update_restart_ledger(state_root, items, specs, now=now)
    ledger_services = ledger.get("services") if isinstance(ledger.get("services"), dict) else {}
    core_restart = _core_restart_state(state_root)
    core_services = core_restart.get("services") if isinstance(core_restart.get("services"), dict) else {}
    core_limit = max(1, _int(core_restart.get("max_restarts_per_window"), 3))

    contracts: list[dict[str, Any]] = []
    ready_by_name: dict[str, str] = {}
    for spec in specs:
        item = items.get(spec.name)
        status = _status(item)
        env = _pm2_env(item or {})
        policy = policy_for(spec.name)
        matches_policy, mismatch_fields = policy_match(spec.name, env)
        fingerprint = str(env.get("POCKETLAB_PM2_POLICY_FINGERPRINT") or "")
        expected_fingerprint = policy.fingerprint() if policy else ""
        fingerprint_match = bool(expected_fingerprint and fingerprint == expected_fingerprint)
        version = _safe_version(env.get("version"))
        declared_version = _safe_version(env.get("POCKETLAB_SERVICE_VERSION"))
        version_match = version != "unavailable" and version == declared_version
        spec_hash_present = bool(str(env.get("POCKETLAB_PROCESS_SPEC_HASH") or "").strip())
        desired_state_match = bool(version_match and matches_policy and fingerprint_match and spec_hash_present)
        uptime = _uptime_seconds(item, now)
        stable_uptime = bool(
            status == "online"
            and policy is not None
            and uptime is not None
            and uptime >= policy.min_uptime_seconds
        )

        ledger_service = ledger_services.get(spec.name) if isinstance(ledger_services.get(spec.name), dict) else {}
        core_service = core_services.get(spec.name) if isinstance(core_services.get(spec.name), dict) else {}
        restart_generation = max(
            _int(ledger_service.get("restart_generation"), 0),
            _int(core_service.get("restart_generation"), 0),
        )
        recent_restarts = max(
            _int(ledger_service.get("recent_restarts"), 0),
            _int(core_service.get("recent_restart_count"), 0),
        )
        budget_remaining = max(0, core_limit - recent_restarts)
        pm2_unstable_restarts = max(0, _int(env.get("unstable_restarts"), 0))
        pm2_budget_remaining = (
            max(0, policy.max_restarts - pm2_unstable_restarts)
            if policy is not None
            else None
        )
        restart_budget_exhausted = bool(
            budget_remaining <= 0
            or (
                policy is not None
                and status in {"errored", "error", "stopped"}
                and pm2_unstable_restarts >= policy.max_restarts
            )
        )

        memory_mb = _memory_mb(item)
        memory_ceiling_mb = policy.max_memory_restart_mb if policy else None
        memory_within_policy = (
            True
            if memory_ceiling_mb is None or memory_mb is None
            else memory_mb <= float(memory_ceiling_mb)
        )
        dependencies = {
            dependency: ready_by_name.get(dependency, "unknown")
            for dependency in spec.dependencies
        }
        semantic_health = _semantic_health(
            spec,
            status=status,
            dependency_states=dependencies,
            health=health,
        )
        ready_by_name[spec.name] = semantic_health

        reasons: list[str] = []
        if status != "online":
            reasons.append("process_not_online")
        if not version_match:
            reasons.append("version_drift")
        if not matches_policy or not fingerprint_match:
            reasons.append("pm2_policy_drift")
        if not stable_uptime:
            reasons.append("minimum_stable_uptime_not_met")
        if restart_budget_exhausted:
            reasons.append("restart_budget_exhausted")
        if not memory_within_policy:
            reasons.append("memory_policy_exceeded")
        if semantic_health != "ready":
            reasons.append("semantic_health_not_ready")
        if any(value != "ready" for value in dependencies.values()):
            reasons.append("dependency_not_ready")

        stable = not reasons
        contracts.append({
            "process": spec.name,
            "role": spec.role,
            "required": spec.required,
            "version": version,
            "declared_version": declared_version,
            "state": status,
            "stable": stable,
            "uptime_seconds": uptime,
            "min_uptime_seconds": policy.min_uptime_seconds if policy else None,
            "restart_generation": restart_generation,
            "recent_restarts": recent_restarts,
            "restart_window_seconds": ledger.get("restart_window_seconds"),
            "restart_budget_remaining": budget_remaining,
            "pm2_restart_budget_remaining": pm2_budget_remaining,
            "last_restart_at": ledger_service.get("last_restart_at"),
            "recovered_at": (
                ledger_service.get("last_restart_at")
                if stable and restart_generation > 0
                else None
            ),
            "memory_mb": memory_mb,
            "memory_ceiling_mb": memory_ceiling_mb,
            "memory_within_policy": memory_within_policy,
            "desired_state_match": desired_state_match,
            "pm2_policy_match": bool(matches_policy and fingerprint_match),
            "pm2_policy": policy.canonical() if policy else None,
            "health": semantic_health,
            "dependencies": dependencies,
            "reason_codes": sorted(set(reasons)),
        })
    return contracts, ledger


def _candidate_state(
    services: Iterable[dict[str, Any]],
    *,
    legacy_present: list[str],
    repairing: bool,
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    services_list = list(services)
    required = [item for item in services_list if item.get("required") is True]
    if legacy_present:
        reasons.append("forbidden_legacy_service_present")
    if any(item.get("reason_codes") and "pm2_policy_drift" in item.get("reason_codes", []) for item in required):
        reasons.append("pm2_policy_drift")
    if any("restart_budget_exhausted" in item.get("reason_codes", []) for item in required):
        reasons.append("restart_budget_exhausted")
    if repairing:
        reasons.append("repair_in_progress")
    for item in required:
        if not item.get("stable"):
            reasons.extend(
                f"{item.get('process')}:{reason}"
                for reason in item.get("reason_codes", [])
            )
    reasons = sorted(set(reasons))
    if "restart_budget_exhausted" in reasons:
        return "restart_budget_exhausted", reasons
    if "pm2_policy_drift" in reasons:
        return "policy_drift", reasons
    if repairing:
        return "repairing", reasons
    if reasons:
        # A fully correct process can still be waiting only for min uptime.
        only_uptime = all(reason.endswith(":minimum_stable_uptime_not_met") for reason in reasons)
        return ("converging" if only_uptime else "degraded"), reasons
    return "candidate", []


def _stable_convergence(
    state_root: Path,
    services: list[dict[str, Any]],
    *,
    candidate_state: str,
    reason_codes: list[str],
    now: float,
) -> dict[str, Any]:
    path = state_root / "runtime" / "stable-convergence.json"
    previous = _read_json(path)
    required_observations = max(
        2,
        min(5, _int(os.environ.get("POCKETLAB_RUNTIME_STABLE_OBSERVATIONS"), DEFAULT_STABLE_OBSERVATIONS)),
    )
    min_seconds = max(
        5,
        min(300, _int(os.environ.get("POCKETLAB_RUNTIME_STABLE_OBSERVATION_SECONDS"), DEFAULT_STABLE_OBSERVATION_SECONDS)),
    )
    signature = "|".join(
        f"{item.get('process')}:{item.get('restart_generation')}:{item.get('state')}:{int(bool(item.get('stable')))}"
        for item in services
        if item.get("required") is True
    )
    previous_signature = str(previous.get("restart_signature") or "")
    previous_at = float(previous.get("last_candidate_epoch") or 0.0)
    previous_count = max(0, _int(previous.get("stable_observations"), 0))
    stable_observations = 0
    first_candidate_epoch: float | None = None

    if candidate_state == "candidate":
        if previous_signature == signature and previous_at > 0 and now - previous_at >= min_seconds:
            stable_observations = previous_count + 1
            first_candidate_epoch = float(previous.get("first_candidate_epoch") or previous_at)
        else:
            stable_observations = 1
            first_candidate_epoch = now

    stable = candidate_state == "candidate" and stable_observations >= required_observations
    final_state = "stable" if stable else ("converging" if candidate_state == "candidate" else candidate_state)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "state": final_state,
        "stable": stable,
        "reason_codes": reason_codes,
        "stable_observations": stable_observations,
        "required_stable_observations": required_observations,
        "minimum_observation_seconds": min_seconds,
        "first_candidate_epoch": first_candidate_epoch,
        "last_candidate_epoch": now if candidate_state == "candidate" else None,
        "restart_signature": signature if candidate_state == "candidate" else "",
        "observed_at": now_iso(now),
        "sanitized": True,
    }
    _atomic_write(path, payload)
    return payload


def _resolve_log_dir(pm2_home: Path | None = None) -> Path:
    home = pm2_home or Path(os.environ.get("PM2_HOME") or (Path.home() / ".pm2"))
    root = home.expanduser()
    if root.is_symlink():
        raise ValueError("pm2_home_symlink_rejected")
    logs = root / "logs"
    if logs.is_symlink():
        raise ValueError("pm2_log_dir_symlink_rejected")
    logs.mkdir(parents=True, exist_ok=True)
    resolved_root = root.resolve()
    resolved_logs = logs.resolve()
    if resolved_logs.parent != resolved_root:
        raise ValueError("pm2_log_dir_escape_rejected")
    return resolved_logs


def enforce_log_policy(
    state_root: Path,
    *,
    now: float | None = None,
    pm2_home: Path | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Bound PM2-owned log storage without reading or copying log contents."""

    observed_now = time.time() if now is None else float(now)
    policy = LogPolicy.from_env()
    evidence_path = state_root / "runtime" / "pm2-log-policy.json"
    previous = _read_json(evidence_path)
    previous_epoch = float(previous.get("cleanup_epoch") or 0.0)
    cleanup_due = force or observed_now - previous_epoch >= policy.cleanup_interval_seconds
    logs = _resolve_log_dir(pm2_home)

    files: list[Path] = []
    for path in logs.iterdir():
        try:
            if path.is_symlink() or not path.is_file():
                continue
            if path.parent.resolve() != logs:
                continue
            files.append(path)
        except OSError:
            continue

    removed = 0
    truncated = 0
    if cleanup_due:
        for path in sorted(files, key=lambda item: item.stat().st_mtime if item.exists() else 0):
            try:
                stat = path.stat()
            except OSError:
                continue
            if observed_now - stat.st_mtime > policy.max_age_seconds:
                path.unlink(missing_ok=True)
                removed += 1
                continue
            if stat.st_size > policy.file_ceiling_bytes:
                # copytruncate semantics without copying: preserve the active
                # inode PM2 already owns, discard old contents, and keep writes
                # flowing into the same file.
                with path.open("r+b") as handle:
                    handle.truncate(0)
                    handle.flush()
                    os.fsync(handle.fileno())
                truncated += 1

        files = [
            path for path in logs.iterdir()
            if not path.is_symlink() and path.is_file() and path.parent.resolve() == logs
        ]
        total = sum(path.stat().st_size for path in files)
        if total > policy.ceiling_bytes:
            for path in sorted(files, key=lambda item: item.stat().st_mtime):
                if total <= policy.ceiling_bytes:
                    break
                size = path.stat().st_size
                with path.open("r+b") as handle:
                    handle.truncate(0)
                    handle.flush()
                    os.fsync(handle.fileno())
                total = max(0, total - size)
                truncated += 1

    files = [
        path for path in logs.iterdir()
        if not path.is_symlink() and path.is_file() and path.parent.resolve() == logs
    ]
    total = sum(path.stat().st_size for path in files)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "observed_at": now_iso(observed_now),
        "cleanup_epoch": observed_now if cleanup_due else previous_epoch,
        "cleanup_performed": cleanup_due,
        "pm2_log_bytes": total,
        "pm2_log_ceiling_bytes": policy.ceiling_bytes,
        "pm2_log_file_ceiling_bytes": policy.file_ceiling_bytes,
        "pm2_log_max_age_seconds": policy.max_age_seconds,
        "within_policy": total <= policy.ceiling_bytes,
        "files_observed": len(files),
        "files_removed": removed,
        "files_truncated": truncated,
        "contains_log_contents": False,
        "sanitized": True,
    }
    _atomic_write(evidence_path, payload)
    return payload


def build_runtime_contract(
    *,
    processes: Iterable[dict[str, Any]],
    state_root: Path,
    photoprism_expected: bool,
    repairing: bool = False,
    remote_access: Mapping[str, Any] | None = None,
    now: float | None = None,
    health: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    observed_now = time.time() if now is None else float(now)
    specs = managed_service_specs(include_photoprism=photoprism_expected)
    process_items = _process_map(processes)
    health_snapshot = dict(health or local_health_snapshot())
    services, _ledger = _build_service_contracts(
        processes=process_items.values(),
        specs=specs,
        state_root=state_root,
        now=observed_now,
        health=health_snapshot,
    )
    legacy_present = sorted(name for name in process_items if name in LEGACY_LITE_SERVICES)
    candidate_state, reasons = _candidate_state(
        services,
        legacy_present=legacy_present,
        repairing=repairing,
    )
    convergence = _stable_convergence(
        state_root,
        services,
        candidate_state=candidate_state,
        reason_codes=reasons,
        now=observed_now,
    )
    log_policy = enforce_log_policy(state_root, now=observed_now)
    remote = remote_access if isinstance(remote_access, Mapping) else {}
    payload = {
        "schema": SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "observed_at": now_iso(observed_now),
        "state": convergence["state"],
        "stable": convergence["stable"],
        "reason_codes": convergence["reason_codes"],
        "stable_observations": convergence["stable_observations"],
        "required_stable_observations": convergence["required_stable_observations"],
        "services": services,
        "legacy_lite_services_present": legacy_present,
        "log_policy": {
            "pm2_log_bytes": log_policy["pm2_log_bytes"],
            "pm2_log_ceiling_bytes": log_policy["pm2_log_ceiling_bytes"],
            "within_policy": log_policy["within_policy"],
        },
        "remote_access": {
            "ready": bool(remote.get("ipv4_ready") or remote.get("ready")),
            "state": (
                "ready"
                if remote.get("ipv4_ready") or remote.get("ready")
                else "not_ready"
            ),
        },
        "sanitized": True,
    }
    _atomic_write(state_root / "runtime" / "pm2-runtime-contract.json", payload)
    return payload


def public_projection(contract: Mapping[str, Any]) -> dict[str, Any]:
    """Return Lite-friendly runtime truth without exposing raw PM2 internals."""

    state = str(contract.get("state") or "unknown")
    if state == "stable":
        summary = "System running normally"
    elif state in {"converging", "repairing"}:
        summary = "Recovery in progress"
    else:
        summary = "Something changed"

    projected_services: list[dict[str, Any]] = []
    for item in contract.get("services") if isinstance(contract.get("services"), list) else []:
        if not isinstance(item, dict):
            continue
        generation = max(0, _int(item.get("restart_generation"), 0))
        stable = bool(item.get("stable"))
        if stable and generation == 0:
            label = "Running normally"
        elif stable and generation > 0:
            label = "Recovered recently"
        elif str(item.get("state") or "") in {"stopped", "errored", "error", "missing"}:
            label = "Something changed"
        else:
            label = "Repairing"
        projected_services.append({
            "process": item.get("process"),
            "role": item.get("role"),
            "status": label,
            "stable": stable,
            "restart_generation": generation,
            "recent_restarts": max(0, _int(item.get("recent_restarts"), 0)),
            "restart_budget_remaining": max(0, _int(item.get("restart_budget_remaining"), 0)),
            "recovered_at": item.get("recovered_at"),
            "reason_codes": list(item.get("reason_codes") or [])[:8],
        })

    return {
        "schema_version": contract.get("schema_version"),
        "state": state,
        "stable": bool(contract.get("stable")),
        "summary": summary,
        "reason_codes": list(contract.get("reason_codes") or [])[:16],
        "observed_at": contract.get("observed_at"),
        "services": projected_services,
        "remote_access": contract.get("remote_access") if isinstance(contract.get("remote_access"), dict) else {},
        "log_policy": contract.get("log_policy") if isinstance(contract.get("log_policy"), dict) else {},
        "sanitized": True,
    }
