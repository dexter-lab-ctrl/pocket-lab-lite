#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
METADATA_PATH = ROOT / "src/stories/tier9UiScreens.json"
STORIES_PATH = ROOT / "src/stories/PocketLabTabs.stories.jsx"
GENERATED_DIR = ROOT / "docs/product/generated"
MANIFEST_PATH = GENERATED_DIR / "ui-storybook-manifest.json"
GENERATED_MD_PATH = GENERATED_DIR / "ui-screen-reference.generated.md"
UI_SCREENSHOT_MANIFEST_PATH = GENERATED_DIR / "ui-screenshot-manifest.json"
PRIMARY_MD_PATH = ROOT / "docs/product/ui-screen-reference.md"
SCREENSHOT_MANIFEST_PATH = GENERATED_DIR / "ui-screenshot-manifest.json"

RETIRED_TOKENS = [
    "legacy" + "_intent",
    "sync" + "_bash",
    "tofu" + "_deploy",
    "/api/action/" + "update",
    "dashboard" + "_api",
    "BaseHTTP" + "RequestHandler",
]


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_metadata() -> dict[str, Any]:
    if not METADATA_PATH.exists():
        raise SystemExit(f"ERROR: missing {rel(METADATA_PATH)}")
    return json.loads(METADATA_PATH.read_text(encoding="utf-8"))


def exported_stories() -> set[str]:
    if not STORIES_PATH.exists():
        raise SystemExit(f"ERROR: missing {rel(STORIES_PATH)}")
    text = STORIES_PATH.read_text(encoding="utf-8")
    return set(re.findall(r"export const ([A-Za-z0-9_]+)\s*=", text))


def validate(metadata: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    story_exports = exported_stories()
    required_states = set(metadata.get("requiredStates", []))
    documented_states: set[str] = set()

    screens = metadata.get("screens", [])
    if not screens:
        errors.append("no screens defined in Storybook UI documentation UI metadata")

    for screen in screens:
        missing = [name for name in screen.get("storyExports", []) if name not in story_exports]
        if missing:
            errors.append(f"{screen.get('id')}: missing Storybook exports: {', '.join(missing)}")
        states = set(screen.get("states", {}).keys())
        documented_states.update(states)
        if screen.get("status") == "required":
            for state in ["normal", "simple_mode", "professional_mode", "button_action_behavior", "operation_status_behavior", "backend_sync_behavior"]:
                if state not in states:
                    errors.append(f"{screen.get('id')}: required screen missing state {state}")
            if not screen.get("operations"):
                errors.append(f"{screen.get('id')}: missing typed operation mapping")
            if not screen.get("backendEndpoints"):
                errors.append(f"{screen.get('id')}: missing backend endpoint mapping")

    missing_global_states = sorted(required_states - documented_states)
    # Enterprise behavior is only applicable to settings/governance, so it is global rather than required on every screen.
    if missing_global_states:
        errors.append("metadata does not document required UI states: " + ", ".join(missing_global_states))

    simple_labels = metadata.get("simpleModeLabels", {})
    expected_simple_labels = {
        "GitOps": "Keep My Environment Updated",
        "Blueprint Catalog": "Apps & Services",
        "Drift Center": "Health & Issues",
        "Fleet Scaling": "My Devices",
        "Identity & Vault": "Passwords & Access",
        "Security Posture": "Safety Center",
        "NOC Telemetry": "System Status",
        "Deploy Blueprint": "Install",
        "Version": "Release",
        "Drift Detected": "Something Changed",
        "Join Fleet": "Add Device",
        "Desired State": "What Should Be Installed",
        "Rotate Secret": "Change Password",
    }
    for source, expected in expected_simple_labels.items():
        if simple_labels.get(source) != expected:
            errors.append(f"Simple Mode label mismatch for {source}: expected {expected!r}")

    forbidden_sources = [METADATA_PATH, STORIES_PATH]
    for path in forbidden_sources:
        text = path.read_text(encoding="utf-8")
        for token in RETIRED_TOKENS:
            if token in text:
                errors.append(f"retired architecture token {token!r} found in {rel(path)}")

    return errors


def build_manifest(metadata: dict[str, Any]) -> dict[str, Any]:
    stories_text = STORIES_PATH.read_text(encoding="utf-8") if STORIES_PATH.exists() else ""
    metadata_text = json.dumps(metadata, indent=2, sort_keys=True)
    screens = metadata.get("screens", [])
    required_screens = [screen for screen in screens if screen.get("status") == "required"]
    additional_screens = [screen for screen in screens if screen.get("status") != "required"]
    story_export_count = sum(len(screen.get("storyExports", [])) for screen in screens)
    documented_states = sorted({state for screen in screens for state in screen.get("states", {}).keys()})
    return {
        "capability": metadata.get("capability", metadata.get("tier", "Storybook UI documentation and evidence")),
        "source_files": [rel(METADATA_PATH), rel(STORIES_PATH)],
        "generated_files": [rel(MANIFEST_PATH), rel(GENERATED_MD_PATH), rel(PRIMARY_MD_PATH)],
        "screen_count": len(screens),
        "required_screen_count": len(required_screens),
        "additional_screen_count": len(additional_screens),
        "story_export_count": story_export_count,
        "documented_states": documented_states,
        "required_screens": [screen.get("id") for screen in required_screens],
        "additional_screens": [screen.get("id") for screen in additional_screens],
        "source_fingerprint": sha256_text(metadata_text + "\n" + stories_text),
        "architecture_guardrails": metadata.get("architectureGuardrails", []),
    }



def load_screenshot_manifest() -> dict[str, Any]:
    if not SCREENSHOT_MANIFEST_PATH.exists():
        return {"screenshots": []}
    return json.loads(SCREENSHOT_MANIFEST_PATH.read_text(encoding="utf-8"))


def screenshots_for_screen(screenshot_manifest: dict[str, Any], screen_id: str | None) -> list[dict[str, Any]]:
    return [
        item for item in screenshot_manifest.get("screenshots", [])
        if item.get("screen_id") == screen_id
    ]


def screenshot_markdown_rows(items: list[dict[str, Any]]) -> list[str]:
    rows: list[str] = []
    for item in items:
        story = item.get("story_export", "Story")
        path = item.get("docs_relative_path", "")
        sha = str(item.get("sha256", ""))[:12]
        if not path:
            continue
        rows.append(f"![{story} screenshot]({path})")
        rows.append("")
        rows.append(f"*Story:* `{story}` · *Evidence SHA-256:* `{sha}`")
        rows.append("")
    return rows

def md_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(cell).replace("\n", "<br>") for cell in row) + " |")
    return "\n".join(lines)


