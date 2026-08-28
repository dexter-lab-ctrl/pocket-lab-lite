#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[3]
DEV = ROOT / "docs/generated/development"
PROD = ROOT / "docs/generated/production"
AUDIT = Path(__file__).with_name("task_audit.json")
FORBIDDEN = re.compile(r"(Bearer\s+[A-Za-z0-9._-]+|-----BEGIN .*PRIVATE KEY-----|nats://[^\s`]+@|tailscale[^\n]{0,20}auth[^\n]{0,20}[=:][^\s`]+|restic_password\s*[=:]\s*[^\s`]+)", re.I)

TAB_FILES = {
    "Home": "src/lite/LiteHome.jsx",
    "Devices": "src/lite/LiteDevices.jsx",
    "Apps": "src/lite/LiteCatalog.jsx",
    "Recovery": "src/lite/LiteRecovery.jsx",
    "Security": "src/lite/LiteSecurity.jsx",
    "Identity": "src/lite/LiteIdentity.jsx",
    "Rules": "src/lite/LiteRules.jsx",
}


def commit() -> str:
    # CI/release builds supply the exact commit. Local committed docs use a
    # stable marker so routine task checks do not drift after every commit.
    return os.environ.get("SOURCE_COMMIT", "").strip() or "uncommitted"


def generated_at() -> str:
    return os.environ.get("SOURCE_GENERATED_AT", "").strip() or "uncommitted"


def generator_sources() -> list[Path]:
    candidates = [
        ROOT / "Taskfile.yml", ROOT / "package.json", ROOT / "package-lock.json",
        ROOT / "requirements-dev.txt", ROOT / "requirements-docs.txt",
        ROOT / "playwright.config.ts", ROOT / "mkdocs.yml", ROOT / "redocly.yaml",
        ROOT / "contracts/metadata/documentation-experience.json",
        Path(__file__).resolve(), AUDIT,
    ]
    for base, pattern in [
        (ROOT / "tasks", "*.yml"),
        (ROOT / ".storybook", "*"),
        (ROOT / "scripts/dev/lite", "*"),
        (ROOT / "scripts/docs/lite", "*"),
        (ROOT / ".github/workflows", "*.yml"),
        (ROOT / "src/lite", "*.jsx"),
        (ROOT / "src/lib", "liteApi.js"),
    ]:
        if base.exists():
            candidates.extend(path for path in base.rglob(pattern) if path.is_file())
    router = ROOT / "pocket-lab-final-structure/runtime/api_fastapi/routers/lite.py"
    if router.exists():
        candidates.append(router)
    return sorted({path.resolve() for path in candidates if path.exists() and "__pycache__" not in path.parts})


