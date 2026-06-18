#!/usr/bin/env python3
"""Generate MkDocs documentation from GitHub Actions workflow files."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_DIR = ROOT / ".github" / "workflows"
OUTPUT = ROOT / "docs" / "development" / "generated" / "github-actions-workflows.md"
MARKER = "<!-- GENERATED FILE: do not edit by hand. Regenerate with `task docs:workflows`. -->"


def read_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return {}
    return data


def workflow_on(data: dict[str, Any]) -> Any:
    # PyYAML still uses YAML 1.1 booleans by default, so an unquoted `on:` key
    # can be parsed as True. Handle both forms to keep the generator robust.
    if "on" in data:
        return data["on"]
    if True in data:
        return data[True]
    return None


def fmt(value: Any) -> str:
    if value is None or value == "":
        return "—"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return value.replace("|", "\\|").replace("\n", "<br>")
    if isinstance(value, list):
        return ", ".join(fmt(item) for item in value) or "—"
    if isinstance(value, dict):
        return ", ".join(f"{fmt(k)}: {fmt(v)}" for k, v in value.items()) or "—"
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def code(value: Any) -> str:
    text = fmt(value)
    if text == "—":
        return text
    return f"`{text}`"


def md_table(headers: list[str], rows: list[list[Any]]) -> str:
    if not rows:
        rows = [["—" for _ in headers]]
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        padded = list(row) + [""] * (len(headers) - len(row))
        lines.append("| " + " | ".join(fmt(cell) for cell in padded[: len(headers)]) + " |")
    return "\n".join(lines)


def trigger_names(trigger: Any) -> list[str]:
    if isinstance(trigger, str):
        return [trigger]
    if isinstance(trigger, list):
        return [str(item) for item in trigger]
    if isinstance(trigger, dict):
        return [str(key) for key in trigger.keys()]
    return []


def render_trigger(trigger: Any) -> str:
    if isinstance(trigger, dict):
        rows = []
        for name, config in sorted(trigger.items(), key=lambda item: str(item[0])):
            rows.append([code(name), fmt(config)])
        return md_table(["Trigger", "Details"], rows)
    if isinstance(trigger, list):
        return md_table(["Trigger"], [[code(item)] for item in trigger])
    if isinstance(trigger, str):
        return md_table(["Trigger"], [[code(trigger)]])
    return md_table(["Trigger"], [["—"]])


def permissions_rows(permissions: Any) -> list[list[str]]:
    if isinstance(permissions, dict):
        return [[code(k), code(v)] for k, v in sorted(permissions.items())]
    if isinstance(permissions, str):
        return [[code(permissions), "—"]]
    return [["—", "—"]]


def classify(path: Path, data: dict[str, Any]) -> str:
    name = str(data.get("name", path.stem)).lower()
    triggers = set(trigger_names(workflow_on(data)))
    text = path.read_text(encoding="utf-8", errors="replace").lower()
    categories: list[str] = []
    if "pull_request" in triggers:
        categories.append("PR validation")
    if "deploy-pages" in text or "upload-pages-artifact" in text or "pages: write" in text:
        categories.append("docs publishing")
    if "release" in triggers or "release" in name or "gh release" in text or "dist.zip" in text:
        categories.append("release automation")
    if "schedule" in triggers:
        categories.append("maintenance automation")
    if "workflow_dispatch" in triggers and not categories:
        categories.append("manual maintenance")
    return ", ".join(dict.fromkeys(categories)) or "maintenance automation"


def release_artifacts(data: dict[str, Any]) -> list[str]:
    artifacts: set[str] = set()
    jobs = data.get("jobs", {})
    if not isinstance(jobs, dict):
        return []
    for job in jobs.values():
        if not isinstance(job, dict):
            continue
        for step in job.get("steps", []) or []:
            if not isinstance(step, dict):
                continue
            haystack = " ".join(str(step.get(k, "")) for k in ("name", "uses", "run"))
            for token in ("dist.zip", "dist.zip.sha256", "site", "github-pages"):
                if token in haystack:
                    artifacts.add(token)
            if "upload-artifact" in haystack:
                artifacts.add(str(step.get("with", {}).get("name", "GitHub Actions artifact")))
            if "upload-pages-artifact" in haystack:
                artifacts.add("GitHub Pages site artifact")
    return sorted(artifacts)


def step_summary(step: dict[str, Any]) -> str:
    name = step.get("name") or step.get("id") or step.get("uses") or "Unnamed step"
    if step.get("uses"):
        return f"{fmt(name)} — uses `{fmt(step.get('uses'))}`"
    run = str(step.get("run", "")).strip().splitlines()
    if run:
        first = run[0].strip()
        return f"{fmt(name)} — `{fmt(first)}`"
    return fmt(name)


def job_rows(data: dict[str, Any]) -> list[list[Any]]:
    jobs = data.get("jobs", {})
    if not isinstance(jobs, dict):
        return []
    rows = []
    for job_id, job in sorted(jobs.items()):
        if not isinstance(job, dict):
            rows.append([code(job_id), "—", "—", "—"])
            continue
        steps = [step_summary(step) for step in job.get("steps", []) or [] if isinstance(step, dict)]
        rows.append([
            code(job_id),
            job.get("name", "—"),
            code(job.get("runs-on", "—")),
            "<br>".join(f"{idx + 1}. {step}" for idx, step in enumerate(steps)) or "—",
        ])
    return rows


def render_workflow(path: Path) -> tuple[list[Any], str]:
    data = read_yaml(path)
    name = data.get("name", path.stem)
    trigger = workflow_on(data)
    classification = classify(path, data)
    artifacts = release_artifacts(data)
    summary_row = [name, code(path.relative_to(ROOT)), classification, fmt(trigger_names(trigger)), fmt(artifacts)]

    section = [f"## {name}", ""]
    section.append(md_table(["Field", "Value"], [
        ["File", code(path.relative_to(ROOT))],
        ["Classification", classification],
        ["Concurrency", fmt(data.get("concurrency"))],
        ["Release artifacts", fmt(artifacts)],
    ]))
    section.extend(["", "### Triggers", "", render_trigger(trigger), "", "### Permissions", "", md_table(["Permission", "Level"], permissions_rows(data.get("permissions"))), "", "### Jobs and major steps", "", md_table(["Job", "Name", "Runs on", "Major steps"], job_rows(data)), ""])
    return summary_row, "\n".join(section)


def main() -> int:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    workflows = sorted(WORKFLOW_DIR.glob("*.yml")) + sorted(WORKFLOW_DIR.glob("*.yaml"))
    summary_rows: list[list[Any]] = []
    sections: list[str] = []
    for path in workflows:
        row, section = render_workflow(path)
        summary_rows.append(row)
        sections.append(section)

    body = [
        MARKER,
        "",
        "# Generated GitHub Actions Workflows",
        "",
        "This page is generated from `.github/workflows/*.yml` and `.github/workflows/*.yaml`. It documents the workflows that validate, publish, and release Pocket Lab without changing runtime behavior.",
        "",
        "## Summary",
        "",
        md_table(["Workflow", "File", "Classification", "Triggers", "Artifacts"], summary_rows),
        "",
        "## Documentation publishing flow",
        "",
        "```mermaid",
        "flowchart LR",
        "  PR[Pull request] --> Check[docs-pr-check]",
        "  Check --> Strict[MkDocs strict build]",
        "  Main[main branch push] --> Generate[Regenerate docs]",
        "  Generate --> Build[MkDocs build --strict]",
        "  Build --> Artifact[Upload Pages artifact]",
        "  Artifact --> Pages[Deploy GitHub Pages]",
        "```",
        "",
        *sections,
    ]
    OUTPUT.write_text("\n".join(body).rstrip() + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
