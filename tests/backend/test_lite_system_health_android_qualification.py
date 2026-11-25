from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "dev" / "lite" / "run-system-health-android-qualification.py"
UI_SCRIPT = REPO / "scripts" / "dev" / "lite" / "qualify-system-health-android-ui.mjs"


def _module():
    spec = importlib.util.spec_from_file_location("system_health_android_qualification", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_candidate_sha_and_identity_fail_closed():
    module = _module()

    class Controller:
        @staticmethod
        def _candidate_sha(_repo, value):
            if value == "1" * 40:
                return value
            raise RuntimeError("candidate repository is dirty")

    with pytest.raises(module.QualificationError):
        module.validate_candidate_sha(REPO, "0" * 40, Controller)
    with pytest.raises(module.QualificationError):
        module.validate_candidate_sha(REPO, "1" * 39, Controller)
    with pytest.raises(module.QualificationError):
        module.validate_candidate_sha(REPO, "2" * 40, Controller)
    module.validate_candidate_sha(REPO, "1" * 40, Controller)
    with pytest.raises(module.QualificationError):
        module.validate_synthetic_identity(
            "Qualification-Health", "security-assurance-runner",
            qualification_owner="0", destructive="0", test_bypass="0",
        )
    with pytest.raises(module.QualificationError):
        module.validate_synthetic_identity(
            "qualification-health-run", "qualification-owner",
            qualification_owner="0", destructive="0", test_bypass="0",
        )
    with pytest.raises(module.QualificationError):
        module.validate_synthetic_identity(
            "qualification-health-run", "security-assurance-runner",
            qualification_owner="1", destructive="0", test_bypass="0",
        )
    module.validate_synthetic_identity(
        "qualification-health-run", "qualification-owner",
        qualification_owner="1", destructive="0", test_bypass="0", allow_browser_ui=True,
    )
    with pytest.raises(module.QualificationError):
        module.validate_synthetic_identity(
            "qualification-health-run", "qualification-owner",
            qualification_owner="1", destructive="0", test_bypass="0",
        )


def test_backend_lane_starts_its_recovery_fixture_before_api_contract():
    source = SCRIPT.read_text(encoding="utf-8")
    run_start = source.index("    def run(self) -> tuple[str, Path]:")
    run_end = source.index("\n\n\ndef main(", run_start)
    run_body = source[run_start:run_end]
    fixture_call = run_body.index("self._start_recovery_projection_fixture()")
    api_call = run_body.index("self._qualify_api()")
    assert fixture_call < api_call
    assert '"POCKETLAB_SYSTEM_HEALTH_RECOVERY_ADAPTER": "1"' in source
    assert "harness_capability_denied" in source
    assert "self.nats_tunnel.stop()" in source
    assert "requested_remote_port = int(self.nats_tunnel.remote_port)" in source
    assert '"POCKETLAB_NATS_RECONNECT_WAIT": "30"' in source


def test_isolated_binding_rejects_production_paths_and_collisions(tmp_path):
    module = _module()
    root = tmp_path / "run"
    state = root / "state"
    state.mkdir(parents=True)
    database = state / "pocketlab-lite.sqlite3"
    database.touch()
    module.assert_isolated_binding(root, database, "nats://127.0.0.1:4222", "127.0.0.1", 8080)
    with pytest.raises(module.QualificationError):
        module.assert_isolated_binding(root, tmp_path / "production.sqlite3", "nats://127.0.0.1:4222", "127.0.0.1", 8080)
    with pytest.raises(module.QualificationError):
        module.assert_isolated_binding(root, database, "nats://phone.example:4222", "127.0.0.1", 8080)
    with pytest.raises(module.QualificationError):
        module.assert_isolated_binding(root, database, "nats://127.0.0.1:4222", "0.0.0.0", 8080)
    with pytest.raises(module.QualificationError):
        module.assert_isolated_binding(root, database, "nats://127.0.0.1:4222", "127.0.0.1", 8080, occupied_ports=[8080])
    with pytest.raises(module.QualificationError):
        module.assert_isolated_binding(root, database, "nats://127.0.0.1:8080", "127.0.0.1", 8080)


def test_production_projection_ignores_runtime_process_ids():
    module = _module()
    before = {
        "system": "Android",
        "architecture": "aarch64",
        "source_sha": "a" * 40,
        "git_clean": True,
        "pm2": [{"name": "api", "pid": 101, "status": "online", "version": "1", "cwd_class": "pocketlab_checkout"}],
        "listeners": {"tcp": ["127.0.0.1:8080"]},
    }
    after = {**before, "pm2": [{**before["pm2"][0], "pid": 202}]}
    assert module.production_projection(before) == module.production_projection(after)


def test_parse_json_log_record_uses_last_valid_record():
    module = _module()
    payload, line_count = module.parse_json_log_record(
        "startup warning\n{\"status\":\"PASS\",\"changed\":true}\nshutdown note\n",
        label="projection driver",
    )
    assert payload["status"] == "PASS"
    assert line_count == 3
    payload, line_count = module.parse_json_log_record(
        "b'{\"status\":\"PASS\",\"changed\":true}\\n'", label="projection driver"
    )
    assert payload["changed"] is True
    assert line_count == 1
    with pytest.raises(module.QualificationError, match="nonempty_lines=2"):
        module.parse_json_log_record("startup warning\nshutdown note\n", label="projection driver")


def test_response_contract_is_bounded_to_denial_fields():
    module = _module()
    contract = module.response_contract(module.HttpResult(409, {
        "detail": {
            "status": "blocked",
            "reason_code": "system_health_recovery_disabled",
            "recorded": True,
            "unexpected": "omitted",
        },
        "extra": "omitted",
    }))
    assert contract["status"] == 409
    assert contract["detail_status"] == "blocked"
    assert contract["reason_code"] == "system_health_recovery_disabled"
    assert contract["recorded"] is True
    assert "unexpected" in contract["detail_keys"]
    direct = module.response_contract(module.HttpResult(409, {
        "status": "blocked",
        "reason_code": "incident_generation_changed",
    }))
    assert direct["detail_status"] == "blocked"
    assert direct["reason_code"] == "incident_generation_changed"


def test_schema42_forward_migrations_repeat_and_rollback_copy(tmp_path):
    module = _module()
    sha = module._run(["git", "rev-parse", "HEAD"], cwd=REPO).stdout.strip()
    base = module._run(["git", "rev-parse", "origin/main"], cwd=REPO).stdout.strip()
    root = tmp_path / "run"
    root.mkdir()
    database, rollback, initial = module.create_schema42_fixture(REPO, sha, root)
    assert initial["before"]["schema_version"] == 42
    assert initial["before"]["marker_revision"] == 7
    applied = module.apply_isolated_health_migrations(REPO, sha, database)
    latest = max(version for version, *_ in module._candidate_migrations(REPO, sha))
    assert applied["applied"] == list(range(43, latest + 1))
    assert module.apply_isolated_health_migrations(REPO, sha, database)["applied"] == []
    final = module._verify_sqlite(database, expected_version=latest)
    assert final["status"] == "PASS"
    assert final["marker_revision"] == 7
    module.validate_rollback_backup(rollback, root)
    assert module.prove_isolated_rollback(REPO, base, rollback, root, str(REPO / ".venv" / "bin" / "python"))["status"] == "PASS"
    with pytest.raises(module.QualificationError):
        module.validate_rollback_backup(root / "missing.sqlite3", root)


def test_readiness_sanitization_and_source_safety_contract():
    module = _module()
    module.validate_candidate_readiness(api_status=200, api_owned=True, worker_owned=True)
    with pytest.raises(module.QualificationError):
        module.validate_candidate_readiness(api_status=503, api_owned=True, worker_owned=True)
    with pytest.raises(module.QualificationError):
        module.validate_candidate_readiness(api_status=200, api_owned=False, worker_owned=True)
    evidence = module.sanitize({"session_token": "secret", "nested": {"private_key": "key", "status": "blocked"}})
    assert evidence["session_token"] == "[redacted]"
    assert evidence["nested"]["private_key"] == "[redacted]"
    assert evidence["nested"]["status"] == "blocked"
    source = SCRIPT.read_text(encoding="utf-8")
    assert '"POCKETLAB_TEST_AUTH_BYPASS": "0"' in source
    assert '"POCKETLAB_QUALIFICATION_OWNER": self.qualification_owner_flag' in source
    assert '"POCKETLAB_HARNESS_DESTRUCTIVE": "0"' in source
    assert '"POCKETLAB_SYSTEM_HEALTH_RECOVERY_ADAPTER": "1"' in source
    assert '"POCKETLAB_NATS_URL": nats_origin' in source
    assert "production_database_touched" in source
    assert "_REMOTE_RECOVERY_FIXTURE" in source
    assert "candidate_sqlite_projection_only" in source


def test_taskfile_wires_only_the_narrow_system_health_lane():
    taskfile = (REPO / "tasks" / "Taskfile.lite.yml").read_text(encoding="utf-8")
    assert "lite:system-health:candidate:android:qualify" in taskfile
    assert "run-system-health-android-qualification.py" in taskfile
    assert "run-ui-performance-android-safety.sh" not in taskfile


def test_browser_ui_lane_keeps_owner_non_destructive_and_uses_candidate_bridge():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "browser_ui: bool = False" in source
    assert 'self.bootstrap_profile = "qualification-owner" if self.browser_ui else "security-assurance-runner"' in source
    assert '"POCKETLAB_HARNESS_DESTRUCTIVE": "0"' in source
    assert '"POCKETLAB_TEST_AUTH_BYPASS": "0"' in source
    assert '"/api/lite/harness/browser/bridge"' in source
    ui_source = (REPO / "scripts" / "dev" / "lite" / "run-system-health-android-ui-qualification.py").read_text(encoding="utf-8")
    assert "run._start_local_opa()" in ui_source
    assert "--performance" in ui_source
    assert '"LITE_ANDROID_QUALIFICATION_SCOPE": "system-health"' in ui_source
    assert '"LITE_QUALIFICATION_BROWSER_BRIDGE": "1"' in ui_source
    assert '"interaction_count": 9' in ui_source


def test_physical_system_health_qualifier_activates_android_target():
    source = UI_SCRIPT.read_text(encoding="utf-8")
    assert "bringToFront" in source
    assert "Page.bringToFront" in source
    assert "context.pages()" in source
    assert "candidatePages" in source
    assert "foreground System Health page" in source
    assert "What needs attention" in source
    assert "Review issue" in source
    assert "unsupported Fix action" in source
    assert "Confirm recovery" in source
    assert "confirmRecovery.waitFor" in source
    assert "eligible NATS recovery incident" in SCRIPT.read_text(encoding="utf-8")
    assert "has: page.getByRole('button', { name: 'Review recovery', exact: true })" in UI_SCRIPT.read_text(encoding="utf-8")
    runner_source = (REPO / "scripts" / "dev" / "lite" / "run-system-health-android-ui-qualification.py").read_text(encoding="utf-8")
    assert "POCKETLAB_CANDIDATE_BROWSER_RECOVERY_SIGNAL_FILE" in runner_source
    assert "_pause_candidate_nats_for_recovery" in runner_source
    assert "watch_browser_recovery_signal" in runner_source
