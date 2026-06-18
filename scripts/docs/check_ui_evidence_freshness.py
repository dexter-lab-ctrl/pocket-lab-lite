#!/usr/bin/env python3
"""UI evidence freshness freshness checks for UI screenshot, visual, a11y, and release evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(".")
METADATA = ROOT / "src/stories/tier9UiScreens.json"
STORIES = ROOT / "src/stories/PocketLabTabs.stories.jsx"
SCREENSHOT_MANIFEST = ROOT / "docs/product/generated/ui-screenshot-manifest.json"
GENERATED_UI_DOC = ROOT / "docs/product/generated/ui-screen-reference.generated.md"
EVIDENCE_MANIFEST = ROOT / "docs/validation/generated/ui-evidence-manifest.json"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def fail_all(errors: list[str]) -> None:
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)


def screenshot_file_path(item: dict[str, Any]) -> Path:
    raw = str(item.get("repository_path") or item.get("screenshot") or item.get("docs_relative_path") or "")
    raw = raw.replace("\\", "/")
    if raw.startswith("/product/"):
        raw = raw.removeprefix("/product/")
    if raw.startswith("product/"):
        raw = raw.removeprefix("product/")
    if raw.startswith("docs/product/"):
        return ROOT / raw
    if raw.startswith("generated/ui-screenshots/"):
        return ROOT / "docs/product" / raw
    if raw.startswith("ui-screenshots/"):
        return ROOT / "docs/product/generated" / raw
    return ROOT / raw


def source_fingerprint() -> str:
    h = hashlib.sha256()
    for path in [METADATA, STORIES, SCREENSHOT_MANIFEST, GENERATED_UI_DOC]:
        h.update(path.as_posix().encode("utf-8"))
        h.update(b"\0")
        h.update(path.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def expected_story_count(metadata: dict[str, Any]) -> int:
    return sum(len(screen.get("storyExports", [])) for screen in metadata.get("screens", []))


def main() -> None:
    errors: list[str] = []
    for path in [METADATA, STORIES, SCREENSHOT_MANIFEST, GENERATED_UI_DOC, EVIDENCE_MANIFEST]:
        if not path.exists():
            errors.append(f"missing {path.as_posix()}")
    fail_all(errors)

    metadata = read_json(METADATA)
    screenshot_manifest = read_json(SCREENSHOT_MANIFEST)
    evidence_manifest = read_json(EVIDENCE_MANIFEST)
    generated_doc = GENERATED_UI_DOC.read_text(encoding="utf-8")

    screenshots = screenshot_manifest.get("screenshots", [])
    expected_stories = expected_story_count(metadata)
    if len(screenshots) != expected_stories:
        errors.append(f"screenshot count mismatch: expected {expected_stories}, found {len(screenshots)}")

    image_links = generated_doc.count("../generated/ui-screenshots/")
    if image_links != len(screenshots):
        errors.append(f"generated UI docs image link mismatch: expected {len(screenshots)}, found {image_links}")

    for item in screenshots:
        path = screenshot_file_path(item)
        if not path.exists():
            errors.append(f"missing screenshot file {path.as_posix()}")
            continue
        if path.stat().st_size <= 0:
            errors.append(f"empty screenshot file {path.as_posix()}")
        expected_hash = item.get("sha256")
        if expected_hash and sha256_file(path) != expected_hash:
            errors.append(f"sha256 mismatch for screenshot {path.as_posix()}")

    current_source_fp = source_fingerprint()
    if evidence_manifest.get("source_fingerprint") != current_source_fp:
        errors.append("UI evidence manifest source_fingerprint is stale; run task docs:ui:evidence")

    if evidence_manifest.get("screenshot_manifest_sha256") != sha256_file(SCREENSHOT_MANIFEST):
        errors.append("UI evidence manifest screenshot_manifest_sha256 is stale; run task docs:ui:evidence")

    if evidence_manifest.get("generated_ui_doc_sha256") != sha256_file(GENERATED_UI_DOC):
        errors.append("UI evidence manifest generated_ui_doc_sha256 is stale; run task docs:ui:evidence")

    required_sections = ["freshness", "visual", "accessibility", "release"]
    evidence_sections = evidence_manifest.get("evidence", {})
    for section in required_sections:
        if section not in evidence_sections:
            errors.append(f"UI evidence manifest missing evidence section {section!r}")

    fail_all(errors)
    print(
        "UI evidence freshness check passed: "
        f"screens={len(metadata.get('screens', []))} screenshots={len(screenshots)} image_links={image_links}"
    )


if __name__ == "__main__":
    main()
