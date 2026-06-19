from __future__ import annotations

import html
import os
from fastapi import APIRouter, HTTPException, Request, Response

from .. import deps
from ..services.action_queue import submit_domain_command
from ..services.live_status import LIVE_STATUS
from ..services.nats_bus import BUS
from ..services import fleet_registry, lite_invites

router = APIRouter(tags=["fleet"])


def _is_browser_join_request(request: Request | None) -> bool:
    if request is None:
        return False
    accept = str(request.headers.get("accept") or "").lower()
    user_agent = str(request.headers.get("user-agent") or "").lower()
    if any(tool in user_agent for tool in ("curl", "wget", "httpie", "python-requests")):
        return False
    return "text/html" in accept


def _join_invite_html(
    *,
    status: str,
    invite: dict | None,
    role: str,
    token: str,
    request: Request | None,
) -> Response:
    safe_role = html.escape(str((invite or {}).get("role_label") or role or "Device"))
    safe_hostname = html.escape(str((invite or {}).get("hostname") or "this device"))
    safe_status = html.escape(status.replace("_", " ").title())

    invite_url = str(request.url) if request is not None else ""
    safe_command = html.escape(f'curl -fsSL "{invite_url}" | bash')

    if status == "valid":
        title = "Pocket Lab Lite invite ready"
        message = (
            "This invite is ready. To join this phone, open Termux on this device "
            "and run the command below."
        )
        detail = f"Role: {safe_role}. Device name: {safe_hostname}."
        command_html = f"<pre><code>{safe_command}</code></pre>"
    elif status == "used":
        title = "Invite already used"
        message = "This invite has already been accepted and cannot be used again."
        detail = "Create a new invite from the Pocket Lab Lite Devices tab if you need to join another device."
        command_html = ""
    elif status == "expired":
        title = "Invite expired"
        message = "This invite has expired."
        detail = "Create a fresh invite from the Pocket Lab Lite Devices tab."
        command_html = ""
    else:
        title = "Invite unavailable"
        message = f"This invite cannot be used. Status: {safe_status}."
        detail = "Check that the link is complete or create a new invite."
        command_html = ""

    body = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(title)}</title>
  <style>
    body {{
      margin: 0;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f8fafc;
      color: #0f172a;
    }}
    main {{
      max-width: 720px;
      margin: 0 auto;
      padding: 32px 20px;
    }}
    .card {{
      background: white;
      border: 1px solid #e2e8f0;
      border-radius: 20px;
      box-shadow: 0 20px 50px rgba(15, 23, 42, 0.08);
      padding: 28px;
    }}
    h1 {{
      margin-top: 0;
      font-size: 1.7rem;
    }}
    p {{
      line-height: 1.6;
    }}
    pre {{
      overflow-x: auto;
      background: #0f172a;
      color: #e2e8f0;
      border-radius: 14px;
      padding: 16px;
      white-space: pre-wrap;
      word-break: break-word;
    }}
    .note {{
      margin-top: 20px;
      padding: 14px;
      border-radius: 14px;
      background: #eff6ff;
      color: #1e3a8a;
    }}
  </style>
</head>
<body>
  <main>
    <section class="card">
      <h1>{html.escape(title)}</h1>
      <p>{message}</p>
      <p>{detail}</p>
      {command_html}
      <div class="note">
        Keep this phone on the same Pocket Lab private network or Tailnet while joining.
      </div>
    </section>
  </main>
