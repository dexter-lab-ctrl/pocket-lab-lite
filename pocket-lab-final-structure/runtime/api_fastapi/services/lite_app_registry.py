from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping

from fastapi import HTTPException

APP_PLATFORM_SCHEMA_VERSION = 1
_APP_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_RESERVED_ROUTE_PREFIXES = ("/api/", "/assets/", "/auth/", "/lite/")


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
        }),
        actions=_PHOTOPRISM_ACTIONS,
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
    if not definition.platforms:
        raise RuntimeError(f"App {definition.id!r} must declare at least one supported platform")
    for action_id in definition.actions:
        if not _APP_ID_RE.fullmatch(action_id.replace("_", "-")):
            raise RuntimeError(f"App {definition.id!r} has invalid action id {action_id!r}")


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
