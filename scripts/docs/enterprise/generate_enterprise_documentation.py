#!/usr/bin/env python3
"""Generate enterprise Documentation Platform projections from canonical repository evidence.

This generator is deliberately static. It may inspect Git/source files and already-canonical
or promoted sanitized contracts. It never captures runtime, polls services, promotes evidence,
or invokes security scanners. Heavy-tool output must be normalized separately before it can
become an input to this generator.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any, Iterable

import jsonschema
import yaml

from enterprise_completion import complete as complete_enterprise_projection
from documentation_ia import build as build_documentation_ia

ROOT = Path(__file__).resolve().parents[3]
GENERATOR = ROOT / "scripts/docs/enterprise/generate_enterprise_documentation.py"
SCHEMA = ROOT / "schemas/documentation/enterprise-documentation.schema.json"
TOOLS = ROOT / "contracts/metadata/documentation-security-tools.json"
PLATFORM = ROOT / "contracts/metadata/documentation-platform.json"
EXPERIENCE = ROOT / "contracts/metadata/documentation-experience.json"
KNOWLEDGE = ROOT / "contracts/generated/knowledge/index.json"
INTELLIGENCE = ROOT / "contracts/generated/documentation-intelligence/index.json"
OP_HEALTH = ROOT / "contracts/generated/runtime/domain-operational-health.json"
RUNTIME = ROOT / "contracts/parity/runtime-verification-baseline.json"
ARCH = ROOT / "architecture/metadata/pocket-lab-architecture.json"
ASYNCAPI = ROOT / "contracts/generated/lite-asyncapi.json"
OPENAPI = ROOT / "contracts/generated/lite-openapi.json"
REASONS = ROOT / "contracts/generated/reason-codes.json"
RELEASES = ROOT / "contracts/generated/releases/index.json"
ADRS = ROOT / "contracts/generated/knowledge/adrs.json"
RELEASE_CHANGES_KB = ROOT / "contracts/generated/knowledge/release-changes.json"
VALIDATION = ROOT / "validation/latest/summary.json"
OUT = ROOT / "contracts/generated/documentation-enterprise"
DOC = ROOT / "docs/generated/enterprise"
THREAT_MODEL = ROOT / "contracts/security/threat-model.json"
DIAGRAMS = ROOT / "docs/generated/assets/enterprise"
INDEX = OUT / "index.json"

PRIVATE = re.compile(r"(?:(?<![A-Za-z0-9._-])/home/[^/\s]+|/data/data/com\.termux/files/(?:home|usr)|[A-Za-z]:\\Users\\|nats://[^\s]+@)", re.I)
SECRET = re.compile(r"(?:BEGIN [A-Z ]*PRIVATE KEY|(?:password|passwd|token|secret|api[_-]?key|credential|authorization)\s*[=:]\s*[^\s,}\]]{6,})", re.I)
STRIDE = ["Spoofing", "Tampering", "Repudiation", "Information Disclosure", "Denial of Service", "Elevation of Privilege"]
BOUNDARIES = [
    ("application-container", "Application-container boundary"),
    ("browser", "Browser trust boundary"),
    ("control-api", "Control API boundary"),
    ("durable-state", "Durable-state boundary"),
    ("external-release", "External release boundary"),
    ("managed-device", "Managed-device boundary"),
    ("messaging-execution", "Messaging and execution boundary"),
    ("server-host", "Server-host boundary"),
    ("private-network", "Private network and Tailnet boundary"),
]
SAFE_COMMANDS = {
    "pm2 status": "READ_ONLY",
    "pm2 logs <process> --lines 80": "READ_ONLY",
    "ss -ltnp": "READ_ONLY",
    "tailscale status": "READ_ONLY",
    "tailscale ip -4": "READ_ONLY",
    "curl -fsS http://127.0.0.1:8443/api/lite/status": "READ_ONLY",
    "task lite:docs:check": "READ_ONLY",
    "task lite:parity:runtime:compare": "READ_ONLY",
}


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def stable(value: Any) -> str:
    return json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, separators=(",", ": ")) + "\n"


def sha(value: Any) -> str:
    raw = value if isinstance(value, bytes) else stable(value).encode()
    return hashlib.sha256(raw).hexdigest()


def source_commit() -> str:
    # Match the established Lite documentation convention: tracked generated docs use a
    # stable honest marker. CI/release jobs may pass SOURCE_COMMIT explicitly. Embedding
    # git HEAD directly would make every commit invalidate its own generated artifacts.
    return os.environ.get("SOURCE_COMMIT", "").strip() or "uncommitted"


def tree_hash() -> str:
    return os.environ.get("SOURCE_TREE_HASH", "").strip() or "uncommitted"


def frontmatter(title: str, description: str, audience: str, page_type: str = "reference") -> str:
    return (
        "---\n"
        f'title: "{title.replace(chr(34), chr(39))}"\n'
        f'description: "{description.replace(chr(34), chr(39))}"\n'
        "generated: true\n"
        f"audience: {audience}\n"
        f"page_type: {page_type}\n"
        "confidence: generated\n"
        "---\n\n"
    )


def table(headers: list[str], rows: Iterable[Iterable[Any]]) -> str:
    def cell(v: Any) -> str:
        if v is None or v == "": return "—"
        if isinstance(v, bool): return "yes" if v else "no"
        if isinstance(v, (list, tuple, set)): v = ", ".join(str(x) for x in v) if v else "—"
        return str(v).replace("\n", " ").replace("|", "\\|")
    rows = list(rows)
    return "\n".join([
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
        *("| " + " | ".join(cell(x) for x in row) + " |" for row in rows),
    ]) + "\n"


def safe(label: str, text: str) -> None:
    if PRIVATE.search(text): raise ValueError(f"{label}: private path or credential-bearing URL detected")
    if SECRET.search(text): raise ValueError(f"{label}: secret-like value detected")


def inputs() -> list[Path]:
    paths = [GENERATOR, ROOT / "scripts/docs/enterprise/enterprise_completion.py", ROOT / "scripts/docs/enterprise/documentation_ia.py", ROOT / "scripts/docs/enterprise/threat_model_experience.py", ROOT / "scripts/docs/release_model.py", ROOT / "security/threat-model-scenarios.json", ROOT / "scripts/docs/enterprise/supply_chain_automation.py", ROOT / "scripts/docs/enterprise/release_provenance.py", SCHEMA, TOOLS, PLATFORM, EXPERIENCE, KNOWLEDGE, INTELLIGENCE, OP_HEALTH, RUNTIME, ARCH, ASYNCAPI, OPENAPI, REASONS, RELEASES, ADRS, RELEASE_CHANGES_KB]
    paths.append(ROOT / "scripts/docs/enterprise/threat_model_poster.py")
    paths.append(ROOT / "scripts/docs/enterprise/threat_model_layout.py")
    paths += sorted((ROOT / "docs/assets/diagrams/production/icons").glob("*.svg"))
    paths += sorted((ROOT / "tasks").glob("Taskfile*.yml"))
    paths += sorted((ROOT / "operations").glob("*.yaml"))
    paths += sorted((ROOT / "runbooks").glob("*.yaml"))
    paths += sorted((ROOT / "contracts/generated/supply-chain").glob("*.json"))
    if (ROOT / "contracts/generated/release-provenance.json").exists(): paths.append(ROOT / "contracts/generated/release-provenance.json")
    if (ROOT / "contracts/generated/release-signatures.json").exists(): paths.append(ROOT / "contracts/generated/release-signatures.json")
    if (ROOT / "contracts/generated/releases/promoted-release-evidence.json").exists(): paths.append(ROOT / "contracts/generated/releases/promoted-release-evidence.json")
    return [p for p in paths if p.exists()]


def fingerprint() -> tuple[dict[str, str], str]:
    values = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs()}
    return values, sha(values)


def task_inventory() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    files = [ROOT / "Taskfile.yml", *sorted((ROOT / "tasks").glob("Taskfile*.yml"))]
    for path in files:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for name, spec in sorted((data.get("tasks") or {}).items()):
            if not isinstance(spec, dict): continue
            cmds = []
            deps = []
            for dep in spec.get("deps", []) or []:
                deps.append(dep if isinstance(dep, str) else dep.get("task", "unknown"))
            for raw in spec.get("cmds", []) or []:
                if isinstance(raw, str): cmds.append(raw)
                elif isinstance(raw, dict): cmds.append(raw.get("task") and f"task {raw['task']}" or raw.get("cmd", "structured command"))
            joined = " ".join(cmds).lower()
            mutation = any(x in joined for x in [" promote", " release", " install", " restart", " rm ", " mv ", " write", " generate"])
            capture = "termux:capture" in name or "capture_termux" in joined
            promote = "promote" in name or "promote_termux" in joined
            termux = any(x in (name + " " + joined).lower() for x in ["termux", "android"])
            heavy = any(x in joined for x in ["playwright", "mkdocs", "graphviz", "schemaspy", "schemathesis", "oasdiff", "syft", "grype", "semgrep", "gitleaks"])
            rows.append({
                "name": name,
                "purpose": spec.get("desc", "No canonical description declared."),
                "source": str(path.relative_to(ROOT)),
                "dependencies": sorted(set(deps)),
                "commands": cmds,
                "captures_runtime": capture,
                "promotes_evidence": promote,
                "repository_mutation": mutation,
                "runtime_mutation": termux and mutation,
                "requires_termux": termux and (capture or "runtime" in name),
                "requires_wsl2_or_ci": heavy and not termux,
                "safe_local_default": not capture and not promote and not (termux and mutation),
                "runtime_class": "heavy-dev" if heavy else "bounded",
            })
    return rows


def task_workflows(tasks: list[dict[str, Any]]) -> dict[str, list[str]]:
    names = [x["name"] for x in tasks]
    groups = {
        "Development loop": [n for n in names if n in {"lite:check", "lite:test:backend", "lite:test:frontend"}],
        "Documentation loop": [n for n in names if n.startswith("lite:docs:") and n.endswith(("generate", "check", "sync"))],
        "API-validation loop": [n for n in names if any(x in n for x in ["contracts", "schemathesis", "breaking-changes"])],
        "Runtime-evidence loop": [n for n in names if "runtime:termux" in n or "evidence:runtime" in n],
        "Security-analysis loop": [n for n in names if "security" in n or "redaction" in n],
        "Release loop": [n for n in names if "release" in n],
        "Recovery-diagnostics loop": [n for n in names if "recovery" in n or "runtime:termux:inspect" in n],
    }
    return {k: sorted(v) for k, v in groups.items()}


def event_inventory() -> list[dict[str, Any]]:
    data = read_json(ASYNCAPI, {}) or {}
    channels = data.get("channels", {}) or {}
    rows = []
    for subject, value in sorted(channels.items()):
        ops = value if isinstance(value, dict) else {}
        publisher = "backend/worker/agent (source-derived ownership requires review)"
        consumers = ["NATS/JetStream consumer"]
        messages = []
        for direction in ("publish", "subscribe"):
            d = ops.get(direction, {}) if isinstance(ops, dict) else {}
            m = d.get("message", {}) if isinstance(d, dict) else {}
            if "$ref" in m: messages.append(m["$ref"].split("/")[-1])
            elif m.get("name"): messages.append(m["name"])
        rows.append({
            "subject": subject,
            "domain": subject.split(".")[2] if subject.startswith("pocketlab.") and len(subject.split(".")) > 2 else "platform",
            "publisher": publisher,
            "consumers": consumers,
            "messages": sorted(set(messages)),
            "durability": "JetStream-governed where declared; otherwise unvalidated",
            "ordering": "subject/consumer semantics; review canonical AsyncAPI",
            "idempotency": "consumer-specific; unvalidated unless operation contract declares it",
            "acknowledgment": "consumer-specific",
            "failure_handling": "retry/DLQ only where canonical contracts declare it",
            "audit_implications": "lifecycle events should remain observable and sanitized",
            "source_owner": "contracts/generated/lite-asyncapi.json",
        })
    return rows


def dependency_rows() -> list[dict[str, Any]]:
    intel = read_json(INTELLIGENCE, {}) or {}
    rows = intel.get("items", {}).get("dependency_health", []) or []
    output = []
    for domain in rows:
        for dep in domain.get("dependencies", []):
            output.append({
                "domain": domain.get("label") or domain.get("domain"),
                "dependency": dep.get("name"),
                "type": "runtime/service" if dep.get("evidence_status") == "verified-runtime-baseline" else "canonical/source",
                "owner": dep.get("name"),
                "state": dep.get("state", "unvalidated"),
                "evidence_authority": dep.get("evidence_status", "unvalidated"),
                "freshness": domain.get("freshness", "unvalidated"),
                "blocking": dep.get("name") in {"FastAPI", "NATS/JetStream", "worker", "SQLite"},
                "affected_capabilities": [domain.get("label") or domain.get("domain")],
                "root_cause": dep.get("note") or domain.get("reason") or "unvalidated",
            })
    return output


def dependency_state_badge(state: Any) -> str:
    """Render textual/symbolic state so dependency status is never color-only."""
    normalized_state = str(state or "unvalidated")
    state_symbol = {
        "healthy": "●",
        "degraded": "▲",
        "unavailable": "!",
        "stale": "◐",
        "unvalidated": "○",
    }.get(normalized_state, "○")
    state_class = re.sub(r"[^a-z0-9-]+", "-", normalized_state.lower())
    return (
        f'<span class="pl-intel-status pl-intel-status--{state_class}">'
        f'<span aria-hidden="true">{state_symbol}</span> {html.escape(normalized_state)}</span>'
    )


def dependency_evidence_badge(evidence: Any) -> str:
    normalized_evidence = str(evidence or "unvalidated")
    evidence_symbol = "●" if normalized_evidence == "verified-runtime-baseline" else "◇"
    status_class = "healthy" if normalized_evidence == "verified-runtime-baseline" else "unvalidated"
    return (
        f'<span class="pl-intel-status pl-intel-status--{status_class}">'
        f'<span aria-hidden="true">{evidence_symbol}</span> {html.escape(normalized_evidence)}</span>'
    )


def dependency_status_badge(state: Any, evidence: Any) -> str:
    return dependency_state_badge(state) + " " + dependency_evidence_badge(evidence)


def dependency_health_table(rows: list[dict[str, Any]]) -> str:
    cells = []
    for row in rows:
        cells.append(
            "<tr>"
            f'<th scope="row">{html.escape(str(row["domain"]))}</th>'
            f'<td>{html.escape(str(row["dependency"]))}</td>'
            f'<td>{dependency_state_badge(row["state"])}</td>'
            f'<td>{dependency_evidence_badge(row["evidence_authority"])}</td>'
            f'<td>{"Yes" if row["blocking"] else "No"}</td>'
            f'<td>{html.escape(str(row["root_cause"]))}</td>'
            "</tr>"
        )
    return (
        '<div class="pl-wide-data" role="region" aria-label="Dependency health details" tabindex="0">'
        '<table><caption>Dependency state and evidence authority by domain</caption>'
        '<thead><tr><th scope="col">Domain</th><th scope="col">Dependency</th>'
        '<th scope="col">State</th><th scope="col">Evidence authority</th><th scope="col">Blocking</th><th scope="col">Evidence note</th>'
        "</tr></thead><tbody>" + "".join(cells) + "</tbody></table></div>"
    )


def dependency_domain_cards(rows: list[dict[str, Any]]) -> str:
    cards = []
    for domain in sorted({str(row["domain"]) for row in rows}):
        dependencies = [row for row in rows if str(row["domain"]) == domain]
        states = Counter(str(row["state"]) for row in dependencies)
        evidence = Counter(str(row["evidence_authority"]) for row in dependencies)
        cards.append(
            '<article class="pl-kpi">'
            f'<h3>{html.escape(domain)}</h3>'
            '<dl>'
            f'<div><dt>Dependencies</dt><dd>{len(dependencies)}</dd></div>'
            f'<div><dt>Healthy</dt><dd>{states["healthy"]}</dd></div>'
            f'<div><dt>Unvalidated</dt><dd>{states["unvalidated"]}</dd></div>'
            f'<div><dt>Runtime verified</dt><dd>{evidence["verified-runtime-baseline"]}</dd></div>'
            f'<div><dt>Source derived</dt><dd>{evidence["source-derived"]}</dd></div>'
            '</dl></article>'
        )
    return '<section class="pl-kpi-grid" aria-label="Domain dependency summaries">' + "".join(cards) + "</section>"


def dep_dot(rows: list[dict[str, Any]], production: bool) -> str:
    states = {"healthy":"#2e7d32","degraded":"#b26a00","unavailable":"#b3261e","unvalidated":"#626262","stale":"#8a6d00"}
    lines = ["digraph dependency_health {", '  graph [rankdir="LR", bgcolor="transparent", fontname="sans-serif"];', '  node [shape="box", style="rounded,filled", fontname="sans-serif", fillcolor="#f5f7fa"];', '  edge [fontname="sans-serif", color="#667085"];']
    by_domain: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows: by_domain[str(row["domain"])].append(row)
    for idx, (domain, deps) in enumerate(sorted(by_domain.items())):
        did = f"d{idx}"
        lines.append(f'  {did} [label="{domain}", shape="folder", fillcolor="#e8eefc"];')
        selected = deps if not production else [d for d in deps if d["blocking"] or d["state"] != "healthy"]
        for j, dep in enumerate(selected):
            nid = f"{did}n{j}"
            state = dep["state"]
            marker = "● verified runtime" if dep["evidence_authority"] == "verified-runtime-baseline" else "◇ source-derived"
            label = f"{dep['dependency']}\\n{state}" + ("" if production else f"\\n{marker}")
            lines.append(f'  {nid} [label="{label}", color="{states.get(state, states["unvalidated"])}"];')
            style = "bold" if dep["blocking"] else "solid"
            lines.append(f'  {did} -> {nid} [style="{style}"];')
    lines.append("}")
    return "\n".join(lines) + "\n"


def render_dependency_svg(rows: list[dict[str, Any]], production: bool) -> str:
    """Render dependency health without depending on local Graphviz SVG serialization.

    DOT remains generated as a review/debug artifact, but the committed SVG uses fixed
    geometry and ordering so WSL2/CI Graphviz version differences cannot create drift.
    """
    by_domain: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_domain[str(row["domain"])].append(row)

    domain_rows: list[tuple[str, list[dict[str, Any]]]] = []
    for domain, deps in sorted(by_domain.items()):
        selected = sorted(
            deps if not production else [d for d in deps if d["blocking"] or d["state"] != "healthy"],
            key=lambda d: (str(d["dependency"]), str(d["state"]), str(d["evidence_authority"])),
        )
        domain_rows.append((domain, selected))

    row_height = 44
    group_gap = 26
    top = 64
    left = 28
    domain_width = 250
    dep_x = 350
    dep_width = 470 if production else 680
    width = dep_x + dep_width + 36
    height = top + 30
    for _, deps in domain_rows:
        height += max(1, len(deps)) * row_height + group_gap

    state_colors = {
        "healthy": "#2e7d32",
        "degraded": "#b26a00",
        "unavailable": "#b3261e",
        "unvalidated": "#626262",
        "stale": "#8a6d00",
    }

    def esc(value: Any) -> str:
        return html.escape(str(value), quote=True)

    out = [
        '<?xml version="1.0" encoding="UTF-8" standalone="no"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        '  <title id="title">Pocket Lab Lite dependency health</title>',
        '  <desc id="desc">Deterministic dependency-health projection derived from canonical documentation intelligence.</desc>',
        '  <style>.t{font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;fill:#101828}.s{font-size:13px}.h{font-size:16px;font-weight:700}.d{fill:#eef3ff;stroke:#9db2e2}.n{fill:#f8fafc;stroke-width:2}.e{stroke:#98a2b3;stroke-width:1.5}.b{stroke-width:2.5}</style>',
        f'  <text class="t h" x="{left}" y="32">Dependency health — {"Production" if production else "Development"}</text>',
    ]
    y = top
    for domain, deps in domain_rows:
        block_height = max(1, len(deps)) * row_height
        domain_y = y + max(0, (block_height - 34) // 2)
        out.append(f'  <rect class="d" x="{left}" y="{domain_y}" width="{domain_width}" height="34" rx="8"/>')
        out.append(f'  <text class="t h" x="{left + 12}" y="{domain_y + 22}">{esc(domain)}</text>')
        if not deps:
            out.append(f'  <line class="e" x1="{left + domain_width}" y1="{domain_y + 17}" x2="{dep_x}" y2="{y + 17}"/>')
            out.append(f'  <rect class="n" x="{dep_x}" y="{y}" width="{dep_width}" height="34" rx="8" stroke="{state_colors["unvalidated"]}"/>')
            out.append(f'  <text class="t s" x="{dep_x + 12}" y="{y + 22}">No production-significant dependency rows</text>')
        for idx, dep in enumerate(deps):
            ny = y + idx * row_height
            state = str(dep["state"])
            color = state_colors.get(state, state_colors["unvalidated"] )
            edge_class = "e b" if dep["blocking"] else "e"
            out.append(f'  <line class="{edge_class}" x1="{left + domain_width}" y1="{domain_y + 17}" x2="{dep_x}" y2="{ny + 17}"/>')
            out.append(f'  <rect class="n" x="{dep_x}" y="{ny}" width="{dep_width}" height="34" rx="8" stroke="{color}"/>')
            detail = f'{dep["dependency"]} — {state}'
            if not production:
                marker = "● verified runtime" if dep["evidence_authority"] == "verified-runtime-baseline" else "◇ source-derived"
                detail += f" — {marker}"
            out.append(f'  <text class="t s" x="{dep_x + 12}" y="{ny + 22}">{esc(detail)}</text>')
        y += block_height + group_gap
    out.append('</svg>')
    return "\n".join(out) + "\n"


def threat_model() -> dict[str, Any]:
    health = read_json(OP_HEALTH, {}) or {}
    domains = {x.get("id"): x for x in health.get("domains", []) if isinstance(x, dict)}
    controls = [
        {"id":"CTRL-BROWSER-NATS","description":"Frontend does not connect directly to NATS.","implementation":["src/","pocket-lab-final-structure/runtime/api_fastapi/"],"status":"mitigation-source-derived"},
        {"id":"CTRL-BROWSER-SHELL","description":"Frontend does not execute shell commands.","implementation":["src/","pocket-lab-final-structure/runtime/api_fastapi/"],"status":"mitigation-source-derived"},
        {"id":"CTRL-API-CONTROL","description":"FastAPI remains the frontend-facing control API.","implementation":["pocket-lab-final-structure/runtime/api_fastapi/"],"status":"mitigation-source-derived"},
        {"id":"CTRL-EXECUTION-OWNERS","description":"Workers, agents and supervisors own execution and recovery.","implementation":["pocket-lab-final-structure/runtime/workers/","pocket-lab-final-structure/runtime/agents/"],"status":"mitigation-source-derived"},
        {"id":"CTRL-EVIDENCE-SANITIZE","description":"Generated/runtime evidence is sanitized before documentation use.","implementation":["scripts/docs/runtime/","scripts/test/parity/"],"status":"control-observed" if health else "control-unvalidated"},
        {"id":"CTRL-PROMOTION","description":"Runtime evidence promotion is explicit and separate from MkDocs generation.","implementation":["scripts/docs/runtime/promote_termux_runtime.py"],"status":"control-observed" if RUNTIME.exists() else "control-unvalidated"},
    ]
    boundaries = []
    threats = []
    for bid, label in BOUNDARIES:
        runtime_status = "control-unvalidated"
        if bid in {"messaging-execution","managed-device","private-network","server-host"} and domains:
            runtime_status = "control-partial"
        boundary = {
            "id": bid, "label": label,
            "assets": ["control-plane state", "identity/evidence metadata"],
            "actors": ["user", "Pocket Lab service", "joined device"],
            "entry_points": ["repository-defined API/event/runtime flow"],
            "allowed_flows": ["UI → Caddy → FastAPI → NATS/worker/agent → evidence → FastAPI → UI"],
            "forbidden_flows": ["frontend → NATS", "frontend → shell", "documentation generator → live runtime capture"],
            "data_classifications": ["sanitized operational metadata", "restricted identity metadata where applicable"],
            "secrets_handled": "not rendered; boundary may handle secrets only in runtime-owned paths",
            "trust_assumptions": ["canonical contracts are reviewed", "promoted runtime evidence is sanitized"],
            "runtime_evidence_status": runtime_status,
            "review_status": "human-review-required",
        }
        boundaries.append(boundary)
        for stride in STRIDE:
            tid = f"THR-{bid.upper()}-{stride.split()[0].upper()}"
            threats.append({
                "id": tid, "boundary": bid, "stride": stride,
                "scenario": f"Candidate {stride} threat at the {label}.",
                "controls": [x["id"] for x in controls if (bid == "browser" and x["id"].startswith("CTRL-BROWSER")) or x["id"] in {"CTRL-API-CONTROL","CTRL-EVIDENCE-SANITIZE"}],
                "runtime_evidence": ["contracts/generated/runtime/domain-operational-health.json", "contracts/parity/runtime-verification-baseline.json"],
                "residual_risk": "unvalidated until human threat review",
                "review_status": "candidate-human-review-required",
            })
    return {
        "schema_version":"1.0.0", "generator":str(GENERATOR.relative_to(ROOT)),
        "source_commit":source_commit(), "posture":"current-promoted-threat-posture",
        "posture_rule":"derived from canonical source and promoted sanitized evidence; no live monitoring",
        "boundaries":boundaries, "threats":threats, "controls":controls,
        "human_review_required":["threat relevance","mitigation adequacy","residual risk","risk acceptance","exceptions"],
    }


def release_evidence() -> dict[str, Any]:
    releases = read_json(RELEASES, {}) or {}
    inv = releases.get("release_inventory", {})
    verified = inv.get("releases", []) if isinstance(inv, dict) else []
    hashes = {}
    for name, path in {"openapi":OPENAPI,"asyncapi":ASYNCAPI,"architecture":ARCH,"operational_health":OP_HEALTH,"documentation_intelligence":INTELLIGENCE}.items():
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
    return {
        "status":"verified-release-evidence-present" if verified else "no-verified-release-manifest-present",
        "source_commit":source_commit(), "tree_hash":tree_hash(),
        "verified_releases":verified,
        "artifacts":{"dist.zip":"unvalidated","github_asset_presence":"unvalidated","signatures":"unvalidated","provenance":"SLSA-style metadata not yet observed"},
        "fingerprints":hashes,
        "runtime_baseline_binding": (read_json(RUNTIME,{}) or {}).get("release") or (read_json(RUNTIME,{}) or {}).get("release_tag") or "unvalidated",
        "sbom_digest":"unvalidated", "security_scan_digest":"unvalidated",
    }


def release_delta(release: dict[str, Any]) -> dict[str, Any]:
    # Fail closed: only compare when repository release inventory contains two verified canonical manifests.
    verified = release.get("verified_releases", [])
    dimensions = ["git-source","openapi","asyncapi-events","sqlite-schema-migrations","architecture","trust-boundaries","capabilities","operational-health","runtime-topology","semantic-parity","platform-capability-evidence","reason-codes","task-inventory","security-controls","threat-model","sbom","dependency-versions","vulnerabilities","licenses","release-artifacts","documentation-coverage","validation-coverage"]
    if len(verified) < 2:
        return {"status":"no-comparable-verified-prior-release","classifications":["not-comparable","unknown"],"dimensions":[{"dimension":d,"status":"not-comparable"} for d in dimensions]}
    return {"status":"comparable","classifications":["added","removed","changed","breaking","non-breaking","improved","degraded","newly-observed","no-longer-observed","evidence-stale","new-vulnerability","resolved-vulnerability","new-license","dependency-added","dependency-removed","dependency-updated","architecture-drift","not-comparable","unknown"],"dimensions":[{"dimension":d,"status":"unknown"} for d in dimensions]}


def supply_chain() -> dict[str, Any]:
    tools = read_json(TOOLS, {}) or {}
    manifests = []
    for p in [ROOT/"package-lock.json", ROOT/"package.json", ROOT/"requirements-dev.txt", ROOT/"requirements-docs.txt", ROOT/"pocket-lab-final-structure/runtime/requirements.txt"]:
        if p.exists(): manifests.append({"path":str(p.relative_to(ROOT)),"sha256":hashlib.sha256(p.read_bytes()).hexdigest()})
    normalized_dir = ROOT / "contracts/generated/supply-chain"
    observed = sorted(str(p.relative_to(ROOT)) for p in normalized_dir.glob("*.json")) if normalized_dir.exists() else []
    return {
        "status":"normalized-evidence-present" if observed else "source-inventory-only-unvalidated-by-heavy-tools",
        "manifests":manifests,
        "normalized_artifacts":observed,
        "tools":tools.get("tools",[]),
        "existing_checker":"scripts/dev/check-supply-chain.sh",
        "normalization_flow":["transient .pocketlab-dev evidence","Pocket Lab normalizer","redacted canonical contract","optional explicit promotion","Documentation Intelligence"],
        "termux_policy":"bounded existing runtime evidence only; no whole-filesystem SBOM or heavy scanning from docs generation",
    }


def config_inventory() -> list[dict[str, Any]]:
    pattern = re.compile(r"\b(?:POCKETLAB|LITE|NATS|TAILSCALE)_[A-Z0-9_]+\b")
    # Configuration intelligence must be derived from tracked/source-oriented inputs only.
    # Never let workstation-local virtualenvs, generated output, caches or build artifacts
    # change the generated contract.
    excluded_parts = {
        ".git", ".venv", "venv", "node_modules", "dist", "pwa_dist", "site",
        ".pocketlab-dev", ".pytest_cache", "__pycache__", "playwright-report",
        "test-results", "allure-results", "allure-report", "coverage",
    }
    excluded_prefixes = {
        ("contracts", "generated"),
        ("docs", "generated"),
    }
    suffixes = {".py", ".sh", ".js", ".jsx", ".ts", ".tsx", ".yml", ".yaml"}
    files = []
    for p in ROOT.rglob("*"):
        if not p.is_file() or p.suffix not in suffixes:
            continue
        rel = p.relative_to(ROOT)
        if any(part in excluded_parts for part in rel.parts):
            continue
        if any(rel.parts[: len(prefix)] == prefix for prefix in excluded_prefixes):
            continue
        files.append(p)
    files.sort(key=lambda p: str(p.relative_to(ROOT)))
    seen: dict[str, set[str]] = defaultdict(set)
    for p in files:
        try: text=p.read_text(encoding="utf-8",errors="ignore")
        except OSError: continue
        for name in pattern.findall(text): seen[name].add(str(p.relative_to(ROOT)))
    out=[]
    for name,sources in sorted(seen.items()):
        secret=any(x in name for x in ["TOKEN","PASSWORD","SECRET","KEY","CREDENTIAL"])
        out.append({"name":name,"purpose":"source-discovered configuration key; canonical purpose requires owner review","owner":"source-defined component","source":sorted(sources)[:6],"default":"redacted/not inferred" if secret else "source-defined/unvalidated","required":"unvalidated","secret":secret,"runtime_scope":"runtime or development depending on source","restart_required":"unvalidated","affects_release":"unvalidated","affects_runtime":True,"validation":"source presence only","related_troubleshooting":[]})
    return out


def knowledge_entities(kind: str) -> list[dict[str, Any]]:
    kb = read_json(KNOWLEDGE,{}) or {}
    return [e for e in kb.get("entities",[]) if e.get("type") == kind or e.get("kind") == kind]


def trace_explorer() -> list[dict[str, Any]]:
    actions = ["Add Device","Restart Agent","Install App","Open App","Run Security Check","Back Up","Preview Restore","Restore","Remove Old Device"]
    openapi = read_json(OPENAPI,{}) or {}
    paths = list((openapi.get("paths") or {}).keys())
    keymap = {"Add Device":["invite","fleet"],"Restart Agent":["restart"],"Install App":["install"],"Open App":["catalog"],"Run Security Check":["security"],"Back Up":["backup"],"Preview Restore":["preview"],"Restore":["restore"],"Remove Old Device":["remove","retire"]}
    out=[]
    for action in actions:
        matches=[p for p in paths if any(k in p.lower() for k in keymap[action])][:8]
        out.append({"action":action,"ui_owner":"React/Vite Lite UI","api":matches or ["unvalidated"],"handler_owner":"FastAPI","execution_owner":"worker/agent/supervisor where applicable","event":"canonical AsyncAPI lookup required","evidence":"backend/runtime projection","tests":"knowledge/test ownership graph","failure_states":"reason-code registry / API semantics"})
    return out


def troubleshooting() -> list[dict[str, Any]]:
    scenarios=[
      ("API unavailable","Lite API cannot be reached","FastAPI/Caddy/NATS dependency issue"),("NATS unavailable","write paths cannot deliver commands","NATS/JetStream unavailable"),("JetStream problem","durable command/event flow degrades","JetStream consumer/storage issue"),("agent offline","device appears Offline","heartbeat/NATS/Tailscale interruption"),("agent stopped","device reports Agent stopped","PM2 process stopped"),("supervisor absent","automatic agent recovery unavailable","supervisor process absent"),("Tailscale unavailable","Remote access not ready","tailscaled/Tailnet readiness issue"),("PhotoPrism unavailable","app route does not open","app runtime/Caddy route issue"),("backup stale","latest backup evidence is old","backup schedule or execution issue"),("restore blocked","restore cannot proceed","preview/checkpoint/health guard not satisfied"),("security scan stuck","Safety Check does not advance","worker/consumer/scanner problem"),("Caddy routing issue","same-origin route fails","Caddy config/runtime issue"),("release mismatch","installed/runtime release identities differ","release binding not converged"),("runtime evidence stale","docs show old promoted observation","new capture has not been explicitly promoted"),("docs generation drift","lite:docs:check reports drift","generated artifacts are out of sync"),("parity mismatch","semantic/runtime parity differs","backend/frontend/runtime contract divergence")]
    checks=[{"command":cmd,"class":cls} for cmd,cls in SAFE_COMMANDS.items()]
    return [{"scenario":name,"symptom":symptom,"interpretation":cause,"likely_causes":[cause],"safe_checks":checks,"expected_result":"compare command output to canonical readiness/health contracts","next_diagnostic_step":"follow the related generated runbook and preserve sanitized evidence","repair_options":"only canonical SAFE_REPAIR procedures; none inferred here","verification":"rerun read-only health and relevant documentation/parity checks","rollback":"use release/recovery runbook when a prior change caused the issue","do_not_do":["do not bypass FastAPI/NATS ownership","do not overwrite device identity","do not expose secrets"],"evidence_to_preserve":["sanitized API status","PM2 status","promoted runtime comparison"],"related_runbook":"generated/production/incident-runbooks.md"} for name,symptom,cause in scenarios]


def privacy_map() -> list[dict[str, Any]]:
    categories=["SQLite","NATS messages","device identity","runtime evidence","logs","audit events","backup metadata","security scan results","app metadata","release evidence"]
    return [{"category":c,"source":"canonical runtime/control-plane component","storage":"source-derived; see SQLite/data-lineage/runtime contracts","retention":"canonical policy or unvalidated","sanitization":"required before Documentation Platform ingestion","access":"FastAPI/backend-owned; UI receives bounded safe projection","network_exposure":"private same-origin/Tailnet path where applicable","backup_behavior":"policy-dependent","deletion_behavior":"explicit lifecycle/retention policy","privacy_risk":"restricted operational metadata; human review for sensitive fields","controls":["redaction","backend ownership","explicit runtime promotion"]} for c in categories]


def fmea(deps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen=set(); out=[]
    for d in deps:
        key=(d["domain"],d["dependency"])
        if key in seen: continue
        seen.add(key)
        severity="high" if d["blocking"] else "moderate"
        out.append({"component":d["dependency"],"failure_mode":f"{d['dependency']} unavailable or stale","detection":d["evidence_authority"],"user_impact":f"{d['domain']} may degrade or become unavailable","automatic_recovery":"supervisor/reconnect/retry only where canonical runtime owns it","manual_recovery":"use generated incident runbook","evidence":d["root_cause"],"severity":severity,"residual_risk":"unknown until scenario-specific review"})
    return out


def reliability_objectives() -> list[dict[str, Any]]:
    return [
      {"objective":"heartbeat freshness","target":"canonical fleet freshness threshold","latest_promoted_observation":"derived from promoted runtime when available","status":"unknown"},
      {"objective":"API availability expectations","target":"health/readiness endpoints available during normal operation","latest_promoted_observation":"promoted runtime topology only","status":"unknown"},
      {"objective":"command delivery latency","target":"bounded by command lifecycle contracts","latest_promoted_observation":"not modeled as live metric","status":"unknown"},
      {"objective":"supervisor recovery time","target":"bounded recovery semantics","latest_promoted_observation":"promoted supervisor state where available","status":"unknown"},
      {"objective":"runtime evidence freshness","target":"explicit freshness policy","latest_promoted_observation":"release-bound promoted baseline","status":"degraded" if (read_json(OP_HEALTH,{}) or {}).get("status") == "degraded" else "unknown"},
      {"objective":"documentation determinism","target":"zero generated drift under check mode","latest_promoted_observation":"repository validation only; not live monitoring","status":"unknown"},
    ]


def quality_scorecard() -> list[dict[str, Any]]:
    domains=["home","apps","devices","security","recovery","identity","rules"]
    return [{"domain":d,"architecture_documented":"complete","api_documented":"complete" if d not in {"identity","rules"} else "partial","events_documented":"partial","runbook_present":"partial","threat_model_present":"complete","operational_health_modeled":"complete","evidence_coverage":"partial","troubleshooting":"complete","release_impact":"partial","ownership":"partial","privacy_map":"complete"} for d in domains]


def search_synonyms() -> list[dict[str, Any]]:
    declared=(read_json(EXPERIENCE,{}) or {}).get("search_synonyms",{})
    defaults={
      "device offline":["node disconnected","agent unreachable","fleet problem"],
      "remote access not ready":["tailscale unavailable","tailnet problem"],
      "security check stuck":["scan stuck","worker safety check"],
      "backup stale":["old backup","recovery freshness"],
      "release mismatch":["runtime release drift","installed release mismatch"],
    }
    if isinstance(declared,dict):
        for k,v in declared.items(): defaults[str(k)]=list(v) if isinstance(v,list) else [str(v)]
    destinations={
      "device offline":["/generated/production/devices/","/generated/production/intelligence/fleet-readiness/","/generated/production/troubleshooting/"],
      "remote access not ready":["/generated/production/remote-access/","/generated/production/troubleshooting/"],
      "security check stuck":["/generated/production/security/","/generated/production/troubleshooting/"],
      "backup stale":["/generated/production/recovery/","/generated/production/intelligence/recovery-readiness/"],
      "release mismatch":["/generated/production/release/","/generated/production/intelligence/what-changed/"],
      "devices":["/generated/production/devices/","/generated/production/intelligence/fleet-readiness/"],
      "remote-access":["/generated/production/remote-access/"],
      "security":["/generated/production/security/"],
      "recovery":["/generated/production/recovery/","/generated/production/intelligence/recovery-readiness/"],
      "operational-health":["/generated/production/intelligence/current-health/","/generated/development/knowledge/operational-health/"],
      "release-impact":["/generated/production/intelligence/what-changed/"],
      "add device":["/generated/production/devices/"],
      "backup restore":["/generated/production/recovery/"],
      "app install":["/generated/production/apps/"],
      "api frontend":["/generated/development/frontend-api-usage/","/generated/enterprise/reference/api-ui-trace/"],
      "event nats":["/generated/enterprise/engineering/events/","/generated/development/lite-events/"],
      "why do we believe this":["/generated/production/intelligence/why-we-believe-this/"],
      "documentation generator":["/generated/enterprise/documentation-platform/generation-pipeline/"],
      "release changed":["/generated/production/intelligence/what-changed/"],
    }
    return [{"canonical":k,"synonyms":sorted(set(v)),"destinations":destinations.get(k,[])} for k,v in sorted(defaults.items())]


def threat_dragon_export(model: dict[str, Any]) -> dict[str, Any]:
    # Derived visualization/export only. Canonical risk decisions stay in contracts/security/threat-model.json.
    return {
        "schema_version": "1.0.0",
        "source": "contracts/security/threat-model.json",
        "canonical_source": False,
        "review_note": "Derived Threat Dragon-compatible review projection; residual risk and acceptance remain human-reviewed in canonical Pocket Lab metadata.",
        "boundaries": [{"id": b["id"], "name": b["label"]} for b in model["boundaries"]],
        "threats": [{"id": t["id"], "boundary": t["boundary"], "category": t["stride"], "title": t["scenario"], "status": t["review_status"]} for t in model["threats"]],
    }


def build() -> tuple[dict[Path,str], dict[str,Any]]:
    fps, fp = fingerprint()
    tasks=task_inventory(); events=event_inventory(); deps=dependency_rows(); threat=threat_model(); release=release_evidence(); delta=release_delta(release); supply=supply_chain(); config=config_inventory(); traces=trace_explorer(); trouble=troubleshooting(); privacy=privacy_map(); fm=fmea(deps); slo=reliability_objectives(); quality=quality_scorecard(); synonyms=search_synonyms()
    controls=threat["controls"]
    ownership=[{"capability":"Device execution","source_owner":"node agent","runtime_owner":"node agent","recovery_owner":"supervisor","control_owner":"FastAPI","presentation_owner":"Devices UI","evidence_owner":"fleet/runtime projection"},{"capability":"Security scan","source_owner":"security policy","runtime_owner":"worker/scanner adapters","recovery_owner":"worker/supervisor","control_owner":"FastAPI","presentation_owner":"Security UI","evidence_owner":"Security projection"},{"capability":"Documentation Platform","source_owner":"repository metadata/generators","runtime_owner":"none","recovery_owner":"developer/CI","control_owner":"documentation generators","presentation_owner":"MkDocs","evidence_owner":"canonical/promoted contracts"}]
    validation={"status":"repository-evidence-only","checks":[{"name":x,"status":"unvalidated-in-current-generator"} for x in ["backend tests","parity","Playwright","accessibility","OpenAPI","Schemathesis","oasdiff","architecture drift","knowledge determinism","runtime evidence","SBOM","vulnerability analysis","secret scanning","static analysis","documentation strict build"]],"rule":"never poll CI; consume recorded canonical evidence only"}
    change_advisor={"rules":[{"path_prefix":"pocket-lab-final-structure/runtime/api_fastapi/","impacts":["OpenAPI","Schemathesis","parity","frontend API usage","reason codes","documentation","release compatibility"],"recommended_tasks":["lite:contracts:check","lite:docs:check","lite:check"]},{"path_prefix":"src/","impacts":["frontend build","Playwright","accessibility","API usage","documentation"],"recommended_tasks":["lite:test:frontend","lite:test:e2e:mocked","lite:test:a11y","lite:docs:check"]},{"path_prefix":"scripts/docs/","impacts":["generated docs","determinism","MkDocs strict build"],"recommended_tasks":["lite:docs:sync","lite:docs:check"]}],"executes_changes":False}
    upgrade={"status":"no-comparable-verified-prior-release" if delta["status"] != "comparable" else "derived","from_release":"unvalidated","to_release":"current source","database_migrations":"derive from migration inventory","agent_compatibility":"unvalidated","runtime_changes":"compare promoted baselines only","backup_requirement":"follow release/recovery policy","breaking_api_changes":"use oasdiff recorded evidence","config_changes":"use configuration delta","rollback":"use release rollback contract","known_risks":"known limitations catalog"}
    supply_change={"status":"no-comparable-verified-prior-release" if delta["status"] != "comparable" else "derived-from-normalized-sboms","dependencies_added":[],"dependencies_removed":[],"versions_changed":[],"new_vulnerabilities":[],"resolved_vulnerabilities":[],"new_licenses":[],"license_classification_changes":[],"upstream_posture_changes":[],"rule":"never compare raw scanner output; compare normalized canonical release evidence only"}
    disaster=[{"scenario":s,"survives":"canonical durable state and external backups where available","lost":"unreplicated local state may be lost","recoverable":"depends on verified backup/release/runtime evidence","dependency_order":["control API/state","NATS/worker","agent/supervisor","remote access","apps"],"required_evidence":["release identity","backup verification","runtime health"],"verification":"domain health + parity + app/device readiness"} for s in ["server phone lost","secondary device lost","SQLite corrupted","NATS unavailable","Tailscale unavailable","PhotoPrism unavailable","bad release","failed update"]]
    adr_payload=read_json(ADRS,{}) or {}
    adr={"status":"source-derived","entities":adr_payload.get("items",[]) or knowledge_entities("adr") or knowledge_entities("decision"),"relationship_model":"knowledge graph relations; no live state"}
    items={"dependency_health":deps,"release_delta":delta,"release_evidence":release,"search_synonyms":synonyms,"tasks":tasks,"task_workflows":task_workflows(tasks),"events":events,"threat_model":threat,"supply_chain":supply,"configuration":config,"api_ui_traces":traces,"troubleshooting":trouble,"privacy_map":privacy,"fmea":fm,"reliability_objectives":slo,"adr_intelligence":adr,"security_controls":controls,"change_advisor":change_advisor,"ownership":ownership,"validation_coverage":validation,"upgrade_migration":upgrade,"disaster_recovery":disaster,"documentation_quality":quality,"supply_chain_change":supply_change,"provenance":{"status":"SLSA-style provenance metadata only","source_commit":source_commit(),"tree_hash":tree_hash(),"artifact_signature":"unvalidated","formal_slsa_level":"not-claimed"}}
    index={"schema_version":"1.0.0","generator":str(GENERATOR.relative_to(ROOT)),"source_commit":source_commit(),"source_fingerprint":fp,"items":items}
    threat["source_fingerprint"]=fp
    jsonschema.validate(index, read_json(SCHEMA,{}))
    outputs: dict[Path,str]={INDEX:stable(index),THREAT_MODEL:stable(threat),OUT/"threat-dragon-export.json":stable(threat_dragon_export(threat)),OUT/"search-synonyms.json":stable({"schema_version":"1.0.0","items":synonyms}),OUT/"release-delta.json":stable(delta),OUT/"release-evidence.json":stable(release),OUT/"supply-chain.json":stable(supply),OUT/"validation-coverage.json":stable(validation),OUT/"documentation-quality.json":stable({"items":quality}),OUT/"supply-chain-change.json":stable(supply_change)}
    devdot=dep_dot(deps,False); proddot=dep_dot(deps,True)
    outputs[DIAGRAMS/"dependency-health-development.dot"]=devdot; outputs[DIAGRAMS/"dependency-health-production.dot"]=proddot; outputs[DIAGRAMS/"dependency-health-development.svg"]=render_dependency_svg(deps,False); outputs[DIAGRAMS/"dependency-health-production.svg"]=render_dependency_svg(deps,True)

    def doc_page(title:str, desc:str, audience:str, body:str, page_type:str="reference") -> str: return frontmatter(title,desc,audience,page_type)+body.strip()+"\n"
    task_rows=[[x["name"],x["purpose"],", ".join(x["dependencies"]) or "—", "yes" if x["captures_runtime"] else "no", "yes" if x["promotes_evidence"] else "no", "WSL2/CI" if x["requires_wsl2_or_ci"] else ("Termux" if x["requires_termux"] else "local"), x["runtime_class"]] for x in tasks]
    # Documentation Platform system-manual pages are owned by documentation_ia.py.
    # The enterprise generator merges that deterministic IA projection after completion.
    dep_summary = Counter(str(x.get("state") or "unvalidated") for x in deps)
    dep_body = '# Dependency Health\n\n<section class="pl-page-lede" aria-labelledby="dependency-health-basis"><p class="pl-eyebrow">Release-bound evidence</p><h2 id="dependency-health-basis">Trace degradation without overstating runtime proof</h2><p>Domain health and child dependency evidence stay independent. A source-derived dependency is documented from canonical architecture or metadata; it is not a runtime verification claim. Aggregate Identity &amp; Access and Rules health remains unvalidated while their promoted implementation coverage is partial.</p></section>\n\n'
    dep_body += '<div class="pl-kpi-grid">' + ''.join(f'<div class="pl-kpi"><span>{html.escape(state.replace("-", " ").title())}</span><strong>{count}</strong><small>dependency observations</small></div>' for state, count in sorted(dep_summary.items())) + '</div>\n\n'
    dep_body += '<figure class="pl-generated-diagram pl-generated-diagram--contained"><img src="../../../assets/enterprise/dependency-health-development.svg" alt="Detailed dependency health with source-derived and runtime-verified evidence markers" loading="lazy"><figcaption>● verified runtime evidence; ◇ source-derived dependency evidence. State remains visible as text and symbol, not color alone.</figcaption></figure>\n\n'
    dep_body += dependency_domain_cards(deps) + '\n\n'
    dep_body += dependency_health_table(deps) + '\n'
    outputs[DOC/"reference/dependency-health.md"]=doc_page("Dependency Health","Graphviz dependency-health visualization derived from canonical metadata and promoted evidence.","development",dep_body)

    # Page-type documentation is generated by documentation_ia.py from one canonical taxonomy.

    task_details=[]
    for t in tasks:
        task_details.append(
            f"<details><summary><code>{t['name']}</code> — {html.escape(str(t['purpose']))}</summary>\n\n"
            f"- **Source:** `{t['source']}`\n"
            f"- **Dependencies:** {', '.join(t['dependencies']) or 'none declared'}\n"
            f"- **Commands:** {', '.join(f'`{c}`' for c in t['commands']) or 'none declared'}\n"
            f"- **Inputs:** task variables/environment are source-defined; values are not inferred or printed\n"
            f"- **Outputs:** derived from command semantics only when canonical; otherwise review task source\n"
            f"- **Side effects:** repository mutation={'yes' if t['repository_mutation'] else 'no detected'}; runtime mutation={'yes' if t['runtime_mutation'] else 'no detected'}\n"
            f"- **Runtime evidence:** captures={'yes' if t['captures_runtime'] else 'no'}; promotes={'yes' if t['promotes_evidence'] else 'no'}\n"
            f"- **Environment:** {'WSL2/CI' if t['requires_wsl2_or_ci'] else ('Termux/runtime host' if t['requires_termux'] else 'repository development environment')}\n"
            f"- **Safe locally by default:** {'yes' if t['safe_local_default'] else 'no — review before execution'}\n"
            f"- **Expected runtime class:** {t['runtime_class']}\n"
            f"- **Failure mode:** non-zero command/task exit; preserve validation output\n"
            f"- **Example:** `task {t['name']}`\n\n</details>"
        )
    outputs[DOC/"engineering/task-reference.md"]=doc_page("Task Reference — Engineering Handbook","Executable engineering handbook generated from Taskfiles without inventing semantics.","development","# Task Reference\n\n## Workflow groups\n\n"+"\n".join(f"### {k}\n\n"+"\n".join(f"- `{n}`" for n in v) for k,v in task_workflows(tasks).items())+"\n\n## Tasks\n\n"+table(["Task","Purpose","Dependencies","Captures runtime","Promotes evidence","Surface","Runtime class"],task_rows)+"\n## Task details\n\n"+"\n\n".join(task_details))
    outputs[DOC/"engineering/contribution-review.md"]=doc_page("Contribution & Review","Developer onboarding and review guardrails.","development","# Contribution & Review\n\n## Before coding\n\nPreserve React/Vite → Caddy → FastAPI → NATS/JetStream → worker/agent/supervisor boundaries. Inspect canonical contracts and ownership before changing code.\n\n## During implementation\n\nKeep execution backend-owned, evidence sanitized, runtime promotion explicit, and generated documentation deterministic.\n\n## Testing and evidence\n\nUse the change advisor to select focused tests, then run the normal validation gates. Never record a PASS without output.\n\n## Change types\n\n"+table(["Change type","Likely review focus"],[[x,y] for x,y in [("Backend API","OpenAPI, parity, reason codes, frontend usage"),("Frontend","FastAPI ownership, accessibility, Playwright"),("SQLite migration","durable semantics, migration tests, rollback"),("NATS/event","AsyncAPI, durability, idempotency, consumer behavior"),("Worker/agent/supervisor","execution ownership, recovery, sanitized evidence"),("Security scanner","bounded profiles, redaction, Termux cost"),("Device bootstrap","identity fail-closed behavior, no secret exposure"),("Tailscale","readiness truth, no hardcoded addresses"),("Application integration","Caddy same-origin route, worker lifecycle"),("Documentation generator","determinism, no live runtime"),("Release workflow","dist.zip, checksums, binding, rollback")]]))
    event_details=[]
    for e in events:
        event_details.append(f"## `{e['subject']}`\n\n- **Domain:** {e['domain']}\n- **Publisher:** {e['publisher']}\n- **Consumers:** {', '.join(e['consumers'])}\n- **Schema/messages:** {', '.join(e['messages']) or 'unvalidated'}\n- **Durability:** {e['durability']}\n- **Replay/ordering:** {e['ordering']}\n- **Idempotency:** {e['idempotency']}\n- **Acknowledgment:** {e['acknowledgment']}\n- **Failure handling:** {e['failure_handling']}\n- **Audit implications:** {e['audit_implications']}\n- **Related API/reason/UI/tests:** derive through API/UI, reason-code and test ownership indexes; no relationship is invented here\n- **Sanitized example payload:** omitted unless a canonical fixture exists\n- **Source/runtime owner:** {e['source_owner']} / runtime consumer ownership\n")
    outputs[DOC/"engineering/events.md"]=doc_page("Event Encyclopedia","Canonical event subjects and lifecycle expectations.","development","# Event Encyclopedia\n\n"+table(["Subject","Domain","Messages","Durability","Idempotency","Failure handling"],[[x["subject"],x["domain"],x["messages"],x["durability"],x["idempotency"],x["failure_handling"]] for x in events])+"\n"+"\n".join(event_details))
    outputs[DOC/"engineering/release-evidence.md"]=doc_page("Release Evidence","Release-bound canonical evidence without unsupported GitHub claims.","development","# Release Evidence\n\nStatus: **"+release["status"]+"**\n\n"+table(["Field","Value"],[["Source commit",release["source_commit"]],["Tree hash",release["tree_hash"]],["Runtime baseline binding",release["runtime_baseline_binding"]],["dist.zip",release["artifacts"]["dist.zip"]],["GitHub asset presence",release["artifacts"]["github_asset_presence"]],["SBOM digest",release["sbom_digest"]],["Security scan digest",release["security_scan_digest"]]]))
    outputs[DOC/"engineering/troubleshooting.md"]=doc_page("Development Troubleshooting","Diagnostic handbook with command safety classification.","development","# Development Troubleshooting\n\n"+"\n".join(f"## {x['scenario']}\n\n**Symptom:** {x['symptom']}\n\n**Interpretation:** {x['interpretation']}\n\n### Safe checks\n\n"+table(["Command","Class"],[[c["command"],c["class"]] for c in x["safe_checks"]])+"\n**Verification:** "+x["verification"]+"\n\n**Do not do:** "+"; ".join(x["do_not_do"])+"\n" for x in trouble))
    outputs[DOC/"threat-model/index.md"]=doc_page("Threat Model","Source-derived STRIDE threat model with promoted evidence posture.","production","# Threat Model\n\n**Current promoted threat posture** — derived only from canonical source and promoted sanitized evidence. This is not live monitoring.\n\n## Trust boundaries\n\n"+table(["Boundary","Runtime evidence","Review"],[[b["label"],b["runtime_evidence_status"],b["review_status"]] for b in threat["boundaries"]])+"\n## Security controls\n\n"+table(["Control","Description","Status"],[[c["id"],c["description"],c["status"]] for c in controls]))
    for b in threat["boundaries"]:
        bt=[t for t in threat["threats"] if t["boundary"]==b["id"]]
        body=f"# {b['label']}\n\n## Boundary\n\n{b['label']}\n\n## Assets\n\n"+"\n".join(f"- {x}" for x in b["assets"])+"\n\n## Actors\n\n"+"\n".join(f"- {x}" for x in b["actors"])+"\n\n## Entry points\n\n"+"\n".join(f"- {x}" for x in b["entry_points"])+"\n\n## Allowed flows\n\n"+"\n".join(f"- {x}" for x in b["allowed_flows"])+"\n\n## Forbidden flows\n\n"+"\n".join(f"- {x}" for x in b["forbidden_flows"])+"\n\n## Threats\n\n"+table(["ID","STRIDE","Scenario","Controls"],[[t["id"],t["stride"],t["scenario"],t["controls"]] for t in bt])+"\n## Controls\n\nSee Security Controls catalog.\n\n## Runtime evidence\n\n"+b["runtime_evidence_status"]+"\n\n## Residual risk\n\nUnvalidated until human review.\n\n## Review status\n\n"+b["review_status"]+"\n"
        outputs[DOC/"threat-model"/f"{b['id']}.md"]=doc_page(b["label"],f"Threats and controls for {b['label']}.","production",body,"threat-model")
    outputs[DOC/"knowledgebase/index.md"]=doc_page("Knowledgebase","First-class Production Living Knowledgebase entry point.","production","# Knowledgebase\n\nUse the existing generated Living Knowledge pages for components, capabilities, scenarios, troubleshooting, limitations, reason codes, glossary, data lineage, ownership and evidence. This tab is navigation over canonical content, not a duplicate knowledge store.\n")
    health_payload=read_json(OP_HEALTH,{}) or {}
    health_domains=health_payload.get("domains",{}) or {}
    domain_iter=sorted(health_domains.items()) if isinstance(health_domains,dict) else [(str(x.get("id") or "unknown"),x) for x in health_domains if isinstance(x,dict)]
    for did,domain in domain_iter:
        did=str(did)
        label={"home":"Home","apps":"Apps","devices":"Devices","security":"Security","recovery":"Backup & Restore","identity":"Identity","rules":"Rules"}.get(did,did.title())
        domain_deps=[x for x in deps if str(x["domain"]).lower().replace(" & ","-").replace(" ","-") in {did,label.lower().replace(" & ","-").replace(" ","-")} or str(x["domain"]).lower()==label.lower()]
        body=(f"# {label}\n\n## Summary\n\nCanonical domain documentation projection.\n\n## Current state\n\nOperational health: **{domain.get('operational_health','unvalidated')}**. Semantic parity remains independent.\n\n## Capabilities\n\n"+(table(["Capability","Status"],[[x.get("id") or x.get("capability") or "domain capability",x.get("status") or x.get("state") or "unvalidated"] for x in domain.get("capabilities",[])]) if domain.get("capabilities") else "No canonical per-domain capability list is present; see Platform Capability Matrix.\n"))
        body += "\n## Dependencies\n\n"+(table(["Dependency","State","Evidence"],[[x["dependency"],x["state"],x["evidence_authority"]] for x in domain_deps]) if domain_deps else "No dedicated dependency rows are available; dependency state is unvalidated.\n")
        body += "\n## Evidence\n\nRelease/promoted evidence status: **"+str(domain.get("evidence_status","unvalidated"))+"**.\n\n## Known limitations\n\n"+str(domain.get("reason") or "See generated Known Limitations; none inferred here.")+"\n\n## Recovery\n\nUse canonical Recovery/Incident Runbooks; this page does not infer repair commands.\n\n## Provenance\n\n`contracts/generated/runtime/domain-operational-health.json` and canonical Documentation Platform metadata.\n"
        if did == "identity":
            body += "\n## Identity relationships\n\n[Identity Feature Journey](../../journeys/identity.md) links the verified passkey, purpose-bound step-up, session, and Enterprise membership relationships. [API-to-UI Trace](../../reference/api-ui-trace.md) remains FastAPI control-plane owned; browser authority is not inferred.\n"
        elif did == "rules":
            body += "\n## Rules relationships\n\n[Rules Feature Journey](../../journeys/rules.md) links protected-action admission, lifecycle, analysis, approval, continuation, and narrow exceptions. [API-to-UI Trace](../../reference/api-ui-trace.md) does not infer NATS or worker execution for these governance operations.\n"
        outputs[DOC/"knowledgebase/domains"/f"{did}.md"]=doc_page(label,f"Operational domain page for {label}.","production",body,"domain")
    outputs[DOC/"architecture/index.md"]=doc_page("Architecture","First-class architecture navigation and cross-links.","production","# Architecture\n\nPocket Lab Lite architecture remains UI → Caddy → FastAPI → NATS/JetStream → worker/agent/supervisor → evidence → FastAPI → UI.\n\nCross-reference the Threat Model, Runtime Drift, Release Delta and Security Controls when reviewing changes.\n")
    outputs[DOC/"operate/incident-runbooks.md"]=doc_page("Production Incident Runbooks","Operator-grade safe incident decision support.","production","# Production Incident Runbooks\n\n"+"\n".join(f"## {x['scenario']}\n\n### Symptom\n{x['symptom']}\n\n### Impact\n{x['interpretation']}\n\n### Likely causes\n- {x['likely_causes'][0]}\n\n### Safe checks\n"+table(["Command","Class"],[[c["command"],c["class"]] for c in x["safe_checks"]])+"\n### Recovery\nOnly reviewed SAFE_REPAIR procedures may be followed; none are inferred by this generator.\n\n### Verification\n"+x["verification"]+"\n\n### Rollback\n"+x["rollback"]+"\n\n### Escalation\nPreserve sanitized evidence and escalate when recovery ownership is unclear.\n\n### Evidence\n"+", ".join(x["evidence_to_preserve"])+"\n" for x in trouble),"runbook")
    for x in trouble:
        slug=re.sub(r"[^a-z0-9]+","-",x["scenario"].lower()).strip("-")
        body=f"# {x['scenario']}\n\n## Symptom\n\n{x['symptom']}\n\n## Impact\n\n{x['interpretation']}\n\n## Likely causes\n\n- {x['likely_causes'][0]}\n\n## Safe checks\n\n"+table(["Command","Class"],[[c["command"],c["class"]] for c in x["safe_checks"]])+"\n## Recovery\n\nOnly repository-reviewed SAFE_REPAIR guidance may be used. No repair command is inferred here.\n\n## Verification\n\n"+x["verification"]+"\n\n## Rollback\n\n"+x["rollback"]+"\n\n## Escalation\n\nPreserve sanitized evidence and escalate when ownership is unclear.\n\n## Evidence\n\n"+", ".join(x["evidence_to_preserve"])+"\n"
        outputs[DOC/"operate/runbooks"/f"{slug}.md"]=doc_page(x["scenario"],f"Incident runbook for {x['scenario']}.","production",body,"runbook")
    outputs[DOC/"operate/troubleshooting.md"]=doc_page("Production Troubleshooting","Plain-language symptom-oriented troubleshooting.","production","# Production Troubleshooting\n\n"+"\n".join(f"## {x['scenario']}\n\n{x['symptom']}. {x['interpretation']}. Open the incident runbook for verified checks and recovery.\n" for x in trouble))
    outputs[DOC/"reference/configuration.md"]=doc_page("Configuration Intelligence","Sanitized source-discovered configuration catalog.","development","# Configuration Intelligence\n\nActual secret values are never rendered.\n\n"+table(["Name","Secret?","Scope","Owner","Validation"],[[x["name"],x["secret"],x["runtime_scope"],x["owner"],x["validation"]] for x in config]))
    outputs[DOC/"reference/api-ui-trace.md"]=doc_page("API-to-UI Trace Explorer","Source-derived ownership traces for important Lite actions.","development","# API-to-UI Trace Explorer\n\n"+table(["Action","API","Handler","Execution owner","Evidence"],[[x["action"],x["api"],x["handler_owner"],x["execution_owner"],x["evidence"]] for x in traces]))
    outputs[DOC/"reference/data-lifecycle.md"]=doc_page("Data Lifecycle & Privacy Map","Sanitized data lifecycle and privacy controls.","production","# Data Lifecycle & Privacy Map\n\n"+table(["Category","Storage","Retention","Sanitization","Privacy risk"],[[x["category"],x["storage"],x["retention"],x["sanitization"],x["privacy_risk"]] for x in privacy]))
    outputs[DOC/"reference/fmea.md"]=doc_page("Failure-mode & Resilience Catalog","Dependency-grounded categorical FMEA without arbitrary numeric RPN.","development","# Failure-mode & Resilience Catalog\n\n"+table(["Component","Failure mode","Impact","Recovery","Severity"],[[x["component"],x["failure_mode"],x["user_impact"],x["manual_recovery"],x["severity"]] for x in fm]))
    outputs[DOC/"reference/reliability.md"]=doc_page("Reliability Objectives","Engineering objectives and promoted observations, not live monitoring.","production","# Reliability Objectives\n\n"+table(["Objective","Target","Latest promoted observation","Status"],[[x["objective"],x["target"],x["latest_promoted_observation"],x["status"]] for x in slo]))
    outputs[DOC/"reference/supply-chain.md"]=doc_page("Software Supply Chain","Canonical source inventory and normalized heavy-tool evidence boundary.","development","# Software Supply Chain\n\nStatus: **"+supply["status"]+"**\n\n## Manifests\n\n"+table(["Manifest","SHA-256"],[[x["path"],x["sha256"]] for x in supply["manifests"]])+"\n## Tooling\n\n"+table(["Tool","Version","Purpose","Surface","Required"],[[x["id"],x["version"],x["purpose"],x["execution_surface"],x["required"]] for x in supply["tools"]])+"\nRaw third-party output is never canonical documentation truth.\n")
    outputs[DOC/"reference/security-controls.md"]=doc_page("Security Controls","Threat → control → implementation → evidence traceability.","development","# Security Controls\n\n"+table(["Control","Description","Implementation","Status"],[[x["id"],x["description"],x["implementation"],x["status"]] for x in controls]))
    outputs[DOC/"reference/change-advisor.md"]=doc_page("Change Impact Advisor","Deterministic change-to-test/documentation advice; does not execute changes.","development","# Change Impact Advisor\n\n"+table(["Changed path prefix","Potential impacts","Recommended tasks"],[[x["path_prefix"],x["impacts"],x["recommended_tasks"]] for x in change_advisor["rules"]]))
    outputs[DOC/"reference/ownership.md"]=doc_page("Ownership & Responsibility Map","Component-role ownership across source, runtime, recovery, control, presentation and evidence.","development","# Ownership & Responsibility Map\n\n"+table(["Capability","Source owner","Runtime owner","Recovery owner","Control owner","Presentation owner","Evidence owner"],[[x["capability"],x["source_owner"],x["runtime_owner"],x["recovery_owner"],x["control_owner"],x["presentation_owner"],x["evidence_owner"]] for x in ownership]))
    outputs[DOC/"reference/validation-coverage.md"]=doc_page("Validation Coverage Dashboard","Latest canonical validation categories without CI polling.","development","# Validation Coverage Dashboard\n\n"+table(["Gate","Status"],[[x["name"],x["status"]] for x in validation["checks"]])+"\nThis page never polls CI or runs heavy tools.\n")
    outputs[DOC/"reference/upgrade-migration.md"]=doc_page("Upgrade & Migration Intelligence","Fail-closed release-to-release upgrade guidance.","production","# Upgrade & Migration Intelligence\n\nStatus: **"+upgrade["status"]+"**. A verified prior release is required before comparative upgrade claims are generated.\n")
    outputs[DOC/"reference/disaster-recovery.md"]=doc_page("Disaster Recovery Architecture","Recovery dependency order and evidence for major loss scenarios.","production","# Disaster Recovery Architecture\n\n"+table(["Scenario","What survives","Recoverability","Dependency order","Verification"],[[x["scenario"],x["survives"],x["recoverable"],x["dependency_order"],x["verification"]] for x in disaster]))
    outputs[DOC/"reference/documentation-quality.md"]=doc_page("Documentation Quality Scorecard","Categorical domain documentation coverage.","development","# Documentation Quality Scorecard\n\n"+table(["Domain","Architecture","API","Events","Runbook","Threat model","Operational health","Evidence","Troubleshooting"],[[x["domain"],x["architecture_documented"],x["api_documented"],x["events_documented"],x["runbook_present"],x["threat_model_present"],x["operational_health_modeled"],x["evidence_coverage"],x["troubleshooting"]] for x in quality]))
    outputs[DOC/"reference/adr-intelligence.md"]=doc_page("ADR Intelligence","Architecture decisions and their source-derived relationships.","development","# ADR Intelligence\n\n"+(table(["Decision","Context / status","Source"],[[x.get("title") or x.get("name") or x.get("id") or "ADR",x.get("status") or x.get("summary") or "source-derived",x.get("source") or x.get("path") or "knowledge graph"] for x in adr["entities"]]) if adr["entities"] else "No canonical ADR entities are currently available; status remains missing rather than fabricated.\n")+"\nRelationship diagrams should use the canonical knowledge graph when explicit ADR relations exist.\n")
    outputs[DOC/"reference/supply-chain-change.md"]=doc_page("Supply-chain Change Intelligence","Release-to-release normalized SBOM/vulnerability/license comparison that fails closed without verified baselines.","development","# Supply-chain Change Intelligence\n\nStatus: **"+supply_change["status"]+"**.\n\nNo dependency, vulnerability or license delta is fabricated without two normalized, verified release inputs.\n")
    outputs[DOC/"release/index.md"]=doc_page("Release","Release evidence, delta, upgrade and supply-chain intelligence.","production","# Release\n\n## Evidence\n\nCurrent source and tree identities are repository-derived. Runtime baseline binding remains independent.\n\n## Release delta\n\n**"+delta["status"]+"** — comparison fails closed without two verified canonical release manifests.\n\n## Provenance\n\nSLSA-style provenance metadata only; no formal SLSA level is claimed.\n")
    search_body = '# Search aliases\n\n<div class="pl-page-lede"><strong>Find the canonical page using the words people actually type.</strong><p>Aliases enrich MkDocs search deterministically without modifying Material internals. Every alias maps back to canonical documentation destinations.</p></div>\n\n<div class="pl-alias-grid">\n'
    for item in synonyms:
        search_body += '<article class="pl-alias-card">'
        search_body += f'<span class="pl-card-kicker">Canonical term</span><h2>{html.escape(str(item["canonical"]))}</h2>'
        search_body += '<h3>Search aliases</h3><div class="pl-chip-list">' + ''.join(f'<span class="pl-chip">{html.escape(str(x))}</span>' for x in item.get("synonyms", [])) + '</div>'
        search_body += '<h3>Destinations</h3><div class="pl-code-stack">' + ''.join(f'<code>{html.escape(str(x))}</code>' for x in item.get("destinations", [])) + '</div>'
        search_body += '</article>\n'
    search_body += '</div>\n'
    outputs[DOC/"search-synonyms.md"]=doc_page("Search aliases","Searchable alias terms mapped to canonical documentation destinations.","all",search_body)
    index, outputs = complete_enterprise_projection(ROOT, index, outputs, frontmatter=frontmatter, table=table, deps=deps, base_config=config, supply=supply)
    ia_overrides = {}
    for key, path in {
        "api-ui-trace": OUT / "api-ui-trace.json",
        "event-encyclopedia": OUT / "event-encyclopedia.json",
        "security-controls": OUT / "security-controls.json",
    }.items():
        if path in outputs:
            ia_overrides[key] = json.loads(outputs[path])
        elif path.exists():
            ia_overrides[key] = read_json(path, {}) or {}
    ia_outputs, ia_contract, ia_cross_links, ia_search = build_documentation_ia(ROOT, overrides=ia_overrides)
    outputs.update(ia_outputs)
    index["items"]["information_architecture"] = {
        "implementation_status": "implemented",
        "contract": "contracts/generated/documentation-enterprise/information-architecture.json",
        "page_count": ia_contract["page_count"],
        "feature_journey_count": len(ia_contract["feature_journeys"]),
        "cross_link_count": len(ia_cross_links["relations"]),
        "top_level": ia_contract["top_level"],
        "live_runtime": False,
    }
    index["items"]["documentation_search"] = {
        "implementation_status": "implemented",
        "contract": "contracts/generated/documentation-enterprise/documentation-search.json",
        "local_static": True,
        "runtime_indexing": False,
        "alias_groups": len(ia_search["entries"]),
    }
    index["source_fingerprint"] = fp
    outputs[INDEX] = stable(index)
    outputs[OUT/"threat-dragon-export.json"] = stable(threat_dragon_export(index["items"]["threat_model"]))
    jsonschema.validate(index, read_json(SCHEMA,{}))
    for p,text in outputs.items(): safe(str(p),text)
    return outputs,index


def anatomy_errors(outputs: dict[Path,str]) -> list[str]:
    req={
      "domain":["summary","current state","capabilities","dependencies","evidence","known limitations","recovery","provenance"],
      "runbook":["trigger","impact","urgency","user-visible symptom","known evidence","safe checks","expected output","decision tree","recovery","verification","rollback","when not to act","evidence to preserve","escalation"],
      "threat-model":["boundary","assets","actors","entry points","data flows","allowed flows","forbidden flows","threats","controls","runtime evidence","residual risk","review status"],
      "release":["summary","release evidence","release delta","compatibility","validation outcomes","known limitations","provenance"],
    }
    errors=[]
    for p,text in outputs.items():
        if p.suffix != ".md": continue
        m=re.search(r"^page_type:\s*([^\n]+)",text,re.M)
        kind=m.group(1).strip() if m else "reference"
        lower=text.lower()
        for section in req.get(kind,[]):
            if f"## {section}" not in lower and f"### {section}" not in lower:
                errors.append(f"{p.relative_to(ROOT)}: {kind} page missing section {section!r}")
    # Universal generated-page anatomy: all tracked generated Markdown, not only this generator,
    # must declare basic provenance/audience metadata and a human-readable H1. This turns page
    # anatomy into a Documentation Platform fence instead of an enterprise-page-only convention.
    enterprise_paths={p.resolve():text for p,text in outputs.items() if p.suffix==".md"}
    for p in sorted((ROOT/"docs/generated").rglob("*.md")):
        text=enterprise_paths.get(p.resolve())
        if text is None:
            text=p.read_text(encoding="utf-8",errors="ignore")
        # Some generated Markdown files are embedded fragments/snippets rather than standalone pages.
        # Full generated pages are identified by YAML frontmatter and universally require a title,
        # generated marker, audience, and H1. Fragments are intentionally not misclassified as pages.
        if not text.startswith("---\n"):
            continue
        for marker in ["title:","generated: true","audience:"]:
            if marker not in text[:1800]: errors.append(f"{p.relative_to(ROOT)}: generated page missing frontmatter marker {marker!r}")
        if not re.search(r"^#\s+\S",text,re.M): errors.append(f"{p.relative_to(ROOT)}: generated page missing H1")
    return errors

def validate_synonyms(index: dict[str,Any]) -> list[str]:
    errors=[]
    for row in index["items"]["search_synonyms"]:
        if not row.get("destinations"): errors.append(f"orphan search synonym: {row['canonical']}")
        for dest in row.get("destinations",[]):
            candidate=ROOT/"docs"/(dest.strip("/")+".md")
            candidate_index=ROOT/"docs"/dest.strip("/")/"index.md"
            if not candidate.exists() and not candidate_index.exists(): errors.append(f"search destination missing: {dest}")
    return errors


def write(outputs: dict[Path,str]) -> int:
    count=0
    for p,text in outputs.items():
        p.parent.mkdir(parents=True,exist_ok=True)
        if not p.exists() or p.read_text(encoding="utf-8")!=text:
            p.write_text(text,encoding="utf-8"); count+=1
    return count


def check(outputs: dict[Path,str], index: dict[str,Any]) -> list[str]:
    errors=[]
    for p,text in outputs.items():
        if not p.exists(): errors.append(f"missing generated output: {p.relative_to(ROOT)}")
        elif p.read_text(encoding="utf-8")!=text: errors.append(f"generated drift: {p.relative_to(ROOT)}")
    errors += anatomy_errors(outputs)
    errors += validate_synonyms(index)
    return errors


def main() -> int:
    ap=argparse.ArgumentParser(); ap.add_argument("mode",choices=["generate","check"]); args=ap.parse_args()
    outputs,index=build()
    if args.mode=="generate":
        changed=write(outputs)
        errors=anatomy_errors(outputs)+validate_synonyms(index)
        if errors:
            print("FAIL enterprise documentation validation",file=sys.stderr); [print(f"- {x}",file=sys.stderr) for x in errors]; return 1
        print(f"PASS enterprise documentation generated: {len(outputs)} artifacts ({changed} changed)")
        return 0
    errors=check(outputs,index)
    if errors:
        print("FAIL enterprise documentation check",file=sys.stderr); [print(f"- {x}",file=sys.stderr) for x in errors]; return 1
    print(f"PASS enterprise documentation check: {len(outputs)} deterministic artifacts")
    return 0

if __name__ == "__main__": raise SystemExit(main())
