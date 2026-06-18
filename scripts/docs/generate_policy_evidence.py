#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/security/generated/policy-evidence-manifest.json"
BUNDLE_GLOBS = ["security/policies/*.yaml", "policy/**/*.yaml", "policies/**/*.yaml", "opa/**/*.yaml"]
REGO_GLOBS = ["security/**/*.rego", "policy/**/*.rego", "policies/**/*.rego", "opa/**/*.rego"]
SOURCE_GLOBS = [
    "security/policies/*.yaml",
    "src/tabs/PolicyGuardrailsTab.jsx",
    "pocket-lab-final-structure/runtime/api_fastapi/services/approval_policy.py",
    "pocket-lab-final-structure/runtime/api_fastapi/services/governance_settings.py",
    "operations/*.yaml",
    "runbooks/*.yaml",
    "contracts/operations/pocketlab-typed-operations.json",
    "contracts/generated/openapi.json",
    "contracts/asyncapi/pocketlab-nats-jetstream.yaml",
    "docs/security/security-architecture-threat-model.md",
    "docs/security/generated/threat-model/*.md",
]


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def read_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def paths_from_globs(patterns: list[str]) -> list[Path]:
    found: list[Path] = []
    for pattern in patterns:
        found.extend(p for p in ROOT.glob(pattern) if p.is_file())
    return sorted(set(found), key=lambda p: rel(p))


def flatten_controls(bundle: dict[str, Any]) -> dict[str, dict[str, Any]]:
    controls = ((bundle.get("spec") or {}).get("controls") or {})
    return {str(k): dict(v or {}) for k, v in sorted(controls.items())}


def load_policy_bundles() -> list[dict[str, Any]]:
    bundles: list[dict[str, Any]] = []
    for path in paths_from_globs(BUNDLE_GLOBS):
        data = read_yaml(path)
        if data.get("kind") == "PolicyBundle":
            bundles.append({"source": rel(path), "data": data})
    return bundles


def load_operations() -> list[dict[str, Any]]:
    operations: list[dict[str, Any]] = []
    for path in sorted((ROOT / "operations").glob("*.yaml")):
        data = read_yaml(path)
        meta = data.get("metadata") or {}
        spec = data.get("spec") or {}
        security = spec.get("security") or {}
        operations.append({
            "name": meta.get("name") or path.stem,
            "title": meta.get("title") or path.stem,
            "tags": sorted(meta.get("tags") or []),
            "nats_subject": spec.get("natsSubject"),
            "api_entrypoints": sorted(spec.get("apiEntrypoints") or []),
            "safety": spec.get("safety") or "",
            "security": security,
            "source": rel(path),
        })
    return sorted(operations, key=lambda item: item["name"])


def load_runbooks() -> list[dict[str, Any]]:
    runbooks: list[dict[str, Any]] = []
    for path in sorted((ROOT / "runbooks").glob("*.yaml")):
        data = read_yaml(path)
        meta = data.get("metadata") or {}
        spec = data.get("spec") or {}
        policy = spec.get("policy") or {}
        approval = spec.get("approval") or {}
        governance = spec.get("governance") or {}
        steps = []
        for step in spec.get("steps") or []:
            if isinstance(step, dict):
                steps.append(step.get("operation") or step.get("typedOperation") or step.get("name"))
        runbooks.append({
            "name": meta.get("name") or path.stem,
            "title": meta.get("title") or path.stem,
            "severity": spec.get("severity"),
            "requires_approval": bool(spec.get("requiresApproval")),
            "minimum_role": policy.get("minimumRole") or approval.get("minimumRole") or governance.get("minimumRole"),
            "approval_reason_required": bool(policy.get("approvalReason") or approval.get("approvalReason") or governance.get("approvalReason")),
            "evidence_required": bool(policy.get("evidenceRequired") or approval.get("evidenceRequired") or governance.get("evidenceRequired")),
            "operations": sorted(x for x in steps if x),
            "policy": policy,
            "source": rel(path),
        })
    return sorted(runbooks, key=lambda item: item["name"])


def load_contract_operations() -> list[str]:
    path = ROOT / "contracts/operations/pocketlab-typed-operations.json"
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    candidates = payload.get("operations") if isinstance(payload, dict) else payload
    names: list[str] = []
    if isinstance(candidates, list):
        for item in candidates:
            if isinstance(item, dict):
                names.append(str(item.get("operation") or item.get("name") or ""))
    return sorted(x for x in names if x)


