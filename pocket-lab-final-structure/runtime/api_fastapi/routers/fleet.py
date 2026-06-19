from __future__ import annotations

import html
import json
import os
from fastapi import APIRouter, HTTPException, Request, Response

from .. import deps
from ..services.action_queue import submit_domain_command
from ..services.live_status import LIVE_STATUS
from ..services.nats_bus import BUS
from ..services import fleet_registry, lite_invites

router = APIRouter(tags=["fleet"])


def _normalize_nats_url(value: str | None) -> str:
    value = str(value or "").strip()
    if not value:
        return ""
    if "://" not in value:
        return f"nats://{value}"
    return value


def _is_local_invite_host(host: str | None) -> bool:
    normalized = str(host or "").strip().lower().strip("[]")
    return normalized in {"", "localhost", "127.0.0.1", "0.0.0.0", "::1", "testserver"}


def _request_hostname(request: Request | None) -> str:
    if request is None:
        return ""
    try:
        host = str(request.url.hostname or "").strip()
    except Exception:
        host = ""
    if host:
        return host.strip("[]")

    # Defensive fallback for deployments where the public host is only present
    # in proxy headers. Keep parsing conservative to avoid accepting arbitrary
    # comma-separated values beyond the first hop.
    forwarded = str(
        request.headers.get("x-forwarded-host")
        or request.headers.get("host")
        or ""
    ).split(",", 1)[0].strip()
    if forwarded.startswith("[") and "]" in forwarded:
        return forwarded[1:forwarded.index("]")]
    if ":" in forwarded:
        return forwarded.rsplit(":", 1)[0].strip("[]")
    return forwarded.strip("[]")


def _autodetected_public_host() -> str:
    for helper_name in ("_tailscale_ipv4", "_lan_ipv4"):
        helper = getattr(lite_invites, helper_name, None)
        if callable(helper):
            try:
                value = str(helper() or "").strip()
            except Exception:
                value = ""
            if value and not _is_local_invite_host(value):
                return value
    return ""


def _public_nats_url_for_invite(request: Request | None, internal_url: str | None) -> str:
    """Return the NATS URL a joining Lite device should use.

    Priority order:
    1. Explicit public NATS URL override for locked-down deployments.
    2. Hostname/IP used to fetch the invite/bootstrap script, with NATS port.
    3. Tailscale/LAN autodetection when the API request is local/testserver.
    4. Internal/local NATS URL fallback.

    This keeps the server's internal control-plane URL private while allowing a
    secondary phone to heartbeat over the same Tailscale address it used to fetch
    the bootstrap script.
    """
    for env_name in (
        "POCKETLAB_LITE_PUBLIC_NATS_URL",
        "POCKETLAB_PUBLIC_NATS_URL",
        "POCKETLAB_LITE_NATS_URL",
    ):
        configured = _normalize_nats_url(os.environ.get(env_name))
        if configured:
            return configured

    port = str(
        os.environ.get("POCKETLAB_LITE_NATS_PORT")
        or os.environ.get("POCKETLAB_PUBLIC_NATS_PORT")
        or "4222"
    ).strip() or "4222"

    host = _request_hostname(request)
    if _is_local_invite_host(host):
        host = _autodetected_public_host()

    if host and not _is_local_invite_host(host):
        return f"nats://{host}:{port}"

    return _normalize_nats_url(internal_url) or "nats://127.0.0.1:4222"


def _is_browser_join_request(request: Request | None) -> bool:
    if request is None:
        return False
    accept = str(request.headers.get("accept") or "").lower()
    user_agent = str(request.headers.get("user-agent") or "").lower()
    if any(tool in user_agent for tool in ("curl", "wget", "httpie", "python-requests")):
        return False
    return "text/html" in accept or "mozilla" in user_agent or "android" in user_agent


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




@router.get("/api/lite/fleet/agent/bootstrap.sh")
def lite_fleet_agent_bootstrap_script(
    role: str = "compute",
    token: str = "",
    request: Request = None,
):
    """Lite-friendly token-gated device bootstrap script.

    This route intentionally lives in the fleet router so it is loaded with the
    existing fleet/join runtime. Browser-safe invite cards can point users to a
    friendly link, while Termux/curl consumes this shell endpoint.
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
    node_name = cfg["hostname"]
    agent_token = cfg["agent_token"]
    agent_token_hash = cfg["agent_token_hash"]

    internal_nats_url = cfg.get("nats_url") or os.environ.get("POCKETLAB_NATS_URL", "nats://127.0.0.1:4222")
    nats_url = _public_nats_url_for_invite(request, internal_nats_url)
    nats_user = os.environ.get(
        "POCKETLAB_AGENT_NATS_USER",
        os.environ.get("POCKETLAB_NATS_AGENT_USER", "pocketlab_agent"),
    )
    nats_password = os.environ.get(
        "POCKETLAB_AGENT_NATS_PASSWORD",
        os.environ.get("POCKETLAB_NATS_AGENT_PASSWORD", ""),
    )

    fleet_registry.upsert_agent(
        {
            "node_id": node_id,
            "hostname": node_name,
            "name": node_name,
            "role": role,
            "status": "joining",
            "agent_status": "joining",
            "auth_token_hash": agent_token_hash,
            "capabilities": consumed.get("capabilities") or ["pending-agent"],
            "accepted_at": deps.now_utc_iso(),
        },
        event_type="fleet.agent_join_started",
    )

    env_lines = [
        f"export POCKETLAB_NODE_ROLE={json.dumps(role)}",
        f"export POCKETLAB_NODE_ID={json.dumps(node_id)}",
        f"export POCKETLAB_NODE_NAME={json.dumps(node_name)}",
        f"export POCKETLAB_AGENT_TOKEN={json.dumps(agent_token)}",
        f"export POCKETLAB_NATS_URL={json.dumps(nats_url)}",
        f"export POCKETLAB_NATS_USER={json.dumps(nats_user)}",
        f"export POCKETLAB_NATS_PASSWORD={json.dumps(nats_password)}",
    ]
    env_body = "\n".join(env_lines)

    bash_script = f"""#!/usr/bin/env bash
