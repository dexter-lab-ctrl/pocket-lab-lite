from __future__ import annotations

import json
import os

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from .. import deps
from ..schemas.operations import OperationRequest
from ..services.action_queue import submit_domain_command, submit_operation_command
from ..services import lite_invites, fleet_registry, lite_status

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


@router.get("/api/lite/fleet/agent/bootstrap.sh")
def lite_fleet_agent_bootstrap_script(
    role: str = "compute",
    token: str = "",
    request: Request = None,
):
    """Token-gated Lite agent bootstrap script.

    This reuses the full Pocket Lab fleet bootstrap model:
    - validate/consume invite token
    - create stable node bootstrap config
    - mark device as joining
    - write a local env file on the second Termux device
    - start the node agent automatically when the Lite repo exists
    """
    role = (role or "compute").strip() or "compute"
    token = (token or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="Missing invite token")

    status, invite = lite_invites.invite_token_status(token, role=role)
    if status == "expired":
        raise HTTPException(status_code=410, detail="Invite token has expired")
    if status == "used":
        raise HTTPException(status_code=410, detail="Invite token has already been used")
    if status != "valid":
        raise HTTPException(status_code=403, detail=f"Invite token is invalid: {status}")

    consumed = lite_invites.consume_invite_token(token, role=role)
    if consumed is None:
        raise HTTPException(status_code=410, detail="Invite token is no longer available")

    hostname = str(consumed.get("hostname") or consumed.get("node_id") or "pocket-lite-device")
    role = str(consumed.get("role") or role)

    cfg = fleet_registry.bootstrap_config(role=role, hostname=hostname)
    node_id = cfg["node_id"]

    fleet_registry.upsert_agent(
        {
            "node_id": node_id,
            "hostname": cfg["hostname"],
            "name": cfg["hostname"],
            "role": role,
            "status": "joining",
            "agent_status": "joining",
            "auth_token_hash": cfg["agent_token_hash"],
            "capabilities": consumed.get("capabilities") or ["pending-agent"],
            "accepted_at": deps.now_utc_iso(),
        },
        event_type="fleet.agent_join_started",
    )

    nats_url = cfg.get("nats_url") or os.environ.get("POCKETLAB_NATS_URL", "nats://127.0.0.1:4222")
    nats_user = os.environ.get(
        "POCKETLAB_AGENT_NATS_USER",
        os.environ.get("POCKETLAB_NATS_AGENT_USER", "pocketlab_agent"),
    )
    nats_password = os.environ.get(
        "POCKETLAB_AGENT_NATS_PASSWORD",
        os.environ.get("POCKETLAB_NATS_AGENT_PASSWORD", ""),
    )

    bash_script = f"""#!/usr/bin/env bash
set -Eeuo pipefail

echo "== Pocket Lab Lite device bootstrap =="
echo "Device name: {cfg["hostname"]}"
echo "Device role: {role}"
echo "Node id: {node_id}"
echo ""

export POCKETLAB_NODE_ROLE={json.dumps(role)}
export POCKETLAB_NODE_ID={json.dumps(node_id)}
export POCKETLAB_NODE_NAME={json.dumps(cfg["hostname"])}
export POCKETLAB_AGENT_TOKEN={json.dumps(cfg["agent_token"])}
export POCKETLAB_NATS_URL={json.dumps(nats_url)}
export POCKETLAB_NATS_USER={json.dumps(nats_user)}
export POCKETLAB_NATS_PASSWORD={json.dumps(nats_password)}

mkdir -p "$HOME/.config/pocket-lab-lite"

cat > "$HOME/.pocketlab-lite-agent.env" <<EOF_ENV
export POCKETLAB_NODE_ROLE={role}
export POCKETLAB_NODE_ID={node_id}
export POCKETLAB_NODE_NAME={cfg["hostname"]}
export POCKETLAB_AGENT_TOKEN={cfg["agent_token"]}
export POCKETLAB_NATS_URL={nats_url}
export POCKETLAB_NATS_USER={nats_user}
export POCKETLAB_NATS_PASSWORD={nats_password}
EOF_ENV

echo "Saved agent environment:"
echo "  $HOME/.pocketlab-lite-agent.env"

if ! python3 - <<'PYCHECK' >/dev/null 2>&1
import importlib.util, sys
sys.exit(0 if importlib.util.find_spec("nats") else 1)
PYCHECK
then
  python3 -m pip install --user 'nats-py>=2.7.2'
fi

AGENT_FILE="$HOME/pocket-lab-lite/pocket-lab-final-structure/runtime/agents/pocketlab_node_agent.py"

if [ -f "$AGENT_FILE" ]; then
  echo "Starting Pocket Lab Lite node agent..."
  if command -v pm2 >/dev/null 2>&1; then
    pm2 delete "pocketlab-agent-{node_id}" >/dev/null 2>&1 || true
    pm2 start python3 --name "pocketlab-agent-{node_id}" -- "$AGENT_FILE"
    pm2 save >/dev/null 2>&1 || true
    echo "Node agent started with PM2: pocketlab-agent-{node_id}"
  else
    nohup python3 "$AGENT_FILE" > "$HOME/pocketlab-agent-{node_id}.log" 2>&1 &
    echo "Node agent started in background."
  fi
else
  echo ""
  echo "Pocket Lab Lite repo was not found on this device."
  echo "To finish setup, clone the Lite repo on this device, then run:"
  echo "  cd $HOME/pocket-lab-lite/pocket-lab-final-structure/runtime"
  echo "  source $HOME/.pocketlab-lite-agent.env"
  echo "  python3 agents/pocketlab_node_agent.py"
fi

echo ""
echo "Join accepted. This device should show as Joining, then Online after heartbeat."
"""

    if not bash_script.strip():
        raise HTTPException(status_code=500, detail="Generated bootstrap script is empty")

    return Response(content=bash_script, media_type="text/x-shellscript; charset=utf-8")

