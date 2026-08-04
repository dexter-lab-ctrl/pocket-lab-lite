#!/usr/bin/env python3
"""Deterministic Graphviz renderer for architecture views and component mini diagrams."""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from architecture_model import ArchitectureIndex, ROOT, derive_mini_graph
from icon_registry import IconRecord
from svg_icon_embedder import (
    EmbeddedIcon,
    SvgIconEmbedError,
    resolve_with_fallback,
    symbol_defs_from_icons,
)

THEMES = {
    "light": {
        "background": "#ffffff", "foreground": "#172033", "muted": "#475569",
        "edge": "#64748b", "cluster": "#f8fafc", "cluster_border": "#94a3b8",
        "actor": "#ecfeff", "ui": "#e0f2fe", "proxy": "#ede9fe",
        "service": "#e0e7ff", "event": "#fce7f3", "process": "#dcfce7",
        "database": "#fef3c7", "network": "#cffafe", "external-app": "#fae8ff", "external": "#f3e8ff",
        "artifact": "#ffedd5", "decision": "#fef2f2", "control": "#475569", "data": "#2563eb",
        "evidence": "#7c3aed", "health": "#047857", "recovery": "#b45309",
    },
    "dark": {
        "background": "#0f172a", "foreground": "#f8fafc", "muted": "#cbd5e1",
        "edge": "#94a3b8", "cluster": "#111827", "cluster_border": "#64748b",
        "actor": "#164e63", "ui": "#0c4a6e", "proxy": "#4c1d95",
        "service": "#312e81", "event": "#831843", "process": "#14532d",
        "database": "#78350f", "network": "#155e75", "external-app": "#701a75", "external": "#581c87",
        "artifact": "#7c2d12", "decision": "#7f1d1d", "control": "#cbd5e1", "data": "#60a5fa",
        "evidence": "#c4b5fd", "health": "#6ee7b7", "recovery": "#fbbf24",
    },
}

POSTER_ZONE_COLORS = {
    "light": ["#eff6ff", "#eef2ff", "#fdf2f8", "#fffbeb", "#ecfdf5", "#f5f3ff"],
    "dark": ["#172554", "#1e1b4b", "#500724", "#451a03", "#052e16", "#2e1065"],
}

SHAPES = {
    "actor": "ellipse", "ui": "box", "proxy": "box", "service": "box",
    "event": "parallelogram", "process": "component", "database": "cylinder",
    "network": "hexagon", "external-app": "ellipse", "external": "ellipse", "artifact": "note", "decision": "diamond",
}
EDGE_STYLES = {
    "control": ("solid", "normal"), "data": ("solid", "normal"),
    "evidence": ("dotted", "normal"), "health": ("dashed", "normal"),
    "recovery": ("dashed", "vee"),
}
ABSOLUTE_PATH_PATTERN = re.compile(r"(?:/home/|/mnt/|/tmp/|/data/data/|[A-Za-z]:\\)")
EXTERNAL_REFERENCE_PATTERN = re.compile(r'(?:href|xlink:href)=["\'](?:https?:)?//', re.I)
SVG_RENDERER_REVISION = 6

VERTICAL_VIEW_IDS = {
    "runtime-topology",
    "network-boundaries",
    "data-projections",
    "frontend-state",
    "security",
    "backup-restore",
}


def _wrap_label(value: str, limit: int = 24, max_lines: int = 3) -> str:
    """Wrap Graphviz labels without changing the source model text."""
    words = value.split()
    if not words:
        return value
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        candidate = " ".join([*current, word])
        if current and len(candidate) > limit:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(" .") + "..."
    return "\n".join(lines)


def _layout_profile(graph_id: str, component_count: int, focus_id: str | None) -> dict[str, str]:
    """Return bounded Graphviz spacing appropriate to the diagram's information density."""
    if focus_id:
        return {"rankdir": "TB", "nodesep": "0.30", "ranksep": "0.52", "ratio": "compress", "splines": "spline"}
    if graph_id in VERTICAL_VIEW_IDS or component_count <= 7:
        return {"rankdir": "TB", "nodesep": "0.34", "ranksep": "0.58", "ratio": "compress", "splines": "spline"}
    if component_count >= 18:
        return {"rankdir": "LR", "nodesep": "0.34", "ranksep": "0.62", "ratio": "compress", "splines": "polyline"}
    return {"rankdir": "LR", "nodesep": "0.40", "ranksep": "0.72", "ratio": "compress", "splines": "polyline"}


