#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

SENSITIVE = re.compile(r"(authorization|cookie|set-cookie|password|token|secret|credential|api[-_]?key|private[-_]?key|nats|restic|tailscale|env)", re.I)
REDACTED = "[REDACTED]"


def clean_url(value: str) -> str:
    try:
        parts = urlsplit(value)
    except ValueError:
        return value
    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"
    query = []
    for pair in parts.query.split("&") if parts.query else []:
        key = pair.split("=", 1)[0]
        query.append(f"{key}={REDACTED}" if SENSITIVE.search(key) else pair)
    return urlunsplit((parts.scheme, host, parts.path, "&".join(query), ""))


def sanitize(value: Any, key: str = "") -> Any:
    if SENSITIVE.search(key):
        return REDACTED
    if isinstance(value, dict):
        result = {}
        for child_key, child in value.items():
            if child_key == "url" and isinstance(child, str):
                result[child_key] = clean_url(child)
            elif child_key.lower() in {"headers", "cookies", "querystring"} and isinstance(child, list):
                cleaned = []
                for item in child:
                    if not isinstance(item, dict):
                        continue
                    name = str(item.get("name", ""))
                    cleaned.append({**item, "value": REDACTED if SENSITIVE.search(name) else sanitize(item.get("value"), name)})
                result[child_key] = cleaned
            else:
                result[child_key] = sanitize(child, child_key)
        return result
    if isinstance(value, list):
        return [sanitize(item, key) for item in value]
    if isinstance(value, str):
        value = re.sub(r"Bearer\s+[A-Za-z0-9._~+/=-]+", f"Bearer {REDACTED}", value, flags=re.I)
        value = re.sub(r"-----BEGIN [^-]+PRIVATE KEY-----.*?-----END [^-]+PRIVATE KEY-----", REDACTED, value, flags=re.I | re.S)
        return value
    return value


def sanitize_file(input_path: Path, output_path: Path) -> None:
    data = json.loads(input_path.read_text(encoding="utf-8"))
    safe = sanitize(data)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(safe, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output_path)


def header_value(headers: list[dict[str, Any]], wanted: str) -> str:
    for header in headers or []:
        if str(header.get("name", "")).lower() == wanted.lower():
            return str(header.get("value", ""))
    return ""


def inspect_file(input_path: Path) -> int:
    data = json.loads(input_path.read_text(encoding="utf-8"))
    entries = data.get("log", {}).get("entries", [])
    requests = []
    for entry in entries:
        request = entry.get("request", {})
        response = entry.get("response", {})
        url = str(request.get("url", ""))
        if "/api/lite/" not in url:
            continue
        path = urlsplit(url).path
        requests.append({
            "method": request.get("method", "GET"),
            "path": path,
            "status": int(response.get("status", 0) or 0),
            "size": int(response.get("bodySize", 0) or 0),
            "revision": header_value(response.get("headers", []), "x-pocketlab-revision") or header_value(response.get("headers", []), "etag"),
            "canonical_hash": header_value(response.get("headers", []), "x-pocketlab-canonical-hash"),
            "cache": header_value(response.get("headers", []), "x-cache") or header_value(response.get("headers", []), "cf-cache-status"),
        })
    counts = Counter((item["method"], item["path"]) for item in requests)
    duplicates = [{"method": key[0], "path": key[1], "count": count} for key, count in counts.items() if count > 2]
    failed = [item for item in requests if item["status"] >= 400 or item["status"] == 0]
    heavy = [item for item in requests[:20] if item["size"] > 250_000]
    report = {
        "request_count": len(requests),
        "recovery_requests": [item for item in requests if "/recovery" in item["path"]],
        "security_requests": [item for item in requests if "/security" in item["path"]],
        "duplicate_requests": duplicates,
        "failed_requests": failed,
        "heavy_first_paint_requests": heavy,
        "revision_samples": [item for item in requests if item["revision"] or item["canonical_hash"]][:30],
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sanitize_parser = sub.add_parser("sanitize")
    sanitize_parser.add_argument("--input", required=True)
    sanitize_parser.add_argument("--output")
    inspect_parser = sub.add_parser("inspect")
    inspect_parser.add_argument("--input", required=True)
    args = parser.parse_args()
    input_path = Path(args.input)
    if args.command == "sanitize":
        output = Path(args.output) if args.output else input_path.with_suffix(".sanitized.har")
        sanitize_file(input_path, output)
        return 0
    return inspect_file(input_path)


if __name__ == "__main__":
    raise SystemExit(main())
