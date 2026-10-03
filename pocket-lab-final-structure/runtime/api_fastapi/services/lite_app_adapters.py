from __future__ import annotations

import json
import os
import re
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from fastapi import HTTPException

from . import lite_app_registry


class AppAdapter(Protocol):
    app_id: str
    services: frozenset[str]

    def route_ready(self) -> bool: ...

    def embed_origin(self) -> str | None: ...

    def hydrate_live_state(self, app: dict[str, Any]) -> None: ...

    def catalog_payload(self, state: dict[str, Any], access: dict[str, Any]) -> dict[str, Any]: ...

    def lifecycle_profile(self, stage_timings: dict[str, float] | None = None) -> dict[str, Any]: ...

    def security_profile(self) -> dict[str, Any]: ...

    def backup_profile(self) -> dict[str, Any]: ...

    def backup_policy(self) -> dict[str, Any]: ...

    def update_status(self) -> dict[str, Any]: ...

    def update_receipt(self, operation_id: str) -> dict[str, Any] | None: ...

    def update_apply_disabled(self) -> dict[str, Any]: ...

    def media_status(self) -> dict[str, Any]: ...

    def media_import_blocked(self) -> bool: ...

    def prepare_special_action(
        self,
        action_id: str,
        payload: dict[str, Any],
        reason: str | None,
    ) -> dict[str, Any] | None: ...


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


def _caddyfile_text() -> str:
    default = "~/pocket-lab-lite/caddy/Caddyfile"
    caddyfile = Path(os.environ.get("POCKETLAB_CADDYFILE") or os.environ.get("CADDYFILE") or default).expanduser()
    try:
        return caddyfile.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


