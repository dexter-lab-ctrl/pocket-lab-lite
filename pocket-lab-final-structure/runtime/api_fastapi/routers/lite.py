from __future__ import annotations

import json
import os
import uuid

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from .. import deps
from ..schemas.operations import OperationRequest
from ..services.action_queue import ensure_worker_execution_ready, submit_domain_command, submit_operation_command
from ..services import fleet_registry, lite_app_actions, lite_app_lifecycle, lite_app_profiles, lite_app_storage, lite_app_backup_targets, lite_app_operations, lite_backup, lite_catalog, lite_invites, lite_status, lite_security, lite_catalog_live, lite_photoprism_media, lite_evidence_receipts

router = APIRouter(prefix="/api/lite", tags=["lite"])

def _lite_payload_dict(payload):
    """Return a request model as a dict on both Pydantic v1 and v2."""
    if payload is None:
        return {}
    if isinstance(payload, dict):
        return payload
    if hasattr(payload, "model_dump"):
        return payload.model_dump()
    if hasattr(payload, "dict"):
        return payload.dict()
    return {}


class LiteCatalogInstallRequest(BaseModel):
    app_id: str = Field(default="", description="Catalog app id")
    target_node_id: str | None = Field(default=None, description="Target Lite device id. PhotoPrism is server-host only in this release.")
    version: str | None = None
    dry_run: bool = False
    requested_by: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)


class LiteCatalogRemoveRequest(BaseModel):
    app_id: str = Field(default="", description="Catalog app or blueprint id")
    confirm: bool = False
    requested_by: str | None = None


class LitePhotoPrismStorageMappingRequest(BaseModel):
    source_type: Literal["phone_media", "managed_media", "storage_device"] = "phone_media"
    label: str | None = None
    source_path: str = Field(default="", description="Approved Pocket Lab media folder path")
    target: Literal["import", "originals"] = "import"
    mode: Literal["read_only", "read_write"] = "read_only"
    device_id: str | None = None
    device_name: str | None = None


class LiteIdentityRotateRequest(BaseModel):
    target: str = "default"
    value: str | None = None
    lease_duration: str | None = None


class LiteSecurityScanRequest(BaseModel):
    scope: str = "local"
    reason: str | None = None


class LiteAppSecurityCheckRequest(BaseModel):
    reason: str | None = None


class LiteAppBackupRequest(BaseModel):
    mode: Literal["config_only", "config_and_index", "full_with_media"] = "config_only"
    reason: str | None = None


class LiteAppRestorePreviewRequest(BaseModel):
    backup_id: str | None = None
    reason: str | None = None


class LiteAppRestoreRequest(BaseModel):
    backup_id: str | None = None
    preview_id: str | None = None
    confirm: bool = False


class LiteAppActionRequest(BaseModel):
    reason: str | None = None
    target_device_id: str | None = None
    confirm: bool = False
    preserve_media: bool = True
    preserve_backups: bool = True
    preserve_evidence: bool = True
    preserve_storage_mappings: bool = True


class LiteAddDeviceRequest(BaseModel):
    role: Literal["compute", "storage"] = Field(
        default="compute",
        description="Lite device role: compute for App Host or storage for Storage Node",
    )
    hostname: str | None = None


class LiteRemoveDeviceRequest(BaseModel):
    device_id: str = Field(default="", description="Lite device id to remove from saved records")
    confirm: bool = False
    reason: str | None = None
    requested_by: str | None = None


class LitePolicyApplyRequest(BaseModel):
    protection_enabled: bool = False
    reason: str | None = None


class LiteBackupRequest(BaseModel):
    include_event_journal: bool = True
    include_app_data: bool = False
    reason: str | None = None
    dry_run: bool = False


class LiteBackupVerifyRequest(BaseModel):
    backup_id: str = "latest"
    reason: str | None = None


class LiteRestorePreviewRequest(BaseModel):
    backup_id: str = "latest"
    reason: str | None = None


