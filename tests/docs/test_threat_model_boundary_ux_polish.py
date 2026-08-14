from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
THREAT_DIR = ROOT / "docs/generated/enterprise/threat-model"


def test_all_canonical_boundary_pages_share_enterprise_detail_anatomy_and_navigation():
    model = json.loads((ROOT / "contracts/security/threat-model.json").read_text(encoding="utf-8"))
    required = (
        "pl-page-lede pl-threat-boundary-lede",
        "pl-threat-boundary-summary",
        "pl-threat-boundary-callout",
        "## Entry points",
        "## Allowed flows",
        "## Forbidden flows",
        "## Threats",
        "## Runtime evidence & provenance",
        "## Residual risk",
    )
    for boundary in model.get("boundaries") or []:
        page = (THREAT_DIR / f"{boundary['id']}.md").read_text(encoding="utf-8")
        for token in required:
            assert token in page, f"{boundary['id']}: missing {token}"
        assert "evidence-zone/" in page

    overview = (THREAT_DIR / "index.md").read_text(encoding="utf-8")
    assert 'href="evidence-zone/"' in overview
    assert "Promoted evidence → documentation" in overview


def test_evidence_projection_zone_matches_boundary_anatomy_without_becoming_canonical_boundary():
    evidence_zone = (THREAT_DIR / "evidence-zone.md").read_text(encoding="utf-8")
    model = json.loads((ROOT / "contracts/security/threat-model.json").read_text(encoding="utf-8"))

    assert "evidence-zone" not in {str(row.get("id")) for row in model.get("boundaries") or []}
    assert "does not create a tenth canonical threat boundary" in evidence_zone
    for heading in (
        "## Assets",
        "## Actors",
        "## Entry points",
        "## Data flows",
        "## Allowed flows",
        "## Forbidden flows",
        "## Threats",
        "## Controls",
        "## Runtime evidence & provenance",
        "## Residual risk",
        "## Guardrails",
        "## Review status",
    ):
        assert heading in evidence_zone


def test_fullscreen_source_keeps_mobile_overlay_but_fences_desktop_to_new_tabs():
    javascript = (ROOT / "docs/javascripts/threat-model-poster.js").read_text(encoding="utf-8")
    assert "isMobilePresentation" in javascript
    assert "navigator.maxTouchPoints" in javascript
    assert "pocketlab-threat-poster-" in javascript
    assert "window.open(link.href, name, 'noopener,noreferrer')" in javascript
    assert "cancelSameTabDesktopFullscreen" in javascript
