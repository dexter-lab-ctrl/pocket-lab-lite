from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable

from ..db.connection import begin_immediate, connection
from ..db.migrations import apply_migrations

ROLE_ORDER = ("compute", "storage")
JOINABLE_DEVICE_ROLES = frozenset(ROLE_ORDER)
PROTECTED_DEVICE_ROLES = frozenset({"server_host"})
ROLE_ALIASES = {
    "compute": "compute",
    "app_host": "compute",
    "storage": "storage",
    "storage_node": "storage",
    "backup_target": "storage",
    "server": "server_host",
    "server_host": "server_host",
    "control_plane": "server_host",
    "control_plane_host": "server_host",
}
ROLE_LABELS = {
    "server_host": "Server Host",
    "compute": "Compute",
    "storage": "Storage",
}
ROLE_DESCRIPTIONS = {
    "server_host": "Protected Pocket Lab Lite control-plane host.",
    "compute": "Run apps and general device work.",
    "storage": "Store backups and provide recovery storage.",
}
AUTHORIZED_CAPABILITIES_BY_ROLE = {
    "server_host": frozenset({"compute", "app_host", "host_apps", "security_scanner", "run_safety_checks"}),
    "compute": frozenset({"compute", "app_host", "host_apps"}),
    "storage": frozenset({"media_storage", "backup_target", "restore_target", "provide_storage", "store_backups"}),
}
BASELINE_AGENT_CAPABILITIES = frozenset({
    "heartbeat", "telemetry", "health", "node-command", "receive_commands",
    "agent-restart", "reconnect-watchdog", "agent-supervisor", "agent-repair",
    "supervisor_recovery",
})
PHOTO_SOURCE_CAPABILITIES = frozenset({
    "media_backup_source", "photo_storage_access", "rclone_available",
    "photoprism_webdav_upload",
})
OBSERVATION_ALIASES = {
    "app_host": frozenset({"app_host", "host_apps", "compute"}),
    "compute": frozenset({"compute", "host_apps"}),
    "media_storage": frozenset({"media_storage", "provide_storage", "store_backups", "backup_target"}),
    "backup_target": frozenset({"backup_target", "store_backups"}),
    "restore_target": frozenset({"restore_target", "provide_storage"}),
    "provide_storage": frozenset({"provide_storage", "media_storage"}),
    "store_backups": frozenset({"store_backups", "backup_target"}),
}
ROLE_REASON_CODES = frozenset({
    "device_roles_required",
    "device_role_invalid",
    "device_role_not_joinable",
    "device_role_assignment_unauthorized",
    "device_role_change_requires_approval",
    "device_role_change_blocked_by_dependency",
    "device_role_change_device_offline",
    "device_role_change_identity_mismatch",
    "device_role_change_failed",
    "device_role_change_pending_verification",
    "device_capability_not_authorized",
    "device_capability_not_advertised",
    "device_capability_verification_failed",
    "device_capability_stale",
    "invite_role_set_mismatch",
})


