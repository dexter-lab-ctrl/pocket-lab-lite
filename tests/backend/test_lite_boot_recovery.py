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
    assert ".termux/boot/pocketlab-lite" in installer
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
