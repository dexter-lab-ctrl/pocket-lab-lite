#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

SEMANTIC_KEYS = (
    "status",
    "summary",
    "active_operations",
    "attention_required",
    "recent_completed",
    "latest_change",
    "workflows",
    "audit_reference_count",
    "policy_mode",
    "item_count",
)


class ActivityNotIdle(ValueError):
    pass


def semantic_material(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: payload.get(key) for key in SEMANTIC_KEYS}


def build_sample(payload: dict[str, Any]) -> dict[str, Any]:
    material = semantic_material(payload)
    active_operations = int(material.get("active_operations") or 0)
    attention_required = int(material.get("attention_required") or 0)
    status = str(material.get("status") or "").strip().lower()
    if active_operations != 0 or attention_required != 0 or status == "active":
        raise ActivityNotIdle(
            json.dumps(
                {
                    "activity_not_idle": {
                        "active_operations": active_operations,
                        "attention_required": attention_required,
                        "status": material.get("status"),
                    }
                },
                sort_keys=True,
            )
        )
    encoded = json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "semantic_hash": hashlib.sha256(encoded).hexdigest(),
        "source_revision": int(payload.get("source_revision") or 0),
        "projection_revision": int(payload.get("projection_revision") or 0),
        "material": material,
    }


def samples_match(first: dict[str, Any], second: dict[str, Any]) -> bool:
    return (
        first.get("semantic_hash") == second.get("semantic_hash")
        and int(first.get("source_revision") or 0) == int(second.get("source_revision") or 0)
    )


def classify_observation(baseline: dict[str, Any], after_payload: dict[str, Any]) -> tuple[str, dict[str, Any] | None]:
    try:
        after = build_sample(after_payload)
    except ActivityNotIdle:
        return "activity_appeared", None
    if not samples_match(baseline, after):
        return "activity_changed", after
    return "idle", after


def _load(path: str) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("activity payload must be an object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    sample_parser = subparsers.add_parser("sample")
    sample_parser.add_argument("input")
    sample_parser.add_argument("output")

    match_parser = subparsers.add_parser("matches")
    match_parser.add_argument("first")
    match_parser.add_argument("second")

    observe_parser = subparsers.add_parser("observe")
    observe_parser.add_argument("baseline")
    observe_parser.add_argument("after")
    observe_parser.add_argument("output")

    args = parser.parse_args()
    if args.command == "sample":
        try:
            sample = build_sample(_load(args.input))
        except ActivityNotIdle as exc:
            print(str(exc), file=__import__("sys").stderr)
            return 3
        Path(args.output).write_text(json.dumps(sample, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        return 0
    if args.command == "matches":
        return 0 if samples_match(_load(args.first), _load(args.second)) else 1

    baseline = _load(args.baseline)
    state, after = classify_observation(baseline, _load(args.after))
    if after is not None:
        Path(args.output).write_text(json.dumps(after, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    if state == "idle":
        return 0
    if state == "activity_appeared":
        print("Phase 3C activity appeared during idle interval", file=__import__("sys").stderr)
        return 4
    print("Phase 3C activity changed during idle interval", file=__import__("sys").stderr)
    return 5


if __name__ == "__main__":
    raise SystemExit(main())
