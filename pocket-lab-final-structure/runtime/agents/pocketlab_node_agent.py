#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import platform
import ssl
import random
import logging
import re
import signal
import shutil
import socket
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from lite_system_profile import collect_system_health, collect_system_profile, unavailable_system_profile

try:
    import nats  # type: ignore
except Exception:  # pragma: no cover
    nats = None  # type: ignore

AGENT_VERSION = "2.5.0-lite-trust-capability-awareness"
SYSTEM_PROFILE_REFRESH_SECONDS = 12 * 60 * 60
SYSTEM_HEALTH_REFRESH_SECONDS = 5 * 60
PROFILE_REPUBLISH_SECONDS = 6 * 60 * 60
RECONNECT_MAX_SECONDS = 30.0

logging.getLogger("nats").setLevel(logging.CRITICAL)


def env(name: str, default: str = "") -> str:
    value = os.environ.get(name)
    return value if value is not None and value != "" else default


def normalize_node_id(value: str | None) -> str:
    raw = (value or "").strip().lower()
    raw = re.sub(r"[^a-z0-9_.-]+", "-", raw).strip("-._")
    return raw or "pocket-node"


def now_iso() -> str:
    import datetime as dt

    return (
        dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:16] if token else ""


def telemetry_snapshot() -> Dict[str, Any]:
    cpu_temp = 42.0
    for candidate in [
        "/sys/class/thermal/thermal_zone0/temp",
        "/sys/class/thermal/thermal_zone1/temp",
        "/sys/devices/virtual/thermal/thermal_zone0/temp",
    ]:
        try:
            p = Path(candidate)
            if p.exists():
                raw = float(p.read_text().strip())
                cpu_temp = raw / 1000.0 if raw > 1000 else raw
                break
        except Exception:
            pass
    try:
        load = os.getloadavg()[0]
        cpu_count = os.cpu_count() or 1
        cpu_usage = max(0.0, min(100.0, (load / cpu_count) * 100.0))
    except Exception:
        cpu_usage = 0.0
    try:
        st = os.statvfs(str(Path.home()))
        free_space = int((st.f_bavail * st.f_frsize) // (1024 * 1024))
        total_space = int((st.f_blocks * st.f_frsize) // (1024 * 1024))
    except Exception:
        free_space = 0
        total_space = 0
    try:
        mem = {}
        with open("/proc/meminfo", "r", encoding="utf-8") as handle:
            for line in handle:
                if ":" in line and line.split()[1].isdigit():
                    mem[line.split(":", 1)[0]] = int(line.split()[1])
        total = mem.get("MemTotal", 0) // 1024
        avail = mem.get("MemAvailable", mem.get("MemFree", 0)) // 1024
    except Exception:
        total = 0
        avail = 0
    return {
        "timestamp": now_iso(),
        "cpu_temp_c": round(cpu_temp, 1),
        "cpu_usage_percent": round(cpu_usage, 1),
        "free_space_mb": free_space,
        "total_space_mb": total_space,
        "memory_total_mb": total,
        "memory_free_mb": avail,
        "memory_usage_mb": max(0, total - avail),
    }




def advertised_capabilities(role: str, *, is_control_plane: bool, supervisor_available: bool) -> list[str]:
    normalized = str(role or "compute").strip().lower().replace("-", "_").replace(" ", "_")
    capabilities = {
        "heartbeat",
        "telemetry",
        "health",
        "node-command",
        "receive_commands",
        "agent-restart",
        "reconnect-watchdog",
    }
    if supervisor_available:
        capabilities.update({"agent-supervisor", "agent-repair", "supervisor_recovery"})
    if normalized in {"storage", "storage_node", "backup_target"}:
        capabilities.update({"provide_storage", "store_backups", "backup_target", "restore_target"})
    else:
        capabilities.update({"host_apps", "compute"})
    if is_control_plane:
        capabilities.update(
            {
                "serve_control_plane",
                "host_apps",
                "run_safety_checks",
                "remote_access",
                "access_phone_media",
            }
        )
    return sorted(capabilities)


def health_snapshot() -> Dict[str, Any]:
    checks = {
        "python": "healthy" if sys.version_info >= (3, 10) else "degraded",
        "filesystem": (
            "healthy" if os.access(str(Path.home()), os.W_OK) else "unhealthy"
        ),
        "nats_agent": "healthy",
    }
    unhealthy = [name for name, status in checks.items() if status != "healthy"]
    return {
        "status": "healthy" if not unhealthy else "degraded",
        "checks": checks,
        "unhealthy": unhealthy,
        "checked_at": now_iso(),
    }


class PocketLabNodeAgent:
    def __init__(self) -> None:
        host = socket.gethostname() or platform.node() or "pocket-node"
        self.node_id = normalize_node_id(env("POCKETLAB_NODE_ID", host))
        self.hostname = env("POCKETLAB_NODE_NAME", host)
        self.role = env("POCKETLAB_NODE_ROLE", "compute")
        self.is_control_plane = env("POCKETLAB_IS_CONTROL_PLANE", "0").strip().lower() in {
            "1", "true", "yes", "on"
        }
        self.nats_url = env("POCKETLAB_NATS_URL", "nats://127.0.0.1:4222")
        self.token = env("POCKETLAB_AGENT_TOKEN", "")
        self.nats_user = env("POCKETLAB_NATS_USER", "")
        self.nats_password = env("POCKETLAB_NATS_PASSWORD", "")
        self.nats_token = env("POCKETLAB_NATS_TOKEN", "")
        self.nats_tls = env("POCKETLAB_NATS_TLS", "").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self.nats_tls_ca = env("POCKETLAB_NATS_TLS_CA", "")
        self.nats_tls_cert = env("POCKETLAB_NATS_TLS_CERT", "")
        self.nats_tls_key = env("POCKETLAB_NATS_TLS_KEY", "")
        self.heartbeat_seconds = int(env("POCKETLAB_AGENT_HEARTBEAT_SECONDS", "15"))
        self.telemetry_seconds = int(env("POCKETLAB_AGENT_TELEMETRY_SECONDS", "20"))
        self.nc = None
        self.stop_event = asyncio.Event()
        self.restarting = False
        self.last_publish_success_epoch = 0.0
        self.last_disconnect_epoch = 0.0
        self.reconnect_count = 0
        self.self_heal_seconds = int(env("POCKETLAB_AGENT_SELF_HEAL_SECONDS", "180"))
        self.capabilities = advertised_capabilities(
            self.role,
            is_control_plane=self.is_control_plane,
            supervisor_available=bool(shutil.which("pm2")),
        )
        self.connected_at = now_iso()
        self.system_profile_refresh_seconds = max(
            3600,
            int(env("POCKETLAB_AGENT_SYSTEM_PROFILE_SECONDS", str(SYSTEM_PROFILE_REFRESH_SECONDS))),
        )
        self.system_health_refresh_seconds = max(
            60,
            int(env("POCKETLAB_AGENT_SYSTEM_HEALTH_SECONDS", str(SYSTEM_HEALTH_REFRESH_SECONDS))),
        )
        self.system_profile: Dict[str, Any] = {}
        self.system_health: Dict[str, Any] = {}
        self.system_profile_collected_epoch = 0.0
        self.system_health_collected_epoch = 0.0
        self.last_published_profile_fingerprint = ""
        self.last_profile_publish_epoch = 0.0
        self.profile_revision = 0
        self.profile_republish_seconds = max(3600, int(env("POCKETLAB_AGENT_PROFILE_REPUBLISH_SECONDS", str(PROFILE_REPUBLISH_SECONDS))))
        self.connection_ready = asyncio.Event()
        self.disconnected_event = asyncio.Event()
        self.connection_lock = asyncio.Lock()
        self.publish_lock = asyncio.Lock()
        self.reconnect_sync_lock = asyncio.Lock()
        self.connection_generation = 0
        self.last_error_signature = ""
        self.last_error_logged_epoch = 0.0

    def refresh_system_profile(self, *, force: bool = False) -> Dict[str, Any]:
        now = time.time()
        due = force or not self.system_profile or (
            now - self.system_profile_collected_epoch >= self.system_profile_refresh_seconds
        )
        if due:
            try:
                collected = collect_system_profile(agent_version=AGENT_VERSION)
                if collected:
                    self.system_profile = collected
            except Exception as exc:
                error_type = type(exc).__name__[:64]
                if not self.system_profile:
                    self.system_profile = unavailable_system_profile(
                        agent_version=AGENT_VERSION,
                        error_type=error_type,
                    )
                print(
                    f"Pocket Lab node agent profile_collection_failed: error_type={error_type}",
                    file=sys.stderr,
                )
            self.system_profile_collected_epoch = now
        return self.system_profile

    def refresh_system_health(self, *, force: bool = False) -> Dict[str, Any]:
        now = time.time()
        due = force or not self.system_health or (
            now - self.system_health_collected_epoch >= self.system_health_refresh_seconds
        )
        if due:
            try:
                self.system_health = collect_system_health()
            except Exception:
                self.system_health = {
                    "uptime_status": "unavailable",
                    "failure_code": "health_collection_failed",
                    "collected_at": now_iso(),
                }
            self.system_health_collected_epoch = now
        return self.system_health

    def system_profile_update(self, *, force_publish: bool = False) -> Dict[str, Any]:
        previous_collected_epoch = self.system_profile_collected_epoch
        profile = dict(self.refresh_system_profile(force=force_publish))
        fingerprint = str(profile.get("profile_fingerprint") or "")
        if not fingerprint:
            return {}
        refreshed = self.system_profile_collected_epoch != previous_collected_epoch
        periodic_due = time.time() - self.last_profile_publish_epoch >= self.profile_republish_seconds
        changed = fingerprint != self.last_published_profile_fingerprint
        if not force_publish and not refreshed and not periodic_due and not changed:
            return {}
        self.profile_revision += 1
        profile.update({
            "revision": self.profile_revision,
            "profile_fingerprint": fingerprint,
            "profile_schema_version": int(profile.get("schema_version") or 1),
        })
        return {"system_profile": profile}

    def _mark_profile_published(self, data: Dict[str, Any]) -> None:
        profile = data.get("system_profile") if isinstance(data.get("system_profile"), dict) else {}
        fingerprint = str(profile.get("profile_fingerprint") or "")
        if fingerprint:
            self.last_published_profile_fingerprint = fingerprint
            self.last_profile_publish_epoch = time.time()

    def _error_reason(self, exc: Exception) -> str:
        name = type(exc).__name__.lower()
        message = str(exc).lower()
        if "network is unreachable" in message:
            return "network_unreachable"
        if "timeout" in message:
            return "timeout"
        if "abort" in message or "reset" in message:
            return "connection_interrupted"
        return re.sub(r"[^a-z0-9_]+", "_", name).strip("_")[:64] or "nats_error"

    def _log_connection_error(self, exc: Exception, *, context: str) -> None:
        reason = self._error_reason(exc)
        signature = f"{context}:{reason}"
        now = time.time()
        if signature == self.last_error_signature and now - self.last_error_logged_epoch < 30:
            return
        self.last_error_signature = signature
        self.last_error_logged_epoch = now
        print(f"Pocket Lab node agent {context}: reason={reason}", file=sys.stderr)

    @staticmethod
    def reconnect_delay(attempt: int) -> float:
        base = min(RECONNECT_MAX_SECONDS, float(2 ** max(0, min(attempt, 5))))
        return min(RECONNECT_MAX_SECONDS, base + random.uniform(0.0, min(1.0, base * 0.2)))

    def base_payload(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "name": self.hostname,
            "hostname": self.hostname,
            "role": self.role,
            "is_control_plane": self.is_control_plane,
            "agent_version": AGENT_VERSION,
            "platform": platform.platform(),
            "python": platform.python_version(),
            "status": "online",
            "auth_token_hash": token_hash(self.token),
            "capabilities": self.capabilities,
            "advertised_capabilities": self.capabilities,
            "capability_schema_version": 1,
            "nats_connected_at": self.connected_at,
            "reconnect_count": self.reconnect_count,
        }

    async def safe_publish(
        self, subject: str, event_type: str, data: Dict[str, Any], *, critical: bool = False
    ) -> bool:
        if not self.connection_ready.is_set() or self.nc is None:
            return False
        try:
            async with self.publish_lock:
                await self.publish(subject, event_type, data, critical=critical)
            self.last_publish_success_epoch = time.time()
            self._mark_profile_published(data)
            return True
        except Exception as exc:
            self._log_connection_error(exc, context="publish_failed")
            self.connection_ready.clear()
            self.disconnected_event.set()
            await self.maybe_self_heal_after_publish_failure()
            return False

    async def maybe_self_heal_after_publish_failure(self) -> None:
        if self.restarting:
            return
        now = time.time()
        last_success = self.last_publish_success_epoch or now
        if now - last_success < max(60, self.self_heal_seconds):
            return
        print(
            "Pocket Lab node agent publish watchdog requested a supervised restart.",
            file=sys.stderr,
        )
        self.restarting = True
        await self.restart_after_ack(delay_seconds=1, reason="publish-watchdog")

    async def restart_after_ack(self, delay_seconds: int = 1, reason: str = "command") -> None:
        await asyncio.sleep(max(0, delay_seconds))
        process_name = f"pocketlab-agent-{self.node_id}"
        if shutil.which("pm2"):
            command = f"pm2 restart {process_name} --update-env >/dev/null 2>&1"
            subprocess.Popen(
                ["sh", "-lc", f"sleep 1; {command}"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return
        self.stop_event.set()

    async def on_disconnected(self) -> None:
        self.last_disconnect_epoch = time.time()
        self.connection_ready.clear()
        self.disconnected_event.set()
        print("Pocket Lab node agent disconnected from NATS; reconnect is scheduled.", file=sys.stderr)

    async def on_reconnected(self) -> None:
        # Manual connection ownership is used; this callback is retained for nats-py
        # compatibility and only signals state. It never starts a second recovery path.
        self.connection_ready.set()

    async def on_closed(self) -> None:
        self.connection_ready.clear()
        self.disconnected_event.set()

    async def on_error(self, exc: Exception) -> None:
        self._log_connection_error(exc, context="nats_error")

    async def publish(
        self, subject: str, event_type: str, data: Dict[str, Any], *, critical: bool = False
    ) -> None:
        event = {
            "id": uuid.uuid4().hex,
            "type": event_type,
            "subject": subject,
            "time": now_iso(),
            "source": f"pocketlab-node-agent/{self.node_id}",
            "trace_id": data.get("command_id") or data.get("trace_id"),
            "data": data,
        }
        if self.nc is None or not self.connection_ready.is_set():
            raise ConnectionError("nats_not_connected")
        await self.nc.publish(subject, json.dumps(event, separators=(",", ":")).encode("utf-8"))
        if critical:
            await self.nc.flush(timeout=2)

    async def register(self) -> bool:
        return await self.safe_publish(
            "pocketlab.events.fleet.node_seen",
            "fleet.node_seen",
            {
                **self.base_payload(),
                "system_health": self.refresh_system_health(force=False),
                "seen_at": now_iso(),
            },
            critical=True,
        )

    async def publish_profile(self, *, force: bool = False) -> bool:
        profile = self.system_profile_update(force_publish=force)
        if not profile:
            return True
        return await self.safe_publish(
            "pocketlab.events.fleet.node_profile",
            "fleet.node_profile",
            {**self.base_payload(), **profile, "profile_reported_at": now_iso()},
            critical=force,
        )

    async def publish_capabilities(self, *, critical: bool = False) -> bool:
        return await self.safe_publish(
            "pocketlab.events.fleet.node_capabilities",
            "fleet.node_capabilities",
            {
                **self.base_payload(),
                "capabilities": self.capabilities,
                "advertised_capabilities": self.capabilities,
                "capability_schema_version": 1,
                "capabilities_reported_at": now_iso(),
            },
            critical=critical,
        )

    async def synchronize_after_connect(self, *, reason: str) -> None:
        async with self.reconnect_sync_lock:
            self.reconnect_count += int(reason == "nats-reconnected")
            self.connection_generation += 1
            self.connected_at = now_iso()
            self.refresh_system_health(force=True)
            await self.register()
            await self.publish_profile(force=True)
            await self.publish_capabilities(critical=True)
            await self.safe_publish(
                "pocketlab.events.fleet.node_heartbeat",
                "fleet.node_heartbeat",
                {
                    **self.base_payload(),
                    "system_health": self.refresh_system_health(force=False),
                    "heartbeat_at": now_iso(),
                    "reason": reason,
                    "connection_generation": self.connection_generation,
                },
                critical=True,
            )

    def _connect_kwargs(self) -> Dict[str, Any]:
        connect_kwargs: Dict[str, Any] = {
            "servers": [self.nats_url],
            "name": f"pocketlab-agent-{self.node_id}",
            "max_reconnect_attempts": 0,
            "disconnected_cb": self.on_disconnected,
            "reconnected_cb": self.on_reconnected,
            "closed_cb": self.on_closed,
            "error_cb": self.on_error,
            "connect_timeout": 5,
        }
        if self.nats_user:
            connect_kwargs["user"] = self.nats_user
        if self.nats_password:
            connect_kwargs["password"] = self.nats_password
        if self.nats_token:
            connect_kwargs["token"] = self.nats_token
        if self.nats_tls or self.nats_tls_ca or self.nats_tls_cert:
            context = ssl.create_default_context(cafile=self.nats_tls_ca or None)
            if self.nats_tls_cert and self.nats_tls_key:
                context.load_cert_chain(self.nats_tls_cert, self.nats_tls_key)
            connect_kwargs["tls"] = context
        return connect_kwargs

    async def connection_manager(self) -> None:
        attempt = 0
        connected_once = False
        while not self.stop_event.is_set():
            try:
                async with self.connection_lock:
                    self.disconnected_event.clear()
                    self.nc = await nats.connect(**self._connect_kwargs())
                    self.connection_ready.set()
                    for subject in (f"pocketlab.commands.node.{self.node_id}.>", "pocketlab.commands.node.all.>"):
                        await self.nc.subscribe(subject, cb=self.handle_command)
                    await self.synchronize_after_connect(
                        reason="nats-reconnected" if connected_once else "agent-started"
                    )
                    connected_once = True
                    attempt = 0
                stop_task = asyncio.create_task(self.stop_event.wait())
                disconnect_task = asyncio.create_task(self.disconnected_event.wait())
                done, pending = await asyncio.wait(
                    {stop_task, disconnect_task}, return_when=asyncio.FIRST_COMPLETED
                )
                for task in pending:
                    task.cancel()
                if self.stop_event.is_set():
                    break
            except Exception as exc:
                self._log_connection_error(exc, context="connect_failed")
            finally:
                self.connection_ready.clear()
                current = self.nc
                self.nc = None
                if current is not None:
                    try:
                        await current.close()
                    except Exception:
                        pass
            if self.stop_event.is_set():
                break
            delay = self.reconnect_delay(attempt)
            attempt += 1
            try:
                await asyncio.wait_for(self.stop_event.wait(), timeout=delay)
            except asyncio.TimeoutError:
                pass

    async def heartbeat_loop(self) -> None:
        while not self.stop_event.is_set():
            await self.safe_publish(
                "pocketlab.events.fleet.node_heartbeat",
                "fleet.node_heartbeat",
                {
                    **self.base_payload(),
                    "heartbeat_at": now_iso(),
                    "connection_generation": self.connection_generation,
                },
            )
            try:
                await asyncio.wait_for(
                    self.stop_event.wait(), timeout=max(5, self.heartbeat_seconds)
                )
            except asyncio.TimeoutError:
                continue

    async def profile_loop(self) -> None:
        while not self.stop_event.is_set():
            await self.publish_profile(force=False)
            try:
                await asyncio.wait_for(self.stop_event.wait(), timeout=60)
            except asyncio.TimeoutError:
                continue

    async def telemetry_loop(self) -> None:
        while not self.stop_event.is_set():
            await self.safe_publish(
                "pocketlab.events.fleet.node_telemetry",
                "fleet.node_telemetry",
                {
                    **self.base_payload(),
                    "telemetry": telemetry_snapshot(),
                    "sampled_at": now_iso(),
                },
            )
            await self.safe_publish(
                "pocketlab.events.fleet.node_health",
                "fleet.node_health",
                {
                    **self.base_payload(),
                    "health": health_snapshot(),
                    "system_health": self.refresh_system_health(),
                    "sampled_at": now_iso(),
                },
            )
            try:
                await asyncio.wait_for(
                    self.stop_event.wait(), timeout=max(5, self.telemetry_seconds)
                )
            except asyncio.TimeoutError:
                continue

    async def handle_command(self, msg: Any) -> None:
        command_id = ""
        command_name = "unknown"
        try:
            envelope = json.loads(msg.data.decode("utf-8"))
            data = envelope.get("data") if isinstance(envelope, dict) else {}
            if not isinstance(data, dict):
                data = {}
            command_id = str(
                data.get("command_id") or envelope.get("trace_id") or uuid.uuid4().hex
            )
            command_name = str(
                data.get("command") or data.get("action") or msg.subject.split(".")[-1]
            )
            result: Dict[str, Any]
            status = "completed"
            if command_name in {"health.check", "health", "check"}:
                result = {"health": health_snapshot()}
            elif command_name in {"telemetry.sample", "telemetry"}:
                result = {"telemetry": telemetry_snapshot()}
            elif command_name in {"agent.describe", "describe"}:
                result = {"agent": self.base_payload()}
            elif command_name in {"agent.restart", "restart"}:
                result = {
                    "message": "Restart requested; PM2 will restart the agent when available.",
                    "supervisor": "pm2" if shutil.which("pm2") else "process-exit",
                }
                status = "acknowledged"
                asyncio.create_task(self.restart_after_ack())
            elif command_name in {"apply_blueprint", "node.apply_blueprint"}:
                result = {
                    "message": "Blueprint execution is acknowledged; install a node executor to enable remote apply.",
                    "accepted": True,
                }
                status = "acknowledged"
            else:
                result = {"message": f"Unsupported node command: {command_name}"}
                status = "unsupported"
            await self.safe_publish(
                "pocketlab.events.fleet.node_command_result",
                "fleet.node_command_result",
                {
                    **self.base_payload(),
                    "command_id": command_id,
                    "command": command_name,
                    "status": status,
                    "result": result,
                    "finished_at": now_iso(),
                },
                critical=True,
            )
        except Exception as exc:
            await self.safe_publish(
                "pocketlab.events.fleet.node_command_result",
                "fleet.node_command_result",
                {
                    **self.base_payload(),
                    "command_id": command_id or uuid.uuid4().hex,
                    "command": command_name,
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "error_reason": "command_execution_failed",
                    "finished_at": now_iso(),
                },
                critical=True,
            )

    async def run(self) -> int:
        if nats is None:
            print("nats-py is required for pocketlab_node_agent.py", file=sys.stderr)
            return 2
        self.refresh_system_profile(force=True)
        self.refresh_system_health(force=True)
        tasks = [
            asyncio.create_task(self.connection_manager()),
            asyncio.create_task(self.heartbeat_loop()),
            asyncio.create_task(self.telemetry_loop()),
            asyncio.create_task(self.profile_loop()),
        ]
        await self.stop_event.wait()
        if self.connection_ready.is_set():
            await self.safe_publish(
                "pocketlab.events.fleet.node_left",
                "fleet.node_left",
                {**self.base_payload(), "status": "offline", "left_at": now_iso()},
                critical=True,
            )
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        return 0


def main() -> int:
    agent = PocketLabNodeAgent()

    def stop(*_: Any) -> None:
        agent.stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, stop)
        except Exception:
            pass
    try:
        return asyncio.run(agent.run())
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        reason = PocketLabNodeAgent._error_reason(exc)
        print(f"Pocket Lab node agent failed: reason={reason}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
