from pathlib import Path

from pocket_lab_test_utils import client, ensure_runtime_path

ensure_runtime_path()


def test_nats_status_endpoint_registered():
    response = client().get("/api/nats/status")
    assert response.status_code != 404


def test_nats_required_mode_does_not_use_legacy_local_fallback(monkeypatch):
    monkeypatch.setenv("POCKETLAB_NATS_REQUIRED", "1")
    monkeypatch.setenv("POCKETLAB_NATS_REQUIRE_JETSTREAM", "1")
    response = client().post(
        "/api/operations/execute", json={"operation": "git_sync", "target": "repo"}
    )
    assert response.status_code in {200, 202, 403, 503}
    assert "local fallback" not in response.text.lower()


def test_bus_status_is_lightweight_and_uses_real_client_state(monkeypatch):
    from api_fastapi.services.nats_bus import PocketLabEventBus

    class FakeClient:
        is_connected = True

    bus = PocketLabEventBus()
    bus.nc = FakeClient()
    bus.js = object()
    bus.connected = False

    status = bus.status()

    assert status["connected"] is True
    assert status["mode"] == "nats"
    assert status["jetstream_enabled"] is True
    assert "workflow_engine" not in status


def test_nats_error_only_schedules_reconnect_when_client_is_down(monkeypatch):
    import asyncio
    from api_fastapi.services.nats_bus import PocketLabEventBus

    class FakeClient:
        def __init__(self, connected):
            self.is_connected = connected

    async def scenario():
        bus = PocketLabEventBus()
        scheduled = []
        monkeypatch.setattr(bus, "_schedule_reconnect", lambda: scheduled.append(True))

        bus.nc = FakeClient(True)
        await bus._nats_error(RuntimeError("transient"))
        assert scheduled == []
        assert bus.connected is False  # wrapper is reconciled by status/watchdog
        assert bus.status()["connected"] is True

        bus.nc = FakeClient(False)
        await bus._nats_error(RuntimeError("down"))
        assert scheduled == [True]
        assert bus.connected is False

    asyncio.run(scenario())


def test_close_stale_client_clears_subscriptions():
    import asyncio
    from api_fastapi.services.nats_bus import PocketLabEventBus

    class FakeClient:
        is_connected = False

        async def close(self):
            return None

    async def scenario():
        bus = PocketLabEventBus()
        bus.nc = FakeClient()
        bus.js = object()
        bus._nats_subscriptions.extend([object(), object()])
        await bus._close_stale_client()
        assert bus.nc is None
        assert bus.js is None
        assert bus._nats_subscriptions == []

    asyncio.run(scenario())


def test_ack_message_waits_for_broker_ack_when_supported():
    import asyncio
    from api_fastapi.services.nats_bus import PocketLabEventBus

    class Message:
        def __init__(self):
            self.calls = []

        async def ack_sync(self, *, timeout):
            self.calls.append(timeout)

        async def ack(self):
            raise AssertionError("fire-and-forget ack must not be used")

    async def scenario():
        message = Message()
        await PocketLabEventBus().ack_message(message)
        return message.calls

    assert asyncio.run(scenario()) == [1.0]


def test_production_worker_policy_allows_bounded_photo_backup_lifecycle_and_node_dispatch():
    from pathlib import Path

    script = Path(
        "pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/start-dashboard.sh"
    ).read_text(encoding="utf-8")
    worker_line = next(
        line
        for line in script.splitlines()
        if "POCKETLAB_NATS_WORKER_USER" in line and "permissions" in line
    )
    worker_publish = worker_line.split("subscribe:", 1)[0]
    assert '"pocketlab.commands.lite.media_backup.start"' in worker_publish
    assert '"pocketlab.commands.lite.media_backup.cancel"' in worker_publish
    assert '"pocketlab.commands.lite.media_backup.repair"' not in worker_publish
    assert '"pocketlab.commands.node.*.media.backup.>"' in worker_publish
    assert '"pocketlab.commands.node.>"' not in worker_publish
    assert '"pocketlab.commands.>"' not in worker_publish


def test_core_publish_does_not_flush_after_every_message():
    source = Path(
        "pocket-lab-final-structure/runtime/api_fastapi/services/nats_bus.py"
    ).read_text()
    publish_block = source.split("async def publish_json", 1)[1].split("def _record", 1)[0]
    assert "await self.nc.publish(subject, payload)" in publish_block
    assert "await self.nc.flush(timeout=1)" not in publish_block
    assert "async with self._flush_lock" in source


