#!/usr/bin/env python3
"""Generate Production architecture Markdown and the searchable component catalog."""
from __future__ import annotations

import hashlib
import html
import json
import posixpath
from pathlib import Path
from typing import Any

from architecture_model import ArchitectureIndex, ROOT, fingerprint
from icon_registry import IconRecord

GENERATOR = "scripts/docs/graphviz/generate_lite_architecture.py"
DOC_ROOT = Path("docs/generated/production/architecture")
INDEX_DIAGRAM_ROOT = "../../../assets/diagrams/production"
VIEW_DIAGRAM_ROOT = "../../../../assets/diagrams/production"
COMPONENT_DIAGRAM_ROOT = "../../../../../assets/diagrams/production"
INDEX_ICON_ROOT = "../../../assets/diagrams/production/icons"
VIEW_ICON_ROOT = "../../../../assets/diagrams/production/icons"
COMPONENT_ICON_ROOT = "../../../../../assets/diagrams/production/icons"

INFRASTRUCTURE_SUMMARY = [
    ("Experience surface", "Browser, React/Vite PWA, and frontend state provide the self-hosted workspace experience."),
    ("Control plane", "Caddy fronts FastAPI /api/lite/*, prepared reads, and guarded write surfaces."),
    ("Event runtime", "NATS / JetStream, worker subprocesses, command lifecycle, and evidence flows coordinate execution."),
    ("Durable state", "SQLite prepared projections and lifecycle tables preserve truthful, auditable state."),
    ("Device runtime", "Node agent, supervisor, PM2, and recovery loops run on enrolled Android/Termux or Ubuntu devices."),
    ("Remote access and apps", "Tailscale, tailscaled, PROot Ubuntu, and PhotoPrism show remote-access and app-hosting boundaries."),
]

WIDE_DIAGRAMS = {
    "complete-system",
    "request-control",
    "apps-lifecycle",
    "audit-evidence",
    "command-reconciliation",
}


def _frontmatter(title: str, description: str, source_fingerprint: str) -> str:
    return (
        "---\n"
        f"title: {json.dumps(title)}\n"
        f"description: {json.dumps(description)}\n"
        "audience: production\n"
        "status: verified\n"
        "generated: true\n"
        "generated_at: uncommitted\n"
        f"generator: {GENERATOR}\n"
        f"source_fingerprint: {source_fingerprint}\n"
        "source_commit: uncommitted\n"
        "schema_revision: 1\n"
        "validation_status: generated\n"
        "---\n\n"
        '<div class="pl-page-meta"><span class="pl-status pl-status--verified">Source verified</span>'
        '<span class="pl-status pl-status--patch-provided">Generated from one canonical model</span></div>\n\n'
    )


def _diagram(
    name: str,
    alt: str,
    *,
    component: bool = False,
    nested_page: bool = False,
) -> str:
    if component:
        root = COMPONENT_DIAGRAM_ROOT
    elif nested_page:
        root = VIEW_DIAGRAM_ROOT
    else:
        root = INDEX_DIAGRAM_ROOT
    folder = "components" if component else "views"
    kind = "component" if component else "system"
    width_class = " pl-architecture-diagram--wide" if name in WIDE_DIAGRAMS else ""
    poster_class = " pl-architecture-diagram--poster" if name == "complete-system" else ""
    loading = "eager" if name == "complete-system" else "lazy"
    light = f"{root}/{folder}/{name}.light.svg"
    dark = f"{root}/{folder}/{name}.dark.svg"
    safe_alt = html.escape(alt, quote=True)
    return (
        f'<figure class="pl-architecture-diagram pl-architecture-diagram--{kind}{width_class}{poster_class}">\n'
        '  <div class="pl-architecture-diagram__viewport">\n'
        f'    <a class="pl-architecture-diagram__link" href="{light}" '
        f'aria-label="Open full-size {safe_alt}">\n'
        f'      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--light" src="{light}" '
        f'alt="{safe_alt}" loading="{loading}" decoding="async" />\n'
        f'      <img class="pl-architecture-diagram__image pl-architecture-diagram__image--dark" src="{dark}" '
        f'alt="{safe_alt}" loading="{loading}" decoding="async" />\n'
        '    </a>\n'
        '  </div>\n'
        f'  <figcaption>{safe_alt}. '
        f'<a href="{light}">View full-size diagram</a></figcaption>\n'
        '</figure>\n'
    )


