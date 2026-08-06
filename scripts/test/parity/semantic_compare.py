#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

ALLOWED_OPERATORS = frozenset({
    "exact",
    "normalized-string",
    "case-insensitive",
    "enum-map",
    "boolean-equivalence",
    "numeric-tolerance",
    "percentage-format",
    "byte-format",
    "duration-format",
    "timestamp-equivalence",
    "freshness-window",
    "set-equality",
    "ordered-list",
    "subset",
    "superset",
    "identity-match",
    "state-machine-map",
    "status-family",
    "presence",
    "absence",
    "safe-redaction",
    "capability-map",
    "intentional-presentation-map",
    "text-contains",
})

_UNSAFE = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----", re.I),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{12,}", re.I),
    re.compile(r"\b(?:password|passwd|token|api[_-]?key|secret)\s*[:=]\s*[^\s,]+", re.I),
    re.compile(r"/data/data/com\.termux/files/(?:home|usr)(?:/|\b)"),
    re.compile(r"/home/[^/\s]+/"),
    re.compile(r"(?:nats|https?)://[^\s/]+:[^\s@]+@", re.I),
    re.compile(r"\b(?:10|127|169\.254|172\.(?:1[6-9]|2\d|3[01])|192\.168|100)\.(?:\d{1,3}\.){2}\d{1,3}\b"),
    re.compile(r"[A-Za-z0-9.-]+\.ts\.net\b", re.I),
)


def _bounded(value: Any, limit: int = 240) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value[:limit]
    if isinstance(value, list):
        return [_bounded(item, limit) for item in value[:30]]
    if isinstance(value, dict):
        return {str(key)[:80]: _bounded(item, limit) for key, item in list(value.items())[:30]}
    return str(value)[:limit]


@lru_cache(maxsize=512)
def _path_tokens(path: str) -> tuple[str | int, ...]:
    if not path or path == "$":
        return ()
    tokens: list[str | int] = []
    for part in path.removeprefix("$.").split("."):
        match = re.fullmatch(r"([^\[]+)(?:\[(\d+)\])?", part)
        if not match:
            raise ValueError(f"unsupported bounded JSON path: {path}")
        tokens.append(match.group(1))
        if match.group(2) is not None:
            tokens.append(int(match.group(2)))
    return tuple(tokens)


def get_path(value: Any, path: str, default: Any = None) -> Any:
    current = value
    try:
        for token in _path_tokens(path):
            if isinstance(token, int):
                if not isinstance(current, list):
                    return default
                current = current[token]
            else:
                if not isinstance(current, dict) or token not in current:
                    return default
                current = current[token]
    except (IndexError, TypeError):
        return default
    return current


def _text(value: Any) -> str:
    if isinstance(value, list):
        value = " ".join(str(item) for item in value)
    elif isinstance(value, dict):
        value = " ".join(f"{key} {item}" for key, item in value.items())
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _normalized(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _text(value).casefold()).strip()


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    match = re.search(r"-?\d+(?:\.\d+)?", _text(value).replace(",", ""))
    return float(match.group(0)) if match else None


def _boolean(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    normalized = _normalized(value)
    if normalized in {"true", "yes", "on", "enabled", "available", "online", "ready", "verified", "present"}:
        return True
    if normalized in {"false", "no", "off", "disabled", "unavailable", "offline", "not ready", "unverified", "absent"}:
        return False
    return None


def _bytes(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)):
        return float(value)
    text = _text(value).replace(",", "")
    match = re.search(r"(-?\d+(?:\.\d+)?)\s*(b|bytes?|kib|kb|mib|mb|gib|gb|tib|tb)?\b", text, re.I)
    if not match:
        return None
    number = float(match.group(1))
    unit = (match.group(2) or "b").casefold()
    factors = {
        "b": 1, "byte": 1, "bytes": 1,
        "kb": 1000, "mb": 1000**2, "gb": 1000**3, "tb": 1000**4,
        "kib": 1024, "mib": 1024**2, "gib": 1024**3, "tib": 1024**4,
    }
    return number * factors[unit]


