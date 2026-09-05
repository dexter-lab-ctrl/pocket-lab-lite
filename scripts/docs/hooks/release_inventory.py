#!/usr/bin/env python3
"""MkDocs hook dispatcher for release inventory plus Device Facts navigation.

The release-inventory implementation is preserved byte-for-byte in
``release_inventory_impl.py``.  This dispatcher keeps that existing page hook
and adds only the repository-owned Device Facts navigation entries, avoiding a
broad rewrite of ``mkdocs.yml`` or generated release navigation.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

_IMPL_PATH = Path(__file__).with_name("release_inventory_impl.py")
_SPEC = importlib.util.spec_from_file_location("pocketlab_release_inventory_impl", _IMPL_PATH)
if _SPEC is None or _SPEC.loader is None:  # pragma: no cover - configuration failure
    raise RuntimeError("release inventory hook implementation is unavailable")
_IMPL = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_IMPL)

on_page_markdown = _IMPL.on_page_markdown


def _section(nav: list[Any], label: str) -> list[Any] | None:
    for item in nav:
        if isinstance(item, dict) and isinstance(item.get(label), list):
            return item[label]
    return None


def _contains(section: list[Any], label: str) -> bool:
    return any(isinstance(item, dict) and label in item for item in section)


def _insert_after(section: list[Any], anchor: str, label: str, target: str) -> None:
    if _contains(section, label):
        return
    for index, item in enumerate(section):
        if isinstance(item, dict) and anchor in item:
            section.insert(index + 1, {label: target})
            return
    section.append({label: target})


def on_config(config: Any) -> Any:
    """Add Device Facts pages to the existing MkDocs nav without replacing it."""
    nav = config.get("nav") if hasattr(config, "get") else None
    if not isinstance(nav, list):
        return config

    understand = _section(nav, "Understand")
    if understand is not None:
        _insert_after(
            understand,
            "Data & projections",
            "Shared Device Facts",
            "architecture/device-facts-telemetry-capability-projection.md",
        )

    build_test = _section(nav, "Build & Test")
    if build_test is not None:
        _insert_after(
            build_test,
            "Backend / FastAPI contract",
            "Device Facts contract",
            "generated/development/device-facts-contract.md",
        )

    reference = _section(nav, "Reference")
    if reference is not None:
        _insert_after(
            reference,
            "Device production readiness",
            "Device Facts API projection",
            "operations/device-facts-api.md",
        )

    return config