def _icon_img(icon: IconRecord, root: str, *, size: str = "small") -> str:
    label = html.escape(icon.display_name, quote=True)
    return (
        f'<span class="pl-architecture-icon pl-architecture-icon--{size} '
        f'pl-architecture-icon--{icon.icon_class}">'
        f'<img src="{root}/{icon.path.name}" alt="" loading="lazy" decoding="async" />'
        f'<span>{label}</span></span>'
    )


def _poster_banner(poster: dict[str, Any], icons: dict[str, IconRecord], icon_root: str) -> str:
    cards = []
    for card in poster["summary_cards"]:
        icon = icons[card["icon"]]
        cards.append(
            '<article class="pl-architecture-summary-card">'
            f'{_icon_img(icon, icon_root, size="summary")}'
            f'<h3>{html.escape(card["title"])}</h3>'
            f'<p>{html.escape(card["value"])}</p>'
            '</article>'
        )
    return '<div class="pl-architecture-summary-grid">' + "".join(cards) + '</div>'


def _poster_zone_cards(poster: dict[str, Any], model: dict[str, Any]) -> str:
    cards = []
    for zone in poster["zones"]:
        names = ", ".join(model["components"][item]["name"] for item in zone["components"])
        cards.append(
            '<article class="pl-architecture-zone-card">'
            f'<h3>{html.escape(zone["label"])}</h3>'
            f'<p>{html.escape(zone["summary"])}</p>'
            f'<p class="pl-architecture-zone-card__members"><strong>Includes:</strong> {html.escape(names)}</p>'
            '</article>'
        )
    return '<div class="pl-architecture-zone-grid">' + "".join(cards) + '</div>'


def _poster_legend(poster: dict[str, Any]) -> str:
    rows = []
    for item in poster["legend"]:
        rows.append(
            f'<li><span class="pl-architecture-legend__mark pl-architecture-legend__mark--{html.escape(item["key"], quote=True)}" '
            'aria-hidden="true"></span>'
            f'<span>{html.escape(item["label"])}</span></li>'
        )
    return '<ul class="pl-architecture-legend">' + "".join(rows) + '</ul>'


def _poster_flows(poster: dict[str, Any], model: dict[str, Any]) -> str:
    by_id = {item["id"]: item for item in model["connections"]}
    rows = []
    for flow in poster["primary_flows"]:
        relationships = [by_id[item]["label"] for item in flow["connections"]]
        rows.append(
            f'| {html.escape(flow["label"])} | {" → ".join(html.escape(item) for item in relationships)} |'
        )
    return "| Primary flow | Canonical relationships |\n| --- | --- |\n" + "\n".join(rows)


def _poster_callouts(poster: dict[str, Any]) -> str:
    cards = []
    for callout in poster["callouts"]:
        items = "".join(f'<li>{html.escape(item)}</li>' for item in callout["items"])
        cards.append(
            '<article class="pl-architecture-callout">'
            f'<h3>{html.escape(callout["title"])}</h3><ul>{items}</ul>'
            '</article>'
        )
    return '<div class="pl-architecture-callout-grid">' + "".join(cards) + '</div>'


def _poster_sections(
    model: dict[str, Any], poster: dict[str, Any], icons: dict[str, IconRecord], icon_root: str
) -> str:
    boundaries = "\n".join(
        f'- **{model["boundaries"][item]["name"]}** — {model["boundaries"][item]["description"]}'
        for item in poster["trust_boundary_bands"]
    )
    technology_ids: list[str] = []
    for component_id in model["views"]["complete-system"]["components"]:
        component = model["components"][component_id]
        technology_ids.extend([component["icon"], *component.get("technology_icons", [])])
    technology = "".join(
        _icon_img(icons[icon_id], icon_root)
        for icon_id in dict.fromkeys(technology_ids)
        if icon_id in icons and icons[icon_id].icon_class == "brand"
    )
    return f"""## Executive summary

{_poster_banner(poster, icons, icon_root)}

## Six architecture zones

{_poster_zone_cards(poster, model)}

## Legend and icon key

{_poster_legend(poster)}

The SVG also includes a generated legend. Brand icons identify verified external products; semantic icons identify Pocket Lab Lite roles, state, guards, evidence, recovery, and workflows. Text labels remain authoritative when an icon is unfamiliar or unavailable.

## Primary flows

{_poster_flows(poster, model)}

## Trust boundaries

{boundaries}

## Runtime technology stack

<div class="pl-architecture-icon-key">{technology}</div>

## Architecture callouts

{_poster_callouts(poster)}
"""


