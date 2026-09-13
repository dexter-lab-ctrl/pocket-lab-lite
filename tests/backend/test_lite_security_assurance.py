from __future__ import annotations

import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from pocket_lab_test_utils import ensure_runtime_path, isolated_state_dir


@pytest.fixture()
def assurance_runtime(tmp_path, monkeypatch):
    ensure_runtime_path()
    from api_fastapi import deps
    from api_fastapi.db.connection import reset_sqlite_path_cache
    from api_fastapi.db.migrations import apply_migrations
    from api_fastapi.db.runtime import SQLITE_READS

    state = isolated_state_dir(tmp_path)
    monkeypatch.setenv("POCKETLAB_LITE_DB_PATH", str(state / "pocketlab-lite.sqlite3"))
    monkeypatch.setenv("POCKETLAB_STATE_DIR", str(state))
    monkeypatch.setenv("POCKETLAB_DEV_STATE_DIR", str(state))
    monkeypatch.setenv("POCKETLAB_ENVIRONMENT", "qualification")
    monkeypatch.setenv("POCKETLAB_HARNESS_ENABLED", "1")
    monkeypatch.setenv("POCKETLAB_HARNESS_DESTRUCTIVE", "0")
    monkeypatch.setenv("POCKETLAB_QUALIFICATION_OWNER", "0")
    monkeypatch.setenv("POCKETLAB_TEST_AUTH_BYPASS", "0")
    monkeypatch.setenv("POCKETLAB_HARNESS_RUNTIME_ID", "assurance-test-runtime")
    reset_sqlite_path_cache()
    SQLITE_READS.invalidate()
    deps.core.SETTINGS = deps.core.Settings(state_dir=state)
    apply_migrations()
    return state


