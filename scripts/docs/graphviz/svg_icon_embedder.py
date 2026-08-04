#!/usr/bin/env python3
"""Build deterministic, self-contained SVG symbols from validated architecture icons."""
from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from icon_registry import IconRecord, IconRegistryError, validate_icon

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
ET.register_namespace("", SVG_NS)
ET.register_namespace("xlink", XLINK_NS)

SAFE_ID = re.compile(r"[^a-zA-Z0-9_.-]+")
NUMERIC_VIEWBOX = re.compile(
    r"^\s*(-?(?:\d+(?:\.\d+)?|\.\d+))\s+"
    r"(-?(?:\d+(?:\.\d+)?|\.\d+))\s+"
    r"((?:\d+(?:\.\d+)?|\.\d+))\s+"
    r"((?:\d+(?:\.\d+)?|\.\d+))\s*$"
)
URL_REF = re.compile(r"url\(\s*#([^)\s]+)\s*\)")
CLASS_SELECTOR = re.compile(r"\.([A-Za-z_][A-Za-z0-9_-]*)")


class SvgIconEmbedError(ValueError):
    """Raised when a validated local icon cannot be embedded safely."""


@dataclass(frozen=True)
class EmbeddedIcon:
    icon_id: str
    symbol_id: str
    view_box: str
    body: str


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _safe_token(value: str) -> str:
    token = SAFE_ID.sub("-", value).strip("-")
    if not token:
        raise SvgIconEmbedError(f"Unsafe empty SVG token derived from {value!r}")
    return token


def _rewrite_reference(value: str, id_map: dict[str, str]) -> str:
    if value.startswith("#"):
        target = value[1:]
        if target in id_map:
            return f"#{id_map[target]}"
    return URL_REF.sub(lambda match: f"url(#{id_map.get(match.group(1), match.group(1))})", value)


def _rewrite_style(value: str, id_map: dict[str, str], class_map: dict[str, str]) -> str:
    value = _rewrite_reference(value, id_map)
    return CLASS_SELECTOR.sub(
        lambda match: f".{class_map.get(match.group(1), match.group(1))}", value
    )


def _serialize_children(root: ET.Element) -> str:
    parts: list[str] = []
    for child in list(root):
        if _local_name(child.tag) in {"title", "desc", "metadata"}:
            continue
        payload = ET.tostring(child, encoding="unicode", short_empty_elements=True)
        payload = payload.replace(f' xmlns="{SVG_NS}"', "")
        parts.append(payload)
    return "".join(parts)


def load_embedded_icon(record: IconRecord) -> EmbeddedIcon:
    """Load one already-validated local SVG as a namespaced symbol payload."""
    try:
        validate_icon(record)
    except IconRegistryError as exc:
        raise SvgIconEmbedError(f"Icon {record.id} failed registry validation: {exc}") from exc
    try:
        root = ET.fromstring(record.path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ET.ParseError) as exc:
        raise SvgIconEmbedError(f"Icon {record.id} could not be parsed as SVG") from exc
    if _local_name(root.tag) != "svg":
        raise SvgIconEmbedError(f"Icon {record.id} root is not svg")
    raw_view_box = root.attrib.get("viewBox", "")
    match = NUMERIC_VIEWBOX.fullmatch(raw_view_box)
    if not match or float(match.group(3)) <= 0 or float(match.group(4)) <= 0:
        raise SvgIconEmbedError(f"Icon {record.id} lacks a positive numeric viewBox")

    prefix = f"pl-{_safe_token(record.id)}"
    id_map: dict[str, str] = {}
    class_map: dict[str, str] = {}
    for element in root.iter():
        old_id = element.attrib.get("id")
        if old_id:
            id_map[old_id] = f"{prefix}-{_safe_token(old_id)}"
        for class_name in element.attrib.get("class", "").split():
            class_map[class_name] = f"{prefix}-{_safe_token(class_name)}"

    for element in root.iter():
        if "id" in element.attrib:
            element.attrib["id"] = id_map[element.attrib["id"]]
        if "class" in element.attrib:
            element.attrib["class"] = " ".join(
                class_map.get(item, item) for item in element.attrib["class"].split()
            )
        for attribute, value in list(element.attrib.items()):
            if attribute in {"id", "class"}:
                continue
            element.attrib[attribute] = _rewrite_reference(value, id_map)
        if _local_name(element.tag) == "style" and element.text:
            element.text = _rewrite_style(element.text, id_map, class_map)

    body = _serialize_children(root)
    if not body.strip():
        raise SvgIconEmbedError(f"Icon {record.id} contains no embeddable graphics")
    if re.search(r'(?:href|xlink:href)=["\'](?:https?:|//|data:|javascript:)', body, re.I):
        raise SvgIconEmbedError(f"Icon {record.id} retained an external reference")
    return EmbeddedIcon(
        icon_id=record.id,
        symbol_id=f"pl-icon-{_safe_token(record.id)}",
        view_box=" ".join(match.groups()),
        body=body,
    )


def build_symbol_defs(records: Iterable[IconRecord]) -> tuple[str, dict[str, EmbeddedIcon]]:
    """Return one deterministic defs block and the embedded icons keyed by registry ID."""
    embedded: dict[str, EmbeddedIcon] = {}
    for record in sorted(records, key=lambda item: item.id):
        embedded.setdefault(record.id, load_embedded_icon(record))
    symbols = "".join(
        f'<symbol id="{html.escape(icon.symbol_id, quote=True)}" '
        f'viewBox="{html.escape(icon.view_box, quote=True)}" '
        'overflow="visible">'
        f'{icon.body}</symbol>\n'
        for icon in embedded.values()
    )
    return f'<defs class="pl-architecture-icon-symbols">\n{symbols}</defs>\n', embedded


def resolve_with_fallback(
    record: IconRecord,
    registry: dict[str, IconRecord],
    *,
    cache: dict[str, EmbeddedIcon],
    visited: tuple[str, ...] = (),
) -> tuple[IconRecord, EmbeddedIcon, bool]:
    """Resolve an icon, falling back only to validated registry-owned SVGs."""
    if record.id in visited:
        raise SvgIconEmbedError(
            f"Icon fallback cycle detected: {' -> '.join((*visited, record.id))}"
        )
    if record.id in cache:
        return record, cache[record.id], bool(visited)
    try:
        embedded = load_embedded_icon(record)
        cache[record.id] = embedded
        return record, embedded, bool(visited)
    except SvgIconEmbedError:
        fallback = registry.get(record.fallback_icon)
        if fallback is None or fallback.id == record.id:
            raise
        return resolve_with_fallback(
            fallback,
            registry,
            cache=cache,
            visited=(*visited, record.id),
        )

def symbol_defs_from_icons(icons: Iterable[EmbeddedIcon]) -> str:
    """Serialize an existing embedded-icon set without reparsing assets."""
    unique = {icon.icon_id: icon for icon in icons}
    symbols = "".join(
        f'<symbol id="{html.escape(icon.symbol_id, quote=True)}" '
        f'viewBox="{html.escape(icon.view_box, quote=True)}" '
        'overflow="visible">'
        f'{icon.body}</symbol>\n'
        for icon in sorted(unique.values(), key=lambda item: item.icon_id)
    )
    return f'<defs class="pl-architecture-icon-symbols">\n{symbols}</defs>\n'
