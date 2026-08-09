#!/usr/bin/env python3
"""Generate deterministic Pocket Lab Lite documentation intelligence and UX surfaces.

The generator is intentionally static/read-only. It consumes repository-owned source and
already-promoted sanitized runtime evidence. It never probes live services, captures runtime,
or promotes evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import posixpath
import re
import sys
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

import jsonschema

ROOT = Path(__file__).resolve().parents[3]
EXPERIENCE = ROOT / "contracts/metadata/documentation-experience.json"
EXPERIENCE_SCHEMA = ROOT / "schemas/documentation/documentation-experience.schema.json"
INTELLIGENCE_SCHEMA = ROOT / "schemas/documentation/documentation-intelligence.schema.json"
DOC_PLATFORM = ROOT / "contracts/metadata/documentation-platform.json"
KNOWLEDGE_META = ROOT / "contracts/metadata/knowledge-base.json"
ARCH = ROOT / "architecture/metadata/pocket-lab-architecture.json"
ARCH_RUNTIME = ROOT / "architecture/runtime-baselines/server-phone.json"
OP_HEALTH = ROOT / "contracts/generated/runtime/domain-operational-health.json"
RUNTIME_BASELINE = ROOT / "contracts/parity/runtime-verification-baseline.json"
PARITY_DRIFT = ROOT / "contracts/generated/parity/runtime-drift.json"
LIMITATIONS = ROOT / "contracts/generated/parity/accepted-limitations.json"
REASONS = ROOT / "contracts/generated/reason-codes.json"
RELEASE_CHANGES = ROOT / "contracts/generated/knowledge/release-changes.json"
RELEASES = ROOT / "contracts/generated/knowledge/releases.json"
GENERATOR = ROOT / "scripts/docs/intelligence/generate_documentation_intelligence.py"
OUT = ROOT / "contracts/generated/documentation-intelligence"
DEV = ROOT / "docs/generated/development/intelligence"
PROD = ROOT / "docs/generated/production/intelligence"
EXPERIENCE_DOCS = ROOT / "docs/generated/experience"
HOME_FRAGMENT = ROOT / "docs/generated/home-dashboard.md"
INDEX = OUT / "index.json"

SCHEMA_VERSION = "1.0.0"
HEALTH_PRECEDENCE = {"healthy": 0, "stale": 1, "degraded": 2, "unavailable": 3, "unvalidated": 4}
GOOD_RUNTIME = {"healthy", "online", "ready", "present", "enabled", "ok", "verified"}
BAD_RUNTIME = {"failed", "unavailable", "missing", "stopped", "offline", "error"}
PRIVATE_PATH = re.compile(r"(?:/home/[^/\s]+|/data/data/com\.termux/files/(?:home|usr)|/mnt/[a-zA-Z]/|[A-Za-z]:\\Users\\)")
SECRET = re.compile(r"(?:-----BEGIN [A-Z ]*PRIVATE KEY-----|Bearer\s+[A-Za-z0-9._~+/-]{12,}|(?:password|passwd|token|secret|api[_-]?key|credential|authorization)\s*[=:]\s*[^\s,}\]]{6,}|nats://[^\s/@]+:[^\s/@]+@)", re.I)

DEPENDENCY_SERVICE_MAP = {
    "Caddy": "caddy",
    "FastAPI": "lite-api",
    "NATS/JetStream": "nats",
    "worker": "worker",
    "node agent": "node-agent",
    "core supervisor": "core-supervisor",
    "Tailscale": "tailscaled",
    "SQLite": "sqlite",
    "PhotoPrism runtime": "photoprism",
}

DOMAIN_LABELS = {
    "home": "Home",
    "apps": "Apps",
    "devices": "Devices",
    "security": "Security",
    "recovery": "Backup & Restore",
    "identity": "Identity",
    "rules": "Rules",
}


def load(path: Path, default: Any = None) -> Any:
    if not path.exists():
        if default is not None:
            return default
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, separators=(",", ": ")) + "\n"


def digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def safe_text(label: str, text: str) -> None:
    if PRIVATE_PATH.search(text):
        raise ValueError(f"{label}: private host path leaked into generated documentation")
    if SECRET.search(text):
        raise ValueError(f"{label}: secret-like content leaked into generated documentation")


def frontmatter(title: str, description: str, audience: str, confidence: str = "generated") -> str:
    return (
        "---\n"
        f'title: "{title.replace(chr(34), chr(39))}"\n'
        f'description: "{description.replace(chr(34), chr(39))}"\n'
        "generated: true\n"
        f"audience: {audience}\n"
        f"confidence: {confidence}\n"
        "---\n\n"
    )


def table(headers: list[str], rows: Iterable[Iterable[Any]]) -> str:
    def clean(value: Any) -> str:
        if value is None:
            return "—"
        if isinstance(value, bool):
            return "yes" if value else "no"
        if isinstance(value, (list, tuple)):
            value = ", ".join(str(x) for x in value) if value else "—"
        return str(value).replace("\n", " ").replace("|", "\\|") or "—"
    rows = list(rows)
    result = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    result.extend("| " + " | ".join(clean(v) for v in row) + " |" for row in rows)
    return "\n".join(result) + "\n"


def runtime_state(value: Any) -> str:
    status = str(value or "").strip().lower().replace("_", " ").replace("-", " ")
    if status in GOOD_RUNTIME:
        return "healthy"
    if status in BAD_RUNTIME:
        return "unavailable"
    if status in {"degraded", "repairing", "waiting", "joining", "partial"}:
        return "degraded"
    return "unvalidated"


def comparison_map(runtime: dict[str, Any], domain_id: str) -> dict[str, dict[str, Any]]:
    domain = next((x for x in runtime.get("domains", []) if x.get("id") == domain_id), {})
    return {str(x.get("id")): x for x in domain.get("comparisons", []) if x.get("id")}


def direct_value(comparisons: dict[str, dict[str, Any]], comparison_id: str) -> Any:
    row = comparisons.get(comparison_id, {})
    value = row.get("backend_value")
    return None if isinstance(value, dict) else value


def dependency_health(op: dict[str, Any], arch_runtime: dict[str, Any]) -> list[dict[str, Any]]:
    service_map = {x.get("id"): x for x in arch_runtime.get("services", [])}
    rows: list[dict[str, Any]] = []
    for domain_id, domain in sorted(op["domains"].items()):
        deps = []
        for name in domain.get("dependencies", []):
            service_id = DEPENDENCY_SERVICE_MAP.get(name)
            service = service_map.get(service_id) if service_id else None
            if service:
                state = runtime_state(service.get("status") or service.get("presence"))
                evidence = "verified-runtime-baseline"
                note = f"Runtime baseline reports {service.get('status') or service.get('presence')}."
                source = "architecture/runtime-baselines/server-phone.json"
            else:
                state = "unvalidated"
                evidence = "source-derived"
                note = "Dependency is canonical, but no dedicated promoted runtime health signal is available."
                source = "contracts/metadata/documentation-platform.json"
            deps.append({
                "name": name,
                "state": state,
                "evidence_status": evidence,
                "source": source,
                "note": note,
            })
        rows.append({
            "domain": domain_id,
            "label": DOMAIN_LABELS.get(domain_id, domain_id.title()),
            "operational_health": domain.get("operational_health", "unvalidated"),
            "semantic_parity": domain.get("semantic_parity", "unvalidated"),
            "evidence_status": domain.get("evidence_status", "unvalidated"),
            "freshness": domain.get("freshness", "unvalidated"),
            "reason": domain.get("reason"),
            "dependencies": deps,
            "dependency_summary": dict(sorted(Counter(x["state"] for x in deps).items())),
        })
    return rows


def release_impact(op: dict[str, Any], runtime: dict[str, Any], release_changes: dict[str, Any], parity_drift: dict[str, Any]) -> dict[str, Any]:
    changes = release_changes.get("items", [])
    canonical = changes[0] if changes else {"status": "no-comparable-verified-prior-release", "added": [], "removed": [], "changed": []}
    health_counts = dict(sorted(Counter(x.get("operational_health", "unvalidated") for x in op["domains"].values()).items()))
    parity_counts = dict(sorted(Counter(x.get("runtime_status", "unvalidated") for x in parity_drift.get("items", [])).items()))
    capability_counts = dict(sorted(Counter(x.get("status", "unvalidated") for x in op.get("platform_capabilities", [])).items()))
    dimensions = [
        {"dimension": "source/repository", "status": canonical.get("status", "unvalidated"), "changed": canonical.get("changed", []), "note": canonical.get("note")},
        {"dimension": "operational-health", "status": "current-baseline-only", "changed": [], "note": "Current promoted domain health is available; prior promoted domain health is not fabricated."},
        {"dimension": "semantic-parity", "status": "current-baseline-only", "changed": [], "note": "Current runtime parity is available independently from operational health."},
        {"dimension": "capability-evidence", "status": "current-baseline-only", "changed": [], "note": "Current role-aware platform capability evidence is available."},
        {"dimension": "database", "status": "not-comparable", "changed": [], "note": "No verified prior release schema snapshot is present for a release-to-release delta."},
        {"dimension": "architecture", "status": "not-comparable", "changed": [], "note": "No verified prior architecture snapshot is present for a release-to-release delta."},
    ]
    return {
        "status": canonical.get("status", "unvalidated"),
        "from_release": canonical.get("from"),
        "to_release": runtime.get("release_tag"),
        "source_commit": runtime.get("source_commit"),
        "added": canonical.get("added", []),
        "removed": canonical.get("removed", []),
        "changed": canonical.get("changed", []),
        "note": canonical.get("note", "No verified prior release comparison is available."),
        "current_snapshot": {"operational_health": health_counts, "semantic_parity": parity_counts, "platform_capabilities": capability_counts},
        "dimensions": dimensions,
    }


def runtime_drift(arch_runtime: dict[str, Any], semantic: dict[str, Any]) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for service in arch_runtime.get("services", []):
        expected = service.get("expected_source_match", "not-evaluated")
        presence = service.get("presence", "unknown")
        if expected == "matched":
            classification = "aligned"
        elif expected in {"mismatch", "different"}:
            classification = "configuration-drift"
        elif presence == "missing" and expected != "not-evaluated":
            classification = "expected-but-missing"
        else:
            classification = "not-evaluated"
        entries.append({
            "kind": "service",
            "id": service.get("id"),
            "classification": classification,
            "runtime_status": service.get("status"),
            "presence": presence,
            "expected_source_match": expected,
            "source": "architecture/runtime-baselines/server-phone.json",
        })
    for route in arch_runtime.get("routes", []):
        entries.append({
            "kind": "route",
            "id": route.get("id"),
            "classification": "aligned" if route.get("presence") == "present" else "expected-but-missing",
            "runtime_status": route.get("presence"),
            "presence": route.get("presence"),
            "expected_source_match": "route-contract",
            "source": "architecture/runtime-baselines/server-phone.json",
        })
    for store in arch_runtime.get("datastores", []):
        ok = store.get("presence") == "present" and store.get("integrity") == "ok" and store.get("expected_tables_present") is True
        entries.append({
            "kind": "datastore",
            "id": store.get("id"),
            "classification": "aligned" if ok else "configuration-drift",
            "runtime_status": store.get("integrity"),
            "presence": store.get("presence"),
            "expected_source_match": "schema-expectation",
            "source": "architecture/runtime-baselines/server-phone.json",
        })
    unresolved = arch_runtime.get("verification", {}).get("unresolved_mismatches", [])
    semantic_rows = [{"domain": x.get("id"), "runtime_parity": x.get("runtime_parity"), "mismatch_count": len(x.get("mismatches", []))} for x in semantic.get("items", [])]
    return {
        "configuration_runtime": entries,
        "configuration_summary": dict(sorted(Counter(x["classification"] for x in entries).items())),
        "unresolved_mismatches": unresolved,
        "semantic_drift_independent": semantic_rows,
        "semantic_note": "Semantic parity drift is reported independently and does not prove configuration alignment or operational health.",
    }


def recovery_readiness(op: dict[str, Any], runtime: dict[str, Any]) -> dict[str, Any]:
    health = op["domains"]["recovery"]
    cmp = comparison_map(runtime, "recovery")
    checks = [
        {"name": "Operational health", "status": health.get("operational_health"), "value": health.get("operational_health"), "authority": "release-promoted"},
        {"name": "Evidence freshness", "status": "degraded" if health.get("freshness") == "stale" else "healthy", "value": health.get("freshness"), "authority": "release-promoted"},
        {"name": "Write safety", "status": "degraded" if health.get("write_safety") == "blocked" else "healthy", "value": health.get("write_safety"), "authority": "release-promoted"},
        {"name": "Fresh restore preview required", "status": "degraded" if direct_value(cmp, "recovery-termux-fresh_preview_required") is True else "healthy", "value": direct_value(cmp, "recovery-termux-fresh_preview_required"), "authority": "release-promoted"},
        {"name": "Restore currently allowed", "status": "healthy" if direct_value(cmp, "recovery-termux-restore_allowed") is True else "degraded", "value": direct_value(cmp, "recovery-termux-restore_allowed"), "authority": "release-promoted"},
        {"name": "Projection refresh pending", "status": "degraded" if direct_value(cmp, "recovery-termux-refresh_pending") is True else "healthy", "value": direct_value(cmp, "recovery-termux-refresh_pending"), "authority": "release-promoted"},
        {"name": "Completed restore evidence", "status": "healthy" if (direct_value(cmp, "recovery-termux-completed_restore_count") or 0) > 0 else "unvalidated", "value": direct_value(cmp, "recovery-termux-completed_restore_count"), "authority": "release-promoted"},
    ]
    return {
        "overall": health.get("operational_health"),
        "reason": health.get("reason"),
        "readiness": health.get("readiness"),
        "freshness_age_seconds": health.get("freshness_age_seconds"),
        "freshness_threshold_seconds": health.get("freshness_threshold_seconds"),
        "checks": checks,
        "next_action": "Refresh and explicitly promote runtime evidence before a guarded restore write." if health.get("reason") == "projection_too_old" else "Follow the current Recovery readiness guardrails.",
    }


def fleet_readiness(op: dict[str, Any], runtime: dict[str, Any], arch_runtime: dict[str, Any]) -> dict[str, Any]:
    health = op["domains"]["devices"]
    cmp = comparison_map(runtime, "devices")
    known = direct_value(cmp, "devices-termux-device_count")
    online = direct_value(cmp, "devices-termux-online_count")
    remote = direct_value(cmp, "devices-termux-remote_access_ready")
    identity = direct_value(cmp, "devices-termux-server_identity_expected")
    tailnet_ip = direct_value(cmp, "devices-termux-tailscale_ip_present")
    relation = (arch_runtime.get("runtime_relationships") or [{}])[0]
    checks = [
        {"name": "Protected server-host health", "status": health.get("operational_health"), "value": health.get("operational_health")},
        {"name": "Server identity guard", "status": "healthy" if identity is True else "unavailable", "value": identity},
        {"name": "Remote access readiness", "status": "healthy" if remote is True else "degraded", "value": remote},
        {"name": "Agent presence", "status": runtime_state(relation.get("agent_presence")), "value": relation.get("agent_presence")},
        {"name": "Supervisor presence", "status": runtime_state(relation.get("supervisor_presence")), "value": relation.get("supervisor_presence")},
        {"name": "NATS connectivity", "status": runtime_state(relation.get("nats_connectivity")), "value": relation.get("nats_connectivity")},
    ]
    return {
        "overall": health.get("operational_health"),
        "readiness": health.get("readiness"),
        "known_device_records": known,
        "online_device_records": online,
        "remote_access_ready": remote,
        "tailscale_ip_present": tailnet_ip,
        "checks": checks,
        "interpretation": "Retained stale/offline records do not by themselves degrade the protected server host; fleet counts and protected-host readiness remain separate signals.",
    }


def evidence_lineage(op: dict[str, Any], runtime: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for domain_id, domain in sorted(op["domains"].items()):
        rows.append({
            "domain": domain_id,
            "label": DOMAIN_LABELS.get(domain_id, domain_id.title()),
            "claim": domain.get("operational_health", "unvalidated"),
            "confidence": domain.get("confidence", "unvalidated"),
            "release_tag": runtime.get("release_tag"),
            "source_commit": runtime.get("source_commit"),
            "promoted_at": runtime.get("promoted_at"),
            "sources": [
                "contracts/parity/runtime-verification-baseline.json",
                "contracts/parity/parity-model.json",
                "contracts/metadata/documentation-platform.json",
                "contracts/generated/reason-codes.json",
            ],
            "projection": "contracts/generated/runtime/domain-operational-health.json",
            "generator": "scripts/docs/runtime/generate_domain_operational_health.py",
            "evidence_comparisons": domain.get("source", {}).get("evidence_comparisons", []),
        })
    return rows


def evidence_coverage(op: dict[str, Any], runtime: dict[str, Any]) -> dict[str, Any]:
    baseline = {x.get("id"): x for x in runtime.get("domains", [])}
    dimensions = ("implementation", "api", "termux", "desktop", "mobile", "semantic-parity", "operational-health", "freshness", "lineage")
    cells = []
    for domain_id in sorted(op["domains"]):
        h = op["domains"][domain_id]
        b = baseline.get(domain_id, {})
        values = {
            "implementation": h.get("implementation_status", "unvalidated"),
            "api": b.get("live_api_coverage", "unvalidated"),
            "termux": b.get("live_termux_coverage", "unvalidated"),
            "desktop": "observed" if b.get("live_ui_coverage") == "observed" and "live-desktop" in runtime.get("browser_projects", []) else "unvalidated",
            "mobile": "observed" if b.get("live_ui_coverage") == "observed" and "live-mobile" in runtime.get("browser_projects", []) else "unvalidated",
            "semantic-parity": h.get("semantic_parity", "unvalidated"),
            "operational-health": h.get("operational_health", "unvalidated"),
            "freshness": h.get("freshness", "unvalidated"),
            "lineage": "release-bound" if runtime.get("release_tag") and runtime.get("source_commit") and runtime.get("promoted_at") else "unvalidated",
        }
        for dim in dimensions:
            value = values[dim]
            evidenced = value not in {None, "", "unvalidated", "unknown"}
            cells.append({"domain": domain_id, "dimension": dim, "status": value, "evidenced": evidenced})
    by_domain = {}
    for domain_id in sorted(op["domains"]):
        subset = [x for x in cells if x["domain"] == domain_id]
        count = sum(1 for x in subset if x["evidenced"])
        by_domain[domain_id] = {"evidenced": count, "total": len(subset), "coverage_fraction": f"{count}/{len(subset)}", "confidence": op["domains"][domain_id].get("confidence", "unvalidated")}
    return {"dimensions": list(dimensions), "cells": cells, "by_domain": by_domain}


def limitations_catalog(limitations: dict[str, Any], op: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for item in limitations.get("items", []):
        domain_id = item.get("id")
        h = op.get("domains", {}).get(domain_id, {})
        for category, status in (("accepted-limitation", "accepted"), ("known-gap", "open"), ("unsupported-operation", "unsupported")):
            key = {"accepted-limitation": "accepted_limitations", "known-gap": "known_gaps", "unsupported-operation": "unsupported_operations"}[category]
            for text in item.get(key, []):
                rows.append({
                    "domain": domain_id,
                    "label": item.get("label"),
                    "category": category,
                    "status": status,
                    "description": text,
                    "implementation_status": h.get("implementation_status", "unvalidated"),
                    "operational_health": h.get("operational_health", "unvalidated"),
                })
    return rows


def reason_encyclopedia(payload: dict[str, Any], op: dict[str, Any]) -> list[dict[str, Any]]:
    body = payload.get("reason_codes", {})
    reasons = body.get("reason_codes", []) if isinstance(body, dict) else body
    active: dict[str, list[str]] = {}
    for domain_id, h in op["domains"].items():
        if h.get("reason"):
            active.setdefault(str(h["reason"]), []).append(domain_id)
    rows = []
    for r in reasons:
        code = r.get("code")
        if code == "projection_too_old":
            next_action = "Capture fresh sanitized runtime evidence and explicitly promote it before claiming current readiness."
        elif code == "remote_access_not_ready":
            next_action = "Verify Tailscale readiness and backend reachability; do not infer remote readiness from UI presentation."
        elif code in {"service_unavailable", "read_degraded"}:
            next_action = "Inspect the owning dependency/readiness evidence and recover through the backend-owned path."
        elif r.get("retryable"):
            next_action = "Correct the prerequisite and retry through the owning backend workflow."
        else:
            next_action = "Review the owning evidence and operator guidance before another action."
        rows.append({
            "code": code,
            "domain": r.get("domain"),
            "meaning": r.get("meaning"),
            "user_message": r.get("user_message"),
            "severity": r.get("audit_severity"),
            "retryable": r.get("retryable"),
            "terminal": r.get("terminal"),
            "http_status": r.get("http_status"),
            "observed_in_current_health": sorted(active.get(str(code), [])),
            "next_action": next_action,
        })
    return rows


def scenario_catalog(meta: dict[str, Any], arch: dict[str, Any]) -> list[dict[str, Any]]:
    names = {k: v.get("name", k) for k, v in arch.get("components", {}).items()}
    rows = []
    for journey in meta.get("journeys", []):
        routes = journey.get("routes", [])
        write = any(not str(route).startswith("GET ") for route in routes)
        components = [names.get(x, x) for x in journey.get("components", [])]
        stages = ["User intent", "Pocket Lab Lite UI"]
        if routes:
            stages.append("FastAPI /api/lite/*")
        if write and any(x in journey.get("components", []) for x in ("nats-jetstream", "worker", "workflow-execution", "app-lifecycle-worker", "security-coordinator", "backup-engine", "agent-command-executor")):
            stages.append("NATS / JetStream + execution owner")
        stages.extend(components)
        if write:
            stages.extend(["Sanitized evidence/state", "FastAPI projection", "UI result"])
        else:
            stages.extend(["FastAPI projection", "UI result"])
        dedup = []
        for s in stages:
            if s not in dedup:
                dedup.append(s)
        rows.append({
            "id": journey.get("id"),
            "title": journey.get("title"),
            "domain": journey.get("domain"),
            "confidence": journey.get("confidence", "source-derived"),
            "write_flow": write,
            "routes": routes,
            "components": components,
            "stages": dedup,
            "source_refs": journey.get("source_refs", []),
            "guardrail": "The browser remains presentation/control only; execution and recovery stay with FastAPI and backend runtime owners." if write else "This scenario is read-oriented and does not authorize browser-side execution.",
        })
    return rows


def platform_matrix(op: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted(op.get("platform_capabilities", []), key=lambda x: (x.get("capability_name", ""), x.get("platform", "")))


def dashboard(op: dict[str, Any], runtime: dict[str, Any], coverage: dict[str, Any], fleet: dict[str, Any], recovery: dict[str, Any], impact: dict[str, Any]) -> dict[str, Any]:
    health_counts = Counter(x.get("operational_health", "unvalidated") for x in op["domains"].values())
    implemented = sum(1 for x in op["domains"].values() if x.get("implementation_status") == "implemented")
    partial = sum(1 for x in op["domains"].values() if x.get("implementation_status") == "partial")
    return {
        "release_tag": runtime.get("release_tag"),
        "source_commit": runtime.get("source_commit"),
        "promoted_at": runtime.get("promoted_at"),
        "runtime_baseline_status": runtime.get("status"),
        "domain_health_counts": dict(sorted(health_counts.items())),
        "implemented_domains": implemented,
        "partial_domains": partial,
        "fleet": {"known": fleet.get("known_device_records"), "online": fleet.get("online_device_records"), "overall": fleet.get("overall")},
        "recovery": {"overall": recovery.get("overall"), "reason": recovery.get("reason"), "readiness": recovery.get("readiness")},
        "release_impact_status": impact.get("status"),
        "coverage": coverage.get("by_domain", {}),
    }


def status_chip(status: str, experience: dict[str, Any]) -> str:
    mapping = experience.get("visual_status", {})
    row = mapping.get(status, mapping.get("unvalidated", {"symbol": "○"}))
    css_status = re.sub(r"[^a-z0-9-]+", "-", status.lower())
    return f'<span class="pl-intel-status pl-intel-status--{css_status}"><span aria-hidden="true">{row.get("symbol", "○")}</span> {status}</span>'


def render_status_strip(domain: dict[str, Any], experience: dict[str, Any]) -> str:
    return (
        '<div class="pl-status-strip" role="group" aria-label="Current evidence status">\n'
        f'<div><span>Health</span>{status_chip(domain.get("operational_health", "unvalidated"), experience)}</div>\n'
        f'<div><span>Parity</span>{status_chip("verified" if str(domain.get("semantic_parity", "")).startswith("verified") else domain.get("semantic_parity", "unvalidated"), experience)}</div>\n'
        f'<div><span>Evidence</span>{status_chip("verified" if domain.get("evidence_status") == "release-promoted" else "unvalidated", experience)}</div>\n'
        f'<div><span>Freshness</span>{status_chip("stale" if domain.get("freshness") == "stale" else "verified", experience)}</div>\n'
        '</div>\n'
    )


def render_dependency_page(data: list[dict[str, Any]], experience: dict[str, Any], audience: str) -> str:
    out = frontmatter("Dependency health", "Why each domain is healthy, degraded, or still unvalidated.", audience, "release-promoted")
    out += "# Service and dependency health\n\nOperational health and dependency evidence remain independent: a healthy domain does not silently mark every dependency healthy.\n\n"
    for row in data:
        out += f"## {row['label']}\n\n{render_status_strip(row, experience)}\n"
        if row.get("reason"):
            out += f"**Current reason:** `{row['reason']}`\n\n"
        out += table(["Dependency", "State", "Evidence", "Why"], ((d["name"], d["state"], d["evidence_status"], d["note"]) for d in row["dependencies"]))
        out += "\n"
    return out


def render_release_page(data: dict[str, Any], audience: str) -> str:
    out = frontmatter("Release change impact", "Semantic release delta across source, health, parity, capabilities, database, and architecture.", audience, "release-promoted")
    out += "# What changed?\n\n"
    if data["status"] == "no-comparable-verified-prior-release":
        out += '<div class="pl-empty-state"><strong>No comparable verified prior release</strong><p>The platform will not fabricate a historical delta. Current-release evidence is shown below and becomes the comparison basis when a second canonical release is available.</p></div>\n\n'
    else:
        out += f"Comparing `{data.get('from_release')}` → `{data.get('to_release')}`.\n\n"
    out += table(["Dimension", "Comparison status", "Note"], ((d["dimension"], d["status"], d["note"]) for d in data["dimensions"]))
    out += "\n## Current release snapshot\n\n"
    for name, counts in data["current_snapshot"].items():
        out += f"**{name.replace('-', ' ').replace('_', ' ').title()}:** " + ", ".join(f"{k} {v}" for k, v in counts.items()) + "\n\n"
    out += "<details class=\"pl-disclosure\"><summary>Technical delta payload</summary>\n\n"
    out += table(["Added", "Changed", "Removed"], [(data.get("added", []), data.get("changed", []), data.get("removed", []))])
    out += "\n</details>\n"
    return out


def render_drift_page(data: dict[str, Any], audience: str) -> str:
    out = frontmatter("Runtime drift", "Expected repository/runtime alignment without confusing drift with semantic parity or operational health.", audience, "generated")
    out += "# Runtime drift\n\nConfiguration/runtime drift, semantic parity, and operational health are separate dimensions.\n\n"
    out += table(["Kind", "Resource", "Classification", "Runtime", "Expectation"], ((x["kind"], x["id"], x["classification"], x.get("runtime_status"), x.get("expected_source_match")) for x in data["configuration_runtime"]))
    out += "\n## Semantic drift (independent)\n\n" + table(["Domain", "Parity", "Mismatches"], ((x["domain"], x["runtime_parity"], x["mismatch_count"]) for x in data["semantic_drift_independent"]))
    return out


def render_scorecard(title: str, description: str, data: dict[str, Any], audience: str) -> str:
    out = frontmatter(title, description, audience, "release-promoted") + f"# {title}\n\n"
    out += f'<div class="pl-scorecard-hero"><span>Overall</span><strong>{data.get("overall", "unvalidated")}</strong>'
    if data.get("reason"):
        out += f'<small>Reason: <code>{data["reason"]}</code></small>'
    out += "</div>\n\n"
    out += '<div class="pl-scorecard-grid">\n'
    for check in data.get("checks", []):
        out += f'<div class="pl-scorecard-item"><span>{check["name"]}</span><strong>{check.get("status", "unvalidated")}</strong><small>{check.get("value", "—")}</small></div>\n'
    out += "</div>\n\n"
    if data.get("interpretation"):
        out += f"!!! info \"How to read this\"\n    {data['interpretation']}\n\n"
    if data.get("next_action"):
        out += f"## What should I do next?\n\n{data['next_action']}\n"
    return out


def render_lineage_page(rows: list[dict[str, Any]], audience: str) -> str:
    out = frontmatter("Evidence lineage", "Why the Documentation Platform believes each operational-health claim.", audience, "release-promoted") + "# Why do we believe this?\n\n"
    out += "Every claim keeps its evidence provenance. Raw secrets and private runtime identities are never required.\n\n"
    for row in rows:
        out += f"## {row['label']}\n\n<div class=\"pl-lineage\">\n"
        out += f'<div><strong>Promoted runtime baseline</strong><span>{row["release_tag"]}</span></div><span aria-hidden="true">→</span>'
        out += f'<div><strong>Operational-health projection</strong><span>{row["claim"]}</span></div><span aria-hidden="true">→</span>'
        out += '<div><strong>Documentation intelligence</strong><span>deterministic view</span></div></div>\n\n'
        out += "<details class=\"pl-disclosure\"><summary>Technical provenance</summary>\n\n"
        out += table(["Field", "Value"], [("Source commit", row["source_commit"]), ("Promoted at", row["promoted_at"]), ("Generator", row["generator"]), ("Evidence comparisons", row["evidence_comparisons"])])
        out += "\n</details>\n\n"
    return out


def _confidence_status(confidence: str, experience: dict[str, Any]) -> str:
    if confidence in experience.get("visual_status", {}):
        return confidence
    if confidence == "release-promoted":
        return "verified"
    return "unvalidated"


def _coverage_cell_status(cell: dict[str, Any]) -> str:
    if not cell.get("evidenced"):
        return "unvalidated"
    status = str(cell.get("status") or "").strip().lower()
    if status in {"partial", "degraded", "stale"}:
        return "partial"
    if status in {"unvalidated", "unknown", "missing"}:
        return "unvalidated"
    return "verified"


def render_coverage_page(data: dict[str, Any], audience: str, experience: dict[str, Any]) -> str:
    out = frontmatter("Evidence coverage", "Coverage and categorical confidence without inventing a confidence percentage.", audience, "generated") + "# Evidence coverage and confidence\n\n"
    out += "Coverage answers **which evidence dimensions exist and where uncertainty remains**. Confidence is categorical; Pocket Lab Lite does not invent a percentage score.\n\n"

    dimensions = []
    for cell in data["cells"]:
        if cell["dimension"] not in dimensions:
            dimensions.append(cell["dimension"])

    complete = sum(1 for summary in data["by_domain"].values() if summary["coverage_fraction"].split("/", 1)[0] == summary["coverage_fraction"].split("/", 1)[1])
    partial = len(data["by_domain"]) - complete
    out += '<div class="pl-evidence-summary" role="group" aria-label="Evidence coverage summary">\n'
    out += f'<div><span>Domains</span><strong>{len(data["by_domain"])}</strong><small>tracked evidence profiles</small></div>\n'
    out += f'<div><span>Complete coverage</span><strong>{complete}</strong><small>all dimensions evidenced</small></div>\n'
    out += f'<div><span>Needs evidence</span><strong>{partial}</strong><small>one or more dimensions unknown</small></div>\n'
    out += f'<div><span>Dimensions</span><strong>{len(dimensions)}</strong><small>evaluated per domain</small></div>\n'
    out += '</div>\n\n'

    out += '<div class="pl-coverage-grid pl-coverage-grid--polished">\n'
    cells_by_domain = {}
    for cell in data["cells"]:
        cells_by_domain.setdefault(cell["domain"], []).append(cell)
    for domain, summary in data["by_domain"].items():
        confidence = _confidence_status(summary["confidence"], experience)
        numerator, denominator = summary["coverage_fraction"].split("/", 1)
        pct = int(round((int(numerator) / max(int(denominator), 1)) * 100))
        missing = [c["dimension"] for c in cells_by_domain.get(domain, []) if not c.get("evidenced")]
        out += '<article class="pl-coverage-card pl-coverage-card--meter">'
        out += '<div class="pl-coverage-card__head">'
        out += f'<strong>{html.escape(DOMAIN_LABELS.get(domain, domain.title()))}</strong>{status_chip(confidence, experience)}</div>'
        out += f'<div class="pl-coverage-meter" role="progressbar" aria-label="{html.escape(DOMAIN_LABELS.get(domain, domain.title()))} evidence coverage" aria-valuemin="0" aria-valuemax="100" aria-valuenow="{pct}"><span style="--pl-coverage:{pct}%"></span></div>'
        out += f'<div class="pl-coverage-card__meta"><span>{summary["coverage_fraction"]} dimensions evidenced</span><strong>{pct}%</strong></div>'
        if missing:
            out += f'<small>Missing: {html.escape(", ".join(missing))}</small>'
        else:
            out += '<small>All modeled evidence dimensions are present.</small>'
        out += '</article>\n'
    out += '</div>\n\n'

    out += "## Coverage matrix\n\n"
    out += "Scan across domains first; open a domain only when you need exact status vocabulary and evidence semantics.\n\n"
    out += '<div class="pl-evidence-matrix-wrap"><table class="pl-evidence-matrix"><thead><tr><th scope="col">Domain</th>'
    for dim in dimensions:
        out += f'<th scope="col"><span>{html.escape(dim.replace("-", " ").title())}</span></th>'
    out += '</tr></thead><tbody>'
    for domain in data["by_domain"]:
        mapping = {c["dimension"]: c for c in cells_by_domain.get(domain, [])}
        out += f'<tr><th scope="row">{html.escape(DOMAIN_LABELS.get(domain, domain.title()))}</th>'
        for dim in dimensions:
            cell = mapping.get(dim, {"evidenced": False, "status": "unvalidated"})
            visual = _coverage_cell_status(cell)
            symbol = experience.get("visual_status", {}).get(visual, {}).get("symbol", "○")
            label = str(cell.get("status") or "unvalidated")
            out += f'<td class="pl-evidence-cell pl-evidence-cell--{visual}" title="{html.escape(label)}"><span aria-hidden="true">{html.escape(symbol)}</span><span class="pl-sr-only">{html.escape(label)}</span></td>'
        out += '</tr>'
    out += '</tbody></table></div>\n\n'

    out += "## Domain details\n\n"
    for domain in data["by_domain"]:
        label = DOMAIN_LABELS.get(domain, domain.title())
        out += f'<details class="pl-disclosure pl-domain-disclosure"><summary><span>{html.escape(label)}</span><small>{data["by_domain"][domain]["coverage_fraction"]} evidenced</small></summary>\n<div class="pl-detail-list">\n'
        for cell in cells_by_domain.get(domain, []):
            visual = _coverage_cell_status(cell)
            out += '<div class="pl-detail-row">'
            out += f'<div><strong>{html.escape(cell["dimension"].replace("-", " ").title())}</strong><small>{"Evidence present" if cell.get("evidenced") else "Evidence missing"}</small></div>'
            out += f'<div>{status_chip(visual, experience)}<code>{html.escape(str(cell.get("status") or "unvalidated"))}</code></div>'
            out += '</div>\n'
        out += '</div>\n</details>\n\n'
    return out

def render_limitations_page(rows: list[dict[str, Any]], audience: str) -> str:
    out = frontmatter("Known limitations", "Accepted constraints, open gaps, and unsupported operations without hiding uncertainty.", audience, "generated") + "# Known limitations and unsupported states\n\n"
    out += table(["Area", "Type", "Status", "What it means", "Implementation", "Health"], ((x["label"], x["category"], x["status"], x["description"], x["implementation_status"], x["operational_health"]) for x in rows))
    return out


def render_reasons_page(rows: list[dict[str, Any]], audience: str) -> str:
    out = frontmatter("Operational reason codes", "Canonical reason-code encyclopedia with current observations and operator guidance.", audience, "generated") + "# Operational reason-code encyclopedia\n\n"
    active = [x for x in rows if x["observed_in_current_health"]]
    if active:
        out += "## Active in current promoted health\n\n" + table(["Code", "Domains", "Meaning", "Next action"], ((x["code"], x["observed_in_current_health"], x["meaning"], x["next_action"]) for x in active)) + "\n"
    out += "## Canonical registry\n\n" + table(["Code", "Domain", "Severity", "Retryable", "Meaning", "Operator guidance"], ((x["code"], x["domain"], x["severity"], x["retryable"], x["meaning"], x["next_action"]) for x in rows))
    return out


def render_scenarios_page(rows: list[dict[str, Any]], audience: str) -> str:
    out = frontmatter("How Pocket Lab works", "Scenario-oriented guide through real Pocket Lab Lite workflows.", audience, "source-derived") + "# How Pocket Lab works\n\n"
    out += "Use scenarios when you want to understand **what happens**, **who owns execution**, and **where evidence returns**.\n\n"
    for row in rows:
        out += f"## {row['title']}\n\n**Area:** {row['domain']} · **Flow:** {'write/execution' if row['write_flow'] else 'read/projection'} · **Confidence:** {row['confidence']}\n\n"
        out += '<div class="pl-flow">' + '<span aria-hidden="true">→</span>'.join(f'<div>{stage}</div>' for stage in row["stages"]) + '</div>\n\n'
        out += f"!!! info \"Boundary\"\n    {row['guardrail']}\n\n"
        out += "<details class=\"pl-disclosure\"><summary>Routes and source evidence</summary>\n\n" + table(["Routes", "Source refs"], [(row["routes"], row["source_refs"])]) + "\n</details>\n\n"
    return out


def render_platform_page(rows: list[dict[str, Any]], audience: str, experience: dict[str, Any]) -> str:
    capabilities = sorted({x["capability_name"] for x in rows})
    platforms = sorted({x["platform"] for x in rows})
    matrix = {(x["capability_name"], x["platform"]): x for x in rows}
    out = frontmatter("Platform capability matrix", "Role-aware capability evidence with executive and detailed views.", audience, "release-promoted") + "# Platform capability matrix\n\n"
    out += "See **where a capability is actually provided**, which role a platform plays, and whether the claim is release-promoted or only source-derived. Browser presentation never proves runtime execution.\n\n"

    counts = Counter(str(x.get("status") or "unvalidated") for x in rows)
    out += '<div class="pl-capability-summary" role="group" aria-label="Capability evidence summary">\n'
    for label, key in (("Verified", "verified"), ("Implemented", "implemented"), ("Unvalidated", "unvalidated"), ("Not applicable", "not-applicable")):
        chip_status = key if key in experience.get("visual_status", {}) else "partial" if key == "implemented" else "unvalidated"
        out += f'<div><span>{html.escape(label)}</span><strong>{counts.get(key, 0)}</strong>{status_chip(chip_status, experience)}</div>\n'
    out += '</div>\n\n'

    out += '<div class="pl-matrix-legend" aria-label="Capability status legend">' + ''.join(status_chip(x, experience) for x in ("verified", "partial", "unvalidated", "not-applicable")) + '</div>\n\n'
    out += '<div class="pl-capability-matrix-wrap"><table class="pl-capability-matrix"><thead><tr><th scope="col">Capability</th>'
    for platform in platforms:
        out += f'<th scope="col"><span>{html.escape(platform)}</span></th>'
    out += '</tr></thead><tbody>'
    for capability in capabilities:
        out += f'<tr><th scope="row">{html.escape(capability)}</th>'
        for platform in platforms:
            row = matrix.get((capability, platform), {})
            status = str(row.get("status") or "unvalidated")
            visual = status if status in experience.get("visual_status", {}) else "partial" if status == "implemented" else "unvalidated"
            symbol = experience.get("visual_status", {}).get(visual, {}).get("symbol", "○")
            role = str(row.get("role") or "unvalidated")
            title = f"{platform}: {status} · role {role}"
            out += f'<td class="pl-capability-cell pl-capability-cell--{html.escape(visual)}" title="{html.escape(title)}"><span aria-hidden="true">{html.escape(symbol)}</span><span>{html.escape(status)}</span></td>'
        out += '</tr>'
    out += '</tbody></table></div>\n\n'

    out += "## Evidence by capability\n\n"
    out += "Open only the capability you are investigating. This keeps role, evidence authority, and rationale together without a 35-row evidence wall.\n\n"
    for capability in capabilities:
        cap_rows = [x for x in rows if x["capability_name"] == capability]
        verified = sum(1 for x in cap_rows if x.get("status") == "verified")
        implemented = sum(1 for x in cap_rows if x.get("status") == "implemented")
        unknown = sum(1 for x in cap_rows if x.get("status") == "unvalidated")
        out += f'<details class="pl-disclosure pl-capability-disclosure"><summary><span>{html.escape(capability)}</span><small>{verified} verified · {implemented} implemented · {unknown} unvalidated</small></summary>\n<div class="pl-capability-detail-grid">\n'
        for row in cap_rows:
            status = str(row.get("status") or "unvalidated")
            visual = status if status in experience.get("visual_status", {}) else "partial" if status == "implemented" else "unvalidated"
            out += '<article class="pl-capability-detail">'
            out += f'<div class="pl-capability-detail__head"><strong>{html.escape(row["platform"])}</strong>{status_chip(visual, experience)}</div>'
            out += f'<dl><div><dt>Role</dt><dd>{html.escape(str(row.get("role") or "—"))}</dd></div><div><dt>Evidence</dt><dd>{html.escape(str(row.get("evidence_status") or "—"))}</dd></div></dl>'
            out += f'<p>{html.escape(str(row.get("rationale") or "No rationale recorded."))}</p>'
            out += '</article>\n'
        out += '</div>\n</details>\n\n'
    return out

def _doc_route(doc_path: str) -> str:
    """Return the browser-facing route for a docs-relative Markdown file.

    MkDocs uses directory URLs by default, so ``foo/bar.md`` is served as
    ``foo/bar/`` and ``foo/index.md`` is served as ``foo/``. Raw HTML links
    are not rewritten by MkDocs, so generated card hrefs must target routes,
    not source ``.md`` paths.
    """
    path = PurePosixPath(doc_path)
    if path.name == "index.md":
        route = path.parent.as_posix()
    else:
        route = path.with_suffix("").as_posix()
    return "" if route == "." else route.rstrip("/")


def doc_href(source_doc: str, target_doc: str, anchor: str | None = None) -> str:
    """Build a portable relative href between MkDocs directory routes."""
    source_route = _doc_route(source_doc)
    target_route = _doc_route(target_doc)
    start = source_route or "."
    target = target_route or "."
    relative = posixpath.relpath(target, start)
    href = "./" if relative == "." else f"{relative.rstrip('/')}/"
    if anchor:
        href += f"#{anchor}"
    return href


def render_hub(kind: str, audience: str = "all") -> str:
    data = {
        "understand": ("Understand Pocket Lab Lite", "Start from user questions instead of repository structure.", [
            ("How does Pocket Lab work?", "generated/development/intelligence/scenarios.md", "Follow real workflows from UI intent through backend evidence."),
            ("What depends on what?", "generated/development/intelligence/dependency-health.md", "See domain dependencies and their evidence authority."),
            ("Which platforms do what?", "generated/development/intelligence/platform-matrix.md", "Understand runtime, execution, storage, browser, and development roles."),
            ("What is known or unknown?", "generated/development/intelligence/evidence-coverage.md", "Inspect evidence coverage without treating absence as success."),
        ]),
        "evidence": ("Evidence", "Inspect why the platform believes a claim and where uncertainty remains.", [
            ("Current operational health", "generated/development/knowledge/operational-health.md", "Health remains independent from semantic parity."),
            ("Dependency health", "generated/development/intelligence/dependency-health.md", "Trace a degraded domain to supporting dependencies."),
            ("Runtime drift", "generated/development/intelligence/runtime-drift.md", "Compare expected and observed runtime configuration truthfully."),
            ("Evidence lineage", "generated/development/intelligence/evidence-lineage.md", "See promoted baseline → projection → documentation provenance."),
            ("Evidence coverage", "generated/development/intelligence/evidence-coverage.md", "See which evidence dimensions are present, partial, or unknown."),
        ]),
        "release": ("Release intelligence", "Understand the current release before changing or promoting runtime evidence.", [
            ("What changed?", "generated/development/intelligence/release-impact.md", "Review semantic release impact without fabricated history."),
            ("Runtime baseline", "generated/development/runtime-verification.md", "Inspect the promoted sanitized runtime baseline."),
            ("Parity", "generated/development/validation/parity/index.md", "Review backend/runtime/UI semantic agreement independently."),
            ("Operational health", "generated/development/intelligence/dependency-health.md", "Review release-bound health and dependency interpretation."),
        ]),
    }[kind]
    title, desc, cards = data
    out = frontmatter(title, desc, audience, "generated") + f"# {title}\n\n{desc}\n\n<div class=\"pl-task-grid\">\n"
    source_doc = f"generated/experience/{kind}.md"
    for name, target_doc, summary in cards:
        href = doc_href(source_doc, target_doc)
        out += f'<a class="pl-task-card pl-intent-link" href="{href}"><strong>{name}</strong><span>{summary}</span></a>\n'
    out += "</div>\n"
    return out


def render_home(data: dict[str, Any], op: dict[str, Any], experience: dict[str, Any]) -> str:
    cards = []
    for domain_id in ("home", "apps", "devices", "security", "recovery"):
        h = op["domains"][domain_id]
        anchor = domain_id.replace("recovery", "backup--restore")
        href = doc_href("index.md", "generated/development/intelligence/dependency-health.md", anchor)
        cards.append(f'<a class="pl-health-card pl-intent-link" href="{href}"><span>{DOMAIN_LABELS[domain_id]}</span>{status_chip(h["operational_health"], experience)}<small>{h.get("reason") or h.get("readiness") or "current promoted evidence"}</small></a>')
    health_counts = data["domain_health_counts"]
    out = '<div class="pl-dashboard" data-pl-dashboard="true">\n'
    out += '<div class="pl-dashboard__masthead"><div><span class="pl-eyebrow">Documentation Control Center</span><h2>Current Pocket Lab Lite evidence</h2><p>Release-bound health, fleet, recovery, parity, and evidence coverage—generated without probing the live system.</p></div>'
    out += f'<div class="pl-release-pill"><span>Promoted release</span><strong>{data["release_tag"]}</strong><small>{data["promoted_at"]}</small></div></div>\n'
    out += '<div class="pl-kpi-grid">'
    out += f'<div class="pl-kpi"><span>Implemented domains</span><strong>{data["implemented_domains"]}</strong><small>{data["partial_domains"]} partial</small></div>'
    out += f'<div class="pl-kpi"><span>Healthy</span><strong>{health_counts.get("healthy",0)}</strong><small>{health_counts.get("degraded",0)} degraded</small></div>'
    out += f'<div class="pl-kpi"><span>Fleet records</span><strong>{data["fleet"].get("known")}</strong><small>{data["fleet"].get("online")} online in promoted observation</small></div>'
    out += f'<div class="pl-kpi"><span>Recovery</span><strong>{data["recovery"].get("overall")}</strong><small>{data["recovery"].get("reason") or data["recovery"].get("readiness")}</small></div>'
    out += '</div>\n<h3>Current operational health</h3><div class="pl-health-grid">' + ''.join(cards) + '</div>\n'
    out += '<h3>I want to…</h3><div class="pl-task-grid">'
    task_links = [
        ("Understand the architecture", "generated/experience/understand.md"),
        ("Check system health", "generated/production/intelligence/current-health.md"),
        ("Investigate degradation", "generated/development/intelligence/dependency-health.md"),
        ("Understand runtime drift", "generated/development/intelligence/runtime-drift.md"),
        ("Prepare a release", "generated/experience/release.md"),
        ("See why we believe a claim", "generated/development/intelligence/evidence-lineage.md"),
    ]
    for label, target_doc in task_links:
        href = doc_href("index.md", target_doc)
        out += f'<a class="pl-task-card pl-intent-link" href="{href}"><strong>{label}</strong><span>Open focused guidance →</span></a>'
    out += '</div>\n'
    if data.get("release_impact_status") == "no-comparable-verified-prior-release":
        release_href = doc_href("index.md", "generated/development/intelligence/release-impact.md")
        out += f'<div class="pl-empty-state"><strong>Release delta is ready, history is not fabricated.</strong><p>The current release is fully summarized; a previous release delta will appear only when a second verified canonical release is available.</p><a href="{release_href}">Open change impact →</a></div>\n'
    out += '</div>\n'
    return out


def build() -> tuple[dict[Path, str], dict[str, Any]]:
    experience = load(EXPERIENCE)
    jsonschema.Draft202012Validator(load(EXPERIENCE_SCHEMA)).validate(experience)
    op = load(OP_HEALTH)
    runtime = load(RUNTIME_BASELINE)
    arch_runtime = load(ARCH_RUNTIME)
    arch = load(ARCH)
    meta = load(KNOWLEDGE_META)
    limitations = load(LIMITATIONS)
    reasons = load(REASONS)
    release_changes = load(RELEASE_CHANGES, {"items": []})
    parity_drift = load(PARITY_DRIFT, {"items": []})

    for field in ("release_tag", "source_commit", "promoted_at"):
        if op.get(field) != runtime.get(field):
            raise ValueError(f"operational health {field} does not match promoted runtime baseline")
    if op.get("sanitized") is not True or arch_runtime.get("sanitized") is not True:
        raise ValueError("runtime evidence inputs must remain sanitized")

    dep = dependency_health(op, arch_runtime)
    impact = release_impact(op, runtime, release_changes, parity_drift)
    drift = runtime_drift(arch_runtime, parity_drift)
    recovery = recovery_readiness(op, runtime)
    fleet = fleet_readiness(op, runtime, arch_runtime)
    lineage = evidence_lineage(op, runtime)
    coverage = evidence_coverage(op, runtime)
    limitation_rows = limitations_catalog(limitations, op)
    reason_rows = reason_encyclopedia(reasons, op)
    scenarios = scenario_catalog(meta, arch)
    matrix = platform_matrix(op)
    dash = dashboard(op, runtime, coverage, fleet, recovery, impact)

    intelligence = {
        "schema_version": SCHEMA_VERSION,
        "release": {"release_tag": runtime.get("release_tag"), "source_commit": runtime.get("source_commit"), "promoted_at": runtime.get("promoted_at")},
        "dependency_health": dep,
        "release_impact": impact,
        "runtime_drift": drift,
        "recovery_readiness": recovery,
        "fleet_readiness": fleet,
        "evidence_lineage": lineage,
        "evidence_coverage": coverage,
        "limitations": limitation_rows,
        "reason_codes": reason_rows,
        "scenarios": scenarios,
        "platform_matrix": matrix,
        "dashboard": dash,
    }
    jsonschema.Draft202012Validator(load(INTELLIGENCE_SCHEMA)).validate(intelligence)

    source_fingerprint = digest({
        "experience": experience,
        "operational_health_fingerprint": op.get("source_fingerprint"),
        "runtime_release": intelligence["release"],
        "architecture_runtime_fingerprint": arch_runtime.get("semantic_fingerprint"),
        "limitations": limitations,
        "reason_codes": reasons,
        "release_changes": release_changes,
        "parity_drift": parity_drift,
        "journeys": meta.get("journeys", []),
    })
    envelope = {"schema_version": SCHEMA_VERSION, "source_fingerprint": source_fingerprint, "generator": str(GENERATOR.relative_to(ROOT)), "items": intelligence}

    outputs: dict[Path, str] = {INDEX: stable_json(envelope)}
    sections = {
        "dependency-health": dep,
        "release-impact": impact,
        "runtime-drift": drift,
        "recovery-readiness": recovery,
        "fleet-readiness": fleet,
        "evidence-lineage": lineage,
        "evidence-coverage": coverage,
        "limitations": limitation_rows,
        "reason-codes": reason_rows,
        "scenarios": scenarios,
        "platform-matrix": matrix,
        "dashboard": dash,
    }
    for name, value in sections.items():
        outputs[OUT / f"{name}.json"] = stable_json({"schema_version": SCHEMA_VERSION, "source_fingerprint": source_fingerprint, "items": value})

    dev_pages = {
        "index.md": frontmatter("Documentation intelligence", "Diagnostic, comparative, and evidence-aware views generated from canonical Pocket Lab Lite sources.", "development") + "# Documentation intelligence\n\nThis layer makes the Documentation Platform diagnostic and comparative without turning MkDocs into a live monitoring system.\n\n" + table(["Question", "Open"], [("Why is a domain degraded?", "[Dependency health](dependency-health.md)"), ("What changed?", "[Release impact](release-impact.md)"), ("What differs at runtime?", "[Runtime drift](runtime-drift.md)"), ("Why do we believe this?", "[Evidence lineage](evidence-lineage.md)"), ("What is unknown?", "[Evidence coverage](evidence-coverage.md)")]),
        "dependency-health.md": render_dependency_page(dep, experience, "development"),
        "release-impact.md": render_release_page(impact, "development"),
        "runtime-drift.md": render_drift_page(drift, "development"),
        "recovery-readiness.md": render_scorecard("Recovery readiness", "Release-bound recovery scorecard.", recovery, "development"),
        "fleet-readiness.md": render_scorecard("Fleet readiness", "Device convergence and protected server-host readiness.", fleet, "development"),
        "evidence-lineage.md": render_lineage_page(lineage, "development"),
        "evidence-coverage.md": render_coverage_page(coverage, "development", experience),
        "limitations.md": render_limitations_page(limitation_rows, "development"),
        "reason-codes.md": render_reasons_page(reason_rows, "development"),
        "scenarios.md": render_scenarios_page(scenarios, "development"),
        "platform-matrix.md": render_platform_page(matrix, "development", experience),
    }
    prod_pages = {
        "current-health.md": frontmatter("Current health", "Operator-oriented current health and next checks.", "production", "release-promoted") + "# Current health\n\n" + table(["Area", "Health", "Reason", "Readiness"], ((DOMAIN_LABELS.get(k,k.title()), v.get("operational_health"), v.get("reason"), v.get("readiness")) for k,v in op["domains"].items())) + "\n[Why is something degraded?](../../development/intelligence/dependency-health.md)\n",
        "recovery-readiness.md": render_scorecard("Recovery readiness", "Plain-language recovery readiness from promoted evidence.", recovery, "production"),
        "fleet-readiness.md": render_scorecard("Fleet readiness", "Plain-language device and remote-access readiness.", fleet, "production"),
        "known-limitations.md": render_limitations_page(limitation_rows, "production"),
        "what-changed.md": render_release_page(impact, "production"),
        "how-it-works.md": render_scenarios_page(scenarios, "production"),
        "supported-platforms.md": render_platform_page(matrix, "production", experience),
        "why-we-believe-this.md": render_lineage_page(lineage, "production"),
    }
    for name, text in dev_pages.items():
        outputs[DEV / name] = text
    for name, text in prod_pages.items():
        outputs[PROD / name] = text
    outputs[EXPERIENCE_DOCS / "understand.md"] = render_hub("understand")
    outputs[EXPERIENCE_DOCS / "evidence.md"] = render_hub("evidence")
    outputs[EXPERIENCE_DOCS / "release.md"] = render_hub("release")
    outputs[HOME_FRAGMENT] = render_home(dash, op, experience)

    # Canonicalize generated Markdown to exactly one trailing newline. This keeps
    # git diff --check clean and prevents renderer-specific blank EOF drift.
    outputs = {
        path: (text.rstrip() + "\n" if path.suffix == ".md" else text)
        for path, text in outputs.items()
    }

    for path, text in outputs.items():
        safe_text(str(path.relative_to(ROOT)), text)
    validate_browser_routes(outputs)
    validate_presentation_outputs(outputs)
    return outputs, {"source_fingerprint": source_fingerprint, "machine_artifacts": sum(1 for p in outputs if p.suffix == ".json"), "pages": sum(1 for p in outputs if p.suffix == ".md")}



def validate_presentation_outputs(outputs: dict[Path, str]) -> None:
    """Guard against regressing intelligence views into raw machine-table dumps."""
    platform = outputs.get(DEV / "platform-matrix.md", "")
    coverage = outputs.get(DEV / "evidence-coverage.md", "")
    errors: list[str] = []
    for marker in ("pl-capability-matrix", "pl-capability-disclosure", "Evidence by capability"):
        if marker not in platform:
            errors.append(f"platform matrix missing polished presentation marker: {marker}")
    for marker in ("pl-evidence-matrix", "pl-coverage-meter", "Domain details"):
        if marker not in coverage:
            errors.append(f"evidence coverage missing polished presentation marker: {marker}")
    if "| Capability | Platform | Role | Status | Evidence | Rationale |" in platform:
        errors.append("platform matrix regressed to an ungrouped raw evidence table")
    if "| Domain | Dimension | Status | Evidenced |" in coverage:
        errors.append("evidence coverage regressed to an ungrouped raw evidence table")
    if errors:
        raise ValueError("invalid intelligence presentation:\n - " + "\n - ".join(errors))

def validate_browser_routes(outputs: dict[Path, str]) -> None:
    """Fail closed when generated raw HTML links cannot resolve in MkDocs.

    MkDocs rewrites Markdown links, but it does not rewrite href values inside
    raw HTML cards. With directory URLs enabled, those hrefs must point at the
    browser route (``foo/bar/``), never the source file (``foo/bar.md``).
    """
    href_re = re.compile(r'href="([^"]+)"')
    sources = [(HOME_FRAGMENT, ".")]
    sources.extend(
        (EXPERIENCE_DOCS / f"{kind}.md", f"generated/experience/{kind}")
        for kind in ("understand", "evidence", "release")
    )
    errors: list[str] = []
    for source, browser_base in sources:
        text = outputs.get(source)
        if text is None:
            continue
        for href in href_re.findall(text):
            if href.startswith(("http:", "https:", "mailto:", "#")):
                continue
            route = href.split("#", 1)[0].split("?", 1)[0]
            if ".md" in route:
                errors.append(f"{source.relative_to(ROOT)} raw href uses a source .md path: {href}")
                continue
            resolved = posixpath.normpath(posixpath.join(browser_base, route)).strip("./")
            if not resolved:
                continue
            target_md = ROOT / "docs" / (resolved.rstrip("/") + ".md")
            target_index = ROOT / "docs" / resolved.rstrip("/") / "index.md"
            if not (target_md in outputs or target_index in outputs or target_md.exists() or target_index.exists()):
                errors.append(
                    f"{source.relative_to(ROOT)} href does not map to a MkDocs page: {href} -> {resolved}"
                )
    if errors:
        raise ValueError("invalid generated browser routes:\n - " + "\n - ".join(errors))


def write_outputs(outputs: dict[Path, str]) -> int:
    for path, text in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists() or path.read_text(encoding="utf-8") != text:
            path.write_text(text, encoding="utf-8")
    return 0


def check_outputs(outputs: dict[Path, str]) -> list[str]:
    errors = []
    for path, text in outputs.items():
        if not path.exists():
            errors.append(f"missing {path.relative_to(ROOT)}")
        elif path.read_text(encoding="utf-8") != text:
            errors.append(f"drift {path.relative_to(ROOT)}")
    return errors


def check_ux_budgets(experience: dict[str, Any]) -> list[str]:
    errors = []
    budgets = experience["performance_budgets"]
    js = ROOT / "docs/javascripts/docs.js"
    css_files = [ROOT / "docs/stylesheets/brand.css", ROOT / "docs/stylesheets/components.css", ROOT / "docs/stylesheets/intelligence.css"]
    if js.exists() and js.stat().st_size > budgets["custom_javascript_bytes"]:
        errors.append("custom documentation JavaScript exceeds the UX contract budget")
    css_bytes = sum(p.stat().st_size for p in css_files if p.exists())
    if css_bytes > budgets["custom_css_bytes"]:
        errors.append("custom documentation CSS exceeds the UX contract budget")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("generate", "check"))
    args = parser.parse_args()
    outputs, report = build()
    if args.mode == "generate":
        write_outputs(outputs)
        print(f"generated documentation intelligence: {report['machine_artifacts']} machine artifacts, {report['pages']} pages")
        return 0
    errors = check_outputs(outputs) + check_ux_budgets(load(EXPERIENCE))
    if errors:
        print("documentation intelligence check failed:")
        for error in errors:
            print(f" - {error}")
        return 1
    print(f"PASS documentation intelligence: {report['machine_artifacts']} machine artifacts, {report['pages']} pages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
