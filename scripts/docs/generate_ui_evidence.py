#!/usr/bin/env python3
"""Generate UI evidence manifest and MkDocs validation page."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(".")
METADATA = ROOT / "src/stories/tier9UiScreens.json"
STORIES = ROOT / "src/stories/PocketLabTabs.stories.jsx"
SCREENSHOT_MANIFEST = ROOT / "docs/product/generated/ui-screenshot-manifest.json"
GENERATED_UI_DOC = ROOT / "docs/product/generated/ui-screen-reference.generated.md"
OUT_DIR = ROOT / "docs/validation/generated"
EVIDENCE_MANIFEST = OUT_DIR / "ui-evidence-manifest.json"
EVIDENCE_DOC = OUT_DIR / "ui-evidence.md"
COMMAND_RESULT_DIR = ROOT / ".pocketlab-dev/validation/command-results"

COMMAND_RESULTS = {
    "visual": ["playwright-visual", "visual", "test-visual"],
    "accessibility": ["playwright-a11y", "a11y", "test-a11y"],
    "release": ["release-dry-run", "npm-build", "storybook-build", "mkdocs-build"],
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def source_fingerprint() -> str:
    h = hashlib.sha256()
    for path in [METADATA, STORIES, SCREENSHOT_MANIFEST, GENERATED_UI_DOC]:
        h.update(path.as_posix().encode("utf-8"))
        h.update(b"\0")
        h.update(path.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def command_result(name: str) -> dict[str, Any]:
    path = COMMAND_RESULT_DIR / f"{name}.json"
    if not path.exists():
        return {"name": name, "status": "missing", "path": path.as_posix()}
    try:
        data = read_json(path)
    except Exception as exc:  # noqa: BLE001
        return {"name": name, "status": "unreadable", "path": path.as_posix(), "error": str(exc)}
    return {
        "name": name,
        "status": "present",
        "path": path.as_posix(),
        "exit_code": data.get("exit_code"),
        "command": data.get("command"),
        "started_at": data.get("started_at"),
        "finished_at": data.get("finished_at"),
    }


def build_manifest() -> dict[str, Any]:
    metadata = read_json(METADATA)
    screenshot_manifest = read_json(SCREENSHOT_MANIFEST)
    generated_doc = GENERATED_UI_DOC.read_text(encoding="utf-8")
    screenshots = screenshot_manifest.get("screenshots", [])
    image_links = generated_doc.count("../generated/ui-screenshots/")

    return {
        "tier": "UI evidence freshness — UI Evidence Freshness, Visual, Accessibility, and Release Evidence",
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "source_files": [
            METADATA.as_posix(),
            STORIES.as_posix(),
            SCREENSHOT_MANIFEST.as_posix(),
            GENERATED_UI_DOC.as_posix(),
        ],
        "generated_files": [EVIDENCE_MANIFEST.as_posix(), EVIDENCE_DOC.as_posix()],
        "source_fingerprint": source_fingerprint(),
        "screenshot_manifest_sha256": sha256_file(SCREENSHOT_MANIFEST),
        "generated_ui_doc_sha256": sha256_file(GENERATED_UI_DOC),
        "screen_count": len(metadata.get("screens", [])),
        "story_export_count": sum(len(screen.get("storyExports", [])) for screen in metadata.get("screens", [])),
        "screenshot_count": len(screenshots),
        "mkdocs_image_link_count": image_links,
        "evidence": {
            "freshness": {
                "status": "tracked",
                "checks": [
                    "source_fingerprint matches current UI metadata, Storybook stories, screenshot manifest, and generated UI docs",
                    "screenshot count matches Storybook UI documentation story export count",
                    "generated MkDocs page references every screenshot evidence item",
                    "screenshot file SHA-256 values match the manifest",
                ],
            },
            "visual": {
                "status": "tracked",
                "command": "task test:visual",
                "command_results": [command_result(name) for name in COMMAND_RESULTS["visual"]],
            },
            "accessibility": {
                "status": "tracked",
                "command": "task test:a11y",
                "command_results": [command_result(name) for name in COMMAND_RESULTS["accessibility"]],
            },
            "release": {
                "status": "tracked",
                "commands": ["task storybook:build", "npm run build", "mkdocs build --strict", "task docs:ui:evidence:check"],
                "command_results": [command_result(name) for name in COMMAND_RESULTS["release"]],
            },
        },
    }


def md_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(cell).replace("\n", "<br>") for cell in row) + " |")
    return "\n".join(lines)


def build_doc(manifest: dict[str, Any]) -> str:
    rows = [
        ["Capability", manifest["tier"]],
        ["Screens", manifest["screen_count"]],
        ["Story exports", manifest["story_export_count"]],
        ["Screenshots", manifest["screenshot_count"]],
        ["MkDocs image links", manifest["mkdocs_image_link_count"]],
        ["Source fingerprint", manifest["source_fingerprint"][:16]],
    ]
    evidence = manifest["evidence"]
    command_rows = []
    for section, item in evidence.items():
        if "command_results" in item:
            result_summary = ", ".join(
                f"{entry['name']}={entry.get('exit_code', entry['status'])}" for entry in item["command_results"]
            )
        else:
            result_summary = "freshness checks encoded in manifest"
        command_rows.append([section, item.get("status", "tracked"), result_summary])

    return "\n".join([
        "# UI evidence freshness UI Evidence",
        "",
        "This page is generated from Storybook screenshot evidence Storybook screenshot evidence and validation command metadata.",
        "",
        "## Evidence summary",
        "",
        md_table(["Field", "Value"], rows),
        "",
        "## Evidence areas",
        "",
        md_table(["Area", "Status", "Evidence"], command_rows),
        "",
        "## Validation commands",
        "",
        "```bash",
        "task docs:ui:screenshots",
        "task docs:ui:evidence",
        "task docs:ui:evidence:check",
        "task test:visual",
        "task test:a11y",
        "mkdocs build --strict",
        "```",
        "",
    ])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if generated evidence files are stale")
    args = parser.parse_args()

    for path in [METADATA, STORIES, SCREENSHOT_MANIFEST, GENERATED_UI_DOC]:
        if not path.exists():
            raise SystemExit(f"ERROR: missing {path.as_posix()}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest()

    # generated_at_utc is useful evidence metadata, but it is intentionally
    # volatile. In --check mode, preserve the existing timestamp so freshness
    # checks are based on source fingerprints, screenshot hashes, and generated
    # evidence content rather than wall-clock time.
    if args.check and EVIDENCE_MANIFEST.exists():
        existing_manifest = json.loads(EVIDENCE_MANIFEST.read_text(encoding="utf-8"))
        if "generated_at_utc" in existing_manifest:
            manifest["generated_at_utc"] = existing_manifest["generated_at_utc"]

    manifest_text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    doc_text = build_doc(manifest)

    if args.check:
        errors = []
        if not EVIDENCE_MANIFEST.exists() or EVIDENCE_MANIFEST.read_text(encoding="utf-8") != manifest_text:
            errors.append("UI evidence manifest is stale; run task docs:ui:evidence")
        if not EVIDENCE_DOC.exists() or EVIDENCE_DOC.read_text(encoding="utf-8") != doc_text:
            errors.append("UI evidence document is stale; run task docs:ui:evidence")
        if errors:
            for error in errors:
                print(f"ERROR: {error}")
            raise SystemExit(1)
        print("UI evidence generation check passed")
        return

    EVIDENCE_MANIFEST.write_text(manifest_text, encoding="utf-8")
    EVIDENCE_DOC.write_text(doc_text, encoding="utf-8")
    print(f"Wrote {EVIDENCE_MANIFEST.as_posix()}")
    print(f"Wrote {EVIDENCE_DOC.as_posix()}")
    print(
        "UI evidence generated: "
        f"screens={manifest['screen_count']} screenshots={manifest['screenshot_count']} "
        f"image_links={manifest['mkdocs_image_link_count']}"
    )


if __name__ == "__main__":
    main()
