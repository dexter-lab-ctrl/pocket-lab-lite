from __future__ import annotations

import json
from pathlib import Path

from pocket_lab_test_utils import client, ensure_runtime_path


def _prepared_health(*, nats: str = "healthy", worker: str = "healthy") -> dict:
    return {
        "engine": "lite-native",
        "source": "prepared-lite-native",
        "status": "healthy" if nats == "healthy" and worker == "healthy" else "unavailable",
        "summary": "prepared native test state",
        "prepared": True,
        "components": {
            "api": "healthy",
            "identity": "healthy",
            "nats": nats,
            "worker": worker,
            "sqlite": "healthy",
            "storage": "healthy",
            "remote_access": "unavailable",
        },
        "services": {
            "api": {"name": "Control API", "status": "healthy"},
            "nats": {"name": "NATS / JetStream", "status": nats},
            "worker": {"name": "Worker Execution", "status": worker},
        },
        "identity": {"status": "healthy", "ready": True},
        "worker": {"status": worker, "ready": worker == "healthy"},
        "nats": {
            "status": nats,
            "secondary_configured": True,
            "secondary_reachable": False,
            "secondary_status": "unavailable",
        },
        "status_counts": {"healthy": 3},
        "updated_at": "2026-11-25T12:00:00Z",
    }


def test_ready_uses_prepared_native_state_and_does_not_gate_on_optional_remote_or_secondary(
    monkeypatch,
):
    ensure_runtime_path()
    from api_fastapi.routers import health

    monkeypatch.setattr(health, "_prepared_health", lambda: _prepared_health())
    monkeypatch.setattr(
        health.BUS,
        "status",
        lambda: {"connected": True, "jetstream_enabled": True},
    )
    monkeypatch.setattr(health.LIVE_STATUS, "status", lambda: {"running": False})

    response = client().get("/ready")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is True
    assert payload["health_engine_source"] == "prepared-lite-native"
    assert payload["optional_capabilities"] == {
        "remote_access": "unavailable",
        "secondary_device": "unavailable",
    }


def test_ready_rejects_missing_required_native_worker_or_nats_evidence(monkeypatch):
    ensure_runtime_path()
    from api_fastapi.routers import health

    monkeypatch.setattr(health, "_prepared_health", lambda: _prepared_health(nats="unavailable"))
    monkeypatch.setattr(
        health.BUS,
        "status",
        lambda: {"connected": False, "jetstream_enabled": False},
    )
    monkeypatch.setattr(health.LIVE_STATUS, "status", lambda: {"running": False})

    response = client().get("/ready")

    assert response.status_code == 503
    payload = response.json()
    assert payload["ready"] is False
    assert payload["health_engine_snapshot"]["components"]["nats"] == "unavailable"


def test_health_get_reads_prepared_projection_without_collecting_or_migrating(monkeypatch):
    ensure_runtime_path()
    from api_fastapi.routers import health

    calls: list[tuple[str, bool]] = []

    def prepared(domain: str, *, ensure_schema: bool = True):
        calls.append((domain, ensure_schema))
        return _prepared_health()

    monkeypatch.setattr(health.phase3b, "snapshot", prepared)

    response = client().get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"
    assert payload["source"] == "api-process"
    assert payload["health_engine"]["engine"] == "lite-native"
    assert calls == [("system.health", False)]


def test_secondary_device_unavailability_is_optional_for_native_nats_health(monkeypatch):
    ensure_runtime_path()
    from api_fastapi.services import lite_phase3b_projections as phase3b
    from api_fastapi.services import lite_status

    monkeypatch.setattr(
        phase3b,
        "_bus_material",
        lambda: {
            "connected": True,
            "jetstream_enabled": True,
            "durable_consumer_health": {
                "pocketlab_command_worker_v1": {"healthy": True},
            },
        },
    )
    monkeypatch.setattr(
        lite_status,
        "lite_secondary_nats_status",
        lambda: {"configured": True, "reachable": False, "route_selection": "primary"},
    )

    payload = phase3b.collect_nats_remote_state()

    assert payload["status"] == "healthy"
    assert payload["secondary_status"] == "unavailable"
    assert payload["primary_ready"] is True


def test_retirement_guards_cover_active_health_and_bootstrap_paths():
    root = Path(__file__).resolve().parents[2]
    health_source = (root / "pocket-lab-final-structure/runtime/api_fastapi/routers/health.py").read_text()
    core_source = (root / "pocket-lab-final-structure/runtime/core/control_plane_core.py").read_text()
    dashboard_source = (root / "pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/start-dashboard.sh").read_text()

    assert "gatus" not in health_source.lower()
    assert "vault" not in health_source.lower()
    assert "iac_dir" not in health_source
    assert "fetch_gatus_statuses" not in core_source
    assert "build_health_engine_snapshot" not in core_source
    assert "/gitea" not in dashboard_source
    assert "prometheus" not in dashboard_source.lower()
    assert not (root / "pocket-lab-final-structure/runtime/api_fastapi/services/observability_status.py").exists()
    for name in ("init-vault.sh", "init-mariadb.sh", "start-gitea.sh", "seed-gitops-repo.sh"):
        assert not (root / "pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts" / name).exists()


def test_retired_route_openapi_contracts_advertise_410_not_200():
    ensure_runtime_path()
    from api_fastapi.main import app

    paths = app.openapi()["paths"]
    for path in (
        "/api/observability/status",
        "/api/pipeline_status.json",
        "/api/gitops/health.json",
        "/api/git_history.json",
    ):
        get_contract = paths[path]["get"]
        assert "200" not in get_contract["responses"]
        assert "410" in get_contract["responses"]


def test_retired_command_subjects_are_absent_from_active_asyncapi_catalog():
    root = Path(__file__).resolve().parents[2]
    contract = json.loads(
        (root / "contracts/generated/lite-asyncapi.json").read_text(encoding="utf-8")
    )
    channels = set(contract["channels"])
    assert "pocketlab.commands.vault.rotate" not in channels
    assert "pocketlab.commands.vault.dynamic_secret" not in channels
    assert "pocketlab.events.command.retired" in channels
