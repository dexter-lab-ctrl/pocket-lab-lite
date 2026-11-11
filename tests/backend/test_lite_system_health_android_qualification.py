from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "dev" / "lite" / "run-system-health-android-qualification.py"


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
            "reason_code": "system_health_executor_not_qualified",
            "recorded": True,
            "unexpected": "omitted",
        },
        "extra": "omitted",
    }))
    assert contract["status"] == 409
    assert contract["detail_status"] == "blocked"
    assert contract["reason_code"] == "system_health_executor_not_qualified"
    assert contract["recorded"] is True
    assert "unexpected" in contract["detail_keys"]


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
    assert applied["applied"] == [43, 44]
    assert module.apply_isolated_health_migrations(REPO, sha, database)["applied"] == []
    final = module._verify_sqlite(database, expected_version=44)
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
    assert '"POCKETLAB_QUALIFICATION_OWNER": "0"' in source
    assert '"POCKETLAB_HARNESS_DESTRUCTIVE": "0"' in source
    assert '"POCKETLAB_NATS_URL": nats_origin' in source
    assert "production_database_touched" in source


def test_taskfile_wires_only_the_narrow_system_health_lane():
    taskfile = (REPO / "tasks" / "Taskfile.lite.yml").read_text(encoding="utf-8")
    assert "lite:system-health:candidate:android:qualify" in taskfile
    assert "run-system-health-android-qualification.py" in taskfile
    assert "run-ui-performance-android-safety.sh" not in taskfile