class GraphvizRenderError(RuntimeError):
    """Raised when Graphviz cannot render a safe non-empty diagram."""


def q(value: Any) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def _html(value: str) -> str:
    return html.escape(value, quote=True)


def component_doc_url(component_id: str) -> str:
    return f"../../../../generated/production/architecture/components/{component_id}/"


CARD_VARIANTS = {
    "actor": "actor",
    "external": "actor",
    "external-app": "actor",
    "proxy": "gateway",
    "network": "gateway",
    "database": "state",
    "event": "state",
    "artifact": "state",
    "ui": "service",
    "service": "service",
    "process": "service",
    "decision": "service",
}
CARD_SHAPES = {
    "actor": "ellipse",
    "gateway": "box",
    "state": "cylinder",
    "service": "box",
}
ICON_ANCHOR_PREFIX = "PLICON__"


def _card_variant(component: dict[str, Any]) -> str:
    presentation = component.get("diagram_presentation") or {}
    requested = presentation.get("card_variant")
    if requested in CARD_SHAPES:
        return requested
    return CARD_VARIANTS.get(component["category"], "service")


def _icon_anchor(component_id: str) -> str:
    return f"{ICON_ANCHOR_PREFIX}{component_id}"


def _node_label(
    component_id: str,
    component: dict[str, Any],
    icon: IconRecord | None,
    *,
    focus: bool,
    poster: bool,
) -> str:
    """Build a bounded poster card with a deterministic Graphviz-owned icon anchor."""
    subtitle = _wrap_label(component["runtime_location"], limit=28, max_lines=2)
    responsibility = _wrap_label(component["responsibility"], limit=38 if poster else 34, max_lines=2)
    name = _wrap_label(component["name"], limit=25, max_lines=2)
    owner = _wrap_label(component.get("runtime_owner") or component.get("owner", ""), limit=24, max_lines=1)
    metadata = f"{subtitle} · {owner}" if owner and owner not in subtitle else subtitle
    text_width = 216 if poster else 188
    icon_cell = ""
    if icon:
        anchor = _html(f"#{_icon_anchor(component_id)}")
        icon_cell = (
            '<TD FIXEDSIZE="TRUE" WIDTH="58" HEIGHT="64" ALIGN="CENTER" VALIGN="MIDDLE" BORDER="1" BGCOLOR="#FFFFFF" '
            f'HREF="{anchor}" TITLE="Architecture icon anchor">'
            '<FONT POINT-SIZE="1">&#160;</FONT></TD>'
        )
    eyebrow = (
        '<FONT POINT-SIZE="7"><B>CURRENT COMPONENT</B></FONT><BR/>'
        if focus else ""
    )
    text_cell = (
        f'<TD WIDTH="{text_width}" ALIGN="LEFT" BALIGN="LEFT" VALIGN="MIDDLE">'
        f'{eyebrow}'
        f'<FONT POINT-SIZE="13"><B>{_html(name).replace(chr(10), "<BR/>")}</B></FONT><BR/>'
        f'<FONT POINT-SIZE="9">{_html(responsibility).replace(chr(10), "<BR/>")}</FONT><BR/>'
        f'<FONT POINT-SIZE="8"><I>{_html(metadata).replace(chr(10), "<BR/>")}</I></FONT>'
        '</TD>'
    )
    return (
        '<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0" CELLPADDING="6">'
        f'<TR>{icon_cell}{text_cell}</TR></TABLE>>'
    )


