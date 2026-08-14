#!/usr/bin/env python3
"""Deterministic Pocket Lab Lite Security Poster projection.

This module is presentation-only. It consumes the already-enriched canonical threat model and
Security Atlas projection and emits static, sanitized poster/catalog views. It never captures
runtime, polls services, calls NATS/FastAPI, runs scanners, invents topology, scores risk, or
changes canonical security decisions.
"""
from __future__ import annotations

import html
import json
import re
from collections import defaultdict
from typing import Any, Iterable

STRIDE = [
    "Spoofing",
    "Tampering",
    "Repudiation",
    "Information Disclosure",
    "Denial of Service",
    "Elevation of Privilege",
]

PRESENTATION_MODES = ["understand", "threats", "controls"]

PRIVATE_PROJECTION = re.compile(
    r"(?:/home/[^/\s]+|/data/data/com\.termux/files/(?:home|usr)|[A-Za-z]:\\Users\\|nats://[^\s]+@)",
    re.I,
)
SECRET_PROJECTION = re.compile(
    r"(?:BEGIN [A-Z ]*PRIVATE KEY|(?:password|passwd|token|secret|api[_-]?key|credential|authorization)\s*[=:]\s*[^\s,}\]]{6,})",
    re.I,
)

# Coordinates are presentation metadata only. Canonical topology remains owned by the architecture
# model and canonical allowed-flow edges from threat["visualization"]["edges"].
POSTER_LAYOUT = {
    "github-release": (115, 115),
    "release-artifacts": (270, 115),
    "scanner-evidence": (425, 115),
    "private-network": (625, 115),
    "tailscale": (785, 115),
    "browser": (100, 335),
    "caddy": (270, 335),
    "lite-api": (445, 335),
    "nats-jetstream": (620, 335),
    "worker": (795, 335),
    "managed-device": (1040, 245),
    "node-agent": (1040, 375),
    "agent-supervisor": (1040, 505),
    "photoprism": (590, 535),
    "server-host": (780, 535),
    "sqlite": (400, 535),
    "recovery-state": (220, 535),
    "promoted-evidence": (470, 690),
    "documentation": (690, 690),
}

NODE_ROLES = {
    "github-release": "release source",
    "release-artifacts": "release bundle",
    "scanner-evidence": "normalized SBOM / scanner evidence",
    "private-network": "private access boundary",
    "tailscale": "Tailnet transport",
    "browser": "request and presentation",
    "caddy": "same-origin proxy",
    "lite-api": "control authority",
    "nats-jetstream": "message transport",
    "worker": "execution orchestration",
    "managed-device": "joined edge device",
    "node-agent": "device execution",
    "agent-supervisor": "recovery supervision",
    "server-host": "Termux process host",
    "photoprism": "managed app runtime",
    "sqlite": "durable control state",
    "recovery-state": "backup / restore evidence",
    "promoted-evidence": "sanitized canonical evidence",
    "documentation": "static evidence projection",
}

ZONE_SPECS = [
    {"id": "external-release", "label": "External release / supply chain", "x": 35, "y": 35, "w": 500, "h": 155},
    {"id": "private-network", "label": "Private network / Tailnet", "x": 560, "y": 35, "w": 320, "h": 155},
    {"id": "control-plane", "label": "Browser → control API → messaging / execution", "x": 35, "y": 225, "w": 850, "h": 220},
    {"id": "managed-edge", "label": "Managed device / edge", "x": 915, "y": 175, "w": 245, "h": 405},
    {"id": "runtime-state", "label": "Application / host / durable state", "x": 150, "y": 470, "w": 735, "h": 145},
    {"id": "evidence", "label": "Promoted evidence → documentation", "x": 365, "y": 635, "w": 480, "h": 105},
]

CORE_FLOW = {
    ("browser", "caddy"),
    ("caddy", "lite-api"),
    ("lite-api", "nats-jetstream"),
    ("nats-jetstream", "worker"),
    ("worker", "node-agent"),
}

# These lines are rendered only when the exact canonical forbidden-flow statement exists.
# The mapping controls presentation endpoints; it never creates a new forbidden-flow assertion.
FORBIDDEN_VISUALS = {
    "frontend → NATS": ("browser", "nats-jetstream", "Browser → NATS"),
    "frontend → shell": ("browser", "server-host", "Browser → shell"),
    "documentation generator → live runtime": ("documentation", "server-host", "Docs → live runtime"),
    "raw scanner output → MkDocs": ("scanner-evidence", "documentation", "Raw scanner → docs"),
}

CONTROL_LAYOUT = {
    "CTRL-BROWSER-NATS": (160, 405, "NO NATS"),
    "CTRL-BROWSER-SHELL": (255, 405, "NO SHELL"),
    "CTRL-API-CONTROL": (445, 405, "API AUTH"),
    "CTRL-EXECUTION-OWNERS": (795, 405, "EXEC OWN"),
    "CTRL-EVIDENCE-SANITIZE": (465, 745, "SANITIZE"),
    "CTRL-EXPLICIT-PROMOTION": (610, 745, "PROMOTE"),
    "CTRL-SUPPLY-CHAIN": (285, 180, "SUPPLY"),
}


def _esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _unique(values: Iterable[Any]) -> list[str]:
    return sorted({str(value).strip() for value in values if str(value).strip()})


def _table(headers: list[str], rows: Iterable[Iterable[Any]]) -> str:
    def cell(value: Any) -> str:
        if value is None or value == "":
            return "—"
        if isinstance(value, bool):
            return "yes" if value else "no"
        if isinstance(value, (list, tuple, set)):
            value = ", ".join(str(item) for item in value) if value else "—"
        return str(value).replace("\n", " ").replace("|", "\\|")

    rendered = list(rows)
    return "\n".join(
        [
            "| " + " | ".join(headers) + " |",
            "| " + " | ".join("---" for _ in headers) + " |",
            *("| " + " | ".join(cell(item) for item in row) + " |" for row in rendered),
        ]
    ) + "\n"


def threat_model_nav(*, nested: bool = False) -> str:
    prefix = "../" if nested else ""
    links = [
        ("Overview", "../" if nested else "./"),
        ("Architecture & trust zones", f"{prefix}architecture/"),
        ("STRIDE", f"{prefix}stride/"),
        ("Attack paths", f"{prefix}attack-paths/"),
        ("Controls", f"{prefix}controls/"),
        ("Assets & guardrails", f"{prefix}assets-guardrails/"),
        ("Evidence & provenance", f"{prefix}evidence/"),
        ("Security Atlas catalog", f"{prefix}catalog/"),
    ]
    return '<nav class="pl-threat-subnav" aria-label="Threat Model sections">' + "".join(
        f'<a class="pl-intent-link" href="{_esc(href)}">{_esc(label)}</a>' for label, href in links
    ) + "</nav>"


