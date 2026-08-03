#!/usr/bin/env python3
"""Build compact source inventories once and verify architecture declarations."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from architecture_model import ROOT, canonical_json


class SourceVerificationError(ValueError):
    """Raised when canonical architecture declarations cannot be verified in source."""


@dataclass(frozen=True)
class SourceInventory:
    paths: frozenset[str]
    routes: frozenset[str]
    nats_subjects: frozenset[str]
    pm2_processes: frozenset[str]
    sqlite_tables: frozenset[str]
    bootstrap_stages: frozenset[str]
    source_files: tuple[str, ...]
    fingerprint: str


def _load(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        raise SourceVerificationError(
            f"Cannot build source inventory from {path.relative_to(ROOT)}: {exc}"
        ) from exc


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_source_inventory(model: dict[str, Any]) -> SourceInventory:
    source_map = model.get("source_inventory") or {}
    required = {"openapi", "asyncapi", "services", "sqlite", "bootstrap", "projections", "icons"}
    missing = sorted(required - source_map.keys())
    if missing:
        raise SourceVerificationError(
            f"Architecture source_inventory is missing: {', '.join(missing)}"
        )
    source_files = tuple(sorted(str(source_map[key]) for key in required))
    for relative in source_files:
        if not (ROOT / relative).is_file():
            raise SourceVerificationError(f"Missing prepared source inventory: {relative}")
    openapi = _load(ROOT / source_map["openapi"])
    routes: set[str] = set()
    for path, operations in (openapi.get("paths") or {}).items():
        if not isinstance(operations, dict):
            continue
        for method in operations:
            if method.lower() in {"get", "post", "put", "patch", "delete"}:
                routes.add(f"{method.upper()} {path}")
    asyncapi = _load(ROOT / source_map["asyncapi"])
    nats_subjects = set((asyncapi.get("channels") or {}).keys())
    services = _load(ROOT / source_map["services"])
    pm2_processes = {
        str(item.get("pattern")) for item in services.get("service_catalog", [])
        if isinstance(item, dict) and item.get("pattern")
    }
    sqlite = _load(ROOT / source_map["sqlite"])
    sqlite_tables = {
        str(item.get("name"))
        for item in (sqlite.get("lite_sqlite_schema") or {}).get("objects", [])
        if isinstance(item, dict) and item.get("type") == "table" and item.get("name")
    }
    bootstrap = _load(ROOT / source_map["bootstrap"])
    bootstrap_stages = {
        str(item.get("stage")) for item in bootstrap.get("bootstrap_stages", [])
        if isinstance(item, dict) and item.get("stage")
    }
    paths = frozenset(
        path.relative_to(ROOT).as_posix() for path in ROOT.rglob("*") if path.is_file()
    )
    input_hashes = {relative: _sha(ROOT / relative) for relative in source_files}
    fingerprint = hashlib.sha256(canonical_json(input_hashes).encode("utf-8")).hexdigest()
    return SourceInventory(
        paths=paths,
        routes=frozenset(routes),
        nats_subjects=frozenset(nats_subjects),
        pm2_processes=frozenset(pm2_processes),
        sqlite_tables=frozenset(sqlite_tables),
        bootstrap_stages=frozenset(bootstrap_stages),
        source_files=source_files,
        fingerprint=fingerprint,
    )


def _verify_reference(reference: dict[str, Any], inventory: SourceInventory) -> str | None:
    kind, value = reference["kind"], reference["value"]
    if kind in {"path", "doc", "contract"}:
        return None if value in inventory.paths else f"missing {kind} {value}"
    if kind == "route":
        return None if value in inventory.routes else f"missing FastAPI route {value}"
    if kind == "nats_subject":
        return None if value in inventory.nats_subjects else f"missing NATS subject {value}"
    if kind == "pm2_process":
        return None if value in inventory.pm2_processes else f"missing PM2 process pattern {value}"
    if kind == "sqlite_table":
        return None if value in inventory.sqlite_tables else f"missing SQLite table {value}"
    if kind == "bootstrap_stage":
        return None if value in inventory.bootstrap_stages else f"missing bootstrap stage {value}"
    if kind == "literal":
        path = reference.get("path")
        if path not in inventory.paths:
            return f"missing literal source path {path}"
        text = (ROOT / path).read_text(encoding="utf-8", errors="ignore")
        return None if value in text else f"missing literal {value!r} in {path}"
    return f"unsupported source reference kind {kind!r}"


def verify_sources(
    model: dict[str, Any], inventory: SourceInventory, *, fail_fast: bool = False
) -> dict[str, Any]:
    failures: list[dict[str, str]] = []
    verified_count = 0
    for component_id, component in model["components"].items():
        component_failures = []
        for reference in component["source_verification"]:
            error = _verify_reference(reference, inventory)
            if error:
                component_failures.append(error)
                if fail_fast:
                    raise SourceVerificationError(f"{component_id}: {error}")
            else:
                verified_count += 1
        for doc in component["documentation_links"]:
            if doc not in inventory.paths:
                component_failures.append(f"missing documentation link {doc}")
        for error in component_failures:
            failures.append({"component_id": component_id, "error": error})
    if failures:
        details = "\n".join(
            f" - {item['component_id']}: {item['error']}" for item in failures[:50]
        )
        suffix = "" if len(failures) <= 50 else f"\n - ... {len(failures) - 50} more"
        raise SourceVerificationError(
            f"Architecture source verification failed ({len(failures)} issues):\n{details}{suffix}"
        )
    return {
        "status": "verified",
        "verified_reference_count": verified_count,
        "component_count": len(model["components"]),
        "inventory_fingerprint": inventory.fingerprint,
        "inventory_sources": list(inventory.source_files),
    }
