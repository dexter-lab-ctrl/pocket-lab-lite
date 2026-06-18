#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
GENERATED_DIR = ROOT / "docs/validation/generated"
ALLURE_RESULTS_DIR = GENERATED_DIR / "allure-results"
ALLURE_HISTORY_DIR = GENERATED_DIR / "allure-history"
COMMAND_RESULTS_DIR = ROOT / ".pocketlab-dev/validation/command-results"
MANIFEST_JSON = GENERATED_DIR / "validation-manifest.json"
EVIDENCE_JSON = GENERATED_DIR / "validation-evidence.json"
READINESS_JSON = GENERATED_DIR / "release-readiness.json"
BUNDLE_JSON = GENERATED_DIR / "validation-evidence-bundle.json"
INDEX_MD = GENERATED_DIR / "index.md"
READINESS_MD = ROOT / "docs/validation/readiness-matrix.md"
STRATEGY_MD = ROOT / "docs/validation/test-strategy-quality-gates.md"

RETIRED_PATTERNS = [
    "legacy" + "_" + "intent",
    "sync" + "_" + "bash",
    "tofu" + "_" + "deploy",
    "/" + "api" + "/" + "action" + "/" + "update",
    "dashboard" + "_" + "api",
]

STATUS_ORDER = {"PASS": 0, "WARNING": 1, "BLOCKED": 2, "FAIL": 3}
ALLURE_STATUS = {
    "PASS": "passed",
    "WARNING": "skipped",
    "BLOCKED": "broken",
    "FAIL": "failed",
}


@dataclass(frozen=True)
class GateDefinition:
    id: str
    title: str
    command: str
    category: str
    owner: str
    release_requirement: str
    blocking: bool
    evidence_patterns: tuple[str, ...] = ()
    coverage: tuple[str, ...] = ()
    notes: str = ""


@dataclass
class GateEvidence:
    id: str
    title: str
    category: str
    command: str
    owner: str
    release_requirement: str
    blocking: bool
    status: str
    evidence_state: str
    summary: str
    evidence: list[str] = field(default_factory=list)
    coverage: list[str] = field(default_factory=list)
    source: str = "repository"
    started_at: str | None = None
    finished_at: str | None = None
    exit_code: int | None = None
    remediation: str = ""


def now_iso() -> str:
    if epoch := os.environ.get("SOURCE_DATE_EPOCH"):
        try:
            return datetime.fromtimestamp(int(epoch), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            pass
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def clean_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", "<br>")


def table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join(["---"] * len(headers)) + "|",
    ]
    for row in rows:
        lines.append("| " + " | ".join(clean_cell(cell) for cell in row) + " |")
    return "\n".join(lines)


