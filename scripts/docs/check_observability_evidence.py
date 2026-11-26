#!/usr/bin/env python3
"""Check the Lite-native health and telemetry evidence manifest."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "docs/observability/generated/observability-evidence-manifest.json"
SCHEMA_VERSION = "pocketlab.observability_evidence.v1"
GENERATED_DOCS = [
    Path("docs/observability/generated/prometheus-scrape-reference.md"),
    Path("docs/observability/generated/loki-log-pipeline-reference.md"),
    Path("docs/observability/generated/grafana-dashboards-reference.md"),
    Path("docs/observability/generated/gatus-health-reference.md"),
    Path("docs/observability/generated/telemetry-contract-reference.md"),
    Path("docs/observability/generated/alerting-slo-reference.md"),
    Path("docs/observability/generated/observability-runtime-map.md"),
]
REQUIRED_GROUPS = [
    "native_health_authority",
    "native_telemetry",
    "fastapi_runtime_observability",
    "frontend_active_lite",
    "runtime_contracts",
    "bootstrap_native",
    "retirement_documentation",
]
GENERATED_PREFIX = "docs/observability/generated/"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_manifest() -> dict[str, Any]:
    if not MANIFEST.exists():
        raise FileNotFoundError(f"Missing {MANIFEST.relative_to(ROOT)}")
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def main() -> int:
    errors: list[str] = []
    try:
        m = load_manifest()
    except Exception as exc:
        print(f"Observability evidence check failed: {exc}", file=sys.stderr)
        return 1

    if m.get("schema_version") != SCHEMA_VERSION:
        errors.append("unexpected observability evidence schema_version")
    if not m.get("generated_at"):
        errors.append("manifest missing generated_at")
    source_files = m.get("source_files")
    if not isinstance(source_files, list) or not source_files:
        errors.append("manifest source_files is empty or invalid")
    groups = m.get("source_groups", {})
    for group in REQUIRED_GROUPS:
        if not groups.get(group):
            errors.append(f"required observed source group is empty: {group}")

    for rec in source_files if isinstance(source_files, list) else []:
        path_value = rec.get("path", "")
        if not path_value:
            errors.append("source record without path")
            continue
        if path_value.startswith(GENERATED_PREFIX):
            errors.append(f"generated docs must not be fingerprinted as source input: {path_value}")
            continue
        path = ROOT / path_value
        if not path.exists():
            errors.append(f"manifest references missing file: {path_value}")
            continue
        recorded = rec.get("sha256")
        if not recorded:
            errors.append(f"source record missing sha256: {path_value}")
        elif sha256(path) != recorded:
            errors.append(f"manifest fingerprint stale for {path_value}")

    if not m.get("observability_components"):
        errors.append("observability_components is empty")
    if not m.get("fastapi_observability_routes"):
        errors.append("fastapi_observability_routes is empty")
    if not m.get("frontend_observability_consumers"):
        errors.append("frontend_observability_consumers is empty")
    authority = m.get("native_health_authority", {})
    if authority.get("source") != "prepared-lite-native":
        errors.append("native health authority is not prepared-lite-native")
    if authority.get("request_side_effects") is not False:
        errors.append("native health reads must declare request_side_effects=false")
    legacy = m.get("legacy_components", [])
    if not legacy or any(item.get("disposition") != "retired" for item in legacy):
        errors.append("legacy component inventory is incomplete or not fully retired")

    for path in GENERATED_DOCS:
        full = ROOT / path
        if not full.exists():
            errors.append(f"generated doc missing: {path}")
        elif "GENERATED FILE" not in full.read_text(encoding="utf-8", errors="replace")[:220]:
            errors.append(f"generated marker missing from {path}")

    if errors:
        print("Observability evidence check failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("Observability evidence check passed")
    print(
        f"Sources={len(source_files)} components={len(m.get('observability_components', []))} "
        f"native_health_sources={len(groups.get('native_health_authority', []))} "
        f"retired_components={len(m.get('legacy_components', []))}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
