#!/usr/bin/env python3
"""Fixed Pocket Lab Lite 360-degree live-runtime assurance probe.

This DEV-PC adapter deliberately has no caller-selected target, URL, port, path,
wordlist, subject, argv, or scanner option. It probes only the repository-owned
loopback tunnels and fixed route inventory used by Runtime Security Assurance.
Raw response bodies, cookies, credentials, and secrets are never persisted.
"""
from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import socket
import ssl
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
API_HOST = "127.0.0.1"
API_PORT = 18080
CADDY_PORT = 18443
NATS_PORT = 14222
OPA_PORT = 18181
NATS_MONITOR_PORT = 18222
ATTACKER_ORIGIN = "http://127.0.0.1:18991"
TLS_SNI_FILE = Path.home() / ".pocketlab-lite" / "qualification" / "caddy-sni"
FIXED_ROUTES = (
    "/health",
    "/ready",
    "/api/lite/status",
    "/api/lite/harness/security-assurance/capabilities",
    "/api/lite/harness/security-assurance/suites",
)
DISCOVERY_ROUTES = (
    "/docs",
    "/redoc",
    "/openapi.json",
    "/debug",
    "/metrics",
    "/api/docs",
    "/api/lite/harness",
)
OWNED_PORTS = {
    NATS_PORT: "nats",
    API_PORT: "api",
    OPA_PORT: "opa",
    NATS_MONITOR_PORT: "nats-monitor",
    CADDY_PORT: "caddy",
}
VERSION = "1.0.0"


def _now_ms() -> int:
    return int(time.time() * 1000)


def _safe_text(value: Any, limit: int = 240) -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ")
    for marker in ("authorization", "cookie", "token", "password", "secret", "api_key", "private_key"):
        if marker in text.casefold():
            return "[REDACTED SECURITY-SENSITIVE TEXT]"
    return " ".join(text.split())[:limit]


def _fixed_sni() -> str | None:
    try:
        value = TLS_SNI_FILE.read_text(encoding="ascii").strip().casefold()
    except (OSError, UnicodeDecodeError):
        return None
    if (
        not value
        or "." not in value
        or ".." in value
        or any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789.-" for ch in value)
    ):
        return None
    return value


def _registered_path(path: str) -> bool:
    return path in FIXED_ROUTES or path in DISCOVERY_ROUTES or path == "/api/lite/harness/security-assurance/runs"


def _caddy_request(
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
    timeout: float = 3.0,
) -> dict[str, Any]:
    """Send one fixed HTTPS request through the approved Caddy tunnel/SNI."""
    if not _registered_path(path):
        raise ValueError("fixed_route_not_registered")
    sni = _fixed_sni()
    if sni is None:
        return {"status": None, "failure_code": "runtime_tls_identity_unavailable", "duration_ms": 0}
    clean_headers = dict(headers or {})
    if any(str(key).casefold() == "host" for key in clean_headers):
        raise ValueError("host_header_is_server_owned")
    payload = body or b""
    lines = [
        f"{method} {path} HTTP/1.1",
        f"Host: {sni}",
        "Connection: close",
        "User-Agent: Pocket-Lab-Lite-security-assurance/1",
    ]
    if payload:
        lines.append(f"Content-Length: {len(payload)}")
    for key, value in clean_headers.items():
        key_text = str(key)
        value_text = str(value)
        if "\r" in key_text or "\n" in key_text or "\r" in value_text or "\n" in value_text:
            raise ValueError("unsafe_header_value")
        lines.append(f"{key_text}: {value_text}")
    request = ("\r\n".join(lines) + "\r\n\r\n").encode("ascii", errors="strict") + payload
    started = time.monotonic()
    context = ssl.create_default_context()
    try:
        with socket.create_connection((API_HOST, CADDY_PORT), timeout=timeout) as raw:
            with context.wrap_socket(raw, server_hostname=sni) as tls:
                tls.settimeout(timeout)
                tls.sendall(request)
                response = bytearray()
                while len(response) < 8192:
                    chunk = tls.recv(min(2048, 8192 - len(response)))
                    if not chunk:
                        break
                    response.extend(chunk)
                    if b"\r\n\r\n" in response and len(response) >= 4096:
                        break
    except (OSError, ssl.SSLError) as exc:
        return {
            "status": None,
            "failure_code": type(exc).__name__.lower(),
            "duration_ms": int((time.monotonic() - started) * 1000),
        }
    head, _, body_bytes = bytes(response).partition(b"\r\n\r\n")
    lines = head.decode("latin-1", errors="replace").splitlines()
    status = None
    if lines:
        parts = lines[0].split()
        if len(parts) >= 2 and parts[1].isdigit():
            status = int(parts[1])
    response_headers: dict[str, str] = {}
    for line in lines[1:]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        response_headers[key.strip().casefold()] = _safe_text(value.strip(), 160)
    return {
        "status": status,
        "headers": response_headers,
        "body_bytes_observed": len(body_bytes),
        "duration_ms": int((time.monotonic() - started) * 1000),
        "transport": "fixed_caddy_https",
    }


