#!/usr/bin/env python3
"""Validate Storybook UI documentation and screenshot evidence freshness.

This checker treats screenshot evidence as part of the generated documentation
when docs/product/generated/ui-screenshot-manifest.json exists.

Expected generated UI docs:

    generate_ui_storybook_docs.build_markdown(...)
    + embed_ui_storybook_screenshots.inject(...)

This prevents Storybook screenshot evidence from being mistaken for manual drift.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS_SCRIPT_DIR = ROOT / "scripts/docs"

sys.path.insert(0, str(DOCS_SCRIPT_DIR))

import generate_ui_storybook_docs as gen  # noqa: E402
import embed_ui_storybook_screenshots as embedder  # noqa: E402


def fail(message: str) -> None:
    print(f"ERROR: {message}")
    raise SystemExit(1)


def read_text(path: Path) -> str:
    if not path.exists():
        fail(f"missing {gen.rel(path)}; run task docs:ui")
    return path.read_text(encoding="utf-8")


def read_json(path: Path) -> dict:
    if not path.exists():
        fail(f"missing {gen.rel(path)}; run task docs:ui")
    return json.loads(path.read_text(encoding="utf-8"))


def build_expected_generated_doc(metadata: dict, expected_manifest: dict) -> str:
    expected = gen.build_markdown(metadata, expected_manifest)

    # Storybook screenshot evidence: if screenshot evidence exists, it is part of generated docs.
    if embedder.SCREENSHOT_MANIFEST.exists():
        screenshot_manifest = embedder.load_json(embedder.SCREENSHOT_MANIFEST)
        by_screen = embedder.group_screenshots(screenshot_manifest)
        expected, injected_screen_count, image_link_count = embedder.inject(expected, by_screen)

        if injected_screen_count <= 0 or image_link_count <= 0:
            fail(
                "Storybook screenshot evidence exists but expected generated docs "
                "could not embed screenshot links"
            )

    return expected


def main() -> None:
    metadata = gen.load_metadata()
    validation_errors = gen.validate(metadata)

    if validation_errors:
        for error in validation_errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)

    expected_manifest = gen.build_manifest(metadata)
    actual_manifest = read_json(gen.MANIFEST_PATH)

    if actual_manifest != expected_manifest:
        fail("UI Storybook manifest is stale; run task docs:ui")

    generated_doc = read_text(gen.GENERATED_MD_PATH)
    expected_generated_doc = build_expected_generated_doc(metadata, expected_manifest)

    if generated_doc != expected_generated_doc:
        fail("generated UI screen reference is stale; run task docs:ui")

    primary_doc = read_text(gen.PRIMARY_MD_PATH)
    expected_primary_doc = gen.build_primary_markdown()

    if primary_doc != expected_primary_doc:
        fail("primary UI screen reference wrapper is stale; run task docs:ui")

    if generated_doc.startswith("# Pocket Lab Screen-by-Screen UI/UX Manual"):
        fail(
            "Generated UI include must not start with an H1 because "
            "docs/product/ui-screen-reference.md already owns the page title."
        )

    screenshot_manifest_exists = embedder.SCREENSHOT_MANIFEST.exists()
    screenshot_links = generated_doc.count("generated/ui-screenshots/")

    if screenshot_manifest_exists and screenshot_links <= 0:
        fail(
            "Storybook screenshot evidence screenshot manifest exists, but generated UI docs contain no screenshot links"
        )

    screens = metadata.get("screens", [])
    required = [screen for screen in screens if screen.get("status") == "required"]
    stories = sum(len(screen.get("storyExports", [])) for screen in screens)

    if screenshot_manifest_exists:
        screenshot_manifest = read_json(embedder.SCREENSHOT_MANIFEST)
        screenshot_count = len(screenshot_manifest.get("screenshots", []))
        print(
            "Storybook screenshot evidence UI Storybook docs check passed: "
            f"screens={len(screens)} required={len(required)} stories={stories} "
            f"screenshot_links={screenshot_links} screenshots={screenshot_count}"
        )
    else:
        print(
            "Storybook UI documentation UI Storybook docs check passed: "
            f"screens={len(screens)} required={len(required)} stories={stories}"
        )


if __name__ == "__main__":
    main()
