#!/usr/bin/env python3
"""Generate deterministic, linked Pocket Lab Lite architecture diagrams with Graphviz."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
METADATA = ROOT / "architecture" / "metadata" / "diagrams.json"
OUTPUT = ROOT / "docs" / "assets" / "diagrams"
GALLERY = ROOT / "docs" / "generated" / "development" / "architecture-diagrams.md"
NAME_MAP = {"prepared-projection-flow": "projection-flow"}

THEMES = {
    "light": {
        "background": "#ffffff",
        "foreground": "#182230",
        "muted": "#475569",
        "edge": "#64748b",
        "ui": "#e0f2fe",
        "service": "#e0e7ff",
        "process": "#dcfce7",
        "database": "#fef3c7",
        "event": "#fce7f3",
        "decision": "#ffedd5",
        "boundary": "#f8fafc",
    },
    "dark": {
        "background": "#101827",
        "foreground": "#f8fafc",
        "muted": "#cbd5e1",
        "edge": "#94a3b8",
        "ui": "#0c4a6e",
        "service": "#312e81",
        "process": "#14532d",
        "database": "#78350f",
        "event": "#831843",
        "decision": "#7c2d12",
        "boundary": "#1e293b",
    },
}

SHAPES = {
    "ui": "box",
    "service": "box",
    "process": "component",
    "database": "cylinder",
    "event": "parallelogram",
    "decision": "diamond",
    "cloud": "ellipse",
    "boundary": "box",
}


def quoted(value: str) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def dot_source(key: str, diagram: dict[str, Any], theme_name: str) -> str:
    theme = THEMES[theme_name]
    graph_name = re.sub(r"[^A-Za-z0-9_]", "_", key)
    lines = [
        f"digraph {graph_name} {{",
        "  graph [",
        f"    rankdir={diagram.get('rankdir', 'LR')},",
        "    splines=ortho,",
        "    compound=true,",
        "    newrank=true,",
        "    outputorder=edgesfirst,",
        "    nodesep=0.42,",
        "    ranksep=0.72,",
        "    pad=0.25,",
        "    margin=0,",
        f"    bgcolor={quoted(theme['background'])},",
        f"    fontcolor={quoted(theme['foreground'])},",
        '    fontname="Arial",',
        f"    label={quoted(diagram['title'])},",
        '    labelloc="t",',
        '    fontsize="20"',
        "  ];",
        "  node [",
        '    fontname="Arial",',
        '    fontsize="11",',
        '    style="rounded,filled",',
        f"    color={quoted(theme['edge'])},",
        f"    fontcolor={quoted(theme['foreground'])},",
        '    penwidth="1.2",',
        '    margin="0.16,0.10"',
        "  ];",
        "  edge [",
        '    fontname="Arial",',
        '    fontsize="9",',
        f"    color={quoted(theme['edge'])},",
        f"    fontcolor={quoted(theme['muted'])},",
        '    arrowsize="0.75",',
        '    penwidth="1.1"',
        "  ];",
    ]
    nodes = {node[0]: node for node in diagram.get("nodes", [])}
    grouped_nodes: set[str] = set()

    def render_node(node: list[str], indent: str = "  ") -> None:
        node_id, label, kind, url = node
        shape = SHAPES.get(kind, "box")
        fill = theme.get(kind, theme["boundary"])
        attrs = {
            "label": label,
            "shape": shape,
            "fillcolor": fill,
            "tooltip": f"{label}. {diagram['description']}",
            "URL": url,
            "target": "_top",
        }
        if kind == "decision":
            attrs["style"] = "filled"
        elif kind == "boundary":
            attrs["style"] = "rounded,dashed,filled"
        rendered = ", ".join(f"{name}={quoted(value)}" for name, value in attrs.items())
        lines.append(f"{indent}{quoted(node_id)} [{rendered}];")

    for group_id, group_label, member_ids in sorted(
        diagram.get("groups", []), key=lambda group: group[0]
    ):
        safe_group = re.sub(r"[^A-Za-z0-9_]", "_", group_id)
        lines.extend([
            f"  subgraph cluster_{safe_group} {{",
            f"    label={quoted(group_label)};",
            '    style="rounded,dashed";',
            f"    color={quoted(theme['edge'])};",
            f"    fontcolor={quoted(theme['muted'])};",
            '    penwidth="1.0";',
            '    margin="16";',
        ])
        for node_id in sorted(member_ids):
            if node_id not in nodes:
                raise ValueError(f"Unknown node {node_id!r} in group {group_id!r} for {key}")
            render_node(nodes[node_id], indent="    ")
            grouped_nodes.add(node_id)
        lines.append("  }")

    for node_id in sorted(nodes):
        if node_id not in grouped_nodes:
            render_node(nodes[node_id])
    for edge in sorted(diagram.get("edges", []), key=lambda item: (item[0], item[1], item[2])):
        source, target, label = edge
        lines.append(
            f"  {quoted(source)} -> {quoted(target)} "
            f"[label={quoted(label)}, tooltip={quoted(label)}];"
        )
    lines.append("}")
    return "\n".join(lines) + "\n"


def normalize_svg(svg: str, *, title: str, description: str, key: str, theme: str) -> str:
    svg = svg.replace("\r\n", "\n")
    svg = re.sub(r"<!DOCTYPE svg PUBLIC.*?>\n?", "", svg, flags=re.S)
    svg = re.sub(r"<!-- Generated by graphviz version .*? -->\n?", "", svg)
    svg = re.sub(r"<!-- Title: .*? -->\n?", "", svg)
    svg = re.sub(r"<title>.*?</title>\n?", "", svg, count=1, flags=re.S)
    svg_id = f"pocketlab-{key}-{theme}"
    svg = re.sub(
        r"<svg\s+",
        f'<svg id="{svg_id}" role="img" aria-labelledby="{svg_id}-title {svg_id}-desc" ',
        svg,
        count=1,
    )
    accessible = (
        f"<title id=\"{svg_id}-title\">{html.escape(title)}</title>\n"
        f"<desc id=\"{svg_id}-desc\">{html.escape(description)}</desc>\n"
    )
    svg = re.sub(r"(<svg[^>]*>\n?)", r"\1" + accessible, svg, count=1)
    svg = re.sub(r"\s+$", "\n", svg)
    return svg


def render_dot(source: str, *, title: str, description: str, key: str, theme: str) -> str:
    executable = shutil.which("dot")
    if not executable:
        raise RuntimeError(
            "Graphviz 'dot' is missing. Run scripts/dev/lite/setup-documentation-tools.sh --install-missing."
        )
    completed = subprocess.run(
        [executable, "-Tsvg"],
        input=source,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        env={**os.environ, "LC_ALL": "C", "LANG": "C"},
    )
    if completed.returncode != 0:
        raise RuntimeError(f"Graphviz failed for {key}/{theme}: {completed.stderr.strip()}")
    return normalize_svg(
        completed.stdout,
        title=title,
        description=description,
        key=key,
        theme=theme,
    )



def gallery_source(data: dict[str, Any]) -> str:
    lines = [
        "---",
        'title: "Architecture diagram catalog"',
        'description: "Generated light and dark architecture diagrams for Pocket Lab Lite."',
        "status: verified",
        "generated: true",
        "audience: development",
        "generator: scripts/docs/graphviz/generate_lite_diagrams.py",
        "schema_revision: 1",
        "validation_status: generated",
        "---",
        "",
        "# Architecture diagram catalog",
        "",
        "These diagrams are generated from `architecture/metadata/diagrams.json`. Edit the metadata, then run `task lite:docs:generate`; never hand-edit generated DOT or SVG files.",
        "",
    ]
    for metadata_key, diagram in sorted(data.get("diagrams", {}).items()):
        output_key = NAME_MAP.get(metadata_key, metadata_key)
        lines.extend([
            f"## {diagram['title']}",
            "",
            diagram["description"],
            "",
            f'![{diagram["title"]}](../../assets/diagrams/{output_key}.light.svg#only-light)',
            "",
            f'![{diagram["title"]}](../../assets/diagrams/{output_key}.dark.svg#only-dark)',
            "",
        ])
    return "\n".join(lines).rstrip() + "\n"

def build_outputs() -> dict[Path, str]:
    data = json.loads(METADATA.read_text(encoding="utf-8"))
    outputs: dict[Path, str] = {}
    for metadata_key, diagram in sorted(data.get("diagrams", {}).items()):
        output_key = NAME_MAP.get(metadata_key, metadata_key)
        for theme_name in ("light", "dark"):
            source = dot_source(metadata_key, diagram, theme_name)
            outputs[OUTPUT / f"{output_key}.{theme_name}.dot"] = source
            outputs[OUTPUT / f"{output_key}.{theme_name}.svg"] = render_dot(
                source,
                title=diagram["title"],
                description=diagram["description"],
                key=output_key,
                theme=theme_name,
            )
    outputs[GALLERY] = gallery_source(data)
    manifest_payload = {
        "schema_revision": 1,
        "generated": True,
        "generated_at": os.environ.get("SOURCE_GENERATED_AT", "").strip() or "uncommitted",
        "source_commit": os.environ.get("SOURCE_COMMIT", "").strip() or "uncommitted",
        "generator": "scripts/docs/graphviz/generate_lite_diagrams.py",
        "generator_version": 1,
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "validation_state": "generated",
        "source": "architecture/metadata/diagrams.json",
        "source_sha256": hashlib.sha256(METADATA.read_bytes()).hexdigest(),
        "diagram_count": len(data.get("diagrams", {})),
        "themes": ["light", "dark"],
        "outputs": sorted(path.relative_to(ROOT).as_posix() for path in outputs),
    }
    outputs[OUTPUT / "manifest.json"] = json.dumps(manifest_payload, indent=2, sort_keys=True) + "\n"
    return outputs


def write_outputs(outputs: dict[Path, str]) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    expected = {path.name for path in outputs}
    for stale in OUTPUT.glob("*.dot"):
        if stale.name not in expected:
            stale.unlink()
    for stale in OUTPUT.glob("*.svg"):
        if stale.name not in expected:
            stale.unlink()
    for path, content in sorted(outputs.items(), key=lambda item: item[0].as_posix()):
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(path)


def check_outputs(outputs: dict[Path, str]) -> int:
    drift = []
    for path, expected in sorted(outputs.items(), key=lambda item: item[0].as_posix()):
        if not path.exists() or path.read_text(encoding="utf-8") != expected:
            drift.append(path.relative_to(ROOT).as_posix())
    if drift:
        print("Graphviz documentation drift detected:")
        for path in drift:
            print(f" - {path}")
        return 1
    print(f"PASS {len(outputs)} Graphviz artifacts are current")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("generate", "check"))
    args = parser.parse_args()
    outputs = build_outputs()
    if args.command == "generate":
        write_outputs(outputs)
        print(f"Generated {len(outputs)} Graphviz artifacts")
        return 0
    return check_outputs(outputs)


if __name__ == "__main__":
    raise SystemExit(main())
