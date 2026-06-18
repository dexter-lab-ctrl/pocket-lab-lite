#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
RUNBOOKS_DIR = ROOT / "runbooks"
OPERATIONS_DIR = ROOT / "operations"
CATALOG_JSON = ROOT / "docs/operations/generated/runbooks/runbook-catalog.json"
CATALOG_MD = ROOT / "docs/operations/generated/runbooks/index.md"
OVERVIEW_MD = ROOT / "docs/operations/runbook-automation.md"

REQUIRED_RUNBOOK_TOP = ["apiVersion", "kind", "metadata", "spec"]
REQUIRED_METADATA = ["name", "title", "description", "owner", "tags"]
REQUIRED_SPEC = [
    "professionalLabel",
    "simpleLabel",
    "category",
    "severity",
    "trigger",
    "requiresApproval",
    "policy",
    "prerequisites",
    "steps",
    "evidence",
    "safety",
]
REQUIRED_STEP = ["name", "title", "operation", "description", "requiresApproval", "timeoutSeconds", "onFailure"]
REQUIRED_EVIDENCE = {"operation_events", "audit_events", "workflow_journal"}
ALLOWED_SEVERITIES = {"low", "medium", "high", "critical"}
ALLOWED_ON_FAILURE = {"stop", "continue"}
RETIRED_PATTERNS = [
    "legacy" + "_" + "intent",
    "sync" + "_" + "bash",
    "tofu" + "_" + "deploy",
    "/" + "api" + "/" + "action" + "/" + "update",
    "dashboard" + "_" + "api",
]


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def operation_catalog() -> dict[str, dict[str, Any]]:
    operations: dict[str, dict[str, Any]] = {}
    for path in sorted(OPERATIONS_DIR.glob("*.yaml")):
        data = load_yaml(path)
        name = str(data.get("metadata", {}).get("name") or path.stem)
        operations[name] = {
            "name": name,
            "path": str(path.relative_to(ROOT)),
            "title": data.get("metadata", {}).get("title", name),
            "tags": data.get("metadata", {}).get("tags", []),
            "professionalLabel": data.get("spec", {}).get("professionalLabel", ""),
            "simpleLabel": data.get("spec", {}).get("simpleLabel", ""),
            "natsSubject": data.get("spec", {}).get("natsSubject", ""),
            "apiEntrypoints": data.get("spec", {}).get("apiEntrypoints", []),
        }
    return operations


def runbook_files() -> list[Path]:
    return sorted(RUNBOOKS_DIR.glob("*.yaml"))


def load_runbooks() -> list[dict[str, Any]]:
    runbooks: list[dict[str, Any]] = []
    for path in runbook_files():
        data = load_yaml(path)
        data["_source_file"] = str(path.relative_to(ROOT))
        runbooks.append(data)
    return runbooks


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def assert_no_retired_text(path: Path) -> None:
    text = path.read_text(encoding="utf-8", errors="ignore")
    found = [pattern for pattern in RETIRED_PATTERNS if pattern in text]
    if found:
        fail(f"{path.relative_to(ROOT)} contains retired architecture token(s)")


def validate_runbook(data: dict[str, Any], operations: dict[str, dict[str, Any]]) -> list[str]:
    source = data.get("_source_file", "<unknown>")
    errors: list[str] = []

    for field in REQUIRED_RUNBOOK_TOP:
        if field not in data:
            errors.append(f"{source}: missing top-level field {field}")

    if data.get("apiVersion") != "pocketlab.io/v1alpha1":
        errors.append(f"{source}: apiVersion must be pocketlab.io/v1alpha1")
    if data.get("kind") != "Runbook":
        errors.append(f"{source}: kind must be Runbook")

    metadata = data.get("metadata") or {}
    spec = data.get("spec") or {}

    for field in REQUIRED_METADATA:
        if metadata.get(field) in (None, "", []):
            errors.append(f"{source}: metadata.{field} is required")

    name = str(metadata.get("name") or "")
    if name and source != f"runbooks/{name}.yaml":
        errors.append(f"{source}: filename must match metadata.name, expected runbooks/{name}.yaml")

    for field in REQUIRED_SPEC:
        if spec.get(field) in (None, "", []):
            errors.append(f"{source}: spec.{field} is required")

    if spec.get("severity") not in ALLOWED_SEVERITIES:
        errors.append(f"{source}: spec.severity must be one of {sorted(ALLOWED_SEVERITIES)}")

    if not isinstance(spec.get("requiresApproval"), bool):
        errors.append(f"{source}: spec.requiresApproval must be boolean")

    if not spec.get("professionalLabel") or not spec.get("simpleLabel"):
        errors.append(f"{source}: professional and simple labels are required")

    policy = spec.get("policy") or {}
    for field in ["approvalReason", "minimumRole", "evidenceRequired"]:
        if policy.get(field) in (None, "", []):
            errors.append(f"{source}: spec.policy.{field} is required")

    if not isinstance(policy.get("evidenceRequired"), bool):
        errors.append(f"{source}: spec.policy.evidenceRequired must be boolean")

    evidence = set(spec.get("evidence") or [])
    missing_evidence = sorted(REQUIRED_EVIDENCE - evidence)
    if missing_evidence:
        errors.append(f"{source}: spec.evidence missing required evidence types: {', '.join(missing_evidence)}")

    steps = spec.get("steps") or []
    if not steps:
        errors.append(f"{source}: at least one step is required")

    seen_step_names: set[str] = set()
    approval_step_seen = False

    for index, step in enumerate(steps):
        step_id = f"{source}: spec.steps[{index}]"
        for field in REQUIRED_STEP:
            if step.get(field) in (None, "", []):
                errors.append(f"{step_id}.{field} is required")

        step_name = str(step.get("name") or "")
        if step_name in seen_step_names:
            errors.append(f"{step_id}.name duplicates another step: {step_name}")
        seen_step_names.add(step_name)

        operation = str(step.get("operation") or "")
        if operation not in operations:
            errors.append(f"{step_id}.operation references unknown typed operation: {operation}")

        if not isinstance(step.get("requiresApproval"), bool):
            errors.append(f"{step_id}.requiresApproval must be boolean")
        if step.get("requiresApproval") is True:
            approval_step_seen = True

        timeout = step.get("timeoutSeconds")
        if not isinstance(timeout, int) or timeout <= 0:
            errors.append(f"{step_id}.timeoutSeconds must be a positive integer")

        if step.get("onFailure") not in ALLOWED_ON_FAILURE:
            errors.append(f"{step_id}.onFailure must be one of {sorted(ALLOWED_ON_FAILURE)}")

    rollback = spec.get("rollback") or {}
    if rollback:
        operation = rollback.get("operation")
        if operation and operation not in operations:
            errors.append(f"{source}: spec.rollback.operation references unknown typed operation: {operation}")
        if "requiresApproval" in rollback and not isinstance(rollback.get("requiresApproval"), bool):
            errors.append(f"{source}: spec.rollback.requiresApproval must be boolean")

    if spec.get("requiresApproval") is True and not approval_step_seen:
        errors.append(f"{source}: spec.requiresApproval is true but no step requires approval")

    safety = spec.get("safety") or {}
    if safety.get("impact") not in ALLOWED_SEVERITIES:
        errors.append(f"{source}: spec.safety.impact must be one of {sorted(ALLOWED_SEVERITIES)}")
    if not safety.get("notes"):
        errors.append(f"{source}: spec.safety.notes is required")

    return errors


