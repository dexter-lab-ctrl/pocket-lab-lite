#!/usr/bin/env python3
"""Inspect, validate, diff, promote, and clean sanitized Termux runtime evidence."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import time
from pathlib import Path
from typing import Any

from runtime_common import (
    BASELINE_PATH,
    BASELINE_SCHEMA_PATH,
    CAPTURE_ROOT,
    SANITIZED_SCHEMA_PATH,
    atomic_write,
    baseline_without_volatile,
    latest_sanitized_capture,
    read_json,
    runtime_mismatches,
    stable_json,
    validate_json,
)
from runtime_redaction import assert_safe


def load_latest() -> tuple[Path, dict[str, Any]]:
    path = latest_sanitized_capture(CAPTURE_ROOT)
    payload = read_json(path)
    validate_json(payload, SANITIZED_SCHEMA_PATH)
    assert_safe(payload, context="sanitized Termux runtime capture")
    return path, payload


def changed_paths(left: Any, right: Any, prefix: str = "") -> list[str]:
    if type(left) is not type(right):
        return [prefix or "<root>"]
    if isinstance(left, dict):
        paths: list[str] = []
        for key in sorted(set(left) | set(right)):
            child = f"{prefix}.{key}" if prefix else key
            if key not in left or key not in right:
                paths.append(child)
            else:
                paths.extend(changed_paths(left[key], right[key], child))
        return paths
    if isinstance(left, list):
        paths = []
        maximum = max(len(left), len(right))
        for index in range(maximum):
            child = f"{prefix}[{index}]"
            if index >= len(left) or index >= len(right):
                paths.append(child)
            else:
                paths.extend(changed_paths(left[index], right[index], child))
        return paths
    return [] if left == right else [prefix or "<root>"]


def inspect() -> int:
    path, payload = load_latest()
    print("PASS latest sanitized capture is safe and schema-valid")
    print(f"Capture: {path.parent.parent.name}")
    print(f"Runtime state: {payload['verification']['runtime_verification_state']}")
    print(f"Services: {len(payload['services'])}; routes: {len(payload['routes'])}; apps: {len(payload['runtime_apps'])}")
    print(f"Semantic fingerprint: {payload['semantic_fingerprint'][:16]}")
    return 0


def validate() -> int:
    _, payload = load_latest()
    baseline = baseline_without_volatile(payload)
    validate_json(baseline, BASELINE_SCHEMA_PATH)
    assert_safe(baseline, context="candidate promoted runtime baseline")
    print("PASS latest sanitized capture and candidate baseline are schema-valid and secret-safe")
    return 0


def diff() -> int:
    _, payload = load_latest()
    candidate = baseline_without_volatile(payload)
    if not BASELINE_PATH.exists():
        print("Baseline is missing; promotion would create it")
        return 0
    current = read_json(BASELINE_PATH)
    validate_json(current, BASELINE_SCHEMA_PATH)
    differences = changed_paths(current, candidate)
    if not differences:
        print("PASS promoted baseline and latest sanitized capture are semantically identical")
        return 0
    print(f"Semantic diff contains {len(differences)} changed path(s):")
    for path in differences[:80]:
        print(f" - {path}")
    if len(differences) > 80:
        print(f" - ... {len(differences) - 80} additional path(s)")
    return 1


def promote(*, simulate_failure_after_backup: bool = False) -> int:
    if os.environ.get("LITE_RUNTIME_PROMOTE") != "1":
        raise RuntimeError("promotion requires LITE_RUNTIME_PROMOTE=1")
    _, payload = load_latest()
    candidate = baseline_without_volatile(payload)
    mismatches = runtime_mismatches(candidate)
    if mismatches:
        raise RuntimeError("promotion refused because repository/runtime mismatches remain: " + "; ".join(mismatches))
    validate_json(candidate, BASELINE_SCHEMA_PATH)
    assert_safe(candidate, context="promoted Termux runtime baseline")

    current = read_json(BASELINE_PATH) if BASELINE_PATH.exists() else {}
    differences = changed_paths(current, candidate)
    print(f"Promotion semantic diff contains {len(differences)} changed path(s):")
    for path in differences[:80]:
        print(f" - {path}")
    if len(differences) > 80:
        print(f" - ... {len(differences) - 80} additional path(s)")

    backup_root = CAPTURE_ROOT.parent / "runtime-baseline-backups"
    backup_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    backup_path = backup_root / f"server-phone.{int(time.time())}.json"
    previous: bytes | None = None
    if BASELINE_PATH.exists():
        previous = BASELINE_PATH.read_bytes()
        backup_path.write_bytes(previous)
        os.chmod(backup_path, 0o600)
    try:
        if simulate_failure_after_backup:
            raise OSError("injected promotion failure")
        atomic_write(BASELINE_PATH, stable_json(candidate), mode=0o644)
        validate_json(read_json(BASELINE_PATH), BASELINE_SCHEMA_PATH)
    except Exception:
        if previous is not None:
            atomic_write(BASELINE_PATH, previous.decode("utf-8"), mode=0o644)
        else:
            BASELINE_PATH.unlink(missing_ok=True)
        raise
    print(f"PASS promoted sanitized Termux runtime baseline: {candidate['semantic_fingerprint'][:16]}")
    return 0


def clean() -> int:
    if not CAPTURE_ROOT.exists():
        print("PASS no local Termux runtime captures require cleanup")
        return 0
    removed_raw = 0
    for raw in sorted(CAPTURE_ROOT.glob("*/raw")):
        if raw.is_dir():
            shutil.rmtree(raw)
            removed_raw += 1
    captures = sorted(
        (path for path in CAPTURE_ROOT.iterdir() if path.is_dir()),
        key=lambda path: path.name,
        reverse=True,
    )
    keep = max(1, int(os.environ.get("LITE_RUNTIME_MAX_CAPTURES", "8")))
    removed_captures = 0
    for old in captures[keep:]:
        shutil.rmtree(old)
        removed_captures += 1
    print(f"PASS local runtime cleanup removed {removed_raw} raw layer(s) and {removed_captures} stale capture(s)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["inspect", "validate", "diff", "promote", "clean"])
    args = parser.parse_args()
    try:
        return globals()[args.command]()
    except (FileNotFoundError, ValueError, RuntimeError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
