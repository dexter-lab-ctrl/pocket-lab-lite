from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest

from pocket_lab_test_utils import client, ensure_runtime_path, isolated_state_dir

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "scripts/dev/lib/long_gate_group4.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("long_gate_group4_storage", TOOL)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def isolate_state(tmp_path: Path):
    ensure_runtime_path()
    from api_fastapi import deps

    state = isolated_state_dir(tmp_path)
    deps.core.SETTINGS = deps.core.Settings(state_dir=state)
    yield state


def test_safe_allocation_cap_preserves_floor_reserve_and_absolute_cap():
    tool = load_tool()
    mib = 1024 * 1024
    assert tool.safe_allocation_cap(
        free_bytes=500 * mib,
        requested_bytes=400 * mib,
        floor_bytes=128 * mib,
        reserve_bytes=16 * mib,
        maximum_bytes=64 * mib,
    ) == 64 * mib
    assert tool.safe_allocation_cap(
        free_bytes=140 * mib,
        requested_bytes=64 * mib,
        floor_bytes=128 * mib,
        reserve_bytes=16 * mib,
        maximum_bytes=64 * mib,
    ) == 0


def test_run_owned_path_rejects_shared_and_photoprism_paths(tmp_path: Path):
    tool = load_tool()
    run = tmp_path / "run"
    assert tool._safe_run_owned(run / "tmp" / "allocation.bin", run)
    assert not tool._safe_run_owned(Path("/storage/emulated/0/allocation.bin"), run)
    assert not tool._safe_run_owned(run / "photoprism" / "originals" / "allocation.bin", run)
    assert not tool._safe_run_owned(run / "photoprism" / "import" / "allocation.bin", run)


def test_security_submission_rejects_before_reservation_when_storage_is_unsafe(monkeypatch: pytest.MonkeyPatch):
    from api_fastapi.routers import lite as lite_router

    monkeypatch.setattr(
        lite_router.lite_storage_guard,
        "storage_readiness",
        lambda request=None: {
            "ready": False,
            "reason": "insufficient_storage",
            "free_bytes": 10,
            "free_percent": 0.1,
            "minimum_free_bytes": 100,
            "minimum_free_percent": 3.0,
            "sanitized": True,
        },
    )
    monkeypatch.setattr(
        lite_router.lite_security,
        "new_run_id",
        lambda: pytest.fail("run identity must not be created before storage rejection"),
    )
    response = client().post("/api/lite/security/check", json={"profile": "quick"})
    assert response.status_code == 507
    payload = response.json()
    assert payload["accepted"] is False
    assert payload["reason"] == "insufficient_storage"
    assert payload["sanitized"] is True
    assert "/data/" not in response.text


def test_deterministic_failpoint_suite_runs_only_in_isolated_state(tmp_path: Path):
    tool = load_tool()
    run = tmp_path / "pocketlab-long-gates-deterministic-test"
    state = tmp_path / "production-state-placeholder"
    state.mkdir()
    ctx = tool.g2.Context(
        repo_root=ROOT,
        run_dir=run,
        run_id="pocketlab-long-gates-deterministic-test",
        gate_id="low-storage",
        state_dir=state,
        db_path=state / "pocketlab-lite.sqlite3",
        proxy_base_url="http://127.0.0.1:9",
        direct_base_url="http://127.0.0.1:9",
        connect_timeout=0.1,
        http_timeout=0.1,
        report_limit_bytes=32 * 1024 * 1024,
        resume=False,
    )
    ctx.gate_dir.mkdir(parents=True)
    result = tool._run_deterministic_failpoints(ctx)
    assert result["failpoints_completed"] == 7
    assert result["failpoints_passed"] == 7
    assert result["false_accepts"] == 0
    assert result["false_successes"] == 0
    assert result["active_key_leaks"] == 0
    assert result["zero_byte_authoritative_files"] == 0
    assert result["partial_outputs"] == 0
    assert result["isolated_quick_check"] == "ok"
    assert not ctx.db_path.exists(), "production placeholder database must not be touched"
