#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from validation_evidence_lib import (
    ALLURE_RESULTS_DIR,
    BUNDLE_JSON,
    EVIDENCE_JSON,
    GENERATED_DIR,
    INDEX_MD,
    MANIFEST_JSON,
    READINESS_JSON,
    READINESS_MD,
    STRATEGY_MD,
    build_validation_artifacts,
    load_generated_bundle,
    rel,
    validate_no_retired_text,
)


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate generated Pocket Lab validation evidence")
    parser.add_argument("--enforce-ready", action="store_true", help="Fail if release readiness is FAIL or BLOCKED")
    args = parser.parse_args()

    required = [MANIFEST_JSON, EVIDENCE_JSON, READINESS_JSON, BUNDLE_JSON, INDEX_MD, READINESS_MD, STRATEGY_MD]
    for path in required:
        if not path.exists():
            fail(f"missing {rel(path)}; run task docs:validation:evidence")

    generated = load_generated_bundle()
    current = build_validation_artifacts()
    if generated["manifest"].get("source_fingerprint") != current["manifest"].get("source_fingerprint"):
        fail("validation evidence source fingerprint is stale; run task docs:validation:evidence")

    gate_count = generated["manifest"].get("gate_count")
    if gate_count != len(generated["evidence"].get("gates", [])):
        fail("validation evidence gate count does not match manifest")

    if not ALLURE_RESULTS_DIR.exists() or not list(ALLURE_RESULTS_DIR.glob("*-result.json")):
        fail("missing Allure result files; run task docs:validation:evidence")

    retired = validate_no_retired_text([GENERATED_DIR, READINESS_MD, STRATEGY_MD])
    if retired:
        for item in retired:
            print(f"  - {item}")
        fail("generated validation evidence contains retired architecture tokens")

    state = generated["readiness"].get("state")
    counts = generated["readiness"].get("status_counts", {})
    print(
        "Validation evidence check passed: "
        f"state={state} PASS={counts.get('PASS', 0)} WARNING={counts.get('WARNING', 0)} "
        f"FAIL={counts.get('FAIL', 0)} BLOCKED={counts.get('BLOCKED', 0)}"
    )

    if args.enforce_ready and state in {"FAIL", "BLOCKED"}:
        fail(f"release readiness is {state}; resolve blockers before release")


if __name__ == "__main__":
    main()