def _duration_seconds(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)):
        return float(value)
    text = _text(value).casefold()
    total = 0.0
    matched = False
    factors = {
        "ms": 0.001, "millisecond": 0.001, "milliseconds": 0.001,
        "s": 1, "sec": 1, "secs": 1, "second": 1, "seconds": 1,
        "m": 60, "min": 60, "mins": 60, "minute": 60, "minutes": 60,
        "h": 3600, "hr": 3600, "hrs": 3600, "hour": 3600, "hours": 3600,
        "d": 86400, "day": 86400, "days": 86400,
    }
    for number, unit in re.findall(r"(-?\d+(?:\.\d+)?)\s*(milliseconds?|ms|seconds?|secs?|s|minutes?|mins?|m|hours?|hrs?|h|days?|d)\b", text):
        total += float(number) * factors[unit]
        matched = True
    return total if matched else None


def _timestamp(value: Any) -> datetime | None:
    text = _text(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _mapped_expected(mapping: dict[str, Any], backend: Any) -> Any:
    candidates = [str(backend), str(backend).casefold()]
    if isinstance(backend, bool):
        candidates.extend(["true" if backend else "false", "1" if backend else "0"])
    for candidate in candidates:
        if candidate in mapping:
            return mapping[candidate]
    return None


def _normalized_contains(haystack_value: Any, needle_value: Any) -> bool:
    haystack = _normalized(haystack_value)
    needle = _normalized(needle_value)
    if not needle:
        return False
    return f" {needle} " in f" {haystack} "


def _contains_expected(frontend: Any, expected: Any) -> bool:
    values = expected if isinstance(expected, list) else [expected]
    return any(_normalized_contains(frontend, item) for item in values)


def _evidence_value(value: Any) -> Any:
    """Return a non-reversible, bounded summary suitable for tracked baselines."""
    if value is None or isinstance(value, (bool, int, float)):
        return value
    stable = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(stable.encode("utf-8")).hexdigest()[:16]
    if isinstance(value, str):
        return {"type": "string", "present": bool(value.strip()), "length": min(len(value), 12000), "fingerprint": digest}
    if isinstance(value, list):
        return {"type": "list", "count": min(len(value), 100), "fingerprint": digest}
    if isinstance(value, dict):
        return {
            "type": "object",
            "count": min(len(value), 100),
            "fingerprint": digest,
        }
    return {"type": type(value).__name__[:40], "fingerprint": digest}


def _result(operator: str, result: str, backend: Any, frontend: Any, explanation: str) -> dict[str, Any]:
    return {
        "operator": operator,
        "result": result,
        "backend_value": _evidence_value(backend),
        "frontend_value": _evidence_value(frontend),
        "explanation": explanation[:300],
    }


def compare_values(operator: str, backend: Any, frontend: Any, definition: dict[str, Any] | None = None) -> dict[str, Any]:
    definition = definition or {}
    if operator not in ALLOWED_OPERATORS:
        raise ValueError(f"unknown comparator: {operator}")

    if operator == "presence":
        matched = frontend not in (None, "", [], {})
        return _result(operator, "match" if matched else "mismatch", backend, frontend, "frontend value is present" if matched else "frontend value is absent")
    if operator == "absence":
        matched = frontend in (None, "", [], {})
        return _result(operator, "match" if matched else "mismatch", backend, frontend, "frontend value is absent" if matched else "unexpected frontend value is present")
    if operator == "safe-redaction":
        unsafe = next((pattern.pattern for pattern in _UNSAFE if pattern.search(_text(frontend))), None)
        return _result(operator, "mismatch" if unsafe else "match", backend, frontend, f"unsafe pattern detected: {unsafe}" if unsafe else "frontend observation remains sanitized")

    if backend is None or frontend is None:
        return _result(operator, "not-observed", backend, frontend, "one side was not observed")

    matched = False
    mapped = False
    explanation = "values differ"

    if operator == "exact":
        matched = backend == frontend
        explanation = "values are exactly equal" if matched else "values are not exactly equal"
    elif operator in {"normalized-string", "case-insensitive", "identity-match"}:
        matched = _normalized(backend) == _normalized(frontend)
        explanation = "normalized values match" if matched else "normalized values differ"
    elif operator == "text-contains":
        matched = _normalized_contains(frontend, backend)
        explanation = "frontend contains the backend meaning" if matched else "frontend does not contain the backend meaning"
    elif operator == "boolean-equivalence":
        left, right = _boolean(backend), _boolean(frontend)
        matched = left is not None and right is not None and left is right
        mapped = matched and _text(backend) != _text(frontend)
        explanation = "boolean meaning matches" if matched else "boolean meaning differs or is not recognized"
    elif operator == "numeric-tolerance":
        left, right = _number(backend), _number(frontend)
        tolerance = float(definition.get("tolerance", 0))
        matched = left is not None and right is not None and abs(left - right) <= tolerance
        explanation = f"numeric delta is within {tolerance}" if matched else f"numeric delta exceeds {tolerance}"
    elif operator == "percentage-format":
        left = _number(backend)
        right = _number(frontend)
        tolerance = float(definition.get("tolerance", 0.51))
        matched = left is not None and right is not None and abs(left - right) <= tolerance
        explanation = "percentage formatting is equivalent" if matched else "percentage formatting is not equivalent"
        mapped = matched and _text(backend) != _text(frontend)
    elif operator in {"byte-format", "duration-format"}:
        parser = _bytes if operator == "byte-format" else _duration_seconds
        left, right = parser(backend), parser(frontend)
        tolerance = float(definition.get("tolerance", 1.0))
        matched = left is not None and right is not None and abs(left - right) <= tolerance
        explanation = "formatted quantity is equivalent" if matched else "formatted quantity differs"
        mapped = matched and _text(backend) != _text(frontend)
    elif operator in {"timestamp-equivalence", "freshness-window"}:
        left, right = _timestamp(backend), _timestamp(frontend)
        seconds = float(definition.get("tolerance_seconds", definition.get("window_seconds", 60)))
        matched = left is not None and right is not None and abs((left - right).total_seconds()) <= seconds
        explanation = f"timestamps are within {int(seconds)} seconds" if matched else f"timestamps differ by more than {int(seconds)} seconds"
    elif operator in {"set-equality", "subset", "superset", "ordered-list"}:
        left = backend if isinstance(backend, list) else [backend]
        right = frontend if isinstance(frontend, list) else [frontend]
        if operator == "ordered-list":
            matched = [_normalized(x) for x in left] == [_normalized(x) for x in right]
        else:
            left_set, right_set = {_normalized(x) for x in left}, {_normalized(x) for x in right}
            matched = left_set == right_set if operator == "set-equality" else (left_set <= right_set if operator == "subset" else left_set >= right_set)
        explanation = f"{operator} relation holds" if matched else f"{operator} relation does not hold"
    elif operator in {"enum-map", "state-machine-map", "status-family", "capability-map", "intentional-presentation-map"}:
        expected = _mapped_expected(definition.get("mapping") or {}, backend)
        if expected is None:
            return _result(operator, "unsupported", backend, frontend, "no allowlisted mapping exists for the backend value")
        matched = _contains_expected(frontend, expected) if definition.get("match", "contains") == "contains" else _normalized(frontend) in {_normalized(x) for x in (expected if isinstance(expected, list) else [expected])}
        mapped = matched and (operator == "intentional-presentation-map" or _normalized(backend) != _normalized(frontend))
        explanation = "frontend uses an allowlisted semantic presentation" if matched else "frontend presentation is outside the allowlisted mapping"
    else:
        raise AssertionError(operator)

    return _result(operator, "mapped" if matched and mapped else ("match" if matched else "mismatch"), backend, frontend, explanation)


def compare_domain(domain: dict[str, Any], backend_observation: dict[str, Any], frontend_observation: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    backend = backend_observation.get("observations") or {}
    frontend = frontend_observation.get("observations") or {}
    for definition in domain.get("semantic_mappings", []):
        result = compare_values(
            str(definition["operator"]),
            get_path(backend, str(definition.get("backend_path") or "$")),
            get_path(frontend, str(definition.get("frontend_path") or "$")),
            definition,
        )
        result.update({
            "id": str(definition["id"]),
            "severity": str(definition.get("severity") or "medium"),
            "boundary": str(definition.get("boundary") or "live-api-live-ui"),
            "accepted_limitation": bool(definition.get("accepted_limitation", False)),
        })
        results.append(result)
    return results
