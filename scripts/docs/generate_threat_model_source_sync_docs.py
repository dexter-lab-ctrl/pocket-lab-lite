#!/usr/bin/env python3
from __future__ import annotations

import subprocess
from typing import Any

from threat_model_source_sync_lib import SYNC_DOC, SYNC_MANIFEST, rel

import json


def table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join(["---"] * len(headers)) + "|",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(cell).replace("\n", "<br>") for cell in row) + " |")
    return "\n".join(lines)


def main() -> None:
    subprocess.run(["python3", "scripts/docs/generate_threat_model_source_sync.py"], check=True)

    manifest = json.loads(SYNC_MANIFEST.read_text(encoding="utf-8"))
    sources = manifest.get("sources", {})
    summary = manifest.get("finding_summary", {})

    source_rows = [
        ["Structurizr", sources.get("structurizr", {}).get("path", ""), len(sources.get("structurizr", {}).get("elements", [])), "C4 architecture elements and enterprise security-review views"],
        ["OpenAPI", sources.get("openapi", {}).get("path", ""), sources.get("openapi", {}).get("endpoint_count", 0), "FastAPI HTTP control-plane surface"],
        ["AsyncAPI", sources.get("asyncapi", {}).get("path", ""), sources.get("asyncapi", {}).get("channel_count", 0), "NATS / JetStream command and event channels"],
        ["Typed Operations", sources.get("typed_operations", {}).get("path", ""), sources.get("typed_operations", {}).get("operation_count", 0), "Execution contract"],
        ["Operation metadata", sources.get("operation_metadata", {}).get("path", ""), sources.get("operation_metadata", {}).get("operation_metadata_count", 0), "Threat Modeling as Code source"],
    ]

    link_rows = []
    for item in manifest.get("operation_source_links", []):
        link_rows.append(
            [
                item.get("operation", ""),
                item.get("metadata_file", ""),
                "yes" if item.get("typed_operation_present") else "no",
                ", ".join(item.get("openapi_matches", [])) or "-",
                ", ".join(item.get("asyncapi_matches", [])) or "-",
                ", ".join(item.get("stride", [])) or "-",
            ]
        )

    finding_rows = []
    for item in manifest.get("findings", []):
        finding_rows.append(
            [
                item.get("severity", ""),
                item.get("source", ""),
                item.get("code", ""),
                item.get("message", ""),
                item.get("remediation", ""),
            ]
        )

    doc = [
        "# Threat Model Source Synchronization",
        "",
        '!!! note "Generated threat-model source synchronization evidence"',
        "    This page is generated from Structurizr, OpenAPI, AsyncAPI, Typed Operations, and `operations/*.yaml`. It verifies that security architecture and threat-model metadata stay synchronized with contract-first engineering artifacts.",
        "",
        "## Objective",
        "",
        "threat-model source synchronization automatically synchronizes Pocket Lab threat-model evidence with the architecture and contract sources that define the control plane.",
        "",
        "```text",
        "Structurizr + OpenAPI + AsyncAPI + Typed Operations + operations/*.yaml",
        "        ↓",
        "Threat-model source synchronization manifest",
        "        ↓",
        "Security Architecture & Threat Model validation",
        "```",
        "",
        "## Source inventory",
        "",
        table(["Source", "Path", "Count", "Purpose"], source_rows),
        "",
        "## Finding summary",
        "",
        table(
            ["Severity", "Count"],
            [
                ["error", summary.get("error", 0)],
                ["warning", summary.get("warning", 0)],
                ["info", summary.get("info", 0)],
            ],
        ),
        "",
        "## Operation source links",
        "",
        table(
            ["Operation", "Metadata", "Typed op", "OpenAPI matches", "AsyncAPI matches", "STRIDE"],
            link_rows,
        ),
        "",
        "## Findings",
        "",
        table(["Severity", "Source", "Code", "Message", "Remediation"], finding_rows) if finding_rows else "No findings.",
        "",
        "## Generated artifact",
        "",
        "```text",
        rel(SYNC_MANIFEST),
        "```",
        "",
        "## Validation",
        "",
        "```bash",
        "task docs:threat-model:sync:check",
        "task docs:threat-model:check",
        "mkdocs build --strict",
        "```",
        "",
        "## Enterprise value",
        "",
        "- New typed operations cannot silently bypass threat-model metadata.",
        "- Structurizr enterprise security-review views remain a required architecture evidence source.",
        "- OpenAPI mutating surfaces are visible for security review.",
        "- AsyncAPI NATS / JetStream channels are visible for command/event boundary review.",
        "- Operation metadata links STRIDE, trust boundaries, attack surfaces, mitigations, and residual risks to generated contracts.",
        "",
    ]

    SYNC_DOC.parent.mkdir(parents=True, exist_ok=True)
    SYNC_DOC.write_text("\n".join(doc), encoding="utf-8")
    print(f"Wrote {rel(SYNC_DOC)}")


if __name__ == "__main__":
    main()
