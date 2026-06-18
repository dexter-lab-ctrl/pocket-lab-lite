# ruff: noqa: E402
from __future__ import annotations

import asyncio
from pathlib import Path
import sys

import yaml

from pocket_lab_test_utils import REPO_ROOT

RUNTIME_DIR = REPO_ROOT / "pocket-lab-final-structure" / "runtime"
CORE_DIR = RUNTIME_DIR / "core"
for value in (str(RUNTIME_DIR), str(CORE_DIR)):
    if value not in sys.path:
        sys.path.insert(0, value)

from runbooks.engine import RunbookEngine
from runbooks.registry import RunbookRegistry
from runbooks.store import RunbookExecutionStore


class FakeOperationService:
    def __init__(self) -> None:
        self.submitted: list[str] = []

    def submit_queued(self, request):
        job_id = f"op-{len(self.submitted) + 1}"
        self.submitted.append(request.operation)
        return {"job_id": job_id, "operation": request.operation, "task_id": request.operation}

    def run_existing(self, job_id: str):
        return {"job_id": job_id, "status": "succeeded", "exit_code": 0}


async def _emit(subject: str, event_type: str, data: dict):
    return None


def test_runbook_registry_loads_metadata(tmp_path: Path):
    runbook_dir = tmp_path / "runbooks"
    runbook_dir.mkdir()
    (runbook_dir / "sample.yaml").write_text(
        yaml.safe_dump(
            {
                "apiVersion": "pocketlab.io/v1alpha1",
                "kind": "Runbook",
                "metadata": {"name": "sample", "title": "Sample"},
                "spec": {
                    "severity": "low",
                    "steps": [{"name": "check", "operation": "health_check"}],
                },
            }
        ),
        encoding="utf-8",
    )

    registry = RunbookRegistry(runbook_dir)
    runbook = registry.get("sample")

    assert runbook is not None
    assert runbook.name == "sample"
    assert runbook.steps[0].operation == "health_check"


def test_runbook_engine_requires_approval(tmp_path: Path):
    runbook_dir = tmp_path / "runbooks"
    runbook_dir.mkdir()
    (runbook_dir / "sample.yaml").write_text(
        yaml.safe_dump(
            {
                "apiVersion": "pocketlab.io/v1alpha1",
                "kind": "Runbook",
                "metadata": {"name": "sample", "title": "Sample"},
                "spec": {
                    "severity": "high",
                    "requiresApproval": True,
                    "policy": {
                        "minimumRole": "platform_admin",
                        "approvalReason": "test",
                        "evidenceRequired": True,
                    },
                    "steps": [{"name": "check", "operation": "health_check"}],
                },
            }
        ),
        encoding="utf-8",
    )

    engine = RunbookEngine(
        registry=RunbookRegistry(runbook_dir),
        store=RunbookExecutionStore(tmp_path / "state"),
        operation_service=FakeOperationService(),
        emit=_emit,
    )

    result = asyncio.run(engine.execute({"runbook": "sample", "execution_id": "rb-1"}))

    assert result["status"] == "approval_required"


def test_runbook_engine_executes_typed_operation_steps(tmp_path: Path):
    runbook_dir = tmp_path / "runbooks"
    runbook_dir.mkdir()
    (runbook_dir / "sample.yaml").write_text(
        yaml.safe_dump(
            {
                "apiVersion": "pocketlab.io/v1alpha1",
                "kind": "Runbook",
                "metadata": {"name": "sample", "title": "Sample"},
                "spec": {
                    "severity": "low",
                    "steps": [
                        {"name": "check", "operation": "health_check"},
                        {"name": "scan", "operation": "security_scan"},
                    ],
                },
            }
        ),
        encoding="utf-8",
    )

    fake = FakeOperationService()
    engine = RunbookEngine(
        registry=RunbookRegistry(runbook_dir),
        store=RunbookExecutionStore(tmp_path / "state"),
        operation_service=fake,
        emit=_emit,
    )

    result = asyncio.run(engine.execute({"runbook": "sample", "execution_id": "rb-2"}))

    assert result["status"] == "succeeded"
    assert fake.submitted == ["health_check", "security_scan"]
