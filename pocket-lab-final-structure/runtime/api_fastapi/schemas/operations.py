from __future__ import annotations

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class OperationTarget(BaseModel):
    type: str = "default"
    ref: str = "default"


class OperationRequest(BaseModel):
    operation: str = Field(default="", description="Typed Pocket Lab operation name")
    target: Dict[str, Any] = Field(default_factory=dict)
    params: Dict[str, Any] = Field(default_factory=dict)
    dry_run: bool = False
    source: Optional[str] = None
