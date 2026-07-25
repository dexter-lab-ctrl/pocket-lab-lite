from api_fastapi.services.projection_scheduler import ProjectionJob, ProjectionScheduler


def test_projection_job_bounds_quiet_window():
    scheduler = ProjectionScheduler()
    scheduler.register(ProjectionJob(
        domain="fleet.summary", builder=lambda: {}, projector=lambda payload: 1,
        priority=10, work_class="critical", deadline_seconds=1.0,
        quiet_window_seconds=999.0,
    ))
    assert scheduler._jobs["fleet.summary"].quiet_window_seconds == 30.0


def test_fleet_invalidation_keeps_last_known_good(monkeypatch):
    from api_fastapi.services.lite_control_plane_store import ControlPlaneProjectionStore, _PreparedItem
    import time
    store = ControlPlaneProjectionStore()
    store._prepared["fleet:summary"] = _PreparedItem(payload={"devices": []}, revision=1, prepared_at=time.monotonic(), database_instance=store.database_instance())
    monkeypatch.setattr("api_fastapi.services.projection_scheduler.PROJECTION_SCHEDULER.mark_registered_prefix_dirty", lambda *a, **k: 0)
    store.invalidate_domain("fleet")
    assert "fleet:summary" in store._prepared


def test_fleet_source_revision_ignores_heartbeat_timestamp_churn(monkeypatch):
    from api_fastapi.services import fleet_registry

    state = {
        "agents": {
            "node-a": {
                "role": "compute",
                "status": "online",
                "last_seen_at": "2026-07-25T08:00:00Z",
                "supervisor_status": "online",
                "pm2_status": "online",
                "tailscale_ready": True,
            }
        }
    }

    monkeypatch.setattr(
        fleet_registry,
        "_agents_payload",
        lambda: state,
    )
    monkeypatch.setattr(
        fleet_registry,
        "_derive_status",
        lambda raw: raw.get("status", "unknown"),
    )

    first = fleet_registry.fleet_source_revision()

    state["agents"]["node-a"]["last_seen_at"] = (
        "2026-07-25T08:00:10Z"
    )
    state["agents"]["node-a"]["updated_at"] = (
        "2026-07-25T08:00:10Z"
    )

    second = fleet_registry.fleet_source_revision()

    assert second == first


def test_fleet_source_revision_changes_on_semantic_transition(monkeypatch):
    from api_fastapi.services import fleet_registry

    state = {
        "agents": {
            "node-a": {
                "role": "compute",
                "status": "online",
                "supervisor_status": "online",
                "pm2_status": "online",
                "tailscale_ready": True,
            }
        }
    }

    monkeypatch.setattr(
        fleet_registry,
        "_agents_payload",
        lambda: state,
    )
    monkeypatch.setattr(
        fleet_registry,
        "_derive_status",
        lambda raw: raw.get("status", "unknown"),
    )

    first = fleet_registry.fleet_source_revision()
    state["agents"]["node-a"]["status"] = "offline"
    second = fleet_registry.fleet_source_revision()

    assert second != first
