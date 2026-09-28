from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_lite_ux_maturity_contract_covers_all_18_requirements() -> None:
    contract = json.loads(read("contracts/metadata/lite-ux-maturity.json"))
    requirements = contract["requirements"]
    assert [item["id"] for item in requirements] == list(range(1, 19))
    for item in requirements:
        assert item["name"]
        assert item["evidence"]
        for evidence_path in item["evidence"]:
            assert (ROOT / evidence_path).exists(), f"missing UX evidence: {evidence_path}"


def test_shared_ux_primitives_and_plain_language_contract_exist() -> None:
    primitives = read("src/lite/LiteUx.jsx")
    presentation = read("src/lib/liteUxPresentation.js")
    for marker in (
        "LiteFreshness",
        "LiteEmptyState",
        "LiteTechnicalFacts",
        "LiteHistoryTimeline",
        "LiteActionOutcome",
        "LiteConsequenceSummary",
    ):
        assert marker in primitives
    assert "LITE_DEFAULT_UI_FORBIDDEN_TERMS" in presentation
    assert "assertPlainLanguage" in presentation
    assert "friendlyLiteText" in presentation


def test_every_primary_tab_has_story_or_summary_first_and_freshness() -> None:
    files = {
        "home": "src/lite/LiteHome.jsx",
        "apps": "src/lite/catalog/AppCatalogScreen.jsx",
        "devices": "src/lite/LiteDevices.jsx",
        "safety": "src/lite/LiteSecurity.jsx",
        "access": "src/lite/LiteIdentity.jsx",
        "rules": "src/lite/LiteRules.jsx",
        "recovery": "src/lite/LiteRecovery.jsx",
    }
    for name, path in files.items():
        source = read(path)
        assert "LiteFreshness" in source, f"{name} must expose product freshness"
        assert any(marker in source for marker in ("LiteOperationalStory", "summary-first", "Open", "Manage")), f"{name} must remain summary/action oriented"


def test_primary_navigation_uses_lite_product_language() -> None:
    source = read("src/lite/liteNavigationMetadata.js")
    for label in ("Home", "Apps", "Access", "Safety", "Devices", "Rules", "Recovery"):
        assert f"label: '{label}'" in source
    assert "label: 'App Catalog'" not in source
    assert "label: 'Identity & Access'" not in source
    assert "label: 'Security'" not in source


def test_former_default_ui_backend_phrases_are_removed_from_focused_surfaces() -> None:
    focused_paths = [
        "src/lite/LiteHome.jsx",
        "src/lite/LiteDevices.jsx",
        "src/lite/LiteIdentity.jsx",
        "src/lite/LiteRules.jsx",
        "src/lite/catalog/AppActionDetailsLazy.jsx",
        "src/lite/recovery/RecoveryConfirmSheetLazy.jsx",
    ]
    forbidden_phrases = (
        "Pocket Lab queued this through the control plane",
        "Worker picked it up",
        "Backend-owned check path",
        "Polling: slow",
        "FastAPI derives the current actor",
        "A backend record was saved for troubleshooting",
        "Raw cookies and session tokens are never shown",
    )
    combined = "\n".join(read(path) for path in focused_paths)
    for phrase in forbidden_phrases:
        assert phrase not in combined


def test_meaningful_technical_details_and_consequence_confirmations_are_reused() -> None:
    assert "LiteTechnicalFacts" in read("src/lite/LiteHome.jsx")
    assert "LiteTechnicalFacts" in read("src/lite/LiteRules.jsx")
    assert "LiteTechnicalFacts" in read("src/lite/LiteSecurity.jsx")
    consequence_paths = [
        "src/lite/LiteDevices.jsx",
        "src/lite/LiteSecurity.jsx",
        "src/lite/LiteIdentity.jsx",
        "src/lite/catalog/AppCatalogScreen.jsx",
        "src/lite/recovery/RecoveryConfirmSheetLazy.jsx",
    ]
    for path in consequence_paths:
        assert "LiteConsequenceSummary" in read(path)


def test_unified_history_and_context_help_contracts_are_present() -> None:
    assert "LiteHistoryTimeline" in read("src/lite/LiteIdentity.jsx")
    assert "LiteHistoryTimeline" in read("src/lite/LiteRules.jsx")
    assert "LiteHistoryTimeline" in read("src/lite/LiteRecovery.jsx")
    assert "LiteHistoryTimeline" in read("src/lite/devices/DeviceDetailsLazy.jsx")
    help_source = read("src/lite/LiteHelp.jsx")
    assert "Explain this" in help_source
    assert "Why it matters" in help_source
    assert "What you can do" in help_source


def test_global_shell_supports_saved_information_instead_of_blank_offline_failure() -> None:
    source = read("src/lite/LiteApp.jsx")
    assert "Using saved information" in source
    assert "Actions that need a live connection" in source
    assert "You are offline" not in source


def test_ux_contract_has_storybook_unit_and_e2e_qualification_sources() -> None:
    for path in (
        "src/lite/LiteUx.stories.jsx",
        "src/lib/liteUxPresentation.test.js",
        "tests/e2e/lite-ux-maturity.spec.ts",
        "docs/validation/lite-ux-maturity-contract.md",
    ):
        assert (ROOT / path).exists()
