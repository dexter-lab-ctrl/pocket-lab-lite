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
SVG_RENDERER_REVISION = 2


class GraphvizRenderError(RuntimeError):
    """Raised when Graphviz cannot render a safe non-empty diagram."""


def q(value: Any) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def _html(value: str) -> str:
    return html.escape(value, quote=True)


def component_doc_url(component_id: str) -> str:
    return f"../../../../generated/production/architecture/components/{component_id}/"


def _node_label(
    component: dict[str, Any], icon: IconRecord | None, *, render_icons: bool
) -> str:
    subtitle = component["runtime_location"]
    responsibility = component["responsibility"]
    if len(responsibility) > 88:
        responsibility = responsibility[:85].rstrip() + "..."
    cells = []
    if icon:
        if render_icons:
            cells.append(
                f'<TD FIXEDSIZE="TRUE" WIDTH="38" HEIGHT="38"><IMG SRC="{_html(str(icon.path))}" '
                'SCALE="TRUE"/></TD>'
            )
        else:
            cells.append('<TD FIXEDSIZE="TRUE" WIDTH="38" HEIGHT="38"> </TD>')
    cells.append(
        '<TD ALIGN="LEFT">'
        f'<FONT POINT-SIZE="12"><B>{_html(component["name"])}</B></FONT><BR/>'
        f'<FONT POINT-SIZE="9">{_html(responsibility)}</FONT><BR/>'
        f'<FONT POINT-SIZE="8">{_html(subtitle)}</FONT>'
        '</TD>'
    )
    return '<<TABLE BORDER="0" CELLBORDER="0" CELLPADDING="4"><TR>' + "".join(cells) + "</TR></TABLE>>"


