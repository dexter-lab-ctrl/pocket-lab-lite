from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = (
    ROOT
    / "pocket-lab-final-structure"
    / "pocket-lab-bootstrap-production-scripts-patched"
    / "scripts"
)


def test_boot_recovery_is_external_to_pm2_and_uses_resurrection_then_reconcile():
    guardian = (SCRIPTS / "lite" / "runtime-guardian.sh").read_text()
    installer = (SCRIPTS / "lite" / "install-boot-recovery.sh").read_text()
    reconcile = (SCRIPTS / "lite" / "reconcile-runtime.sh").read_text()

    assert "pm2 resurrect" in guardian
    assert "pocketlab-runtime-reconciler" in guardian
    assert "nohup" in installer
    assert 'BOOT_DIR="$HOME/.termux/boot"' in installer
    assert 'BOOT_FILE="$BOOT_DIR/pocketlab-lite"' in installer
    assert 'atomic_write "$BOOT_FILE" 0700' in installer
    assert "--reconcile-only" in reconcile
    assert "bootstrap.sh" not in reconcile


def test_runtime_reconcile_contract_forbids_install_and_legacy_work():
    reconcile = (SCRIPTS / "lite" / "reconcile-runtime.sh").read_text().lower()
    assert "downloads_allowed" in reconcile
    assert '"downloads_allowed": false' in reconcile
    assert '"legacy_services_allowed": false' in reconcile
    assert "apt-get" not in reconcile
    assert "pkg install" not in reconcile
    assert "curl -f" not in reconcile


def test_bootstrap_has_lite_only_boot_recovery_stage():
    bootstrap = (SCRIPTS / "bootstrap.sh").read_text()
    assert "13|install_lite_boot_recovery|lite/install-boot-recovery.sh" in bootstrap
    assert 'install_lite_boot_recovery)' in bootstrap
    assert '[[ "$BOOTSTRAP_PROFILE" != "lite" ]]' in bootstrap


def test_guardian_checks_pm2_pid_without_cli_autostart():
    guardian = (SCRIPTS / "lite" / "runtime-guardian.sh").read_text()
    block = guardian[guardian.index("pm2_alive()"):guardian.index("pm2_process_matches_source()")]
    assert "pm2.pid" in block
    assert "kill -0" in block
    assert "pm2 ping" not in block


def test_guardian_compares_running_supervisors_to_current_source_versions():
    guardian = (SCRIPTS / "lite" / "runtime-guardian.sh").read_text()

    assert 'pm2_process_matches_source()' in guardian
    assert 'pocketlab_source_version "$source_path"' in guardian
    assert '"pocketlab-runtime-reconciler" "$RUNTIME_RECONCILER_SERVER"' in guardian
    assert '"pocketlab-core-supervisor" "$CORE_SUPERVISOR_SERVER"' in guardian
    assert 'runtime_reconciler_missing_or_source_drift' in guardian
    assert 'core_supervisor_missing_or_source_drift' in guardian


def test_guardian_self_reloads_when_repository_source_changes():
    guardian = (SCRIPTS / "lite" / "runtime-guardian.sh").read_text()

    assert 'GUARDIAN_START_DIGEST="$(guardian_source_digest)"' in guardian
    assert 'reload_if_source_changed' in guardian
    assert 'Runtime guardian source changed; reloading current repository version' in guardian
    assert 'exec bash "$0" --boot' in guardian


def test_boot_recovery_installer_restarts_existing_guardian_to_activate_current_source():
    installer = (SCRIPTS / "lite" / "install-boot-recovery.sh").read_text()

    assert 'pkill -f "[r]untime-guardian.sh"' in installer
    assert 'nohup "$GUARDIAN" --boot' in installer
