from __future__ import annotations

import json
import os
import re
import urllib.request
from pathlib import Path
from typing import Any, Protocol

from fastapi import HTTPException

from . import lite_app_registry


class AppAdapter(Protocol):
    app_id: str
    services: frozenset[str]

    def route_ready(self) -> bool: ...

    def embed_origin(self) -> str | None: ...

    def hydrate_with_readiness(
        self,
        app: dict[str, Any],
        *,
        route_ready: bool,
        embed_origin: str | None,
    ) -> None:
        runtime = app.get("runtime") if isinstance(app.get("runtime"), dict) else {}
        installed = app.get("status") == "ready" or app.get("install_state") == "installed" or app.get("installed") is True
        if not installed or runtime.get("health") != "healthy":
            return

        runtime = app.setdefault("runtime", {})
        access = app.setdefault("access", {})
        actions = app.setdefault("actions", {})
        workspace = app.setdefault("workspace", {})
        runtime["route"] = runtime.get("route") or self.definition.route

        if route_ready:
            runtime["url"] = self.definition.route
            access["route_ready"] = True
            access["open_url"] = self.definition.route
            access["message"] = "Open is ready."
            actions["open"] = True
            if embed_origin:
                access["embed_allowed"] = True
                access["embed_policy"] = "portal_only"
                access["embed_origin"] = embed_origin
                workspace["embed_allowed"] = True
                workspace["mode"] = "embed"
                runtime["embed_allowed"] = True
            else:
                access["embed_allowed"] = False
                access["embed_policy"] = "full_screen"
                access.pop("embed_origin", None)
                workspace["embed_allowed"] = False
                runtime["embed_allowed"] = False
        else:
            access["route_ready"] = False
            access["open_url"] = None
            access["message"] = "Open is not ready yet."
            access["embed_allowed"] = False
            access["embed_policy"] = "full_screen"
            access.pop("embed_origin", None)
            workspace["embed_allowed"] = False
            runtime["embed_allowed"] = False
            actions["open"] = False

    def hydrate_live_state(self, app: dict[str, Any]) -> None:
        route_ready = self.route_ready()
        embed_origin = self.embed_origin() if route_ready else None
        self.hydrate_with_readiness(app, route_ready=route_ready, embed_origin=embed_origin)


_ADAPTERS: dict[str, AppAdapter] = {
    "photoprism": PhotoPrismAdapter(),
}


def adapter_for(app_id: Any) -> AppAdapter:
    definition = lite_app_registry.app_definition(app_id)
    adapter = _ADAPTERS.get(definition.adapter)
    if adapter is None or adapter.app_id != definition.id:
        raise RuntimeError(f"App adapter binding is unavailable for {definition.id!r}")
    return adapter


def supports_service(app_id: Any, service: str) -> bool:
    try:
        adapter = adapter_for(app_id)
    except (HTTPException, RuntimeError):
        return False
    return str(service or "").strip() in adapter.services


def app_ids_for_service(service: str) -> tuple[str, ...]:
    return tuple(
        app_id
        for app_id in lite_app_registry.app_ids()
        if supports_service(app_id, service)
    )


def validate_adapter_bindings() -> None:
    for app_id in lite_app_registry.app_ids():
        adapter = adapter_for(app_id)
        if not adapter.services:
            raise RuntimeError(f"App adapter {app_id!r} must explicitly declare implemented services")


validate_adapter_bindings()
