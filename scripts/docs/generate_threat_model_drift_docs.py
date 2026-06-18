#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone

from threat_model_drift_lib import DRIFT_DOC, MANIFEST, current_manifest_payload, load_manifest, rel


def row(values: list[str]) -> str:
    return "| " + " | ".join(value.replace("\n", "<br>") for value in values) + " |"


def main() -> None:
    try:
        manifest = load_manifest()
    except FileNotFoundError:
        manifest = current_manifest_payload()
        manifest["metadata"]["sealedAt"] = "not sealed yet"

    current = current_manifest_payload()
    source_status = "PASS" if manifest.get("source_fingerprint") == current.get("source_fingerprint") else "DRIFT"
    output_status = "PASS" if manifest.get("generated_output_fingerprint") == current.get("generated_output_fingerprint") else "DRIFT"

    source_rows = []
    for item in manifest.get("source_files", []):
        source_rows.append(row([item.get("path", ""), str(item.get("bytes", "")), item.get("sha256", "")[:16] + "..."]))

    output_rows = []
    for item in manifest.get("generated_output_files", []):
        output_rows.append(row([item.get("path", ""), str(item.get("bytes", "")), item.get("sha256", "")[:16] + "..."]))

    doc = f"""# Threat Model Drift Detection

This page documents threat drift detection — Threat Drift Detection for Pocket Lab.

!!! note "Generated page"
    This page is generated from `threat-model/pocketlab-threat-model-drift-manifest.json` and current repository fingerprints.

## Objective

Threat drift detection fails the build when architecture, API contracts, event contracts, typed operation contracts, or operation security metadata change without resealing the generated threat model artifacts.

## Drift status

| Check | Status |
|---|---|
| Source fingerprint | {source_status} |
| Generated output fingerprint | {output_status} |
| Manifest | `{rel(MANIFEST)}` |
| Page generated at | {datetime.now(timezone.utc).isoformat()} |

## Sources tracked

| Source | Size bytes | SHA-256 prefix |
|---|---:|---|
{chr(10).join(source_rows)}

## Generated outputs tracked

| Output | Size bytes | SHA-256 prefix |
|---|---:|---|
{chr(10).join(output_rows)}

## Commands

Seal after regenerating threat-model artifacts:

```bash
task docs:threat-model
task docs:threat-model:drift:seal
```

Check without modifying files:

```bash
task docs:threat-model:drift
```

Full validation:

```bash
task docs:threat-model:check
mkdocs build --strict
```

## Enterprise value

threat drift detection protects against silent security documentation drift. If a developer changes `Structurizr`, `OpenAPI`, `AsyncAPI`, typed operations, or operation-level security metadata, the drift gate fails until the generated threat model is regenerated, reviewed, and resealed.

## Raw manifest summary

```json
{json.dumps({k: manifest.get(k) for k in ['apiVersion', 'kind', 'source_fingerprint', 'generated_output_fingerprint']}, indent=2)}
```
"""

    DRIFT_DOC.parent.mkdir(parents=True, exist_ok=True)
    DRIFT_DOC.write_text(doc, encoding="utf-8")
    print(f"Wrote {rel(DRIFT_DOC)}")


if __name__ == "__main__":
    main()