def build_security_poster(threat: dict[str, Any], atlas: dict[str, Any]) -> dict[str, Any]:
    """Build a bounded, deterministic poster projection from canonical/enriched threat data."""
    viz = threat.get("visualization") or {}
    source_nodes = list(viz.get("nodes") or [])
    source_edges = list(viz.get("edges") or [])
    attack_paths = list(threat.get("attack_paths") or viz.get("attack_paths") or [])
    boundaries = {str(row.get("id")): row for row in threat.get("boundaries") or []}
    controls = {str(row.get("id")): row for row in threat.get("controls") or []}

    node_ids = [str(row.get("id")) for row in source_nodes]
    if len(node_ids) != len(set(node_ids)):
        raise ValueError("Security Poster contains duplicate visualization node ids")
    missing_layout = sorted(set(node_ids) - set(POSTER_LAYOUT))
    if missing_layout:
        raise ValueError(f"Security Poster has no bounded presentation coordinates for: {missing_layout}")

    stride_by_boundary: dict[str, set[str]] = defaultdict(set)
    for row in threat.get("threats") or []:
        boundary = str(row.get("boundary") or "")
        stride = str(row.get("stride") or "")
        if boundary and stride:
            stride_by_boundary[boundary].add(stride)

    controls_by_boundary: dict[str, set[str]] = defaultdict(set)
    for cid, row in controls.items():
        for boundary in row.get("boundaries") or []:
            controls_by_boundary[str(boundary)].add(cid)

    nodes = []
    for row in sorted(source_nodes, key=lambda item: str(item.get("id"))):
        node_id = str(row.get("id"))
        boundary = str(row.get("boundary") or "unvalidated")
        x, y = POSTER_LAYOUT[node_id]
        boundary_row = boundaries.get(boundary, {})
        nodes.append(
            {
                "id": node_id,
                "label": str(row.get("label") or node_id),
                "role": NODE_ROLES.get(node_id, "architecture component"),
                "boundary": boundary,
                "architecture_component": str(row.get("architecture_component") or "unvalidated"),
                "posture": str(row.get("posture") or "control-unvalidated"),
                "icon": str(row.get("icon") or "docs.svg"),
                "stride": sorted(stride_by_boundary.get(boundary, set())),
                "controls": sorted(controls_by_boundary.get(boundary, set())),
                "assets": _unique(boundary_row.get("assets") or []),
                "x": x,
                "y": y,
            }
        )

    node_set = set(node_ids)
    edges = []
    for row in sorted(source_edges, key=lambda item: str(item.get("id"))):
        source = str(row.get("from") or "")
        target = str(row.get("to") or "")
        if source not in node_set or target not in node_set:
            raise ValueError(f"Security Poster allowed flow references unknown node: {source} -> {target}")
        edges.append(
            {
                "id": str(row.get("id")),
                "from": source,
                "to": target,
                "label": str(row.get("label") or "modeled flow"),
                "kind": "allowed-flow",
                "core": (source, target) in CORE_FLOW,
            }
        )

    normalized_paths = []
    for row in sorted(attack_paths, key=lambda item: str(item.get("id"))):
        path_nodes = [str(item) for item in row.get("path_nodes") or []]
        unknown = sorted(set(path_nodes) - node_set)
        if unknown:
            raise ValueError(f"Security Poster attack path {row.get('id')} references unknown nodes: {unknown}")
        path_controls = [str(item) for item in row.get("controls") or []]
        missing_controls = sorted(set(path_controls) - set(controls))
        if missing_controls:
            raise ValueError(f"Security Poster attack path {row.get('id')} references unknown controls: {missing_controls}")
        normalized_paths.append(
            {
                "id": str(row.get("id")),
                "name": str(row.get("name") or row.get("id")),
                "path_nodes": path_nodes,
                "stride": _unique(row.get("stride") or []),
                "controls": path_controls,
                "consequences": _unique(row.get("consequences") or []),
                "review_status": str(row.get("review_status") or "human-review-required"),
                "confirmed_exploit": bool(row.get("confirmed_exploit", False)),
            }
        )

    canonical_forbidden: dict[str, set[str]] = defaultdict(set)
    for bid, row in boundaries.items():
        for statement in row.get("forbidden_flows") or []:
            canonical_forbidden[str(statement)].add(bid)
    forbidden = []
    for statement, (source, target, label) in FORBIDDEN_VISUALS.items():
        if statement not in canonical_forbidden:
            continue
        if source not in node_set or target not in node_set:
            raise ValueError(f"Security Poster forbidden-flow visual has unknown endpoint: {statement}")
        forbidden.append(
            {
                "id": "forbidden-" + str(len(forbidden) + 1).zfill(2),
                "statement": statement,
                "from": source,
                "to": target,
                "label": label,
                "boundaries": sorted(canonical_forbidden[statement]),
            }
        )

    poster_controls = []
    for cid, row in sorted(controls.items()):
        if cid not in CONTROL_LAYOUT:
            raise ValueError(f"Security Poster has no bounded shield placement for control {cid}")
        x, y, short = CONTROL_LAYOUT[cid]
        affected_stride = set()
        for boundary in row.get("boundaries") or []:
            affected_stride.update(stride_by_boundary.get(str(boundary), set()))
        poster_controls.append(
            {
                "id": cid,
                "short_label": short,
                "description": str(row.get("description") or "Source-derived security control."),
                "boundaries": _unique(row.get("boundaries") or []),
                "stride": sorted(affected_stride),
                "status": str(row.get("status") or "control-unvalidated"),
                "x": x,
                "y": y,
            }
        )

    poster = {
        "schema_version": "1.0.0",
        "source_model": "contracts/security/threat-model.json",
        "architecture_model": str((threat.get("architecture_integration") or {}).get("canonical_model") or "architecture/metadata/pocket-lab-architecture.json"),
        "architecture_rule": str((threat.get("architecture_integration") or {}).get("rule") or "Security overlays never redefine architecture ownership."),
        "live_monitoring": False,
        "generated_intelligence": "deterministic-presentation-projection-only",
        "layout_engine": "canonical-security-layout-v2",
        "layout_authority": "scripts/docs/enterprise/threat_model_layout.py",
        "presentation_layouts": ["wide", "stacked"],
        "presentation_variants": ["overview", "architecture", "catalog"],
        "presentation_modes": list(PRESENTATION_MODES),
        "stride_lens": list(STRIDE),
        "motion_semantics": [
            "gentle canonical-flow pulse",
            "selected modeled attack-path tracing",
            "selected control halo",
            "focus fade transitions",
        ],
        "zones": list(ZONE_SPECS),
        "nodes": nodes,
        "flows": edges,
        "forbidden_flows": forbidden,
        "controls": poster_controls,
        "attack_paths": normalized_paths,
        "evidence_lineage": list(viz.get("evidence_lineage") or []),
        "atlas_contract": str(atlas.get("source_model") or "contracts/security/threat-model.json"),
        "guardrails": {
            "no_live_runtime": True,
            "no_network_fetch": True,
            "no_synthetic_risk_score": True,
            "sanitized_input_required": True,
            "human_review_required": True,
        },
    }

    serialized_raw = json.dumps(poster, sort_keys=True)
    serialized = serialized_raw.lower()
    for forbidden_key in ("risk_score", "security_score", "last_seen", "live_feed", "active_attack"):
        if f'"{forbidden_key}"' in serialized:
            raise ValueError(f"Security Poster must not emit synthetic/live field {forbidden_key}")
    if PRIVATE_PROJECTION.search(serialized_raw) or SECRET_PROJECTION.search(serialized_raw):
        raise ValueError("Security Poster rejected private-path or secret-like projection content")
    return poster