def build_markdown(metadata: dict[str, Any], manifest: dict[str, Any]) -> str:
    screenshot_manifest = load_screenshot_manifest()
    lines: list[str] = []
    lines.append("<!-- GENERATED BY scripts/docs/generate_ui_storybook_docs.py. Do not edit this generated section manually. -->")
    lines.append("")
    lines.append("This Storybook UI reference is generated from UI evidence metadata and the `PocketLabTabs.stories.jsx` story file. It documents screen behavior with deterministic FastAPI mock responses, not manually captured stale screenshots.")
    lines.append("")
    lines.append("## Generation manifest")
    lines.append("")
    lines.append(md_table(["Field", "Value"], [
        ["Capability", manifest["capability"]],
        ["Required screens", str(manifest["required_screen_count"])],
        ["Additional screens", str(manifest["additional_screen_count"])],
        ["Story exports", str(manifest["story_export_count"])],
        ["Source fingerprint", manifest["source_fingerprint"][:16]],
    ]))
    lines.append("")
    lines.append("## Runtime and architecture guardrails")
    lines.append("")
    for item in metadata.get("architectureGuardrails", []):
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Simple Mode terminology covered")
    lines.append("")
    simple_rows = [[k, v] for k, v in metadata.get("simpleModeLabels", {}).items()]
    lines.append(md_table(["Professional wording", "Simple wording"], simple_rows))
    lines.append("")
    lines.append("## Storybook coverage summary")
    lines.append("")
    rows = []
    for screen in metadata.get("screens", []):
        rows.append([
            screen.get("professionalLabel", ""),
            screen.get("simpleLabel", ""),
            screen.get("component", ""),
            screen.get("status", ""),
            ", ".join(screen.get("storyExports", [])),
        ])
    lines.append(md_table(["Screen", "Simple label", "Component", "Coverage", "Story exports"], rows))
    lines.append("")
    lines.append("## Required UI state coverage")
    lines.append("")
    state_rows = []
    for state in metadata.get("requiredStates", []):
        screens = [screen.get("professionalLabel") for screen in metadata.get("screens", []) if state in screen.get("states", {})]
        state_rows.append([state, ", ".join(screens) if screens else "Not documented"])
    lines.append(md_table(["Required state", "Covered by screens"], state_rows))
    lines.append("")
    lines.append("## Screen-by-screen reference")
    lines.append("")
    for screen in metadata.get("screens", []):
        lines.append(f"### {screen.get('professionalLabel')}")
        lines.append("")
        lines.append(f"**Simple Mode label:** {screen.get('simpleLabel')}  ")
        lines.append(f"**Component:** `{screen.get('component')}`  ")
        lines.append(f"**Storybook title:** `{screen.get('storybookTitle')}`  ")
        lines.append(f"**Purpose:** {screen.get('purpose')}")
        lines.append("")
        lines.append("#### Stories")
        lines.append("")
        for story in screen.get("storyExports", []):
            lines.append(f"- `{story}`")
        lines.append("")
        screenshot_items = screenshots_for_screen(screenshot_manifest, screen.get("id"))
        if screenshot_items:
            lines.append("#### Screenshot evidence")
            lines.append("")
            lines.append(
                "These images are captured automatically from `storybook-static` with deterministic FastAPI mocks. "
                "They are release evidence for visual UI behavior, not manually maintained screenshots."
            )
            lines.append("")
            lines.extend(screenshot_markdown_rows(screenshot_items))
        lines.append("#### UI states and behavior")
        lines.append("")
        state_rows = [[state, detail] for state, detail in screen.get("states", {}).items()]
        lines.append(md_table(["State / behavior", "Documented behavior"], state_rows))
        lines.append("")
        lines.append("#### Actions and backend synchronization")
        lines.append("")
        lines.append(md_table(["Area", "Values"], [
            ["Buttons / actions", ", ".join(screen.get("actions", []))],
            ["Typed operations", ", ".join(f"`{op}`" for op in screen.get("operations", []))],
            ["Backend endpoints", ", ".join(f"`{endpoint}`" for endpoint in screen.get("backendEndpoints", []))],
        ]))
        lines.append("")
    lines.append("## Validation commands")
    lines.append("")
    lines.append("```bash")
    lines.append("task docs:ui")
    lines.append("task docs:ui:check")
    lines.append("task docs:ui:screenshots")
    lines.append("task docs:ui:screenshots:check")
    lines.append("task storybook:build")
    lines.append("mkdocs build --strict")
    lines.append("```")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_primary_markdown() -> str:
    return """# Pocket Lab Screen-by-Screen UI/UX Manual\n\nThis page is generated from Storybook UI documentation Storybook UI documentation metadata. Update `src/stories/tier9UiScreens.json` and `src/stories/PocketLabTabs.stories.jsx`, then run `task docs:ui`.\n\n--8<-- \"docs/product/generated/ui-screen-reference.generated.md\"\n"""


