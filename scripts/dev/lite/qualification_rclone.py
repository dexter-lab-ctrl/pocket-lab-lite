#!/usr/bin/env python3
"""Small WebDAV-only rclone test double for the isolated qualification lane.

The candidate node agent still executes its normal ``rclone`` command path.
This helper is used only when a real rclone binary is not deliberately
selected.  It speaks the HTTPS WebDAV protocol against the loopback fixture,
keeps all configuration inside the run root, and never prints credentials.
"""
from __future__ import annotations

import argparse
import base64
import configparser
import hashlib
import json
import os
import ssl
import stat
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path


def _error(message: str) -> int:
    print(message[:160], file=sys.stderr)
    return 1


def _config(path: str) -> tuple[str, str, str]:
    cfg = configparser.ConfigParser()
    cfg.read(path, encoding="utf-8")
    if not cfg.has_section("photoprism"):
        raise ValueError("qualification rclone config missing remote")
    section = cfg["photoprism"]
    url = str(section.get("url") or "").strip().rstrip("/")
    user = str(section.get("user") or "").strip()
    obscured = str(section.get("pass") or "").strip()
    if not url.startswith("https://") or not user or not obscured:
        raise ValueError("qualification rclone config is incomplete")
    try:
        password = base64.urlsafe_b64decode(obscured.encode("ascii") + b"===").decode("utf-8")
    except Exception as exc:
        raise ValueError("qualification rclone credential encoding is invalid") from exc
    parsed = urllib.parse.urlsplit(url)
    if parsed.hostname not in {"127.0.0.1", "::1", "localhost"} or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("qualification rclone origin is not an HTTPS loopback origin")
    return url, user, password


def _ssl_context() -> ssl.SSLContext:
    ca = os.environ.get("SSL_CERT_FILE", "").strip()
    return ssl.create_default_context(cafile=ca or None)


def _url(base: str, remote: str) -> str:
    if not remote.startswith("photoprism:"):
        raise ValueError("qualification rclone remote is invalid")
    relative = remote.split(":", 1)[1].lstrip("/")
    if ".." in Path(relative).parts:
        raise ValueError("qualification rclone path traversal rejected")
    encoded = "/".join(urllib.parse.quote(part, safe="") for part in relative.split("/"))
    return f"{base}/{encoded}" if encoded else f"{base}/"


def _request(
    method: str,
    url: str,
    user: str,
    password: str,
    *,
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, bytes, dict[str, str]]:
    request_headers = {"Authorization": "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()}
    request_headers.update(headers or {})
    request = urllib.request.Request(url, data=body, headers=request_headers, method=method)
    with urllib.request.urlopen(request, timeout=20, context=_ssl_context()) as response:
        return int(response.status), response.read(), dict(response.headers.items())


def _parse_propfind(payload: bytes) -> dict[str, object]:
    root = ET.fromstring(payload)
    size = -1
    modified = ""
    for elem in root.iter():
        name = elem.tag.rsplit("}", 1)[-1].casefold()
        text = (elem.text or "").strip()
        if name == "getcontentlength":
            try:
                size = int(text)
            except ValueError:
                size = -1
        elif name == "getlastmodified":
            modified = text
    if size < 0:
        raise ValueError("qualification WebDAV response omitted size")
    return {
        "Path": "",
        "Name": "",
        "Size": size,
        "IsDir": False,
        "ModTime": modified or datetime.now(timezone.utc).isoformat(),
        "Hashes": {},
    }


def _remote_metadata(url: str, user: str, password: str) -> dict[str, object]:
    _, body, _ = _request(
        "PROPFIND",
        url,
        user,
        password,
        headers={"Depth": "0", "Content-Length": "0"},
    )
    return _parse_propfind(body)


def _parse_args(argv: list[str]) -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("command")
    parser.add_argument("rest", nargs="*")
    args = parser.parse_args(argv)
    return args, args.rest


def main(argv: list[str] | None = None) -> int:
    args, rest = _parse_args(list(argv or sys.argv[1:]))
    command = args.command
    if command == "version":
        print("rclone v1.0.0-qualification-webdav")
        return 0
    if command == "obscure":
        if not rest or rest[0] != "-":
            return _error("qualification obscure requires stdin")
        value = sys.stdin.read().rstrip("\r\n")
        if not value:
            return _error("qualification obscure received empty input")
        print(base64.urlsafe_b64encode(value.encode()).decode().rstrip("="))
        return 0

    config_path = ""
    remote = ""
    source = ""
    for index, value in enumerate(rest):
        if value == "--config" and index + 1 < len(rest):
            config_path = rest[index + 1]
        elif value.startswith("photoprism:") and not remote:
            remote = value
        elif command == "copyto" and index == 0:
            source = value
    try:
        if not config_path or not remote:
            raise ValueError("qualification WebDAV command is missing config or remote")
        base, user, password = _config(config_path)
        target = _url(base, remote)
        if command == "lsjson":
            print(json.dumps(_remote_metadata(target, user, password), separators=(",", ":")))
            return 0
        if command == "deletefile":
            _request("DELETE", target, user, password)
            return 0
        if command == "copyto":
            candidate_home = Path.home().resolve(strict=True)
            source_path = Path(source).resolve(strict=True)
            if os.path.commonpath((str(source_path), str(candidate_home))) != str(candidate_home):
                raise ValueError("qualification source is outside the synthetic HOME")
            source_stat = source_path.stat()
            if not stat.S_ISREG(source_stat.st_mode) or source_path.is_symlink():
                raise ValueError("qualification source is not a regular non-symlink file")
            body = source_path.read_bytes()
            last_error: Exception | None = None
            for attempt in range(3):
                try:
                    _request(
                        "PUT",
                        target,
                        user,
                        password,
                        body=body,
                        headers={"Content-Type": "application/octet-stream"},
                    )
                    last_error = None
                    break
                except (urllib.error.HTTPError, urllib.error.URLError) as exc:
                    last_error = exc
                    if attempt < 2:
                        time.sleep(0.2 * (attempt + 1))
            if last_error is not None:
                raise last_error
            return 0
        if command == "moveto":
            if len(rest) < 2:
                raise ValueError("qualification moveto requires source and destination")
            destination = next((item for item in rest[1:] if item.startswith("photoprism:")), "")
            if not destination:
                raise ValueError("qualification moveto destination is invalid")
            _request(
                "MOVE",
                target,
                user,
                password,
                headers={"Destination": _url(base, destination), "Overwrite": "T"},
            )
            return 0
        raise ValueError("qualification rclone command is unsupported")
    except (OSError, ValueError, urllib.error.URLError, urllib.error.HTTPError, ET.ParseError) as exc:
        return _error(type(exc).__name__)


if __name__ == "__main__":
    raise SystemExit(main())
