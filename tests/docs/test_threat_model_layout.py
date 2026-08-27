from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENTERPRISE = ROOT / "scripts/docs/enterprise"
if str(ENTERPRISE) not in sys.path:
    sys.path.insert(0, str(ENTERPRISE))

from threat_model_layout import (
    CONTROL_OWNERS,
    ENGINE_VERSION,
    compile_layout,
    render_security_projection_svg,
)


def _poster() -> dict:
    return json.loads((ROOT / "contracts/generated/documentation-enterprise/security-poster.json").read_text(encoding="utf-8"))


def test_layout_engine_has_bounded_owners_for_every_security_control():
    poster = _poster()

    poster_control_ids = {row["id"] for row in poster["controls"]}

    assert poster_control_ids == set(CONTROL_OWNERS)

    for layout in ("wide", "stacked"):
        compiled = compile_layout(poster, layout=layout)

        assert set(compiled["control_boxes"]) == poster_control_ids

        ordered = sorted(compiled["control_boxes"].items())
        for index, (_a_id, a) in enumerate(ordered):
            for _b_id, b in ordered[index + 1 :]:
                assert not a.intersects(b, gap=3)


def test_single_layout_engine_covers_every_canonical_presentation_node_without_overlap():
    poster = _poster()
    for layout in ("wide", "stacked"):
        compiled = compile_layout(poster, layout=layout)
        boxes = compiled["boxes"]
        assert len(boxes) == len(poster["nodes"])
        assert set(boxes) == {row["id"] for row in poster["nodes"]}
        ordered = sorted(boxes.items())
        for index, (_a_id, a) in enumerate(ordered):
            for _b_id, b in ordered[index + 1 :]:
                assert not a.intersects(b, gap=6)
        for zone_id, zone in compiled["zones"].items():
            assert zone.w > 0 and zone.h > 0, zone_id
        zone_items = sorted(compiled["zones"].items())
        for index, (_a_id, a) in enumerate(zone_items):
            for _b_id, b in zone_items[index + 1 :]:
                assert not a.intersects(b, gap=4)


def test_one_renderer_owns_overview_architecture_and_catalog_variants():
    poster = _poster()
    for layout in ("wide", "stacked"):
        for variant in ("overview", "architecture", "catalog"):
            svg = render_security_projection_svg(poster, variant=variant, layout=layout)
            assert f'data-layout-engine="{ENGINE_VERSION}"' in svg
            assert f'data-layout="{layout}"' in svg
            assert f'data-variant="{variant}"' in svg
            assert 'data-layout-bounds=' in svg
            assert 'data-reset-target="true"' in svg
            assert 'data-threat-legend="svg"' in svg
            assert 'Modeled allowed/control flow' in svg
            assert 'Selected modeled attack path' in svg
            assert 'Security control' in svg
            assert 'Trust zone' in svg
            assert 'Saved relationship motion only' in svg
            assert 'NOT LIVE MONITORING' in svg


def test_layout_renderer_rejects_unknown_nodes_and_live_or_synthetic_semantics():
    poster = _poster()
    bad = json.loads(json.dumps(poster))
    bad["nodes"].append({"id": "future-unplaced-node"})
    try:
        compile_layout(bad, layout="wide")
    except ValueError as exc:
        assert "node-set drift" in str(exc)
    else:
        raise AssertionError("unknown presentation node must fail closed")

    for token in ("risk_score", "security_score", "last_seen", "live_feed", "active_attack", "websocket", "eventsource"):
        assert token not in render_security_projection_svg(poster).lower()

    unsafe = json.loads(json.dumps(poster))
    unsafe["nodes"][0]["label"] = "/home/alice/.pocketlab-lite-agent.env"
    try:
        render_security_projection_svg(unsafe)
    except ValueError as exc:
        assert "private-path" in str(exc)
    else:
        raise AssertionError("private-path projection must fail closed")


def test_enterprise_completion_emits_all_threat_diagrams_from_the_same_engine():
    source = (ROOT / "scripts/docs/enterprise/enterprise_completion.py").read_text(encoding="utf-8")
    assert 'render_security_poster_svg(poster, variant="overview", layout="wide")' in source
    assert 'render_security_poster_svg(poster, variant="overview", layout="stacked")' in source
    assert 'render_security_poster_svg(poster, variant="architecture", layout="wide")' in source
    assert 'render_security_poster_svg(poster, variant="architecture", layout="stacked")' in source
    assert 'render_security_poster_svg(poster, variant="catalog", layout="wide")' in source
    assert 'render_security_poster_svg(poster, variant="catalog", layout="stacked")' in source
    assert 'render_threat_svg(threat)' not in source
    assert 'render_security_atlas_svg(atlas)' not in source
