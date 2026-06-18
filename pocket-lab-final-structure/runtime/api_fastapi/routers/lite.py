from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from .. import deps
from ..schemas.operations import OperationRequest
from ..services.action_queue import submit_domain_command, submit_operation_command
from ..services import lite_invites, lite_status

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


class LitePolicyApplyRequest(BaseModel):
    protection_enabled: bool = False
    reason: str | None = None


class LiteBackupRequest(BaseModel):
    include_event_journal: bool = True
    dry_run: bool = False


class LiteRestoreRequest(BaseModel):
    backup_ref: str = "latest"
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
        result = lite_invites.create_lite_invite(
            role=payload.role,
            hostname=payload.hostname,
            request=request,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    await lite_invites.publish_invite_evidence(result)
    return {key: value for key, value in result.items() if key != "event"}


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
    op, raw = _operation_payload(
        "backup_now",
        {"type": "state", "ref": "default"},
        {"include_event_journal": payload.include_event_journal},
        dry_run=payload.dry_run,
    )
    return await submit_operation_command(op, raw)


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
    op, raw = _operation_payload(
        "restore_backup",
        {"type": "backup", "ref": payload.backup_ref},
        {"backup_ref": payload.backup_ref, "confirmed": True},
        dry_run=payload.dry_run,
    )
    return await submit_operation_command(op, raw)
