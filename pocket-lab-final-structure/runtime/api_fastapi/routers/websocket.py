from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .. import deps
from ..services.nats_bus import BUS

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/events")
async def events_socket(websocket: WebSocket):
    await websocket.accept()
    heartbeat_interval = 15
    try:
        await websocket.send_text(
            json.dumps(
                {
                    "type": "bus.status",
                    "time": deps.now_utc_iso(),
                    "data": BUS.status(),
                },
                ensure_ascii=False,
            )
        )
        last_heartbeat = asyncio.get_running_loop().time()
        async for event in BUS.subscribe_local(replay=25):
            await websocket.send_text(json.dumps(event, ensure_ascii=False))
            now = asyncio.get_running_loop().time()
            if now - last_heartbeat >= heartbeat_interval:
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "heartbeat",
                            "subject": "pocketlab.events.websocket.heartbeat",
                            "time": deps.now_utc_iso(),
                            "data": {
                                "health": deps.core.build_health_engine_snapshot().get(
                                    "status"
                                ),
                                "bus": BUS.status(),
                            },
                        },
                        ensure_ascii=False,
                    )
                )
                last_heartbeat = now
    except WebSocketDisconnect:
        return


@router.websocket("/ws/operations/{job_id}")
async def operation_socket(websocket: WebSocket, job_id: str):
    await websocket.accept()
    last_status = None
    try:
        while True:
            job = deps.operation_service().get(job_id)
            payload = {
                "type": "operation.snapshot",
                "subject": "pocketlab.events.operation.snapshot",
                "job_id": job_id,
                "job": job,
                "time": deps.now_utc_iso(),
                "data": {"job_id": job_id, "job": job},
            }
            await websocket.send_text(json.dumps(payload, ensure_ascii=False))
            status = job.get("status") if isinstance(job, dict) else None
            if status and status != last_status:
                await BUS.publish_json(
                    "pocketlab.events.operation.status",
                    "operation.status",
                    {
                        "job_id": job_id,
                        "status": status,
                        "operation": (
                            job.get("operation") if isinstance(job, dict) else None
                        ),
                    },
                )
            last_status = status
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        return