def _list(values: list[str], empty: str = "None declared") -> str:
    return "\n".join(f"- {value}" for value in values) if values else f"- {empty}"


def _documentation_link(source_page: Path, repository_path: str) -> str:
    """Return a MkDocs-relative link for a repository documentation path."""
    target = repository_path.removeprefix("docs/")
    source_parent = source_page.parent.relative_to(Path("docs")).as_posix()
    return posixpath.relpath(target, start=source_parent)


def _related_views(model: dict[str, Any], component_id: str) -> list[dict[str, str]]:
    result = []
    for view in model["views"].values():
        if component_id in view["components"]:
            result.append({"title": view["title"], "page": view["page"]})
    return sorted(result, key=lambda item: item["title"])


def architecture_index_page(
    model: dict[str, Any], source_report: dict[str, Any], source_fingerprint: str,
    icons: dict[str, IconRecord],
) -> str:
    views = sorted(model["views"].values(), key=lambda item: (item["level"], item["title"]))
    links = "\n".join(f"- [{view['title']}]({view['page']})" for view in views)
    guarantees = _list(model["operational_guarantees"])
    infrastructure_summary = "\n".join(
        f"- **{name}** — {description}" for name, description in INFRASTRUCTURE_SUMMARY
    )
    boundary_summary = "\n".join(
        f"- **{boundary['name']}** — {boundary['description']}"
        for _, boundary in sorted(model["boundaries"].items())
    )
    poster = model["views"]["complete-system"].get("poster")
    return _frontmatter(
        "Pocket Lab Lite Architecture",
        "Generated Production architecture from one canonical, source-verified model.",
        source_fingerprint,
    ) + f"""# Pocket Lab Lite Architecture

{_poster_banner(poster, icons, INDEX_ICON_ROOT) if poster else ''}

## Pocket Lab Lite in one view

{_diagram('complete-system', 'Complete Pocket Lab Lite executive architecture poster')}

```text
React/Vite PWA
→ Caddy
→ FastAPI /api/lite/*
→ NATS/JetStream
→ worker / agent / supervisor
→ lifecycle events / evidence / heartbeats
→ FastAPI prepared projections
→ PWA
```

## How to read the infrastructure map

{infrastructure_summary}

## Generated architecture facts

| Measure | Count |
| --- | ---: |
| Components | {len(model['components'])} |
| Connections | {len(model['connections'])} |
| Trust boundaries | {len(model['boundaries'])} |
| Domain views | {len(model['views'])} |
| Component mini diagrams | {sum(1 for item in model['components'].values() if item['mini_diagram'])} |
| Verified source references | {source_report['verified_reference_count']} |

**Architecture source fingerprint:** `{source_fingerprint}`

**Repository source inventory fingerprint:** `{source_report['inventory_fingerprint']}`

## Operational guarantees

{guarantees}

## Trust-boundary summary

{boundary_summary}

## Architecture views

{links}

## Component catalog

Open the [generated component catalog](component-catalog.md) for component function, protocols, ownership, runtime placement, health signals, evidence, source verification, and per-component mini diagrams.
"""


