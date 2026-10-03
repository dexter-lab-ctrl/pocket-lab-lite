from __future__ import annotations

from dataclasses import dataclass
import os
import platform
import re
import sys
from typing import Any, Mapping

from fastapi import HTTPException

APP_PLATFORM_SCHEMA_VERSION = 1
_APP_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_BINDING_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_UPSTREAM_RE = re.compile(r"^(?:127\.0\.0\.1|localhost):([1-9][0-9]{0,4})$")
_CAPABILITY_RE = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")
_RESERVED_ROUTE_PREFIXES = ("/api/", "/assets/", "/auth/", "/lite/")
_ACTION_CAPABILITIES = {
    "open": "open",
    "open_full_screen": "open",
    "install_to_phone": "open",
    "connect_photos": "media_sources",
    "import_photos": "media_import",
    "check_app": "security_check",
    "backup_app": "backup",
    "preview_restore": "restore_preview",
    "backup_to_storage": "backup_to_storage",
    "install_app": "install",
    "update_app": "update_readiness",
    "repair_app": "repair",
    "remove_app": "remove",
}


@dataclass(frozen=True)
class AppDefinition:
    id: str
    name: str
    category: str
    summary: str
    adapter: str
    route: str
    upstream: str
    process: str
    platforms: tuple[str, ...]
    capabilities: frozenset[str]
    actions: Mapping[str, Mapping[str, Any]]
    placement: Mapping[str, Any]
    credentials: tuple[Mapping[str, Any], ...]
    presentation: Mapping[str, Any]

    def public_contract(self) -> dict[str, Any]:
        return {
            "schema_version": APP_PLATFORM_SCHEMA_VERSION,
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "summary": self.summary,
            "platforms": list(self.platforms),
            "capabilities": {capability: True for capability in sorted(self.capabilities)},
            "actions": {
                action_id: {
                    key: value
                    for key, value in action.items()
                    if key in {"label", "category", "summary", "risk"}
                }
                for action_id, action in self.actions.items()
            },
            "placement": {
                key: value
                for key, value in self.placement.items()
                if key in {"kind", "server_host_only", "required_device_capabilities", "backup_target_capabilities"}
            },
            "credentials": [
                {
                    key: value
                    for key, value in item.items()
                    if key in {"id", "label", "purpose", "required", "management"}
                }
                for item in self.credentials
            ],
        }


_PHOTOPRISM_ACTIONS: dict[str, dict[str, Any]] = {
    "open": {"label": "Open", "category": "access", "summary": "Open PhotoPrism through Pocket Lab.", "risk": "low"},
    "open_full_screen": {"label": "Open full screen", "category": "access", "summary": "Open PhotoPrism in a full browser tab.", "risk": "low"},
    "install_to_phone": {"label": "Install to phone", "category": "access", "summary": "Install the PhotoPrism web app shortcut on this phone.", "risk": "low"},
    "connect_photos": {"label": "Connect photos", "category": "media", "summary": "Choose where PhotoPrism should look for pictures.", "risk": "low"},
    "import_photos": {"label": "Import photos", "category": "media", "summary": "Bring connected photos into PhotoPrism.", "risk": "low"},
    "check_app": {"label": "Check app", "category": "safety", "summary": "Check app health and safe application records. User media is excluded.", "risk": "low"},
    "backup_app": {"label": "Back up app", "category": "recovery", "summary": "Back up safe app settings and records. Media is excluded by default.", "risk": "low"},
    "preview_restore": {"label": "Preview restore", "category": "recovery", "summary": "Review what would be restored before making changes.", "risk": "review"},
    "backup_to_storage": {"label": "Back up to storage device", "category": "recovery", "summary": "Save an app backup to an eligible joined storage device.", "risk": "low"},
    "install_app": {"label": "Install", "category": "setup", "summary": "Set up the app through the backend worker.", "risk": "review"},
    "update_app": {"label": "Update", "category": "setup", "summary": "Check whether the app is ready for a safe update. No update is applied.", "risk": "review"},
    "repair_app": {"label": "Repair", "category": "recovery", "summary": "Repair route, health, and storage setup safely.", "risk": "review"},
    "remove_app": {"label": "Remove app", "category": "danger", "summary": "Remove the app after explicit confirmation while preserving protected data by default.", "risk": "destructive"},
}


