"""Server-owned, purpose-specific review contracts. No credential or dispatcher.

Only existing internal owners may consume this evaluator. It must never be
exposed as an HTTP actor-construction interface. T3–T7 must implement actual
operation-specific OPA and runtime admission before execution.
"""
from dataclasses import dataclass
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from .lite_lifecycle_contract import Capability

@dataclass(frozen=True)
class ServiceContract:
    purpose: str
    owner: str
    capability_id: str | None
    category: str
    grantable: bool = False
    version: int = 1


SERVICES = (
    ServiceContract("release-reconciler", "release_runtime", "lifecycle.release.verify", "software", True),
    ServiceContract("policy-reconciler", "lite_policy_lifecycle", "lifecycle.policy.review", "safety_rules", True),
    ServiceContract("migration-executor", "existing_recovery_owner", None, "migrations"),
    ServiceContract("system-health-scheduler", "projection_scheduler", "system.activity_history.reconcile", "maintenance"),
    ServiceContract("app-update-reconciler", "existing_app_action", None, "applications"),
    ServiceContract("maintenance-executor", "existing_maintenance_owner", None, "maintenance"),
)
BY_PURPOSE = {item.purpose: item for item in SERVICES}


class DelegationReview(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    disposition: Literal["within", "restrictive", "outside", "revoked", "expired", "unknown", "blocked", "unsupported"]
    reason_code: str
    execution_eligible: Literal[False] = False


def scope_review(*, purpose: str, internal_owner: str, ceiling: Capability,
                 proposed: Capability, channel: str, category: str,
                 current_record: str, opa_allowed: bool | None, runtime_ready: bool | None) -> DelegationReview:
    """Review an exact proposed capability against all independent layers.

    The last two inputs are internal evidence, not HTTP parameters. Even a
    successful review is not executable authority in this phase.
    """
    service = BY_PURPOSE.get(purpose)
    def result(disposition, code):
        return DelegationReview(disposition=disposition, reason_code=code)
    if not service or not service.grantable:
        return result("unsupported", "service_contract_not_enabled")
    if service.owner != internal_owner or service.capability_id != proposed.id or service.category != category:
        return result("outside", "service_scope_mismatch")
    if proposed.mutation or proposed.secret_access or proposed.network or proposed.unattended or proposed.risk != "A":
        return result("blocked", "platform_non_delegable")
    if current_record in ("revoked", "expired"):
        return result(current_record, "standing_consent_" + current_record)
    if current_record != "within_recorded_boundary" or channel != "stable":
        return result("outside", "current_boundary_required")
    if ceiling.id != proposed.id or ceiling.version != proposed.version:
        return result("unknown", "capability_version_review_required")
    from .lite_lifecycle_contract import _expands
    if _expands(ceiling, proposed):
        return result("outside", "capability_scope_expanded")
    if opa_allowed is False or runtime_ready is False:
        return result("blocked", "current_policy_or_runtime_denied")
    if opa_allowed is not True or runtime_ready is not True:
        return result("unknown", "current_policy_and_runtime_evidence_required")
    return result("within" if ceiling == proposed else "restrictive", "review_only_no_execution")