def view_page(
    model: dict[str, Any], index: ArchitectureIndex, view_id: str, source_fingerprint: str,
    icons: dict[str, IconRecord],
) -> str:
    view = model["views"][view_id]
    members = [model["components"][component_id] for component_id in view["components"]]
    rows = []
    for component in members:
        rows.append(
            "| [{name}](components/{id}.md) | {category} | {runtime} | {owner} | {boundary} |".format(
                name=component["name"], id=component["id"], category=component["category"],
                runtime=component["runtime_location"], owner=component["runtime_owner"],
                boundary=model["boundaries"][component["security_boundary"]]["name"],
            )
        )
    connection_rows = []
    for connection in index.view_connections[view_id]:
        source = model["components"][connection["source"]]["name"]
        target = model["components"][connection["target"]]["name"]
        connection_rows.append(
            f"| {source} | {connection['label']} | {target} | {connection['kind']} | {connection['protocol'] or 'Repository-defined'} |"
        )
    poster_sections = (
        _poster_sections(model, view["poster"], icons, VIEW_ICON_ROOT)
        if view.get("poster") else ""
    )
    diagram_heading = "Complete-system hero poster" if view.get("poster") else "Architecture diagram"
    return _frontmatter(view["title"], view["description"], source_fingerprint) + f"""# {view['title']}

{view['description']}

{poster_sections}

## {diagram_heading}

{_diagram(view_id, view['title'], nested_page=True)}

## Components

| Component | Category | Runs on | Runtime owner | Security boundary |
| --- | --- | --- | --- | --- |
{chr(10).join(rows)}

## Connections

| Source | Relationship | Target | Flow | Protocol |
| --- | --- | --- | --- | --- |
{chr(10).join(connection_rows) if connection_rows else '| None | No direct connection in this view | None | None | None |'}

## Source-derived status

All components and connections on this page are generated from `architecture/metadata/pocket-lab-architecture.json`. Source references are checked against prepared OpenAPI, AsyncAPI, PM2 service, SQLite, bootstrap, projection, and repository path inventories before generation.

[Back to Architecture overview](index.md) · [Component catalog](component-catalog.md)
"""


def component_page(
    model: dict[str, Any], index: ArchitectureIndex, component_id: str,
    mini: dict[str, Any], source_fingerprint: str, icons: dict[str, IconRecord],
) -> str:
    component = model["components"][component_id]
    primary_icon = icons[component["icon"]]
    technology_icons = [icons[item] for item in component.get("technology_icons", []) if item in icons]
    icon_key = _icon_img(primary_icon, COMPONENT_ICON_ROOT, size="component")
    if technology_icons:
        icon_key += "".join(_icon_img(item, COMPONENT_ICON_ROOT) for item in technology_icons)
    incoming = [
        f"{model['components'][item['source']]['name']} — {item['label']}"
        for item in index.incoming[component_id]
    ]
    outgoing = [
        f"{item['label']} — {model['components'][item['target']]['name']}"
        for item in index.outgoing[component_id]
    ]
    related = _related_views(model, component_id)
    related_links = "\n".join(f"- [{item['title']}](../{item['page']})" for item in related)
    source_refs = "\n".join(
        f"- `{item['kind']}` — `{item.get('path', item['value'])}`"
        + (f" contains `{item['value']}`" if item["kind"] == "literal" else "")
        for item in component["source_verification"]
    )
    diagram = (
        _diagram(component_id, f"{component['name']} mini architecture", component=True)
        if component["mini_diagram"] else
        "> This component is represented in domain diagrams; a dedicated mini diagram is intentionally omitted.\n"
    )
    omitted = (
        f"\nThe mini diagram deterministically collapses **{mini['omitted_connection_count']}** additional connections.\n"
        if mini.get("omitted_connection_count") else ""
    )
    return _frontmatter(
        component["name"], component["responsibility"], source_fingerprint
    ) + f"""# {component['name']}

{component['responsibility']}

<div class="pl-architecture-component-icons">{icon_key}</div>

{diagram}{omitted}

## Function and use

| Field | Value |
| --- | --- |
| Function | {component['responsibility']} |
| Primary inputs | {', '.join(component['inputs'][:3]) or 'None'} |
| Primary outputs | {', '.join(component['outputs'][:3]) or 'None'} |
| Protocols / uses | {', '.join(component['protocols'][:3]) or 'None'} |
| Evidence | {', '.join(component['evidence_produced'][:3]) or 'None'} |

## Ownership and placement

| Field | Value |
| --- | --- |
| Category | {component['category']} |
| Runs on | {component['runtime_location']} |
| Started / runtime owner | {component['runtime_owner']} |
| Process owner | {component['process_owner']} |
| Execution owner | {component['owner']} |
| Data owner | {component['data_owner']} |
| Recovery owner | {component['recovery_owner']} |
| Security boundary | {model['boundaries'][component['security_boundary']]['name']} |
| Supported platforms | {', '.join(component['supported_platforms'])} |
| Verification | {component['verification_status']} |
| Architecture icon | {component['icon']} |
| Icon class | {primary_icon.icon_class} |
| Icon upstream | {primary_icon.upstream_project} |
| Icon source revision | {primary_icon.source_revision} |
| Icon license | {primary_icon.license} |
| Icon trademark note | {primary_icon.trademark_note} |
| Technology markers | {', '.join(item.id for item in technology_icons) or 'None'} |

## Inputs

{_list(component['inputs'])}

## Outputs

{_list(component['outputs'])}

## Protocols

{_list(component['protocols'])}

## Durable state

{_list(component['durable_state_dependencies'])}

## Health and readiness

{_list(component['health_signals'])}

## Evidence

{_list(component['evidence_produced'])}

## Failure behavior

{_list(component['failure_paths'])}

## Recovery behavior

{_list(component['recovery_paths'])}

## Connections

### Incoming

{_list(incoming)}

### Outgoing

{_list(outgoing)}

## Source verification

{source_refs}

## Existing documentation

{_list([f'[{Path(path).name}]({_documentation_link(DOC_ROOT / "components" / f"{component_id}.md", path)})' for path in component['documentation_links']])}

## Related architecture views

{related_links or '- None'}

[Back to component catalog](../component-catalog.md) · [Architecture overview](../index.md)
"""


