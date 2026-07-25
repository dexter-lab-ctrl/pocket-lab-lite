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
