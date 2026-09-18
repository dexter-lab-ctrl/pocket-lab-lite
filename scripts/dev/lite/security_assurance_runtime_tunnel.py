#!/usr/bin/env python3
"""Create only fixed DEV-PC to Server Phone Runtime Security Assurance tunnels.

The caller cannot supply an SSH host, user, port, forward, URL, target, SNI, or
remote command. Discovery starts from the already managed pocketlab-termux SSH
alias. The connected phone reports the actual SSH server endpoint through
SSH_CONNECTION and its active Tailnet IPv4 through tailscale-cli/tailscale.
"""
from __future__ import annotations

import argparse
import contextlib
import ipaddress
import json
import os
import re
import socket
import ssl
import stat
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping

SSH = Path("/usr/bin/ssh")
SSH_ALIAS = "pocketlab-termux"
STATE_FILE = Path.home() / ".pocketlab-lite" / "qualification" / "runtime-tunnel.json"
SNI_FILE = Path.home() / ".pocketlab-lite" / "qualification" / "caddy-sni"
TAILNET = ipaddress.ip_network("100.64.0.0/10")
PRIVATE_V4 = tuple(ipaddress.ip_network(v) for v in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))
TAILSCALE_DNS = re.compile(r"[a-z0-9-]+(?:\.[a-z0-9-]+)*\.ts\.net", re.I)
USER_RE = re.compile(r"[A-Za-z0-9._-]{1,64}")
SNI_RE = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9.-]{0,252}[A-Za-z0-9])?")
LOCAL_FORWARD_MAP = {
    14222: ("127.0.0.1", 4222),
    18080: ("127.0.0.1", 8080),
    18181: ("127.0.0.1", 8181),
    18222: ("127.0.0.1", 8222),
}
CADDY_LOCAL_PORT = 18443
CADDY_REMOTE_PORT = 443
API_HEALTH = "http://127.0.0.1:18080/health"
VERSION = "1.0.0"

REMOTE_DISCOVERY = r"""set -eu
case "${PREFIX:-}" in
  /data/data/com.termux/files/usr) ;;
  *) exit 73 ;;
esac
ts=""
if command -v tailscale-cli >/dev/null 2>&1; then
  ts="$(tailscale-cli ip -4 2>/dev/null | head -n 1 || true)"
elif command -v tailscale >/dev/null 2>&1; then
  ts="$(tailscale ip -4 2>/dev/null | head -n 1 || true)"
fi
printf 'TERMUX_OK=1\n'
printf 'SSH_CONNECTION=%s\n' "${SSH_CONNECTION:-}"
printf 'REMOTE_USER=%s\n' "$(id -un)"
printf 'TAILSCALE_IPV4=%s\n' "$ts"
"""