def source_fingerprints() -> dict[str, str]:
    values: dict[str, str] = {}
    for path in generator_sources():
        values[path.relative_to(ROOT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return values


def aggregate_fingerprint(values: dict[str, str] | None = None) -> str:
    values = values or source_fingerprints()
    digest = hashlib.sha256()
    for path, value in sorted(values.items()):
        digest.update(path.encode())
        digest.update(b"\0")
        digest.update(value.encode())
        digest.update(b"\n")
    return digest.hexdigest()


def frontmatter(audience: str, source_commit: str, fingerprint: str, title: str, description: str, status: str) -> str:
    return (
        "---\n"
        f"title: {json.dumps(title)}\n"
        f"description: {json.dumps(description)}\n"
        f"status: {status}\n"
        "generated: true\n"
        f"audience: {audience.lower()}\n"
        f"source_commit: {source_commit}\n"
        f"generated_at: {generated_at()}\n"
        "generator: scripts/docs/lite/generate_docs.py\n"
        f"source_fingerprint: {fingerprint}\n"
        "schema_revision: 1\n"
        "validation_status: generated\n"
        "---\n\n"
    )


def list_files(relative: str, pattern: str = "*") -> list[str]:
    base = ROOT / relative
    if not base.exists():
        return []
    return sorted(path.relative_to(ROOT).as_posix() for path in base.rglob(pattern) if path.is_file())


def grep_strings(pattern: re.Pattern[str], files: Iterable[Path]) -> list[str]:
    values: set[str] = set()
    for file in files:
        try:
            text = file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        values.update(match.group(0) for match in pattern.finditer(text))
    return sorted(values)


def markdown_list(values: Iterable[str], empty: str = "None found") -> str:
    values = list(values)
    return "\n".join(f"- `{value}`" for value in values) if values else f"- {empty}"


def task_names() -> list[str]:
    values: list[str] = []
    for file in [ROOT / "Taskfile.yml", *sorted((ROOT / "tasks").glob("Taskfile.*.yml"))]:
        for line in file.read_text().splitlines():
            match = re.match(r"^  (lite:[A-Za-z0-9_.:-]+):\s*$", line)
            if match:
                values.append(match.group(1))
    return sorted(set(values))


def task_dependency_edges() -> list[tuple[str, str]]:
    edges: set[tuple[str, str]] = set()
    files = [ROOT / "Taskfile.yml", *sorted((ROOT / "tasks").glob("Taskfile.*.yml"))]
    for file in files:
        current = ""
        for line in file.read_text(encoding="utf-8").splitlines():
            match = re.match(r"^  (lite:[A-Za-z0-9_.:-]+):\s*$", line)
            if match:
                current = match.group(1)
                continue
            if not current:
                continue
            nested = re.search(r"- task:\s*(lite:[A-Za-z0-9_.:-]+)", line)
            if nested:
                edges.add((current, nested.group(1)))
            deps = re.search(r"deps:\s*\[([^]]+)\]", line)
            if deps:
                for value in deps.group(1).split(","):
                    dependency = value.strip().strip("'\"")
                    if dependency.startswith("lite:"):
                        edges.add((current, dependency))
    return sorted(edges)


def ci_task_mapping() -> list[str]:
    calls: list[str] = []
    for file in sorted((ROOT / ".github/workflows").glob("*.yml")):
        text = file.read_text(encoding="utf-8")
        for match in re.finditer(r"(?:^|\s)(task\s+lite:[A-Za-z0-9_.:-]+)", text):
            calls.append(f"{file.name}: {match.group(1)}")
    return sorted(set(calls))


def story_inventory() -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for file in sorted((ROOT / "src/lite").glob("*.stories.jsx")):
        names = re.findall(r"^export const ([A-Za-z0-9_]+)\s*=", file.read_text(), re.M)
        result[file.stem.replace(".stories", "")] = names
    return result


def openapi_paths() -> list[str]:
    path = ROOT / "contracts/generated/lite-openapi.json"
    if not path.exists():
        return []
    return sorted(json.loads(path.read_text()).get("paths", {}))


def event_subjects() -> list[str]:
    regex = re.compile(r"pocketlab\.(?:commands|events|telemetry|health|agent|lite)[A-Za-z0-9_.{}:-]*")
    files = list((ROOT / "pocket-lab-final-structure/runtime").rglob("*.py"))
    return grep_strings(regex, files)[:250]


def reason_codes() -> list[str]:
    regex = re.compile(r"(?<![A-Za-z0-9])(?:projection_too_old|read_degraded|worker_start_timeout|identity_mismatch|remote_access_not_ready|[a-z][a-z0-9]+(?:_[a-z0-9]+){1,5})(?![A-Za-z0-9])")
    files = list((ROOT / "pocket-lab-final-structure/runtime/api_fastapi").rglob("*.py"))
    values = grep_strings(regex, files)
    ignored = {"schema_version", "updated_at", "created_at", "app_id", "run_id", "device_id", "command_id", "source_commit", "status_code", "content_type", "user_agent", "request_id"}
    return [item for item in values if item not in ignored][:300]


def env_vars() -> list[str]:
    regex = re.compile(r"(?:POCKETLAB|LITE|NATS|PLAYWRIGHT|CHROME|CHROMIUM|EDGE)_[A-Z0-9_]+")
    files = [*ROOT.glob("Taskfile.yml"), *list((ROOT / "tasks").glob("*.yml")), *list((ROOT / "scripts").rglob("*.sh")), *list((ROOT / "scripts").rglob("*.py")), ROOT / "playwright.config.ts"]
    return grep_strings(regex, [path for path in files if path.exists()])[:250]


def sqlite_sources() -> list[str]:
    candidates = []
    for path in (ROOT / "pocket-lab-final-structure/runtime/api_fastapi/services").glob("*store*.py"):
        text = path.read_text(errors="ignore")
        if "sqlite" in text.lower() or "CREATE TABLE" in text:
            candidates.append(path.relative_to(ROOT).as_posix())
    return sorted(candidates)


def bootstrap_stages() -> list[str]:
    regex = re.compile(r"(?:stage|run_stage)\s+[\"']?([a-z][a-z0-9_-]+)")
    values: set[str] = set()
    for file in (ROOT / "pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts").rglob("*.sh"):
        text = file.read_text(errors="ignore")
        for match in regex.finditer(text):
            values.add(match.group(1))
    return sorted(values)


def header(title: str, audience: str, source_commit: str, intro: str, status: str = "verified") -> str:
    badge = status.replace("_", "-")
    label = status.replace("_", " ").title()
    return (
        frontmatter(audience, source_commit, aggregate_fingerprint(), title, intro, status)
        + f"# {title}\n\n"
        + '<div class="pl-page-meta" markdown>\n'
        + f'<span class="pl-status pl-status--{badge}">{label}</span>\n'
        + f'<span class="pl-status pl-status--patch-provided">{audience} guidance</span>\n'
        + "</div>\n\n"
        + f"{intro}\n\n"
    )


def development_outputs(source_commit: str) -> dict[Path, str]:
    audit = json.loads(AUDIT.read_text())
    tasks = task_names()
    stories = story_inventory()
    paths = openapi_paths()
    subjects = event_subjects()
    reasons = reason_codes()
    envs = env_vars()
    stores = sqlite_sources()
    stages = bootstrap_stages()
    outputs: dict[Path, str] = {}

    outputs[DEV / "index.md"] = header(
        "Development documentation",
        "Development",
        source_commit,
        "Everything in this section is generated for Ubuntu/WSL2 maintainers. Development tooling is not a production dependency and is not included in `dist.zip`.",
    ) + "## Fast path\n\n```bash\ntask lite:setup:check\ntask lite:check:quick\ntask lite:docs:check\n```\n\nThe verified WSL2 browser is selected through `task lite:playwright:preflight`; no machine-specific path is committed.\n"

    audit_sections = []
    labels = {
        "verified_lite_ready": "Verified Lite-ready before refactor",
        "adapted_to_lite": "Adapted into the Lite task surface",
        "removed_full_version_only": "Removed full-version-only tasks",
        "removed_duplicate_or_legacy": "Removed duplicate or legacy aliases",
        "optional_release_only": "Kept only as explicit release/device concepts",
    }
    for key, label in labels.items():
        audit_sections.append(f"## {label}\n\n{markdown_list(audit.get(key, []))}")
    outputs[DEV / "task-audit.md"] = header("Task ownership audit", "Development", source_commit, "The old root Taskfile exposed full-product tasks that were not a truthful Lite command surface. The repository search below drove the replacement.") + "\n\n".join(audit_sections) + f"\n\n## Current Lite task surface\n\n{markdown_list(tasks)}\n"

    task_edges = task_dependency_edges()
    outputs[DEV / "task-reference.md"] = header("Lite task reference", "Development", source_commit, "The root Taskfile uses included Lite task files and separates quick, full, release, UI, docs, and Windows/WSL2 workflows.") + markdown_list(tasks) + "\n\n## Task dependency graph\n\n" + ("\n".join(f"- `{source}` → `{target}`" for source, target in task_edges) or "- No nested Lite task edges found") + "\n\n## Validation tiers\n\n- Quick: compile, shell syntax, focused tests, contracts, PWA build, cheap generated-doc drift.\n- Full: full Lite suites, Storybook, mocked Playwright, accessibility, redaction, Redocly, strict MkDocs.\n- Release: live read-only browser checks, runtime/projection checks, optional Android evidence, release artifact validation, Allure-compatible evidence.\n"

    architecture = """```mermaid
flowchart LR
  UI[React/Vite PWA] --> Caddy[Caddy same-origin proxy]
  Caddy --> API[FastAPI /api/lite/*]
  API --> DB[(SQLite prepared state)]
  API --> NATS[NATS / JetStream]
  NATS --> Exec[Worker / agent / supervisor]
  Exec --> Evidence[Events, heartbeats, sanitized evidence]
  Evidence --> API
  API --> UI
```

Mandatory boundaries: the frontend never talks directly to NATS, never executes shell commands, and never stores backend secrets. Bootstrap commands remain backend-generated; agents and supervisors own execution and recovery.
"""
    outputs[DEV / "architecture.md"] = header("Lite architecture as code", "Development", source_commit, "This page is generated from the active Lite source layout and architectural constraints.") + architecture + "\n## Active screen modules\n\n" + markdown_list(TAB_FILES.values())

    outputs[DEV / "api.md"] = header("HTTP API inventory", "Development", source_commit, "FastAPI OpenAPI is the canonical browser/backend contract. Redocly validates the generated Lite-only view.") + f"## Lite paths ({len(paths)})\n\n{markdown_list(paths)}\n"
    outputs[DEV / "events.md"] = header("NATS and event inventory", "Development", source_commit, "Subjects are scanned from current runtime source. This does not reintroduce the retired full-product typed-operation catalog.") + f"## Detected subjects ({len(subjects)})\n\n{markdown_list(subjects)}\n"
    outputs[DEV / "sqlite-projections.md"] = header("SQLite and prepared projections", "Development", source_commit, "SQLite store modules are the source for durable enrollment, Security, Recovery, command lifecycle, and prepared read behavior.") + "## Store and migration sources\n\n" + markdown_list(stores) + "\n\nPrepared projection documentation must distinguish scheduler generation, committed generation, canonical hash, freshness, read degradation, and cache state.\n"
    outputs[DEV / "fixtures-schemas.md"] = header("Canonical fixtures and schemas", "Development", source_commit, "`generate_contracts.py` exports a Lite-only OpenAPI contract, validates frontend routes, and generates bounded sanitized scenario metadata used by MSW, Storybook, and mocked Playwright.") + "## Generated fixture directories\n\n" + markdown_list(list_files("src/test/fixtures/generated", "*.json")) + "\n\nIdentity and Rules fixtures model the implemented owner/session/recovery and OPA status contracts. Protected mutation success is never fabricated without an explicit mocked policy decision and backend acceptance.\n"

    story_lines = []
    for screen, names in stories.items():
        story_lines.append(f"## {screen}\n\n" + markdown_list(names))
    outputs[DEV / "ui-storybook.md"] = header("Storybook scenario inventory", "Development", source_commit, "Lite Storybook uses the production screen components, global Lite styling, deterministic MSW behavior, an isolated query/offline cache reset, mobile/tablet/desktop viewports, accessibility, interactions, and reduced-motion defaults.") + "\n\n".join(story_lines)

    outputs[DEV / "browser-testing.md"] = header("Playwright and browser resolution", "Development", source_commit, "WSL2 browser selection is a first-class preflight. The resolver checks explicit environment variables before auto-detecting `/usr/bin/google-chrome`; CI may use a verified Playwright-managed browser.") + "## Projects\n\n- mocked-desktop\n- mocked-mobile\n- live-desktop\n- live-mobile\n\n## Evidence\n\n`.pocketlab-dev/validation/playwright-browser.json` records the actual executable, version, launch mode, and WSL detection. Raw HAR files are ignored; only sanitized HAR output may be retained.\n"
    outputs[DEV / "configuration-services.md"] = header("Configuration and service inventory", "Development", source_commit, "Only variable names and safe defaults are documented. Runtime values and private paths are excluded.") + f"## Environment variables ({len(envs)})\n\n{markdown_list(envs)}\n\n## Process roles\n\n- FastAPI control API\n- NATS/JetStream\n- pocket-worker\n- Lite node agent\n- Lite supervisor\n- Caddy same-origin proxy\n"
    outputs[DEV / "bootstrap.md"] = header("Bootstrap source reference", "Development", source_commit, "Bootstrap scripts remain backend-generated and secret-safe. This inventory lists only detected stage names, never generated commands or invite values.") + f"## Detected stages ({len(stages)})\n\n{markdown_list(stages)}\n"
    # The canonical structured reason-code registry is owned by
    # generate_platform_catalogs.py; do not overwrite it with regex-only output.
    outputs[DEV / "validation-release.md"] = header("Validation and release evidence", "Development", source_commit, "Lite validation commands write bounded command records under `.pocketlab-dev/validation`; `task lite:allure` converts those records into Allure-compatible JSON without adding a production dependency.") + "## Release artifact contract\n\n- `dist.zip` contains only the PWA output.\n- `checksums.txt` must match `dist.zip`.\n- `pocketlab-lite-release.json`, when present, must identify product, release tag, source commit, target, and artifact digest.\n- Storybook, MkDocs, Redocly, Playwright, Allure results, state databases, and secrets are excluded.\n"
    outputs[DEV / "partial-surfaces.md"] = header("Identity and Rules implementation boundaries", "Development", source_commit, "Identity implements local human authentication, passkeys, step-up, and opt-in Enterprise memberships. Rules provides bounded policy governance without moving execution authority from FastAPI.") + "## Identity\n\nThe local human flow covers setup, sign-in, password change, logout/session revocation, one-time recovery codes, and passkey registration, sign-in, rename, and revoke. WebAuthn validates origin, RP ID, and one-use challenges; purpose-bound passkey step-up expires. Personal Mode is the default. Opt-in Enterprise Mode uses server-owned memberships and roles, with final-Owner protection. Device identities remain owned by Devices. The separate API-token actor/path is not a browser human session. External OIDC federation and service-identity provisioning or management remain deferred.\n\n## Rules\n\nFastAPI builds server-owned authorization input, preserves non-bypassable domain invariants, asks loopback OPA only for registered protected actions, records bounded sanitized decisions, and fails closed on unavailable or invalid policy responses. Rules supports immutable typed revisions, validation, activation/readiness, known-good rollback, uncertain-recovery resolution, deterministic analysis, and non-executing simulation. Independent approval is a bounded gate: an eligible Owner or Admin other than the initiator completes passkey step-up for the exact action, target, and revision; the initiator retries with a one-use continuation. Approval never executes the action. Temporary exceptions are limited to exact `catalog.install` app/device/human/revision scope, are revocable, and last no more than 60 minutes.\n"
    outputs[DEV / "repository-setup.md"] = header("Repository and WSL2 setup", "Development", source_commit, "Development runs from the Linux filesystem under WSL2. Repository setup restores the committed lockfiles and does not search for or install newer tool versions.") + "```bash\ncd ~/pocket-lab-lite\ntask lite:setup\ntask lite:setup:check\n```\n\nThe setup task reuses the existing `.venv`, runs `npm ci` only when `node_modules` is absent, skips Playwright browser downloads, and installs Python requirements only when imports are missing.\n"
    outputs[DEV / "local-services.md"] = header("Local services and URLs", "Development", source_commit, "Development URLs are independent so direct FastAPI, same-origin Caddy/PWA, Vite, Storybook, MkDocs, NATS, state, and validation paths cannot be confused.") + "- FastAPI direct: `LITE_API_DIRECT_URL` (default `http://127.0.0.1:8000`)\n- Caddy/PWA: `LITE_BASE_URL` (default `http://127.0.0.1:8443`)\n- Vite: `LITE_FRONTEND_URL` (default `http://127.0.0.1:5173`)\n- Storybook: `LITE_STORYBOOK_URL` (default `http://127.0.0.1:6006`)\n- MkDocs: `LITE_DOCS_URL` (default `http://127.0.0.1:8001`)\n- NATS: `NATS_URL` (default `nats://127.0.0.1:4222`)\n"
    outputs[DEV / "coding-standards.md"] = header("Coding and architecture standards", "Development", source_commit, "Changes must preserve Android/Termux, ARM64, low-power, same-origin, and backend-owned execution boundaries.") + "- Frontend code never executes shell commands or connects directly to NATS.\n- FastAPI remains the control API; workers, agents, and supervisors own execution and recovery.\n- Safe read caches never store secrets, raw logs, invite tokens, bootstrap secrets, or write responses.\n- Generated files must be deterministic, bounded, sanitized, and source-fingerprinted.\n- Identity and Rules behavior is not claimed beyond verified source contracts.\n"
    outputs[DEV / "testing.md"] = header("Testing matrix", "Development", source_commit, "The Lite test matrix separates deterministic component/API checks from live read-only integration and explicit device qualification.") + "- Unit: Vitest and focused backend Pytest.\n- Contract: FastAPI OpenAPI export, frontend route usage, generated fixture metadata, Redocly.\n- Component: Storybook render and interaction checks.\n- Mock integration: Playwright desktop/mobile through MSW and TanStack Query.\n- Live integration: read-only Playwright through Caddy/FastAPI when `LITE_E2E_LIVE=1`.\n- Device qualification: explicit Android/Termux and long-duration gates only.\n"
    outputs[DEV / "documentation-experience.md"] = header("Documentation experience", "Development", source_commit, "The MkDocs Material portal is a tested knowledge product with question-oriented navigation, a canonical UX contract, responsive intelligence views, accessible status semantics, and strict generated-content ownership.") + """## Design system\n\n- `contracts/metadata/documentation-experience.json` is the canonical Documentation UX contract.\n- Brand, component, intelligence, and print styles live outside generated directories.\n- System fonts avoid external font requests.\n- Status always uses text plus shape/symbol and color; color is never the only signal.\n- Evidence-heavy pages use a consistent status hierarchy: health first, then implementation/runtime/parity, then freshness and evidence confidence.\n- Summary → explanation → technical evidence is the default progressive-disclosure sequence.\n- The home dashboard, role shortcuts, task-oriented entry points, evidence lineage, scorecards, and matrix views are generated from canonical source and promoted evidence.\n- Motion is bounded and respects `prefers-reduced-motion`; continuous decorative animation is prohibited.\n\n## Authoring conventions\n\n!!! info "Context"\n    Use informational notes for verified background.\n\n!!! warning "Action required"\n    Use warnings for service interruption, validation gaps, or state that needs user review.\n\n```bash title="Documentation validation"\ntask lite:docs:generate\ntask lite:docs:check\ntask lite:docs:intelligence:check\ntask lite:test:docs\n```\n\n## Browser acceptance\n\nThe dedicated Playwright documentation suite checks the dashboard, question-oriented navigation, search, theme switching, mobile layouts, progressive disclosure, evidence lineage, matrix overflow, code-copy controls, console health, and serious/critical Axe findings.\n"""
    outputs[DEV / "accessibility-visual.md"] = header("Accessibility, visual, and performance gates", "Development", source_commit, "Desktop browser evidence is useful but does not prove Android production performance.") + "Playwright checks serious/critical Axe findings, reduced motion, mobile/desktop rendering, console/API failures, and canonical screenshots. Existing Lighthouse and bundle-budget helpers remain Development-PC gates. Visual baselines must be reviewed before update.\n"
    outputs[DEV / "har-sanitization.md"] = header("HAR capture and sanitization", "Development", source_commit, "Raw HAR files are transient and ignored. Only sanitized HAR output may be retained as evidence.") + "`task lite:har:sanitize INPUT=<raw.har> OUTPUT=<safe.har>` removes authorization, cookies, credentials, NATS user info, Restic/Tailscale secrets, private keys, and sensitive query/header fields. `task lite:har:inspect` reports failed or duplicate Lite requests and heavy first-paint responses.\n"
    outputs[DEV / "allure-evidence.md"] = header("Validation and Allure-compatible evidence", "Development", source_commit, "Every recorded gate includes command, commit, platform, start/end timestamps, exit code, result, bounded output, and artifact paths.") + "`task lite:validation:evidence` generates `allure-results/`, a validation manifest, readiness matrix, and test artifact index. `task lite:allure` also creates a bounded local HTML evidence index. The upstream Allure UI is optional and must use an independently provisioned pinned CLI; it is not a server-phone dependency.\n"
    outputs[DEV / "ci-workflows.md"] = header("CI workflow to task mapping", "Development", source_commit, "CI uses the Lite task surface rather than reintroducing full-product workflows.") + markdown_list(ci_task_mapping(), "No Lite task calls detected in CI") + "\n"
    outputs[DEV / "release-engineering.md"] = header("Release engineering", "Development", source_commit, "Release qualification is explicit and does not make live, Android, or long-duration checks part of every edit loop.") + "Run `task lite:check:release` with a running isolated stack and `LITE_E2E_LIVE=1`, then `task lite:release:dry-run`. Artifact validation checks required PWA files, checksum, optional release manifest identity, and forbidden development/state/secret entries.\n"
    outputs[DEV / "contribution-review.md"] = header("Contribution and review", "Development", source_commit, "Keep changes targeted and main clean.") + "Before review: run quick/full gates as appropriate, generated contract/docs drift checks, `git diff --check`, and generated-artifact cleanup. Do not commit `.orig`, `.rej`, `.pytest_cache`, raw HAR, accidental `dist`, Storybook static output, Allure output, state databases, or secrets.\n"
    return outputs


def user_guide(
    source_commit: str,
    title: str,
    purpose: str,
    glance: list[str],
    controls: list[tuple[str, str, str, str, str, str, str]],
    workflows: list[str],
    unavailable: str,
    safety: str,
    journey: str,
    technical: str,
) -> str:
    """Generate a consistent, static user manual for a Lite tab."""
    fingerprint = aggregate_fingerprint()
    card_html = "\n".join(
        f'<article class="pl-card"><span class="pl-card-kicker">At a glance</span><p>{item}</p></article>'
        for item in glance
    )
    control_cards = render_control_cards(controls)
    status_matrix = render_status_matrix(title, controls)
    return header(title, "Production", source_commit, purpose) + "\n".join([
        "## What this tab is for", "", purpose, "", "## What you see at a glance", "",
        markdown_list(glance), "", "## Main cards and sections", "", '<div class="pl-card-grid">', card_html, "</div>",
        "", "## Buttons, controls and options", "", control_cards,
        "", "## What happens when you use them", "", "Controls request supported FastAPI actions or navigate to another tab. The browser does not execute shell commands, directly contact NATS or OPA, or hold backend secrets. Progress and prepared reads are rendered after backend-owned work returns bounded evidence.",
        "", "## Statuses and messages", "", "Treat **Ready**, **Completed**, and visible verified evidence as distinct from **Waiting**, **Working**, **Needs attention**, **Blocked**, **Failed**, saved, or degraded states. A saved projection explains what was last known; it does not authorize a write or prove a fresh action succeeded. Approval never auto-executes an action.", "", status_matrix,
        "", "## Common workflows", "", markdown_list(workflows), "", "## When something is unavailable", "", unavailable,
        "", "## Safety / trust boundaries", "", safety,
        "", "## Related Feature Journey", "", journey,
        "", "## Related technical references", "", technical,
    ]) + "\n"


def render_control_cards(controls: list[tuple[str, str, str, str, str, str, str]]) -> str:
    """Render layered, progressively disclosed control cards for a Lite tab."""
    fields = (
        "Where",
        "Purpose",
        "Available when",
        "What happens next",
        "Success looks like",
        "May be blocked when",
    )
    cards = []
    for control, *values in controls:
        where, purpose, available_when, *detail_values = values
        details = "".join(
            f"<div><dt>{label}</dt><dd>{value}</dd></div>"
            for label, value in zip(fields[3:], detail_values)
        )
        cards.append(
            '<article class="pl-card">'
            '<details class="pl-disclosure--compact pl-control-card">'
            "<summary>"
            '<span class="pl-card-kicker">Control</span>'
            f"<h3>{control}</h3>"
            f'<span class="pl-control-card__purpose">{purpose}</span>'
            '<span class="pl-control-card__availability">'
            '<span class="pl-control-card__availability-label">Available when</span>'
            f'<span class="pl-control-card__availability-value">{available_when}</span>'
            '</span>'
            '<span class="pl-control-card__toggle" aria-hidden="true"></span>'
            "</summary>"
            '<dl class="pl-detail-list pl-control-card__facts">'
            f"<div><dt>Where</dt><dd>{where}</dd></div>{details}"
            "</dl></details></article>"
        )
    return '<section class="pl-card-grid" aria-label="Buttons, controls and options">\n' + "\n".join(cards) + "\n</section>"


def render_status_matrix(title: str, controls: list[tuple[str, str, str, str, str, str, str]]) -> str:
    """Render status guidance as a layered, responsive semantic table."""
    blocked_examples = "; ".join(control[6] for control in controls[:3])
    rows = [
        ("ready", "Ready / available", "The displayed control can accept a supported request.", "Select it, then follow the returned progress and evidence."),
        ("working", "Working / waiting", "A request is in progress or is awaiting a stated prerequisite.", "Wait for a fresh state; resolve the named prerequisite before retrying."),
        ("complete", "Completed / verified", "The backend returned a bounded result or verification evidence.", "Review the visible outcome before taking a related action."),
        ("attention", "Needs attention / blocked", f"{title} cannot safely continue. Examples: {blocked_examples}.", "Read the specific message and use the stated recovery path; do not infer success."),
        ("saved", "Saved / degraded / failed", "The view is historical, incomplete, or the request did not complete.", "Refresh prepared state or investigate the bounded evidence; a saved view does not authorize a write."),
    ]
    body = "".join(
        f'<tr><th scope="row"><span class="pl-status-pill pl-status-pill--{kind}">{status}</span></th>'
        f'<td data-label="What it means">{meaning}</td><td data-label="What to do">{next_step}</td></tr>'
        for kind, status, meaning, next_step in rows
    )
    return (
        '<section class="pl-status-panel" aria-label="Status matrix">'
        '<div class="pl-status-panel__header"><span class="pl-card-kicker">Status matrix</span>'
        f"<h3>{title} states at a glance</h3><p>Read the state before retrying or taking a related action.</p></div>"
        '<div class="pl-table-wrap"><table class="pl-status-matrix">'
        f"<caption>{title} status matrix</caption>"
        "<thead><tr><th scope=\"col\">Status</th><th scope=\"col\">What it means</th><th scope=\"col\">What to do</th></tr></thead>"
        f"<tbody>{body}</tbody></table></div></section>"
    )


def render_tab_cards() -> str:
    """Render the seven deployed Lite tabs as concise, scan-friendly cards."""
    tabs = [
        ("Home", "Workspace and update summary", "Refresh prepared information and review current-versus-saved state."),
        ("Devices", "Enrollment and device health", "Add, reconnect, recover, or retire devices with identity safeguards."),
        ("Apps", "Supported app lifecycle", "Open or manage a supported catalog app through FastAPI requests."),
        ("Security & Safety", "Bounded local checks", "Choose an enabled scan and review normalized, sanitized results."),
        ("Backup & Restore", "Guarded recovery workflow", "Back up, verify, preview, and explicitly confirm restore."),
        ("Identity & Access", "Local human access", "Manage sign-in, passkeys, recovery, sessions, and memberships."),
        ("Rules", "Protected-action governance", "Review policy state, simulation, approvals, exceptions, and decisions."),
    ]
    cards = "".join(
        '<article class="pl-card pl-tab-card">'
        f'<span class="pl-card-kicker">{name}</span><h3>{focus}</h3><p>{summary}</p></article>'
        for name, focus, summary in tabs
    )
    return '<section class="pl-tab-grid" aria-label="Current Lite tabs">' + cards + "</section>"


def production_outputs(source_commit: str) -> dict[Path, str]:
    outputs: dict[Path, str] = {}
    outputs[PROD / "index.md"] = header("Production and user documentation", "Production", source_commit, "This section contains only verified deployable Pocket Lab Lite behavior. Development fixtures, test-only routes, machine-specific paths, raw evidence, and planned workflows are excluded.") + "Pocket Lab Lite is an edge-first self-hosted control plane for Android/Termux, ARM64, low-power devices, and private self-hosting.\n"
    outputs[PROD / "architecture.md"] = header("Production architecture", "Production", source_commit, "The deployable flow is UI → Caddy → FastAPI → SQLite/NATS → worker/agent/supervisor → sanitized events and prepared reads → UI.") + "The frontend never talks directly to NATS, executes shell commands, or stores backend secrets. FastAPI is the control API. Agents and supervisors own execution and recovery.\n"
    outputs[PROD / "tabs.md"] = header("Current Lite tabs", "Production", source_commit, "The deployed PWA exposes seven Lite-friendly sections.") + "## Choose a tab\n\n" + render_tab_cards() + "\n\nEach tab renders prepared, backend-owned state and supported actions. The browser does not execute shell commands, connect directly to NATS or OPA, or hold backend secrets.\n"
    outputs[PROD / "devices.md"] = header("Devices and onboarding", "Production", source_commit, "Device onboarding is backend-owned: invite creation → audit evidence → copyable bootstrap command → identity guard → safe acceptance → env write → node agent/supervisor start → heartbeats in Devices.") + "Duplicate names and invites are blocked case-insensitively and separator-insensitively. Identity mismatches fail closed. A lost heartbeat changes a durable enrolled device to Offline/Stale; it does not implicitly delete enrollment.\n"
    outputs[PROD / "apps.md"] = header("Apps and PhotoPrism", "Production", source_commit, "The App Catalog is a backend-owned action surface. PhotoPrism is served through the same-origin `/apps/photoprism/` route when installed and route-ready.") + "The UI may open the route and request supported actions through FastAPI. It does not run PhotoPrism, PM2, Caddy, storage, backup, repair, or scanner commands directly.\n"
    outputs[PROD / "security.md"] = header("Security and Safety", "Production", source_commit, "Security checks run through FastAPI, NATS/JetStream, and the worker. Lynis/Trivy output is normalized and sanitized before summary display.") + "Quick Safety Check is the default low-power profile. Full Local Check and PhotoPrism App Check are explicit deeper checks where enabled. Photos/media, secrets, raw logs, private paths, and raw scanner payloads are excluded from normal UI and generated docs.\n"
    outputs[PROD / "recovery.md"] = header("Backup and restore", "Production", source_commit, "Recovery is backend/worker-owned. The UI can request a backup, verification, restore preview, and confirmed restore only through supported FastAPI endpoints.") + "Restore requires explicit confirmation, a pre-restore checkpoint, and post-restore health validation. Saved-state display never fakes action success.\n"
    outputs[PROD / "remote-access.md"] = header("Remote access", "Production", source_commit, "Tailscale and Caddy provide private same-origin access where configured. The Devices tab shows Tailscale IP only when readiness is verified.") + "When unavailable, the product says **Remote access not ready**. Startup scripts may safely start `tailscaled`; read APIs remain side-effect free.\n"
    outputs[PROD / "bootstrap.md"] = header("Bootstrap and install", "Production", source_commit, "Use the repository's Lite bootstrap profile and generated device command. Bootstrap output must not be copied into public documentation or support records when it contains enrollment material.") + "The production server phone does not require Storybook, Playwright, Redocly, MkDocs, or Allure. Those remain Development-PC tools.\n"
    outputs[PROD / "release.md"] = header("Release and dist.zip", "Production", source_commit, "Pocket Lab Lite releases use a date-based annotated tag and a GitHub release containing `dist.zip`, `checksums.txt`, and the release manifest.") + "The PWA artifact is promoted atomically and validated after switch. Development documentation/tooling is not included in `dist.zip`.\n"
    outputs[PROD / "troubleshooting.md"] = header("Troubleshooting", "Production", source_commit, "Use truthful Lite states before restarting services.") + "- Running but disconnected: check NATS/Tailscale and reconnect watchdog evidence.\n- Agent stopped: verify supervisor and PM2 state.\n- Stopped without supervisor: follow recovery guidance; do not fabricate command delivery.\n- Security scan accepted but not starting: verify durable consumer health and stale-run recovery evidence.\n- Recovery projection stale: inspect freshness/revision and refresh prepared reads; do not treat saved state as fresh.\n"
    outputs[PROD / "limitations.md"] = header("Current limitations", "Production", source_commit, "Only source-implemented behavior is listed; live server-phone qualification remains separate.", status="unvalidated") + "- Passkeys/WebAuthn are implemented for local human registration/login/rename/revoke and purpose-bound step-up. External OIDC federation and service-identity provisioning or management remain deferred; the separate API-token actor/path is not a browser human session.\n- Enterprise Mode is opt-in. Memberships and roles are server-owned, including final-Owner protection; it does not imply external federation.\n- Rules protects only explicitly registered actions; broader authorization coverage is not implied. Approval is an independent, expiring gate and never executes an action automatically.\n- Temporary exceptions apply only to exact `catalog.install` app/device/human/revision scope, are revocable, and last at most 60 minutes.\n- The legacy generic secret store remains separate from the human Identity credential store and must not be treated as the owner password backend.\n- Android performance and live OPA/process claims require server-phone evidence; desktop/source validation alone is insufficient.\n- Live browser and long-duration qualification require a running isolated stack and explicit user action.\n"
    outputs[PROD / "installation.md"] = header("Installation", "Production", source_commit, "Install through the repository-owned Lite bootstrap profile on the server phone. Do not install Development-PC documentation or browser tooling on Android/Termux.") + "Use the current release artifact and bootstrap scripts from the verified repository/release. Validate `/health`, `/ready`, Caddy same-origin access, NATS/JetStream, worker, node agent, and supervisor after install.\n"
    outputs[PROD / "upgrade.md"] = header("Upgrade and release verification", "Production", source_commit, "An upgrade is valid only when release identity, manifest, artifact checksum, staged PWA contents, and post-switch health agree.") + "Stable healthy systems use a calm release-check cadence. Manual checks are immediate; active download/apply stages may poll faster only during transition. Auto-apply remains disabled unless explicitly configured and validated.\n"
    outputs[PROD / "android-termux.md"] = header("Android and Termux operations", "Production", source_commit, "The server-phone runtime is ARM64/Android/Termux and must avoid desktop-only assumptions.") + "Use Termux-compatible paths and commands, keep generated work bounded, and validate PM2, NATS, Caddy, Tailscale, FastAPI, worker, agent, and supervisor with server-phone evidence. Development browser, Storybook, MkDocs, Redocly, and Allure tooling is not required.\n"
    outputs[PROD / "caddy-access.md"] = header("Caddy and same-origin access", "Production", source_commit, "Caddy serves the PWA and proxies `/api/lite/*`; app routes such as `/apps/photoprism/*` remain backend-owned and are excluded from PWA fallback capture.") + "Tailscale HTTPS uses verified Tailnet readiness and protected certificate material. Certificates, private keys, FQDN-specific secrets, and runtime values are never emitted by generated documentation.\n"
    outputs[PROD / "identity.md"] = header("Identity", "Production", source_commit, "Identity owns local human credentials, browser session lifecycle, recovery codes, passkeys, step-up, and safe identity-class visibility. It does not replace device enrollment identity or the separate API-token actor/path.") + "## Local human authentication\n\n- A local owner is created through the explicit setup flow and one-time setup token, or through the explicit passkey owner-claim flow.\n- Password verifiers use `scrypt`; raw passwords are never stored in the Identity tables.\n- Browser sessions use opaque random credentials whose hashes are stored in SQLite; session cookies are HttpOnly and Secure by default. Browser writes require a separate same-site CSRF token.\n\n## Passkeys and step-up\n\n- Passkeys support registration, sign-in, friendly-name updates, and revoke. WebAuthn validates the HTTPS origin (with localhost development support), RP ID, and one-use challenge; credential public keys and counters are server-recorded without exposing authenticator material.\n- Purpose-bound passkey step-up provides short-lived server-recorded assurance for protected actions. It does not make browser-provided assurance authoritative.\n\n## Recovery, sessions, and Enterprise Mode\n\n- Recovery codes are high-entropy, shown once, stored hash-only, generation-scoped, and consumed once. Regeneration invalidates the prior batch. Password change and recovery increment the owner auth version and revoke stale sessions; sessions can also be revoked explicitly.\n- Personal Mode is the default. Opt-in Enterprise Mode uses server-owned memberships and roles, and prevents removal or demotion of the final active Owner.\n- Identity audit rows contain bounded reason codes and summaries, not credentials, recovery material, challenges, or credential identifiers.\n\n## Boundaries\n\nDevice enrollment identity remains owned by Devices. The separate API-token actor/path is non-browser and does not grant a human session. External OIDC federation and service-identity provisioning or management are deferred. The frontend does not persist session credentials in localStorage, Dexie, Zustand, XState, or TanStack Query.\n"
    outputs[PROD / "rules.md"] = header("Rules", "Production", source_commit, "Rules is the operator view of loopback-only Open Policy Agent admission and bounded policy governance. FastAPI remains authoritative and preserves hard domain invariants before any policy call or continuation.") + "## Runtime model\n\n- OPA is installed as a pinned ARM64 runtime dependency and is not packaged in `dist.zip`.\n- Startup validates repository Rego with `opa fmt`, `opa check --strict`, and `opa test --fail-on-empty` before atomically activating a revision and starting `pocket-opa` on `127.0.0.1:8181`. OPA is not routed through Caddy and is not called by the browser or NATS.\n- FastAPI constructs bounded authorization input from server-owned actor/session and target state, asks loopback OPA, reuses existing domain invariants/revision checks, and only then reaches the existing execution path. Unavailable, timed-out, malformed, or unknown decisions fail closed.\n\n## Policy lifecycle and evaluation\n\n- Typed policy candidates become immutable revisions. Validation, activation/readiness, active and known-good state, rollback, and uncertain-recovery resolution remain explicit and auditable.\n- Analysis reports only direct registered-action coverage that current templates can prove. Simulation uses bounded real-derived or synthetic input and never executes an action.\n- Decision evidence stores bounded identifiers, allow/block state, stable reason code, policy revision, and evaluation duration; raw policy input, credentials, command payloads, and secrets are excluded.\n\n## Approval and exception bounds\n\n- A policy may require independent approval. An eligible Owner or Admin other than the initiator must complete purpose-bound passkey step-up for the exact action, target, and policy revision before an expiring approval is recorded. The initiator must retry; the matching continuation is atomic, one-use, and refuses replay. Approval never auto-executes an action.\n- Temporary exceptions are limited to exact `catalog.install` app/device/human/revision scope, must be revoked or expire within 60 minutes, and do not bypass hard domain invariants.\n\nThe registered enforcement surface remains deliberately bounded; broader authorization coverage is not implied.\n"
    outputs[PROD / "services-pm2.md"] = header("Services and PM2", "Production", source_commit, "Expected Lite processes include Caddy, FastAPI, NATS/JetStream, worker, node agent, supervisors, and the loopback `pocket-opa` policy engine; installed apps may add their own managed process.") + "Use `pm2 status` and bounded process logs for diagnosis. Validate `pocket-opa` health on loopback before protected mutations. Do not restart healthy services casually; distinguish disconnected, stopped, repairing, policy-unavailable, and undeliverable-command states.\n"
    outputs[PROD / "health-diagnostics.md"] = header("Health and diagnostics", "Production", source_commit, "Start with safe reads and prepared diagnostics.") + "Expected entry points include `/health`, `/ready`, `/api/lite/status`, and domain-specific Lite reads. Verify SQLite quick-check/parity, projection freshness/revisions, NATS durable-consumer health, PM2 state, Tailnet reachability, and recent sanitized evidence before recovery action.\n"
    outputs[PROD / "incident-runbooks.md"] = header("Incident runbooks", "Production", source_commit, "Runbooks are user guidance, not browser shell execution.") + "- NATS unavailable: verify listener, Tailnet reachability, credentials/config posture, and reconnect evidence.\n- Worker consumer stalled: verify durable consumer health and watchdog recovery before restart.\n- Agent stopped: verify supervisor, then use explicit recovery.\n- Projection stale: preserve last valid state, rebuild prepared projection, and validate revision parity.\n- Release verification failed: keep last-known-good PWA and investigate manifest/checksum/health.\n"
    outputs[PROD / "rollback.md"] = header("Release rollback", "Production", source_commit, "Rollback returns to a previously verified PWA artifact and last-known-good identity.") + "Do not overwrite evidence. Restore the prior staged artifact atomically, restart only the serving layer that requires it, then verify Caddy, `/health`, `/ready`, release identity, service worker state, and device/app reads.\n"
    outputs[PROD / "data-retention.md"] = header("Data retention", "Production", source_commit, "Enrollment, audit, backup, Security, and lifecycle history are retained independently from live connectivity.") + "Offline devices are not deleted implicitly. Command cleanup cannot remove enrollment. Removal/retirement is explicit, transactional, dependency-aware, and preserves historical audit records. Bounded generated validation evidence follows user retention policy and never enters `dist.zip`.\n"
    outputs[PROD / "security-boundaries.md"] = header("Security boundaries and redaction", "Production", source_commit, "Secrets and raw operational payloads remain backend-only.") + "The UI and generated artifacts exclude passwords, recovery codes, session credentials, CSRF material, hashes/verifiers, authorization headers, cookies, NATS credentials, Restic passwords, Tailscale auth keys, private keys, raw environment values, OPA input documents, scanner payloads, raw logs, and private Android paths. Human browser writes require an authenticated HttpOnly session plus CSRF header; service API-token authentication remains separate. OPA remains loopback-only and additive to FastAPI-owned hard invariants.\n"
    outputs[PROD / "home.md"] = user_guide(source_commit, "Home", "Home summarizes the self-hosted workspace, release/system information, and safe next actions. Refreshing asks for current prepared information; navigation cards only navigate and never execute backend work.", ["Workspace ready / Review recommended / Showing saved information", "Recommended next action and Apps, Devices, and Backups shortcuts", "Workspace device, capacity, processor, temperature, storage, memory, health, database, and activity where rendered", "Workspace readiness, ready count, Private by design, service cards, and current-versus-saved information", "System Update source and installed-files verification, last checked, and lifecycle status"], [("Workspace summary", "Hero and stat cards", "Shows prepared workspace information", "When a projection is available", "Opens the relevant tab when selected", "A rendered current or saved label", "Projection may be unavailable or saved"), ("Refresh", "Home", "Requests current prepared information", "When the control is enabled", "Updates the displayed projection", "Freshness/status message", "Read or service state may be unavailable"), ("Check now", "System Update", "Requests update verification", "When update checks are supported", "Shows checking or a result", "Source and installed-files verification status", "Connectivity or update service is unavailable"), ("Install Update", "System Update", "Requests a supported update install", "Only when an update is available", "Downloading → preparing → installing → validating or safely rolling back", "Installed from source or completed state", "No update, maintenance guard, or failed verification")], ["Review Workspace ready or Review recommended before taking an action.", "Use Apps, Devices, or Backups shortcuts to continue in their dedicated tabs.", "Check now, then read update available, checking, downloading, preparing, installing, validating, rolling back safely, or update failed honestly."], "Saved-status-only information is informative, not proof that an update action can run.", "System Update status is backend-owned. Source and installed-files verification do not expose credentials, private paths, or raw runtime payloads.", "[Feature Journeys](../enterprise/hubs/use.md#feature-journeys) describe the backend-owned flow for each shortcut.", "[Current Lite tabs](tabs.md) · [Release and upgrade](upgrade.md) · [Security boundaries](security-boundaries.md)")
    outputs[PROD / "devices.md"] = user_guide(source_commit, "Devices", "Devices manages the server host and enrolled devices through backend-generated invitations, identity guards, agents, supervisors, and truthful prepared state.", ["Refresh and Connected now", "online / total / health-attention counts", "Remote access ready or Remote access not ready; Tailscale IP only when ready", "Add a device disclosure, invite, device cards, details, model/type control, restart and retirement controls"], [("Refresh", "Devices header", "Refreshes prepared device state", "When reads are available", "Updates counts and cards", "Fresh state label", "Backend read unavailable"), ("Add Device", "Add a device", "Prepares a bounded invite", "After device name and role validation", "Shows hostname, role, expiry, Connect this device and Copy command", "Preparing invite / copied / invite details", "Reconnect to continue, duplicate name, or device already added"), ("Role selector", "Add a device", "Chooses a currently emitted device role", "During invite preparation", "Role is included in the invite request", "Invite displays selected role", "Role/name validation fails"), ("Restart Agent", "Device details", "Requests supervised agent recovery", "For an eligible enrolled device", "Preparing request → private channel → device agent → back online", "Completed or fresh heartbeat", "Waiting, stopped, repairing, failed, or command undeliverable"), ("Remove Old Device", "Device details", "Assesses and requests explicit retirement", "After dependency and protected-host checks", "Confirmation and recovery assessment", "Removal outcome and audit evidence", "Hosted apps/backups, stale assessment, delivery failure, or protected server host")], ["Add a named device, copy the backend-generated bootstrap command, and wait for safe acceptance and heartbeat.", "Use Remote access only after its ready state is shown.", "Read status glossary: Online, Joining, Waiting, Offline, Agent stopped, Repairing, Remote access not ready, and Protected server host."], "A disconnected running agent follows reconnect/watchdog recovery; a stopped agent requires supervisor recovery; stopped without a supervisor results in guidance, not fabricated delivery.", "Duplicate names/identities are protected case- and separator-insensitively. Identity mismatch fails closed: no environment overwrite or PM2 restart. Bootstrap material is never reproduced in this guide.", "[Devices Feature Journey](../enterprise/journeys/devices.md)", "[Device onboarding architecture](architecture/device-onboarding.md) · [Remote access](remote-access.md) · [Troubleshooting](troubleshooting.md)")
    outputs[PROD / "apps.md"] = user_guide(source_commit, "Apps", "Apps is the supported App Catalog and PhotoPrism lifecycle surface. Each action is a FastAPI request; browser UI never runs PM2, Caddy, storage, backup, repair, or scanner commands.", ["Open and Manage", "PhotoPrism actions and Manage sections: Photos, Safety, Recovery, App setup, Remove", "Phone-photo and storage-device sources", "Ready, Connected, Imported, Getting ready, Working, Done, Needs attention, Paused for safety, Not available, Waiting, Not ready, and Installed"], [("Open", "App card", "Navigates to the same-origin installed app route", "When installed and route-ready", "Opens the app", "App route loads", "App not installed or route not ready"), ("Manage", "App card", "Opens supported management sections", "For a catalog app", "Shows Photos, Safety, Recovery, setup, or removal controls", "Visible management state", "App state does not support the section"), ("Connect photos / Import photos", "Photos", "Requests supported media connection/import", "After source selection", "Backend-owned progress", "Connected / Imported", "Source or safety prerequisite unavailable"), ("Back up app / Check app / Preview restore / Back up to storage device", "Recovery and Safety", "Requests bounded recovery/safety work", "When app and target prerequisites are met", "Progress and sanitized evidence", "Done or verification evidence", "Waiting, paused for safety, or needs attention"), ("Install / Update / Repair / Remove app", "App actions", "Requests lifecycle work", "When the action is allowed", "Backend execution and progress", "Installed or completed state", "Prerequisite, policy, or recovery guard")], ["Open an installed app for its own user experience.", "Manage PhotoPrism to select sources and request an action, then follow progress and recovery evidence.", "Use status chips to distinguish working from complete or blocked."], "Not available, Waiting, Not ready, and Paused for safety are truthful states; retry only after the stated prerequisite or recovery path is resolved.", "App requests remain same-origin through FastAPI and backend services. Media, raw logs, secrets, and private paths are not exposed by this documentation.", "[Apps Feature Journey](../enterprise/journeys/apps.md)", "[Apps architecture](architecture/apps.md) · [Backup & Restore](recovery.md) · [Security boundaries](security-boundaries.md)")
    outputs[PROD / "security.md"] = user_guide(source_commit, "Security & Safety", "Security & Safety runs bounded Quick Safety Check, Full Local Check, and PhotoPrism App Check profiles through FastAPI, NATS/JetStream, and workers, then presents normalized and sanitized results.", ["Quick Scan / Quick Safety Check for the default low-power scope", "Full Scan / Full Local Check for explicit deeper local review", "App Scan / PhotoPrism App Check where enabled", "Safety Center Manage sections: Overview, Changes, Issues, Check path, Evidence, History, Technical details"], [("Choose scan", "Security header", "Requests the selected profile", "When the profile is enabled", "Shows progress and execution stages", "Completion or review state", "Profile unavailable or preflight fails"), ("Show check path", "Safety Center", "Reveals the bounded execution path", "When a result exists", "Expands details", "Visible path", "No result is available"), ("Open history / Open all review items", "Safety Center", "Navigates to retained summaries", "When history/findings exist", "Shows reviewable normalized items", "Rows and timestamps", "No retained items"), ("View evidence / finding details", "Result cards", "Shows sanitized evidence and details", "When evidence is retained", "Expands bounded detail", "Normalized finding", "Raw payload, secrets, media, or private paths are excluded"), ("Protection dashboard / Execution timeline", "Manage", "Shows summarized protection and stages", "When supported", "Displays status progression", "Completion/review/failure state", "No execution evidence")], ["Use Quick for the default low-power check; use Full only when deeper local scope is needed; use App Scan for supported PhotoPrism checks.", "Review completion, findings, evidence, and history rather than interpreting raw scanner output."], "Failure or skipped content is reported as such. Photos/media, secrets, private paths, raw scanner payloads, and raw logs remain excluded.", "The UI cannot run a scanner directly. Findings are normalized and sanitized after backend/worker execution.", "[Security & Safety Feature Journey](../enterprise/journeys/security.md)", "[Security architecture](architecture/security.md) · [Security boundaries](security-boundaries.md)")
    outputs[PROD / "recovery.md"] = user_guide(source_commit, "Backup & Restore", "Backup & Restore manages a guarded sequence: Backup → Verified → Preview → Checkpoint → Restored. A backup is not automatically verified, and saved state never authorizes a write.", ["Backup readiness, history/restore points, app backups, targets, evidence and copy controls", "Backup, verification, non-mutating preview, explicit restore confirmation", "Maintenance lock, unresolved-restore guard, active restore, historical preview, and projection reconciliation states"], [("Backup Now", "Recovery", "Requests a backup", "When target and guards allow", "Backend/worker creates a backup", "Backup entry", "Target, lock, or stale projection guard"), ("Verify Backup", "Backup detail", "Requests verification", "When a backup exists", "Produces verification evidence", "Verified state", "Backup unavailable or verification failure"), ("Preview Restore", "Recovery", "Requests a non-mutating preview", "When a restore point exists", "Shows planned restore evidence", "Preview result", "Historical/projection state unavailable"), ("Restore Latest", "Recovery", "Requests confirmed restore", "After confirmation and guards", "Checkpoint → restore → service restart → health validation", "Restored and health evidence", "Maintenance lock, unresolved guard, active restore, or validation failure"), ("Manage / details / copy evidence", "Recovery cards", "Opens details or copies bounded evidence", "When an item exists", "Shows retained status", "Visible evidence", "No safe evidence available")], ["Create a backup, verify it, and use Preview Restore before a confirmed restore.", "Read restore points and app-backup/target details before acting.", "Resolve stale/saved projection status before retrying a write."], "Active restore, maintenance locks, unresolved guards, and stale projection write blocking are safety controls, not successful completion.", "Restore is backend/worker-owned, requires confirmation and a pre-restore checkpoint, and ends with post-restore health validation. The browser cannot write backup storage directly.", "[Backup & Restore Feature Journey](../enterprise/journeys/recovery.md)", "[Backup/recovery architecture](architecture/backup-recovery.md) · [Security boundaries](security-boundaries.md)")
    outputs[PROD / "identity.md"] = user_guide(source_commit, "Identity & Access", "Identity & Access owns local human credentials, passkeys, sessions, recovery codes, purpose-bound step-up, and safe identity-class visibility. Opt-in Enterprise Mode uses server-owned memberships and roles. Device identities and the separate API-token path remain outside this tab.", ["Personal Mode owner claim/connect link, passkey and Advanced setup fallback", "Sign-in with passkey, password, advanced sign-in, and recovery access", "Passkeys, password, recovery codes, active sessions and Sign Out", "Enterprise Mode: Your access, current server-resolved role, People, activity, role/status and Active/Inactive"], [("Create your passkey / Add passkey", "Owner claim and Passkeys", "Starts WebAuthn registration", "HTTPS/WebAuthn requirements and eligible session", "Server verifies a one-use challenge", "Completed passkey state", "Browser, origin, RP ID, or challenge constraint"), ("Sign in with passkey / password / advanced sign-in / Recover access", "Sign-in", "Requests supported authentication or recovery", "When the required credential/recovery code exists", "Server creates/updates a session", "Server accepted / Verifying / Completed", "Preparing, Waiting for Pocket Lab, Blocked, or Failed"), ("Rename / Save rename / Revoke", "Passkeys", "Changes friendly name or revokes a passkey", "For an owned passkey", "Server validates and audits change", "Updated passkey list", "Step-up or final-access safety constraint"), ("Change Password", "Password", "Changes the local password", "With current password and valid session", "Affected sessions are revoked", "Completed status", "Current-password or policy validation failure"), ("Generate/regenerate recovery codes", "Recovery", "Creates a one-time recovery-code batch", "For an eligible owner", "Displays/copies once; regeneration invalidates prior batch", "Confirmed generation", "Session/authorization constraint"), ("Revoke / Sign Out", "Sessions", "Revokes a session or signs out", "For an active session", "Server invalidates session", "Session no longer active", "Final-owner or current-session constraints"), ("Enable Enterprise Mode / Save", "Enterprise", "Requests opt-in mode or membership change", "Only when exposed and authorized", "Server resolves role/status", "Updated People/activity", "Final active Owner protection or authorization")], ["First owner: claim/connect, create a passkey, choose owner/display/friendly names where offered, or use Advanced setup.", "Sign in and manage passkeys, password, recovery codes, and active sessions.", "In Enterprise Mode, read the server-resolved role; role names Owner, Admin, Operator, Auditor, and Viewer do not themselves document permissions."], "Blocked, Failed, and Waiting for Pocket Lab do not create access. The final active Owner cannot be removed or demoted.", "Passwords, recovery codes, authenticator material, challenges, and session credentials are never printed. WebAuthn validates origin, RP ID, and one-use challenges; browser storage is not authoritative.", "[Identity & Access Feature Journey](../enterprise/journeys/identity.md)", "[Identity guards](architecture/components/api-guards.md) · [Security boundaries](security-boundaries.md)")
    outputs[PROD / "rules.md"] = user_guide(source_commit, "Rules", "Rules presents bounded policy governance for registered protected actions. FastAPI keeps authority and applies domain invariants before its loopback-only OPA consultation; the browser never calls OPA.", ["Personal Safety Rules posture, protections, safe templates, active/available rules, diagnostics and sanitized recent decisions", "Enterprise tabs: Active Rules, Simulate, Decisions, Approvals, Exceptions, Health", "Readiness, active/known-good/runtime-observed revision, degraded state and uncertain recovery where exposed"], [("Copy revision", "Active Rules", "Copies the displayed revision", "When a revision is visible", "Copies display text only", "Copied feedback", "No revision present"), ("Run Simulation", "Simulate", "Requests a non-executing evaluation", "With revision, action, target and mode", "Returns allow/block/step-up, constraints and technical reason", "Simulation result", "Invalid scenario or unavailable policy"), ("Approve / Reject / Cancel", "Approvals", "Reviews a bounded approval request", "For an eligible independent reviewer", "Passkey step-up and approval status change", "Recorded approval outcome", "Initiator cannot self-approve, step-up fails, expiry, or cancellation"), ("Create exception / Revoke", "Exceptions", "Requests an exact temporary exception or its revocation", "For allowed app/device/human/revision scope", "Server records expiry and revision binding", "Visible exception status", "Role restriction, unsupported scope, or expiry"), ("Decision filters / details", "Decisions", "Filters and expands bounded decision evidence", "When decisions exist", "Shows action, target, reason, time and sanitized metadata", "Visible decision row", "No matching evidence")], ["Personal Mode: review protections, diagnostics (engine, runtime, network boundary, package/revision, reason code), and recent allowed/blocked decisions.", "Enterprise: inspect revisions, use non-executing simulation, review decisions/approvals/exceptions/health.", "After a valid one-use approval continuation, the requester retries the exact protected action."], "Degraded, uncertain recovery, unavailable policy, insufficient role/assurance, and blocked decisions fail closed. Approval does not execute the protected action.", "OPA is loopback-only and additive to FastAPI domain invariants. Evidence excludes raw policy input, command payloads, credentials, secrets, and private paths.", "[Rules Feature Journey](../enterprise/journeys/rules.md)", "[OPA policy-engine architecture](architecture/components/opa-policy-engine.md) · [Security boundaries](security-boundaries.md)")
    return outputs


def manifest_for(audience: str, outputs: dict[Path, str]) -> tuple[Path, str]:
    fingerprints = source_fingerprints()
    base = DEV if audience == "development" else PROD
    generated_files = sorted(path.relative_to(ROOT).as_posix() for path in outputs if path.is_relative_to(base))
    if audience == "development":
        generated_files.extend(sorted(
            path.relative_to(ROOT).as_posix()
            for path in [
                ROOT / "docs/generated/development/api-contract.md",
                ROOT / "docs/generated/development/api-compatibility.md",
                ROOT / "docs/generated/development/frontend-api-usage.md",
            ]
            if path.exists()
        ))
    payload = {
        "schema_revision": 1,
        "generated": True,
        "audience": audience,
        "source_commit": commit(),
        "generated_at": generated_at(),
        "generator": "scripts/docs/lite/generate_docs.py",
        "source_fingerprint": aggregate_fingerprint(fingerprints),
        "source_fingerprints": fingerprints,
        "validation_status": "generated",
        "generated_files": sorted(set(generated_files)),
    }
    return base / "manifest.json", json.dumps(payload, indent=2, sort_keys=True) + "\n"


def outputs_for(audience: str) -> dict[Path, str]:
    source_commit = commit()
    outputs: dict[Path, str] = {}
    if audience in {"development", "all"}:
        dev_outputs = development_outputs(source_commit)
        outputs.update(dev_outputs)
        path, content = manifest_for("development", dev_outputs)
        outputs[path] = content
    if audience in {"production", "all"}:
        prod_outputs = production_outputs(source_commit)
        outputs.update(prod_outputs)
        path, content = manifest_for("production", prod_outputs)
        outputs[path] = content
    return outputs


def write_outputs(outputs: dict[Path, str]) -> None:
    for path, content in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def validate_safe(outputs: dict[Path, str]) -> list[str]:
    failures = []
    required = [
        "generated: true", "audience:", "source_commit:", "generated_at:",
        "generator:", "source_fingerprint:", "schema_revision:", "validation_status:",
    ]
    for path, content in outputs.items():
        if FORBIDDEN.search(content):
            failures.append(path.relative_to(ROOT).as_posix())
        if path.suffix == ".md":
            missing = [field for field in required if field not in content]
            if missing:
                failures.append(path.relative_to(ROOT).as_posix() + " (missing metadata: " + ", ".join(missing) + ")")
    return failures


def check_outputs(outputs: dict[Path, str]) -> int:
    drift: list[str] = []
    with tempfile.TemporaryDirectory(prefix="pocketlab-lite-docs-") as temp_name:
        temp_root = Path(temp_name)
        for path, content in outputs.items():
            relative = path.relative_to(ROOT)
            candidate = temp_root / relative
            candidate.parent.mkdir(parents=True, exist_ok=True)
            candidate.write_text(content, encoding="utf-8")
            if not path.exists() or path.read_text(encoding="utf-8") != candidate.read_text(encoding="utf-8"):
                drift.append(relative.as_posix())
    unsafe = validate_safe(outputs)
    if drift:
        print("Generated documentation drift:")
        for path in drift:
            print(" -", path)
    if unsafe:
        print("Unsafe or incomplete generated documentation:")
        for path in unsafe:
            print(" -", path)
    if drift or unsafe:
        return 1
    print(f"PASS {len(outputs)} generated documentation pages are current and sanitized")
    return 0


def check_storybook() -> int:
    required = {
        "LiteHome": 9, "LiteDevices": 14, "LiteCatalog": 10,
        "LiteRecovery": 12, "LiteSecurity": 11, "LiteIdentity": 6, "LiteRules": 8,
    }
    inventory = story_inventory()
    failures = []
    for key, minimum in required.items():
        count = len(inventory.get(key, []))
        if count < minimum:
            failures.append(f"{key}: expected at least {minimum}, found {count}")
    if failures:
        print("Storybook inventory failures:")
        print("\n".join(f" - {item}" for item in failures))
        return 1
    print(f"PASS Storybook documents all seven Lite tabs with {sum(map(len, inventory.values()))} canonical stories")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["generate", "check", "check-storybook"])
    parser.add_argument("--audience", choices=["development", "production", "all"], default="all")
    args = parser.parse_args()
    if args.command == "check-storybook":
        return check_storybook()
    outputs = outputs_for(args.audience)
    if args.command == "generate":
        write_outputs(outputs)
        failures = validate_safe(outputs)
        if failures:
            print("Generated unsafe documentation:", failures, file=sys.stderr)
            return 1
        print(f"Generated {len(outputs)} {args.audience} documentation pages")
        return 0
    return check_outputs(outputs)


if __name__ == "__main__":
    raise SystemExit(main())
