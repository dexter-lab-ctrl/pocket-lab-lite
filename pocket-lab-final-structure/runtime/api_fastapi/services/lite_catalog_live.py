from __future__ import annotations

import copy
import json
import os
import re
import urllib.request
from pathlib import Path
from typing import Any


PHOTOPRISM_ROUTE = "/apps/photoprism/"
PHOTOPRISM_STATUS_URL = "http://127.0.0.1:8443/apps/photoprism/api/v1/status"
PHOTOPRISM_ROOT_URL = "http://127.0.0.1:8443/apps/photoprism/"
DEFAULT_CADDYFILE = "~/pocket-lab-lite/caddy/Caddyfile"


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


def _url_reachable(url: str, *, timeout: float = 1.5) -> bool:
    try:
        request = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = int(getattr(response, "status", response.getcode()))
            return 200 <= status < 400
    except Exception:
        return False


def _photoprism_route_ready() -> bool:
    # Prefer the app health API when available, but accept the root route redirect/login
    # path as a current liveness signal because PhotoPrism may return 404 for the
    # status endpoint when its base-path configuration changes.
    return _url_json_healthy(PHOTOPRISM_STATUS_URL) or _url_reachable(PHOTOPRISM_ROOT_URL)


def _caddyfile_text() -> str:
    caddyfile = Path(os.environ.get("POCKETLAB_CADDYFILE") or os.environ.get("CADDYFILE") or DEFAULT_CADDYFILE).expanduser()
    try:
        return caddyfile.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def _photoprism_embed_origin_from_caddyfile(text: str | None = None) -> str | None:
    content = text if text is not None else _caddyfile_text()
    if not content or "handle /apps/photoprism/*" not in content:
        return None
    if "header_down -X-Frame-Options" not in content or "header_down -Content-Security-Policy" not in content:
        return None
    match = re.search(
        r'Content-Security-Policy\s+"frame-ancestors\s+\'self\'\s+(https://[A-Za-z0-9.-]+\.ts\.net)"',
        content,
    )
    if not match:
        return None
    return match.group(1)


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


def _hydrate_photoprism(app: dict[str, Any], *, route_ready: bool, embed_origin: str | None) -> None:
    if not _is_photoprism_ready(app):
        return
    runtime = app.setdefault("runtime", {})
    access = app.setdefault("access", {})
    actions = app.setdefault("actions", {})
    workspace = app.setdefault("workspace", {})
    runtime["route"] = runtime.get("route") or PHOTOPRISM_ROUTE
    if route_ready:
        runtime["url"] = PHOTOPRISM_ROUTE
        access["route_ready"] = True
        access["open_url"] = PHOTOPRISM_ROUTE
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


def hydrate_catalog(payload: dict[str, Any]) -> dict[str, Any]:
    hydrated = copy.deepcopy(payload)
    route_ready = _photoprism_route_ready()
    embed_origin = _photoprism_embed_origin_from_caddyfile() if route_ready else None
    for key in ("apps", "items"):
        apps = hydrated.get(key)
        if not isinstance(apps, list):
            continue
        for app in apps:
            if isinstance(app, dict):
                _hydrate_photoprism(app, route_ready=route_ready, embed_origin=embed_origin)
    return hydrated
