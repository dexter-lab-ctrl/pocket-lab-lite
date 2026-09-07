from __future__ import annotations

import hashlib
import json
import os
import types
from typing import Any

from .. import deps
from . import lite_device_facts, lite_device_resource_health, lite_runtime_services
from .lite_device_runtime_projection import enrich_device

_HEALTH_EXTENSION_MARKER = "_pocketlab_device_facts_health_extension_v3"
_RUNTIME_EXTENSION_MARKER = "_pocketlab_device_facts_runtime_extensions_v3"
_HEALTH_INPUT_CONTRACT_VERSION = 2


def _canonical_fact_revision(facts: Any) -> int:
    if not isinstance(facts, dict):
        return 0
    try:
        return max(0, int(facts.get("revision") or 0))
    except (TypeError, ValueError):
        return 0


def _signal_backed_facts(
    effective: dict[str, Any], signals: dict[str, Any], *, now_epoch: float | None
) -> dict[str, Any]:
    facts = (
        effective.get("device_facts")
        if isinstance(effective.get("device_facts"), dict)
        else {}
    )
    telemetry = signals.get("telemetry") if isinstance(signals.get("telemetry"), dict) else {}
    if not telemetry:
        return facts
    source = "server_central_telemetry" if (
        effective.get("is_current")
        or effective.get("protected_server_host")
        or str(effective.get("role") or "").strip().lower().replace("-", "_") == "server_host"
    ) else "agent_telemetry"
    try:
        # Reconcile the exact telemetry used by this health evaluation with any
        # already-persisted facts. Fresh current observations win; stale facts
        # remain available only when the new sample cannot provide the metric.
        return lite_device_facts.build_device_facts(
            effective,
            telemetry=telemetry,
            telemetry_source=source,
            now_epoch=now_epoch,
        )
    except Exception:
        return facts


