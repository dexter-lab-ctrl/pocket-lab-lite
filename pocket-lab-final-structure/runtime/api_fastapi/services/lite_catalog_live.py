from __future__ import annotations

import copy
import json
import urllib.request
from typing import Any


PHOTOPRISM_ROUTE = "/apps/photoprism/"
PHOTOPRISM_STATUS_URL = "http://127.0.0.1:8443/apps/photoprism/api/v1/status"


def _url_json_healthy(url: str, *, timeout: float = 1.5) -> bool:
    try:
        request = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = int(getattr(response, "status", response.getcode()))
            if status < 200 or status >= 400:
                return False
            body = response.read(1024)
            payload = json.loads(body.decode("utf-8", errors="replace"))
            return payload.get("status") in {"operational", "healthy", "ok"}
    except Exception:
        return False


def _is_photoprism_ready(app: dict[str, Any]) -> bool:
    runtime = app.get("runtime") if isinstance(app.get("runtime"), dict) else {}
    return (
        app.get("id") == "photoprism"
        and (
            app.get("status") == "ready"
            or app.get("install_state") == "installed"
            or app.get("installed") is True
        )
        and runtime.get("health") == "healthy"
    )


def _hydrate_photoprism(app: dict[str, Any], *, route_ready: bool) -> None:
    if not _is_photoprism_ready(app):
        return
    runtime = app.setdefault("runtime", {})
    access = app.setdefault("access", {})
    actions = app.setdefault("actions", {})
    runtime["route"] = runtime.get("route") or PHOTOPRISM_ROUTE
    if route_ready:
        runtime["url"] = PHOTOPRISM_ROUTE
        access["route_ready"] = True
        access["open_url"] = PHOTOPRISM_ROUTE
        access["message"] = "Open is ready."
        actions["open"] = True
    else:
        access["route_ready"] = False
        access["open_url"] = None
        access["message"] = "Open is not ready yet."
        actions["open"] = False


def hydrate_catalog(payload: dict[str, Any]) -> dict[str, Any]:
    hydrated = copy.deepcopy(payload)
    route_ready = _url_json_healthy(PHOTOPRISM_STATUS_URL)
    for key in ("apps", "items"):
        apps = hydrated.get(key)
        if not isinstance(apps, list):
            continue
        for app in apps:
            if isinstance(app, dict):
                _hydrate_photoprism(app, route_ready=route_ready)
    return hydrated
