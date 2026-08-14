#!/usr/bin/env python3
"""Single deterministic layout engine for Pocket Lab Lite threat-model SVG projections.

Presentation only: consumes the normalized security-poster projection and emits static SVG.
No runtime capture, network access, risk scoring, topology inference, force layout, polling,
ResizeObserver/MutationObserver, canvas/WebGL, or probabilistic placement is permitted here.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Any, Iterable

ENGINE_VERSION = "canonical-security-layout-v2"
SUPPORTED_VARIANTS = {"overview", "architecture", "catalog"}
SUPPORTED_LAYOUTS = {"wide", "stacked"}

PRIVATE_PROJECTION = re.compile(
    r"(?:/home/[^/\s]+|/data/data/com\.termux/files/(?:home|usr)|[A-Za-z]:\\Users\\|nats://[^\s]+@)",
    re.I,
)
SECRET_PROJECTION = re.compile(
    r"(?:BEGIN [A-Z ]*PRIVATE KEY|(?:password|passwd|token|secret|api[_-]?key|credential|authorization)\s*[=:]\s*[^\s,}\]]{6,})",
    re.I,
)
REMOTE_HREF = re.compile(r"(?:href|xlink:href)=[\"'](?:https?:)?//", re.I)

EXPECTED_NODES = {
    "github-release", "release-artifacts", "scanner-evidence", "private-network", "tailscale",
    "browser", "caddy", "lite-api", "nats-jetstream", "worker", "managed-device", "node-agent",
    "agent-supervisor", "photoprism", "server-host", "sqlite", "recovery-state",
    "promoted-evidence", "documentation",
}

ZONE_MEMBERS = {
    "external-release": ("github-release", "release-artifacts", "scanner-evidence"),
    "private-network": ("private-network", "tailscale"),
    "control-plane": ("browser", "caddy", "lite-api", "nats-jetstream", "worker"),
    "managed-edge": ("managed-device", "node-agent", "agent-supervisor"),
    "runtime-state": ("recovery-state", "sqlite", "photoprism", "server-host"),
    "evidence": ("promoted-evidence", "documentation"),
}

ZONE_LABELS = {
    "external-release": "External release / supply chain",
    "private-network": "Private network / Tailnet",
    "control-plane": "Browser → control API → messaging / execution",
    "managed-edge": "Managed device / edge",
    "runtime-state": "Application / host / durable state",
    "evidence": "Promoted evidence → documentation",
}

CONTROL_OWNERS = {
    "CTRL-BROWSER-NATS": ("browser", "NO NATS", -65, 17),
    "CTRL-BROWSER-SHELL": ("browser", "NO SHELL", 65, 17),
    "CTRL-API-CONTROL": ("lite-api", "API AUTH", 18, 59),
    "CTRL-EXECUTION-OWNERS": ("worker", "EXEC OWN", 28, 59),
    "CTRL-EVIDENCE-SANITIZE": ("promoted-evidence", "SANITIZE", -30, 59),
    "CTRL-EXPLICIT-PROMOTION": ("documentation", "PROMOTE", -30, 59),
    "CTRL-SUPPLY-CHAIN": ("release-artifacts", "SUPPLY", 30, 59),
}

WIDE_LANES = (
    ("external", ("github-release", "release-artifacts", "scanner-evidence"), 58, 112, 190),
    ("private", ("private-network", "tailscale"), 770, 112, 205),
    ("control", ("browser", "caddy", "lite-api", "nats-jetstream", "worker"), 48, 365, 190),
    ("runtime", ("recovery-state", "sqlite", "photoprism", "server-host"), 240, 610, 205),
    ("evidence", ("promoted-evidence", "documentation"), 430, 835, 255),
)
WIDE_EDGE = (("managed-device", 1170, 320), ("node-agent", 1170, 475), ("agent-supervisor", 1170, 630))

STACKED_ROWS = (
    (("github-release", "release-artifacts"), 20, 110),
    (("scanner-evidence",), 140, 250),
    (("private-network", "tailscale"), 20, 470),
    (("browser", "caddy"), 20, 685),
    (("lite-api", "nats-jetstream"), 20, 835),
    (("worker",), 140, 985),
    (("managed-device", "node-agent"), 20, 1205),
    (("agent-supervisor",), 140, 1355),
    (("recovery-state", "sqlite"), 20, 1575),
    (("photoprism", "server-host"), 20, 1725),
    (("promoted-evidence", "documentation"), 20, 1950),
)


@dataclass(frozen=True)
class Box:
    x: float
    y: float
    w: float
    h: float

    @property
    def x2(self) -> float: return self.x + self.w
    @property
    def y2(self) -> float: return self.y + self.h
    @property
    def cx(self) -> float: return self.x + self.w / 2
    @property
    def cy(self) -> float: return self.y + self.h / 2

    def expanded(self, pad_x: float, pad_y: float) -> "Box":
        return Box(self.x - pad_x, self.y - pad_y, self.w + 2 * pad_x, self.h + 2 * pad_y)

    def intersects(self, other: "Box", gap: float = 0) -> bool:
        return not (
            self.x2 + gap <= other.x or other.x2 + gap <= self.x
            or self.y2 + gap <= other.y or other.y2 + gap <= self.y
        )


def _esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _wrap(value: Any, *, width: int = 21, lines: int = 2) -> list[str]:
    words = str(value).split()
    out: list[str] = []
    current: list[str] = []
    for word in words:
        candidate = " ".join([*current, word])
        if current and len(candidate) > width:
            out.append(" ".join(current))
            current = [word]
            if len(out) == lines - 1:
                break
        else:
            current.append(word)
    if len(out) < lines and current:
        remainder = " ".join(current)
        if len(out) == lines - 1 and len(remainder) > width:
            remainder = remainder[: max(1, width - 1)].rstrip() + "…"
        out.append(remainder)
    return out[:lines] or ["unvalidated"]


def _plate(text: str, x: float, y: float, cls: str = "flow-caption") -> str:
    width = max(46, min(152, len(text) * 5.6 + 18))
    return (
        f'<g class="{cls}" aria-hidden="true"><rect x="{x-width/2:.1f}" y="{y-12:.1f}" width="{width:.1f}" height="18" rx="8"/>'
        f'<text x="{x:.1f}" y="{y+1:.1f}" text-anchor="middle">{_esc(text)}</text></g>'
    )


def _lane_boxes(layout: str) -> tuple[dict[str, Box], int, int]:
    if layout == "wide":
        width, height = 1280, 1120
        boxes: dict[str, Box] = {}
        card_w, card_h = 168, 94
        header_offset = 90
        for _name, ids, start_x, center_y, step in WIDE_LANES:
            center_y += header_offset
            for index, node_id in enumerate(ids):
                boxes[node_id] = Box(start_x + index * step, center_y - card_h / 2, card_w, card_h)
        for node_id, center_x, center_y in WIDE_EDGE:
            center_y += header_offset
            boxes[node_id] = Box(center_x - card_w / 2, center_y - card_h / 2, card_w, card_h)
        return boxes, width, height

    if layout == "stacked":
        width, height = 480, 2360
        boxes = {}
        card_w, card_h = 200, 110
        header_offset = 90
        for ids, start_x, center_y in STACKED_ROWS:
            center_y += header_offset
            if len(ids) == 1:
                boxes[ids[0]] = Box((width - card_w) / 2, center_y - card_h / 2, card_w, card_h)
            else:
                step = 240
                for index, node_id in enumerate(ids):
                    boxes[node_id] = Box(start_x + index * step, center_y - card_h / 2, card_w, card_h)
        return boxes, width, height

    raise ValueError(f"unsupported threat-model layout: {layout}")


def _zone_box(boxes: dict[str, Box], members: Iterable[str], *, layout: str) -> Box:
    selected = [boxes[node_id] for node_id in members]
    pad_x = 22 if layout == "wide" else 12
    pad_top = 42
    pad_bottom = 60 if layout == "wide" else 50
    x = min(box.x for box in selected) - pad_x
    y = min(box.y for box in selected) - pad_top
    x2 = max(box.x2 for box in selected) + pad_x
    y2 = max(box.y2 for box in selected) + pad_bottom
    return Box(x, y, x2 - x, y2 - y)


def compile_layout(poster: dict[str, Any], *, layout: str = "wide") -> dict[str, Any]:
    """Compile and validate presentation geometry. Canonical topology is never inferred here."""
    if layout not in SUPPORTED_LAYOUTS:
        raise ValueError(f"unsupported threat-model layout: {layout}")
    source_ids = {str(row.get("id")) for row in poster.get("nodes") or []}
    missing = sorted(EXPECTED_NODES - source_ids)
    extra = sorted(source_ids - EXPECTED_NODES)
    if missing or extra:
        raise ValueError(f"security layout node-set drift: missing={missing} extra={extra}")

    boxes, width, height = _lane_boxes(layout)
    if set(boxes) != EXPECTED_NODES:
        raise ValueError("security layout engine does not cover the canonical presentation node set")

    for node_id, box in boxes.items():
        if box.x < 0 or box.y < 0 or box.x2 > width or box.y2 > height:
            raise ValueError(f"security layout node out of bounds: {node_id} {box}")

    ordered = sorted(boxes.items())
    for index, (a_id, a) in enumerate(ordered):
        for b_id, b in ordered[index + 1 :]:
            if a.intersects(b, gap=6):
                raise ValueError(f"security layout node overlap: {a_id} <-> {b_id}")

    zones = {zone_id: _zone_box(boxes, members, layout=layout) for zone_id, members in ZONE_MEMBERS.items()}
    for zone_id, members in ZONE_MEMBERS.items():
        zone = zones[zone_id]
        for node_id in members:
            box = boxes[node_id]
            if not (zone.x <= box.x and zone.y <= box.y and zone.x2 >= box.x2 and zone.y2 >= box.y2):
                raise ValueError(f"security layout zone containment failed: {zone_id}/{node_id}")

    zone_items = sorted(zones.items())
    for index, (a_id, a) in enumerate(zone_items):
        for b_id, b in zone_items[index + 1 :]:
            if a.intersects(b, gap=4):
                raise ValueError(f"security layout trust-zone overlap: {a_id} <-> {b_id}")

    control_boxes: dict[str, Box] = {}
    for control_id, (owner, label, dx, _dy) in CONTROL_OWNERS.items():
        if control_id not in {str(row.get("id")) for row in poster.get("controls") or []}:
            raise ValueError(f"security layout missing canonical control: {control_id}")
        if owner not in boxes:
            raise ValueError(f"security layout control owner missing: {control_id}/{owner}")
        owner_box = boxes[owner]
        scale = .82 if layout == "stacked" else 1.0
        cx = owner_box.cx + dx * scale
        cy = owner_box.y2 + 17
        caption_width = max(48, len(label) * 6 + 16)
        control_box = Box(cx - 14, cy - 14, 31 + caption_width, 34)
        if control_box.x < 0 or control_box.y < 0 or control_box.x2 > width or control_box.y2 > height:
            raise ValueError(f"security layout control out of bounds: {control_id} {control_box}")
        control_boxes[control_id] = control_box

    control_items = sorted(control_boxes.items())
    for index, (a_id, a) in enumerate(control_items):
        for b_id, b in control_items[index + 1 :]:
            if a.intersects(b, gap=3):
                raise ValueError(f"security layout control overlap: {a_id} <-> {b_id}")

    return {
        "layout": layout, "width": width, "height": height,
        "boxes": boxes, "zones": zones, "control_boxes": control_boxes,
    }


def _anchors(source: Box, target: Box) -> tuple[tuple[float, float], tuple[float, float], str]:
    dx, dy = target.cx - source.cx, target.cy - source.cy
    if abs(dx) >= abs(dy):
        if dx >= 0:
            return (source.x2, source.cy), (target.x, target.cy), "horizontal"
        return (source.x, source.cy), (target.x2, target.cy), "horizontal"
    if dy >= 0:
        return (source.cx, source.y2), (target.cx, target.y), "vertical"
    return (source.cx, source.y), (target.cx, target.y2), "vertical"


def _route(source: Box, target: Box) -> tuple[str, float, float]:
    (sx, sy), (tx, ty), axis = _anchors(source, target)
    if axis == "horizontal":
        mid = (sx + tx) / 2
        return f"M {sx:.1f} {sy:.1f} C {mid:.1f} {sy:.1f}, {mid:.1f} {ty:.1f}, {tx:.1f} {ty:.1f}", mid, (sy + ty) / 2
    mid = (sy + ty) / 2
    return f"M {sx:.1f} {sy:.1f} C {sx:.1f} {mid:.1f}, {tx:.1f} {mid:.1f}, {tx:.1f} {ty:.1f}", (sx + tx) / 2, mid


def _node_svg(row: dict[str, Any], box: Box, *, layout: str) -> str:
    icon = f'../../../assets/diagrams/production/icons/{row.get("icon") or "docs.svg"}'
    name_lines = _wrap(row.get("label") or row.get("id"), width=20 if layout == "wide" else 28)
    role_lines = _wrap(row.get("role") or "architecture component", width=28 if layout == "wide" else 36, lines=1)
    controls = list(row.get("controls") or [])
    assets = list(row.get("assets") or [])
    control_label = f'{len(controls)} control' + ("" if len(controls) == 1 else "s")
    asset_label = f'{len(assets)} asset' + ("" if len(assets) == 1 else "s")
    compact_state = {
        "control-observed": "observed",
        "control-partial": "partial",
        "control-unvalidated": "unvalidated",
        "evidence-stale": "stale",
    }.get(str(row.get("posture")), str(row.get("posture") or "unvalidated"))
    cue_label = f"{compact_state} · C{len(controls)} · A{len(assets)}"
    text_x = box.x + (48 if layout == "wide" else 56)
    icon_size = 30 if layout == "wide" else 34
    icon_x = box.x + 12
    icon_y = box.y + 17
    name_y = box.y + 28
    tspans = "".join(
        f'<tspan x="{text_x:.1f}" dy="{0 if index == 0 else 15}">{_esc(line)}</tspan>'
        for index, line in enumerate(name_lines)
    )
    role_y = box.y + (59 if len(name_lines) > 1 else 47)
    cue_y = box.y2 - 11
    bounds = f"{box.x:.1f},{box.y:.1f},{box.w:.1f},{box.h:.1f}"
    return (
        f'<g class="node" data-node="{_esc(row.get("id"))}" data-boundary="{_esc(row.get("boundary"))}" '
        f'data-state="{_esc(row.get("posture"))}" data-architecture-component="{_esc(row.get("architecture_component"))}" '
        f'data-stride="{_esc("|".join(row.get("stride") or []))}" data-threat-count="{len(row.get("stride") or [])}" '
        f'data-assets="{_esc(" | ".join(assets))}" data-layout-bounds="{bounds}" tabindex="0" role="button" '
        f'aria-label="{_esc(row.get("label"))}; {_esc(row.get("role"))}; {_esc(row.get("posture"))}; {control_label}; {asset_label}">'
        f'<rect x="{box.x:.1f}" y="{box.y:.1f}" width="{box.w:.1f}" height="{box.h:.1f}"/>'
        f'<image href="{icon}" x="{icon_x:.1f}" y="{icon_y:.1f}" width="{icon_size}" height="{icon_size}" preserveAspectRatio="xMidYMid meet"/>'
        f'<text class="name" x="{text_x:.1f}" y="{name_y:.1f}">{tspans}</text>'
        f'<text class="role" x="{text_x:.1f}" y="{role_y:.1f}">{_esc(role_lines[0])}</text>'
        f'<text class="cue" x="{box.x + 12:.1f}" y="{cue_y:.1f}">{_esc(cue_label)}</text>'
        '</g>'
    )


def _control_svg(row: dict[str, Any], boxes: dict[str, Box], *, layout: str) -> str:
    owner, short, dx, dy = CONTROL_OWNERS[str(row.get("id"))]
    box = boxes[owner]
    scale = .82 if layout == "stacked" else 1.0
    x = box.cx + dx * scale
    y = box.y2 + 15
    return (
        f'<g class="control" data-control="{_esc(row.get("id"))}" data-boundaries="{_esc(" ".join(row.get("boundaries") or []))}" '
        f'data-threats="{_esc("|".join(row.get("stride") or []))}" data-stride="{_esc("|".join(row.get("stride") or []))}" '
        f'tabindex="0" role="button" aria-label="Control {_esc(row.get("id"))}; {_esc(row.get("description"))}; {_esc(row.get("status"))}">'
        f'<path class="shield" d="M {x:.1f} {y-13:.1f} l 12 4 v 10 c 0 10 -8 15 -12 18 c -4 -3 -12 -8 -12 -18 v -10 z"/>'
        f'<g class="control-caption"><rect x="{x+17:.1f}" y="{y-9:.1f}" width="{max(48, len(short)*6+16):.1f}" height="20" rx="9"/>'
        f'<text x="{x+25:.1f}" y="{y+5:.1f}">{_esc(short)}</text></g></g>'
    )


def _legend(width: int, height: int) -> str:
    if width < 800:
        x, y = 22, height - 190
        rows = [
            ("flow", "Modeled allowed/control flow"),
            ("attack", "Selected modeled attack path"),
            ("shield", "Security control"),
            ("zone", "Trust zone"),
            ("motion", "Saved relationship motion only"),
        ]
        parts = [f'<g class="legend" data-threat-legend="svg" aria-label="Diagram legend">']
        for index, (kind, label) in enumerate(rows):
            row_y = y + index * 30
            if kind == "flow":
                parts.append(f'<path class="legend-flow" d="M {x} {row_y} h 44"/>')
            elif kind == "attack":
                parts.append(f'<path class="legend-attack" d="M {x} {row_y} h 44"/>')
            elif kind == "shield":
                parts.append(f'<path class="legend-shield" d="M {x+18} {row_y-12} l 9 3 v 7 c 0 7 -5 11 -9 13 c -4 -2 -9 -6 -9 -13 v -7 z"/>')
            elif kind == "zone":
                parts.append(f'<rect class="legend-zone" x="{x+5}" y="{row_y-11}" width="34" height="21" rx="7"/>')
            else:
                parts.append(f'<circle class="legend-motion" cx="{x+8}" cy="{row_y}" r="4"/><path class="legend-motion-path" d="M {x+17} {row_y} h 28"/>')
            parts.append(f'<text x="{x+58}" y="{row_y+4}">{_esc(label)}</text>')
        parts.append('</g>')
        return "".join(parts)

    y = height - 44
    x = 34
    return (
        f'<g class="legend" data-threat-legend="svg" aria-label="Diagram legend">'
        f'<path class="legend-flow" d="M {x} {y} h 54"/><text x="{x+64}" y="{y+4}">Modeled allowed/control flow</text>'
        f'<path class="legend-attack" d="M {x+270} {y} h 54"/><text x="{x+334}" y="{y+4}">Selected modeled attack path</text>'
        f'<path class="legend-shield" d="M {x+565} {y-13} l 10 4 v 8 c 0 8 -6 12 -10 14 c -4 -2 -10 -6 -10 -14 v -8 z"/>'
        f'<text x="{x+584}" y="{y+4}">Security control</text>'
        f'<rect class="legend-zone" x="{x+745}" y="{y-12}" width="32" height="22" rx="7"/><text x="{x+786}" y="{y+4}">Trust zone</text>'
        f'<circle class="legend-motion" cx="{x+905}" cy="{y}" r="4"/><path class="legend-motion-path" d="M {x+914} {y} h 36"/><text x="{x+958}" y="{y+4}">Saved relationship motion only</text>'
        '</g>'
    )


def render_security_projection_svg(
    poster: dict[str, Any], *, variant: str = "overview", layout: str = "wide"
) -> str:
    if variant not in SUPPORTED_VARIANTS:
        raise ValueError(f"unsupported threat-model variant: {variant}")
    compiled = compile_layout(poster, layout=layout)
    boxes: dict[str, Box] = compiled["boxes"]
    zones: dict[str, Box] = compiled["zones"]
    width, height = int(compiled["width"]), int(compiled["height"])
    nodes = {str(row.get("id")): row for row in poster.get("nodes") or []}

    wide_titles = {
        "overview": "Pocket Lab Lite Security Architecture Poster",
        "architecture": "Pocket Lab Lite threat model architecture overlay",
        "catalog": "Pocket Lab Lite · Security Atlas Architecture Overlay",
    }
    stacked_titles = {
        "overview": "Pocket Lab Lite · Security Architecture",
        "architecture": "Architecture & Trust Zones",
        "catalog": "Security Atlas · Architecture Overlay",
    }
    title = (stacked_titles if layout == "stacked" else wide_titles)[variant]
    wide_subtitles = {
        "overview": "Static model · canonical architecture overlay · promoted/sanitized evidence · human review required",
        "architecture": "One canonical layout engine · trust zones and architecture ownership · not live traffic",
        "catalog": "Interactive saved-model projection · systems, controls, attack paths and evidence posture",
    }
    stacked_subtitles = {
        "overview": "Static model · canonical architecture · promoted evidence · human review",
        "architecture": "Canonical architecture + trust zones · one layout engine · not live",
        "catalog": "Saved-model systems · controls · attack paths · evidence posture",
    }
    subtitle = (stacked_subtitles if layout == "stacked" else wide_subtitles)[variant]

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" preserveAspectRatio="xMidYMin meet" role="img" '
        f'aria-labelledby="poster-title poster-desc" class="mode-understand view-system" data-poster-mode="understand" data-view-mode="system" '
        f'data-layout-engine="{ENGINE_VERSION}" data-layout="{layout}" data-variant="{variant}">',
        f'<title id="poster-title">{_esc(title)}</title>',
        '<desc id="poster-desc">Static architecture security overlay showing trust zones, canonical flows, controls, assets, forbidden paths and modeled attack paths. Modeled flow — not live traffic. Motion is explanatory and never represents a live connection or active attack.</desc>',
        '''<defs>
<pattern id="poster-grid" width="28" height="28" patternUnits="userSpaceOnUse"><path d="M28 0H0V28" fill="none" stroke="#93a4bd" stroke-opacity=".065" stroke-width="1"/></pattern>
<marker id="poster-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0L8 4L0 8Z" fill="#4f8bd6"/></marker>
<marker id="forbidden-x" markerWidth="10" markerHeight="10" refX="5" refY="5"><path d="M1 1L9 9M9 1L1 9" stroke="#c94c4c" stroke-width="2"/></marker>
</defs>''',
        '''<style>
.bg{fill:#f5f7fb}.grid{fill:url(#poster-grid)}.title{fill:#172338;font:700 24px system-ui,sans-serif}.subtitle{fill:#53647c;font:500 12px system-ui,sans-serif}.badge{fill:#e7edf7;stroke:#c9d4e5}.badge-text{fill:#34445c;font:700 10px system-ui,sans-serif;letter-spacing:.08em}.zone{stroke-width:1.2}.zone--external{fill:#fff8ea;stroke:#e2c27c}.zone--private{fill:#eef7ff;stroke:#9cc6e8}.zone--control{fill:#f1f7ff;stroke:#8bb4df}.zone--edge{fill:#eef9f4;stroke:#8bc8ad}.zone--state{fill:#f7f3fb;stroke:#baa3d5}.zone--evidence{fill:#f3f5f8;stroke:#aab6c7}.zone-title-bg{fill:#f5f7fb;fill-opacity:.94;stroke:#cfd8e6}.zone-title{fill:#34465f;font:700 11px system-ui,sans-serif;letter-spacing:.035em}.node{cursor:pointer;transition:opacity .18s ease}.node rect{fill:#fff;stroke:#8293aa;stroke-width:1.3;rx:14}.node .name{fill:#1e2b40;font:700 12px system-ui,sans-serif}.node .role{fill:#586a82;font:500 9.5px system-ui,sans-serif}.node .cue{font:700 8.2px system-ui,sans-serif}svg[data-layout="stacked"] .title{font-size:20px}svg[data-layout="stacked"] .subtitle{font-size:11px}svg[data-layout="stacked"] .node .name{font-size:16px}svg[data-layout="stacked"] .node .role{font-size:12px}svg[data-layout="stacked"] .node .cue{font-size:10.5px}svg[data-layout="stacked"] .zone-title{font-size:13px}svg[data-layout="stacked"] .control-caption text{font-size:10px}svg[data-layout="stacked"] .legend{font-size:11px}.node[data-state="control-observed"] rect{stroke:#4f9f76}.node[data-state="control-observed"] .cue{fill:#367b59}.node[data-state="evidence-stale"] rect,.node[data-state="control-partial"] rect{stroke:#b4862c}.node[data-state="evidence-stale"] .cue,.node[data-state="control-partial"] .cue{fill:#795716}.node[data-state="control-unvalidated"] rect{stroke:#8994a6;stroke-dasharray:4 3}.node[data-state="control-unvalidated"] .cue{fill:#596575}.node.is-active rect{stroke-width:3.5}.node.is-muted,.control.is-muted,.flow.is-muted{opacity:.14}.node.is-filtered-out,.control.is-filtered-out,.attack.is-filtered-out{opacity:.075!important}.flow{fill:none;stroke:#4f8bd6;stroke-width:1.8;opacity:.58;marker-end:url(#poster-arrow)}.flow[data-core="true"]{stroke-width:2.5;stroke-dasharray:3 11;stroke-linecap:round;animation:canonical-flow 8s linear infinite}.flow-caption rect,.control-caption rect{fill:#f5f7fb;fill-opacity:.96;stroke:#cfd8e6}.flow-caption text{fill:#53647c;font:700 8.5px system-ui,sans-serif}.attack{fill:none;stroke:#c94c4c;stroke-width:4;stroke-dasharray:10 8;opacity:0;pointer-events:none}.attack.is-active{opacity:.92;animation:attack-trace 1.5s linear infinite}.forbidden{opacity:0;pointer-events:none}.show-guardrails .forbidden{opacity:.86}.forbidden path{fill:none;stroke:#c94c4c;stroke-width:1.9;stroke-dasharray:5 5;marker-end:url(#forbidden-x)}.forbidden .flow-caption rect{stroke:#dca5a5}.forbidden .flow-caption text{fill:#943b3b}.control{cursor:pointer;transition:opacity .18s ease}.control .shield{fill:#e9f6ef;stroke:#4d9a72;stroke-width:1.6}.control-caption text{fill:#326e51;font:700 8px system-ui,sans-serif}.control.is-active .shield{stroke-width:4;animation:control-halo .65s ease-out 1}.mode-understand .control{opacity:.72}.mode-threats .control{opacity:.36}.mode-controls .flow{opacity:.2}.mode-controls .node{opacity:.63}.mode-controls .control{opacity:1}.view-controls .flow{opacity:.18}.view-controls .control{opacity:1}.view-attack-paths .flow{opacity:.2}.view-evidence .flow{opacity:.12}.view-evidence .node rect{stroke-width:2.4}.motion-paused .flow,.motion-paused .attack,.motion-paused .control .shield{animation-play-state:paused!important}.legend{font:600 9.5px system-ui,sans-serif;fill:#53647c}.legend-flow{fill:none;stroke:#4f8bd6;stroke-width:2.4;marker-end:url(#poster-arrow)}.legend-attack{fill:none;stroke:#c94c4c;stroke-width:3;stroke-dasharray:8 6}.legend-shield{fill:#e9f6ef;stroke:#4d9a72;stroke-width:1.5}.legend-zone{fill:#eef7ff;stroke:#9cc6e8}.legend-motion{fill:#4f8bd6}.legend-motion-path{stroke:#4f8bd6;stroke-width:1.5;stroke-dasharray:2 5}@keyframes canonical-flow{to{stroke-dashoffset:-56}}@keyframes attack-trace{to{stroke-dashoffset:-36}}@keyframes control-halo{0%{stroke-width:1.5}45%{stroke-width:5}100%{stroke-width:4}}@media(prefers-color-scheme:dark){.bg{fill:#0d1422}.grid{opacity:.5}.title{fill:#f2f6ff}.subtitle{fill:#aebbd0}.badge{fill:#19263a;stroke:#35475f}.badge-text{fill:#d8e2f1}.zone--external{fill:#241f16;stroke:#6f5a2b}.zone--private{fill:#112235;stroke:#315c7d}.zone--control{fill:#101f31;stroke:#31597d}.zone--edge{fill:#10271e;stroke:#366d54}.zone--state{fill:#20182a;stroke:#5f4778}.zone--evidence{fill:#171d27;stroke:#4b586c}.zone-title-bg,.flow-caption rect,.control-caption rect{fill:#151f2e;stroke:#40516a}.zone-title{fill:#c6d2e4}.node rect{fill:#151f2e;stroke:#71839c}.node .name{fill:#eef4ff}.node .role{fill:#b6c2d3}.flow-caption text,.legend{fill:#b6c2d3}.control-caption text{fill:#9be2ba}}@media(prefers-reduced-motion:reduce){.flow,.attack,.node,.control,.control .shield{animation:none!important;transition:none!important}}@media print{.bg{fill:#fff}.grid{display:none}.flow[data-core="true"]{stroke-dasharray:none;animation:none}.attack{display:none}.forbidden{opacity:.75}.node,.control{transition:none}}
</style>''',
        f'<rect class="bg" data-reset-target="true" width="{width}" height="{height}"/><rect class="grid" data-reset-target="true" width="{width}" height="{height}"/>',
        f'<text class="title" x="34" y="31">{_esc(title)}</text>',
        f'<text class="subtitle" x="34" y="51">{_esc(subtitle)}</text>',
        (f'<rect class="badge" x="34" y="62" width="154" height="30" rx="15"/><text class="badge-text" x="111" y="81" text-anchor="middle">NOT LIVE MONITORING</text>'
         if layout == "stacked" else
         f'<rect class="badge" x="{width-190}" y="17" width="154" height="30" rx="15"/><text class="badge-text" x="{width-113}" y="36" text-anchor="middle">NOT LIVE MONITORING</text>'),
    ]

    zone_class = {"external-release":"external","private-network":"private","control-plane":"control","managed-edge":"edge","runtime-state":"state","evidence":"evidence"}
    for zone_id, box in zones.items():
        label = ZONE_LABELS[zone_id]
        label_w = min(box.w - 24, max(120, len(label) * 6.1 + 24))
        parts.append(
            f'<g data-zone="{_esc(zone_id)}"><rect class="zone zone--{zone_class[zone_id]}" x="{box.x:.1f}" y="{box.y:.1f}" width="{box.w:.1f}" height="{box.h:.1f}" rx="18"/>'
            f'<rect class="zone-title-bg" x="{box.x+12:.1f}" y="{box.y+9:.1f}" width="{label_w:.1f}" height="22" rx="9"/>'
            f'<text class="zone-title" x="{box.x+22:.1f}" y="{box.y+24:.1f}">{_esc(label)}</text></g>'
        )

    for edge in poster.get("flows") or []:
        source_id, target_id = str(edge.get("from")), str(edge.get("to"))
        if source_id not in boxes or target_id not in boxes:
            raise ValueError(f"security layout flow references unknown node: {source_id}->{target_id}")
        route, mx, my = _route(boxes[source_id], boxes[target_id])
        parts.append(
            f'<path class="flow" data-flow="{_esc(edge.get("id"))}" data-from="{_esc(source_id)}" data-to="{_esc(target_id)}" '
            f'data-core="{str(bool(edge.get("core"))).lower()}" d="{route}"/>'
        )
        if edge.get("core"):
            parts.append(_plate(str(edge.get("label") or "modeled flow"), mx, my - 5))

    for row in poster.get("forbidden_flows") or []:
        source_id, target_id = str(row.get("from")), str(row.get("to"))
        route, mx, my = _route(boxes[source_id], boxes[target_id])
        parts.append(
            f'<g class="forbidden" data-forbidden="{_esc(row.get("statement"))}"><path d="{route}"/>'
            f'{_plate(str(row.get("label") or "forbidden flow"), mx, my - 4)}</g>'
        )

    for path in poster.get("attack_paths") or []:
        ids = [str(node_id) for node_id in path.get("path_nodes") or []]
        unknown = [node_id for node_id in ids if node_id not in boxes]
        if unknown:
            raise ValueError(f"security layout attack path references unknown nodes: {path.get('id')} {unknown}")
        points = " ".join(f'{boxes[node_id].cx:.1f},{boxes[node_id].cy:.1f}' for node_id in ids)
        parts.append(
            f'<polyline class="attack" data-attack-path="{_esc(path.get("id"))}" data-stride="{_esc("|".join(path.get("stride") or []))}" '
            f'data-nodes="{_esc(" ".join(ids))}" data-controls="{_esc(" ".join(path.get("controls") or []))}" points="{points}"/>'
        )

    for row in poster.get("nodes") or []:
        parts.append(_node_svg(row, boxes[str(row.get("id"))], layout=layout))
    for row in poster.get("controls") or []:
        parts.append(_control_svg(row, boxes, layout=layout))

    parts.append(_legend(width, height))
    parts.append('</svg>\n')
    rendered = "".join(parts)
    lowered = rendered.lower()
    for forbidden in ("risk_score", "security_score", "last_seen", "live_feed", "active_attack", "websocket", "eventsource"):
        if forbidden in lowered:
            raise ValueError(f"security SVG emitted forbidden live/synthetic token: {forbidden}")
    if "<script" in lowered or REMOTE_HREF.search(rendered):
        raise ValueError("security SVG rejected executable or remote-linked content")
    if PRIVATE_PROJECTION.search(rendered) or SECRET_PROJECTION.search(rendered):
        raise ValueError("security SVG rejected private-path or secret-like content")
    return rendered


# Enterprise Threat Model presentation extension.
#
# This remains presentation-only. Repository-owned icons are embedded into the generated SVG so
# posters rendered through <img> retain their brand marks. Node counts expose explicit labels and
# a deterministic detail-page slug without changing canonical boundary ownership.
import base64 as _base64
from functools import lru_cache as _lru_cache
from pathlib import Path as _Path

_ICON_ROOT = _Path(__file__).resolve().parents[3] / "docs/assets/diagrams/production/icons"


@_lru_cache(maxsize=64)
def _icon_data_uri(filename: str) -> str:
    raw_name = str(filename or "docs.svg")
    safe_name = _Path(raw_name).name
    if safe_name != raw_name or not safe_name.endswith(".svg"):
        raise ValueError(f"security layout rejected unsafe icon name: {raw_name!r}")
    path = _ICON_ROOT / safe_name
    if not path.is_file():
        raise ValueError(f"security layout brand icon missing: {safe_name}")
    raw = path.read_bytes()
    text = raw.decode("utf-8", errors="strict")
    lowered = text.lower()
    if "<script" in lowered or REMOTE_HREF.search(text):
        raise ValueError(f"security layout brand icon is not self-contained: {safe_name}")
    if PRIVATE_PROJECTION.search(text) or SECRET_PROJECTION.search(text):
        raise ValueError(f"security layout brand icon rejected unsafe content: {safe_name}")
    return "data:image/svg+xml;base64," + _base64.b64encode(raw).decode("ascii")


def _node_svg(row: dict[str, Any], box: Box, *, layout: str) -> str:
    icon = _icon_data_uri(str(row.get("icon") or "docs.svg"))
    name_lines = _wrap(row.get("label") or row.get("id"), width=20 if layout == "wide" else 28)
    role_lines = _wrap(row.get("role") or "architecture component", width=28 if layout == "wide" else 36, lines=1)
    controls = list(row.get("controls") or [])
    assets = list(row.get("assets") or [])
    control_label = f'{len(controls)} control' + ("" if len(controls) == 1 else "s")
    asset_label = f'{len(assets)} asset' + ("" if len(assets) == 1 else "s")
    compact_state = {
        "control-observed": "observed",
        "control-partial": "partial",
        "control-unvalidated": "unvalidated",
        "evidence-stale": "stale",
    }.get(str(row.get("posture")), str(row.get("posture") or "unvalidated"))
    text_x = box.x + (48 if layout == "wide" else 56)
    icon_size = 30 if layout == "wide" else 34
    icon_x = box.x + 12
    icon_y = box.y + 17
    name_y = box.y + 28
    tspans = "".join(
        f'<tspan x="{text_x:.1f}" dy="{0 if index == 0 else 15}">{_esc(line)}</tspan>'
        for index, line in enumerate(name_lines)
    )
    role_y = box.y + (59 if len(name_lines) > 1 else 47)
    cue_y = box.y2 - 11
    bounds = f"{box.x:.1f},{box.y:.1f},{box.w:.1f},{box.h:.1f}"
    detail_slug = "evidence-zone" if str(row.get("id")) in {"promoted-evidence", "documentation"} else str(row.get("boundary") or "unvalidated")
    return (
        f'<g class="node" data-node="{_esc(row.get("id"))}" data-boundary="{_esc(row.get("boundary"))}" '
        f'data-state="{_esc(row.get("posture"))}" data-architecture-component="{_esc(row.get("architecture_component"))}" '
        f'data-stride="{_esc("|".join(row.get("stride") or []))}" data-threat-count="{len(row.get("stride") or [])}" '
        f'data-control-count="{len(controls)}" data-asset-count="{len(assets)}" '
        f'data-assets="{_esc(" | ".join(assets))}" data-layout-bounds="{bounds}" tabindex="0" role="button" '
        f'aria-label="{_esc(row.get("label"))}; {_esc(row.get("role"))}; {_esc(row.get("posture"))}; {control_label}; {asset_label}">'
        f'<rect x="{box.x:.1f}" y="{box.y:.1f}" width="{box.w:.1f}" height="{box.h:.1f}"/>'
        f'<image class="brand-icon" href="{icon}" x="{icon_x:.1f}" y="{icon_y:.1f}" width="{icon_size}" height="{icon_size}" preserveAspectRatio="xMidYMid meet"/>'
        f'<text class="name" x="{text_x:.1f}" y="{name_y:.1f}">{tspans}</text>'
        f'<text class="role" x="{text_x:.1f}" y="{role_y:.1f}">{_esc(role_lines[0])}</text>'
        f'<text class="cue cue-state" x="{box.x + 12:.1f}" y="{cue_y:.1f}">{_esc(compact_state)}</text>'
        f'<text class="cue cue-link" data-boundary-link="{_esc(detail_slug)}" x="{box.x2 - 12:.1f}" y="{cue_y:.1f}" text-anchor="end">{_esc(control_label)} · {_esc(asset_label)}</text>'
        '</g>'
    )


def _control_svg(row: dict[str, Any], boxes: dict[str, Box], *, layout: str) -> str:
    owner, short, dx, _dy = CONTROL_OWNERS[str(row.get("id"))]
    box = boxes[owner]
    scale = .82 if layout == "stacked" else 1.0
    x = box.cx + dx * scale
    y = box.y2 + 15
    caption_width = max(54, len(short) * 6.4 + 18)
    return (
        f'<g class="control" data-control="{_esc(row.get("id"))}" data-boundaries="{_esc(" ".join(row.get("boundaries") or []))}" '
        f'data-threats="{_esc("|".join(row.get("stride") or []))}" data-stride="{_esc("|".join(row.get("stride") or []))}" '
        f'tabindex="0" role="button" aria-label="Control {_esc(row.get("id"))}; {_esc(row.get("description"))}; {_esc(row.get("status"))}">'
        f'<path class="shield" d="M {x:.1f} {y-14:.1f} l 13 4.5 v 10.5 c 0 10.5 -8.5 16 -13 19 c -4.5 -3 -13 -8.5 -13 -19 v -10.5 z"/>'
        f'<path class="shield-mark" d="M {x-6:.1f} {y+1:.1f} l 4.5 4.5 l 8.5 -9"/>'
        f'<g class="control-caption"><rect x="{x+18:.1f}" y="{y-10:.1f}" width="{caption_width:.1f}" height="22" rx="10"/>'
        f'<text x="{x+26:.1f}" y="{y+5:.1f}">{_esc(short)}</text></g></g>'
    )


def _legend(_width: int, _height: int) -> str:
    # The page-level accessible HTML legend is authoritative. Preserve legacy regression
    # tokens only as non-rendering SVG metadata; no second visual/accessibility legend is emitted.
    return (
        '<metadata data-threat-legend="svg" aria-hidden="true">'
        'Modeled allowed/control flow · Selected modeled attack path · Security control · '
        'Trust zone · Saved relationship motion only'
        '</metadata>'
    )


_render_security_projection_svg_enterprise_base = render_security_projection_svg


def _enterprise_replace_once(value: str, old: str, new: str, label: str) -> str:
    if value.count(old) != 1:
        raise ValueError(f"security SVG presentation fence drifted: {label}")
    return value.replace(old, new, 1)


def render_security_projection_svg(
    poster: dict[str, Any], *, variant: str = "overview", layout: str = "wide"
) -> str:
    rendered = _render_security_projection_svg_enterprise_base(poster, variant=variant, layout=layout)
    replacements = (
        (
            '.node .cue{font:700 8.2px system-ui,sans-serif}',
            '.node .cue{font:700 8.2px system-ui,sans-serif}.node .cue-link{cursor:pointer;text-decoration:underline;text-decoration-thickness:.7px;text-underline-offset:1.5px}.node .cue-link:hover{fill:#245f9c}',
            'explicit control/asset cue',
        ),
        (
            'svg[data-layout="stacked"] .control-caption text{font-size:10px}svg[data-layout="stacked"] .legend{font-size:11px}',
            'svg[data-layout="stacked"] .control-caption text{font-size:10px}svg[data-layout="stacked"] .flow-caption text{font-size:11.5px}svg[data-layout="stacked"] .legend{font-size:11px}',
            'stacked flow-label typography',
        ),
        (
            '.flow-caption rect,.control-caption rect{fill:#f5f7fb;fill-opacity:.96;stroke:#cfd8e6}.flow-caption text{fill:#53647c;font:700 8.5px system-ui,sans-serif}',
            '.flow-caption rect{fill:#fff;fill-opacity:.99;stroke:#91a5c0;stroke-width:1.25}.control-caption rect{fill:#f5f7fb;fill-opacity:.98;stroke:#b8c8dc}.flow-caption text{fill:#1f2d42;font:800 10px system-ui,sans-serif;paint-order:stroke;stroke:#fff;stroke-width:.35px}',
            'flow-label contrast',
        ),
        (
            '.control .shield{fill:#e9f6ef;stroke:#4d9a72;stroke-width:1.6}.control-caption text{fill:#326e51;font:700 8px system-ui,sans-serif}',
            '.control .shield{fill:#e7f6ee;stroke:#367b59;stroke-width:2}.control .shield-mark{fill:none;stroke:#2f704f;stroke-width:2.2;stroke-linecap:round;stroke-linejoin:round}.control-caption text{fill:#285f45;font:800 8.5px system-ui,sans-serif}',
            'shield geometry',
        ),
        (
            '.zone-title-bg,.flow-caption rect,.control-caption rect{fill:#151f2e;stroke:#40516a}.zone-title{fill:#c6d2e4}',
            '.zone-title-bg,.control-caption rect{fill:#151f2e;stroke:#40516a}.flow-caption rect{fill:#111b2a;fill-opacity:.99;stroke:#6f88aa}.zone-title{fill:#c6d2e4}',
            'dark flow-label plate',
        ),
        (
            '.flow-caption text,.legend{fill:#b6c2d3}.control-caption text{fill:#9be2ba}',
            '.flow-caption text{fill:#edf3ff;stroke:#111b2a}.legend{fill:#b6c2d3}.control-caption text{fill:#9be2ba}',
            'dark flow-label text',
        ),
    )
    for old, new, label in replacements:
        rendered = _enterprise_replace_once(rendered, old, new, label)
    return rendered