def _node_attrs(
    component_id: str,
    component: dict[str, Any],
    theme: dict[str, str],
    icons: dict[str, IconRecord],
    *,
    render_icons: bool,
    focus: bool = False,
    poster: bool = False,
) -> str:
    del render_icons  # Graphviz establishes anchor geometry; SVG postprocessing owns icon rendering.
    category = component["category"]
    icon = icons.get(component["icon"])
    variant = _card_variant(component)
    attrs: dict[str, str] = {
        "label": _node_label(
            component_id, component, icon, focus=focus, poster=poster
        ),
        "shape": CARD_SHAPES[variant],
        "style": "rounded,filled,bold" if focus else "rounded,filled",
        "fillcolor": theme.get(category, theme["cluster"]),
        "color": theme["foreground"] if focus else theme["edge"],
        "fontcolor": theme["foreground"],
        "penwidth": "2.5" if focus else "1.25",
        "tooltip": f"{component['name']}. {component['responsibility']}",
        "URL": component_doc_url(component_id),
        "target": "_top",
        "margin": "0.10,0.08",
    }
    if variant == "actor":
        attrs["margin"] = "0.16,0.11"
    rendered = []
    for name, value in attrs.items():
        if name == "label" and value.startswith("<<"):
            rendered.append(f"{name}={value}")
        else:
            rendered.append(f"{name}={q(value)}")
    return ", ".join(rendered)

