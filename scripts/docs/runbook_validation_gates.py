#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from runbook_catalog_lib import (
    CATALOG_JSON,
    OPERATIONS_DIR,
    ROOT,
    RUNBOOKS_DIR,
    operation_catalog,
    runbook_files,
    validate_all,
    write_catalog,
)

GENERATED_DIR = ROOT / "docs/operations/generated/runbooks"
REPORT_JSON = GENERATED_DIR / "runbook-validation-gates.json"
REPORT_MD = GENERATED_DIR / "validation-gates.md"
MANIFEST_JSON = GENERATED_DIR / "runbook-docs-manifest.json"

REQUIRED_EVIDENCE = {"operation_events", "audit_events", "workflow_journal"}
HIGH_IMPACT = {"high", "critical"}
APPROVAL_ROLES = {
    "admin",
    "operator",
    "owner",
    "platform_admin",
    "release_manager",
    "security_admin",
    "security_reviewer",
}
MAX_STEP_TIMEOUT_SECONDS = 1800
MAX_RUNBOOK_TIMEOUT_SECONDS = 7200

RETIRED_PATTERNS = [
    "legacy" + "_" + "intent",
    "sync" + "_" + "bash",
    "tofu" + "_" + "deploy",
    "/" + "api" + "/" + "action" + "/" + "update",
    "dashboard" + "_" + "api",
]

FORBIDDEN_EXECUTION_KEYS = {
    "command",
    "commands",
    "shell",
    "script",
    "inline_script",
    "inlineScript",
    "subprocess",
    "exec",
    "executable",
}

SIMPLE_MODE_TECHNICAL_TERMS = {
    "gitops",
    "blueprint",
    "drift",
    "nats",
    "jetstream",
    "vault",
    "opa",
    "kubernetes",
    "asyncapi",
    "openapi",
}


@dataclass
class GateResult:
    id: str
    title: str
    severity: str
    status: str
    message: str
    evidence: list[str]
    remediation: str


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def run_command(args: list[str]) -> tuple[int, str, str]:
    completed = subprocess.run(args, cwd=ROOT, text=True, capture_output=True)
    return completed.returncode, completed.stdout.strip(), completed.stderr.strip()


def result(
    gate_id: str,
    title: str,
    severity: str,
    status: str,
    message: str,
    evidence: list[str] | None = None,
    remediation: str = "Review the generated validation report and update runbooks/*.yaml.",
) -> GateResult:
    return GateResult(
        id=gate_id,
        title=title,
        severity=severity,
        status=status,
        message=message,
        evidence=evidence or [],
        remediation=remediation,
    )