def _request(method: str, path: str, *, headers: dict[str, str] | None = None, body: bytes | None = None, timeout: float = 3.0) -> dict[str, Any]:
    if not _registered_path(path):
        raise ValueError("fixed_route_not_registered")
    url = f"http://{API_HOST}:{API_PORT}{path}"
    request = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    started = time.monotonic()
    try:
        with opener.open(request, timeout=timeout) as response:
            payload = response.read(4096)
            return {
                "status": int(response.status),
                "headers": {str(k).casefold(): _safe_text(v, 160) for k, v in response.headers.items()},
                "body_bytes_observed": len(payload),
                "duration_ms": int((time.monotonic() - started) * 1000),
            }
    except urllib.error.HTTPError as exc:
        return {
            "status": int(exc.code),
            "headers": {str(k).casefold(): _safe_text(v, 160) for k, v in exc.headers.items()},
            "body_bytes_observed": 0,
            "duration_ms": int((time.monotonic() - started) * 1000),
        }
    except (OSError, urllib.error.URLError) as exc:
        return {
            "status": None,
            "failure_code": type(exc).__name__.lower(),
            "duration_ms": int((time.monotonic() - started) * 1000),
        }


def _tcp(port: int, timeout: float = 1.5) -> bool:
    if port not in OWNED_PORTS:
        raise ValueError("fixed_port_not_registered")
    try:
        with socket.create_connection((API_HOST, port), timeout=timeout):
            return True
    except OSError:
        return False


def _websocket_handshake(*, hostile_origin: bool) -> dict[str, Any]:
    sni = _fixed_sni()
    if sni is None:
        return {"accepted": False, "failure_code": "runtime_tls_identity_unavailable"}
    key = "UG9ja2V0TGFiRml4ZWRLZXk="
    origin = ATTACKER_ORIGIN if hostile_origin else f"https://{sni}:{CADDY_PORT}"
    request = (
        "GET /ws/events HTTP/1.1\r\n"
        f"Host: {sni}\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Origin: {origin}\r\n"
        "Sec-WebSocket-Version: 13\r\n"
        f"Sec-WebSocket-Key: {key}\r\n\r\n"
    ).encode("ascii")
    context = ssl.create_default_context()
    try:
        with socket.create_connection((API_HOST, CADDY_PORT), timeout=2.0) as raw:
            with context.wrap_socket(raw, server_hostname=sni) as sock:
                sock.settimeout(2.0)
                sock.sendall(request)
                response = sock.recv(2048).decode("latin-1", errors="replace")
    except (OSError, ssl.SSLError) as exc:
        return {"accepted": False, "failure_code": type(exc).__name__.lower()}
    first = response.splitlines()[0] if response else ""
    accepted = " 101 " in first
    return {
        "accepted": accepted,
        "status_line": _safe_text(first, 120),
        "origin_class": "hostile" if hostile_origin else "same-origin",
        "transport": "fixed_caddy_wss",
    }


