"""System Health incident, membership and controlled-recovery behavior."""
from __future__ import annotations

from contextlib import contextmanager
import asyncio
from pathlib import Path
import sqlite3

import pytest

from pocket_lab_test_utils import ensure_runtime_path


@pytest.fixture()
def health(tmp_path, monkeypatch):
    ensure_runtime_path()
    from api_fastapi.services import lite_system_health as health_engine
    db = tmp_path / "health.sqlite3"
    schema_root = Path(__file__).parents[2] / "pocket-lab-final-structure/runtime/api_fastapi/db/schema"
    with sqlite3.connect(db) as conn:
        # Use the actual registry/receipt DDL; skip legacy backfill in this isolated fixture.
        registry_ddl = (schema_root / "0022_device_durable_enrollment.sql").read_text(encoding="utf-8")
        conn.executescript(registry_ddl.split("-- Backfill only")[0])
        conn.executescript((schema_root / "0043_system_health_intelligence.sql").read_text(encoding="utf-8"))
        conn.executescript((schema_root / "0044_system_health_audit.sql").read_text(encoding="utf-8"))
        conn.executescript((schema_root / "0045_system_health_enrollment_generation.sql").read_text(encoding="utf-8"))
        conn.executescript((schema_root / "0046_system_health_recovery_requests.sql").read_text(encoding="utf-8"))
        conn.executescript((schema_root / "0048_system_health_owner_recovery_evidence.sql").read_text(encoding="utf-8"))

    def connect():
        conn = sqlite3.connect(db, isolation_level=None)
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def writing():
        conn = connect()
        try:
            yield conn
        finally:
            conn.close()

    monkeypatch.setattr(health_engine, "connection", writing)
    monkeypatch.setattr(health_engine, "open_fast_read_connection", connect)
    return health_engine


def observed_nats(status="degraded", revision=1):
    return {"status": status, "generation": revision, "connected": status == "healthy",
            "durable_consumer_health": {}, "sanitized": True}


def test_incident_is_persisted_deduplicated_and_reopened(health):
    assert health.ingest_projection("system.nats_remote", observed_nats()) == 1
    original = health.incidents()["items"][0]
    assert original["state"] == "detected"
    assert original["incident_id"].startswith("health-")
    assert health.ingest_projection("system.nats_remote", observed_nats()) == 0
    assert len(health.incidents()["items"]) == 1
    assert health.ingest_projection("system.nats_remote", observed_nats("healthy", 2)) == 1
    assert health.incident(original["incident_id"])["state"] == "resolved"
    assert health.ingest_projection("system.nats_remote", observed_nats("degraded", 3)) == 1
    reopened = health.incident(original["incident_id"])
    assert reopened["generation"] == original["generation"] + 1
    assert reopened["recurrence_count"] == 1
    assert reopened["state"] == "detected"


def test_unknown_does_not_recover_unhealthy_incident(health):
    health.ingest_projection("system.nats_remote", observed_nats())
    health.ingest_projection("system.nats_remote", observed_nats("unknown", 2))
    assert len(health.incidents()["items"]) == 1
    assert health.incidents()["items"][0]["state"] != "resolved"


def test_diagnosis_is_truthful_and_persisted(health):
    health.ingest_projection("system.nats_remote", observed_nats())
    incident_id = health.incidents()["items"][0]["incident_id"]
    result = health.record_diagnosis(incident_id)
    assert result["recorded"]
    assert result["verified_cause"] is None
    assert result["repair_available"] is False
    assert health.decision_history(incident_id)["diagnoses"][0]["diagnosis_id"] == result["diagnosis_id"]


def test_repair_denial_audit_is_idempotent_and_never_executes(health):
    health.ingest_projection("system.nats_remote", observed_nats())
    problem = health.incidents()["items"][0]
    ident = "immutable-client-request-000001"
    decision = health.record_repair_denial(
        problem["incident_id"], "runtime.consumer.reconnect", problem["generation"], ident, "human"
    )
    assert decision["allowed"] is False
    assert decision["execution"] == "not_started"
    repeat = health.record_repair_denial(
        problem["incident_id"], "runtime.consumer.reconnect", problem["generation"], ident, "human"
    )
    assert repeat["idempotent_replay"] is True
    denials = health.decision_history(problem["incident_id"])["repair_denials"]
    assert len(denials) == 1
    assert ident not in str(denials)


