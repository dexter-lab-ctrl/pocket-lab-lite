from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest

from scripts.test.parity.parity_common import (
    FIXTURE_ROOT,
    GENERATED_ROOT,
    MODEL_PATH,
    ROOT,
    assert_bounded,
    assert_safe_text,
    assert_unique_ids,
    load_json,
    semantic_fingerprint,
    stable_json,
)

GENERATOR = ROOT / "scripts" / "docs" / "parity" / "generate_parity.py"
MODEL_SCHEMA = ROOT / "schemas" / "parity" / "parity-model.schema.json"
CONTRACT_SCHEMA = ROOT / "schemas" / "parity" / "parity-contract.schema.json"
DOC_ROOT = ROOT / "docs" / "generated" / "development" / "validation" / "parity"


def _generated_bytes() -> dict[str, bytes]:
    roots = (GENERATED_ROOT, FIXTURE_ROOT, DOC_ROOT)
    output = {}
    for root in roots:
        for path in sorted(root.rglob("*")):
            if path.is_file():
                output[str(path.relative_to(ROOT))] = path.read_bytes()
    output["docs/generated/production/parity-readiness.md"] = (
        ROOT / "docs" / "generated" / "production" / "parity-readiness.md"
    ).read_bytes()
    output["src/test/fixtures/generated/parity/recovery-parity.js"] = (
        ROOT / "src" / "test" / "fixtures" / "generated" / "parity" / "recovery-parity.js"
    ).read_bytes()
    return output


def test_parity_generation_is_two_run_byte_deterministic() -> None:
    subprocess.run([sys.executable, str(GENERATOR), "generate"], cwd=ROOT, check=True)
    first = _generated_bytes()
    subprocess.run([sys.executable, str(GENERATOR), "generate"], cwd=ROOT, check=True)
    second = _generated_bytes()
    assert first == second
    subprocess.run([sys.executable, str(GENERATOR), "check"], cwd=ROOT, check=True)


def test_model_and_generated_contracts_validate_and_share_fingerprint() -> None:
    model = load_json(MODEL_PATH)
    jsonschema.Draft202012Validator(load_json(MODEL_SCHEMA)).validate(model)
    expected = semantic_fingerprint(model)
    for path in sorted(GENERATED_ROOT.glob("*.json")):
        contract = load_json(path)
        jsonschema.Draft202012Validator(load_json(CONTRACT_SCHEMA)).validate(contract)
        assert contract["semantic_fingerprint"] == expected
        assert_unique_ids(contract["items"], path.name)
        assert_bounded(path)
        assert_safe_text(stable_json(contract), path.name)


def test_mappings_have_existing_sources_targets_and_owners() -> None:
    model = load_json(MODEL_PATH)
    owners = {item["owner"] for item in model["ownership"]}
    boundaries = {item["id"] for item in model["architecture"]["boundaries"]}
    projection_domains = {item["domain"] for item in model["api_projections"]}
    selector_source = (ROOT / "src" / "lib" / "liteViewModels.js").read_text(encoding="utf-8")
    assert owners
    for boundary in model["architecture"]["boundaries"]:
        assert boundary["owner"] in owners
    for mapping in model["field_mappings"]:
        assert mapping["boundary"] in boundaries
        assert mapping["domain"] in projection_domains
        assert mapping["source"] and mapping["target"] and mapping["test_id"]
        if mapping.get("selector"):
            assert mapping["selector"] in selector_source


def test_scenario_linkage_is_complete_and_no_ui_compares_raw_sqlite() -> None:
    model = load_json(MODEL_PATH)
    assert_unique_ids(model["scenarios"], "scenarios")
    for scenario in model["scenarios"]:
        assert scenario["storybook_story"]
        assert scenario["mocked_playwright_test"].startswith("tests/e2e/lite-parity.spec.ts#")
        assert scenario["accessibility_test"]
        assert scenario["evidence_result"]
    prohibited = " ".join(model["architecture"]["prohibited_shortcuts"]).lower()
    assert "rendered ui to raw sqlite comparison" in prohibited
    assert "browser sqlite access" in prohibited


def test_redaction_rejects_secret_address_path_and_oversized_evidence(tmp_path: Path) -> None:
    bad_values = (
        "Bearer abcdefghijklmnopqrstuvwxyz",
        "password=do-not-store",
        "192.168.1.22",
        "/home/example/.ssh/id_ed25519",
        "/data/data/com.termux/files/home/private",
    )
    from scripts.test.parity.parity_common import assert_bounded, assert_safe_text

    for value in bad_values:
        with pytest.raises(AssertionError):
            assert_safe_text(value)
    oversized = tmp_path / "oversized.json"
    oversized.write_bytes(b"x" * 256_001)
    with pytest.raises(AssertionError):
        assert_bounded(oversized, 256_000)



def test_storybook_and_playwright_sources_are_linked_to_every_registry_scenario() -> None:
    model = load_json(MODEL_PATH)
    stories = (ROOT / "src" / "lite" / "LiteRecoveryParity.stories.jsx").read_text(encoding="utf-8")
    playwright = (ROOT / "tests" / "e2e" / "lite-parity.spec.ts").read_text(encoding="utf-8")
    assert "recoveryParityScenarios" in playwright
    for scenario in model["scenarios"]:
        assert f"export const {scenario['storybook_export']}" in stories
        assert scenario["id"] in stories

def test_generated_documentation_has_no_drift() -> None:
    subprocess.run([sys.executable, str(GENERATOR), "check"], cwd=ROOT, check=True)
