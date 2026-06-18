#!/usr/bin/env python3
"""Check deployment evidence deployment evidence manifest integrity."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "docs/platform/generated/deployment-evidence-manifest.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if not MANIFEST.exists():
        print(f"Missing {MANIFEST.relative_to(ROOT)}", file=sys.stderr)
        return 1
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    errors: list[str] = []
    if m.get("schema_version") != "pocketlab.deployment_evidence.v1":
        errors.append("unexpected deployment evidence schema_version")
    summary = m.get("source_summary", {})
    if summary.get("playbook_count", 0) <= 0:
        errors.append("no Ansible playbooks were discovered")
    if summary.get("role_count", 0) <= 0:
        errors.append("no Ansible roles were discovered")
    if summary.get("bootstrap_script_count", 0) <= 0:
        errors.append("no bootstrap/platform scripts were discovered")
    for section in ["playbooks", "inventories_and_vars", "iac_catalog"]:
        for rec in m.get("ansible", {}).get(section, []):
            if rec.get("yaml_error"):
                errors.append(f"YAML error in {rec.get('path')}: {rec.get('yaml_error')}")
    for role in m.get("ansible", {}).get("roles", []):
        if role.get("task_count", 0) <= 0:
            errors.append(f"role without readable task summaries: {role.get('path')}")
        for err in role.get("yaml_errors", []):
            errors.append(f"YAML error in {err.get('path')}: {err.get('error')}")
    for finding in m.get("forbidden_active_token_findings", []):
        errors.append(f"forbidden active deployment token {finding.get('token')} in {finding.get('path')}")
    records = []
    records += m.get("bootstrap_and_platform_scripts", [])
    records += m.get("platform_source_docs", [])
    records += m.get("environment_and_runtime_files", [])
    for key in ["playbooks", "inventories_and_vars", "iac_catalog", "collections"]:
        records += m.get("ansible", {}).get(key, [])
    for rec in records:
        path = ROOT / rec.get("path", "")
        if not path.exists():
            errors.append(f"manifest references missing file: {rec.get('path')}")
            continue
        if rec.get("sha256") and sha256(path) != rec.get("sha256"):
            errors.append(f"manifest fingerprint stale for {rec.get('path')}")
    if errors:
        print("Deployment evidence check failed:", file=sys.stderr)
        for e in errors:
            print(f"- {e}", file=sys.stderr)
        return 1
    print("Deployment evidence check passed")
    print(f"Playbooks={summary.get('playbook_count')} roles={summary.get('role_count')} scripts={summary.get('bootstrap_script_count')}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