def install_health_projection_extension() -> None:
    """Make canonical Device Facts the only resource-health input at runtime."""
    try:
        from . import lite_device_health as health_module, lite_status
    except Exception:
        return
    if getattr(health_module, _HEALTH_EXTENSION_MARKER, False):
        return
    original = health_module.evaluate_device_health

    def canonical_resource_assessment(signals, previous_resources, policy, now_iso, now_epoch):
        signals = signals if isinstance(signals, dict) else {}
        observations = signals.get("resource_observations") if isinstance(signals.get("resource_observations"), dict) else {}
        if not observations:
            # Backward-compatible ingress is normalized once into Device Facts;
            # health never consumes legacy numeric telemetry directly.
            telemetry = signals.get("telemetry") if isinstance(signals.get("telemetry"), dict) else {}
            observations = lite_device_facts.normalize_resource_observations(
                telemetry,
                source="legacy_health_ingress",
                now_epoch=now_epoch,
            )
        return lite_device_resource_health.assess_resource_observations(
            observations,
            previous_resources if isinstance(previous_resources, dict) else {},
            policy,
            now_iso,
            now_epoch,
            hysteresis_band=health_module._hysteresis_band,
            recovery_duration_guard=health_module._recovery_duration_guard,
            duration_guard=health_module._duration_guard,
        )

    # evaluate_device_health resolves this module global at call time. Replacing
    # the resource assessor preserves connection/recovery/software logic while
    # removing Device Facts -> legacy telemetry -> old health translation.
    health_module._resource_assessment = canonical_resource_assessment

    # The Server Host is synthesized by the fleet builder rather than by an
    # agent heartbeat. Supply one bounded local telemetry sample only while that
    # background builder runs. Request handlers continue to read prepared state.
    original_server_host_device = getattr(lite_status, "_server_host_device", None)
    if callable(original_server_host_device) and not getattr(
        lite_status, "_pocketlab_server_health_signals_v2", False
    ):
        def server_host_device(remote_access=None):
            device = original_server_host_device(remote_access)
            try:
                telemetry = deps.core.telemetry_snapshot()
            except Exception:
                telemetry = {}
            if isinstance(telemetry, dict) and telemetry:
                signals = dict(device.get("_health_signals") or {}) if isinstance(device.get("_health_signals"), dict) else {}
                signals["telemetry"] = telemetry
                device["_health_signals"] = signals
            return device

        lite_status._server_host_device = server_host_device
        setattr(lite_status, "_pocketlab_server_health_signals_v2", True)

    # A durable node record for the protected Server Host is merged back into
    # the synthesized host before health evaluation. The normal fleet merge is
    # intentionally shallow; an equal-rank incoming node therefore replaces the
    # private _health_signals dict wholesale. When that node copy carries no
    # telemetry, preserve the bounded central sample attached above rather than
    # turning all canonical resource observations into "missing".
    original_merge_lite_device = getattr(lite_status, "_merge_lite_device", None)
    merge_marker = "_pocketlab_server_health_signal_merge_v1"
    if callable(original_merge_lite_device) and not getattr(lite_status, merge_marker, False):
        def merge_lite_device(existing, incoming):
            merged = original_merge_lite_device(existing, incoming)
            existing_signals = (
                existing.get("_health_signals")
                if isinstance(existing, dict) and isinstance(existing.get("_health_signals"), dict)
                else {}
            )
            existing_telemetry = (
                existing_signals.get("telemetry")
                if isinstance(existing_signals.get("telemetry"), dict)
                else {}
            )
            incoming_signals = (
                incoming.get("_health_signals")
                if isinstance(incoming, dict) and isinstance(incoming.get("_health_signals"), dict)
                else {}
            )
            incoming_telemetry = (
                incoming_signals.get("telemetry")
                if isinstance(incoming_signals.get("telemetry"), dict)
                else {}
            )
            protected_existing = bool(
                isinstance(existing, dict)
                and (
                    existing.get("is_current")
                    or existing.get("protected_server_host")
                    or str(existing.get("role") or "").strip().lower().replace("-", "_") == "server_host"
                )
            )
            if protected_existing and existing_telemetry and not incoming_telemetry:
                merged_signals = (
                    dict(merged.get("_health_signals") or {})
                    if isinstance(merged.get("_health_signals"), dict)
                    else {}
                )
                merged_signals["telemetry"] = dict(existing_telemetry)
                merged["_health_signals"] = merged_signals
            return merged

        lite_status._merge_lite_device = merge_lite_device
        setattr(lite_status, merge_marker, True)

    def evaluate_device_health(device, *, signals=None, previous=None, now_epoch=None):
        signals = signals if isinstance(signals, dict) else {}
        previous = previous if isinstance(previous, dict) else {}
        effective = enrich_device(device if isinstance(device, dict) else {})
        facts = _signal_backed_facts(effective, signals, now_epoch=now_epoch)
        observations = facts.get("resources") if isinstance(facts.get("resources"), dict) else {}
        canonical_signals = dict(signals)
        if observations:
            canonical_signals["resource_observations"] = observations

        facts_revision = _canonical_fact_revision(facts)
        previous_for_evaluation = previous
        legacy_contract = facts_revision > 0 and (
            int(previous.get("source_revision") or 0) <= 0
            or int(previous.get("health_input_contract_version") or 0) < _HEALTH_INPUT_CONTRACT_VERSION
        )
        if legacy_contract:
            # Preserve prior bands/candidate timers for hysteresis, but remove the
            # old equality fence so a persisted pre-Device-Facts health row is
            # actually reevaluated once under the new input contract.
            previous_for_evaluation = dict(previous)
            previous_for_evaluation.pop("health_revision", None)

        result = original(
            effective,
            signals=canonical_signals,
            previous=previous_for_evaluation,
            now_epoch=now_epoch,
        )

        versions = dict(result.get("versions") or {}) if isinstance(result.get("versions"), dict) else {}
        software = facts.get("software") if isinstance(facts.get("software"), dict) else {}
        for component in ("node_agent", "supervisor"):
            part = versions.get(component) if isinstance(versions.get(component), dict) else {}
            fact = software.get(component) if isinstance(software.get(component), dict) else {}
            if fact:
                versions[component] = {
                    **part,
                    "version": fact.get("version") or part.get("version"),
                    "source": fact.get("source"),
                    "freshness": fact.get("freshness"),
                    "observed_at": fact.get("observed_at"),
                    "reason_code": fact.get("reason_code"),
                }
        version_status = str(versions.get("status") or "unknown")
        software_freshness = {
            str((software.get(component) or {}).get("freshness") or "missing")
            for component in ("node_agent", "supervisor")
            if isinstance(software.get(component), dict)
        }
        if version_status == "behind":
            software_status = "outdated"
        elif version_status == "incompatible":
            software_status = "incompatible"
        elif version_status == "current" and software_freshness and software_freshness <= {"stale", "missing"}:
            software_status = "stale"
        elif version_status == "current":
            software_status = "current"
        elif any((software.get(component) or {}).get("version") for component in ("node_agent", "supervisor")):
            software_status = "unknown"
        else:
            software_status = "verification_pending"
        software_posture = dict(result.get("software_posture") or {})
        software_posture.update({
            "status": software_status,
            "verification_pending": software_status == "verification_pending",
            "parts": {key: value for key, value in versions.items() if isinstance(value, dict)},
            "summary": (
                "Device software is current." if software_status == "current"
                else "Agent software update is recommended." if software_status == "outdated"
                else "Device software is incompatible." if software_status == "incompatible"
                else "Software evidence is stale." if software_status == "stale"
                else "Software version evidence is available but compatibility is unknown." if software_status == "unknown"
                else "Software verification is pending."
            ),
        })
        attention_items = [
            {**item, "source_revision": facts_revision}
            for item in (result.get("attention_items") or [])
            if isinstance(item, dict)
        ]
        return {
            **result,
            "source_revision": facts_revision,
            "health_input_contract_version": _HEALTH_INPUT_CONTRACT_VERSION,
            "resource_observations": observations,
            "versions": versions,
            "software_posture": software_posture,
            "device_facts": facts,
            "attention_items": attention_items,
            "attention_count": len(attention_items),
        }

    health_module.evaluate_device_health = evaluate_device_health
    setattr(health_module, _HEALTH_EXTENSION_MARKER, True)


