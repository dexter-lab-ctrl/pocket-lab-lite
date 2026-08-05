#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[3]
MODEL_PATH = ROOT / "contracts" / "parity" / "parity-model.json"
MODEL_SCHEMA = ROOT / "schemas" / "parity" / "parity-model.schema.json"
CONTRACT_SCHEMA = ROOT / "schemas" / "parity" / "parity-contract.schema.json"
GENERATED_ROOT = ROOT / "contracts" / "generated" / "parity"
FIXTURE_ROOT = ROOT / "src" / "test" / "fixtures" / "generated" / "parity" / "recovery"
DOC_ROOT = ROOT / "docs" / "generated" / "development" / "validation" / "parity"
PRODUCTION_DOC = ROOT / "docs" / "generated" / "production" / "parity-readiness.md"
REGISTRY_MODULE = ROOT / "src" / "test" / "fixtures" / "generated" / "parity" / "recovery-parity.js"

CONTRACTS = {
    "domain-catalog.json": ("domain-catalog", "domains"),
    "backend-authority.json": ("backend-authority", "backend_authorities"),
    "api-projections.json": ("api-projections", "api_projections"),
    "frontend-state-ownership.json": ("frontend-state-ownership", "frontend_state_ownership"),
    "field-mappings.json": ("field-mappings", "field_mappings"),
    "scenario-registry.json": ("scenario-registry", "scenarios"),
    "validation-gates.json": ("validation-gates", "validation_gates"),
    "environment-matrix.json": ("environment-matrix", "environments"),
    "coverage-matrix.json": ("coverage-matrix", "domains"),
    "evidence-manifest.json": ("evidence-manifest", "validation_gates"),
    "ownership-matrix.json": ("ownership-matrix", "ownership"),
    "freshness-policy.json": ("freshness-policy", "freshness"),
    "sanitization-policy.json": ("sanitization-policy", "sanitization"),
}

DOCS = [
    ("index.md", "Backend-to-Frontend Parity", "landing"),
    ("architecture.md", "Projection Parity Architecture", "architecture"),
    ("domain-catalog.md", "Domain Parity Catalog", "domains"),
    ("backup-restore.md", "Backup & Restore Parity Specification", "recovery"),
    ("backend-data-ownership.md", "Backend Data Ownership Catalog", "backend"),
    ("api-projections.md", "API Projection Catalog", "api"),
    ("backend-api-field-mapping.md", "Backend-to-API Field Mapping", "backend-api-mapping"),
    ("api-frontend-field-mapping.md", "API-to-Frontend Field Mapping", "api-selector-mapping"),
    ("frontend-state-ownership.md", "Frontend State Ownership Matrix", "frontend"),
    ("scenario-registry.md", "Parity Scenario Registry", "scenarios"),
    ("storybook-coverage.md", "Storybook Coverage Catalog", "storybook"),
    ("playwright-coverage.md", "Playwright Test Coverage Report", "playwright"),
    ("live-termux-verification.md", "Live Termux Verification Guide", "termux"),
    ("runtime-verification-matrix.md", "Runtime Verification Matrix", "runtime"),
    ("test-environment-matrix.md", "Test Environment Matrix", "environments"),
    ("fixture-governance.md", "Test Data and Fixture Governance", "fixtures"),
    ("openapi-compatibility.md", "OpenAPI Compatibility Report", "oasdiff"),
    ("api-property-tests.md", "API Property-Test Report", "schemathesis"),
    ("accessibility.md", "Accessibility Conformance Report", "accessibility"),
    ("visual-regression.md", "Visual Regression Report", "visual"),
    ("performance-edge-budget.md", "Performance and Edge Budget Report", "performance"),
    ("validation-gates.md", "Validation Gate Catalog", "gates"),
    ("ci-gate-map.md", "CI Workflow-to-Gate Map", "ci"),
    ("evidence-traceability.md", "Evidence Manifest and Traceability Report", "evidence"),
    ("failure-triage.md", "Test Failure Triage Guide", "triage"),
    ("parity-failure-runbook.md", "Operational Runbook for Parity Failures", "runbook"),
    ("freshness-staleness.md", "Data Freshness and Staleness Policy", "freshness"),
    ("sanitization-exposure.md", "Sanitization and Data Exposure Report", "sanitization"),
    ("release-readiness.md", "Release Readiness Report", "readiness"),
    ("coverage-gaps.md", "Coverage and Gap Analysis", "gaps"),
    ("maintenance-ownership.md", "Maintenance Ownership Matrix", "ownership"),
]

