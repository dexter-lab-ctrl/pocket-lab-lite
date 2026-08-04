#!/usr/bin/env python3
"""Load, validate, normalize, and index the canonical Pocket Lab Lite architecture model."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[3]
MODEL_PATH = ROOT / "architecture" / "metadata" / "pocket-lab-architecture.json"
SUPPORTED_SCHEMA_REVISIONS = {1}
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{1,79}$")
REQUIRED_COMPONENT_FIELDS = {
    "id", "name", "category", "responsibility", "runtime_location", "owner",
    "runtime_owner", "process_owner", "data_owner", "recovery_owner",
    "security_boundary", "supported_platforms", "documentation_links", "inputs",
    "outputs", "protocols", "durable_state_dependencies", "evidence_produced",
    "health_signals", "failure_paths", "recovery_paths", "icon",
    "source_verification", "verification_status", "mini_diagram", "orphan_exempt",
}
REQUIRED_CONNECTION_FIELDS = {
    "id", "source", "target", "label", "kind", "protocol", "evidence", "recovery"
}
REQUIRED_VIEW_FIELDS = {"id", "title", "description", "components", "page", "level", "max_nodes"}
ALLOWED_CONNECTION_KINDS = {"control", "data", "evidence", "health", "recovery"}
ALLOWED_VERIFICATION_STATES = {
    "verified", "inferred", "patch-provided", "missing", "planned", "unvalidated"
}


class ArchitectureModelError(ValueError):
    """Raised when the canonical architecture model violates its contract."""


@dataclass(frozen=True)
class ArchitectureIndex:
    incoming: dict[str, tuple[dict[str, Any], ...]]
    outgoing: dict[str, tuple[dict[str, Any], ...]]
    by_boundary: dict[str, tuple[str, ...]]
    view_connections: dict[str, tuple[dict[str, Any], ...]]


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def fingerprint(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ArchitectureModelError(f"Missing architecture model: {path.relative_to(ROOT)}") from exc
    except json.JSONDecodeError as exc:
        raise ArchitectureModelError(f"Invalid architecture JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ArchitectureModelError("Architecture model root must be an object")
    return data


def _validate_id(value: Any, kind: str) -> str:
    text = str(value)
    if not ID_PATTERN.fullmatch(text):
        raise ArchitectureModelError(f"Invalid {kind} id: {text!r}")
    return text


def _require_string_list(value: Any, context: str, *, allow_empty: bool = True) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ArchitectureModelError(f"{context} must be a list of strings")
    if not allow_empty and not value:
        raise ArchitectureModelError(f"{context} must not be empty")
    return value


def _validate_source_refs(component_id: str, value: Any) -> None:
    if not isinstance(value, list) or not value:
        raise ArchitectureModelError(f"Component {component_id} needs source_verification references")
    for index, reference in enumerate(value):
        if not isinstance(reference, dict):
            raise ArchitectureModelError(
                f"Component {component_id} source_verification[{index}] must be an object"
            )
        if reference.get("kind") not in {
            "path", "doc", "contract", "route", "nats_subject", "pm2_process",
            "sqlite_table", "bootstrap_stage", "literal"
        }:
            raise ArchitectureModelError(
                f"Component {component_id} has unsupported source reference kind "
                f"{reference.get('kind')!r}"
            )
        if not isinstance(reference.get("value"), str) or not reference["value"].strip():
            raise ArchitectureModelError(
                f"Component {component_id} source reference {index} has no value"
            )
        if reference.get("kind") == "literal" and not isinstance(reference.get("path"), str):
            raise ArchitectureModelError(
                f"Component {component_id} literal reference {index} requires path"
            )


def _validate_poster_metadata(
    *, view_id: str, view: dict[str, Any], poster: Any, component_ids: set[str],
    connection_ids: set[str], boundary_ids: set[str], icon_set: set[str],
) -> None:
    if view_id != "complete-system":
        raise ArchitectureModelError("Poster metadata is only supported on complete-system")
    if not isinstance(poster, dict) or poster.get("layout_mode") != "executive-poster":
        raise ArchitectureModelError("Complete-system poster needs layout_mode=executive-poster")
    for flag in (
        "show_summary_cards", "show_legend", "show_callouts",
        "show_trust_boundary_bands", "emphasize_primary_flows",
    ):
        if not isinstance(poster.get(flag), bool):
            raise ArchitectureModelError(f"Complete-system poster {flag} must be boolean")
    zones = poster.get("zones")
    if not isinstance(zones, list) or len(zones) != 6:
        raise ArchitectureModelError("Complete-system poster must define exactly six zones")
    zone_ids: set[str] = set()
    assigned: list[str] = []
    for zone in zones:
        if not isinstance(zone, dict):
            raise ArchitectureModelError("Poster zone must be an object")
        zone_id = _validate_id(zone.get("id"), "poster zone")
        if zone_id in zone_ids:
            raise ArchitectureModelError(f"Duplicate poster zone id: {zone_id}")
        zone_ids.add(zone_id)
        if not isinstance(zone.get("label"), str) or not zone["label"].strip():
            raise ArchitectureModelError(f"Poster zone {zone_id} needs a label")
        if not isinstance(zone.get("summary"), str) or not zone["summary"].strip():
            raise ArchitectureModelError(f"Poster zone {zone_id} needs a summary")
        members = _require_string_list(
            zone.get("components"), f"Poster zone {zone_id} components", allow_empty=False
        )
        unknown = sorted(set(members) - component_ids)
        if unknown:
            raise ArchitectureModelError(
                f"Poster zone {zone_id} references unknown components: {', '.join(unknown)}"
            )
        assigned.extend(members)
    view_members = list(view["components"])
    if len(assigned) != len(set(assigned)):
        raise ArchitectureModelError("Complete-system poster assigns a component more than once")
    if set(assigned) != set(view_members):
        missing = sorted(set(view_members) - set(assigned))
        extra = sorted(set(assigned) - set(view_members))
        raise ArchitectureModelError(
            "Complete-system poster zones must exactly cover the view; "
            f"missing={missing}, extra={extra}"
        )
    cards = poster.get("summary_cards")
    if not isinstance(cards, list) or not cards:
        raise ArchitectureModelError("Complete-system poster needs summary_cards")
    for card in cards:
        if not isinstance(card, dict) or not all(
            isinstance(card.get(field), str) and card[field].strip()
            for field in ("title", "value", "icon")
        ):
            raise ArchitectureModelError("Poster summary card needs title, value, and icon")
        if icon_set and card["icon"] not in icon_set:
            raise ArchitectureModelError(
                f"Poster summary card references unknown icon {card['icon']!r}"
            )
    flows = poster.get("primary_flows")
    if not isinstance(flows, list) or not flows:
        raise ArchitectureModelError("Complete-system poster needs primary_flows")
    flow_ids: set[str] = set()
    for flow in flows:
        if not isinstance(flow, dict):
            raise ArchitectureModelError("Poster primary flow must be an object")
        flow_id = _validate_id(flow.get("id"), "poster flow")
        if flow_id in flow_ids:
            raise ArchitectureModelError(f"Duplicate poster flow id: {flow_id}")
        flow_ids.add(flow_id)
        if not isinstance(flow.get("label"), str) or not flow["label"].strip():
            raise ArchitectureModelError(f"Poster flow {flow_id} needs a label")
        refs = _require_string_list(
            flow.get("connections"), f"Poster flow {flow_id} connections", allow_empty=False
        )
        unknown = sorted(set(refs) - connection_ids)
        if unknown:
            raise ArchitectureModelError(
                f"Poster flow {flow_id} references unknown connections: {', '.join(unknown)}"
            )
    bands = _require_string_list(
        poster.get("trust_boundary_bands"), "Poster trust_boundary_bands", allow_empty=False
    )
    unknown_bands = sorted(set(bands) - boundary_ids)
    if unknown_bands:
        raise ArchitectureModelError(
            "Poster trust boundary bands reference unknown boundaries: "
            + ", ".join(unknown_bands)
        )
    if len(bands) != len(set(bands)):
        raise ArchitectureModelError("Poster trust_boundary_bands contains duplicates")
    for collection_name in ("callouts", "legend"):
        collection = poster.get(collection_name)
        if not isinstance(collection, list) or not collection:
            raise ArchitectureModelError(f"Complete-system poster needs {collection_name}")


def validate_model(data: dict[str, Any], *, known_icons: Iterable[str] | None = None) -> None:
    revision = data.get("schema_revision")
    if revision not in SUPPORTED_SCHEMA_REVISIONS:
        raise ArchitectureModelError(f"Unsupported architecture schema revision: {revision!r}")
    categories = data.get("categories")
    if not isinstance(categories, list) or not categories or len(categories) != len(set(categories)):
        raise ArchitectureModelError("categories must be a non-empty unique list")
    boundaries = data.get("boundaries")
    components = data.get("components")
    connections = data.get("connections")
    views = data.get("views")
    if not isinstance(boundaries, dict) or not boundaries:
        raise ArchitectureModelError("boundaries must be a non-empty object")
    if not isinstance(components, dict) or not components:
        raise ArchitectureModelError("components must be a non-empty object")
    if not isinstance(connections, list) or not connections:
        raise ArchitectureModelError("connections must be a non-empty list")
    if not isinstance(views, dict) or not views:
        raise ArchitectureModelError("views must be a non-empty object")
    boundary_ids: set[str] = set()
    for key, boundary in boundaries.items():
        boundary_id = _validate_id(key, "boundary")
        if boundary_id in boundary_ids:
            raise ArchitectureModelError(f"Duplicate boundary id: {boundary_id}")
        boundary_ids.add(boundary_id)
        if not isinstance(boundary, dict) or not boundary.get("name") or not boundary.get("description"):
            raise ArchitectureModelError(f"Boundary {boundary_id} needs name and description")
    icon_set = set(known_icons or [])
    component_ids: set[str] = set()
    for key, component in components.items():
        component_id = _validate_id(key, "component")
        if component_id in component_ids:
            raise ArchitectureModelError(f"Duplicate component id: {component_id}")
        component_ids.add(component_id)
        if not isinstance(component, dict):
            raise ArchitectureModelError(f"Component {component_id} must be an object")
        missing = sorted(REQUIRED_COMPONENT_FIELDS - component.keys())
        if missing:
            raise ArchitectureModelError(
                f"Component {component_id} is missing: {', '.join(missing)}"
            )
        if component.get("id") != component_id:
            raise ArchitectureModelError(f"Component key/id mismatch for {component_id}")
        if component.get("category") not in categories:
            raise ArchitectureModelError(
                f"Component {component_id} uses unknown category {component.get('category')!r}"
            )
        boundary = component.get("security_boundary")
        if boundary not in boundary_ids:
            raise ArchitectureModelError(
                f"Component {component_id} uses unknown boundary {boundary!r}"
            )
        for field in (
            "name", "responsibility", "runtime_location", "owner", "runtime_owner",
            "process_owner", "data_owner", "recovery_owner", "icon", "verification_status"
        ):
            if not isinstance(component.get(field), str) or not component[field].strip():
                raise ArchitectureModelError(f"Component {component_id} field {field} is empty")
        if component["verification_status"] not in ALLOWED_VERIFICATION_STATES:
            raise ArchitectureModelError(
                f"Component {component_id} has invalid verification status"
            )
        for field in (
            "supported_platforms", "documentation_links", "inputs", "outputs", "protocols",
            "durable_state_dependencies", "evidence_produced", "health_signals",
            "failure_paths", "recovery_paths"
        ):
            _require_string_list(
                component.get(field), f"Component {component_id} {field}",
                allow_empty=field not in {"supported_platforms", "documentation_links"},
            )
        if not isinstance(component.get("mini_diagram"), bool) or not isinstance(
            component.get("orphan_exempt"), bool
        ):
            raise ArchitectureModelError(
                f"Component {component_id} mini_diagram/orphan_exempt must be boolean"
            )
        if icon_set and component["icon"] not in icon_set:
            raise ArchitectureModelError(
                f"Component {component_id} references unknown icon {component['icon']!r}"
            )
        technology_icons = _require_string_list(
            component.get("technology_icons", []),
            f"Component {component_id} technology_icons",
        )
        if len(technology_icons) != len(set(technology_icons)):
            raise ArchitectureModelError(
                f"Component {component_id} contains duplicate technology_icons"
            )
        if icon_set:
            unknown_icons = sorted(set(technology_icons) - icon_set)
            if unknown_icons:
                raise ArchitectureModelError(
                    f"Component {component_id} references unknown technology icons: "
                    + ", ".join(unknown_icons)
                )
        _validate_source_refs(component_id, component["source_verification"])
    connection_ids: set[str] = set()
    edge_pairs: set[tuple[str, str, str, str]] = set()
    degree = {component_id: 0 for component_id in component_ids}
    for index, connection in enumerate(connections):
        if not isinstance(connection, dict):
            raise ArchitectureModelError(f"Connection {index} must be an object")
        missing = sorted(REQUIRED_CONNECTION_FIELDS - connection.keys())
        if missing:
            raise ArchitectureModelError(
                f"Connection {index} is missing: {', '.join(missing)}"
            )
        connection_id = _validate_id(connection["id"], "connection")
        if connection_id in connection_ids:
            raise ArchitectureModelError(f"Duplicate connection id: {connection_id}")
        connection_ids.add(connection_id)
        source, target = connection["source"], connection["target"]
        if source not in component_ids or target not in component_ids:
            raise ArchitectureModelError(
                f"Connection {connection_id} references unknown component {source!r}->{target!r}"
            )
        if source == target:
            raise ArchitectureModelError(f"Connection {connection_id} cannot self-reference")
        kind = connection.get("kind")
        if kind not in ALLOWED_CONNECTION_KINDS:
            raise ArchitectureModelError(
                f"Connection {connection_id} has unsupported kind {kind!r}"
            )
        edge_key = (source, target, str(connection["label"]), str(kind))
        if edge_key in edge_pairs:
            raise ArchitectureModelError(
                f"Duplicate edge semantics for {source}->{target}: {connection['label']!r}"
            )
        edge_pairs.add(edge_key)
        degree[source] += 1
        degree[target] += 1
    for component_id, count in sorted(degree.items()):
        if count == 0 and not components[component_id]["orphan_exempt"]:
            raise ArchitectureModelError(
                f"Component {component_id} is orphaned without an explicit exemption"
            )
    view_ids: set[str] = set()
    pages: set[str] = set()
    for key, view in views.items():
        view_id = _validate_id(key, "view")
        if view_id in view_ids:
            raise ArchitectureModelError(f"Duplicate view id: {view_id}")
        view_ids.add(view_id)
        if not isinstance(view, dict):
            raise ArchitectureModelError(f"View {view_id} must be an object")
        missing = sorted(REQUIRED_VIEW_FIELDS - view.keys())
        if missing:
            raise ArchitectureModelError(f"View {view_id} is missing: {', '.join(missing)}")
        if view.get("id") != view_id:
            raise ArchitectureModelError(f"View key/id mismatch for {view_id}")
        members = _require_string_list(view.get("components"), f"View {view_id} components", allow_empty=False)
        unknown = sorted(set(members) - component_ids)
        if unknown:
            raise ArchitectureModelError(
                f"View {view_id} references unknown components: {', '.join(unknown)}"
            )
        if len(members) != len(set(members)):
            raise ArchitectureModelError(f"View {view_id} contains duplicate components")
        if int(view["max_nodes"]) < len(members):
            raise ArchitectureModelError(
                f"View {view_id} has {len(members)} components above max_nodes={view['max_nodes']}"
            )
        page = str(view["page"])
        if not page.endswith(".md") or "/" in page or page in pages:
            raise ArchitectureModelError(f"View {view_id} has invalid or duplicate page {page!r}")
        pages.add(page)
        poster = view.get("poster")
        if poster is not None:
            _validate_poster_metadata(
                view_id=view_id, view=view, poster=poster, component_ids=component_ids,
                connection_ids=connection_ids, boundary_ids=boundary_ids, icon_set=icon_set,
            )
    policy = data.get("mini_diagram_policy")
    if not isinstance(policy, dict):
        raise ArchitectureModelError("mini_diagram_policy must be an object")
    for field in ("max_incoming", "max_outgoing", "max_state_dependencies", "max_total_neighbors"):
        if not isinstance(policy.get(field), int) or policy[field] < 1:
            raise ArchitectureModelError(f"Invalid mini_diagram_policy {field}")


def normalize_model(data: dict[str, Any]) -> dict[str, Any]:
    """Return a deeply sorted copy used for deterministic rendering and hashing."""
    normalized = json.loads(canonical_json(data))
    normalized["components"] = {
        key: normalized["components"][key] for key in sorted(normalized["components"])
    }
    normalized["boundaries"] = {
        key: normalized["boundaries"][key] for key in sorted(normalized["boundaries"])
    }
    normalized["views"] = {key: normalized["views"][key] for key in sorted(normalized["views"])}
    normalized["connections"] = sorted(
        normalized["connections"], key=lambda item: item["id"]
    )
    return normalized


def load_model(path: Path = MODEL_PATH, *, known_icons: Iterable[str] | None = None) -> dict[str, Any]:
    data = _load_json(path)
    validate_model(data, known_icons=known_icons)
    return normalize_model(data)


def build_index(model: dict[str, Any]) -> ArchitectureIndex:
    incoming: dict[str, list[dict[str, Any]]] = {key: [] for key in model["components"]}
    outgoing: dict[str, list[dict[str, Any]]] = {key: [] for key in model["components"]}
    for connection in model["connections"]:
        outgoing[connection["source"]].append(connection)
        incoming[connection["target"]].append(connection)
    for values in incoming.values():
        values.sort(key=lambda item: (item["kind"], item["source"], item["id"]))
    for values in outgoing.values():
        values.sort(key=lambda item: (item["kind"], item["target"], item["id"]))
    by_boundary: dict[str, list[str]] = {key: [] for key in model["boundaries"]}
    for component_id, component in model["components"].items():
        by_boundary[component["security_boundary"]].append(component_id)
    for values in by_boundary.values():
        values.sort()
    view_connections: dict[str, list[dict[str, Any]]] = {}
    for view_id, view in model["views"].items():
        members = set(view["components"])
        view_connections[view_id] = [
            connection for connection in model["connections"]
            if connection["source"] in members and connection["target"] in members
        ]
    return ArchitectureIndex(
        incoming={key: tuple(value) for key, value in incoming.items()},
        outgoing={key: tuple(value) for key, value in outgoing.items()},
        by_boundary={key: tuple(value) for key, value in by_boundary.items()},
        view_connections={key: tuple(value) for key, value in view_connections.items()},
    )


def derive_mini_graph(
    model: dict[str, Any], index: ArchitectureIndex, component_id: str
) -> dict[str, Any]:
    if component_id not in model["components"]:
        raise ArchitectureModelError(f"Unknown component for mini diagram: {component_id}")
    policy = model["mini_diagram_policy"]
    incoming = list(index.incoming[component_id])[: policy["max_incoming"]]
    outgoing = list(index.outgoing[component_id])[: policy["max_outgoing"]]
    selected_ids = {component_id}
    selected_connections: list[dict[str, Any]] = []
    for connection in incoming + outgoing:
        selected_connections.append(connection)
        selected_ids.add(connection["source"])
        selected_ids.add(connection["target"])
    component = model["components"][component_id]
    dependencies = [
        item for item in component["durable_state_dependencies"]
        if item and len(selected_ids) < policy["max_total_neighbors"] + 1
    ][: policy["max_state_dependencies"]]
    omitted = max(0, len(index.incoming[component_id]) - len(incoming)) + max(
        0, len(index.outgoing[component_id]) - len(outgoing)
    )
    return {
        "component_id": component_id,
        "component_ids": sorted(selected_ids),
        "connections": sorted(selected_connections, key=lambda item: item["id"]),
        "state_dependencies": dependencies,
        "omitted_connection_count": omitted,
        "additional_dependencies_label": policy["collapse_label"] if omitted else "",
    }