def test_stale_preflight_blocks_and_unknown_never_means_healthy(health, monkeypatch):
    health.ingest_projection("system.nats_remote", observed_nats())
    problem = health.incidents()["items"][0]
    with health.connection() as conn:
        conn.execute("UPDATE lite_system_health_observations SET observed_at='2001-01-01T00:00:00Z'")
        conn.execute("UPDATE lite_system_health_incidents SET last_seen_at='2001-01-01T00:00:00Z'")
    preflight = health.repair_preflight(problem["incident_id"], "app.repair", problem["generation"])
    assert "evidence_not_current" in preflight["reasons"]
    assert preflight["allowed"] is False
    assert health.summary()["status"] == "unknown"


def test_forecast_and_ai_claims_remain_disabled(health):
    assert health.resource_intelligence()["forecast"] == "not_enough_information"
    assert health.knowledge()["ai_provider"] == "disabled"
    assert health.policy()["engine_auto_repair"] is False


def test_anonymous_system_health_incident_read_is_denied():
    ensure_runtime_path()
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from api_fastapi.routers.lite_system_health import router

    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        response = client.get("/api/lite/system-health/summary")
        assert response.status_code == 401
        assert response.json()["detail"]["reason_code"] == "authentication_required"
        attempt = client.post(
            "/api/lite/system-health/incidents/health-111111111111111111111111/diagnose"
        )
        assert attempt.status_code == 401


def test_recovery_router_is_backend_governed_and_sanitizes_harness_denial(monkeypatch):
    ensure_runtime_path()
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from api_fastapi.routers import lite_system_health as module
    from api_fastapi.services import lite_harness

    app = FastAPI()
    app.include_router(module.router)
    context = {
        "actor": {"identity_id": "qualification-owner", "type": "qualification"},
        "session": {"authenticated": True},
    }
    found = {
        "incident_id": "health-111111111111111111111111", "generation": 1,
        "enrollment_generation": 0, "target_id": "jetstream", "source": "nats",
    }
    allowed_preflight = {"allowed": True, "reasons": [], "risk_class": "A"}
    monkeypatch.setattr(module.deps, "require_auth", lambda request, write=False: context)
    monkeypatch.setattr(module.health, "incident", lambda incident_id: found)
    monkeypatch.setattr(module.health, "repair_preflight", lambda *args: allowed_preflight)
    policy_inputs = []

    def allow_policy(**kwargs):
        policy_inputs.append(kwargs)
        return {
            "allow": True, "reason_code": "qualification_owner_system_health_recovery",
            "policy_revision": "test-policy", "decision_id": "decision-1",
        }

    monkeypatch.setattr(module.lite_policy_opa, "evaluate_authorization", allow_policy)
    monkeypatch.setattr(module.health, "admit_controlled_recovery", lambda *args, **kwargs: {
        "request": {"request_id": "recovery-1", "status": "admitted"}, "recorded": True,
    })
    with TestClient(app) as client:
        payload = {
            "operation_id": "runtime.consumer.reconnect", "expected_generation": 1,
            "idempotency_key": "router-recovery-key-0001", "confirm": False,
        }
        monkeypatch.setattr(module.lite_harness, "enforce_capability", lambda *args, **kwargs: None)
        response = client.post("/api/lite/system-health/incidents/health-111111111111111111111111/repair", json=payload)
        assert response.status_code == 202
        assert response.json()["status"] == "admitted"
        assert policy_inputs[0]["target"]["operation_id"] == "runtime.consumer.reconnect"
        assert policy_inputs[0]["target"]["incident_generation"] == 1
        assert "state" not in policy_inputs[0]["target"]

        def reject(*_args, **_kwargs):
            raise lite_harness.HarnessError("harness_capability_missing", "capability rejected", status_code=403)

        monkeypatch.setattr(module.lite_harness, "enforce_capability", reject)
        denied = client.post("/api/lite/system-health/incidents/health-111111111111111111111111/repair", json=payload)
        assert denied.status_code == 403
        assert denied.json()["detail"] == {
            "status": "denied", "reason_code": "harness_capability_missing", "summary": "capability rejected",
        }


