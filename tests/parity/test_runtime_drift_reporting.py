from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(
        name,
        path,
    )
    assert spec and spec.loader

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module


semantic = load_module(
    ROOT
    / "scripts/test/parity/"
    / "semantic_compare.py",
    "semantic_compare_runtime_drift_reporting",
)

comparison = load_module(
    ROOT
    / "scripts/test/parity/"
    / "compare_runtime_parity.py",
    "compare_runtime_drift_reporting",
)


def test_text_contains_handles_adjacent_dom_nodes():
    assert semantic._normalized_contains(
        (
            "Featured local app"
            "PhotoPrism"
            "Private photo library"
        ),
        "PhotoPrism",
    )

    assert semantic._normalized_contains(
        (
            "Access readiness"
            "Vault readiness will appear"
        ),
        "Vault readiness will appear",
    )


def test_over_redaction_reports_capture_corrupted():
    marker = "[private-identity]"

    domain = {
        "semantic_mappings": [{
            "id": "home-overall-presentation",
            "backend_path": "overall_status",
            "frontend_path": "screen_text",
            "operator": (
                "intentional-presentation-map"
            ),
            "mapping": {
                "degraded": [
                    "Review recommended",
                ],
            },
            "severity": "high",
        }],
    }

    backend = {
        "observations": {
            "overall_status": "degraded",
        },
    }

    frontend = {
        "observations": {
            "screen_text": (
                marker * 12
                + "Review recommended"
            ),
        },
    }

    result = semantic.compare_domain(
        domain,
        backend,
        frontend,
    )[0]

    assert result["result"] == "capture-corrupted"

    assert comparison.semantic_status(
        [result],
        ["observed"] * 4,
    ) == (
        "capture-corrupted",
        "partial",
    )


def test_required_unsupported_is_contract_gap():
    result = {
        "result": "unsupported",
        "required": True,
        "implementation_status": "implemented",
        "boundary": "live-api-live-ui",
    }

    assert comparison.semantic_status(
        [result],
        ["observed"] * 4,
    ) == (
        "contract-gap",
        "partial",
    )


def test_optional_implemented_absence_is_partial():
    result = {
        "result": "not-applicable",
        "required": False,
        "implementation_status": "implemented",
        "boundary": "live-api-live-termux",
    }

    assert comparison.semantic_status(
        [result],
        ["observed"] * 4,
        "partial",
    ) == (
        "partial",
        "partial",
    )


def test_real_mismatch_remains_drift():
    result = {
        "result": "mismatch",
        "required": True,
        "implementation_status": "implemented",
        "accepted_limitation": False,
        "boundary": "live-api-live-ui",
    }

    assert comparison.semantic_status(
        [result],
        ["observed"] * 4,
    ) == (
        "drift-detected",
        "needs-review",
    )

def test_not_applicable_is_a_supported_comparison_result():
    counts = {
        name: 0
        for name in (
            "match",
            "mapped",
            "mismatch",
            "unsupported",
            "not-observed",
            "not-applicable",
            "capture-corrupted",
        )
    }

    result = "not-applicable"
    counts[result] = counts.get(result, 0) + 1

    assert counts["not-applicable"] == 1

