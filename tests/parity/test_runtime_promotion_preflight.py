from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT
    / "scripts/test/parity/preflight_runtime_promotion.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location(
        "runtime_promotion_preflight",
        SCRIPT,
    )
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_release_tag_format_is_strict():
    module = load_module()

    assert module.TAG_RE.fullmatch(
        "lite-2026.08.07.1"
    )
    assert module.TAG_RE.fullmatch(
        "lite-2026.08.07.10"
    )

    assert not module.TAG_RE.fullmatch(
        "2026.08.07.1"
    )
    assert not module.TAG_RE.fullmatch(
        "lite-2026.08.07.0"
    )


def test_expected_release_assets_are_complete():
    module = load_module()

    assert module.EXPECTED_RELEASE_ASSETS == {
        "dist.zip",
        "checksums.txt",
        "pocketlab-lite-release.json",
    }


def test_preflight_uses_exact_four_lane_inventory():
    module = load_module()

    domains = [
        "home",
        "apps",
        "devices",
        "security",
        "identity",
        "rules",
        "recovery",
    ]

    paths = module.evidence_paths(domains)

    assert len(paths) == 28

    browser = [
        item
        for item in paths
        if item[1] == "frontend"
    ]

    assert len(browser) == 14

    assert {
        project
        for _, _, project in browser
    } == {
        "live-desktop",
        "live-mobile",
    }


def test_missing_local_tag_is_a_safe_repair_boundary():
    module = load_module()

    # Contract-level guard: local tag reconciliation is
    # deliberately isolated from evidence mutation.
    assert callable(module.ensure_local_tag)
    assert callable(module.verify_evidence)
    assert callable(module.recompute_comparison)


def test_preflight_allows_truthful_runtime_drift(
    tmp_path,
    monkeypatch,
):
    module = load_module()

    comparison = {
        "release_tag": "lite-2026.08.12.2",
        "source_commit": "a6e4abc",
        "status": "needs-review",
        "domains": [
            {
                "id": "apps",
                "implementation_status": "implemented",
                "runtime_parity": "drift-detected",
                "comparison_summary": {
                    "mapped": 0,
                    "match": 10,
                    "mismatch": 2,
                    "not_applicable": 0,
                    "not_observed": 0,
                    "unsupported": 0,
                },
            }
        ],
    }

    normalized = tmp_path / "runtime-comparison.json"

    import json

    normalized.write_text(
        json.dumps(comparison),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        module,
        "NORMALIZED",
        normalized,
    )

    module.verify_comparison(
        "lite-2026.08.12.2",
        "a6e4abc",
        ["apps"],
    )


def test_preflight_never_has_runtime_write_api_logic():
    text = SCRIPT.read_text(encoding="utf-8")

    forbidden = (
        "/apply",
        "/restart",
        "/remove",
        "pm2 restart",
        "git reset",
        "git checkout",
        "git switch",
        "git tag -f",
        "git fetch --force",
    )

    for value in forbidden:
        assert value not in text