# P4 qualification helpers and executed regression coverage.
def test_fresh_vs_saved_incidents_are_counted_separately(health):
    assert health.ingest_projection("system.nats_remote", observed_nats("degraded", 1)) == 1
    initial = health.summary()
    assert initial["current_problems"] == 1
    assert initial["saved_problems"] == 0
    assert initial["active_problems"] == 1  # legacy unresolved count remains stable
    assert health.incidents()["items"][0]["concern_state"] == "current_concern"

    # A newer unknown observation cannot remove the unresolved lifecycle record.
    assert health.ingest_projection("system.nats_remote", observed_nats("unknown", 2)) == 0
    newer = health.summary()
    assert newer["current_problems"] == 0
    assert newer["saved_problems"] == 1
    assert newer["active_problems"] == 1
    assert newer["status"] == "unknown"
    assert health.incidents()["items"][0]["concern_state"] == "saved_concern"


def test_stale_critical_incident_is_not_current_or_resolved(health):
    health.ingest_projection("system.nats_remote", observed_nats("unavailable"))
    original = health.incidents()["items"][0]
    assert original["severity"] == "critical"
    with health.connection() as conn:
        conn.execute(
            "UPDATE lite_system_health_observations SET observed_at='2001-01-01T00:00:00Z'"
        )
        conn.execute(
            "UPDATE lite_system_health_incidents SET last_seen_at='2001-01-01T00:00:00Z'"
        )
    current = health.summary()
    assert current["current_problems"] == 0
    assert current["saved_problems"] == 1
    assert current["critical_problems"] == 1
    assert current["unresolved_critical_problems"] == 1
    assert current["status"] == "unknown"
    incident = health.incident(original["incident_id"])
    assert incident["state"] == "detected"
    assert incident["generation"] == original["generation"]
    assert incident["concern_state"] == "saved_concern"


@pytest.mark.parametrize("domain,field", [
    ("system.agent", "items"),
    ("system.supervisor", "items"),
    ("system.processes", "items"),
    ("system.telemetry_thresholds", "devices"),
])
def test_malformed_projection_collection_cannot_create_incidents(health, domain, field):
    for invalid in ("abc", {"3": {"device_id": "3"}}, 5, None):
        assert health.ingest_projection(domain, {field: invalid, "generation": 1}) == 0
    assert health.incidents()["items"] == []


def test_short_but_explicit_valid_device_identity_is_preserved(health):
    enroll(health, "3")
    payload = {"items": [{"device_id": "3", "connection_state": "offline",
                          "command_deliverable": False}], "generation": 1}
    assert health.ingest_projection("system.agent", payload) == 1
    assert health.incidents()["items"][0]["target_id"] == "3"
    assert health.incidents()["items"][0]["concern_state"] == "current_concern"
    assert health.ingest_projection("system.agent", {"items": [
        {"device_id": "../../private", "connection_state": "offline"},
        {"device_id": 3, "connection_state": "offline"},
        {"device_id": "", "connection_state": "offline"},
    ], "generation": 2}) == 0


def test_malformed_consumer_names_are_not_converted_to_fake_targets(health):
    payload = {"status": "healthy", "generation": 1,
               "durable_consumer_health": {
                   "consumer-safe": {"healthy": False},
                   "../../unsafe": {"healthy": False},
                   3: {"healthy": False},
               }}
    assert health.ingest_projection("system.nats_remote", payload) == 1
    assert health.incidents()["items"][0]["target_id"] == "consumer:consumer-safe"


def test_observed_healthy_transition_is_not_verified_repair(health):
    health.ingest_projection("system.nats_remote", observed_nats("degraded", 1))
    incident_id = health.incidents()["items"][0]["incident_id"]
    health.ingest_projection("system.nats_remote", observed_nats("healthy", 2))
    item = health.incident(incident_id)
    assert item["state"] == "resolved"
    assert item["concern_state"] == "resolved_observation"
    assert health.summary()["recent_verified_recoveries"] == 0
    assert health.policy()["engine_auto_repair"] is False
    assert health.repair_preflight(incident_id, "runtime.consumer.reconnect",
                                   item["generation"])["allowed"] is False


