#!/usr/bin/env sh
# Streamed, read-only Termux runtime probe. It is never installed on the phone.
set -eu

command -v python3 >/dev/null 2>&1 || {
  printf '%s\n' 'ERROR remote Termux probe requires python3; no packages were installed' >&2
  exit 74
}

exec python3 - <<'PY'
from __future__ import annotations

import datetime as dt
import ipaddress
import json
import os
import re
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

TAILSCALE_NETWORK = ipaddress.ip_network("100.64.0.0/10")
PRIVATE_IPV4_NETWORKS = tuple(ipaddress.ip_network(value) for value in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))

MAX_CAPTURE_BYTES = 512 * 1024
MAX_COMMAND_BYTES = 256 * 1024
DEFAULT_TIMEOUT = 6.0
START = time.monotonic()

APPROVED_PM2_NAMES = {
    "pocket-api", "pocket-worker", "pocket-nats", "pocket-node-agent",
    "pocketlab-core-supervisor", "caddy-proxy", "pocketlab-app-photoprism",
}
APPROVED_PM2_PREFIXES = ("pocketlab-agent-", "pocketlab-agent-supervisor-")
PROBE_REGISTRY = (
    {"id": "platform", "capabilities": ("uname",), "timeout": 6, "max_output_bytes": 4096, "parser": "platform-semantic", "sanitizer": "identity-free", "required": True, "failure": "partial"},
    {"id": "pm2", "capabilities": ("pm2",), "timeout": 10, "max_output_bytes": MAX_COMMAND_BYTES, "parser": "pm2-allowlist", "sanitizer": "approved-process-fields", "required": True, "failure": "missing-or-error"},
    {"id": "caddy", "capabilities": ("caddy",), "timeout": 10, "max_output_bytes": MAX_COMMAND_BYTES, "parser": "caddy-semantic-routes", "sanitizer": "no-address-or-certificate-path", "required": True, "failure": "missing-or-invalid"},
    {"id": "nats", "capabilities": ("nats-server",), "timeout": 8, "max_output_bytes": MAX_COMMAND_BYTES, "parser": "nats-listener-and-config", "sanitizer": "no-bind-address-or-credentials", "required": True, "failure": "missing-or-partial"},
    {"id": "agent-supervisor", "capabilities": ("pm2",), "timeout": 2, "max_output_bytes": 4096, "parser": "approved-pm2-relationships", "sanitizer": "no-node-identity-or-subjects", "required": True, "failure": "partial"},
    {"id": "tailscale", "capabilities": ("tailscale-cli|tailscale",), "timeout": 8, "max_output_bytes": MAX_COMMAND_BYTES, "parser": "tailscale-json-booleans", "sanitizer": "address-and-hostname-redacted", "required": False, "failure": "unavailable"},
    {"id": "sqlite", "capabilities": ("sqlite3",), "timeout": 12, "max_output_bytes": 16384, "parser": "allowlisted-pragmas-and-table-names", "sanitizer": "no-rows-or-paths", "required": True, "failure": "missing-or-failed"},
    {"id": "proot-apps", "capabilities": ("proot-distro",), "timeout": 8, "max_output_bytes": 16384, "parser": "bounded-runtime-presence", "sanitizer": "no-media-or-user-paths", "required": False, "failure": "unavailable"},
)


