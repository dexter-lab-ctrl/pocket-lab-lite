#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from parity_common import EVIDENCE_ROOT, ROOT, assert_bounded, assert_safe_text, load_json, stable_json

SCHEMA = ROOT / "schemas" / "parity" / "parity-evidence.schema.json"
SCENARIOS = ROOT / "contracts" / "generated" / "parity" / "scenario-registry.json"
RESULT_FIELDS = (
    "backend_result", "api_result", "selector_result", "browser_result",
    "accessibility_result", "visual_result", "runtime_result",
)


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    temporary = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(stable_json(payload))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _validate(payload: dict[str, Any]) -> None:
    import jsonschema

    jsonschema.Draft202012Validator(load_json(SCHEMA)).validate(payload)
    text = stable_json(payload)
    assert_safe_text(text, "parity evidence")
    if any(value == "pass" for value in (payload.get(field) for field in RESULT_FIELDS)):
        if not payload.get("artifacts"):
            raise AssertionError("a pass result requires at least one recorded artifact")


def generate() -> None:
    registry = load_json(SCENARIOS)
    source_commit = os.environ.get("SOURCE_COMMIT", "repository-source")[:64]
    environment = os.environ.get("LITE_PARITY_ENVIRONMENT", "wsl2-isolated")
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    for scenario in registry["items"]:
        scenario_id = scenario["id"]
        payload = {
            "schema_version": "1.0.0",
            "scenario_id": scenario_id,
            "source_commit": source_commit,
            "environment": environment,
            "generated_at": generated_at,
            "backend_result": "unvalidated",
            "api_result": "unvalidated",
            "selector_result": "unvalidated",
            "browser_result": "unvalidated",
            "accessibility_result": "unvalidated",
            "visual_result": "unvalidated",
            "runtime_result": "runtime-unavailable",
            "status": "unvalidated",
            "artifacts": [],
            "notes": ["Generated evidence template; test runners must record actual outcomes before changing a result to pass."],
        }
        _validate(payload)
        _atomic_write(EVIDENCE_ROOT / f"{scenario_id}.json", payload)
    print(f"PASS parity evidence templates: {len(registry['items'])} scenarios")


def check() -> None:
    registry = load_json(SCENARIOS)
    expected = {item["id"] for item in registry["items"]}
    found = {path.stem for path in EVIDENCE_ROOT.glob("*.json")} if EVIDENCE_ROOT.exists() else set()
    missing = sorted(expected - found)
    if missing:
        raise SystemExit(f"missing parity evidence templates: {missing}")
    for scenario_id in sorted(expected):
        path = EVIDENCE_ROOT / f"{scenario_id}.json"
        payload = load_json(path)
        _validate(payload)
        assert_bounded(path, max_bytes=64_000)
    print(f"PASS parity evidence check: {len(expected)} sanitized templates")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("generate", "check"))
    args = parser.parse_args()
    globals()[args.command]()


if __name__ == "__main__":
    main()
