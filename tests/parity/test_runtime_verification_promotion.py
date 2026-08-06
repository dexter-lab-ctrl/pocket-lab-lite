from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

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
        "tests_per_project": 3,
        "status": "verified",
    }



def test_playwright_report_rejects_mocked_mode_and_incomplete_projects():
    mocked = live_report()
    mocked["config"]["metadata"]["pocketlab_lite_mode"] = "mocked"
    with pytest.raises(SystemExit, match="not from LITE_E2E_MODE=live"):
        promotion.validate_playwright(mocked)

    incomplete = live_report()
    for suite in incomplete["suites"]:
        for spec in suite["specs"]:
            spec["tests"] = [item for item in spec["tests"] if item["projectName"] == "live-desktop"]
    with pytest.raises(SystemExit, match="incomplete"):
        promotion.validate_playwright(incomplete)


def test_promotion_rejects_incomplete_or_unobserved_semantic_comparison():
    domain = {
        "id": "home",
        "live_api_coverage": "observed",
        "live_ui_coverage": "capture-failed",
        "live_termux_coverage": "observed",
        "runtime_parity": "capture-failed",
        "comparisons": [],
    }
    with pytest.raises(SystemExit, match="incomplete for home"):
        promotion.validate_promotable_comparison({"domains": [domain]})

    domain.update({
        "live_ui_coverage": "observed",
        "runtime_parity": "verified",
        "comparisons": [{"result": "not-observed"}],
    })
    with pytest.raises(SystemExit, match="unobserved fields"):
        promotion.validate_promotable_comparison({"domains": [domain]})


def test_observation_validation_rejects_stale_source_release_and_kind(tmp_path, monkeypatch):
    now = datetime.now(timezone.utc).replace(microsecond=0)
    payload = {
        "schema_version": "2.0.0",
        "evidence_kind": "backend",
        "domain": "home",
        "status": "observed",
        "sanitized": True,
        "captured_at": now.isoformat().replace("+00:00", "Z"),
        "source_commit": "a" * 40,
        "release_tag": "lite-2026.08.06.1",
        "observations": {"status": "healthy"},
        "error_code": "",
    }
    target = tmp_path / "home.json"
    target.write_text(json.dumps(payload), encoding="utf-8")
    assert promotion.validate_observation(
        target, evidence_kind="backend", domain="home", source_commit="a" * 40,
        release_tag="lite-2026.08.06.1",
    )["status"] == "observed"

    with pytest.raises(SystemExit, match="source commit mismatch"):
        promotion.validate_observation(
            target, evidence_kind="backend", domain="home", source_commit="b" * 40,
            release_tag="lite-2026.08.06.1",
        )
    with pytest.raises(SystemExit, match="release tag mismatch"):
        promotion.validate_observation(
            target, evidence_kind="backend", domain="home", source_commit="a" * 40,
            release_tag="lite-2026.08.06.2",
        )
    with pytest.raises(SystemExit, match="identity mismatch"):
        promotion.validate_observation(
            target, evidence_kind="termux", domain="home", source_commit="a" * 40,
            release_tag="lite-2026.08.06.1",
        )

    payload["captured_at"] = (now - timedelta(days=2)).isoformat().replace("+00:00", "Z")
    target.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setenv("LITE_PARITY_MAX_EVIDENCE_AGE_SECONDS", "60")
    with pytest.raises(SystemExit, match="is stale"):
        promotion.validate_observation(
            target, evidence_kind="backend", domain="home", source_commit="a" * 40,
            release_tag="lite-2026.08.06.1",
        )

def test_legacy_recovery_runtime_overlays_coverage_only():
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
    assert recovery["runtime_parity"] == "unvalidated"
    assert recovery["status"] != "verified"
    assert devices["live_api_coverage"] == "unvalidated"


def test_repository_baseline_is_sanitized_and_valid():
    payload = json.loads(promotion.BASELINE.read_text(encoding="utf-8"))
    promotion.validate_baseline(payload)


def test_promotion_rejects_release_tag_not_bound_to_current_head(monkeypatch):
    def fake_git(*args):
        return "a" * 40 if args[:2] == ("rev-parse", "HEAD") else "b" * 40

    monkeypatch.setattr(promotion, "git", fake_git)
    try:
        promotion.promote("lite-2026.08.06.1")
    except SystemExit as exc:
        assert "not current HEAD" in str(exc)
    else:
        raise AssertionError("promotion accepted a tag bound to another commit")


def test_promotion_rejects_comparison_source_mismatch(monkeypatch):
    monkeypatch.setattr(promotion, "git", lambda *args: "a" * 40)
    monkeypatch.setattr(promotion, "validate_playwright", lambda report: {"projects": sorted(promotion.EXPECTED_PROJECTS), "tests_per_project": 3, "status": "verified"})
    monkeypatch.setattr(promotion, "validate_v2", lambda payload, schema: None)
    monkeypatch.setattr(promotion, "validate_freshness", lambda payload: None)

    comparison_payload = {
        "source_commit": "b" * 40,
        "release_tag": "lite-2026.08.06.1",
        "browser_projects": sorted(promotion.EXPECTED_PROJECTS),
    }

    def fake_load(path):
        if path == promotion.PLAYWRIGHT_REPORT:
            return {}
        if path == promotion.COMPARISON:
            return comparison_payload
        raise AssertionError(path)

    monkeypatch.setattr(promotion, "load_json", fake_load)
    try:
        promotion.promote("lite-2026.08.06.1")
    except SystemExit as exc:
        assert "source commit does not match" in str(exc)
    else:
        raise AssertionError("promotion accepted a comparison from another source commit")


def test_promotion_rejects_comparison_release_mismatch(monkeypatch):
    monkeypatch.setattr(promotion, "git", lambda *args: "a" * 40)
    monkeypatch.setattr(promotion, "validate_playwright", lambda report: {"projects": sorted(promotion.EXPECTED_PROJECTS), "tests_per_project": 3, "status": "verified"})
    monkeypatch.setattr(promotion, "validate_v2", lambda payload, schema: None)
    monkeypatch.setattr(promotion, "validate_freshness", lambda payload: None)

    comparison_payload = {
        "source_commit": "a" * 40,
        "release_tag": "lite-2026.08.05.9",
        "browser_projects": sorted(promotion.EXPECTED_PROJECTS),
    }
    monkeypatch.setattr(
        promotion,
        "load_json",
        lambda path: {} if path == promotion.PLAYWRIGHT_REPORT else comparison_payload,
    )
    try:
        promotion.promote("lite-2026.08.06.1")
    except SystemExit as exc:
        assert "release tag does not match" in str(exc)
    else:
        raise AssertionError("promotion accepted comparison evidence from another release")
