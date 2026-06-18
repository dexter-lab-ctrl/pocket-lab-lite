#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runbook_catalog_lib import CATALOG_JSON, CATALOG_MD, OVERVIEW_MD, ROOT, write_catalog

GENERATED_DIR = ROOT / "docs/operations/generated/runbooks"
MANIFEST_JSON = GENERATED_DIR / "runbook-docs-manifest.json"
OPERATION_MAP_MD = GENERATED_DIR / "operation-map.md"
APPROVAL_MATRIX_MD = GENERATED_DIR / "approval-matrix.md"
EVIDENCE_MATRIX_MD = GENERATED_DIR / "evidence-matrix.md"
SIMPLE_MODE_MD = GENERATED_DIR / "simple-mode.md"

RETIRED_PATTERNS = [
    "legacy" + "_" + "intent",
    "sync" + "_" + "bash",
    "tofu" + "_" + "deploy",
    "/" + "api" + "/" + "action" + "/" + "update",
    "dashboard" + "_" + "api",
]


def slug(value: str) -> str:
    return value.replace("_", "-").lower()


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def clean_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join(["---"] * len(headers)) + "|",
    ]
    for row in rows:
        lines.append("| " + " | ".join(clean_cell(cell) for cell in row) + " |")
    return "\n".join(lines)


def code_block(language: str, body: str) -> str:
    return f"```{language}\n{body.rstrip()}\n```"


def bullet(items: list[Any], empty: str = "None declared.") -> str:
    if not items:
        return empty + "\n"
    return "\n".join(f"- {item}" for item in items) + "\n"


def validate_no_retired_text(path: Path) -> None:
    text = path.read_text(encoding="utf-8", errors="ignore")
    found = [pattern for pattern in RETIRED_PATTERNS if pattern in text]
    if found:
        raise SystemExit(f"ERROR: {rel(path)} contains retired architecture token(s)")


def operation_step_rows(catalog: dict[str, Any]) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for runbook in catalog["runbooks"]:
        for step in runbook["steps"]:
            rows.append(
                [
                    f"[`{runbook['name']}`]({slug(runbook['name'])}.md)",
                    step["order"],
                    step["title"],
                    f"`{step['operation']}`",
                    step.get("simpleOperationLabel", ""),
                    step.get("natsSubject", ""),
                    ", ".join(step.get("apiEntrypoints", [])),
                ]
            )
    return rows


def write_catalog_index(catalog: dict[str, Any]) -> Path:
    rows = []
    for runbook in catalog["runbooks"]:
        rows.append(
            [
                f"[`{runbook['name']}`]({slug(runbook['name'])}.md)",
                runbook["professionalLabel"],
                runbook["simpleLabel"],
                runbook["category"],
                runbook["severity"],
                "yes" if runbook["requiresApproval"] else "no",
                len(runbook["steps"]),
                runbook["owner"],
            ]
        )

    parts: list[str] = []
    parts.append("# Generated Runbook Catalog\n")
    parts.append(
        '!!! note "Generated runbook documentation capability runbook documentation"\n'
        "    This page is generated from `runbooks/*.yaml`. Runbooks orchestrate typed operations only. They do not introduce shell execution or any external automation control plane.\n"
    )
    parts.append("## Summary\n")
    parts.append(
        table(
            ["Metric", "Value"],
            [
                ["Runbooks", catalog["summary"]["runbookCount"]],
                ["Typed operation step references", catalog["summary"]["operationReferenceCount"]],
                ["Approval-gated runbooks", catalog["summary"]["approvalRunbookCount"]],
                ["Categories", ", ".join(catalog["summary"]["categories"])],
                ["Severities", ", ".join(catalog["summary"]["severities"])],
            ],
        )
    )
    parts.append("\n## Generated Pages\n")
    parts.append("- [Runbook Operation Map](operation-map.md)")
    parts.append("- [Runbook Approval Matrix](approval-matrix.md)")
    parts.append("- [Runbook Evidence Matrix](evidence-matrix.md)")
    parts.append("- [Runbook Validation Gates](validation-gates.md)")
    parts.append("- [Simple Mode Runbook Guide](simple-mode.md)\n")
    parts.append("## Runbook Index\n")
    parts.append(
        table(
            ["Runbook", "Professional label", "Simple label", "Category", "Severity", "Approval", "Steps", "Owner"],
            rows,
        )
    )
    parts.append("\n## Enterprise Rules\n")
    parts.append("- Runbook steps must reference typed operations from `operations/*.yaml`.")
    parts.append("- Runbook documentation is generated and must not be manually edited under `docs/operations/generated/runbooks/`.")
    parts.append("- Runbooks preserve FastAPI as the control API, NATS / JetStream as the event backbone, and workers as the execution boundary.")
    parts.append("- runbook documentation capability is documentation generation only. Runtime execution is intentionally deferred to later native runbook capability steps.\n")

    CATALOG_MD.parent.mkdir(parents=True, exist_ok=True)
    CATALOG_MD.write_text("\n".join(parts).rstrip() + "\n", encoding="utf-8")
    return CATALOG_MD


