from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from pocket_lab_test_utils import ensure_runtime_path


DOMAINS = {
    "system.telemetry_thresholds",
    "system.storage_pressure",
    "system.sqlite_health",
    "system.activity_summary",
}


def _configure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    ensure_runtime_path()
    state_dir = tmp_path / "state"
    database = state_dir / "pocketlab-lite.sqlite3"
    state_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("POCKETLAB_LITE_DB_PATH", str(database))
    monkeypatch.setenv("POCKETLAB_STATE_DIR", str(state_dir))
    monkeypatch.setenv("POCKETLAB_BASE_DIR", str(tmp_path))
    from api_fastapi.db.connection import reset_sqlite_path_cache
    from api_fastapi.db.migrations import apply_migrations, current_schema_version
    from api_fastapi.db.runtime import SQLITE_READS

    reset_sqlite_path_cache()
    SQLITE_READS.invalidate()

    # Migration application is intentionally idempotent. In combined test
    # runs, an already-imported runtime component may initialize this temporary
    # database before this call, causing apply_migrations() to return [].
    # Validate the authoritative postcondition rather than which caller won
    # the initialization race.
    apply_migrations()
    assert current_schema_version() == 16
    return database


def test_phase3c_migration_seeds_domains_and_targeted_indexes(tmp_path, monkeypatch):
    database = _configure(tmp_path, monkeypatch)
    conn = sqlite3.connect(database)
    try:
        domains = {
            row[0]
            for row in conn.execute(
                "SELECT domain FROM domain_revisions WHERE domain LIKE 'system.%'"
            )
        }
        indexes = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
        }
        plan = " ".join(
            str(row[-1])
            for row in conn.execute(
                "EXPLAIN QUERY PLAN SELECT operation_id,status FROM app_action_lifecycle "
                "WHERE status=? ORDER BY updated_at_epoch_ms DESC,operation_id DESC LIMIT 24",
                ("running",),
            )
        ).lower()
    finally:
        conn.close()
    assert DOMAINS.issubset(domains)
    assert {
        "idx_phase3c_maintenance_status_latest",
        "idx_phase3c_app_actions_status_latest",
        "idx_phase3c_recovery_status_latest",
        "idx_phase3c_audit_latest",
    }.issubset(indexes)
    assert "idx_phase3c_app_actions_status_latest" in plan or "index" in plan


def test_phase3c_threshold_bands_use_integer_hysteresis():
    ensure_runtime_path()
    from api_fastapi.services.lite_semantic_bands import ThresholdPolicy, semantic_band

    high = ThresholdPolicy(watch=70, elevated=85, critical=95, hysteresis=5)
    assert semantic_band(69, high) == "normal"
    assert semantic_band(70, high) == "watch"
    assert semantic_band(86, high) == "elevated"
    assert semantic_band(84, high, previous="elevated") == "elevated"
    assert semantic_band(80, high, previous="elevated") == "watch"

    low = ThresholdPolicy(watch=15_000, elevated=8_000, critical=3_000, hysteresis=2_000, low_is_bad=True)
    assert semantic_band(20_000, low) == "normal"
    assert semantic_band(14_000, low) == "watch"
    assert semantic_band(2_000, low) == "critical"
    assert semantic_band(16_000, low, previous="watch") == "watch"
    assert semantic_band(17_000, low, previous="watch") == "normal"
    assert semantic_band(None, low) == "unknown"
    assert semantic_band(10, low, supported=False) == "unsupported"