FORBIDDEN = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----", re.I),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{12,}", re.I),
    re.compile(r"\b(?:password|passwd|token|api[_-]?key|secret)\s*[:=]\s*[^\s,]+", re.I),
    re.compile(r"\b(?:10|127|169\.254|172\.(?:1[6-9]|2\d|3[01])|192\.168|100)\.(?:\d{1,3}\.){2}\d{1,3}\b"),
    re.compile(r"(?<![0-9T])(?:[0-9a-f]{1,4}:){2,7}[0-9a-f]{0,4}(?![0-9a-f:Z])", re.I),
    re.compile(r"[A-Za-z0-9.-]+\.ts\.net\b", re.I),
    re.compile(r"/data/data/com\.termux/files/(?:home|usr)(?:/|\b)"),
    re.compile(r"/home/[^/\s]+/"),
    re.compile(r"(?:nats|https?)://[^\s/]+:[^\s@]+@", re.I),
]


def stable_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def fingerprint(model: dict[str, Any]) -> str:
    payload = json.dumps(model, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load_model() -> dict[str, Any]:
    return json.loads(MODEL_PATH.read_text(encoding="utf-8"))


def validate_json(instance: Any, schema_path: Path) -> None:
    try:
        import jsonschema
    except ImportError as exc:
        raise SystemExit("jsonschema is required; install requirements-dev.txt") from exc
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(instance)


def record_array(value: Any, *, key: str) -> list[dict[str, Any]]:
    if isinstance(value, list):
        items = value
    elif isinstance(value, dict):
        items = [{"id": key, **value}]
    else:
        raise ValueError(f"{key} must be an array or object")
    return sorted((dict(item) for item in items), key=lambda item: str(item.get("id", "")))


def make_contract(model: dict[str, Any], kind: str, key: str, digest: str) -> dict[str, Any]:
    items = record_array(model[key], key=kind)
    if kind == "coverage-matrix":
        items = [
            {
                "id": item["id"],
                "label": item["label"],
                "status": item["status"],
                "vertical_slice": item.get("vertical_slice", False),
                "fixture_coverage": item.get("fixture_coverage", "unvalidated"),
                "storybook_coverage": item.get("storybook_coverage", "unvalidated"),
                "mocked_playwright_coverage": item.get("mocked_playwright_coverage", "unvalidated"),
                "live_api_coverage": item.get("live_api_coverage", "unvalidated"),
                "live_termux_coverage": item.get("live_termux_coverage", "unvalidated"),
                "known_gaps": item.get("known_gaps", []),
            }
            for item in items
        ]
    if kind == "evidence-manifest":
        items = [
            {
                "id": item["id"],
                "gate": item.get("label", item["id"]),
                "task": item.get("task", ""),
                "artifact": item.get("evidence", ""),
                "environment": item.get("environment", ""),
                "blocking": bool(item.get("blocking")),
                "status": item.get("status", "unvalidated"),
            }
            for item in items
        ]
    return {
        "schema_version": "1.0.0",
        "kind": kind,
        "source_revision": model["source_revision"],
        "semantic_fingerprint": digest,
        "status": "generated",
        "items": items,
    }


def fixture_for(scenario: dict[str, Any], digest: str) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "scenario_id": scenario["id"],
        "source_revision": "repository-source",
        "semantic_fingerprint": digest,
        "status": scenario["status"],
        "identity": {"fields": scenario["stable_identity_fields"]},
        "authority": {
            "arrangement": scenario["backend_arrangement"],
            "sanitized": True,
            "raw_sqlite_rows_included": False,
            "raw_manifest_included": False,
        },
        "api": scenario["api_fixture"],
        "selector_expected": scenario["selector_expected"],
        "ui_expected": scenario["ui_expected"],
        "traceability": {
            "api_projection": scenario["api_projection"],
            "selector": scenario["selector"],
            "storybook_story": scenario["storybook_story"],
            "storybook_export": scenario["storybook_export"],
            "msw_scenario": scenario["msw_scenario"],
            "mocked_playwright_test": scenario["mocked_playwright_test"],
            "live_eligibility": scenario["live_eligibility"],
            "accessibility_test": scenario["accessibility_test"],
            "visual_test": scenario["visual_test"],
            "evidence_result": scenario["evidence_result"],
        },
    }


