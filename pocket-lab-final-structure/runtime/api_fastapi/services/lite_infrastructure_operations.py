"""Source-owned infrastructure operation metadata, not an execution engine.

The existing P4 consumer adapter and fixed maintenance owner adapter have
System Health admission/owner contracts. Guided entries link to existing protected flows. Candidate entries
cannot be made executable through configuration or by a browser.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import os
import re
from typing import Literal

Risk = Literal["A", "B", "C"]
Availability = Literal["externally_managed", "guided_existing_flow", "not_enabled", "never_automatic"]

# This value is deliberately source-owned.  Bump it whenever the reviewed
# production allowlist or its execution contract changes.  A durable Owner
# confirmation and the runtime activation revision must both match it before a
# production preference can become effective.
PRODUCTION_QUALIFICATION_REVISION = "system-health-a1-2026-11-26"
PRODUCTION_ASSISTED_REVISION_ENV = "POCKETLAB_SYSTEM_HEALTH_PRODUCTION_ASSISTED_REVISION"
PRODUCTION_AUTOMATIC_REVISION_ENV = "POCKETLAB_SYSTEM_HEALTH_PRODUCTION_AUTOMATIC_REVISION"


@dataclass(frozen=True)
class Operation:
    operation_id: str
    title: str
    execution_owner: str
    risk_class: Risk
    availability: Availability
    destination: str | None = None
    qualification: str = "qualification_required"
    target_scope: str = "owner_validated_target"
    verification: str = "fresh_independent_owner_evidence_required"
    expected_impact: str = "Review impact in the authoritative owner workflow."
    cancellation: str = "not_available_without_owner_contract"

    def public(self) -> dict:
        result = asdict(self)
        controlled = self.operation_id == "runtime.consumer.reconnect"
        maintenance = self.operation_id in MAINTENANCE_OPERATIONS
        source_qualified = self.operation_id in PRODUCTION_QUALIFIED_OPERATIONS
        automatic_qualified = self.operation_id in PRODUCTION_QUALIFIED_AUTOMATIC_OPERATIONS
        requestable = controlled_recovery_enabled() if controlled else maintenance_enabled(self.operation_id) if maintenance else False
        automatic_enabled = automatic_gate_open() if automatic_qualified else False
        assisted_reasons = _assisted_reason_codes(self.operation_id, controlled=controlled, maintenance=maintenance)
        automatic_reasons = _automatic_reason_codes(self.operation_id, qualified=automatic_qualified)
        owner_preferred = (
            _automatic_preference_enabled() if automatic_qualified
            else _owner_preferred() if controlled or maintenance
            else None
        )
        implementation_status = (
            "implemented_assisted_adapter" if controlled or maintenance
            else "existing_owner_managed" if self.availability == "externally_managed"
            else "existing_guided_workflow" if self.availability == "guided_existing_flow"
            else "protected_manual_only" if self.availability == "never_automatic"
            else "unsupported_candidate"
        )
        reason_codes = list(dict.fromkeys(assisted_reasons + automatic_reasons))
        if requestable:
            effective_availability = "assisted"
        elif automatic_enabled:
            effective_availability = "automatic"
        elif source_qualified or automatic_qualified:
            effective_availability = "source_qualified_monitor_only"
        elif self.availability == "never_automatic":
            effective_availability = "manual_only"
        elif self.availability == "guided_existing_flow":
            effective_availability = "guided_existing_flow"
        elif self.availability == "externally_managed":
            effective_availability = "existing_owner_managed"
        else:
            effective_availability = "monitor_only"
        result.update({
            "supported_platforms": ["android_termux", "linux_arm64", "linux_dev"],
            "supported_modes": (["monitor", "assisted"] if controlled or maintenance else ["monitor"])
                + (["automatic"] if automatic_qualified else []),
            "production_modes": (["monitor", "assisted"] if source_qualified else ["monitor"])
                + (["automatic"] if automatic_qualified else []),
            "implementation_status": implementation_status,
            "implemented": controlled or maintenance,
            "source_qualified": source_qualified,
            "automatic_source_qualified": automatic_qualified,
            "runtime_enabled": bool(requestable or automatic_enabled),
            "owner_preferred": owner_preferred,
            "automatic_admission_enabled": automatic_enabled,
            "system_health_requestable": requestable,
            "effective_availability": effective_availability,
            "assisted_reason_codes": assisted_reasons,
            "automatic_reason_codes": automatic_reasons,
            "reason_codes": reason_codes,
            # These are intentionally null at catalog scope.  Authorization,
            # target eligibility, execution and verification are request- and
            # evidence-scoped; a catalog row must not imply any of them.
            "currently_authorized": None,
            "currently_eligible": None,
            "executing": None,
            "verified": None,
            "evidence_scope": "request_and_target_scoped",
            "request_channel": "incident_recovery" if controlled else "maintenance" if maintenance else None,
            "required_permission": "system_health.recovery" if controlled else "system_health.maintenance" if maintenance else "existing_owner_policy",
            "approval": "existing_opa_and_approval" if controlled else "existing_owner_approval",
            "incident_generation_required": controlled,
            "enrollment_generation_required": controlled,
            "preconditions": ["fresh_evidence", "authorized_actor", "owner_eligibility"],
            "maintenance_conflict_policy": "deny_new_unqualified_work",
            "resource_admission": "existing_owner_required",
            "single_flight_scope": "worker_consumer" if controlled else "existing_owner",
            "idempotency": "actor_and_incident_bound" if controlled else "existing_owner",
            "max_attempts": 2 if controlled else None,
            "deadline_seconds": 90 if controlled else None,
            "cooldown": "existing_bounded_worker_retry" if controlled else "existing_owner",
            "audit_required": True,
            "sanitized": True,
            "summary": self.expected_impact,
        })
        return result


OPERATIONS = (
    Operation("runtime.consumer.reconnect", "Restore command connection", "nats_worker_watchdog", "A", "externally_managed", qualification="p4_isolated_qualification_only", target_scope="local_worker_consumer", verification="fresh_consumer_generation_and_health", expected_impact="May briefly interrupt command delivery; active callbacks are protected."),
    Operation("runtime.nats.recover", "Recover command bus", "core_supervisor", "B", "externally_managed"),
    Operation("runtime.gateway.recover", "Recover web gateway", "core_supervisor", "B", "externally_managed"),
    Operation("runtime.worker.recover", "Recover background worker", "core_supervisor", "B", "externally_managed"),
    Operation("runtime.telemetry.recover", "Restore monitoring", "core_supervisor", "B", "externally_managed"),
    Operation("runtime.server_agent.recover", "Recover server agent", "core_supervisor", "B", "externally_managed", "devices"),
    Operation("runtime.api.recover", "Review control service recovery", "runtime_guardian", "B", "externally_managed"),
    Operation("runtime.gateway.validate", "Review web gateway configuration", "runtime_reconciler", "A", "not_enabled"),
    Operation("runtime.policy.recover", "Review policy service recovery", "existing_policy_supervisor", "B", "guided_existing_flow", "rules"),
    Operation("network.remote_access.restore", "Review remote access", "existing_remote_access_owner", "B", "guided_existing_flow", "devices"),
    Operation("device.agent.recover", "Recover device agent", "node_supervisor", "A", "externally_managed", "devices"),
    Operation("app.repair", "Repair app", "existing_app_action", "B", "guided_existing_flow", "catalog"),
    Operation("storage.logs.preview", "Review expired managed log archives", "security_maintenance", "A", "not_enabled"),
    Operation("storage.logs.cleanup", "Clean expired managed logs", "existing_retention_owner", "B", "not_enabled"),
    Operation("storage.temp.preview", "Review abandoned database rehearsal files", "security_maintenance", "A", "not_enabled"),
    Operation("storage.temp.cleanup", "Free abandoned temporary files", "existing_maintenance_owner", "B", "not_enabled"),
    Operation("storage.cache.cleanup", "Review application cache", "existing_app_action", "B", "guided_existing_flow", "catalog"),
    Operation("storage.evidence.preview", "Preview old evidence records", "security_maintenance", "A", "not_enabled"),
    Operation("storage.evidence.retention", "Review old diagnostic evidence", "security_maintenance", "B", "not_enabled"),
    Operation("sqlite.checkpoint.passive", "Review database storage optimization", "security_maintenance", "A", "not_enabled"),
    Operation("sqlite.health.review", "Review database health", "existing_recovery_owner", "A", "guided_existing_flow", "recovery"),
    Operation("projection.reconcile", "Refresh stale projections", "projection_scheduler", "A", "not_enabled"),
    Operation("maintenance.window", "Review maintenance", "security_maintenance", "B", "not_enabled"),
    Operation("workflow.retry", "Review interrupted operation", "existing_command_owner", "B", "not_enabled"),
    Operation("workflow.cancel", "Review safe cancellation", "existing_command_owner", "B", "not_enabled"),
    Operation("resource.defer", "Review workload deferral", "projection_scheduler", "A", "not_enabled"),
    Operation("resource.resume", "Review workload resumption", "projection_scheduler", "A", "not_enabled"),
    Operation("runtime.configuration.restore", "Restore service configuration", "runtime_reconciler", "B", "not_enabled"),
    Operation("policy.known_good.reconcile", "Review approved policy reconciliation", "policy_lifecycle", "B", "guided_existing_flow", "rules"),
    Operation("security.scanner.review", "Review scanner readiness", "existing_security_owner", "A", "guided_existing_flow", "security"),
    Operation("recovery.backup.create", "Create recovery backup", "existing_recovery_owner", "B", "guided_existing_flow", "recovery"),
    Operation("recovery.backup.verify", "Verify existing backup", "existing_recovery_owner", "A", "guided_existing_flow", "recovery"),
    Operation("recovery.database.rehearse", "Rehearse database restore on isolated copy", "existing_recovery_owner", "B", "not_enabled"),
    Operation("recovery.database.restore", "Restore Pocket Lab data", "recovery", "C", "never_automatic", "recovery"),
    Operation("diagnostics.support.export", "Review diagnostic export", "existing_evidence_owner", "B", "not_enabled"),
)


# Promotion is a reviewed source change after exact-candidate qualification.
# No environment flag or preference can qualify an operation.
PRODUCTION_QUALIFIED_OPERATIONS: frozenset[str] = frozenset({
    "runtime.consumer.reconnect",
    "storage.logs.preview",
    "storage.temp.preview",
    "storage.evidence.preview",
    "sqlite.checkpoint.passive",
    "projection.reconcile",
})
PRODUCTION_QUALIFIED_AUTOMATIC_OPERATIONS: frozenset[str] = frozenset({
    "projection.reconcile",
})


MAINTENANCE_OPERATIONS = frozenset({"storage.evidence.preview", "storage.evidence.retention", "sqlite.checkpoint.passive", "recovery.database.rehearse", "projection.reconcile", "storage.logs.preview", "storage.logs.cleanup", "storage.temp.preview", "storage.temp.cleanup", "runtime.telemetry.recover", "runtime.server_agent.recover", "runtime.configuration.restore"})


def _qualification_environment() -> bool:
    return os.environ.get("POCKETLAB_ENVIRONMENT", "").strip().casefold() == "qualification"


def _safe_revision(value: object) -> str:
    return re.sub(r"[^A-Za-z0-9_.:+-]+", "-", str(value or "").strip())[:80]


def _runtime_revision(mode: str) -> str:
    name = PRODUCTION_ASSISTED_REVISION_ENV if mode == "assisted" else PRODUCTION_AUTOMATIC_REVISION_ENV
    return _safe_revision(os.environ.get(name, ""))


def _activation_fence_row() -> dict:
    try:
        from . import lite_system_health as health
        rows = health._read("SELECT * FROM lite_system_health_activation_fence WHERE singleton_id=1")
    except Exception:
        rows = []
    return rows[0] if rows else {}


def activation_fence_status(mode: str) -> dict:
    """Return sanitized current/confirmed activation-fence state.

    Production flags are intentionally insufficient by themselves.  The
    Owner action that saves the current preference/policy records the current
    source qualification revision and a separately supplied runtime rollout
    revision.  Rotating the runtime revision therefore requires a fresh Owner
    confirmation, even when an older preference remains in SQLite.
    """
    if mode not in {"assisted", "automatic"}:
        raise ValueError("unknown_activation_mode")
    if _qualification_environment():
        return {
            "mode": mode,
            "required": False,
            "valid": True,
            "source_revision": PRODUCTION_QUALIFICATION_REVISION,
            "runtime_revision": "qualification",
            "stored_source_revision": PRODUCTION_QUALIFICATION_REVISION,
            "stored_runtime_revision": "qualification",
            "reason_codes": [],
            "sanitized": True,
        }

    stored = _activation_fence_row()
    prefix = "assisted" if mode == "assisted" else "automatic"
    stored_source = _safe_revision(stored.get(f"{prefix}_source_revision"))
    stored_runtime = _safe_revision(stored.get(f"{prefix}_runtime_revision"))
    stored_reference = int(stored.get(f"{prefix}_{'preference' if mode == 'assisted' else 'policy'}_revision") or 0)
    runtime_revision = _runtime_revision(mode)
    reasons: list[str] = []
    if not runtime_revision:
        reasons.append("runtime_activation_revision_required")

    if mode == "assisted":
        try:
            from . import lite_system_health as health
            rows = health._read("SELECT revision,recovery_mode FROM lite_system_health_preferences WHERE singleton_id=1")
        except Exception:
            rows = []
        preference = rows[0] if rows else {}
        current_reference = int(preference.get("revision") or 0)
        if preference.get("recovery_mode") != "assisted":
            reasons.append("owner_preference_required")
    else:
        try:
            from . import lite_system_health as health
            rows = health._read("SELECT revision,enabled FROM lite_system_health_automation_policy WHERE singleton_id=1")
        except Exception:
            rows = []
        preference = rows[0] if rows else {}
        current_reference = int(preference.get("revision") or 0)
        if not preference or not bool(preference.get("enabled")):
            reasons.append("owner_preference_required")

    if not stored_source or not stored_runtime or stored_reference != current_reference:
        reasons.append("activation_confirmation_required")
    elif stored_source != PRODUCTION_QUALIFICATION_REVISION or stored_runtime != runtime_revision:
        reasons.append("activation_fence_stale")

    return {
        "mode": mode,
        "required": True,
        "valid": not reasons,
        "source_revision": PRODUCTION_QUALIFICATION_REVISION,
        "runtime_revision": runtime_revision,
        "stored_source_revision": stored_source,
        "stored_runtime_revision": stored_runtime,
        "stored_reference_revision": stored_reference,
        "reason_codes": list(dict.fromkeys(reasons)),
        "sanitized": True,
    }


def write_activation_fence(conn, mode: str, *, confirmed: bool, reference_revision: int, now: str) -> None:
    """Persist or clear one mode's Owner confirmation in the same transaction."""
    if mode not in {"assisted", "automatic"}:
        raise ValueError("unknown_activation_mode")
    prefix = "assisted" if mode == "assisted" else "automatic"
    if confirmed:
        values = (
            PRODUCTION_QUALIFICATION_REVISION,
            _runtime_revision(mode),
            int(reference_revision),
        )
    else:
        values = ("", "", 0)
    conn.execute(
        f"""UPDATE lite_system_health_activation_fence
            SET {prefix}_source_revision=?, {prefix}_runtime_revision=?,
                {prefix}_{'preference' if mode == 'assisted' else 'policy'}_revision=?, updated_at=?
            WHERE singleton_id=1""",
        (*values, now),
    )