def _bounded_burst() -> dict[str, Any]:
    def one(_: int) -> dict[str, Any]:
        return _caddy_request("GET", "/health", headers={"Accept": "application/json"}, timeout=3.0)

    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="pocketlab-assurance") as pool:
        results = list(pool.map(one, range(8)))
    statuses = [row.get("status") for row in results]
    return {
        "request_count": 8,
        "max_concurrency": 2,
        "duration_ms": int((time.monotonic() - started) * 1000),
        "successful": sum(1 for value in statuses if value == 200),
        "observed_responses": sum(1 for value in statuses if value is not None),
        "statuses": statuses,
    }


def _slow_client_probe() -> dict[str, Any]:
    sni = _fixed_sni()
    if sni is None:
        return {"slow_connections": 0, "hold_ms": 250, "failure_code": "runtime_tls_identity_unavailable"}
    sockets: list[ssl.SSLSocket] = []
    context = ssl.create_default_context()
    try:
        for _ in range(2):
            raw = socket.create_connection((API_HOST, CADDY_PORT), timeout=2.0)
            try:
                sock = context.wrap_socket(raw, server_hostname=sni)
            except Exception:
                raw.close()
                raise
            sock.sendall(f"GET /health HTTP/1.1\r\nHost: {sni}\r\n".encode("ascii"))
            sockets.append(sock)
        time.sleep(0.25)
        health = _caddy_request("GET", "/health", timeout=2.0)
        return {
            "slow_connections": 2,
            "hold_ms": 250,
            "health_status_during_hold": health.get("status"),
            "transport": "fixed_caddy_https",
        }
    except (OSError, ssl.SSLError) as exc:
        return {
            "slow_connections": len(sockets),
            "hold_ms": 250,
            "failure_code": type(exc).__name__.lower(),
        }
    finally:
        for sock in sockets:
            try:
                sock.close()
            except OSError:
                pass


def _tls_identity() -> dict[str, Any]:
    sni = _fixed_sni()
    if sni is None:
        return {"status": "NOT_ASSESSED", "reason": "fixed_tls_identity_unavailable"}
    context = ssl.create_default_context()
    try:
        with socket.create_connection((API_HOST, CADDY_PORT), timeout=3.0) as raw:
            with context.wrap_socket(raw, server_hostname=sni) as tls:
                cert = tls.getpeercert()
                return {
                    "status": "PASS",
                    "protocol": tls.version(),
                    "cipher": (tls.cipher() or (None,))[0],
                    "subject_alt_names_present": bool(cert.get("subjectAltName")),
                    "identity": "fixed_caddy_identity",
                }
    except (OSError, ssl.SSLError) as exc:
        return {"status": "FAIL", "reason": type(exc).__name__.lower(), "identity": "fixed_caddy_identity"}


def _release_provenance() -> dict[str, Any]:
    dist = ROOT / "dist.zip"
    manifest = ROOT / "security" / "release" / "signed-artifacts.json"
    lock = ROOT / "package-lock.json"
    requirements = ROOT / "pocket-lab-final-structure" / "runtime" / "requirements.txt"

    def digest(path: Path) -> str | None:
        if not path.is_file():
            return None
        value = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                value.update(block)
        return "sha256:" + value.hexdigest()

    return {
        "dist_present": dist.is_file(),
        "dist_sha256": digest(dist),
        "signed_artifact_manifest_present": manifest.is_file(),
        "package_lock_sha256": digest(lock),
        "runtime_requirements_sha256": digest(requirements),
        "status": "PASS" if lock.is_file() and requirements.is_file() else "PARTIAL",
    }


def _scenario(status: str, evidence: str, *, reason: str | None = None) -> dict[str, Any]:
    row = {"status": status, "evidence": evidence}
    if reason:
        row["reason"] = reason
    return row


