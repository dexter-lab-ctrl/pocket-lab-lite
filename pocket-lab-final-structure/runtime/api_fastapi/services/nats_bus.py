from __future__ import annotations

import asyncio
import contextlib
import json
import os
import ssl
import time
import uuid
from collections import deque
from dataclasses import dataclass
from typing import Any, AsyncIterator, Awaitable, Callable, Deque, Dict, Optional

try:  # Optional so Phase 2 remains runnable in minimal Termux/test harnesses.
    import nats  # type: ignore
    from nats.aio.client import Client as NATS  # type: ignore
    from nats.js import JetStreamContext  # type: ignore
except Exception:  # pragma: no cover - exercised when nats-py is absent.
    nats = None  # type: ignore
    NATS = Any  # type: ignore
    JetStreamContext = Any  # type: ignore

from .. import deps


DEFAULT_STREAMS = {
    "POCKETLAB_COMMANDS": ["pocketlab.commands.>"],
    "POCKETLAB_EVENTS": ["pocketlab.events.>"],
    "POCKETLAB_AUDIT": ["pocketlab.audit.>"],
    "POCKETLAB_TELEMETRY": ["pocketlab.events.telemetry.>"],
    "POCKETLAB_DLQ": ["pocketlab.dlq.>"],
}


@dataclass
class BusStatus:
    mode: str
    connected: bool
    servers: list[str]
    jetstream_enabled: bool
    fallback_reason: str = ""
    published: int = 0
    received: int = 0


@dataclass(frozen=True)
class DurableConsumerSpec:
    subject: str
    callback: Callable[[Any], Awaitable[None]]
    durable: str
    queue: str | None
    stream: str


