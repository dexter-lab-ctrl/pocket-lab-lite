#!/usr/bin/env python3
"""Serve an exact-branch Lite candidate through the fixed Caddy tunnel.

This server is qualification-only.  It binds to DEV-PC loopback, serves one
already-built ``dist`` tree, exposes a non-secret candidate manifest, and
proxies only read-oriented ``/api/lite/*`` requests to the Server Phone's
loopback Caddy listener through the checked-in SSH tunnel.  Harness authority
is never proxied through this server; the browser bridge is a short-lived
request header consumed by normal FastAPI authorization on the remote side.
"""
from __future__ import annotations

import argparse
import http.client
import json
import mimetypes
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from security_assurance_runtime_tunnel import (  # noqa: E402
    CADDY_HTTP_LOCAL_PORT,
    RuntimeTunnelError,
    ui_performance_runtime_tunnel,
)


CANDIDATE_HOST = "127.0.0.1"
CANDIDATE_PORT = 18765
CANDIDATE_MANIFEST_PATH = "/__pocketlab_qualification__/candidate.json"
CANDIDATE_HEALTH_PATH = "/__pocketlab_qualification__/health"
BRIDGE_HEADER = "X-Pocket-Lab-Qualification-Bridge"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
MAX_BRIDGE_HEADER_BYTES = 4096
MAX_PROXY_RESPONSE_BYTES = 32 * 1024 * 1024
READ_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
HOP_BY_HOP_HEADERS = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailer",
        "transfer-encoding",
        "upgrade",
    }
)


class CandidateServerError(RuntimeError):
    """Raised when a candidate cannot be served fail-closed."""


def exact_source_commit(value: str | None = None) -> str:
    candidate = str(value or os.environ.get("LITE_PERF_SOURCE_COMMIT") or "").strip().lower()
    if not candidate:
        try:
            candidate = subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                cwd=REPO_ROOT,
                text=True,
                stderr=subprocess.DEVNULL,
            ).strip().lower()
        except (OSError, subprocess.CalledProcessError) as exc:
            raise CandidateServerError("candidate_source_commit_unavailable") from exc
    if not SHA_RE.fullmatch(candidate) or candidate == "0" * 40:
        raise CandidateServerError("candidate_source_commit_invalid")
    return candidate


def candidate_manifest(source_commit: str) -> dict[str, Any]:
    commit = exact_source_commit(source_commit)
    return {
        "schema_version": "1.0.0",
        "source_commit": commit,
        "build_timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "performance_schema_version": "1.0.0",
        "qualification_surface": "devpc_candidate_loopback",
        "runtime_transport": "ssh_loopback_to_server_phone_caddy",
        "browser_secret_persisted": False,
        "sanitized": True,
    }


def is_allowed_api_path(path: str) -> bool:
    parsed = urlsplit(str(path or ""))
    pathname = parsed.path
    if not pathname.startswith("/api/lite/"):
        return False
    # The direct-loopback harness namespace is never a browser-facing proxy.
    return not (pathname == "/api/lite/harness" or pathname.startswith("/api/lite/harness/"))


def safe_dist_file(dist_root: Path, request_path: str) -> Path | None:
    parsed = urlsplit(str(request_path or "/"))
    relative = parsed.path.lstrip("/") or "index.html"
    if "\\" in relative or "\x00" in relative:
        return None
    root = dist_root.resolve()
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    if candidate.is_symlink() or not candidate.is_file():
        return None
    return candidate


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


class CandidateRequestHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"
    server_version = "PocketLabLiteCandidate/1.0"

    @property
    def dist_root(self) -> Path:
        return self.server.dist_root  # type: ignore[attr-defined]

    @property
    def source_commit(self) -> str:
        return self.server.source_commit  # type: ignore[attr-defined]

    def log_message(self, _format: str, *_args: object) -> None:
        # Do not log request paths or headers.  Qualification browser headers
        # are deliberately process-only and must not enter terminal evidence.
        return

    def _send_bytes(self, status: int, body: bytes, *, content_type: str, cache_control: str = "no-store") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache_control)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Pocket-Lab-Candidate-SHA", self.source_commit)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _send_error_json(self, status: int, reason: str) -> None:
        self._send_bytes(status, _json_bytes({"status": "error", "reason": reason, "sanitized": True}), content_type="application/json")

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Allow", "GET, HEAD, OPTIONS")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def do_HEAD(self) -> None:  # noqa: N802
        self._dispatch()

    def do_GET(self) -> None:  # noqa: N802
        self._dispatch()

    def do_POST(self) -> None:  # noqa: N802
        self._send_error_json(405, "candidate_read_only")

    do_PUT = do_POST
    do_PATCH = do_POST
    do_DELETE = do_POST

    def _dispatch(self) -> None:
        path = urlsplit(self.path).path
        if path == CANDIDATE_MANIFEST_PATH:
            self._send_bytes(200, _json_bytes(candidate_manifest(self.source_commit)), content_type="application/json")
            return
        if path == CANDIDATE_HEALTH_PATH:
            self._send_bytes(200, _json_bytes({"status": "ready", "source_commit": self.source_commit, "sanitized": True}), content_type="application/json")
            return
        if path == "/api/lite/harness" or path.startswith("/api/lite/harness/"):
            self._send_error_json(404, "browser_harness_route_not_available")
            return
        if is_allowed_api_path(self.path):
            self._proxy_api()
            return
        if path.startswith("/api/"):
            self._send_error_json(404, "candidate_api_route_not_available")
            return
        self._serve_static()

    def _proxy_api(self) -> None:
        bridge = self.headers.get(BRIDGE_HEADER, "")
        if len(bridge.encode("utf-8", "ignore")) > MAX_BRIDGE_HEADER_BYTES or "\r" in bridge or "\n" in bridge:
            self._send_error_json(400, "qualification_bridge_invalid")
            return

        headers = {"Accept": self.headers.get("Accept", "application/json")[:256]}
        for name in ("Cache-Control", "If-None-Match", "Last-Event-ID"):
            value = self.headers.get(name)
            if value:
                headers[name] = value[:512]
        if bridge:
            headers[BRIDGE_HEADER] = bridge
        try:
            connection = http.client.HTTPConnection("127.0.0.1", CADDY_HTTP_LOCAL_PORT, timeout=20)
            connection.request(self.command, self.path, headers=headers)
            response = connection.getresponse()
            self.send_response(response.status, response.reason)
            for name, value in response.getheaders():
                if name.casefold() in HOP_BY_HOP_HEADERS:
                    continue
                if name.casefold() in {"set-cookie", "location"}:
                    # The candidate never adopts remote cookies or redirects.
                    continue
                self.send_header(name, value)
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Pocket-Lab-Candidate-SHA", self.source_commit)
            self.end_headers()
            if self.command != "HEAD":
                remaining = 0
                while True:
                    chunk = response.read(64 * 1024)
                    if not chunk:
                        break
                    remaining += len(chunk)
                    if remaining > MAX_PROXY_RESPONSE_BYTES:
                        raise CandidateServerError("candidate_api_response_too_large")
                    self.wfile.write(chunk)
        except (CandidateServerError, OSError, http.client.HTTPException):
            if not self.wfile.closed:
                try:
                    self._send_error_json(502, "candidate_runtime_unavailable")
                except OSError:
                    pass
        finally:
            try:
                connection.close()
            except UnboundLocalError:
                pass

    def _serve_static(self) -> None:
        file_path = safe_dist_file(self.dist_root, self.path)
        if file_path is None:
            parsed = urlsplit(self.path)
            if parsed.path.startswith("/__pocketlab_qualification__/"):
                self._send_error_json(404, "candidate_qualification_route_not_available")
                return
            file_path = safe_dist_file(self.dist_root, "/index.html")
        if file_path is None:
            self._send_error_json(503, "candidate_dist_unavailable")
            return
        try:
            body = file_path.read_bytes()
        except OSError:
            self._send_error_json(503, "candidate_dist_unavailable")
            return
        content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        cache_control = "no-store" if file_path.name == "index.html" else "public, max-age=0, must-revalidate"
        self._send_bytes(200, body, content_type=content_type, cache_control=cache_control)


def serve_candidate(dist_dir: Path, source_commit: str) -> None:
    root = dist_dir.resolve()
    index = root / "index.html"
    if not root.is_dir() or not index.is_file():
        raise CandidateServerError("candidate_dist_unavailable")
    html = index.read_text(encoding="utf-8")
    marker = f'name="pocketlab-candidate-sha" content="{source_commit}"'
    if marker not in html:
        raise CandidateServerError("candidate_dist_sha_mismatch")

    server = ThreadingHTTPServer((CANDIDATE_HOST, CANDIDATE_PORT), CandidateRequestHandler)
    server.dist_root = root  # type: ignore[attr-defined]
    server.source_commit = source_commit  # type: ignore[attr-defined]
    print(
        json.dumps(
            {
                "status": "READY",
                "bind": f"{CANDIDATE_HOST}:{CANDIDATE_PORT}",
                "source_commit": source_commit,
                "runtime_transport": "ssh_loopback_to_server_phone_caddy",
                "browser_secret_persisted": False,
                "sanitized": True,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    try:
        server.serve_forever(poll_interval=0.2)
    finally:
        server.server_close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist-dir", default=str(REPO_ROOT / "dist"))
    parser.add_argument("--source-commit", default="")
    args = parser.parse_args(argv)
    try:
        commit = exact_source_commit(args.source_commit)
        with ui_performance_runtime_tunnel():
            serve_candidate(Path(args.dist_dir), commit)
    except KeyboardInterrupt:
        return 0
    except (CandidateServerError, RuntimeTunnelError) as exc:
        print(f"[ui-performance-candidate] ERROR {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