# P4 qualification coverage.
def enroll(health, device_id, *, protected=False, removal_status="active"):
    with health.connection() as conn:
        conn.execute(
            "INSERT INTO device_enrollment_registry(device_id,device_name,enrolled_at,updated_at,"
            "removal_status,protected_server_host) VALUES (?,?,?,?,?,?)",
            (device_id, device_id, health._now(), health._now(), removal_status, int(protected)),
        )


def observe_device(health, device_id, revision=1, state="offline"):
    return health.ingest_projection("system.agent", {
        "generation": revision, "items": [{"device_id": device_id, "connection_state": state}],
    })


@pytest.mark.parametrize("removal_status", ["retired", "removed"])
def test_p4_membership_history_and_late_event(health, removal_status):
    enroll(health, "secondary")
    enroll(health, "still-enrolled")
    assert observe_device(health, "secondary") == 1
    assert observe_device(health, "still-enrolled") == 1
    original = next(i for i in health.incidents()["items"] if i["target_id"] == "secondary")
    with health.connection() as conn:
        conn.execute("UPDATE device_enrollment_registry SET removal_status=?, retired_at=? WHERE device_id=?",
                     (removal_status, health._now(), "secondary"))
    assert observe_device(health, "secondary", revision=2, state="online") == 0
    assert health.summary()["current_problems"] == 1
    assert health.summary()["historical_device_records"] == 1
    page = health.incidents(limit=1)
    assert page["items"][0]["target_id"] == "still-enrolled"
    assert page["next_offset"] is None
    historical = health.incident(original["incident_id"])
    assert historical["state"] == original["state"]
    assert historical["generation"] == original["generation"]
    assert historical["concern_state"] == "historical_record"
    assert historical["current_monitoring"] is False
    assert historical["repair_available"] is False
    assert any(i["incident_id"] == original["incident_id"] for i in health.history()["items"])
    assert all(i["target_id"] != "secondary" for i in health.dependency_graph()["nodes"])
    assert all(i["target_id"] != "secondary" for i in health.knowledge()["recurring_components"])
    preflight = health.repair_preflight(original["incident_id"], "device.agent.recover", original["generation"])
    assert "device_no_longer_enrolled" in preflight["reasons"]
    assert preflight["allowed"] is False


def test_p4_unknown_identity_cannot_create_current_incident(health):
    assert observe_device(health, "unknown") == 0
    assert health.incidents()["items"] == []


def test_p4_protected_host_inconsistent_retirement_is_not_hidden(health):
    enroll(health, "host", protected=True)
    observe_device(health, "host")
    with health.connection() as conn:
        conn.execute("UPDATE device_enrollment_registry SET removal_status='removed' WHERE device_id='host'")
    item = health.incidents()["items"][0]
    assert item["membership_state"] == "protected_conflict"
    assert item["concern_state"] == "saved_concern"
    assert health.summary()["status"] == "unknown"
    assert "protected_host_membership_conflict" in health.repair_preflight(
        item["incident_id"], "device.agent.recover", item["generation"])["reasons"]


def test_p4_resources_filter_removed_device_and_preserve_shared_signal(health):
    enroll(health, "old")
    enroll(health, "new")
    health.ingest_projection("system.telemetry_thresholds", {"generation": 1, "devices": [
        {"device_id": "old", "status": "degraded"},
        {"device_id": "new", "status": "degraded"},
    ]})
    health.ingest_projection("system.storage_pressure", {"generation": 1, "status": "degraded"})
    with health.connection() as conn:
        conn.execute("UPDATE device_enrollment_registry SET removal_status='removed' WHERE device_id='old'")
    targets = {r["target_id"] for r in health.resource_intelligence()["signals"]}
    assert targets == {"new", "storage"}


def test_p4_enrollment_generation_fences_late_observations(health):
    enroll(health, "generation-device")
    assert observe_device(health, "generation-device", revision=1) == 1
    previous = health.incidents()["items"][0]
    with health.connection() as conn:
        conn.execute(
            "UPDATE device_enrollment_registry SET enrollment_generation=2 WHERE device_id=?",
            ("generation-device",),
        )
    # The new generation is a distinct current incident. The prior incident
    # remains a historical record and cannot authorize a current repair.
    assert observe_device(health, "generation-device", revision=2, state="offline") == 1
    items = health.incidents(include_resolved=True, limit=10)["items"]
    current = [item for item in items if item["current_monitoring"]]
    historical = health.incident(previous["incident_id"])
    assert len(current) == 1
    assert current[0]["enrollment_generation"] == 2
    assert historical["concern_state"] == "historical_record"
    assert historical["current_monitoring"] is False
    assert health.repair_preflight(previous["incident_id"], "device.agent.recover", previous["generation"])["allowed"] is False