def markdown_table(headers: list[str], rows: Iterable[Iterable[Any]]) -> str:
    output = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        output.append("| " + " | ".join(str(value).replace("|", "\\|").replace("\n", " ") for value in row) + " |")
    return "\n".join(output)


def frontmatter(title: str, digest: str, status: str = "generated") -> str:
    return (
        "---\n"
        f"title: {json.dumps(title)}\n"
        "generated: true\n"
        "audience: development\n"
        f"status: {status}\n"
        "source_revision: repository-source\n"
        f"semantic_fingerprint: {digest}\n"
        "generator: scripts/docs/parity/generate_parity.py\n"
        "---\n\n"
    )


def status_note() -> str:
    return (
        "> Status vocabulary: **verified** is source/test confirmed; **partial** is source-derived but incomplete; "
        "**planned** is not implemented; **unvalidated** has not been run in the current environment.\n\n"
    )


def render_doc(kind: str, title: str, model: dict[str, Any], digest: str) -> str:
    recovery = next(item for item in model["domains"] if item["id"] == "recovery")
    body = [frontmatter(title, digest), f"# {title}\n", status_note()]
    if kind == "landing":
        body += [
            "Pocket Lab Lite verifies projection parity at three independent boundaries so a failure can be attributed to persistence, API projection, frontend selection, or rendering. The framework never compares rendered UI directly with raw SQLite.\n\n",
            "## Navigation\n\n",
            "- [Architecture and Method](architecture.md)\n- [Backup & Restore](backup-restore.md)\n- [Domain catalog](domain-catalog.md)\n- [Coverage and gaps](coverage-gaps.md)\n- [Release readiness](release-readiness.md)\n\n",
            "## Current release statement\n\nBackup & Restore is the first complete source-and-test vertical slice. Live WSL2-to-Termux and live browser checks remain optional and **unvalidated** until explicitly run.\n",
        ]
    elif kind == "architecture":
        body += ["## Flow\n\n```text\n" + "\n→ ".join(model["architecture"]["flow"]) + "\n```\n\n",
                 markdown_table(["Boundary", "Left", "Right", "Comparison", "Owner"], ((x["id"], x["left"], x["right"], x["comparison"], x["owner"]) for x in model["architecture"]["boundaries"])),
                 "\n\n## Method\n\nStable identifiers correlate authority, API, selector, and UI evidence. Comparisons normalize enums, formatting, ordering, timestamps, and intentional user-facing labels. Byte equality is reserved for generated artifacts. Last-good and stale states must remain visibly truthful. Runtime evidence and fixture evidence are recorded separately.\n"]
    elif kind == "domains":
        body += [markdown_table(["Domain", "Status", "Backend", "API", "Selector", "Storybook", "Mocked browser", "Live Termux"], ((d["label"], d["status"], ", ".join(d["backend_authorities"][:3]), ", ".join(d["api_projections"]), d["selector"], d["storybook_coverage"], d["mocked_playwright_coverage"], d["live_termux_coverage"]) for d in model["domains"])), "\n"]
    elif kind == "recovery":
        body += [f"**Current status:** {recovery['status']}\n\n",
                 "## Repository-backed flow\n\n```text\nmanifests / receipts / SQLite recovery state\n→ FastAPI recovery summary, details, operations and cursor history\n→ TanStack Query\n→ selectRecoverySummaryView / selectRecoveryScreenView\n→ LiteRecovery React surface\n→ Storybook / Playwright / evidence\n```\n\n",
                 "## Authorities\n\n" + markdown_table(["ID", "Kind", "Location", "Writer", "Exposure"], ((x["id"], x["kind"], x["location"], x["writer"], x["frontend_exposure"]) for x in model["backend_authorities"] if x["domain"] == "recovery")) + "\n\n",
                 "## API projections\n\n" + markdown_table(["Method", "Endpoint", "Backend sources", "Freshness", "Offline"], ((x["method"], x["endpoint"], ", ".join(x["backend_sources"]), x["freshness"], x["offline_eligibility"]) for x in model["api_projections"] if x["domain"] == "recovery")) + "\n\n",
                 "## Prohibited data\n\nRaw SQLite rows, raw manifests, restic passwords, backend secrets, private paths, media paths, raw logs, NATS credentials, and phone identity are not parity artifacts.\n"]
    elif kind == "backend":
        body += [markdown_table(["Entity", "Authority", "Writer", "Transaction", "Projection", "Retention", "Recovery", "Frontend"], ((x["id"], x["location"], x["writer"], x["transaction_boundary"], x["projection"], x["retention"], x["recovery"], x["frontend_exposure"]) for x in model["backend_authorities"])), "\n"]
    elif kind == "api":
        body += [markdown_table(["Method", "Endpoint", "Identity", "Pagination", "Freshness", "Degraded", "Offline", "Status"], ((x["method"], x["endpoint"], x["view_model_identity"], x["pagination"], x["freshness"], x["degraded_behavior"], x["offline_eligibility"], x["status"]) for x in model["api_projections"])), "\n"]
    elif kind in {"backend-api-mapping", "api-selector-mapping"}:
        boundary = "backend-api" if kind == "backend-api-mapping" else "api-selector"
        selected = [x for x in model["field_mappings"] if x["boundary"] == boundary]
        body += [markdown_table(["ID", "Source", "Target", "Transformation", "Sensitivity", "Test"], ((x["id"], x["source"], x["target"], x["transformation"], x["sensitivity"], x["test_id"]) for x in selected)), "\n\nIntentional presentation transformations are semantic and are not treated as parity failures.\n"]
    elif kind == "frontend":
        body += [markdown_table(["Layer", "Responsibility", "Allowed", "Prohibited", "Status"], ((x["id"], x["responsibility"], ", ".join(x["may_store"]), ", ".join(x["must_not_store"]), x["status"]) for x in model["frontend_state_ownership"])), "\n"]
    elif kind == "scenarios":
        body += [markdown_table(["Scenario", "Fixture", "Story", "Mocked browser", "Live", "Status"], ((x["id"], x["fixture"], x["storybook_export"], x["mocked_playwright_test"], x["live_eligibility"], x["status"]) for x in model["scenarios"])), "\n"]
    elif kind == "storybook":
        body += ["Storybook uses the generated scenario registry and deterministic MSW aliases. It proves fixture-driven component states, accessibility intent, and viewport behavior; it does **not** prove backend persistence.\n\n",
                 markdown_table(["Scenario", "Story export", "MSW scenario", "A11y", "Visual"], ((x["id"], x["storybook_export"], x["msw_scenario"], x["accessibility_test"], x["visual_test"]) for x in model["scenarios"])), "\n"]
    elif kind == "playwright":
        body += ["Mocked desktop/mobile projects use the existing external-browser resolver, retained failure traces, screenshots, JSON/JUnit evidence, and deterministic MSW scenarios. Live projects are read-only and opt-in.\n\n",
                 markdown_table(["Project", "Mode", "Proves", "Evidence"], [("mocked-desktop/mobile", "MSW", "rendered meaning, stale/offline/error states", ".pocketlab-dev/validation/playwright-results.json"), ("live-desktop/mobile", "Caddy/FastAPI", "live browser/API integration", ".pocketlab-dev/validation/playwright-results.json")]), "\n"]
    elif kind == "termux":
        body += ["```text\nVS Code WSL2\n→ managed hardened SSH alias\n→ one bounded read-only verifier\n→ sanitized backend projection\n→ live FastAPI query\n→ optional Playwright observation\n→ normalized evidence\n```\n\nThe verifier never copies a database, prints raw rows, reads credentials, writes to the phone, or restarts services. Missing SSH configuration reports **runtime-unavailable**, not PASS.\n"]
    elif kind == "runtime":
        body += [markdown_table(["Domain", "Source", "Fixture", "Mock browser", "Live API", "Live Termux", "Status"], ((d["label"], "verified" if d["status"] != "planned" else "partial", d["fixture_coverage"], d["mocked_playwright_coverage"], d["live_api_coverage"], d["live_termux_coverage"], d["status"]) for d in model["domains"])), "\n"]
    elif kind == "environments":
        body += [markdown_table(["Environment", "Proves", "Does not prove", "Status"], ((x["label"], ", ".join(x["proves"]), ", ".join(x["does_not_prove"]), x["status"]) for x in model["environments"])), "\n"]
    elif kind == "fixtures":
        body += ["Fixtures are synthetic, sanitized, schema-bound, stable-ID driven, and generated from the canonical registry. Timestamps are normalized. Raw runtime captures cannot become fixtures without explicit sanitization and promotion. Deprecated scenarios remain traceable until consumers are removed.\n\n",
                 markdown_table(["Scenario", "Stable IDs", "Fixture", "Runtime eligibility"], ((x["id"], ", ".join(x["stable_identity_fields"]), x["fixture"], x["live_eligibility"]) for x in model["scenarios"])), "\n"]
    elif kind == "oasdiff":
        body += ["`lite:api:breaking-changes` compares a caller-supplied or promoted OpenAPI baseline with the generated current Lite OpenAPI contract. It reports removed paths, required-field additions, enum/nullability changes, and response compatibility. No generated OpenAPI file is manually edited.\n\n**Current result:** unvalidated until `oasdiff` is installed and a baseline is provided or promoted explicitly.\n"]
    elif kind == "schemathesis":
        body += ["`lite:api:schemathesis` exercises safe isolated endpoints from the generated OpenAPI contract. Live mode permits only GET/HEAD and excludes backup, restore, install, update, remove, restart, invite, and Security mutation paths. Unexpected 5xx responses and schema violations fail the gate.\n\n**Current result:** unvalidated until the repository-local tool is installed.\n"]
    elif kind == "accessibility":
        body += ["The repository already uses `@axe-core/playwright` and Storybook a11y. Recovery coverage includes the main tab and links to Manage, history, confirmation, progress, error, desktop, and mobile states. Serious and critical violations block the mocked gate; color contrast remains tracked separately by the existing test policy.\n"]
    elif kind == "visual":
        body += ["Existing Playwright screenshots cover the Recovery tab at desktop and mobile viewports with reduced motion. Visual approval is separate from data parity approval. A pixel change can require baseline review even when semantic parity passes, and semantic parity can fail while screenshots remain visually similar.\n"]
    elif kind == "performance":
        body += [markdown_table(["Profile", "VUs", "Duration", "Endpoints", "Thresholds", "Status"], ((x["id"], x.get("vus", f"1-{x.get('max_vus', 1)}"), f"{x['duration_seconds']}s", ", ".join(x["endpoints"]), ", ".join(f"{k}={v}" for k,v in x["thresholds"].items()), x["status"]) for x in model["performance_profiles"])), "\n\nThe edge profile is read-only, explicitly enabled, battery/memory/CPU guarded, and intentionally not a stress test.\n"]
    elif kind == "gates":
        body += [markdown_table(["Gate", "Task", "Suite", "Evidence", "Blocking", "Environment", "Status"], ((x["label"], x["task"], x["suite"], x["evidence"], x["blocking"], x["environment"], x["status"]) for x in model["validation_gates"])), "\n"]
    elif kind == "ci":
        body += [markdown_table(["Workflow", "Job", "Task", "Suite", "Evidence", "Blocking", "Status"], ((x["workflow"], x["job"], x["task"], x["suite"], x["evidence"], x["blocking"], x["status"]) for x in model["ci_map"])), "\n"]
    elif kind == "evidence":
        body += ["Evidence traceability is generated from the same scenario and gate registry. Runtime evidence is stored only under `.pocketlab-dev/validation/parity` and is not tracked. Stable relative artifact identifiers replace local absolute paths.\n\n",
                 markdown_table(["Scenario", "Backend", "API", "Selector", "UI", "Story", "Browser", "Runtime"], ((x["id"], x["backend_arrangement"], x["api_projection"], x["selector"], ", ".join(x["ui_expected"]["visible_text"]), x["storybook_export"], x["mocked_playwright_test"], x["evidence_result"]) for x in model["scenarios"])), "\n"]
    elif kind == "triage":
        body += ["## Failure attribution\n\n- **backend ≠ API:** inspect manifest/current-state writers, transactions, projection refresh, and allowlist mapping.\n- **API ≠ selector:** inspect query key, selector normalizer, enum mapping, and omitted sensitive fields.\n- **selector ≠ rendered UI:** inspect conditional labels, component state, stale/offline indicators, and test selectors.\n- **mocked passes, live fails:** inspect Caddy origin, API freshness, authentication, runtime projection, and external browser configuration.\n- **API/browser match, authority differs:** treat as backend/projection drift; do not patch the UI to hide it.\n- **Storybook passes, page fails:** inspect integrated providers, routing, query invalidation, and overlay state.\n- **offline conflicts with live:** inspect Dexie snapshot revision and TanStack replacement rules.\n"]
    elif kind == "runbook":
        body += ["## Symptoms\n\nStale or contradictory recovery status, missing backup history, a verified backup shown as unverified, restore readiness mismatch, or mocked/live divergence.\n\n## Read-only verification\n\n1. Run parity contract and fixture checks.\n2. Query Recovery summary/details/history through FastAPI.\n3. Inspect prepared-projection freshness and worker/NATS health without mutation.\n4. Inspect safe Dexie metadata in browser DevTools; never treat it as authority.\n5. Capture sanitized evidence.\n6. Refresh projections through established safe backend paths only.\n\n## Recovery\n\nDo not edit SQLite or manifests manually. Restore or repair must use explicit backend-owned flows and existing confirmations.\n"]
    elif kind == "freshness":
        body += [markdown_table(["Projection", "Fresh", "Stale", "Last-good", "Offline", "UI label", "Status"], ((x["projection"], x["fresh_window_seconds"], x["stale_window_seconds"], x["last_good_allowed"], x["offline_allowed"], x["ui_label"], x["status"]) for x in model["freshness"])), "\n\nFreshness conflicts fail the relevant boundary; saved state must never be presented as live.\n"]
    elif kind == "sanitization":
        p = model["sanitization"]
        body += [f"Maximum evidence size: **{p['max_evidence_bytes']} bytes**.\n\n",
                 "## Rejected classes\n\n" + "\n".join(f"- {x}" for x in p["forbidden_classes"]) + "\n\n",
                 "All generated artifacts are allowlisted and scanned by the existing repository redaction checker plus parity-specific checks.\n"]
    elif kind == "readiness":
        blocking = [x for x in model["validation_gates"] if x["blocking"]]
        body += ["**Release decision:** ready-with-accepted-limitations only after all blocking local/CI gates pass. Live Termux, live browser, visual review, and edge performance remain separately reported when not run.\n\n",
                 markdown_table(["Blocking gate", "Task", "Status"], ((x["label"], x["task"], x["status"]) for x in blocking)), "\n"]
    elif kind == "gaps":
        body += [markdown_table(["Domain", "Status", "Known gaps"], ((x["label"], x["status"], "; ".join(x["known_gaps"])) for x in model["domains"])), "\n\nBackup & Restore is implemented end to end in this framework. Other domains are intentionally source-derived catalogs rather than fabricated full parity coverage.\n"]
    elif kind == "ownership":
        body += [markdown_table(["Artifact", "Owner", "Reviewers", "Cadence", "Status"], ((x["artifact"], x["owner"], ", ".join(x["reviewers"]), x["cadence"], x["status"]) for x in model["ownership"])), "\n"]
    else:
        raise ValueError(kind)
    return "".join(body).rstrip() + "\n"


