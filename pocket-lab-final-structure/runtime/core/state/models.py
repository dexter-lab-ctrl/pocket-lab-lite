from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional


@dataclass
class RunnerEvent:
    timestamp: str
    level: str
    message: str
    stream: str = "stdout"
    data: Dict[str, Any] = field(default_factory=dict)

    def asdict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OperationRun:
    job_id: str
    operation: str
    task_id: str
    status: str
    target: Dict[str, Any]
    params: Dict[str, Any]
    dry_run: bool
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
    runner_events: list[dict[str, Any]] = field(default_factory=list)

    def asdict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_mapping(cls, payload: Dict[str, Any]) -> "OperationRun":
        return cls(
            job_id=str(payload.get("job_id", "")),
            operation=str(payload.get("operation", "")),
            task_id=str(
                payload.get("task_id")
                or payload.get("task")
                or payload.get("operation")
                or ""
            ),
            status=str(payload.get("status", "unknown")),
            target=dict(payload.get("target") or {}),
            params=dict(payload.get("params") or {}),
            dry_run=bool(payload.get("dry_run", False)),
            created_at=str(payload.get("created_at", "")),
            updated_at=str(payload.get("updated_at", "")),
            started_at=payload.get("started_at"),
            finished_at=payload.get("finished_at"),
            exit_code=payload.get("exit_code"),
            stdout=str(payload.get("stdout", "")),
            stderr=str(payload.get("stderr", "")),
            events=list(payload.get("events") or []),
            artifacts=dict(payload.get("artifacts") or {}),
            error=payload.get("error"),
            runner_events=list(
                payload.get("runner_events") or payload.get("events") or []
            ),
        )


@dataclass
class ArtifactVersion:
    ref: str
    name: str
    version: str
    digest: str
    source: str
    created_at: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def asdict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SourceProvenance:
    ref: str
    kind: str
    path: str
    digest: str
    fetched_at: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def asdict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RepoSnapshot:
    ref: str
    branch: str
    commit: Dict[str, Any]
    dirty: bool
    captured_at: str

    def asdict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BlueprintDigest:
    ref: str
    digest: str
    source: str
    created_at: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def asdict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DriftSnapshot:
    job_id: str
    summary: Dict[str, Any]
    metrics: Dict[str, Any]
    created_at: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def asdict(self) -> Dict[str, Any]:
        return asdict(self)
