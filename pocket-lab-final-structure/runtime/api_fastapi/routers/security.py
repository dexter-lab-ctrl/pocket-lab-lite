from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Request, Response

from .. import deps
from ..services.nats_bus import BUS

router = APIRouter(tags=["security"])


@router.get("/api/opa_evaluations.json")
def opa_evaluations(background_tasks: BackgroundTasks, request: Request) -> list[dict]:
    deps.require_auth(request)
    evaluations = deps.core.build_opa_evaluations()
    background_tasks.add_task(
        BUS.publish_json,
        "pocketlab.events.security.evaluated",
        "security.evaluated",
        {"count": len(evaluations)},
    )
    return evaluations


@router.get("/api/opa_interceptor.py")
def opa_interceptor(request: Request):
    deps.require_auth(request)
    return Response(
        "# Pocket Lab OPA interceptor\nprint('OPA interceptor placeholder')\n",
        media_type="text/x-python; charset=utf-8",
    )


@router.get("/api/logs/query")
@router.get("/loki/api/v1/query")
@router.get("/api/v1/query")
def loki_query(
    background_tasks: BackgroundTasks,
    request: Request,
    query: str = "",
    limit: int = 20,
) -> dict:
    deps.require_auth(request)
    safe_limit = max(1, min(100, int(limit or 20)))
    result = deps.core.search_loki(query, limit=safe_limit)
    background_tasks.add_task(
        BUS.publish_json,
        "pocketlab.events.security.log_query",
        "security.log_query",
        {
            "query": query,
            "limit": safe_limit,
            "matches": (
                len(result.get("data", {}).get("result", []))
                if isinstance(result, dict)
                else 0
            ),
        },
    )
    return result


@router.post("/api/security/scan", status_code=202)
async def security_scan(request: Request) -> dict:
    deps.require_auth(request, write=True)
    from ..services.action_queue import submit_domain_command

    return await submit_domain_command(
        "pocketlab.commands.security.scan",
        "security.scan.requested",
        {},
    )
