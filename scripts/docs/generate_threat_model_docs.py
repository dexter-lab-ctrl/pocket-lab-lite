#!/usr/bin/env python3
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT / "threat-model/pocketlab-threat-model.yaml"
OUT = ROOT / "docs/security/security-architecture-threat-model.md"


def run_generate() -> None:
    subprocess.run(["python3", "scripts/docs/generate_threat_model.py"], cwd=ROOT, check=True)


def table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join(["---"] * len(headers)) + "|",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(cell).replace("\n", "<br>") for cell in row) + " |")
    return "\n".join(lines)


def load_model() -> dict[str, Any]:
    if not MODEL.exists():
        run_generate()
    return yaml.safe_load(MODEL.read_text(encoding="utf-8")) or {}


def main() -> None:
    run_generate()
    model = load_model()
    metadata = model.get("metadata", {})

    parts: list[str] = []

    parts.append("# Security Architecture & Threat Model\n")
    parts.append(
        '!!! note "Generated threat-model-as-code threat-model page"\n'
        "    This page is generated from repository metadata. Operation-level `security` blocks in `operations/*.yaml` are required for new features. OWASP Threat Dragon is a local review/editing tool, not the source of truth.\n"
    )

    parts.append("## Objective\n")
    parts.append(
        "Pocket Lab uses Threat Modeling as Code to document trust boundaries, data flows, attack surfaces, STRIDE threats, mitigations, residual risks, and evidence sources across the FastAPI + NATS / JetStream + Worker architecture.\n"
    )

    parts.append("## Source of Truth\n")
    parts.append(
        table(
            ["Field", "Value"],
            [
                ["Model", metadata.get("name", "")],
                ["Documentation track", metadata.get("tier", "").replace("Tier", "Capability")],
                ["Generated at", metadata.get("generatedAt", "")],
                ["Source rule", metadata.get("sourceOfTruth", "")],
            ],
        )
    )

    parts.append("\n## Evidence Sources\n")
    evidence_rows = []
    for item in model.get("evidence_sources", []):
        if "paths" in item:
            value = ", ".join(item.get("paths", [])[:6])
            if len(item.get("paths", [])) > 6:
                value += f" ... ({len(item.get('paths', []))} total)"
        else:
            value = item.get("path", "")
        count = item.get("api_path_count") or item.get("channel_count") or item.get("operation_count") or ""
        evidence_rows.append([item.get("type", ""), value, count, item.get("notes", "")])
    parts.append(table(["Type", "Path / sample", "Count", "Notes"], evidence_rows))

    parts.append("\n## Architecture Views Used\n")
    parts.append("\n".join(f"- `{view}`" for view in model.get("tier5b_views", [])) + "\n")

    parts.append("## Operation Security Metadata Coverage\n")
    parts.append(
        table(
            ["Operation", "Classification", "STRIDE", "Trust Boundaries", "Attack Surfaces"],
            [
                [
                    op.get("name", ""),
                    op.get("security", {}).get("data_classification", ""),
                    ", ".join(op.get("security", {}).get("stride", [])),
                    ", ".join(op.get("security", {}).get("trust_boundaries", [])),
                    ", ".join(op.get("security", {}).get("attack_surfaces", [])),
                ]
                for op in model.get("operation_security", [])
            ],
        )
    )

    parts.append("\n## Protected Assets\n")
    parts.append(
        table(
            ["Asset", "Classification", "Evidence"],
            [[a.get("name", ""), a.get("classification", ""), a.get("evidence", "")] for a in model.get("assets", [])],
        )
    )

    parts.append("\n## Trust Boundaries\n")
    parts.append(
        table(
            ["Boundary", "Description", "Controls"],
            [
                [b.get("name", ""), b.get("description", ""), ", ".join(b.get("controls", [])[:10])]
                for b in model.get("trust_boundaries", [])
            ],
        )
    )

    parts.append("\n## Data Flows\n")
    parts.append(
        table(
            ["Flow", "Source", "Destination", "Trust Boundary", "STRIDE"],
            [
                [
                    f.get("name", ""),
                    f.get("source", ""),
                    f.get("destination", ""),
                    f.get("trustBoundary", ""),
                    ", ".join(f.get("stride", [])),
                ]
                for f in model.get("data_flows", [])
            ],
        )
    )

    parts.append("\n## Attack Surfaces\n")
    parts.append(
        table(
            ["Surface", "Evidence Count", "Example Operations"],
            [
                [s.get("name", ""), s.get("evidence_count", ""), ", ".join(s.get("examples", []))]
                for s in model.get("attack_surfaces", [])
            ],
        )
    )

    parts.append("\n## STRIDE Threats\n")
    parts.append(
        table(
            ["ID", "Source", "Operation", "Category", "Scenario", "Mitigations", "Residual Risk"],
            [
                [
                    t.get("id", ""),
                    t.get("source", ""),
                    t.get("operation", ""),
                    t.get("stride", ""),
                    t.get("scenario", ""),
                    ", ".join(t.get("mitigations", [])[:8]),
                    t.get("residualRisk", ""),
                ]
                for t in model.get("threats", [])
            ],
        )
    )

    parts.append("\n## Mitigations\n")
    parts.append(
        table(
            ["Mitigation", "Covers", "Evidence"],
            [
                [m.get("name", ""), ", ".join(m.get("covers", [])), m.get("evidence", "")]
                for m in model.get("mitigations", [])
            ],
        )
    )

    parts.append("\n## Residual Risks\n")
    parts.append(
        table(
            ["Operation", "Risk", "Owner", "Treatment"],
            [
                [r.get("operation", ""), r.get("risk", ""), r.get("owner", ""), r.get("treatment", "")]
                for r in model.get("residual_risks", [])
            ],
        )
    )

    parts.append("\n## OWASP Threat Dragon Local Review\n")
    parts.append(
        "Threat Dragon can be started locally for visual review/editing. Keep generated repository metadata authoritative and reconcile manual review notes back into version-controlled files.\n"
    )
    parts.append("```bash\ntask threatdragon:pull\ntask threatdragon:serve\n# open http://localhost:8082\n```\n")

    parts.append("## Validation\n")
    parts.append("```bash\ntask docs:threat-model:check\ntask docs:threat-model\nmkdocs build --strict\n```\n")

    OUT.write_text("\n".join(parts).rstrip() + "\n", encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
