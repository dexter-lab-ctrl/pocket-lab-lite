from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


semantic = load_module(ROOT / "scripts" / "test" / "parity" / "semantic_compare.py", "semantic_compare_planned_fields")
comparison = load_module(ROOT / "scripts" / "test" / "parity" / "compare_runtime_parity.py", "compare_runtime_planned_fields")
promotion = load_module(ROOT / "scripts" / "test" / "parity" / "promote_runtime_verification.py", "promote_runtime_planned_fields")


def test_presentation_map_matches_case_and_concatenated_dom_text() -> None:
    healthy = semantic.compare_values(
        "intentional-presentation-map",
        "healthy",
        "Needs attentionProtected · review item",
        {"mapping": {"healthy": ["Protected"]}},
    )
    profile = semantic.compare_values(
        "intentional-presentation-map",
        "app",
        "PhotoPrism App CheckApp Check completed.",
        {"mapping": {"app": ["App Check", "PhotoPrism"]}},
    )
    assert healthy["result"] == "mapped"
    assert profile["result"] == "mapped"


def test_termux_comparison_propagates_implemented_metadata() -> None:
    domain = {
        "id": "rules",
        "live_observation_contract": {
            "backend": {
                "fields": [
                    {
                        "id": "status",
                        "authority_operator": "exact",
                        "authority_severity": "high",
                    }
                ]
            }
        },
    }
    backend = {"status": "observed", "observations": {"status": "healthy"}}
    termux = {"status": "observed", "observations": {"status": "healthy"}}
    result = comparison.termux_agreement(domain, backend, termux)[0]
    assert result["result"] == "match"
    assert result["required"] is True
    assert result["implementation_status"] == "implemented"


def test_planned_optional_missing_field_is_partial_not_verified() -> None:
    result = {
        "result": "not-observed",
        "boundary": "live-api-live-termux",
        "required": False,
        "implementation_status": "planned",
        "accepted_limitation": False,
    }
    assert comparison.is_planned_optional(result) is True
    assert comparison.blocking_not_observed(result) is False
    assert comparison.semantic_status([result], ["observed"] * 4, "partial") == ("partial", "partial")


def test_required_missing_field_remains_blocking() -> None:
    result = {
        "result": "not-observed",
        "boundary": "live-api-live-termux",
        "required": True,
        "implementation_status": "implemented",
        "accepted_limitation": False,
    }
    assert comparison.blocking_not_observed(result) is True
    assert comparison.semantic_status([result], ["observed"] * 4, "implemented") == ("partial", "partial")


def _domain(comparison_item: dict, *, implementation_status: str, runtime_parity: str = "partial") -> dict:
    return {
        "id": "identity",
        "implementation_status": implementation_status,
        "live_api_coverage": "observed",
        "live_ui_coverage": "observed",
        "live_termux_coverage": "observed",
        "runtime_parity": runtime_parity,
        "comparisons": [comparison_item],
    }


def test_promotion_permits_planned_optional_partial_domain() -> None:
    item = {
        "id": "identity-termux-identity_guard",
        "result": "not-observed",
        "required": False,
        "implementation_status": "planned",
        "accepted_limitation": False,
    }
    promotion.validate_promotable_comparison({"domains": [_domain(item, implementation_status="partial")]})


def test_promotion_rejects_required_unobserved_field() -> None:
    item = {
        "id": "recovery-termux-restore_allowed",
        "result": "not-observed",
        "required": True,
        "implementation_status": "implemented",
        "accepted_limitation": False,
    }
    with pytest.raises(SystemExit, match="required unobserved fields"):
        promotion.validate_promotable_comparison({"domains": [_domain(item, implementation_status="implemented")]})


def test_declared_partial_domain_is_promotable_without_becoming_verified() -> None:
    item = {
        "id": "rules-termux-status",
        "result": "match",
        "required": True,
        "implementation_status": "implemented",
        "accepted_limitation": False,
    }
    promotion.validate_promotable_comparison({"domains": [_domain(item, implementation_status="partial")]})
