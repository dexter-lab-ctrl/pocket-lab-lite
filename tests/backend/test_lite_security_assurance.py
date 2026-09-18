from __future__ import annotations

import json
import importlib.util
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


def test_control_plane_ownership_requires_live_jetstream_worker_path(assurance_runtime, monkeypatch):
    from api_fastapi.services import lite_security_assurance as assurance

    monkeypatch.setattr(
        assurance.BUS,
        "status",
        lambda: {
            "connected": True,
            "jetstream_enabled": True,
            "durable_consumer_health": {
                "pocketlab_command_worker_v1": {"healthy": True}
            },
        },
    )
    result = assurance._control_plane_ownership()
    assert result["status"] == "PASS"
    assert result["checks"]["message_bus_connected"] is True
    assert result["checks"]["message_bus_jetstream"] is True
    assert result["checks"]["durable_worker_consumer"] is True

    monkeypatch.setattr(
        assurance.BUS,
        "status",
        lambda: {
            "connected": False,
            "jetstream_enabled": False,
            "durable_consumer_health": {},
        },
    )
    assert assurance._control_plane_ownership()["status"] == "FAIL"


def test_existing_security_deadline_bounds_child_timeout(assurance_runtime, monkeypatch):
    from api_fastapi.services import lite_security

    monkeypatch.setattr(lite_security.time, "time", lambda: 100.0)
    assert lite_security._assurance_command_timeout(105.0, 420) == 5
    assert lite_security._assurance_command_timeout(99.0, 420) == 0
    assert lite_security._assurance_command_timeout(None, 420) == 420


def test_existing_security_scan_receives_server_derived_deadline(assurance_runtime, monkeypatch):
    from api_fastapi.services import lite_security_assurance as assurance

    monkeypatch.setattr(
        assurance,
        "suite_def",
        lambda _suite_id: {"existing_security_profile": "quick"},
    )
    monkeypatch.setattr(assurance, "_security_conflict", lambda _profile: None)
    monkeypatch.setattr(
        assurance.lite_security,
        "build_and_reserve_scan_request",
        lambda **_kwargs: {"reservation": {"reserved": True}},
    )
    captured = {}

    def fake_scan(command):
        captured.update(command)
        return {
            "run": {
                "run_id": "security-" + "a" * 32,
                "status": "succeeded",
                "tool_results": {},
                "findings": [],
            },
            "findings": [],
            "evidence_refs": [],
        }

    monkeypatch.setattr(assurance.lite_security, "run_security_scan", fake_scan)
    result = assurance._run_existing_security_scan(
        "smoke", assurance_deadline_epoch=123.5
    )

    assert result["status"] == "PASS"
    assert captured["assurance_deadline_epoch"] == 123.5


def test_existing_security_scan_restarts_only_the_owned_child(assurance_runtime, monkeypatch):
    from api_fastapi.services import lite_security_assurance as assurance

    parent_id = "assurance-parent-" + "b" * 32
    monkeypatch.setattr(
        assurance,
        "suite_def",
        lambda _suite_id: {"existing_security_profile": "quick"},
    )
    monkeypatch.setattr(assurance, "_security_conflict", lambda _profile: None)
    monkeypatch.setattr(
        assurance.lite_security,
        "active_assurance_scan",
        lambda _profile, correlation_id: {
            "run_id": "security-old-child",
            "correlation_id": correlation_id,
            "status": "running",
        },
    )
    interrupted = []
    monkeypatch.setattr(
        assurance.lite_security,
        "interrupt_assurance_scan",
        lambda _profile, correlation_id: interrupted.append(correlation_id) or {
            "run_id": "security-old-child",
            "status": "failed",
        },
    )
    captured = {}

    def fake_reserve(**kwargs):
        captured.update(kwargs)
        return {"reservation": {"reserved": True}}

    monkeypatch.setattr(
        assurance.lite_security,
        "build_and_reserve_scan_request",
        fake_reserve,
    )

    def fake_scan(command):
        captured["command"] = command
        return {
            "run": {
                "run_id": command["run_id"],
                "status": "succeeded",
                "tool_results": {},
                "findings": [],
            },
            "findings": [],
            "evidence_refs": [],
        }

    monkeypatch.setattr(assurance.lite_security, "run_security_scan", fake_scan)
    result = assurance._run_existing_security_scan(
        "smoke",
        assurance_run_id=parent_id,
        assurance_deadline_epoch=123.5,
        worker_restarted=True,
    )

    assert interrupted == [parent_id]
    assert captured["correlation_id"] == parent_id
    assert captured["command"]["correlation_id"] == parent_id
    assert captured["command"]["assurance_deadline_epoch"] == 123.5
    assert result["status"] == "PASS"
    assert result["recovery"]["owned_child_interrupted"] is True


