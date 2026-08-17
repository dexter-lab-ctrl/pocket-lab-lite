#!/usr/bin/env python3
"""Deterministic threat-model visualization and interaction projection.

No live data, network access, scanners, or runtime capture are used. The diagram is a visual
projection of the canonical architecture, threat model, and already-promoted sanitized evidence.
"""
from __future__ import annotations

import html
import json
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any

SCENARIOS = Path("security/threat-model-scenarios.json")
STATE_RANK = {"control-observed": 0, "mitigation-source-derived": 1, "control-partial": 2, "evidence-stale": 3, "control-unvalidated": 4, "not-applicable": 5}

NODE_SPECS = [
    ("github-release", "GitHub Release", "external-release", "github.svg", 90, 90, "github-release"),
    ("release-artifacts", "Release artifacts", "external-release", "release.svg", 280, 90, "release-artifacts"),
    ("scanner-evidence", "Scanner / SBOM", "external-release", "trivy.svg", 470, 90, "security-profiles"),
    ("private-network", "Private network", "private-network", "network.svg", 90, 260, "tailscale"),
    ("tailscale", "Tailscale", "private-network", "tailscale.svg", 280, 260, "tailscale"),
    ("browser", "Browser / PWA", "browser", "react.svg", 90, 430, "pwa"),
    ("caddy", "Caddy", "server-host", "caddy.svg", 280, 430, "caddy"),
    ("lite-api", "FastAPI", "control-api", "fastapi.svg", 470, 430, "lite-api"),
    ("nats-jetstream", "NATS / JetStream", "messaging-execution", "nats.svg", 660, 430, "nats-jetstream"),
    ("worker", "Worker", "messaging-execution", "python.svg", 850, 430, "worker"),
    ("managed-device", "Managed device", "managed-device", "android.svg", 1040, 260, "node-agent"),
    ("node-agent", "Node agent", "managed-device", "agent.svg", 1040, 430, "node-agent"),
    ("agent-supervisor", "Supervisor", "managed-device", "supervisor.svg", 1040, 600, "agent-supervisor"),
    ("server-host", "Termux host", "server-host", "terminal.svg", 850, 600, "pm2"),
    ("photoprism", "PhotoPrism", "application-container", "photoprism.svg", 660, 600, "photoprism"),
    ("sqlite", "SQLite", "durable-state", "sqlite.svg", 470, 600, "sqlite"),
    ("recovery-state", "Recovery state", "durable-state", "recovery.svg", 280, 600, "recovery-state"),
    ("promoted-evidence", "Promoted evidence", "durable-state", "evidence.svg", 470, 760, "completion-evidence"),
    ("documentation", "Documentation", "durable-state", "docs.svg", 660, 760, "completion-evidence")
]

NORMAL_EDGES = [
    ("browser", "caddy", "HTTPS"), ("caddy", "lite-api", "same-origin"), ("lite-api", "nats-jetstream", "commands/events"),
    ("nats-jetstream", "worker", "JetStream"), ("worker", "node-agent", "execution"), ("node-agent", "agent-supervisor", "recovery"), ("managed-device", "node-agent", "device identity/agent"), ("agent-supervisor", "server-host", "PM2 supervision"),
    ("lite-api", "sqlite", "durable state"), ("worker", "photoprism", "app lifecycle"), ("photoprism", "server-host", "hosted runtime"), ("private-network", "tailscale", "private access"),
    ("tailscale", "caddy", "remote HTTPS"), ("github-release", "release-artifacts", "release"), ("release-artifacts", "server-host", "explicit install/update"),
    ("scanner-evidence", "promoted-evidence", "sanitize + promote"), ("server-host", "promoted-evidence", "sanitized runtime evidence"),
    ("promoted-evidence", "documentation", "deterministic projection"), ("sqlite", "recovery-state", "backup/recovery metadata"),
    ("recovery-state", "lite-api", "safe projection")
]


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _boundary_state(threat: dict[str, Any], boundary: str) -> str:
    signals = [x.get("state", "control-unvalidated") for x in threat.get("production_posture", {}).get("signals", []) if x.get("boundary") == boundary]
    if not signals:
        return "control-unvalidated"
    return max(signals, key=lambda x: STATE_RANK.get(str(x), 99))