def test_connected_invalid_state_error_is_counted_without_disconnect(monkeypatch):
    import asyncio
    from api_fastapi.services.nats_bus import PocketLabEventBus

    class FakeClient:
        is_connected = True

    async def scenario():
        bus = PocketLabEventBus()
        bus.nc = FakeClient()
        scheduled = []
        monkeypatch.setattr(bus, "_schedule_reconnect", lambda: scheduled.append(True))
        await bus._nats_error(asyncio.InvalidStateError("invalid state"))
        status = bus.status()
        assert status["connected"] is True
        assert status["transient_invalid_state_errors"] == 1
        assert status["last_error"] == ""
        assert scheduled == []

    asyncio.run(scenario())


def test_durable_pull_consumer_is_recreated_after_fetch_task_dies():
    import asyncio
    from api_fastapi.services.nats_bus import PocketLabEventBus

    class FakeClient:
        is_connected = True

        async def drain(self):
            return None

        async def close(self):
            self.is_connected = False

    class FailingSubscription:
        async def fetch(self, *, batch, timeout):
            raise RuntimeError("stale subscription")

        async def unsubscribe(self):
            return None

    class HealthySubscription:
        async def fetch(self, *, batch, timeout):
            await asyncio.sleep(0)
            raise TimeoutError

        async def unsubscribe(self):
            return None

    class FakeJetStream:
        def __init__(self):
            self.calls = 0

        async def pull_subscribe(self, subject, *, durable, stream):
            self.calls += 1
            if self.calls == 1:
                return FailingSubscription()
            return HealthySubscription()

    async def callback(_msg):
        return None

    async def scenario():
        bus = PocketLabEventBus()
        bus.nc = FakeClient()
        bus.js = FakeJetStream()
        bus.connected = True

        await bus.subscribe_durable(
            "pocketlab.commands.>",
            callback,
            durable="worker-test",
        )
        await asyncio.sleep(0.02)
        assert bus.durable_consumer_status("worker-test")["task_alive"] is False

        recovered = await bus.ensure_durable_consumer("worker-test")
        assert recovered is True
        status = bus.durable_consumer_status("worker-test")
        assert status["task_alive"] is True
        assert status["generation"] == 2
        assert status["recoveries"] == 1
        assert status["last_error_type"] == ""

        await bus.stop()

    asyncio.run(scenario())


def test_progress_route_is_async_to_avoid_sync_threadpool_starvation():
    import inspect
    from api_fastapi.routers.lite import get_lite_security_progress

    assert inspect.iscoroutinefunction(get_lite_security_progress)


def test_prepared_publish_reports_jetstream_ack_timing():
    import asyncio
    from api_fastapi.services.nats_bus import PocketLabEventBus

    class FakeClient:
        is_connected = True

    class FakeJetStream:
        async def publish(self, subject, payload):
            await asyncio.sleep(0)
            return object()

    async def scenario():
        bus = PocketLabEventBus()
        bus.nc = FakeClient()
        bus.js = FakeJetStream()
        bus.connected = True
        event, encoded = bus.prepare_json_event(
            "pocketlab.commands.test", "test.requested", {"command_id": "c1"}
        )
        timing = {}
        await bus.publish_prepared_json(
            "pocketlab.commands.test", event, encoded, timing_sink=timing
        )
        assert timing["send_ms"] >= 0
        assert timing["ack_wait_ms"] >= 0
        assert timing["post_ack_ms"] >= 0
        assert timing["broker_ms"] >= 0

    asyncio.run(scenario())


def test_prepared_publish_splits_memory_record_and_workflow_enqueue(monkeypatch):
    import asyncio
    from api_fastapi.services.nats_bus import PocketLabEventBus
    from api_fastapi.services.workflow_engine import WORKFLOW_ENGINE

    class FakeClient:
        is_connected = True

    class FakeJetStream:
        async def publish(self, subject, payload):
            return object()

    async def scenario():
        bus = PocketLabEventBus()
        bus.nc = FakeClient()
        bus.js = FakeJetStream()
        bus.connected = True
        queued = []
        monkeypatch.setattr(WORKFLOW_ENGINE, "enqueue_event", lambda event: queued.append(event) or True)
        event, encoded = bus.prepare_json_event(
            "pocketlab.commands.test", "test.requested", {"command_id": "c1"}
        )
        timing = {}
        await bus.publish_prepared_json(
            "pocketlab.commands.test", event, encoded, timing_sink=timing
        )
        assert timing["record_memory_ms"] >= 0
        assert timing["workflow_enqueue_ms"] >= 0
        assert timing["post_ack_ms"] >= timing["workflow_enqueue_ms"]
        assert queued == [event]

    asyncio.run(scenario())
