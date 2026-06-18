from __future__ import annotations

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class EventEnvelope(BaseModel):
    type: str = Field(..., description="Event type, for example operation.created")
    subject: str = Field(..., description="NATS subject used for this event")
    id: str = Field(..., description="Unique event id")
    time: str = Field(..., description="UTC event timestamp")
    source: str = Field(default="pocketlab.fastapi", description="Event producer")
    data: Dict[str, Any] = Field(default_factory=dict)
    trace_id: Optional[str] = None


class PublishEventRequest(BaseModel):
    subject: str = Field(default="pocketlab.events.manual")
    type: str = Field(default="manual")
    data: Dict[str, Any] = Field(default_factory=dict)
    trace_id: Optional[str] = None
