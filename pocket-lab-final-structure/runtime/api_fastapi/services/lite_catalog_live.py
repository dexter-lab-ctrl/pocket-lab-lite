from __future__ import annotations

import copy
from typing import Any

from . import lite_app_adapters, lite_app_registry


def _photoprism_route_ready() -> bool:
    """Compatibility seam for existing qualification tests."""
    return lite_app_adapters.adapter_for("photoprism").route_ready()


def _photoprism_embed_origin_from_caddyfile() -> str | None:
    """Compatibility seam; the adapter remains the single implementation owner."""
    return lite_app_adapters.adapter_for("photoprism").embed_origin()


def hydrate_catalog(payload: dict[str, Any]) -> dict[str, Any]:
    """Hydrate live app facts through the registered backend adapter.

    Catalog GETs remain sanitized and bounded: adapters own any app-specific
    readiness probes, while unknown/unregistered apps are left untouched
    rather than gaining implicit execution behavior.
    """
    hydrated = copy.deepcopy(payload)
    for key in ("apps", "items"):
        apps = hydrated.get(key)
        if not isinstance(apps, list):
            continue
        for app in apps:
            if not isinstance(app, dict):
                continue
            app_id = app.get("id")
            definition = lite_app_registry.maybe_app_definition(app_id)
            if definition is None:
                continue
            app.setdefault("platform_contract", definition.public_contract())
            adapter = lite_app_adapters.adapter_for(definition.id)
            if definition.id == "photoprism" and isinstance(adapter, lite_app_adapters.PhotoPrismAdapter):
                if adapter.should_probe_live_state(app):
                    route_ready = _photoprism_route_ready()
                    embed_origin = _photoprism_embed_origin_from_caddyfile() if route_ready else None
                    adapter.hydrate_with_readiness(app, route_ready=route_ready, embed_origin=embed_origin)
            else:
                adapter.hydrate_live_state(app)
    return hydrated