# Legacy renderer retained only as source-history compatibility. Active generation is bound
# to threat_model_layout.render_security_projection_svg below.
def _render_security_poster_svg_legacy_unused(poster: dict[str, Any]) -> str:
    nodes = {row["id"]: row for row in poster["nodes"]}
    width, height = 1200, 790
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="poster-title poster-desc" class="mode-understand" data-poster-mode="understand">',
        '<title id="poster-title">Pocket Lab Lite Security Architecture Poster</title>',
        '<desc id="poster-desc">Static architecture security overlay showing trust zones, canonical flows, controls, assets, forbidden paths and modeled attack paths. Motion is explanatory and never represents live traffic or an active attack.</desc>',
        '''<defs>
<pattern id="poster-grid" width="28" height="28" patternUnits="userSpaceOnUse"><path d="M28 0H0V28" fill="none" stroke="#93a4bd" stroke-opacity=".07" stroke-width="1"/></pattern>
<marker id="poster-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0L8 4L0 8Z" fill="#4f8bd6"/></marker>
<marker id="forbidden-x" markerWidth="10" markerHeight="10" refX="5" refY="5"><path d="M1 1L9 9M9 1L1 9" stroke="#c94c4c" stroke-width="2"/></marker>
</defs>''',
        '''<style>
.bg{fill:#f5f7fb}.grid{fill:url(#poster-grid)}.title{fill:#172338;font:700 24px system-ui,sans-serif}.subtitle{fill:#53647c;font:500 12px system-ui,sans-serif}.badge{fill:#e7edf7;stroke:#c9d4e5}.badge-text{fill:#34445c;font:700 10px system-ui,sans-serif;letter-spacing:.08em}.zone{stroke-width:1.2;rx:18}.zone--external{fill:#fff8ea;stroke:#e2c27c}.zone--private{fill:#eef7ff;stroke:#9cc6e8}.zone--control{fill:#f1f7ff;stroke:#8bb4df}.zone--edge{fill:#eef9f4;stroke:#8bc8ad}.zone--state{fill:#f7f3fb;stroke:#baa3d5}.zone--evidence{fill:#f3f5f8;stroke:#aab6c7}.zone-title{fill:#44566f;font:700 11px system-ui,sans-serif;letter-spacing:.055em}.node{cursor:pointer;transition:opacity .18s ease}.node rect{fill:#fff;stroke:#8293aa;stroke-width:1.2;rx:13}.node .name{fill:#1e2b40;font:700 12px system-ui,sans-serif}.node .role{fill:#68778c;font:500 9.5px system-ui,sans-serif}.node .cue{font:700 8.5px system-ui,sans-serif}.node[data-state="control-observed"] rect{stroke:#4f9f76}.node[data-state="control-observed"] .cue{fill:#367b59}.node[data-state="evidence-stale"] rect,.node[data-state="control-partial"] rect{stroke:#b4862c}.node[data-state="evidence-stale"] .cue,.node[data-state="control-partial"] .cue{fill:#8a651b}.node[data-state="control-unvalidated"] rect{stroke:#8994a6;stroke-dasharray:4 3}.node[data-state="control-unvalidated"] .cue{fill:#6e7888}.node.is-active rect{stroke-width:3}.node.is-muted,.control.is-muted,.flow.is-muted{opacity:.16}.node.is-filtered-out,.control.is-filtered-out,.attack.is-filtered-out{opacity:.08!important}.flow{fill:none;stroke:#4f8bd6;stroke-width:1.7;opacity:.62;marker-end:url(#poster-arrow)}.flow[data-core="true"]{stroke-width:2.4;stroke-dasharray:3 11;stroke-linecap:round;animation:canonical-flow 8s linear infinite}.flow-label{fill:#74839a;font:600 8.5px system-ui,sans-serif}.attack{fill:none;stroke:#c94c4c;stroke-width:4;stroke-dasharray:10 8;opacity:0;pointer-events:none}.attack.is-active{opacity:.9;animation:attack-trace 1.5s linear infinite}.forbidden{opacity:0;pointer-events:none}.show-guardrails .forbidden{opacity:.82}.forbidden path{fill:none;stroke:#c94c4c;stroke-width:1.8;stroke-dasharray:5 5;marker-end:url(#forbidden-x)}.forbidden text{fill:#a63f3f;font:700 8.5px system-ui,sans-serif}.control{cursor:pointer;transition:opacity .18s ease}.control .shield{fill:#e9f6ef;stroke:#4d9a72;stroke-width:1.5}.control text{fill:#326e51;font:700 8px system-ui,sans-serif}.control.is-active .shield{stroke-width:4;filter:none;animation:control-halo .65s ease-out 1}.mode-understand .control{opacity:.72}.mode-threats .control{opacity:.38}.mode-threats .node[data-threat-count="0"]{opacity:.42}.mode-controls .flow{opacity:.22}.mode-controls .node{opacity:.66}.mode-controls .control{opacity:1}.motion-paused .flow,.motion-paused .attack,.motion-paused .control .shield{animation-play-state:paused!important}@keyframes canonical-flow{to{stroke-dashoffset:-56}}@keyframes attack-trace{to{stroke-dashoffset:-36}}@keyframes control-halo{0%{stroke-width:1.5}45%{stroke-width:5}100%{stroke-width:4}}@media(prefers-color-scheme:dark){.bg{fill:#0d1422}.grid{opacity:.55}.title{fill:#f2f6ff}.subtitle{fill:#aebbd0}.badge{fill:#19263a;stroke:#35475f}.badge-text{fill:#d8e2f1}.zone--external{fill:#241f16;stroke:#6f5a2b}.zone--private{fill:#112235;stroke:#315c7d}.zone--control{fill:#101f31;stroke:#31597d}.zone--edge{fill:#10271e;stroke:#366d54}.zone--state{fill:#20182a;stroke:#5f4778}.zone--evidence{fill:#171d27;stroke:#4b586c}.zone-title{fill:#b9c7dc}.node rect{fill:#151f2e;stroke:#71839c}.node .name{fill:#eef4ff}.node .role{fill:#aebbd0}.flow-label{fill:#9fb0c8}}@media(prefers-reduced-motion:reduce){.flow,.attack,.node,.control,.control .shield{animation:none!important;transition:none!important}}@media print{.bg{fill:#fff}.grid{display:none}.flow[data-core="true"]{stroke-dasharray:none;animation:none}.attack{display:none}.forbidden{opacity:.75}.node,.control{transition:none}}
</style>''',
        '<rect class="bg" width="1200" height="790"/><rect class="grid" width="1200" height="790"/>',
        '<text class="title" x="38" y="31">Pocket Lab Lite · Security Architecture</text>',
        '<text class="subtitle" x="38" y="51">Static model · canonical architecture overlay · promoted/sanitized evidence · human review required</text>',
        '<rect class="badge" x="1010" y="18" width="150" height="30" rx="15"/><text class="badge-text" x="1085" y="37" text-anchor="middle">NOT LIVE MONITORING</text>',
    ]

    zone_class = {
        "external-release": "external",
        "private-network": "private",
        "control-plane": "control",
        "managed-edge": "edge",
        "runtime-state": "state",
        "evidence": "evidence",
    }
    for zone in poster["zones"]:
        cls = zone_class.get(zone["id"], "evidence")
        parts.append(
            f'<g data-zone="{_esc(zone["id"])}"><rect class="zone zone--{cls}" x="{zone["x"]}" y="{zone["y"]}" width="{zone["w"]}" height="{zone["h"]}"/>'
            f'<text class="zone-title" x="{zone["x"]+16}" y="{zone["y"]+22}">{_esc(zone["label"])}</text></g>'
        )

    for edge in poster["flows"]:
        source, target = nodes[edge["from"]], nodes[edge["to"]]
        parts.append(
            f'<path class="flow" data-flow="{_esc(edge["id"])}" data-from="{_esc(edge["from"])}" data-to="{_esc(edge["to"])}" data-core="{str(bool(edge["core"])).lower()}" '
            f'd="M {source["x"]} {source["y"]} L {target["x"]} {target["y"]}"/>'
        )
        if edge["core"]:
            mx, my = (source["x"] + target["x"]) / 2, (source["y"] + target["y"]) / 2
            parts.append(f'<text class="flow-label" x="{mx}" y="{my-8}" text-anchor="middle">{_esc(edge["label"])}</text>')

    for row in poster["forbidden_flows"]:
        source, target = nodes[row["from"]], nodes[row["to"]]
        mx, my = (source["x"] + target["x"]) / 2, (source["y"] + target["y"]) / 2
        parts.append(
            f'<g class="forbidden" data-forbidden="{_esc(row["statement"])}"><path d="M {source["x"]} {source["y"]} L {target["x"]} {target["y"]}"/>'
            f'<text x="{mx}" y="{my-7}" text-anchor="middle">{_esc(row["label"])}</text></g>'
        )

    for path in poster["attack_paths"]:
        points = " ".join(f'{nodes[node]["x"]},{nodes[node]["y"]}' for node in path["path_nodes"])
        parts.append(
            f'<polyline class="attack" data-attack-path="{_esc(path["id"])}" data-stride="{_esc(" ".join(path["stride"]))}" '
            f'data-nodes="{_esc(" ".join(path["path_nodes"]))}" data-controls="{_esc(" ".join(path["controls"]))}" points="{points}"/>'
        )

    for row in poster["nodes"]:
        icon = f'../../../assets/diagrams/production/icons/{row["icon"]}'
        threat_count = len(row["stride"])
        control_label = f'{len(row["controls"])} control' + ("" if len(row["controls"]) == 1 else "s")
        asset_label = f'{len(row["assets"])} asset' + ("" if len(row["assets"]) == 1 else "s")
        parts.append(
            f'<g class="node" data-node="{_esc(row["id"])}" data-boundary="{_esc(row["boundary"])}" data-state="{_esc(row["posture"])}" '
            f'data-architecture-component="{_esc(row["architecture_component"])}" data-stride="{_esc(" ".join(row["stride"]))}" data-threat-count="{threat_count}" data-assets="{_esc(" | ".join(row["assets"]))}" '
            f'tabindex="0" role="button" aria-label="{_esc(row["label"])}; {_esc(row["role"])}; {_esc(row["posture"])}; {control_label}; {asset_label}">'
            f'<rect x="{row["x"]-70}" y="{row["y"]-37}" width="140" height="74"/>'
            f'<image href="{icon}" x="{row["x"]-59}" y="{row["y"]-22}" width="25" height="25"/>'
            f'<text class="name" x="{row["x"]-27}" y="{row["y"]-10}">{_esc(row["label"])}</text>'
            f'<text class="role" x="{row["x"]-27}" y="{row["y"]+7}">{_esc(row["role"])}</text>'
            f'<text class="cue" x="{row["x"]-59}" y="{row["y"]+27}">{_esc(row["posture"])} · {control_label} · {asset_label}</text></g>'
        )

    for row in poster["controls"]:
        parts.append(
            f'<g class="control" data-control="{_esc(row["id"])}" data-boundaries="{_esc(" ".join(row["boundaries"]))}" data-threats="{_esc(" ".join(row["stride"]))}" '
            f'data-stride="{_esc(" ".join(row["stride"]))}" tabindex="0" role="button" aria-label="Control {_esc(row["id"])}; {_esc(row["description"])}; {_esc(row["status"])}">'
            f'<path class="shield" d="M {row["x"]} {row["y"]-12} l 11 4 v 9 c 0 9 -7 14 -11 16 c -4 -2 -11 -7 -11 -16 v -9 z"/>'
            f'<text x="{row["x"]+16}" y="{row["y"]+4}">{_esc(row["short_label"])}</text></g>'
        )

    parts.append('<text class="subtitle" x="38" y="775">Modeled flow — not live traffic · motion explains saved relationships only: canonical-flow pulse, selected path tracing, selected control halo, and focus fades.</text>')
    parts.append('</svg>\n')
    return "".join(parts)