def _canonical_resource_revision_material(telemetry: Any, source: str) -> dict[str, Any]:
    observations = lite_device_facts.normalize_resource_observations(
        telemetry if isinstance(telemetry, dict) else {}, source=source
    )
    return {
        metric: {
            "value": item.get("value"),
            "status": item.get("status"),
            "collection_status": item.get("collection_status"),
            "freshness": item.get("freshness"),
            "reason_code": item.get("reason_code"),
            "revision": item.get("revision"),
        }
        for metric, item in sorted(observations.items())
        if isinstance(item, dict)
    }


def _semantic_revision(namespace: str, material: Any) -> int:
    encoded = json.dumps(
        {"namespace": namespace, "material": material},
        sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str,
    )
    return max(
        1,
        int.from_bytes(hashlib.sha256(encoded.encode("utf-8")).digest()[:8], "big")
        & ((1 << 63) - 1),
    )


def _projection_dirty_generation(domain: str) -> int:
    """Return the durable cross-process invalidation generation for one job."""
    try:
        from ..db.runtime import SQLITE_READS

        entry, _ = SQLITE_READS.acquire(timeout_seconds=0.35)
    except Exception:
        return 0
    discard = False
    try:
        row = entry.connection.execute(
            "SELECT signal_generation FROM projection_dirty_signals WHERE domain=?",
            (str(domain or "")[:120],),
        ).fetchone()
        return max(0, int(row["signal_generation"] or 0)) if row is not None else 0
    except Exception:
        discard = True
        return 0
    finally:
        SQLITE_READS.release(entry, discard=discard)


