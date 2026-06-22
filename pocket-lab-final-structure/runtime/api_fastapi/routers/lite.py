from __future__ import annotations

import json
import os
import uuid

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from .. import deps
from ..schemas.operations import OperationRequest
from ..services.action_queue import submit_domain_command, submit_operation_command
from ..services import fleet_registry, lite_backup, lite_invites, lite_status

router = APIRouter(prefix="/api/lite", tags=["lite"])


class LiteCatalogInstallRequest(BaseModel):
    app_id: str = Field(default="", description="Catalog app or blueprint id")
    version: str | None = None
    dry_run: bool = False
    requested_by: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)


class LiteCatalogRemoveRequest(BaseModel):
    app_id: str = Field(default="", description="Catalog app or blueprint id")
    confirm: bool = False
    requested_by: str | None = None


class LiteIdentityRotateRequest(BaseModel):
    target: str = "default"
    value: str | None = None
    lease_duration: str | None = None


class LiteSecurityScanRequest(BaseModel):
    scope: str = "local"


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
    return lite_status.lite_catalog()


@router.post("/catalog/install", status_code=202)
async def install_lite_catalog_item(payload: LiteCatalogInstallRequest, request: Request) -> dict[str, Any]:
    deps.require_auth(request, write=True)
    app_ref = (payload.app_id or "").strip()
    if not app_ref:
        raise HTTPException(status_code=400, detail="Choose an app to install.")
    params = {**payload.params, "app_id": app_ref}
    if payload.version:
        params["version"] = payload.version
    if payload.requested_by:
        params["requested_by"] = payload.requested_by
    op, raw = _operation_payload(
        "deploy_blueprint",
        {"type": "catalog", "ref": app_ref},
        params,
        dry_run=payload.dry_run,
    )
    return await submit_operation_command(op, raw)


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
    return lite_status.lite_security()


@router.post("/security/scan", status_code=202)
async def scan_lite_security(payload: LiteSecurityScanRequest, request: Request) -> dict[str, Any]:
    deps.require_auth(request, write=True)
    return await submit_domain_command(
        "pocketlab.commands.security.scan",
        "security.scan.requested",
        {"scope": payload.scope},
    )


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
    return lite_status.lite_recovery()


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


@router.post("/recovery/restore", status_code=501)
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
    raise HTTPException(
        status_code=501,
        detail={
            "status": "restore_not_implemented",
            "summary": "Restore is protected and will be enabled after backup creation, verification, and restore preview are validated.",
            "required_next_steps": ["Verify Backup", "Preview Restore", "Confirm Restore"],
        },
    )