def _graph() -> dict[str, set[str]]:
    graph: dict[str, set[str]] = defaultdict(set)
    for a, b, _ in NORMAL_EDGES:
        graph[a].add(b)
        graph[b].add(a)
    return graph


def _reachable(graph: dict[str, set[str]], start: str, target: str) -> bool:
    if start == target:
        return True
    seen = {start}
    queue = deque([start])
    while queue:
        node = queue.popleft()
        for nxt in graph.get(node, set()):
            if nxt == target:
                return True
            if nxt not in seen:
                seen.add(nxt); queue.append(nxt)
    return False


def enrich(threat: dict[str, Any], root: Path) -> dict[str, Any]:
    scenarios = read_json(root / SCENARIOS, {}) or {}
    controls = {x["id"]: x for x in threat.get("controls", [])}
    boundaries = {x["id"]: x for x in threat.get("boundaries", [])}
    architecture = read_json(root / "architecture/metadata/pocket-lab-architecture.json", {}) or {}
    arch_components = architecture.get("components", {}) if isinstance(architecture, dict) else {}
    node_ids = {x[0] for x in NODE_SPECS}
    graph = _graph()

    attack_paths = []
    for row in scenarios.get("attack_paths", []):
        path = list(row.get("path_nodes") or [])
        if len(path) < 2 or any(x not in node_ids for x in path):
            raise ValueError(f"attack path {row.get('id')} references unknown visualization node")
        missing_controls = [x for x in row.get("controls", []) if x not in controls]
        missing_boundaries = [x for x in row.get("boundaries", []) if x not in boundaries]
        if missing_controls or missing_boundaries:
            raise ValueError(f"attack path {row.get('id')} has unresolved controls/boundaries: {missing_controls} {missing_boundaries}")
        # Attack paths may include a prohibited shortcut; require every pair to be connected through the canonical graph
        # so a typo cannot silently create a disconnected visual path.
        for a, b in zip(path, path[1:]):
            if not _reachable(graph, a, b):
                raise ValueError(f"attack path {row.get('id')} contains disconnected nodes: {a} -> {b}")
        attack_paths.append({**row, "confidence": "source-derived", "confirmed_exploit": False, "mitigation_language": "controls mitigate/reduce exposure; prevention is not claimed unless separately evidenced"})

    consequence_defaults = {
        "CTRL-BROWSER-NATS": ["browser could bypass the control API and attempt unauthorized messaging/command injection"],
        "CTRL-BROWSER-SHELL": ["browser-originated input could reach host shell execution and mutate the server host"],
        "CTRL-API-CONTROL": ["frontend intent could bypass centralized validation, authorization, reason codes and audit ownership"],
        "CTRL-HUMAN-SESSION-CSRF": ["ambient browser session authority could be reused without a separate write-intent proof or reusable session material could be exposed"],
        "CTRL-OPA-FAIL-CLOSED": ["a protected mutation could proceed without a valid authorization decision or while policy state is unavailable or ambiguous"],
        "CTRL-EXECUTION-OWNERS": ["commands or recovery could execute outside worker/agent/supervisor ownership and lose delivery/recovery guarantees"],
        "CTRL-EVIDENCE-SANITIZE": ["secret-bearing or private-path evidence could enter canonical documentation or mislead security posture"],
        "CTRL-EXPLICIT-PROMOTION": ["transient/unreviewed capture could be mistaken for canonical release/runtime evidence"],
        "CTRL-SUPPLY-CHAIN": ["unqualified dependencies or release artifacts could enter runtime without normalized SBOM/scanner evidence"]
    }
    for control in threat.get("controls", []):
        control["effect"] = "mitigates"
        control["prevention_claim"] = False
        control["failure_consequences"] = consequence_defaults.get(control["id"], ["control coverage would be reduced; exact exploitability remains human review"])
        control["where_used"] = list(control.get("boundaries") or [])

    nodes = []
    for node_id, label, boundary, icon, x, y, component in NODE_SPECS:
        if component not in arch_components:
            raise ValueError(f"threat visualization component {component!r} is missing from canonical architecture")
        nodes.append({"id": node_id, "label": label, "boundary": boundary, "icon": icon, "x": x, "y": y, "architecture_component": component, "posture": _boundary_state(threat, boundary)})

    edge_rows = [{"id": f"flow-{i:02d}", "from": a, "to": b, "label": label, "kind": "allowed-flow"} for i, (a, b, label) in enumerate(NORMAL_EDGES, 1)]
    control_bindings = []
    for cid, control in controls.items():
        for boundary in control.get("boundaries", []):
            control_bindings.append({"control": cid, "boundary": boundary, "status": control.get("status"), "threats": control.get("threats", [])})
    control_counts = Counter(x.get("status", "control-unvalidated") for x in threat.get("controls", []))
    posture_counts = Counter(x.get("state", "control-unvalidated") for x in threat.get("production_posture", {}).get("signals", []))

    threat["framework"] = scenarios.get("framework", {})
    threat["truth_layers"] = scenarios.get("truth_layers", [])
    threat["attack_paths"] = attack_paths
    threat["exclusions"] = scenarios.get("exclusions", [])
    threat["consequences_without_model"] = scenarios.get("consequences_without_model", [])
    threat["architecture_integration"] = {
        "canonical_model": "architecture/metadata/pocket-lab-architecture.json",
        "architecture_page": "generated/production/architecture/",
        "rule": "Threat visualization nodes reference canonical architecture component ids; security overlays never redefine topology ownership.",
        "component_count": len({x["architecture_component"] for x in nodes}),
    }
    threat["visualization"] = {
        "schema_version": "1.0.0", "live_monitoring": False, "nodes": nodes, "edges": edge_rows, "attack_paths": attack_paths,
        "control_bindings": control_bindings,
        "legend": {"allowed-flow": "canonical architecture flow", "attack-path": "modeled threat path", "control": "mitigation/control interception"},
        "animation_semantics": "animated lines represent modeled control/evidence flow, never live traffic or attacks",
        "evidence_lineage": [
            {"id": "runtime", "label": "Promoted runtime baseline", "source": "contracts/parity/runtime-verification-baseline.json"},
            {"id": "health", "label": "Domain operational health", "source": "contracts/generated/runtime/domain-operational-health.json"},
            {"id": "dependencies", "label": "Dependency health", "source": "contracts/generated/documentation-intelligence/dependency-health.json"},
            {"id": "supply-chain", "label": "Normalized scanner/SBOM evidence", "source": "contracts/generated/supply-chain"},
            {"id": "threat-posture", "label": "Threat posture projection", "source": "contracts/generated/documentation-enterprise/threat-posture.json"},
            {"id": "diagram", "label": "Threat model diagram", "source": "docs/generated/assets/enterprise/threat-model.svg"}
        ],
        "posture_summary": {
            "trust_boundaries": len(threat.get("boundaries", [])), "stride_candidates": len(threat.get("threats", [])),
            "controls": len(threat.get("controls", [])), "attack_paths": len(attack_paths),
            "control_states": dict(sorted(control_counts.items())), "posture_states": dict(sorted(posture_counts.items())),
            "human_review_required": True,
        }
    }
    return threat


