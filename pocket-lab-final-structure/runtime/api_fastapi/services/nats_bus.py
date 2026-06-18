from __future__ import annotations

import asyncio
import contextlib
import json
import os
import ssl
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
        self.durable_consumers: dict[str, str] = {}

    async def start(self) -> None:
        async with self._lock:
            if self.connected:
                return
            if nats is None:
                self.fallback_reason = (
                    "nats-py is not installed; production NATS is required"
                )
                raise RuntimeError(self.fallback_reason)
            try:
                connect_kwargs = {
                    "servers": self.servers,
                    "name": self.name,
                    "connect_timeout": self.connect_timeout,
                    "reconnect_time_wait": 2,
                    "max_reconnect_attempts": -1,
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
            except Exception as exc:
                self.nc = None
                self.js = None
                self.connected = False
                self.fallback_reason = str(exc)
                raise RuntimeError(
                    f"NATS connection failed: {self.fallback_reason}"
                ) from exc

    async def _subscribe_event_fanout(self) -> None:
        if not self.nc:
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
                    await self.nc.publish(subject, payload)
                    await self.nc.flush(timeout=1)
            except Exception as exc:
                self.connected = False
                self.fallback_reason = str(exc)
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

    async def subscribe_durable(
        self,
        subject: str,
        callback: Callable[[Any], Awaitable[None]],
        *,
        durable: str,
        queue: str | None = None,
        stream: str = "POCKETLAB_COMMANDS",
    ) -> Any:
        """Subscribe with a JetStream pull durable consumer.

        Enterprise behavior:
        - Uses JetStream durable pull consumption.
        - Uses manual ack.
        - Does not use volatile NATS delivery.
        - Does not use in-memory command fallback.
        - Avoids push-consumer deliver-subject binding conflicts.
        """
        if not self.connected or self.nc is None:
            await self.start()

        if self.js is None:
            raise RuntimeError("JetStream is required for durable command consumption")

        self.durable_consumers[durable] = subject

        try:
            sub = await self.js.pull_subscribe(
                subject,
                durable=durable,
                stream=stream,
            )
        except Exception as exc:
            raise RuntimeError(
                f"JetStream durable pull consumer setup failed for {subject}: {exc}"
            ) from exc

        async def _pull_loop() -> None:
            import asyncio

            while True:
                try:
                    messages = await sub.fetch(batch=8, timeout=1)
                    for msg in messages:
                        await callback(msg)
                except TimeoutError:
                    continue
                except Exception:
                    await asyncio.sleep(1)
                    if not self.connected:
                        break

        task = asyncio.create_task(_pull_loop())
        if not hasattr(self, "_durable_tasks"):
            self._durable_tasks = []
        self._durable_tasks.append(task)

        return sub


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
        if self.connected and self.nc is not None:
            with contextlib.suppress(Exception):
                await self.nc.flush(timeout=1)

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
        mode = "nats" if self.connected else "nats-required-unavailable"
        return BusStatus(
            mode=mode,
            connected=self.connected,
            servers=self.servers,
            jetstream_enabled=bool(self.js is not None),
            fallback_reason=self.fallback_reason,
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
            "workflow_engine": self._workflow_status(),
        }

    def _workflow_status(self) -> Dict[str, Any]:
        try:
            from .workflow_engine import WORKFLOW_ENGINE

            return WORKFLOW_ENGINE.status()
        except Exception as exc:
            return {"status": "unavailable", "error": str(exc)}

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