def _insert_synthetic_session():
    from api_fastapi.db.connection import connection
    from api_fastapi.services import lite_harness

    now = datetime.now(timezone.utc)
    started = now.isoformat().replace("+00:00", "Z")
    expires = (now + timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    with connection() as conn:
        conn.execute(
            """
            INSERT INTO synthetic_principals(
                principal_id,principal_class,display_name,environment_scope,target_scope,
                allowed_profiles_json,default_profile,public_key,public_key_fingerprint,
                created_at,expires_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                "assurance-test-principal",
                "qualification",
                "Assurance test principal",
                lite_harness.HARNESS_RUNTIME_ENVIRONMENT,
                lite_harness.HARNESS_TARGET_SCOPE,
                json.dumps(["security-assurance-runner"]),
                "security-assurance-runner",
                "test-public-key",
                "sha256:test-public-key",
                started,
                expires,
            ),
        )
        conn.execute(
            """
            INSERT INTO harness_sessions(
                harness_session_id,principal_id,principal_class,purpose,capability_profile,
                capabilities_json,target_scope,runtime_id,token_hash,started_at,expires_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                "assurance-test-session",
                "assurance-test-principal",
                "qualification",
                "security.assurance",
                "security-assurance-runner",
                json.dumps(["security.assurance.run", "security.assurance.read"]),
                lite_harness.HARNESS_TARGET_SCOPE,
                lite_harness._runtime_id(),
                "sha256:test-session-token",
                started,
                expires,
            ),
        )


def test_registry_is_complete_and_execution_defaults_are_safe(assurance_runtime):
    from api_fastapi.services import lite_security_assurance as assurance

    result = assurance.validate_registries()
    assert result["primary_framework"] == "STRIDE"
    assert result["target_scope"] == "local_server_host_only"
    assert result["execution_owner"] == "worker"
    assert set(result["suites"]) == {"smoke", "standard", "deep", "adversarial"}
    assert len(result["attack_paths"]) == 14
    defaults = result["execution_defaults"]
    assert defaults == {
        "shell": False,
        "cwd": "repository_root",
        "allowed_target": "local_server_host_only",
        "allowed_target_scope": "local_server_host_only",
        "timeout_seconds": 5,
        "max_output_bytes": 32768,
        "process_group_cleanup": True,
        "concurrency": "exclusive_for_heavy_tools",
        "output_parser": "first_version_line_only",
        "finding_normalizer": "normalized_sanitized_assurance_finding",
        "sanitization_policy": "lite_security_policy.redact_value",
        "failure_classification": ["missing", "failed", "timed_out", "output_limited"],
    }


def test_unknown_registry_values_and_extra_command_fields_fail_closed(assurance_runtime):
    from api_fastapi.services import lite_security_assurance as assurance
    from api_fastapi.routers.security_assurance import AssuranceRunRequest

    with pytest.raises(assurance.AssuranceError) as suite_error:
        assurance.suite_def("not-registered")
    assert suite_error.value.reason_code == "suite_unknown"

    with pytest.raises(assurance.AssuranceError) as scenario_error:
        assurance.scenario_def("not-registered")
    assert scenario_error.value.reason_code == "scenario_unknown"

    with pytest.raises(assurance.AssuranceError) as tool_error:
        assurance._tool_inventory("not-registered", execute_version=False)
    assert tool_error.value.reason_code == "tool_unknown"

    with pytest.raises(ValidationError):
        AssuranceRunRequest.model_validate(
            {"suite_id": "smoke", "command": "echo forbidden"}
        )
    valid_baseline = "assurance-" + "a" * 32
    assert AssuranceRunRequest.model_validate(
        {"suite_id": "smoke", "baseline_run_id": valid_baseline}
    ).baseline_run_id == valid_baseline


def test_profile_has_assurance_capabilities_without_generic_authority(assurance_runtime):
    from api_fastapi.services import lite_security_assurance as assurance

    capabilities = assurance.list_capabilities()
    assert capabilities["profile"] == "security-assurance-runner"
    assert capabilities["target_scope"] == "local_server_host_only"
    assert capabilities["principal_class"] == "qualification"
    assert capabilities["destructive_capabilities"] == []
    assert capabilities["generic_shell"] is False
    assert capabilities["arbitrary_nats"] is False
    assert capabilities["arbitrary_network_targets"] is False
    assert capabilities["browser_surface"] is False
    assert "security.assurance.run" in capabilities["capabilities"]
    assert "Owner" not in str(capabilities)


def test_bounded_process_path_uses_absolute_argv_and_cleans_up(assurance_runtime, tmp_path):
    from api_fastapi.services import lite_security_assurance as assurance

    echo = shutil.which("echo")
    assert echo
    result = assurance._bounded_argv(
        [str(Path(echo).resolve()), "assurance-safe"],
        cwd=Path(assurance.REPOSITORY_ROOT),
        timeout_seconds=2,
        max_output_bytes=1024,
    )
    assert result["status"] == "completed"
    assert result["stdout"].strip() == "assurance-safe"
    assert result["timed_out"] is False
    assert "shell" not in result

    with pytest.raises(assurance.AssuranceError) as relative_error:
        assurance._bounded_argv(["echo", "not-registered"], cwd=Path(assurance.REPOSITORY_ROOT))
    assert relative_error.value.reason_code == "assurance_command_unregistered"

    with pytest.raises(assurance.AssuranceError) as cwd_error:
        assurance._bounded_argv(
            [str(Path(echo).resolve()), "outside-repository"],
            cwd=tmp_path,
        )
    assert cwd_error.value.reason_code == "assurance_cwd_unregistered"

    sleep = shutil.which("sleep")
    if sleep:
        timed = assurance._bounded_argv(
            [str(Path(sleep).resolve()), "1"],
            cwd=Path(assurance.REPOSITORY_ROOT),
            timeout_seconds=0.05,
            max_output_bytes=1024,
        )
        assert timed["status"] == "timed_out"
        assert timed["timed_out"] is True


def test_websocket_probe_uses_fixed_upgrade_and_bounded_response(assurance_runtime, monkeypatch):
    from api_fastapi.services import lite_security_assurance as assurance

    class FakeSocket:
        def __init__(self):
            self.sent = b""

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def settimeout(self, _timeout):
            return None

        def sendall(self, value):
            self.sent = value

        def recv(self, _maximum):
            return b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\n\r\n"

    fake = FakeSocket()
    monkeypatch.setattr(assurance.socket, "create_connection", lambda *_args, **_kwargs: fake)
    result = assurance._websocket_probe(
        port=8443,
        path="/ws/events",
        headers={"X-Pocket-Lab-Qualification": "forged"},
    )
    request = fake.sent.decode("ascii")
    assert "GET /ws/events HTTP/1.1" in request
    assert "Upgrade: websocket" in request
    assert "X-Pocket-Lab-Qualification: forged" in request
    assert result["status_code"] == 101
    assert result["handshake_accepted"] is True
    assert result["response_harness_marker_echoed"] is False


def test_stream_probe_reads_only_fixed_sse_headers(assurance_runtime, monkeypatch):
    from api_fastapi.services import lite_security_assurance as assurance

    class FakeStreamSocket:
        def __init__(self):
            self.sent = b""

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def settimeout(self, _timeout):
            return None

        def sendall(self, value):
            self.sent = value

        def recv(self, _maximum):
            return b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\n\r\n"

    fake = FakeStreamSocket()
    monkeypatch.setattr(assurance.socket, "create_connection", lambda *_args, **_kwargs: fake)
    result = assurance._stream_probe(
        port=8443,
        path="/api/lite/security/events",
        headers={"X-Pocket-Lab-Qualification": "forged"},
    )
    assert "GET /api/lite/security/events HTTP/1.1" in fake.sent.decode("ascii")
    assert result["status_code"] == 200
    assert result["response_harness_marker_echoed"] is False


def test_pm2_summary_uses_status_only_command(assurance_runtime, monkeypatch):
    from api_fastapi.services import lite_security_assurance as assurance

    captured = {}
    monkeypatch.setattr(assurance, "_verified_executable", lambda _name: Path("/usr/bin/pm2"))

    def bounded(argv, **kwargs):
        captured["argv"] = argv
        captured["kwargs"] = kwargs
        return {
            "status": "completed",
            "stdout": "id name status\n1 pocket-worker online\n",
        }

    monkeypatch.setattr(assurance, "_bounded_argv", bounded)
    result = assurance._pm2_summary()
    assert captured["argv"] == ["/usr/bin/pm2", "status", "pocket-worker", "--no-color"]
    assert result["worker_online"] is True
    assert result["worker_status"] == "online"


def test_redaction_source_boundaries_and_attack_path_mapping(assurance_runtime):
    from api_fastapi.services import lite_security_assurance as assurance

    assert assurance._redaction_contract()["status"] == "PASS"
    assert assurance._source_boundaries()["status"] == "PASS"

    attack_paths = assurance._attack_path_inventory()
    assert attack_paths["all_current_paths_classified"] is True
    assert {item["attack_path_id"] for item in attack_paths["paths"]} == {
        f"AP-{number:02d}" for number in range(1, 15)
    }
    assert attack_paths["classification_counts"]["HUMAN_REVIEW_REQUIRED"] >= 1
    assert assurance.scenario_def("AP-14")["id"] == "AP-14"
    assert assurance.scenario_def("AP-14")["owasp"] == ["A01", "A08"]

    stride, owasp, controls = assurance._coverage_payload(
        [
            {
                "scenario_id": "fixture",
                "status": "PASS",
                "stride": ["Spoofing"],
                "owasp": ["A07"],
                "controls": ["CTRL-API-CONTROL"],
                "attack_paths": ["AP-01"],
            }
        ]
    )
    assert stride["by_category"]["Spoofing"]["PASS"] == 1
    assert owasp["version"] == "2021"
    assert owasp["categories"][6]["name"] == "Identification and Authentication Failures"
    assert controls["controls"][0]["control_id"] == "CTRL-API-CONTROL"


def test_preflight_distinguishes_pm2_online_from_api_readiness(assurance_runtime, monkeypatch):
    from api_fastapi.services import lite_security_assurance as assurance

    revision = "a" * 40
    monkeypatch.setattr(assurance, "_fixed_git_revision", lambda: {"revision": revision})
    monkeypatch.setattr(assurance, "_fixed_git_clean", lambda: {"ok": True, "changed_count": 0})
    monkeypatch.setattr(
        assurance,
        "_health_summary",
        lambda: {
            "health_ok": True,
            "ready_ok": True,
            "health": {"status_code": 200},
            "ready": {"status_code": 200},
        },
    )
    monkeypatch.setattr(
        assurance,
        "_http_probe",
        lambda **_kwargs: {"status_code": 200, "body": {"status": "ok"}},
    )
    monkeypatch.setattr(
        assurance,
        "_pm2_summary",
        lambda: {"available": True, "status": "checked", "worker_online": True, "worker_status": "online"},
    )
    monkeypatch.setattr(
        assurance,
        "_bus_summary",
        lambda: {
            "connected": True,
            "jetstream_enabled": True,
            "durable_consumer_count": 1,
            "local_api_durable_consumer": True,
        },
    )
    monkeypatch.setattr(
        assurance.optimization,
        "resource_snapshot",
        lambda: {"free_storage": 10**10, "available_memory": 10**9, "available_memory_percent": 50},
    )
    monkeypatch.setattr(assurance, "_security_conflict", lambda _profile: None)

    ready = assurance.preflight("smoke", expected_revision=revision)
    assert ready["status"] == "ready"
    assert ready["pm2_online_is_not_api_ready"] is True
    assert ready["checks"]["worker_process"]["ok"] is True

    monkeypatch.setattr(
        assurance,
        "_health_summary",
        lambda: {
            "health_ok": True,
            "ready_ok": False,
            "health": {"status_code": 200},
            "ready": {"status_code": 503},
        },
    )
    blocked = assurance.preflight("smoke", expected_revision=revision)
    assert blocked["status"] == "blocked"
    assert "api_ready" in blocked["blockers"]

    def unavailable_bus():
        raise RuntimeError("not persisted")

    monkeypatch.setattr(assurance, "_bus_summary", unavailable_bus)
    infrastructure_blocked = assurance.preflight("smoke", expected_revision=revision)
    assert infrastructure_blocked["status"] == "blocked"
    assert "nats" in infrastructure_blocked["blockers"]
    assert infrastructure_blocked["checks"]["nats"]["failure_code"] == "nats_status_unavailable"


def test_migration_and_blocked_run_report_are_durable_and_sanitized(assurance_runtime):
    from api_fastapi.db.connection import read_connection
    from api_fastapi.db.migrations import current_schema_version
    from api_fastapi.services import lite_security_assurance as assurance

    assert current_schema_version() == 35
    with read_connection() as conn:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert {"assurance_runs", "assurance_scenarios", "assurance_tool_results", "assurance_findings"}.issubset(tables)
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []

    _insert_synthetic_session()
    run = assurance.create_run(
        suite_id="smoke",
        scenario_id="evidence-redaction",
        baseline_run_id=None,
        principal_id="assurance-test-principal",
        session_id="assurance-test-session",
        revision_sha="b" * 40,
        preflight_result={"status": "blocked", "blockers": ["api_ready"], "sanitized": True},
    )
    assert run["status"] == "QUEUED"
    blocked = assurance.record_blocked_run(
        run["run_id"],
        failure_code="preflight_blocked",
        preflight_result={"status": "blocked", "blockers": ["api_ready"], "sanitized": True},
    )
    assert blocked["status"] == "BLOCKED"
    assert blocked["report"]["available"] is True
    report = assurance.read_report(run["run_id"])
    assert report["available"] is True
    assert "summary.md" in report["files"]
    report_text = json.dumps(report, sort_keys=True)
    assert "test-session-token" not in report_text
    assert "private_key" not in report_text.casefold()

    with pytest.raises(assurance.AssuranceError) as baseline_error:
        assurance.create_run(
            suite_id="smoke",
            scenario_id="evidence-redaction",
            baseline_run_id="assurance-" + "c" * 32,
            principal_id="assurance-test-principal",
            session_id="assurance-test-session",
            revision_sha="c" * 40,
            preflight_result={"status": "blocked"},
        )
    assert baseline_error.value.reason_code == "baseline_invalid"


def test_cancel_is_bound_to_the_admitting_session(assurance_runtime):
    from api_fastapi.services import lite_security_assurance as assurance

    _insert_synthetic_session()
    run = assurance.create_run(
        suite_id="smoke",
        scenario_id="evidence-redaction",
        baseline_run_id=None,
        principal_id="assurance-test-principal",
        session_id="assurance-test-session",
        revision_sha="d" * 40,
        preflight_result={"status": "ready", "sanitized": True},
    )
    with pytest.raises(assurance.AssuranceError) as mismatch:
        assurance.request_cancel(
            run["run_id"], principal_id="other-principal", session_id="other-session"
        )
    assert mismatch.value.reason_code == "run_principal_mismatch"
    cancelled = assurance.request_cancel(
        run["run_id"],
        principal_id="assurance-test-principal",
        session_id="assurance-test-session",
    )
    assert cancelled["cancel_requested"] == 1


def test_stale_run_reconciliation_is_truthful_and_terminal(assurance_runtime):
    from api_fastapi.db.connection import connection
    from api_fastapi.services import lite_security_assurance as assurance

    _insert_synthetic_session()
    run = assurance.create_run(
        suite_id="smoke",
        scenario_id="evidence-redaction",
        baseline_run_id=None,
        principal_id="assurance-test-principal",
        session_id="assurance-test-session",
        revision_sha="f" * 40,
        preflight_result={"status": "ready", "sanitized": True},
    )
    with connection() as conn:
        conn.execute(
            "UPDATE assurance_runs SET updated_at=? WHERE run_id=?",
            ("2000-01-01T00:00:00Z", run["run_id"]),
        )
    recovered = assurance.reconcile_stale_runs()
    assert recovered["count"] == 1
    assert recovered["reconciled"][0]["status"] == "PARTIAL"
    assert assurance.get_run(run["run_id"])["status"] == "PARTIAL"


def test_worker_command_is_bound_to_durable_runtime_envelope(assurance_runtime):
    from api_fastapi.services import lite_security_assurance as assurance

    _insert_synthetic_session()
    run = assurance.create_run(
        suite_id="smoke",
        scenario_id="evidence-redaction",
        baseline_run_id=None,
        principal_id="assurance-test-principal",
        session_id="assurance-test-session",
        revision_sha="e" * 40,
        preflight_result={"status": "ready", "sanitized": True},
    )
    command = {
        "run_id": run["run_id"],
        "command_id": run["run_id"],
        "trace_id": run["run_id"],
        "suite_id": "smoke",
        "scenario_id": "evidence-redaction",
        "baseline_run_id": "",
        "profile": assurance.ASSURANCE_PROFILE,
        "purpose": assurance.ASSURANCE_PURPOSE,
        "target_scope": assurance.ASSURANCE_TARGET_SCOPE,
        "runtime_id": "tampered-runtime",
        "revision_sha": "e" * 40,
        "principal_id": "assurance-test-principal",
        "session_id": "assurance-test-session",
    }
    result = assurance.execute_run(command)
    assert result["status"] == "FAIL"
    assert result["failure_code"] == "worker_execution_failed"