_DEFINITIONS = (
    AppDefinition(
        id="photoprism",
        name="PhotoPrism",
        category="Photos",
        summary="Private photo library for your self-hosted workspace.",
        adapter="photoprism",
        route="/apps/photoprism/",
        upstream="127.0.0.1:2342",
        process="pocketlab-app-photoprism",
        platforms=("android-termux-arm64", "ubuntu-dev"),
        capabilities=frozenset({
            "install",
            "open",
            "repair",
            "security_check",
            "backup",
            "backup_to_storage",
            "restore_preview",
            "update_readiness",
            "remove",
            "media_sources",
            "media_import",
            "credentials",
        }),
        actions=_PHOTOPRISM_ACTIONS,
        placement={
            "kind": "server_host",
            "server_host_only": True,
            "required_device_capabilities": ["app_host", "compute"],
            "backup_target_capabilities": ["backup_target", "restore_target"],
        },
        credentials=(
            {
                "id": "app_sign_in",
                "label": "App sign-in",
                "purpose": "interactive_app_access",
                "required": False,
                "management": "external_or_manual",
            },
        ),
        presentation={
            "security_label_ready": "Protected app",
            "backup_label_ready": "Backup ready",
            "media_excluded_from_security_scan": True,
            "media_excluded_from_default_backup": True,
        },
    ),
)


def _validate_definition(definition: AppDefinition) -> None:
    if not _APP_ID_RE.fullmatch(definition.id):
        raise RuntimeError(f"Invalid app id: {definition.id!r}")
    expected_route = f"/apps/{definition.id}/"
    if definition.route != expected_route:
        raise RuntimeError(f"App {definition.id!r} must own exactly {expected_route!r}")
    if any(definition.route.startswith(prefix) for prefix in _RESERVED_ROUTE_PREFIXES):
        raise RuntimeError(f"App {definition.id!r} uses a reserved route")
    if not definition.adapter or not definition.process or not definition.upstream:
        raise RuntimeError(f"App {definition.id!r} is missing a required backend binding")
    if not _BINDING_ID_RE.fullmatch(definition.adapter):
        raise RuntimeError(f"App {definition.id!r} has invalid adapter binding")
    if not _BINDING_ID_RE.fullmatch(definition.process):
        raise RuntimeError(f"App {definition.id!r} has invalid process binding")
    upstream_match = _UPSTREAM_RE.fullmatch(definition.upstream)
    if not upstream_match or not 1 <= int(upstream_match.group(1)) <= 65535:
        raise RuntimeError(f"App {definition.id!r} upstream must be loopback host:port")
    if not definition.platforms:
        raise RuntimeError(f"App {definition.id!r} must declare at least one supported platform")
    if any(not _APP_ID_RE.fullmatch(platform_id) for platform_id in definition.platforms):
        raise RuntimeError(f"App {definition.id!r} has an invalid platform id")
    for capability in definition.capabilities:
        if not _CAPABILITY_RE.fullmatch(capability):
            raise RuntimeError(f"App {definition.id!r} has invalid capability {capability!r}")
    placement_kind = str(definition.placement.get("kind") or "")
    if placement_kind not in {"server_host", "compute", "any_verified_host"}:
        raise RuntimeError(f"App {definition.id!r} has invalid placement kind")
    for capability in definition.placement.get("required_device_capabilities") or ():
        if not _CAPABILITY_RE.fullmatch(str(capability)):
            raise RuntimeError(f"App {definition.id!r} has invalid placement capability")
    for capability in definition.placement.get("backup_target_capabilities") or ():
        if not _CAPABILITY_RE.fullmatch(str(capability)):
            raise RuntimeError(f"App {definition.id!r} has invalid backup-target capability")
    for credential in definition.credentials:
        if not isinstance(credential, Mapping):
            raise RuntimeError(f"App {definition.id!r} credential metadata must be declarative")
        if not _BINDING_ID_RE.fullmatch(str(credential.get("id") or "")):
            raise RuntimeError(f"App {definition.id!r} has invalid credential id")
        if not _CAPABILITY_RE.fullmatch(str(credential.get("purpose") or "").replace("-", "_")):
            raise RuntimeError(f"App {definition.id!r} has invalid credential purpose")
    for action_id, action in definition.actions.items():
        if not _APP_ID_RE.fullmatch(action_id.replace("_", "-")):
            raise RuntimeError(f"App {definition.id!r} has invalid action id {action_id!r}")
        if not isinstance(action, Mapping):
            raise RuntimeError(f"App {definition.id!r} action {action_id!r} must be declarative metadata")
        required_capability = _ACTION_CAPABILITIES.get(action_id)
        if required_capability and required_capability not in definition.capabilities:
            raise RuntimeError(
                f"App {definition.id!r} action {action_id!r} requires capability {required_capability!r}"
            )


