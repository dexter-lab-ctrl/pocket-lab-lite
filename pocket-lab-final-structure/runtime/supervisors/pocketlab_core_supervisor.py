#!/usr/bin/env python3
"""Pocket Lab Lite core service supervisor.

Watches PM2-managed Lite control-plane services and performs small, ordered
self-healing actions when the server-side control plane drifts into a degraded
state.  It is intentionally conservative: it restarts only known PM2 process
names, uses cooldowns to avoid flapping, writes sanitized local evidence, and
never logs or persists secrets.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import signal
import socket
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

SUPERVISOR_VERSION = "1.0.0-lite-core-supervisor"
DEFAULT_INTERVAL_SECONDS = 45
DEFAULT_COOLDOWN_SECONDS = 120
DEFAULT_API_PORT = 8080
DEFAULT_CADDY_PORT = 8443
DEFAULT_NATS_PORT = 4222

_STOP = False

SENSITIVE_KEY_RE = re.compile(
    r"(token|secret|password|passwd|api[_-]?key|private[_-]?key|credential|authorization|cookie)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ServiceSpec:
    name: str
    role: str
    required: bool = True


CORE_SERVICES: tuple[ServiceSpec, ...] = (
    ServiceSpec("pocket-nats", "nats", True),
    ServiceSpec("pocket-api", "api", True),
    ServiceSpec("pocket-worker", "worker", True),
    ServiceSpec("caddy-proxy", "proxy", True),
    ServiceSpec("pocket-telemetry", "telemetry", False),
)

DEPENDENTS_AFTER_NATS = ("pocket-api", "pocket-worker")


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def epoch() -> float:
    return time.time()


def sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: Dict[str, Any] = {}
        for key, item in value.items():
            if SENSITIVE_KEY_RE.search(str(key)):
                sanitized[str(key)] = "***REDACTED***"
            else:
                sanitized[str(key)] = sanitize(item)
        return sanitized
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize(item) for item in value]
    if isinstance(value, str):
        # Avoid leaking user:password@host style URLs if one accidentally reaches evidence.
        return re.sub(r"(nats|http|https)://([^:/@]+):([^@]+)@", r"\1://***REDACTED***:***REDACTED***@", value)
    return value


def run_command(args: List[str], timeout: float = 15.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=False, capture_output=True, text=True, timeout=timeout)


def pm2_available() -> bool:
    try:
        return run_command(["sh", "-lc", "command -v pm2"], timeout=4).returncode == 0
    except Exception:
        return False


def load_pm2_processes() -> List[Dict[str, Any]]:
    try:
        result = run_command(["pm2", "jlist"], timeout=10)
        if result.returncode != 0 or not result.stdout.strip():
            return []
        parsed = json.loads(result.stdout)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []


def process_status(processes: Iterable[Dict[str, Any]], name: str) -> str:
    for process in processes:
        if str(process.get("name") or "") != name:
            continue
        env = process.get("pm2_env") if isinstance(process.get("pm2_env"), dict) else {}
        return str(env.get("status") or process.get("status") or "unknown").lower()
    return "missing"


def is_online(status: str) -> bool:
    return str(status or "").lower() == "online"


def tcp_reachable(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def fetch_json(url: str, timeout: float = 4.0) -> Optional[Dict[str, Any]]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:  # nosec B310 - local-only control-plane probe
            payload = response.read(256 * 1024).decode("utf-8", errors="replace")
        parsed = json.loads(payload)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def nats_api_status_unhealthy(payload: Optional[Dict[str, Any]]) -> bool:
    if not isinstance(payload, dict):
        return True
    if payload.get("connected") is not True:
        return True
    mode = str(payload.get("mode") or "").lower()
    if mode and mode != "nats":
        return True
    fallback = str(payload.get("fallback_reason") or "").strip()
    return bool(fallback)


def status_summary(statuses: Dict[str, str], nats_tcp: bool, api_nats_status: Optional[Dict[str, Any]], caddy_http: bool) -> Dict[str, Any]:
    return {
        "services": statuses,
        "checks": {
            "nats_tcp_reachable": nats_tcp,
            "api_nats_connected": not nats_api_status_unhealthy(api_nats_status),
            "caddy_http_reachable": caddy_http,
        },
        "api_nats_mode": (api_nats_status or {}).get("mode"),
        "api_nats_connected": (api_nats_status or {}).get("connected"),
        "api_nats_fallback_reason": (api_nats_status or {}).get("fallback_reason"),
    }


class LiteCoreSupervisor:
    def __init__(self) -> None:
        self.interval = max(10, int(os.environ.get("POCKETLAB_CORE_SUPERVISOR_INTERVAL_SECONDS", DEFAULT_INTERVAL_SECONDS)))
        self.cooldown = max(30, int(os.environ.get("POCKETLAB_CORE_SUPERVISOR_COOLDOWN_SECONDS", DEFAULT_COOLDOWN_SECONDS)))
        self.api_port = int(os.environ.get("API_PORT", os.environ.get("POCKETLAB_API_PORT", DEFAULT_API_PORT)))
        self.caddy_port = int(os.environ.get("DASH_PORT", os.environ.get("POCKETLAB_DASH_PORT", DEFAULT_CADDY_PORT)))
        self.nats_port = int(os.environ.get("POCKETLAB_NATS_PORT", DEFAULT_NATS_PORT))
        self.state_root = self._state_root()
        self.evidence_dir = self.state_root / "core-supervisor"
        self.state_file = self.evidence_dir / "state.json"
        self.events_file = self.evidence_dir / "events.jsonl"
        self.last_actions: Dict[str, float] = self._load_last_actions()

    def _state_root(self) -> Path:
        configured = os.environ.get("POCKETLAB_STATE_DIR") or os.environ.get("STATE_DIR")
        if configured:
            return Path(configured).expanduser()
        return Path.home() / ".pocket_lab"

    def _load_last_actions(self) -> Dict[str, float]:
        try:
            payload = json.loads(self.state_file.read_text())
            last_actions = payload.get("last_actions") if isinstance(payload, dict) else {}
            if isinstance(last_actions, dict):
                return {str(k): float(v) for k, v in last_actions.items()}
        except Exception:
            pass
        return {}

    def _write_json(self, path: Path, payload: Dict[str, Any]) -> None:
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        safe_payload = sanitize(payload)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(safe_payload, indent=2, sort_keys=True) + "\n")
        tmp.replace(path)

    def _append_event(self, event: Dict[str, Any]) -> None:
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        safe_event = sanitize({"time": now_iso(), "source": "pocketlab-core-supervisor", **event})
        with self.events_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(safe_event, sort_keys=True) + "\n")

    def can_act(self, action: str) -> bool:
        last_at = self.last_actions.get(action, 0.0)
        return (epoch() - last_at) >= self.cooldown

    def mark_action(self, action: str) -> None:
        self.last_actions[action] = epoch()

    def restart_pm2(self, service: str, reason: str) -> Dict[str, Any]:
        action = f"restart:{service}"
        if not self.can_act(action):
            event = {"event": "restart_skipped_cooldown", "service": service, "reason": reason, "cooldown_seconds": self.cooldown}
            self._append_event(event)
            return {**event, "acted": False}
        try:
            result = run_command(["pm2", "restart", service, "--update-env"], timeout=30)
            acted = result.returncode == 0
            self.mark_action(action)
            event = {
                "event": "restart_attempted",
                "service": service,
                "reason": reason,
                "returncode": result.returncode,
                "acted": acted,
            }
            self._append_event(event)
            return event
        except Exception as exc:
            self.mark_action(action)
            event = {"event": "restart_failed", "service": service, "reason": reason, "error": str(exc), "acted": False}
            self._append_event(event)
            return event

    def wait_for_nats_tcp(self, seconds: int = 20) -> bool:
        deadline = epoch() + seconds
        while epoch() < deadline:
            if tcp_reachable("127.0.0.1", self.nats_port):
                return True
            time.sleep(1)
        return tcp_reachable("127.0.0.1", self.nats_port)

    def collect(self) -> Dict[str, Any]:
        processes = load_pm2_processes()
        statuses = {spec.name: process_status(processes, spec.name) for spec in CORE_SERVICES}
        nats_tcp = tcp_reachable("127.0.0.1", self.nats_port)
        api_nats_url = f"http://127.0.0.1:{self.api_port}/api/nats/status"
        caddy_url = f"http://127.0.0.1:{self.caddy_port}/health"
        api_nats = fetch_json(api_nats_url)
        caddy_http = fetch_json(caddy_url) is not None
        return status_summary(statuses, nats_tcp, api_nats, caddy_http)

    def tick(self) -> Dict[str, Any]:
        if not pm2_available():
            payload = {
                "supervisor_status": "degraded",
                "reason": "pm2_missing",
                "checked_at": now_iso(),
                "version": SUPERVISOR_VERSION,
                "last_actions": self.last_actions,
            }
            self._write_json(self.state_file, payload)
            self._append_event({"event": "pm2_missing", "severity": "warning"})
            return payload

        observed = self.collect()
        statuses: Dict[str, str] = observed["services"]
        actions: List[Dict[str, Any]] = []

        nats_unhealthy = not is_online(statuses.get("pocket-nats", "missing")) or not bool(observed["checks"]["nats_tcp_reachable"])
        if nats_unhealthy:
            actions.append(self.restart_pm2("pocket-nats", "nats_unhealthy"))
            if self.wait_for_nats_tcp():
                actions.append(self.restart_pm2("pocket-api", "nats_recovered_refresh_api_client"))
                actions.append(self.restart_pm2("pocket-worker", "nats_recovered_refresh_worker_client"))
        else:
            if not is_online(statuses.get("pocket-api", "missing")):
                actions.append(self.restart_pm2("pocket-api", "api_pm2_not_online"))
            elif observed["checks"].get("api_nats_connected") is not True:
                actions.append(self.restart_pm2("pocket-api", "api_nats_client_unhealthy"))
                actions.append(self.restart_pm2("pocket-worker", "api_nats_client_unhealthy_refresh_worker"))

            if not is_online(statuses.get("pocket-worker", "missing")):
                actions.append(self.restart_pm2("pocket-worker", "worker_pm2_not_online"))

        if not is_online(statuses.get("caddy-proxy", "missing")) or not bool(observed["checks"].get("caddy_http_reachable")):
            actions.append(self.restart_pm2("caddy-proxy", "caddy_unhealthy"))

        if not is_online(statuses.get("pocket-telemetry", "missing")):
            actions.append(self.restart_pm2("pocket-telemetry", "telemetry_pm2_not_online"))

        post = self.collect()
        required_unhealthy = [
            spec.name
            for spec in CORE_SERVICES
            if spec.required and not is_online(post["services"].get(spec.name, "missing"))
        ]
        supervisor_status = "healthy"
        if actions:
            supervisor_status = "repairing"
        if required_unhealthy or post["checks"].get("api_nats_connected") is not True:
            supervisor_status = "degraded" if not actions else "repairing"

        payload = {
            "supervisor": "pocketlab-core-supervisor",
            "version": SUPERVISOR_VERSION,
            "supervisor_status": supervisor_status,
            "checked_at": now_iso(),
            "observed_before": observed,
            "observed_after": post,
            "actions": actions,
            "last_actions": self.last_actions,
            "capabilities": ["core-service-supervision", "nats-client-recovery", "pm2-repair"],
        }
        self._write_json(self.state_file, payload)
        if actions:
            self._append_event({"event": "tick_actions", "status": supervisor_status, "actions": actions})
        return payload

    def run(self) -> None:
        while not _STOP:
            try:
                self.tick()
            except Exception as exc:
                self._append_event({"event": "tick_error", "error": str(exc)})
            time.sleep(self.interval)


def _handle_stop(_signum: int, _frame: Any) -> None:
    global _STOP
    _STOP = True


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Pocket Lab Lite core service supervisor")
    parser.add_argument("--once", action="store_true", help="run one supervisor iteration and exit")
    args = parser.parse_args(argv)

    if os.environ.get("POCKETLAB_CORE_SUPERVISOR_DISABLED") == "1":
        return 0

    signal.signal(signal.SIGTERM, _handle_stop)
    signal.signal(signal.SIGINT, _handle_stop)
    supervisor = LiteCoreSupervisor()
    if args.once:
        payload = supervisor.tick()
        print(json.dumps(sanitize(payload), indent=2, sort_keys=True))
        return 0
    supervisor.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
