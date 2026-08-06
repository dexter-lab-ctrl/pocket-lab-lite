from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


promotion = load_module(
    ROOT / "scripts" / "test" / "parity" / "promote_runtime_verification.py",
    "promote_runtime_verification",
)
generator = load_module(
    ROOT / "scripts" / "docs" / "parity" / "generate_parity.py",
    "generate_parity",
)


def live_report() -> dict:
    specs = []
    for title in sorted(promotion.EXPECTED_TESTS):
        specs.append(
            {
                "title": title,
                "tests": [
                    {"projectName": project, "results": [{"status": "passed"}]}
                    for project in sorted(promotion.EXPECTED_PROJECTS)
                ],
            }
        )
    return {
        "config": {"metadata": {"pocketlab_lite_mode": "live"}},
        "suites": [{"title": "Pocket Lab Lite live read-only smoke", "specs": specs}],
    }


def test_live_playwright_report_requires_both_projects_and_tests():
    result = promotion.validate_playwright(live_report())
    assert result == {
        "projects": ["live-desktop", "live-mobile"],
        "tests_per_project": 2,
        "status": "verified",
    }


def test_promoted_recovery_runtime_overlays_only_runtime_lanes():
    model = json.loads((ROOT / "contracts" / "parity" / "parity-model.json").read_text())
    baseline = {
        "schema_version": "1.0.0",
        "sanitized": True,
        "status": "verified",
        "source_commit": "a" * 40,
        "release_tag": "lite-2026.08.05.2",
        "domains": [
            {
                "id": "recovery",
                "live_api_coverage": "verified",
                "live_termux_coverage": "verified",
                "status": "verified",
            }
        ],
    }
    merged = generator.apply_runtime_baseline(model, baseline)
    recovery = next(item for item in merged["domains"] if item["id"] == "recovery")
    devices = next(item for item in merged["domains"] if item["id"] == "devices")
    assert recovery["live_api_coverage"] == "verified"
    assert recovery["live_termux_coverage"] == "verified"
    assert recovery["status"] == "verified"
    assert devices["live_api_coverage"] == "unvalidated"


def test_repository_baseline_is_sanitized_and_valid():
    payload = json.loads(promotion.BASELINE.read_text(encoding="utf-8"))
    promotion.validate_baseline(payload)
