"""README source governance tests. Defined for a later qualification session."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def gate_module():
    path = ROOT / "scripts/docs/check_readme.py"
    spec = importlib.util.spec_from_file_location("readme_static_gate", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_readme_claims_assets_and_links():
    assert gate_module().run_checks(ROOT) == []


def test_claim_inventory_does_not_reinterpret_verification():
    data = json.loads((ROOT / "contracts/metadata/readme-claims.json").read_text())
    assert data["schema_version"] == 1
    assert "not an independent verification" in data["description"].lower()
    assert "uncommitted" in data["description"]
    assert len(data["claims"]) >= 7
    assert all(item.get("sources") and item.get("limitation") for item in data["claims"])
    assert all("verified" not in item and "evidence_status" not in item for item in data["claims"])


def test_readme_visuals_are_explicitly_mocked_with_pinned_provenance():
    data = json.loads((ROOT / "contracts/metadata/readme-media.json").read_text())
    assert len(data["captures"]) >= 5
    assert all(i["environment"] == "mocked" and len(i["sha"]) == 40 for i in data["captures"])
    assert all(len(i["spec_sha"]) == 40 for i in data["captures"])


def test_readme_limits_critical_marketing_claims():
    content = (ROOT / "README.md").read_text().lower()
    assert "not a live installation" in content
    assert "not a guarantee of security" in content
    assert "explicitly registered actions" in content
    assert "releases/latest" in content