def validate_all() -> None:
    if not RUNBOOKS_DIR.exists():
        fail("runbooks/ directory is missing")
    operations = operation_catalog()
    if not operations:
        fail("operations/*.yaml typed operation metadata is missing")
    runbooks = load_runbooks()
    if not runbooks:
        fail("runbooks/*.yaml catalog is empty")

    for path in runbook_files():
        assert_no_retired_text(path)

    all_errors: list[str] = []
    names: set[str] = set()
    for runbook in runbooks:
        name = str(runbook.get("metadata", {}).get("name") or "")
        if name in names:
            all_errors.append(f"duplicate runbook metadata.name: {name}")
        names.add(name)
        all_errors.extend(validate_runbook(runbook, operations))

    if all_errors:
        fail("Runbook catalog validation failed:\n" + "\n".join(f"  - {error}" for error in all_errors))


def build_catalog() -> dict[str, Any]:
    validate_all()
    operations = operation_catalog()
    runbooks = []

    for data in load_runbooks():
        metadata = data["metadata"]
        spec = data["spec"]
        steps = []
        for index, step in enumerate(spec.get("steps", []), start=1):
            operation = operations[step["operation"]]
            steps.append(
                {
                    "order": index,
                    "name": step["name"],
                    "title": step["title"],
                    "operation": step["operation"],
                    "operationTitle": operation["title"],
                    "professionalOperationLabel": operation["professionalLabel"],
                    "simpleOperationLabel": operation["simpleLabel"],
                    "natsSubject": operation["natsSubject"],
                    "apiEntrypoints": operation["apiEntrypoints"],
                    "description": step["description"],
                    "requiresApproval": step["requiresApproval"],
                    "timeoutSeconds": step["timeoutSeconds"],
                    "onFailure": step["onFailure"],
                }
            )

        runbooks.append(
            {
                "name": metadata["name"],
                "title": metadata["title"],
                "description": metadata["description"],
                "owner": metadata["owner"],
                "tags": metadata.get("tags", []),
                "sourceFile": data["_source_file"],
                "professionalLabel": spec["professionalLabel"],
                "simpleLabel": spec["simpleLabel"],
                "category": spec["category"],
                "severity": spec["severity"],
                "trigger": spec.get("trigger", {}),
                "requiresApproval": spec["requiresApproval"],
                "policy": spec.get("policy", {}),
            "approval": spec.get("approval", {}),
            "governance": spec.get("governance", {}),
                "prerequisites": spec.get("prerequisites", []),
                "steps": steps,
                "rollback": spec.get("rollback", {}),
                "evidence": spec.get("evidence", []),
                "safety": spec.get("safety", {}),
            }
        )

    return {
        "apiVersion": "pocketlab.io/v1alpha1",
        "kind": "RunbookCatalog",
        "metadata": {
            "name": "pocketlab-runbook-catalog",
            "title": "Pocket Lab Runbook Metadata Catalog",
            "tier": "7A",
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "sourceOfTruth": "runbooks/*.yaml",
        },
        "summary": {
            "runbookCount": len(runbooks),
            "operationReferenceCount": sum(len(runbook["steps"]) for runbook in runbooks),
            "approvalRunbookCount": sum(1 for runbook in runbooks if runbook["requiresApproval"]),
            "categories": sorted({runbook["category"] for runbook in runbooks}),
            "severities": sorted({runbook["severity"] for runbook in runbooks}),
        },
        "runbooks": sorted(runbooks, key=lambda item: item["name"]),
    }


def write_catalog() -> dict[str, Any]:
    catalog = build_catalog()
    CATALOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    CATALOG_JSON.write_text(json.dumps(catalog, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    return catalog
