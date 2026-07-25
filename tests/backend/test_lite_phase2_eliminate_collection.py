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


def test_prepared_only_fleet_summary_installs_mandatory_revision_guard(
    monkeypatch,
):
    from api_fastapi.services import fleet_registry
    from api_fastapi.services.lite_control_plane_store import (
        ControlPlaneProjectionStore,
    )

    store = ControlPlaneProjectionStore()
    captured = {}

    class SchedulerStub:
        def mark_dirty(
            self,
            domain,
            *,
            job=None,
            priority=None,
            force_followup=False,
        ):
            captured["domain"] = domain
            captured["job"] = job
            captured["priority"] = priority
            captured["force_followup"] = force_followup
            return {
                "accepted": True,
                "refresh_pending": True,
                "retry_after_seconds": 0,
            }

        def status(self, _domain):
            return {
                "registered": True,
                "refresh_pending": False,
                "retry_after_seconds": 0,
            }

    monkeypatch.setattr(
        "api_fastapi.services.projection_scheduler."
        "PROJECTION_SCHEDULER",
        SchedulerStub(),
    )

    try:
        store.prepared_only_read(
            domain="fleet",
            key="summary",
            snapshot_builder=lambda: None,
            builder=lambda: {"devices": []},
            projector=lambda _payload: 1,
            stale_after_ms=30_000,
            max_stale_ms=300_000,
            deadline_seconds=1.0,
            priority=10,
            work_class="critical",
        )
    except Exception:
        # No prepared snapshot exists in this fixture. Registration metadata
        # is the behavior under test.
        pass

    job = captured.get("job")
    assert job is not None
    assert captured["domain"] == "fleet.summary"
    assert job.source_revision is fleet_registry.fleet_source_revision
    assert job.max_probe_seconds == 300.0
    assert job.quiet_window_seconds >= 1.5