def dot_for_graph(
    *,
    graph_id: str,
    title: str,
    description: str,
    component_ids: list[str],
    connections: list[dict[str, Any]],
    model: dict[str, Any],
    icons: dict[str, IconRecord],
    theme_name: str,
    focus_id: str | None = None,
    state_dependencies: list[str] | None = None,
    omitted_connection_count: int = 0,
    render_icons: bool = True,
    poster: dict[str, Any] | None = None,
) -> str:
    theme = THEMES[theme_name]
    graph_name = re.sub(r"[^A-Za-z0-9_]", "_", graph_id)
    layout = _layout_profile(graph_id, len(component_ids), focus_id)
    if poster:
        layout = {"rankdir": "LR", "nodesep": "0.34", "ranksep": "0.78", "ratio": "compress", "splines": "spline"}
    lines = [
        f"digraph {graph_name} {{",
        "  graph [",
        f'    rankdir={q(layout["rankdir"])},', f'    splines={q(layout["splines"])},', '    compound="true",',
        '    newrank="true",', f'    nodesep={q(layout["nodesep"])},',
        f'    ranksep={q(layout["ranksep"])},', f'    ratio={q(layout["ratio"])},',
        '    pad="0.20",', '    margin="0",', '    outputorder="edgesfirst",',
        f"    bgcolor={q(theme['background'])},", f"    fontcolor={q(theme['foreground'])},",
        '    fontname="Arial",', f"    label={q(title)},", '    labelloc="t",',
        '    fontsize="20"', "  ];",
        "  node [", '    fontname="Arial",', '    fontsize="10",',
        f"    color={q(theme['edge'])},", f"    fontcolor={q(theme['foreground'])},",
        '    margin="0.12,0.08"', "  ];",
        "  edge [", '    fontname="Arial",', '    fontsize="8",',
        f"    color={q(theme['edge'])},", f"    fontcolor={q(theme['muted'])},",
        '    arrowsize="0.72",', '    penwidth="1.15"', "  ];",
    ]
    selected = set(component_ids)
    if poster:
        zone_colors = POSTER_ZONE_COLORS[theme_name]
        visible_bands = set(poster.get("trust_boundary_bands", []))
        for zone_index, zone in enumerate(poster["zones"]):
            zone_members = [item for item in zone["components"] if item in selected]
            lines.extend([
                f"  subgraph {q('cluster_zone_' + zone['id'])} {{",
                f"    label={q(zone['label'])};",
                '    style="rounded,filled,bold";',
                f"    color={q(theme['cluster_border'])};",
                f"    fillcolor={q(zone_colors[zone_index % len(zone_colors)])};",
                f"    fontcolor={q(theme['foreground'])};",
                '    penwidth="1.6";',
                '    margin="18";',
            ])
            for boundary_id in poster.get("trust_boundary_bands", []):
                members = [
                    component_id for component_id in zone_members
                    if model["components"][component_id]["security_boundary"] == boundary_id
                ]
                if not members or boundary_id not in visible_bands:
                    continue
                boundary = model["boundaries"][boundary_id]
                lines.extend([
                    f"    subgraph {q('cluster_' + zone['id'] + '_' + boundary_id)} {{",
                    f"      label={q(boundary['name'])};",
                    '      style="rounded,dashed,filled";',
                    f"      color={q(theme['cluster_border'])};",
                    f"      fillcolor={q(theme['cluster'])};",
                    f"      fontcolor={q(theme['foreground'])};",
                    '      penwidth="1.0";',
                ])
                for component_id in members:
                    attrs = _node_attrs(
                        component_id, model["components"][component_id], theme, icons,
                        render_icons=render_icons, focus=component_id == focus_id, poster=True,
                    )
                    lines.append(f"      {q(component_id)} [{attrs}];")
                lines.append("    }")
            lines.append("  }")
        if poster.get("show_legend"):
            lines.extend([
                '  subgraph cluster_poster_legend {',
                f"    label={q('Legend and flow key')};",
                '    style="rounded,dashed";',
                f"    color={q(theme['cluster_border'])};",
                f"    fontcolor={q(theme['foreground'])};",
                '    rank="sink";',
                f"    poster_legend_brand [label={q('Brand icon\nVerified external technology')}, shape=box, style={q('rounded,filled')}, fillcolor={q(theme['proxy'])}];",
                f"    poster_legend_semantic [label={q('Semantic icon\nPocket Lab Lite role')}, shape=box, style={q('rounded,filled')}, fillcolor={q(theme['service'])}];",
                f"    poster_legend_primary [label={q('Bold solid\nPrimary control flow')}, shape=box, style={q('rounded,filled')}, fillcolor={q(theme['ui'])}];",
                f"    poster_legend_async [label={q('Dotted / dashed\nEvidence, health, recovery')}, shape=box, style={q('rounded,filled')}, fillcolor={q(theme['event'])}];",
            ])
            lines.append("  }")
    else:
        for boundary_id in sorted(model["boundaries"]):
            members = [
                component_id for component_id in component_ids
                if model["components"][component_id]["security_boundary"] == boundary_id
            ]
            if not members:
                continue
            boundary = model["boundaries"][boundary_id]
            lines.extend([
                f"  subgraph {q('cluster_' + boundary_id)} {{",
                f"    label={q(boundary['name'])};", '    style="rounded,dashed,filled";',
                f"    color={q(theme['cluster_border'])};", f"    fillcolor={q(theme['cluster'])};",
                f"    fontcolor={q(theme['foreground'])};", '    penwidth="1.0";',
            ])
            for component_id in members:
                attrs = _node_attrs(
                    component_id, model["components"][component_id], theme, icons,
                    render_icons=render_icons, focus=component_id == focus_id,
                )
                lines.append(f"    {q(component_id)} [{attrs}];")
            lines.append("  }")
    primary_flow_map: dict[str, tuple[int, str]] = {}
    if poster and poster.get("emphasize_primary_flows"):
        for flow_index, flow in enumerate(poster.get("primary_flows", []), start=1):
            for connection_id in flow["connections"]:
                primary_flow_map.setdefault(connection_id, (flow_index, flow["label"]))
    for connection in sorted(connections, key=lambda item: item["id"]):
        if connection["source"] not in selected or connection["target"] not in selected:
            continue
        kind = connection["kind"]
        style, arrowhead = EDGE_STYLES[kind]
        label = connection["label"]
        protocol = connection.get("protocol") or ""
        tooltip = label if not protocol else f"{label} ({protocol})"
        primary = primary_flow_map.get(connection["id"])
        if primary:
            flow_index, flow_label = primary
            display_label = f"{flow_index} · {label}"
            color = theme[kind]
            penwidth = "2.8"
            arrowsize = "0.92"
            tooltip = f"{flow_label}: {tooltip}"
        elif poster:
            display_label = label
            color = theme["muted"]
            penwidth = "0.85"
            arrowsize = "0.62"
        else:
            display_label = label
            color = theme[kind]
            penwidth = "1.15"
            arrowsize = "0.72"
        lines.append(
            f"  {q(connection['source'])} -> {q(connection['target'])} "
            f"[label={q(display_label)}, tooltip={q(tooltip)}, style={q(style)}, "
            f"arrowhead={q(arrowhead)}, color={q(color)}, fontcolor={q(color)}, "
            f"penwidth={q(penwidth)}, arrowsize={q(arrowsize)}];"
        )
    for index, dependency in enumerate(state_dependencies or []):
        node_id = f"state_dependency_{index}"
        lines.append(
            f"  {q(node_id)} [label={q(dependency)}, shape={q('note')}, style={q('filled')}, "
            f"fillcolor={q(theme['database'])}, color={q(theme['edge'])}, "
            f"fontcolor={q(theme['foreground'])}, tooltip={q('Durable-state dependency')}];"
        )
        if focus_id:
            lines.append(
                f"  {q(focus_id)} -> {q(node_id)} [label={q('state')}, style={q('dotted')}, "
                f"color={q(theme['data'])}, fontcolor={q(theme['data'])}];"
            )
    if omitted_connection_count:
        node_id = "additional_dependencies"
        label = f"Additional dependencies ({omitted_connection_count})"
        lines.append(
            f"  {q(node_id)} [label={q(label)}, shape={q('note')}, style={q('dashed,filled')}, "
            f"fillcolor={q(theme['cluster'])}, color={q(theme['edge'])}, "
            f"fontcolor={q(theme['foreground'])}, tooltip={q(label)}];"
        )
        if focus_id:
            lines.append(
                f"  {q(focus_id)} -> {q(node_id)} [style={q('dotted')}, arrowhead={q('none')}, "
                f"color={q(theme['muted'])}];"
            )
    lines.append("}")
    source = "\n".join(lines) + "\n"
    if ABSOLUTE_PATH_PATTERN.search(source) and not render_icons:
        raise GraphvizRenderError(f"Public DOT for {graph_id} contains an absolute path")
    return source