class PhotoPrismAdapter:
    app_id = "photoprism"
    services = frozenset({
        "actions",
        "catalog",
        "backup",
        "backup_to_storage",
        "install",
        "lifecycle",
        "profiles",
        "security_profile",
        "backup_profile",
        "update_readiness",
    })

    @property
    def definition(self) -> lite_app_registry.AppDefinition:
        return lite_app_registry.app_definition(self.app_id)

    def route_ready(self) -> bool:
        route = self.definition.route.rstrip("/")
        status_url = f"http://127.0.0.1:8443{route}/api/v1/status"
        root_url = f"http://127.0.0.1:8443{self.definition.route}"
        return _url_json_healthy(status_url) or _url_reachable(root_url)

    def embed_origin(self) -> str | None:
        content = _caddyfile_text()
        if not content or f"handle {self.definition.route}*" not in content:
            return None
        if "header_down -X-Frame-Options" not in content or "header_down -Content-Security-Policy" not in content:
            return None
        match = re.search(
            r'Content-Security-Policy\s+"frame-ancestors\s+\'self\'\s+(https://[A-Za-z0-9.-]+\.ts\.net)"',
            content,
        )
        return match.group(1) if match else None

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

    def catalog_payload(self, state: dict[str, Any], access: dict[str, Any]) -> dict[str, Any]:
        from . import lite_catalog

        app = lite_catalog._get_app_state(state)
        payload = lite_catalog._app_payload(app, access)
        payload["platform_contract"] = self.definition.public_contract()
        return payload

    def lifecycle_profile(self, stage_timings: dict[str, float] | None = None) -> dict[str, Any]:
        from . import lite_app_lifecycle

        return lite_app_lifecycle.photoprism_lifecycle_profile(stage_timings)

    def security_profile(self) -> dict[str, Any]:
        from . import lite_app_profiles

        return lite_app_profiles.photoprism_security_profile()

    def backup_profile(self) -> dict[str, Any]:
        from . import lite_app_profiles

        return lite_app_profiles.photoprism_backup_profile()

    def backup_policy(self) -> dict[str, Any]:
        return {
            "default_mode": "config_only",
            "included_sets": [
                "app_config",
                "photoprism_safe_configuration",
                "photoprism_metadata_database",
                "app_metadata",
                "storage_mappings",
                "route_registry",
                "safe_evidence_refs",
            ],
            "excluded_sets": [
                "android_shared_storage",
                "original_media",
                "import_folder_media",
                "generated_cache",
                "raw_secrets",
            ],
            "media_included_by_default": False,
            "restore_preview_supported": True,
            "restore_apply_supported": False,
            "profile_summary": "PhotoPrism settings, mappings, route records, and safe app records are included. Media is excluded by default.",
            "backup_summary": "PhotoPrism app backup saved. Settings, mappings, route records, and safe app records are protected; media remains excluded by default.",
        }

    def update_status(self) -> dict[str, Any]:
        from . import lite_app_update

        return lite_app_update.update_status(self.app_id)

    def update_receipt(self, operation_id: str) -> dict[str, Any] | None:
        from . import lite_app_update

        return lite_app_update.update_receipt(self.app_id, operation_id)

    def update_apply_disabled(self) -> dict[str, Any]:
        from . import lite_app_update

        return lite_app_update.apply_update_disabled(self.app_id)

    def media_status(self) -> dict[str, Any]:
        from . import lite_photoprism_media

        return lite_photoprism_media.media_status(self.app_id)

    def media_import_blocked(self) -> bool:
        from . import lite_photoprism_media

        return bool(lite_photoprism_media.live_phone_import_blocked())

    def prepare_special_action(
        self,
        action_id: str,
        payload: dict[str, Any],
        reason: str | None,
    ) -> dict[str, Any] | None:
        if action_id == "remove_app":
            from . import lite_photoprism_lifecycle

            response = lite_photoprism_lifecycle.remove_not_implemented(payload)
            return {
                "kind": "remove_not_implemented",
                "response": response,
                "summary": response.get("summary"),
            }
        if action_id == "connect_photos":
            return {
                "kind": "guidance",
                "status": "ready",
                "accepted": False,
                "app_id": self.app_id,
                "action_id": action_id,
                "label": "Connect photos",
                "summary": "Use the media folder buttons to connect phone photos safely.",
            }
        if action_id == "import_photos":
            from . import lite_photoprism_media

            command = lite_photoprism_media.media_command(action_id, reason=reason)
            return {"kind": "media", "command": command, "summary": "Photo import queued."}
        if action_id == "install_app":
            from . import lite_photoprism_lifecycle

            command = lite_photoprism_lifecycle.install_command(reason=reason)
            return {"kind": "install_app", "command": command, "summary": "PhotoPrism install started."}
        if action_id == "check_app":
            from . import lite_security

            run_id = f"security-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
            return {
                "kind": "security_app_check",
                "subject": lite_security.policy.COMMAND_SUBJECT,
                "command": {
                    "run_id": run_id,
                    "command_id": run_id,
                    "scope": "local",
                    "profile": "app",
                    "app_id": self.app_id,
                    "reason": reason or "manual app check",
                    "requested_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                },
                "summary": "Checking PhotoPrism safety.",
            }
        if action_id == "repair_app":
            from . import lite_app_operations

            command = lite_app_operations.command_for_operation(self.app_id, action_id, reason=reason)
            return {
                "kind": "app_operation",
                "command": command,
                "subject": lite_app_operations.subject_for_action(action_id),
                "summary": "Repairing PhotoPrism safely.",
            }
        if action_id == "update_app":
            from . import lite_app_update

            command = lite_app_update.update_command(self.app_id, reason=reason)
            return {
                "kind": "update_check",
                "command": command,
                "subject": lite_app_update.APP_UPDATE_CHECK_SUBJECT,
                "summary": "Checking PhotoPrism update readiness.",
            }
        return None


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
    service_methods = {
        "catalog": "catalog_payload",
        "lifecycle": "lifecycle_profile",
        "security_profile": "security_profile",
        "backup_profile": "backup_profile",
        "backup": "backup_policy",
        "update_readiness": "update_status",
        "actions": "prepare_special_action",
    }
    for app_id in lite_app_registry.app_ids():
        adapter = adapter_for(app_id)
        if not adapter.services:
            raise RuntimeError(f"App adapter {app_id!r} must explicitly declare implemented services")
        for service, method_name in service_methods.items():
            if service in adapter.services and not callable(getattr(adapter, method_name, None)):
                raise RuntimeError(f"App adapter {app_id!r} declares {service!r} without {method_name}()")


validate_adapter_bindings()