def test_p4_controlled_recovery_is_default_off(health):
    health.ingest_projection("system.nats_remote", observed_nats())
    item = health.incidents()["items"][0]
    preflight = health.repair_preflight(item["incident_id"], "runtime.consumer.reconnect", item["generation"])
    assert preflight["allowed"] is False
    assert "system_health_recovery_disabled" in preflight["reasons"]


def test_p4_controlled_recovery_preflight_rejects_non_nats_target(health, monkeypatch):
    monkeypatch.setenv("POCKETLAB_ENVIRONMENT", "qualification")
    monkeypatch.setenv("POCKETLAB_SYSTEM_HEALTH_RECOVERY_ADAPTER", "1")
    assert health.ingest_projection("system.health", {
        "status": "degraded", "generation": 1,
        "components": {"supervisor": "degraded"}, "sanitized": True,
    }) == 1
    item = health.incidents()["items"][0]
    preflight = health.repair_preflight(
        item["incident_id"], "runtime.consumer.reconnect", item["generation"]
    )
    assert preflight["allowed"] is False
    assert "target_not_allowlisted" in preflight["reasons"]


def test_p4_controlled_recovery_is_actor_bound_and_idempotent(health, monkeypatch):
    monkeypatch.setenv("POCKETLAB_ENVIRONMENT", "qualification")
    monkeypatch.setenv("POCKETLAB_SYSTEM_HEALTH_RECOVERY_ADAPTER", "1")
    health.ingest_projection("system.nats_remote", observed_nats())
    item = health.incidents()["items"][0]
    decision = {"allow": True, "reason_code": "qualification_owner_system_health_recovery", "policy_revision": "test-policy", "decision_id": "decision-test"}
    context = {"actor": {"identity_id": "qualification-owner", "type": "qualification"}}
    first = health.admit_controlled_recovery(
        item["incident_id"], "runtime.consumer.reconnect", item["generation"],
        "recovery-idempotency-key-0001", confirm=False, auth_context=context, decision=decision,
    )
    assert first["request"]["status"] == "admitted"
    replay = health.admit_controlled_recovery(
        item["incident_id"], "runtime.consumer.reconnect", item["generation"],
        "recovery-idempotency-key-0001", confirm=False, auth_context=context, decision=decision,
    )
    assert replay["idempotent_replay"] is True
    conflict = health.admit_controlled_recovery(
        item["incident_id"], "runtime.consumer.reconnect", item["generation"],
        "recovery-idempotency-key-0001", confirm=False,
        auth_context={"actor": {"identity_id": "other-actor", "type": "qualification"}}, decision=decision,
    )
    assert conflict["reasons"] == ["idempotency_conflict"]
    assert health.decision_history(item["incident_id"])["recovery_requests"][0]["status"] == "admitted"


def test_p4_terminal_replay_precedes_resolved_incident_preflight(health, monkeypatch):
    monkeypatch.setenv("POCKETLAB_ENVIRONMENT", "qualification")
    monkeypatch.setenv("POCKETLAB_SYSTEM_HEALTH_RECOVERY_ADAPTER", "1")
    health.ingest_projection("system.nats_remote", observed_nats())
    item = health.incidents()["items"][0]
    context = {"actor": {"identity_id": "qualification-owner", "type": "qualification"}}
    key = "replay-after-health-0001"
    decision = {"allow": True, "reason_code": "qualification_owner_system_health_recovery", "policy_revision": "test-policy", "decision_id": "decision-replay"}
    first = health.admit_controlled_recovery(
        item["incident_id"], "runtime.consumer.reconnect", item["generation"], key,
        confirm=False, auth_context=context, decision=decision,
    )
    assert first["request"]["status"] == "admitted"
    health.ingest_projection("system.nats_remote", observed_nats("healthy", 2))
    replay = health.recovery_request_replay(
        item["incident_id"], "runtime.consumer.reconnect", item["generation"], key,
        confirm=False, auth_context=context,
    )
    assert replay["idempotent_replay"] is True
    assert replay["request"]["request_id"] == first["request"]["request_id"]
    conflict = health.recovery_request_replay(
        item["incident_id"], "runtime.consumer.reconnect", item["generation"], key,
        confirm=False, auth_context={"actor": {"identity_id": "other-owner", "type": "qualification"}},
    )
    assert conflict["reasons"] == ["idempotency_conflict"]


