"""Versioned, declarative Lite app registry. No executable manifest content or secrets."""
from __future__ import annotations

import re
from typing import Any, Mapping

_SAFE_ID = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
_ALLOWED_ADAPTERS = frozenset({"photoprism"})
_ALLOWED_ACTIONS = frozenset({"open", "install", "check", "repair", "backup", "backup_to_storage", "preview_restore", "update_readiness", "remove"})
_PHOTOPRISM = {"schema_version": 1, "id": "photoprism", "name": "PhotoPrism",
                "adapter": "photoprism", "route": "/apps/photoprism/",
                "platforms": ["termux", "linux-arm64"],
                "capabilities": ["open", "install", "check", "repair", "backup", "backup_to_storage", "preview_restore", "update_readiness", "remove"]}


def validate_app_definition(raw: Mapping[str, Any], *, allowed_adapters: frozenset[str] = _ALLOWED_ADAPTERS) -> dict[str, Any]:
    if not isinstance(raw, Mapping) or type(raw.get("schema_version")) is not int or raw["schema_version"] != 1:
        raise ValueError("Unsupported app definition schema.")
    if set(raw) - {"schema_version", "id", "name", "adapter", "route", "platforms", "capabilities"}:
        raise ValueError("Unknown app definition fields.")
    app_id = raw.get("id")
    adapter = raw.get("adapter")
    route = raw.get("route")
    if not isinstance(app_id, str) or not _SAFE_ID.fullmatch(app_id):
        raise ValueError("Unsafe app ID.")
    if not isinstance(adapter, str) or adapter not in allowed_adapters:
        raise ValueError("Unsupported app adapter.")
    if not isinstance(route, str) or route != f"/apps/{app_id}/":
        raise ValueError("Unsafe app route.")
    if not isinstance(raw.get("name"), str) or not raw["name"].strip() or len(raw["name"]) > 80:
        raise ValueError("Invalid app name.")
    platforms = raw.get("platforms")
    capabilities = raw.get("capabilities")
    if not isinstance(platforms, list) or not platforms or any(p not in {"termux", "linux-arm64"} for p in platforms):
        raise ValueError("Unsupported app platform.")
    if not isinstance(capabilities, list) or any(not isinstance(a, str) or a not in _ALLOWED_ACTIONS for a in capabilities):
        raise ValueError("Unsupported app capability.")
    if len(set(capabilities)) != len(capabilities) or len(set(platforms)) != len(platforms):
        raise ValueError("Duplicate app attributes.")
    return {key: list(value) if isinstance(value, list) else value for key, value in raw.items()}


def load_app_registry(definitions: list[Mapping[str, Any]] | None = None, *, allowed_adapters: frozenset[str] = _ALLOWED_ADAPTERS) -> dict[str, dict[str, Any]]:
    entries = [validate_app_definition(item, allowed_adapters=allowed_adapters) for item in (_default_definitions() if definitions is None else definitions)]
    result: dict[str, dict[str, Any]] = {}
    routes: set[str] = set()
    for item in entries:
        if item["id"] in result or item["route"] in routes:
            raise ValueError("Duplicate app identity or route.")
        result[item["id"]] = item
        routes.add(item["route"])
    return dict(sorted(result.items()))


def _default_definitions() -> list[dict[str, Any]]:
    return [_PHOTOPRISM.copy()]


def project_registered_catalog(payload: dict[str, Any]) -> dict[str, Any]:
    """Annotate supported installed app projections, never fabricate install/action state."""
    registry = load_app_registry()
    for key in ("apps", "items"):
        for app in payload.get(key) or []:
            if not isinstance(app, dict):
                continue
            app_id = str(app.get("id") or "").lower()
            definition = registry.get(app_id)
            if definition is None:
                # Do not make an unknown app executable or available for Open.
                app["actions"] = {}
                app["registry_status"] = "unsupported"
                continue
            app["definition_version"] = definition["schema_version"]
            app["adapter"] = definition["adapter"]
            app["declared_capabilities"] = definition["capabilities"][:]
            app["registry_status"] = "supported"
    payload["registry_schema_version"] = 1
    return payload