def registry_module(model: dict[str, Any]) -> str:
    rows = []
    for scenario in sorted(model["scenarios"], key=lambda item: item["id"]):
        rows.append({
            "id": scenario["id"],
            "label": scenario["label"],
            "fixture": scenario["fixture"],
            "mswScenario": scenario["msw_scenario"],
            "storyExport": scenario["storybook_export"],
            "visibleText": scenario["ui_expected"]["visible_text"],
            "liveEligibility": scenario["live_eligibility"],
        })
    return "// Generated by scripts/docs/parity/generate_parity.py. Do not edit.\nexport const recoveryParityScenarios = " + json.dumps(rows, indent=2, ensure_ascii=False) + ";\nexport default recoveryParityScenarios;\n"


def all_outputs(model: dict[str, Any]) -> dict[Path, str]:
    digest = fingerprint(model)
    outputs: dict[Path, str] = {}
    for filename, (kind, key) in CONTRACTS.items():
        contract = make_contract(model, kind, key, digest)
        validate_json(contract, CONTRACT_SCHEMA)
        outputs[GENERATED_ROOT / filename] = stable_json(contract)
    for scenario in model["scenarios"]:
        outputs[FIXTURE_ROOT / f"{scenario['id']}.json"] = stable_json(fixture_for(scenario, digest))
    outputs[REGISTRY_MODULE] = registry_module(model)
    for filename, title, kind in DOCS:
        outputs[DOC_ROOT / filename] = render_doc(kind, title, model, digest)
    prod = frontmatter("Projection parity readiness", digest, "ready-with-accepted-limitations").replace("audience: development", "audience: production")
    prod += "# Projection parity readiness\n\nPocket Lab Lite validates Backup & Restore across backend authority, FastAPI projection, frontend selection, and rendered UI. Ordinary production documentation exposes only the readiness result and safe operator actions; internal test mechanics remain under Development.\n\n- Backup & Restore: ready-with-accepted-limitations after blocking local/CI gates pass.\n- Live Termux and live browser: optional, read-only, and unvalidated until explicitly run.\n- Devices, Apps, Security, Rules, and Releases: source-derived partial/planned catalogs.\n"
    outputs[PRODUCTION_DOC] = prod
    return outputs


