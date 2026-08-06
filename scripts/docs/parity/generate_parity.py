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
RUNTIME_BASELINE_PATH = ROOT / "contracts" / "parity" / "runtime-verification-baseline.json"
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
    "comparator-registry.json": ("comparator-registry", "comparator_registry"),
    "runtime-scenario-registry.json": ("runtime-scenario-registry", "runtime_scenarios"),
    "pairwise-scenario-registry.json": ("pairwise-scenario-registry", "pairwise_dimensions"),
    "runtime-drift.json": ("runtime-drift", "domains"),
    "accepted-limitations.json": ("accepted-limitations", "domains"),
}

DOCS = [
    ("index.md", "Backend-to-Frontend Parity", "landing"),
    ("architecture.md", "Projection Parity Architecture", "architecture"),
    ("domain-catalog.md", "Domain Parity Catalog", "domains"),
    ("home.md", "Home Parity Specification", "domain-home"),
    ("apps.md", "Apps Parity Specification", "domain-apps"),
    ("devices.md", "Devices Parity Specification", "domain-devices"),
    ("security.md", "Security Parity Specification", "domain-security"),
    ("identity.md", "Identity Parity Specification", "domain-identity"),
    ("rules.md", "Rules Parity Specification", "domain-rules"),
    ("backup-restore.md", "Backup & Restore Parity Specification", "domain-recovery"),
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
    ("runtime-drift-report.md", "Runtime Semantic Drift Report", "runtime-drift"),
    ("accepted-limitations.md", "Accepted Parity Limitations", "accepted-limitations"),
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


def load_runtime_baseline() -> dict[str, Any]:
    if not RUNTIME_BASELINE_PATH.exists():
        return {"schema_version": "1.0.0", "status": "unvalidated", "sanitized": True, "domains": []}
    baseline = json.loads(RUNTIME_BASELINE_PATH.read_text(encoding="utf-8"))
    if not isinstance(baseline, dict) or baseline.get("sanitized") is not True:
        raise ValueError("runtime verification baseline must be a sanitized object")
    domains = baseline.get("domains", [])
    if not isinstance(domains, list):
        raise ValueError("runtime verification baseline domains must be an array")
    if baseline.get("schema_version") == "1.0.0":
        allowed = {"verified", "unvalidated"}
        for item in domains:
            if item.get("id") != "recovery":
                raise ValueError("legacy runtime baseline may contain only Recovery coverage")
            if item.get("live_api_coverage") not in allowed or item.get("live_termux_coverage") not in allowed:
                raise ValueError("legacy runtime verification baseline contains an invalid coverage status")
        return baseline
    if baseline.get("schema_version") != "2.0.0":
        raise ValueError("unsupported runtime verification baseline schema")
    validate_json(baseline, ROOT / "schemas" / "parity" / "parity-runtime-baseline.schema.json")
    expected = {item["id"] for item in load_model()["domains"]}
    observed = {item.get("id") for item in domains}
    if observed != expected:
        raise ValueError(f"runtime baseline domain set differs from canonical model: {sorted(expected ^ observed)}")
    return baseline


def apply_runtime_baseline(model: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    merged = json.loads(json.dumps(model))
    merged["_source_fingerprint"] = fingerprint(model)
    promoted = {item["id"]: item for item in baseline.get("domains", [])}
    legacy = baseline.get("schema_version") == "1.0.0"
    for domain in merged["domains"]:
        item = promoted.get(domain["id"])
        if not item:
            continue
        if legacy:
            # The pre-semantic baseline proves only that Recovery API/browser/Termux
            # coverage ran successfully. It must not be upgraded into semantic parity.
            domain["live_api_coverage"] = item.get("live_api_coverage", "unvalidated")
            domain["live_ui_coverage"] = item.get("live_api_coverage", "unvalidated")
            domain["live_termux_coverage"] = item.get("live_termux_coverage", "unvalidated")
            domain["runtime_parity"] = "unvalidated"
            continue
        domain["live_api_coverage"] = item.get("live_api_coverage", "unvalidated")
        domain["live_ui_coverage"] = item.get("live_ui_coverage", "unvalidated")
        domain["live_termux_coverage"] = item.get("live_termux_coverage", "unvalidated")
        domain["runtime_parity"] = item.get("runtime_parity", "unvalidated")
        domain["runtime_status"] = item.get("status", "unvalidated")
        domain["comparison_summary"] = item.get("comparison_summary", {})
        domain["runtime_comparisons"] = item.get("comparisons", [])
        domain["observation_fingerprints"] = item.get("observation_fingerprints", {})
        if item.get("runtime_parity") == "drift-detected":
            domain["status"] = "needs-review"
        elif item.get("runtime_parity") in {"verified", "verified-with-mapped-presentation"}:
            domain["status"] = "verified"
    merged["runtime_verification_baseline"] = {
        "schema_version": baseline.get("schema_version", "1.0.0"),
        "status": baseline.get("status", "unvalidated"),
        "release_tag": baseline.get("release_tag", ""),
        "source_commit": baseline.get("source_commit", ""),
        "promoted_at": baseline.get("promoted_at", ""),
        "evidence_hashes": baseline.get("evidence_hashes", {}),
    }
    return merged

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
                "source_coverage": "verified" if item.get("backend_authorities") and item.get("api_routes") else "partial",
                "fixture_coverage": item.get("fixture_coverage", "unvalidated"),
                "storybook_coverage": item.get("storybook_coverage", "unvalidated"),
                "mocked_playwright_coverage": item.get("mocked_playwright_coverage", "unvalidated"),
                "live_api_coverage": item.get("live_api_coverage", "unvalidated"),
                "live_ui_coverage": item.get("live_ui_coverage", "unvalidated"),
                "live_termux_coverage": item.get("live_termux_coverage", "unvalidated"),
                "runtime_parity": item.get("runtime_parity", "unvalidated"),
                "known_gaps": item.get("known_gaps", []),
            }
            for item in items
        ]
    elif kind == "evidence-manifest":
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
    elif kind == "runtime-drift":
        items = [
            {
                "id": item["id"],
                "label": item["label"],
                "runtime_parity": item.get("runtime_parity", "unvalidated"),
                "runtime_status": item.get("runtime_status", "unvalidated"),
                "comparison_summary": item.get("comparison_summary", {}),
                "mismatches": [x for x in item.get("runtime_comparisons", []) if x.get("result") == "mismatch"],
            }
            for item in items
        ]
    elif kind == "accepted-limitations":
        items = [
            {
                "id": item["id"],
                "label": item["label"],
                "accepted_limitations": item.get("accepted_limitations", []),
                "unsupported_operations": item.get("unsupported_operations", []),
                "known_gaps": item.get("known_gaps", []),
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


def render_domain_doc(domain: dict[str, Any], model: dict[str, Any], digest: str, title: str) -> str:
    authorities = [x for x in model["backend_authorities"] if x.get("domain") == domain["id"]]
    projections = [x for x in model["api_projections"] if x.get("domain") == domain["id"]]
    mappings = domain.get("semantic_mappings", [])
    baseline = model.get("runtime_verification_baseline", {})
    comparison_summary = domain.get("comparison_summary", {})
    comparisons = domain.get("runtime_comparisons", [])
    mismatches = [x for x in comparisons if x.get("result") == "mismatch"]
    mapped = [x for x in mappings if x.get("operator") in {"enum-map", "state-machine-map", "status-family", "capability-map", "intentional-presentation-map", "percentage-format", "byte-format", "duration-format"}]
    backend_contract = ((domain.get("live_observation_contract") or {}).get("backend") or {})
    frontend_contract = ((domain.get("live_observation_contract") or {}).get("frontend") or {})
    fingerprints = domain.get("observation_fingerprints", {})
    evidence_hashes = baseline.get("evidence_hashes", {})
    relevant_hashes = {
        key: value for key, value in evidence_hashes.items()
        if key in {"runtime-comparison", "playwright-report"} or domain["id"] in key
    }

    def bullets(values: list[Any], fallback: str = "None recorded.") -> str:
        rows = [str(value) for value in values if str(value).strip()]
        return "\n".join(f"- {value}" for value in rows) if rows else f"- {fallback}"

    body = [frontmatter(title, digest), f"# {title}\n", status_note()]
    body += [
        "## 1. Current status\n\n",
        markdown_table(
            ["Repository", "Fixture", "Mock browser", "Live API", "Live UI", "Live Termux", "Runtime parity", "Status"],
            [(
                "verified" if authorities and domain.get("api_routes") else "partial",
                domain.get("fixture_coverage", "unvalidated"),
                domain.get("mocked_playwright_coverage", "unvalidated"),
                domain.get("live_api_coverage", "unvalidated"),
                domain.get("live_ui_coverage", "unvalidated"),
                domain.get("live_termux_coverage", "unvalidated"),
                domain.get("runtime_parity", "unvalidated"),
                domain.get("status", "partial"),
            )],
        ),
        "\n\n## 2. Repository-backed flow\n\n",
        "```text\nReact/Vite PWA screen: " + ", ".join(domain.get("frontend_screens", [])) +
        "\n→ Caddy same-origin proxy\n→ FastAPI: " + ", ".join(domain.get("api_routes", [])) +
        "\n→ repository authorities: " + ", ".join(x["id"] for x in authorities) +
        "\n→ sanitized projection / selector / rendered UI\n```\n\n",
        "## 3. Backend authorities\n\n",
        markdown_table(
            ["Authority", "Kind", "Repository location", "Writer", "Reader", "Frontend exposure"],
            ((x["id"], x.get("kind", ""), x.get("location", ""), x.get("writer", ""), x.get("reader", ""), x.get("frontend_exposure", "")) for x in authorities),
        ),
        "\n\n## 4. FastAPI routes\n\n",
        markdown_table(
            ["Method", "Endpoint", "Backend sources", "Freshness", "Degraded behavior", "Sanitization"],
            ((x.get("method", "GET"), x.get("endpoint", ""), ", ".join(x.get("backend_sources", [])), x.get("freshness", ""), x.get("degraded_behavior", ""), x.get("sanitization", "")) for x in projections),
        ),
        "\n\n## 5. Frontend selectors and screens\n\n",
        markdown_table(
            ["Selectors/presentation", "Query keys", "Screens"],
            [(", ".join(domain.get("selectors", [])), ", ".join(domain.get("query_keys", [])), ", ".join(domain.get("frontend_screens", [])))],
        ),
        "\n\n## 6. Query and state ownership\n\n",
        markdown_table(
            ["Layer", "Owner", "Responsibility", "May store", "Must not store"],
            ((x["id"], x.get("owner", ""), x.get("responsibility", ""), "; ".join(x.get("may_store", [])), "; ".join(x.get("must_not_store", []))) for x in model.get("frontend_state_ownership", [])),
        ),
        "\n\nFastAPI and repository authorities remain the source of truth. Frontend caches and workflow/UI state never become execution authority.\n\n",
        "## 7. Storybook coverage\n\n" + bullets(domain.get("storybook_exports", []), "No Storybook export is linked.") + "\n\n",
        "## 8. Mocked-browser scenarios\n\n" + bullets(domain.get("mocked_scenarios", []), "No mocked browser scenario is linked.") + "\n\n",
        "## 9. Live API observation\n\n",
        f"Status: **{domain.get('live_api_coverage', 'unvalidated')}**\n\n",
        markdown_table(
            ["Observation", "Route adapter", "Extractor", "Path", "API ↔ Termux comparator", "Severity"],
            ((x.get("id", ""), x.get("route", "primary"), x.get("extract", "path"), x.get("path", x.get("value_path", x.get("list_path", ""))), x.get("authority_operator", "exact"), x.get("authority_severity", "high")) for x in backend_contract.get("fields", [])),
        ),
        "\n\n## 10. Live UI observation\n\n",
        f"Status: **{domain.get('live_ui_coverage', 'unvalidated')}**. Screen: `{frontend_contract.get('screen_id', '')}`. Required projects: " + ", ".join(frontend_contract.get("project_required", [])) + ".\n\n",
        "Browser capture uses visible semantics, accessible controls, existing stable screen identifiers, bounded text, exact backend-derived identity checks, and privacy redaction.\n\n",
        "## 11. Live Termux observation\n\n",
        f"Status: **{domain.get('live_termux_coverage', 'unvalidated')}**. The Termux lane uses the same allowlisted GET adapters through the managed read-only SSH alias and the phone loopback API, or an explicitly configured safe tunnel. It never reads databases, credentials, or environment secrets and never restarts services.\n\n",
        "## 12. Field-level semantic comparisons\n\n",
        markdown_table(
            ["Mapping", "Boundary", "Backend observation", "Frontend observation", "Comparator", "Severity"],
            ((x["id"], x.get("boundary", "live-api-live-ui"), x.get("backend_path", "$"), x.get("frontend_path", "$"), x["operator"], x.get("severity", "medium")) for x in mappings),
        ),
        "\n\n## 13. Mapped presentation differences\n\n",
        markdown_table(
            ["Mapping", "Comparator", "Allowlisted presentation"],
            ((x["id"], x["operator"], json.dumps(x.get("mapping", {"format": "bounded equivalent"}), sort_keys=True, ensure_ascii=False)) for x in mapped),
        ),
        "\n\nDifferent user-facing wording or formatting is not drift when an allowlisted deterministic mapping proves equivalent meaning.\n\n",
        "## 14. Detected drift\n\n",
        markdown_table(
            ["Comparison", "Boundary", "Severity", "Project", "Explanation"],
            ((x.get("id", ""), x.get("boundary", ""), x.get("severity", ""), x.get("project", ""), x.get("explanation", "")) for x in mismatches),
        ),
        "\n\n" + ("No promoted semantic drift is recorded for this domain." if not mismatches else "Drift is valid review evidence; this page does not authorize changing backend or frontend behavior automatically.") + "\n\n",
        "## 15. Accepted limitations\n\n" + bullets(domain.get("accepted_limitations", [])) + "\n\n",
        "## 16. Unsupported operations\n\n" + bullets(domain.get("unsupported_operations", [])) + "\n\n",
        "## 17. Known gaps\n\n" + bullets(domain.get("known_gaps", [])) + "\n\n",
        "## 18. Evidence hashes\n\n",
        markdown_table(
            ["Evidence", "SHA-256 / semantic fingerprint"],
            list(sorted({**relevant_hashes, **{f"observation-{key}": value for key, value in fingerprints.items()}}.items())),
        ),
        "\n\nNo raw API payload, database row, hostname, username, private address, browser trace, or screenshot is stored in the promoted baseline.\n\n",
        "## 19. Release and source binding\n\n",
        markdown_table(
            ["Baseline schema", "Release tag", "Source commit", "Promoted at"],
            [(baseline.get("schema_version", "1.0.0"), baseline.get("release_tag", ""), baseline.get("source_commit", ""), baseline.get("promoted_at", ""))],
        ),
        "\n\nA legacy v1 baseline proves coverage only. It cannot upgrade semantic parity to verified.\n\n",
        "## 20. Operator validation commands\n\n",
        "```bash\n"
        "task lite:parity:model:check\n"
        "task lite:parity:contracts:check\n"
        "task lite:parity:fixtures:check\n"
        "LITE_PARITY_RELEASE_TAG=<release-tag> task lite:parity:runtime:capture\n"
        "LITE_PARITY_RELEASE_TAG=<release-tag> task lite:parity:playwright:live\n"
        "LITE_PARITY_RELEASE_TAG=<release-tag> task lite:parity:termux\n"
        "task lite:parity:runtime:compare\n"
        "LITE_PARITY_RELEASE_TAG=<release-tag> task lite:evidence:runtime:promote\n"
        "task lite:evidence:runtime:check\n"
        "```\n\n",
        "## 21. Failure attribution guidance\n\n",
        bullets([
            "backend authority ≠ API projection",
            "API projection ≠ selector/direct presentation",
            "selector/direct presentation ≠ rendered UI",
            "mocked browser ≠ live browser",
            "live API ≠ Termux observation",
            "saved snapshot ≠ live API",
            "desktop ≠ mobile",
            "expected mapping ≠ actual wording",
            "capability advertised ≠ action available",
            "state machine ≠ rendered action state",
        ]),
        "\n\nMissing, failed, stale, or unavailable evidence is classified separately from drift.\n\n",
        "## 22. Last promoted runtime result\n\n",
        markdown_table(
            ["Runtime parity", "Runtime status", "Match", "Mapped", "Mismatch", "Unsupported", "Not observed", "Not applicable"],
            [(
                domain.get("runtime_parity", "unvalidated"),
                domain.get("runtime_status", "unvalidated"),
                comparison_summary.get("match", 0),
                comparison_summary.get("mapped", 0),
                comparison_summary.get("mismatch", 0),
                comparison_summary.get("unsupported", 0),
                comparison_summary.get("not_observed", 0),
                comparison_summary.get("not_applicable", 0),
            )],
        ),
        "\n",
    ]
    return "".join(body).rstrip() + "\n"


def generate_pairwise_cases(model: dict[str, Any]) -> list[dict[str, Any]]:
    # Deterministic bounded all-pairs greedy cover. It never executes runtime work;
    # it generates the scenario catalog consumed by tests and documentation.
    output: list[dict[str, Any]] = []
    for spec in model.get("pairwise_dimensions", []):
        raw_dimensions = spec.get("dimensions", {})
        if not raw_dimensions:
            continue
        dimensions = (
            [{"id": key, "values": values} for key, values in sorted(raw_dimensions.items())]
            if isinstance(raw_dimensions, dict)
            else raw_dimensions
        )
        candidates = [{}]
        for dimension in dimensions:
            next_rows = []
            for row in candidates:
                for value in dimension.get("values", []):
                    candidate = {**row, dimension["id"]: value}
                    excluded = False
                    for rule in spec.get("exclusions", []):
                        when = rule.get("when", rule)
                        if len(candidate) == len(dimensions) and all(candidate.get(key) == expected for key, expected in when.items()):
                            excluded = True
                            break
                    if not excluded:
                        next_rows.append(candidate)
            candidates = next_rows
        pairs = set()
        for row in candidates:
            keys = sorted(row)
            pairs.update((keys[i], str(row[keys[i]]), keys[j], str(row[keys[j]])) for i in range(len(keys)) for j in range(i + 1, len(keys)))
        uncovered = set(pairs)
        selected = []
        while uncovered and candidates and len(selected) < int(spec.get("max_cases", 24)):
            def score(row: dict[str, Any]) -> tuple[int, str]:
                keys = sorted(row)
                row_pairs = {(keys[i], str(row[keys[i]]), keys[j], str(row[keys[j]])) for i in range(len(keys)) for j in range(i + 1, len(keys))}
                return (len(row_pairs & uncovered), json.dumps(row, sort_keys=True))
            chosen = max(candidates, key=score)
            selected.append(chosen)
            keys = sorted(chosen)
            uncovered -= {(keys[i], str(chosen[keys[i]]), keys[j], str(chosen[keys[j]])) for i in range(len(keys)) for j in range(i + 1, len(keys))}
            candidates = [row for row in candidates if row != chosen]
        for index, values in enumerate(selected, start=1):
            output.append({"id": f"{spec['id']}-{index:02d}", "matrix_id": spec["id"], "values": values})
    return output


def render_doc(kind: str, title: str, model: dict[str, Any], digest: str) -> str:
    recovery = next(item for item in model["domains"] if item["id"] == "recovery")
    body = [frontmatter(title, digest), f"# {title}\n", status_note()]
    if kind.startswith("domain-"):
        domain_id = kind.removeprefix("domain-")
        domain = next(item for item in model["domains"] if item["id"] == domain_id)
        return render_domain_doc(domain, model, digest, title)
    if kind == "landing":
        body += [
            "Pocket Lab Lite verifies projection parity at three independent boundaries so a failure can be attributed to persistence, API projection, frontend selection, or rendering. The framework never compares rendered UI directly with raw SQLite.\n\n",
            "## Navigation\n\n",
            "- [Architecture and Method](architecture.md)\n- [Home](home.md)\n- [Apps](apps.md)\n- [Devices](devices.md)\n- [Security](security.md)\n- [Identity](identity.md)\n- [Rules](rules.md)\n- [Backup & Restore](backup-restore.md)\n- [Runtime drift report](runtime-drift-report.md)\n- [Accepted limitations](accepted-limitations.md)\n- [Domain catalog](domain-catalog.md)\n- [Coverage and gaps](coverage-gaps.md)\n- [Release readiness](release-readiness.md)\n\n",
            "## Current release statement\n\nThe canonical parity model now covers all seven Lite tabs. Repository contracts and deterministic mocked evidence remain distinct from explicitly promoted semantic runtime evidence. The currently tracked legacy runtime baseline is coverage-only; it must not be interpreted as field-level semantic verification.\n",
        ]
    elif kind == "architecture":
        body += ["## Flow\n\n```text\n" + "\n→ ".join(model["architecture"]["flow"]) + "\n```\n\n",
                 markdown_table(["Boundary", "Left", "Right", "Comparison", "Owner"], ((x["id"], x["left"], x["right"], x["comparison"], x["owner"]) for x in model["architecture"]["boundaries"])),
                 "\n\n## Method\n\nStable identifiers correlate authority, API, selector, and UI evidence. Comparisons normalize enums, formatting, ordering, timestamps, and intentional user-facing labels. Byte equality is reserved for generated artifacts. Last-good and stale states must remain visibly truthful. Runtime evidence and fixture evidence are recorded separately.\n"]
    elif kind == "domains":
        body += [markdown_table(["Domain", "Repository status", "Backend", "API", "Selectors", "Mocked browser", "Live API", "Live UI", "Live Termux", "Semantic parity"], ((d["label"], d["status"], ", ".join(d["backend_authorities"][:3]), ", ".join(d["api_routes"]), ", ".join(d["selectors"]), d["mocked_playwright_coverage"], d.get("live_api_coverage", "unvalidated"), d.get("live_ui_coverage", "unvalidated"), d.get("live_termux_coverage", "unvalidated"), d.get("runtime_parity", "unvalidated")) for d in model["domains"])), "\n"]
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
        baseline = model.get("runtime_verification_baseline", {})
        release = baseline.get("release_tag") or "none"
        baseline_label = baseline.get("status", "unvalidated")
        if baseline.get("schema_version") == "1.0.0" and baseline_label == "verified":
            baseline_label = "verified coverage-only (semantic parity unvalidated)"
        body += [
            f"Promoted runtime baseline: **{baseline_label}**; release: **{release}**. Promotion is explicit, sanitized, hash-bound, and ordinary generation never reads live captures.\n\n",
            markdown_table(["Domain", "Repository", "Fixture", "Mock browser", "Live API", "Live UI", "Live Termux", "Semantic parity", "Status"], ((d["label"], "verified" if d.get("backend_authorities") and d.get("api_routes") else "partial", d["fixture_coverage"], d["mocked_playwright_coverage"], d.get("live_api_coverage", "unvalidated"), d.get("live_ui_coverage", "unvalidated"), d.get("live_termux_coverage", "unvalidated"), d.get("runtime_parity", "unvalidated"), d["status"]) for d in model["domains"])), "\n",
        ]
    elif kind == "runtime-drift":
        mismatches = []
        for domain in model["domains"]:
            for item in domain.get("runtime_comparisons", []):
                if item.get("result") == "mismatch":
                    mismatches.append((domain["label"], item.get("id", ""), item.get("severity", ""), item.get("explanation", "")))
        body += [
            "A semantic mismatch is valid promoted evidence. It indicates that observed backend meaning and rendered UI meaning diverged under an allowlisted comparator. Missing or failed capture is reported separately and is not drift.\n\n",
            markdown_table(["Domain", "Mapping", "Severity", "Finding"], mismatches or [("None", "None", "None", "No promoted semantic mismatch; runtime may still be unvalidated.")]),
            "\n",
        ]
    elif kind == "accepted-limitations":
        rows = []
        for domain in model["domains"]:
            for item in domain.get("accepted_limitations", []):
                rows.append((domain["label"], "accepted-limitation", item))
            for item in domain.get("unsupported_operations", []):
                rows.append((domain["label"], "unsupported", item))
        body += [markdown_table(["Domain", "Type", "Description"], rows), "\n"]
    elif kind == "environments":
        body += [markdown_table(["Environment", "Proves", "Does not prove", "Status"], ((x["label"], ", ".join(x["proves"]), ", ".join(x["does_not_prove"]), x["status"]) for x in model["environments"])), "\n"]
    elif kind == "fixtures":
        body += ["Fixtures are synthetic, sanitized, schema-bound, stable-ID driven, and generated from the canonical registry. Timestamps are normalized. Raw runtime captures cannot become fixtures without explicit sanitization and promotion. Deprecated scenarios remain traceable until consumers are removed.\n\n",
                 markdown_table(["Scenario", "Stable IDs", "Fixture", "Runtime eligibility"], ((x["id"], ", ".join(x["stable_identity_fields"]), x["fixture"], x["live_eligibility"]) for x in model["scenarios"])), "\n"]
    elif kind == "oasdiff":
        body += ["`lite:api:breaking-changes` verifies the promoted baseline hash before comparing it with the generated Lite OpenAPI contract. The wrapper disables external references, writes JSON through an atomic temporary file, rejects malformed reports, and fails on unapproved breaking errors. Baseline replacement requires an explicit promotion manifest containing the previous hash, promoted hash, rationale, validation commands, and secret-safety review. No generated OpenAPI file is manually edited.\n\n**Runtime result:** unvalidated until the repository-local `oasdiff` binary is available and the gate is run.\n"]
    elif kind == "schemathesis":
        body += ["`lite:api:schemathesis` first compiles a deny-by-default local OpenAPI document containing only Recovery GET projections. The compiler rejects write methods, maintenance endpoints, streams, side-effectful compatibility GETs, non-loopback sources, and empty selections before Schemathesis starts. It discovers bounded safe resource identifiers through FastAPI reads, injects only sanitized examples, runs one deterministic worker with rate limits and retries, and writes sanitized JUnit, NDJSON, selection-manifest, and categorized summary evidence.\n\n`lite:api:schemathesis:discovery` compiles a broader GET-only schema and records non-gating evidence without coverage-phase unsupported-method probes or destructive operations.\n\n**Runtime result:** unvalidated until run against an explicitly configured loopback API or SSH loopback tunnel.\n"]
    elif kind == "accessibility":
        body += ["The repository already uses `@axe-core/playwright` and Storybook a11y. The all-tab parity model links accessibility evidence to Home, Apps, Devices, Security, Identity, Rules, and Backup & Restore scenarios. Serious and critical violations block the mocked gate; color contrast remains tracked separately by the existing test policy. Accessibility success is evidence for presentation quality, not a substitute for semantic field comparison.\n"]
    elif kind == "visual":
        body += ["Existing Playwright visual checks remain separate from semantic parity. The all-tab live capture records bounded desktop and mobile observations, while visual approval continues to govern screenshot baselines independently. A pixel change can require baseline review even when semantic parity passes, and semantic parity can fail while screenshots remain visually similar.\n"]
    elif kind == "performance":
        body += [markdown_table(["Profile", "VUs", "Duration", "Endpoints", "Thresholds", "Status"], ((x["id"], x.get("vus", f"1-{x.get('max_vus', 1)}"), f"{x['duration_seconds']}s", ", ".join(x["endpoints"]), ", ".join(f"{k}={v}" for k,v in x["thresholds"].items()), x["status"]) for x in model["performance_profiles"])), "\n\nThe edge profile is read-only, explicitly enabled, battery/memory/CPU guarded, and intentionally not a stress test. `lite:api:read-latency` captures two to five bounded cold/warm samples for Recovery and Security reads, records median/p95/max timing without host disclosure, and rejects non-loopback targets. Runtime thresholds are evidence-driven rather than guessed.\n"]
    elif kind == "gates":
        body += [markdown_table(["Gate", "Task", "Suite", "Evidence", "Blocking", "Environment", "Status"], ((x["label"], x["task"], x["suite"], x["evidence"], x["blocking"], x["environment"], x["status"]) for x in model["validation_gates"])), "\n"]
    elif kind == "ci":
        body += [markdown_table(["Workflow", "Job", "Task", "Suite", "Evidence", "Blocking", "Status"], ((x["workflow"], x["job"], x["task"], x["suite"], x["evidence"], x["blocking"], x["status"]) for x in model["ci_map"])), "\n"]
    elif kind == "evidence":
        body += ["Evidence traceability is generated from the same canonical domain, scenario, comparator, and gate registries. Raw API, browser, and Termux observations stay under `.pocketlab-dev/validation/parity` and are not tracked. The comparison step produces a sanitized normalized semantic result. `lite:evidence:runtime:promote` independently revalidates the raw allowlisted observations, recomputes their comparisons, binds the evidence hashes to a release tag and source commit, and writes only the promoted baseline under `contracts/parity`. Ordinary documentation generation consumes only that promoted baseline. A mismatch remains valid drift evidence; missing, stale, failed, or unavailable capture is classified separately and is not called drift.\n\n",
                 markdown_table(["Scenario", "Backend", "API", "Selector", "UI", "Story", "Browser", "Runtime"], ((x["id"], x["backend_arrangement"], x["api_projection"], x["selector"], ", ".join(x["ui_expected"]["visible_text"]), x["storybook_export"], x["mocked_playwright_test"], x["evidence_result"]) for x in model["scenarios"])), "\n"]
    elif kind == "triage":
        body += ["## Failure attribution\n\n- **backend ≠ API:** inspect manifest/current-state writers, transactions, projection refresh, and allowlist mapping.\n- **API ≠ selector:** inspect query key, selector normalizer, enum mapping, and omitted sensitive fields.\n- **selector ≠ rendered UI:** inspect conditional labels, component state, stale/offline indicators, and test selectors.\n- **mocked passes, live fails:** inspect Caddy origin, API freshness, authentication, runtime projection, and external browser configuration.\n- **API/browser match, authority differs:** treat as backend/projection drift; do not patch the UI to hide it.\n- **Storybook passes, page fails:** inspect integrated providers, routing, query invalidation, and overlay state.\n- **offline conflicts with live:** inspect Dexie snapshot revision and TanStack replacement rules.\n- **Schemathesis server error:** reproduce once, inspect sanitized PM2 traceback, and fix the route invariant; never document `500` as an accepted response.\n- **Schemathesis timeout:** classify streams separately, inspect cold/warm read-latency evidence, and adjust bounded endpoint behavior rather than disabling the gate.\n- **Expected `503`:** verify the response is documented, sanitized, retryable, and carries bounded `Retry-After`; focused read-only schemas must never activate maintenance.\n- **Discovery-only finding:** categorize it in the sanitized summary and keep it non-gating until an explicit contract policy is approved.\n"]
    elif kind == "runbook":
        body += ["## Symptoms\n\nA backend/API value is rendered with the wrong meaning, desktop and mobile disagree, an API/Termux observation differs, a selector maps the wrong state family, evidence is stale or incomplete, a capture fails, runtime is unavailable, or generated parity artifacts drift from the canonical model.\n\n## Read-only verification\n\n1. Verify the local API or bounded SSH loopback tunnel without exposing the phone directly.\n2. Run deterministic model, schema, selector, fixture, and generated-artifact checks.\n3. Capture sanitized read-only API and Termux observations for the affected domains.\n4. Run live desktop and mobile Playwright capture with the release tag and source commit bound.\n5. Run the semantic comparator and inspect failure attribution before interpreting any mismatch.\n6. Treat `drift-detected` as valid evidence; do not rewrite application behavior merely to make documentation pass.\n7. Treat `capture-failed`, `stale-evidence`, and `runtime-unavailable` as capture states, not drift.\n8. Promote only after the allowlisted observations and recomputed comparisons pass release/source/freshness validation.\n\n## Recovery\n\nDo not edit SQLite, generated baselines, runtime state, or frontend selectors merely to clear a parity report. Repair the owning backend, projection, selector, presentation mapping, capture adapter, or documented accepted limitation according to failure attribution. Destructive or identity-sensitive recovery remains backend-owned and must use existing explicit confirmations.\n"]
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
        body += [markdown_table(["Domain", "Status", "Runtime parity", "Known gaps"], ((x["label"], x["status"], x.get("runtime_parity", "unvalidated"), "; ".join(x["known_gaps"])) for x in model["domains"])), "\n\nRepository-derived contracts exist for all seven tabs. Successful, mapped, drifted, partial, failed, stale, unavailable, unsupported, and accepted-limitation outcomes remain distinct.\n"]
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
    digest = str(model.get("_source_fingerprint") or fingerprint(model))
    outputs: dict[Path, str] = {}
    pairwise_cases = generate_pairwise_cases(model)
    enriched = json.loads(json.dumps(model))
    enriched["pairwise_dimensions"] = pairwise_cases
    for filename, (kind, key) in CONTRACTS.items():
        contract = make_contract(enriched, kind, key, digest)
        validate_json(contract, CONTRACT_SCHEMA)
        outputs[GENERATED_ROOT / filename] = stable_json(contract)
    for domain in model["domains"]:
        domain_contract = {
            "schema_version": "1.0.0",
            "kind": "domain-fingerprint",
            "source_revision": model["source_revision"],
            "semantic_fingerprint": digest,
            "status": "generated",
            "items": [{
                "id": domain["id"],
                "fingerprint": hashlib.sha256(json.dumps(domain, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
                "api_routes": domain.get("api_routes", []),
                "selectors": domain.get("selectors", []),
                "semantic_mapping_ids": [item["id"] for item in domain.get("semantic_mappings", [])],
            }],
        }
        validate_json(domain_contract, CONTRACT_SCHEMA)
        outputs[GENERATED_ROOT / f"domain-{domain['id']}.json"] = stable_json(domain_contract)
    for scenario in model["scenarios"]:
        outputs[FIXTURE_ROOT / f"{scenario['id']}.json"] = stable_json(fixture_for(scenario, digest))
    outputs[REGISTRY_MODULE] = registry_module(model)
    for filename, title, kind in DOCS:
        outputs[DOC_ROOT / filename] = render_doc(kind, title, model, digest)
    baseline = model.get("runtime_verification_baseline", {})
    overall = baseline.get("status", "unvalidated")
    semantic_results = {d.get("runtime_parity", "unvalidated") for d in model["domains"]}
    all_semantic_verified = bool(semantic_results) and semantic_results <= {"verified", "verified-with-mapped-presentation"}
    production_status = "needs-review" if overall == "needs-review" else ("verified" if all_semantic_verified else "ready-with-accepted-limitations")
    prod = frontmatter("Projection parity readiness", digest, production_status).replace("audience: development", "audience: production")
    prod += "# Projection parity readiness\n\nPocket Lab Lite has deterministic repository-derived parity contracts for Home, Apps, Devices, Security, Identity, Rules, and Backup & Restore. Runtime capture remains explicit, read-only, sanitized, and independent of ordinary documentation generation.\n\n"
    prod += markdown_table(["Domain", "Repository", "Live API", "Live UI", "Live Termux", "Semantic parity"], ((d["label"], d["status"], d.get("live_api_coverage", "unvalidated"), d.get("live_ui_coverage", "unvalidated"), d.get("live_termux_coverage", "unvalidated"), d.get("runtime_parity", "unvalidated")) for d in model["domains"]))
    prod += "\n\nA promoted drift result is a review signal, not a documentation failure and not permission to change application behavior automatically.\n"
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
    expected_domains = ["home", "apps", "devices", "security", "identity", "rules", "recovery"]
    if [item["id"] for item in model["domains"]] != expected_domains:
        raise ValueError(f"canonical Lite domain order must be {expected_domains}")
    ids = {}
    sections = ["domains", "backend_authorities", "api_projections", "frontend_state_ownership", "field_mappings", "scenarios", "validation_gates", "environments", "ownership", "freshness", "comparator_registry", "runtime_scenarios", "pairwise_dimensions"]
    for section in sections:
        values = model[section]
        section_ids = [item["id"] for item in values]
        if len(section_ids) != len(set(section_ids)):
            raise ValueError(f"duplicate ids in {section}")
        ids[section] = set(section_ids)
    comparator_ids = ids["comparator_registry"]
    authority_by_id = {item["id"]: item for item in model["backend_authorities"]}
    projection_by_id = {item["id"]: item for item in model["api_projections"]}
    browser_observation_fields = {
        "headings", "button_names", "button_enabled", "status_labels", "screen_text",
        "server_identity_visible", "tailscale_ip_visible", "protection_toggle_pressed",
        "home_cpu_note", "recovery_status", "recovery_summary", "latest_backup_id",
        "stale_warning_visible", "backup_action_disabled", "status_label", "summary_label",
        "last_restore_id", "last_restore_status_label", "restore_history_count",
        "historical_preview_visible", "fresh_preview_required_visible",
    }
    mapping_ids: set[str] = set()
    runtime_by_domain = {domain: [] for domain in expected_domains}
    for domain in model["domains"]:
        for key in ("backend_authorities", "api_routes", "selectors", "query_keys", "frontend_screens", "live_observation_contract", "semantic_mappings", "accepted_limitations", "unsupported_operations", "known_gaps"):
            if key not in domain:
                raise ValueError(f"missing domain field {key}: {domain['id']}")
        if not domain["semantic_mappings"]:
            raise ValueError(f"domain has no semantic mappings: {domain['id']}")
        frontend_surface = ROOT / domain["frontend_surface"]
        if not frontend_surface.is_file():
            raise ValueError(f"frontend surface does not exist: {domain['id']}: {domain['frontend_surface']}")
        for linked_path in [*domain["storybook_exports"], *domain["mocked_scenarios"]]:
            if not (ROOT / linked_path).is_file():
                raise ValueError(f"linked parity source does not exist: {domain['id']}: {linked_path}")
        for authority_id in domain["backend_authorities"]:
            authority = authority_by_id.get(authority_id)
            if not authority or authority.get("domain") != domain["id"]:
                raise ValueError(f"invalid backend authority link: {domain['id']}:{authority_id}")
        for projection_id in domain["api_projections"]:
            projection = projection_by_id.get(projection_id)
            if not projection or projection.get("domain") != domain["id"]:
                raise ValueError(f"invalid API projection link: {domain['id']}:{projection_id}")
        backend_contract = (domain.get("live_observation_contract") or {}).get("backend") or {}
        route_ids = [item["id"] for item in backend_contract.get("routes", [])]
        if len(route_ids) != len(set(route_ids)):
            raise ValueError(f"duplicate live route ids: {domain['id']}")
        if any(item["path"] not in domain["api_routes"] for item in backend_contract.get("routes", [])):
            raise ValueError(f"live route is not declared by domain API routes: {domain['id']}")
        field_ids = [item["id"] for item in backend_contract.get("fields", [])]
        if len(field_ids) != len(set(field_ids)):
            raise ValueError(f"duplicate live observation field ids: {domain['id']}")
        if any(item["route"] not in set(route_ids) for item in backend_contract.get("fields", [])):
            raise ValueError(f"live observation references an unknown route: {domain['id']}")
        for field in backend_contract.get("fields", []):
            authority_operator = field.get("authority_operator", "exact")
            if authority_operator not in comparator_ids:
                raise ValueError(f"unknown Termux authority comparator {authority_operator}: {domain['id']}:{field.get('id')}")
        for mapping in domain["semantic_mappings"]:
            mapping_id = mapping["id"]
            backend_root = str(mapping.get("backend_path") or "$").split(".", 1)[0]
            frontend_root = str(mapping.get("frontend_path") or "$").split(".", 1)[0]
            if backend_root != "$" and backend_root not in set(field_ids):
                raise ValueError(f"semantic mapping references an unknown backend observation: {mapping_id}")
            if frontend_root != "$" and frontend_root not in browser_observation_fields:
                raise ValueError(f"semantic mapping references an unknown frontend observation: {mapping_id}")
            if mapping_id in mapping_ids:
                raise ValueError(f"duplicate semantic mapping id: {mapping_id}")
            mapping_ids.add(mapping_id)
            if mapping["operator"] not in comparator_ids:
                raise ValueError(f"unknown semantic comparator {mapping['operator']}: {mapping_id}")
    for scenario in model["runtime_scenarios"]:
        if scenario.get("domain") not in runtime_by_domain:
            raise ValueError(f"unknown runtime scenario domain: {scenario['id']}")
        runtime_by_domain[scenario["domain"]].append(scenario)
        domain = next(item for item in model["domains"] if item["id"] == scenario["domain"])
        if scenario.get("mapping_id") not in {item["id"] for item in domain["semantic_mappings"]}:
            raise ValueError(f"runtime scenario references an unknown semantic mapping: {scenario['id']}")
        if scenario.get("expected_runtime_parity") not in model["status_vocabulary"]:
            raise ValueError(f"unknown runtime scenario status: {scenario['id']}")
    for domain, rows in runtime_by_domain.items():
        expected = {row.get("expected_runtime_parity") for row in rows}
        if not {"verified-with-mapped-presentation", "drift-detected"} <= expected:
            raise ValueError(f"runtime scenarios must cover mapped presentation and deliberate drift: {domain}")
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
    pairwise = generate_pairwise_cases(model)
    if not pairwise or len(pairwise) > 24:
        raise ValueError("pairwise scenario generation must produce 1-24 cases")
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
    model = apply_runtime_baseline(model, load_runtime_baseline())
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
