"""Non-executing, versioned lifecycle and capability contracts.

A capability describes authority, never a dispatch route. Unknown impact cannot
be promoted to a compatible change by a publisher or the browser.
"""
from __future__ import annotations

import hashlib
import json
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SCHEMA_VERSION = 1


class Impact(str, Enum):
    U0 = "U0"
    U1 = "U1"
    U2 = "U2"
    U3 = "U3"
    U4 = "U4"
    U5 = "U5"
    UX = "UX"


class Capability(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    id: str = Field(pattern=r"^[a-z][a-z0-9_.-]{2,79}$")
    version: int = Field(ge=1, le=1000000)
    domain: str = Field(pattern=r"^[a-z][a-z0-9_.-]{1,79}$")
    owner: str = Field(pattern=r"^[a-z][a-z0-9_.-]{1,79}$")
    action: str = Field(pattern=r"^[a-z][a-z0-9_.-]{1,79}$")
    targets: tuple[str, ...] = Field(min_length=1, max_length=32)
    data: tuple[str, ...] = Field(min_length=1, max_length=32)
    access: Literal["read", "write"]
    risk: Literal["A", "B", "C", "D"]
    mutation: bool
    network: bool
    secret_access: bool
    unattended: bool
    qualification_required: bool = True
    confirmation_required: bool = True
    constraints: tuple[str, ...] = Field(max_length=32)
    verification_required: bool = True
    revocable: bool = True
    optional: bool = False
    default_enabled: Literal[False] = False
    standing_authorization_supported: bool = False
    single_flight: bool = True
    cooldown_seconds: int = Field(default=0, ge=0, le=86400)
    audit_required: Literal[True] = True
    blind_replay_allowed: Literal[False] = False

    @field_validator("targets", "data", "constraints")
    @classmethod
    def canonical_scope(cls, value):
        import re
        if tuple(sorted(set(value))) != value or any(
            not re.fullmatch(r"[a-z][a-z0-9_.-]{0,79}", item) for item in value
        ):
            raise ValueError("invalid_capability_scope")
        return value


def canonical_bytes(value) -> bytes:
    # Repository-owned deterministic encoding, not a claim of RFC 8785/JCS.
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False).encode("ascii")


def digest(value) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _cap(id, domain, owner, action, target, data, *, read=True, network=False, standing=False):
    return Capability(id=id, version=1, domain=domain, owner=owner, action=action,
                      targets=(target,), data=(data,), access="read" if read else "write",
                      risk="A" if read else "B", mutation=not read, network=network,
                      secret_access=False, unattended=False,
                      constraints=("current_authority",), confirmation_required=not read,
                      standing_authorization_supported=standing)


# Actual existing execution-owner names are referenced, not reimplemented.
# Future policy/release delegation is descriptive and never eligible here.
def _recovery_reference():
    from .lite_infrastructure_operations import OPERATIONS
    op = next(x for x in OPERATIONS if x.operation_id == "projection.reconcile")
    return Capability(id="system.activity_history.reconcile", version=1, domain="system_health",
        owner=op.execution_owner, action="system_health.automatic", targets=("local_activity_history",),
        data=("activity_projection",), access="write", risk=op.risk_class, mutation=True, network=False,
        secret_access=False, unattended=True, constraints=("balanced_resource_mode", "current_authority", "healthy_sqlite", "maintenance_excluded", "normal_storage"),
        cooldown_seconds=1800, standing_authorization_supported=False)


CAPABILITIES = (
    _cap("lifecycle.release.inspect", "release", "release_runtime", "lifecycle.release.inspect", "release_metadata", "public_release_metadata", network=True),
    _cap("lifecycle.release.verify", "release", "release_runtime", "lifecycle.release.verify", "staged_release", "release_evidence", standing=True),
    _cap("lifecycle.preferences.manage", "lifecycle", "fastapi", "lifecycle.preferences.manage", "local_workspace", "update_preferences", read=False),
    _cap("lifecycle.authority.manage", "lifecycle", "fastapi", "lifecycle.authority.manage", "local_workspace", "authority_records", read=False),
    _cap("lifecycle.delegation.review", "lifecycle", "fastapi", "lifecycle.delegation.review", "local_workspace", "authority_records"),
    _recovery_reference(),
    _cap("lifecycle.policy.review", "rules", "lite_policy_lifecycle", "lifecycle.policy.review", "policy_metadata", "policy_evidence", standing=True),
)


def inventory(capabilities=CAPABILITIES):
    rows = sorted((item.model_dump(mode="json") for item in capabilities), key=lambda row: row["id"])
    if len({row["id"] for row in rows}) != len(rows):
        raise ValueError("duplicate_capability_id")
    return rows


def registry_revision() -> str:
    return digest({"schema_version": SCHEMA_VERSION, "capabilities": inventory()})


class ChangeAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    impact: Impact
    reasons: tuple[str, ...]
    added: tuple[str, ...] = ()
    removed: tuple[str, ...] = ()
    changed: tuple[str, ...] = ()
    execution_eligible: Literal[False] = False