def _owner_preferred() -> bool:
    try:
        from . import lite_system_health as health
        rows = health._read("SELECT recovery_mode FROM lite_system_health_preferences WHERE singleton_id=1")
        return bool(rows and rows[0].get("recovery_mode") == "assisted")
    except Exception:
        return False


def _automatic_preference_enabled() -> bool:
    try:
        from . import lite_system_health as health
        rows = health._read("SELECT enabled FROM lite_system_health_automation_policy WHERE singleton_id=1")
        return bool(rows and rows[0].get("enabled"))
    except Exception:
        return False


def automatic_gate_open() -> bool:
    if os.environ.get("POCKETLAB_SYSTEM_HEALTH_RECOVERY_EMERGENCY_DISABLE", "0") != "0":
        return False
    if _qualification_environment():
        return os.environ.get("POCKETLAB_SYSTEM_HEALTH_AUTOMATIC_ADAPTER") == "1"
    return bool(
        "projection.reconcile" in PRODUCTION_QUALIFIED_AUTOMATIC_OPERATIONS
        and os.environ.get("POCKETLAB_SYSTEM_HEALTH_PRODUCTION_AUTOMATIC") == "1"
        and activation_fence_status("automatic")["valid"]
    )


def _assisted_reason_codes(operation: str, *, controlled: bool, maintenance: bool) -> list[str]:
    if not controlled and not maintenance:
        return ["existing_owner_workflow_required"] if operation not in PRODUCTION_QUALIFIED_OPERATIONS else []
    reasons: list[str] = []
    qualification = _qualification_environment()
    adapter_env = "POCKETLAB_SYSTEM_HEALTH_RECOVERY_ADAPTER" if controlled else "POCKETLAB_SYSTEM_HEALTH_MAINTENANCE_ADAPTER"
    if qualification:
        if os.environ.get(adapter_env) != "1":
            reasons.append("qualification_adapter_disabled")
        return reasons
    if operation not in PRODUCTION_QUALIFIED_OPERATIONS:
        reasons.append("source_qualification_required")
    if os.environ.get("POCKETLAB_SYSTEM_HEALTH_RECOVERY_EMERGENCY_DISABLE", "0") != "0":
        reasons.append("emergency_disabled")
    if os.environ.get("POCKETLAB_SYSTEM_HEALTH_PRODUCTION_ASSISTED") != "1":
        reasons.append("runtime_opt_in_required")
    if operation in PRODUCTION_QUALIFIED_OPERATIONS:
        reasons.extend(activation_fence_status("assisted")["reason_codes"])
        if not _owner_preferred():
            reasons.append("owner_preference_required")
    return list(dict.fromkeys(reasons))


