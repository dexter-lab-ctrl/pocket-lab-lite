from __future__ import annotations

import sys
from pathlib import Path


def ensure_runtime_path() -> None:
    runtime = Path(__file__).resolve().parents[2] / "pocket-lab-final-structure" / "runtime"
    value = str(runtime)
    if value not in sys.path:
        sys.path.insert(0, value)


def test_system_health_source_revision_ignores_dependency_projection_envelopes(monkeypatch):
    ensure_runtime_path()
    from api_fastapi.services import lite_phase3b_projections as phase3b

    states = {
        "system.processes": {"status": "healthy", "generation": 1, "source_revision": 11, "projection_revision": 21},
        "system.agent": {"status": "healthy", "generation": 2, "source_revision": 12, "projection_revision": 22},
        "system.supervisor": {"status": "degraded", "generation": 3, "source_revision": 13, "projection_revision": 23},
        "system.remote_access": {"status": "healthy", "generation": 4, "source_revision": 14, "projection_revision": 24},
        "system.nats_remote": {"status": "healthy", "generation": 5, "source_revision": 15, "projection_revision": 25},
        "system.telemetry_thresholds": {"status": "normal", "generation": 6, "source_revision": 16, "projection_revision": 26},
        "system.storage_pressure": {"status": "normal", "generation": 7, "source_revision": 17, "projection_revision": 27},
        "system.sqlite_health": {"status": "healthy", "generation": 8, "source_revision": 18, "projection_revision": 28},
    }
    monkeypatch.setattr(phase3b, "snapshot", lambda domain: dict(states.get(domain) or {}))
    monkeypatch.setattr(phase3b, "_database_instance", lambda: "db-instance")
    monkeypatch.setattr(phase3b, "_maintenance_material", lambda: [])
    monkeypatch.setattr(phase3b, "_bus_material", lambda: {"status": "healthy", "generation": 99})

    before = phase3b.system_health_source_revision()
    for item in states.values():
        item["generation"] += 100
        item["source_revision"] += 100
        item["projection_revision"] += 100
        item["updated_at"] = "2026-07-26T20:00:00Z"

    assert phase3b.system_health_source_revision() == before

    states["system.supervisor"]["status"] = "healthy"
    assert phase3b.system_health_source_revision() != before


def test_system_health_source_revision_tracks_maintenance_band_only(monkeypatch):
    ensure_runtime_path()
    from api_fastapi.services import lite_phase3b_projections as phase3b

    monkeypatch.setattr(phase3b, "snapshot", lambda domain: {"status": "healthy"})
    monkeypatch.setattr(phase3b, "_database_instance", lambda: "db-instance")
    monkeypatch.setattr(phase3b, "_bus_material", lambda: {"status": "healthy"})

    maintenance = [
        {"maintenance_id": "m1", "kind": "wal", "mode": "apply", "status": "succeeded"}
    ]
    monkeypatch.setattr(phase3b, "_maintenance_material", lambda: list(maintenance))
    completed = phase3b.system_health_source_revision()

    maintenance[0]["maintenance_id"] = "m2"
    maintenance[0]["kind"] = "retention"
    assert phase3b.system_health_source_revision() == completed

    maintenance[0]["status"] = "running"
    assert phase3b.system_health_source_revision() != completed