def write_outputs(metadata: dict[str, Any], manifest: dict[str, Any]) -> None:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    generated_markdown = inject_tier9a_screenshot_evidence(build_markdown(metadata, manifest))
    duplicate_h1 = "# Pocket Lab Screen-by-Screen UI/UX Manual\\n\\n"
    if generated_markdown.startswith(duplicate_h1):
        generated_markdown = generated_markdown[len(duplicate_h1):]
    GENERATED_MD_PATH.write_text(generated_markdown, encoding="utf-8")
    embed_tier9a_screenshot_evidence()
    PRIMARY_MD_PATH.write_text(build_primary_markdown(), encoding="utf-8")



def inject_tier9a_screenshot_evidence(markdown: str) -> str:
    """Inject Storybook screenshot evidence screenshot images into the generated UI manual.

    The screenshot manifest is generated by scripts/docs/capture_ui_storybook_screenshots.mjs.
    This function keeps Storybook UI documentation usable without screenshots, but embeds them when evidence exists.
    """
    screenshot_manifest_path = Path("docs/product/generated/ui-screenshot-manifest.json")
    if not screenshot_manifest_path.exists():
        return markdown

    screenshot_manifest = json.loads(screenshot_manifest_path.read_text(encoding="utf-8"))
    screenshots = screenshot_manifest.get("screenshots", [])
    if not screenshots:
        return markdown

    by_screen = {}
    for shot in screenshots:
        screen_id = shot.get("screen_id")
        if not screen_id:
            continue
        by_screen.setdefault(screen_id, []).append(shot)

    if not by_screen:
        return markdown

    lines = markdown.splitlines()
    output = []
    current_screen_id = None
    inserted_for_screen = set()

    for index, line in enumerate(lines):
        output.append(line)

        # Capture the generated screen id from the metadata line.
        # Existing generated docs include the screen title first, then Simple label/component/story info.
        if line.startswith("## ") and not line.startswith("## Screen-by-screen"):
            current_screen_id = None

        # Infer screen id from the Storybook section title or component/title block.
        stripped = line.strip()
        title_to_id = {
            "## App Store / Blueprint Catalog": "app-store",
            "## GitOps": "gitops",
            "## Fleet Scaling": "fleet-scaling",
            "## Identity & Vault": "identity-vault",
            "## Release Workflow / Release": "release-workflow",
            "## Drift Center": "drift-center",
            "## Security Posture": "security-posture",
            "## NOC Telemetry": "noc-telemetry",
            "## Disaster Recovery": "disaster-recovery",
            "## Policy Guardrails": "policy-guardrails",
            "## Settings / Enterprise Governance": "settings-governance",
        }
        if stripped in title_to_id:
            current_screen_id = title_to_id[stripped]

        if (
            stripped == "These images are captured automatically from storybook-static with deterministic FastAPI mocks. They are release evidence for visual UI behavior, not manually maintained screenshots."
            and current_screen_id
            and current_screen_id in by_screen
            and current_screen_id not in inserted_for_screen
        ):
            output.append("")
            for shot in by_screen[current_screen_id]:
                screenshot = shot.get("screenshot") or shot.get("repository_path", "").replace("docs/product/", "")
                story_export = shot.get("story_export", "Story")
                sha = str(shot.get("sha256", ""))[:12]
                story_id = shot.get("story_id", "")

                if not screenshot:
                    continue

                output.extend([
                    f"![{current_screen_id} — {story_export}]({screenshot})",
                    "",
                    f"- Story: `{story_export}`",
                    f"- Storybook ID: `{story_id}`",
                    f"- Evidence SHA-256: `{sha}`",
                    "",
                ])

            inserted_for_screen.add(current_screen_id)

    return "\n".join(output).rstrip() + "\n"