def walk_forbidden_execution_fields(value: Any, path: str = "") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            next_path = f"{path}.{key}" if path else str(key)
            if key in FORBIDDEN_EXECUTION_KEYS:
                findings.append(next_path)
            findings.extend(walk_forbidden_execution_fields(child, next_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(walk_forbidden_execution_fields(child, f"{path}[{index}]"))
    return findings


def runbooks_raw() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in runbook_files():
        data = load_yaml(path)
        data["_path"] = path
        data["_source_file"] = rel(path)
        rows.append(data)
    return rows


def generated_runbook_page_name(name: str) -> str:
    return name.replace("_", "-").lower() + ".md"


def validate_no_retired_text(paths: list[Path]) -> list[str]:
    findings: list[str] = []
    for path in paths:
        if not path.exists():
            continue
        files = [p for p in path.rglob("*") if p.is_file()] if path.is_dir() else [path]
        for file_path in files:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
            for pattern in RETIRED_PATTERNS:
                if pattern in text:
                    findings.append(f"{rel(file_path)} contains retired architecture token")
    return findings


def gate_schema_validation() -> GateResult:
    try:
        validate_all()
    except SystemExit as exc:
        return result(
            "RB-GATE-001",
            "Runbook schema and catalog validation",
            "blocking",
            "fail",
            str(exc),
            ["scripts/docs/runbook_catalog_lib.py", "runbooks/*.yaml"],
            "Run task docs:runbooks:check and fix all schema, filename, typed operation, approval, evidence, and safety errors.",
        )
    return result(
        "RB-GATE-001",
        "Runbook schema and catalog validation",
        "blocking",
        "pass",
        "All runbooks satisfy the runbook metadata catalog schema and typed-operation catalog validation.",
        ["runbooks/*.yaml", "operations/*.yaml"],
    )


def gate_no_direct_execution(runbooks: list[dict[str, Any]]) -> GateResult:
    findings: list[str] = []
    for runbook in runbooks:
        source = runbook["_source_file"]
        for field_path in walk_forbidden_execution_fields(runbook):
            findings.append(f"{source}: {field_path}")

    if findings:
        return result(
            "RB-GATE-002",
            "No direct shell or script execution in runbooks",
            "blocking",
            "fail",
            "Runbooks must orchestrate typed operations only. Forbidden execution fields were found.",
            findings,
            "Remove direct execution fields and replace them with typed operation references under spec.steps[].operation.",
        )

    return result(
        "RB-GATE-002",
        "No direct shell or script execution in runbooks",
        "blocking",
        "pass",
        "No direct shell/script execution fields were found. Runbooks preserve typed-operation-only execution semantics.",
        ["runbooks/*.yaml"],
    )



def has_enterprise_approval_role(runbook: dict[str, Any]) -> bool:
    spec = runbook.get("spec") or {}

    policy = spec.get("policy") or {}
    approval = spec.get("approval") or {}
    governance = spec.get("governance") or {}

    candidates: list[str] = []

    for mapping in [policy, approval, governance]:
        if not isinstance(mapping, dict):
            continue

        for key in ["minimumRole", "role"]:
            value = mapping.get(key)
            if isinstance(value, str):
                candidates.append(value)

        for key in ["approvalRoles", "roles", "reviewerRoles"]:
            value = mapping.get(key)
            if isinstance(value, list):
                candidates.extend(str(item) for item in value)

        approvers = mapping.get("approvers")
        if isinstance(approvers, list):
            for approver in approvers:
                if isinstance(approver, dict) and isinstance(approver.get("role"), str):
                    candidates.append(approver["role"])

    return any(role in APPROVAL_ROLES for role in candidates)


def gate_approval_policy(runbooks: list[dict[str, Any]]) -> GateResult:
    findings: list[str] = []
    for runbook in runbooks:
        source = runbook["_source_file"]
        spec = runbook.get("spec") or {}
        severity = str(spec.get("severity") or "").lower()
        policy = spec.get("policy") or {}
        steps = spec.get("steps") or []
        approval_steps = [step for step in steps if step.get("requiresApproval") is True]

        if severity in HIGH_IMPACT and spec.get("requiresApproval") is not True:
            findings.append(f"{source}: high-impact runbook must set spec.requiresApproval=true")
        if severity in HIGH_IMPACT and not approval_steps:
            findings.append(f"{source}: high-impact runbook must have at least one approval-gated step")
        if spec.get("requiresApproval") is True and not has_enterprise_approval_role(runbook):
            findings.append(f"{source}: approval-gated runbook must use an enterprise approval role")
        if spec.get("requiresApproval") is True and policy.get("evidenceRequired") is not True:
            findings.append(f"{source}: approval-gated runbook must require evidence")
        if spec.get("requiresApproval") is True and not policy.get("approvalReason"):
            findings.append(f"{source}: approval-gated runbook must document approvalReason")

    if findings:
        return result(
            "RB-GATE-003",
            "Approval and policy gate",
            "blocking",
            "fail",
            "Approval and policy metadata is incomplete for one or more runbooks.",
            findings,
            "Update spec.requiresApproval, spec.policy.minimumRole, spec.policy.evidenceRequired, and step-level approval gates.",
        )

    return result(
        "RB-GATE-003",
        "Approval and policy gate",
        "blocking",
        "pass",
        "High-impact and approval-gated runbooks include enterprise approval metadata.",
        ["runbooks/*.yaml"],
    )


def gate_evidence_coverage(runbooks: list[dict[str, Any]]) -> GateResult:
    findings: list[str] = []
    for runbook in runbooks:
        source = runbook["_source_file"]
        evidence = set((runbook.get("spec") or {}).get("evidence") or [])
        missing = sorted(REQUIRED_EVIDENCE - evidence)
        if missing:
            findings.append(f"{source}: missing evidence types: {', '.join(missing)}")

    if findings:
        return result(
            "RB-GATE-004",
            "Evidence coverage gate",
            "blocking",
            "fail",
            "One or more runbooks do not declare the required audit and workflow evidence sources.",
            findings,
            "Add operation_events, audit_events, and workflow_journal to spec.evidence.",
        )

    return result(
        "RB-GATE-004",
        "Evidence coverage gate",
        "blocking",
        "pass",
        "All runbooks declare operation events, audit events, and workflow journal evidence.",
        ["runbooks/*.yaml"],
    )


def gate_operation_contract_coverage(catalog: dict[str, Any]) -> GateResult:
    findings: list[str] = []
    for runbook in catalog.get("runbooks", []):
        for step in runbook.get("steps", []):
            evidence = f"{runbook['name']} step {step['order']} operation {step['operation']}"
            if not step.get("natsSubject"):
                findings.append(f"{evidence}: operation has no NATS subject metadata")
            elif not str(step.get("natsSubject")).startswith("pocketlab."):
                findings.append(f"{evidence}: NATS subject should start with pocketlab.")
            if not step.get("apiEntrypoints"):
                findings.append(f"{evidence}: operation has no API entrypoint metadata")

    if findings:
        return result(
            "RB-GATE-005",
            "Typed operation contract evidence gate",
            "warning",
            "warn",
            "Some referenced typed operations are missing NATS or API evidence metadata.",
            findings,
            "Update operations/*.yaml spec.natsSubject and spec.apiEntrypoints so runbook docs can prove the FastAPI/NATS path.",
        )

    return result(
        "RB-GATE-005",
        "Typed operation contract evidence gate",
        "warning",
        "pass",
        "All runbook steps reference typed operations with API and NATS evidence metadata.",
        ["operations/*.yaml", "runbooks/*.yaml"],
    )


def gate_timeout_controls(runbooks: list[dict[str, Any]]) -> GateResult:
    warnings: list[str] = []
    for runbook in runbooks:
        source = runbook["_source_file"]
        total = 0
        for step in (runbook.get("spec") or {}).get("steps") or []:
            timeout = step.get("timeoutSeconds")
            if isinstance(timeout, int):
                total += timeout
                if timeout > MAX_STEP_TIMEOUT_SECONDS:
                    warnings.append(f"{source}: step {step.get('name')} timeout {timeout}s exceeds {MAX_STEP_TIMEOUT_SECONDS}s")
        if total > MAX_RUNBOOK_TIMEOUT_SECONDS:
            warnings.append(f"{source}: total declared step timeout {total}s exceeds {MAX_RUNBOOK_TIMEOUT_SECONDS}s")

    if warnings:
        return result(
            "RB-GATE-006",
            "Timeout and bounded execution gate",
            "warning",
            "warn",
            "Some runbooks have long declared timeout windows.",
            warnings,
            "Review step timeoutSeconds and split long remediation workflows into smaller auditable runbooks.",
        )

    return result(
        "RB-GATE-006",
        "Timeout and bounded execution gate",
        "warning",
        "pass",
        "Runbook timeout metadata is bounded within runbook validation gates guidance.",
        ["runbooks/*.yaml"],
    )


def gate_simple_mode_labels(runbooks: list[dict[str, Any]]) -> GateResult:
    findings: list[str] = []
    for runbook in runbooks:
        source = runbook["_source_file"]
        label = str((runbook.get("spec") or {}).get("simpleLabel") or "")
        lower = label.lower()
        for term in SIMPLE_MODE_TECHNICAL_TERMS:
            if term in lower:
                findings.append(f"{source}: simpleLabel contains technical term '{term}': {label}")

    if findings:
        return result(
            "RB-GATE-007",
            "Simple Mode language gate",
            "warning",
            "warn",
            "Some Simple Mode labels contain technical terminology.",
            findings,
            "Replace technical labels with Simple Mode wording such as Guided Fixes, Start Guided Fix, Needs Approval, or Proof of What Happened.",
        )

    return result(
        "RB-GATE-007",
        "Simple Mode language gate",
        "warning",
        "pass",
        "Simple Mode runbook labels avoid the configured technical terms.",
        ["runbooks/*.yaml"],
    )


def gate_generated_docs_freshness(catalog: dict[str, Any]) -> GateResult:
    findings: list[str] = []
    expected_files = {
        "index.md",
        "operation-map.md",
        "approval-matrix.md",
        "evidence-matrix.md",
        "simple-mode.md",
        "runbook-catalog.json",
        "runbook-docs-manifest.json",
    }
    for runbook in catalog.get("runbooks", []):
        expected_files.add(generated_runbook_page_name(runbook["name"]))

    for filename in sorted(expected_files):
        if not (GENERATED_DIR / filename).exists():
            findings.append(f"missing generated file: {rel(GENERATED_DIR / filename)}")

    if MANIFEST_JSON.exists():
        try:
            manifest = json.loads(MANIFEST_JSON.read_text(encoding="utf-8"))
            generated_pages = {Path(item).name for item in manifest.get("generatedPages", [])}
            missing_from_manifest = sorted(expected_files - generated_pages - {"runbook-catalog.json"})
            if missing_from_manifest:
                findings.append("manifest missing generated pages: " + ", ".join(missing_from_manifest))
        except json.JSONDecodeError as exc:
            findings.append(f"invalid docs manifest JSON: {exc}")
    else:
        findings.append(f"missing docs manifest: {rel(MANIFEST_JSON)}")

    if findings:
        return result(
            "RB-GATE-008",
            "Generated documentation freshness gate",
            "blocking",
            "fail",
            "Generated runbook documentation is missing or stale.",
            findings,
            "Run task docs:runbooks:docs and then rerun task docs:runbooks:gates:check.",
        )

    return result(
        "RB-GATE-008",
        "Generated documentation freshness gate",
        "blocking",
        "pass",
        "Generated runbook documentation is present for the current catalog.",
        ["docs/operations/generated/runbooks/"],
    )


def gate_no_retired_tokens() -> GateResult:
    findings = validate_no_retired_text(
        [
            RUNBOOKS_DIR,
            GENERATED_DIR,
            ROOT / "docs/operations/runbook-automation.md",
            ROOT / "scripts/docs/runbook_catalog_lib.py",
            ROOT / "scripts/docs/generate_runbook_catalog.py",
            ROOT / "scripts/docs/check_runbook_catalog.py",
            ROOT / "scripts/docs/generate_runbook_docs.py",
            ROOT / "scripts/docs/check_runbook_docs.py",
            ROOT / "scripts/docs/runbook_validation_gates.py",
        ]
    )
    if findings:
        return result(
            "RB-GATE-009",
            "Retired architecture token gate",
            "blocking",
            "fail",
            "Retired architecture tokens were found in runbook metadata, docs, or generators.",
            findings,
            "Remove retired symbols and use typed operations, FastAPI, NATS / JetStream, workers, audit events, and generated docs terminology.",
        )
    return result(
        "RB-GATE-009",
        "Retired architecture token gate",
        "blocking",
        "pass",
        "No retired architecture tokens were found in native runbook capability runbook paths.",
        ["runbooks/", "scripts/docs/", "docs/operations/generated/runbooks/"],
    )


def gate_rollback_safety(runbooks: list[dict[str, Any]]) -> GateResult:
    findings: list[str] = []
    for runbook in runbooks:
        source = runbook["_source_file"]
        spec = runbook.get("spec") or {}
        severity = str(spec.get("severity") or "").lower()
        rollback = spec.get("rollback") or {}
        safety = spec.get("safety") or {}
        if severity in HIGH_IMPACT and not rollback.get("operation"):
            findings.append(f"{source}: high-impact runbook should declare spec.rollback.operation")
        if severity in HIGH_IMPACT and not safety.get("notes"):
            findings.append(f"{source}: high-impact runbook should declare spec.safety.notes")

    if findings:
        return result(
            "RB-GATE-010",
            "Rollback and safety review gate",
            "warning",
            "warn",
            "Some high-impact runbooks need stronger rollback or safety metadata.",
            findings,
            "Add spec.rollback.operation where possible and keep spec.safety.notes explicit for operator review.",
        )
    return result(
        "RB-GATE-010",
        "Rollback and safety review gate",
        "warning",
        "pass",
        "High-impact runbooks include rollback and safety metadata suitable for review.",
        ["runbooks/*.yaml"],
    )


def build_report() -> dict[str, Any]:
    # Regenerate docs first so the gate evaluates current generated artifacts.
    subprocess.run(["python3", "scripts/docs/generate_runbook_docs.py"], cwd=ROOT, check=True)

    catalog = write_catalog()
    runbooks = runbooks_raw()

    gates = [
        gate_schema_validation(),
        gate_no_direct_execution(runbooks),
        gate_approval_policy(runbooks),
        gate_evidence_coverage(runbooks),
        gate_operation_contract_coverage(catalog),
        gate_timeout_controls(runbooks),
        gate_simple_mode_labels(runbooks),
        gate_generated_docs_freshness(catalog),
        gate_no_retired_tokens(),
        gate_rollback_safety(runbooks),
    ]

    blocking_failures = [gate for gate in gates if gate.severity == "blocking" and gate.status == "fail"]
    warnings = [gate for gate in gates if gate.status == "warn"]

    return {
        "apiVersion": "pocketlab.io/v1alpha1",
        "kind": "RunbookValidationGatesReport",
        "metadata": {
            "name": "pocketlab-runbook-validation-gates",
            "title": "Pocket Lab Runbook Validation Gates",
            "tier": "7C",
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "sourceOfTruth": "runbooks/*.yaml and operations/*.yaml",
        },
        "summary": {
            "runbookCount": catalog["summary"]["runbookCount"],
            "operationReferenceCount": catalog["summary"]["operationReferenceCount"],
            "gateCount": len(gates),
            "blockingFailureCount": len(blocking_failures),
            "warningCount": len(warnings),
            "status": "fail" if blocking_failures else "pass",
        },
        "gates": [asdict(gate) for gate in gates],
        "remediation": [asdict(gate) for gate in gates if gate.status in {"fail", "warn"}],
    }


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


def write_report(report: dict[str, Any]) -> None:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(report, indent=2, sort_keys=False) + "\n", encoding="utf-8")

    rows = []
    for gate in report["gates"]:
        rows.append(
            [
                gate["id"],
                gate["title"],
                gate["severity"],
                gate["status"],
                gate["message"],
                gate["remediation"],
            ]
        )

    parts: list[str] = []
    parts.append("# Runbook Validation Gates\n")
    parts.append(
        '!!! note "Generated runbook validation report"\n'
        "    This page is generated from `runbooks/*.yaml`, `operations/*.yaml`, and the generated runbook catalog. Update source metadata, not this generated page.\n"
    )
    parts.append("## Summary\n")
    parts.append(
        table(
            ["Metric", "Value"],
            [
                ["Runbooks", report["summary"]["runbookCount"]],
                ["Typed operation step references", report["summary"]["operationReferenceCount"]],
                ["Validation gates", report["summary"]["gateCount"]],
                ["Blocking failures", report["summary"]["blockingFailureCount"]],
                ["Warnings", report["summary"]["warningCount"]],
                ["Overall status", report["summary"]["status"]],
            ],
        )
    )
    parts.append("\n## Gate Results\n")
    parts.append(table(["Gate", "Title", "Severity", "Status", "Message", "Remediation"], rows))
    parts.append("\n## Gate Semantics\n")
    parts.append("- `blocking` gates fail CI/release readiness when their status is `fail`.")
    parts.append("- `warning` gates do not block generation yet, but they identify enterprise-readiness improvements.")
    parts.append("- Runbooks must orchestrate typed operations only and must not introduce direct script execution or an external automation control plane.")
    parts.append("- Runbook validation gates verify metadata, documentation, safety, approval, and evidence readiness. Runtime execution remains worker-owned and governed by typed operations.\n")
    parts.append("## Validation Commands\n")
    parts.append("```bash\ntask docs:runbooks:gates:check\ntask docs:runbooks:docs:check\nmkdocs build --strict\n```\n")

    REPORT_MD.write_text("\n".join(parts).rstrip() + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate Pocket Lab runbook validation gates.")
    parser.add_argument("--write", action="store_true", help="Write JSON and Markdown validation gate reports.")
    parser.add_argument("--check", action="store_true", help="Write reports and fail on blocking gate failures.")
    args = parser.parse_args()

    if not args.write and not args.check:
        args.check = True

    report = build_report()
    write_report(report)

    print(f"Wrote {rel(REPORT_JSON)}")
    print(f"Wrote {rel(REPORT_MD)}")
    print(f"Runbook validation gates: {report['summary']['gateCount']}")
    print(f"Blocking failures: {report['summary']['blockingFailureCount']}")
    print(f"Warnings: {report['summary']['warningCount']}")

    if args.check and report["summary"]["blockingFailureCount"]:
        print("\nBlocking runbook validation gate failures:")
        for gate in report["gates"]:
            if gate["severity"] == "blocking" and gate["status"] == "fail":
                print(f"- {gate['id']} {gate['title']}: {gate['message']}")
                for item in gate.get("evidence", [])[:10]:
                    print(f"  - {item}")
        raise SystemExit(1)

    print("Runbook validation gates passed")


if __name__ == "__main__":
    main()