def build_security_atlas(threat: dict[str, Any]) -> dict[str, Any]:
    """Build deterministic, source-derived catalog projections from the canonical model."""
    viz = threat.get("visualization", {})

    def display(value: Any) -> str:
        if isinstance(value, (dict, list, tuple, set, Counter)):
            normalized = dict(value) if isinstance(value, Counter) else list(value) if isinstance(value, (tuple, set)) else value
            return json.dumps(normalized, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return str(value)
    boundaries = {row.get("id"): row for row in threat.get("boundaries", [])}
    catalog: list[dict[str, Any]] = []

    def add(
        view: str,
        kind: str,
        catalog_id: str,
        target_id: str,
        title: str,
        summary: str,
        meta: str,
        source_refs: list[str],
    ) -> None:
        catalog.append({
            "view": view,
            "kind": kind,
            "catalog_id": catalog_id,
            "target_id": target_id,
            "title": title,
            "summary": summary,
            "meta": meta,
            "source_refs": source_refs,
        })

    for row in threat.get("threats", []):
        add(
            "threats",
            "threat",
            str(row.get("id")),
            str(row.get("id")),
            f"{row.get('stride', 'Threat')} — {row.get('boundary', 'unvalidated')}",
            str(row.get("scenario") or "Source-derived STRIDE candidate requiring human review."),
            "Controls: " + ", ".join(row.get("controls", []) or ["unvalidated"]),
            ["contracts/security/threat-model.json", *list(row.get("runtime_evidence", []) or [])],
        )

    for row in viz.get("nodes", []):
        boundary = boundaries.get(row.get("boundary"), {})
        assets = ", ".join(boundary.get("assets", []) or ["source-derived asset scope"])
        add(
            "system",
            "system",
            f"system:{row.get('id')}",
            str(row.get("id")),
            str(row.get("label") or row.get("id")),
            f"Trust boundary: {row.get('boundary', 'unvalidated')}. Promoted posture: {row.get('posture', 'unvalidated')}. Assets: {assets}.",
            f"architecture:{row.get('architecture_component', 'unvalidated')}",
            ["architecture/metadata/pocket-lab-architecture.json", "contracts/security/threat-model.json"],
        )

    for row in threat.get("boundaries", []):
        add(
            "attack-surface",
            "boundary",
            f"boundary:{row.get('id')}",
            str(row.get("id")),
            str(row.get("label") or row.get("id")),
            "Assets: " + ", ".join(row.get("assets", []) or ["unvalidated"]) + ". Entry points: " + ", ".join(row.get("entry_points", []) or ["unvalidated"]) + ".",
            "Forbidden flows: " + ", ".join(row.get("forbidden_flows", []) or ["none declared"]),
            ["contracts/security/threat-model.json", "architecture/metadata/pocket-lab-architecture.json"],
        )

    for row in threat.get("attack_paths", []):
        add(
            "attack-surface",
            "attack-path",
            str(row.get("id")),
            str(row.get("id")),
            f"Attack path {row.get('id')}",
            str(row.get("name") or "Reviewed modeled attack path."),
            "STRIDE: " + " · ".join(row.get("stride", []) or ["unvalidated"]) + "; controls: " + ", ".join(row.get("controls", []) or ["unvalidated"]),
            ["security/threat-model-scenarios.json", "contracts/security/threat-model.json"],
        )

    for row in threat.get("controls", []):
        consequences = "; ".join(row.get("failure_consequences", []) or ["control coverage would be reduced"])
        add(
            "controls",
            "control",
            str(row.get("id")),
            str(row.get("id")),
            f"Control {row.get('id')}",
            str(row.get("description") or "Source-derived security control."),
            f"Coverage: {', '.join(row.get('where_used', []) or ['unvalidated'])}. If it fails: {consequences}",
            ["contracts/security/threat-model.json", *list(row.get("source_refs", []) or [])],
        )

    for row in viz.get("evidence_lineage", []):
        add(
            "evidence",
            "evidence",
            f"evidence:{row.get('id')}",
            str(row.get("id")),
            str(row.get("label") or row.get("id")),
            "Canonical or promoted evidence lineage used by the threat-model projection.",
            str(row.get("source") or "unvalidated"),
            [str(row.get("source") or "unvalidated")],
        )

    for index, row in enumerate(threat.get("production_posture", {}).get("signals", []), 1):
        add(
            "evidence",
            "posture",
            f"posture:{index:02d}",
            f"posture:{index:02d}",
            str(row.get("signal") or f"Posture signal {index}"),
            f"Boundary: {row.get('boundary', 'unvalidated')}. State: {row.get('state', 'unvalidated')}. Observed: {display(row.get('observed', 'unobserved'))}.",
            str(row.get("source") or "unvalidated"),
            [str(row.get("source") or "unvalidated")],
        )

    catalog.sort(key=lambda row: (str(row["view"]), str(row["kind"]), str(row["catalog_id"])))
    keys = [(row["kind"], row["catalog_id"]) for row in catalog]
    targets = [(row["kind"], row["target_id"]) for row in catalog]
    if len(keys) != len(set(keys)):
        raise ValueError("Security Atlas catalog contains duplicate kind/id entries")
    if len(targets) != len(set(targets)):
        raise ValueError("Security Atlas catalog contains ambiguous deep-link targets")

    views = [
        {"id": "threats", "label": "Threat Atlas", "description": "STRIDE candidates and their reviewed source-derived control relationships."},
        {"id": "system", "label": "System Atlas", "description": "Canonical architecture components, trust boundaries, assets and promoted posture."},
        {"id": "attack-surface", "label": "Attack Surface Atlas", "description": "Entry surfaces, trust boundaries and reviewed modeled attack paths."},
        {"id": "controls", "label": "Control Atlas", "description": "Controls, coverage, threat relationships and consequences if controls fail."},
        {"id": "evidence", "label": "Evidence Atlas", "description": "Promoted/canonical evidence lineage and posture signals; never live monitoring."},
    ]
    counts = Counter(row["view"] for row in catalog)
    for row in views:
        row["entry_count"] = counts.get(row["id"], 0)

    return {
        "schema_version": "1.0.0",
        "source_model": "contracts/security/threat-model.json",
        "live_monitoring": False,
        "generated_intelligence": "deterministic-projection-only",
        "architecture_rule": "Architecture is the map. Security Atlas explains threats, assets, controls, trust boundaries, attack paths and evidence without redefining architecture ownership.",
        "poster": {"asset": "docs/generated/assets/enterprise/security-atlas.svg", "view_count": len(views)},
        "views": views,
        "catalog": catalog,
    }


def _esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def render_svg(threat: dict[str, Any]) -> str:
    viz = threat["visualization"]
    nodes = {x["id"]: x for x in viz["nodes"]}
    width, height = 1160, 840
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="tm-title tm-desc">',
             '<title id="tm-title">Pocket Lab Lite threat model architecture overlay</title>',
             '<desc id="tm-desc">Canonical architecture, trust-boundary posture, controls and modeled attack paths. Animation represents modeled flow, never live traffic.</desc>',
             '''<style>
:root{color-scheme:light dark}.bg{fill:#0b1020}.zone{fill:#111a2d;stroke:#3c4d70;stroke-width:1.5;rx:18}.node rect{fill:#17243a;stroke:#7892b8;stroke-width:1.4;rx:12}.node text{fill:#f2f6ff;font:600 13px system-ui,sans-serif}.node .state{font:500 10px system-ui,sans-serif;fill:#b9c7dc}.node[data-state="control-observed"] rect{stroke:#3fb950}.node[data-state="evidence-stale"] rect,.node[data-state="control-partial"] rect{stroke:#d29922}.node[data-state="control-unvalidated"] rect{stroke:#8b949e;stroke-dasharray:5 4}.flow{fill:none;stroke:#58a6ff;stroke-width:2.2;opacity:.72;stroke-dasharray:8 8;animation:flow 5s linear infinite}.attack{fill:none;stroke:#ff6b6b;stroke-width:4;opacity:0;stroke-dasharray:10 8;pointer-events:none}.attack.is-active{opacity:.92;animation:attack 1.4s linear infinite}.motion-paused .flow,.motion-paused .attack{animation-play-state:paused!important}.control{cursor:pointer}.control circle{fill:#173b2b;stroke:#56d364;stroke-width:2}.control text{fill:#dfffe8;font:700 9px system-ui,sans-serif}.control.is-active circle{stroke-width:5}.node.is-muted,.flow.is-muted,.control.is-muted{opacity:.16}.node.is-active rect{stroke-width:4}.label{fill:#9fb3ce;font:600 11px system-ui,sans-serif}.zone-title{fill:#c7d5e9;font:700 12px system-ui,sans-serif;letter-spacing:.06em}.legend{fill:#c7d5e9;font:500 11px system-ui,sans-serif}@keyframes flow{to{stroke-dashoffset:-32}}@keyframes attack{to{stroke-dashoffset:-36}}@media(prefers-reduced-motion:reduce){.flow,.attack{animation:none!important}}@media print{.flow{stroke-dasharray:none}.attack{display:none}}
</style>''', '<rect class="bg" width="1160" height="840"/>']
    zones = [
        ("external-release", 35, 35, 540, 135, "EXTERNAL RELEASE / SUPPLY CHAIN"),
        ("private-network", 35, 205, 430, 115, "PRIVATE NETWORK / TAILNET"),
        ("control-plane", 35, 355, 1110, 160, "CONTROL PLANE / EXECUTION"),
        ("runtime-state", 235, 545, 910, 120, "HOST / APPLICATION / DURABLE STATE"),
        ("evidence", 405, 705, 420, 105, "PROMOTED EVIDENCE → DOCUMENTATION")
    ]
    for zid,x,y,w,h,label in zones:
        parts.append(f'<g data-zone="{zid}"><rect class="zone" x="{x}" y="{y}" width="{w}" height="{h}"/><text class="zone-title" x="{x+18}" y="{y+24}">{_esc(label)}</text></g>')
    for edge in viz["edges"]:
        a,b=nodes[edge["from"]],nodes[edge["to"]]
        parts.append(f'<path class="flow" data-flow="{_esc(edge["id"])}" data-from="{_esc(edge["from"])}" data-to="{_esc(edge["to"])}" d="M {a["x"]+62} {a["y"]} L {b["x"]-62} {b["y"]}"/>')
    for path in viz["attack_paths"]:
        pts=[]
        for nid in path["path_nodes"]:
            n=nodes[nid]; pts.append(f'{n["x"]},{n["y"]}')
        parts.append(f'<polyline class="attack" data-attack-path="{_esc(path["id"])}" data-stride="{_esc(" ".join(path["stride"]))}" data-nodes="{_esc(" ".join(path["path_nodes"]))}" data-controls="{_esc(" ".join(path["controls"]))}" points="{" ".join(pts)}"/>')
    for n in viz["nodes"]:
        icon=f'../../../assets/diagrams/production/icons/{n["icon"]}'
        parts.append(f'<g class="node" data-node="{_esc(n["id"])}" data-boundary="{_esc(n["boundary"])}" data-state="{_esc(n["posture"])}" data-architecture-component="{_esc(n["architecture_component"])}" tabindex="0" role="button" aria-label="{_esc(n["label"])}; {_esc(n["posture"])}"><rect x="{n["x"]-68}" y="{n["y"]-34}" width="136" height="68"/><image href="{icon}" x="{n["x"]-56}" y="{n["y"]-19}" width="28" height="28"/><text x="{n["x"]-20}" y="{n["y"]-3}">{_esc(n["label"])}</text><text class="state" x="{n["x"]-20}" y="{n["y"]+15}">{_esc(n["posture"])}</text></g>')
    # Controls are placed in a stable row; interaction highlights every bound boundary/path.
    for i, c in enumerate(threat.get("controls", [])):
        x=55+i*155; y=825
        parts.append(f'<g class="control" data-control="{_esc(c["id"])}" data-boundaries="{_esc(" ".join(c.get("boundaries",[])))}" data-threats="{_esc(" ".join(c.get("threats",[])))}" tabindex="0" role="button" aria-label="Control {_esc(c["id"])}; {_esc(c.get("status"))}"><circle cx="{x}" cy="{y-20}" r="12"/><text x="{x+18}" y="{y-16}">{_esc(c["id"].replace("CTRL-",""))}</text></g>')
    parts.append('<text class="legend" x="38" y="690">Modeled flow — not live traffic · Blue = allowed/control flow · Red dashed = selected modeled attack path · Shield row = controls</text>')
    parts.append('</svg>\n')
    return ''.join(parts)


