#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from threat_model_source_sync_lib import ROOT, SYNC_DOC, SYNC_MANIFEST, build_sync_manifest, rel


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def load_manifest() -> dict:
    if not SYNC_MANIFEST.exists():
        fail(f"missing {rel(SYNC_MANIFEST)}; run task docs:threat-model:sync")
    return json.loads(SYNC_MANIFEST.read_text(encoding="utf-8"))


def main() -> None:
    recorded = load_manifest()
    current = build_sync_manifest()

    if recorded.get("source_fingerprint") != current.get("source_fingerprint"):
        fail(
            "Threat model source synchronization manifest is stale. "
            "Run: task docs:threat-model:sync"
        )

    findings = recorded.get("findings", [])
    errors = [item for item in findings if item.get("severity") == "error"]
    if errors:
        print("Source synchronization errors:")
        for item in errors:
            print(f"  - [{item.get('source')}] {item.get('code')}: {item.get('message')}")
            print(f"    Remediation: {item.get('remediation')}")
        fail("Threat model source synchronization has blocking errors")

    for required in [SYNC_DOC]:
        if not required.exists():
            fail(f"missing generated documentation: {rel(required)}")

    print("Threat model source synchronization check passed")
    print(
        "Findings: "
        f"errors={recorded.get('finding_summary', {}).get('error', 0)} "
        f"warnings={recorded.get('finding_summary', {}).get('warning', 0)} "
        f"info={recorded.get('finding_summary', {}).get('info', 0)}"
    )


if __name__ == "__main__":
    main()
