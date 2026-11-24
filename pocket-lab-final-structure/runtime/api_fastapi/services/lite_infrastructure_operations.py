"""Source-owned infrastructure operation metadata, not an execution engine.

The existing P4 consumer adapter and fixed maintenance owner adapter have
System Health admission/owner contracts. Guided entries link to existing protected flows. Candidate entries
cannot be made executable through configuration or by a browser.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import os
from typing import Literal

Risk = Literal["A", "B", "C"]
Availability = Literal["externally_managed", "guided_existing_flow", "not_enabled", "never_automatic"]


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
        requestable = controlled_recovery_enabled() if controlled else maintenance_enabled(self.operation_id) if maintenance else False
        result.update({
            "supported_platforms": ["android_termux", "linux_arm64", "linux_dev"],
            "supported_modes": ["monitor", "assisted"] if controlled or maintenance else ["monitor"],
            "production_modes": ["monitor"],
            "automatic_admission_enabled": False,
            "system_health_requestable": requestable,
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
PRODUCTION_QUALIFIED_OPERATIONS: frozenset[str] = frozenset()
PRODUCTION_QUALIFIED_AUTOMATIC_OPERATIONS: frozenset[str] = frozenset()


MAINTENANCE_OPERATIONS = frozenset({"storage.evidence.preview", "storage.evidence.retention", "sqlite.checkpoint.passive", "recovery.database.rehearse", "projection.reconcile", "storage.logs.preview", "storage.logs.cleanup", "storage.temp.preview", "storage.temp.cleanup", "runtime.telemetry.recover", "runtime.server_agent.recover"})


def maintenance_enabled(operation: str) -> bool:
    if operation not in MAINTENANCE_OPERATIONS or os.environ.get("POCKETLAB_SYSTEM_HEALTH_RECOVERY_EMERGENCY_DISABLE", "0") != "0":
        return False
    if os.environ.get("POCKETLAB_ENVIRONMENT", "").strip().casefold() == "qualification":
        return os.environ.get("POCKETLAB_SYSTEM_HEALTH_MAINTENANCE_ADAPTER") == "1"
    if operation not in PRODUCTION_QUALIFIED_OPERATIONS or os.environ.get("POCKETLAB_SYSTEM_HEALTH_PRODUCTION_ASSISTED") != "1":
        return False
    from . import lite_infrastructure_authority as authority
    return authority.preferences()["recovery_mode"] == "assisted"


def controlled_recovery_enabled() -> bool:
    if os.environ.get("POCKETLAB_SYSTEM_HEALTH_RECOVERY_EMERGENCY_DISABLE", "0") != "0":
        return False
    if os.environ.get("POCKETLAB_ENVIRONMENT", "").strip().casefold() == "qualification":
        return os.environ.get("POCKETLAB_SYSTEM_HEALTH_RECOVERY_ADAPTER") == "1"
    if ("runtime.consumer.reconnect" not in PRODUCTION_QUALIFIED_OPERATIONS
            or os.environ.get("POCKETLAB_SYSTEM_HEALTH_PRODUCTION_ASSISTED") != "1"):
        return False
    from . import lite_infrastructure_authority as authority
    return authority.preferences()["recovery_mode"] == "assisted"


def activation_policy() -> dict:
    from . import lite_infrastructure_authority as authority
    qualified = "runtime.consumer.reconnect" in PRODUCTION_QUALIFIED_OPERATIONS
    qualification = os.environ.get("POCKETLAB_ENVIRONMENT", "").strip().casefold() == "qualification"
    enabled = controlled_recovery_enabled()
    return {
        "environment": "qualification" if qualification else "production",
        "adapter_implemented": True,
        "qualification": "production_qualified" if qualified else "p4_isolated_only",
        "production_qualified": qualified,
        "production_assisted_enabled": bool(not qualification and enabled),
        "production_automatic_enabled": False,
        "qualification_adapter_enabled": bool(qualification and enabled),
        "emergency_disable": os.environ.get("POCKETLAB_SYSTEM_HEALTH_RECOVERY_EMERGENCY_DISABLE", "0") != "0",
        "emergency_disable_scope": "new_controlled_adapter_admission_and_claim",
        "existing_guardians_affected": False,
        "available_modes": ["monitor", "assisted"] if qualified else ["monitor"],
        "preferences": authority.preferences(),
        "reason": "Production activation requires source qualification, explicit runtime opt-in, owner preference and current execution authority.",
    }


def operation_catalog() -> list[dict]:
    return [item.public() for item in OPERATIONS]