def _automatic_reason_codes(operation: str, *, qualified: bool) -> list[str]:
    if not qualified:
        return ["automatic_source_qualification_required"] if operation in MAINTENANCE_OPERATIONS else ["automatic_not_supported"]
    reasons: list[str] = []
    if _qualification_environment():
        if os.environ.get("POCKETLAB_SYSTEM_HEALTH_AUTOMATIC_ADAPTER") != "1":
            reasons.append("qualification_adapter_disabled")
        return reasons
    if os.environ.get("POCKETLAB_SYSTEM_HEALTH_RECOVERY_EMERGENCY_DISABLE", "0") != "0":
        reasons.append("emergency_disabled")
    if os.environ.get("POCKETLAB_SYSTEM_HEALTH_PRODUCTION_AUTOMATIC") != "1":
        reasons.append("automatic_runtime_opt_in_required")
    reasons.extend(activation_fence_status("automatic")["reason_codes"])
    return list(dict.fromkeys(reasons))


def maintenance_enabled(operation: str) -> bool:
    if operation not in MAINTENANCE_OPERATIONS or os.environ.get("POCKETLAB_SYSTEM_HEALTH_RECOVERY_EMERGENCY_DISABLE", "0") != "0":
        return False
    if os.environ.get("POCKETLAB_ENVIRONMENT", "").strip().casefold() == "qualification":
        return os.environ.get("POCKETLAB_SYSTEM_HEALTH_MAINTENANCE_ADAPTER") == "1"
    if operation not in PRODUCTION_QUALIFIED_OPERATIONS or os.environ.get("POCKETLAB_SYSTEM_HEALTH_PRODUCTION_ASSISTED") != "1":
        return False
    from . import lite_infrastructure_authority as authority
    return authority.preferences()["recovery_mode"] == "assisted" and activation_fence_status("assisted")["valid"]