def _embedded_icon_use(
    icon: EmbeddedIcon, *, x: float, y: float, width: float, height: float, css_class: str
) -> str:
    return (
        f'<use class="{css_class}" href="#{icon.symbol_id}" x="{x:.2f}" y="{y:.2f}" '
        f'width="{width:.2f}" height="{height:.2f}" '
        'preserveAspectRatio="xMidYMid meet" aria-hidden="true"/>'
    )


def _embed_icon_anchors(
    svg: str,
    *,
    component_icons: dict[str, tuple[IconRecord, ...]],
    registry: dict[str, IconRecord],
    theme_name: str,
) -> str:
    """Replace exact Graphviz-owned icon-cell anchors with embedded SVG symbols."""
    cache: dict[str, EmbeddedIcon] = {}
    resolved_by_component: dict[str, tuple[EmbeddedIcon, ...]] = {}
    fallback_used: list[str] = []
    for component_id, records in sorted(component_icons.items()):
        resolved: list[EmbeddedIcon] = []
        for record in records[:4]:
            resolved_record, embedded, used_fallback = resolve_with_fallback(
                record, registry, cache=cache
            )
            if used_fallback:
                fallback_used.append(f"{component_id}:{record.id}->{resolved_record.id}")
            if embedded.icon_id not in {item.icon_id for item in resolved}:
                resolved.append(embedded)
        if not resolved:
            raise GraphvizRenderError(f"No embeddable icon remains for component {component_id}")
        resolved_by_component[component_id] = tuple(resolved)

    anchor_pattern = re.compile(
        r'<a\b(?P<attrs>[^>]*(?:xlink:href|href)=["\']#PLICON__(?P<component>[^"\']+)["\'][^>]*)>'
        r'(?P<body>.*?)</a>',
        flags=re.I | re.S,
    )
    seen: dict[str, int] = {}

    def replace_anchor(match: re.Match[str]) -> str:
        component_id = html.unescape(match.group("component"))
        seen[component_id] = seen.get(component_id, 0) + 1
        records = resolved_by_component.get(component_id)
        if not records:
            raise GraphvizRenderError(
                f"Graphviz emitted icon anchor for unknown component {component_id}"
            )
        polygon = re.search(r'<polygon\b[^>]*\bpoints=["\'](?P<points>[^"\']+)["\']', match.group("body"), re.I)
        if polygon is None:
            raise GraphvizRenderError(f"Icon anchor for {component_id} lacks Graphviz cell geometry")
        coordinates: list[tuple[float, float]] = []
        for token in polygon.group("points").split():
            if "," not in token:
                continue
            raw_x, raw_y = token.split(",", 1)
            try:
                coordinates.append((float(raw_x), float(raw_y)))
            except ValueError as exc:
                raise GraphvizRenderError(
                    f"Icon anchor for {component_id} has invalid cell coordinates"
                ) from exc
        if len(coordinates) < 4:
            raise GraphvizRenderError(f"Icon anchor for {component_id} has incomplete geometry")
        min_x = min(item[0] for item in coordinates)
        max_x = max(item[0] for item in coordinates)
        min_y = min(item[1] for item in coordinates)
        max_y = max(item[1] for item in coordinates)
        cell_width = max_x - min_x
        cell_height = max_y - min_y
        if cell_width < 28 or cell_height < 28:
            raise GraphvizRenderError(
                f"Icon anchor for {component_id} collapsed to {cell_width:.2f}x{cell_height:.2f}"
            )
        tile_size = min(44.0, cell_width - 8.0, cell_height - 8.0)
        tile_x = min_x + (cell_width - tile_size) / 2
        tile_y = min_y + (cell_height - tile_size) / 2
        tile_fill = "#ffffff" if theme_name == "light" else "#f8fafc"
        tile_stroke = "#cbd5e1" if theme_name == "light" else "#94a3b8"
        fragments = [
            f'<g class="pl-node-icon" data-component="{html.escape(component_id, quote=True)}" '
            f'data-icon-cell="{min_x:.2f},{min_y:.2f},{cell_width:.2f},{cell_height:.2f}" '
            f'data-icon-tile="{tile_x:.2f},{tile_y:.2f},{tile_size:.2f},{tile_size:.2f}" '
            'aria-hidden="true">',
            f'<rect class="pl-node-icon__tile" x="{tile_x:.2f}" y="{tile_y:.2f}" '
            f'width="{tile_size:.2f}" height="{tile_size:.2f}" rx="8" '
            f'fill="{tile_fill}" stroke="{tile_stroke}" stroke-width="1.1"/>',
            _embedded_icon_use(
                records[0], x=tile_x + 8, y=tile_y + 7, width=tile_size - 16,
                height=tile_size - 16, css_class="pl-node-icon__primary",
            ),
        ]
        badges = records[1:4]
        badge_size = 11.0
        badge_y = tile_y + tile_size - badge_size + 1.5
        badge_start_x = tile_x + tile_size - badge_size - max(0, len(badges) - 1) * 10.0 - 1.5
        for badge_index, badge in enumerate(badges):
            badge_x = badge_start_x + badge_index * 10.0
            fragments.extend([
                f'<rect class="pl-node-icon__badge-tile" x="{badge_x - 1:.2f}" '
                f'y="{badge_y - 1:.2f}" width="{badge_size + 2:.2f}" '
                f'height="{badge_size + 2:.2f}" rx="3" fill="{tile_fill}" '
                f'stroke="{tile_stroke}" stroke-width="0.7"/>',
                _embedded_icon_use(
                    badge, x=badge_x, y=badge_y, width=badge_size, height=badge_size,
                    css_class="pl-node-icon__badge",
                ),
            ])
        fragments.append('</g>')
        return "".join(fragments)

    svg = anchor_pattern.sub(replace_anchor, svg)
    for component_id in resolved_by_component:
        count = seen.get(component_id, 0)
        if count != 1:
            raise GraphvizRenderError(
                f"Expected exactly one icon anchor for {component_id}; Graphviz emitted {count}"
            )
    if ICON_ANCHOR_PREFIX in svg:
        raise GraphvizRenderError("Unresolved architecture icon anchor remains after rendering")
    defs = symbol_defs_from_icons(cache.values())
    svg = re.sub(r'(<svg\b[^>]*>\n?)', r'\1' + defs, svg, count=1)
    if fallback_used:
        marker = html.escape(";".join(sorted(fallback_used)))
        svg = re.sub(
            r'(<svg\b[^>]*>\n?)',
            r'\1<metadata id="pocketlab-icon-fallbacks">' + marker + '</metadata>\n',
            svg, count=1,
        )
    if re.search(r'<image\b[^>]*(?:href|xlink:href)=', svg, re.I):
        raise GraphvizRenderError("Generated architecture SVG retained an external image reference")
    return svg

