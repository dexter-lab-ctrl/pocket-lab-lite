from __future__ import annotations

import importlib.util
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts/dev/lite/run-coordinated-runtime-qualification.py"
TASKS = ROOT / "tasks/Taskfile.lite.yml"


def _runner_module():
    spec = importlib.util.spec_from_file_location("pocketlab_coordinated_runtime_test", RUNNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def test_coordinated_runtime_binds_supervisor_nats_probe_to_isolated_port():
    source = RUNNER.read_text(encoding="utf-8")
    assert '"POCKETLAB_NATS_PORT": str(ports["nats"])' in source
    assert '"POCKETLAB_LITE_NATS_PORT": str(ports["nats"])' in source


def test_coordinated_runtime_binds_supervisor_lifecycle_lock_to_run_root():
    source = RUNNER.read_text(encoding="utf-8")
    assert '"POCKETLAB_START_DASHBOARD_LOCK": str(root / "locks" / "start-dashboard.sh.lock")' in source


def test_coordinated_runtime_reconcile_cadence_allows_stable_observations():
    source = RUNNER.read_text(encoding="utf-8")
    assert '"POCKETLAB_RUNTIME_RECONCILE_SECONDS": "20"' in source


def test_qualification_candidate_packages_exact_installable_source_profile(tmp_path: Path):
    runner = _runner_module()
    commit = runner._git(ROOT, "rev-parse", "HEAD")
    assets = tmp_path / "assets"
    assets.mkdir()
    declaration = runner._package_coordinated_source(
        repo=ROOT,
        source=ROOT,
        commit=commit,
        assets=assets,
    )
    assert declaration is not None
    assert declaration["profile"] == "runtime-install-v1"
    archive = assets / declaration["artifact"]
    assert declaration["sha256"] == runner._sha256(archive)
    with zipfile.ZipFile(archive) as bundle:
        names = set(bundle.namelist())
    assert "pocket-lab-final-structure/runtime/runtime-dependencies.json" in names
    assert all(not name.startswith((".git/", "docs/", ".pocketlab-dev/")) for name in names)
