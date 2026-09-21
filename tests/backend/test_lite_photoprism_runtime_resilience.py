from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LITE_SCRIPTS = (
    ROOT
    / "pocket-lab-final-structure"
    / "pocket-lab-bootstrap-production-scripts-patched"
    / "scripts"
    / "lite"
)


def _function_body(source: str, name: str, next_name: str) -> str:
    start = source.index(f"{name}()")
    end = source.index(f"{next_name}()", start)
    return source[start:end]


def test_photoprism_reconcile_never_installs_downloads_or_updates():
    source = (LITE_SCRIPTS / "install-photoprism-proot.sh").read_text()
    body = _function_body(source, "reconcile_runtime", "install_runtime")
    lowered = body.lower()
    assert "apt-get" not in lowered
    assert "curl -f" not in lowered
    assert "proot-distro install" not in lowered
    assert "install_or_update_package" not in body
    assert "create_env_file_for_install" not in body
    assert "require_existing_ubuntu" in body
    assert "require_existing_env" in body
    assert "binary_ready" in body
    assert "ensure_pm2_ownership" in body


def test_photoprism_update_is_explicit_and_separate_from_reconcile():
    source = (LITE_SCRIPTS / "install-photoprism-proot.sh").read_text()
    assert "install|reconcile|repair|update" in source
    update = _function_body(source, "update_runtime", "main")
    assert "install_or_update_package" in update
    reconcile = _function_body(source, "reconcile_runtime", "install_runtime")
    assert "install_or_update_package" not in reconcile


def test_global_runtime_reconcile_only_reconciles_photoprism_when_installed():
    source = (LITE_SCRIPTS / "reconcile-runtime.sh").read_text()
    assert "install-manifest.json" in source
    assert 'bash "$photoprism" reconcile' in source


def test_backend_repair_uses_non_installing_photoprism_reconcile():
    source = (
        ROOT
        / "pocket-lab-final-structure"
        / "runtime"
        / "api_fastapi"
        / "services"
        / "lite_app_operations.py"
    ).read_text()
    section = source[source.index("def _restart_photoprism_if_safe"):source.index("def _wait_for_photoprism_health")]
    assert '"reconcile"' in section
    assert '["pm2", "restart"' not in section


def test_photoprism_caddy_refresh_uses_canonical_version_aware_runtime_path():
    helper = (LITE_SCRIPTS / "restart-caddy-proxy.sh").read_text()
    photoprism = (LITE_SCRIPTS / "install-photoprism-proot.sh").read_text()

    assert 'bash "$DASHBOARD" --lite --caddy-only' in helper
    assert "pm2 delete caddy-proxy" not in helper
    assert 'pm2 start "$(command -v caddy)" --name caddy-proxy' not in helper
    assert 'restart-caddy-proxy.sh' in photoprism
