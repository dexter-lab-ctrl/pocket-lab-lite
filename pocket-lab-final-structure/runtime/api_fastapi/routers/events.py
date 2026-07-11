from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Request

from .. import deps
from ..schemas.events import PublishEventRequest
from ..services.nats_bus import BUS

router = APIRouter(tags=["events"])


@router.get("/api/events/status")
@router.get("/api/nats/status")
def event_bus_status(request: Request) -> dict:
    deps.require_auth(request)
    return BUS.status()


@router.get("/api/events/recent")
def recent_events(request: Request, limit: int = 100, subject_prefix: str = "") -> dict:
    deps.require_auth(request)
    return {"events": BUS.recent(limit=limit, subject_prefix=subject_prefix)}


@router.post("/api/events/publish", status_code=202)
def publish_event(
    payload: PublishEventRequest, background_tasks: BackgroundTasks, request: Request
) -> dict:
    deps.require_auth(request, write=True)
    event = BUS.envelope(
        payload.subject, payload.type, payload.data, trace_id=payload.trace_id
    )
    background_tasks.add_task(
        BUS.publish_json,
        payload.subject,
        payload.type,
        payload.data,
        trace_id=payload.trace_id,
    )
    return {"status": "queued", "event": event, "bus": BUS.status()}


@router.get("/api/reliability/status")
def reliability_status(request: Request) -> dict:
    deps.require_auth(request)
    from ..services.reliability import reliability_status as build_status

    return {"bus": BUS.status(), **build_status()}


@router.get("/api/reliability/dead-letters")
def reliability_dead_letters(request: Request, limit: int = 100) -> dict:
    deps.require_auth(request)
    from ..services.reliability import recent_dead_letters

    return {"dead_letters": recent_dead_letters(limit=limit), "bus": BUS.status()}


@router.post("/api/reliability/dead-letters/{dead_letter_id}/replay", status_code=202)
async def reliability_replay_dead_letter(dead_letter_id: str, request: Request) -> dict:
    deps.require_auth(request, write=True)
    from ..services.reliability import replay_dead_letter

    result = await replay_dead_letter(dead_letter_id)
    return {**result, "bus": BUS.status()}


@router.post("/api/reliability/recover", status_code=202)
async def reliability_recover(request: Request, limit: int = 25) -> dict:
    deps.require_auth(request, write=True)
    from ..services.reliability import recover_queued_operations

    result = await recover_queued_operations(limit=limit)
    return {**result, "bus": BUS.status()}


@router.get("/api/live-status/status")
def live_status(request: Request) -> dict:
    deps.require_auth(request)
    from ..services.live_status import LIVE_STATUS

    return LIVE_STATUS.status()


@router.post("/api/live-status/sample")
async def live_status_sample(request: Request) -> dict:
    deps.require_auth(request, write=True)
    from ..services.live_status import LIVE_STATUS

    sample = await LIVE_STATUS.sample_all(source="manual")
    return {"status": "sampled", "sample": sample, "live_status": LIVE_STATUS.status()}


@router.post("/api/live-status/restart")
async def live_status_restart(request: Request) -> dict:
    deps.require_auth(request, write=True)
    from ..services.live_status import LIVE_STATUS

    await LIVE_STATUS.restart()
    return {"status": "restarted", "live_status": LIVE_STATUS.status()}


@router.get("/api/workers/status")
def worker_status(request: Request) -> dict:
    deps.require_auth(request)
    heartbeats = BUS.recent(
        limit=20, subject_prefix="pocketlab.events.worker.heartbeat"
    )
    started = BUS.recent(limit=20, subject_prefix="pocketlab.events.worker.started")
    errors = BUS.recent(limit=20, subject_prefix="pocketlab.events.worker.error")
    from ..services.domain_commands import supported_subjects
    from ..services.fleet_registry import list_agents

    agents = list_agents(include_stale=True)
    return {
        "status": "ok",
        "bus": {
            key: value
            for key, value in BUS.status().items()
            if key in {
                "mode", "connected", "jetstream_enabled",
                "fallback_reason", "reconnect_pending", "watchdog_running",
            }
        },
        "workers_seen": len(
            {
                (event.get("data") or {}).get("worker")
                for event in heartbeats + started
                if (event.get("data") or {}).get("worker")
            }
        ),
        "fleet_agents_seen": len(agents),
        "fleet_agents_online": len([agent for agent in agents if agent.get("online")]),
        "command_subject": "pocketlab.commands.>",
        "node_command_subjects": [
            "pocketlab.commands.node.<node_id>.>",
            "pocketlab.commands.node.all.>",
        ],
        "supported_domain_commands": supported_subjects(),
        "reliability": __import__(
            "api_fastapi.services.reliability", fromlist=["reliability_status"]
        ).reliability_status(),
        "recent_heartbeats": heartbeats,
        "recent_starts": started,
        "recent_errors": errors,
    }