</body>
</html>"""
    code = 200 if status == "valid" else 410 if status in {"used", "expired"} else 400
    return Response(content=body, media_type="text/html; charset=utf-8", status_code=code)


@router.get("/api/config/tailscale.json")
def tailscale_config(request: Request) -> dict:
    deps.require_auth(request)
    return {"configured": bool(deps.core.get_tailscale_api_key())}


@router.get("/api/fleet.json")
def fleet(request: Request) -> list[dict]:
    deps.require_auth(request)
    return fleet_registry.merged_fleet_nodes()


@router.get("/api/fleet/agents")
def fleet_agents(request: Request, include_stale: bool = True) -> dict:
    deps.require_auth(request)
    return {
        "status": "ok",
        "agents": fleet_registry.list_agents(include_stale=include_stale),
        "ttl_seconds": fleet_registry.AGENT_TTL_SECONDS,
        "updated_at": deps.now_utc_iso(),
    }


@router.get("/api/fleet/agents/{node_id}")
def fleet_agent(node_id: str, request: Request) -> dict:
    deps.require_auth(request)
    agent = fleet_registry.get_agent(node_id)
    if not agent:
        raise HTTPException(
            status_code=404,
            detail={"error": "Fleet agent not found", "node_id": node_id},
        )
    return {
        "status": "ok",
        "agent": agent,
        "commands": fleet_registry.list_commands(node_id=node_id, limit=25),
    }


@router.get("/api/fleet/agents/{node_id}/commands")
def fleet_agent_commands(node_id: str, request: Request, limit: int = 100) -> dict:
    deps.require_auth(request)
    return {
        "status": "ok",
        "node_id": fleet_registry.normalize_node_id(node_id),
        "commands": fleet_registry.list_commands(node_id=node_id, limit=limit),
    }


@router.post("/api/fleet/agents/{node_id}/commands", status_code=202)
async def send_fleet_agent_command(
    node_id: str, payload: dict | None = None, request: Request = None
) -> dict:
    deps.require_auth(request, write=True)
    payload = payload or {}
    command = str(payload.get("command") or payload.get("action") or "health.check")
    command_payload = (
        payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
    )
    node_id = fleet_registry.normalize_node_id(node_id)
    item = fleet_registry.create_node_command(
        node_id, command, command_payload, requested_by="api"
    )
    subject = f"pocketlab.commands.node.{node_id}.{command.replace('_', '.')}"
    await BUS.publish_json(
        subject,
        "fleet.node_command_requested",
        {**item, "command_subject": subject},
        trace_id=item["command_id"],
    )
    await BUS.publish_json(
        "pocketlab.events.fleet.node_command_queued",
        "fleet.node_command_queued",
        {"node_id": node_id, "command_id": item["command_id"], "command": command},
        trace_id=item["command_id"],
    )
    return {
        "accepted": True,
        "status": "queued",
        "node_id": node_id,
        "command": item,
        "command_subject": subject,
        "bus": BUS.status(),
    }


@router.post("/api/fleet/agents/broadcast", status_code=202)
async def broadcast_fleet_agent_command(
    payload: dict | None = None, request: Request = None
) -> dict:
    deps.require_auth(request, write=True)
    payload = payload or {}
    command = str(payload.get("command") or payload.get("action") or "health.check")
    command_payload = (
        payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
    )
    item = fleet_registry.create_node_command(
        "all", command, command_payload, requested_by="api"
    )
    subject = f"pocketlab.commands.node.all.{command.replace('_', '.')}"
    await BUS.publish_json(
        subject,
        "fleet.node_broadcast_requested",
        {**item, "command_subject": subject},
        trace_id=item["command_id"],
    )
    await BUS.publish_json(
        "pocketlab.events.fleet.node_command_queued",
        "fleet.node_command_queued",
        {"node_id": "all", "command_id": item["command_id"], "command": command},
        trace_id=item["command_id"],
    )
    return {
        "accepted": True,
        "status": "queued",
        "command": item,
        "command_subject": subject,
        "bus": BUS.status(),
    }


@router.get("/api/fleet/agent/bootstrap")
def fleet_agent_bootstrap(
    role: str = "compute", hostname: str = "", request: Request = None
) -> dict:
    deps.require_auth(request)
    cfg = fleet_registry.bootstrap_config(role=role, hostname=hostname or None)
    # Store only the hash so the control plane can correlate agents without retaining a raw enrollment token.
    fleet_registry.upsert_agent(
        {
            "node_id": cfg["node_id"],
            "hostname": cfg["hostname"],
            "role": role,
            "status": "invited",
            "auth_token_hash": cfg["agent_token_hash"],
            "capabilities": ["pending-agent"],
        },
        event_type="fleet.agent_invited",
    )
    return {"status": "created", "agent": cfg}


@router.get("/api/fleet/health.json")
async def fleet_health(request: Request) -> dict:
    deps.require_auth(request)
    # Keep the live sampler side-effect/event path, then return the richer agent-aware snapshot.
    try:
        await LIVE_STATUS.sample_fleet(source="api-read")
    except Exception:
        pass
    return fleet_registry.fleet_health_snapshot()


@router.get("/api/fleet/nodes/{node_id}/health")
def fleet_node_health(node_id: str, request: Request) -> dict:
    deps.require_auth(request)
    agent = fleet_registry.get_agent(node_id)
    if agent:
        status = (
            "healthy"
            if str(agent.get("status")).lower() == "active"
            else str(agent.get("status") or "unavailable")
        )
        return {
            "status": status,
            "node": agent,
            "healthy": status == "healthy" or status == "active",
            "last_checked_at": deps.now_utc_iso(),
        }
    nodes = fleet_registry.merged_fleet_nodes()
    found = next(
        (
            n
            for n in nodes
            if str(n.get("id") or "").lower() == node_id.lower()
            or str(n.get("name") or "").lower() == node_id.lower()
        ),
        None,
    )
    if not found:
        raise HTTPException(
            status_code=404,
            detail={
                "status": "unavailable",
                "node": node_id,
                "message": "Node not found",
            },
        )
    node_status = (
        "healthy" if str(found.get("status")).lower() == "active" else "unavailable"
    )
    return {
        "status": node_status,
        "node": found,
        "healthy": node_status == "healthy",
        "last_checked_at": deps.now_utc_iso(),
    }


@router.post("/api/fleet/join", status_code=202)
async def create_fleet_join(
    payload: dict | None = None, request: Request = None
) -> dict:
    deps.require_auth(request, write=True)
    payload = payload or {}
    role = str(payload.get("role") or "compute")
    hostname = payload.get("hostname")
    return await submit_domain_command(
        "pocketlab.commands.fleet.join",
        "fleet.join.requested",
        {"role": role, "hostname": hostname},
    )


@router.get("/api/join.sh")
def join_script(role: str = "compute", token: str = "", request: Request = None):
    # Public like the legacy endpoint, but requires the invite token.
    if not deps.settings().enable_join_script:
        raise HTTPException(
            status_code=403, detail="Join script generation is disabled"
        )
    role = (role or "compute").strip() or "compute"
    token = (token or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="Missing token")
    status, invite = lite_invites.invite_token_status(token, role=role)

    if _is_browser_join_request(request):
        return _join_invite_html(status=status, invite=invite, role=role, token=token, request=request)

    if status == "expired":
        raise HTTPException(status_code=410, detail="Invite token has expired")
    if status == "used":
        raise HTTPException(status_code=410, detail="Invite token has already been used")
    if status != "valid":
        raise HTTPException(status_code=403, detail="Invite token is invalid")

    consumed = lite_invites.consume_invite_token(token, role=role)
    if consumed is None:
        raise HTTPException(status_code=410, detail="Invite token is no longer available")
    role = consumed.get("role") or role
    nats_url = BUS.servers[0] if BUS.servers else "nats://127.0.0.1:4222"
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
echo "== Pocket Lab zero-touch provisioning =="
echo "Target role: {role}"
export POCKETLAB_NODE_ROLE="{role}"
export POCKETLAB_AGENT_TOKEN="{token}"
export POCKETLAB_NATS_URL="{nats_url}"
export POCKETLAB_NATS_USER="{nats_user}"
export POCKETLAB_NATS_PASSWORD="{nats_password}"
if ! python3 - <<'PYCHECK' >/dev/null 2>&1
import importlib.util, sys
sys.exit(0 if importlib.util.find_spec("nats") else 1)
PYCHECK
then
  python3 -m pip install --user 'nats-py>=2.7.2'
fi
echo "Start the Pocket Lab node agent with:"
echo "  python3 pocketlab_node_agent.py"
echo "Join request registered."
"""
    return Response(content=bash_script, media_type="text/x-shellscript; charset=utf-8")
