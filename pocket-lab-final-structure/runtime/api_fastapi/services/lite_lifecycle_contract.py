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


def _cap(id, domain, owner, action, target, data, *, read=True, network=False):
    return Capability(id=id, version=1, domain=domain, owner=owner, action=action,
                      targets=(target,), data=(data,), access="read" if read else "write",
                      risk="A" if read else "B", mutation=not read, network=network,
                      secret_access=False, unattended=False,
                      constraints=("current_authority",), confirmation_required=not read)


# Actual existing execution-owner names are referenced, not reimplemented.
# Future policy/release delegation is descriptive and never eligible here.
CAPABILITIES = (
    _cap("lifecycle.release.inspect", "release", "release_runtime", "lifecycle.release.inspect", "release_metadata", "public_release_metadata", network=True),
    _cap("lifecycle.release.verify", "release", "release_runtime", "lifecycle.release.verify", "staged_release", "release_evidence"),
    _cap("lifecycle.preferences.manage", "lifecycle", "fastapi", "lifecycle.preferences.manage", "local_workspace", "update_preferences", read=False),
    _cap("lifecycle.authority.manage", "lifecycle", "fastapi", "lifecycle.authority.manage", "local_workspace", "authority_records", read=False),
    _cap("lifecycle.delegation.review", "lifecycle", "fastapi", "lifecycle.delegation.review", "local_workspace", "authority_records"),
    _cap("system.activity_history.reconcile", "system_health", "projection_scheduler", "system_health.automatic", "local_activity_history", "activity_projection", read=False),
    _cap("lifecycle.policy.review", "rules", "lite_policy_lifecycle", "lifecycle.policy.review", "policy_metadata", "policy_evidence"),
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


def assess(old: tuple[Capability, ...], new: tuple[Capability, ...], *,
           policy_changed: bool, migration_changed: bool, root_changed: bool) -> ChangeAssessment:
    inventory(old)
    inventory(new)
    before = {c.id: c for c in old}
    after = {c.id: c for c in new}
    added = tuple(sorted(after.keys() - before.keys()))
    removed = tuple(sorted(before.keys() - after.keys()))
    changed = tuple(sorted(k for k in before.keys() & after.keys() if before[k] != after[k]))
    details = dict(added=added, removed=removed, changed=changed)
    if root_changed:
        return ChangeAssessment(impact=Impact.U5, reasons=("trust_root_changed",), **details)
    if added:
        return ChangeAssessment(impact=Impact.U4, reasons=("new_capability_requires_review",), **details)
    for k in changed:
        a, b = before[k], after[k]
        if (not set(b.targets).issubset(a.targets) or not set(b.data).issubset(a.data)
            or a.owner != b.owner or a.action != b.action or a.domain != b.domain
            or (a.access == "read" and b.access == "write") or b.risk > a.risk
            or any(not getattr(a, f) and getattr(b, f) for f in ("mutation", "network", "secret_access", "unattended"))
            or any(getattr(a, f) and not getattr(b, f) for f in ("confirmation_required", "qualification_required", "verification_required", "revocable"))
            or not set(a.constraints).issubset(b.constraints)):
            return ChangeAssessment(impact=Impact.U4, reasons=("capability_authority_expanded",), **details)
    if policy_changed or migration_changed:
        return ChangeAssessment(impact=Impact.UX, reasons=("compatibility_proof_required",), **details)
    if changed:
        return ChangeAssessment(impact=Impact.UX, reasons=("changed_contract_requires_review",), **details)
    if removed:
        return ChangeAssessment(impact=Impact.U2, reasons=("capabilities_removed",), **details)
    return ChangeAssessment(impact=Impact.U1, reasons=("structured_inventory_unchanged",), **details)


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
