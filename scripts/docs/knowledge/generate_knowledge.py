#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[3]
GENERATOR = "scripts/docs/knowledge/generate_knowledge.py"
GENERATOR_VERSION = 2
SCHEMA_VERSION = "1.0.0"
META = ROOT / "contracts/metadata/knowledge-base.json"
ARCH = ROOT / "architecture/metadata/pocket-lab-architecture.json"
DOC_META = ROOT / "contracts/metadata/documentation-platform.json"
OPENAPI = ROOT / "contracts/generated/lite-openapi.json"
FRONTEND = ROOT / "contracts/generated/frontend-api-usage.json"
SQLITE = ROOT / "contracts/generated/lite-sqlite-schema.json"
ASYNCAPI = ROOT / "contracts/generated/lite-asyncapi.json"
REASON_CODES = ROOT / "contracts/generated/reason-codes.json"
CAPABILITIES = ROOT / "contracts/generated/device-capabilities.json"
SERVICES = ROOT / "contracts/generated/service-catalog.json"
PROJECTIONS = ROOT / "contracts/generated/projection-catalog.json"
UI_STATES = ROOT / "contracts/generated/ui-state-catalog.json"
RELEASES = ROOT / "contracts/generated/releases/index.json"
PARITY_MODEL = ROOT / "contracts/parity/parity-model.json"
RUNTIME_BASELINE = ROOT / "contracts/parity/runtime-verification-baseline.json"
ACCEPTED_LIMITATIONS = ROOT / "contracts/generated/parity/accepted-limitations.json"
RUNTIME_CONTRACT_ROOT = ROOT / "contracts/generated/runtime"
RUNBOOK_ROOT = ROOT / "runbooks"
TEST_ROOTS = (ROOT / "tests", ROOT / "src/__tests__")
OUT = ROOT / "contracts/generated/knowledge"
DEV = ROOT / "docs/generated/development/knowledge"
PROD = ROOT / "docs/generated/production/knowledge"
SCHEMA_ROOT = ROOT / "schemas/knowledge"
MKDOCS = ROOT / "mkdocs.yml"

NAV_MARKERS = {
    "development": (
        "# BEGIN GENERATED KNOWLEDGE RELEASE NAV: development",
        "# END GENERATED KNOWLEDGE RELEASE NAV: development",
        DEV,
    ),
    "production": (
        "# BEGIN GENERATED KNOWLEDGE RELEASE NAV: production",
        "# END GENERATED KNOWLEDGE RELEASE NAV: production",
        PROD,
    ),
}
SOURCE_COMMIT = os.environ.get("SOURCE_COMMIT", "").strip() or "uncommitted"
SOURCE_GENERATED_AT = os.environ.get("SOURCE_GENERATED_AT", "").strip() or "uncommitted"

HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}
CONFIDENCE = {
    "source-derived", "contract-derived", "generated", "runtime-observed", "release-promoted",
    "verified", "inferred", "partial", "planned", "unvalidated", "stale", "historical",
    "deprecated", "not-applicable",
}
REL_TYPES = {
    "owns", "uses", "calls", "reads", "writes", "publishes", "subscribes", "depends_on",
    "rendered_by", "verified_by", "observed_by", "affected_by", "introduced_in", "resolved_in",
    "documented_by", "protected_by", "recovers_with", "related_to", "produced_by", "consumed_by",
    "changed_in",
}
PRIVATE_PATH = re.compile(r"(?:/home/[^/\s]+|/data/data/com\.termux/files/(?:home|usr)|/mnt/[a-zA-Z]/|[A-Za-z]:\\Users\\)")
SECRET = re.compile(
    r"(?:-----BEGIN [A-Z ]*PRIVATE KEY-----|Bearer\s+[A-Za-z0-9._~+/-]{12,}|"
    r"(?:password|passwd|token|secret|api[_-]?key|credential|authorization)\s*[=:]\s*[^\s,}\]]{6,}|"
    r"nats://[^\s/@]+:[^\s/@]+@)", re.I,
)
IPV4 = re.compile(r"(?<![A-Za-z0-9])(?:\d{1,3}\.){3}\d{1,3}(?![A-Za-z0-9])")


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        if default is not None:
            return default
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, separators=(",", ": ")) + "\n"


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def digest(value: Any) -> str:
    raw = value if isinstance(value, bytes) else canonical_json(value).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def slug(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return text or "item"


def normalize_route(route: str) -> str:
    route = re.sub(r":([A-Za-z_][A-Za-z0-9_]*)", r"{\1}", route)
    route = re.sub(r"\$\{[^}]+\}", "{param}", route)
    return route.rstrip("/") or "/"


def domain_for_route(route: str, aliases: dict[str, str]) -> str:
    bits = [p for p in route.split("/") if p]
    if len(bits) >= 3 and bits[:2] == ["api", "lite"]:
        key = bits[2].replace("_", "-")
        if key in {"apps", "catalog"}:
            return "apps"
        if key in {"fleet", "devices"}:
            return "devices"
        if key in {"security"}:
            return "security"
        if key in {"recovery", "backup"}:
            return "recovery"
        if key in {"identity"}:
            return "identity"
        if key in {"policy", "rules"}:
            return "rules"
        if key in {"status", "health", "ready", "revisions"}:
            return "home"
        if key in {"release"}:
            return "release"
        return aliases.get(key, key)
    return "platform"


def rel_id(rel_type: str, source: str, target: str) -> str:
    return "rel:" + hashlib.sha256(f"{rel_type}\0{source}\0{target}".encode()).hexdigest()[:16]


def source_fingerprint(paths: Iterable[Path]) -> tuple[dict[str, str], str]:
    mapping: dict[str, str] = {}
    for path in sorted(set(paths), key=lambda p: str(p)):
        if path.is_file():
            mapping[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return mapping, digest(mapping)


def md_table(headers: list[str], rows: Iterable[Iterable[Any]]) -> str:
    def clean(value: Any) -> str:
        if value is None:
            return "—"
        if isinstance(value, bool):
            return "yes" if value else "no"
        if isinstance(value, (list, tuple, set)):
            value = ", ".join(str(x) for x in value) if value else "—"
        text = str(value).replace("\n", " ").replace("|", "\\|")
        return text or "—"
    rows = list(rows)
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    out.extend("| " + " | ".join(clean(v) for v in row) + " |" for row in rows)
    return "\n".join(out) + "\n"


def frontmatter(title: str, description: str, confidence: str = "generated") -> str:
    return (
        "---\n"
        f'title: "{title.replace(chr(34), chr(39))}"\n'
        f'description: "{description.replace(chr(34), chr(39))}"\n'
        "generated: true\n"
        "audience: knowledgebase\n"
        f"confidence: {confidence}\n"
        f"source_commit: {SOURCE_COMMIT}\n"
        f"generated_at: {SOURCE_GENERATED_AT}\n"
        f"generator: {GENERATOR}\n"
        f"generator_version: {GENERATOR_VERSION}\n"
        "---\n\n"
    )


@dataclass
class Graph:
    entities: dict[str, dict[str, Any]]
    relations: dict[str, dict[str, Any]]

    def add_entity(self, entity: dict[str, Any]) -> str:
        entity = dict(entity)
        entity["source_refs"] = sorted(set(entity.get("source_refs", [])))
        if entity.get("confidence") not in CONFIDENCE:
            raise ValueError(f"invalid confidence {entity.get('confidence')} for {entity.get('id')}")
        existing = self.entities.get(entity["id"])
        if existing and canonical_json(existing) != canonical_json(entity):
            raise ValueError(f"duplicate entity id with different data: {entity['id']}")
        self.entities[entity["id"]] = entity
        return entity["id"]

    def add_relation(self, rel_type: str, source: str, target: str, evidence: Iterable[str] = ()) -> None:
        if rel_type not in REL_TYPES:
            raise ValueError(f"unknown relation type: {rel_type}")
        if source == target and rel_type not in {"related_to"}:
            return
        rid = rel_id(rel_type, source, target)
        self.relations[rid] = {
            "id": rid,
            "type": rel_type,
            "source": source,
            "target": target,
            "evidence": sorted(set(evidence)),
        }


def load_runbooks() -> list[dict[str, Any]]:
    result = []
    for path in sorted(RUNBOOK_ROOT.glob("*.yaml")):
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        meta = payload.get("metadata", {})
        spec = payload.get("spec", {})
        result.append({
            "id": meta.get("name") or path.stem,
            "title": meta.get("title") or path.stem.replace("_", " ").title(),
            "description": meta.get("description") or "",
            "owner": meta.get("owner") or "unvalidated",
            "tags": sorted(meta.get("tags") or []),
            "category": spec.get("category"),
            "severity": spec.get("severity"),
            "requires_approval": bool(spec.get("requiresApproval")),
            "steps": [
                {"name": x.get("name"), "operation": x.get("operation"), "requires_approval": bool(x.get("requiresApproval"))}
                for x in spec.get("steps", [])
            ],
            "evidence": sorted(spec.get("evidence") or []),
            "source": str(path.relative_to(ROOT)),
        })
    return result


def test_inventory() -> list[str]:
    files: list[str] = []
    for root in TEST_ROOTS:
        if root.exists():
            files.extend(str(p.relative_to(ROOT)) for p in sorted(root.rglob("*")) if p.is_file() and p.suffix in {".py", ".js", ".jsx", ".mjs", ".ts", ".tsx"})
    return sorted(set(files))


def source_text_cache(paths: Iterable[str]) -> dict[str, str]:
    cache = {}
    for rel in paths:
        path = ROOT / rel
        try:
            cache[rel] = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            cache[rel] = ""
    return cache


def known_reason_fingerprints(reasons: list[dict[str, Any]]) -> dict[str, str]:
    # Runtime parity sanitizes strings as sha256(JSON-string)[:16]. Reverse only against the canonical reason registry.
    return {hashlib.sha256(json.dumps(r["code"]).encode()).hexdigest()[:16]: r["code"] for r in reasons}


def build_graph() -> tuple[Graph, dict[str, Any]]:
    meta = read_json(META)
    arch = read_json(ARCH)
    doc_meta = read_json(DOC_META)
    openapi = read_json(OPENAPI)
    frontend = read_json(FRONTEND)["frontend_api_usage"]
    sqlite = read_json(SQLITE)["lite_sqlite_schema"]
    asyncapi = read_json(ASYNCAPI)
    reasons_payload = read_json(REASON_CODES)["reason_codes"]
    reasons = reasons_payload.get("reason_codes", reasons_payload if isinstance(reasons_payload, list) else [])
    parity = read_json(PARITY_MODEL)
    runtime = read_json(RUNTIME_BASELINE)
    accepted = read_json(ACCEPTED_LIMITATIONS, {"items": []})
    capabilities_payload = read_json(CAPABILITIES, {"device_capabilities": []})
    runbooks = load_runbooks()
    tests = test_inventory()
    test_text = source_text_cache(tests)
    aliases = meta.get("domain_aliases", {})
    graph = Graph({}, {})

    baseline_domains = {d["id"]: d for d in runtime.get("domains", [])}
    parity_domains = {d["id"]: d for d in parity.get("domains", [])}
    reason_fp = known_reason_fingerprints(reasons)

    # Domains and independent status dimensions.
    for did, domain in sorted(parity_domains.items()):
        b = baseline_domains.get(did, {})
        read_degraded = None
        degraded_reason = None
        for comparison in b.get("comparisons", []):
            cid = comparison.get("id", "")
            if cid == f"{did}-termux-read_degraded" and isinstance(comparison.get("backend_value"), bool):
                read_degraded = comparison["backend_value"]
            if cid == f"{did}-termux-degraded_reason":
                val = comparison.get("backend_value")
                if isinstance(val, dict) and val.get("fingerprint") in reason_fp:
                    degraded_reason = reason_fp[val["fingerprint"]]
        implementation = b.get("implementation_status") or domain.get("implementation_status") or "unvalidated"
        parity_state = b.get("runtime_parity") or domain.get("runtime_parity") or "unvalidated"
        runtime_status = "observed" if all(b.get(k) == "observed" for k in ("live_api_coverage", "live_termux_coverage", "live_ui_coverage")) else "not-observed"
        operational = "degraded" if read_degraded is True else ("healthy" if read_degraded is False else "unvalidated")
        evidence_status = "release-promoted" if b and runtime.get("release_tag") else "unvalidated"
        confidence = "release-promoted" if b else ("source-derived" if domain else "unvalidated")
        entity = {
            "id": f"domain:{did}", "type": "domain", "name": domain.get("label", did.title()), "domain": did,
            "description": domain.get("description", ""), "confidence": confidence,
            "source_refs": ["contracts/parity/parity-model.json"] + (["contracts/parity/runtime-verification-baseline.json"] if b else []),
            "status_dimensions": {
                "implementation_status": implementation,
                "runtime_status": runtime_status,
                "operational_health": operational,
                "runtime_parity": parity_state,
                "evidence_status": evidence_status,
                "confidence": confidence,
                "freshness": "promoted-observation" if b else "unvalidated",
                "readiness": "ready-with-guardrails" if implementation == "implemented" else "partial",
                "capability_status": implementation,
                "degraded_reason": degraded_reason,
            },
            "observation_summary": b.get("comparison_summary", {}),
            "known_gaps": domain.get("known_gaps", []),
        }
        graph.add_entity(entity)

    for did in ("release", "validation", "documentation", "platform"):
        eid = f"domain:{did}"
        if eid not in graph.entities:
            graph.add_entity({"id": eid, "type": "domain", "name": did.title(), "domain": did, "confidence": "source-derived", "source_refs": ["architecture/metadata/pocket-lab-architecture.json"]})

    # Components and architecture edges.
    component_paths: dict[str, set[str]] = defaultdict(set)
    for cid, comp in sorted(arch["components"].items()):
        refs = [x.get("value") for x in comp.get("source_verification", []) if x.get("kind") == "path" and x.get("value")]
        for ref in refs:
            component_paths[ref].add(cid)
        graph.add_entity({
            "id": f"component:{cid}", "type": "component", "name": comp["name"], "domain": None,
            "description": comp.get("responsibility", ""), "confidence": comp.get("verification_status", "source-derived") if comp.get("verification_status") in CONFIDENCE else "source-derived",
            "source_refs": ["architecture/metadata/pocket-lab-architecture.json"] + refs,
            "owner": comp.get("owner"), "execution_owner": comp.get("process_owner"), "data_owner": comp.get("data_owner"),
            "recovery_owner": comp.get("recovery_owner"), "runtime_owner": comp.get("runtime_owner"), "runtime_process": comp.get("process_owner"),
            "runtime_platform": comp.get("runtime_location"), "supported_platforms": comp.get("supported_platforms", []),
            "security_boundary": comp.get("security_boundary"), "protocols": comp.get("protocols", []), "inputs": comp.get("inputs", []), "outputs": comp.get("outputs", []),
            "health_signals": comp.get("health_signals", []), "failure_modes": comp.get("failure_paths", []), "recovery_behavior": comp.get("recovery_paths", []),
            "evidence": comp.get("evidence_produced", []), "durable_state_dependencies": comp.get("durable_state_dependencies", []),
            "documentation_links": comp.get("documentation_links", []), "icon": comp.get("icon"),
            "status_dimensions": {"implementation_status": "implemented", "runtime_status": "unvalidated", "operational_health": "unvalidated", "runtime_parity": "unvalidated", "evidence_status": "source-derived", "confidence": "source-derived", "freshness": "source-current", "readiness": "unvalidated", "capability_status": "implemented", "degraded_reason": None},
        })
    for edge in arch.get("connections", []):
        graph.add_relation("depends_on", f"component:{edge['source']}", f"component:{edge['target']}", ["architecture/metadata/pocket-lab-architecture.json"])
    for cid, comp in sorted(arch["components"].items()):
        boundary = comp.get("security_boundary")
        if boundary:
            bid = f"boundary:{boundary}"
            bmeta = arch.get("boundaries", {}).get(boundary, {})
            if bid not in graph.entities:
                graph.add_entity({"id": bid, "type": "threat-boundary", "name": bmeta.get("name", boundary), "domain": "security", "description": bmeta.get("description", ""), "confidence": "source-derived", "source_refs": ["architecture/metadata/pocket-lab-architecture.json"]})
            graph.add_relation("protected_by", f"component:{cid}", bid, ["architecture/metadata/pocket-lab-architecture.json"])

    # APIs and frontend reverse index.
    api_by_route_method: dict[tuple[str, str], str] = {}
    api_by_route: dict[str, list[str]] = defaultdict(list)
    for route, path_item in sorted(openapi.get("paths", {}).items()):
        for method, op in sorted(path_item.items()):
            if method.lower() not in HTTP_METHODS or not isinstance(op, dict):
                continue
            method_u = method.upper()
            eid = f"api:{method.lower()}:{normalize_route(route)}"
            domain = domain_for_route(route, aliases)
            graph.add_entity({
                "id": eid, "type": "api", "name": f"{method_u} {route}", "domain": domain,
                "description": op.get("summary") or op.get("description") or "", "confidence": "contract-derived",
                "source_refs": ["contracts/generated/lite-openapi.json"], "method": method_u, "route": route,
                "operation_id": op.get("operationId"), "tags": sorted(op.get("tags") or []),
                "response_statuses": sorted(op.get("responses", {}).keys()),
            })
            api_by_route_method[(method_u, normalize_route(route))] = eid
            api_by_route[normalize_route(route)].append(eid)
            graph.add_relation("owns", f"domain:{domain}", eid, ["contracts/generated/lite-openapi.json"])

    ui_entities: dict[str, str] = {}
    for call in frontend.get("modules", []):
        route = normalize_route(call.get("route", ""))
        method = str(call.get("method") or "GET").upper()
        api_id = api_by_route_method.get((method, route))
        if not api_id:
            # Match path parameters by segment shape without fuzzy title matching.
            for (candidate_method, candidate_route), candidate_id in api_by_route_method.items():
                if candidate_method != method:
                    continue
                pat = "^" + re.sub(r"\\\{[^/]+\\\}", r"[^/]+", re.escape(candidate_route)) + "$"
                if re.match(pat, route):
                    api_id = candidate_id
                    break
        consumers = [p for p in call.get("import_chain", []) if p.startswith("src/lite/Lite") and p.endswith((".jsx", ".js"))]
        if call.get("source_module", "").startswith("src/lite/Lite"):
            consumers.append(call["source_module"])
        for src in sorted(set(consumers)):
            if src not in ui_entities:
                name = Path(src).stem
                uid = f"ui:{slug(name)}"
                ui_entities[src] = uid
                domain = {"LiteCatalog": "apps", "LiteDevices": "devices", "LiteSecurity": "security", "LiteRecovery": "recovery", "LiteIdentity": "identity", "LiteRules": "rules", "LiteHome": "home"}.get(name, "platform")
                graph.add_entity({"id": uid, "type": "ui", "name": name, "domain": domain, "confidence": "source-derived", "source_refs": [src], "state_owner": "TanStack Query for live server state; Dexie safe snapshots; Zustand UI coordination; XState guided workflows where applicable"})
                graph.add_relation("owns", f"domain:{domain}", uid, [src])
            if api_id:
                graph.add_relation("calls", ui_entities[src], api_id, [call.get("source_module", "")])
        if api_id:
            graph.entities[api_id].setdefault("frontend_clients", []).append({k: call.get(k) for k in ("owner", "source_module", "usage", "mocked", "resolved")})

    # SQLite semantic encyclopedia and API relationships.
    for obj in sorted(sqlite.get("objects", []), key=lambda x: x["name"]):
        tid = f"table:{obj['name']}"
        domain = aliases.get(obj.get("domain", ""), obj.get("domain") or "platform")
        graph.add_entity({
            "id": tid, "type": "table", "name": obj["name"], "domain": domain, "description": obj.get("purpose", ""),
            "confidence": "source-derived" if obj.get("semantic_status") == "verified" else "inferred",
            "source_refs": ["contracts/generated/lite-sqlite-schema.json"] + obj.get("migration_sources", []),
            "owner": obj.get("projection_owner"), "writer": obj.get("writer"), "readers": obj.get("readers", []),
            "classification": obj.get("classification"), "retention": obj.get("retention"), "sensitive_fields": obj.get("sensitive_fields", []),
            "indexes": [x.get("name") for x in obj.get("indexes", [])], "migration_sources": obj.get("migration_sources", []),
        })
        graph.add_relation("owns", f"domain:{domain}", tid, ["contracts/generated/lite-sqlite-schema.json"])
        for reader in obj.get("readers", []):
            rr = normalize_route(reader)
            for aid in api_by_route.get(rr, []):
                graph.add_relation("reads", aid, tid, ["contracts/generated/lite-sqlite-schema.json"])

    # NATS subjects/events.
    for subject, details in sorted(asyncapi.get("channels", {}).items()):
        sid = f"subject:{subject}"
        domain = aliases.get(details.get("x-pocketlab-domain", ""), details.get("x-pocketlab-domain") or "platform")
        graph.add_entity({
            "id": sid, "type": "subject", "name": subject, "domain": domain, "description": details.get("description", ""),
            "confidence": "contract-derived", "source_refs": ["contracts/generated/lite-asyncapi.json"] + details.get("x-pocketlab-source", []),
            "publishers": details.get("x-pocketlab-publisher", []), "subscribers": details.get("x-pocketlab-consumer", []),
            "delivery": details.get("x-pocketlab-delivery"), "durability": details.get("x-pocketlab-durable"), "retry": details.get("x-pocketlab-retry"),
            "stream": details.get("x-pocketlab-stream"), "classification": details.get("x-pocketlab-security-classification"),
        })
        graph.add_relation("owns", f"domain:{domain}", sid, ["contracts/generated/lite-asyncapi.json"])
        for source_ref in details.get("x-pocketlab-source", []):
            source_path = source_ref.split(":", 1)[0]
            for path, cids in component_paths.items():
                if source_path == path:
                    for cid in cids:
                        rel = "publishes" if details.get("x-pocketlab-publisher") else "related_to"
                        graph.add_relation(rel, f"component:{cid}", sid, [source_ref])

    # Reason codes.
    for reason in sorted(reasons, key=lambda x: x["code"]):
        rid = f"reason:{reason['code']}"
        domain = aliases.get(reason.get("domain", ""), reason.get("domain") or "platform")
        graph.add_entity({
            "id": rid, "type": "reason-code", "name": reason["code"], "domain": domain, "description": reason.get("meaning", ""),
            "confidence": "source-derived", "source_refs": ["contracts/metadata/documentation-platform.json", "contracts/generated/reason-codes.json"],
            "severity": reason.get("audit_severity"), "user_interpretation": reason.get("user_message"), "retryable": reason.get("retryable"),
            "terminal": reason.get("terminal"), "http_status": reason.get("http_status"), "ui_mapping": reason.get("ui_mapping", []),
            "projection_mapping": reason.get("projection_mapping", []), "event_mapping": reason.get("event_mapping", []),
        })
        graph.add_relation("owns", f"domain:{domain}", rid, ["contracts/generated/reason-codes.json"])

    # Journeys, ADRs, runbooks, troubleshooting.
    for j in meta.get("journeys", []):
        jid = f"journey:{j['id']}"
        graph.add_entity({"id": jid, "type": "journey", "name": j["title"], "domain": j.get("domain"), "confidence": j.get("confidence", "source-derived"), "source_refs": j.get("source_refs", []), "routes": j.get("routes", []), "components": j.get("components", [])})
        for cid in j.get("components", []):
            if f"component:{cid}" in graph.entities:
                graph.add_relation("uses", jid, f"component:{cid}", j.get("source_refs", []))
        for route in j.get("routes", []):
            parts = route.split(" ", 1)
            if len(parts) == 2:
                aid = api_by_route_method.get((parts[0].upper(), normalize_route(parts[1])))
                if aid:
                    graph.add_relation("calls", jid, aid, j.get("source_refs", []))
        if f"domain:{j.get('domain')}" in graph.entities:
            graph.add_relation("owns", f"domain:{j['domain']}", jid, j.get("source_refs", []))

    for adr in meta.get("adrs", []):
        aid = f"adr:{adr['id']}"
        graph.add_entity({"id": aid, "type": "adr", "name": adr["title"], "domain": "architecture", "description": adr.get("decision", ""), "confidence": "source-derived", "source_refs": adr.get("source_refs", []), **{k: adr.get(k) for k in ("status", "context", "alternatives", "trade_offs", "consequences", "security_implications", "runtime_implications")}})
        for cid in adr.get("components", []):
            if f"component:{cid}" in graph.entities:
                graph.add_relation("affected_by", f"component:{cid}", aid, adr.get("source_refs", []))

    for runbook in runbooks:
        rid = f"runbook:{runbook['id']}"
        graph.add_entity({"id": rid, "type": "runbook", "name": runbook["title"], "domain": runbook.get("category") or "operations", "description": runbook["description"], "confidence": "source-derived", "source_refs": [runbook["source"]], **{k: runbook[k] for k in ("owner", "tags", "severity", "requires_approval", "steps", "evidence")}})

    for t in meta.get("troubleshooting", []):
        tid = f"troubleshooting:{t['id']}"
        graph.add_entity({"id": tid, "type": "troubleshooting", "name": t["title"], "domain": "operations", "confidence": "source-derived", "source_refs": ["contracts/metadata/knowledge-base.json"], "checks": t.get("checks", []), "recovery": t.get("recovery", []), "components": t.get("components", [])})
        for cid in t.get("components", []):
            if f"component:{cid}" in graph.entities:
                graph.add_relation("recovers_with", f"component:{cid}", tid, ["contracts/metadata/knowledge-base.json"])

    # Limitations: canonical generated parity limitations, split into stable entities.
    for item in sorted(accepted.get("items", []), key=lambda x: x["id"]):
        domain = item["id"]
        for idx, text in enumerate(item.get("known_gaps", []), 1):
            lid = f"limitation:{domain}:gap-{idx}"
            graph.add_entity({"id": lid, "type": "limitation", "name": f"{item['label']} gap {idx}", "domain": domain, "description": text, "confidence": "contract-derived", "source_refs": ["contracts/generated/parity/accepted-limitations.json"], "status": "open", "lifecycle": "open", "risk": "unvalidated", "workaround": None})
            graph.add_relation("affected_by", f"domain:{domain}", lid, ["contracts/generated/parity/accepted-limitations.json"])
        for idx, text in enumerate(item.get("accepted_limitations", []), 1):
            lid = f"limitation:{domain}:accepted-{idx}"
            graph.add_entity({"id": lid, "type": "limitation", "name": f"{item['label']} accepted limitation {idx}", "domain": domain, "description": text, "confidence": "contract-derived", "source_refs": ["contracts/generated/parity/accepted-limitations.json"], "status": "accepted", "lifecycle": "accepted", "risk": "accepted limitation", "workaround": None})
            graph.add_relation("affected_by", f"domain:{domain}", lid, ["contracts/generated/parity/accepted-limitations.json"])

    # No historical incidents are fabricated. The incident entity type remains intentionally empty until a structured record exists.

    # Release knowledge from verified promoted runtime evidence and verified release inventory when present.
    if runtime.get("release_tag") and runtime.get("source_commit"):
        rid = f"release:{runtime['release_tag']}"
        graph.add_entity({
            "id": rid, "type": "release", "name": runtime["release_tag"], "domain": "release", "confidence": "release-promoted",
            "source_refs": ["contracts/parity/runtime-verification-baseline.json"], "source_commit": runtime["source_commit"],
            "promoted_at": runtime.get("promoted_at"), "runtime_parity_status": runtime.get("status"), "sanitized": runtime.get("sanitized"),
            "artifact": None, "artifact_checksum": None, "release_manifest_status": "unvalidated",
        })
        for did in baseline_domains:
            graph.add_relation("observed_by", f"domain:{did}", rid, ["contracts/parity/runtime-verification-baseline.json"])

    release_inventory = read_json(RELEASES, {}).get("release_inventory", {})
    for rel in release_inventory.get("releases", []) if isinstance(release_inventory, dict) else []:
        tag = rel.get("tag") or rel.get("release_tag")
        if not tag:
            continue
        rid = f"release:{tag}"
        entity = graph.entities.get(rid, {"id": rid, "type": "release", "name": tag, "domain": "release", "confidence": "verified", "source_refs": ["contracts/generated/releases/index.json"]})
        entity.update({k: v for k, v in rel.items() if k not in {"id", "type"}})
        entity["source_refs"] = sorted(set(entity.get("source_refs", []) + ["contracts/generated/releases/index.json"]))
        graph.entities[rid] = entity

    # Glossary and vocabulary.
    for item in meta.get("glossary", []):
        gid = f"glossary:{slug(item['term'])}"
        graph.add_entity({"id": gid, "type": "glossary", "name": item["term"], "domain": item.get("domain"), "description": item["definition"], "confidence": "source-derived", "source_refs": ["contracts/metadata/knowledge-base.json"], "aliases": item.get("aliases", [])})
    vocab_values = set(parity.get("status_vocabulary", [])) | set(meta.get("vocabulary_overrides", {}))
    # Include observed/not-observed/not-applicable and live device states when they are present in tracked contracts/source.
    tracked_text = (PARITY_MODEL.read_text(encoding="utf-8") + "\n" + DOC_META.read_text(encoding="utf-8") + "\n" + (ROOT / "src/lite/LiteUi.jsx").read_text(encoding="utf-8", errors="ignore"))
    candidates = ["ready", "ready-only", "observed", "implemented", "unsupported", "not-applicable", "match", "mapped", "mismatch", "not-observed", "stale", "degraded", "healthy", "offline", "online", "joining", "waiting", "repairing", "agent stopped", "remote access not ready", "protected server host", "release-promoted", "runtime-observed", "source-derived", "contract-derived", "accepted-limitation", "ready-with-accepted-limitations", "verified-with-mapped-presentation"]
    for value in candidates:
        if value in tracked_text or value in meta.get("vocabulary_overrides", {}):
            vocab_values.add(value)
    for status in sorted(vocab_values):
        override = meta.get("vocabulary_overrides", {}).get(status, {})
        graph.add_entity({
            "id": f"vocabulary:{slug(status)}", "type": "vocabulary", "name": status, "domain": "vocabulary", "confidence": "source-derived",
            "source_refs": ["contracts/parity/parity-model.json"] + (["contracts/metadata/knowledge-base.json"] if override else []),
            "description": override.get("meaning", f"Repository-defined status `{status}`; consult its owning contract before applying it across dimensions."),
            "does_not_prove": override.get("does_not_prove", "A status in one documentation dimension does not automatically prove another dimension."),
            "dimensions": [d for d in meta.get("status_dimensions", []) if status in {"implemented", "partial", "planned", "unvalidated"} and d == "implementation_status"] or [],
            "where_used": "Repository contracts, runtime evidence, generated documentation, or UI state where the owning source defines this exact value.",
            "proves": override.get("meaning", f"Only the owning status dimension's repository-defined condition for `{status}`."),
            "blocks_promotion": "policy-dependent",
            "blocks_writes": "policy-dependent",
            "can_coexist_with": "Independent status dimensions may coexist unless an owning contract explicitly forbids the combination.",
            "example": status,
        })

    # Platform capabilities from canonical catalog.
    cap_items = capabilities_payload.get("device_capabilities") if isinstance(capabilities_payload, dict) else None
    if not isinstance(cap_items, list):
        cap_items = doc_meta.get("capabilities", [])
    for cap in sorted(cap_items, key=lambda x: x.get("name", x.get("id", ""))):
        name = cap.get("name") or cap.get("id")
        if not name:
            continue
        cid = f"capability:{slug(name)}"
        graph.add_entity({"id": cid, "type": "capability", "name": cap.get("label") or name, "domain": "platform", "description": cap.get("verification_source") or cap.get("description") or "", "confidence": "source-derived", "source_refs": ["contracts/metadata/documentation-platform.json", "contracts/generated/device-capabilities.json"], **{k: cap.get(k) for k in ("freshness_seconds", "expiry_behavior", "degraded_behavior", "related_api", "runtime_evidence", "ui_states")}})

    # Requirements from architecture guarantees and traceability to tests by exact terms/source paths.
    for idx, guarantee in enumerate(arch.get("operational_guarantees", []), 1):
        qid = f"requirement:architecture-{idx:02d}"
        graph.add_entity({"id": qid, "type": "requirement", "name": guarantee, "domain": "architecture", "description": guarantee, "confidence": "source-derived", "source_refs": ["architecture/metadata/pocket-lab-architecture.json"]})
    # Source-derived test entities and conservative exact-reference verification relations.
    for rel in tests:
        tid = f"test:{rel}"
        graph.add_entity({"id": tid, "type": "test", "name": rel, "domain": "testing", "confidence": "source-derived", "source_refs": [rel]})
        text = test_text.get(rel, "")
        for eid, entity in list(graph.entities.items()):
            if entity["type"] not in {"domain", "component", "api", "reason-code", "journey", "runbook", "requirement"}:
                continue
            probes = [entity.get("name", "")] + entity.get("source_refs", [])
            if any(p and len(p) >= 8 and p in text for p in probes):
                graph.add_relation("verified_by", eid, tid, [rel])

    # Threat models are generated from verified boundaries plus component failure/security metadata; inferred threats are labeled inferred.
    for boundary, bmeta in sorted(arch.get("boundaries", {}).items()):
        tm_id = f"threat-model:{boundary}"
        members = [cid for cid, comp in arch["components"].items() if comp.get("security_boundary") == boundary]
        failures = sorted({f for cid in members for f in arch["components"][cid].get("failure_paths", [])})
        graph.add_entity({
            "id": tm_id, "type": "threat-model", "name": bmeta.get("name", boundary), "domain": "security",
            "description": bmeta.get("description", ""), "confidence": "inferred", "source_refs": ["architecture/metadata/pocket-lab-architecture.json"],
            "assets": [arch["components"][cid]["name"] for cid in members], "entry_points": sorted({p for cid in members for p in arch["components"][cid].get("protocols", [])}),
            "threats_or_failure_modes": failures, "mitigations": sorted({r for cid in members for r in arch["components"][cid].get("recovery_paths", [])}),
            "fail_behavior": "fail-closed where the owning component declares guarded write/admission behavior; otherwise unvalidated",
        })
        for cid in members:
            graph.add_relation("protected_by", f"component:{cid}", tm_id, ["architecture/metadata/pocket-lab-architecture.json"])

    # Runtime topology entities from promoted sanitized contracts.
    runtime_contracts = []
    for path in sorted(RUNTIME_CONTRACT_ROOT.glob("*.json")):
        payload = read_json(path)
        key = next((k for k in payload if k != "metadata"), path.stem)
        runtime_contracts.append({"id": key, "source": str(path.relative_to(ROOT)), "payload": payload.get(key, {})})
        eid = f"runtime:{slug(key)}"
        graph.add_entity({"id": eid, "type": "runtime-topology", "name": key.replace("_", " ").title(), "domain": "runtime", "description": "Sanitized promoted runtime topology projection.", "confidence": "release-promoted", "source_refs": [str(path.relative_to(ROOT))], "projection": payload.get(key, {})})

    # Ensure every discovered semantic domain has a graph entity before backlink validation.
    # Generated contracts contain additional low-level domains (for example workflow, drift,
    # projections, worker) that are not top-level Lite tabs. Keep them distinct instead of
    # incorrectly folding them into a user-facing tab.
    discovered_domains = sorted({str(e.get("domain")) for e in graph.entities.values() if e.get("domain")})
    for did in discovered_domains:
        eid = f"domain:{did}"
        if eid not in graph.entities:
            graph.add_entity({
                "id": eid,
                "type": "domain",
                "name": did.replace("_", " ").replace("-", " ").title(),
                "domain": did,
                "description": "Source-derived supporting domain discovered from generated contracts.",
                "confidence": "source-derived",
                "source_refs": ["contracts/generated/lite-openapi.json", "contracts/generated/lite-asyncapi.json", "contracts/generated/lite-sqlite-schema.json"],
                "status_dimensions": {
                    "implementation_status": "unvalidated",
                    "runtime_status": "unvalidated",
                    "operational_health": "unvalidated",
                    "runtime_parity": "unvalidated",
                    "evidence_status": "source-derived",
                    "confidence": "source-derived",
                    "freshness": "source-current",
                    "readiness": "unvalidated",
                    "capability_status": "unvalidated",
                    "degraded_reason": None,
                },
            })

    # Cross-link canonical architecture source verification to API, event, and SQLite entities.
    for cid, comp in sorted(arch["components"].items()):
        source_id = f"component:{cid}"
        for item in comp.get("source_verification", []):
            kind = item.get("kind")
            value = item.get("value")
            if not value:
                continue
            if kind == "route":
                parts = str(value).split(" ", 1)
                if len(parts) == 2:
                    aid = api_by_route_method.get((parts[0].upper(), normalize_route(parts[1])))
                    if aid:
                        graph.add_relation("uses", source_id, aid, ["architecture/metadata/pocket-lab-architecture.json"])
            elif kind == "nats_subject":
                sid = f"subject:{value}"
                if sid in graph.entities:
                    graph.add_relation("related_to", source_id, sid, ["architecture/metadata/pocket-lab-architecture.json"])
        for table in comp.get("durable_state_dependencies", []):
            tid = f"table:{table}"
            if tid in graph.entities:
                graph.add_relation("depends_on", source_id, tid, ["architecture/metadata/pocket-lab-architecture.json"])

    # Exact repository map reverse index from entity source refs.
    repo_map: dict[str, list[str]] = defaultdict(list)
    for eid, entity in graph.entities.items():
        for ref in entity.get("source_refs", []):
            path = ref.split(":", 1)[0]
            if path.startswith(("src/", "pocket-lab-final-structure/", "scripts/", "contracts/", "architecture/", "runbooks/", "tests/", "docs/", "tasks/")):
                repo_map[path].append(eid)

    return graph, {
        "meta": meta, "arch": arch, "doc_meta": doc_meta, "openapi": openapi, "frontend": frontend,
        "sqlite": sqlite, "asyncapi": asyncapi, "reasons": reasons, "parity": parity, "runtime": runtime,
        "accepted": accepted, "runbooks": runbooks, "tests": tests, "runtime_contracts": runtime_contracts,
        "repo_map": {k: sorted(set(v)) for k, v in sorted(repo_map.items())},
    }


def graph_indexes(graph: Graph) -> dict[str, Any]:
    outgoing: dict[str, list[dict[str, str]]] = defaultdict(list)
    incoming: dict[str, list[dict[str, str]]] = defaultdict(list)
    by_type: dict[str, list[str]] = defaultdict(list)
    by_domain: dict[str, list[str]] = defaultdict(list)
    for eid, entity in graph.entities.items():
        by_type[entity["type"]].append(eid)
        if entity.get("domain"):
            by_domain[str(entity["domain"])].append(eid)
    for rel in graph.relations.values():
        outgoing[rel["source"]].append({"type": rel["type"], "target": rel["target"]})
        incoming[rel["target"]].append({"type": rel["type"], "source": rel["source"]})
    return {
        "by_type": {k: sorted(v) for k, v in sorted(by_type.items())},
        "by_domain": {k: sorted(v) for k, v in sorted(by_domain.items())},
        "outgoing": {k: sorted(v, key=lambda x: (x["type"], x["target"])) for k, v in sorted(outgoing.items())},
        "incoming": {k: sorted(v, key=lambda x: (x["type"], x["source"])) for k, v in sorted(incoming.items())},
    }


def validate_graph(graph: Graph) -> list[str]:
    errors: list[str] = []
    ids = set(graph.entities)
    for rid, rel in graph.relations.items():
        if rel["source"] not in ids:
            errors.append(f"{rid}: dangling source {rel['source']}")
        if rel["target"] not in ids:
            errors.append(f"{rid}: dangling target {rel['target']}")
    for eid, entity in graph.entities.items():
        if entity.get("confidence") not in CONFIDENCE:
            errors.append(f"{eid}: invalid confidence {entity.get('confidence')}")
        for ref in entity.get("source_refs", []):
            if PRIVATE_PATH.search(ref):
                errors.append(f"{eid}: private absolute source path")
    # Domain status contradiction guard: parity verification and degradation may coexist; partial domains must not be upgraded.
    for did in ("identity", "rules"):
        e = graph.entities.get(f"domain:{did}", {})
        if e.get("status_dimensions", {}).get("implementation_status") == "implemented":
            errors.append(f"domain:{did}: partial surface was incorrectly upgraded to implemented")
    return errors


def safe_text(label: str, text: str) -> None:
    if SECRET.search(text):
        raise ValueError(f"secret-like value detected in {label}")
    if PRIVATE_PATH.search(text):
        raise ValueError(f"private absolute path detected in {label}")
    # Documentation may contain symbolic loopback references in existing sources, but knowledge export should not contain deployment IPv4s.
    for match in IPV4.findall(text):
        if match not in {"127.0.0.1", "0.0.0.0"}:
            raise ValueError(f"deployment IPv4 detected in {label}")


def load_schema(name: str) -> dict[str, Any]:
    return read_json(SCHEMA_ROOT / name)


def validate_export(export: dict[str, Any]) -> None:
    # Inline the small local schema set before validation so generation is fully offline and
    # does not depend on deprecated remote-reference resolution behavior.
    root_schema = json.loads(json.dumps(load_schema("knowledge-export.schema.json")))
    entity_schema = json.loads(json.dumps(load_schema("entity.schema.json")))
    relation_schema = json.loads(json.dumps(load_schema("relation.schema.json")))
    status_schema = load_schema("status-dimensions.schema.json")
    entity_schema["properties"]["status_dimensions"] = status_schema
    root_schema["properties"]["entities"]["items"] = entity_schema
    root_schema["properties"]["relations"]["items"] = relation_schema
    jsonschema.Draft202012Validator(root_schema).validate(export)


def entity_exports(graph: Graph, indexes: dict[str, Any], context: dict[str, Any], fingerprint: str) -> dict[str, Any]:
    def items(kind: str) -> list[dict[str, Any]]:
        return [graph.entities[eid] for eid in indexes["by_type"].get(kind, [])]

    api_by_route: dict[str, list[str]] = defaultdict(list)
    for api in items("api"):
        api_by_route[normalize_route(str(api.get("route") or ""))].append(api["id"])

    operational = []
    for entity in items("domain"):
        if entity["id"] not in {"domain:home", "domain:apps", "domain:devices", "domain:security", "domain:identity", "domain:rules", "domain:recovery"}:
            continue
        dims = entity.get("status_dimensions", {})
        operational.append({
            "domain": entity.get("domain"), "label": entity["name"], "implementation_status": dims.get("implementation_status"),
            "runtime_status": dims.get("runtime_status"), "operational_health": dims.get("operational_health"), "degraded_reason": dims.get("degraded_reason"),
            "runtime_parity": dims.get("runtime_parity"), "evidence_status": dims.get("evidence_status"), "freshness": dims.get("freshness"),
            "readiness": dims.get("readiness"), "source_of_truth": entity.get("source_refs", []),
            "user_impact": "Writes remain subject to backend freshness and readiness guards; semantic parity is reported separately.",
            "recommended_operator_action": "Follow the linked troubleshooting path when operational health is degraded.",
        })

    # API/UI reverse indexes from graph edges.
    api_to_ui: dict[str, list[str]] = defaultdict(list)
    ui_to_api: dict[str, list[str]] = defaultdict(list)
    for rel in graph.relations.values():
        if rel["type"] == "calls" and rel["source"].startswith("ui:") and rel["target"].startswith("api:"):
            api_to_ui[rel["target"]].append(rel["source"])
            ui_to_api[rel["source"]].append(rel["target"])

    lineage = []
    table_reads: dict[str, list[str]] = defaultdict(list)
    for rel in graph.relations.values():
        if rel["type"] == "reads" and rel["source"].startswith("api:") and rel["target"].startswith("table:"):
            table_reads[rel["source"]].append(rel["target"])
    for api_id, uis in sorted(api_to_ui.items()):
        api = graph.entities[api_id]
        lineage.append({
            "api": api_id, "route": api.get("route"), "method": api.get("method"), "ui": sorted(set(uis)),
            "sqlite": sorted(set(table_reads.get(api_id, []))), "source_refs": api.get("source_refs", []),
            "confidence": "contract-derived" if table_reads.get(api_id) else "unvalidated",
        })

    # Test traceability is relation-backed; no test implies verification by itself.
    traceability = []
    for eid, entity in sorted(graph.entities.items()):
        if entity["type"] not in {"requirement", "domain", "component", "api", "journey"}:
            continue
        tests = [x["target"] for x in indexes["outgoing"].get(eid, []) if x["type"] == "verified_by"]
        traceability.append({"entity": eid, "name": entity["name"], "type": entity["type"], "tests": tests, "verification_status": "test-linked" if tests else "unvalidated", "note": "A test link does not by itself prove runtime verification."})

    runtime = context["runtime"]
    freshness = {
        "current_repository_commit": SOURCE_COMMIT,
        "source_fingerprint": fingerprint,
        "promoted_release": runtime.get("release_tag"),
        "promoted_source_commit": runtime.get("source_commit"),
        "promoted_at": runtime.get("promoted_at"),
        "runtime_baseline_status": runtime.get("status"),
        "runtime_evidence_sanitized": runtime.get("sanitized"),
        "architecture_source": "architecture/metadata/pocket-lab-architecture.json",
        "openapi_source": "contracts/generated/lite-openapi.json",
        "sqlite_source": "contracts/generated/lite-sqlite-schema.json",
        "knowledge_generation_time": SOURCE_GENERATED_AT,
        "operational_degradation": [x["domain"] for x in operational if x["operational_health"] == "degraded"],
        "partial_parity_domains": [x["domain"] for x in operational if x["runtime_parity"] == "partial"],
        "limitations_count": len(items("limitation")),
        "unresolved_incidents_count": len(items("incident")),
        "adr_count": len(items("adr")),
        "generated_doc_drift": "checked-by-lite:docs:knowledge:check",
        "schema_drift": "checked-by-knowledge-schema-validation",
        "api_drift": "owned-by-existing-openapi-gates",
        "runtime_topology_freshness": runtime.get("promoted_at") or "unvalidated",
        "release_metadata_freshness": runtime.get("promoted_at") or "unvalidated",
        "ai_knowledge_export_freshness": fingerprint,
    }

    release_items = items("release")
    release_changes = []
    if len(release_items) >= 2:
        ordered = sorted(release_items, key=lambda x: (x.get("promoted_at") or "", x["name"]))
        for previous, current in zip(ordered, ordered[1:]):
            release_changes.append({"from": previous["id"], "to": current["id"], "status": "semantic-comparison-available", "added": [], "removed": [], "changed": [], "note": "Canonical release manifests should supply future semantic change classes."})
    elif release_items:
        release_changes.append({"from": None, "to": release_items[-1]["id"], "status": "no-comparable-verified-prior-release", "added": [], "removed": [], "changed": [], "note": "No second verified canonical release record exists in the repository; no historical diff is fabricated."})

    # Platform/capability support is derived conservatively from capability APIs and architecture component platform metadata.
    supported_platform_labels = ["Android/Termux ARM64", "ARM64 Ubuntu/proot", "Ubuntu/WSL2 Dev", "desktop browser", "mobile browser", "server phone", "secondary device"]
    platform_aliases = {
        "Android/Termux ARM64": {"Android/Termux", "Android", "ARM64"},
        "ARM64 Ubuntu/proot": {"Ubuntu", "ARM64"},
        "Ubuntu/WSL2 Dev": {"Ubuntu", "WSL2 development"},
        "desktop browser": {"Browser", "Desktop"},
        "mobile browser": {"Browser", "Android"},
        "server phone": {"Android/Termux", "Android", "ARM64"},
        "secondary device": {"Android/Termux", "Android", "ARM64"},
    }
    platform_matrix = []
    for cap in items("capability"):
        related_api = normalize_route(str(cap.get("related_api") or ""))
        component_ids: set[str] = set()
        if related_api:
            for aid in api_by_route.get(related_api, []):
                for rel in indexes["incoming"].get(aid, []):
                    if rel["type"] == "uses" and rel["source"].startswith("component:"):
                        component_ids.add(rel["source"])
        component_platforms = {p for cid in component_ids for p in graph.entities[cid].get("supported_platforms", [])}
        for platform in supported_platform_labels:
            overlap = component_platforms & platform_aliases[platform]
            status = "implemented" if overlap else "unvalidated"
            if overlap and platform in {"Android/Termux ARM64", "server phone", "secondary device"} and runtime.get("release_tag"):
                status = "observed" if platform != "secondary device" else "unvalidated"
            platform_matrix.append({
                "capability": cap["id"], "capability_name": cap["name"], "platform": platform, "status": status,
                "components": sorted(component_ids), "source_refs": sorted(set(cap.get("source_refs", []) + ["architecture/metadata/pocket-lab-architecture.json"])),
                "note": "Platform status is derived only from exact API/component relationships; unavailable relationships remain unvalidated.",
            })

    ownership_reverse: dict[str, list[str]] = defaultdict(list)
    for component in items("component"):
        for key in ("owner", "execution_owner", "data_owner", "recovery_owner", "runtime_owner"):
            value = component.get(key)
            if value:
                ownership_reverse[f"{key}:{value}"].append(component["id"])

    field_lineage = []
    projections_by_domain: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for projection in context["parity"].get("api_projections", []):
        projections_by_domain[projection.get("domain", "platform")].append(projection)
    for mapping in context["parity"].get("field_mappings", []):
        domain = mapping.get("domain", "platform")
        projections = projections_by_domain.get(domain, [])
        field_lineage.append({
            "id": mapping.get("id"), "domain": domain, "boundary": mapping.get("boundary"),
            "source_field": mapping.get("source"), "target_field": mapping.get("target"), "transformation": mapping.get("transformation"),
            "sensitivity": mapping.get("sensitivity"), "test_id": mapping.get("test_id"),
            "api_routes": sorted({f"{x.get('method')} {x.get('endpoint')}" for x in projections if x.get("endpoint")}),
            "frontend_consumers": sorted({c for x in projections for c in x.get("frontend_consumers", [])}),
            "confidence": "contract-derived", "source_refs": ["contracts/parity/parity-model.json"],
        })

    exports = {
        "components": items("component"), "domains": items("domain"), "apis": items("api"), "ui-surfaces": items("ui"),
        "tables": items("table"), "subjects": items("subject"), "journeys": items("journey"), "reason-codes": items("reason-code"),
        "adrs": items("adr"), "runbooks": items("runbook"), "incidents": items("incident"), "releases": release_items,
        "release-changes": release_changes, "limitations": items("limitation"), "threat-models": items("threat-model"), "capabilities": items("capability"),
        "platform-capabilities": platform_matrix, "ownership": {k: sorted(v) for k, v in sorted(ownership_reverse.items())},
        "incident-template": context["meta"].get("incident_template", {}), "field-lineage": field_lineage,
        "traceability": traceability, "glossary": items("glossary"), "vocabulary": items("vocabulary"),
        "repository-map": [{"source": k, "entities": v} for k, v in context["repo_map"].items()],
        "operational-health": operational, "freshness": freshness,
        "cross-references": {"outgoing": indexes["outgoing"], "incoming": indexes["incoming"]},
        "data-lineage": lineage,
        "api-ui-index": {"api_to_ui": {k: sorted(set(v)) for k, v in sorted(api_to_ui.items())}, "ui_to_api": {k: sorted(set(v)) for k, v in sorted(ui_to_api.items())}},
        "runtime-topology": items("runtime-topology"), "troubleshooting": items("troubleshooting"), "tests": items("test"), "requirements": items("requirement"),
    }
    return exports


def backlinks(entity_id: str, indexes: dict[str, Any], graph: Graph) -> tuple[list[str], list[str]]:
    uses = [f"{x['type']}: `{graph.entities[x['target']]['name']}`" for x in indexes["outgoing"].get(entity_id, [])]
    used_by = [f"{x['type']}: `{graph.entities[x['source']]['name']}`" for x in indexes["incoming"].get(entity_id, [])]
    return uses, used_by


def render_component_page(entity: dict[str, Any], indexes: dict[str, Any], graph: Graph) -> str:
    uses, used_by = backlinks(entity["id"], indexes, graph)
    rows = [
        ("Component ID", f"`{entity['id']}`"), ("Owner", entity.get("owner")), ("Execution owner", entity.get("execution_owner")),
        ("Data owner", entity.get("data_owner")), ("Recovery owner", entity.get("recovery_owner")), ("Runtime owner", entity.get("runtime_owner")),
        ("Runtime process", entity.get("runtime_process")), ("Runtime platform", entity.get("runtime_platform")),
        ("Security boundary", entity.get("security_boundary")), ("Confidence", entity.get("confidence")),
    ]
    out = frontmatter(entity["name"], entity.get("description") or "Pocket Lab Lite component knowledge page.", entity["confidence"])
    out += f"# {entity['name']}\n\n{entity.get('description','')}\n\n"
    out += "## Why it exists\n\n" + (entity.get("description") or "The canonical architecture model does not provide a separate rationale; responsibility is the verified source-derived purpose.") + "\n\n"
    out += "## Knowledge card\n\n" + md_table(["Field", "Value"], rows) + "\n"
    for title, key in [("Responsibilities", "description"), ("Inputs", "inputs"), ("Outputs", "outputs"), ("Health signals", "health_signals"), ("Failure modes", "failure_modes"), ("Recovery behavior", "recovery_behavior"), ("Evidence", "evidence"), ("Supported platforms", "supported_platforms")]:
        value = entity.get(key)
        if not value:
            continue
        out += f"## {title}\n\n"
        vals = value if isinstance(value, list) else [value]
        out += "".join(f"- {v}\n" for v in vals) + "\n"
    out += "## Depends on / uses\n\n" + ("".join(f"- {x}\n" for x in uses) if uses else "No verified graph relationships.\n") + "\n"
    out += "## Used by / backlinks\n\n" + ("".join(f"- {x}\n" for x in used_by) if used_by else "No verified backlinks.\n") + "\n"
    out += "## Release history\n\nNo canonical component introduction/fix release is recorded, so release history remains unvalidated rather than inferred.\n\n"
    out += "## Related architecture\n\n" + f"- [Production architecture component page](../../../production/architecture/components/{entity['id'].split(':',1)[1]}.md)\n\n"
    out += "## Canonical sources\n\n" + "".join(f"- `{x}`\n" for x in entity.get("source_refs", [])) + "\n"
    return out.rstrip() + "\n"


def render_docs(graph: Graph, indexes: dict[str, Any], exports: dict[str, Any]) -> dict[Path, str]:
    outputs: dict[Path, str] = {}
    stats = {k: len(v) for k, v in indexes["by_type"].items()}
    health = exports["operational-health"]
    outputs[DEV / "index.md"] = frontmatter("Living knowledgebase", "Canonical cross-linked Pocket Lab Lite knowledge system.") + "# Living Pocket Lab Lite knowledgebase\n\nThis generated layer joins architecture, contracts, runtime evidence, parity, data, events, tests, ownership, release knowledge, and troubleshooting without replacing their canonical sources.\n\n## What is indexed\n\n" + md_table(["Entity type", "Count"], sorted(stats.items())) + "\n## Truth model\n\nImplementation status, semantic parity, operational health, evidence, freshness, readiness, and capability availability are independent dimensions. A verified semantic mapping can coexist with degraded runtime health.\n"
    outputs[DEV / "operational-health.md"] = frontmatter("Operational health encyclopedia", "Operational health kept distinct from semantic parity.", "release-promoted") + "# Operational health encyclopedia\n\n" + md_table(["Domain", "Implementation", "Runtime", "Operational health", "Reason", "Semantic parity", "Evidence", "Freshness", "Readiness"], ((x["label"], x["implementation_status"], x["runtime_status"], x["operational_health"], x.get("degraded_reason"), x["runtime_parity"], x["evidence_status"], x["freshness"], x["readiness"]) for x in health)) + "\nOperational degradation is not converted into semantic mismatch.\n"
    components = exports["components"]
    outputs[DEV / "components/index.md"] = frontmatter("Component encyclopedia", "Index of canonical architecture component knowledge pages.") + "# Component encyclopedia\n\n" + md_table(["Component", "Owner", "Runtime", "Boundary", "Confidence"], ((f"[{c['name']}](./{c['id'].split(':',1)[1]}.md)", c.get("owner"), c.get("runtime_platform"), c.get("security_boundary"), c.get("confidence")) for c in components))
    for c in components:
        outputs[DEV / f"components/{c['id'].split(':',1)[1]}.md"] = render_component_page(c, indexes, graph)

    journey_rows = []
    journey_sections = []
    for j in exports["journeys"]:
        uses, used_by = backlinks(j["id"], indexes, graph)
        journey_rows.append((j["name"], j.get("domain"), len(j.get("components", [])), len(j.get("routes", [])), j.get("confidence")))
        journey_sections.append(f"## {j['name']}\n\n**Flow:** user action → UI/query → FastAPI → durable state or NATS → worker/agent/supervisor → evidence/projection → UI.\n\n**Verified components:** {', '.join('`'+x+'`' for x in j.get('components', [])) or 'none declared'}\n\n**Verified API routes:** {', '.join('`'+x+'`' for x in j.get('routes', [])) or 'none'}\n\n**Graph links:** {', '.join(uses) or 'none'}\n\n**Sources:** {', '.join('`'+x+'`' for x in j.get('source_refs', []))}\n")
    outputs[DEV / "journeys.md"] = frontmatter("How Pocket Lab works", "Generated end-to-end journey knowledge from verified repository sources.") + "# How Pocket Lab works\n\n" + md_table(["Journey", "Domain", "Components", "APIs", "Confidence"], journey_rows) + "\n" + "\n".join(journey_sections)

    api_ui = exports["api-ui-index"]
    api_rows = []
    for api in exports["apis"]:
        consumers = api_ui["api_to_ui"].get(api["id"], [])
        api_rows.append((f"`{api.get('method')} {api.get('route')}`", api.get("domain"), ", ".join(graph.entities[x]["name"] for x in consumers), api.get("operation_id"), api.get("confidence")))
    outputs[DEV / "api-ui-index.md"] = frontmatter("API ↔ UI reverse index", "Cross-reference from FastAPI contracts to frontend consumers and back.") + "# API ↔ UI reverse index\n\n## API → UI\n\n" + md_table(["API", "Domain", "UI consumers", "Operation", "Confidence"], api_rows) + "\n## UI → API\n\n" + md_table(["UI", "APIs"], ((graph.entities[uid]["name"], [graph.entities[x]["name"] for x in aids]) for uid, aids in api_ui["ui_to_api"].items()))
    outputs[DEV / "data-lineage.md"] = frontmatter("Data lineage explorer", "Field and route lineage using explicit API/UI/table relationships.") + "# Data lineage explorer\n\nVerified relationships are generated from frontend API usage, parity field mappings, and SQLite reader metadata. Missing links remain unvalidated rather than guessed.\n\n## Route lineage\n\n" + md_table(["API", "UI", "SQLite", "Confidence"], ((f"`{x['method']} {x['route']}`", x["ui"], x["sqlite"], x["confidence"]) for x in exports["data-lineage"])) + "\n## Field lineage\n\n" + md_table(["Mapping", "Domain", "Boundary", "Source field", "Target field", "Transformation", "APIs", "UI consumers", "Test"], ((x["id"], x["domain"], x["boundary"], x["source_field"], x["target_field"], x["transformation"], x["api_routes"], x["frontend_consumers"], x["test_id"]) for x in exports["field-lineage"]))
    outputs[DEV / "sqlite.md"] = frontmatter("SQLite knowledgebase", "Semantic SQLite metadata linked to SchemaSpy and API consumers.") + "# SQLite knowledgebase\n\nSchemaSpy remains the structural authority; this page adds semantic ownership.\n\n" + "\n".join(f"## `{t['name']}`\n\n{t.get('description','')}\n\n" + md_table(["Field", "Value"], [("Domain",t.get('domain')), ("Owner",t.get('owner')), ("Writer",t.get('writer')), ("Readers",t.get('readers')), ("Retention",t.get('retention')), ("Classification",t.get('classification')), ("Indexes",t.get('indexes')), ("Confidence",t.get('confidence'))]) for t in exports["tables"])
    outputs[DEV / "events-nats.md"] = frontmatter("NATS and event encyclopedia", "Sanitized subject/event knowledge from the generated AsyncAPI contract.") + "# NATS and event encyclopedia\n\nCredentials are never included. Incomplete delivery semantics remain explicitly incomplete.\n\n" + md_table(["Subject", "Domain", "Publishers", "Consumers", "Delivery", "Durability", "Retry"], ((f"`{s['name']}`", s.get("domain"), s.get("publishers"), s.get("subscribers"), s.get("delivery"), s.get("durability"), s.get("retry")) for s in exports["subjects"]))
    outputs[DEV / "reason-codes.md"] = frontmatter("Reason-code encyclopedia", "Canonical reason-code semantics with operational links.") + "# Reason-code encyclopedia\n\n" + md_table(["Code", "Domain", "Meaning", "Severity", "Retryable", "Terminal", "User interpretation"], ((f"`{r['name']}`", r.get("domain"), r.get("description"), r.get("severity"), r.get("retryable"), r.get("terminal"), r.get("user_interpretation")) for r in exports["reason-codes"]))
    outputs[DEV / "decisions.md"] = frontmatter("Architecture decisions", "Structured ADRs seeded only from verified repository architecture.") + "# Architecture decisions\n\n" + "\n".join(f"## {a['name']}\n\n**Status:** {a.get('status')}\n\n**Decision:** {a.get('description')}\n\n**Context:** {a.get('context')}\n\n**Alternatives:** {', '.join(a.get('alternatives') or [])}\n\n**Trade-offs:** {', '.join(a.get('trade_offs') or [])}\n\n**Consequences:** {', '.join(a.get('consequences') or [])}\n" for a in exports["adrs"])
    outputs[DEV / "ownership.md"] = frontmatter("Ownership encyclopedia", "System/subsystem ownership without personal names.") + "# Ownership encyclopedia\n\n" + md_table(["Component", "Owner", "Execution", "Data", "Recovery", "Runtime"], ((c["name"], c.get("owner"), c.get("execution_owner"), c.get("data_owner"), c.get("recovery_owner"), c.get("runtime_owner")) for c in components)) + "\n## Reverse owner lookup\n\n" + md_table(["Owner role", "Resources"], exports["ownership"].items())
    outputs[DEV / "repository-map.md"] = frontmatter("Repository map", "Reverse source lookup from files to knowledge entities.") + "# Repository map\n\n" + md_table(["Source", "Knowledge entities"], ((f"`{x['source']}`", x["entities"]) for x in exports["repository-map"]))
    outputs[DEV / "runtime-topology.md"] = frontmatter("Runtime topology", "Sanitized promoted runtime topology projections.", "release-promoted") + "# Runtime topology\n\nThis page uses the existing promoted runtime contracts. It never reads arbitrary `.pocketlab-dev` captures.\n\n" + md_table(["Projection", "Source", "Confidence"], ((x["name"], x["source_refs"], x["confidence"]) for x in exports["runtime-topology"]))
    outputs[DEV / "releases.md"] = frontmatter("Release knowledge", "Release knowledge from verified canonical release metadata and promoted runtime binding.", "release-promoted") + "# Release knowledge\n\n" + md_table(["Release", "Source commit", "Promoted", "Parity", "Manifest"], ((r["name"], r.get("source_commit"), r.get("promoted_at"), r.get("runtime_parity_status"), r.get("release_manifest_status")) for r in exports["releases"])) + "\n## What changed?\n\n" + md_table(["From", "To", "Status", "Note"], ((x.get("from"), x.get("to"), x.get("status"), x.get("note")) for x in exports["release-changes"]))
    for release in exports["releases"]:
        release_slug = slug(release["name"])
        outputs[DEV / f"releases/{release_slug}.md"] = frontmatter(release["name"], "Release-bound knowledge from verified canonical metadata.", release.get("confidence", "release-promoted")) + f"# {release['name']}\n\n" + md_table(["Field", "Value"], [("Source commit", release.get("source_commit")), ("Promoted at", release.get("promoted_at")), ("Runtime parity", release.get("runtime_parity_status")), ("Sanitized evidence", release.get("sanitized")), ("Artifact", release.get("artifact")), ("Artifact checksum", release.get("artifact_checksum")), ("Manifest status", release.get("release_manifest_status"))]) + "\nNo component introduction/fix chronology is invented when canonical release manifests are unavailable.\n"
        outputs[PROD / f"releases/{release_slug}.md"] = outputs[DEV / f"releases/{release_slug}.md"].replace("audience: knowledgebase", "audience: production")
    outputs[DEV / "limitations-incidents.md"] = frontmatter("Known issues and incidents", "Canonical limitation lifecycle plus incident model without fabricated history.") + "# Known issues / limitations lifecycle\n\n" + md_table(["ID", "Domain", "Status", "Description", "Confidence"], ((x["id"], x.get("domain"), x.get("status"), x.get("description"), x.get("confidence")) for x in exports["limitations"])) + "\n# Incident knowledgebase\n\n" + (md_table(["Incident", "Severity", "Release"], ((x["name"], x.get("severity"), x.get("affected_release")) for x in exports["incidents"])) if exports["incidents"] else "No structured historical incident records exist in the repository, so none are fabricated. The canonical metadata defines the incident template for future records.\n")
    outputs[DEV / "troubleshooting.md"] = frontmatter("Troubleshooting decision trees", "Generated safe troubleshooting paths from structured knowledge metadata.") + "# Troubleshooting decision trees\n\n" + "\n".join(f"## {t['name']}\n\n**Check**\n" + "".join(f"- {x}\n" for x in t.get("checks", [])) + "\n**Recovery**\n" + "".join(f"- {x}\n" for x in t.get("recovery", [])) for t in exports["troubleshooting"])
    outputs[DEV / "threat-models.md"] = frontmatter("Security threat models", "Trust-boundary threat/failure views derived from canonical architecture.", "inferred") + "# Security threat models\n\nThreat/failure modes are labeled inferred when they are derived from verified boundary/component failure metadata rather than a historical incident.\n\n" + "\n".join(f"## {t['name']}\n\n{t.get('description','')}\n\n**Assets:** {', '.join(t.get('assets') or [])}\n\n**Entry points:** {', '.join(t.get('entry_points') or [])}\n\n**Threats/failure modes:** {', '.join(t.get('threats_or_failure_modes') or []) or 'unvalidated'}\n\n**Mitigations/recovery:** {', '.join(t.get('mitigations') or []) or 'unvalidated'}\n" for t in exports["threat-models"])
    outputs[DEV / "traceability.md"] = frontmatter("Tests and traceability", "Requirement/implementation/test traceability without equating tests to runtime verification.") + "# Tests and traceability\n\n" + md_table(["Entity", "Type", "Tests", "Status"], ((x["name"], x["type"], x["tests"], x["verification_status"]) for x in exports["traceability"]))
    outputs[DEV / "capabilities.md"] = frontmatter("Platforms and capabilities", "Capability knowledge designed for Android/Termux, ARM64, WSL2, desktop, and mobile contexts.") + "# Platforms and capabilities\n\n" + md_table(["Capability", "Freshness", "Expiry", "Degraded behavior", "Runtime evidence"], ((x["name"], x.get("freshness_seconds"), x.get("expiry_behavior"), x.get("degraded_behavior"), x.get("runtime_evidence")) for x in exports["capabilities"])) + "\n## Platform matrix\n\n" + md_table(["Capability", "Platform", "Status", "Components"], ((x["capability_name"], x["platform"], x["status"], x["components"]) for x in exports["platform-capabilities"])) + "\nIdentity and Rules remain partial and are not promoted to supported/verified by this matrix.\n"
    outputs[DEV / "vocabulary.md"] = frontmatter("Vocabulary", "Canonical status semantics and independent documentation dimensions.") + "# Vocabulary\n\n" + md_table(["Status", "Exact meaning", "Does not prove", "Dimensions", "Blocks promotion", "Blocks writes", "Can coexist"], ((f"`{x['name']}`", x.get("description"), x.get("does_not_prove"), x.get("dimensions"), x.get("blocks_promotion"), x.get("blocks_writes"), x.get("can_coexist_with")) for x in exports["vocabulary"]))
    outputs[DEV / "glossary.md"] = frontmatter("Glossary", "Canonical Pocket Lab Lite terminology ontology.") + "# Glossary\n\n" + md_table(["Term", "Definition", "Aliases", "Domain"], ((x["name"], x.get("description"), x.get("aliases"), x.get("domain")) for x in exports["glossary"]))
    outputs[DEV / "freshness.md"] = frontmatter("Knowledge freshness dashboard", "Pre-generated documentation freshness and evidence status dashboard.") + "# Freshness dashboard\n\n" + md_table(["Signal", "Value"], sorted(exports["freshness"].items()))
    outputs[DEV / "knowledge-graph.md"] = frontmatter("Knowledge graph", "Stable entity/relation graph and backlinks for Pocket Lab Lite.") + "# Knowledge graph\n\n" + md_table(["Metric", "Count"], [("Entities", len(graph.entities)), ("Relations", len(graph.relations)), ("Entity types", len(indexes["by_type"])), ("Domains", len(indexes["by_domain"]))]) + "\nThe AI-ready canonical export is `contracts/generated/knowledge/index.json`. Relations use stable IDs and graph validation rejects dangling references.\n"

    # Production keeps Lite-friendly operator views and omits source-heavy catalogs.
    outputs[PROD / "index.md"] = frontmatter("Pocket Lab Lite knowledge", "Operator-oriented living knowledgebase.") + "# Pocket Lab Lite knowledge\n\nUse this section to understand current health, workflows, supported capabilities, known limitations, releases, and safe recovery guidance.\n"
    outputs[PROD / "current-health.md"] = frontmatter("Current health", "Operational health and semantic parity shown independently.", "release-promoted") + "# Current health\n\n" + md_table(["Area", "Health", "Semantic parity", "Freshness", "Action"], ((x["label"], x["operational_health"], x["runtime_parity"], x["freshness"], x["recommended_operator_action"]) for x in health))
    outputs[PROD / "journeys.md"] = frontmatter("How Pocket Lab works", "Lite-friendly workflow guide generated from verified journey metadata.") + "# How Pocket Lab works\n\n" + md_table(["Workflow", "Area", "Status"], ((x["name"], x.get("domain"), x.get("confidence")) for x in exports["journeys"]))
    outputs[PROD / "troubleshooting.md"] = frontmatter("Troubleshooting", "Safe operator guidance generated from canonical decision trees.") + "# Troubleshooting\n\n" + "\n".join(f"## {t['name']}\n\n" + "".join(f"- Check: {x}\n" for x in t.get("checks", [])) + "".join(f"- Recovery: {x}\n" for x in t.get("recovery", [])) for t in exports["troubleshooting"])
    outputs[PROD / "known-issues.md"] = frontmatter("Known issues", "Current limitations without hiding accepted constraints.") + "# Known issues\n\n" + md_table(["Area", "Status", "What it means"], ((x.get("domain"), x.get("status"), x.get("description")) for x in exports["limitations"]))
    outputs[PROD / "releases.md"] = frontmatter("Releases", "Verified release binding and promoted runtime evidence.", "release-promoted") + "# Releases\n\n" + md_table(["Release", "Source", "Runtime parity", "Manifest status"], ((r["name"], r.get("source_commit"), r.get("runtime_parity_status"), r.get("release_manifest_status")) for r in exports["releases"]))
    outputs[PROD / "supported-platforms.md"] = frontmatter("Supported platforms", "Platform-aware capability knowledge.") + "# Supported platforms\n\nPocket Lab Lite remains designed for Android/Termux ARM64 and low-power edge operation, with Ubuntu/WSL2 used for development. Capability evidence is nuanced; implemented, observed, verified, partial, and unvalidated are not collapsed into yes/no.\n\n" + md_table(["Capability", "Freshness", "Degraded behavior"], ((x["name"], x.get("freshness_seconds"), x.get("degraded_behavior")) for x in exports["capabilities"]))
    outputs[PROD / "security.md"] = frontmatter("Security model", "Trust boundaries, fail-closed controls, and safe recovery guidance.") + "# Security model\n\n" + md_table(["Boundary", "Assets", "Entry points", "Confidence"], ((x["name"], x.get("assets"), x.get("entry_points"), x.get("confidence")) for x in exports["threat-models"]))
    outputs[PROD / "vocabulary.md"] = outputs[DEV / "vocabulary.md"].replace("audience: knowledgebase", "audience: production")
    outputs[PROD / "glossary.md"] = outputs[DEV / "glossary.md"].replace("audience: knowledgebase", "audience: production")
    return outputs


def build_outputs() -> tuple[dict[Path, str], dict[str, Any]]:
    start = time.perf_counter()
    graph, context = build_graph()
    errors = validate_graph(graph)
    if errors:
        raise ValueError("knowledge graph validation failed:\n" + "\n".join(f" - {x}" for x in errors))
    indexes = graph_indexes(graph)
    source_paths = [META, ARCH, DOC_META, OPENAPI, FRONTEND, SQLITE, ASYNCAPI, REASON_CODES, CAPABILITIES, SERVICES, PROJECTIONS, UI_STATES, RELEASES, PARITY_MODEL, RUNTIME_BASELINE, ACCEPTED_LIMITATIONS]
    source_paths.extend(sorted(RUNTIME_CONTRACT_ROOT.glob("*.json")))
    source_paths.extend(sorted(RUNBOOK_ROOT.glob("*.yaml")))
    source_paths.extend(ROOT / rel for rel in context["tests"])
    source_paths.append(ROOT / GENERATOR)
    source_paths.extend(sorted(SCHEMA_ROOT.glob("*.json")))
    fingerprints, fp = source_fingerprint(source_paths)
    exports = entity_exports(graph, indexes, context, fp)
    entities = [graph.entities[k] for k in sorted(graph.entities)]
    relations = [graph.relations[k] for k in sorted(graph.relations)]
    export = {
        "schema_version": SCHEMA_VERSION,
        "generator": GENERATOR,
        "source_fingerprint": fp,
        "entities": entities,
        "relations": relations,
        "indexes": indexes,
        "statistics": {
            "entity_count": len(entities), "relation_count": len(relations),
            "entity_type_counts": {k: len(v) for k, v in indexes["by_type"].items()},
            "source_count": len(fingerprints),
        },
    }
    validate_export(export)
    outputs: dict[Path, str] = {OUT / "index.json": stable_json(export)}
    envelope_meta = {"schema_version": SCHEMA_VERSION, "generator": GENERATOR, "generator_version": GENERATOR_VERSION, "source_commit": SOURCE_COMMIT, "generated_at": SOURCE_GENERATED_AT, "source_fingerprint": fp}
    for name, value in sorted(exports.items()):
        outputs[OUT / f"{name}.json"] = stable_json({"metadata": envelope_meta, "items": value})
    outputs.update(render_docs(graph, indexes, exports))
    elapsed = time.perf_counter() - start
    report = {"entities": len(entities), "relations": len(relations), "pages": sum(1 for p in outputs if p.suffix == ".md"), "machine_artifacts": sum(1 for p in outputs if p.suffix == ".json"), "source_fingerprint": fp, "duration_seconds": round(elapsed, 3)}
    for path, text in outputs.items():
        safe_text(str(path.relative_to(ROOT)), text)
    return outputs, report




def _release_title(text: str, path: Path) -> str:
    match = re.search(r'^title: "([^"]+)"$', text, re.MULTILINE)
    if not match:
        raise ValueError(f"generated release page lacks a frontmatter title: {path.relative_to(ROOT)}")
    return match.group(1)


def expected_release_nav_lines(outputs: dict[Path, str], audience_root: Path, indent: str) -> list[str]:
    release_root = audience_root / "releases"
    entries = []
    for path, text in outputs.items():
        if path.parent != release_root or path.suffix != ".md":
            continue
        title = _release_title(text, path)
        rel = path.relative_to(ROOT / "docs").as_posix()
        entries.append((title, f"{indent}- {title}: {rel}"))
    return [line for _, line in sorted(entries)]


def render_mkdocs_release_nav(outputs: dict[Path, str], current: str) -> str:
    rendered = current
    for audience, (begin_marker, end_marker, audience_root) in NAV_MARKERS.items():
        begin_matches = list(re.finditer(rf"^(?P<indent>\s*){re.escape(begin_marker)}\s*$", rendered, re.MULTILINE))
        end_matches = list(re.finditer(rf"^(?P<indent>\s*){re.escape(end_marker)}\s*$", rendered, re.MULTILINE))
        if len(begin_matches) != 1 or len(end_matches) != 1:
            raise ValueError(
                f"mkdocs release-nav markers for {audience} must exist exactly once "
                f"(begin={len(begin_matches)}, end={len(end_matches)})"
            )
        begin = begin_matches[0]
        end = end_matches[0]
        if end.start() <= begin.end():
            raise ValueError(f"mkdocs release-nav markers are out of order for {audience}")
        if begin.group("indent") != end.group("indent"):
            raise ValueError(f"mkdocs release-nav marker indentation differs for {audience}")
        indent = begin.group("indent")
        lines = expected_release_nav_lines(outputs, audience_root, indent)
        replacement = begin.group(0) + "\n" + ("\n".join(lines) + "\n" if lines else "") + end.group(0)
        rendered = rendered[:begin.start()] + replacement + rendered[end.end():]
    return rendered


def sync_mkdocs_release_nav(outputs: dict[Path, str]) -> bool:
    current = MKDOCS.read_text(encoding="utf-8")
    expected = render_mkdocs_release_nav(outputs, current)
    if current == expected:
        return False
    tmp = MKDOCS.with_name(MKDOCS.name + ".tmp")
    tmp.write_text(expected, encoding="utf-8")
    os.replace(tmp, MKDOCS)
    return True


def check_mkdocs_release_nav(outputs: dict[Path, str]) -> list[str]:
    current = MKDOCS.read_text(encoding="utf-8")
    expected = render_mkdocs_release_nav(outputs, current)
    return [] if current == expected else [
        "mkdocs.yml knowledge release navigation drift (run task lite:docs:sync)"
    ]


def write_outputs(outputs: dict[Path, str]) -> int:
    changed = 0
    expected = set(outputs)
    for root in (OUT, DEV, PROD):
        if root.exists():
            for path in sorted(root.rglob("*"), reverse=True):
                if path.is_file() and path not in expected:
                    path.unlink()
                    changed += 1
    for path, text in sorted(outputs.items(), key=lambda x: str(x[0])):
        path.parent.mkdir(parents=True, exist_ok=True)
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current != text:
            tmp = path.with_name(path.name + ".tmp")
            tmp.write_text(text, encoding="utf-8")
            os.replace(tmp, path)
            changed += 1
    return changed


def check_outputs(outputs: dict[Path, str]) -> list[str]:
    drift = []
    expected = set(outputs)
    for path, text in sorted(outputs.items(), key=lambda x: str(x[0])):
        if not path.exists() or path.read_text(encoding="utf-8") != text:
            drift.append(str(path.relative_to(ROOT)))
    for root in (OUT, DEV, PROD):
        if root.exists():
            for path in sorted(root.rglob("*")):
                if path.is_file() and path not in expected:
                    drift.append(str(path.relative_to(ROOT)))
    return sorted(set(drift))


def validate_links(outputs: dict[Path, str]) -> list[str]:
    errors = []
    md_link = re.compile(r"\[[^\]]+\]\(([^)]+\.md)(?:#[^)]+)?\)")
    for path, text in outputs.items():
        if path.suffix != ".md":
            continue
        for target in md_link.findall(text):
            if target.startswith(("http://", "https://")):
                continue
            resolved = (path.parent / target).resolve()
            if resolved not in outputs and not resolved.exists():
                errors.append(f"{path.relative_to(ROOT)} -> {target}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the Pocket Lab Lite living knowledgebase")
    parser.add_argument("command", choices=("generate", "check", "graph", "health", "traceability", "releases", "ai-export"))
    args = parser.parse_args()
    outputs, report = build_outputs()
    link_errors = validate_links(outputs)
    if link_errors:
        print("Knowledge link errors:", file=sys.stderr)
        for error in link_errors:
            print(f" - {error}", file=sys.stderr)
        return 1
    if args.command == "generate":
        changed = write_outputs(outputs)
        nav_changed = sync_mkdocs_release_nav(outputs)
        print(
            f"PASS knowledge generation: {report['entities']} entities, {report['relations']} relations, "
            f"{report['pages']} pages, {report['machine_artifacts']} machine artifacts, {changed} files changed, "
            f"release_nav={'updated' if nav_changed else 'current'}, {report['duration_seconds']:.3f}s"
        )
        return 0
    if args.command in {"graph", "health", "traceability", "releases", "ai-export"}:
        # Subcommands are bounded views over one cached generator run; generation remains centralized to avoid repeated scanning.
        keys = {"graph": "index.json", "health": "operational-health.json", "traceability": "traceability.json", "releases": "releases.json", "ai-export": "index.json"}
        path = OUT / keys[args.command]
        expected = outputs[path]
        if not path.exists() or path.read_text(encoding="utf-8") != expected:
            print(f"FAIL {args.command}: generated artifact drift at {path.relative_to(ROOT)}", file=sys.stderr)
            return 1
        print(f"PASS knowledge {args.command}: {path.relative_to(ROOT)}")
        return 0
    drift = check_outputs(outputs) + check_mkdocs_release_nav(outputs)
    if drift:
        print("Knowledgebase drift:", file=sys.stderr)
        for item in drift:
            print(f" - {item}", file=sys.stderr)
        return 1
    print(f"PASS knowledge check: {report['entities']} entities, {report['relations']} relations, {report['pages']} pages, {report['machine_artifacts']} machine artifacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