def gates() -> list[GateDefinition]:
    return [
        GateDefinition(
            id="docs-api",
            title="OpenAPI backend contract",
            command="task docs:api",
            category="Contract",
            owner="Backend",
            release_requirement="Required",
            blocking=True,
            evidence_patterns=("contracts/generated/openapi.json", "contracts/openapi.json"),
            coverage=("FastAPI route contract", "Redocly API lint", "frontend/backend integration evidence"),
        ),
        GateDefinition(
            id="docs-events",
            title="NATS / JetStream AsyncAPI contract",
            command="task docs:events",
            category="Contract",
            owner="Runtime",
            release_requirement="Required",
            blocking=True,
            evidence_patterns=(
                "contracts/asyncapi/pocketlab-nats-jetstream.yaml",
                "docs/runtime/generated/nats-jetstream-asyncapi/index.html",
            ),
            coverage=("NATS subjects", "JetStream streams", "audit and DLQ events"),
        ),
        GateDefinition(
            id="docs-operations",
            title="Typed Operations catalog",
            command="task docs:operations",
            category="Contract",
            owner="Runtime",
            release_requirement="Required",
            blocking=True,
            evidence_patterns=(
                "contracts/operations/pocketlab-typed-operations.json",
                "docs/runtime/generated/typed-operations-catalog/index.html",
            ),
            coverage=("typed operation registry", "UI entrypoints", "NATS subjects", "operation safety metadata"),
        ),
        GateDefinition(
            id="docs-architecture",
            title="Structurizr architecture-as-code",
            command="task docs:architecture",
            category="Architecture",
            owner="Architecture",
            release_requirement="Required",
            blocking=True,
            evidence_patterns=("architecture/structurizr/workspace.dsl", "docs/architecture/structurizr-architecture.md"),
            coverage=("C4 workspace", "security-review views", "runtime flow diagrams"),
        ),
        GateDefinition(
            id="docs-threat-model",
            title="Threat model validation",
            command="task docs:threat-model:check",
            category="Security",
            owner="Security",
            release_requirement="Required",
            blocking=True,
            evidence_patterns=(
                "threat-model/pocketlab-threat-model.yaml",
                "threat-model/pocketlab-threat-model-drift-manifest.json",
                "threat-model/pocketlab-threat-model-sync-manifest.json",
                "docs/security/security-architecture-threat-model.md",
            ),
            coverage=("threat metadata", "drift evidence", "source synchronization evidence"),
        ),
        GateDefinition(
            id="docs-runbooks",
            title="Runbook catalog, docs, and validation gates",
            command="task docs:runbooks:full-check",
            category="Operations",
            owner="Operations",
            release_requirement="Required",
            blocking=True,
            evidence_patterns=(
                "docs/operations/generated/runbooks/runbook-catalog.json",
                "docs/operations/generated/runbooks/runbook-validation-gates.json",
                "docs/operations/generated/runbooks/validation-gates.md",
            ),
            coverage=("native runbooks", "approval metadata", "evidence matrix", "typed operation mapping"),
        ),
        GateDefinition(
            id="mkdocs-build",
            title="MkDocs strict documentation build",
            command="mkdocs build --strict",
            category="Documentation",
            owner="Docs",
            release_requirement="Required",
            blocking=True,
            evidence_patterns=("site/index.html",),
            coverage=("documentation navigation", "generated pages", "strict link validation"),
        ),
        GateDefinition(
            id="pytest-backend",
            title="Backend pytest evidence",
            command="task test:backend",
            category="Test",
            owner="Backend",
            release_requirement="Required",
            blocking=True,
            evidence_patterns=(
                ".pocketlab-dev/validation/pytest-backend.xml",
                ".pocketlab-dev/validation/pytest.xml",
            ),
            coverage=("FastAPI routes", "runtime services", "runbook engine", "state and reliability tests"),
        ),
        GateDefinition(
            id="pytest-performance",
            title="Performance smoke pytest evidence",
            command="task test:performance",
            category="Performance",
            owner="Platform",
            release_requirement="Required",
            blocking=True,
            evidence_patterns=(".pocketlab-dev/validation/pytest-performance.xml",),
            coverage=("edge performance smoke budgets", "lightweight runtime assumptions"),
        ),
        GateDefinition(
            id="playwright-e2e",
            title="Playwright browser E2E evidence",
            command="task test:e2e",
            category="Test",
            owner="Frontend",
            release_requirement="Required",
            blocking=True,
            evidence_patterns=(
                ".pocketlab-dev/validation/playwright-results.json",
                ".pocketlab-dev/playwright-report/index.html",
                ".pocketlab-dev/test-results",
            ),
            coverage=("PWA operator journeys", "Simple/Professional mode", "backend sync behavior"),
        ),
        GateDefinition(
            id="playwright-visual",
            title="Playwright visual regression evidence",
            command="task test:visual",
            category="UI",
            owner="Frontend",
            release_requirement="Required",
            blocking=True,
            evidence_patterns=(
                ".pocketlab-dev/test-results",
                "tests/e2e/visual-regression.spec.ts-snapshots/app-shell-chromium-linux.png",
            ),
            coverage=("visual baseline", "app shell rendering"),
        ),
        GateDefinition(
            id="playwright-a11y",
            title="Accessibility evidence",
            command="task test:a11y",
            category="Accessibility",
            owner="Frontend",
            release_requirement="Required",
            blocking=True,
            evidence_patterns=(".pocketlab-dev/validation/playwright-results.json", ".pocketlab-dev/test-results"),
            coverage=("critical accessibility journeys", "keyboard/screen-reader regressions"),
        ),
        GateDefinition(
            id="playwright-network",
            title="Frontend network contract evidence",
            command="task test:network",
            category="Contract",
            owner="Frontend",
            release_requirement="Required",
            blocking=True,
            evidence_patterns=(".pocketlab-dev/validation/playwright-results.json", ".pocketlab-dev/test-results"),
            coverage=("typed frontend write payloads", "no direct NATS", "no direct shell execution"),
        ),
        GateDefinition(
            id="lighthouse",
            title="Lighthouse PWA quality evidence",
            command="task test:lighthouse",
            category="Performance",
            owner="Frontend",
            release_requirement="Required",
            blocking=True,
            evidence_patterns=(
                ".pocketlab-dev/lighthouse/manifest.json",
                ".pocketlab-dev/lighthouse/*.report.json",
                ".pocketlab-dev/lighthouse/*.html",
            ),
            coverage=("PWA quality", "performance", "accessibility", "best practices", "SEO"),
        ),
        GateDefinition(
            id="nats-runtime",
            title="NATS / JetStream runtime stack evidence",
            command="task test:nats",
            category="Runtime",
            owner="Runtime",
            release_requirement="Required",
            blocking=True,
            evidence_patterns=(".pocketlab-dev/state", ".pocketlab-dev/logs"),
            coverage=("FastAPI → NATS → Worker", "typed operation events", "journal evidence"),
        ),
        GateDefinition(
            id="nats-permissions",
            title="NATS subject permission evidence",
            command="task test:nats-permissions",
            category="Security",
            owner="Runtime",
            release_requirement="Required",
            blocking=True,
            evidence_patterns=(".pocketlab-dev/validation/command-results/nats-permissions.json",),
            coverage=("API subject permissions", "worker subject permissions", "fleet subject boundaries"),
        ),
        GateDefinition(
            id="redaction",
            title="Secret redaction evidence",
            command="task test:redaction",
            category="Security",
            owner="Security",
            release_requirement="Required",
            blocking=True,
            evidence_patterns=(".pocketlab-dev/validation/command-results/redaction.json",),
            coverage=("event journal redaction", "audit evidence redaction", "UI-visible log safety"),
        ),
        GateDefinition(
            id="faults",
            title="Fault and degraded-mode evidence",
            command="task test:faults",
            category="Reliability",
            owner="Platform",
            release_requirement="Required",
            blocking=True,
            evidence_patterns=(".pocketlab-dev/validation/command-results/faults.json",),
            coverage=("NATS down", "worker degraded", "health failure", "fail-closed behavior"),
        ),
        GateDefinition(
            id="flakes",
            title="Flaky-test stability evidence",
            command="task test:flakes",
            category="Reliability",
            owner="QA",
            release_requirement="Required",
            blocking=True,
            evidence_patterns=(
                ".pocketlab-dev/reports/flakes/flaky-tests.json",
                ".pocketlab-dev/reports/flakes/flaky-tests.md",
            ),
            coverage=("no focused tests", "no hidden skip/fixme", "repeated high-signal Playwright stability"),
        ),
        GateDefinition(
            id="android-smoke",
            title="Android / Termux edge smoke evidence",
            command="task android:smoke",
            category="Platform",
            owner="Platform",
            release_requirement="Required before edge release",
            blocking=False,
            evidence_patterns=(".pocketlab-dev/validation/command-results/android-smoke.json",),
            coverage=("Android/Termux assumptions", "ARM64 edge runtime readiness"),
        ),
        GateDefinition(
            id="release-dry-run",
            title="Release dry-run evidence",
            command="task release:dry-run",
            category="Release",
            owner="Release Engineering",
            release_requirement="Required before tag/release",
            blocking=True,
            evidence_patterns=(".pocketlab-dev/validation/command-results/release-dry-run.json",),
            coverage=("release artifact workflow", "upgrade readiness", "packaging checks"),
        ),
    ]


