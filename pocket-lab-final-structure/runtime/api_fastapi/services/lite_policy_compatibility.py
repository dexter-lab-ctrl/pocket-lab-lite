"""Conservative source compatibility and differential evidence, not admission.

Source equality is not loaded-runtime identity. Finite observations never prove
arbitrary Rego equivalence. Changed Rego stays held until a locally supported
evolution contract and independent activation proof exist.
"""
from __future__ import annotations

from .lite_lifecycle_contract import canonical_bytes
from .lite_release_package import POLICY_PREFIX, _inventory
from .lite_release_trust import TrustError

REGISTERED_MODULES = frozenset(
    POLICY_PREFIX + "pocketlab/" + name for name in (
        "pocketlab.rego", "harness_test.rego", "pocketlab_test.rego",
        "pr557_owner_personal_mode_hotfix_test.rego",
    )
)


def compare_source(installed: bytes | None, candidate: bytes):
    after = _inventory(candidate, prefix=POLICY_PREFIX, suffix=".rego")
    if set(after) != REGISTERED_MODULES:
        return {"state": "unsupported_inventory", "reason_code": "policy_module_set_unknown",
                "execution_eligible": False}
    if installed is None:
        return {"state": "unknown", "reason_code": "local_policy_source_unavailable",
                "execution_eligible": False}
    before = _inventory(installed, prefix=POLICY_PREFIX, suffix=".rego")
    changed = sorted(name for name in set(before) | set(after) if before.get(name) != after.get(name))
    return {"state": "unknown_semantic_impact" if changed else "source_unchanged",
            "reason_code": "policy_compatibility_proof_required" if changed else "loaded_policy_proof_required",
            "changed_module_count": len(changed), "execution_eligible": False}


def differential_evidence(before: dict, after: dict):
    """Compare complete decision envelopes, including unknown fields.

    This is a diagnostic comparator only. Unknown schemas and any changes hold
    activation; no allow-only comparison or positive execution decision.
    """
    if not isinstance(before, dict) or not isinstance(after, dict):
        raise TrustError("policy_decision_invalid")
    if type(before.get("allow")) is not bool or type(after.get("allow")) is not bool:
        raise TrustError("policy_decision_invalid")
    fields = sorted(k for k in set(before) | set(after)
                    if k not in before or k not in after or canonical_bytes(before[k]) != canonical_bytes(after[k]))
    return {"state": "differences_observed" if fields else "sample_equal",
            "changed_fields": fields, "semantic_equivalence_proved": False,
            "execution_eligible": False}
