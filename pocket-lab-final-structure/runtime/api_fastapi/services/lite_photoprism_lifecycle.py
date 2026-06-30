from __future__ import annotations

import hashlib
from typing import Any

from fastapi import HTTPException

from .. import deps
from . import lite_catalog, lite_catalog_live

PHOTOPRISM_APP_ID = "photoprism"
LIFECYCLE_ACTIONS = {"install_app", "update_app", "repair_app", "remove_app"}
_SECRET_MARKERS = (
    "token",
    "password",
    "secret",
    "api_key",
    "private_key",
    "credential",
    "vault",
    "nats",
    "restic",
    "backup_key",
    "encryption_key",
)


def _now() -> str:
    return deps.now_utc_iso()


def _validate_app_id(app_id: Any) -> str:
    normalized = str(app_id or "").strip().lower().replace("_", "-")
    if normalized != PHOTOPRISM_APP_ID:
        raise HTTPException(status_code=404, detail={"status": "unsupported_app", "summary": "PhotoPrism is the first app with Lite app lifecycle actions."})
    return normalized


def validate_lifecycle_action(action_id: Any) -> str:
    normalized = str(action_id or "").strip().lower().replace("-", "_")
    if normalized not in LIFECYCLE_ACTIONS:
        raise HTTPException(status_code=404, detail={"status": "unsupported_action", "summary": "Choose a supported PhotoPrism lifecycle action."})
    return normalized


def _safe_text(value: Any, fallback: str = "Available") -> str:
    text = str(value or fallback).strip() or fallback
    lowered = text.lower()
    if any(marker in lowered for marker in _SECRET_MARKERS):
        return fallback
    if (text.startswith("/") or text.startswith("~")) and "/apps/" not in text:
        return fallback
    return text[:220]


def _catalog_app() -> dict[str, Any]:
    payload = lite_catalog.catalog_payload()
    try:
        payload = lite_catalog_live.hydrate_catalog(payload)
    except Exception:
        pass
    for app in payload.get("apps") or payload.get("items") or []:
        if isinstance(app, dict) and str(app.get("id") or "").lower() == PHOTOPRISM_APP_ID:
            return app
    return {}


def installed() -> bool:
    app = _catalog_app()
    return bool(app.get("installed") or app.get("install_state") == "installed" or app.get("status") == "ready")


def lifecycle_state() -> dict[str, Any]:
    app = _catalog_app()
    is_installed = installed()
    status = "ready" if is_installed else "not_installed"
    update_status = "already_current" if is_installed else "not_installed"
    return {
        "app_id": PHOTOPRISM_APP_ID,
        "name": "PhotoPrism",
        "installed": is_installed,
        "status": status,
        "install_state": app.get("install_state") or status,
        "update_status": update_status,
        "summary": "PhotoPrism is installed." if is_installed else "PhotoPrism is not installed yet.",
        "preservation": {
            "media_preserved_by_default": True,
            "backups_preserved_by_default": True,
            "evidence_preserved_by_default": True,
            "storage_mappings_preserved_by_default": True,
        },
        "updated_at": _now(),
    }


def action_readiness() -> dict[str, dict[str, Any]]:
    is_installed = installed()
    return {
        "install_app": {
            "enabled": not is_installed,
            "label": "Install",
            "summary": "Install PhotoPrism on this device." if not is_installed else "PhotoPrism is already installed.",
            **({"reason": "PhotoPrism is already installed. Use Repair if something changed."} if is_installed else {}),
        },
        "update_app": {
            "enabled": False,
            "label": "Update",
            "summary": "Update readiness is checked by Pocket Lab before changes are made.",
            "reason": "Update check not ready yet." if is_installed else "Install PhotoPrism first.",
        },
        "repair_app": {
            "enabled": False,
            "label": "Repair",
            "summary": "Refresh PhotoPrism routing and health checks.",
            "reason": "Repair app is prepared, but backend repair execution is not enabled yet." if is_installed else "Install PhotoPrism first.",
        },
        "remove_app": {
            "enabled": is_installed,
            "label": "Remove app",
            "risk": "destructive",
            "requires_confirmation": True,
            "summary": "Remove PhotoPrism runtime while preserving media, backups, and evidence by default.",
            **({"reason": "Install PhotoPrism first."} if not is_installed else {}),
        },
    }


def install_command(reason: str | None = None) -> dict[str, Any]:
    if installed():
        raise HTTPException(status_code=409, detail={"status": "already_installed", "summary": "PhotoPrism is already installed. Use Repair if something changed."})
    return lite_catalog.install_command(PHOTOPRISM_APP_ID, None, requested_by="lite-api", dry_run=False, params={"reason": _safe_text(reason, "manual install")})


def _remove_id() -> str:
    digest = hashlib.sha256(f"remove|{_now()}".encode("utf-8")).hexdigest()[:12]
    return f"app-remove-photoprism-{digest}"


def remove_not_implemented(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    if not bool(payload.get("confirm")):
        raise HTTPException(
            status_code=409,
            detail={
                "status": "confirmation_required",
                "summary": "Confirm remove before Pocket Lab changes PhotoPrism.",
                "what_will_happen": ["Remove PhotoPrism runtime and Pocket Lab route when remove support is enabled."],
                "what_will_not_happen": ["Your photo files will not be deleted by default.", "Backups and evidence will be preserved by default."],
            },
        )
    reason = str(payload.get("reason") or "").strip()
    if not reason:
        raise HTTPException(status_code=422, detail={"status": "reason_required", "summary": "Add a reason before removing PhotoPrism."})
    return {
        "status": "not_implemented",
        "accepted": False,
        "app_id": PHOTOPRISM_APP_ID,
        "action_id": "remove_app",
        "remove_id": _remove_id(),
        "summary": "Remove app is confirmation-gated, but PhotoPrism removal execution is not enabled yet.",
        "reason": _safe_text(reason, "user requested removal"),
        "preserve_media": bool(payload.get("preserve_media", True)),
        "preserve_backups": bool(payload.get("preserve_backups", True)),
        "preserve_evidence": bool(payload.get("preserve_evidence", True)),
        "preserve_storage_mappings": bool(payload.get("preserve_storage_mappings", True)),
        "evidence": {"status": "pending", "summary": "Pre-remove evidence pending"},
        "sensitive_values_hidden": True,
    }


def update_not_implemented(reason: str | None = None) -> dict[str, Any]:
    return {
        "status": "not_implemented",
        "accepted": False,
        "app_id": PHOTOPRISM_APP_ID,
        "action_id": "update_app",
        "summary": "Update check not ready yet. Pocket Lab will not update PhotoPrism blindly.",
        "reason": _safe_text(reason, "manual update request"),
    }


def repair_not_implemented(reason: str | None = None) -> dict[str, Any]:
    return {
        "status": "not_implemented",
        "accepted": False,
        "app_id": PHOTOPRISM_APP_ID,
        "action_id": "repair_app",
        "summary": "Repair app is prepared, but backend repair execution is not enabled yet.",
        "reason": _safe_text(reason, "manual repair request"),
    }