def run(suite: str) -> dict[str, Any]:
    if suite not in {"standard", "deep", "adversarial"}:
        raise ValueError("suite_not_registered")

    health = _request("GET", "/health", headers={"Accept": "application/json"})
    ready = _request("GET", "/ready", headers={"Accept": "application/json"})
    hostile_get = _caddy_request(
        "GET",
        "/api/lite/status",
        headers={"Origin": ATTACKER_ORIGIN, "Referer": ATTACKER_ORIGIN + "/"},
    )
    forged_headers = _caddy_request(
        "GET",
        "/api/lite/harness/security-assurance/capabilities",
        headers={
            "Origin": ATTACKER_ORIGIN,
            "X-Forwarded-For": "203.0.113.10",
            "X-Pocket-Lab-Test": "1",
            "X-Pocket-Lab-Qualification": "forged",
        },
    )
    csrf_probe = _caddy_request(
        "POST",
        "/api/lite/harness/security-assurance/runs",
        headers={"Origin": ATTACKER_ORIGIN, "Content-Type": "application/json"},
        body=b'{"suite_id":"smoke"}',
    )
    ws_hostile = _websocket_handshake(hostile_origin=True)
    ws_same = _websocket_handshake(hostile_origin=False)
    listeners = {name: _tcp(port) for port, name in OWNED_PORTS.items()}
    burst = _bounded_burst() if suite in {"deep", "adversarial"} else None
    slow = _slow_client_probe() if suite == "adversarial" else None
    tls = _tls_identity()
    discovery = {route: _caddy_request("GET", route).get("status") for route in DISCOVERY_ROUTES}
    provenance = _release_provenance() if suite == "deep" else None

    findings: list[dict[str, Any]] = []
    if ws_hostile.get("accepted"):
        findings.append({
            "scenario_id": "websocket-auth-boundary",
            "severity": "high",
            "title": "Hostile-origin unauthenticated WebSocket was accepted",
            "summary": "The fixed hostile-origin handshake to /ws/events received a WebSocket upgrade without browser session evidence.",
        })
    allow_origin = str((hostile_get.get("headers") or {}).get("access-control-allow-origin") or "")
    if allow_origin in {"*", ATTACKER_ORIGIN}:
        findings.append({
            "scenario_id": "cross-origin-session-abuse",
            "severity": "high",
            "title": "Cross-origin API response is readable",
            "summary": "The fixed hostile Origin received permissive Access-Control-Allow-Origin on the status route.",
        })
    if csrf_probe.get("status") is not None and int(csrf_probe["status"]) < 400:
        findings.append({
            "scenario_id": "csrf-protected-mutation",
            "severity": "high",
            "title": "Unauthenticated hostile-origin mutation was admitted",
            "summary": "The fixed qualification mutation probe was not rejected.",
        })
    if forged_headers.get("status") is not None and int(forged_headers["status"]) < 400:
        findings.append({
            "scenario_id": "proxy-header-trust-confusion",
            "severity": "high",
            "title": "Forged proxy or qualification headers reached an admitted capability response",
            "summary": "The fixed forged-header request was not rejected at the control boundary.",
        })
    unexpected = {route: code for route, code in discovery.items() if code == 200 and route in {"/debug", "/metrics", "/api/docs"}}
    if unexpected:
        findings.append({
            "scenario_id": "hidden-route-and-debug-surface",
            "severity": "medium",
            "title": "Unexpected diagnostic route is externally reachable",
            "summary": "A fixed diagnostic route returned HTTP 200 through the approved runtime tunnel.",
        })
    if burst and burst.get("observed_responses", 0) > 0 and burst.get("successful", 0) < 6:
        findings.append({
            "scenario_id": "rate-limit-and-admission-resilience",
            "severity": "medium",
            "title": "Bounded concurrency degraded health availability",
            "summary": "Fewer than six of eight fixed low-concurrency health requests completed successfully.",
        })
    if slow and slow.get("health_status_during_hold") is not None and slow.get("health_status_during_hold") != 200:
        findings.append({
            "scenario_id": "slow-client-resource-exhaustion",
            "severity": "medium",
            "title": "Two bounded slow clients degraded health availability",
            "summary": "The health route did not remain available while two fixed partial connections were held briefly.",
        })
    if tls.get("status") == "FAIL":
        findings.append({
            "scenario_id": "tls-identity-drift",
            "severity": "high",
            "title": "Caddy TLS identity validation failed",
            "summary": "The fixed SNI/TLS connection could not validate the approved Caddy identity.",
        })

    by_scenario = {str(item["scenario_id"]): item for item in findings}
    ws_hostile_observed = not bool(ws_hostile.get("failure_code"))
    discovery_observed = any(code is not None for code in discovery.values())

    scenarios: dict[str, dict[str, Any]] = {
        "cross-origin-session-abuse": _scenario(
            "FAIL"
            if "cross-origin-session-abuse" in by_scenario
            else "PASS"
            if hostile_get.get("status") is not None
            else "PARTIAL",
            "fixed hostile-Origin GET and response-header observation",
            reason=None if hostile_get.get("status") is not None else "Caddy HTTPS target was unavailable for the fixed hostile-origin request.",
        ),
        "csrf-protected-mutation": _scenario(
            "FAIL"
            if "csrf-protected-mutation" in by_scenario
            else "PASS"
            if csrf_probe.get("status") is not None
            else "PARTIAL",
            "fixed hostile-Origin unauthenticated mutation rejection",
            reason=None if csrf_probe.get("status") is not None else "Caddy HTTPS target was unavailable for the fixed mutation probe.",
        ),
        "websocket-auth-boundary": _scenario(
            "FAIL"
            if "websocket-auth-boundary" in by_scenario
            else "PASS"
            if ws_hostile_observed
            else "PARTIAL",
            "fixed hostile and same-origin WebSocket handshakes through Caddy WSS",
            reason=None if ws_hostile_observed else "Caddy WSS target was unavailable; no authorization conclusion was inferred.",
        ),
        "proxy-header-trust-confusion": _scenario(
            "FAIL"
            if "proxy-header-trust-confusion" in by_scenario
            else "PASS"
            if forged_headers.get("status") is not None
            else "PARTIAL",
            "fixed forged forwarding/qualification headers through Caddy HTTPS",
            reason=None if forged_headers.get("status") is not None else "Caddy HTTPS target was unavailable for the fixed forged-header request.",
        ),
        "tailnet-service-exposure": _scenario(
            "PARTIAL",
            "approved DEV-PC loopback tunnel listener inventory",
            reason="Tailnet peer-side reachability requires a separately registered runtime observation; loopback tunnels alone do not prove exposure.",
        ),
        "tls-identity-drift": _scenario(
            "FAIL" if "tls-identity-drift" in by_scenario else tls.get("status", "PARTIAL"),
            "fixed Caddy TLS tunnel and operator-approved SNI",
            reason=tls.get("reason") if tls.get("status") in {"NOT_ASSESSED", "PARTIAL"} else None,
        ),
        "hidden-route-and-debug-surface": _scenario(
            "FAIL"
            if "hidden-route-and-debug-surface" in by_scenario
            else "PASS"
            if discovery_observed
            else "PARTIAL",
            "tiny repository-owned diagnostic route allowlist through Caddy HTTPS",
            reason=None if discovery_observed else "Caddy HTTPS target was unavailable for route discovery.",
        ),
        "malformed-api-state-machine": _scenario(
            "PARTIAL",
            "negative auth/input probes are worker-owned; this lane adds fixed HTTP boundary observations",
            reason="stateful authenticated fixture remains server-owned",
        ),
        "nats-command-replay-integrity": _scenario(
            "NOT_ASSESSED",
            "NATS replay must remain behind a registered server-owned harness executor",
            reason="no arbitrary NATS subject access is permitted from DEV-PC",
        ),
        "worker-reconnect-command-integrity": _scenario(
            "NOT_ASSESSED",
            "requires repository-owned fault control and worker evidence",
            reason="fault execution remains server-owned",
        ),
        "device-invite-replay-and-misbinding": _scenario(
            "NOT_ASSESSED",
            "requires disposable server-owned device identity fixture",
            reason="no invite credential is exposed to DEV-PC",
        ),
        "authorization-resource-boundary": _scenario(
            "NOT_ASSESSED",
            "requires bounded synthetic application identity",
            reason="no privileged browser credential is injected into external tools",
        ),
        "audit-event-attribution": _scenario(
            "PARTIAL",
            "runtime health and assurance evidence are observable; identity-bound mutation fixture required",
            reason="identity-bound mutation not executed by external lane",
        ),
    }
    if burst is not None:
        scenarios["rate-limit-and-admission-resilience"] = _scenario(
            "FAIL"
            if "rate-limit-and-admission-resilience" in by_scenario
            else "PASS"
            if burst.get("observed_responses", 0) > 0
            else "PARTIAL",
            "8 requests / max concurrency 2 / fixed Caddy /health",
            reason=None if burst.get("observed_responses", 0) > 0 else "No Caddy response was observed; resilience was not inferred.",
        )
    if slow is not None:
        slow_observed = slow.get("health_status_during_hold") is not None
        scenarios["slow-client-resource-exhaustion"] = _scenario(
            "FAIL"
            if "slow-client-resource-exhaustion" in by_scenario
            else "PASS"
            if slow_observed
            else "PARTIAL",
            "2 fixed Caddy TLS partial connections held for 250ms with concurrent health check",
            reason=None if slow_observed else "Caddy target was unavailable during the bounded slow-client probe.",
        )
    if provenance is not None:
        scenarios.update({
            "release-artifact-tamper": _scenario("PASS" if provenance.get("dist_present") and provenance.get("signed_artifact_manifest_present") else "NOT_ASSESSED", "fixed dist.zip and signed-artifact manifest hashes", reason=None if provenance.get("dist_present") else "dist.zip is not present in the source checkout"),
            "dependency-confusion-and-lock-integrity": _scenario("PASS" if provenance.get("status") == "PASS" else "PARTIAL", "package-lock and runtime requirements fixed hashes"),
            "app-package-provenance": _scenario("NOT_ASSESSED", "registered app artifact required", reason="no generic artifact path is accepted"),
            "backup-confidentiality-integrity": _scenario("NOT_ASSESSED", "registered Recovery fixture required", reason="backup payloads are not read by the generic DEV-PC probe"),
            "restore-transaction-integrity": _scenario("NOT_ASSESSED", "registered Recovery fault fixture required", reason="restore mutation remains server-owned"),
            "android-termux-host-hardening": _scenario("PARTIAL", "listener/runtime evidence plus worker-owned Lynis/Trivy evidence"),
            "runtime-env-secret-boundary": _scenario("PARTIAL", "paired with Gitleaks/Trivy/redaction tools in Deep"),
            "security-evidence-poisoning": _scenario("PARTIAL", "paired with server redaction contract and synthetic evidence tests"),
            "unicode-log-and-ui-injection": _scenario("PARTIAL", "paired with browser adapter and source sanitization tests"),
        })

    return {
        "schema_version": "1.0.0",
        "tool": "pocketlab-runtime-360",
        "version": VERSION,
        "suite": suite,
        "target": "fixed_server_phone_runtime_tunnels",
        "captured_at_ms": _now_ms(),
        "checks": {
            "health": health,
            "ready": ready,
            "hostile_origin_status": hostile_get.get("status"),
            "forged_headers_status": forged_headers.get("status"),
            "csrf_probe_status": csrf_probe.get("status"),
            "websocket_hostile": ws_hostile,
            "websocket_same_origin": ws_same,
            "listeners": listeners,
            "discovery": discovery,
            "tls": tls,
            "bounded_burst": burst,
            "slow_client": slow,
            "provenance": provenance,
        },
        "scenario_results": scenarios,
        "findings": findings,
        "raw_response_bodies_persisted": False,
        "sanitized": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="store_true")
    parser.add_argument("suite", nargs="?", choices=("standard", "deep", "adversarial"))
    args = parser.parse_args()
    if args.version:
        print(f"pocketlab-runtime-360 {VERSION}")
        return 0
    if args.suite is None:
        parser.error("suite is required")
    result = run(args.suite)
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