def _build_registry(definitions: tuple[AppDefinition, ...]) -> dict[str, AppDefinition]:
    registry: dict[str, AppDefinition] = {}
    routes: set[str] = set()
    for definition in definitions:
        _validate_definition(definition)
        if definition.id in registry:
            raise RuntimeError(f"Duplicate app id: {definition.id}")
        if definition.route in routes:
            raise RuntimeError(f"Duplicate app route: {definition.route}")
        registry[definition.id] = definition
        routes.add(definition.route)
    return registry


_REGISTRY = _build_registry(_DEFINITIONS)


def normalize_app_id(value: Any) -> str:
    app_id = str(value or "").strip().lower()
    if not _APP_ID_RE.fullmatch(app_id):
        raise HTTPException(status_code=400, detail="Invalid app id.")
    return app_id


def app_ids() -> tuple[str, ...]:
    return tuple(sorted(_REGISTRY))


def app_definition(app_id: Any) -> AppDefinition:
    normalized = normalize_app_id(app_id)
    definition = _REGISTRY.get(normalized)
    if definition is None:
        raise HTTPException(status_code=404, detail="App is not registered.")
    return definition


def maybe_app_definition(app_id: Any) -> AppDefinition | None:
    try:
        normalized = normalize_app_id(app_id)
    except HTTPException:
        return None
    return _REGISTRY.get(normalized)


def supports(app_id: Any, capability: str) -> bool:
    definition = maybe_app_definition(app_id)
    return bool(definition and capability in definition.capabilities)


def current_platform_id() -> str:
    prefix = str(os.environ.get("PREFIX") or "").lower()
    machine = platform.machine().lower()
    if "com.termux" in prefix or sys.platform == "android":
        return "android-termux-arm64" if machine in {"aarch64", "arm64"} else "android-termux-unsupported"
    if sys.platform.startswith("linux"):
        return "ubuntu-dev"
    return "unsupported"


def platform_supported(app_id: Any, platform_id: str | None = None) -> bool:
    definition = app_definition(app_id)
    selected = str(platform_id or current_platform_id()).strip().lower()
    return selected in definition.platforms


def registered_action_ids(app_id: Any) -> frozenset[str]:
    definition = app_definition(app_id)
    return frozenset(definition.actions)


def action_definition(app_id: Any, action_id: str) -> Mapping[str, Any] | None:
    definition = app_definition(app_id)
    return definition.actions.get(str(action_id or "").strip())


def public_registry() -> dict[str, Any]:
    return {
        "schema_version": APP_PLATFORM_SCHEMA_VERSION,
        "apps": [definition.public_contract() for definition in _REGISTRY.values()],
        "count": len(_REGISTRY),
    }


def validate_test_definitions(definitions: tuple[AppDefinition, ...]) -> dict[str, AppDefinition]:
    """Test-only validation seam; does not mutate the production registry."""
    return _build_registry(definitions)
