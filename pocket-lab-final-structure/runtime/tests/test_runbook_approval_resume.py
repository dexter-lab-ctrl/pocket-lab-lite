# ruff: noqa: E402
from __future__ import annotations

from pathlib import Path
from typing import Any
import sys
import asyncio

RUNTIME_DIR = Path(__file__).resolve().parents[1]
CORE_DIR = RUNTIME_DIR / "core"

for path in (str(RUNTIME_DIR), str(CORE_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from runbooks.engine import RunbookEngine
from runbooks.registry import RunbookRegistry
from runbooks.store import RunbookExecutionStore


class FakeOperationService:
    def __init__(self) -> None:
        self.submitted: list[str] = []

    def submit_queued(self, request: Any) -> dict[str, Any]:
        job_id = f"job-{len(self.submitted) + 1}"
        self.submitted.append(job_id)
        return {"job_id": job_id, "operation": request.operation}

    def run_existing(self, job_id: str) -> dict[str, Any]:
        return {"job_id": job_id, "status": "succeeded", "exit_code": 0}


async def collect(
    events: list[tuple[str, str, dict[str, Any]]],
    subject: str,
    event_type: str,
    data: dict[str, Any],
) -> None:
    events.append((subject, event_type, data))


def test_runbook_approval_resume_executes_pending_steps(tmp_path: Path) -> None:
    async def run_test() -> None:
        runbooks_dir = tmp_path / "runbooks"
        runbooks_dir.mkdir()

        (runbooks_dir / "approval_resume.yaml").write_text(
            """
    apiVersion: pocketlab.io/v1alpha1
    kind: Runbook
    metadata:
      name: approval_resume
      title: Approval Resume
    spec:
      requiresApproval: true
      severity: high
      policy:
        minimumRole: operator
        evidenceRequired: true
        approvalReason: test approval
      steps:
        - name: first
          operation: health_check
          timeoutSeconds: 30
          requiresApproval: false
        - name: second
          operation: backup_verify
          timeoutSeconds: 30
          requiresApproval: false
    """,
            encoding="utf-8",
        )

        events: list[tuple[str, str, dict[str, Any]]] = []
        store = RunbookExecutionStore(tmp_path / "state")
        operation_service = FakeOperationService()

        engine = RunbookEngine(
            registry=RunbookRegistry(runbooks_dir),
            store=store,
            operation_service=operation_service,
            emit=lambda subject, event_type, data: collect(events, subject, event_type, data),
        )

        started = await engine.execute(
            {
                "execution_id": "exec-1",
                "runbook": "approval_resume",
                "dry_run": True,
                "requested_by": "pytest",
            }
        )

        assert started["status"] == "approval_required"
        assert operation_service.submitted == []

        store.update("exec-1", status="approved", approved=True, approved_by="pytest")

        resumed = await engine.resume("exec-1")

        assert resumed["status"] == "succeeded"
        assert operation_service.submitted == ["job-1", "job-2"]
        event_types = [event_type for _, event_type, _ in events]
        assert "runbook.approval_required" in event_types
        assert "runbook.resumed" in event_types
        assert "runbook.step_started" in event_types
        assert "runbook.step_succeeded" in event_types
        assert "runbook.succeeded" in event_types

    asyncio.run(run_test())
