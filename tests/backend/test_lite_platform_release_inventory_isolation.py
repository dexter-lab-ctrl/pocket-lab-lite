from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "scripts/docs/lite/run_platform_catalogs.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location("platform_release_inventory_isolation", RUNNER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_release_inventory_ignores_local_pocketlab_dev_manifests() -> None:
    local_root = ROOT / ".pocketlab-dev" / "tmp" / "docs-release-inventory-isolation"
    manifest = local_root / "pocketlab-lite-release.json"
    local_root.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        json.dumps(
            {
                "release_tag": "lite-2099.12.31.99",
                "source_commit": "a" * 40,
                "validation_evidence": [str(local_root / "evidence.json")],
            }
        ),
        encoding="utf-8",
    )

    try:
        platform = _load_runner()
        outputs = platform.release_outputs()
        rendered = "\n".join(outputs.values())
        assert "lite-2099.12.31.99" not in rendered
        assert str(local_root) not in rendered
        assert platform.validate_output_safety(outputs) == []
    finally:
        shutil.rmtree(local_root, ignore_errors=True)
