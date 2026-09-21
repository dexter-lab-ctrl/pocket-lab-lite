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


def test_stale_pm2_version_projection_forces_controlled_recreation(tmp_path: Path):
    actions = tmp_path / "actions.log"
    state = tmp_path / "present"
    state.write_text("1", encoding="utf-8")
    shell = r"""
set -Eeuo pipefail
export POCKET_LAB_ALLOW_NON_TERMUX=1
export HOME="$TEST_HOME"
export PREFIX="$TEST_PREFIX"
source "$COMMON_PATH"

pm2() {
  case "${1:-}" in
    jlist)
      if [[ -f "$STATE_FILE" ]]; then
        printf '%s\n' '[{"name":"caddy-proxy","pm2_env":{"status":"online","version":"N/A","POCKETLAB_SERVICE_VERSION":"1.0.0+sha.wrong","POCKETLAB_PROCESS_SPEC_HASH":"old"}}]'
      else
        printf '%s\n' '[]'
      fi
      ;;
    delete)
      printf 'delete\n' >>"$ACTION_FILE"
      rm -f "$STATE_FILE"
      ;;
    start)
      printf 'start\n' >>"$ACTION_FILE"
      ;;
    *)
      return 0
      ;;
  esac
}

pm2_ensure_versioned_process caddy-proxy "2.10.2" "$SOURCE_EXEC" -- run --config /tmp/Caddyfile
"""
    env = os.environ.copy()
    env.update(
        {
            "POCKET_LAB_ALLOW_NON_TERMUX": "1",
            "TEST_HOME": str(tmp_path / "home"),
            "TEST_PREFIX": str(tmp_path / "prefix"),
            "COMMON_PATH": str(COMMON),
            "SOURCE_EXEC": shutil.which("sh") or "/bin/sh",
            "ACTION_FILE": str(actions),
            "STATE_FILE": str(state),
        }
    )
    completed = subprocess.run(
        ["bash", "-lc", shell],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    assert actions.read_text(encoding="utf-8").splitlines() == ["delete", "start"]


def test_caddy_config_fallback_restart_preserves_projected_service_version():
    source = DASHBOARD.read_text(encoding="utf-8")
    start = source.index("reload_caddy_if_config_changed(){")
    end = source.index("start_pm2_daemons(){", start)
    block = source[start:end]
    assert "pm2 restart caddy-proxy" in block
    assert "pm2 restart caddy-proxy --update-env" not in block


def test_invalid_service_version_never_returns_fatal_log_on_stdout(tmp_path: Path):
    result = _run_common(
        tmp_path,
        'pm2_normalize_service_version ""',
    )
    assert result.returncode != 0
    assert "[FATAL]" not in result.stdout
    assert result.stdout == ""


def test_fatal_helper_writes_stderr_not_stdout(tmp_path: Path):
    result = _run_common(
        tmp_path,
        'die "version probe failed"',
    )
    assert result.returncode != 0
    assert result.stdout == ""
    assert "version probe failed" in result.stderr
    assert "[FATAL]" in result.stderr


def test_caddy_version_resolver_extracts_semver_from_combined_output(tmp_path: Path):
    dashboard = DASHBOARD.read_text(encoding="utf-8")
    start = dashboard.index("caddy_installed_version(){")
    end = dashboard.index("reload_caddy_if_config_changed(){", start)
    resolver = dashboard[start:end]
    shell = f"""
set -Eeuo pipefail
export POCKET_LAB_ALLOW_NON_TERMUX=1
export HOME="$TEST_HOME"
export PREFIX="$TEST_PREFIX"
source "$COMMON_PATH"
{resolver}
caddy() {{
  if [[ "${{1:-}}" == "version" ]]; then
    printf 'warning: termux build metadata follows\\n' >&2
    printf 'v2.10.2 h1:testhash\\n' >&2
    return 0
  fi
  return 1
}}
caddy_installed_version
"""
    env = os.environ.copy()
    env.update(
        {
            "TEST_HOME": str(tmp_path / "home"),
            "TEST_PREFIX": str(tmp_path / "prefix"),
            "COMMON_PATH": str(COMMON),
        }
    )
    result = subprocess.run(
        ["bash", "-lc", shell],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "2.10.2"


def test_opa_version_resolver_extracts_version_from_combined_output(tmp_path: Path):
    source = OPA.read_text(encoding="utf-8")
    start = source.index("opa_installed_version() {")
    end = source.index("start_opa_process() {", start)
    resolver = source[start:end]
    shell = f"""
set -Eeuo pipefail
export POCKET_LAB_ALLOW_NON_TERMUX=1
export HOME="$TEST_HOME"
export PREFIX="$TEST_PREFIX"
source "$COMMON_PATH"
{resolver}
opa() {{
  if [[ "${{1:-}}" == "version" ]]; then
    printf 'Version: 1.19.0\\nBuild Commit: test\\n' >&2
    return 0
  fi
  return 1
}}
opa_installed_version
"""
    env = os.environ.copy()
    env.update(
        {
            "TEST_HOME": str(tmp_path / "home"),
            "TEST_PREFIX": str(tmp_path / "prefix"),
            "COMMON_PATH": str(COMMON),
        }
    )
    result = subprocess.run(
        ["bash", "-lc", shell],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "1.19.0"


def test_caddy_version_resolver_falls_back_to_termux_package_metadata(tmp_path: Path):
    dashboard = DASHBOARD.read_text(encoding="utf-8")
    start = dashboard.index("caddy_installed_version(){")
    end = dashboard.index("reload_caddy_if_config_changed(){", start)
    resolver = dashboard[start:end]
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True)
    dpkg_query = bin_dir / "dpkg-query"
    dpkg_query.write_text(
        "#!/usr/bin/env bash\n"
        "expected='-f=${Version}\\n'\n"
        "if [[ \"${2:-}\" != \"$expected\" ]]; then\n"
        "  printf 'unexpected format: %s\\n' \"${2:-}\" >&2\n"
        "  exit 9\n"
        "fi\n"
        "printf '1:2.10.2-1\\n'\n",
        encoding="utf-8",
    )
    dpkg_query.chmod(0o755)

    shell = f"""
set -Eeuo pipefail
export POCKET_LAB_ALLOW_NON_TERMUX=1
export HOME="$TEST_HOME"
export PREFIX="$TEST_PREFIX"
export PATH="$TEST_BIN:/usr/bin:/bin"
source "$COMMON_PATH"
{resolver}
caddy() {{
  if [[ "${{1:-}}" == "version" ]]; then
    printf 'unknown\\n'
    return 0
  fi
  return 1
}}
caddy_installed_version
"""
    env = os.environ.copy()
    env.update(
        {
            "TEST_HOME": str(tmp_path / "home"),
            "TEST_PREFIX": str(tmp_path / "prefix"),
            "TEST_BIN": str(bin_dir),
            "COMMON_PATH": str(COMMON),
        }
    )
    result = subprocess.run(
        ["bash", "-lc", shell],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "2.10.2-1"


def test_service_version_normalizer_rejects_dollar_prefixed_values(tmp_path: Path):
    result = _run_common(tmp_path, 'pm2_normalize_service_version "$2.11.4"')
    assert result.returncode != 0
    assert result.stdout == ""


def test_caddy_version_resolver_fails_closed_without_binary_or_package_version(tmp_path: Path):
    dashboard = DASHBOARD.read_text(encoding="utf-8")
    start = dashboard.index("caddy_installed_version(){")
    end = dashboard.index("reload_caddy_if_config_changed(){", start)
    resolver = dashboard[start:end]
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True)
    dpkg_query = bin_dir / "dpkg-query"
    dpkg_query.write_text("#!/usr/bin/env bash\nexit 1\n", encoding="utf-8")
    dpkg_query.chmod(0o755)

    shell = f"""
set -Eeuo pipefail
export POCKET_LAB_ALLOW_NON_TERMUX=1
export HOME="$TEST_HOME"
export PREFIX="$TEST_PREFIX"
export PATH="$TEST_BIN:/usr/bin:/bin"
source "$COMMON_PATH"
{resolver}
caddy() {{
  [[ "${{1:-}}" == "version" ]] && printf 'unknown\\n' && return 0
  return 1
}}
caddy_installed_version
"""
    env = os.environ.copy()
    env.update(
        {
            "TEST_HOME": str(tmp_path / "home"),
            "TEST_PREFIX": str(tmp_path / "prefix"),
            "TEST_BIN": str(bin_dir),
            "COMMON_PATH": str(COMMON),
        }
    )
    result = subprocess.run(
        ["bash", "-lc", shell],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode != 0
    assert result.stdout == ""
    assert "Could not determine installed Caddy version from binary or Termux package metadata" in result.stderr