def expand_patterns(patterns: tuple[str, ...]) -> list[Path]:
    found: list[Path] = []
    for pattern in patterns:
        matches = sorted(ROOT.glob(pattern))
        found.extend(path for path in matches if path.exists())
    deduped: list[Path] = []
    seen: set[Path] = set()
    for path in found:
        if path not in seen:
            deduped.append(path)
            seen.add(path)
    return deduped


def command_result_path(gate_id: str) -> Path:
    return COMMAND_RESULTS_DIR / f"{gate_id}.json"


def parse_command_result(gate: GateDefinition) -> GateEvidence | None:
    path = command_result_path(gate.id)
    if not path.exists():
        return None

    try:
        data = read_json(path)
    except Exception as exc:
        return GateEvidence(
            id=gate.id,
            title=gate.title,
            category=gate.category,
            command=gate.command,
            owner=gate.owner,
            release_requirement=gate.release_requirement,
            blocking=gate.blocking,
            status="FAIL" if gate.blocking else "WARNING",
            evidence_state="invalid-command-result",
            summary=f"Command result exists but could not be parsed: {exc}",
            evidence=[rel(path)],
            coverage=list(gate.coverage),
            source="command-result",
            remediation=f"Re-run `{gate.command}` through scripts/docs/record_validation_result.py.",
        )

    exit_code = data.get("exit_code")
    status = "PASS" if exit_code == 0 else "FAIL"
    evidence = [rel(path)]
    for key in ("stdout_log", "stderr_log", "combined_log"):
        value = data.get(key)
        if value and (ROOT / value).exists():
            evidence.append(value)

    return GateEvidence(
        id=gate.id,
        title=gate.title,
        category=gate.category,
        command=data.get("command_display") or gate.command,
        owner=gate.owner,
        release_requirement=gate.release_requirement,
        blocking=gate.blocking,
        status=status,
        evidence_state="executed-command",
        summary="Recorded command completed successfully." if status == "PASS" else f"Recorded command failed with exit code {exit_code}.",
        evidence=evidence,
        coverage=list(gate.coverage),
        source="command-result",
        started_at=data.get("started_at"),
        finished_at=data.get("finished_at"),
        exit_code=exit_code,
        remediation="Review the command log and rerun after fixing the failing gate." if status == "FAIL" else "",
    )


