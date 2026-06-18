#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys

from threat_model_drift_lib import (
    MANIFEST,
    compare_files,
    current_manifest_payload,
    load_manifest,
    output_fingerprints,
    rel,
    source_fingerprints,
)


def print_section(title: str, values: list[str]) -> None:
    if not values:
        return
    print(title)
    for value in values:
        print(f"  - {value}")


def main() -> None:
    try:
        recorded = load_manifest()
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print("Run: task docs:threat-model && task docs:threat-model:drift:seal", file=sys.stderr)
        raise SystemExit(1)

    subprocess.run(["python3", "scripts/docs/check_threat_model.py"], check=True)

    current = current_manifest_payload()
    current_sources = source_fingerprints()
    current_outputs = output_fingerprints()

    source_diff = compare_files(recorded.get("source_files", []), current_sources)
    output_diff = compare_files(recorded.get("generated_output_files", []), current_outputs)

    drift_found = False

    if recorded.get("source_fingerprint") != current.get("source_fingerprint"):
        drift_found = True
        print("ERROR: Threat-model source drift detected.", file=sys.stderr)
        print("Architecture, contract, or operation metadata changed after the threat-model drift manifest was sealed.", file=sys.stderr)
        print_section("Missing source files:", source_diff["missing"])
        print_section("Added source files:", source_diff["added"])
        print_section("Changed source files:", source_diff["changed"])

    if recorded.get("generated_output_fingerprint") != current.get("generated_output_fingerprint"):
        drift_found = True
        print("ERROR: Generated threat-model output drift detected.", file=sys.stderr)
        print("Generated docs or machine-readable outputs changed after the drift manifest was sealed.", file=sys.stderr)
        print_section("Missing generated outputs:", output_diff["missing"])
        print_section("Added generated outputs:", output_diff["added"])
        print_section("Changed generated outputs:", output_diff["changed"])

    if drift_found:
        print("", file=sys.stderr)
        print("Remediation:", file=sys.stderr)
        print("  task docs:threat-model", file=sys.stderr)
        print("  task docs:threat-model:drift:seal", file=sys.stderr)
        print("  task docs:threat-model:drift", file=sys.stderr)
        raise SystemExit(1)

    print("Threat-model drift check passed")
    print(f"Manifest: {rel(MANIFEST)}")
    print(f"Source fingerprint: {recorded.get('source_fingerprint')}")
    print(f"Generated output fingerprint: {recorded.get('generated_output_fingerprint')}")


if __name__ == "__main__":
    main()