def run(argv: list[str], timeout: float = DEFAULT_TIMEOUT) -> tuple[str, str]:
    try:
        completed = subprocess.run(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        return "missing", ""
    except subprocess.TimeoutExpired:
        return "timeout", ""
    output = completed.stdout[:MAX_COMMAND_BYTES]
    return ("ok" if completed.returncode == 0 else "error"), output


def command_exists(name: str) -> bool:
    state, _ = run(["sh", "-c", f"command -v {name}"], timeout=2.0)
    return state == "ok"


def safe_bool(value: Any) -> bool:
    return bool(value)


def platform_probe() -> dict[str, Any]:
    kernel_state, kernel = run(["uname", "-s"])
    arch_state, architecture = run(["uname", "-m"])
    android_state, android_release = run(["getprop", "ro.build.version.release"]) if command_exists("getprop") else ("missing", "")
    abi_state, abi = run(["getprop", "ro.product.cpu.abi"]) if command_exists("getprop") else ("missing", "")
    prefix = os.environ.get("PREFIX", "")
    prefix_kind = "termux" if prefix == "/data/data/com.termux/files/usr" else ("non-termux" if prefix else "unknown")
    state = "ok" if kernel_state == arch_state == "ok" and prefix_kind == "termux" else "partial"
    return {
        "state": state,
        "kernel": kernel.strip()[:32],
        "architecture": architecture.strip()[:32],
        "android_release": android_release.strip()[:32] if android_state == "ok" else "",
        "abi": abi.strip()[:32] if abi_state == "ok" else "",
        "termux_prefix_kind": prefix_kind,
    }


def approved_pm2_name(name: str) -> bool:
    return name in APPROVED_PM2_NAMES or any(name.startswith(prefix) for prefix in APPROVED_PM2_PREFIXES)


def version_major(value: Any) -> str:
    match = re.search(r"(?:^|\D)(\d+)(?:\.\d+)?", str(value or ""))
    return match.group(1) if match else "unknown"


def runtime_type(process: dict[str, Any]) -> str:
    interpreter = str(process.get("pm2_env", {}).get("exec_interpreter") or "").lower()
    script = str(process.get("pm2_env", {}).get("pm_exec_path") or "").lower()
    if "python" in interpreter or script.endswith(".py"):
        return "python"
    if "node" in interpreter or script.endswith((".js", ".mjs", ".cjs")):
        return "node"
    if "proot" in script or "photoprism" in str(process.get("name", "")).lower():
        return "proot"
    if interpreter in {"bash", "sh"}:
        return "shell"
    if interpreter in {"none", ""}:
        return "native"
    return "unknown"


def pm2_probe() -> dict[str, Any]:
    if not command_exists("pm2"):
        return {"state": "missing", "command_available": False, "processes": []}
    state, output = run(["pm2", "jlist"], timeout=10.0)
    processes: list[dict[str, Any]] = []
    if state == "ok":
        try:
            payload = json.loads(output)
        except json.JSONDecodeError:
            state = "error"
            payload = []
        if isinstance(payload, list):
            for process in payload[:128]:
                if not isinstance(process, dict):
                    continue
                name = str(process.get("name") or "")[:96]
                if not approved_pm2_name(name):
                    continue
                env = process.get("pm2_env") if isinstance(process.get("pm2_env"), dict) else {}
                monit = process.get("monit") if isinstance(process.get("monit"), dict) else {}
                try:
                    process_id = max(0, int(process.get("pm_id")))
                except (TypeError, ValueError):
                    process_id = None
                # Emit only approved semantic PM2 fields. Never emit env or command lines.
                processes.append({
                    "name": name,
                    "process_id": process_id,
                    "status": str(env.get("status") or "unknown")[:32],
                    "restarts": max(0, int(env.get("restart_time") or 0)),
                    "memory_bytes": max(0, int(monit.get("memory") or 0)),
                    "runtime_type": runtime_type(process),
                    "version_major": version_major(env.get("version")),
                })
    return {"state": state, "command_available": True, "processes": processes}


def caddy_candidates() -> list[Path]:
    home = Path.home()
    candidates = []
    configured = os.environ.get("POCKETLAB_CADDYFILE", "").strip()
    if configured:
        candidates.append(Path(configured).expanduser())
    candidates.extend([
        home / "pocket-lab-lite" / "caddy" / "Caddyfile",
        home / ".pocket_lab" / "caddy" / "Caddyfile",
    ])
    unique: list[Path] = []
    for candidate in candidates:
        if candidate not in unique:
            unique.append(candidate)
    return unique[:4]


def _upstream_kind(text: str, marker: str, app: bool = False) -> str:
    position = text.find(marker)
    if position < 0:
        return "missing"
    window = text[position: position + 3000]
    match = re.search(r"\breverse_proxy\s+([^\s{]+)", window)
    if not match:
        return "unknown"
    target = match.group(1).strip().lower()
    if any(value in target for value in ("127.0.0.1", "localhost", "[::1]", "unix/", "unix//")):
        return "loopback-app" if app else "loopback-fastapi"
    return "private-or-unknown"


def _https_mode(text: str) -> str:
    lowered = text.lower()
    if "get_certificate tailscale" in lowered:
        return "tailscale-integration"
    if re.search(r"\btls\s+[^\s{]+\.(?:crt|pem)\s+[^\s{]+\.(?:key|pem)", lowered):
        return "explicit-files"
    if "https://" in lowered or ".ts.net" in lowered:
        return "automatic-caddy"
    return "none" if text else "unknown"


def caddy_probe() -> dict[str, Any]:
    available = command_exists("caddy")
    version_state, version = run(["caddy", "version"]) if available else ("missing", "")
    config = next((path for path in caddy_candidates() if path.is_file()), None)
    text = ""
    if config:
        try:
            text = config.read_text(encoding="utf-8", errors="ignore")[:MAX_COMMAND_BYTES]
        except OSError:
            text = ""
    validation_state = "not-run"
    if available and config:
        validation, _ = run(["caddy", "validate", "--config", str(config)], timeout=10.0)
        validation_state = "valid" if validation == "ok" else ("invalid" if validation == "error" else "unavailable")
    elif not available:
        validation_state = "unavailable"
    api_position = text.find("/api/lite")
    pwa_positions = [value for value in (text.find("file_server"), text.find("try_files"), text.find("root *")) if value >= 0]
    pwa_position = min(pwa_positions) if pwa_positions else -1
    route_order = "unknown"
    if api_position >= 0 and pwa_position >= 0:
        route_order = "api-before-pwa" if api_position < pwa_position else "pwa-before-api"
    photoprism_present = "/apps/photoprism" in text
    routes = {
        "pwa": bool(text and pwa_position >= 0),
        "api_lite": api_position >= 0,
        "apps": "/apps/" in text,
        "photoprism": photoprism_present,
        "https": _https_mode(text) not in {"none", "unknown"},
        "https_mode": _https_mode(text),
        "route_order": route_order,
        "api_upstream_kind": _upstream_kind(text, "/api/lite"),
        "app_upstream_kind": _upstream_kind(text, "/apps/photoprism", app=True),
    }
    return {
        "state": "ok" if available and config and validation_state == "valid" else ("partial" if available else "missing"),
        "command_available": available,
        "version": version.strip()[:96] if version_state == "ok" else "",
        "config_present": bool(config),
        "validation_state": validation_state,
        "routes": routes,
    }


def nats_config_candidates() -> list[Path]:
    home = Path.home()
    configured = os.environ.get("POCKETLAB_NATS_CONFIG", "").strip()
    candidates = [Path(configured).expanduser()] if configured else []
    candidates.extend([
        home / ".pocket_lab" / "nats" / "nats-server.conf",
        home / "pocket-lab-lite" / "state" / "nats" / "nats-server.conf",
    ])
    unique: list[Path] = []
    for candidate in candidates:
        if candidate not in unique:
            unique.append(candidate)
    return unique[:4]


def _nats_listener_lines() -> tuple[bool, list[str]]:
    if command_exists("ss"):
        state, output = run(["ss", "-ltn"], timeout=4.0)
    elif command_exists("netstat"):
        state, output = run(["netstat", "-ltn"], timeout=4.0)
    else:
        return False, []
    visible = state == "ok"
    lines = [line for line in output.splitlines() if visible and re.search(r":4222(?:\s|$)", line)]
    return visible, lines


def _nats_local_listener_reachable() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 4222), timeout=2.0):
            return True
    except OSError:
        return False


