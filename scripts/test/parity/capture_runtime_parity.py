#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import jsonschema

sys.path.insert(0, str(Path(__file__).resolve().parent))

from parity_common import MODEL_PATH, ROOT, assert_safe_text, stable_json
from semantic_compare import get_path

DEFAULT_BASE_URL = os.environ.get("LITE_PARITY_API_URL", "http://127.0.0.1:18080").rstrip("/")
DEFAULT_ROOT = ROOT / ".pocketlab-dev" / "validation" / "parity"
RELEASE_TAG_RE = re.compile(r"^lite-\d{4}\.\d{2}\.\d{2}\.\d+$")
OBSERVATION_SCHEMA = ROOT / "schemas" / "parity" / "parity-runtime-observation.schema.json"
SSH_ALIAS_RE = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")


class RuntimeUnavailable(RuntimeError):
    pass


class CaptureFailed(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def git(*args: str) -> str:
    result = subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def load_model() -> dict[str, Any]:
    return json.loads(MODEL_PATH.read_text(encoding="utf-8"))


def fetch_json(url: str, timeout: float) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"Accept": "application/json", "Cache-Control": "no-cache"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            raise RuntimeError(f"unexpected HTTP status {response.status}")
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise RuntimeError("API response was not a JSON object")
    return payload


def validate_api_base_url(base_url: str, *, loopback_only: bool = False) -> str:
    normalized = base_url.rstrip("/")
    parsed = urllib.parse.urlsplit(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("parity capture requires an HTTP(S) API base URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("parity capture URL must not contain credentials, query, or fragment")
    if parsed.path not in {"", "/"}:
        raise ValueError("parity capture URL must not contain a path")
    if loopback_only and (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}):
        raise ValueError("Termux SSH capture requires an HTTP loopback base URL")
    return normalized


def validate_remote_base_url(base_url: str) -> str:
    normalized = validate_api_base_url(base_url, loopback_only=True)
    parsed = urllib.parse.urlsplit(normalized)
    if not parsed.port:
        raise ValueError("Termux SSH capture URL must declare a loopback port")
    return normalized


def fetch_json_ssh(alias: str, base_url: str, path: str, timeout: float) -> dict[str, Any]:
    if not SSH_ALIAS_RE.fullmatch(alias):
        raise ValueError("managed SSH alias contains unsupported characters")
    remote_base = validate_remote_base_url(base_url)
    url = f"{remote_base}{path}"
    command = [
        "ssh", "-o", "BatchMode=yes", "-o", f"ConnectTimeout={max(1, min(int(timeout), 30))}",
        "-o", "ConnectionAttempts=1", alias,
        "curl", "-fsS", "--max-time", str(max(1, min(int(timeout), 30))),
        "--header", "Accept: application/json", url,
    ]
    try:
        completed = subprocess.run(
            command, check=False, capture_output=True, text=True, timeout=timeout + 5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise RuntimeUnavailable(type(exc).__name__) from exc
    if completed.returncode == 255:
        raise RuntimeUnavailable("ssh_unavailable")
    if completed.returncode != 0:
        raise CaptureFailed(f"remote_curl_{completed.returncode}")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise CaptureFailed("remote_invalid_json") from exc
    if not isinstance(payload, dict):
        raise CaptureFailed("remote_response_not_object")
    return payload


def _find_item(payload: dict[str, Any], spec: dict[str, Any]) -> Any:
    values = get_path(payload, str(spec.get("list_path") or "$"), [])
    if not isinstance(values, list):
        return None
    where = spec.get("where") or {}
    for item in values[:200]:
        if not isinstance(item, dict):
            continue
        if all(get_path(item, str(key)) == expected for key, expected in where.items()):
            return get_path(item, str(spec.get("value_path") or "$"))
    return None


def extract(payloads: dict[str, dict[str, Any]], spec: dict[str, Any]) -> Any:
    source = payloads.get(str(spec.get("route") or "primary"), {})
    kind = str(spec.get("extract") or "path")
    if kind == "path":
        return get_path(source, str(spec.get("path") or "$"))
    if kind == "count":
        value = get_path(source, str(spec.get("path") or "$"), [])
        return len(value) if isinstance(value, (list, dict)) else 0
    if kind == "count_where":
        values = get_path(source, str(spec.get("list_path") or "$"), [])
        where = spec.get("where") or {}
        return sum(1 for item in values[:200] if isinstance(item, dict) and all(get_path(item, str(key)) == expected for key, expected in where.items())) if isinstance(values, list) else 0
    if kind == "presence":
        value = get_path(source, str(spec.get("path") or "$"))
        return value not in (None, "", [], {})
    if kind == "find":
        return _find_item(source, spec)
    if kind == "any":
        values = get_path(source, str(spec.get("list_path") or "$"), [])
        where = spec.get("where") or {}
        return any(isinstance(item, dict) and all(get_path(item, str(key)) == expected for key, expected in where.items()) for item in values[:200]) if isinstance(values, list) else False
    raise ValueError(f"unsupported capture extractor: {kind}")


def bounded(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value.strip()[:240]
    if isinstance(value, list):
        return [bounded(item) for item in value[:50]]
    if isinstance(value, dict):
        return {str(key)[:80]: bounded(item) for key, item in list(value.items())[:50]}
    return str(value)[:240]


def atomic_write(path: Path, payload: dict[str, Any]) -> None:
    jsonschema.Draft202012Validator(
        json.loads(OBSERVATION_SCHEMA.read_text(encoding="utf-8"))
    ).validate(payload)
    text = stable_json(payload)
    assert_safe_text(text, str(path))
    if len(text.encode("utf-8")) > 64_000:
        raise RuntimeError(f"runtime observation exceeds 64000 bytes: {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    temporary = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def safe_error_code(exc: BaseException, status: str) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        return f"http_{exc.code}"
    if isinstance(exc, RuntimeUnavailable):
        candidate = str(exc)
        if re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", candidate):
            return candidate
    if isinstance(exc, CaptureFailed):
        candidate = str(exc)
        if re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", candidate):
            return candidate
    if isinstance(exc, (urllib.error.URLError, TimeoutError, subprocess.TimeoutExpired)):
        return "network_unavailable" if status == "runtime-unavailable" else "timeout"
    if isinstance(exc, json.JSONDecodeError):
        return "invalid_json"
    return type(exc).__name__[:64]


def capture_domain(
    domain: dict[str, Any],
    fetcher: Callable[[str], dict[str, Any]],
    evidence_kind: str,
    source_commit: str,
    release_tag: str,
) -> dict[str, Any]:
    contract = domain.get("live_observation_contract") or {}
    backend_contract = contract.get("backend") or {}
    routes = backend_contract.get("routes") or []
    payloads: dict[str, dict[str, Any]] = {}
    status = "observed"
    error_code = ""
    try:
        for route in routes:
            route_id = str(route.get("id") or "primary")
            path = str(route["path"])
            payloads[route_id] = fetcher(path)
        observations = {
            str(field["id"]): bounded(extract(payloads, field))
            for field in backend_contract.get("fields", [])
        }
    except (RuntimeUnavailable, urllib.error.URLError, TimeoutError) as exc:
        observations = {}
        status = "runtime-unavailable"
        error_code = safe_error_code(exc, status)
    except (CaptureFailed, urllib.error.HTTPError, json.JSONDecodeError, RuntimeError, ValueError) as exc:
        observations = {}
        status = "capture-failed"
        error_code = safe_error_code(exc, status)
    return {
        "schema_version": "2.0.0",
        "evidence_kind": evidence_kind,
        "domain": domain["id"],
        "status": status,
        "sanitized": True,
        "captured_at": utc_now(),
        "source_commit": source_commit,
        "release_tag": release_tag,
        "observations": observations,
        "error_code": error_code,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture sanitized read-only Lite runtime parity observations")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--kind", choices=("backend", "termux"), default="backend")
    parser.add_argument("--ssh-alias", default=os.environ.get("POCKETLAB_TERMUX_SSH_ALIAS", ""))
    parser.add_argument("--output-root", default="")
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--release-tag", default=os.environ.get("LITE_PARITY_RELEASE_TAG", ""))
    parser.add_argument("--domain", action="append", default=[])
    args = parser.parse_args()

    release_tag = args.release_tag.strip()
    if release_tag and not RELEASE_TAG_RE.fullmatch(release_tag):
        raise SystemExit("release tag must use lite-YYYY.MM.DD.N")
    source_commit = git("rev-parse", "HEAD")
    model = load_model()
    selected = set(args.domain)
    domains = [item for item in model["domains"] if not selected or item["id"] in selected]
    if selected - {item["id"] for item in domains}:
        raise SystemExit(f"unknown parity domains: {sorted(selected - {item['id'] for item in domains})}")

    root = Path(args.output_root) if args.output_root else DEFAULT_ROOT / args.kind
    root.mkdir(parents=True, exist_ok=True)
    stale_targets = [root / f"{item['id']}.json" for item in domains] if selected else list(root.glob("*.json"))
    for old in stale_targets:
        old.unlink(missing_ok=True)

    base_url = validate_api_base_url(args.base_url)
    if args.kind == "termux" and args.ssh_alias:
        remote_base = validate_remote_base_url(base_url)
        fetcher = lambda path: fetch_json_ssh(args.ssh_alias, remote_base, path, args.timeout)
    else:
        fetcher = lambda path: fetch_json(f"{base_url}{path}", args.timeout)

    observed = 0
    for domain in domains:
        result = capture_domain(domain, fetcher, args.kind, source_commit, release_tag)
        atomic_write(root / f"{domain['id']}.json", result)
        if result["status"] == "observed":
            observed += 1

    print(f"PASS {args.kind} parity capture: {observed}/{len(domains)} domains observed")
    return 0 if observed == len(domains) else 2


if __name__ == "__main__":
    raise SystemExit(main())