def render_threat_model_overview(threat: dict[str, Any], poster: dict[str, Any]) -> str:
    summary = (threat.get("visualization") or {}).get("posture_summary") or {}
    posture = threat.get("production_posture") or {}
    posture_states = summary.get("posture_states") or {}
    evidence_gaps = sum(int(posture_states.get(key, 0) or 0) for key in ("control-partial", "control-unvalidated", "evidence-stale"))

    body = "# Threat Model\n\n"
    body += '<div class="pl-page-lede"><strong>Pocket Lab Lite security architecture, explained as a saved model.</strong><p>The poster overlays trust zones, threats, controls, assets and promoted evidence on the canonical architecture. It is not a live monitor, attack detector or risk-scoring dashboard.</p></div>\n\n'
    body += threat_model_nav() + "\n\n"
    body += '<div class="pl-kpi-grid pl-threat-kpis">'
    for label, value in [
        ("Trust boundaries", summary.get("trust_boundaries", len(threat.get("boundaries") or []))),
        ("STRIDE candidates", summary.get("stride_candidates", len(threat.get("threats") or []))),
        ("Security controls", summary.get("controls", len(threat.get("controls") or []))),
        ("Reviewed attack paths", summary.get("attack_paths", len(threat.get("attack_paths") or []))),
        ("Evidence gaps", evidence_gaps),
        ("Human review", "Required"),
    ]:
        body += f'<div class="pl-kpi"><span>{_esc(label)}</span><strong>{_esc(value)}</strong><small>saved canonical projection</small></div>'
    body += "</div>\n\n"
    body += f'Promoted runtime release: **{posture.get("promoted_runtime_release", "unobserved")}** · authority: **{posture.get("authority", "promoted/canonical evidence only")}**.\n\n'

    body += '<section id="security-atlas" class="pl-threat-poster" data-pl-threat-poster="true">\n'
    body += '<div class="pl-threat-poster-head"><div><span class="pl-card-kicker">Security Architecture Poster</span><h2>How control moves — and where trust changes</h2><p>Architecture is the map. Security annotations explain the saved model without redefining topology ownership.</p></div><span class="pl-threat-static-badge">Static model · not live</span></div>\n'
    body += '<div class="pl-threat-poster-controls">\n'
    body += '<div class="pl-threat-mode-group" role="group" aria-label="Threat Model presentation mode"><span>View</span><button type="button" class="md-button md-button--primary" data-threat-poster-mode="understand" aria-pressed="true">Understand</button><button type="button" class="md-button" data-threat-poster-mode="threats" aria-pressed="false">Threats</button><button type="button" class="md-button" data-threat-poster-mode="controls" aria-pressed="false">Controls</button></div>\n'
    body += '<div class="pl-threat-stride-lens" role="group" aria-label="STRIDE exploration lens"><span>STRIDE lens</span><button type="button" class="md-button md-button--primary" data-stride-lens="all" aria-pressed="true">All</button>'
    stride_short = {"Spoofing": "S", "Tampering": "T", "Repudiation": "R", "Information Disclosure": "I", "Denial of Service": "D", "Elevation of Privilege": "E"}
    for name in STRIDE:
        body += f'<button type="button" class="md-button" data-stride-lens="{_esc(name)}" aria-pressed="false" title="{_esc(name)}">{stride_short[name]}</button>'
    body += '</div>\n'
    body += '<div class="pl-threat-poster-actions"><button type="button" class="md-button" data-threat-guardrails="toggle" aria-pressed="false">Show guardrails</button><button type="button" class="md-button" data-threat-motion="toggle">Pause animation</button></div>\n'
    body += '</div>\n'
    body += '<div class="pl-threat-poster-layout"><div class="pl-threat-poster-canvas" role="region" aria-label="Pocket Lab Lite Security Architecture Poster" tabindex="0"><object id="pl-threat-model-svg" data-pl-base-src="../../assets/enterprise/threat-model.svg" type="image/svg+xml" aria-label="Interactive Pocket Lab Lite Security Architecture Poster"><img data-pl-base-src="../../assets/enterprise/threat-model.svg" alt="Pocket Lab Lite Security Architecture Poster"></object><p>Blue routes are modeled allowed/control flows. Red appears only for a selected modeled attack path. Shield markers are controls. Motion never means live traffic.</p></div><aside class="pl-threat-detail pl-threat-poster-detail" id="threat-selection" aria-live="polite"><span class="pl-card-kicker">Select the poster</span><strong>Start with the architecture story</strong><p>Choose a component or shield to focus the saved model. For full source/evidence detail, open the Security Atlas catalog.</p><a class="pl-intent-link" href="catalog/">Open Security Atlas catalog →</a></aside></div>\n'
    body += '</section>\n\n'

    body += '## How Pocket Lab protects control\n\n'
    story = [
        ("1", "Browser asks", "The PWA requests operations. It does not talk directly to NATS, execute shell commands or own backend secrets."),
        ("2", "FastAPI decides", "Caddy keeps the browser same-origin and FastAPI remains the control authority for /api/lite/* operations."),
        ("3", "Messaging delivers", "NATS/JetStream carries modeled command and event flows; it is not a browser API."),
        ("4", "Agents execute", "Workers, node agents and the separate supervisor own execution, reconnect and recovery semantics."),
        ("5", "Evidence returns", "Sanitized events, health and promoted evidence project back through FastAPI and static documentation."),
    ]
    body += '<div class="pl-threat-story-grid">' + "".join(
        f'<article><span>{step}</span><h3>{_esc(title)}</h3><p>{_esc(text)}</p></article>' for step, title, text in story
    ) + '</div>\n\n'

    body += '## Explore the model\n\n<div class="pl-threat-explore-grid">'
    cards = [
        ("Architecture & trust zones", "See how the canonical topology is partitioned into Pocket Lab-specific trust zones.", "architecture/"),
        ("STRIDE lens", "Understand each STRIDE category and where candidates apply without treating candidates as exploits.", "stride/"),
        ("Modeled attack paths", "Trace AP-01 through AP-08 as reviewed scenarios, with controls and consequences.", "attack-paths/"),
        ("Controls", "Inspect guardrails such as browser→NATS prohibition, API authority, execution ownership and evidence promotion.", "controls/"),
        ("Assets & guardrails", "See what is protected and which architectural paths are explicitly forbidden.", "assets-guardrails/"),
        ("Evidence & provenance", "See what evidence supports the saved posture and which gaps still require human review.", "evidence/"),
        ("Security Atlas catalog", "Open the full expert catalog for threats, systems, attack surface, controls and evidence.", "catalog/"),
    ]
    for title, text, href in cards:
        body += f'<a class="pl-threat-explore-card pl-intent-link" href="{_esc(href)}"><span class="pl-card-kicker">Explore</span><strong>{_esc(title)}</strong><small>{_esc(text)}</small></a>'
    body += '</div>\n\n'

    body += '## Model provenance\n\n<div class="pl-threat-provenance-strip">'
    provenance = [
        ("Architecture", "canonical architecture"),
        ("Threats", "source-derived STRIDE model"),
        ("Controls", "canonical security controls"),
        ("Runtime context", "promoted sanitized evidence"),
        ("Supply chain", "normalized scanner / SBOM evidence"),
        ("Judgement", "human review required"),
    ]
    for label, value in provenance:
        body += f'<div><span>{_esc(label)}</span><strong>{_esc(value)}</strong></div>'
    body += '</div>\n\n'
    body += '!!! info "Static assessment, not monitoring"\n    Animation communicates modeled relationships in saved information. The page does not poll runtime, GitHub, scanners, FastAPI or NATS, and it does not claim that a modeled attack is occurring.\n'
    return body


