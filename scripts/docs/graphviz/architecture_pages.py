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

GENERATOR = "scripts/docs/graphviz/generate_lite_architecture.py"
DOC_ROOT = Path("docs/generated/production/architecture")
DIAGRAM_ROOT = "../../../assets/diagrams/production"
COMPONENT_DIAGRAM_ROOT = "../../../../assets/diagrams/production"


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


def _diagram(name: str, alt: str, *, component: bool = False) -> str:
    root = COMPONENT_DIAGRAM_ROOT if component else DIAGRAM_ROOT
    folder = "components" if component else "views"
    return (
        f"![{alt}]({root}/{folder}/{name}.light.svg#only-light)\n"
        f"![{alt}]({root}/{folder}/{name}.dark.svg#only-dark)\n"
    )


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
    model: dict[str, Any], source_report: dict[str, Any], source_fingerprint: str
) -> str:
    views = sorted(model["views"].values(), key=lambda item: (item["level"], item["title"]))
    links = "\n".join(f"- [{view['title']}]({view['page']})" for view in views)
    guarantees = _list(model["operational_guarantees"])
    boundary_summary = "\n".join(
        f"- **{boundary['name']}** — {boundary['description']}"
        for _, boundary in sorted(model["boundaries"].items())
    )
    return _frontmatter(
        "Pocket Lab Lite Architecture",
        "Generated Production architecture from one canonical, source-verified model.",
        source_fingerprint,
    ) + f"""# Pocket Lab Lite Architecture

## Pocket Lab Lite in one view

{_diagram('complete-system', 'Complete Pocket Lab Lite system map')}

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

Open the [generated component catalog](component-catalog.md) for ownership, runtime placement, health signals, evidence, source verification, and per-component mini diagrams.
"""


def view_page(
    model: dict[str, Any], index: ArchitectureIndex, view_id: str, source_fingerprint: str
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
    return _frontmatter(view["title"], view["description"], source_fingerprint) + f"""# {view['title']}

{view['description']}

{_diagram(view_id, view['title'])}

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
    mini: dict[str, Any], source_fingerprint: str,
) -> str:
    component = model["components"][component_id]
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

{diagram}{omitted}

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


def component_catalog_page(model: dict[str, Any], source_fingerprint: str) -> str:
    rows = []
    for component_id, component in sorted(model["components"].items(), key=lambda item: item[1]["name"]):
        outgoing = sorted({
            model["components"][connection["target"]]["name"]
            for connection in model["connections"] if connection["source"] == component_id
        })
        rows.append(
            "| [{name}](components/{id}.md) | {category} | {runtime} | {runtime_owner} | "
            "{owner} | {data_owner} | {recovery_owner} | {communicates} | {stores} | "
            "{evidence} | {health} | {platforms} |".format(
                name=component["name"], id=component_id, category=component["category"],
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

| Component | Category | Runs on | Started by / runtime owner | Execution owner | Data owner | Recovery owner | Communicates with | Stores data | Produces evidence | Health signal | Supported platforms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
{chr(10).join(rows)}

</div>

[Back to Architecture overview](index.md)
"""


def build_pages(
    model: dict[str, Any], index: ArchitectureIndex, mini_graphs: dict[str, dict[str, Any]],
    source_report: dict[str, Any], source_fingerprint: str,
) -> dict[Path, str]:
    outputs: dict[Path, str] = {}
    outputs[DOC_ROOT / "index.md"] = architecture_index_page(
        model, source_report, source_fingerprint
    )
    for view_id, view in sorted(model["views"].items()):
        outputs[DOC_ROOT / view["page"]] = view_page(
            model, index, view_id, source_fingerprint
        )
    outputs[DOC_ROOT / "component-catalog.md"] = component_catalog_page(
        model, source_fingerprint
    )
    for component_id in sorted(model["components"]):
        outputs[DOC_ROOT / "components" / f"{component_id}.md"] = component_page(
            model, index, component_id, mini_graphs.get(component_id, {}), source_fingerprint
        )
    return outputs
