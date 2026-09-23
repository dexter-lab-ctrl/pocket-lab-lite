#!/usr/bin/env python3
"""Canonical Pocket Lab Lite runtime desired-state and PM2 policy registry.

This module is the single repository-owned source of truth for Lite PM2 policy.
It contains desired policy only; runtime observations (PID, CPU, current memory,
uptime and restart counters) deliberately do not participate in desired identity.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
import hashlib
import json
import os
import re
import sys
from typing import Any, Mapping, Tuple


@dataclass(frozen=True)
class PM2Policy:
    """Stable PM2 lifecycle policy for one managed process."""

    min_uptime_seconds: int
    max_restarts: int
    kill_timeout_ms: int
    max_memory_restart_mb: int | None = None
    restart_delay_ms: int | None = None
    exp_backoff_restart_delay_ms: int | None = None
    autorestart: bool = True

    def canonical(self) -> dict[str, Any]:
        return {
            "autorestart": self.autorestart,
            "exp_backoff_restart_delay_ms": self.exp_backoff_restart_delay_ms,
            "kill_timeout_ms": self.kill_timeout_ms,
            "max_memory_restart_mb": self.max_memory_restart_mb,
            "max_restarts": self.max_restarts,
            "min_uptime_seconds": self.min_uptime_seconds,
            "restart_delay_ms": self.restart_delay_ms,
        }

    def fingerprint(self) -> str:
        encoded = json.dumps(self.canonical(), sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def ecosystem_fields(self) -> dict[str, Any]:
        fields: dict[str, Any] = {
            "autorestart": self.autorestart,
            "exec_mode": "fork",
            "kill_timeout": self.kill_timeout_ms,
            "max_restarts": self.max_restarts,
            "min_uptime": f"{self.min_uptime_seconds}s",
        }
        if self.max_memory_restart_mb is not None:
            fields["max_memory_restart"] = f"{self.max_memory_restart_mb}M"
        if self.restart_delay_ms is not None:
            fields["restart_delay"] = self.restart_delay_ms
        if self.exp_backoff_restart_delay_ms is not None:
            fields["exp_backoff_restart_delay"] = self.exp_backoff_restart_delay_ms
        return fields


@dataclass(frozen=True)
class ServiceSpec:
    name: str
    role: str
    required: bool = True
    dependencies: Tuple[str, ...] = ()
    pm2: PM2Policy | None = None


# Conservative Android/Termux defaults. Memory ceilings are applied only to
# predictable small processes plus the already-bounded API/worker. NATS and
# PhotoPrism intentionally remain uncapped by default because their legitimate
# working set depends on JetStream/app workload.
PM2_POLICIES: dict[str, PM2Policy] = {
    "pocket-nats": PM2Policy(10, 8, 8_000, None, restart_delay_ms=1_000),
    "pocket-opa": PM2Policy(10, 8, 8_000, 192, restart_delay_ms=1_000),
    "pocket-worker": PM2Policy(20, 6, 15_000, 320, exp_backoff_restart_delay_ms=250),
    "pocket-api": PM2Policy(20, 6, 15_000, 384, exp_backoff_restart_delay_ms=250),
    "pocket-node-agent": PM2Policy(20, 8, 10_000, 192, exp_backoff_restart_delay_ms=500),
    "caddy-proxy": PM2Policy(10, 8, 10_000, 256, restart_delay_ms=1_000),
    "pocket-telemetry": PM2Policy(15, 6, 8_000, 128, exp_backoff_restart_delay_ms=250),
    "pocketlab-core-supervisor": PM2Policy(20, 6, 12_000, 192, exp_backoff_restart_delay_ms=500),
    "pocketlab-runtime-reconciler": PM2Policy(20, 6, 12_000, 192, exp_backoff_restart_delay_ms=500),
    "pocketlab-app-photoprism": PM2Policy(60, 5, 30_000, None, exp_backoff_restart_delay_ms=1_000),
}

CONTROL_PLANE_SERVICES: tuple[ServiceSpec, ...] = (
    ServiceSpec("pocket-nats", "messaging", pm2=PM2_POLICIES["pocket-nats"]),
    ServiceSpec("pocket-opa", "policy", pm2=PM2_POLICIES["pocket-opa"]),
    ServiceSpec("pocket-worker", "execution", dependencies=("pocket-nats", "pocket-opa"), pm2=PM2_POLICIES["pocket-worker"]),
    ServiceSpec("pocket-api", "control-api", dependencies=("pocket-nats", "pocket-opa"), pm2=PM2_POLICIES["pocket-api"]),
    ServiceSpec("pocket-node-agent", "server-host-agent", dependencies=("pocket-nats",), pm2=PM2_POLICIES["pocket-node-agent"]),
    ServiceSpec("caddy-proxy", "same-origin-proxy", dependencies=("pocket-api",), pm2=PM2_POLICIES["caddy-proxy"]),
    ServiceSpec("pocket-telemetry", "host-telemetry", required=False, pm2=PM2_POLICIES["pocket-telemetry"]),
    ServiceSpec("pocketlab-core-supervisor", "core-recovery", pm2=PM2_POLICIES["pocketlab-core-supervisor"]),
)

RECONCILER_PROCESS = "pocketlab-runtime-reconciler"
PHOTOPRISM_PROCESS = "pocketlab-app-photoprism"

RECONCILER_SPEC = ServiceSpec(
    RECONCILER_PROCESS,
    "desired-state-reconciliation",
    pm2=PM2_POLICIES[RECONCILER_PROCESS],
)
PHOTOPRISM_SPEC = ServiceSpec(
    PHOTOPRISM_PROCESS,
    "app-runtime",
    dependencies=("caddy-proxy",),
    pm2=PM2_POLICIES[PHOTOPRISM_PROCESS],
)

LEGACY_LITE_SERVICES = frozenset(
    {
        "vault", "mariadb", "gitea", "gitea-runner", "pocket-gatus", "gatus",
        "prometheus-db", "prometheus", "grafana-ui", "grafana", "loki-kms",
        "loki", "promtail-agent", "promtail",
    }
)

REPAIRABLE_PM2_STATUSES = frozenset({"missing", "stopped", "errored", "error"})

_LEGACY_MEMORY_ENV = {
    "pocket-api": "POCKETLAB_API_MAX_MEMORY_RESTART",
    "pocket-worker": "POCKETLAB_WORKER_MAX_MEMORY_RESTART",
}
_MIN_MEMORY_RESTART_MB = 64
_MAX_MEMORY_RESTART_MB = 1024


def control_plane_names() -> tuple[str, ...]:
    return tuple(spec.name for spec in CONTROL_PLANE_SERVICES)


def managed_service_specs(*, include_photoprism: bool = False) -> tuple[ServiceSpec, ...]:
    values = (*CONTROL_PLANE_SERVICES, RECONCILER_SPEC)
    if include_photoprism:
        values = (*values, PHOTOPRISM_SPEC)
    return values


def is_legacy_lite_service(name: str) -> bool:
    return str(name or "").strip().lower() in LEGACY_LITE_SERVICES


def _service_env_key(name: str, suffix: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_").upper()
    return f"POCKETLAB_PM2_{normalized}_{suffix}"


def _parse_memory_mb(value: Any, default: int | None) -> int | None:
    if value in (None, ""):
        return default
    text = str(value).strip().upper()
    match = re.fullmatch(r"(\d+)([KMG]?)B?", text)
    if not match:
        return default
    try:
        amount = int(match.group(1))
    except (ValueError, OverflowError):
        return default
    unit = match.group(2)
    if unit == "G":
        return amount * 1024
    if unit == "K":
        return max(1, amount // 1024)
    return amount


def _bounded_int(environ: Mapping[str, str], key: str, default: int, low: int, high: int) -> int:
    try:
        return max(low, min(high, int(str(environ.get(key, default)).strip())))
    except (TypeError, ValueError):
        return default


def policy_for(name: str, environ: Mapping[str, str] | None = None) -> PM2Policy | None:
    base = PM2_POLICIES.get(str(name or "").strip())
    if base is None:
        return None
    env = os.environ if environ is None else environ
    min_uptime = _bounded_int(
        env, _service_env_key(name, "MIN_UPTIME_SECONDS"), base.min_uptime_seconds, 5, 600
    )
    max_restarts = _bounded_int(
        env, _service_env_key(name, "MAX_RESTARTS"), base.max_restarts, 1, 25
    )
    kill_timeout = _bounded_int(
        env, _service_env_key(name, "KILL_TIMEOUT_MS"), base.kill_timeout_ms, 1_000, 120_000
    )
    memory_key = _service_env_key(name, "MAX_MEMORY_RESTART")
    legacy_key = _LEGACY_MEMORY_ENV.get(name)
    raw_memory = env.get(memory_key)
    if raw_memory in (None, "") and legacy_key:
        raw_memory = env.get(legacy_key)
    # An uncapped service stays uncapped. In particular, operator environment
    # overrides must not assign guessed ceilings to NATS or PhotoPrism.
    memory = base.max_memory_restart_mb
    if memory is not None and raw_memory not in (None, ""):
        candidate_memory = _parse_memory_mb(raw_memory, None)
        if candidate_memory is not None and _MIN_MEMORY_RESTART_MB <= candidate_memory <= _MAX_MEMORY_RESTART_MB:
            memory = candidate_memory
    return replace(
        base,
        min_uptime_seconds=min_uptime,
        max_restarts=max_restarts,
        kill_timeout_ms=kill_timeout,
        max_memory_restart_mb=memory,
    )


def policy_fingerprint(name: str, environ: Mapping[str, str] | None = None) -> str:
    policy = policy_for(name, environ)
    return policy.fingerprint() if policy else ""


def effective_interpreter(script: str, interpreter: str = "") -> str:
    """Return the interpreter PM2 will use for an ecosystem app."""
    selected = str(interpreter or "").strip()
    if selected:
        return selected
    if os.path.splitext(str(script or "").strip())[1].lower() in {".js", ".cjs", ".mjs"}:
        return "node"
    return "none"


def launch_fingerprint(script: str, interpreter: str = "", cwd: str = "") -> str:
    """Fingerprint the executable and interpreter without persisting their paths."""
    executable = str(script or "").strip()
    working_dir = str(cwd or "").strip()
    if not executable or len(executable) > 4096 or len(working_dir) > 4096:
        return ""
    if not os.path.isabs(executable):
        executable = os.path.abspath(os.path.join(working_dir or os.getcwd(), executable))
    payload = {
        "interpreter": effective_interpreter(executable, interpreter),
        "script": executable,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _memory_bytes(value: Any) -> int | None:
    if value in (None, "", 0, "0"):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    mb = _parse_memory_mb(value, None)
    return None if mb is None else mb * 1024 * 1024


def observed_policy(env: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "autorestart": bool(env.get("autorestart", True)),
        "exp_backoff_restart_delay_ms": _as_int(env.get("exp_backoff_restart_delay")),
        "kill_timeout_ms": _as_int(env.get("kill_timeout")),
        "max_memory_restart_bytes": _memory_bytes(env.get("max_memory_restart")),
        "max_restarts": _as_int(env.get("max_restarts")),
        "min_uptime_ms": _as_int(env.get("min_uptime")),
        "restart_delay_ms": _as_int(env.get("restart_delay")),
    }


def policy_match(name: str, env: Mapping[str, Any], environ: Mapping[str, str] | None = None) -> tuple[bool, tuple[str, ...]]:
    policy = policy_for(name, environ)
    if policy is None:
        return True, ()
    observed = observed_policy(env)
    expected_memory = (
        policy.max_memory_restart_mb * 1024 * 1024
        if policy.max_memory_restart_mb is not None
        else None
    )
    expected = {
        "autorestart": policy.autorestart,
        "exp_backoff_restart_delay_ms": policy.exp_backoff_restart_delay_ms,
        "kill_timeout_ms": policy.kill_timeout_ms,
        "max_memory_restart_bytes": expected_memory,
        "max_restarts": policy.max_restarts,
        "min_uptime_ms": policy.min_uptime_seconds * 1000,
        "restart_delay_ms": policy.restart_delay_ms,
    }
    mismatches: list[str] = []
    for field, expected_value in expected.items():
        observed_value = observed.get(field)
        if expected_value is None:
            if observed_value not in (None, 0):
                mismatches.append(field)
        elif observed_value != expected_value:
            mismatches.append(field)
    return not mismatches, tuple(mismatches)


def ecosystem_config_for(
    name: str,
    script: str,
    *,
    interpreter: str = "",
    cwd: str = "",
    app_args: list[str] | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Build a bounded one-process PM2 ecosystem config.

    Lifecycle options live in ecosystem fields because Termux PM2 releases do
    not consistently accept them as CLI flags. The transient JS wrapper adds
    the invoking environment at load time so credentials are not written to
    the config artifact.
    """
    process_name = str(name or "").strip()
    executable = str(script or "").strip()
    interpreter = str(interpreter or "").strip()
    cwd = str(cwd or "").strip()
    if not process_name or len(process_name) > 120:
        raise ValueError("invalid PM2 process name")
    if not executable or len(executable) > 4096:
        raise ValueError("invalid PM2 process script")
    if len(interpreter) > 256 or len(cwd) > 4096:
        raise ValueError("PM2 launch field exceeds its bound")
    if cwd and not os.path.isabs(cwd):
        raise ValueError("PM2 process cwd must be absolute")
    arguments = [] if app_args is None else app_args
    if (
        not isinstance(arguments, list)
        or len(arguments) > 128
        or any(not isinstance(value, str) or len(value) > 8192 for value in arguments)
        or sum(len(value) for value in arguments) > 65536
    ):
        raise ValueError("PM2 app arguments are invalid or exceed their bound")

    app: dict[str, Any] = {
        "name": process_name,
        "script": executable,
        "exec_mode": "fork",
    }
    policy = policy_for(process_name, environ)
    if policy is not None:
        app.update(policy.ecosystem_fields())
    if interpreter:
        app["interpreter"] = interpreter
    elif os.path.splitext(executable)[1].lower() not in {".js", ".cjs", ".mjs"}:
        # Bare Termux commands (NATS, OPA, Caddy, bash) are executables, not
        # JavaScript entry points. PM2's ecosystem default is Node, so mark
        # these explicitly as binaries when no interpreter was requested.
        app["interpreter"] = "none"
    if cwd:
        app["cwd"] = cwd
    if arguments:
        app["args"] = arguments
    return {"apps": [app]}


