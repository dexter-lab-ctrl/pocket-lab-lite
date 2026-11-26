"""Diagnostic-only candidate review; no production trust or OPA mutation."""
import pytest
from pocket_lab_test_utils import ensure_runtime_path

ensure_runtime_path()
from api_fastapi.services.lite_lifecycle_contract import CAPABILITIES, canonical_bytes
from api_fastapi.services.lite_policy_compatibility import REGISTERED_MODULES, compare_source, differential_evidence
from api_fastapi.services.lite_capability_review import compare_capabilities


def policy(digest="a"*64):
    return canonical_bytes([{"path": p, "sha256": digest} for p in sorted(REGISTERED_MODULES)])


def test_source_equality_never_proves_loaded_policy():
    assert compare_source(policy(), policy())["state"] == "source_unchanged"
    changed = compare_source(policy(), policy("b"*64))
    assert changed["state"] == "unknown_semantic_impact"
    assert changed["execution_eligible"] is False


def test_differential_detects_constraint_loss_with_same_allow():
    result = differential_evidence({"allow": True, "constraints": ["step_up"]},
                                   {"allow": True, "constraints": []})
    assert result["changed_fields"] == ["constraints"]
    assert result["semantic_equivalence_proved"] is False
    assert result["execution_eligible"] is False


def test_sample_equality_is_not_equivalence():
    value = {"allow": False, "reason_code": "denied"}
    assert differential_evidence(value, value)["semantic_equivalence_proved"] is False


def test_capability_scope_expansion_not_granted():
    cap = CAPABILITIES[0]
    changed = cap.model_copy(update={"targets": tuple(sorted((*cap.targets, "other_target")))})
    review = compare_capabilities((cap,), (changed,))
    assert review["changes"][0]["impact"] == "U4"
    assert review["changes"][0]["execution_eligible"] is False


def test_contract_version_change_not_automatically_accepted():
    cap = CAPABILITIES[0]
    result = compare_capabilities((cap,), (cap.model_copy(update={"version": cap.version + 1}),))
    assert result["changes"][0]["impact"] == "UX"