def test_suite_listing_exposes_registered_external_tool_contracts(assurance_runtime):
    from api_fastapi.services import lite_security_assurance as assurance

    result = assurance.list_suites()
    by_id = {item["id"]: item for item in result["suites"]}
    assert "bandit" in by_id["standard"]["registered_tools"]
    assert "schemathesis" in by_id["standard"]["external_tools"]
    assert "owasp-zap" in by_id["deep"]["external_tools"]
    assert "playwright-runtime" in by_id["standard"]["external_tools"]
    assert "pocketlab-runtime-360" in by_id["adversarial"]["external_tools"]
    assert by_id["standard"]["external_execution_lane"] == "dev_pc_live_runtime"
    assert "browser-origin-control-plane-bypass" in by_id["standard"]["external_scenarios"]
    assert "rate-limit-and-admission-resilience" in by_id["adversarial"]["external_scenarios"]
    assert "release-artifact-tamper" in by_id["deep"]["external_scenarios"]
    assert "pocketlab-security" in by_id["smoke"]["active_tools"]


def test_smoke_lease_covers_observed_phone_quick_scan(assurance_runtime):
    from api_fastapi.services import lite_security_assurance as assurance

    smoke = assurance.suite_def("smoke")
    assert smoke["target_seconds"] == 180
    assert smoke["maximum_seconds"] == 1200
    assert smoke["maximum_seconds"] > smoke["target_seconds"]


def test_terminal_security_result_cannot_be_overwritten_by_late_worker(assurance_runtime):
    from api_fastapi.services.lite_security_store import SecuritySQLiteRepository

    repo = SecuritySQLiteRepository()
    repo.reserve_scan(
        run_id="security-terminal-immutable",
        profile="quick",
        correlation_id="assurance-terminal-parent",
    )
    repo.fail_run(
        "security-terminal-immutable",
        failure_code="worker_restarted",
        failure_message="Worker restarted.",
        partial_results=True,
    )
    late = repo.complete_run("security-terminal-immutable", summary="Late success", score=100)
    assert late["ignored_terminal"] is True
    assert late["run"]["status"] == "failed"


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
    assert set(ready["registry_hashes"]) >= {"tools", "suites", "scenarios", "faults"}

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

    assert current_schema_version() == 36
    with read_connection() as conn:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert {
            "assurance_runs",
            "assurance_scenarios",
            "assurance_tool_results",
            "assurance_findings",
            "assurance_execution_checkpoints",
        }.issubset(tables)
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


def test_idempotent_admission_returns_the_existing_active_run(assurance_runtime):
    from api_fastapi.services import lite_security_assurance as assurance

    _insert_synthetic_session()
    kwargs = {
        "suite_id": "smoke",
        "scenario_id": "evidence-redaction",
        "baseline_run_id": None,
        "principal_id": "assurance-test-principal",
        "session_id": "assurance-test-session",
        "revision_sha": "1" * 40,
        "preflight_result": {"status": "ready", "sanitized": True},
    }
    first = assurance.create_run(**kwargs)
    second = assurance.create_run(**kwargs)
    assert second["run_id"] == first["run_id"]
    assert second["idempotent_reuse"] is True
    assert second["status"] == "QUEUED"


def test_full_suite_admission_preserves_all_registered_scenarios(assurance_runtime):
    from api_fastapi.services import lite_security_assurance as assurance

    _insert_synthetic_session()
    run = assurance.create_run(
        suite_id="smoke",
        scenario_id=None,
        baseline_run_id=None,
        principal_id="assurance-test-principal",
        session_id="assurance-test-session",
        revision_sha="e" * 40,
        preflight_result={"status": "ready", "sanitized": True},
    )

    assert run["scenario_id"] is None
    selected = assurance._scenario_items_for_suite(assurance.suite_def("smoke"), None)
    assert len(selected) == 8
    assert {str(item["id"]) for item in selected} >= {
        "harness-default-off",
        "security-projection",
        "threat-model-integrity",
    }