set -Eeuo pipefail

echo "== Pocket Lab Lite device bootstrap =="
echo "Device name: {node_name}"
echo "Device role: {role}"
echo "Node id: {node_id}"
echo ""

mkdir -p "$HOME/.config/pocket-lab-lite"

cat > "$HOME/.pocketlab-lite-agent.env" <<'EOF_ENV'
{env_body}
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

@router.get("/api/join.sh")
def join_script(role: str = "compute", token: str = "", request: Request = None):
    """Shell-consumable Lite device invite.

    Browser access is treated as a preview/instruction flow and does not consume
    the invite. Curl/Termux access consumes the invite, marks the device as
    joining, and returns a non-empty shell script with stable node identity.
    """
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
        return _join_invite_html(
            status=status,
            invite=invite,
            role=role,
            token=token,
            request=request,
        )

    if status == "expired":
        raise HTTPException(status_code=410, detail="Invite token has expired")
    if status == "used":
        raise HTTPException(status_code=410, detail="Invite token has already been used")
    if status != "valid":
        raise HTTPException(status_code=403, detail=f"Invite token is invalid: {status}")

    consumed = lite_invites.consume_invite_token(token, role=role)
    if consumed is None:
        raise HTTPException(status_code=410, detail="Invite token is no longer available")

    role = str(consumed.get("role") or role)
    node_id = str(consumed.get("node_id") or "")
    hostname = str(consumed.get("hostname") or node_id or "Pocket Lab Device")

    # Ensure the UI immediately moves from Invite sent / waiting to Joining.
    fleet_registry.upsert_agent(
        {
            "node_id": node_id,
            "name": hostname,
            "hostname": hostname,
            "role": role,
            "status": "joining",
            "agent_status": "joining",
            "accepted_at": deps.now_utc_iso(),
            "capabilities": consumed.get("capabilities") or [],
            "auth_token_hash": str(consumed.get("token_hash") or "")[:16],
        },
        event_type="fleet.agent_join_started",
    )

    internal_nats_url = BUS.servers[0] if BUS.servers else "nats://127.0.0.1:4222"
    nats_url = _public_nats_url_for_invite(request, internal_nats_url)
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

echo "== Pocket Lab Lite device join =="
echo "Device name: {hostname}"
echo "Device role: {role}"
echo ""
echo "This invite has been accepted by the Pocket Lab Lite server."
echo "The device will show as Joining until a Pocket Lab node agent heartbeat is received."

export POCKETLAB_NODE_ROLE={json.dumps(role)}
export POCKETLAB_NODE_ID={json.dumps(node_id)}
export POCKETLAB_NODE_NAME={json.dumps(hostname)}
export POCKETLAB_AGENT_TOKEN={json.dumps(token)}
export POCKETLAB_NATS_URL={json.dumps(nats_url)}
export POCKETLAB_NATS_USER={json.dumps(nats_user)}
export POCKETLAB_NATS_PASSWORD={json.dumps(nats_password)}

if ! python3 - <<'PYCHECK' >/dev/null 2>&1
import importlib.util, sys
sys.exit(0 if importlib.util.find_spec("nats") else 1)
PYCHECK
then
  python3 -m pip install --user 'nats-py>=2.7.2'
fi

cat > "$HOME/.pocketlab-lite-agent.env" <<EOF_ENV
export POCKETLAB_NODE_ROLE={role}
export POCKETLAB_NODE_ID={node_id}
export POCKETLAB_NODE_NAME={hostname}
export POCKETLAB_AGENT_TOKEN={token}
export POCKETLAB_NATS_URL={nats_url}
export POCKETLAB_NATS_USER={nats_user}
export POCKETLAB_NATS_PASSWORD={nats_password}
EOF_ENV

echo ""
echo "Saved agent environment to:"
echo "  $HOME/.pocketlab-lite-agent.env"
echo ""
echo "Next step on this device:"
echo "  source $HOME/.pocketlab-lite-agent.env"
echo "  python3 pocketlab_node_agent.py"
echo ""
echo "If this device has the Pocket Lab Lite repo cloned, run:"
echo "  cd $HOME/pocket-lab-lite/pocket-lab-final-structure/runtime"
echo "  source $HOME/.pocketlab-lite-agent.env"
echo "  python3 agents/pocketlab_node_agent.py"
echo ""
"""

    if not bash_script.strip():
        raise HTTPException(status_code=500, detail="Join script generation produced an empty response")

    return Response(
        content=bash_script,
        media_type="text/x-shellscript; charset=utf-8",
    )