def test_p4_controlled_recovery_uses_existing_owner_and_fresh_verification(health, monkeypatch):
    monkeypatch.setenv("POCKETLAB_ENVIRONMENT", "qualification")
    monkeypatch.setenv("POCKETLAB_SYSTEM_HEALTH_RECOVERY_ADAPTER", "1")
    health.ingest_projection("system.nats_remote", observed_nats())
    item = health.incidents()["items"][0]
    request = health.admit_controlled_recovery(
        item["incident_id"], "runtime.consumer.reconnect", item["generation"],
        "recovery-owner-key-0001", confirm=False,
        auth_context={"actor": {"identity_id": "qualification-owner", "type": "qualification"}},
        decision={"allow": True, "reason_code": "qualification_owner_system_health_recovery", "policy_revision": "test-policy", "decision_id": "decision-owner"},
    )

    class FakeBus:
        def __init__(self):
            self.generation = 4
            self.healthy = False

        def durable_consumer_status(self, durable):
            return {"generation": self.generation, "healthy": self.healthy, "callback_inflight": False}

        async def ensure_durable_consumer(self, durable, *, force=False):
            assert durable == "pocketlab_command_worker_v1"
            assert force is True
            self.generation += 1
            self.healthy = True
            return True

    assert asyncio.run(health.process_controlled_recovery_requests(FakeBus(), "pocketlab_command_worker_v1")) == 1
    history = health.decision_history(item["incident_id"])["recovery_requests"]
    assert history[0]["status"] == "verified"
    assert history[0]["verification_state"] == "verified"
    assert history[0]["outcome"] == "verified_recovery"


def test_p4_enterprise_approval_promotes_same_idempotent_request(health, monkeypatch):
    monkeypatch.setenv("POCKETLAB_ENVIRONMENT", "qualification")
    monkeypatch.setenv("POCKETLAB_SYSTEM_HEALTH_RECOVERY_ADAPTER", "1")
    health.ingest_projection("system.nats_remote", observed_nats())
    item = health.incidents()["items"][0]
    context = {"actor": {"identity_id": "operator-1", "type": "human"}}
    key = "enterprise-recovery-key-0001"
    pending = health.admit_controlled_recovery(
        item["incident_id"], "runtime.consumer.reconnect", item["generation"], key,
        confirm=False, auth_context=context,
        decision={
            "allow": False, "reason_code": "approval_required", "policy_revision": "policy-1",
            "decision_id": "decision-pending", "approval": {"approval_id": "apr-1"},
        },
    )
    assert pending["request"]["status"] == "approval_required"
    admitted = health.admit_controlled_recovery(
        item["incident_id"], "runtime.consumer.reconnect", item["generation"], key,
        confirm=False, auth_context=context,
        decision={
            "allow": True, "reason_code": "independent_approval_satisfied", "policy_revision": "policy-1",
            "decision_id": "decision-approved", "continuation_approval_id": "apr-1",
        },
    )
    assert admitted["idempotent_replay"] is True
    assert admitted["request"]["status"] == "admitted"
    assert admitted["request"]["authorization_state"] == "authorized"
    assert health.decision_history(item["incident_id"])["recovery_requests"][0]["status"] == "admitted"


