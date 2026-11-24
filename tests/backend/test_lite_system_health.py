"""System Health incident behavior. Source only; execution deferred."""
from __future__ import annotations

from contextlib import contextmanager
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


# H1 source qualification: author only, never execute in this implementation session.
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


# P4 qualification — ADDED, NOT RUN.
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
