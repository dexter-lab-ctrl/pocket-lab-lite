#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[3]
HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head", "trace"}
FOCUSED_PATH = re.compile(r"^/api/lite/recovery(?:$|/)")
UNSAFE_GET_PATHS = {
    "/api/fleet/agent/bootstrap",
    "/api/catalog/refresh",
    "/api/join.sh",
    "/api/lite/fleet/agent/bootstrap.sh",
}
STREAM_PATHS = {"/api/lite/events", "/api/lite/security/events"}
SECRET_KEY = re.compile(r"(?:token|password|secret|authorization|api[_-]?key)", re.I)
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,159}$")


def _require_loopback_url(value: str, label: str) -> None:
    parsed = urlsplit(value)
    if parsed.scheme != "http" or parsed.username or parsed.password:
        raise SystemExit(f"ERROR {label} must be an unauthenticated HTTP loopback URL")
    host = (parsed.hostname or "").lower()
    if host == "localhost":
        return
    try:
        import ipaddress

        if ipaddress.ip_address(host).is_loopback:
            return
    except ValueError:
        pass
    raise SystemExit(f"ERROR {label} must resolve to loopback, got {host or 'missing-host'}")


def _read_json_url(url: str, timeout: float) -> Any:
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "PocketLab-Parity/1"})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read(2_000_000).decode("utf-8"))


def _safe_get(base_url: str, path: str, timeout: float) -> Any:
    try:
        return _read_json_url(urljoin(base_url.rstrip("/") + "/", path.lstrip("/")), timeout)
    except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError):
        return None


def _first_safe(value: Any, keys: tuple[str, ...]) -> str | None:
    if isinstance(value, dict):
        for key in keys:
            candidate = value.get(key)
            if isinstance(candidate, str) and SAFE_ID.fullmatch(candidate) and not SECRET_KEY.search(key):
                return candidate
        for child in value.values():
            found = _first_safe(child, keys)
            if found:
                return found
    elif isinstance(value, list):
        for child in value[:20]:
            found = _first_safe(child, keys)
            if found:
                return found
    return None


def discover_examples(base_url: str, timeout: float) -> dict[str, str]:
    probes = {
        "device_id": ("/api/lite/fleet", ("device_id", "node_id", "id")),
        "node_id": ("/api/lite/fleet", ("node_id", "device_id", "id")),
        "app_id": ("/api/lite/recovery/apps", ("app_id", "id")),
        "backup_id": ("/api/lite/recovery/backups?limit=1", ("backup_id",)),
        "run_id": ("/api/lite/security/history?limit=1", ("run_id",)),
        "restore_id": ("/api/lite/recovery/details", ("restore_id",)),
        "preview_id": ("/api/lite/recovery/details", ("preview_id",)),
        "checkpoint_id": ("/api/lite/recovery/details", ("checkpoint_id",)),
    }
    examples: dict[str, str] = {"app_id": "photoprism"}
    for name, (path, keys) in probes.items():
        payload = _safe_get(base_url, path, timeout)
        found = _first_safe(payload, keys)
        if found:
            examples[name] = found
    return examples


def _atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp = Path(raw)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _selected(profile: str, path: str, method: str, operation: dict[str, Any]) -> bool:
    if method != "get":
        return False
    if path in STREAM_PATHS or path in UNSAFE_GET_PATHS:
        return False
    if bool(operation.get("x-pocketlab-streaming")):
        return False
    if profile == "focused":
        return bool(FOCUSED_PATH.match(path)) and "/maintenance" not in path
    return path.startswith("/api/") or path.startswith("/loki/") or path in {"/health", "/ready"}


def _inject_examples(operation: dict[str, Any], examples: dict[str, str]) -> None:
    for parameter in operation.get("parameters") or []:
        if not isinstance(parameter, dict):
            continue
        name = str(parameter.get("name") or "")
        if name in examples and parameter.get("in") == "path":
            parameter["example"] = examples[name]
        if name == "cursor" and parameter.get("in") == "query":
            # Empty means first page and is always safe. Real next cursors are
            # exercised by endpoint-specific contract tests.
            parameter["example"] = ""


def compile_schema(source: dict[str, Any], profile: str, examples: dict[str, str]) -> tuple[dict[str, Any], list[dict[str, str]]]:
    output = {key: value for key, value in source.items() if key != "paths"}
    output["paths"] = {}
    selected: list[dict[str, str]] = []
    for path, path_item in sorted((source.get("paths") or {}).items()):
        if not isinstance(path_item, dict):
            continue
        compiled_item: dict[str, Any] = {
            key: value for key, value in path_item.items() if key.lower() not in HTTP_METHODS
        }
        for method, operation in sorted(path_item.items()):
            lower = method.lower()
            if lower not in HTTP_METHODS or not isinstance(operation, dict):
                continue
            if not _selected(profile, path, lower, operation):
                continue
            copied = json.loads(json.dumps(operation))
            _inject_examples(copied, examples)
            copied["x-pocketlab-parity-profile"] = profile
            compiled_item[lower] = copied
            selected.append({"method": lower.upper(), "path": path, "operation_id": str(copied.get("operationId") or "")})
        if any(key.lower() in HTTP_METHODS for key in compiled_item):
            output["paths"][path] = compiled_item

    if not selected:
        raise SystemExit(f"ERROR no operations selected for Schemathesis profile {profile}")
    if any(item["method"] != "GET" for item in selected):
        raise SystemExit("ERROR compiled Schemathesis schema contains a write operation")
    if profile == "focused" and any(not FOCUSED_PATH.match(item["path"]) or "/maintenance" in item["path"] for item in selected):
        raise SystemExit("ERROR focused Schemathesis schema escaped the Recovery read-only boundary")
    return output, selected


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=("focused", "discovery"), required=True)
    parser.add_argument("--openapi-url", required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args()

    _require_loopback_url(args.openapi_url, "OpenAPI URL")
    _require_loopback_url(args.base_url, "base URL")
    started = time.monotonic()
    source = _read_json_url(args.openapi_url, args.timeout)
    if not isinstance(source, dict) or not isinstance(source.get("paths"), dict):
        raise SystemExit("ERROR OpenAPI payload is not a valid object with paths")
    examples = discover_examples(args.base_url, min(args.timeout, 8.0))
    compiled, operations = compile_schema(source, args.profile, examples)
    _atomic_json(args.output, compiled)
    fingerprint = hashlib.sha256(args.output.read_bytes()).hexdigest()
    manifest = {
        "profile": args.profile,
        "operation_count": len(operations),
        "operations": operations,
        "examples": sorted(examples),
        "schema_sha256": fingerprint,
        "elapsed_ms": round((time.monotonic() - started) * 1000, 2),
        "read_only": True,
        "streaming_excluded": True,
        "unsafe_gets_excluded": sorted(UNSAFE_GET_PATHS),
        "sanitized": True,
    }
    _atomic_json(args.manifest, manifest)
    print(f"PASS compiled {args.profile} Schemathesis schema: {len(operations)} GET operations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