class PocketLabEventBus:
    """Production NATS/JetStream event bus wrapper.

    NATS is fail-closed by default. FastAPI write paths must not silently
    execute locally when the command/event backbone is unavailable.  The local
    history deque is retained only as a read-side WebSocket/recent-events cache
    for events that were successfully published or received from NATS.
    """

    def __init__(self) -> None:
        self.servers = [
            s.strip()
            for s in os.environ.get(
                "POCKETLAB_NATS_URL", "nats://127.0.0.1:4222"
            ).split(",")
            if s.strip()
        ]
        self.name = os.environ.get("POCKETLAB_NATS_NAME", "pocketlab-fastapi")
        self.jetstream_enabled = deps.core._env_bool("POCKETLAB_NATS_JETSTREAM", True)
        self.required = deps.core._env_bool("POCKETLAB_NATS_REQUIRED", True)
        self.require_jetstream = deps.core._env_bool(
            "POCKETLAB_NATS_REQUIRE_JETSTREAM", True
        )
        self.user = os.environ.get("POCKETLAB_NATS_USER") or None
        self.password = os.environ.get("POCKETLAB_NATS_PASSWORD") or None
        self.token = os.environ.get("POCKETLAB_NATS_TOKEN") or None
        self.tls_required = deps.core._env_bool("POCKETLAB_NATS_TLS", False)
        self.tls_ca = os.environ.get("POCKETLAB_NATS_TLS_CA") or None
        self.tls_cert = os.environ.get("POCKETLAB_NATS_TLS_CERT") or None
        self.tls_key = os.environ.get("POCKETLAB_NATS_TLS_KEY") or None
        self.history_limit = deps.core._env_int("POCKETLAB_EVENT_HISTORY_LIMIT", 500)
        self.connect_timeout = float(
            os.environ.get("POCKETLAB_NATS_CONNECT_TIMEOUT", "1.5")
        )
        self.nc: Optional[NATS] = None
        self.js: Optional[JetStreamContext] = None
        self.connected = False
        self.fallback_reason = "not started"
        self.published = 0
        self.received = 0
        self._history: Deque[Dict[str, Any]] = deque(maxlen=self.history_limit)
        self._seen_event_ids: Deque[str] = deque(maxlen=self.history_limit * 2)
        self._seen_event_id_set: set[str] = set()
        self._subscribers: set[asyncio.Queue[Dict[str, Any]]] = set()
        self._nats_subscriptions: list[Any] = []
        self._lock = asyncio.Lock()
        self.command_max_deliver = deps.core._env_int(
            "POCKETLAB_COMMAND_MAX_DELIVER", 5
        )
        self.command_ack_wait_seconds = deps.core._env_int(
            "POCKETLAB_COMMAND_ACK_WAIT_SECONDS", 60
        )
        self.event_fanout_enabled = deps.core._env_bool(
            "POCKETLAB_NATS_EVENT_FANOUT", True
        )
        self.durable_consumers: dict[str, str] = {}
        self._last_error: str = ""
        self._watchdog_task: asyncio.Task[None] | None = None
        self._reconnect_task: asyncio.Task[None] | None = None
        self._stopping = False
        self._last_connected_at = ""
        self._last_disconnected_at = ""
        self._flush_lock = asyncio.Lock()
        self._transient_invalid_state_errors = 0
        self._last_transient_invalid_state_at = ""
        self._durable_lock = asyncio.Lock()
        self._durable_specs: dict[str, DurableConsumerSpec] = {}
        self._durable_subscriptions: dict[str, Any] = {}
        self._durable_tasks: dict[str, asyncio.Task[None]] = {}
        self._durable_generation: dict[str, int] = {}
        self._durable_started_monotonic: dict[str, float] = {}
        self._durable_last_fetch_monotonic: dict[str, float] = {}
        self._durable_last_fetch_at: dict[str, str] = {}
        self._durable_last_message_at: dict[str, str] = {}
        self._durable_last_callback_at: dict[str, str] = {}
        self._durable_callback_inflight: dict[str, bool] = {}
        self._durable_last_error: dict[str, str] = {}
        self._durable_recoveries: dict[str, int] = {}

    def _client_is_connected(self) -> bool:
        nc = self.nc
        if nc is None:
            return False
        try:
            return bool(nc.is_connected)
        except Exception:
            return False

    def _schedule_reconnect(self) -> None:
        if self._stopping or nats is None:
            return
        task = self._reconnect_task
        if task is not None and not task.done():
            return
        try:
            self._reconnect_task = asyncio.create_task(
                self._reconnect_loop(), name="pocketlab-nats-reconnect"
            )
        except RuntimeError:
            # A callback can race with event-loop shutdown. Lifespan startup will
            # establish the next connection instead of creating an orphan task.
            self._reconnect_task = None

    async def _nats_error(self, exc: Exception) -> None:
        """Record client errors and recover only when the real client is down.

        nats-py can surface an asyncio InvalidStateError when a late PONG races
        with a completed flush future. Treat that exact condition as transient
        while the underlying client is still connected; the watchdog remains
        authoritative for real disconnects.
        """
        if isinstance(exc, asyncio.InvalidStateError) and self._client_is_connected():
            self._transient_invalid_state_errors += 1
            self._last_transient_invalid_state_at = deps.now_utc_iso()
            return
        self._last_error = f"{exc.__class__.__name__}: {exc}"
        if self._client_is_connected():
            return
        self.connected = False
        self.fallback_reason = self._last_error
        self._last_disconnected_at = deps.now_utc_iso()
        self._schedule_reconnect()

    async def _nats_disconnected(self) -> None:
        self.connected = False
        self.fallback_reason = "NATS disconnected"
        self._last_disconnected_at = deps.now_utc_iso()
        self._schedule_reconnect()

    async def _nats_reconnected(self) -> None:
        self.connected = self._client_is_connected()
        if self.connected:
            self.fallback_reason = ""
            self._last_error = ""
            self._last_connected_at = deps.now_utc_iso()
            try:
                asyncio.create_task(
                    self.recover_durable_consumers(force=True),
                    name="pocketlab-durable-reconnect-recovery",
                )
            except RuntimeError:
                # Event-loop shutdown owns cleanup in this race.
                pass

    async def _nats_closed(self) -> None:
        self.connected = False
        self.fallback_reason = "NATS connection closed"
        self._last_disconnected_at = deps.now_utc_iso()
        self._schedule_reconnect()

    async def _close_stale_client(self) -> None:
        stale = self.nc
        await self._dispose_all_durable_consumers(
            forget_specs=False, shutdown=False
        )
        self.nc = None
        self.js = None
        self.connected = False
        self._nats_subscriptions.clear()
        if stale is not None:
            with contextlib.suppress(Exception):
                await stale.close()

    async def _reconnect_loop(self) -> None:
        delay = max(0.25, float(os.environ.get("POCKETLAB_NATS_RECONNECT_MIN_SECONDS", "1")))
        maximum = max(delay, float(os.environ.get("POCKETLAB_NATS_RECONNECT_MAX_SECONDS", "30")))
        try:
            while not self._stopping:
                if self._client_is_connected():
                    self.connected = True
                    self.fallback_reason = ""
                    self._last_connected_at = deps.now_utc_iso()
                    return
                try:
                    await self.start()
                except Exception as exc:
                    self._last_error = f"{exc.__class__.__name__}: {exc}"
                    self.fallback_reason = self._last_error
                if self._client_is_connected():
                    return
                await asyncio.sleep(delay)
                delay = min(maximum, delay * 2)
        except asyncio.CancelledError:
            raise
        finally:
            if asyncio.current_task() is self._reconnect_task:
                self._reconnect_task = None

    async def _watchdog_loop(self) -> None:
        interval = max(2.0, float(os.environ.get("POCKETLAB_NATS_WATCHDOG_SECONDS", "5")))
        try:
            while not self._stopping:
                actual = self._client_is_connected()
                self.connected = actual
                if actual:
                    self.fallback_reason = ""
                    with contextlib.suppress(Exception):
                        await self.recover_durable_consumers()
                else:
                    if not self.fallback_reason:
                        self.fallback_reason = "NATS client connection lost"
                    self._schedule_reconnect()
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            raise

    async def start_watchdog(self) -> None:
        if self._watchdog_task is not None and not self._watchdog_task.done():
            return
        self._stopping = False
        self._watchdog_task = asyncio.create_task(
            self._watchdog_loop(), name="pocketlab-nats-watchdog"
        )

    async def stop_watchdog(self) -> None:
        self._stopping = True
        current = asyncio.current_task()
        tasks = [self._watchdog_task, self._reconnect_task]
        for task in tasks:
            if task is not None and task is not current and not task.done():
                task.cancel()
        for task in tasks:
            if task is not None and task is not current:
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await task
        self._watchdog_task = None
        self._reconnect_task = None

    async def start(self) -> None:
        async with self._lock:
            if self._client_is_connected():
                self.connected = self._client_is_connected()
                self.fallback_reason = ""
                self._last_error = ""
                self._last_connected_at = deps.now_utc_iso()
                return
            if nats is None:
                self.fallback_reason = (
                    "nats-py is not installed; production NATS is required"
                )
                raise RuntimeError(self.fallback_reason)
            try:
                await self._close_stale_client()
                connect_kwargs = {
                    "servers": self.servers,
                    "name": self.name,
                    "connect_timeout": self.connect_timeout,
                    "reconnect_time_wait": float(os.environ.get("POCKETLAB_NATS_RECONNECT_WAIT", "2")),
                    "max_reconnect_attempts": -1,
                    "ping_interval": float(os.environ.get("POCKETLAB_NATS_PING_INTERVAL", "20")),
                    "max_outstanding_pings": int(os.environ.get("POCKETLAB_NATS_MAX_OUTSTANDING_PINGS", "3")),
                    "error_cb": self._nats_error,
                    "disconnected_cb": self._nats_disconnected,
                    "reconnected_cb": self._nats_reconnected,
                    "closed_cb": self._nats_closed,
                }
                if self.user:
                    connect_kwargs["user"] = self.user
                if self.password:
                    connect_kwargs["password"] = self.password
                if self.token:
                    connect_kwargs["token"] = self.token
                if self.tls_required or self.tls_ca or self.tls_cert:
                    context = (
                        ssl.create_default_context(cafile=self.tls_ca)
                        if self.tls_ca
                        else ssl.create_default_context()
                    )
                    if self.tls_cert and self.tls_key:
                        context.load_cert_chain(self.tls_cert, self.tls_key)
                    connect_kwargs["tls"] = context
                self.nc = await nats.connect(**connect_kwargs)
                self.connected = True
                self.fallback_reason = ""
                if self.jetstream_enabled:
                    self.js = self.nc.jetstream()
                    await self.ensure_streams()
                if self.require_jetstream and self.js is None:
                    raise RuntimeError("JetStream is required but unavailable")
                await self._subscribe_event_fanout()
                await self.recover_durable_consumers(force=True)
            except Exception as exc:
                await self._close_stale_client()
                self.fallback_reason = str(exc)
                raise RuntimeError(
                    f"NATS connection failed: {self.fallback_reason}"
                ) from exc

    async def _subscribe_event_fanout(self) -> None:
        if not self.nc or not self.event_fanout_enabled:
            return

        async def _fanout(msg: Any) -> None:
            try:
                payload = json.loads(msg.data.decode("utf-8"))
                if isinstance(payload, dict):
                    self._record(payload)
                    self.received += 1
            except Exception:
                return

        for subject in ("pocketlab.events.>", "pocketlab.audit.>"):
            sub = await self.nc.subscribe(subject, cb=_fanout)
            self._nats_subscriptions.append(sub)

    async def stop(self) -> None:
        await self.stop_watchdog()
        await self._dispose_all_durable_consumers(
            forget_specs=True, shutdown=True
        )
        async with self._lock:
            for sub in list(self._nats_subscriptions):
                with contextlib.suppress(Exception):
                    await sub.unsubscribe()
            self._nats_subscriptions.clear()
            if self.nc is not None:
                with contextlib.suppress(Exception):
                    await self.nc.drain()
                with contextlib.suppress(Exception):
                    await self.nc.close()
            self.nc = None
            self.js = None
            self.connected = False

    async def ensure_streams(self) -> None:
        if not self.js:
            if self.require_jetstream:
                raise RuntimeError("JetStream is required but unavailable")
            return
        max_msgs = deps.core._env_int("POCKETLAB_JETSTREAM_MAX_MSGS", 50000)
        max_bytes = deps.core._env_int(
            "POCKETLAB_JETSTREAM_MAX_BYTES", 256 * 1024 * 1024
        )
        for stream, subjects in DEFAULT_STREAMS.items():
            kwargs = {"name": stream, "subjects": subjects, "max_msgs": max_msgs}
            # nats-py versions differ in accepted stream kwargs. Try the richer
            # enterprise retention config first, then fall back to the minimal
            # config used by earlier Pocket Lab phases.
            try:
                await self.js.add_stream(**{**kwargs, "max_bytes": max_bytes})
            except TypeError:
                with contextlib.suppress(Exception):
                    await self.js.add_stream(**kwargs)
            except Exception:
                with contextlib.suppress(Exception):
                    await self.js.update_stream(**{**kwargs, "max_bytes": max_bytes})
                with contextlib.suppress(Exception):
                    await self.js.update_stream(**kwargs)

    def envelope(
        self,
        subject: str,
        event_type: str,
        data: Dict[str, Any] | None = None,
        *,
        trace_id: str | None = None,
    ) -> Dict[str, Any]:
        return {
            "id": uuid.uuid4().hex,
            "type": event_type,
            "subject": subject,
            "time": deps.now_utc_iso(),
            "source": self.name,
            "trace_id": trace_id,
            "data": data or {},
        }

    def prepare_json_event(
        self,
        subject: str,
        event_type: str,
        data: Dict[str, Any] | None = None,
        *,
        trace_id: str | None = None,
    ) -> tuple[Dict[str, Any], bytes]:
        """Build and encode one event outside the event loop when requested."""
        event = self.envelope(subject, event_type, data, trace_id=trace_id)
        payload = json.dumps(event, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
        return event, payload

    async def publish_prepared_json(
        self,
        subject: str,
        event: Dict[str, Any],
        payload: bytes,
    ) -> Dict[str, Any]:
        """Publish a pre-encoded event without rebuilding or serializing it."""
        if self.connected and self.nc is not None:
            try:
                if self.js is not None and (
                    subject.startswith("pocketlab.commands.")
                    or subject.startswith("pocketlab.audit.")
                    or subject.startswith("pocketlab.dlq.")
                ):
                    await self.js.publish(subject, payload)
                else:
                    await self.nc.publish(subject, payload)
            except Exception as exc:
                self.connected = False
                self.fallback_reason = str(exc)
                await self._close_stale_client()
                raise RuntimeError(
                    f"NATS connection failed: {self.fallback_reason}"
                ) from exc
        self.published += 1
        self._record(event)
        return event

    async def publish_json(
        self,
        subject: str,
        event_type: str,
        data: Dict[str, Any] | None = None,
        *,
        trace_id: str | None = None,
    ) -> Dict[str, Any]:
        event = self.envelope(subject, event_type, data, trace_id=trace_id)
        payload = json.dumps(event, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
        if self.connected and self.nc is not None:
            try:
                if self.js is not None and (
                    subject.startswith("pocketlab.commands.")
                    or subject.startswith("pocketlab.audit.")
                    or subject.startswith("pocketlab.dlq.")
                ):
                    await self.js.publish(subject, payload)
                else:
                    # Core NATS publish is already buffered and drained by the
                    # client writer task. Flushing after every event creates a
                    # large number of ping/PONG futures and can trigger the
                    # nats-py InvalidStateError race seen on Android/Termux.
                    await self.nc.publish(subject, payload)
            except Exception as exc:
                self.connected = False
                self.fallback_reason = str(exc)
                await self._close_stale_client()
                raise RuntimeError(
                    f"NATS connection failed: {self.fallback_reason}"
                ) from exc
        self.published += 1
        self._record(event)
        return event

    def _record(self, event: Dict[str, Any]) -> None:
        event_id = str(event.get("id") or "")
        if event_id:
            if event_id in self._seen_event_id_set:
                return
            self._seen_event_ids.append(event_id)
            self._seen_event_id_set.add(event_id)
            while len(self._seen_event_id_set) > self._seen_event_ids.maxlen:
                old = self._seen_event_ids.popleft()
                self._seen_event_id_set.discard(old)
        # Phase 12: persist every event to the event-sourced workflow journal
        # before in-memory fanout, so dead-letter/recovery can reconstruct state
        # after API/worker restarts.  This is best effort; the event bus must not
        # fail user workflows if the local projection file is temporarily locked.
        try:
            from .workflow_engine import WORKFLOW_ENGINE

            WORKFLOW_ENGINE.ingest_event(event)
        except Exception:
            pass
        self._history.append(event)
        subject = str(event.get("subject") or "")
        if subject.startswith("pocketlab.events.fleet.node_"):
            try:
                from .fleet_registry import handle_agent_event

                handle_agent_event(event)
            except Exception:
                pass
        stale: list[asyncio.Queue[Dict[str, Any]]] = []
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                stale.append(queue)
        for queue in stale:
            self._subscribers.discard(queue)

    async def subscribe_nats(
        self,
        subject: str,
        callback: Callable[[Any], Awaitable[None]],
        *,
        queue: str | None = None,
    ) -> Any:
        """Subscribe to a live NATS subject when the real bus is connected.

        Workers and control-plane services use this for live NATS subjects.
        There is no memory-backed command queue in production mode.
        """
        if not self.connected or self.nc is None:
            raise RuntimeError(self.fallback_reason or "NATS is not connected")
        sub = await self.nc.subscribe(subject, queue=queue, cb=callback)
        self._nats_subscriptions.append(sub)
        return sub

    def durable_consumer_status(self, durable: str | None = None) -> Dict[str, Any]:
        names = [durable] if durable else sorted(self._durable_specs)
        now = time.monotonic()
        payload: dict[str, Any] = {}
        for name in names:
            if not name:
                continue
            task = self._durable_tasks.get(name)
            started = self._durable_started_monotonic.get(name, 0.0)
            last_fetch = self._durable_last_fetch_monotonic.get(name, 0.0)
            inflight = bool(self._durable_callback_inflight.get(name))
            task_alive = bool(task is not None and not task.done())
            payload[name] = {
                "subject": self.durable_consumers.get(name, ""),
                "task_alive": task_alive,
                "subscription_present": name in self._durable_subscriptions,
                "callback_inflight": inflight,
                "healthy": bool(
                    task_alive
                    and name in self._durable_subscriptions
                    and (self._client_is_connected() or inflight)
                ),
                "generation": int(self._durable_generation.get(name, 0)),
                "recoveries": int(self._durable_recoveries.get(name, 0)),
                "task_age_seconds": round(max(0.0, now - started), 3)
                if started
                else None,
                "fetch_age_seconds": round(max(0.0, now - last_fetch), 3)
                if last_fetch
                else None,
                "last_fetch_at": self._durable_last_fetch_at.get(name, ""),
                "last_message_at": self._durable_last_message_at.get(name, ""),
                "last_callback_at": self._durable_last_callback_at.get(name, ""),
                "last_error_type": self._durable_last_error.get(name, ""),
            }
        if durable:
            return payload.get(durable, {})
        return payload

    async def _dispose_durable_consumer_locked(
        self,
        durable: str,
        *,
        forget_spec: bool,
        shutdown: bool,
    ) -> None:
        task = self._durable_tasks.get(durable)
        inflight = bool(self._durable_callback_inflight.get(durable))
        if task is not None and not task.done() and (shutdown or not inflight):
            task.cancel()
            if task is not asyncio.current_task():
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await task
        if task is None or task.done() or shutdown or not inflight:
            self._durable_tasks.pop(durable, None)
            sub = self._durable_subscriptions.pop(durable, None)
            if sub is not None:
                with contextlib.suppress(Exception):
                    await sub.unsubscribe()
        if forget_spec:
            self._durable_specs.pop(durable, None)
            self.durable_consumers.pop(durable, None)

    async def _dispose_all_durable_consumers(
        self, *, forget_specs: bool, shutdown: bool
    ) -> None:
        async with self._durable_lock:
            names = set(self._durable_specs) | set(self._durable_tasks)
            for durable in sorted(names):
                await self._dispose_durable_consumer_locked(
                    durable, forget_spec=forget_specs, shutdown=shutdown
                )

    async def _start_durable_consumer(
        self, durable: str, *, force: bool = False
    ) -> Any:
        spec = self._durable_specs.get(durable)
        if spec is None:
            raise RuntimeError(f"Durable consumer {durable} is not registered")
        if not self.connected or self.nc is None:
            await self.start()
        if self.js is None:
            raise RuntimeError("JetStream is required for durable command consumption")

        async with self._durable_lock:
            existing_task = self._durable_tasks.get(durable)
            existing_sub = self._durable_subscriptions.get(durable)
            inflight = bool(self._durable_callback_inflight.get(durable))
            if (
                existing_task is not None
                and not existing_task.done()
                and existing_sub is not None
                and (not force or inflight)
            ):
                return existing_sub

            replacing = existing_task is not None or existing_sub is not None
            await self._dispose_durable_consumer_locked(
                durable, forget_spec=False, shutdown=False
            )
            if bool(self._durable_callback_inflight.get(durable)):
                # Never cancel a command callback that is already executing.
                return self._durable_subscriptions.get(durable)

            try:
                sub = await self.js.pull_subscribe(
                    spec.subject,
                    durable=spec.durable,
                    stream=spec.stream,
                )
            except Exception as exc:
                self._durable_last_error[durable] = type(exc).__name__
                raise RuntimeError(
                    f"JetStream durable pull consumer setup failed for {spec.subject}: "
                    f"{type(exc).__name__}"
                ) from exc

            generation = int(self._durable_generation.get(durable, 0)) + 1
            self._durable_generation[durable] = generation
            if replacing:
                self._durable_recoveries[durable] = int(
                    self._durable_recoveries.get(durable, 0)
                ) + 1
            self._durable_subscriptions[durable] = sub
            self._durable_started_monotonic[durable] = time.monotonic()
            self._durable_last_fetch_monotonic[durable] = time.monotonic()
            self._durable_last_fetch_at[durable] = deps.now_utc_iso()
            self._durable_last_error[durable] = ""
            self._durable_callback_inflight[durable] = False

            async def _pull_loop() -> None:
                try:
                    while not self._stopping:
                        try:
                            messages = await sub.fetch(batch=8, timeout=1)
                            self._durable_last_fetch_monotonic[durable] = time.monotonic()
                            self._durable_last_fetch_at[durable] = deps.now_utc_iso()
                        except TimeoutError:
                            self._durable_last_fetch_monotonic[durable] = time.monotonic()
                            self._durable_last_fetch_at[durable] = deps.now_utc_iso()
                            continue
                        except asyncio.CancelledError:
                            raise
                        except Exception as exc:
                            self._durable_last_error[durable] = type(exc).__name__
                            return

                        for msg in messages:
                            self._durable_last_message_at[durable] = deps.now_utc_iso()
                            self._durable_callback_inflight[durable] = True
                            try:
                                await spec.callback(msg)
                            finally:
                                self._durable_callback_inflight[durable] = False
                                self._durable_last_callback_at[durable] = deps.now_utc_iso()
                finally:
                    self._durable_callback_inflight[durable] = False

            task = asyncio.create_task(
                _pull_loop(),
                name=f"pocketlab-durable-{durable}-{generation}",
            )
            self._durable_tasks[durable] = task
            return sub

    async def ensure_durable_consumer(
        self,
        durable: str,
        *,
        stale_seconds: float | None = None,
        force: bool = False,
    ) -> bool:
        if durable not in self._durable_specs:
            return False
        task = self._durable_tasks.get(durable)
        inflight = bool(self._durable_callback_inflight.get(durable))
        task_alive = bool(task is not None and not task.done())
        sub_present = durable in self._durable_subscriptions
        stale_limit = max(3.0, float(
            stale_seconds
            if stale_seconds is not None
            else os.environ.get("POCKETLAB_NATS_DURABLE_STALE_SECONDS", "15")
        ))
        last_fetch = self._durable_last_fetch_monotonic.get(
            durable, self._durable_started_monotonic.get(durable, 0.0)
        )
        stale = bool(
            last_fetch
            and time.monotonic() - last_fetch > stale_limit
            and not inflight
        )
        if task_alive and sub_present and not stale and not force:
            return False
        if inflight:
            return False
        await self._start_durable_consumer(durable, force=True)
        return True

    async def recover_durable_consumers(self, *, force: bool = False) -> list[str]:
        if not self._client_is_connected() or self.js is None:
            return []
        recovered: list[str] = []
        for durable in sorted(self._durable_specs):
            try:
                if await self.ensure_durable_consumer(durable, force=force):
                    recovered.append(durable)
            except Exception as exc:
                self._durable_last_error[durable] = type(exc).__name__
        return recovered

    async def subscribe_durable(
        self,
        subject: str,
        callback: Callable[[Any], Awaitable[None]],
        *,
        durable: str,
        queue: str | None = None,
        stream: str = "POCKETLAB_COMMANDS",
    ) -> Any:
        """Register and supervise one JetStream durable pull consumer."""
        if not durable.strip():
            raise ValueError("Durable consumer name is required")
        spec = DurableConsumerSpec(
            subject=subject,
            callback=callback,
            durable=durable,
            queue=queue,
            stream=stream,
        )
        current = self._durable_specs.get(durable)
        if current is not None and (
            current.subject != spec.subject or current.stream != spec.stream
        ):
            raise RuntimeError(
                f"Durable consumer {durable} is already registered for another subject"
            )
        self._durable_specs[durable] = spec
        self.durable_consumers[durable] = subject
        return await self._start_durable_consumer(durable)


    async def ack_message(self, msg: Any) -> None:
        with contextlib.suppress(Exception):
            await msg.ack()

    async def nak_message(self, msg: Any, *, delay: int | None = None) -> None:
        with contextlib.suppress(TypeError):
            await msg.nak(delay=delay)
            return
        with contextlib.suppress(Exception):
            await msg.nak()

    async def term_message(self, msg: Any) -> None:
        with contextlib.suppress(Exception):
            await msg.term()
            return
        await self.ack_message(msg)

    def delivery_attempt(self, msg: Any) -> int:
        meta = getattr(msg, "metadata", None)
        delivered = getattr(meta, "num_delivered", None) if meta is not None else None
        try:
            return int(delivered or 1)
        except Exception:
            return 1

    async def dead_letter(
        self,
        *,
        original_subject: str,
        command: Dict[str, Any],
        error: str,
        attempt: int,
    ) -> Dict[str, Any]:
        from .reliability import append_dead_letter

        record = append_dead_letter(
            {
                "original_subject": original_subject,
                "command": {
                    k: v
                    for k, v in dict(command).items()
                    if k not in {"api_key", "token", "password", "secret"}
                },
                "error": error,
                "attempt": attempt,
                "job_id": command.get("job_id"),
                "command_id": command.get("command_id"),
            }
        )
        await self.publish_json(
            f"pocketlab.dlq.{original_subject.replace('.', '_')}",
            "command.dead_lettered",
            record,
            trace_id=str(
                command.get("trace_id")
                or command.get("job_id")
                or command.get("command_id")
                or ""
            ),
        )
        await self.publish_json(
            "pocketlab.events.command.dead_lettered",
            "command.dead_lettered",
            {
                "original_subject": original_subject,
                "attempt": attempt,
                "error": error,
                "job_id": command.get("job_id"),
                "command_id": command.get("command_id"),
            },
            trace_id=str(
                command.get("trace_id")
                or command.get("job_id")
                or command.get("command_id")
                or ""
            ),
        )
        return record

    async def flush(self) -> None:
        """Explicit durability barrier for callers that truly require one.

        The lock prevents concurrent flush futures from competing for the same
        PONG. Routine publishes intentionally do not call this method.
        """
        if not self._client_is_connected() or self.nc is None:
            return
        async with self._flush_lock:
            try:
                await self.nc.flush(timeout=1)
            except asyncio.InvalidStateError as exc:
                if self._client_is_connected():
                    self._transient_invalid_state_errors += 1
                    self._last_transient_invalid_state_at = deps.now_utc_iso()
                    return
                await self._nats_error(exc)
                raise

    def recent(
        self, limit: int = 100, subject_prefix: str = ""
    ) -> list[Dict[str, Any]]:
        items = list(self._history)
        if subject_prefix:
            items = [
                item
                for item in items
                if str(item.get("subject", "")).startswith(subject_prefix)
            ]
        return items[-max(1, min(limit, self.history_limit)) :]

    def status(self) -> Dict[str, Any]:
        actual = self._client_is_connected()
        self.connected = actual
        if actual:
            self.fallback_reason = ""
        mode = "nats" if actual else "nats-required-unavailable"
        reconnect_pending = bool(
            self._reconnect_task is not None and not self._reconnect_task.done()
        )
        return BusStatus(
            mode=mode,
            connected=actual,
            servers=self.servers,
            jetstream_enabled=bool(actual and self.js is not None),
            fallback_reason="" if actual else self.fallback_reason,
            published=self.published,
            received=self.received,
        ).__dict__ | {
            "nats_required": self.required,
            "jetstream_required": self.require_jetstream,
            "auth_configured": bool(self.user or self.token),
            "tls_configured": bool(self.tls_required or self.tls_ca or self.tls_cert),
            "durable_consumers": dict(self.durable_consumers),
            "command_max_deliver": self.command_max_deliver,
            "command_ack_wait_seconds": self.command_ack_wait_seconds,
            "streams": list(DEFAULT_STREAMS.keys()),
            "last_error": self._last_error,
            "last_connected_at": self._last_connected_at,
            "last_disconnected_at": self._last_disconnected_at,
            "reconnect_pending": reconnect_pending,
            "watchdog_running": bool(
                self._watchdog_task is not None and not self._watchdog_task.done()
            ),
            "transient_invalid_state_errors": self._transient_invalid_state_errors,
            "last_transient_invalid_state_at": self._last_transient_invalid_state_at,
            "durable_consumer_health": self.durable_consumer_status(),
        }

    async def subscribe_local(
        self, *, replay: int = 25
    ) -> AsyncIterator[Dict[str, Any]]:
        queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue(maxsize=200)
        self._subscribers.add(queue)
        try:
            for event in self.recent(limit=replay):
                yield event
            while True:
                event = await queue.get()
                self.received += 1
                yield event
        finally:
            self._subscribers.discard(queue)


BUS = PocketLabEventBus()


async def get_bus() -> PocketLabEventBus:
    if not BUS.connected and not BUS.fallback_reason:
        await BUS.start()
    return BUS