def controlled_recovery_enabled() -> bool:
    if os.environ.get("POCKETLAB_SYSTEM_HEALTH_RECOVERY_EMERGENCY_DISABLE", "0") != "0":
        return False
    if os.environ.get("POCKETLAB_ENVIRONMENT", "").strip().casefold() == "qualification":
        return os.environ.get("POCKETLAB_SYSTEM_HEALTH_RECOVERY_ADAPTER") == "1"
    if ("runtime.consumer.reconnect" not in PRODUCTION_QUALIFIED_OPERATIONS
            or os.environ.get("POCKETLAB_SYSTEM_HEALTH_PRODUCTION_ASSISTED") != "1"):
        return False
    from . import lite_infrastructure_authority as authority
    return authority.preferences()["recovery_mode"] == "assisted" and activation_fence_status("assisted")["valid"]


def activation_policy() -> dict:
    from . import lite_infrastructure_authority as authority
    qualified = "runtime.consumer.reconnect" in PRODUCTION_QUALIFIED_OPERATIONS
    qualification = os.environ.get("POCKETLAB_ENVIRONMENT", "").strip().casefold() == "qualification"
    enabled = controlled_recovery_enabled()
    automatic_gate = automatic_gate_open()
    automatic_preference = _automatic_preference_enabled()
    assisted_fence = activation_fence_status("assisted")
    automatic_fence = activation_fence_status("automatic")
    return {
        "environment": "qualification" if qualification else "production",
        "adapter_implemented": True,
        "qualification": "production_qualified" if qualified else "p4_isolated_only",
        "production_qualified": qualified,
        "production_assisted_enabled": bool(not qualification and enabled),
        "production_automatic_enabled": bool(not qualification and automatic_gate and automatic_preference),
        "production_automatic_gate_open": bool(not qualification and automatic_gate),
        "qualification_adapter_enabled": bool(qualification and enabled),
        "emergency_disable": os.environ.get("POCKETLAB_SYSTEM_HEALTH_RECOVERY_EMERGENCY_DISABLE", "0") != "0",
        "emergency_disable_scope": "new_controlled_adapter_admission_and_claim",
        "existing_guardians_affected": False,
        "available_modes": ["monitor", "assisted"] if PRODUCTION_QUALIFIED_OPERATIONS else ["monitor"],
        "qualified_operations": sorted(PRODUCTION_QUALIFIED_OPERATIONS),
        "qualified_automatic_operations": sorted(PRODUCTION_QUALIFIED_AUTOMATIC_OPERATIONS),
        "activation_confirmation": {
            "assisted": {key: assisted_fence[key] for key in ("valid", "required", "runtime_revision", "reason_codes", "sanitized")},
            "automatic": {key: automatic_fence[key] for key in ("valid", "required", "runtime_revision", "reason_codes", "sanitized")},
        },
        "default_off": True,
        "preferences": authority.preferences(),
        "reason": "Production activation requires source qualification, explicit runtime opt-in, a current Owner confirmation fence and current execution authority.",
    }


def operation_catalog() -> list[dict]:
    return [item.public() for item in OPERATIONS]