def _normalize_svg(
    svg: str, *, graph_id: str, theme_name: str, title: str, description: str,
    component_icons: dict[str, tuple[IconRecord, ...]], registry: dict[str, IconRecord],
    source_fingerprint: str,
) -> str:
    svg = svg.replace("\r\n", "\n")
    svg = re.sub(r"<!DOCTYPE svg PUBLIC.*?>\n?", "", svg, flags=re.S)
    svg = re.sub(r"<!-- Generated by graphviz version .*? -->\n?", "", svg)
    svg = re.sub(r"<!-- Title: .*? -->\n?", "", svg)
    svg = re.sub(r"<title>.*?</title>\n?", "", svg, count=1, flags=re.S)
    svg = _embed_icon_anchors(
        svg, component_icons=component_icons, registry=registry, theme_name=theme_name
    )
    safe_id = re.sub(r"[^a-z0-9-]", "-", graph_id.lower())
    svg_id = f"pocketlab-{safe_id}-{theme_name}"
    view_box_match = re.search(
        r'viewBox="(?P<min_x>-?[0-9.]+) (?P<min_y>-?[0-9.]+) '
        r'(?P<width>[0-9.]+) (?P<height>[0-9.]+)"',
        svg,
    )
    if not view_box_match:
        raise GraphvizRenderError(
            f"SVG for {graph_id}/{theme_name} lacks a numeric viewBox"
        )
    intrinsic_width = view_box_match.group("width")
    intrinsic_height = view_box_match.group("height")
    svg = re.sub(r'\s(?:width|height)="[^"]*"', "", svg, count=2)
    svg = re.sub(
        r"<svg\s+",
        f'<svg id="{svg_id}" role="img" aria-labelledby="{svg_id}-title {svg_id}-desc" '
        f'width="{intrinsic_width}" height="{intrinsic_height}" '
        'preserveAspectRatio="xMidYMid meet" focusable="false" ',
        svg, count=1,
    )
    accessible = (
        f'<title id="{svg_id}-title">{html.escape(title)}</title>\n'
        f'<desc id="{svg_id}-desc">{html.escape(description)}</desc>\n'
        f'<metadata id="pocketlab-source-fingerprint">{source_fingerprint}</metadata>\n'
    )
    svg = re.sub(r"(<svg[^>]*>\n?)", r"\1" + accessible, svg, count=1)
    svg = re.sub(r"\s+$", "\n", svg)
    if ABSOLUTE_PATH_PATTERN.search(svg):
        raise GraphvizRenderError(f"SVG for {graph_id}/{theme_name} contains an absolute path")
    if "<svg" not in svg or "<title id=" not in svg or "<desc id=" not in svg:
        raise GraphvizRenderError(f"SVG for {graph_id}/{theme_name} lacks accessibility metadata")
    if len(svg) < 300:
        raise GraphvizRenderError(f"Graphviz produced an empty or implausibly small SVG for {graph_id}")
    return svg


