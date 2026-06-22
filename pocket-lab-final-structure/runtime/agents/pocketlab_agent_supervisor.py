#!/usr/bin/env python3
"""Pocket Lab Lite local agent supervisor.

Runs on a joined Lite device next to the device agent.  The supervisor is
intentionally small: it keeps the local PM2-managed device agent alive, writes
safe local status, and publishes sanitized supervisor evidence when NATS is
reachable.  It never logs or publishes raw invite tokens, NATS passwords, or API
secrets.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import shlex
import signal
import socket
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlparse

try:  # Optional on partially bootstrapped devices; local supervision still works.
    import nats  # type: ignore
except Exception:  # pragma: no cover - optional dependency fallback
    nats = None  # type: ignore

SUPERVISOR_VERSION = "1.0.0-lite-agent-supervisor"
DEFAULT_INTERVAL_SECONDS = 20
DEFAULT_NATS_TIMEOUT_SECONDS = 4

_STOP = False


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _normalize_node_id(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9_.-]+", "-", str(value or "").strip().lower()).strip("-._")
    return normalized or "pocket-lab-lite-device"


def _load_env_file(path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        key = key.strip()
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key):
            continue
        try:
            parsed = shlex.split(raw_value, posix=True)
            value = parsed[0] if parsed else ""
        except Exception:
            value = raw_value.strip().strip('"').strip("'")
        values[key] = value
    return values


def _run(command: List[str], *, env: Dict[str, str] | None = None, timeout: float = 12.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=False, capture_output=True, text=True, env=env, timeout=timeout)


def _pm2_available() -> bool:
    try:
        return _run(["sh", "-lc", "command -v pm2"], timeout=4).returncode == 0
    except Exception:
        return False


class LiteAgentSupervisor:
    def __init__(self) -> None:
        self.home = Path.home()
        self.env_file = Path(os.environ.get("POCKETLAB_AGENT_ENV_FILE", self.home / ".pocketlab-lite-agent.env")).expanduser()
        self.env_data = {**_load_env_file(self.env_file), **dict(os.environ)}
        self.node_id = _normalize_node_id(
            self.env_data.get("POCKETLAB_NODE_ID")
            or self.env_data.get("POCKETLAB_NODE_NAME")
            or socket.gethostname()
        )
        self.node_name = self.env_data.get("POCKETLAB_NODE_NAME") or self.node_id
        self.role = self.env_data.get("POCKETLAB_NODE_ROLE") or self.env_data.get("POCKETLAB_ROLE") or "compute"
        self.nats_url = self.env_data.get("POCKETLAB_NATS_URL", "")
        self.agent_process = f"pocketlab-agent-{self.node_id}"
        self.supervisor_process = f"pocketlab-agent-supervisor-{self.node_id}"
        self.agent_file = Path(
            self.env_data.get(
                "POCKETLAB_AGENT_FILE",
                self.home / "pocket-lab-lite/pocket-lab-final-structure/runtime/agents/pocketlab_node_agent.py",
            )
        ).expanduser()
        self.interval = max(5, int(self.env_data.get("POCKETLAB_AGENT_SUPERVISOR_SECONDS", DEFAULT_INTERVAL_SECONDS)))
        self.state_file = Path(
            self.env_data.get(
                "POCKETLAB_AGENT_SUPERVISOR_STATE",
                self.home / ".config/pocket-lab-lite/agent-supervisor.json",
            )
        ).expanduser()
        self.repair_count = 0
        self.last_repair_at = ""

    def _process_env(self) -> Dict[str, str]:
        env = {**os.environ, **self.env_data}
        env["POCKETLAB_NODE_ID"] = self.node_id
        env["POCKETLAB_NODE_NAME"] = self.node_name
        env["POCKETLAB_NODE_ROLE"] = self.role
        env["POCKETLAB_AGENT_FILE"] = str(self.agent_file)
        return env

    def _pm2_processes(self) -> List[Dict[str, Any]]:
        try:
            result = _run(["pm2", "jlist"], env=self._process_env(), timeout=8)
            if result.returncode != 0 or not result.stdout.strip():
                return []
            payload = json.loads(result.stdout)
            return payload if isinstance(payload, list) else []
        except Exception:
            return []

    def _agent_process_status(self) -> str:
        for item in self._pm2_processes():
            if str(item.get("name") or "") != self.agent_process:
                continue
            env = item.get("pm2_env") if isinstance(item.get("pm2_env"), dict) else {}
            status = str(env.get("status") or item.get("status") or "unknown").lower()
            return status or "unknown"
        return "missing"

    def _start_or_restart_agent(self, process_status: str) -> bool:
        if not _pm2_available() or not self.agent_file.exists():
            return False
        env = self._process_env()
        started = False
        if process_status == "missing":
            result = _run(
                ["pm2", "start", "python3", "--name", self.agent_process, "--update-env", "--", str(self.agent_file)],
                env=env,
                timeout=20,
            )
            started = result.returncode == 0
        else:
            result = _run(["pm2", "restart", self.agent_process, "--update-env"], env=env, timeout=20)
            started = result.returncode == 0
            if not started:
                fallback = _run(
                    ["pm2", "start", "python3", "--name", self.agent_process, "--update-env", "--", str(self.agent_file)],
                    env=env,
                    timeout=20,
                )
                started = fallback.returncode == 0
        if started:
            self.repair_count += 1
            self.last_repair_at = _now_iso()
            try:
                _run(["pm2", "save"], env=env, timeout=12)
            except Exception:
                pass
        return started

    def _nats_reachable(self) -> bool:
        if not self.nats_url:
            return False
        parsed = urlparse(self.nats_url)
        host = parsed.hostname
        port = parsed.port or 4222
        if not host:
            return False
        try:
            with socket.create_connection((host, port), timeout=DEFAULT_NATS_TIMEOUT_SECONDS) as sock:
                sock.settimeout(2)
                sock.recv(16)
            return True
        except Exception:
            return False

    def _write_state(self, payload: Dict[str, Any]) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        tmp.replace(self.state_file)

    async def _publish_status(self, payload: Dict[str, Any]) -> None:
        if nats is None or not self.nats_url:
            return
        try:
            kwargs: Dict[str, Any] = {"servers": [self.nats_url], "connect_timeout": 4, "max_reconnect_attempts": 1}
            if self.env_data.get("POCKETLAB_NATS_TOKEN"):
                kwargs["token"] = self.env_data["POCKETLAB_NATS_TOKEN"]
            elif self.env_data.get("POCKETLAB_NATS_USER") and self.env_data.get("POCKETLAB_NATS_PASSWORD"):
                kwargs["user"] = self.env_data["POCKETLAB_NATS_USER"]
                kwargs["password"] = self.env_data["POCKETLAB_NATS_PASSWORD"]
            nc = await nats.connect(**kwargs)  # type: ignore[union-attr]
            await nc.publish(
                "pocketlab.events.fleet.node_supervisor",
                json.dumps({
                    "type": "fleet.node_supervisor",
                    "time": payload.get("checked_at") or _now_iso(),
                    "data": payload,
                }).encode("utf-8"),
            )
            await nc.drain()
        except Exception:
            return

    async def tick(self) -> Dict[str, Any]:
        process_status = self._agent_process_status()
        repair_attempted = False
        repaired = False
        supervisor_status = "healthy"

        if process_status in {"missing", "stopped", "errored", "error", "stopping", "stopped"}:
            repair_attempted = True
            repaired = self._start_or_restart_agent(process_status)
            supervisor_status = "repairing" if repaired else "degraded"
            if repaired:
                process_status = self._agent_process_status()

        nats_reachable = self._nats_reachable()
        if process_status in {"stopped", "errored", "error", "missing"}:
            agent_status = "agent_stopped"
        elif supervisor_status == "repairing":
            agent_status = "repairing"
        elif process_status == "online":
            agent_status = "online"
        else:
            agent_status = "unknown"

        payload: Dict[str, Any] = {
            "node_id": self.node_id,
            "id": self.node_id,
            "name": self.node_name,
            "hostname": self.node_name,
            "role": self.role,
            "status": agent_status,
            "agent_status": agent_status,
            "agent_process": self.agent_process,
            "agent_process_status": process_status,
            "supervisor_process": self.supervisor_process,
            "supervisor_status": supervisor_status,
            "supervisor_version": SUPERVISOR_VERSION,
            "repair_attempted": repair_attempted,
            "repair_count": self.repair_count,
            "last_repair_at": self.last_repair_at,
            "nats_reachable": nats_reachable,
            "checked_at": _now_iso(),
            "seen_at": _now_iso(),
            "capabilities": ["agent-supervisor", "agent-repair"],
        }
        self._write_state(payload)
        await self._publish_status(payload)
        return payload

    async def run(self) -> None:
        while not _STOP:
            try:
                await self.tick()
            except Exception as exc:
                try:
                    self._write_state({
                        "node_id": self.node_id,
                        "name": self.node_name,
                        "supervisor_status": "degraded",
                        "error": str(exc),
                        "checked_at": _now_iso(),
                    })
                except Exception:
                    pass
            await asyncio.sleep(self.interval)


def _handle_stop(_signum: int, _frame: Any) -> None:
    global _STOP
    _STOP = True


def main() -> int:
    if os.environ.get("POCKETLAB_AGENT_SUPERVISOR_DISABLED") == "1":
        return 0
    signal.signal(signal.SIGTERM, _handle_stop)
    signal.signal(signal.SIGINT, _handle_stop)
    supervisor = LiteAgentSupervisor()
    asyncio.run(supervisor.run())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