def test_assurance_router_publishes_one_fixed_command_for_duplicate_admission(assurance_runtime, monkeypatch):
    from api_fastapi.routers import security_assurance as router
    from api_fastapi.services import lite_security_assurance as assurance

    helper_path = Path("tests/backend/test_lite_harness.py").resolve()
    helper_spec = importlib.util.spec_from_file_location("lite_harness_test_helpers", helper_path)
    assert helper_spec and helper_spec.loader
    helpers = importlib.util.module_from_spec(helper_spec)
    helper_spec.loader.exec_module(helpers)
    monkeypatch.setenv("POCKETLAB_HARNESS_PROVISIONING_TOKEN", helpers.PROVISIONING_TOKEN)

    client = helpers._client()
    private, public = helpers._key()
    helpers._register(
        client,
        private,
        public,
        principal_id="assurance-router-runner",
        profiles=("security-assurance-runner",),
    )
    session, _ = helpers._start_session(
        client,
        private,
        principal_id="assurance-router-runner",
        profile="security-assurance-runner",
        purpose="security.assurance",
    )
    monkeypatch.setattr(
        assurance,
        "preflight",
        lambda *_args, **_kwargs: {
            "status": "ready",
            "revision": "a" * 40,
            "runtime_id": "assurance-test-runtime",
            "sanitized": True,
        },
    )
    published: list[dict] = []

    async def fake_publish(subject, event_type, command, *, trace_id=None):
        published.append({"subject": subject, "event_type": event_type, "command": command, "trace_id": trace_id})
        return {"command_id": command["run_id"]}

    monkeypatch.setattr(router, "submit_domain_command", fake_publish)
    headers = {"X-Pocket-Lab-Harness-Session": session["session_token"]}
    first = client.post("/api/lite/harness/security-assurance/runs", headers=headers, json={"suite_id": "smoke", "scenario_id": "evidence-redaction"})
    assert first.status_code == 202, first.text
    second = client.post("/api/lite/harness/security-assurance/runs", headers=headers, json={"suite_id": "smoke", "scenario_id": "evidence-redaction"})
    assert second.status_code == 202, second.text
    assert first.json()["run_id"] == second.json()["run_id"]
    assert second.json()["idempotent_reuse"] is True
    assert len(published) == 1
    assert published[0]["subject"] == assurance.ASSURANCE_SUBJECT
    assert "argv" not in published[0]["command"]
    assert "nats_subject" not in published[0]["command"]


def test_run_lease_checkpoint_and_resume_keep_one_run_id(assurance_runtime, monkeypatch):
    from api_fastapi.services import lite_security_assurance as assurance

    _insert_synthetic_session()
    revision = "2" * 40
    run = assurance.create_run(
        suite_id="smoke",
        scenario_id="evidence-redaction",
        baseline_run_id=None,
        principal_id="assurance-test-principal",
        session_id="assurance-test-session",
        revision_sha=revision,
        preflight_result={"status": "ready", "sanitized": True},
    )
    assurance.mark_running(run["run_id"], worker_instance_id="pocket-worker-test", worker_operation_id=run["run_id"])
    checkpoint = assurance._checkpoint(
        run["run_id"],
        unit_kind="scenario",
        unit_id="evidence-redaction",
        status="RUNNING",
        retry_safe=True,
        resume_supported=True,
        worker_instance_id="pocket-worker-test",
    )
    assert checkpoint["status"] == "RUNNING"
    assert checkpoint["retry_safe"] is True
    assert checkpoint["resume_supported"] is True
    assurance._set_terminal(
        run["run_id"],
        status="PARTIAL",
        summary={"status": "PARTIAL", "sanitized": True},
        report={"available": False, "sanitized": True},
        scenarios=[],
        tools=[],
        findings=[],
        failure_code="worker_interrupted",
    )
    monkeypatch.setattr(assurance, "_fixed_git_revision", lambda: {"revision": revision})
    resumed = assurance.resume_run(run["run_id"])
    assert resumed["run_id"] == run["run_id"]
    assert resumed["status"] == "QUEUED"
    assert resumed["resume_action"] == "requeued"
    already = assurance.resume_run(run["run_id"])
    assert already["resume_action"] == "already_running"
    events = assurance.run_events(run["run_id"], after_sequence=0)
    assert events["run"]["worker_operation_id"] == run["run_id"]
    assert events["checkpoints"]


