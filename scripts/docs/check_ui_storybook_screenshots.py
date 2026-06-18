#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
METADATA_PATH = ROOT / "src/stories/tier9UiScreens.json"
SCREENSHOT_MANIFEST_PATH = ROOT / "docs/product/generated/ui-screenshot-manifest.json"
GENERATED_MD_PATH = ROOT / "docs/product/generated/ui-screen-reference.generated.md"
SCREENSHOT_DIR = ROOT / "docs/product/generated/ui-screenshots"


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    errors: list[str] = []
    if not METADATA_PATH.exists():
        errors.append(f"missing {rel(METADATA_PATH)}")
    if not SCREENSHOT_MANIFEST_PATH.exists():
        errors.append(f"missing {rel(SCREENSHOT_MANIFEST_PATH)}; run task docs:ui:screenshots")
    if not SCREENSHOT_DIR.exists():
        errors.append(f"missing {rel(SCREENSHOT_DIR)}; run task docs:ui:screenshots")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)

    metadata = load_json(METADATA_PATH)
    manifest = load_json(SCREENSHOT_MANIFEST_PATH)
    screenshots = manifest.get("screenshots", [])
    expected_pairs = {
        (screen.get("id"), story)
        for screen in metadata.get("screens", [])
        for story in screen.get("storyExports", [])
    }
    actual_pairs = {(item.get("screen_id"), item.get("story_export")) for item in screenshots}

    missing_pairs = sorted(expected_pairs - actual_pairs)
    extra_pairs = sorted(actual_pairs - expected_pairs)
    if missing_pairs:
        errors.append("missing screenshot evidence for stories: " + ", ".join(f"{a}/{b}" for a, b in missing_pairs))
    if extra_pairs:
        errors.append("unexpected screenshot evidence entries: " + ", ".join(f"{a}/{b}" for a, b in extra_pairs))

    for item in screenshots:
        repo_path = item.get("repository_path")
        if not repo_path:
            errors.append(f"screenshot entry for {item.get('screen_id')}/{item.get('story_export')} missing repository_path")
            continue
        path = ROOT / repo_path
        if not path.exists():
            errors.append(f"missing screenshot file {repo_path}")
            continue
        if path.stat().st_size <= 0:
            errors.append(f"empty screenshot file {repo_path}")
        expected_hash = item.get("sha256")
        if expected_hash and sha256_file(path) != expected_hash:
            errors.append(f"sha256 mismatch for {repo_path}; rerun task docs:ui:screenshots")

    if GENERATED_MD_PATH.exists():
        generated_doc = GENERATED_MD_PATH.read_text(encoding="utf-8")
        for item in screenshots:
            docs_path = item.get("docs_relative_path")
            if docs_path and docs_path not in generated_doc:
                errors.append(f"generated UI docs do not reference screenshot {docs_path}; run task docs:ui after screenshots")
    else:
        errors.append(f"missing {rel(GENERATED_MD_PATH)}; run task docs:ui")

    if manifest.get("capture_mode") != "storybook-static iframe screenshot with deterministic FastAPI mocks":
        errors.append("screenshot manifest capture_mode does not document Storybook deterministic mock capture")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)

    print(
        "Storybook screenshot evidence UI screenshot evidence check passed: "
        f"screens={manifest.get('screen_count')} screenshots={manifest.get('screenshot_count')}"
    )


if __name__ == "__main__":
    main()