def _nats_config_semantics(text: str) -> tuple[str, bool, bool | None]:
    def setting(name: str) -> str:
        patterns = (
            rf"(?mi)^\s*{re.escape(name)}\s*[:=]\s*['\"]?([^'\"\s#}}]+)",
            rf"(?mi)^\s*{re.escape(name)}\s+['\"]?([^'\"\s#}}]+)",
        )
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()
        return ""

    host = setting("host")
    listen = setting("listen")
    port = setting("port")
    values = [value.lower() for value in (host, listen) if value]
    if any("0.0.0.0" in value or "[::]" in value or value == "::" for value in values):
        bind_scope = "private-or-all"
    elif any("127.0.0.1" in value or "::1" in value or "localhost" in value for value in values):
        bind_scope = "loopback"
    elif values:
        bind_scope = "private-or-all"
    else:
        bind_scope = "unknown"
    configured_port = 4222 if not port else (int(port) if port.isdigit() else -1)
    fleet_listener_configured = configured_port == 4222 and bind_scope == "private-or-all"
    jetstream = bool(re.search(r"(?:^|\s)jetstream\s*(?:\{|:|$)", text, re.I)) if text else None
    return bind_scope, fleet_listener_configured, jetstream


def _fleet_server_nats_observation() -> bool | None:
    for url in ("http://127.0.0.1:8080/api/lite/fleet", "http://127.0.0.1:8443/api/lite/fleet"):
        try:
            with urllib.request.urlopen(url, timeout=3.0) as response:
                payload = json.load(response)
        except (OSError, urllib.error.URLError, json.JSONDecodeError, ValueError):
            continue
        if not isinstance(payload, dict):
            continue
        devices = payload.get("devices")
        if not isinstance(devices, list):
            continue
        for device in devices[:64]:
            if not isinstance(device, dict):
                continue
            if not (device.get("protected_server_host") is True or device.get("role") == "server_host"):
                continue
            dependencies = device.get("dependencies") if isinstance(device.get("dependencies"), dict) else {}
            return bool(
                device.get("connection") == "online"
                and device.get("command_delivery_status") == "deliverable"
                and dependencies.get("nats_tailnet_reachable") is True
            )
    return None


