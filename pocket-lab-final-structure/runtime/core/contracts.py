from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import re


def utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def slugify(value: str, default: str = "item") -> str:
    value = re.sub(r"[^a-zA-Z0-9._-]+", "-", (value or "").strip().lower()).strip("-_.")
    return value or default


@dataclass
class OperationTarget:
    type: str = "repo"
    ref: str = ""


@dataclass
class OperationRequest:
    operation: str
    target: OperationTarget = field(default_factory=OperationTarget)
    params: Dict[str, Any] = field(default_factory=dict)
    dry_run: bool = False
    source: Optional[Dict[str, Any]] = None


@dataclass
class OperationEvent:
    timestamp: str
    level: str
    message: str
    stream: str = "stdout"
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OperationResult:
    job_id: str
    operation: str
    status: str
    target: Dict[str, Any]
    params: Dict[str, Any]
    created_at: str
    updated_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    exit_code: Optional[int] = None
    stdout: str = ""
    stderr: str = ""
    events: list[dict[str, Any]] = field(default_factory=list)
    artifacts: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    def asdict(self) -> Dict[str, Any]:
        return asdict(self)


def result_from_dict(payload: Dict[str, Any]) -> OperationResult:
    return OperationResult(
        job_id=payload.get("job_id", ""),
        operation=payload.get("operation", ""),
        status=payload.get("status", "unknown"),
        target=payload.get("target") or {},
        params=payload.get("params") or {},
        created_at=payload.get("created_at", utc_now_iso()),
        updated_at=payload.get("updated_at", utc_now_iso()),
        started_at=payload.get("started_at"),
        finished_at=payload.get("finished_at"),
        exit_code=payload.get("exit_code"),
        stdout=payload.get("stdout", ""),
        stderr=payload.get("stderr", ""),
        events=list(payload.get("events") or []),
        artifacts=dict(payload.get("artifacts") or {}),
        error=payload.get("error"),
    )
