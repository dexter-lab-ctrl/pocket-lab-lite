#!/usr/bin/env python3
"""Check observability evidence generated observability docs freshness and MkDocs nav coverage."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GENERATED_FILES = [
    Path("docs/observability/generated/prometheus-scrape-reference.md"),
    Path("docs/observability/generated/loki-log-pipeline-reference.md"),
    Path("docs/observability/generated/grafana-dashboards-reference.md"),
    Path("docs/observability/generated/gatus-health-reference.md"),
    Path("docs/observability/generated/telemetry-contract-reference.md"),
    Path("docs/observability/generated/alerting-slo-reference.md"),
    Path("docs/observability/generated/observability-runtime-map.md"),
]
REQUIRED_NAV_TOKENS = [
    "observability/observability-logging-guide.md",
    "observability/generated/prometheus-scrape-reference.md",
    "observability/generated/loki-log-pipeline-reference.md",
    "observability/generated/grafana-dashboards-reference.md",
    "observability/generated/gatus-health-reference.md",
    "observability/generated/telemetry-contract-reference.md",
    "observability/generated/alerting-slo-reference.md",
    "observability/generated/observability-runtime-map.md",
]


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def main() -> int:
    errors: list[str] = []
    for path in GENERATED_FILES:
        full = ROOT / path
        if not full.exists():
            errors.append(f"missing generated doc: {path}")
        elif "GENERATED FILE" not in full.read_text(encoding="utf-8", errors="replace")[:220]:
            errors.append(f"generated marker missing from {path}")
    mkdocs = (ROOT / "mkdocs.yml").read_text(encoding="utf-8", errors="replace") if (ROOT / "mkdocs.yml").exists() else ""
    for token in REQUIRED_NAV_TOKENS:
        if token not in mkdocs:
            errors.append(f"mkdocs.yml nav missing {token}")

    evidence = run([sys.executable, "scripts/docs/check_observability_evidence.py"])
    if evidence.returncode != 0:
        errors.append("observability evidence manifest is stale or invalid: " + (evidence.stderr.strip() or evidence.stdout.strip()))

    before = {str(path): (ROOT / path).read_text(encoding="utf-8") for path in GENERATED_FILES if (ROOT / path).exists()}
    result = run([sys.executable, "scripts/docs/generate_observability_docs.py"])
    if result.returncode != 0:
        errors.append("observability docs regeneration failed: " + (result.stderr.strip() or result.stdout.strip()))
    else:
        for path in GENERATED_FILES:
            full = ROOT / path
            if full.exists() and before.get(str(path)) is not None and before[str(path)] != full.read_text(encoding="utf-8"):
                errors.append(f"stale generated doc: {path}")

    if errors:
        print("Observability docs check failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Observability docs check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
