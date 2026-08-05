#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[3]
MODEL_PATH = ROOT / "contracts" / "parity" / "parity-model.json"
GENERATED_ROOT = ROOT / "contracts" / "generated" / "parity"
FIXTURE_ROOT = ROOT / "src" / "test" / "fixtures" / "generated" / "parity" / "recovery"
EVIDENCE_ROOT = ROOT / ".pocketlab-dev" / "validation" / "parity"

SAFE_GET_PREFIXES = (
    "/api/lite/recovery",
    "/api/lite/fleet",
    "/api/lite/catalog",
    "/api/lite/security",
)
FORBIDDEN_WRITE_TOKENS = (
    "/backup",
    "/restore",
    "/check",
    "/restart",
    "/remove",
    "/install",
    "/update",
    "/repair",
    "/invite",
)
FORBIDDEN_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----", re.I),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{12,}", re.I),
    re.compile(r"\b(?:password|passwd|token|api[_-]?key|secret)\s*[:=]\s*[^\s,]+", re.I),
    re.compile(r"\b(?:(?:10|127|100)\.(?:\d{1,3}\.){2}\d{1,3}|169\.254\.(?:\d{1,3}\.)\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.(?:\d{1,3}\.)\d{1,3}|192\.168\.(?:\d{1,3}\.)\d{1,3})\b"),
    re.compile(r"[A-Za-z0-9.-]+\.ts\.net\b", re.I),
    re.compile(r"/data/data/com\.termux/files/(?:home|usr)(?:/|\b)"),
    re.compile(r"/home/[^/\s]+/"),
    re.compile(r"(?:nats|https?)://[^\s/]+:[^\s@]+@", re.I),
)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def stable_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def semantic_fingerprint(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def assert_unique_ids(items: Iterable[dict[str, Any]], label: str) -> None:
    values = [str(item.get("id") or "") for item in items]
    missing = [index for index, value in enumerate(values) if not value]
    if missing:
        raise AssertionError(f"{label} contains missing ids at indexes {missing}")
    duplicates = sorted({value for value in values if values.count(value) > 1})
    if duplicates:
        raise AssertionError(f"{label} contains duplicate ids: {duplicates}")


def assert_safe_text(text: str, label: str = "payload") -> None:
    for pattern in FORBIDDEN_PATTERNS:
        match = pattern.search(text)
        if match:
            raise AssertionError(f"{label} contains prohibited value matching {pattern.pattern!r}: {match.group(0)!r}")


def assert_bounded(path: Path, max_bytes: int = 256_000) -> None:
    size = path.stat().st_size
    if size > max_bytes:
        raise AssertionError(f"{path} is {size} bytes; limit is {max_bytes}")


def safe_openapi_operations(openapi: dict[str, Any]) -> list[tuple[str, str]]:
    operations: list[tuple[str, str]] = []
    for path, methods in sorted((openapi.get("paths") or {}).items()):
        if not isinstance(methods, dict) or not path.startswith(SAFE_GET_PREFIXES):
            continue
        for method in sorted(methods):
            if method.lower() != "get":
                continue
            lower_path = path.lower()
            if any(token in lower_path for token in FORBIDDEN_WRITE_TOKENS):
                continue
            operations.append((method.upper(), path))
    return operations


def compare_subset(actual: Any, expected: Any, path: str = "$") -> list[str]:
    problems: list[str] = []
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return [f"{path}: expected object, got {type(actual).__name__}"]
        for key, value in expected.items():
            if key not in actual:
                problems.append(f"{path}.{key}: missing")
            else:
                problems.extend(compare_subset(actual[key], value, f"{path}.{key}"))
    elif isinstance(expected, list):
        if actual != expected:
            problems.append(f"{path}: expected {expected!r}, got {actual!r}")
    elif actual != expected:
        problems.append(f"{path}: expected {expected!r}, got {actual!r}")
    return problems
