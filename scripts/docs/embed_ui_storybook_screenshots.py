#!/usr/bin/env python3
"""Enterprise-grade Storybook screenshot evidence embedder for MkDocs."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(".")
GENERATED_DOC = ROOT / "docs/product/generated/ui-screen-reference.generated.md"
SCREENSHOT_MANIFEST = ROOT / "docs/product/generated/ui-screenshot-manifest.json"
START_MARKER = "<!-- tier9a-screenshot-evidence:start -->"
END_MARKER = "<!-- tier9a-screenshot-evidence:end -->"

HEADING_TO_SCREEN_ID = {
    "App Store / Blueprint Catalog": "app-store",
    "GitOps": "gitops",
    "Fleet Scaling": "fleet-scaling",
    "Identity & Vault": "identity-vault",
    "Release Workflow / Release": "release-workflow",
    "Drift Center": "drift-center",
    "Security Posture": "security-posture",
    "NOC Telemetry": "noc-telemetry",
    "Disaster Recovery": "disaster-recovery",
    "Policy Guardrails": "policy-guardrails",
    "Settings / Enterprise Governance": "settings-governance",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_manifest_path(value: str) -> str:
    """Normalize a screenshot path from the manifest to repo-relative form."""
    value = value.replace("\\", "/")

    if value.startswith("/product/"):
        value = value.removeprefix("/product/")

    if value.startswith("product/"):
        value = value.removeprefix("product/")

    if value.startswith("docs/product/"):
        value = value.removeprefix("docs/product/")

    return value


def filesystem_image_path(value: str) -> Path:
    """Return the real repo filesystem path for a manifest screenshot path."""
    normalized = normalize_manifest_path(value)

    if normalized.startswith("generated/ui-screenshots/"):
        return ROOT / "docs/product" / normalized

    if normalized.startswith("ui-screenshots/"):
        return ROOT / "docs/product/generated" / normalized

    return ROOT / normalized


def mkdocs_image_path(value: str) -> str:
    """Return a GitHub Pages-safe image URL for UI screenshot markdown."""
    normalized = str(value).replace("\\", "/").lstrip("/")

    repo_prefix = "docs/product/generated/ui-screenshots/"
    generated_prefix = "generated/ui-screenshots/"
    screenshot_prefix = "ui-screenshots/"

    if normalized.startswith(repo_prefix):
        filename = normalized[len(repo_prefix):]
        return "../generated/ui-screenshots/" + filename

    if normalized.startswith(generated_prefix):
        filename = normalized[len(generated_prefix):]
        return "../generated/ui-screenshots/" + filename

    if normalized.startswith(screenshot_prefix):
        return "../generated/" + normalized

    return normalized
def screenshot_path_value(shot: dict[str, Any]) -> str:
    return str(
        shot.get("screenshot")
        or shot.get("docs_relative_path")
        or shot.get("repository_path")
        or ""
    )


def strip_existing_blocks(markdown: str) -> str:
    pattern = re.compile(
        re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER) + r"\n?",
        flags=re.DOTALL,
    )
    return pattern.sub("", markdown)


def group_screenshots(manifest: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    by_screen: dict[str, list[dict[str, Any]]] = {}

    for shot in manifest.get("screenshots", []):
        screen_id = shot.get("screen_id")
        if not screen_id:
            continue
        by_screen.setdefault(screen_id, []).append(shot)

    for shots in by_screen.values():
        shots.sort(key=lambda item: str(item.get("story_export", "")))

    return by_screen


def validate_manifest(manifest: dict[str, Any], by_screen: dict[str, list[dict[str, Any]]]) -> list[str]:
    errors: list[str] = []

    capture_mode = str(manifest.get("capture_mode", "")).lower()
    for token in ["storybook", "deterministic", "mock"]:
        if token not in capture_mode:
            errors.append(f"capture_mode must document {token!r}: {manifest.get('capture_mode')!r}")

    if not by_screen:
        errors.append("manifest has no screenshot evidence grouped by screen_id")

    for screen_id, shots in by_screen.items():
        for shot in shots:
            raw = screenshot_path_value(shot)
            if not raw:
                errors.append(f"{screen_id}/{shot.get('story_export')}: missing screenshot path")
                continue

            image_path = filesystem_image_path(raw)

            if not image_path.exists():
                errors.append(
                    f"{screen_id}/{shot.get('story_export')}: missing image file {image_path.as_posix()}"
                )
            elif image_path.stat().st_size <= 0:
                errors.append(
                    f"{screen_id}/{shot.get('story_export')}: empty image file {image_path.as_posix()}"
                )

    return errors


def image_block(screen_heading: str, shots: list[dict[str, Any]]) -> list[str]:
    lines = [
        "",
        START_MARKER,
        "",
        "The following screenshots are generated from `storybook-static` iframe stories with deterministic FastAPI mock data. They are visual release evidence for this screen.",
        "",
    ]

    for shot in shots:
        raw = screenshot_path_value(shot)
        screenshot = mkdocs_image_path(raw)
        story_export = str(shot.get("story_export", "Story"))
        story_id = str(shot.get("story_id", ""))
        sha = str(shot.get("sha256", ""))[:12]

        lines.extend(
            [
                f"![{screen_heading} — {story_export}]({screenshot})",
                "",
                f"- Story: `{story_export}`",
                f"- Storybook ID: `{story_id}`",
                f"- Evidence SHA-256: `{sha}`",
                "",
            ]
        )

    lines.extend([END_MARKER, ""])
    return lines



def html_screenshot_line(line: str) -> str:
    """Convert generated screenshot Markdown image links into raw HTML.

    MkDocs strict mode validates Markdown image links as documentation targets.
    The UI screenshot files are static assets copied into site/product/generated,
    so raw HTML avoids false broken-link warnings while preserving the browser path.
    """
    match = re.match(
        r'^!\[(?P<alt>[^\]]*)\]\((?P<src>\.\./generated/ui-screenshots/[^)]+)\)$',
        line,
    )
    if not match:
        return line

    alt = html.escape(match.group("alt"), quote=True)
    src = html.escape(match.group("src"), quote=True)
    return f'<img src="{src}" alt="{alt}" loading="lazy" />'

def inject(markdown: str, by_screen: dict[str, list[dict[str, Any]]]) -> tuple[str, int, int]:
    markdown = strip_existing_blocks(markdown)
    lines = markdown.splitlines()

    output: list[str] = []
    current_heading: str | None = None
    current_screen_id: str | None = None
    pending_injection: tuple[str, list[dict[str, Any]]] | None = None
    injected_screens: set[str] = set()

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        heading_text = None
        if line.startswith("### "):
            heading_text = line.removeprefix("### ").strip()
        elif line.startswith("## "):
            heading_text = line.removeprefix("## ").strip()

        if heading_text in HEADING_TO_SCREEN_ID:
            current_heading = heading_text
            current_screen_id = HEADING_TO_SCREEN_ID[heading_text]

        if stripped == "#### Screenshot evidence" and current_heading and current_screen_id in by_screen:
            output.append(line)
            pending_injection = (current_heading, by_screen[current_screen_id])
            i += 1
            continue

        if pending_injection and stripped.startswith("#### "):
            heading, shots = pending_injection
            screen_id = HEADING_TO_SCREEN_ID[heading]
            output.extend(image_block(heading, shots))
            injected_screens.add(screen_id)
            pending_injection = None
            output.append(line)
            i += 1
            continue

        output.append(line)
        i += 1

    if pending_injection:
        heading, shots = pending_injection
        screen_id = HEADING_TO_SCREEN_ID[heading]
        output.extend(image_block(heading, shots))
        injected_screens.add(screen_id)

    output = [html_screenshot_line(line) for line in output]

    image_links = sum(1 for line in output if "ui-screenshots/" in line and "<img " in line)
    return "\n".join(output).rstrip() + "\n", len(injected_screens), image_links


def main() -> None:
    if not GENERATED_DOC.exists():
        raise SystemExit(f"ERROR: missing {GENERATED_DOC}; run task docs:ui first")
    if not SCREENSHOT_MANIFEST.exists():
        raise SystemExit(f"ERROR: missing {SCREENSHOT_MANIFEST}; run task docs:ui:screenshots first")

    manifest = load_json(SCREENSHOT_MANIFEST)
    by_screen = group_screenshots(manifest)

    errors = validate_manifest(manifest, by_screen)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)

    markdown = GENERATED_DOC.read_text(encoding="utf-8")
    updated, injected_screen_count, image_link_count = inject(markdown, by_screen)

    if injected_screen_count == 0 or image_link_count == 0:
        print("ERROR: no screenshot image links were injected")
        print("Manifest screen_ids: " + ", ".join(sorted(by_screen)))
        raise SystemExit(1)

    GENERATED_DOC.write_text(updated, encoding="utf-8")

    print(
        f"Embedded Storybook screenshot evidence: screens={injected_screen_count} "
        f"image_links={image_link_count} into {GENERATED_DOC}"
    )


if __name__ == "__main__":
    main()