def component_catalog_page(
    model: dict[str, Any], source_fingerprint: str, icons: dict[str, IconRecord]
) -> str:
    rows = []
    for component_id, component in sorted(model["components"].items(), key=lambda item: item[1]["name"]):
        outgoing = sorted({
            model["components"][connection["target"]]["name"]
            for connection in model["connections"] if connection["source"] == component_id
        })
        rows.append(
            "| [{name}](components/{id}.md) | {icon_class} | {category} | {runtime} | {runtime_owner} | "
            "{owner} | {data_owner} | {recovery_owner} | {communicates} | {stores} | "
            "{evidence} | {health} | {platforms} |".format(
                name=component["name"], id=component_id,
                icon_class=icons[component["icon"]].icon_class, category=component["category"],
                runtime=component["runtime_location"], runtime_owner=component["runtime_owner"],
                owner=component["owner"], data_owner=component["data_owner"],
                recovery_owner=component["recovery_owner"],
                communicates=", ".join(outgoing[:4]) or "None",
                stores=", ".join(component["durable_state_dependencies"][:3]) or "None",
                evidence=", ".join(component["evidence_produced"][:2]) or "None",
                health=", ".join(component["health_signals"][:2]) or "None",
                platforms=", ".join(component["supported_platforms"]),
            )
        )
    return _frontmatter(
        "Pocket Lab Lite Component Catalog",
        "Searchable ownership, runtime, state, evidence, health, and platform inventory.",
        source_fingerprint,
    ) + f"""# Component catalog

This catalog is generated from the canonical architecture model. Component names remain authoritative; icons are supplementary and locally owned.

<div class="pl-architecture-table" markdown>

| Component | Icon class | Category | Runs on | Started by / runtime owner | Execution owner | Data owner | Recovery owner | Communicates with | Stores data | Produces evidence | Health signal | Supported platforms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
{chr(10).join(rows)}

</div>

[Back to Architecture overview](index.md)
"""


def build_pages(
    model: dict[str, Any], index: ArchitectureIndex, mini_graphs: dict[str, dict[str, Any]],
    source_report: dict[str, Any], source_fingerprint: str, icons: dict[str, IconRecord],
) -> dict[Path, str]:
    outputs: dict[Path, str] = {}
    outputs[DOC_ROOT / "index.md"] = architecture_index_page(
        model, source_report, source_fingerprint, icons
    )
    for view_id, view in sorted(model["views"].items()):
        outputs[DOC_ROOT / view["page"]] = view_page(
            model, index, view_id, source_fingerprint, icons
        )
    outputs[DOC_ROOT / "component-catalog.md"] = component_catalog_page(
        model, source_fingerprint, icons
    )
    for component_id in sorted(model["components"]):
        outputs[DOC_ROOT / "components" / f"{component_id}.md"] = component_page(
            model, index, component_id, mini_graphs.get(component_id, {}), source_fingerprint, icons
        )
    return outputs
