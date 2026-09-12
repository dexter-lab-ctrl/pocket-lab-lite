from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from pocket_lab_test_utils import ensure_runtime_path, isolated_state_dir


@pytest.fixture(autouse=True)
def isolate_security_optimization_state(tmp_path, monkeypatch):
    ensure_runtime_path()
    from api_fastapi import deps

    state = isolated_state_dir(tmp_path)
    deps.core.SETTINGS = deps.core.Settings(state_dir=state)
    monkeypatch.setenv("POCKETLAB_LITE_SCAN_ROOT", str(Path.cwd()))
    for name in (
        "POCKETLAB_SECURITY_BATTERY_PAUSE_PERCENT",
        "POCKETLAB_SECURITY_THERMAL_PAUSE_C",
        "POCKETLAB_SECURITY_MIN_MEMORY_AVAILABLE_PERCENT",
        "POCKETLAB_SECURITY_MAX_ATOMIC_TARGETS",
        "POCKETLAB_SECURITY_TRIVY_DB_MANAGED",
        "POCKETLAB_SECURITY_TRIVY_DB_MAX_STALE_SECONDS",
    ):
        monkeypatch.delenv(name, raising=False)
    yield


def _write_fake_tool(path: Path, body: str) -> None:
    path.write_text(f"#!{sys.executable}\n" + body, encoding="utf-8")
    path.chmod(0o755)


def _prepare_scan_tools(tmp_path, monkeypatch):
    bin_dir = tmp_path / "advanced-bin"
    bin_dir.mkdir()
    call_log = tmp_path / "advanced-trivy-calls"
    monkeypatch.setenv("TRIVY_CALL_LOG", str(call_log))
    _write_fake_tool(
        bin_dir / "lynis",
        "print('Lynis scan completed')\nraise SystemExit(0)\n",
    )
    _write_fake_tool(
        bin_dir / "trivy",
        """
import json
import os
import pathlib
import sys
args = sys.argv[1:]
if args == ['--version']:
    print('Version: advanced-test-trivy')
    raise SystemExit(0)
format_value = args[args.index('--format') + 1] if '--format' in args else ''
scanner_value = args[args.index('--scanners') + 1] if '--scanners' in args else ''
pathlib.Path(os.environ['TRIVY_CALL_LOG']).open('a', encoding='utf-8').write(
    (scanner_value or format_value or 'other') + '\\n'
)
if format_value == 'cyclonedx':
    output = pathlib.Path(args[args.index('--output') + 1])
    output.write_text(json.dumps({'bomFormat': 'CycloneDX', 'components': []}), encoding='utf-8')
    raise SystemExit(0)
print(json.dumps({'Results': [{'Target': 'package-lock.json', 'Vulnerabilities': [
    {'VulnerabilityID': 'CVE-ADVANCED-1', 'PkgName': 'advanced-package', 'Severity': 'HIGH'}
]}]}))
raise SystemExit(0)
""",
    )
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")

    from api_fastapi.services import lite_security, lite_security_policy as policy

    monkeypatch.setattr(
        lite_security,
        "_security_git_target_identity",
        lambda root, **kwargs: {"kind": "git_clean_checkout", "commit": "d" * 40},
    )
    monkeypatch.setattr(
        lite_security,
        "_trivy_database_identity",
        lambda: {
            "revision": "sha256:advanced-db",
            "version": "2",
            "valid_until": "2099-01-01T00:00:00+00:00",
        },
    )
    monkeypatch.setattr(lite_security, "runtime_config_posture", lambda root: {"status": "completed", "checks": []})
    monkeypatch.setattr(policy, "discover_proot_ubuntu_rootfs", lambda root: None)
    monkeypatch.setattr(policy, "photoprism_config_dir", lambda: tmp_path / "missing-photoprism-config")
    monkeypatch.setattr(policy, "backup_metadata_candidates", lambda root: [])
    return lite_security, call_log