def render_threat_model_subpages(threat: dict[str, Any], poster: dict[str, Any]) -> dict[str, dict[str, str]]:
    boundaries = list(threat.get("boundaries") or [])
    controls = list(threat.get("controls") or [])
    paths = list(threat.get("attack_paths") or [])
    framework = threat.get("framework") or {}
    posture = threat.get("production_posture") or {}
    nav = threat_model_nav(nested=True)

    architecture = "# Architecture & trust zones\n\n" + nav + "\n\n"
    architecture += '<div class="pl-page-lede"><strong>The canonical architecture remains the map.</strong><p>This page explains where trust changes. The security layer annotates architecture component IDs and canonical flows; it does not create a second topology.</p></div>\n\n'
    architecture += '## Threat Model Diagram\n\n'
    architecture += 'This is a security overlay on the [canonical Pocket Lab Lite Architecture](../../production/architecture/index.md). Architecture continues to own topology and component ownership; this page only adds threat-model context.\n\n'
    architecture += '<figure class="pl-threat-detail-diagram"><picture><source media="(max-width: 44.9844em)" srcset="../../../assets/enterprise/threat-model-detail-mobile.svg"><img src="../../../assets/enterprise/threat-model-detail.svg" alt="Detailed Pocket Lab Lite threat architecture overlay" loading="eager" decoding="async"></picture><figcaption>Detailed source-derived architecture overlay. Open the Overview for the museum-style Security Poster.</figcaption></figure>\n\n'
    architecture += "## Trust zones\n\n" + _table(
        ["Boundary", "Assets", "Controls", "Review"],
        [[row.get("label"), row.get("assets"), row.get("controls"), row.get("review_status")] for row in boundaries],
    )
    architecture += "\n## Boundary pages\n\n" + "\n".join(
        f'- [{row.get("label")}]({row.get("id")}.md)' for row in boundaries
    ) + "\n\n"
    architecture += "## Architecture ownership\n\n" + str((threat.get("architecture_integration") or {}).get("rule") or "Security overlays never redefine topology ownership.") + "\n"

    stride = "# STRIDE exploration lens\n\n" + nav + "\n\n"
    stride += '<div class="pl-page-lede"><strong>STRIDE is a review lens, not a vulnerability verdict.</strong><p>Categories are applied only where the canonical model says they apply. A candidate does not mean an exploit is confirmed.</p></div>\n\n'
    stride += "## Threat framework\n\n"
    stride += f'Primary framework: **{framework.get("primary", "STRIDE")}**. Reference mapping: **{", ".join(framework.get("reference_mappings") or []) or "source-derived"}**.\n\n'
    stride += "## STRIDE definitions\n\n" + _table(
        ["STRIDE", "Pocket Lab interpretation"],
        [[name, text] for name, text in (framework.get("definitions") or {}).items()],
    )
    boundary_threats: dict[str, set[str]] = defaultdict(set)
    for row in threat.get("threats") or []:
        boundary_threats[str(row.get("boundary"))].add(str(row.get("stride")))
    stride += "\n## Boundary coverage\n\n" + _table(
        ["Boundary", *[name.split()[0] if name != "Information Disclosure" else "Disclosure" for name in STRIDE]],
        [[row.get("label"), *[("✓" if name in boundary_threats.get(str(row.get("id")), set()) else "—") for name in STRIDE]] for row in boundaries],
    )
    stride += "\n## How Pocket Lab applies STRIDE\n\n" + "\n".join(
        f'{index}. {item}' for index, item in enumerate(framework.get("application") or [], 1)
    ) + "\n"
    stride += "\n## Three truth layers\n\n" + _table(
        ["Layer", "Question", "Authority"],
        [
            [row.get("id"), row.get("question"), row.get("authority")]
            for row in threat.get("truth_layers") or []
        ],
    )
    stride += '\n!!! info "Human review remains authoritative"\n    Exploitability, mitigation adequacy, residual risk and risk acceptance are not inferred by the poster.\n'

    attack = "# Modeled attack paths\n\n" + nav + "\n\n"
    attack += '<div class="pl-page-lede"><strong>Trace reviewed scenarios through the saved architecture.</strong><p>Attack paths are modeled review paths, never confirmed exploits or live detections. Use semantic links to open the exact path in the Security Atlas.</p></div>\n\n'
    attack += '<div class="pl-threat-path-grid">'
    for row in paths:
        query = f'../catalog/?atlas-attack-path={row.get("id")}#security-atlas'
        attack += (
            f'<a class="pl-threat-path-card pl-intent-link" href="{_esc(query)}"><span class="pl-card-kicker">{_esc(row.get("id"))}</span>'
            f'<strong>{_esc(row.get("name"))}</strong><small>{_esc(" · ".join(row.get("stride") or []))}</small>'
            f'<p>{_esc(" → ".join(row.get("path_nodes") or []))}</p></a>'
        )
    attack += '</div>\n\n## Review table\n\n' + _table(
        ["Path", "Entry", "Target", "STRIDE", "Controls", "Consequences", "Review"],
        [[row.get("id"), row.get("entry_point"), row.get("target"), row.get("stride"), row.get("controls"), row.get("consequences"), row.get("review_status")] for row in paths],
    )

    controls_page = "# Security controls\n\n" + nav + "\n\n"
    controls_page += '<div class="pl-page-lede"><strong>Controls are architectural guardrails with evidence, not posture scores.</strong><p>Each control shows where it is used, what it mitigates and what can happen if it fails. Prevention is not claimed unless separate evidence supports it.</p></div>\n\n<div class="pl-threat-control-grid">'
    for row in controls:
        query = f'../catalog/?atlas-control={row.get("id")}#security-atlas'
        controls_page += (
            f'<a class="pl-threat-control-card pl-intent-link" href="{_esc(query)}"><span class="pl-threat-shield" aria-hidden="true">◇</span>'
            f'<div><span class="pl-card-kicker">{_esc(row.get("status"))}</span><strong>{_esc(row.get("id"))}</strong><p>{_esc(row.get("description"))}</p>'
            f'<small>Used at: {_esc(", ".join(row.get("where_used") or row.get("boundaries") or []))}</small></div></a>'
        )
    controls_page += '</div>\n\n## Control evidence\n\n' + _table(
        ["Control", "Where used", "Effect", "Current evidence", "If it fails"],
        [[row.get("id"), row.get("where_used"), row.get("effect"), row.get("status"), row.get("failure_consequences")] for row in controls],
    )
    boundary_ids = [str(row.get("id")) for row in boundaries]
    controls_page += "\n## Where controls are used\n\n" + _table(
        ["Control", *boundary_ids],
        [
            [
                row.get("id"),
                *[
                    "✓"
                    if boundary in (row.get("boundaries") or row.get("where_used") or [])
                    else "—"
                    for boundary in boundary_ids
                ],
            ]
            for row in controls
        ],
    )

    guardrails = "# Assets & architectural guardrails\n\n" + nav + "\n\n"
    guardrails += '<div class="pl-page-lede"><strong>What Pocket Lab protects — and the paths architecture forbids.</strong><p>Assets come directly from canonical boundary metadata. Forbidden paths are rendered only when the exact canonical statement exists.</p></div>\n\n'
    guardrails += "## Protected assets\n\n" + _table(
        ["Boundary", "Assets", "Data classification"],
        [[row.get("label"), row.get("assets"), row.get("data_classifications")] for row in boundaries],
    )
    all_forbidden: dict[str, set[str]] = defaultdict(set)
    for row in boundaries:
        for item in row.get("forbidden_flows") or []:
            all_forbidden[str(item)].add(str(row.get("id")))
    guardrails += "\n## Forbidden paths\n\n" + _table(
        ["Canonical guardrail", "Declared at boundaries"],
        [[statement, sorted(boundary_ids)] for statement, boundary_ids in sorted(all_forbidden.items())],
    )
    guardrails += "\n## Poster guardrail overlay\n\nThe Overview **Show guardrails** control reveals only forbidden paths that have an explicit visual mapping and an exact canonical forbidden-flow statement. No missing path is inferred.\n"

    evidence = "# Evidence & provenance\n\n" + nav + "\n\n"
    evidence += '<div class="pl-page-lede"><strong>Evidence explains why the saved model says what it says.</strong><p>Promoted runtime, dependency, scanner, release and security-control evidence are provenance inputs. They are not a live feed and do not convert modeled scenarios into observed attacks.</p></div>\n\n'
    evidence += "## Evidence lineage\n\n" + _table(
        ["Stage", "Canonical/promoted source"],
        [[row.get("label"), row.get("source")] for row in poster.get("evidence_lineage") or []],
    )
    evidence += "\n## Current promoted evidence posture\n\n" + _table(
        ["Signal", "Boundary", "State", "Observed", "Source"],
        [[row.get("signal"), row.get("boundary"), row.get("state"), row.get("observed"), row.get("source")] for row in posture.get("signals") or []],
    )
    evidence += "\n## Truth boundary\n\n- Canonical architecture owns topology.\n- Canonical threat metadata owns threats, controls and review status.\n- Promoted sanitized evidence can inform posture.\n- MkDocs only renders static projections.\n- Human review owns exploitability, residual risk and acceptance.\n"

    evidence += "\n## What this threat model does not do\n\n"
    exclusions = list(threat.get("exclusions") or [])
    evidence += (
        "\n".join(f"- {item}" for item in exclusions)
        if exclusions
        else "- No additional canonical exclusions are recorded."
    )
    evidence += "\n"

    evidence += "\n## Consequences of not threat modelling\n\n"
    consequences = list(threat.get("consequences_without_model") or [])
    evidence += (
        "\n".join(f"- {item}" for item in consequences)
        if consequences
        else "- No additional canonical consequences are recorded."
    )
    evidence += "\n"

    evidence += "\n## Human review required\n\n"
    review = list(threat.get("human_review_required") or [])
    evidence += (
        "\n".join(f"- {item}" for item in review)
        if review
        else "- Exploitability, residual risk and risk acceptance require human review."
    )
    evidence += "\n"

    return {
        "architecture": {"title": "Architecture & Trust Zones", "description": "Pocket Lab-specific trust zones over the canonical architecture.", "body": architecture},
        "stride": {"title": "STRIDE Lens", "description": "STRIDE categories and boundary coverage without exploit claims.", "body": stride},
        "attack-paths": {"title": "Modeled Attack Paths", "description": "Reviewed static attack-path scenarios and semantic deep links.", "body": attack},
        "controls": {"title": "Security Controls", "description": "Source-derived control catalog with coverage and failure consequences.", "body": controls_page},
        "assets-guardrails": {"title": "Assets & Guardrails", "description": "Protected assets and canonical forbidden architecture paths.", "body": guardrails},
        "evidence": {"title": "Evidence & Provenance", "description": "Promoted/canonical evidence lineage for the saved threat model.", "body": evidence},
    }