def nats_probe(pm2: dict[str, Any]) -> dict[str, Any]:
    available = command_exists("nats-server")
    version_state, version = run(["nats-server", "--version"]) if available else ("missing", "")
    listener_tool_visible, lines = _nats_listener_lines()
    local_listener_reachable = _nats_local_listener_reachable() if available else False
    socket_bind_scope = "unknown"
    if lines:
        hosts = []
        for line in lines:
            fields = line.split()
            endpoint = next((field for field in reversed(fields) if ":4222" in field), "")
            host = endpoint.rsplit(":", 1)[0].strip("[]") if endpoint else ""
            if host:
                hosts.append(host)
        if hosts and all(host in {"127.0.0.1", "::1"} for host in hosts):
            socket_bind_scope = "loopback"
        elif hosts:
            socket_bind_scope = "private-or-all"
    config = next((path for path in nats_config_candidates() if path.is_file()), None)
    config_text = ""
    if config:
        try:
            config_text = config.read_text(encoding="utf-8", errors="ignore")[:MAX_COMMAND_BYTES]
        except OSError:
            config_text = ""
    config_bind_scope, fleet_listener_configured, jetstream_enabled = _nats_config_semantics(config_text)
    bind_scope = socket_bind_scope if socket_bind_scope != "unknown" else config_bind_scope
    fleet_connectivity_observed = _fleet_server_nats_observation()
    process_owner = "pm2" if any(
        item.get("name") == "pocket-nats" and str(item.get("status", "")).lower() == "online"
        for item in pm2.get("processes", [])
    ) else "unknown"
    listener_present = bool(local_listener_reachable or lines)
    expected_client_port_present = bool(listener_present and fleet_listener_configured)
    runtime_ready = bool(
        available
        and process_owner == "pm2"
        and local_listener_reachable
        and fleet_listener_configured
        and jetstream_enabled is True
    )
    return {
        "state": "ok" if runtime_ready else ("partial" if available else "missing"),
        "command_available": available,
        "version": version.strip()[:96] if version_state == "ok" else "",
        "listener_present": listener_present,
        "expected_client_port_present": expected_client_port_present,
        "listener_tool_visible": listener_tool_visible,
        "local_listener_reachable": local_listener_reachable,
        "fleet_listener_configured": fleet_listener_configured,
        "fleet_connectivity_observed": fleet_connectivity_observed,
        "bind_scope": bind_scope,
        "jetstream_enabled": jetstream_enabled,
        "process_owner": process_owner,
    }


