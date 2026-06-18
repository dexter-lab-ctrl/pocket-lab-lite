#!/usr/bin/env python3
from __future__ import annotations

from validation_evidence_lib import (
    ALLURE_HISTORY_DIR,
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
    rel,
    write_all,
)


def main() -> None:
    bundle = build_validation_artifacts()
    write_all(bundle)
    counts = bundle["readiness"]["status_counts"]
    print(f"Wrote {rel(MANIFEST_JSON)}")
    print(f"Wrote {rel(EVIDENCE_JSON)}")
    print(f"Wrote {rel(READINESS_JSON)}")
    print(f"Wrote {rel(BUNDLE_JSON)}")
    print(f"Wrote {rel(INDEX_MD)}")
    print(f"Wrote {rel(READINESS_MD)}")
    print(f"Wrote {rel(STRATEGY_MD)}")
    print(f"Wrote Allure results in {rel(ALLURE_RESULTS_DIR)}")
    print(f"Updated validation history in {rel(ALLURE_HISTORY_DIR)}")
    print(
        "Release readiness: "
        f"{bundle['readiness']['state']} "
        f"PASS={counts['PASS']} WARNING={counts['WARNING']} "
        f"FAIL={counts['FAIL']} BLOCKED={counts['BLOCKED']}"
    )


if __name__ == "__main__":
    main()
