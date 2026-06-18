from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


TERMINAL_RUNBOOK_STATUSES = {
    "approval_required",
    "succeeded",
    "failed",
    "cancelled",
    "rejected",
}


@dataclass(frozen=True)
class RunbookStep:
    name: str
    operation: str
    target: dict[str, Any] = field(default_factory=dict)
    params: dict[str, Any] = field(default_factory=dict)
    requires_approval: bool = False
    timeout_seconds: int | None = None


@dataclass(frozen=True)
class RunbookDefinition:
    name: str
    title: str
    source_file: str
    spec: dict[str, Any]
    steps: list[RunbookStep]
    requires_approval: bool = False
    severity: str = "medium"

    def as_public_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "title": self.title,
            "source_file": self.source_file,
            "severity": self.severity,
            "requiresApproval": self.requires_approval,
            "steps": [
                {
                    "name": step.name,
                    "operation": step.operation,
                    "target": step.target,
                    "params": step.params,
                    "requiresApproval": step.requires_approval,
                    "timeoutSeconds": step.timeout_seconds,
                }
                for step in self.steps
            ],
            "spec": self.spec,
        }