def parse_junit(path: Path) -> tuple[str, str]:
    try:
        root = ET.fromstring(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception as exc:
        return "FAIL", f"Unable to parse JUnit XML: {exc}"

    tests = int(float(root.attrib.get("tests", 0)))
    failures = int(float(root.attrib.get("failures", 0)))
    errors = int(float(root.attrib.get("errors", 0)))
    skipped = int(float(root.attrib.get("skipped", 0)))
    if failures or errors:
        return "FAIL", f"JUnit evidence reports tests={tests}, failures={failures}, errors={errors}, skipped={skipped}."
    if tests == 0:
        return "WARNING", "JUnit evidence exists but reports zero tests."
    if skipped:
        return "WARNING", f"JUnit evidence passed with skipped tests: tests={tests}, skipped={skipped}."
    return "PASS", f"JUnit evidence passed: tests={tests}, failures=0, errors=0."


def parse_playwright(path: Path) -> tuple[str, str]:
    try:
        data = read_json(path)
    except Exception as exc:
        return "FAIL", f"Unable to parse Playwright JSON: {exc}"
    stats = data.get("stats", {})
    unexpected = int(stats.get("unexpected", 0) or 0)
    flaky = int(stats.get("flaky", 0) or 0)
    skipped = int(stats.get("skipped", 0) or 0)
    expected = int(stats.get("expected", 0) or 0)
    if unexpected:
        return "FAIL", f"Playwright evidence reports expected={expected}, unexpected={unexpected}, flaky={flaky}, skipped={skipped}."
    if flaky or skipped:
        return "WARNING", f"Playwright evidence passed with expected={expected}, flaky={flaky}, skipped={skipped}."
    if expected == 0:
        return "WARNING", "Playwright evidence exists but reports zero expected tests."
    return "PASS", f"Playwright evidence passed: expected={expected}, unexpected=0."


def parse_lighthouse(paths: list[Path]) -> tuple[str, str]:
    manifest = next((p for p in paths if p.name == "manifest.json"), None)
    reports = [p for p in paths if p.name.endswith(".report.json")]
    if not manifest and not reports:
        return "WARNING", "Lighthouse output directory exists but no machine-readable report was found."

    failures = 0
    warnings = 0
    details: list[str] = []
    for report in reports[:3]:
        try:
            data = read_json(report)
        except Exception as exc:
            return "FAIL", f"Unable to parse Lighthouse report {rel(report)}: {exc}"
        categories = data.get("categories", {})
        for name in ("performance", "accessibility", "best-practices", "seo"):
            score = categories.get(name, {}).get("score")
            if score is None:
                warnings += 1
                continue
            pct = round(float(score) * 100)
            details.append(f"{name}={pct}")
            if name == "performance" and score < 0.7:
                failures += 1
            elif name in {"accessibility", "best-practices"} and score < 0.9:
                warnings += 1
            elif name == "seo" and score < 0.8:
                warnings += 1
    if failures:
        return "FAIL", "Lighthouse performance score is below release budget: " + ", ".join(details)
    if warnings:
        return "WARNING", "Lighthouse evidence has advisory findings: " + ", ".join(details)
    return "PASS", "Lighthouse evidence passed: " + (", ".join(details) if details else rel(manifest) if manifest else "report available")


def parse_flake_report(path: Path) -> tuple[str, str]:
    try:
        data = read_json(path)
    except Exception as exc:
        return "FAIL", f"Unable to parse flaky-test report: {exc}"
    status = str(data.get("status", "")).lower()
    if status == "passed":
        return "PASS", "Flaky-test evidence passed."
    return "FAIL", "Flaky-test evidence failed or is inconclusive."


def evidence_from_artifacts(gate: GateDefinition, paths: list[Path]) -> tuple[str, str, str]:
    if not paths:
        if gate.blocking:
            return (
                "BLOCKED",
                "missing-execution-evidence",
                "No machine-readable execution evidence found. Run the gate and record it before release readiness can pass.",
            )
        return (
            "WARNING",
            "missing-advisory-evidence",
            "No machine-readable advisory evidence found. This does not block the default release readiness calculation.",
        )

    first = paths[0]
    if first.suffix == ".xml" and "pytest" in first.name:
        status, summary = parse_junit(first)
        return status, "artifact-junit", summary
    if first.name.endswith(".json") and ("playwright" in first.name or "round" in first.name):
        status, summary = parse_playwright(first)
        return status, "artifact-playwright-json", summary
    if first.name == "flaky-tests.json":
        status, summary = parse_flake_report(first)
        return status, "artifact-flake-json", summary
    if "lighthouse" in rel(first):
        status, summary = parse_lighthouse(paths)
        return status, "artifact-lighthouse", summary

    return (
        "WARNING" if gate.blocking else "PASS",
        "repository-artifact",
        "Repository artifact exists, but no recorded command outcome was found. Use the validation recorder for release-grade evidence.",
    )


def build_gate_evidence(gate: GateDefinition) -> GateEvidence:
    if command_result := parse_command_result(gate):
        return command_result

    evidence_paths = expand_patterns(gate.evidence_patterns)
    status, evidence_state, summary = evidence_from_artifacts(gate, evidence_paths)
    return GateEvidence(
        id=gate.id,
        title=gate.title,
        category=gate.category,
        command=gate.command,
        owner=gate.owner,
        release_requirement=gate.release_requirement,
        blocking=gate.blocking,
        status=status,
        evidence_state=evidence_state,
        summary=summary,
        evidence=[rel(path) for path in evidence_paths],
        coverage=list(gate.coverage),
        source="artifact-scan",
        remediation="Run the gate and record evidence with `python3 scripts/docs/record_validation_result.py <gate-id> -- <command>`.",
    )


def source_fingerprint(paths: list[Path]) -> str:
    h = hashlib.sha256()
    for path in sorted(paths):
        if not path.exists() or not path.is_file():
            continue
        h.update(rel(path).encode())
        h.update(b"\0")
        h.update(path.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def fingerprint_sources() -> list[Path]:
    candidates = [
        ROOT / "Taskfile.yml",
        ROOT / "mkdocs.yml",
        ROOT / "playwright.config.ts",
        ROOT / "lighthouserc.json",
        ROOT / "package.json",
        ROOT / "requirements-dev.txt",
    ]
    candidates.extend(sorted((ROOT / "scripts/docs").glob("*.py")))
    candidates.extend(sorted((ROOT / "scripts/dev").glob("*.sh")))
    candidates.extend(sorted((ROOT / "operations").glob("*.yaml")))
    candidates.extend(sorted((ROOT / "runbooks").glob("*.yaml")))
    return [path for path in candidates if path.exists()]


def summarize(evidence: list[GateEvidence]) -> dict[str, Any]:
    summary = {"PASS": 0, "WARNING": 0, "FAIL": 0, "BLOCKED": 0}
    for item in evidence:
        summary[item.status] += 1
    blockers = [item for item in evidence if item.blocking and item.status in {"FAIL", "BLOCKED"}]
    warnings = [item for item in evidence if item.status == "WARNING"]
    if any(item.status == "FAIL" for item in blockers):
        state = "FAIL"
    elif blockers:
        state = "BLOCKED"
    elif warnings:
        state = "WARNING"
    else:
        state = "PASS"
    return {
        "state": state,
        "counts": summary,
        "release_blockers": [asdict(item) for item in blockers],
        "warnings": [asdict(item) for item in warnings],
    }


def build_validation_artifacts() -> dict[str, Any]:
    generated_at = now_iso()
    gate_defs = gates()
    evidence = [build_gate_evidence(gate) for gate in gate_defs]
    sources = fingerprint_sources()
    fp = source_fingerprint(sources)
    readiness = summarize(evidence)

    manifest = {
        "schemaVersion": "pocketlab.validation.v1",
        "tier": "validation evidence and release readiness — Validation Documentation with Allure",
        "generated_at": generated_at,
        "source_fingerprint": fp,
        "source_files": [rel(path) for path in sources],
        "generated_files": [
            rel(MANIFEST_JSON),
            rel(EVIDENCE_JSON),
            rel(READINESS_JSON),
            rel(BUNDLE_JSON),
            rel(INDEX_MD),
            rel(READINESS_MD),
            rel(STRATEGY_MD),
            rel(ALLURE_RESULTS_DIR),
            rel(ALLURE_HISTORY_DIR),
        ],
        "gate_count": len(gate_defs),
        "status_counts": readiness["counts"],
        "release_readiness_state": readiness["state"],
        "principles": [
            "Architecture-as-Code",
            "Documentation-as-Code",
            "Validation-as-Code",
            "Policy-as-Code",
            "Contract-first development",
        ],
    }

    evidence_json = {
        "schemaVersion": "pocketlab.validation.evidence.v1",
        "generated_at": generated_at,
        "source_fingerprint": fp,
        "gates": [asdict(item) for item in evidence],
    }

    readiness_json = {
        "schemaVersion": "pocketlab.release-readiness.v1",
        "generated_at": generated_at,
        "state": readiness["state"],
        "status_counts": readiness["counts"],
        "release_blockers": readiness["release_blockers"],
        "warnings": readiness["warnings"],
        "decision_rule": {
            "PASS": "All blocking gates have recorded pass evidence and there are no advisory warnings.",
            "WARNING": "No blocking failures exist, but advisory warnings or missing advisory evidence remain.",
            "FAIL": "At least one blocking gate has recorded failure evidence.",
            "BLOCKED": "At least one blocking gate is missing release-grade machine-readable execution evidence.",
        },
    }

    bundle = {
        "manifest": manifest,
        "validation_evidence": evidence_json,
        "release_readiness": readiness_json,
    }

    return {
        "manifest": manifest,
        "evidence": evidence_json,
        "readiness": readiness_json,
        "bundle": bundle,
    }


def status_badge(status: str) -> str:
    return {
        "PASS": "✅ PASS",
        "WARNING": "⚠️ WARNING",
        "FAIL": "❌ FAIL",
        "BLOCKED": "⛔ BLOCKED",
    }.get(status, status)


def write_index_md(bundle: dict[str, Any]) -> None:
    evidence = bundle["evidence"]["gates"]
    readiness = bundle["readiness"]
    parts: list[str] = []
    parts.append("# Generated Validation Evidence\n")
    parts.append(
        '!!! note "Generated validation evidence"\n'
        "    This page is generated from validation command results, repository contracts, generated documentation artifacts, and local test outputs. Update validation sources and rerun `task docs:validation:evidence`; do not manually edit generated files.\n"
    )
    parts.append("## Release Readiness\n")
    parts.append(
        table(
            ["Field", "Value"],
            [
                ["State", status_badge(readiness["state"])],
                ["Generated", bundle["manifest"]["generated_at"]],
                ["Gates", bundle["manifest"]["gate_count"]],
                ["PASS", readiness["status_counts"]["PASS"]],
                ["WARNING", readiness["status_counts"]["WARNING"]],
                ["FAIL", readiness["status_counts"]["FAIL"]],
                ["BLOCKED", readiness["status_counts"]["BLOCKED"]],
            ],
        )
    )
    parts.append("\n## Machine-Readable Evidence\n")
    parts.append("- [`validation-manifest.json`](validation-manifest.json)")
    parts.append("- [`validation-evidence.json`](validation-evidence.json)")
    parts.append("- [`release-readiness.json`](release-readiness.json)")
    parts.append("- [`validation-evidence-bundle.json`](validation-evidence-bundle.json)")
    parts.append("- [`allure-results/`](allure-results/)")
    parts.append("- [`allure-history/`](allure-history/)\n")
    parts.append("## Gate Evidence\n")
    parts.append(
        table(
            ["Gate", "Status", "Category", "Command", "Evidence state", "Evidence"],
            [
                [
                    f"`{item['id']}` {item['title']}",
                    status_badge(item["status"]),
                    item["category"],
                    f"`{item['command']}`",
                    item["evidence_state"],
                    "<br>".join(f"`{path}`" for path in item.get("evidence", [])) or "missing",
                ]
                for item in evidence
            ],
        )
    )
    parts.append("\n## Release Blockers\n")
    blockers = readiness.get("release_blockers", [])
    if blockers:
        parts.append(
            table(
                ["Gate", "Status", "Why blocked", "Remediation"],
                [[item["id"], status_badge(item["status"]), item["summary"], item.get("remediation", "")] for item in blockers],
            )
        )
    else:
        parts.append("No release blockers recorded.\n")
    parts.append("\n## Documentation Flow\n")
    parts.append(
        "```text\n"
        "Validation Tools\n"
        "→ Generated Results\n"
        "→ Allure result files\n"
        "→ Generated Evidence\n"
        "→ MkDocs\n"
        "→ Release Readiness\n"
        "```\n"
    )
    INDEX_MD.parent.mkdir(parents=True, exist_ok=True)
    INDEX_MD.write_text("\n".join(parts).rstrip() + "\n", encoding="utf-8")


def write_readiness_md(bundle: dict[str, Any]) -> None:
    evidence = bundle["evidence"]["gates"]
    readiness = bundle["readiness"]
    blockers = readiness.get("release_blockers", [])
    warnings = readiness.get("warnings", [])
    parts: list[str] = []
    parts.append("# Validation / Release Gate Matrix\n")
    parts.append(
        '!!! note "Generated validation readiness matrix"\n'
        "    This page is generated from validation evidence. Update the source gate definitions or run validation commands; do not manually maintain this matrix.\n"
    )
    parts.append("## Current Release Readiness\n")
    parts.append(
        table(
            ["Metric", "Value"],
            [
                ["State", status_badge(readiness["state"])],
                ["Generated", bundle["manifest"]["generated_at"]],
                ["Source fingerprint", f"`{bundle['manifest']['source_fingerprint'][:16]}`"],
                ["Passed checks", readiness["status_counts"]["PASS"]],
                ["Warnings", readiness["status_counts"]["WARNING"]],
                ["Failed checks", readiness["status_counts"]["FAIL"]],
                ["Blocked checks", readiness["status_counts"]["BLOCKED"]],
            ],
        )
    )
    parts.append("\n## Validation Matrix\n")
    parts.append(
        table(
            ["Gate", "Status", "Category", "Owner", "Release Requirement", "Command", "Evidence"],
            [
                [
                    f"`{item['id']}` {item['title']}",
                    status_badge(item["status"]),
                    item["category"],
                    item["owner"],
                    item["release_requirement"],
                    f"`{item['command']}`",
                    "<br>".join(f"`{path}`" for path in item.get("evidence", [])) or "missing",
                ]
                for item in evidence
            ],
        )
    )
    parts.append("\n## Release Blockers\n")
    if blockers:
        parts.append(
            table(
                ["Gate", "Status", "Evidence State", "Summary", "Remediation"],
                [
                    [item["id"], status_badge(item["status"]), item["evidence_state"], item["summary"], item.get("remediation", "")]
                    for item in blockers
                ],
            )
        )
    else:
        parts.append("No release blockers recorded.\n")
    parts.append("\n## Advisory Warnings\n")
    if warnings:
        parts.append(
            table(
                ["Gate", "Evidence State", "Summary"],
                [[item["id"], item["evidence_state"], item["summary"]] for item in warnings],
            )
        )
    else:
        parts.append("No advisory warnings recorded.\n")
    parts.append("\n## Machine-Readable Evidence\n")
    parts.append("- [Generated validation evidence](generated/index.md)")
    parts.append("- [`validation-manifest.json`](generated/validation-manifest.json)")
    parts.append("- [`validation-evidence.json`](generated/validation-evidence.json)")
    parts.append("- [`release-readiness.json`](generated/release-readiness.json)")
    parts.append("- [`validation-evidence-bundle.json`](generated/validation-evidence-bundle.json)")
    parts.append("- [`allure-results/`](generated/allure-results/)\n")
    parts.append("## Decision Rule\n")
    parts.append(
        table(
            ["State", "Meaning"],
            [[state, meaning] for state, meaning in readiness["decision_rule"].items()],
        )
    )
    parts.append("\n## Maintenance Rule\n")
    parts.append(
        "Validation docs are generated from actual command results where available, plus machine-readable repository artifacts. "
        "Before a release, run the release validation gates through `scripts/docs/record_validation_result.py` so the matrix reflects execution evidence instead of artifact presence alone.\n"
    )
    READINESS_MD.parent.mkdir(parents=True, exist_ok=True)
    READINESS_MD.write_text("\n".join(parts).rstrip() + "\n", encoding="utf-8")


def write_strategy_md(bundle: dict[str, Any]) -> None:
    evidence = bundle["evidence"]["gates"]
    parts: list[str] = []
    parts.append("# Test Strategy & Quality Gates Guide\n")
    parts.append(
        '!!! note "Generated validation evidence and release readiness test strategy"\n'
        "    This guide is generated from the validation gate catalog. Update `scripts/docs/validation_evidence_lib.py` when a gate is added, removed, or changes scope.\n"
    )
    parts.append("## Strategy\n")
    parts.append(
        "```mermaid\n"
        "flowchart TB\n"
        "  Contracts[Contracts: OpenAPI / AsyncAPI / Typed Operations] --> Docs[Generated Docs]\n"
        "  Docs --> Backend[Pytest Backend + Runtime]\n"
        "  Backend --> Browser[Playwright UI / Network / Accessibility]\n"
        "  Browser --> Quality[Lighthouse / Performance / Visual]\n"
        "  Quality --> Resilience[Faults / Flakes / NATS Permissions]\n"
        "  Resilience --> Evidence[Allure Results + Evidence Bundle]\n"
        "  Evidence --> Readiness[Release Readiness]\n"
        "```\n"
    )
    parts.append("## Gate Catalog\n")
    parts.append(
        table(
            ["Gate", "Category", "Owner", "Command", "Blocking", "Coverage"],
            [
                [
                    f"`{item['id']}` {item['title']}",
                    item["category"],
                    item["owner"],
                    f"`{item['command']}`",
                    "yes" if item["blocking"] else "no",
                    "<br>".join(item.get("coverage", [])),
                ]
                for item in evidence
            ],
        )
    )
    parts.append("\n## Allure Integration\n")
    parts.append(
        "The validation evidence workflow writes Allure-compatible result files under `docs/validation/generated/allure-results/`. "
        "Run `task docs:validation:allure` to turn those local result files into a static Allure HTML report when the Allure command line is available. Pocket Lab does not require a centralized Allure server.\n"
    )
    parts.append("## Evidence Recording\n")
    parts.append(
        "Use the recorder when running release gates so generated documentation reflects command execution status. Example:\n\n"
        "```bash\n"
        "python3 scripts/docs/record_validation_result.py pytest-backend -- task test:backend\n"
        "python3 scripts/docs/record_validation_result.py playwright-e2e -- task test:e2e\n"
        "task docs:validation:evidence\n"
        "```\n"
    )
    parts.append("## Architecture Boundary\n")
    parts.append(
        "Validation remains build-time/backend-driven. The React PWA does not talk directly to validation systems, Allure, NATS, or shell commands. Release evidence is generated from local artifacts and published through MkDocs.\n"
    )
    STRATEGY_MD.parent.mkdir(parents=True, exist_ok=True)
    STRATEGY_MD.write_text("\n".join(parts).rstrip() + "\n", encoding="utf-8")


def allure_result_for_gate(item: dict[str, Any], generated_at: str) -> dict[str, Any]:
    stable_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"pocketlab-validation:{item['id']}"))
    start_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    return {
        "uuid": stable_uuid,
        "historyId": hashlib.md5(item["id"].encode()).hexdigest(),
        "testCaseId": item["id"],
        "name": item["title"],
        "fullName": f"Pocket Lab Validation::{item['category']}::{item['id']}",
        "status": ALLURE_STATUS.get(item["status"], "broken"),
        "stage": "finished",
        "description": item["summary"],
        "start": start_ms,
        "stop": start_ms,
        "labels": [
            {"name": "epic", "value": "validation evidence and release readiness Validation Documentation"},
            {"name": "feature", "value": item["category"]},
            {"name": "story", "value": item["id"]},
            {"name": "owner", "value": item["owner"]},
            {"name": "severity", "value": "blocker" if item["blocking"] else "minor"},
            {"name": "tag", "value": item["status"]},
        ],
        "parameters": [
            {"name": "command", "value": item["command"]},
            {"name": "evidence_state", "value": item["evidence_state"]},
            {"name": "generated_at", "value": generated_at},
        ],
    }