def _expands(a: Capability, b: Capability) -> bool:
    return (not set(b.targets).issubset(a.targets) or not set(b.data).issubset(a.data)
            or a.owner != b.owner or a.action != b.action or a.domain != b.domain
            or (a.access == "read" and b.access == "write") or b.risk > a.risk
            or any(not getattr(a, f) and getattr(b, f) for f in
                   ("mutation", "network", "secret_access", "unattended", "standing_authorization_supported"))
            or any(getattr(a, f) and not getattr(b, f) for f in
                   ("confirmation_required", "qualification_required", "verification_required", "revocable", "single_flight"))
            or not set(a.constraints).issubset(b.constraints) or b.cooldown_seconds < a.cooldown_seconds)


def assess(old: tuple[Capability, ...], new: tuple[Capability, ...], *,
           policy_changed: bool, migration_changed: bool, root_changed: bool,
           approved_optional: tuple[Capability, ...] = (), presentation_only_proved: bool = False) -> ChangeAssessment:
    """Optional ceiling and presentation proof must originate locally."""
    inventory(old)
    inventory(new)
    inventory(approved_optional)
    before = {c.id: c for c in old}
    after = {c.id: c for c in new}
    ceiling = {c.id: c for c in approved_optional}
    added = tuple(sorted(after.keys() - before.keys()))
    removed = tuple(sorted(before.keys() - after.keys()))
    changed = tuple(sorted(k for k in before.keys() & after.keys() if before[k] != after[k]))
    details = dict(added=added, removed=removed, changed=changed)
    if root_changed or any(before[k].owner != after[k].owner for k in changed):
        return ChangeAssessment(impact=Impact.U5, reasons=("trust_or_execution_owner_changed",), **details)
    if any(not after[k].optional or k not in ceiling or ceiling[k] != after[k] for k in added):
        return ChangeAssessment(impact=Impact.U4, reasons=("new_capability_requires_review",), **details)
    if any(_expands(before[k], after[k]) for k in changed):
        return ChangeAssessment(impact=Impact.U4, reasons=("capability_authority_expanded",), **details)
    if policy_changed or migration_changed:
        return ChangeAssessment(impact=Impact.UX, reasons=("compatibility_proof_required",), **details)
    if changed:
        if all(_expands(after[k], before[k]) and after[k].version >= before[k].version for k in changed):
            return ChangeAssessment(impact=Impact.U2, reasons=("structured_authority_reduced",), **details)
        return ChangeAssessment(impact=Impact.UX, reasons=("changed_contract_requires_review",), **details)
    if added:
        return ChangeAssessment(impact=Impact.U3, reasons=("optional_capabilities_within_local_ceiling",), **details)
    if removed:
        return ChangeAssessment(impact=Impact.U2, reasons=("capabilities_removed",), **details)
    if presentation_only_proved:
        return ChangeAssessment(impact=Impact.U0, reasons=("local_presentation_evidence",), **details)
    return ChangeAssessment(impact=Impact.U1, reasons=("structured_inventory_unchanged",), **details)


class RevisionIdentities(BaseModel):
    """Independent identifiers; absent evidence is null, never substituted."""
    model_config = ConfigDict(extra="forbid", frozen=True)
    release_source_commit: str | None = None
    frontend_artifact_sha256: str | None = None
    backend_artifact_sha256: str | None = None
    policy_content_sha256: str | None = None
    loaded_policy_revision: str | None = None
    policy_contract_version: str | None = None
    capability_contract_version: int = SCHEMA_VERSION
    capability_registry_revision: str
    boundary_revision: int
    workspace_governance_revision: int | None = None
    authorization_version: int | None = None
    delegation_revision: int
    trust_root_version: int | None = None
    signed_metadata_version: int | None = None
    recovery_assisted_source_revision: str | None = None
    recovery_assisted_runtime_revision: str | None = None
    recovery_automatic_source_revision: str | None = None
    recovery_automatic_runtime_revision: str | None = None


class DecisionDimensions(BaseModel):
    """Independent facts; no composite 'trusted therefore authorized' flag."""
    model_config = ConfigDict(extra="forbid", frozen=True)
    authenticity: Literal["unknown", "verified", "failed"] = "unknown"
    integrity: Literal["unknown", "verified", "failed"] = "unknown"
    provenance: Literal["unknown", "verified", "failed"] = "unknown"
    compatibility: Literal["unknown", "compatible", "incompatible"] = "unknown"
    impact: Impact = Impact.UX
    authority: Literal["unknown", "within", "outside", "revoked", "expired"] = "unknown"
    preference: Literal["unknown", "permitted", "deferred"] = "unknown"
    runtime: Literal["unknown", "ready", "blocked"] = "unknown"
    execution: Literal["not_enabled"] = "not_enabled"
    outcome: Literal["unverified"] = "unverified"