def agent_supervisor_probe(pm2: dict[str, Any], nats: dict[str, Any]) -> dict[str, Any]:
    process_by_name = {item["name"]: item for item in pm2.get("processes", [])}
    online = {
        name for name, item in process_by_name.items()
        if str(item.get("status", "")).lower() == "online"
    }
    agent = process_by_name.get("pocket-node-agent", {})
    supervisor = process_by_name.get("pocketlab-core-supervisor", {})
    worker_present = "pocket-worker" in online
    return {
        "state": "ok" if pm2.get("state") == "ok" else "partial",
        "agent_present": "pocket-node-agent" in online,
        "core_supervisor_present": "pocketlab-core-supervisor" in online,
        "joined_supervisor_present": any(name.startswith("pocketlab-agent-supervisor-") for name in online),
        "worker_command_owner_present": worker_present,
        "nats_connectivity": "ready" if nats.get("listener_present") else "not-ready",
        "recovery_capability": "supervised" if "pocketlab-core-supervisor" in online else "unavailable",
        "last_evidence_freshness_bucket": "unknown",
        "agent_version_major": str(agent.get("version_major") or "unknown"),
        "supervisor_version_major": str(supervisor.get("version_major") or "unknown"),
        "expected_pm2_ownership": bool(pm2.get("command_available")),
    }


def private_ip_ready(text: str) -> bool:
    for token in re.findall(r"(?<![0-9])(?:\d{1,3}\.){3}\d{1,3}(?![0-9])", text):
        try:
            address = ipaddress.ip_address(token)
        except ValueError:
            continue
        if address.version == 4 and (address in TAILSCALE_NETWORK or any(address in network for network in PRIVATE_IPV4_NETWORKS)):
            return True
    return False


def tailscale_probe() -> dict[str, Any]:
    variant = "missing"
    for candidate in ("tailscale-cli", "tailscale"):
        if command_exists(candidate):
            variant = candidate
            break
    ps_state, ps_output = run(["ps", "-A"], timeout=4.0)
    daemon_running = ps_state == "ok" and any("tailscaled" in line for line in ps_output.splitlines())
    ipv4_ready = False
    connectivity = False
    peer_reachability = "unknown"
    state = "missing" if variant == "missing" else "partial"
    if variant != "missing":
        status_state, status_output = run([variant, "status", "--json"], timeout=8.0)
        if status_state == "ok":
            state = "ok"
            try:
                payload = json.loads(status_output)
            except json.JSONDecodeError:
                payload = {}
            backend_state = str(payload.get("BackendState") or "").lower() if isinstance(payload, dict) else ""
            connectivity = backend_state == "running"
            peers = payload.get("Peer") if isinstance(payload, dict) else {}
            if isinstance(peers, dict):
                online = [bool(item.get("Online")) for item in peers.values() if isinstance(item, dict)]
                peer_reachability = "ready" if any(online) else ("not-ready" if online else "unknown")
        ip_state, ip_output = run([variant, "ip", "-4"], timeout=5.0)
        ipv4_ready = ip_state == "ok" and private_ip_ready(ip_output)
        connectivity = connectivity and ipv4_ready
    return {
        "state": state,
        "command_variant": variant,
        "daemon_running": daemon_running,
        "ipv4_ready": ipv4_ready,
        "private_connectivity_ready": connectivity,
        "peer_reachability": peer_reachability,
        "address_redacted": True,
        "hostname_redacted": True,
    }


def sqlite_candidates() -> list[Path]:
    home = Path.home()
    candidates = []
    configured = os.environ.get("POCKETLAB_LITE_DB_PATH", "").strip()
    if configured:
        candidates.append(Path(configured).expanduser())
    candidates.extend([
        home / "pocket-lab-lite" / "state" / "pocketlab-lite.sqlite3",
        home / ".pocket_lab" / "state" / "pocketlab-lite.sqlite3",
    ])
    unique: list[Path] = []
    for candidate in candidates:
        if candidate not in unique:
            unique.append(candidate)
    return unique[:4]