def extract_embedded_policy_ids() -> list[str]:
    path = ROOT / "src/tabs/PolicyGuardrailsTab.jsx"
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="ignore")
    # The current UI has an inline policies object. This scanner is intentionally shallow
    # and evidence-only; runtime policy behavior remains unchanged.
    match = re.search(r"const\s+policies\s*=\s*\{(?P<body>.*?)\n\s*\};", text, flags=re.S)
    if not match:
        return []
    return sorted(set(re.findall(r"\n\s*([A-Za-z0-9_-]+):\s*\{", match.group("body"))))


def build_manifest() -> dict[str, Any]:
    bundles = load_policy_bundles()
    operations = load_operations()
    runbooks = load_runbooks()
    policies: list[dict[str, Any]] = []
    controls: dict[str, dict[str, Any]] = {}
    governance_modes: dict[str, Any] = {}

    for bundle in bundles:
        spec = bundle["data"].get("spec") or {}
        controls.update(flatten_controls(bundle["data"]))
        governance_modes.update(spec.get("governanceModes") or {})
        for policy in spec.get("policies") or []:
            item = dict(policy or {})
            item["source"] = bundle["source"]
            policies.append(item)

    policy_ids = sorted(str(p.get("id")) for p in policies if p.get("id"))
    operation_names = {op["name"] for op in operations}
    runbook_names = {rb["name"] for rb in runbooks}

    operation_policy_map = []
    for op in operations:
        matched = []
        for policy in policies:
            applies = ((policy.get("appliesTo") or {}).get("operations") or [])
            if op["name"] in applies:
                matched.append(policy.get("id"))
        operation_policy_map.append({"operation": op["name"], "policies": sorted(x for x in matched if x), "source": op["source"]})

    runbook_policy_map = []
    for rb in runbooks:
        matched = []
        for policy in policies:
            applies = ((policy.get("appliesTo") or {}).get("runbooks") or [])
            if rb["name"] in applies:
                matched.append(policy.get("id"))
        runbook_policy_map.append({"runbook": rb["name"], "policies": sorted(x for x in matched if x), "requires_approval": rb["requires_approval"], "minimum_role": rb["minimum_role"], "source": rb["source"]})

    unknown_policy_operations = sorted({op for p in policies for op in ((p.get("appliesTo") or {}).get("operations") or []) if op not in operation_names})
    unknown_policy_runbooks = sorted({rb for p in policies for rb in ((p.get("appliesTo") or {}).get("runbooks") or []) if rb not in runbook_names})

    source_files = [{"path": rel(p), "sha256": sha256(p)} for p in paths_from_globs(SOURCE_GLOBS)]
    rego_files = [{"path": rel(p), "sha256": sha256(p)} for p in paths_from_globs(REGO_GLOBS)]

    return {
        "schema": "pocketlab.policyEvidenceManifest.v1",
        "generated_by": "scripts/docs/generate_policy_evidence.py",
        "runtime_behavior_changed": False,
        "formal_opa_bundle_found": bool(rego_files),
        "policy_bundles": [{"path": item["source"], "sha256": sha256(ROOT / item["source"])} for item in bundles],
        "embedded_ui_guardrails": extract_embedded_policy_ids(),
        "rego_files": rego_files,
        "governance_modes": governance_modes,
        "controls": controls,
        "policies": sorted(policies, key=lambda item: str(item.get("id"))),
        "operations": operations,
        "runbooks": runbooks,
        "typed_operations_contract_names": load_contract_operations(),
        "operation_policy_map": operation_policy_map,
        "runbook_policy_map": runbook_policy_map,
        "validation": {
            "unknown_policy_operations": unknown_policy_operations,
            "unknown_policy_runbooks": unknown_policy_runbooks,
            "operations_without_policy_mapping": sorted(item["operation"] for item in operation_policy_map if not item["policies"]),
            "runbooks_without_policy_mapping": sorted(item["runbook"] for item in runbook_policy_map if not item["policies"]),
        },
        "source_files": source_files,
        "summary": {
            "policy_count": len(policies),
            "control_count": len(controls),
            "operation_count": len(operations),
            "runbook_count": len(runbooks),
            "mapped_operation_count": sum(1 for item in operation_policy_map if item["policies"]),
            "mapped_runbook_count": sum(1 for item in runbook_policy_map if item["policies"]),
            "source_file_count": len(source_files),
        },
    }


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(build_manifest(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
