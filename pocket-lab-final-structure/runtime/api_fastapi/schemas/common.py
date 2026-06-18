from __future__ import annotations

from pydantic import BaseModel, Field


class TargetsRequest(BaseModel):
    targets: list[str] | str | None = Field(default_factory=list)


class TailscaleConfigRequest(BaseModel):
    api_key: str


class FleetJoinRequest(BaseModel):
    role: str = "compute"
    hostname: str | None = None