def embed_tier9a_screenshot_evidence() -> None:
    """Embed Storybook screenshot evidence into the generated UI manual.

    This runs after the normal Storybook UI markdown generation so the UI manual remains
    usable without screenshots, but automatically includes visual evidence when
    docs/product/generated/ui-screenshot-manifest.json exists.
    """
    screenshot_manifest_path = Path("docs/product/generated/ui-screenshot-manifest.json")
    generated_doc_path = Path("docs/product/generated/ui-screen-reference.generated.md")

    if not screenshot_manifest_path.exists() or not generated_doc_path.exists():
        return

    data = json.loads(screenshot_manifest_path.read_text(encoding="utf-8"))
    screenshots = data.get("screenshots", [])
    if not screenshots:
        return

    markdown = generated_doc_path.read_text(encoding="utf-8")

    # Avoid duplicate image injection on repeated task docs:ui runs.
    if "generated/ui-screenshots/" in markdown:
        return

    by_title = {}
    for item in screenshots:
        title = item.get("screen_title") or item.get("screen_id")
        if not title:
            continue
        by_title.setdefault(title, []).append(item)

    if not by_title:
        return

    evidence_sentence = (
        "These images are captured automatically from storybook-static with deterministic FastAPI mocks. "
        "They are release evidence for visual UI behavior, not manually maintained screenshots."
    )

    output = []
    current_title = None

    for line in markdown.splitlines():
        output.append(line)

        if line.startswith("## "):
            possible_title = line.removeprefix("## ").strip()
            current_title = possible_title if possible_title in by_title else None

        if line.strip() == evidence_sentence and current_title in by_title:
            output.append("")

            for shot in by_title[current_title]:
                screenshot = shot.get("screenshot") or shot.get("repository_path", "").replace("docs/product/", "")
                story_export = shot.get("story_export", "Story")
                story_id = shot.get("story_id", "")
                sha = str(shot.get("sha256", ""))[:12]

                if not screenshot:
                    continue

                output.extend(
                    [
                        f"![{current_title} — {story_export}]({screenshot})",
                        "",
                        f"- Story: `{story_export}`",
                        f"- Storybook ID: `{story_id}`",
                        f"- Evidence SHA-256: `{sha}`",
                        "",
                    ]
                )

    generated_doc_path.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")



def main() -> None:
    metadata = load_metadata()
    errors = validate(metadata)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        raise SystemExit(1)
    manifest = build_manifest(metadata)
    write_outputs(metadata, manifest)
    print(f"Wrote {rel(MANIFEST_PATH)}")
    print(f"Wrote {rel(GENERATED_MD_PATH)}")
    print(f"Updated {rel(PRIMARY_MD_PATH)}")
    print(f"Storybook UI documentation: screens={manifest['screen_count']} stories={manifest['story_export_count']}")


if __name__ == "__main__":
    main()