def write_allure_results(bundle: dict[str, Any]) -> None:
    if ALLURE_RESULTS_DIR.exists():
        shutil.rmtree(ALLURE_RESULTS_DIR)
    ALLURE_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    generated_at = bundle["manifest"]["generated_at"]
    for item in bundle["evidence"]["gates"]:
        result = allure_result_for_gate(item, generated_at)
        write_json(ALLURE_RESULTS_DIR / f"{item['id']}-result.json", result)

    history_rows = []
    history_file = ALLURE_HISTORY_DIR / "history.json"
    if history_file.exists():
        try:
            existing_history = json.loads(history_file.read_text(encoding="utf-8"))
            history_rows = list(existing_history.get("history", []))[-19:]
        except Exception:
            history_rows = []
    history_rows.append(
        {
            "generated_at": generated_at,
            "state": bundle["readiness"]["state"],
            "status_counts": bundle["readiness"]["status_counts"],
            "source_fingerprint": bundle["manifest"]["source_fingerprint"],
        }
    )
    history = {"schemaVersion": "pocketlab.validation.history.v1", "history": history_rows}
    write_json(history_file, history)
    write_json(ALLURE_RESULTS_DIR / "executor.json", {"name": "Pocket Lab local validation", "type": "local", "buildName": "validation evidence and release readiness evidence"})
    write_json(ALLURE_RESULTS_DIR / "environment.properties.json", {"Pocket Lab": "edge-first self-hostable control plane"})
    (ALLURE_RESULTS_DIR / "history").mkdir(parents=True, exist_ok=True)
    write_json(ALLURE_RESULTS_DIR / "history/history.json", history)


def validate_no_retired_text(paths: list[Path]) -> list[str]:
    findings: list[str] = []
    for path in paths:
        if not path.exists():
            continue
        files = [p for p in path.rglob("*") if p.is_file()] if path.is_dir() else [path]
        for file_path in files:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
            for pattern in RETIRED_PATTERNS:
                if pattern in text:
                    findings.append(f"{rel(file_path)} contains retired architecture token")
    return findings


def write_all(bundle: dict[str, Any]) -> None:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    write_json(MANIFEST_JSON, bundle["manifest"])
    write_json(EVIDENCE_JSON, bundle["evidence"])
    write_json(READINESS_JSON, bundle["readiness"])
    write_json(BUNDLE_JSON, bundle["bundle"])
    write_index_md(bundle)
    write_readiness_md(bundle)
    write_strategy_md(bundle)
    write_allure_results(bundle)


def load_generated_bundle() -> dict[str, Any]:
    return {
        "manifest": read_json(MANIFEST_JSON),
        "evidence": read_json(EVIDENCE_JSON),
        "readiness": read_json(READINESS_JSON),
        "bundle": read_json(BUNDLE_JSON),
    }