class LiteRestoreRequest(BaseModel):
    backup_id: str | None = None
    backup_ref: str = "latest"
    preview_id: str | None = None
    confirm: bool = False
    dry_run: bool = False


def _operation_payload(operation: str, target: dict[str, Any], params: dict[str, Any], *, dry_run: bool = False) -> tuple[OperationRequest, dict[str, Any]]:
    raw = {
        "operation": operation,
        "target": target,
        "params": params,
        "dry_run": dry_run,
        "source": "lite-api",
    }
    return deps.normalize_operation_request(raw), raw


def _safe_duplicate_conflict_payload(conflict: dict[str, Any]) -> dict[str, Any]:
    return {
        "device_id": conflict.get("device_id"),
        "device_name": conflict.get("device_name"),
        "role": conflict.get("role"),
        "status": conflict.get("status"),
        "connection": conflict.get("connection"),
        "source": conflict.get("source"),
        "can_remove_old_record": bool(conflict.get("can_remove_old_record")),
    }


def _duplicate_device_detail(conflict: dict[str, Any]) -> dict[str, Any]:
    status = str(conflict.get("status") or "unknown").lower()
    connection = str(conflict.get("connection") or "unknown").lower()
    can_remove = bool(conflict.get("can_remove_old_record"))
    if connection == "online" or status in {"healthy", "active", "online", "ready"}:
        message = "This device is already connected. Use a different name if this is another phone."
    elif status in {"pending", "invited"} or connection == "waiting":
        message = "An invite for this device is already in progress. Use the existing invite or wait for the device to connect."
    elif status in {"joining", "accepted"} or connection == "joining":
        message = "This device is already joining. Use the existing invite or wait for the device to connect."
    elif can_remove:
        message = "An old device record already uses this name. Remove the old device record before creating a new invite."
    else:
        message = "Choose a different name, or refresh the Devices list before trying again."
    return {
        "status": "duplicate_device",
        "summary": "A device with this name already exists.",
        "message": message,
        "existing_device": _safe_duplicate_conflict_payload(conflict),
        "safe_next_actions": [
            "Use a different device name",
            "Refresh the Devices list",
            "Remove the old device record if it is no longer used",
        ],
    }


def _candidate_device_name(payload: LiteAddDeviceRequest) -> str:
    if (payload.hostname or "").strip():
        return str(payload.hostname).strip()
    role_info = lite_invites.role_metadata(payload.role)
    return f"Pocket Lab {role_info['role_label']}"