class RuntimeTunnelError(RuntimeError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _run(argv: list[str], *, timeout: int = 12) -> subprocess.CompletedProcess[str]:
    if not SSH.is_file():
        raise RuntimeTunnelError("runtime_ssh_client_unavailable")
    try:
        return subprocess.run(
            argv,
            check=False,
            shell=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=max(1, timeout),
            env={"PATH": "/usr/bin:/bin", "HOME": str(Path.home()), "LC_ALL": "C", "LANG": "C"},
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeTunnelError("runtime_ssh_command_failed") from exc


def _safe_ssh_host(value: str) -> bool:
    candidate = str(value or "").strip().rstrip(".")
    if not candidate:
        return False
    try:
        address = ipaddress.ip_address(candidate)
    except ValueError:
        return bool(TAILSCALE_DNS.fullmatch(candidate))
    return isinstance(address, ipaddress.IPv4Address) and (
        address in TAILNET or any(address in network for network in PRIVATE_V4)
    )


def _ssh_config() -> dict[str, str]:
    result = _run([str(SSH), "-G", SSH_ALIAS], timeout=5)
    if result.returncode != 0:
        raise RuntimeTunnelError("runtime_ssh_alias_unavailable")
    config: dict[str, str] = {}
    for raw in result.stdout.splitlines():
        parts = raw.strip().split(None, 1)
        if len(parts) == 2 and parts[0].casefold() not in config:
            config[parts[0].casefold()] = parts[1].strip()
    if not _safe_ssh_host(config.get("hostname", "")):
        raise RuntimeTunnelError("runtime_ssh_alias_host_not_private")
    if not USER_RE.fullmatch(config.get("user", "")):
        raise RuntimeTunnelError("runtime_ssh_alias_user_invalid")
    port = config.get("port", "")
    if not port.isdigit() or not 1 <= int(port) <= 65535:
        raise RuntimeTunnelError("runtime_ssh_alias_port_invalid")
    required = {
        "batchmode": "yes",
        "passwordauthentication": "no",
        "kbdinteractiveauthentication": "no",
        "stricthostkeychecking": "yes",
        "identitiesonly": "yes",
    }
    if any(config.get(k, "").casefold() != v for k, v in required.items()):
        raise RuntimeTunnelError("runtime_ssh_alias_policy_unsafe")
    known_hosts = config.get("userknownhostsfile", "")
    if not known_hosts or known_hosts.casefold() in {"/dev/null", "none"}:
        raise RuntimeTunnelError("runtime_ssh_alias_hostkey_store_invalid")
    return config


def _safe_server_ipv4(value: str) -> str:
    try:
        address = ipaddress.ip_address(str(value or "").strip())
    except ValueError as exc:
        raise RuntimeTunnelError("runtime_ssh_server_ip_invalid") from exc
    if not isinstance(address, ipaddress.IPv4Address):
        raise RuntimeTunnelError("runtime_ssh_server_ip_invalid")
    if address not in TAILNET and not any(address in network for network in PRIVATE_V4):
        raise RuntimeTunnelError("runtime_ssh_server_ip_not_private")
    return str(address)


def _tailnet_ipv4(value: str) -> str:
    try:
        address = ipaddress.ip_address(str(value or "").strip())
    except ValueError as exc:
        raise RuntimeTunnelError("runtime_tailscale_ipv4_invalid") from exc
    if not isinstance(address, ipaddress.IPv4Address) or address not in TAILNET:
        raise RuntimeTunnelError("runtime_tailscale_ipv4_invalid")
    return str(address)


def _approved_sni() -> str:
    try:
        details = SNI_FILE.lstat()
        if not stat.S_ISREG(details.st_mode) or stat.S_ISLNK(details.st_mode):
            raise RuntimeTunnelError("runtime_tls_identity_unavailable")
        if details.st_mode & 0o022:
            raise RuntimeTunnelError("runtime_tls_identity_permissions_unsafe")
        value = SNI_FILE.read_text(encoding="ascii").strip().casefold()
    except RuntimeTunnelError:
        raise
    except (OSError, UnicodeDecodeError) as exc:
        raise RuntimeTunnelError("runtime_tls_identity_unavailable") from exc
    if not SNI_RE.fullmatch(value) or "." not in value or ".." in value:
        raise RuntimeTunnelError("runtime_tls_identity_invalid")
    return value


def _parse_runtime_facts(output: str, config: Mapping[str, str], *, caddy_sni: str) -> dict[str, Any]:
    rows: dict[str, str] = {}
    for line in str(output or "").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            rows[key.strip()] = value.strip()
    if rows.get("TERMUX_OK") != "1":
        raise RuntimeTunnelError("runtime_termux_identity_unverified")
    connection = rows.get("SSH_CONNECTION", "").split()
    if len(connection) != 4:
        raise RuntimeTunnelError("runtime_ssh_connection_unavailable")
    server_ip = _safe_server_ipv4(connection[2])
    server_port = connection[3]
    if not server_port.isdigit() or not 1 <= int(server_port) <= 65535:
        raise RuntimeTunnelError("runtime_ssh_server_port_invalid")
    remote_user = rows.get("REMOTE_USER", "")
    if not USER_RE.fullmatch(remote_user):
        raise RuntimeTunnelError("runtime_ssh_remote_user_invalid")
    if remote_user != config.get("user"):
        raise RuntimeTunnelError("runtime_ssh_user_mismatch")
    if int(server_port) != int(config.get("port", "0")):
        raise RuntimeTunnelError("runtime_ssh_port_mismatch")
    tailscale_ip = _tailnet_ipv4(rows.get("TAILSCALE_IPV4", ""))
    return {
        "schema_version": "1.0.0",
        "captured_at": _utc_now(),
        "ssh_alias": SSH_ALIAS,
        "server_phone_ip": server_ip,
        "ssh_server_port": int(server_port),
        "ssh_user": remote_user,
        "tailscale_ipv4": tailscale_ip,
        "caddy_sni": caddy_sni,
        "server_phone_ip_source": "SSH_CONNECTION",
        "tailscale_ipv4_source": "tailscale_runtime_ip4",
        "caddy_sni_source": "operator_approved_local_marker",
    }


def discover_runtime_facts() -> tuple[dict[str, Any], dict[str, str]]:
    config = _ssh_config()
    result = _run([
        str(SSH),
        "-o", "BatchMode=yes",
        "-o", "PasswordAuthentication=no",
        "-o", "KbdInteractiveAuthentication=no",
        "-o", "StrictHostKeyChecking=yes",
        "-o", "ConnectTimeout=8",
        "-o", "ConnectionAttempts=1",
        "-o", "ProxyCommand=none",
        "-o", "ProxyJump=none",
        "-o", "IdentitiesOnly=yes",
        "-o", "PreferredAuthentications=publickey",
        "-o", "PermitLocalCommand=no",
        SSH_ALIAS,
        REMOTE_DISCOVERY,
    ])
    if result.returncode != 0:
        raise RuntimeTunnelError("runtime_fact_discovery_failed")
    return _parse_runtime_facts(result.stdout, config, caddy_sni=_approved_sni()), config


def build_tunnel_argv(facts: Mapping[str, Any], config: Mapping[str, str]) -> list[str]:
    server_ip = _safe_server_ipv4(str(facts.get("server_phone_ip") or ""))
    tailscale_ip = _tailnet_ipv4(str(facts.get("tailscale_ipv4") or ""))
    server_port = int(facts.get("ssh_server_port") or 0)
    remote_user = str(facts.get("ssh_user") or "")
    host_key_alias = str(config.get("hostname") or "")
    if not 1 <= server_port <= 65535 or not USER_RE.fullmatch(remote_user):
        raise RuntimeTunnelError("runtime_tunnel_facts_invalid")
    if not _safe_ssh_host(host_key_alias):
        raise RuntimeTunnelError("runtime_ssh_hostkey_alias_invalid")
    argv = [
        str(SSH), "-N",
        "-o", "BatchMode=yes",
        "-o", "PasswordAuthentication=no",
        "-o", "KbdInteractiveAuthentication=no",
        "-o", "StrictHostKeyChecking=yes",
        "-o", "ExitOnForwardFailure=yes",
        "-o", "ConnectTimeout=8",
        "-o", "ConnectionAttempts=1",
        "-o", "ProxyCommand=none",
        "-o", "ProxyJump=none",
        "-o", "IdentitiesOnly=yes",
        "-o", "PreferredAuthentications=publickey",
        "-o", "PermitLocalCommand=no",
        "-o", f"Hostname={server_ip}",
        "-o", f"HostKeyAlias={host_key_alias}",
        "-p", str(server_port),
        "-l", remote_user,
    ]
    for local_port, (remote_host, remote_port) in LOCAL_FORWARD_MAP.items():
        argv.extend(["-L", f"127.0.0.1:{local_port}:{remote_host}:{remote_port}"])
    argv.extend(["-L", f"127.0.0.1:{CADDY_LOCAL_PORT}:{tailscale_ip}:{CADDY_REMOTE_PORT}"])
    argv.append(SSH_ALIAS)
    return argv


def _port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", int(port)), timeout=0.4):
            return True
    except OSError:
        return False


def _api_ready() -> bool:
    request = urllib.request.Request(API_HEALTH, headers={"Accept": "application/json"})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=2.0) as response:
            return int(response.status) == 200
    except (OSError, urllib.error.URLError, urllib.error.HTTPError):
        return False


def _tls_ready(sni: str) -> bool:
    context = ssl.create_default_context()
    try:
        with socket.create_connection(("127.0.0.1", CADDY_LOCAL_PORT), timeout=2.0) as raw:
            with context.wrap_socket(raw, server_hostname=sni) as tls:
                return bool(tls.version())
    except (OSError, ssl.SSLError):
        return False


def _write_state(facts: Mapping[str, Any], *, created_by_harness: bool, pid: int | None) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(STATE_FILE.parent, 0o700)
    payload = {
        **dict(facts),
        "created_by_harness": bool(created_by_harness),
        "ssh_pid": int(pid) if pid else None,
        "active": True,
        "local_forward_ports": [*LOCAL_FORWARD_MAP.keys(), CADDY_LOCAL_PORT],
    }
    encoded = (json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n").encode("utf-8")
    temporary = STATE_FILE.with_name(f".{STATE_FILE.name}.{os.getpid()}.tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(fd, encoded)
        os.fchmod(fd, 0o600)
    finally:
        os.close(fd)
    os.replace(temporary, STATE_FILE)
    os.chmod(STATE_FILE, 0o600)


def sanitized_tunnel_summary(state: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "status": "READY",
        "source": "managed_termux_runtime_discovery",
        "server_phone_ip_source": "SSH_CONNECTION",
        "tailscale_ipv4_source": "tailscale_runtime_ip4",
        "caddy_sni_source": "operator_approved_local_marker",
        "runtime_addresses_available": bool(state.get("server_phone_ip") and state.get("tailscale_ipv4")),
        "caddy_sni_approved": bool(state.get("caddy_sni")),
        "forward_count": len(LOCAL_FORWARD_MAP) + 1,
        "created_by_harness": bool(state.get("created_by_harness")),
        "raw_addresses_persisted_in_assurance_evidence": False,
        "sanitized": True,
    }


@contextlib.contextmanager
def fixed_runtime_tunnel() -> Iterator[dict[str, Any]]:
    facts, config = discover_runtime_facts()
    ports = [*LOCAL_FORWARD_MAP.keys(), CADDY_LOCAL_PORT]
    occupied = [port for port in ports if _port_open(port)]
    process: subprocess.Popen[bytes] | None = None
    created = False
    try:
        if occupied:
            if len(occupied) != len(ports) or not _api_ready() or not _tls_ready(str(facts["caddy_sni"])):
                raise RuntimeTunnelError("runtime_fixed_port_collision")
        else:
            process = subprocess.Popen(
                build_tunnel_argv(facts, config),
                shell=False,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
                env={"PATH": "/usr/bin:/bin", "HOME": str(Path.home()), "LC_ALL": "C", "LANG": "C"},
            )
            created = True
            deadline = time.monotonic() + 10.0
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeTunnelError("runtime_tunnel_exited_early")
                if all(_port_open(port) for port in ports) and _api_ready() and _tls_ready(str(facts["caddy_sni"])):
                    break
                time.sleep(0.15)
            else:
                raise RuntimeTunnelError("runtime_tunnel_readiness_failed")
        state = {**facts, "created_by_harness": created}
        _write_state(state, created_by_harness=created, pid=process.pid if process else None)
        yield state
    finally:
        try:
            STATE_FILE.unlink()
        except FileNotFoundError:
            pass
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="store_true")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("check")
    sub.add_parser("hold")
    args = parser.parse_args(argv)
    if args.version:
        print(f"pocketlab-security-assurance-runtime-tunnel {VERSION}")
        return 0
    if args.command == "check":
        facts, _ = discover_runtime_facts()
        print(json.dumps({"status": "READY", **sanitized_tunnel_summary(facts)}, sort_keys=True))
        return 0
    if args.command == "hold":
        try:
            with fixed_runtime_tunnel() as state:
                print(json.dumps(sanitized_tunnel_summary(state), sort_keys=True), flush=True)
                while True:
                    time.sleep(30)
        except KeyboardInterrupt:
            return 0
    parser.error("a fixed command is required")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