# Sole production renderer for Overview, Architecture and Catalog. The normalized poster
# projection is the shared input; variant/layout only change deterministic presentation.
from threat_model_layout import render_security_projection_svg as _render_security_projection_svg


def render_security_poster_svg(
    poster: dict[str, Any], *, variant: str = "overview", layout: str = "wide"
) -> str:
    return _render_security_projection_svg(poster, variant=variant, layout=layout)


# Enterprise Threat Model page extension. Keep canonical threat-boundary ownership unchanged;
# the evidence lane below is explicitly a presentation/evidence projection zone.
_render_threat_model_overview_enterprise_base = render_threat_model_overview
_render_threat_model_subpages_enterprise_base = render_threat_model_subpages


def render_threat_model_overview(threat: dict[str, Any], poster: dict[str, Any]) -> str:
    body = _render_threat_model_overview_enterprise_base(threat, poster)
    old = '<button type="button" class="md-button" data-threat-motion="toggle">Pause animation</button></div>'
    new = '<button type="button" class="md-button" data-threat-motion="toggle">Pause animation</button><a class="md-button" data-threat-fullscreen="open" href="?poster-fullscreen=1#security-atlas" target="_blank" rel="noopener noreferrer">Full screen</a></div>'
    if body.count(old) != 1:
        raise ValueError("Threat Model poster action fence drifted")
    return body.replace(old, new, 1)


