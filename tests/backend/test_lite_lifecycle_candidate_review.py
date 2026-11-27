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


def test_runtime_observation_matches_exact_module_digests_only():
    import hashlib
    from api_fastapi.services.lite_policy_runtime_evidence import compare_loaded_modules
    names = sorted({p.rsplit("/", 1)[-1] for p in REGISTERED_MODULES} | {"revision.rego"})
    rows = [{"path": name, "sha256": hashlib.sha256(name.encode()).hexdigest()} for name in names]
    modules = [{"id": str(i), "raw": name} for i, name in enumerate(names)]
    assert compare_loaded_modules({"files": rows}, modules)
    assert not compare_loaded_modules({"files": rows}, modules[:-1])
    modules[0]["raw"] += "changed"
    assert not compare_loaded_modules({"files": rows}, modules)


def test_exact_scope_digest_binds_every_field():
    from api_fastapi.services.lite_lifecycle_contract import digest
    cap = CAPABILITIES[0]
    changed = cap.model_copy(update={"version": cap.version + 1})
    review = compare_capabilities((cap,), (changed,))
    scope = review["exact_scopes"][0]
    assert review["changes"][0]["scope_sha256"] == digest(scope)
    assert scope["before"] == cap.model_dump(mode="json")
    assert scope["after"] == changed.model_dump(mode="json")
    scope["after"]["network"] = not scope["after"]["network"]
    assert review["changes"][0]["scope_sha256"] != digest(scope)


def test_candidate_consent_request_cannot_smuggle_execution_scope():
    from pydantic import ValidationError
    from api_fastapi.services.lite_lifecycle_candidate_consent import CandidateConsentRequest
    body = dict(expected_revision=1, metadata_sha256="a"*64, capability_id=CAPABILITIES[0].id,
                scope_sha256="b"*64, disposition="accepted_for_review", confirm=True)
    assert CandidateConsentRequest(**body).disposition == "accepted_for_review"
    with pytest.raises(ValidationError):
        CandidateConsentRequest(**body, execution_enabled=True)
    with pytest.raises(ValidationError):
        CandidateConsentRequest(**{**body, "disposition": "enabled"})