def test_bounded_target_identity_changes_only_with_target_content(tmp_path):
    from api_fastapi.services import lite_security_optimization as optimization

    target = tmp_path / "config"
    target.mkdir()
    config = target / "settings.yaml"
    config.write_text("mode: safe\n", encoding="utf-8")
    first = optimization.path_target_identity(target, identity_label="settings")
    second = optimization.path_target_identity(target, identity_label="settings")
    config.write_text("mode: stricter\n", encoding="utf-8")
    changed = optimization.path_target_identity(target, identity_label="settings")

    assert first == second
    assert first is not None and changed is not None
    assert first["content_revision"] != changed["content_revision"]


def test_bounded_target_identity_rejects_top_level_symlink(tmp_path):
    from api_fastapi.services import lite_security_optimization as optimization

    target = tmp_path / "real-config"
    target.mkdir()
    (target / "settings.yaml").write_text("mode: safe\n", encoding="utf-8")
    alias = tmp_path / "config-alias"
    alias.symlink_to(target, target_is_directory=True)

    assert optimization.path_target_identity(alias, identity_label="settings") is None


def test_target_dag_normalizes_exact_and_nested_overlap(tmp_path):
    from api_fastapi.services import lite_security_optimization as optimization

    parent = tmp_path / "app"
    child = parent / "bin"
    child.mkdir(parents=True)
    nodes = optimization.normalize_target_dag(
        [
            {"target_id": "app", "path": str(parent), "contract_id": "same", "scanners": "vuln"},
            {"target_id": "app-copy", "path": str(parent), "contract_id": "same", "scanners": "vuln"},
            {"target_id": "app-bin", "path": str(child), "contract_id": "same", "scanners": "vuln"},
        ]
    )

    assert [item["state"] for item in nodes] == ["pending", "reused", "reused"]
    assert nodes[1]["overlap"] == "exact"
    assert nodes[2]["overlap"] == "nested"


def test_source_contract_is_identical_across_quick_and_full(tmp_path, monkeypatch):
    from api_fastapi.services import lite_security

    monkeypatch.setattr(
        lite_security,
        "_security_git_target_identity",
        lambda root, **kwargs: {"kind": "git_clean_checkout", "commit": "a" * 40},
    )
    monkeypatch.setattr(lite_security, "_trivy_version_identity", lambda trivy, root: "1.2.3")
    monkeypatch.setattr(
        lite_security,
        "_trivy_executable_identity",
        lambda trivy: "sha256:scanner-artifact",
    )
    database = {"revision": "sha256:db", "valid_until": "2099-01-01T00:00:00+00:00"}
    quick = lite_security._trivy_target_cache_identity(
        root=tmp_path,
        trivy="trivy",
        target_id="pocketlab_source",
        scanners="vuln,misconfig,secret",
        secret_mode=True,
        profile="quick",
        database_identity=database,
    )
    full = lite_security._trivy_target_cache_identity(
        root=tmp_path,
        trivy="trivy",
        target_id="pocketlab_source",
        scanners="vuln,misconfig,secret",
        secret_mode=True,
        profile="full",
        database_identity=database,
    )

    assert quick == full
    assert quick is not None
    assert quick["compatible_profiles"] == ["quick", "full"]

    without_secret_scanning = lite_security._trivy_target_cache_identity(
        root=tmp_path,
        trivy="trivy",
        target_id="pocketlab_source",
        scanners="vuln,misconfig",
        secret_mode=False,
        profile="quick",
        database_identity=database,
    )
    assert without_secret_scanning is not None
    assert quick["secret_mode"] is True
    assert without_secret_scanning["secret_mode"] is False
    assert quick["scanner_configuration_revision"] != without_secret_scanning["scanner_configuration_revision"]