def render_security_atlas_svg(atlas: dict[str, Any]) -> str:
    """Render a self-contained Security Atlas overview poster."""
    views = atlas.get("views", [])
    width, height = 1200, 720
    cards = [
        ("Architecture", "The map", "Canonical topology and ownership stay architecture-owned."),
        *[(row.get("label"), f"{row.get('entry_count', 0)} entries", row.get("description")) for row in views],
    ]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="sa-title sa-desc">',
        '<title id="sa-title">Pocket Lab Lite Security Atlas</title>',
        '<desc id="sa-desc">Architecture is the map. Security Atlas explains threats, assets, controls, trust boundaries, reviewed attack paths and evidence from canonical source.</desc>',
        '<style>.bg{fill:#0b1020}.title{fill:#f2f6ff;font:700 28px system-ui,sans-serif}.sub{fill:#b9c7dc;font:500 14px system-ui,sans-serif}.card{fill:#111a2d;stroke:#3c4d70;stroke-width:1.5;rx:18}.k{fill:#7ee787;font:700 12px system-ui,sans-serif;letter-spacing:.08em}.h{fill:#f2f6ff;font:700 18px system-ui,sans-serif}.p{fill:#b9c7dc;font:500 12px system-ui,sans-serif}.line{stroke:#58a6ff;stroke-width:2;opacity:.55}</style>',
        '<rect class="bg" width="1200" height="720"/>',
        '<text class="title" x="55" y="64">Pocket Lab Lite Security Atlas</text>',
        '<text class="sub" x="55" y="92">Architecture is the map. The Atlas is a deterministic security projection — never live monitoring.</text>',
    ]
    positions = [(55,135),(420,135),(785,135),(55,390),(420,390),(785,390)]
    for (label, kicker, description), (x, y) in zip(cards, positions):
        parts.append(f'<rect class="card" x="{x}" y="{y}" width="320" height="190"/>')
        parts.append(f'<text class="k" x="{x+24}" y="{y+38}">{_esc(kicker)}</text>')
        parts.append(f'<text class="h" x="{x+24}" y="{y+72}">{_esc(label)}</text>')
        words = str(description or "").split()
        lines: list[str] = []
        current: list[str] = []
        for word in words:
            if len(" ".join(current + [word])) > 40 and current:
                lines.append(" ".join(current)); current = [word]
            else:
                current.append(word)
        if current: lines.append(" ".join(current))
        for offset, line in enumerate(lines[:4]):
            parts.append(f'<text class="p" x="{x+24}" y="{y+108+offset*22}">{_esc(line)}</text>')
    parts.append('<path class="line" d="M 375 230 L 420 230 M 740 230 L 785 230 M 375 485 L 420 485 M 740 485 L 785 485"/>')
    parts.append('<text class="sub" x="55" y="665">Canonical source → deterministic projection → human review. No probabilistic scoring, exploit prediction, runtime polling or automatic attack-path invention.</text>')
    parts.append('</svg>\n')
    return ''.join(parts)