def render_threat_model_subpages(threat: dict[str, Any], poster: dict[str, Any]) -> dict[str, dict[str, str]]:
    pages = _render_threat_model_subpages_enterprise_base(threat, poster)
    architecture = str((pages.get("architecture") or {}).get("body") or "")
    marker = "\n\n## Architecture ownership"
    evidence_link = "\n- [Promoted evidence → documentation](evidence-zone.md) — presentation evidence zone; this does not create a new canonical trust boundary.\n"
    if architecture.count(marker) != 1:
        raise ValueError("Threat Model Architecture boundary-page fence drifted")
    pages["architecture"]["body"] = architecture.replace(marker, evidence_link + marker, 1)

    controls = list(threat.get("controls") or [])
    evidence_node_ids = {"promoted-evidence", "documentation"}
    evidence_nodes = [row for row in poster.get("nodes") or [] if str(row.get("id")) in evidence_node_ids]
    evidence_assets = _unique(asset for row in evidence_nodes for asset in (row.get("assets") or []))
    evidence_control_ids = _unique(control for row in evidence_nodes for control in (row.get("controls") or []))
    control_index = {str(row.get("id")): row for row in controls}
    evidence_flows = [
        row for row in poster.get("flows") or []
        if str(row.get("from")) in evidence_node_ids or str(row.get("to")) in evidence_node_ids
    ]
    nav = threat_model_nav(nested=True)
    evidence_zone = "# Promoted evidence → documentation\n\n" + nav + "\n\n"
    evidence_zone += '<div class="pl-page-lede"><strong>Saved evidence enters documentation through an explicit projection zone.</strong><p>This page explains the visual evidence lane in the Security Architecture Poster. It is a presentation/evidence zone backed by canonical and promoted inputs; it is not promoted into a new canonical threat boundary.</p></div>\n\n'
    evidence_zone += "## Boundary\n\n**Projection zone:** Promoted evidence → documentation. Canonical threat-boundary ownership remains unchanged.\n\n"
    evidence_zone += "## Assets\n\n" + ("\n".join(f"- {item}" for item in evidence_assets) if evidence_assets else "- unvalidated") + "\n\n"
    evidence_zone += "## Actors & components\n\n" + _table(
        ["Component", "Role", "Architecture component", "Canonical boundary"],
        [[row.get("label"), row.get("role"), row.get("architecture_component"), row.get("boundary")] for row in evidence_nodes],
    )
    evidence_zone += "\n## Controls\n\n" + _table(
        ["Control", "Description", "Status"],
        [[cid, (control_index.get(cid) or {}).get("description"), (control_index.get(cid) or {}).get("status")] for cid in evidence_control_ids],
    )
    evidence_zone += "\n## Data flows\n\n" + _table(
        ["Flow", "From", "To", "Meaning"],
        [[row.get("id"), row.get("from"), row.get("to"), row.get("label")] for row in evidence_flows],
    )
    evidence_zone += "\n## Evidence lineage\n\n" + _table(
        ["Stage", "Canonical/promoted source"],
        [[row.get("label"), row.get("source")] for row in poster.get("evidence_lineage") or []],
    )
    evidence_zone += "\n## Guardrails\n\n- Documentation does not capture or poll live runtime.\n- Raw scanner output does not become documentation truth.\n- Runtime/scanner evidence must be sanitized and explicitly promoted before canonical documentation ingestion.\n\n"
    evidence_zone += "## Review status\n\nHuman review remains required for evidence adequacy, exploitability, residual risk and acceptance.\n"
    pages["evidence-zone"] = {
        "title": "Promoted evidence → documentation",
        "description": "Projection-zone detail for promoted evidence flowing into static documentation without creating a new canonical trust boundary.",
        "body": evidence_zone,
    }
    return pages


# Threat Model boundary-detail polish. Canonical boundaries remain unchanged; this layer
# only aligns generated presentation/anatomy and keeps the evidence lane explicitly
# labeled as a projection zone.
_threat_model_nav_boundary_polish_base = threat_model_nav
_render_threat_model_subpages_boundary_polish_base = render_threat_model_subpages


def threat_model_nav(*, nested: bool = False) -> str:
    prefix = "../" if nested else ""
    links = [
        ("Overview", "../" if nested else "./"),
        ("Architecture & trust zones", f"{prefix}architecture/"),
        ("STRIDE", f"{prefix}stride/"),
        ("Attack paths", f"{prefix}attack-paths/"),
        ("Controls", f"{prefix}controls/"),
        ("Assets & guardrails", f"{prefix}assets-guardrails/"),
        ("Evidence & provenance", f"{prefix}evidence/"),
        ("Promoted evidence → documentation", f"{prefix}evidence-zone/"),
        ("Security Atlas catalog", f"{prefix}catalog/"),
    ]
    return '<nav class="pl-threat-subnav" aria-label="Threat Model sections">' + "".join(
        f'<a class="pl-intent-link" href="{_esc(href)}">{_esc(label)}</a>' for label, href in links
    ) + "</nav>"


def _detail_list(values: Iterable[Any], empty: str) -> str:
    items = [str(value).strip() for value in values if str(value).strip()]
    return "\n".join(f"- {_esc(item)}" for item in items) if items else f"- {_esc(empty)}"


def _detail_summary(*, kind: str, assets: int, controls: int, review: str) -> str:
    return (
        '<div class="pl-threat-boundary-summary" aria-label="Threat Model detail summary">'
        f'<article><span>Type</span><strong>{_esc(kind)}</strong></article>'
        f'<article><span>Assets</span><strong>{assets}</strong></article>'
        f'<article><span>Controls</span><strong>{controls}</strong></article>'
        f'<article><span>Review</span><strong>{_esc(review)}</strong></article>'
        "</div>\n\n"
    )