def sqlite_probe() -> dict[str, Any]:
    available = command_exists("sqlite3")
    database = next((path for path in sqlite_candidates() if path.is_file()), None)
    if not available or not database:
        return {
            "state": "missing" if not available else "partial",
            "command_available": available,
            "database_present": bool(database),
            "integrity": "unavailable" if not available else "not-run",
            "journal_mode": "unknown",
            "expected_tables_present": False,
            "schema_revision": None,
        }
    integrity_state, integrity_output = run(["sqlite3", str(database), "PRAGMA integrity_check;"], timeout=12.0)
    journal_state, journal_output = run(["sqlite3", str(database), "PRAGMA journal_mode;"], timeout=5.0)
    table_state, table_output = run([
        "sqlite3", str(database),
        "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('audit_evidence_index','command_lifecycle','device_enrollment_registry','device_heartbeats','device_supervisor_state','projection_refresh_state') ORDER BY name;",
    ], timeout=7.0)
    revision_state, revision_output = run([
        "sqlite3", str(database),
        "SELECT COALESCE(MAX(version),0) FROM schema_migrations;",
    ], timeout=5.0)
    expected = {
        "audit_evidence_index", "command_lifecycle", "device_enrollment_registry",
        "device_heartbeats", "device_supervisor_state", "projection_refresh_state",
    }
    observed = {line.strip() for line in table_output.splitlines() if line.strip()} if table_state == "ok" else set()
    try:
        revision = int(revision_output.strip()) if revision_state == "ok" else None
    except ValueError:
        revision = None
    journal = journal_output.strip().lower() if journal_state == "ok" else "unknown"
    if journal not in {"wal", "delete", "truncate", "persist", "memory", "off"}:
        journal = "unknown"
    integrity = "ok" if integrity_state == "ok" and integrity_output.strip().lower() == "ok" else "failed"
    return {
        "state": "ok" if integrity == "ok" and expected <= observed else "partial",
        "command_available": True,
        "database_present": True,
        "integrity": integrity,
        "journal_mode": journal,
        "expected_tables_present": expected <= observed,
        "schema_revision": revision,
    }


def proot_apps_probe(pm2: dict[str, Any], caddy: dict[str, Any]) -> dict[str, Any]:
    proot_present = command_exists("proot-distro")
    ubuntu_present = False
    if proot_present:
        state, output = run(["proot-distro", "list"], timeout=8.0)
        ubuntu_present = state == "ok" and bool(re.search(r"\bubuntu\b", output, re.I))
    online_names = {
        item["name"] for item in pm2.get("processes", [])
        if str(item.get("status", "")).lower() == "online"
    }
    photoprism_pm2 = "pocketlab-app-photoprism" in online_names
    photoprism_process = photoprism_pm2
    return {
        "state": "ok" if proot_present else "missing",
        "proot_present": proot_present,
        "ubuntu_present": ubuntu_present,
        "photoprism_present": photoprism_process,
        "photoprism_pm2_present": photoprism_pm2,
        "photoprism_route_present": bool(caddy.get("routes", {}).get("photoprism")),
    }


if tuple(item["id"] for item in PROBE_REGISTRY) != (
    "platform", "pm2", "caddy", "nats", "agent-supervisor", "tailscale", "sqlite", "proot-apps"
):
    raise SystemExit(76)

platform = platform_probe()
pm2 = pm2_probe()
caddy = caddy_probe()
nats = nats_probe(pm2)
agent = agent_supervisor_probe(pm2, nats)
tailscale = tailscale_probe()
sqlite = sqlite_probe()
proot_apps = proot_apps_probe(pm2, caddy)

payload = {
    "schema_revision": 1,
    "capture_kind": "termux-runtime",
    "sanitized": False,
    "source": "allowlisted-read-only-ssh-probe",
    "host_role": "server-phone",
    "probe_revision": 1,
    "capture_started_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    "capture_duration_ms": int((time.monotonic() - START) * 1000),
    "probes": {
        "platform": platform,
        "pm2": pm2,
        "caddy": caddy,
        "nats": nats,
        "agent_supervisor": agent,
        "tailscale": tailscale,
        "sqlite": sqlite,
        "proot_apps": proot_apps,
    },
}
encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
if len(encoded.encode("utf-8")) > MAX_CAPTURE_BYTES:
    raise SystemExit(75)
print(encoded, end="")
PY