@router.get("/status")
async def get_lite_status(request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    return await lite_status.build_lite_status()


@router.get("/catalog")
def get_lite_catalog(request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    return lite_app_lifecycle.hydrate_catalog_lifecycle(lite_catalog_live.hydrate_catalog(lite_catalog.catalog_payload(request)))



@router.get("/apps/lifecycle")
def get_lite_app_lifecycle_profiles(request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    return lite_app_lifecycle.app_lifecycle_profiles()


@router.get("/apps/lifecycle/{app_id}")
def get_lite_app_lifecycle_profile(app_id: str, request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    return lite_app_lifecycle.app_lifecycle_profile(app_id)


@router.get("/apps/{app_id}/actions")
def get_lite_app_actions(app_id: str, request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    return lite_app_actions.app_actions(app_id)


@router.get("/apps/{app_id}/evidence")
def get_lite_app_evidence(app_id: str, request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    return lite_evidence_receipts.app_evidence(app_id)


@router.post("/apps/{app_id}/actions/{action_id}")
async def run_lite_app_action(app_id: str, action_id: str, payload: LiteAppActionRequest, request: Request) -> dict[str, Any]:
    deps.require_auth(request, write=True)
    action = lite_app_actions.prepare_action(app_id, action_id, payload=_lite_payload_dict(payload))
    kind = action.get("kind")

    if kind in {"url", "guidance"}:
        return {key: value for key, value in action.items() if key != "kind"}

    if kind == "backup":
        command = action["command"]
        try:
            submitted = await submit_domain_command(
                lite_app_profiles.APP_BACKUP_SUBJECT,
                "lite.backup.app_queued",
                command,
            )
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail={
                    "status": "app_backup_queue_unavailable",
                    "summary": "App backup request could not be queued because the local command bus is not reachable.",
                    "detail": str(exc),
                },
            ) from exc
        pending = lite_backup.record_backup_request(command)
        submitted.update({
            "accepted": True,
            "status": submitted.get("status") or "queued",
            "app_id": "photoprism",
            "action_id": "backup_app",
            "backup_id": command["backup_id"],
            "mode": command["app_backup_mode"],
            "pending_backup": pending,
            "summary": "PhotoPrism app backup queued. Config and app metadata are included; media remains excluded unless a supported media backup mode is enabled.",
        })
        return submitted

    if kind == "media":
        command = action["command"]
        try:
            submitted = await submit_domain_command(
                lite_photoprism_media.MEDIA_COMMAND_SUBJECT,
                "lite.app.media.queued",
                command,
            )
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail={
                    "status": "media_action_queue_unavailable",
                    "summary": "PhotoPrism media action could not be queued because the local command bus is not reachable.",
                    "detail": str(exc),
                },
            ) from exc
        operation = lite_photoprism_media.record_operation(command, status="queued")
        submitted.update({
            "accepted": True,
            "status": submitted.get("status") or "queued",
            "app_id": "photoprism",
            "action_id": command["action_id"],
            "media_operation": operation,
            "summary": action.get("summary") or operation.get("summary") or "PhotoPrism media action queued.",
            "evidence": {"status": "pending", "summary": "Media evidence pending"},
        })
        return submitted

    if kind == "app_operation":
        command = action["command"]
        subject = action.get("subject") or lite_app_operations.subject_for_action(command.get("action_id"))
        await ensure_worker_execution_ready()
        operation = lite_app_operations.record_queued_operation(command)
        try:
            submitted = await submit_domain_command(
                subject,
                "lite.app.operation.queued",
                command,
                trace_id=command.get("command_id"),
            )
        except Exception as exc:
            lite_app_operations.mark_operation_failed(command, "App action could not be queued safely.")
            raise
        submitted.update({
            "accepted": True,
            "status": submitted.get("status") or "queued",
            "app_id": "photoprism",
            "action_id": command["action_id"],
            "operation": operation,
            "summary": action.get("summary") or operation.get("summary") or "App action queued.",
            "progress": operation.get("progress") or {"phase": "queued", "step": "Request queued.", "bounded": True},
            "evidence": {"status": "pending", "summary": "Evidence pending."},
        })
        return submitted

    if kind == "media_fast_forward":
        response = action.get("response") if isinstance(action.get("response"), dict) else {}
        response.setdefault("accepted", True)
        response.setdefault("status", "skipped")
        response.setdefault("app_id", "photoprism")
        response.setdefault("action_id", "index_photos")
        response.setdefault("fast_forwarded", True)
        return response

    if kind == "cancel_media":
        response = action.get("response") if isinstance(action.get("response"), dict) else {}
        response.setdefault("accepted", True)
        response.setdefault("status", "cancelled")
        response.setdefault("app_id", "photoprism")
        response.setdefault("action_id", "cancel_media")
        return response

    if kind == "install_app":
        command = action["command"]
        await ensure_worker_execution_ready()
        lite_catalog.record_install_queued(command)
        try:
            queued = await submit_domain_command(
                lite_catalog.COMMAND_SUBJECT,
                "lite.catalog.install.requested",
                command,
                trace_id=command["operation_id"],
            )
        except Exception:
            lite_catalog.discard_operation(command["operation_id"])
            raise
        queued.update({
            "accepted": True,
            "status": "queued",
            "app_id": "photoprism",
            "action_id": "install_app",
            "operation_id": command["operation_id"],
            "summary": "PhotoPrism install started.",
        })
        return queued

    if kind == "backup_to_storage_not_implemented":
        raise HTTPException(status_code=501, detail=action["response"])

    if kind == "remove_not_implemented":
        raise HTTPException(status_code=501, detail=action["response"])

    if kind == "update_not_implemented":
        raise HTTPException(status_code=501, detail=action["response"])

    if kind == "repair_not_implemented":
        raise HTTPException(status_code=501, detail=action["response"])

    raise HTTPException(
        status_code=501,
        detail={
            "status": "not_implemented",
            "summary": "This app action is not implemented yet.",
        },
    )


@router.get("/apps/photoprism/storage-preview")
def get_photoprism_storage_preview(request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    return lite_app_storage.photoprism_storage_preview()


@router.get("/apps/photoprism/storage-mappings")
def get_photoprism_storage_mappings(request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    return lite_app_storage.list_mappings("photoprism")


@router.post("/apps/photoprism/storage-mappings", status_code=201)
def create_photoprism_storage_mapping(payload: LitePhotoPrismStorageMappingRequest, request: Request) -> dict[str, Any]:
    deps.require_auth(request, write=True)
    return lite_app_storage.create_mapping(_lite_payload_dict(payload))


@router.delete("/apps/photoprism/storage-mappings/{mapping_id}")
def delete_photoprism_storage_mapping(mapping_id: str, request: Request) -> dict[str, Any]:
    deps.require_auth(request, write=True)
    return lite_app_storage.delete_mapping("photoprism", mapping_id)


@router.post("/catalog/install", status_code=202)
async def install_lite_catalog_item(payload: LiteCatalogInstallRequest, request: Request) -> dict[str, Any]:
    deps.require_auth(request, write=True)
    app_ref = (payload.app_id or "").strip()
    if not app_ref:
        raise HTTPException(status_code=400, detail="Choose an app to install.")
    params = {**payload.params}
    if payload.version:
        params["version"] = payload.version

    command = lite_catalog.install_command(
        app_ref,
        payload.target_node_id,
        requested_by=payload.requested_by,
        dry_run=payload.dry_run,
        params=params,
    )
    if command.get("already_installed"):
        return lite_catalog.already_installed_response(command)

    await ensure_worker_execution_ready()
    lite_catalog.record_install_queued(command)
    try:
        queued = await submit_domain_command(
            lite_catalog.COMMAND_SUBJECT,
            "lite.catalog.install.requested",
            command,
            trace_id=command["operation_id"],
        )
    except Exception:
        lite_catalog.discard_operation(command["operation_id"])
        raise
    queued.update(
        {
            "accepted": True,
            "status": "queued",
            "operation_id": command["operation_id"],
            "app_id": lite_catalog.PHOTOPRISM_APP_ID,
            "target_node_id": command["target_node_id"],
            "message": "PhotoPrism install started.",
        }
    )
    return queued


@router.post("/catalog/remove", status_code=501)
def remove_lite_catalog_item(payload: LiteCatalogRemoveRequest, request: Request) -> dict[str, Any]:
    deps.require_auth(request, write=True)
    # The uploaded source does not currently prove a remove_blueprint/remove_app typed operation.
    # Keep the endpoint explicit and friendly instead of pretending removal is implemented.
    return {
        "status": "not_implemented",
        "accepted": False,
        "summary": "Remove is not enabled yet because the lite operation contract has not been added.",
        "app_id": payload.app_id,
        "next_step": "Add and validate a remove_blueprint typed operation before enabling this action.",
    }


@router.get("/identity")
def get_lite_identity(request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    return lite_status.lite_identity()


@router.post("/identity/rotate", status_code=202)
async def rotate_lite_identity(payload: LiteIdentityRotateRequest, request: Request) -> dict[str, Any]:
    deps.require_auth(request, write=True)
    data: dict[str, Any] = {"target": payload.target}
    if payload.value is not None:
        data["value"] = payload.value
    if payload.lease_duration:
        data["lease_duration"] = payload.lease_duration
    return await submit_domain_command(
        "pocketlab.commands.vault.rotate",
        "vault.rotate.requested",
        data,
    )


@router.get("/security")
def get_lite_security(request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    state = lite_security.current_state()
    profiles = lite_app_profiles.app_security_profiles()
    lifecycle = lite_app_lifecycle.app_lifecycle_profiles()
    state["protected_apps"] = profiles.get("apps", [])
    state["app_security_profiles"] = profiles
    state["app_lifecycle_profiles"] = lifecycle
    return state


@router.post("/security/check", status_code=202)
async def check_lite_security(payload: LiteSecurityScanRequest, request: Request) -> dict[str, Any]:
    deps.require_auth(request, write=True)
    run_id = lite_security.new_run_id()
    command = {
        "run_id": run_id,
        "command_id": run_id,
        "scope": payload.scope or "local",
        "reason": payload.reason or "manual safety check",
        "requested_at": deps.now_utc_iso(),
    }
    # Record the queued state before publishing so a fast worker cannot complete
    # the scan and then have the API overwrite the completed state back to queued.
    lite_security.record_queued_run(command)
    try:
        queued = await submit_domain_command(
            lite_security.policy.COMMAND_SUBJECT,
            "lite.security.scan.requested",
            command,
        )
    except Exception:
        lite_security.discard_queued_run(run_id)
        raise
    queued.update(
        {
            "status": "queued",
            "accepted": True,
            "run_id": run_id,
            "command_subject": lite_security.policy.COMMAND_SUBJECT,
            "execution_mode": "worker",
            "summary": "Safety check queued. Pocket Lab will scan local security posture and dependency risks.",
        }
    )
    return queued


@router.post("/security/scan", status_code=202)
async def scan_lite_security(payload: LiteSecurityScanRequest, request: Request) -> dict[str, Any]:
    # Backward-compatible alias for older Lite UI builds. New UI calls /security/check.
    return await check_lite_security(payload, request)


@router.get("/security/runs/{run_id}")
def get_lite_security_run(run_id: str, request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    run = lite_security.read_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Security check run not found.")
    return run


@router.get("/security/evidence/{run_id}")
def get_lite_security_evidence(run_id: str, request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    payload = lite_security.read_evidence(run_id)
    if not payload:
        raise HTTPException(status_code=404, detail="Security evidence not found.")
    return payload


@router.get("/security/apps")
def get_lite_security_apps(request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    return lite_app_profiles.app_security_profiles()


@router.get("/security/apps/{app_id}")
def get_lite_security_app(app_id: str, request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    return lite_app_profiles.app_security_profile(app_id)


@router.post("/security/apps/{app_id}/check", status_code=501)
def check_lite_security_app(app_id: str, payload: LiteAppSecurityCheckRequest, request: Request) -> dict[str, Any]:
    deps.require_auth(request, write=True)
    return lite_app_profiles.app_security_check_not_implemented(app_id, reason=payload.reason)


@router.get("/fleet")
def get_lite_fleet(request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    return lite_status.lite_fleet()


@router.get("/fleet/invites/latest")
def get_latest_lite_fleet_invite(request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    invite = lite_invites.latest_invite()
    return {
        "status": "invite_ready" if invite else "not_found",
        "latest_invite": invite,
        "updated_at": deps.now_utc_iso(),
    }


@router.post("/fleet/add-device", status_code=202)
async def add_lite_device(payload: LiteAddDeviceRequest, request: Request) -> dict[str, Any]:
    deps.require_auth(request, write=True)
    try:
        device_name = _candidate_device_name(payload)
        device_conflict = fleet_registry.find_device_identity_conflict(device_name)
        invite_conflict = lite_invites.find_invite_identity_conflict(device_name)
        conflict = device_conflict or invite_conflict
        if conflict:
            raise HTTPException(status_code=409, detail=_duplicate_device_detail(conflict))

        result = lite_invites.create_lite_invite(
            role=payload.role,
            hostname=payload.hostname,
            request=request,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    await lite_invites.publish_invite_evidence(result)
    return {key: value for key, value in result.items() if key != "event"}


@router.post("/fleet/remove-device")
async def remove_lite_device(payload: LiteRemoveDeviceRequest, request: Request) -> dict[str, Any]:
    deps.require_auth(request, write=True)
    device_id = (payload.device_id or "").strip()
    if not device_id:
        raise HTTPException(status_code=400, detail="Choose a device to remove.")
    if not payload.confirm:
        raise HTTPException(status_code=400, detail="Confirm removal before removing a saved device record.")

    try:
        removal = fleet_registry.remove_device_records(device_id)
    except fleet_registry.DeviceRemovalError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    invite_cleanup = lite_invites.remove_invites_for_device(device_id, device=removal)
    removed_invites = int(invite_cleanup.get("removed_invite_records") or 0)
    requested_by = (payload.requested_by or "lite-api").strip() or "lite-api"
    evidence = fleet_registry.append_device_removed_evidence(
        removal,
        removed_invite_records=removed_invites,
        reason=payload.reason,
        requested_by=requested_by,
    )
    await fleet_registry.publish_device_removed_evidence(evidence)

    return {
        **removal,
        "removed_invite_records": removed_invites,
        "message": "Old device record removed.",
        "summary": "Old device record removed. The phone was not wiped and Pocket Lab was not uninstalled from that device.",
        "updated_at": deps.now_utc_iso(),
    }


@router.get("/policy")
def get_lite_policy(request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    return lite_status.lite_policy()


@router.post("/policy/apply", status_code=202)
async def apply_lite_policy(payload: LitePolicyApplyRequest, request: Request) -> dict[str, Any]:
    deps.require_auth(request, write=True)
    return await submit_domain_command(
        "pocketlab.commands.security.configure_opa",
        "security.configure_opa.requested",
        {"enforce_mode": payload.protection_enabled, "reason": payload.reason},
    )


@router.get("/recovery")
def get_lite_recovery(request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    state = lite_status.lite_recovery()
    profiles = lite_app_profiles.app_backup_profiles()
    lifecycle = lite_app_lifecycle.app_lifecycle_profiles()
    targets = lite_app_backup_targets.backup_targets()
    state["app_backups"] = profiles.get("apps", [])
    state["app_backup_profiles"] = profiles
    state["app_lifecycle_profiles"] = lifecycle
    state["backup_targets"] = targets.get("targets", [])
    state["backup_target_profiles"] = targets
    return state




@router.get("/recovery/backup-targets")
def get_lite_backup_targets(request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    return lite_app_backup_targets.backup_targets()


@router.get("/recovery/apps/{app_id}/backup-targets")
def get_lite_recovery_app_backup_targets(app_id: str, request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    return lite_app_backup_targets.app_backup_targets(app_id)


@router.post("/recovery/apps/{app_id}/backup-to-target", status_code=501)
def backup_lite_app_to_target(app_id: str, payload: LiteAppActionRequest, request: Request) -> dict[str, Any]:
    deps.require_auth(request, write=True)
    return lite_app_backup_targets.backup_to_storage_not_implemented(
        app_id,
        payload.target_device_id,
        reason=payload.reason,
    )

@router.get("/recovery/apps")
def get_lite_recovery_apps(request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    return lite_app_profiles.app_backup_profiles()


@router.get("/recovery/apps/{app_id}")
def get_lite_recovery_app(app_id: str, request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    return lite_app_profiles.app_backup_profile(app_id)


@router.post("/recovery/apps/{app_id}/backup", status_code=202)
async def backup_lite_app(app_id: str, payload: LiteAppBackupRequest, request: Request) -> dict[str, Any]:
    deps.require_auth(request, write=True)
    command = lite_app_profiles.app_backup_command(app_id, mode=payload.mode, reason=payload.reason)
    try:
        submitted = await submit_domain_command(
            lite_app_profiles.APP_BACKUP_SUBJECT,
            "lite.backup.app_queued",
            command,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "app_backup_queue_unavailable",
                "summary": "App backup request could not be queued because the local command bus is not reachable.",
                "detail": str(exc),
            },
        ) from exc
    pending = lite_backup.record_backup_request(command)
    submitted.update({
        "accepted": True,
        "status": submitted.get("status") or "queued",
        "app_id": "photoprism",
        "backup_id": command["backup_id"],
        "mode": command["app_backup_mode"],
        "pending_backup": pending,
        "summary": "PhotoPrism app backup queued. Config and app metadata are included; media remains excluded unless a supported media backup mode is enabled.",
    })
    return submitted


@router.post("/recovery/apps/{app_id}/restore/preview", status_code=501)
def preview_lite_app_restore(app_id: str, payload: LiteAppRestorePreviewRequest, request: Request) -> dict[str, Any]:
    deps.require_auth(request, write=True)
    return lite_app_profiles.app_restore_preview_not_implemented(app_id)


@router.post("/recovery/apps/{app_id}/restore", status_code=501)
def restore_lite_app(app_id: str, payload: LiteAppRestoreRequest, request: Request) -> dict[str, Any]:
    deps.require_auth(request, write=True)
    return lite_app_profiles.app_restore_not_implemented(app_id)


@router.post("/recovery/backup", status_code=202)
async def backup_lite(payload: LiteBackupRequest, request: Request) -> dict[str, Any]:
    deps.require_auth(request, write=True)
    command_id = uuid.uuid4().hex
    command = {
        "command_id": command_id,
        "include_event_journal": payload.include_event_journal,
        "include_app_data": payload.include_app_data,
        "reason": payload.reason or "manual backup",
        "dry_run": payload.dry_run,
        "requested_by": "lite-api",
    }
    try:
        submitted = await submit_domain_command(
            "pocketlab.commands.lite.backup.create",
            "lite.backup.queued",
            command,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "backup_queue_unavailable",
                "summary": "Backup request could not be queued because the local command bus is not reachable.",
                "detail": str(exc),
            },
        ) from exc
    pending = lite_backup.record_backup_request(command)
    submitted["backup_id"] = command_id
    submitted["pending_backup"] = pending
    submitted["summary"] = "Backup request queued. The encrypted repository will be initialized automatically if this is the first backup."
    return submitted


@router.get("/recovery/backups")
def list_lite_backups(request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    return lite_backup.list_backups()


@router.get("/recovery/backups/{backup_id}")
def get_lite_backup(backup_id: str, request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    backup = lite_backup.get_backup(backup_id)
    if not backup:
        raise HTTPException(
            status_code=404,
            detail={"status": "not_found", "summary": "Backup was not found."},
        )
    return backup


@router.get("/recovery/receipts/{backup_id}")
def get_lite_backup_receipt(backup_id: str, request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    receipt = lite_backup.get_receipt(backup_id)
    if not receipt:
        raise HTTPException(
            status_code=404,
            detail={"status": "not_found", "summary": "Backup receipt was not found."},
        )
    return receipt


@router.post("/recovery/backups/{backup_id}/verify", status_code=202)
async def verify_lite_backup(backup_id: str, payload: LiteBackupVerifyRequest, request: Request) -> dict[str, Any]:
    deps.require_auth(request, write=True)
    selected = backup_id or payload.backup_id or "latest"
    command_id = uuid.uuid4().hex
    submitted = await submit_domain_command(
        "pocketlab.commands.lite.backup.verify",
        "lite.backup.verify_queued",
        {
            "command_id": command_id,
            "backup_id": selected,
            "reason": payload.reason or "manual verification",
            "requested_by": "lite-api",
        },
    )
    submitted["backup_id"] = selected
    submitted["summary"] = "Backup verification queued. The worker will check the manifest, restic snapshot, and repository metadata."
    return submitted


@router.post("/recovery/restore/preview", status_code=202)
async def preview_lite_restore(payload: LiteRestorePreviewRequest, request: Request) -> dict[str, Any]:
    deps.require_auth(request, write=True)
    command_id = uuid.uuid4().hex
    selected = payload.backup_id or "latest"
    submitted = await submit_domain_command(
        "pocketlab.commands.lite.restore.preview",
        "lite.restore.preview_queued",
        {
            "command_id": command_id,
            "backup_id": selected,
            "reason": payload.reason or "manual restore preview",
            "requested_by": "lite-api",
        },
    )
    submitted["backup_id"] = selected
    submitted["summary"] = "Restore preview queued. The worker will inspect the verified backup without changing local state."
    return submitted


@router.get("/recovery/restore/previews/{preview_id}")
def get_lite_restore_preview(preview_id: str, request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    preview = lite_backup.get_restore_preview(preview_id)
    if not preview:
        raise HTTPException(
            status_code=404,
            detail={"status": "not_found", "summary": "Restore preview was not found."},
        )
    return preview


@router.get("/recovery/restore/checkpoints/{checkpoint_id}")
def get_lite_restore_checkpoint(checkpoint_id: str, request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    checkpoint = lite_backup.get_restore_checkpoint(checkpoint_id)
    if not checkpoint:
        raise HTTPException(
            status_code=404,
            detail={"status": "not_found", "summary": "Restore checkpoint was not found."},
        )
    return checkpoint


@router.get("/recovery/restore/runs/{restore_id}")
def get_lite_restore_run(restore_id: str, request: Request) -> dict[str, Any]:
    deps.require_auth(request)
    restore_run = lite_backup.get_restore_run(restore_id)
    if not restore_run:
        raise HTTPException(
            status_code=404,
            detail={"status": "not_found", "summary": "Restore run was not found."},
        )
    return restore_run


@router.post("/recovery/restore", status_code=202)
async def restore_lite(payload: LiteRestoreRequest, request: Request) -> dict[str, Any]:
    deps.require_auth(request, write=True)
    if not payload.confirm:
        raise HTTPException(
            status_code=409,
            detail={
                "status": "confirmation_required",
                "summary": "Restore can change local state. Confirm the restore before running it.",
            },
        )
    if not payload.preview_id:
        raise HTTPException(
            status_code=409,
            detail={
                "status": "preview_required",
                "summary": "Run Preview Restore and include the preview id before restoring.",
            },
        )
    if not payload.backup_id or payload.backup_id == "latest":
        raise HTTPException(
            status_code=409,
            detail={
                "status": "backup_required",
                "summary": "Restore requires the explicit backup id from the verified preview.",
            },
        )
    preview = lite_backup.get_restore_preview(payload.preview_id)
    if not preview:
        raise HTTPException(
            status_code=404,
            detail={"status": "preview_not_found", "summary": "Restore preview was not found."},
        )
    if preview.get("status") != "ready" or not preview.get("restore_allowed"):
        raise HTTPException(
            status_code=409,
            detail={
                "status": "preview_not_ready",
                "summary": "Create a verified Preview Restore before restoring.",
            },
        )
    command_id = uuid.uuid4().hex
    selected = payload.backup_id
    submitted = await submit_domain_command(
        "pocketlab.commands.lite.restore.apply",
        "lite.restore.apply_queued",
        {
            "command_id": command_id,
            "backup_id": selected,
            "preview_id": payload.preview_id,
            "confirm": True,
            "reason": "manual confirmed restore",
            "requested_by": "lite-api",
        },
    )
    submitted["backup_id"] = selected
    submitted["preview_id"] = payload.preview_id
    submitted["summary"] = "Restore queued. Pocket Lab will create a pre-restore checkpoint before changing Lite state."
    return submitted

