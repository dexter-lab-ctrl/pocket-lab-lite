from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENTERPRISE = ROOT / "scripts/docs/enterprise"
if str(ENTERPRISE) not in sys.path:
    sys.path.insert(0, str(ENTERPRISE))

from threat_model_layout import render_security_projection_svg


def _poster() -> dict:
    return json.loads((ROOT / "contracts/generated/documentation-enterprise/security-poster.json").read_text(encoding="utf-8"))


def test_explicit_control_asset_labels_brand_icons_shields_and_single_legend_contract():
    poster = _poster()
    svg = render_security_projection_svg(poster, variant="overview", layout="wide")
    browser = next(row for row in poster["nodes"] if row["id"] == "browser")
    expected = f'{len(browser.get("controls") or [])} controls · {len(browser.get("assets") or [])} assets'
    assert expected in svg
    assert not re.search(r"· C\d+ · A\d+", svg)
    assert svg.count('class="brand-icon" href="data:image/svg+xml;base64,') == len(poster["nodes"])
    assert 'class="shield-mark"' in svg
    assert '<g class="legend"' not in svg
    assert '<metadata data-threat-legend="svg"' in svg


def test_evidence_projection_zone_is_explicit_without_becoming_a_canonical_boundary():
    architecture = (ROOT / "docs/generated/enterprise/threat-model/architecture.md").read_text(encoding="utf-8")
    evidence_zone = (ROOT / "docs/generated/enterprise/threat-model/evidence-zone.md").read_text(encoding="utf-8")
    model = json.loads((ROOT / "contracts/security/threat-model.json").read_text(encoding="utf-8"))
    assert "evidence-zone" not in {str(row.get("id")) for row in model.get("boundaries") or []}
    assert "[Promoted evidence → documentation](evidence-zone.md)" in architecture
    assert "# Promoted evidence → documentation" in evidence_zone
    assert "not promoted into a new canonical threat boundary" in evidence_zone
    for heading in ("## Assets", "## Actors & components", "## Controls", "## Data flows", "## Evidence lineage", "## Guardrails", "## Review status"):
        assert heading in evidence_zone


def test_interactive_threat_objects_defer_resource_until_responsive_selection():
    poster_source = (
        ROOT
        / "scripts/docs/enterprise/threat_model_poster.py"
    ).read_text(encoding="utf-8")

    completion_source = (
        ROOT
        / "scripts/docs/enterprise/enterprise_completion.py"
    ).read_text(encoding="utf-8")

    javascript = (
        ROOT
        / "docs/javascripts/threat-model-poster.js"
    ).read_text(encoding="utf-8")

    assert (
        'data-pl-base-src="../../assets/enterprise/'
        'threat-model.svg"'
        in poster_source
    )

    assert (
        'data="../../assets/enterprise/threat-model.svg"'
        not in poster_source
    )

    assert (
        'data-pl-base-src="{asset_prefix}/'
        'security-atlas.svg"'
        in completion_source
    )

    assert (
        'data="{asset_prefix}/security-atlas.svg"'
        not in completion_source
    )

    assert "object.dataset.plBaseSrc" in javascript
    assert "responsiveSrc(" in javascript
    assert "object.setAttribute('data', next)" in javascript
