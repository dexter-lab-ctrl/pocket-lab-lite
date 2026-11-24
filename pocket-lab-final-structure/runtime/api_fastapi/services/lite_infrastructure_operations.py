"""Source-owned infrastructure operation metadata, not an execution engine.

Only the existing P4 consumer adapter has a System Health admission/owner
contract. Guided entries link to existing protected flows. Candidate entries
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
        result.update({
            "supported_platforms": ["android_termux", "linux_arm64", "linux_dev"],
            "supported_modes": ["monitor", "assisted"] if controlled else ["monitor"],
            "production_modes": ["monitor"],
            "automatic_admission_enabled": False,
            "system_health_requestable": controlled and controlled_recovery_enabled(),
            "required_permission": "system_health.recovery" if controlled else "existing_owner_policy",
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
    Operation("runtime.worker.recover", "Recover background worker", "core_supervisor", "B", "externally_managed"),
    Operation("runtime.telemetry.recover", "Restore monitoring", "core_supervisor", "B", "externally_managed"),
    Operation("runtime.server_agent.recover", "Recover server agent", "core_supervisor", "B", "externally_managed", "devices"),
    Operation("runtime.api.recover", "Review control service recovery", "runtime_guardian", "B", "externally_managed"),
    Operation("runtime.gateway.validate", "Review web gateway configuration", "runtime_reconciler", "A", "not_enabled"),
    Operation("runtime.policy.recover", "Review policy service recovery", "existing_policy_supervisor", "B", "guided_existing_flow", "rules"),
    Operation("network.remote_access.restore", "Review remote access", "existing_remote_access_owner", "B", "guided_existing_flow", "devices"),
    Operation("device.agent.recover", "Recover device agent", "node_supervisor", "A", "externally_managed", "devices"),
    Operation("app.repair", "Repair app", "existing_app_action", "B", "guided_existing_flow", "apps"),
    Operation("storage.logs.cleanup", "Clean expired managed logs", "existing_retention_owner", "B", "not_enabled"),
    Operation("storage.temp.cleanup", "Free abandoned temporary files", "existing_maintenance_owner", "B", "not_enabled"),
    Operation("storage.cache.cleanup", "Review application cache", "existing_app_action", "B", "guided_existing_flow", "apps"),
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
    Operation("recovery.database.restore", "Restore Pocket Lab data", "recovery", "C", "never_automatic", "recovery"),
    Operation("diagnostics.support.export", "Review diagnostic export", "existing_evidence_owner", "B", "not_enabled"),
)


def controlled_recovery_enabled() -> bool:
    # Production qualification must be explicitly promoted in a later reviewed
    # source change; a runtime environment switch is not qualification evidence.
    # Emergency disable applies to the controlled adapter, not the autonomous
    # watchdog. Unknown values fail closed.
    return (
        os.environ.get("POCKETLAB_SYSTEM_HEALTH_RECOVERY_EMERGENCY_DISABLE", "0") == "0"
        and os.environ.get("POCKETLAB_ENVIRONMENT", "").strip().casefold() == "qualification"
        and os.environ.get("POCKETLAB_SYSTEM_HEALTH_RECOVERY_ADAPTER") == "1"
    )


def activation_policy() -> dict:
    disabled = os.environ.get("POCKETLAB_SYSTEM_HEALTH_RECOVERY_EMERGENCY_DISABLE", "0") != "0"
    return {
        "environment": "qualification" if os.environ.get("POCKETLAB_ENVIRONMENT", "").strip().casefold() == "qualification" else "production",
        "adapter_implemented": True,
        "qualification": "p4_isolated_only",
        "production_qualified": False,
        "production_assisted_enabled": False,
        "production_automatic_enabled": False,
        "qualification_adapter_enabled": controlled_recovery_enabled(),
        "emergency_disable": disabled,
        "emergency_disable_scope": "new_controlled_adapter_admission_and_claim",
        "existing_guardians_affected": False,
        "available_modes": ["monitor"],
        "reason": "Production qualification, activation authority and execution-time policy revalidation are required.",
    }


def operation_catalog() -> list[dict]:
    return [item.public() for item in OPERATIONS]