def test_infrastructure_registry_cannot_enable_production_or_generic_execution(health, monkeypatch):
    from api_fastapi.services import lite_infrastructure_operations as ops
    monkeypatch.setenv("POCKETLAB_ENVIRONMENT", "production")
    monkeypatch.setenv("POCKETLAB_SYSTEM_HEALTH_RECOVERY_ADAPTER", "1")
    assert not ops.controlled_recovery_enabled()
    assert not ops.activation_policy()["production_automatic_enabled"]
    assert not any(row["system_health_requestable"] for row in ops.operation_catalog())
    monkeypatch.setenv("POCKETLAB_ENVIRONMENT", "qualification")
    monkeypatch.setenv("POCKETLAB_SYSTEM_HEALTH_RECOVERY_EMERGENCY_DISABLE", "0")
    assert ops.controlled_recovery_enabled()
    assert [r["operation_id"] for r in ops.operation_catalog() if r["system_health_requestable"]] == ["runtime.consumer.reconnect"]
    monkeypatch.setenv("POCKETLAB_SYSTEM_HEALTH_RECOVERY_EMERGENCY_DISABLE", "1")
    assert not ops.controlled_recovery_enabled()


def test_infrastructure_prepared_reads_do_not_leak_payloads_or_invent_capacity(health):
    import json
    from api_fastapi.services import lite_infrastructure_read_model as model
    with health.connection() as conn:
        conn.execute("CREATE TABLE phase3b_current_state(domain TEXT, status TEXT, payload_json TEXT, updated_at TEXT)")
        conn.execute("INSERT INTO phase3b_current_state VALUES(?,?,?,?)",
                     ("system.processes", "healthy", json.dumps({"items": [
                         {"name": "pocket-worker", "status": "online", "command": "SECRET_COMMAND"},
                         {"name": "private-process", "status": "online"}]}), health._now()))
    result = model.infrastructure()
    worker = next(row for row in result["services"] if row["id"] == "worker")
    assert worker["process_status"] == "online"
    assert worker["functional_readiness"] == "unknown"
    assert "SECRET_COMMAND" not in json.dumps(result)
    assert "private-process" not in json.dumps(result)
    assert result["cleanup"]["estimated_bytes"] is None
    assert result["cleanup"]["available"] is False
    assert result["retry_available"] is False
    assert model.reliability()["observed_availability"] is None


def test_correlation_excludes_history_and_never_claims_verified_cause(health):
    from api_fastapi.services import lite_infrastructure_read_model as model
    edges = [{"upstream": "nats", "downstream": "worker", "authority": "verified_contract"}]
    rows = [{"source": "system", "target_id": name, "concern_state": "current_concern", "current_monitoring": True}
            for name in ("nats", "worker")]
    assert model.correlate(rows, edges)[0]["cause_confidence"] == "inferred"
    rows[1]["current_monitoring"] = False
    assert model.correlate(rows, edges) == []


def test_owner_evidence_requires_later_same_generation_fetch(health, monkeypatch):
    from datetime import datetime, timedelta, timezone
    from api_fastapi.services import lite_infrastructure_owner_evidence as evidence
    monkeypatch.setattr(evidence, "connection", health.connection)
    then = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat(timespec="seconds").replace("+00:00", "Z")
    fetched = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(timespec="seconds").replace("+00:00", "Z")
    assert evidence.record_consumer_recovery(owner_instance="test-worker", durable="worker",
        before={"generation": 1}, after={"generation": 1}, started_at=then) is None
    for _ in range(2):
        evidence.record_consumer_recovery(owner_instance="test-worker", durable="worker",
            before={"generation": 1}, after={"generation": 2}, started_at=then)
    assert evidence.summary()["recorded_count"] == 1
    assert evidence.summary()["verified_count"] == 0
    with health.connection() as conn:
        conn.execute("UPDATE lite_system_health_owner_recovery_evidence SET completed_at=?", (then,))
    evidence.verify_consumer_recoveries("test-worker", {"generation": 2, "healthy": True, "task_alive": True,
        "subscription_present": True, "last_fetch_at": fetched})
    assert evidence.summary()["verified_count"] == 1
    assert "test-worker" not in str(evidence.history())


def test_owner_restart_does_not_verify_previous_worker_execution(health, monkeypatch):
    from api_fastapi.services import lite_infrastructure_owner_evidence as evidence
    monkeypatch.setattr(evidence, "connection", health.connection)
    evidence.record_consumer_recovery(owner_instance="previous", durable="worker", before={"generation": 1},
                                     after={"generation": 2}, started_at=health._now())
    evidence.verify_consumer_recoveries("replacement", {"generation": 2, "healthy": True})
    assert evidence.summary()["verified_count"] == 0
    assert evidence.summary()["unverified_count"] == 1