def install_status_projection_extension() -> None:
    """Make canonical Server Host Device Facts part of the prepared `/status` contract."""
    try:
        from . import lite_status
    except Exception:
        return
    marker = "_pocketlab_device_facts_status_extension_v2"
    if getattr(lite_status, marker, False):
        return

    original_build = lite_status._build_lite_status_from_inputs
    original_default = lite_status.default_lite_status_state

    def lite_telemetry(payload: dict[str, Any]) -> dict[str, Any]:
        payload = payload if isinstance(payload, dict) else {}

        def first(*keys: str) -> Any:
            for key in keys:
                if key in payload and payload.get(key) is not None:
                    return payload.get(key)
            return None

        result = {
            "status": lite_status._status(payload.get("status", "unknown")),
            "cpu_temp_c": first("cpu_temp_c", "cpuTemp"),
            "free_space_mb": first("free_space_mb", "freeSpaceMB"),
            "total_space_mb": first("total_space_mb", "totalSpaceMB"),
            "pocketlab_workload_cpu_percent": first("pocketlab_workload_cpu_percent"),
            "pocketlab_workload_process_count": first("pocketlab_workload_process_count"),
            "memory_usage_mb": first("memory_usage_mb"),
            "memory_total_mb": first("memory_total_mb", "memoryTotalMB"),
            "memory_free_mb": first("memory_free_mb", "memoryFreeMB"),
            "sampled_at": first("sampled_at", "timestamp", "time", "updated_at"),
            "schema_version": payload.get("schema_version"),
            "resource_observations": payload.get("resource_observations")
            if isinstance(payload.get("resource_observations"), dict)
            else {},
        }
        if isinstance(payload.get("devices"), list) or isinstance(payload.get("counts"), dict):
            result.update({
                "summary": str(payload.get("summary") or "Telemetry is not available.")[:192],
                "counts": payload.get("counts") if isinstance(payload.get("counts"), dict) else {},
                "device_count": len(payload.get("devices") or []),
                "semantic": True,
            })
        return result

    def build_from_inputs(*, checked_at, engine, bus, live, remote_access, telemetry, fleet, fleet_nodes, current_state):
        payload = original_build(
            checked_at=checked_at,
            engine=engine,
            bus=bus,
            live=live,
            remote_access=remote_access,
            telemetry=telemetry,
            fleet=fleet,
            fleet_nodes=fleet_nodes,
            current_state=current_state,
        )
        server_id = lite_status.normalize_node_id(
            os.environ.get("POCKETLAB_SERVER_NODE_ID")
            or os.environ.get("POCKETLAB_NODE_ID")
            or "pocket-lab-lite-server"
        )
        device = dict(payload.get("device") or {})
        device.update({
            "id": server_id,
            "role": "server_host",
            "is_current": True,
            "protected_server_host": True,
        })
        facts = lite_device_facts.build_device_facts(
            device,
            telemetry=telemetry if isinstance(telemetry, dict) else {},
            telemetry_source="server_central_telemetry",
        )
        device["device_facts"] = facts
        payload["device"] = device
        payload["device_facts"] = facts
        payload["resource_observations"] = facts.get("resources") or {}
        payload["telemetry"] = lite_telemetry(telemetry if isinstance(telemetry, dict) else {})
        payload["sanitized"] = True
        return payload

    def default_state():
        payload = original_default()
        server_id = lite_status.normalize_node_id(
            os.environ.get("POCKETLAB_SERVER_NODE_ID")
            or os.environ.get("POCKETLAB_NODE_ID")
            or "pocket-lab-lite-server"
        )
        facts = lite_device_facts.build_device_facts(
            {"id": server_id, "role": "server_host", "is_current": True},
            telemetry={}, telemetry_source="server_central_telemetry",
        )
        device = dict(payload.get("device") or {})
        device.update({
            "id": server_id, "role": "server_host", "is_current": True,
            "protected_server_host": True, "device_facts": facts,
        })
        payload.update({
            "device": device,
            "device_facts": facts,
            "resource_observations": {},
            "sanitized": True,
        })
        return payload

    lite_status._lite_telemetry = lite_telemetry
    lite_status._build_lite_status_from_inputs = build_from_inputs
    lite_status.default_lite_status_state = default_state
    setattr(lite_status, marker, True)


