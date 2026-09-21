from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = (
    ROOT
    / "pocket-lab-final-structure"
    / "pocket-lab-bootstrap-production-scripts-patched"
    / "scripts"
)
COMMON = SCRIPTS / "lib" / "common.sh"
DASHBOARD = SCRIPTS / "start-dashboard.sh"
OPA = SCRIPTS / "lite" / "start-opa-runtime.sh"
PHOTOPRISM = SCRIPTS / "lite" / "install-photoprism-proot.sh"
FLEET_ROUTER = ROOT / "pocket-lab-final-structure" / "runtime" / "api_fastapi" / "routers" / "fleet.py"
AGENT_SUPERVISOR = ROOT / "pocket-lab-final-structure" / "runtime" / "agents" / "pocketlab_agent_supervisor.py"
RUNTIME_RECONCILER = ROOT / "pocket-lab-final-structure" / "runtime" / "supervisors" / "pocketlab_runtime_reconciler.py"
GUARDIAN = SCRIPTS / "lite" / "runtime-guardian.sh"


def _run_common(tmp_path: Path, body: str, **extra: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(
        {
            "POCKET_LAB_ALLOW_NON_TERMUX": "1",
            "HOME": str(tmp_path / "home"),
            "PREFIX": str(tmp_path / "prefix"),
            "COMMON_PATH": str(COMMON),
            **extra,
        }
    )
    return subprocess.run(
        ["bash", "-lc", f'source "$COMMON_PATH"\n{body}'],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_source_version_is_repo_version_plus_exact_source_digest(tmp_path: Path):
    package_version = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))["version"]
    digest = hashlib.sha256(COMMON.read_bytes()).hexdigest()[:12]
    result = _run_common(tmp_path, 'pocketlab_source_version "$COMMON_PATH"')
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().endswith(f"{package_version}+sha.{digest}")


def test_pm2_version_manifest_is_adjacent_to_projected_executable(tmp_path: Path):
    shell = shutil.which("sh")
    assert shell
    result = _run_common(
        tmp_path,
        'pm2_prepare_versioned_exec demo-service "9.8.7+build.42" "$SOURCE_EXEC"',
        SOURCE_EXEC=shell,
    )
    assert result.returncode == 0, result.stderr
    projected = Path(result.stdout.strip().splitlines()[-1])
    assert projected.is_symlink()
    assert projected.resolve() == Path(shell).resolve()
    manifest = json.loads((projected.parent / "package.json").read_text(encoding="utf-8"))
    assert manifest["version"] == "9.8.7+build.42"
    assert manifest["name"] == "pocketlab-pm2-demo-service"


def test_core_lite_pm2_services_all_supply_exact_versions():
    source = DASHBOARD.read_text(encoding="utf-8")
    expected = {
        "pocket-telemetry": "pocketlab_source_version",
        "pocket-nats": "nats_installed_version",
        "pocket-worker": "pocketlab_source_version",
        "pocket-node-agent": "pocketlab_source_version",
        "pocket-api": "pocketlab_source_version",
        "caddy-proxy": "caddy_installed_version",
        "pocketlab-core-supervisor": "pocketlab_source_version",
        "pocketlab-runtime-reconciler": "pocketlab_source_version",
    }
    for process_name, resolver in expected.items():
        matching = [
            line
            for line in source.splitlines()
            if f"pm2_runtime_process {process_name}" in line
        ]
        assert matching, process_name
        assert all("POCKETLAB_PM2_SERVICE_VERSION=" in line for line in matching), process_name
        assert any(resolver in line for line in matching), process_name


def test_opa_and_photoprism_use_versioned_pm2_projection():
    opa = OPA.read_text(encoding="utf-8")
    photoprism = PHOTOPRISM.read_text(encoding="utf-8")
    assert "opa_installed_version" in opa
    assert "pm2_ensure_versioned_process pocket-opa" in opa
    assert "photoprism_pm2_version" in photoprism
    assert 'pm2_ensure_versioned_process "$PROCESS_NAME" "$version"' in photoprism


def test_joined_device_agent_and_supervisor_use_versioned_pm2_projection():
    fleet = FLEET_ROUTER.read_text(encoding="utf-8")
    supervisor = AGENT_SUPERVISOR.read_text(encoding="utf-8")
    assert 'pm2_ensure_versioned_process "pocketlab-agent-$POCKETLAB_NODE_ID"' in fleet
    assert 'pm2_ensure_versioned_process "pocketlab-agent-supervisor-$POCKETLAB_NODE_ID"' in fleet
    assert "_prepare_versioned_python_exec" in supervisor
    assert "agent_version_drift" in supervisor


def test_runtime_reconciler_and_guardian_treat_version_metadata_as_desired_state():
    reconciler = RUNTIME_RECONCILER.read_text(encoding="utf-8")
    guardian = GUARDIAN.read_text(encoding="utf-8")
    assert "pm2_version_projection" in reconciler
    assert "POCKETLAB_SERVICE_VERSION" in reconciler
    assert "pm2_version_projection:" in reconciler
    assert "POCKETLAB_SERVICE_VERSION" in guardian
    assert "runtime_reconciler_missing_or_version_drift" in guardian