def test_app_contract_is_cross_profile_and_config_specific(tmp_path, monkeypatch):
    from api_fastapi.services import lite_security

    app = tmp_path / "photoprism"
    app.mkdir()
    settings = app / "settings.yml"
    settings.write_text("safe: true\n", encoding="utf-8")
    monkeypatch.setattr(lite_security, "_trivy_version_identity", lambda trivy, root: "1.2.3")
    monkeypatch.setattr(
        lite_security,
        "_trivy_executable_identity",
        lambda trivy: "sha256:scanner-artifact",
    )
    database = {"revision": "sha256:db", "valid_until": "2099-01-01T00:00:00+00:00"}

    def identity(profile: str):
        return lite_security._trivy_target_cache_identity(
            root=tmp_path,
            trivy="trivy",
            target_path=app,
            target_id="photoprism_settings",
            scanners="secret",
            secret_mode=True,
            profile=profile,
            database_identity=database,
        )

    app_identity = identity("app")
    full_identity = identity("full")
    settings.write_text("safe: false\n", encoding="utf-8")
    changed = identity("app")

    assert app_identity == full_identity
    assert app_identity is not None and changed is not None
    assert app_identity["target_fingerprint"] != changed["target_fingerprint"]


def test_trivy_database_revision_change_invalidates_target_identity(tmp_path, monkeypatch):
    from api_fastapi.services import lite_security

    monkeypatch.setattr(lite_security, "_security_git_target_identity", lambda root, **kwargs: {
        "kind": "git_clean_checkout", "commit": "b" * 40,
    })
    monkeypatch.setattr(lite_security, "_trivy_version_identity", lambda trivy, root: "1.2.3")
    monkeypatch.setattr(
        lite_security,
        "_trivy_executable_identity",
        lambda trivy: "sha256:scanner-artifact",
    )

    def identity(revision: str):
        return lite_security._trivy_target_cache_identity(
            root=tmp_path,
            trivy="trivy",
            target_id="pocketlab_source",
            scanners="vuln,misconfig,secret",
            secret_mode=True,
            profile="quick",
            database_identity={"revision": revision, "valid_until": "2099-01-01T00:00:00+00:00"},
        )

    first = identity("sha256:db-one")
    changed = identity("sha256:db-two")

    assert first is not None and changed is not None
    assert first["scanner_db_revision"] != changed["scanner_db_revision"]
    assert first != changed


def test_target_cache_identity_mismatch_invalidates_reuse(tmp_path):
    from api_fastapi.services import lite_security

    identity = {
        "schema": 2,
        "contract_id": "target-trivy-v2",
        "compatible_profiles": ["full"],
        "target_id": "target",
        "target_fingerprint": "sha256:target-one",
        "scanner": "trivy",
        "scanner_version": "1.2.3",
        "scanner_artifact_revision": "sha256:scanner",
        "scanner_db_revision": "sha256:db-one",
        "scanner_db_valid_until": "2099-01-01T00:00:00+00:00",
        "policy_revision": "sha256:policy",
        "exclusion_revision": "sha256:exclusions",
        "scanner_configuration_revision": "sha256:config",
        "scanners": "vuln",
        "secret_mode": False,
        "sbom_format": "cyclonedx",
        "sbom_generator": "trivy",
        "sbom_schema": 1,
    }
    assert lite_security._write_security_target_cache(
        identity=identity,
        target_id="target",
        target_label="Target",
        scanners="vuln",
        findings=[],
        sbom=None,
        run_id="security-cache-source",
        profile="full",
    )
    assert lite_security._read_security_target_cache(identity) is not None

    incompatible = {**identity, "scanner_db_revision": "sha256:db-two"}
    assert lite_security._read_security_target_cache(incompatible) is None


def test_trivy_database_lifecycle_refreshes_stale_metadata(tmp_path, monkeypatch):
    from api_fastapi.services import lite_security

    metadata = tmp_path / "db" / "metadata.json"
    metadata.parent.mkdir()
    now = datetime.now(timezone.utc)

    def write_metadata(next_update: datetime) -> None:
        metadata.write_text(
            json.dumps(
                {
                    "Version": 2,
                    "UpdatedAt": (now - timedelta(hours=6)).isoformat(),
                    "NextUpdate": next_update.isoformat(),
                    "DownloadedAt": (now - timedelta(hours=5)).isoformat(),
                }
            ),
            encoding="utf-8",
        )

    write_metadata(now - timedelta(minutes=5))
    calls: list[list[str]] = []

    def refresh(args, *, cwd, timeout):
        calls.append(args)
        write_metadata(now + timedelta(days=1))
        return {"ok": True, "returncode": 0, "timed_out": False}

    monkeypatch.setattr(lite_security, "_trivy_database_candidates", lambda: [metadata])
    monkeypatch.setattr(lite_security, "_trivy_managed_lifecycle_enabled", lambda: True)
    monkeypatch.setattr(lite_security, "_run_command", refresh)
    monkeypatch.setenv("POCKETLAB_SECURITY_TRIVY_DB_MAX_STALE_SECONDS", "0")

    result = lite_security._prepare_trivy_intelligence("/usr/bin/trivy", tmp_path)
    assert calls == [["/usr/bin/trivy", "image", "--download-db-only"]]
    assert result["status"] == "refreshed"
    assert result["scan_db_mode"] == "skip_update_known_revision"
    assert result["refresh_succeeded"] is True