def test_admitted_run_does_not_depend_on_expired_session(assurance_runtime, monkeypatch):
    from api_fastapi.db.connection import connection
    from api_fastapi.services import lite_security_assurance as assurance

    _insert_synthetic_session()
    revision = "3" * 40
    run = assurance.create_run(
        suite_id="smoke",
        scenario_id="evidence-redaction",
        baseline_run_id=None,
        principal_id="assurance-test-principal",
        session_id="assurance-test-session",
        revision_sha=revision,
        preflight_result={"status": "ready", "sanitized": True},
    )
    with connection() as conn:
        conn.execute(
            "UPDATE harness_sessions SET expires_at=? WHERE harness_session_id=?",
            ("2000-01-01T00:00:00Z", "assurance-test-session"),
        )
    monkeypatch.setattr(assurance, "preflight", lambda *_args, **_kwargs: {"status": "ready", "sanitized": True})
    monkeypatch.setattr(assurance, "_inventory_tools", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(assurance.optimization, "resource_snapshot", lambda: {})
    result = assurance.execute_run({
        "run_id": run["run_id"],
        "command_id": run["run_id"],
        "trace_id": run["run_id"],
        "suite_id": "smoke",
        "scenario_id": "evidence-redaction",
        "baseline_run_id": "",
        "profile": assurance.ASSURANCE_PROFILE,
        "purpose": assurance.ASSURANCE_PURPOSE,
        "target_scope": assurance.ASSURANCE_TARGET_SCOPE,
        "runtime_id": run["runtime_id"],
        "revision_sha": revision,
        "principal_id": "assurance-test-principal",
        "session_id": "assurance-test-session",
    })
    assert result["status"] == "PASS"
    assert result["run_id"] == run["run_id"]


def test_expired_execution_lease_is_partial_and_never_passes(assurance_runtime, monkeypatch):
    from api_fastapi.db.connection import connection
    from api_fastapi.services import lite_security_assurance as assurance

    _insert_synthetic_session()
    revision = "4" * 40
    run = assurance.create_run(
        suite_id="smoke",
        scenario_id="evidence-redaction",
        baseline_run_id=None,
        principal_id="assurance-test-principal",
        session_id="assurance-test-session",
        revision_sha=revision,
        preflight_result={"status": "ready", "sanitized": True},
    )
    with connection() as conn:
        conn.execute(
            "UPDATE assurance_runs SET run_deadline=?,updated_at=?,heartbeat_at=? WHERE run_id=?",
            ("2000-01-01T00:00:00Z", "2000-01-01T00:00:00Z", "2000-01-01T00:00:00Z", run["run_id"]),
        )
    monkeypatch.setattr(assurance, "preflight", lambda *_args, **_kwargs: {"status": "ready", "sanitized": True})
    monkeypatch.setattr(assurance, "_inventory_tools", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(assurance.optimization, "resource_snapshot", lambda: {})
    result = assurance.execute_run({
        "run_id": run["run_id"],
        "command_id": run["run_id"],
        "trace_id": run["run_id"],
        "suite_id": "smoke",
        "scenario_id": "evidence-redaction",
        "baseline_run_id": "",
        "profile": assurance.ASSURANCE_PROFILE,
        "purpose": assurance.ASSURANCE_PURPOSE,
        "target_scope": assurance.ASSURANCE_TARGET_SCOPE,
        "runtime_id": run["runtime_id"],
        "revision_sha": revision,
        "principal_id": "assurance-test-principal",
        "session_id": "assurance-test-session",
    })
    assert result["status"] == "PARTIAL"
    assert result["summary"]["run_deadline_exceeded"] is True
    scenarios = assurance.list_scenarios(run["run_id"])
    assert scenarios[0]["failure_code"] == "run_deadline_exceeded"


def test_principal_revocation_marks_active_assurance_run_for_cancellation(assurance_runtime):
    from api_fastapi.services import lite_harness
    from api_fastapi.services import lite_security_assurance as assurance

    _insert_synthetic_session()
    run = assurance.create_run(
        suite_id="smoke",
        scenario_id="evidence-redaction",
        baseline_run_id=None,
        principal_id="assurance-test-principal",
        session_id="assurance-test-session",
        revision_sha="5" * 40,
        preflight_result={"status": "ready", "sanitized": True},
    )
    revoked = lite_harness.revoke_principal("assurance-test-principal", reason_code="qualification_cleanup")
    assert revoked["active_assurance_runs_cancelled"] == 1
    assert assurance.get_run(run["run_id"])["cancel_requested"] is True


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


def test_terminal_assurance_releases_only_its_orphaned_security_child(
    assurance_runtime, monkeypatch
):
    from api_fastapi.services import lite_security_assurance as assurance
    from api_fastapi.services import lite_security_store

    monkeypatch.setenv("POCKETLAB_LITE_SECURITY_STORE_MODE", "sqlite")
    _insert_synthetic_session()
    parent = assurance.create_run(
        suite_id="smoke",
        scenario_id="evidence-redaction",
        baseline_run_id=None,
        principal_id="assurance-test-principal",
        session_id="assurance-test-session",
        revision_sha="1" * 40,
        preflight_result={"status": "ready", "sanitized": True},
    )
    assurance.record_blocked_run(
        parent["run_id"],
        failure_code="preflight_blocked",
        preflight_result={"status": "blocked", "sanitized": True},
    )
    repository = lite_security_store.SecuritySQLiteRepository()
    reserved = repository.reserve_scan(
        run_id="security-orphaned-child",
        profile="quick",
        correlation_id=parent["run_id"],
    )
    assert reserved.reserved is True

    recovered = assurance.reconcile_stale_runs()

    assert recovered["orphaned_security_child_count"] == 1
    assert recovered["orphaned_security_children"][0]["assurance_run_id"] == parent[
        "run_id"
    ]
    child = repository.get_run("security-orphaned-child")
    assert child["status"] == "failed"
    assert child["failure_code"] == "assurance_orphaned_child_reconciled"
    assert repository.get_active_scan() is None


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