def test_phase3c_telemetry_revision_ignores_nonsemantic_summary_churn(tmp_path, monkeypatch):
    database = _configure(tmp_path, monkeypatch)
    from api_fastapi.services import lite_phase3c_projections as phase3c

    conn = sqlite3.connect(database)
    try:
        conn.execute(
            "INSERT INTO device_current_state(device_id,device_name,role,ui_state,connection_state,agent_status,supervisor_status,pm2_status,updated_at,updated_at_epoch_ms,summary) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            ("phone-2", "Phone 2", "compute", "Online", "online", "online", "healthy", "online", "2026-07-25T00:00:00Z", 1, "first"),
        )
        conn.execute(
            "INSERT INTO device_health_current(device_id,health_status,health_severity,health_revision,source_revision,source_freshness_json,resources_json,connection_json,last_evaluated_at,last_evaluated_at_epoch_ms,updated_at,updated_at_epoch_ms,summary) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "phone-2", "healthy", "none", "health-1", 7,
                json.dumps({"telemetry": {"state": "current", "age_seconds": 4}}),
                json.dumps({"storage": {"status": "healthy", "free_mb": 9999}, "memory": {"status": "healthy", "used_mb": 100}, "load": {"status": "healthy", "percent": 12}, "temperature": {"status": "healthy", "celsius": 40}}),
                json.dumps({"status": "online", "last_seen_at": "2026-07-25T00:00:00Z"}),
                "2026-07-25T00:00:00Z", 1, "2026-07-25T00:00:00Z", 1, "first summary",
            ),
        )
        conn.commit()
    finally:
        conn.close()
    first = phase3c.telemetry_source_revision()
    conn = sqlite3.connect(database)
    try:
        conn.execute(
            "UPDATE device_health_current SET summary=?,updated_at=?,updated_at_epoch_ms=? WHERE device_id=?",
            ("display wording changed", "2026-07-25T00:05:00Z", 2, "phone-2"),
        )
        conn.commit()
    finally:
        conn.close()
    assert phase3c.telemetry_source_revision() == first

    conn = sqlite3.connect(database)
    try:
        resources = json.dumps({"storage": {"status": "low"}, "memory": {"status": "healthy"}, "load": {"status": "healthy"}, "temperature": {"status": "healthy"}})
        conn.execute(
            "UPDATE device_health_current SET resources_json=?,health_revision=? WHERE device_id=?",
            (resources, "health-2", "phone-2"),
        )
        conn.commit()
    finally:
        conn.close()
    assert phase3c.telemetry_source_revision() != first