class DeviceRoleError(RuntimeError):
    def __init__(self, reason_code: str, message: str, status_code: int = 422, *, detail: dict[str, Any] | None = None):
        super().__init__(message)
        self.reason_code = reason_code
        self.message = message
        self.status_code = int(status_code)
        self.detail = detail or {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_node_id(value: Any) -> str:
    raw = str(value or "").strip().lower()
    raw = re.sub(r"[^a-z0-9_.-]+", "-", raw).strip("-._")
    return raw[:120]


def _safe_text(value: Any, limit: int = 120) -> str:
    return " ".join(str(value or "").replace("\x00", " ").split())[:limit]


def _role_token(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def normalize_device_role(value: Any, *, joinable_only: bool = False) -> str:
    raw = _role_token(value)
    if not raw:
        raise DeviceRoleError("device_roles_required", "Choose at least one device role.")
    role = ROLE_ALIASES.get(raw)
    if not role:
        raise DeviceRoleError("device_role_invalid", "Choose a recognized Pocket Lab device role.")
    if joinable_only and role not in JOINABLE_DEVICE_ROLES:
        raise DeviceRoleError("device_role_not_joinable", "The protected Server Host role cannot be assigned through device join.")
    return role


def normalize_device_roles(
    value: Any,
    *,
    joinable_only: bool = False,
    allow_legacy_default: bool = False,
    max_roles: int = 2,
) -> list[str]:
    if value is None and allow_legacy_default:
        return ["compute"]
    if isinstance(value, str):
        source: Iterable[Any] = [part for part in value.split(",") if part.strip()]
    elif isinstance(value, (list, tuple, set)):
        source = value
    elif value is None:
        source = []
    else:
        raise DeviceRoleError("device_role_invalid", "Device roles must be a bounded list.")
    roles: list[str] = []
    for item in source:
        role = normalize_device_role(item, joinable_only=joinable_only)
        if role not in roles:
            roles.append(role)
    roles.sort(key=lambda role: (ROLE_ORDER.index(role) if role in ROLE_ORDER else 99, role))
    if not roles:
        raise DeviceRoleError("device_roles_required", "Choose at least one device role.")
    if len(roles) > max(1, int(max_roles)):
        raise DeviceRoleError("device_role_invalid", "Too many device roles were requested.")
    if joinable_only and any(role not in JOINABLE_DEVICE_ROLES for role in roles):
        raise DeviceRoleError("device_role_not_joinable", "Only Compute and Storage can be assigned to joined devices.")
    return roles


def role_metadata(role: Any) -> dict[str, Any]:
    normalized = normalize_device_role(role)
    return {
        "role": normalized,
        "role_label": ROLE_LABELS[normalized],
        "label": ROLE_LABELS[normalized],
        "description": ROLE_DESCRIPTIONS[normalized],
        "joinable": normalized in JOINABLE_DEVICE_ROLES,
        "protected": normalized in PROTECTED_DEVICE_ROLES,
    }


def joinable_role_options() -> list[dict[str, Any]]:
    return [role_metadata(role) for role in ROLE_ORDER]


def legacy_role_projection(roles: Any, *, server_host: bool = False) -> str:
    if server_host:
        return "server_host"
    normalized = normalize_device_roles(roles, joinable_only=True)
    return "compute" if "compute" in normalized else normalized[0]


def authorized_capabilities_for_roles(roles: Any, *, server_host: bool = False) -> list[str]:
    normalized = ["server_host"] if server_host else normalize_device_roles(roles, joinable_only=True)
    capabilities: set[str] = set()
    for role in normalized:
        capabilities.update(AUTHORIZED_CAPABILITIES_BY_ROLE.get(role, ()))
    return sorted(capabilities)


def roles_fingerprint(roles: Any) -> str:
    normalized = normalize_device_roles(roles, joinable_only=True)
    return hashlib.sha256(",".join(normalized).encode("utf-8")).hexdigest()[:24]


def request_fingerprint(
    *,
    action_id: str,
    device_id: str,
    requested_roles: Any,
    authorization_version: int,
    generation: int = 0,
) -> str:
    roles = normalize_device_roles(requested_roles, joinable_only=True)
    material = json.dumps(
        {
            "action_id": _safe_text(action_id, 120),
            "device_id": _safe_node_id(device_id),
            "device_roles": roles,
            "authorization_version": max(1, int(authorization_version or 1)),
            "generation": max(0, int(generation or 0)),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]


def _rows_for_device(conn: Any, device_id: str) -> list[Any]:
    return conn.execute(
        "SELECT * FROM device_role_assignments WHERE device_id=? ORDER BY role",
        (_safe_node_id(device_id),),
    ).fetchall()


def assignment_state(device_id: str, *, legacy_role: Any = None, protected_server_host: bool = False) -> dict[str, Any]:
    apply_migrations()
    safe_id = _safe_node_id(device_id)
    with connection() as conn:
        rows = _rows_for_device(conn, safe_id)
        latest = conn.execute(
            "SELECT * FROM device_role_change_operations WHERE device_id=? ORDER BY generation DESC LIMIT 1",
            (safe_id,),
        ).fetchone()
    if not rows:
        if protected_server_host:
            return {
                "device_roles": ["server_host"], "desired_device_roles": ["server_host"],
                "active_device_roles": ["server_host"], "generation": 0,
                "status": "active", "source": "protected_server_host",
            }
        if legacy_role not in (None, ""):
            try:
                roles = normalize_device_roles([legacy_role], joinable_only=True)
            except DeviceRoleError:
                roles = []
            if roles:
                return {
                    "device_roles": roles, "desired_device_roles": roles,
                    "active_device_roles": roles, "generation": 0,
                    "status": "legacy_compatibility", "source": "legacy_single_role",
                }
        return {
            "device_roles": [], "desired_device_roles": [], "active_device_roles": [],
            "generation": 0, "status": "unassigned", "source": "device_role_assignments",
        }
    desired = [str(row["role"]) for row in rows if int(row["desired"] or 0)]
    active = [str(row["role"]) for row in rows if int(row["active"] or 0)]
    desired.sort(key=lambda role: ROLE_ORDER.index(role) if role in ROLE_ORDER else 99)
    active.sort(key=lambda role: ROLE_ORDER.index(role) if role in ROLE_ORDER else 99)
    return {
        "device_roles": desired,
        "desired_device_roles": desired,
        "active_device_roles": active,
        "generation": max([int(row["generation"] or 0) for row in rows] or [0]),
        "status": str(latest["status"]) if latest else ("active" if desired == active else "verifying"),
        "reason_code": str(latest["reason_code"] or "") if latest else "",
        "change_id": str(latest["change_id"] or "") if latest else "",
        "source": "device_role_assignments",
        "assignments": [
            {
                "role": str(row["role"]),
                "desired": bool(row["desired"]),
                "active": bool(row["active"]),
                "assignment_status": str(row["assignment_status"] or ""),
                "verification_status": str(row["verification_status"] or ""),
                "verification_reason": str(row["verification_reason"] or ""),
                "generation": int(row["generation"] or 0),
            }
            for row in rows
        ],
    }


def record_desired_roles(
    device_id: str,
    roles: Any,
    *,
    status: str,
    action_id: str = "device.roles.change",
    actor_human_id: str = "",
    actor_role: str = "",
    authorization_version: int = 1,
    policy_revision: str = "",
    correlation_id: str = "",
    expected_generation: int | None = None,
    reason_code: str = "",
) -> dict[str, Any]:
    apply_migrations()
    safe_id = _safe_node_id(device_id)
    if not safe_id:
        raise DeviceRoleError("device_role_change_failed", "Device identity is unavailable.", 404)
    requested = normalize_device_roles(roles, joinable_only=True)
    now = _now()
    change_id = "drc-" + uuid.uuid4().hex

    with connection() as conn:
        with begin_immediate(conn) as tx:
            current_rows = _rows_for_device(tx, safe_id)
            current_generation = max([int(row["generation"] or 0) for row in current_rows] or [0])
            if expected_generation is not None and int(expected_generation) != current_generation:
                raise DeviceRoleError(
                    "device_role_change_failed",
                    "Device role state changed. Refresh and review the roles again.",
                    409,
                    detail={"current_generation": current_generation},
                )
            previous = [str(row["role"]) for row in current_rows if int(row["desired"] or 0)]
            if not previous:
                registry = tx.execute(
                    "SELECT role FROM device_enrollment_registry WHERE device_id=? AND removal_status='active'",
                    (safe_id,),
                ).fetchone()
                if registry and str(registry["role"] or ""):
                    try:
                        previous = normalize_device_roles([registry["role"]], joinable_only=True)
                    except DeviceRoleError:
                        previous = []
            generation = current_generation + 1
            fingerprint = request_fingerprint(
                action_id=action_id,
                device_id=safe_id,
                requested_roles=requested,
                authorization_version=authorization_version,
                generation=generation,
            )
            for role in ROLE_ORDER:
                desired = int(role in requested)
                prior = next((row for row in current_rows if str(row["role"]) == role), None)
                active = int(prior["active"] or 0) if prior else 0
                tx.execute(
                    """INSERT INTO device_role_assignments(
                           device_id,role,desired,active,assignment_status,generation,
                           assigned_at,assigned_by_human_id,authorization_version,policy_revision,
                           correlation_id,verification_status,verification_reason,verified_at,updated_at
                       ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                       ON CONFLICT(device_id,role) DO UPDATE SET
                           desired=excluded.desired,assignment_status=excluded.assignment_status,
                           generation=excluded.generation,assigned_at=excluded.assigned_at,
                           assigned_by_human_id=excluded.assigned_by_human_id,
                           authorization_version=excluded.authorization_version,
                           policy_revision=excluded.policy_revision,correlation_id=excluded.correlation_id,
                           verification_status=excluded.verification_status,
                           verification_reason=excluded.verification_reason,updated_at=excluded.updated_at""",
                    (
                        safe_id, role, desired, active, status[:32], generation, now,
                        _safe_text(actor_human_id, 120), max(1, int(authorization_version or 1)),
                        _safe_text(policy_revision, 80), _safe_text(correlation_id, 80),
                        "pending", "device_role_change_pending_verification", None, now,
                    ),
                )
            tx.execute(
                """INSERT INTO device_role_change_operations(
                       change_id,device_id,generation,requested_roles_json,previous_roles_json,
                       status,reason_code,summary,requested_by_human_id,requested_by_role,
                       authorization_version,policy_revision,correlation_id,request_fingerprint,
                       created_at,updated_at
                   ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    change_id, safe_id, generation, json.dumps(requested, separators=(",", ":")),
                    json.dumps(previous, separators=(",", ":")), status[:32],
                    _safe_text(reason_code, 80),
                    "Device role assignment recorded; runtime verification is pending.",
                    _safe_text(actor_human_id, 120), _safe_text(actor_role, 24),
                    max(1, int(authorization_version or 1)), _safe_text(policy_revision, 80),
                    _safe_text(correlation_id, 80), fingerprint, now, now,
                ),
            )
    return {
        "change_id": change_id, "device_id": safe_id, "generation": generation,
        "requested_device_roles": requested, "previous_device_roles": previous,
        "status": status[:32], "action_id": action_id[:120], "request_fingerprint": fingerprint,
        "reason_code": reason_code, "sanitized": True,
    }


def ensure_legacy_assignment(device_id: str, legacy_role: Any) -> dict[str, Any]:
    state = assignment_state(device_id, legacy_role=legacy_role)
    if state["source"] != "legacy_single_role":
        return state
    result = record_desired_roles(
        device_id, state["desired_device_roles"], status="legacy_compatibility",
        actor_human_id="system:migration", actor_role="system",
        authorization_version=1, correlation_id="legacy-role-compatibility",
        reason_code="legacy_single_role_compatibility",
    )
    record_runtime_attestation(
        device_id,
        reported_roles=state["desired_device_roles"],
        advertised_capabilities=[],
        online=False,
        identity_verified=True,
        generation=result["generation"],
        compatibility_observation=True,
    )
    return assignment_state(device_id, legacy_role=legacy_role)


def record_runtime_attestation(
    device_id: str,
    *,
    reported_roles: Any,
    advertised_capabilities: Any,
    online: bool,
    identity_verified: bool,
    generation: int | None = None,
    compatibility_observation: bool = False,
) -> dict[str, Any]:
    apply_migrations()
    safe_id = _safe_node_id(device_id)
    state = assignment_state(safe_id)
    desired = list(state.get("desired_device_roles") or [])
    if not desired:
        return state
    try:
        reported = normalize_device_roles(reported_roles, joinable_only=True)
    except DeviceRoleError:
        reported = []
    advertised = {str(item).strip() for item in (advertised_capabilities if isinstance(advertised_capabilities, list) else []) if str(item).strip()}
    current_generation = int(state.get("generation") or 0)
    if generation is not None and int(generation) not in {0, current_generation}:
        return {**state, "status": "blocked", "reason_code": "device_role_change_identity_mismatch"}
    identity_ok = bool(identity_verified)
    exact_match = set(reported) == set(desired)
    now = _now()
    with connection() as conn:
        with begin_immediate(conn) as tx:
            for role in ROLE_ORDER:
                wanted = role in desired
                attested = role in reported
                required = AUTHORIZED_CAPABILITIES_BY_ROLE[role]
                observed = any(
                    bool(advertised.intersection(OBSERVATION_ALIASES.get(cap, frozenset({cap}))))
                    for cap in required
                ) if required else True
                verified = bool(identity_ok and online and attested and (observed or compatibility_observation))
                if not wanted:
                    active = 0
                    if attested:
                        assignment_status = "blocked"
                        verification_status = "failed"
                        verification_reason = "device_role_assignment_unauthorized"
                    else:
                        assignment_status = "removed"
                        verification_status = "verified"
                        verification_reason = ""
                elif not identity_ok:
                    active = 0
                    assignment_status = "blocked"
                    verification_status = "failed"
                    verification_reason = "device_role_change_identity_mismatch"
                elif not attested:
                    active = 0
                    assignment_status = "verifying"
                    verification_status = "pending"
                    verification_reason = "device_role_change_pending_verification"
                elif not online:
                    active = 0
                    assignment_status = "verifying"
                    verification_status = "stale"
                    verification_reason = "device_capability_stale"
                elif not observed and not compatibility_observation:
                    active = 0
                    assignment_status = "verifying"
                    verification_status = "failed"
                    verification_reason = "device_capability_verification_failed"
                else:
                    active = int(verified)
                    assignment_status = "active" if verified else "verifying"
                    verification_status = "verified" if verified else "pending"
                    verification_reason = "" if verified else "device_role_change_pending_verification"
                tx.execute(
                    """UPDATE device_role_assignments
                       SET active=?,assignment_status=?,verification_status=?,
                           verification_reason=?,verified_at=?,updated_at=?
                       WHERE device_id=? AND role=?""",
                    (
                        active, assignment_status, verification_status, verification_reason,
                        now if verification_status == "verified" else None, now, safe_id, role,
                    ),
                )
            unauthorized_report = bool(set(reported) - set(desired))
            final_status = (
                "active" if identity_ok and online and exact_match
                and all(
                    row["verification_status"] == "verified"
                    for row in tx.execute(
                        "SELECT verification_status FROM device_role_assignments WHERE device_id=? AND desired=1",
                        (safe_id,),
                    ).fetchall()
                )
                else "blocked" if (not identity_ok or unauthorized_report)
                else "verifying"
            )
            reason = "" if final_status == "active" else (
                "device_role_change_identity_mismatch" if not identity_ok
                else "device_role_assignment_unauthorized" if unauthorized_report
                else "device_role_change_pending_verification"
            )
            tx.execute(
                """UPDATE device_role_change_operations SET status=?,reason_code=?,summary=?,updated_at=?
                   WHERE device_id=? AND generation=?""",
                (
                    final_status, reason,
                    "Device roles are active and verified." if final_status == "active"
                    else "Pocket Lab is waiting for the device to verify its assigned roles.",
                    now, safe_id, current_generation,
                ),
            )
    return assignment_state(safe_id)


def retire_device_roles(device_id: str, *, reason_code: str = "device_removed") -> dict[str, Any]:
    """Deactivate governed role authority without deleting historical assignment rows."""
    apply_migrations()
    safe_id = _safe_node_id(device_id)
    now = _now()
    with connection() as conn:
        with begin_immediate(conn) as tx:
            rows = _rows_for_device(tx, safe_id)
            generation = max([int(row["generation"] or 0) for row in rows] or [0])
            tx.execute(
                """UPDATE device_role_assignments
                   SET desired=0,active=0,assignment_status='retired',
                       verification_status='retired',verification_reason=?,updated_at=?
                   WHERE device_id=?""",
                (_safe_text(reason_code, 80), now, safe_id),
            )
            tx.execute(
                """UPDATE device_role_change_operations
                   SET status='retired',reason_code=?,summary=?,updated_at=?
                   WHERE device_id=? AND status NOT IN ('failed','cancelled','retired')""",
                (
                    _safe_text(reason_code, 80),
                    "Device role authority retired with the enrolled device; historical records were preserved.",
                    now,
                    safe_id,
                ),
            )
    return {
        "device_id": safe_id,
        "generation": generation,
        "status": "retired",
        "reason_code": reason_code,
        "sanitized": True,
    }


def mark_change_status(device_id: str, generation: int, status: str, reason_code: str, summary: str) -> None:
    apply_migrations()
    with connection() as conn:
        conn.execute(
            """UPDATE device_role_change_operations SET status=?,reason_code=?,summary=?,updated_at=?
               WHERE device_id=? AND generation=?""",
            (status[:32], _safe_text(reason_code, 80), _safe_text(summary, 240), _now(), _safe_node_id(device_id), int(generation)),
        )
        conn.commit()


def role_change_dependency_assessment(device: dict[str, Any], current_roles: Any, requested_roles: Any) -> dict[str, Any]:
    current = normalize_device_roles(current_roles, joinable_only=True)
    requested = normalize_device_roles(requested_roles, joinable_only=True)
    removing_storage = "storage" in current and "storage" not in requested
    if not removing_storage:
        return {"safe": True, "blockers": [], "storage_role_removed": False}
    blockers: list[dict[str, str]] = []
    assessment = device.get("removal_assessment") if isinstance(device.get("removal_assessment"), dict) else {}
    for item in assessment.get("blockers") or []:
        if not isinstance(item, dict):
            continue
        text = json.dumps(item, sort_keys=True).lower()
        if any(term in text for term in ("backup", "restore", "storage", "recovery", "media")):
            blockers.append({
                "reason_code": "device_role_change_blocked_by_dependency",
                "summary": _safe_text(item.get("summary") or item.get("message") or "Storage responsibility is still in use.", 220),
            })
    dependencies = device.get("dependencies") if isinstance(device.get("dependencies"), dict) else {}
    for key in ("backup_set_count", "active_backup_count", "restore_target_count", "storage_mapping_count"):
        try:
            count = int(dependencies.get(key) or 0)
        except (TypeError, ValueError):
            count = 0
        if count > 0:
            blockers.append({
                "reason_code": "device_role_change_blocked_by_dependency",
                "summary": f"Storage role is still used by {count} saved {key.replace('_count', '').replace('_', ' ')} item(s).",
            })
    return {"safe": not blockers, "blockers": blockers[:8], "storage_role_removed": True}


def capability_projection(device: dict[str, Any], roles: Any) -> list[dict[str, Any]]:
    server_host = bool(device.get("protected_server_host") or str(device.get("role") or "") == "server_host")
    role_ids = ["server_host"] if server_host else normalize_device_roles(roles, joinable_only=True)
    authorized = set(authorized_capabilities_for_roles(role_ids if not server_host else ["compute"], server_host=server_host))
    authorized.update(BASELINE_AGENT_CAPABILITIES)
    advertised = {
        str(item.get("id") or "").strip() if isinstance(item, dict) else str(item).strip()
        for item in (device.get("advertised_capabilities") or device.get("capabilities") or [])
    }
    advertised.discard("")
    online = str(device.get("connection") or device.get("status") or "").lower() in {"online", "active", "healthy", "ready"}
    universe = sorted(authorized.union(advertised))
    rows: list[dict[str, Any]] = []
    for capability in universe:
        independent = capability in PHOTO_SOURCE_CAPABILITIES
        allowed = capability in authorized or independent
        aliases = OBSERVATION_ALIASES.get(capability, frozenset({capability}))
        observed = bool(advertised.intersection(aliases))
        if not allowed:
            status = "blocked_by_role"
            reason = "device_capability_not_authorized"
        elif not online:
            status = "stale"
            reason = "device_capability_stale"
        elif not observed:
            status = "not_advertised"
            reason = "device_capability_not_advertised"
        else:
            status = "ready"
            reason = ""
        rows.append({
            "id": capability,
            "authorization": "independent_runtime_policy" if independent else ("allowed" if allowed else "blocked"),
            "observation": "advertised" if observed else "not_advertised",
            "verification": "verified" if status == "ready" else ("stale" if status == "stale" else "unverified"),
            "status": status,
            "reason_code": reason,
            "effective": status == "ready",
        })
    return rows


def enrich_device_projection(device: dict[str, Any]) -> dict[str, Any]:
    result = dict(device)
    server_host = bool(result.get("protected_server_host") or result.get("is_current") or str(result.get("role") or "") == "server_host")
    state = assignment_state(
        str(result.get("id") or result.get("node_id") or ""),
        legacy_role=result.get("role"),
        protected_server_host=server_host,
    )
    role_ids = list(state.get("desired_device_roles") or (["server_host"] if server_host else []))
    result["device_roles"] = [
        {
            "id": role,
            "label": ROLE_LABELS.get(role, role.replace("_", " ").title()),
            "assignment_status": next(
                (item.get("assignment_status") for item in state.get("assignments", []) if item.get("role") == role),
                "active" if role in state.get("active_device_roles", []) else state.get("status", "pending"),
            ),
        }
        for role in role_ids
    ]
    result["device_role_ids"] = role_ids
    result["desired_device_roles"] = list(state.get("desired_device_roles") or [])
    result["active_device_roles"] = list(state.get("active_device_roles") or [])
    result["device_role_generation"] = int(state.get("generation") or 0)
    result["device_role_status"] = state.get("status") or "unknown"
    result["device_role_reason_code"] = state.get("reason_code") or ""
    if not server_host and role_ids:
        result["role"] = legacy_role_projection(role_ids)
        result["role_label"] = " + ".join(ROLE_LABELS.get(role, role.title()) for role in role_ids)
        result["role_compatibility_lossy"] = len(role_ids) > 1
    result["capability_states"] = capability_projection(result, role_ids or (["compute"] if not server_host else ["server_host"]))
    result["capabilities"] = [item["id"] for item in result["capability_states"] if item["effective"]]
    return result
