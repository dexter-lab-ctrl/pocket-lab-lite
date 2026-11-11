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
    monkeypatch.setattr(health, "freshness", lambda _: "stale")
    preflight = health.repair_preflight(problem["incident_id"], "app.repair", problem["generation"])
    assert "evidence_not_current" in preflight["reasons"]
    assert preflight["allowed"] is False
    assert health.summary()["status"] == "unknown"


def test_forecast_and_ai_claims_remain_disabled(health):
    assert health.resource_intelligence()["forecast"] == "not_enough_information"
    assert health.knowledge()["ai_provider"] == "disabled"
    assert health.policy()["engine_auto_repair"] is False
