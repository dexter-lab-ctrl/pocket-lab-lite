from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts/docs/parity/render_local_runtime_comparison.py"

spec = importlib.util.spec_from_file_location("local_runtime_report", MODULE_PATH)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def payload():
    return {
        "release_tag": "lite-2026.08.06.2",
        "source_commit": "a" * 40,
        "status": "partial",
        "domains": [
            {
                "id": "home",
                "label": "Home",
                "implementation_status": "implemented",
                "live_api_coverage": "observed",
                "live_ui_coverage": "observed",
                "live_termux_coverage": "observed",
                "runtime_parity": "capture-corrupted",
                "status": "partial",
                "comparisons": [
                    {
                        "id": "home-overall-presentation",
                        "result": "capture-corrupted",
                        "project": "live-desktop",
                        "required": True,
                        "implementation_status": "implemented",
                        "explanation": "frontend evidence was over-redacted",
                    }
                ],
            }
        ],
    }


def test_local_report_is_clearly_unpromoted():
    rendered = module.render_markdown(payload())
    assert "Local, sanitized, unpromoted evidence" in rendered
    assert "capture-corrupted" in rendered
    assert "runtime-verification-baseline.json" in rendered


def test_local_report_contains_no_raw_observation_values():
    data = payload()
    data["domains"][0]["comparisons"][0]["backend"] = {"secret": "raw"}
    rendered = module.render_markdown(data)
    assert '"secret"' not in rendered
    assert "raw" not in rendered