def test_trivy_database_lifecycle_uses_bounded_stale_exact_revision(tmp_path, monkeypatch):
    from api_fastapi.services import lite_security

    metadata = tmp_path / "db" / "metadata.json"
    metadata.parent.mkdir()
    now = datetime.now(timezone.utc)
    metadata.write_text(
        json.dumps(
            {
                "Version": 2,
                "UpdatedAt": (now - timedelta(days=1)).isoformat(),
                "NextUpdate": (now - timedelta(minutes=5)).isoformat(),
                "DownloadedAt": (now - timedelta(hours=23)).isoformat(),
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(lite_security, "_trivy_database_candidates", lambda: [metadata])
    monkeypatch.setattr(lite_security, "_trivy_managed_lifecycle_enabled", lambda: True)
    monkeypatch.setattr(
        lite_security,
        "_run_command",
        lambda *args, **kwargs: pytest.fail("bounded-stale intelligence must not refresh in the scan critical path"),
    )

    result = lite_security._prepare_trivy_intelligence("/usr/bin/trivy", tmp_path)

    assert result["status"] == "stale_within_grace"
    assert result["scan_db_mode"] == "skip_update_bounded_stale"
    assert result["reuse_eligible"] is True
    assert result["refresh_attempted"] is False


def test_trivy_database_lifecycle_blocks_after_failed_hard_expiry(tmp_path, monkeypatch):
    from api_fastapi.services import lite_security

    metadata = tmp_path / "db" / "metadata.json"
    metadata.parent.mkdir()
    now = datetime.now(timezone.utc)
    metadata.write_text(
        json.dumps(
            {
                "Version": 2,
                "UpdatedAt": (now - timedelta(days=5)).isoformat(),
                "NextUpdate": (now - timedelta(days=4)).isoformat(),
                "DownloadedAt": (now - timedelta(days=5)).isoformat(),
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(lite_security, "_trivy_database_candidates", lambda: [metadata])
    monkeypatch.setattr(lite_security, "_trivy_managed_lifecycle_enabled", lambda: True)
    monkeypatch.setattr(
        lite_security,
        "_run_command",
        lambda *args, **kwargs: {
            "ok": False,
            "returncode": 1,
            "timed_out": False,
        },
    )

    result = lite_security._prepare_trivy_intelligence("/usr/bin/trivy", tmp_path)

    assert result["hard_expired"] is True
    assert result["refresh_attempted"] is True
    assert result["refresh_succeeded"] is False
    assert result["scan_db_mode"] == "blocked_stale_intelligence"
    assert lite_security._trivy_intelligence_blocks_scan(result) is True


def test_trivy_artifact_identity_includes_managed_wrapper_target(tmp_path):
    from api_fastapi.services import lite_security

    managed = tmp_path / "managed-trivy"
    managed.write_bytes(b"scanner-build-one")
    managed.chmod(0o755)
    wrapper = tmp_path / "trivy"
    wrapper.write_text(
        f'#!/usr/bin/env bash\nexec "{managed}" "$@"\n',
        encoding="utf-8",
    )
    wrapper.chmod(0o755)

    first = lite_security._trivy_executable_identity(str(wrapper))
    managed.write_bytes(b"scanner-build-two")
    managed.chmod(0o755)
    changed = lite_security._trivy_executable_identity(str(wrapper))

    assert first is not None
    assert changed is not None
    assert first != changed


def test_budget_uses_configured_battery_policy_and_never_invents_one(monkeypatch):
    from api_fastapi.services import lite_security_optimization as optimization

    telemetry = {
        "battery_percent": 5,
        "charging": False,
        "temperature_c": 35,
        "available_memory_percent": 40,
        "free_storage": 8 * 1024 * 1024 * 1024,
    }
    default = optimization.scan_budget_decision(
        profile="full",
        started_monotonic=time.monotonic(),
        completed_atomic_targets=0,
        telemetry=telemetry,
    )
    monkeypatch.setenv("POCKETLAB_SECURITY_BATTERY_PAUSE_PERCENT", "20")
    configured = optimization.scan_budget_decision(
        profile="full",
        started_monotonic=time.monotonic(),
        completed_atomic_targets=0,
        telemetry=telemetry,
    )

    assert default["outcome"] == "continue"
    assert default["policy"]["battery_pause_percent"] is None
    assert configured["outcome"] == "pause_at_checkpoint"
    assert configured["reason"] == "battery_policy_threshold"


def test_budget_keeps_unknown_charging_telemetry_unknown(monkeypatch):
    from api_fastapi.services import lite_security_optimization as optimization

    monkeypatch.setenv("POCKETLAB_SECURITY_BATTERY_PAUSE_PERCENT", "20")
    decision = optimization.scan_budget_decision(
        profile="full",
        started_monotonic=time.monotonic(),
        completed_atomic_targets=0,
        telemetry={
            "battery_percent": 5,
            "charging": None,
            "available_memory_percent": 40,
            "free_storage": 8 * 1024 * 1024 * 1024,
        },
    )

    assert decision["outcome"] == "continue"
    assert decision["telemetry"]["charging"] is None


def test_resource_snapshot_marks_unavailable_battery_signals_unknown(tmp_path, monkeypatch):
    from api_fastapi.services import lite_security_optimization as optimization

    monkeypatch.setattr(optimization.shutil, "which", lambda name: None)
    snapshot = optimization.resource_snapshot(storage_path=tmp_path)

    assert snapshot["battery_percent"] is None
    assert snapshot["charging"] is None
    assert snapshot["temperature_c"] is None
    assert snapshot["telemetry_source"] == "unavailable"
    assert snapshot["sanitized"] is True


def test_coverage_preserves_resume_and_resource_deferral_provenance():
    from api_fastapi.services import lite_security, lite_security_policy as policy

    plan = policy.build_full_scan_plan(Path.cwd())
    provenance = {
        "kind": "resumed",
        "source_run_id": "prior-full",
        "source_profile": "full",
        "cross_profile": False,
        "checkpoint_compatible": True,
    }
    coverage = lite_security.build_coverage_summary(
        plan,
        {
            "trivy_source": {"status": "resumed", "label": "Pocket Lab Lite"},
            "proot_ubuntu": {
                "status": "deferred_resource_pressure",
                "label": "PROot Ubuntu",
            },
        },
        target_statuses=[
            {
                "target_id": "pocketlab_source",
                "target_label": "Pocket Lab Lite",
                "tool": "trivy",
                "status": "resumed",
                "provenance": "resumed",
                "cache": {"status": "hit", "provenance": provenance},
            },
            {
                "target_id": "proot_ubuntu",
                "target_label": "PROot Ubuntu",
                "tool": "trivy",
                "status": "deferred_resource_pressure",
            },
        ],
    )

    assert "Pocket Lab Lite" in coverage["checked_targets"]
    assert "PROot Ubuntu" in coverage["partial_targets"]
    source = next(
        item
        for item in coverage["target_statuses"]
        if item["target_id"] == "pocketlab_source"
    )
    assert source["provenance"] == "resumed"
    assert source["cache"]["provenance"]["checkpoint_compatible"] is True


def test_full_progress_marks_resource_deferred_targets_for_review():
    from api_fastapi.services import lite_security

    timeline = lite_security._full_execution_timeline_for_phase(
        {
            "target_statuses": [
                {
                    "target_id": "proot_ubuntu",
                    "status": "deferred_resource_pressure",
                }
            ]
        },
        "degraded",
    )

    step = next(item for item in timeline if item["key"] == "proot_ubuntu")
    assert step["status"] == "review"


def test_full_pause_checkpoint_is_resumed_by_next_compatible_run(tmp_path, monkeypatch):
    lite_security, call_log = _prepare_scan_tools(tmp_path, monkeypatch)
    monkeypatch.setenv("POCKETLAB_SECURITY_MAX_ATOMIC_TARGETS", "1")

    first = lite_security.run_security_scan(
        {"command_id": "security-full-paused", "run_id": "security-full-paused", "profile": "full"}
    )
    first_ledger = lite_security.optimization.checkpoint_run_state("security-full-paused")
    monkeypatch.delenv("POCKETLAB_SECURITY_MAX_ATOMIC_TARGETS")
    second = lite_security.run_security_scan(
        {"command_id": "security-full-resumed", "run_id": "security-full-resumed", "profile": "full"}
    )
    third = lite_security.run_security_scan(
        {"command_id": "security-full-reused", "run_id": "security-full-reused", "profile": "full"}
    )

    assert first["state"]["last_run"]["status"] == "degraded"
    assert first_ledger is not None
    assert first_ledger["status"] == "paused_at_checkpoint"
    assert first_ledger["resume_available"] is True
    source = [
        item
        for item in second["run"]["target_statuses"]
        if item.get("target_id") == "pocketlab_source"
    ]
    assert [item["status"] for item in source] == ["resumed", "resumed"]
    third_source = [
        item
        for item in third["run"]["target_statuses"]
        if item.get("target_id") == "pocketlab_source"
    ]
    assert [item["status"] for item in third_source] == ["reused", "reused"]
    assert first_ledger["targets"][1]["compatibility"]["scanner_db_revision"] == "sha256:advanced-db"
    assert call_log.read_text(encoding="utf-8").splitlines() == [
        "vuln,misconfig,secret",
        "cyclonedx",
    ]


def test_full_process_failure_leaves_compatible_checkpoint_for_next_run(tmp_path, monkeypatch):
    lite_security, call_log = _prepare_scan_tools(tmp_path, monkeypatch)
    posture_calls = 0

    def interrupted_posture(root):
        nonlocal posture_calls
        posture_calls += 1
        if posture_calls == 1:
            raise RuntimeError("simulated worker interruption")
        return {"status": "completed", "checks": []}

    monkeypatch.setattr(lite_security, "runtime_config_posture", interrupted_posture)
    with pytest.raises(RuntimeError, match="simulated worker interruption"):
        lite_security.run_security_scan(
            {
                "command_id": "security-full-interrupted",
                "run_id": "security-full-interrupted",
                "profile": "full",
            }
        )

    interrupted = lite_security.optimization.checkpoint_run_state(
        "security-full-interrupted"
    )
    resumed = lite_security.run_security_scan(
        {
            "command_id": "security-full-after-interruption",
            "run_id": "security-full-after-interruption",
            "profile": "full",
        }
    )

    assert interrupted is not None
    assert interrupted["status"] == "running"
    assert interrupted["resume_available"] is True
    source = [
        item
        for item in resumed["run"]["target_statuses"]
        if item.get("target_id") == "pocketlab_source"
    ]
    assert [item["status"] for item in source] == ["resumed", "resumed"]
    assert call_log.read_text(encoding="utf-8").splitlines() == [
        "vuln,misconfig,secret",
        "cyclonedx",
    ]


def test_quick_source_result_is_reused_by_full_exact_contract(tmp_path, monkeypatch):
    lite_security, call_log = _prepare_scan_tools(tmp_path, monkeypatch)

    lite_security.run_security_scan(
        {"command_id": "security-quick-source", "run_id": "security-quick-source", "profile": "quick"}
    )
    full = lite_security.run_security_scan(
        {"command_id": "security-full-from-quick", "run_id": "security-full-from-quick", "profile": "full"}
    )

    source = [
        item
        for item in full["run"]["target_statuses"]
        if item.get("target_id") == "pocketlab_source"
    ]
    assert [item["status"] for item in source] == ["reused", "reused"]
    assert source[0]["cache"]["provenance"]["cross_profile"] is True
    assert call_log.read_text(encoding="utf-8").splitlines() == [
        "vuln,misconfig,secret",
        "cyclonedx",
    ]


def _prepare_photoprism_targets(tmp_path, monkeypatch, lite_security):
    from api_fastapi.services import lite_security_policy as policy

    rootfs = tmp_path / "ubuntu-rootfs"
    app_files = rootfs / "opt" / "photoprism"
    app_files.mkdir(parents=True)
    (app_files / "assets.dat").write_text("app-build-one\n", encoding="utf-8")
    app_binary = rootfs / "usr" / "local" / "bin" / "photoprism"
    app_binary.parent.mkdir(parents=True)
    app_binary.write_bytes(b"photoprism-binary-one")
    app_binary.chmod(0o755)
    settings = tmp_path / "photoprism-settings"
    settings.mkdir()
    (settings / "photoprism.env").write_text("PHOTOPRISM_READONLY=true\n", encoding="utf-8")
    monkeypatch.setattr(policy, "discover_proot_ubuntu_rootfs", lambda root: rootfs)
    monkeypatch.setattr(policy, "photoprism_config_dir", lambda: settings)
    monkeypatch.setattr(
        lite_security,
        "_app_route_posture",
        lambda app_id: {
            "status": "checked",
            "route_ready": True,
            "summary": "PhotoPrism route checked by deterministic fixture.",
        },
    )
    return settings


def test_app_exact_targets_are_reused_by_full(tmp_path, monkeypatch):
    lite_security, call_log = _prepare_scan_tools(tmp_path, monkeypatch)
    _prepare_photoprism_targets(tmp_path, monkeypatch, lite_security)

    lite_security.run_security_scan(
        {
            "command_id": "security-app-for-full",
            "run_id": "security-app-for-full",
            "profile": "app",
            "app_id": "photoprism",
        }
    )
    full = lite_security.run_security_scan(
        {
            "command_id": "security-full-from-app",
            "run_id": "security-full-from-app",
            "profile": "full",
        }
    )

    app_targets = [
        item
        for item in full["run"]["target_statuses"]
        if item.get("target_id")
        in {"photoprism_app_files", "photoprism_app_binary", "photoprism_settings"}
    ]
    assert [item["status"] for item in app_targets] == [
        "reused",
        "reused",
        "reused",
        "reused",
    ]
    assert all(item.get("cache", {}).get("provenance", {}).get("cross_profile") for item in app_targets)
    assert call_log.read_text(encoding="utf-8").splitlines() == [
        "vuln,misconfig",
        "vuln,misconfig",
        "cyclonedx",
        "secret",
        "vuln,misconfig,secret",
        "cyclonedx",
        "vuln,misconfig",
    ]


def test_app_settings_change_invalidates_only_settings_target(tmp_path, monkeypatch):
    lite_security, call_log = _prepare_scan_tools(tmp_path, monkeypatch)
    settings = _prepare_photoprism_targets(tmp_path, monkeypatch, lite_security)

    lite_security.run_security_scan(
        {
            "command_id": "security-app-before-settings-change",
            "run_id": "security-app-before-settings-change",
            "profile": "app",
            "app_id": "photoprism",
        }
    )
    (settings / "photoprism.env").write_text(
        "PHOTOPRISM_READONLY=false\n", encoding="utf-8"
    )
    changed = lite_security.run_security_scan(
        {
            "command_id": "security-app-after-settings-change",
            "run_id": "security-app-after-settings-change",
            "profile": "app",
            "app_id": "photoprism",
        }
    )

    statuses = {
        (str(item.get("target_id")), str(item.get("tool"))): str(item.get("status"))
        for item in changed["run"]["target_statuses"]
    }
    assert statuses[("photoprism_app_files", "trivy")] == "reused"
    assert statuses[("photoprism_app_binary", "trivy")] == "reused"
    assert statuses[("photoprism_settings", "trivy")] == "checked"
    assert call_log.read_text(encoding="utf-8").splitlines() == [
        "vuln,misconfig",
        "vuln,misconfig",
        "cyclonedx",
        "secret",
        "secret",
    ]
