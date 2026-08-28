from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROMOTED = ROOT / "contracts/generated/releases/promoted-release-evidence.json"
MANIFEST_ROOT = ROOT / "contracts/generated/releases/manifests"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def promoted_releases() -> list[dict]:
    payload = json.loads(PROMOTED.read_text(encoding="utf-8"))
    rows = payload.get("releases")
    assert isinstance(rows, list)
    return rows


def test_promoted_releases_have_immutable_inventory_manifest_snapshots():
    promotion = load_module(
        "release_evidence_promotion_test",
        ROOT / "scripts/docs/enterprise/release_evidence_promotion.py",
    )
    rows = promoted_releases()
    assert len(rows) >= 2
    tags = {str(row["release_tag"]) for row in rows}
    assert {"lite-2026.08.12.2", "lite-2026.08.19.2"} <= tags

    for row in rows:
        tag = str(row["release_tag"])
        assert row["verification_status"] == "promoted"
        assert row["sanitized"] is True
        snapshot = MANIFEST_ROOT / tag / "pocketlab-lite-release.json"
        assert snapshot.is_file(), tag
        actual = json.loads(snapshot.read_text(encoding="utf-8"))
        assert actual == promotion.release_manifest_snapshot(row)
        assert actual["release_tag"] == tag
        assert actual["source_commit"] == row["source_commit"]
        assert actual["dist_zip_sha256"] == row["manifest_binding"]["dist_zip_sha256"]
        assert set(actual["artifacts"]) == {
            "dist.zip",
            "checksums.txt",
            "pocketlab-lite-release.json",
        }


def test_existing_platform_release_catalog_discovers_promoted_manifest_snapshots():
    platform = load_module(
        "release_platform_catalog_test",
        ROOT / "scripts/docs/lite/generate_platform_catalogs.py",
    )
    outputs = platform.release_outputs()
    inventory_path = ROOT / "docs/generated/development/release-inventory.md"
    index_path = ROOT / "contracts/generated/releases/index.json"
    assert inventory_path in outputs
    assert index_path in outputs

    inventory = outputs[inventory_path]
    index = json.loads(outputs[index_path])
    tags = {
        str(row["release_tag"])
        for row in index["release_inventory"]["releases"]
    }
    assert {"lite-2026.08.12.2", "lite-2026.08.19.2"} <= tags
    assert "lite-2026.08.12.2" in inventory
    assert "lite-2026.08.19.2" in inventory
    assert "no verified release manifest present" not in inventory.lower()


def test_release_inventory_hook_is_static_evidence_backed_and_renders_enterprise_primitives():
    hook_path = ROOT / "scripts/docs/hooks/release_inventory.py"
    source = hook_path.read_text(encoding="utf-8")
    hook = load_module("release_inventory_hook_test", hook_path)
    rendered = hook._render_inventory()

    assert "contracts/generated/releases/promoted-release-evidence.json" in source
    for forbidden in ("import subprocess", "import requests", "import urllib", "gh api", "gh release"):
        assert forbidden not in source
    for tag in ("lite-2026.08.12.2", "lite-2026.08.19.2"):
        assert tag in rendered
    for primitive in (
        'class="pl-page-lede"',
        'class="pl-kpi-grid"',
        'class="pl-card-grid"',
        'class="pl-fact-grid"',
        'class="pl-table-wrap"',
        'class="pl-lineage"',
    ):
        assert primitive in rendered
    assert "Artifact integrity and full digests" in rendered
    assert "Evidence & Promotion" in rendered
    assert "Release Assurance" in rendered
    assert "does **not** claim live runtime health" in rendered
    assert "Evidence & Promotion" in hook._release_hub_addendum()


def test_evidence_and_promotion_page_tracks_established_release_contract():
    page = (ROOT / "docs/release/evidence-promotion.md").read_text(encoding="utf-8")
    required = (
        "LITE_E2E_LIVE=1 task lite:check:release",
        "LITE_ANDROID_GATE=1",
        "task lite:release:dry-run",
        "task lite:release:artifact-check",
        ".github/workflows/release-dist.yml",
        "lite-YYYY.MM.DD.N",
        "repair_existing_release=true",
        "dist.zip",
        "checksums.txt",
        "pocketlab-lite-release.json",
        "task lite:docs:release-assurance:capture",
        "task lite:docs:release-assurance:promote",
        "task lite:docs:release-assurance:check",
        "task lite:docs:generate",
        "task lite:docs:check",
        "LITE_RUNTIME_PROMOTE=1 task lite:runtime:termux:promote",
        "task lite:docs:supply-chain:capture",
        "task lite:docs:supply-chain:promote",
        'class="pl-journey-stepper"',
        'class="pl-card-grid"',
        'class="pl-lineage"',
    )
    for token in required:
        assert token in page, token

    workflow = (ROOT / ".github/workflows/release-dist.yml").read_text(encoding="utf-8")
    gate = (ROOT / "scripts/dev/lite/run-gate.sh").read_text(encoding="utf-8")
    tasks = (ROOT / "tasks/Taskfile.docs.yml").read_text(encoding="utf-8")
    assert "git tag -a" in workflow
    assert "release_tag" in workflow and "repair_existing_release" in workflow
    assert "LITE_E2E_LIVE" in gate and "release-dry-run" in gate
    for task_name in (
        "lite:docs:release-assurance:capture:",
        "lite:docs:release-assurance:promote:",
        "lite:docs:release-assurance:check:",
    ):
        assert task_name in tasks


def test_mkdocs_registers_release_inventory_hook_without_breaking_canonical_release_nav_ownership():
    mkdocs = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    assert "hooks:\n  - scripts/docs/hooks/release_inventory.py" in mkdocs
    assert "- Release inventory: generated/development/release-inventory.md" in mkdocs
    # The source-owned procedure is contextually linked from the release hub and
    # inventory. It is intentionally not assigned a conflicting top-level nav
    # owner until the canonical IA contract explicitly owns docs/release/*.
    assert "Evidence & Promotion: release/evidence-promotion.md" not in mkdocs