def render_svg(
    render_dot: str, *, graph_id: str, theme_name: str, title: str, description: str,
    icons: dict[str, IconRecord], public_icon_prefix: str,
    component_icons: dict[str, tuple[IconRecord, ...]], source_fingerprint: str,
) -> tuple[str, bool]:
    executable = shutil.which("dot")
    if not executable:
        raise GraphvizRenderError(
            "Graphviz 'dot' is missing. Run scripts/dev/lite/setup-documentation-tools.sh --install-missing."
        )
    completed = subprocess.run(
        [executable, "-Tsvg"], input=render_dot, text=True, cwd=ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        env={**os.environ, "LC_ALL": "C", "LANG": "C"},
    )
    if completed.returncode != 0:
        return completed.stderr.strip(), False
    return _normalize_svg(
        completed.stdout, graph_id=graph_id, theme_name=theme_name, title=title,
        description=description, component_icons=component_icons, registry=icons,
        source_fingerprint=source_fingerprint,
    ), True


def _svg_source_fingerprint(public_dot: str) -> str:
    payload = f"{SVG_RENDERER_REVISION}\0{public_dot}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _read_reusable_svg(path: Path, source_fingerprint: str) -> str | None:
    try:
        svg = path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError, UnicodeDecodeError):
        return None
    marker = f'<metadata id="pocketlab-source-fingerprint">{source_fingerprint}</metadata>'
    if marker not in svg:
        return None
    if "<title id=" not in svg or "<desc id=" not in svg or 'role="img"' not in svg:
        return None
    if '<symbol id="pl-icon-' not in svg or '<use class="pl-node-icon__primary"' not in svg:
        return None
    if '<image href=' in svg or ICON_ANCHOR_PREFIX in svg:
        return None
    if ABSOLUTE_PATH_PATTERN.search(svg) or EXTERNAL_REFERENCE_PATTERN.search(svg):
        return None
    return svg


