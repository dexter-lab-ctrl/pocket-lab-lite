from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from pocket_lab_test_utils import ensure_runtime_path, isolated_state_dir


@pytest.fixture()
def controls_runtime(tmp_path, monkeypatch):
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
    monkeypatch.setenv("POCKETLAB_HARNESS_FAULT_CONTROL", "0")
    monkeypatch.setenv("POCKETLAB_HARNESS_RUNTIME_ID", "assurance-controls-runtime")
    reset_sqlite_path_cache()
    SQLITE_READS.invalidate()
    deps.core.SETTINGS = deps.core.Settings(state_dir=state)
    apply_migrations()
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    with __import__("sqlite3").connect(state / "pocketlab-lite.sqlite3") as conn:
        conn.execute(
            """INSERT INTO synthetic_principals(
                   principal_id,principal_type,principal_class,display_name,enabled,
                   environment_scope,target_scope,allowed_profiles_json,default_profile,
                   algorithm,public_key,public_key_fingerprint,created_at,expires_at
               ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "controls-principal", "synthetic_machine", "qualification", "Assurance controls principal", 1,
                "qualification", "local_server_host_only", json.dumps(["security-assurance-runner"]),
                "security-assurance-runner", "ed25519", "test-public-key", "sha256:controls-public-key",
                now, (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
            ),
        )
    yield state

    from api_fastapi.services import lite_assurance_faults

    lite_assurance_faults._USED_FAULTS.clear()


def _assurance_context(*, capabilities: list[str] | None = None) -> dict:
    return {
        "actor": {
            "identity_id": "controls-principal",
            "type": "synthetic_machine",
            "display_name": "Assurance controls principal",
        },
        "session": {"authenticated": True, "auth_method": "harness_session"},
        "auth_method": "harness_session",
        "authorization": {
            "role": None,
            "owner_authority": False,
            "membership_active": False,
            "identity_class": "synthetic_machine",
            "enterprise_enabled": False,
        },
        "harness": {
            "enabled": True,
            "session_id": "hs-controls",
            "principal_id": "controls-principal",
            "principal_class": "qualification",
            "profile": "security-assurance-runner",
            "purpose": "security.assurance",
            "capabilities": capabilities or [
                "security.assurance.policy_sync",
                "security.assurance.fault_control",
            ],
            "target_scope": "local_server_host_only",
            "runtime_id": "assurance-controls-runtime",
            "destructive_allowed": False,
            "qualification_environment": True,
        },
    }


def _install_durable_stale_revision() -> str:
    from api_fastapi.db.connection import begin_immediate, connection

    revision = "plr-00000000000000000000000000000000"
    now = "2026-09-14T00:00:00Z"
    params = {"admin_device_remove_approval": 1, "operator_device_remove_approval": 1}
    with connection() as conn, begin_immediate(conn) as tx:
        tx.execute(
            """INSERT INTO policy_revisions(
                   revision_id,parent_revision_id,template_id,template_version,
                   canonical_parameters_json,manifest_json,content_hash,created_by_human_id,
                   created_at,validation_status,validated_at,validation_reason_code,lifecycle_status,
                   activated_at,change_summary
               ) VALUES (?,NULL,'enterprise_governance','1',?,?,?,NULL,?,
                         'valid',?,'','active',?,'Stale test policy')""",
            (
                revision,
                json.dumps(params, sort_keys=True, separators=(",", ":")),
                json.dumps({"files": [], "candidate_hash": "old"}, sort_keys=True, separators=(",", ":")),
                "0" * 64,
                now,
                now,
                now,
            ),
        )
        tx.execute(
            """INSERT INTO policy_runtime_state(
                   state_id,active_revision_id,known_good_revision_id,updated_at,updated_by_operation_id
               ) VALUES (1,?,?,?,NULL)""",
            (revision, revision, now),
        )
    return revision


def test_fault_registry_is_fixed_and_complete(controls_runtime):
    from api_fastapi.services import lite_assurance_faults

    result = lite_assurance_faults.validate_registry()
    assert {item["id"] for item in result["faults"]} == {
        "worker_restart_once",
        "nats_restart_once",
        "opa_restart_once",
    }
    assert {item["service_name"] for item in result["faults"]} == {
        "pocket-worker",
        "pocket-nats",
        "pocket-opa",
    }
    with pytest.raises(lite_assurance_faults.FaultControlError) as error:
        lite_assurance_faults.fault_def("shell_execute")
    assert error.value.reason_code == "fault_unknown"


def test_fault_control_requires_explicit_flag_and_confirmation(controls_runtime, monkeypatch):
    from api_fastapi.services import lite_assurance_faults

    with pytest.raises(lite_assurance_faults.FaultControlError) as disabled:
        lite_assurance_faults.execute_fault(
            fault_id="worker_restart_once",
            auth_context=_assurance_context(),
            confirm=True,
        )
    assert disabled.value.reason_code == "fault_control_disabled"

    monkeypatch.setenv("POCKETLAB_HARNESS_FAULT_CONTROL", "1")
    with pytest.raises(lite_assurance_faults.FaultControlError) as unconfirmed:
        lite_assurance_faults.execute_fault(
            fault_id="worker_restart_once",
            auth_context=_assurance_context(),
            confirm=False,
        )
    assert unconfirmed.value.reason_code == "fault_confirmation_required"


def test_worker_fault_uses_supervisor_fixed_service_and_one_use(controls_runtime, monkeypatch):
    from supervisors import pocketlab_core_supervisor
    from api_fastapi.services import lite_assurance_faults

    class FakeSupervisor:
        def restart_pm2(self, service, reason):
            assert service == "pocket-worker"
            assert reason == "security_assurance_fault:worker_restart_once"
            return {"acted": True, "restart_generation": 7}

        def collect(self):
            return {
                "services": {"pocket-worker": "online"},
                "checks": {
                    "api_nats_connected": True,
                    "nats_tcp_reachable": True,
                    "api_http_reachable": True,
                },
            }

    monkeypatch.setenv("POCKETLAB_HARNESS_FAULT_CONTROL", "1")
    monkeypatch.setattr(pocketlab_core_supervisor, "LiteCoreSupervisor", FakeSupervisor)
    result = lite_assurance_faults.execute_fault(
        fault_id="worker_restart_once",
        auth_context=_assurance_context(),
        confirm=True,
    )
    assert result["status"] == "PASS"
    assert result["acted"] is True
    assert result["recovery"]["healthy"] is True
    assert result["sanitized"] is True

    with pytest.raises(lite_assurance_faults.FaultControlError) as replay:
        lite_assurance_faults.execute_fault(
            fault_id="worker_restart_once",
            auth_context=_assurance_context(),
            confirm=True,
        )
    assert replay.value.reason_code == "fault_already_used"


def test_assurance_policy_sync_queues_qualification_principal_without_owner(controls_runtime):
    from api_fastapi.db.connection import connection
    from api_fastapi.services import lite_policy_source_sync

    _install_durable_stale_revision()
    result = lite_policy_source_sync.request_assurance_source_sync(
        auth_context=_assurance_context(),
        correlation_id="controls-policy-sync",
    )
    assert result["status"] == "queued"
    assert result["accepted"] is True
    with connection() as conn:
        operation = conn.execute(
            "SELECT requested_by_human_id,requested_by_principal_type,requested_by_principal_id,state FROM policy_activation_operations"
        ).fetchone()
        audit = conn.execute(
            "SELECT event_type,capability FROM harness_audit_events WHERE event_type='assurance_policy_source_sync_requested'"
        ).fetchone()
    assert operation["requested_by_human_id"] is None
    assert operation["requested_by_principal_type"] == "qualification"
    assert operation["requested_by_principal_id"] == "controls-principal"
    assert operation["state"] == "pending"
    assert audit["capability"] == "security.assurance.policy_sync"


def test_negative_auth_probe_is_fixed_and_never_sends_authority_material(controls_runtime, monkeypatch):
    from api_fastapi.services import lite_security_assurance as assurance

    observed = []

    def fake_probe(*, port, path, method="GET", body=None, headers=None):
        observed.append({"port": port, "path": path, "method": method, "body": body, "headers": headers})
        return {
            "status_code": 401,
            "body": {"json": True, "keys": ["reason_code", "sanitized"], "reason_code": "harness_session_invalid", "sanitized": True},
            "duration_ms": 1,
        }

    monkeypatch.setattr(assurance, "_http_probe", fake_probe)
    result = assurance._negative_auth_probes()

    assert result["status"] == "PASS"
    assert result["probe_count"] == 10
    assert result["rejected_count"] == 10
    assert result["valid_authority_material_sent"] is False
    assert all(item["status_code"] == 401 for item in result["results"])
    assert all(call["path"].startswith("/") for call in observed)
    assert all(call["path"].find("..") == -1 for call in observed)
    assert not any("command" in str(call).casefold() for call in observed)


def test_adversarial_registry_contains_independent_negative_probe_scenario(controls_runtime):
    from api_fastapi.services import lite_security_assurance as assurance

    definition = assurance.scenario_def("adversarial-negative-auth-probes")
    assert definition["execution"] == "fixed_negative_auth_probes"
    assert definition["safety_class"] == "SAFE_ACTIVE"
    assert definition["suites"] == ["adversarial"]
    assert "standard" not in definition["suites"]


def test_policy_sync_request_rejects_caller_supplied_policy_fields():
    from api_fastapi.routers.security_assurance import PolicySyncRequest
    from pydantic import ValidationError

    assert PolicySyncRequest.model_validate({})
    with pytest.raises(ValidationError):
        PolicySyncRequest.model_validate({"revision": "caller-selected"})


def test_assurance_policy_sync_rejects_owner_or_production_context(controls_runtime, monkeypatch):
    from api_fastapi.services import lite_policy_source_sync

    owner_context = _assurance_context()
    owner_context["authorization"]["role"] = "Owner"
    with pytest.raises(lite_policy_source_sync.PolicySourceSyncError) as owner:
        lite_policy_source_sync.request_assurance_source_sync(auth_context=owner_context)
    assert owner.value.reason_code == "assurance_policy_sync_denied"

    monkeypatch.setenv("POCKETLAB_ENVIRONMENT", "production")
    with pytest.raises(lite_policy_source_sync.PolicySourceSyncError) as production:
        lite_policy_source_sync.request_assurance_source_sync(auth_context=_assurance_context())
    assert production.value.reason_code in {"assurance_policy_sync_disabled", "assurance_policy_sync_denied"}


def test_caddy_probe_requires_harness_namespace_denial(controls_runtime, monkeypatch):
    from api_fastapi.services import lite_security_assurance as assurance

    http_paths: list[tuple[str, str]] = []

    def fake_http(*, port, path, method="GET", body=None, headers=None):
        http_paths.append((path, method))
        if path.startswith("/api/lite/harness"):
            return {"status_code": 404, "body": {}, "duration_ms": 1}
        return {"status_code": 200, "body": {}, "duration_ms": 1}

    def fake_stream(*, port, path, headers=None):
        return {"status_code": 200, "response_harness_marker_echoed": False, "duration_ms": 1}

    def fake_websocket(*, port, path, headers=None):
        return {"status_code": 101, "handshake_accepted": True, "response_harness_marker_echoed": False}

    monkeypatch.setattr(assurance, "_http_probe", fake_http)
    monkeypatch.setattr(assurance, "_stream_probe", fake_stream)
    monkeypatch.setattr(assurance, "_websocket_probe", fake_websocket)

    result = assurance._caddy_probe()

    assert result["status"] == "PASS"
    assert result["harness_namespace_denied"] is True
    assert ("/api/lite/harness/bootstrap/grants", "POST") in http_paths
    assert ("/api/lite/harness/bootstrap/challenge", "POST") in http_paths
    assert ("/api/lite/harness/bootstrap/complete", "POST") in http_paths
    assert ("/api/lite/harness/session", "POST") in http_paths