def test_phase3c_storage_revision_changes_only_when_band_changes(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    from api_fastapi.services import lite_phase3c_projections as phase3c
    from api_fastapi.services import lite_storage_guard

    readings = {"free_percent": 30.0}
    monkeypatch.setattr(
        lite_storage_guard,
        "storage_readiness",
        lambda **kwargs: {"ready": True, "reason": "ready", "free_percent": readings["free_percent"]},
    )
    monkeypatch.setattr(phase3c, "_file_size", lambda path: 0)
    first = phase3c.storage_source_revision()
    readings["free_percent"] = 29.5
    assert phase3c.storage_source_revision() == first
    readings["free_percent"] = 14.0
    assert phase3c.storage_source_revision() != first
    payload = phase3c.collect_storage_pressure()
    encoded = json.dumps(payload, sort_keys=True).lower()
    assert "free_bytes" not in encoded
    assert str(tmp_path).lower() not in encoded


def test_phase3c_sqlite_source_probe_never_runs_quick_check(monkeypatch):
    ensure_runtime_path()
    from api_fastapi.services import lite_phase3c_projections as phase3c

    calls: list[bool] = []
    monkeypatch.setattr(phase3c, "snapshot", lambda domain: {})
    monkeypatch.setattr(
        phase3c,
        "_sqlite_material",
        lambda *, run_quick_check: calls.append(run_quick_check) or {
            "status": "healthy", "quick_check": "ok", "database_instance": "db"
        },
    )
    phase3c.sqlite_health_source_revision()
    assert calls == [False]
    phase3c.collect_sqlite_health()
    assert calls == [False, True]


def test_phase3c_activity_summary_is_bounded_and_excludes_payloads(tmp_path, monkeypatch):
    database = _configure(tmp_path, monkeypatch)
    from api_fastapi.services import lite_phase3c_projections as phase3c

    conn = sqlite3.connect(database)
    try:
        conn.execute(
            "INSERT INTO command_lifecycle(command_id,entity_type,entity_id,operation_type,status,created_at,updated_at,updated_at_epoch_ms,source_ref,summary,metadata_json) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            ("cmd-1", "device", "phone-2", "restart_agent", "running", "2026-07-25T00:00:00Z", "2026-07-25T00:00:01Z", 10, "safe", "password=must-not-appear", '{"token":"must-not-appear"}'),
        )
        conn.execute(
            "INSERT INTO app_action_lifecycle(operation_id,app_id,action_id,status,created_at,updated_at,updated_at_epoch_ms,source_ref,summary,metadata_json) VALUES(?,?,?,?,?,?,?,?,?,?)",
            ("app-1", "photoprism", "check_app", "succeeded", "2026-07-25T00:00:00Z", "2026-07-25T00:00:02Z", 20, "safe", "secret=must-not-appear", '{}'),
        )
        conn.execute(
            "INSERT INTO recovery_operations(operation_id,operation_type,status,created_at,updated_at,updated_at_epoch_ms,source_ref,summary,metadata_json) VALUES(?,?,?,?,?,?,?,?,?)",
            ("rec-1", "backup", "failed", "2026-07-25T00:00:00Z", "2026-07-25T00:00:03Z", 30, "safe", "token=must-not-appear", '{}'),
        )
        conn.execute(
            "INSERT INTO audit_evidence_index(event_type,entity_type,entity_id,operation_id,status,evidence_ref,created_at,created_at_epoch_ms,summary) VALUES(?,?,?,?,?,?,?,?,?)",
            ("operation", "device", "phone-2", "cmd-1", "running", "/private/path/must-not-appear", "2026-07-25T00:00:04Z", 40, "password=must-not-appear"),
        )
        conn.execute("UPDATE domain_revisions SET revision=revision+1 WHERE domain IN ('commands','apps','recovery','audit')")
        conn.commit()
    finally:
        conn.close()
    payload = phase3c.collect_activity_summary()
    encoded = json.dumps(payload, sort_keys=True).lower()
    assert payload["active_operations"] == 1
    assert payload["attention_required"] == 1
    assert payload["audit_reference_count"] == 1
    assert "must-not-appear" not in encoded
    assert "private/path" not in encoded
    assert "metadata_json" not in encoded
    assert payload["item_count"] <= 4 * 24


def test_phase3c_projection_is_change_only_and_bounded(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    from api_fastapi.services import lite_phase3c_projections as phase3c

    payload = {"status": "normal", "summary": "Storage looks good.", "free_space_band": "normal", "item_count": 1, "sanitized": True}
    first = phase3c.project("system.storage_pressure", payload)
    second = phase3c.project("system.storage_pressure", {**payload, "collector_duration_ms": 999.0})
    assert first == 1
    assert second == first
    saved = phase3c.snapshot("system.storage_pressure")
    assert saved and saved["projection_revision"] == first
    assert len(json.dumps(saved).encode("utf-8")) <= 64 * 1024


def test_phase3c_contracts_are_central_and_mandatory():
    ensure_runtime_path()
    from api_fastapi.services.lite_semantic_revisions import contract_for

    for domain in DOMAINS:
        parent, key = domain.split(".", 1)
        contract = contract_for(parent, key)
        assert contract is not None
        assert callable(contract.source_revision)
        assert contract.deadline_seconds <= 8
        assert contract.max_probe_seconds <= (1800 if domain == "system.sqlite_health" else 300)


def test_phase3c_routes_are_prepared_read_only():
    source = Path("pocket-lab-final-structure/runtime/api_fastapi/routers/lite.py").read_text(encoding="utf-8")
    for path in (
        "/system/telemetry-thresholds",
        "/system/storage-pressure",
        "/system/sqlite-health",
        "/system/activity-summary",
    ):
        start = source.index(f'@router.get("{path}")')
        end = source.find("\n@router.", start + 1)
        block = source[start:end if end >= 0 else len(source)]
        assert "_phase3c_prepared_read" in block
        for forbidden in ("subprocess", "disk_usage", "quick_check", "BUS.connect", "pm2"):
            assert forbidden not in block


def test_phase3c_home_presentation_prefers_semantic_current_state():
    source = Path("src/lib/liteHomePresentation.js").read_text(encoding="utf-8")
    assert "status.system_current_state" in source
    for key in ("telemetry_thresholds", "storage_pressure", "sqlite_health", "activity_summary"):
        assert key in source
    assert "semanticResourceMetric" in source


def test_phase3c_frontend_keys_conditional_reads_and_safe_snapshots():
    query = Path("src/lib/liteQueryClient.js").read_text(encoding="utf-8")
    api = Path("src/lib/liteApi.js").read_text(encoding="utf-8")
    snapshots = Path("src/lib/liteSafeSnapshots.js").read_text(encoding="utf-8")
    for path in (
        "/api/lite/system/telemetry-thresholds",
        "/api/lite/system/storage-pressure",
        "/api/lite/system/sqlite-health",
        "/api/lite/system/activity-summary",
    ):
        assert path in query
        assert f"conditionalGet('{path}')" in api
        assert path in snapshots


def test_phase3c_gate_is_termux_safe_and_strict():
    script = Path("scripts/dev/check-lite-phase3c-projections.sh").read_text(encoding="utf-8")
    assert "/tmp/" not in script
    assert "$STATE_DIR/.pocketlab-dev/phase3c" in script
    assert "api/lite/diagnostics/runtime" in script
    assert "payload_bytes" in script
    assert "source_revision_enabled" in script
    assert "stale_generation_count" in script
    assert "commit churn" in script
    assert "fetch_runtime_evidence" in script
    assert "POCKETLAB_PHASE3C_RUNTIME_MAX_TIME" in script
    assert "remaining_domain_capacity" in script
    assert 'rm -f "$raw"' in script
    assert "nats://user:" not in script.lower()