def scan_safe(path: Path, text: str, max_bytes: int) -> None:
    encoded = text.encode("utf-8")
    if len(encoded) > max_bytes and path.suffix == ".json" and "fixture" in path.as_posix():
        raise ValueError(f"oversized parity fixture: {path.relative_to(ROOT)}")
    for pattern in FORBIDDEN:
        match = pattern.search(text)
        if match:
            raise ValueError(f"forbidden parity content in {path.relative_to(ROOT)}: {pattern.pattern}")


def atomic_write(path: Path, text: str) -> bool:
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)
    return True


def validate_links(model: dict[str, Any]) -> None:
    ids = {}
    for section in ["domains", "backend_authorities", "api_projections", "frontend_state_ownership", "field_mappings", "scenarios", "validation_gates", "environments", "ownership", "freshness"]:
        values = model[section]
        section_ids = [item["id"] for item in values]
        if len(section_ids) != len(set(section_ids)):
            raise ValueError(f"duplicate ids in {section}")
        ids[section] = set(section_ids)
    for mapping in model["field_mappings"]:
        if mapping["domain"] not in ids["domains"]:
            raise ValueError(f"orphan mapping domain: {mapping['id']}")
    for scenario in model["scenarios"]:
        if scenario["domain"] not in ids["domains"]:
            raise ValueError(f"orphan scenario domain: {scenario['id']}")
        for key in ["fixture", "storybook_story", "mocked_playwright_test", "accessibility_test", "visual_test"]:
            if not scenario.get(key):
                raise ValueError(f"missing scenario linkage {key}: {scenario['id']}")
    for authority in model["backend_authorities"]:
        if not authority.get("writer") or not authority.get("reader"):
            raise ValueError(f"missing owner/writer: {authority['id']}")
    edge = next(item for item in model["performance_profiles"] if item["id"] == "edge")
    if edge["max_vus"] > 3 or edge["duration_seconds"] > 30 or edge["destructive_endpoints"]:
        raise ValueError("edge performance profile exceeds bounded safe policy")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate/check Pocket Lab Lite projection parity contracts and docs")
    parser.add_argument("command", choices=["generate", "check", "fingerprint"])
    args = parser.parse_args()
    model = load_model()
    validate_json(model, MODEL_SCHEMA)
    validate_links(model)
    outputs = all_outputs(model)
    max_bytes = int(model["sanitization"]["max_evidence_bytes"])
    for path, text in outputs.items():
        scan_safe(path, text, max_bytes)
    if args.command == "fingerprint":
        print(fingerprint(model))
        return 0
    if args.command == "generate":
        changed = [str(path.relative_to(ROOT)) for path, text in outputs.items() if atomic_write(path, text)]
        print(f"PASS parity generation: {len(outputs)} artifacts, {len(changed)} changed")
        return 0
    drift = []
    for path, text in outputs.items():
        if not path.exists() or path.read_text(encoding="utf-8") != text:
            drift.append(str(path.relative_to(ROOT)))
    if drift:
        print("FAIL parity generated drift:")
        for item in drift:
            print(f"  {item}")
        return 1
    print(f"PASS parity check: {len(outputs)} deterministic artifacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