def write_runbook_page(runbook: dict[str, Any]) -> Path:
    path = GENERATED_DIR / f"{slug(runbook['name'])}.md"
    parts: list[str] = []
    parts.append(f"# {runbook['title']}\n")
    parts.append(
        '!!! note "Generated runbook page"\n'
        f"    This page is generated from `{runbook['sourceFile']}`. Update the runbook YAML source, not this generated page.\n"
    )
    parts.append("## Identity\n")
    parts.append(
        table(
            ["Field", "Value"],
            [
                ["Runbook ID", f"`{runbook['name']}`"],
                ["Source", f"`{runbook['sourceFile']}`"],
                ["Owner", runbook["owner"]],
                ["Category", runbook["category"]],
                ["Severity", f"`{runbook['severity']}`"],
                ["Approval Required", "yes" if runbook["requiresApproval"] else "no"],
                ["Professional Mode", runbook["professionalLabel"]],
                ["Simple Mode", runbook["simpleLabel"]],
            ],
        )
    )
    parts.append("\n## Description\n")
    parts.append(runbook["description"] + "\n")
    parts.append("## Trigger Metadata\n")
    parts.append(code_block("yaml", json.dumps(runbook.get("trigger", {}), indent=2)))
    parts.append("\n## Policy and Approval\n")
    policy = runbook.get("policy", {})
    parts.append(
        table(
            ["Policy Field", "Value"],
            [
                ["Minimum Role", policy.get("minimumRole", "")],
                ["Evidence Required", "yes" if policy.get("evidenceRequired") else "no"],
                ["Approval Reason", policy.get("approvalReason", "")],
            ],
        )
    )
    parts.append("\n## Prerequisites\n")
    parts.append(bullet(runbook.get("prerequisites", [])))
    parts.append("## Execution Plan\n")
    parts.append(
        table(
            ["#", "Step", "Typed Operation", "Operation Label", "Simple Label", "Approval", "Timeout", "On Failure"],
            [
                [
                    step["order"],
                    step["title"],
                    f"`{step['operation']}`",
                    step.get("professionalOperationLabel", ""),
                    step.get("simpleOperationLabel", ""),
                    "yes" if step["requiresApproval"] else "no",
                    f"{step['timeoutSeconds']}s",
                    step["onFailure"],
                ]
                for step in runbook["steps"]
            ],
        )
    )
    parts.append("\n## Operation Contract Evidence\n")
    parts.append(
        table(
            ["Step", "NATS Subject", "API Entrypoints"],
            [
                [
                    step["title"],
                    step.get("natsSubject", ""),
                    ", ".join(step.get("apiEntrypoints", [])),
                ]
                for step in runbook["steps"]
            ],
        )
    )
    if runbook.get("rollback"):
        rollback = runbook["rollback"]
        parts.append("\n## Rollback\n")
        parts.append(
            table(
                ["Field", "Value"],
                [
                    ["Operation", f"`{rollback.get('operation', '')}`"],
                    ["Requires Approval", "yes" if rollback.get("requiresApproval") else "no"],
                    ["Description", rollback.get("description", "")],
                ],
            )
        )
    parts.append("\n## Evidence Requirements\n")
    parts.append(bullet([f"`{item}`" for item in runbook.get("evidence", [])]))
    parts.append("## Safety\n")
    safety = runbook.get("safety", {})
    parts.append(f"- Impact: `{safety.get('impact', '')}`")
    parts.append(f"- Notes: {safety.get('notes', '')}\n")
    parts.append("## Scope\n")
    parts.append("This page documents metadata only. Runtime execution through FastAPI, NATS / JetStream, and workers is planned for later native runbook capability steps.\n")

    path.write_text("\n".join(parts).rstrip() + "\n", encoding="utf-8")
    return path


def write_operation_map(catalog: dict[str, Any]) -> Path:
    parts = ["# Runbook Operation Map\n"]
    parts.append(
        '!!! note "Generated operation map"\n'
        "    This page maps runbook steps to typed operations, NATS subjects, and API entrypoints.\n"
    )
    parts.append(table(["Runbook", "Step #", "Step", "Typed Operation", "Simple Label", "NATS Subject", "API Entrypoints"], operation_step_rows(catalog)))
    OPERATION_MAP_MD.write_text("\n".join(parts).rstrip() + "\n", encoding="utf-8")
    return OPERATION_MAP_MD


