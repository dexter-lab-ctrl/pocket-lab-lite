"""Targeted persistence/read extension for canonical Device Facts.

This module keeps the large control-plane store stable while extending its
existing prepared-SQLite contract for observation-only Device Facts refreshes.
The extension preserves semantic fleet revisions: changing metric values or
freshness refreshes current observation columns without emitting a health
transition or a fleet-domain revision reason.
"""
from __future__ import annotations

import json
import types
from typing import Any

from . import lite_control_plane_store as store_module

_EXTENSION_MARKER = "_pocketlab_device_facts_extension_v1"


def _health_values(health: dict[str, Any], updated_at: str, item: dict[str, Any] | None = None) -> dict[str, str]:
    resources = health.get("resources") if isinstance(health.get("resources"), dict) else {}
    versions = health.get("versions") if isinstance(health.get("versions"), dict) else {}
    dimensions = {
        "operational_health": health.get("operational_health") or {},
        "software_posture": health.get("software_posture") or {},
        "recovery_posture": health.get("recovery_posture") or {},
        "profile_completeness": health.get("profile_completeness") or {},
        "field_freshness": health.get("field_freshness") or {},
        "device_facts": health.get("device_facts") or ((item or {}).get("device_facts") if isinstance((item or {}).get("device_facts"), dict) else {}),
    }
    return {
        "resources_json": store_module._safe_json(resources, max_bytes=12288),
        "versions_json": store_module._safe_json(versions, max_bytes=8192),
        "source_freshness_json": store_module._safe_json(health.get("source_freshness") or {}, max_bytes=8192),
        "dimensions_json": store_module._safe_json(dimensions, max_bytes=16384),
        "updated_at": store_module._safe_text(updated_at, 64),
        "updated_at_epoch_ms": store_module._epoch_ms(updated_at),
    }


def _enrollment_overlay(control_plane: Any, device_id: str) -> dict[str, Any]:
    def read(conn):
        return conn.execute(
            "SELECT last_valid_state_json FROM device_enrollment_registry WHERE device_id=?",
            (device_id,),
        ).fetchone()

    try:
        row, _wait_ms, _query_ms = control_plane._read(read)
    except Exception:
        return {}
    if not row:
        return {}
    raw = dict(row).get("last_valid_state_json")
    try:
        payload = json.loads(raw or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    allowed = (
        "runtime_services", "restart_agent_assessment", "capability_labels",
        "dependencies", "field_freshness", "agent_version", "supervisor_version",
        "agent_version_source", "agent_version_freshness",
    )
    return {key: payload[key] for key in allowed if payload.get(key) not in (None, "", [], {})}


def install_device_fact_store_extension(control_plane: Any) -> Any:
    """Install the bounded extension once on the shared control-plane instance."""
    if getattr(control_plane, _EXTENSION_MARKER, False):
        return control_plane

    original_upsert = control_plane._upsert_device_health_row
    original_details = control_plane.device_details
    original_fleet_snapshot = control_plane.fleet_projection_snapshot

    def upsert_device_health_row(self, conn, *, device_id, item, updated_at, updated_at_epoch_ms):
        changed, reasons = original_upsert(
            conn,
            device_id=device_id,
            item=item,
            updated_at=updated_at,
            updated_at_epoch_ms=updated_at_epoch_ms,
        )
        health = item.get("proactive_health") if isinstance(item.get("proactive_health"), dict) else {}
        if not health:
            return changed, reasons
        values = _health_values(health, updated_at, item)
        row = conn.execute(
            "SELECT resources_json,versions_json,source_freshness_json,dimensions_json "
            "FROM device_health_current WHERE device_id=?",
            (device_id,),
        ).fetchone()
        if not row:
            return changed, reasons
        current = dict(row)
        observation_changed = any(
            str(current.get(column) or "") != str(values[column])
            for column in ("resources_json", "versions_json", "source_freshness_json", "dimensions_json")
        )
        if observation_changed:
            conn.execute(
                """
                UPDATE device_health_current
                   SET resources_json=?, versions_json=?, source_freshness_json=?,
                       dimensions_json=?, updated_at=?, updated_at_epoch_ms=?
                 WHERE device_id=?
                """,
                (
                    values["resources_json"], values["versions_json"],
                    values["source_freshness_json"], values["dimensions_json"],
                    values["updated_at"], values["updated_at_epoch_ms"], device_id,
                ),
            )
        # Observation refreshes intentionally keep the original semantic result.
        return changed, reasons

    def device_details(self, device_id: str):
        payload = original_details(device_id)
        device = payload.get("device") if isinstance(payload, dict) else None
        if not isinstance(device, dict):
            return payload
        device.update(_enrollment_overlay(self, str(device.get("id") or device_id)))
        health = device.get("proactive_health") if isinstance(device.get("proactive_health"), dict) else {}
        facts = health.get("device_facts") if isinstance(health.get("device_facts"), dict) else {}
        if facts:
            device["device_facts"] = facts
        return payload

    def fleet_projection_snapshot(self):
        payload = original_fleet_snapshot()
        devices = payload.get("devices") if isinstance(payload, dict) else None
        if isinstance(devices, list):
            for item in devices:
                if not isinstance(item, dict) or isinstance(item.get("device_facts"), dict):
                    continue
                health = item.get("proactive_health") if isinstance(item.get("proactive_health"), dict) else {}
                facts = health.get("device_facts") if isinstance(health.get("device_facts"), dict) else {}
                if facts:
                    item["device_facts"] = facts
        return payload

    control_plane._upsert_device_health_row = types.MethodType(upsert_device_health_row, control_plane)
    control_plane.device_details = types.MethodType(device_details, control_plane)
    control_plane.fleet_projection_snapshot = types.MethodType(fleet_projection_snapshot, control_plane)
    setattr(control_plane, _EXTENSION_MARKER, True)
    return control_plane