def _node_attrs(
    component_id: str,
    component: dict[str, Any],
    theme: dict[str, str],
    icons: dict[str, IconRecord],
    *,
    render_icons: bool,
    focus: bool = False,
) -> str:
    category = component["category"]
    icon = icons.get(component["icon"])
    attrs: dict[str, str] = {
        "label": _node_label(component, icon, render_icons=render_icons),
        "shape": SHAPES.get(category, "box"),
        "style": "rounded,filled,bold" if focus else "rounded,filled",
        "fillcolor": theme.get(category, theme["cluster"]),
        "color": theme["foreground"] if focus else theme["edge"],
        "fontcolor": theme["foreground"],
        "penwidth": "2.2" if focus else "1.15",
        "tooltip": f"{component['name']}. {component['responsibility']}",
        "URL": component_doc_url(component_id),
        "target": "_top",
    }
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
) -> str:
    theme = THEMES[theme_name]
    graph_name = re.sub(r"[^A-Za-z0-9_]", "_", graph_id)
    lines = [
        f"digraph {graph_name} {{",
        "  graph [",
        '    rankdir="LR",', '    splines="ortho",', '    compound="true",',
        '    newrank="true",', '    nodesep="0.38",', '    ranksep="0.72",',
        '    pad="0.25",', '    margin="0",', '    outputorder="edgesfirst",',
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
    for connection in sorted(connections, key=lambda item: item["id"]):
        if connection["source"] not in selected or connection["target"] not in selected:
            continue
        kind = connection["kind"]
        style, arrowhead = EDGE_STYLES[kind]
        label = connection["label"]
        protocol = connection.get("protocol") or ""
        tooltip = label if not protocol else f"{label} ({protocol})"
        lines.append(
            f"  {q(connection['source'])} -> {q(connection['target'])} "
            f"[label={q(label)}, tooltip={q(tooltip)}, style={q(style)}, "
            f"arrowhead={q(arrowhead)}, color={q(theme[kind])}, fontcolor={q(theme[kind])}];"
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


def _inject_icon_references(
    svg: str, *, component_icons: dict[str, IconRecord], public_icon_prefix: str
) -> str:
    """Inject local icon references into Graphviz node groups across Graphviz versions."""
    cursor = 0
    while True:
        node_match = re.search(
            r'<g\b(?=[^>]*\bclass=["\']node["\'])[^>]*>',
            svg[cursor:],
            flags=re.I,
        )
        if node_match is None:
            break
        node_start = cursor + node_match.start()
        next_node = re.search(
            r'<g\b(?=[^>]*\bclass=["\']node["\'])[^>]*>',
            svg[node_start + 1:],
            flags=re.I,
        )
        node_end = (
            node_start + 1 + next_node.start()
            if next_node is not None
            else len(svg)
        )
        block = svg[node_start:node_end]
        title_match = re.search(r'<title>(?P<id>[^<]+)</title>', block)
        if title_match is None:
            cursor = node_end
            continue
        component_id = html.unescape(title_match.group("id"))
        icon = component_icons.get(component_id)
        if icon is None or re.search(r'<image\b[^>]*(?:href|xlink:href)=', block, re.I):
            cursor = node_end
            continue
        text_match = re.search(
            r'<text\b[^>]*\bx="(?P<x>-?[0-9.]+)"[^>]*\by="(?P<y>-?[0-9.]+)"[^>]*>',
            block,
            flags=re.I,
        )
        if text_match is None:
            cursor = node_end
            continue
        x = float(text_match.group("x")) - 31.0
        y = float(text_match.group("y")) - 15.5
        image = (
            f'<image href="{public_icon_prefix}/{icon.path.name}" x="{x:.2f}" y="{y:.2f}" '
            'width="24" height="24" preserveAspectRatio="xMidYMid meet" aria-hidden="true"/>\n'
        )
        insertion = node_start + block.index('<text ', text_match.start())
        svg = svg[:insertion] + image + svg[insertion:]
        cursor = node_end + len(image)
    return svg


def _normalize_svg(
    svg: str, *, graph_id: str, theme_name: str, title: str, description: str,
    icon_paths: list[Path], public_icon_prefix: str,
    component_icons: dict[str, IconRecord], source_fingerprint: str,
) -> str:
    svg = svg.replace("\r\n", "\n")
    svg = re.sub(r"<!DOCTYPE svg PUBLIC.*?>\n?", "", svg, flags=re.S)
    svg = re.sub(r"<!-- Generated by graphviz version .*? -->\n?", "", svg)
    svg = re.sub(r"<!-- Title: .*? -->\n?", "", svg)
    svg = re.sub(r"<title>.*?</title>\n?", "", svg, count=1, flags=re.S)
    for icon_path in icon_paths:
        svg = svg.replace(str(icon_path), f"{public_icon_prefix}/{icon_path.name}")
    svg = _inject_icon_references(
        svg, component_icons=component_icons, public_icon_prefix=public_icon_prefix
    )
    safe_id = re.sub(r"[^a-z0-9-]", "-", graph_id.lower())
    svg_id = f"pocketlab-{safe_id}-{theme_name}"
    svg = re.sub(
        r"<svg\s+", f'<svg id="{svg_id}" role="img" aria-labelledby="{svg_id}-title {svg_id}-desc" ',
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
    component_icons: dict[str, IconRecord], source_fingerprint: str,
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
        description=description, icon_paths=[record.path for record in icons.values()],
        public_icon_prefix=public_icon_prefix, component_icons=component_icons,
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
    if '<image href="../icons/' not in svg:
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
) -> tuple[dict[str, str], bool]:
    outputs: dict[str, str] = {}
    icon_fallback_used = False
    component_icons = {
        component_id: icons[model["components"][component_id]["icon"]]
        for component_id in component_ids
        if model["components"][component_id]["icon"] in icons
    }
    for theme_name in ("light", "dark"):
        render_source = dot_for_graph(
            graph_id=graph_id, title=title, description=description,
            component_ids=component_ids, connections=connections, model=model, icons=icons,
            theme_name=theme_name, focus_id=focus_id, state_dependencies=state_dependencies,
            omitted_connection_count=omitted_connection_count, render_icons=False,
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
        existing_outputs=existing_outputs,
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