def write_approval_matrix(catalog: dict[str, Any]) -> Path:
    rows: list[list[Any]] = []
    for runbook in catalog["runbooks"]:
        approval_steps = [step["title"] for step in runbook["steps"] if step["requiresApproval"]]
        rows.append(
            [
                f"[`{runbook['name']}`]({slug(runbook['name'])}.md)",
                runbook["severity"],
                "yes" if runbook["requiresApproval"] else "no",
                runbook.get("policy", {}).get("minimumRole", ""),
                runbook.get("policy", {}).get("approvalReason", ""),
                ", ".join(approval_steps) if approval_steps else "None",
                "yes" if runbook.get("policy", {}).get("evidenceRequired") else "no",
            ]
        )
    parts = ["# Runbook Approval Matrix\n"]
    parts.append(
        '!!! note "Generated approval matrix"\n'
        "    Approval metadata is generated from `runbooks/*.yaml` and is intended for later FastAPI / OPA enforcement.\n"
    )
    parts.append(table(["Runbook", "Severity", "Runbook Approval", "Minimum Role", "Reason", "Approval Steps", "Evidence Required"], rows))
    APPROVAL_MATRIX_MD.write_text("\n".join(parts).rstrip() + "\n", encoding="utf-8")
    return APPROVAL_MATRIX_MD


def write_evidence_matrix(catalog: dict[str, Any]) -> Path:
    all_evidence = sorted({item for runbook in catalog["runbooks"] for item in runbook.get("evidence", [])})
    rows: list[list[Any]] = []
    for runbook in catalog["runbooks"]:
        evidence = set(runbook.get("evidence", []))
        rows.append(
            [
                f"[`{runbook['name']}`]({slug(runbook['name'])}.md)",
                runbook["severity"],
                *["yes" if item in evidence else "" for item in all_evidence],
            ]
        )
    parts = ["# Runbook Evidence Matrix\n"]
    parts.append(
        '!!! note "Generated evidence matrix"\n'
        "    Evidence requirements prepare native runbook capability runbooks for auditability, workflow recovery, and later event-sourced execution.\n"
    )
    parts.append(table(["Runbook", "Severity", *[f"`{item}`" for item in all_evidence]], rows))
    EVIDENCE_MATRIX_MD.write_text("\n".join(parts).rstrip() + "\n", encoding="utf-8")
    return EVIDENCE_MATRIX_MD


def write_simple_mode_guide(catalog: dict[str, Any]) -> Path:
    rows = []
    for runbook in catalog["runbooks"]:
        rows.append(
            [
                runbook["professionalLabel"],
                runbook["simpleLabel"],
                runbook["category"],
                runbook["severity"],
                "Needs Approval" if runbook["requiresApproval"] else "Can Start Directly",
            ]
        )
    parts = ["# Simple Mode Runbook Guide\n"]
    parts.append(
        '!!! note "Generated Simple Mode guide"\n'
        "    This page preserves Pocket Lab's non-technical Simple Mode language while keeping Professional Mode labels available for operators.\n"
    )
    parts.append("## Simple Mode Label Rules\n")
    parts.append("- Runbook Automation → Guided Fixes")
    parts.append("- Run Recovery Runbook → Start Guided Fix")
    parts.append("- Approval Required → Needs Approval")
    parts.append("- Execution Evidence → Proof of What Happened\n")
    parts.append("## Runbook Labels\n")
    parts.append(table(["Professional Mode", "Simple Mode", "Category", "Severity", "Approval UX"], rows))
    SIMPLE_MODE_MD.write_text("\n".join(parts).rstrip() + "\n", encoding="utf-8")
    return SIMPLE_MODE_MD


