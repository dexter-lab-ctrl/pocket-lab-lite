#!/usr/bin/env python3
"""Shared deterministic helpers for the local Termux runtime documentation pipeline."""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[3]
CAPTURE_ROOT = ROOT / ".pocketlab-dev" / "runtime-captures"
BASELINE_PATH = ROOT / "architecture" / "runtime-baselines" / "server-phone.json"
SCHEMA_ROOT = ROOT / "schemas" / "runtime"
RAW_SCHEMA_PATH = SCHEMA_ROOT / "termux-runtime-capture.schema.json"
SANITIZED_SCHEMA_PATH = SCHEMA_ROOT / "termux-runtime-sanitized.schema.json"
BASELINE_SCHEMA_PATH = SCHEMA_ROOT / "termux-runtime-baseline.schema.json"
SCHEMA_REVISION = 1
SUPPORTED_SCHEMA_REVISIONS = {SCHEMA_REVISION}

REQUIRED_SERVICE_IDS = {
    "pm2",
    "caddy",
    "lite-api",
    "nats",
    "worker",
    "node-agent",
    "core-supervisor",
    "sqlite",
}
OPTIONAL_SERVICE_IDS = {"tailscaled", "proot-ubuntu", "photoprism"}
EXPECTED_SERVICE_IDS = REQUIRED_SERVICE_IDS | OPTIONAL_SERVICE_IDS

SERVICE_ROLE_MAP = {
    "pocket-api": ("lite-api", "FastAPI control API", "python"),
    "pocket-worker": ("worker", "worker execution plane", "python"),
    "pocket-nats": ("nats", "NATS/JetStream service", "native"),
    "pocket-node-agent": ("node-agent", "server-host node agent", "python"),
    "pocketlab-core-supervisor": ("core-supervisor", "server-host recovery supervisor", "python"),
    "caddy-proxy": ("caddy", "same-origin proxy", "native"),
    "pocketlab-app-photoprism": ("photoprism", "managed application", "proot"),
}

STATUS_VALUES = {
    "online", "offline", "stopped", "degraded", "healthy", "ready", "missing",
    "unavailable", "unknown", "invalid", "partial",
}
PRESENCE_VALUES = {"present", "missing", "unknown"}
VERIFICATION_STATES = {
    "source-verified", "runtime-verified", "source-and-runtime-verified",
    "runtime-mismatch", "runtime-unavailable",
}


def stable_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def semantic_fingerprint(value: Any) -> str:
    if isinstance(value, dict):
        value = {key: item for key, item in value.items() if key != "semantic_fingerprint"}
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_schema(path: Path) -> dict[str, Any]:
    schema = read_json(path)
    Draft202012Validator.check_schema(schema)
    return schema


def validate_json(payload: Any, schema_path: Path) -> None:
    revision = payload.get("schema_revision") if isinstance(payload, dict) else None
    if revision not in SUPPORTED_SCHEMA_REVISIONS:
        raise ValueError(f"unsupported schema revision: {revision!r}")
    validator = Draft202012Validator(load_schema(schema_path))
    errors = sorted(validator.iter_errors(payload), key=lambda item: list(item.absolute_path))
    if errors:
        messages = []
        for error in errors[:12]:
            location = ".".join(str(part) for part in error.absolute_path) or "<root>"
            messages.append(f"{location}: {error.message}")
        extra = "" if len(errors) <= 12 else f"; {len(errors) - 12} additional errors"
        raise ValueError("schema validation failed: " + "; ".join(messages) + extra)


def atomic_write(path: Path, content: str, *, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def latest_sanitized_capture(capture_root: Path = CAPTURE_ROOT) -> Path:
    candidates = sorted(
        (path for path in capture_root.glob("*/sanitized/termux-runtime.json") if path.is_file()),
        key=lambda path: path.parent.parent.name,
    )
    if not candidates:
        raise FileNotFoundError("no sanitized Termux runtime capture is available")
    return candidates[-1]


def safe_bucket_memory(value: Any) -> str:
    try:
        amount = max(0, int(value))
    except (TypeError, ValueError):
        return "unknown"
    mib = amount / (1024 * 1024)
    if mib < 64:
        return "under-64-mib"
    if mib < 192:
        return "64-191-mib"
    if mib < 384:
        return "192-383-mib"
    return "384-mib-or-more"


def safe_bucket_restarts(value: Any) -> str:
    try:
        count = max(0, int(value))
    except (TypeError, ValueError):
        return "unknown"
    if count == 0:
        return "none"
    if count <= 2:
        return "low"
    if count <= 9:
        return "elevated"
    return "high"


def normalized_status(value: Any) -> str:
    text = str(value or "unknown").strip().lower().replace(" ", "_")
    mapping = {
        "errored": "degraded",
        "error": "degraded",
        "launching": "partial",
        "one-launch-status": "partial",
        "stopping": "stopped",
        "not_found": "missing",
        "not-found": "missing",
        "ok": "healthy",
        "running": "online",
    }
    text = mapping.get(text, text).replace("_", "-")
    return text if text in STATUS_VALUES else "unknown"


def normalize_architecture(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"aarch64", "arm64", "armv8l"}:
        return "arm64"
    if text in {"x86_64", "amd64"}:
        return "x86-64"
    return "other" if text else "unknown"


def normalize_android_major(value: Any) -> str:
    match = re.search(r"\d+", str(value or ""))
    return match.group(0) if match else "unknown"


def normalize_version_major(value: Any) -> str:
    match = re.search(r"(?:^|\D)(\d+)(?:\.\d+)?", str(value or ""))
    return match.group(1) if match else "unknown"


def stable_sorted(items: Iterable[dict[str, Any]], key: str = "id") -> list[dict[str, Any]]:
    return sorted(items, key=lambda item: canonical_json([item.get(key), item]))


def baseline_without_volatile(payload: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "schema_revision", "capture_kind", "sanitized", "source", "host_role",
        "platform", "services", "listeners", "routes", "runtime_apps", "messaging",
        "remote_access", "datastores", "runtime_relationships", "verification",
    }
    result = {key: payload[key] for key in sorted(allowed) if key in payload}
    result["semantic_fingerprint"] = semantic_fingerprint(result)
    return result


def runtime_mismatches(payload: dict[str, Any]) -> list[str]:
    services = {item.get("id"): item for item in payload.get("services", []) if isinstance(item, dict)}
    verification = payload.get("verification", {}) if isinstance(payload.get("verification"), dict) else {}
    unresolved = verification.get("unresolved_mismatches", [])
    mismatches: list[str] = [str(item) for item in unresolved if isinstance(item, str) and item.strip()]
    for service_id in sorted(REQUIRED_SERVICE_IDS):
        item = services.get(service_id)
        if not item:
            mismatches.append(f"services.{service_id}: missing runtime claim")
            continue
        if item.get("presence") != "present":
            mismatches.append(f"services.{service_id}: required process or runtime is absent")
        if item.get("expected_source_match") != "matched":
            mismatches.append(f"services.{service_id}: repository expectation mismatch")
        if item.get("status") in {"offline", "stopped", "missing", "invalid", "degraded"}:
            mismatches.append(f"services.{service_id}: unhealthy runtime state")
    sqlite_service = services.get("sqlite")
    if sqlite_service and sqlite_service.get("status") not in {"healthy", "ready", "online"}:
        mismatches.append("services.sqlite: integrity or schema verification did not pass")
    return sorted(set(mismatches))