def install_source_revision_extensions() -> None:
    """Refresh prepared facts on canonical observation changes across API/worker processes."""
    try:
        from . import fleet_registry, lite_phase3b_projections as phase3b, lite_status
        from .live_status import LIVE_STATUS
    except Exception:
        return
    marker = "_pocketlab_device_facts_source_revision_v2"
    if getattr(phase3b, marker, False):
        return

    original_status_revision = phase3b.status_source_revision
    original_fleet_revision = fleet_registry.fleet_source_revision
    original_builder_for = phase3b.builder_for
    original_source_revision_for = phase3b.source_revision_for

    def status_source_revision() -> int:
        try:
            resources = _canonical_resource_revision_material(
                LIVE_STATUS.last_telemetry_snapshot(), "server_central_telemetry"
            )
        except Exception:
            resources = {}
        return _semantic_revision(
            "system.status.device_facts",
            {
                "base_revision": int(original_status_revision()),
                # This durable generation is the cross-process fence. The API
                # increments it when its canonical telemetry revision changes;
                # the worker can therefore observe invalidation without reading
                # the API process's in-memory LiveStatus sample.
                "device_facts_generation": _projection_dirty_generation("system.status"),
                "resources": resources,
            },
        )

    def fleet_source_revision() -> int:
        agents: list[dict[str, Any]] = []
        try:
            for raw in fleet_registry.list_agents(include_stale=True)[:512]:
                if not isinstance(raw, dict):
                    continue
                telemetry = raw.get("telemetry") if isinstance(raw.get("telemetry"), dict) else {}
                agents.append({
                    "id": str(raw.get("node_id") or raw.get("id") or "")[:120],
                    "resources": _canonical_resource_revision_material(telemetry, "agent_telemetry"),
                    "agent_version": str(raw.get("agent_version") or "")[:80],
                    "supervisor_version": str(raw.get("supervisor_version") or "")[:80],
                })
        except Exception:
            agents = []
        try:
            server_resources = _canonical_resource_revision_material(
                LIVE_STATUS.last_telemetry_snapshot(), "server_central_telemetry"
            )
        except Exception:
            server_resources = {}
        return _semantic_revision(
            "fleet.device_facts",
            {
                "base_revision": int(original_fleet_revision()),
                "device_facts_generation": _projection_dirty_generation("fleet.summary"),
                "agents": sorted(agents, key=lambda item: item.get("id") or ""),
                "server_resources": server_resources,
            },
        )

    def builder_for(domain: str):
        if domain == "system.status":
            # Return a thunk rather than a captured function object. A prepared
            # job registered before a later adapter refresh still resolves the
            # currently installed status builder when it executes.
            return lambda: lite_status.build_lite_status_projection()
        return original_builder_for(domain)

    def source_revision_for(domain: str):
        if domain == "system.status":
            # Same late-binding rule for the semantic source fence.
            return lambda: phase3b.status_source_revision()
        return original_source_revision_for(domain)

    phase3b.status_source_revision = status_source_revision
    phase3b.builder_for = builder_for
    phase3b.source_revision_for = source_revision_for
    fleet_registry.fleet_source_revision = fleet_source_revision

    # Telemetry is sampled in the API process while projection execution is
    # worker-owned. Convert every canonical resource revision into durable dirty
    # signals so the worker cannot keep serving a prepared pre-revision snapshot.
    telemetry_marker = "_pocketlab_device_facts_telemetry_invalidation_v2"
    if not getattr(LIVE_STATUS, telemetry_marker, False):
        original_sample_telemetry = LIVE_STATUS.sample_telemetry
        last_resource_revision = {"value": 0}

        async def sample_telemetry(self, *, source="manual"):
            sample = await original_sample_telemetry(source=source)
            revision = _semantic_revision(
                "live_status.device_facts",
                _canonical_resource_revision_material(sample, "server_central_telemetry"),
            )
            changed = revision != last_resource_revision["value"]
            last_resource_revision["value"] = revision
            if changed:
                phase3b.mark_dirty(
                    "system.status", reason="canonical_device_facts_changed"
                )
                if getattr(self, "_device_health_sampler", None) is not None:
                    self.request_sample(
                        "device_health", reason="canonical_device_facts_changed"
                    )
            return sample

        LIVE_STATUS.sample_telemetry = types.MethodType(sample_telemetry, LIVE_STATUS)
        setattr(LIVE_STATUS, telemetry_marker, True)

    setattr(phase3b, marker, True)


def install_store_extension() -> None:
    try:
        from .lite_control_plane_store import CONTROL_PLANE
        from .lite_device_fact_store_extension import install_device_fact_store_extension

        install_device_fact_store_extension(CONTROL_PLANE)
    except Exception:
        return


def install_runtime_extensions() -> None:
    """Install all Device Facts adapters before the projection scheduler starts."""
    try:
        from . import lite_phase3b_projections as phase3b
    except Exception:
        return
    if getattr(phase3b, _RUNTIME_EXTENSION_MARKER, False):
        return
    # All adapters are installed before the scheduler captures builders and
    # source-revision callbacks. They only reconcile prepared/cached evidence.
    lite_runtime_services.install_phase3b_runtime_service_extension()
    install_status_projection_extension()
    install_source_revision_extensions()
    install_health_projection_extension()
    install_store_extension()
    setattr(phase3b, _RUNTIME_EXTENSION_MARKER, True)