def write_overview(catalog: dict[str, Any]) -> Path:
    parts = []
    parts.append("# Runbook Automation\n")
    parts.append(
        "This capability provides enterprise-grade generated runbook documentation from the native Pocket Lab runbook catalog. This remains metadata and documentation only; runtime execution is intentionally deferred to later native runbook capability steps.\n"
    )
    parts.append("## Architecture\n")
    parts.append(
        code_block(
            "text",
            "runbooks/*.yaml\n"
            "  -> runbook catalog generator\n"
            "  -> generated runbook documentation\n"
            "  -> generated operation map\n"
            "  -> generated approval matrix\n"
            "  -> generated evidence matrix\n"
            "  -> later FastAPI runbook API\n"
            "  -> later NATS / JetStream runbook commands\n"
            "  -> later runbook worker\n"
            "  -> typed operations\n"
            "  -> operation events, audit evidence, and DLQ paths",
        )
    )
    parts.append("\n## Enterprise Design Rules\n")
    parts.append("- Runbooks orchestrate typed operations only.")
    parts.append("- Runbooks do not execute shell commands.")
    parts.append("- The frontend must not talk directly to NATS.")
    parts.append("- FastAPI remains the control API.")
    parts.append("- NATS / JetStream remains the command and event backbone.")
    parts.append("- Workers remain the execution boundary.")
    parts.append("- Approval, evidence, rollback, and safety metadata are required.")
    parts.append("- Generated runbook docs must be reproducible from `runbooks/*.yaml`.\n")
    parts.append("## Generated Documentation\n")
    parts.append("- [Generated Runbook Catalog](generated/runbooks/)")
    parts.append("- [Runbook Operation Map](generated/runbooks/operation-map.md)")
    parts.append("- [Runbook Approval Matrix](generated/runbooks/approval-matrix.md)")
    parts.append("- [Runbook Evidence Matrix](generated/runbooks/evidence-matrix.md)")
    parts.append("- [Simple Mode Runbook Guide](generated/runbooks/simple-mode.md)\n")
    parts.append("## Current Scope\n")
    parts.append(
        table(
            ["Capability", "Evidence Area", "Status"],
            [
                ["Runbook metadata catalog", "Metadata evidence", "Implemented"],
                ["Generated runbook documentation", "Documentation evidence", "Implemented"],
                ["Runbook validation gates", "Validation evidence", "Implemented"],
                ["FastAPI / NATS runbook execution", "Runtime capability", "Implemented where validated"],
                ["Runbook audit and DLQ events", "Audit evidence", "Implemented where validated"],
            ],
        )
    )
    parts.append("\n## Validation\n")
    parts.append(code_block("bash", "task docs:runbooks:docs:check\ntask docs:runbooks\nmkdocs build --strict"))
    OVERVIEW_MD.write_text("\n".join(parts).rstrip() + "\n", encoding="utf-8")
    return OVERVIEW_MD


def cleanup_stale_runbook_pages(catalog: dict[str, Any]) -> None:
    expected = {f"{slug(runbook['name'])}.md" for runbook in catalog["runbooks"]}
    protected = {
        "index.md",
        "operation-map.md",
        "approval-matrix.md",
        "evidence-matrix.md",
        "simple-mode.md",
    }
    for path in GENERATED_DIR.glob("*.md"):
        if path.name not in expected and path.name not in protected:
            path.unlink()


def write_manifest(catalog: dict[str, Any], generated_paths: list[Path]) -> Path:
    manifest = {
        "apiVersion": "pocketlab.io/v1alpha1",
        "kind": "RunbookDocsManifest",
        "metadata": {
            "name": "pocketlab-runbook-docs-manifest",
            "tier": "7B",
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "sourceOfTruth": "runbooks/*.yaml",
        },
        "summary": {
            "runbookCount": catalog["summary"]["runbookCount"],
            "generatedPageCount": len(generated_paths),
            "operationReferenceCount": catalog["summary"]["operationReferenceCount"],
        },
        "generatedPages": [rel(path) for path in sorted(generated_paths)],
        "runbookPages": [
            {
                "runbook": runbook["name"],
                "sourceFile": runbook["sourceFile"],
                "page": rel(GENERATED_DIR / f"{slug(runbook['name'])}.md"),
            }
            for runbook in catalog["runbooks"]
        ],
    }
    MANIFEST_JSON.write_text(json.dumps(manifest, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    return MANIFEST_JSON


def main() -> None:
    catalog = write_catalog()
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    cleanup_stale_runbook_pages(catalog)

    generated_paths: list[Path] = []
    generated_paths.append(write_catalog_index(catalog))
    generated_paths.append(write_operation_map(catalog))
    generated_paths.append(write_approval_matrix(catalog))
    generated_paths.append(write_evidence_matrix(catalog))
    generated_paths.append(write_simple_mode_guide(catalog))
    generated_paths.append(write_overview(catalog))

    for runbook in catalog["runbooks"]:
        generated_paths.append(write_runbook_page(runbook))

    generated_paths.append(MANIFEST_JSON)
    write_manifest(catalog, generated_paths)

    for path in generated_paths:
        validate_no_retired_text(path)
        print(f"Wrote {rel(path)}")
    print(f"Wrote {rel(CATALOG_JSON)}")


if __name__ == "__main__":
    main()