def _main() -> int:
    parser = argparse.ArgumentParser(description="Pocket Lab Lite PM2 policy registry")
    parser.add_argument("--policy-json", metavar="PROCESS")
    parser.add_argument("--policy-fingerprint", metavar="PROCESS")
    parser.add_argument("--launch-fingerprint", action="store_true")
    parser.add_argument("--ecosystem-js", metavar="PROCESS")
    parser.add_argument("--script")
    parser.add_argument("--interpreter", default="")
    parser.add_argument("--cwd", default="")
    parser.add_argument("--app-args-json", default="[]")
    parser.add_argument("--all-json", action="store_true")
    args = parser.parse_args()

    if args.policy_json:
        policy = policy_for(args.policy_json)
        if policy is None:
            return 3
        print(json.dumps(policy.canonical(), sort_keys=True, separators=(",", ":")))
        return 0
    if args.policy_fingerprint:
        value = policy_fingerprint(args.policy_fingerprint)
        if not value:
            return 3
        print(value)
        return 0
    if args.launch_fingerprint:
        value = launch_fingerprint(args.script or "", args.interpreter, args.cwd)
        if not value:
            return 2
        print(value)
        return 0
    if args.ecosystem_js:
        try:
            app_args = json.loads(args.app_args_json)
            payload = ecosystem_config_for(
                args.ecosystem_js,
                args.script or "",
                interpreter=args.interpreter,
                cwd=args.cwd,
                app_args=app_args,
            )
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            print(f"invalid PM2 ecosystem request: {error}", file=sys.stderr)
            return 2
        app = json.dumps(payload["apps"][0], sort_keys=True, separators=(",", ":"))
        print(f"const app = {app};")
        print("app.env = process.env;")
        print("module.exports = { apps: [app] };")
        return 0
    if args.all_json:
        payload = {
            name: policy_for(name).canonical()
            for name in sorted(PM2_POLICIES)
            if policy_for(name) is not None
        }
        print(json.dumps(payload, sort_keys=True, separators=(",", ":")))
        return 0
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(_main())