def render_threat_boundary_page(
    boundary: dict[str, Any],
    boundary_threats: list[dict[str, Any]],
    *,
    table,
) -> str:
    """Render one canonical trust-boundary page with the shared enterprise detail anatomy."""
    label = str(boundary.get("label") or boundary.get("id") or "Threat boundary")
    assets = list(boundary.get("assets") or [])
    controls = list(boundary.get("controls") or [])
    review = str(boundary.get("review_status") or "human-review-required")
    body = f"# {label}\n\n{threat_model_nav(nested=True)}\n\n"
    body += (
        '<div class="pl-page-lede pl-threat-boundary-lede">'
        f'<strong>{_esc(label)} in the saved security model.</strong>'
        '<p>This page keeps assets, actors, flows, threats, controls and evidence together so the boundary can be reviewed without leaving the canonical Threat Model context.</p>'
        "</div>\n\n"
    )
    body += _detail_summary(kind="Canonical trust boundary", assets=len(assets), controls=len(controls), review=review)
    body += f"## Boundary\n\n<div class=\"pl-threat-boundary-callout\"><strong>{_esc(label)}</strong><span>Canonical threat boundary · source-derived · not live monitoring</span></div>\n\n"
    body += "## Assets\n\n" + _detail_list(assets, "No canonical assets are recorded.") + "\n\n"
    body += "## Actors\n\n" + _detail_list(boundary.get("actors") or [], "No canonical actors are recorded.") + "\n\n"
    body += "## Entry points\n\n" + _detail_list(boundary.get("entry_points") or [], "No canonical entry points are recorded.") + "\n\n"
    body += "## Data flows\n\n" + _detail_list(boundary.get("data_flows") or [], "No canonical data flows are recorded.") + "\n\n"
    body += "## Allowed flows\n\n" + _detail_list(boundary.get("allowed_flows") or [], "No canonical allowed flows are recorded.") + "\n\n"
    body += "## Forbidden flows\n\n" + _detail_list(boundary.get("forbidden_flows") or [], "No boundary-specific forbidden flows are recorded.") + "\n\n"
    body += "## Threats\n\n" + table(
        ["STRIDE", "Scenario", "OWASP mapping", "Controls"],
        [[row.get("stride"), row.get("scenario"), row.get("owasp_mappings"), row.get("controls")] for row in boundary_threats],
    )
    body += "\n## Controls\n\n" + _detail_list((f"`{item}`" for item in controls), "No canonical controls are recorded.") + "\n\n"
    body += "## Runtime evidence & provenance\n\n" + table(
        ["Signal", "State", "Source"],
        [[row.get("signal"), row.get("state"), row.get("source")] for row in boundary.get("runtime_evidence") or []],
    )
    body += f"\n## Residual risk\n\n{boundary.get('residual_risk') or 'Unvalidated until human review.'}\n\n"
    body += f"## Review status\n\n{review}\n"
    return body


def render_evidence_projection_page(threat: dict[str, Any], poster: dict[str, Any]) -> str:
    """Render the evidence lane with boundary-like anatomy without redefining canonical topology."""
    evidence_node_ids = {"promoted-evidence", "documentation"}
    evidence_nodes = [row for row in poster.get("nodes") or [] if str(row.get("id")) in evidence_node_ids]
    evidence_assets = _unique(asset for row in evidence_nodes for asset in (row.get("assets") or []))
    evidence_control_ids = _unique(control for row in evidence_nodes for control in (row.get("controls") or []))
    control_index = {str(row.get("id")): row for row in threat.get("controls") or []}
    evidence_flows = [
        row for row in poster.get("flows") or []
        if str(row.get("from")) in evidence_node_ids or str(row.get("to")) in evidence_node_ids
    ]
    incoming = [
        row for row in evidence_flows
        if str(row.get("to")) in evidence_node_ids and str(row.get("from")) not in evidence_node_ids
    ]
    forbidden = [
        row for row in poster.get("forbidden_flows") or []
        if str(row.get("from")) in evidence_node_ids or str(row.get("to")) in evidence_node_ids
    ]
    body = f"# Promoted evidence → documentation\n\n{threat_model_nav(nested=True)}\n\n"
    body += (
        '<div class="pl-page-lede pl-threat-boundary-lede">'
        '<strong>Saved evidence enters documentation through an explicit projection zone.</strong>'
        '<p>This lane uses the same review anatomy as canonical boundaries while remaining a presentation/evidence projection. It does not create a tenth canonical threat boundary or imply live monitoring.</p>'
        "</div>\n\n"
    )
    body += _detail_summary(
        kind="Evidence projection zone",
        assets=len(evidence_assets),
        controls=len(evidence_control_ids),
        review="Human review required",
    )
    body += (
        '## Boundary\n\n<div class="pl-threat-boundary-callout">'
        '<strong>Promoted evidence → documentation</strong>'
        '<span>Presentation/evidence zone · canonical threat-boundary ownership unchanged</span>'
        "</div>\n\n"
    )
    body += "## Assets\n\n" + _detail_list(evidence_assets, "No promoted/canonical evidence assets are currently projected.") + "\n\n"
    body += "## Actors\n\n" + _table(
        ["Component", "Role", "Architecture component", "Canonical boundary"],
        [[row.get("label"), row.get("role"), row.get("architecture_component"), row.get("boundary")] for row in evidence_nodes],
    )
    body += "\n## Entry points\n\n" + _detail_list(
        (
            f"{row.get('from')} → {row.get('to')} — {row.get('label') or row.get('id')}"
            for row in incoming
        ),
        "No source-derived incoming flow is mapped directly to this projection zone.",
    ) + "\n\n"
    body += "## Data flows\n\n" + _table(
        ["Flow", "From", "To", "Meaning"],
        [[row.get("id"), row.get("from"), row.get("to"), row.get("label")] for row in evidence_flows],
    )
    body += "\n## Allowed flows\n\n" + _detail_list(
        (
            f"{row.get('from')} → {row.get('to')} — {row.get('label') or row.get('id')}"
            for row in evidence_flows
        ),
        "No source-derived allowed flow is mapped directly to this projection zone.",
    ) + "\n\n"
    body += "## Forbidden flows\n\n" + _detail_list(
        (
            f"{row.get('statement') or row.get('label') or row.get('id')} ({row.get('from')} → {row.get('to')})"
            for row in forbidden
        ),
        "No additional canonical forbidden flow is mapped directly to this projection zone; global Threat Model guardrails still apply.",
    ) + "\n\n"
    body += (
        "## Threats\n\n"
        "No canonical STRIDE threat is assigned directly to this projection zone because it is not a canonical threat boundary. "
        "Relevant threats remain owned by the canonical boundaries and controls that produce, sanitize, promote or consume the evidence.\n\n"
    )
    body += "## Controls\n\n" + _table(
        ["Control", "Description", "Status"],
        [
            [cid, (control_index.get(cid) or {}).get("description"), (control_index.get(cid) or {}).get("status")]
            for cid in evidence_control_ids
        ],
    )
    body += "\n## Runtime evidence & provenance\n\n"
    body += (
        "Promoted runtime evidence and canonical provenance are shown together here because this page explains how saved evidence reaches documentation. "
        "The table is lineage information, not a live feed.\n\n"
    )
    body += _table(
        ["Stage", "Canonical/promoted source"],
        [[row.get("label"), row.get("source")] for row in poster.get("evidence_lineage") or []],
    )
    body += (
        "\n## Residual risk\n\n"
        "No independent residual-risk score is assigned to this projection zone. Evidence adequacy, stale or missing observations, control effectiveness and acceptance remain human-review decisions owned by the canonical model.\n\n"
    )
    body += (
        "## Guardrails\n\n"
        "- Documentation does not capture or poll live runtime.\n"
        "- Raw scanner output does not become documentation truth.\n"
        "- Runtime/scanner evidence must be sanitized and explicitly promoted before canonical documentation ingestion.\n\n"
    )
    body += "## Review status\n\nHuman review remains required for evidence adequacy, exploitability, residual risk and acceptance.\n"
    return body


def render_threat_model_subpages(threat: dict[str, Any], poster: dict[str, Any]) -> dict[str, dict[str, str]]:
    pages = _render_threat_model_subpages_boundary_polish_base(threat, poster)
    pages["evidence-zone"] = {
        "title": "Promoted evidence → documentation",
        "description": "Projection-zone detail for promoted evidence flowing into static documentation without creating a new canonical trust boundary.",
        "body": render_evidence_projection_page(threat, poster),
    }
    return pages
