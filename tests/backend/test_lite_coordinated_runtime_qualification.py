from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts/dev/lite/run-coordinated-runtime-qualification.py"
TASKS = ROOT / "tasks/Taskfile.lite.yml"


def test_coordinated_runtime_runner_is_exact_sha_and_fail_closed():
    source = RUNNER.read_text(encoding="utf-8")
    assert "candidate checkout is not clean" in source
    assert "candidate checkout does not match requested SHA" in source
    assert "human_owner_authorization_required" in source
    assert '"production_execution": False' in source
    assert "physical_android" in source
    assert "POCKETLAB_TEST_AUTH_BYPASS" in source
    assert "POCKETLAB_QUALIFICATION_PM2_ALLOW_SERVICES" in source


def test_coordinated_runtime_task_is_repository_owned():
    tasks = TASKS.read_text(encoding="utf-8")
    assert "lite:lifecycle:runtime:preflight:" in tasks
    assert "run-coordinated-runtime-qualification.py" in tasks
    assert "CANDIDATE_SHA" in tasks
