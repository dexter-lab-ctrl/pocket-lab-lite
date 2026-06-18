#!/usr/bin/env python3
from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any

from generate_policy_evidence import ROOT, build_manifest

GENERATED = "<!-- GENERATED FILE - DO NOT EDIT. Run task docs:security:policies. -->\n\n"
OUTPUTS = {
    "docs/security/policy-guardrails-guide.md": "guide",
    "docs/security/generated/policy-reference.md": "reference",
    "docs/security/generated/policy-operation-map.md": "operation_map",
    "docs/security/generated/compliance-controls-reference.md": "controls",
}


def esc(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", "<br>")


def list_text(values: Any) -> str:
    if not values:
        return "—"
    if isinstance(values, list):
        return ", ".join(str(v) for v in values) or "—"
    return str(values)


def policy_by_id(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(p.get("id")): p for p in manifest.get("policies") or [] if p.get("id")}


def render_guide(manifest: dict[str, Any]) -> str:
    summary = manifest["summary"]
    formal = "Yes" if manifest.get("formal_opa_bundle_found") else "No — using repository-native policy metadata plus embedded guardrail evidence."
    modes = manifest.get("governance_modes") or {}
    lines = [
        "# Policy Guardrails Guide",
        "",
        "This page is generated from Pocket Lab policy metadata, operation metadata, runbook metadata, runtime approval/governance services, and existing security documentation sources.",
        "",
        "## Source Status",
        "",
        f"- Formal `.rego` bundle discovered: **{formal}**",
        f"- Policy metadata bundles: **{len(manifest.get('policy_bundles') or [])}**",
        f"- Policies documented: **{summary['policy_count']}**",
        f"- Controls documented: **{summary['control_count']}**",
        f"- Operations inspected: **{summary['operation_count']}**",
        f"- Runbooks inspected: **{summary['runbook_count']}**",
        "",
        "## Runtime Guardrail Boundary",
        "",
        "Pocket Lab policy documentation does not change runtime behavior. User actions continue to flow through React / Vite PWA → FastAPI Control API → NATS / JetStream → Workers → Events → FastAPI → UI.",
        "",
        "Runbooks orchestrate typed operations. Policies document the governance expectations around those typed operations, approvals, and audit events; they do not authorize frontend shell execution or frontend NATS access.",
        "",
        "## Mode Semantics",
        "",
        "| Mode | Meaning |",
        "| --- | --- |",
    ]
    for mode, data in sorted(modes.items()):
        lines.append(f"| {esc(data.get('label') or mode)} | {esc(data.get('description'))} |")
    lines.extend([
        "",
        "## Guardrail Summary",
        "",
        "| Policy | Severity | Mode | Simple wording |",
        "| --- | --- | --- | --- |",
    ])
    for p in manifest.get("policies") or []:
        lines.append(f"| {esc(p.get('title'))} | {esc(p.get('severity'))} | {esc(p.get('mode'))} | {esc(p.get('simpleSummary'))} |")
    lines.extend([
        "",
        "## Policy Decision Evidence",
        "",
        "Policy decision evidence is expected in generated operation/runbook documentation, event contracts, and audit subjects. Personal Mode auto-approval remains audit logged. Enterprise Mode requires strict human authorization and reason capture for governed runbooks.",
        "",
        "See also:",
        "",
        "- [OPA Policy Reference](generated/policy-reference.md)",
        "- [Operation-to-policy Mapping](generated/policy-operation-map.md)",
        "- [Compliance Controls Reference](generated/compliance-controls-reference.md)",
        "- [Security Architecture & Threat Model](security-architecture-threat-model.md)",
    ])
    return GENERATED + "\n".join(lines) + "\n"


def render_reference(manifest: dict[str, Any]) -> str:
    lines = [
        "# OPA Policy Reference",
        "",
        "This generated reference describes OPA-style policy guardrails and repository-native policy metadata found in the current Pocket Lab source tree.",
        "",
    ]
    if not manifest.get("formal_opa_bundle_found"):
        lines.extend([
            "> No standalone `.rego` bundle was found in this repository snapshot. policy and security evidence therefore uses `security/policies/*.yaml` as a minimal repository-native policy metadata layer and records embedded UI guardrail evidence without changing runtime behavior.",
            "",
        ])
    for p in manifest.get("policies") or []:
        lines.extend([
            f"## {p.get('title')}",
            "",
            f"- Policy ID: `{p.get('id')}`",
            f"- Package: `{p.get('package', 'n/a')}`",
            f"- Severity: **{p.get('severity', 'n/a')}**",
            f"- Decision mode: **{p.get('mode', 'n/a')}**",
            f"- Source: `{p.get('source')}`",
            "",
            p.get("summary") or "",
            "",
            "**Simple Mode wording:** " + (p.get("simpleSummary") or "—"),
            "",
            "**Mapped controls:** " + list_text(p.get("controls")),
            "",
            "**Evidence events:** " + list_text(p.get("evidenceEvents")),
            "",
        ])
        if p.get("rego"):
            lines.extend(["```rego", p["rego"].rstrip(), "```", ""])
    return GENERATED + "\n".join(lines) + "\n"


def render_operation_map(manifest: dict[str, Any]) -> str:
    policies = policy_by_id(manifest)
    lines = [
        "# Operation-to-policy Mapping",
        "",
        "This generated page maps typed operations and native runbooks to policy guardrails. It is documentation-only and preserves worker-owned execution through NATS / JetStream.",
        "",
        "## Typed Operations",
        "",
        "| Operation | Policies | Source |",
        "| --- | --- | --- |",
    ]
    for item in manifest.get("operation_policy_map") or []:
        policy_titles = [policies[p].get("title", p) for p in item.get("policies") or [] if p in policies]
        lines.append(f"| `{esc(item['operation'])}` | {esc(list_text(policy_titles))} | `{esc(item['source'])}` |")
    lines.extend([
        "",
        "## Runbooks",
        "",
        "| Runbook | Policies | Requires approval | Minimum role | Source |",
        "| --- | --- | --- | --- | --- |",
    ])
    for item in manifest.get("runbook_policy_map") or []:
        policy_titles = [policies[p].get("title", p) for p in item.get("policies") or [] if p in policies]
        lines.append(f"| `{esc(item['runbook'])}` | {esc(list_text(policy_titles))} | {esc(item.get('requires_approval'))} | {esc(item.get('minimum_role') or '—')} | `{esc(item['source'])}` |")
    validation = manifest.get("validation") or {}
    lines.extend([
        "",
        "## Freshness Signals",
        "",
        f"- Unknown policy operation references: `{validation.get('unknown_policy_operations') or []}`",
        f"- Unknown policy runbook references: `{validation.get('unknown_policy_runbooks') or []}`",
        f"- Operations without explicit policy mapping: `{validation.get('operations_without_policy_mapping') or []}`",
        f"- Runbooks without explicit policy mapping: `{validation.get('runbooks_without_policy_mapping') or []}`",
    ])
    return GENERATED + "\n".join(lines) + "\n"


def render_controls(manifest: dict[str, Any]) -> str:
    lines = [
        "# Compliance Controls Reference",
        "",
        "This generated reference maps Pocket Lab policy guardrails to repository evidence sources for security review, auditability, and release readiness.",
        "",
        "| Control | Family | Description | Evidence |",
        "| --- | --- | --- | --- |",
    ]
    for cid, control in sorted((manifest.get("controls") or {}).items()):
        evidence = "<br>".join(f"`{item}`" for item in control.get("evidence") or []) or "—"
        lines.append(f"| `{esc(cid)}` {esc(control.get('title'))} | {esc(control.get('family'))} | {esc(control.get('description'))} | {evidence} |")
    lines.extend([
        "",
        "## Source Fingerprints",
        "",
        "The policy evidence manifest records SHA-256 fingerprints for source files used by this generator. Use `task docs:security:policies:check` or `task docs:security:full-check` to detect stale generated output.",
    ])
    return GENERATED + "\n".join(lines) + "\n"


def render_outputs() -> dict[str, str]:
    manifest = build_manifest()
    return {
        "docs/security/policy-guardrails-guide.md": render_guide(manifest),
        "docs/security/generated/policy-reference.md": render_reference(manifest),
        "docs/security/generated/policy-operation-map.md": render_operation_map(manifest),
        "docs/security/generated/compliance-controls-reference.md": render_controls(manifest),
    }


def main() -> int:
    outputs = render_outputs()
    for rel_path, content in outputs.items():
        path = ROOT / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"Wrote {rel_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