def render_graph_pair(
    *, graph_id: str, title: str, description: str, component_ids: list[str],
    connections: list[dict[str, Any]], model: dict[str, Any], icons: dict[str, IconRecord],
    focus_id: str | None = None, state_dependencies: list[str] | None = None,
    omitted_connection_count: int = 0, public_icon_prefix: str = "../icons",
    existing_outputs: dict[str, Path] | None = None,
    poster: dict[str, Any] | None = None,
) -> tuple[dict[str, str], bool]:
    outputs: dict[str, str] = {}
    icon_fallback_used = False
    component_icons: dict[str, tuple[IconRecord, ...]] = {}
    for component_id in component_ids:
        component = model["components"][component_id]
        icon_ids = [component["icon"], *component.get("technology_icons", [])]
        resolved = tuple(icons[icon_id] for icon_id in icon_ids if icon_id in icons)
        if resolved:
            component_icons[component_id] = resolved
    for theme_name in ("light", "dark"):
        render_source = dot_for_graph(
            graph_id=graph_id, title=title, description=description,
            component_ids=component_ids, connections=connections, model=model, icons=icons,
            theme_name=theme_name, focus_id=focus_id, state_dependencies=state_dependencies,
            omitted_connection_count=omitted_connection_count, render_icons=False,
            poster=poster,
        )
        public_source = render_source
        for record in icons.values():
            public_source = public_source.replace(str(record.path), f"{public_icon_prefix}/{record.path.name}")
        if ABSOLUTE_PATH_PATTERN.search(public_source):
            raise GraphvizRenderError(f"DOT for {graph_id}/{theme_name} contains absolute paths")
        source_fingerprint = _svg_source_fingerprint(public_source)
        existing_svg = None
        if existing_outputs:
            existing_svg = _read_reusable_svg(
                existing_outputs.get(f"{theme_name}.svg", Path("__missing__")),
                source_fingerprint,
            )
        if existing_svg is None:
            svg_or_error, ok = render_svg(
                render_source, graph_id=graph_id, theme_name=theme_name, title=title,
                description=description, icons=icons, public_icon_prefix=public_icon_prefix,
                component_icons=component_icons, source_fingerprint=source_fingerprint,
            )
            if not ok:
                raise GraphvizRenderError(
                    f"Graphviz failed for {graph_id}/{theme_name}: {svg_or_error}"
                )
            existing_svg = svg_or_error
        outputs[f"{theme_name}.dot"] = public_source
        outputs[f"{theme_name}.svg"] = existing_svg
    return outputs, icon_fallback_used


def render_view(
    model: dict[str, Any], index: ArchitectureIndex, icons: dict[str, IconRecord], view_id: str,
    *, existing_outputs: dict[str, Path] | None = None,
) -> tuple[dict[str, str], bool]:
    view = model["views"][view_id]
    return render_graph_pair(
        graph_id=view_id, title=view["title"], description=view["description"],
        component_ids=list(view["components"]),
        connections=list(index.view_connections[view_id]), model=model, icons=icons,
        existing_outputs=existing_outputs, poster=view.get("poster"),
    )


def render_component(
    model: dict[str, Any], index: ArchitectureIndex, icons: dict[str, IconRecord], component_id: str,
    *, existing_outputs: dict[str, Path] | None = None,
) -> tuple[dict[str, str], dict[str, Any], bool]:
    mini = derive_mini_graph(model, index, component_id)
    component = model["components"][component_id]
    outputs, fallback = render_graph_pair(
        graph_id=f"component-{component_id}", title=f"{component['name']} connections",
        description=(
            f"Inputs, outputs, durable state, evidence, failure, and recovery relationships for "
            f"{component['name']}."
        ), component_ids=mini["component_ids"], connections=mini["connections"],
        model=model, icons=icons, focus_id=component_id,
        state_dependencies=mini["state_dependencies"],
        omitted_connection_count=mini["omitted_connection_count"],
        existing_outputs=existing_outputs,
    )
    return outputs, mini, fallback
