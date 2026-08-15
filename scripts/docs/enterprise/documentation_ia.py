#!/usr/bin/env python3
"""Deterministic Documentation Platform information architecture and cross-link generator.

This module is intentionally static and repository-bound. It may read canonical source,
tracked generated contracts, and explicitly promoted/sanitized evidence already present in
the repository. It never captures runtime, polls services, promotes evidence, invokes
scanners, or mutates the Pocket Lab Lite control plane.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import posixpath
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "contracts/generated/documentation-enterprise"
DOC = ROOT / "docs/generated/enterprise"
EXPERIENCE = ROOT / "contracts/metadata/documentation-experience.json"
KNOWLEDGE_DOMAINS = ROOT / "contracts/generated/knowledge/domains.json"
KNOWLEDGE_JOURNEYS = ROOT / "contracts/generated/knowledge/journeys.json"
KNOWLEDGE_XREFS = ROOT / "contracts/generated/knowledge/cross-references.json"
DATA_LINEAGE = ROOT / "contracts/generated/knowledge/data-lineage.json"
API_UI_TRACE = ROOT / "contracts/generated/documentation-enterprise/api-ui-trace.json"
EVENTS = ROOT / "contracts/generated/documentation-enterprise/event-encyclopedia.json"
SECURITY_CONTROLS = ROOT / "contracts/generated/documentation-enterprise/security-controls.json"

IA_CONTRACT = OUT / "information-architecture.json"
CROSS_LINK_CONTRACT = OUT / "documentation-cross-links.json"
SEARCH_CONTRACT = OUT / "documentation-search.json"

AUDIENCES = (
    "user",
    "operator",
    "developer",
    "tester",
    "security-reviewer",
    "release-reviewer",
    "documentation-maintainer",
)
INTENTS = ("learn", "use", "operate", "build", "test", "diagnose", "audit", "reference")
PAGE_TYPES = (
    "overview",
    "guide",
    "journey",
    "architecture",
    "reference",
    "runbook",
    "evidence",
    "catalog",
    "handbook",
)
AUTHORITIES = ("canonical-source", "promoted-evidence", "derived", "human-review")
TOP_LEVEL = (
    "start-here",
    "use",
    "operate",
    "understand",
    "build-test",
    "security-assurance",
    "release-change",
    "reference",
    "documentation-platform",
)

PRIVATE = re.compile(
    r"(?:(?<![A-Za-z0-9._-])/home/[^/\s]+|/data/data/com\.termux/files/(?:home|usr)|[A-Za-z]:\\Users\\|nats://[^\s]+@)",
    re.I,
)
SECRET = re.compile(
    r"(?:BEGIN [A-Z ]*PRIVATE KEY|(?:password|passwd|token|secret|api[_-]?key|credential|authorization)\s*[=:]\s*[^\s,}\]]{6,})",
    re.I,
)
ABSOLUTE_MACHINE_PATH = re.compile(r"(?:/mnt/[a-z]/|/Users/[^/\s]+/|[A-Za-z]:\\Users\\)", re.I)
LOCALHOST_LEAK = re.compile(r"(?:127\.0\.0\.1|localhost)", re.I)
REMOTE_ASSET = re.compile(r"<(?:script|link|img)\b[^>]*(?:src|href)=[\"']https?://", re.I)

HUBS: dict[str, dict[str, Any]] = {
    "start-here": {
        "title": "Start Here",
        "path": "generated/enterprise/hubs/start-here.md",
        "audience": "user",
        "intents": ["learn", "use"],
        "description": "Choose the shortest path into Pocket Lab Lite documentation.",
        "links": [
            ("Use Pocket Lab", "generated/enterprise/hubs/use.md", "Add devices, use apps, run safety checks, and restore safely."),
            ("Operate Pocket Lab", "generated/enterprise/hubs/operate.md", "Install, check health, troubleshoot, recover, and manage remote access."),
            ("Build or Test Pocket Lab", "generated/enterprise/hubs/build-test.md", "Set up the repo, understand code, APIs, tests, parity, and contribution workflows."),
            ("Understand or Audit Pocket Lab", "generated/enterprise/hubs/understand.md", "Architecture, knowledge, trust boundaries, evidence, and decisions."),
            ("Security & Assurance", "generated/enterprise/hubs/security-assurance.md", "Threat Model, controls, evidence coverage, supply chain, and review boundaries."),
            ("Release & Change", "generated/enterprise/hubs/release-change.md", "What changed, release assurance, upgrade, provenance, and rollback."),
            ("Reference", "generated/enterprise/hubs/reference.md", "Exact APIs, events, configuration, components, tasks, reason codes, and catalogs."),
            ("Documentation Platform", "generated/enterprise/documentation-platform/index.md", "How this documentation system is generated, governed, validated, and secured."),
        ],
        "search_terms": ["quick start", "new to pocket lab", "how do i use pocket lab", "documentation map"],
    },
    "use": {
        "title": "Use",
        "path": "generated/enterprise/hubs/use.md",
        "audience": "user",
        "intents": ["use", "learn"],
        "description": "User-facing Pocket Lab Lite capabilities and common journeys.",
        "links": [
            ("Overview", "generated/production/tabs.md", "Current Lite tabs and user-facing surfaces."),
            ("Devices", "generated/production/devices.md", "Add, reconnect, restart, and retire devices safely."),
            ("Apps", "generated/production/apps.md", "Use the App Catalog and PhotoPrism through backend-owned actions."),
            ("Security & Safety", "generated/production/security.md", "Run bounded safety checks and review sanitized findings."),
            ("Backup & Restore", "generated/production/recovery.md", "Back up, verify, preview restore, and recover with confirmation."),
            ("Identity", "generated/production/identity.md", "Identity and password-change behavior currently exposed by Lite."),
            ("Rules", "generated/production/rules.md", "Current Rules surface and its documented limitations."),
            ("Common journeys", "generated/enterprise/journeys/devices.md", "Start with a feature journey and follow canonical technical truth."),
        ],
        "search_terms": ["add device", "restart agent", "app install", "security scan", "backup restore"],
    },
    "operate": {
        "title": "Operate",
        "path": "generated/enterprise/hubs/operate.md",
        "audience": "operator",
        "intents": ["operate", "diagnose"],
        "description": "Installation, health, diagnostics, incident response, and recovery.",
        "links": [
            ("Current health", "generated/production/intelligence/current-health.md", "Promoted operational-health projection; not live monitoring."),
            ("Fleet readiness", "generated/production/intelligence/fleet-readiness.md", "Device readiness and offline/degraded conditions."),
            ("Recovery readiness", "generated/production/intelligence/recovery-readiness.md", "Backup and restore readiness from canonical/promoted evidence."),
            ("Install & access", "generated/production/installation.md", "Install and access Pocket Lab Lite safely."),
            ("Remote access", "generated/production/remote-access.md", "Tailscale and remote-access readiness."),
            ("Services / PM2", "generated/production/services-pm2.md", "Service ownership and process operations."),
            ("Health & diagnostics", "generated/production/health-diagnostics.md", "Safe diagnostics without browser-side execution."),
            ("Incident runbooks", "generated/enterprise/operate/incident-runbooks.md", "Bounded operator runbooks and escalation."),
            ("Troubleshooting", "generated/enterprise/operate/troubleshooting.md", "Production troubleshooting and known failure modes."),
            ("Recovery", "generated/production/recovery.md", "Backup, verification, restore preview, and confirmed recovery."),
            ("Known limitations", "generated/production/limitations.md", "Current supported and incomplete behavior."),
        ],
        "search_terms": ["device offline", "agent stopped", "remote access not ready", "service failed", "recover pocket lab"],
    },
    "understand": {
        "title": "Understand",
        "path": "generated/enterprise/hubs/understand.md",
        "audience": "developer",
        "intents": ["learn", "reference"],
        "description": "Architecture, runtime topology, knowledge, data flows, and decisions.",
        "links": [
            ("System architecture", "generated/production/architecture/index.md", "Architecture overview derived from canonical architecture metadata."),
            ("Complete system map", "generated/production/architecture/complete-system.md", "End-to-end system map and ownership boundaries."),
            ("Components", "generated/production/architecture/component-catalog.md", "Generated component catalog; specialist component pages remain discoverable here."),
            ("Runtime topology", "generated/production/architecture/runtime-topology.md", "Process/runtime topology and supervision."),
            ("Trust boundaries", "generated/production/architecture/network-boundaries.md", "Network and trust-zone boundaries."),
            ("Data & projections", "generated/production/architecture/data-projections.md", "Durable state, projections, and data flow."),
            ("API / event flows", "generated/development/knowledge/events-nats.md", "NATS/event knowledge and API-related flow references."),
            ("Device lifecycle", "generated/production/architecture/device-onboarding.md", "Invite, bootstrap, enrollment, and recovery architecture."),
            ("App lifecycle", "generated/production/architecture/apps.md", "App Catalog and app lifecycle architecture."),
            ("Knowledgebase", "generated/production/knowledge/index.md", "Living generated knowledge for operators and engineers."),
            ("Knowledge Graph", "generated/enterprise/knowledgebase/knowledge-graph.md", "Canonical entity/relation explorer with bounded static interaction."),
            ("Architecture decisions", "generated/enterprise/reference/adr-intelligence.md", "Source-derived ADR intelligence and relationships."),
        ],
        "search_terms": ["how does pocket lab work", "architecture", "knowledge graph", "runtime topology", "data flow"],
    },
    "build-test": {
        "title": "Build & Test",
        "path": "generated/enterprise/hubs/build-test.md",
        "audience": "developer",
        "intents": ["build", "test"],
        "description": "Repository setup, contracts, frontend/backend ownership, testing, parity, and contribution.",
        "links": [
            ("Developer onboarding", "generated/development/index.md", "Development entry point and current engineering surface."),
            ("Repository structure", "generated/development/repository-setup.md", "WSL2 repository setup and layout."),
            ("Local development", "generated/development/local-services.md", "Local services and development runtime."),
            ("Frontend", "generated/development/frontend-api-usage.md", "Frontend API usage and browser control-plane boundary."),
            ("Backend / FastAPI", "generated/development/api-contract.md", "FastAPI control surface and contract detail."),
            ("NATS / events", "generated/development/lite-events.md", "Lite messaging and event contracts."),
            ("SQLite / data", "generated/development/lite-sqlite-schema.md", "SQLite schema and durable-state ownership."),
            ("APIs & contracts", "reference/api/lite-api.md", "Detailed Lite API reference."),
            ("UI state", "generated/development/ui-state-catalog.md", "Canonical frontend UI-state ownership."),
            ("Testing", "generated/development/testing.md", "Testing matrix and development validation."),
            ("Accessibility / visual", "generated/development/accessibility-visual.md", "Accessibility and visual regression gates."),
            ("Validation / parity", "generated/development/validation/parity/index.md", "Backend-to-Frontend semantic parity and validation evidence."),
            ("Task Reference", "generated/enterprise/engineering/task-reference.md", "Executable engineering handbook generated from Taskfiles."),
            ("Contributing", "generated/development/contribution-review.md", "Contribution and review workflow."),
        ],
        "search_terms": ["developer setup", "api frontend", "event nats", "test pocket lab", "task reference"],
    },
    "security-assurance": {
        "title": "Security & Assurance",
        "path": "generated/enterprise/hubs/security-assurance.md",
        "audience": "security-reviewer",
        "intents": ["audit", "diagnose"],
        "description": "Threat modeling, controls, evidence, supply chain, resilience, and human-review boundaries.",
        "links": [
            ("Threat Model", "generated/enterprise/threat-model/index.md", "Canonical generated threat-model experience and security poster."),
            ("Security Atlas", "generated/enterprise/threat-model/catalog.md", "Static Security Atlas catalog; modeled, not live traffic."),
            ("Trust boundaries", "generated/production/architecture/network-boundaries.md", "Architecture-owned trust boundaries."),
            ("Security controls", "generated/enterprise/reference/security-controls.md", "Threat → control → implementation → evidence traceability."),
            ("Assets & guardrails", "generated/enterprise/threat-model/assets-guardrails.md", "Protected assets, invariants, and guardrails."),
            ("Data lifecycle & privacy", "generated/enterprise/reference/data-lifecycle.md", "Sanitized lifecycle/privacy map."),
            ("Evidence coverage", "generated/development/intelligence/evidence-coverage.md", "Evidence coverage and confidence without invented certainty."),
            ("Dependency health", "generated/enterprise/reference/dependency-health.md", "Dependency health from canonical/promoted evidence."),
            ("Supply chain", "generated/enterprise/reference/supply-chain.md", "Normalized supply-chain evidence and execution boundary."),
            ("Reliability / resilience", "generated/enterprise/reference/reliability.md", "Engineering objectives and promoted observations."),
            ("Human review", "generated/enterprise/threat-model/evidence.md", "Residual risk, evidence provenance, and human-review requirements."),
        ],
        "search_terms": ["why do we believe this", "security control", "threat model", "supply chain", "evidence coverage"],
    },
    "release-change": {
        "title": "Release & Change",
        "path": "generated/enterprise/hubs/release-change.md",
        "audience": "release-reviewer",
        "intents": ["audit", "operate", "reference"],
        "description": "Release delta, assurance, compatibility, provenance, upgrade, and rollback.",
        "links": [
            ("What changed?", "generated/production/intelligence/what-changed.md", "Release comparison and operational impact."),
            ("Release assurance", "generated/enterprise/engineering/release-evidence.md", "Canonical release assurance and evidence state."),
            ("Upgrade & migration", "generated/enterprise/reference/upgrade-migration.md", "Fail-closed compatibility and migration guidance."),
            ("Compatibility", "generated/development/api-compatibility.md", "API compatibility and recorded breaking-change evidence."),
            ("Supply-chain changes", "generated/enterprise/reference/supply-chain-change.md", "Normalized release-to-release dependency/security changes."),
            ("Provenance", "generated/enterprise/release/index.md", "Release provenance model without substituting source HEAD for a release."),
            ("Rollback", "generated/production/rollback.md", "Rollback behavior and last-known-good recovery."),
            ("Release inventory", "generated/development/release-inventory.md", "Repository release inventory and evidence."),
        ],
        "search_terms": ["what changed", "release changed", "upgrade safe", "rollback", "release provenance"],
    },
    "reference": {
        "title": "Reference",
        "path": "generated/enterprise/hubs/reference.md",
        "audience": "developer",
        "intents": ["reference"],
        "description": "Exact technical definitions and canonical generated catalogs.",
        "links": [
            ("APIs", "reference/api/lite-api.md", "Detailed Lite HTTP API reference."),
            ("Events", "generated/enterprise/engineering/events.md", "Event encyclopedia with publisher/consumer evidence."),
            ("Configuration", "generated/enterprise/reference/configuration.md", "Configuration intelligence without secret values."),
            ("Components", "generated/production/architecture/component-catalog.md", "Architecture component catalog."),
            ("Tasks", "generated/enterprise/engineering/task-reference.md", "Task handbook generated from repository Taskfiles."),
            ("Reason codes", "generated/development/reason-codes.md", "Reason-code reference and failure semantics."),
            ("Ownership", "generated/enterprise/reference/ownership.md", "Source/runtime/recovery/control/presentation/evidence ownership."),
            ("ADRs", "generated/enterprise/reference/adr-intelligence.md", "Architecture-decision intelligence."),
            ("Glossary", "generated/production/knowledge/glossary.md", "Shared Pocket Lab vocabulary."),
            ("Knowledge Graph", "generated/enterprise/knowledgebase/knowledge-graph.md", "Stable entity/relation export and bounded explorer."),
            ("API-to-UI Trace", "generated/enterprise/reference/api-ui-trace.md", "User intent through UI, API, execution, and evidence."),
            ("Configuration & services", "generated/development/configuration-services.md", "Detailed implementation reference."),
        ],
        "search_terms": ["exact api", "event nats", "configuration", "reason code", "ownership", "knowledge graph"],
    },
}

JOURNEYS: dict[str, dict[str, Any]] = {
    "devices": {
        "title": "Devices Feature Journey",
        "domain": "devices",
        "audience": "user",
        "guide": "generated/production/devices.md",
        "architecture": "generated/production/architecture/device-onboarding.md",
        "journey_ids": ["journey:add-device", "journey:device-enrollment", "journey:device-reconnect", "journey:remove-old-device", "journey:restart-agent"],
    },
    "apps": {
        "title": "Apps Feature Journey",
        "domain": "apps",
        "audience": "user",
        "guide": "generated/production/apps.md",
        "architecture": "generated/production/architecture/apps.md",
        "journey_ids": ["journey:app-installation", "journey:photoprism-operation"],
    },
    "security": {
        "title": "Security & Safety Feature Journey",
        "domain": "security",
        "audience": "user",
        "guide": "generated/production/security.md",
        "architecture": "generated/production/architecture/security.md",
        "journey_ids": ["journey:security-review", "journey:security-scan"],
    },
    "recovery": {
        "title": "Backup & Restore Feature Journey",
        "domain": "recovery",
        "audience": "operator",
        "guide": "generated/production/recovery.md",
        "architecture": "generated/production/architecture/backup-recovery.md",
        "journey_ids": ["journey:backup-create", "journey:recovery-reconciliation", "journey:restore-preview", "journey:restore-execution"],
    },
    "remote-access": {
        "title": "Remote Access Feature Journey",
        "domain": "remote-access",
        "audience": "operator",
        "guide": "generated/production/remote-access.md",
        "architecture": "generated/production/architecture/remote-access.md",
        "journey_ids": ["journey:remote-access-readiness"],
    },
    "identity": {
        "title": "Identity Feature Journey",
        "domain": "identity",
        "audience": "user",
        "guide": "generated/production/identity.md",
        "architecture": "generated/production/architecture/components/api-guards.md",
        "journey_ids": ["journey:change-password"],
    },
    "release": {
        "title": "Release Feature Journey",
        "domain": "release",
        "audience": "release-reviewer",
        "guide": "generated/production/release.md",
        "architecture": "generated/production/architecture/release-rollback.md",
        "journey_ids": ["journey:release-update", "journey:rollback"],
    },
}

TRACE_ACTION_FEATURE = {
    "Add Device": "devices",
    "Restart Agent": "devices",
    "Remove Old Device": "devices",
    "Install App": "apps",
    "Open App": "apps",
    "Run Security Check": "security",
    "Back Up": "recovery",
    "Preview Restore": "recovery",
    "Restore": "recovery",
}

SEARCH_ALIASES = {
    "device offline": ["agent stopped", "node disconnected", "device not reachable", "restart agent"],
    "add device": ["join device", "device invite", "enroll device", "bootstrap device"],
    "remote access not ready": ["tailscale unavailable", "tailnet problem", "remote access broken"],
    "backup restore": ["backup", "restore", "recovery", "preview restore"],
    "app install": ["install app", "photoprism install", "app catalog"],
    "security scan": ["safety check", "lynis", "trivy", "security check"],
    "release changed": ["what changed", "release delta", "upgrade impact"],
    "api frontend": ["api ui", "frontend api", "api to ui"],
    "event nats": ["nats event", "jetstream event", "event encyclopedia"],
    "why do we believe this": ["evidence", "evidence coverage", "provenance", "confidence"],
    "documentation generator": ["docs generator", "documentation platform", "generation lifecycle"],
}

SEARCH_DESTINATIONS = {
    "device offline": ["generated/enterprise/hubs/operate.md", "generated/production/troubleshooting.md", "generated/enterprise/journeys/devices.md"],
    "add device": ["generated/enterprise/journeys/devices.md", "generated/production/devices.md"],
    "remote access not ready": ["generated/enterprise/journeys/remote-access.md", "generated/production/remote-access.md", "generated/enterprise/operate/troubleshooting.md"],
    "backup restore": ["generated/enterprise/journeys/recovery.md", "generated/production/recovery.md"],
    "app install": ["generated/enterprise/journeys/apps.md", "generated/production/apps.md"],
    "security scan": ["generated/enterprise/journeys/security.md", "generated/production/security.md"],
    "release changed": ["generated/enterprise/hubs/release-change.md", "generated/production/intelligence/what-changed.md"],
    "api frontend": ["generated/enterprise/reference/api-ui-trace.md", "generated/development/frontend-api-usage.md"],
    "event nats": ["generated/enterprise/engineering/events.md", "generated/development/knowledge/events-nats.md"],
    "why do we believe this": ["generated/enterprise/hubs/security-assurance.md", "generated/production/intelligence/why-we-believe-this.md"],
    "documentation generator": ["generated/enterprise/documentation-platform/generation-pipeline.md", "generated/enterprise/documentation-platform/architecture.md"],
}


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def stable(value: Any) -> str:
    return json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, separators=(",", ": ")) + "\n"


def digest(value: Any) -> str:
    raw = value if isinstance(value, bytes) else stable(value).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def docs_path(relative: str) -> Path:
    return ROOT / "docs" / relative


def page_url(path: str) -> str:
    clean = path.replace("\\", "/")
    if clean.endswith("index.md"):
        clean = clean[: -len("index.md")]
    elif clean.endswith(".md"):
        clean = clean[:-3]
    return "/" + clean.strip("/") + "/"


def page_id(path: str) -> str:
    clean = path.replace("\\", "/").strip("/")
    if clean.endswith(".md"):
        clean = clean[:-3]
    return "page:" + clean


def frontmatter(title: str, description: str, audience: str, page_type: str) -> str:
    safe_title = title.replace('"', "'")
    safe_desc = description.replace('"', "'")
    legacy_audience = {
        "user": "production",
        "operator": "production",
        "developer": "development",
        "tester": "development",
        "security-reviewer": "development",
        "release-reviewer": "development",
        "documentation-maintainer": "development",
    }.get(audience, "all")
    return (
        "---\n"
        f'title: "{safe_title}"\n'
        f'description: "{safe_desc}"\n'
        "generated: true\n"
        f"audience: {legacy_audience}\n"
        f"page_type: {page_type}\n"
        "confidence: generated\n"
        "---\n\n"
    )


def _route(path: str) -> str:
    clean = path.replace("\\", "/").strip("/")
    if clean == "index.md":
        return ""
    if clean.endswith("/index.md"):
        return clean[: -len("/index.md")]
    if clean.endswith(".md"):
        return clean[:-3]
    return clean.rstrip("/")


def _relative_url(source_path: str, target_path: str) -> str:
    """Return a browser-route-relative URL for raw HTML href attributes.

    MkDocs serves a page such as:

        generated/enterprise/hubs/start-here.md

    at the directory route:

        generated/enterprise/hubs/start-here/

    Raw HTML href values are resolved by the browser from that route.
    """

    source_route = _route(source_path)
    target_route = _route(target_path)

    relative = posixpath.relpath(
        target_route or ".",
        start=source_route or ".",
    )

    if relative == ".":
        return "./"

    return relative.rstrip("/") + "/"


def _markdown_relative_url(source_path: str, target_path: str) -> str:
    """Return a source-file-relative path for a Markdown link.

    MkDocs resolves Markdown links against source documents, so these
    links must retain the target .md filename. Pretty directory routes
    are reserved for raw HTML href attributes.
    """

    source_path = source_path.strip("/")
    target_path = target_path.strip("/")
    source_dir = posixpath.dirname(source_path)

    return posixpath.relpath(
        target_path,
        start=source_dir or ".",
    )


def _card(source_path: str, label: str, path: str, description: str) -> str:
    return (
        '<article class="pl-card">'
        f'<span class="pl-card-kicker">{html.escape(label)}</span>'
        f'<p>{html.escape(description)}</p>'
        f'<a class="pl-intent-link" href="{html.escape(_relative_url(source_path, path))}">Open {html.escape(label)}</a>'
        "</article>"
    )


def render_hub(slug: str, spec: dict[str, Any]) -> str:
    body = [
        f"# {spec['title']}",
        "",
        f'<div class="pl-page-lede"><strong>{html.escape(spec["description"])}</strong><p>Choose by task or question. Canonical technical pages are linked, not duplicated.</p></div>',
        "",
        '<div class="pl-card-grid">',
    ]
    body.extend(_card(spec["path"], label, path, description) for label, path, description in spec["links"])
    body += ["</div>"]
    if slug == "start-here":
        body += [
            "",
            "## New to Pocket Lab?",
            "",
            "1. [Read the overview](" + _markdown_relative_url(spec["path"], "index.md") + ").",
            "2. [Follow the Android / Termux quick start](" + _markdown_relative_url(spec["path"], "getting-started/android-termux.md") + ").",
            "3. [See the system architecture](" + _markdown_relative_url(spec["path"], "generated/production/architecture/complete-system.md") + ").",
            "4. [Learn the vocabulary](" + _markdown_relative_url(spec["path"], "generated/production/knowledge/vocabulary.md") + ") and [glossary](" + _markdown_relative_url(spec["path"], "generated/production/knowledge/glossary.md") + ").",
            "",
            "## Looking for something exact?",
            "",
            "Use local MkDocs search first, then open the [Reference hub](" + _markdown_relative_url(spec["path"], "generated/enterprise/hubs/reference.md") + ") or [Knowledge Graph](" + _markdown_relative_url(spec["path"], "generated/enterprise/knowledgebase/knowledge-graph.md") + ") when you need exact entities and relationships.",
        ]
    body += [
        "",
        "## Search terms",
        "",
        "Use local documentation search for: " + ", ".join(f"`{x}`" for x in spec.get("search_terms", [])) + ".",
        "",
        "## Authority",
        "",
        "This hub is a derived navigation projection. Linked canonical source, contracts, and promoted evidence retain their own authority.",
    ]
    return frontmatter(spec["title"], spec["description"], spec["audience"], "overview") + "\n".join(body).rstrip() + "\n"


def _entity_label(entity_id: str) -> str:
    return entity_id.split(":", 1)[-1].replace("-", " ").replace("_", " ")


def _bounded_expand(outgoing: dict[str, list[dict[str, Any]]], starts: Iterable[str], *, max_depth: int = 2, max_results: int = 80) -> list[dict[str, Any]]:
    queue: deque[tuple[str, int]] = deque((item, 0) for item in sorted(set(starts)))
    seen_nodes = set(starts)
    seen_edges: set[tuple[str, str, str]] = set()
    result: list[dict[str, Any]] = []
    while queue and len(result) < max_results:
        source, depth = queue.popleft()
        if depth >= max_depth:
            continue
        rows = sorted(outgoing.get(source, []), key=lambda x: (str(x.get("type")), str(x.get("target"))))
        for row in rows:
            target = str(row.get("target") or "")
            relation = str(row.get("type") or "related_to")
            if not target:
                continue
            edge_key = (source, relation, target)
            if edge_key in seen_edges:
                continue
            seen_edges.add(edge_key)
            result.append({"source": source, "relation_type": relation, "target": target, "depth": depth + 1})
            if len(result) >= max_results:
                break
            if target not in seen_nodes:
                seen_nodes.add(target)
                queue.append((target, depth + 1))
    return sorted(result, key=lambda x: (x["depth"], x["source"], x["relation_type"], x["target"]))


def _source_documents(root: Path, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    overrides = overrides or {}
    return {
        "journeys": read_json(root / "contracts/generated/knowledge/journeys.json", {}) or {},
        "cross-references": read_json(root / "contracts/generated/knowledge/cross-references.json", {}) or {},
        "data-lineage": read_json(root / "contracts/generated/knowledge/data-lineage.json", {}) or {},
        "api-ui-trace": overrides.get("api-ui-trace") or read_json(root / "contracts/generated/documentation-enterprise/api-ui-trace.json", {}) or {},
        "event-encyclopedia": overrides.get("event-encyclopedia") or read_json(root / "contracts/generated/documentation-enterprise/event-encyclopedia.json", {}) or {},
        "security-controls": overrides.get("security-controls") or read_json(root / "contracts/generated/documentation-enterprise/security-controls.json", {}) or {},
    }


def _journey_model(root: Path, slug: str, spec: dict[str, Any], sources: dict[str, Any]) -> dict[str, Any]:
    journeys_doc = sources["journeys"]
    journey_by_id = {str(x.get("id")): x for x in journeys_doc.get("items", []) if isinstance(x, dict) and x.get("id")}
    xrefs_doc = sources["cross-references"]
    outgoing = ((xrefs_doc.get("items") or {}).get("outgoing") or {}) if isinstance(xrefs_doc, dict) else {}
    selected = [journey_by_id[jid] for jid in spec["journey_ids"] if jid in journey_by_id]
    expanded = _bounded_expand(outgoing, [x["id"] for x in selected], max_depth=2, max_results=80)

    traces_doc = sources["api-ui-trace"]
    traces = traces_doc.get("items", [])
    trace_rows = [x for x in traces if isinstance(x, dict) and TRACE_ACTION_FEATURE.get(str(x.get("action"))) == slug]
    event_doc = sources["event-encyclopedia"]
    event_rows = event_doc.get("items", [])
    event_subjects = {str(x.get("nats_subject")) for x in event_rows if isinstance(x, dict) and x.get("nats_subject")}
    events = sorted({str(subject) for row in trace_rows for subject in (row.get("nats_or_event") or []) if str(subject) in event_subjects})

    data_rows = sources["data-lineage"].get("items", [])
    api_ids = sorted({x["target"] for x in expanded if x["target"].startswith("api:")})
    api_routes = {api_id.split(":", 2)[-1] for api_id in api_ids}
    data_tables = sorted({str(table) for row in data_rows if isinstance(row, dict) and str(row.get("route")) in api_routes for table in (row.get("sqlite") or [])})

    boundaries = sorted({x["target"].split(":", 1)[1] for x in expanded if x["target"].startswith("boundary:")})
    controls_source = sources["security-controls"]
    controls_doc = controls_source.get("items", [])
    controls = sorted({str(row.get("id")) for row in controls_doc if isinstance(row, dict) and row.get("id") and set(map(str, row.get("where_used") or row.get("boundaries") or [])) & set(boundaries)})

    categories: dict[str, list[str]] = defaultdict(list)
    for edge in expanded:
        prefix = edge["target"].split(":", 1)[0]
        categories[prefix].append(edge["target"])
    for key in list(categories):
        categories[key] = sorted(set(categories[key]))

    sources = sorted({str(src) for row in selected for src in (row.get("source_refs") or [])})
    execution_owners = sorted({str(row.get("execution_owner")) for row in trace_rows if row.get("execution_owner")})
    return {
        "id": f"feature-journey:{slug}",
        "slug": slug,
        "title": spec["title"],
        "domain": spec["domain"],
        "audience": spec["audience"],
        "guide": spec["guide"],
        "architecture": spec["architecture"],
        "source_journeys": [x["id"] for x in selected],
        "user_journeys": [x.get("name") for x in selected],
        "source_refs": sources,
        "api_entities": api_ids,
        "events": events,
        "data_tables": data_tables,
        "components": categories.get("component", []),
        "tests": categories.get("test", []),
        "boundaries": boundaries,
        "security_controls": controls,
        "troubleshooting": categories.get("troubleshooting", []),
        "evidence_entities": categories.get("evidence", []) + categories.get("audit", []),
        "execution_owners": execution_owners,
        "expanded_relations": expanded,
        "expansion": {"algorithm": "deterministic-bfs", "max_depth": 2, "max_results": 80, "cycle_detection": True},
        "confidence": "source-derived",
    }


def render_journey(model: dict[str, Any]) -> str:
    def chips(values: Iterable[str], empty: str) -> str:
        vals = list(values)
        if not vals:
            return f"- {empty}"
        return "\n".join(f"- `{value}`" for value in vals)

    source_names = [str(x) for x in model.get("user_journeys") or []]
    body = [
        f"# {model['title']}",
        "",
        '<div class="pl-page-lede"><strong>One feature journey, many canonical authorities.</strong><p>This page orchestrates existing repository knowledge. It does not duplicate or override the linked architecture, API, event, data, security, test, evidence, or runbook sources.</p></div>',
        "",
        "## What the feature does",
        "",
        f"Canonical user guide: [{_entity_label(model['domain']).title()} guide](" + _markdown_relative_url(f"generated/enterprise/journeys/{model['slug']}.md", model["guide"]) + ").",
        "",
        "## What the user sees",
        "",
        "Source-derived journeys in the canonical Knowledge Graph: " + (", ".join(source_names) if source_names else "none emitted") + ".",
        "",
        "## Typical user journey",
        "",
        chips(model["source_journeys"], "No canonical journey entity was available; no flow was fabricated."),
        "",
        "## Architecture",
        "",
        f"Primary architecture: [open architecture](" + _markdown_relative_url(f"generated/enterprise/journeys/{model['slug']}.md", model["architecture"]) + ").",
        "",
        "### Components",
        "",
        chips(model["components"], "No component relationship was emitted."),
        "",
        "## Frontend and FastAPI ownership",
        "",
        "### Source ownership",
        "",
        chips(model["source_refs"], "No source reference was emitted."),
        "",
        "### API relationships",
        "",
        chips(model["api_entities"], "No API relationship was emitted."),
        "",
        "## Events and execution",
        "",
        chips(model["events"], "No exact event subject relationship was proven by both API-to-UI trace and event encyclopedia, so none is emitted."),
        "",
        "Execution ownership: " + ("; ".join(model["execution_owners"]) if model["execution_owners"] else "use the component/API ownership links above; no additional execution owner was inferred") + ".",
        "",
        "## SQLite / data ownership",
        "",
        chips(model["data_tables"], "No SQLite relation was emitted for the journey APIs."),
        "",
        "## Evidence and audit projection",
        "",
        chips(model["evidence_entities"], "No feature-specific evidence entity was emitted; evidence remains backend-owned and is reached through the canonical linked projections."),
        "",
        "## Security controls and threat boundaries",
        "",
        "### Boundaries",
        "",
        chips(model["boundaries"], "No boundary relation was emitted."),
        "",
        "### Controls",
        "",
        chips(model["security_controls"], "No control was joined without a proven boundary relationship."),
        "",
        "## Tests and validation",
        "",
        chips(model["tests"], "No direct test relation was emitted."),
        "",
        "## Failure modes and recovery",
        "",
        chips(model["troubleshooting"], "No feature-specific troubleshooting entity was emitted; use the general Operate → Troubleshooting entry point."),
        "",
        "## Source and bounded expansion",
        "",
        "Relationships come from `contracts/generated/knowledge/cross-references.json` plus exact joins to data-lineage, event, API-to-UI, and security-control contracts. Expansion is deterministic BFS with depth ≤ 2, a strict result cap, cycle detection, and stable ordering. No runtime traversal or network call occurs.",
    ]
    return frontmatter(model["title"], f"Source-derived orchestration journey for {model['domain']}.", model["audience"], "journey") + "\n".join(body).rstrip() + "\n"


def _parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}
    result: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def _title_from_text(path: str, text: str) -> str:
    fm = _parse_frontmatter(text)
    if fm.get("title"):
        return fm["title"]
    match = re.search(r"^#\s+(.+?)\s*$", text, re.M)
    if match:
        return re.sub(r"\s+¶$", "", match.group(1)).strip()
    return Path(path).stem.replace("-", " ").title()


def _owner(path: str) -> str:
    exact = {
        "index.md": "start-here",
        "getting-started/android-termux.md": "start-here",
        "generated/production/knowledge/vocabulary.md": "start-here",
        "generated/production/knowledge/glossary.md": "start-here",
        "generated/production/tabs.md": "use",
        "generated/production/devices.md": "use",
        "generated/production/apps.md": "use",
        "generated/production/security.md": "use",
        "generated/production/recovery.md": "use",
        "generated/production/identity.md": "use",
        "generated/production/rules.md": "use",
        "generated/production/intelligence/what-changed.md": "release-change",
        "generated/production/intelligence/why-we-believe-this.md": "security-assurance",
        "generated/enterprise/engineering/release-evidence.md": "release-change",
        "generated/enterprise/reference/upgrade-migration.md": "release-change",
        "generated/enterprise/reference/supply-chain-change.md": "release-change",
        "generated/enterprise/reference/security-controls.md": "security-assurance",
        "generated/enterprise/reference/data-lifecycle.md": "security-assurance",
        "generated/enterprise/reference/dependency-health.md": "security-assurance",
        "generated/enterprise/reference/supply-chain.md": "security-assurance",
        "generated/enterprise/reference/reliability.md": "security-assurance",
        "generated/enterprise/engineering/task-reference.md": "build-test",
        "generated/enterprise/engineering/events.md": "reference",
        "generated/enterprise/engineering/troubleshooting.md": "build-test",
        "generated/enterprise/operate/incident-runbooks.md": "operate",
        "generated/enterprise/operate/troubleshooting.md": "operate",
        "generated/enterprise/reference/disaster-recovery.md": "operate",
        "generated/development/knowledge/events-nats.md": "understand",
        "generated/enterprise/reference/adr-intelligence.md": "understand",
        "generated/enterprise/reference/validation-coverage.md": "build-test",
        "generated/enterprise/reference/change-advisor.md": "build-test",
        "generated/enterprise/engineering/troubleshooting.md": "build-test",
        "generated/experience/evidence.md": "security-assurance",
        "generated/development/configuration-services.md": "reference",
        "generated/development/reason-codes.md": "reference",
        "generated/development/intelligence/evidence-coverage.md": "security-assurance",
        "generated/production/intelligence/why-we-believe-this.md": "security-assurance",
        "generated/development/api-compatibility.md": "release-change",
        "generated/development/release-inventory.md": "release-change",
        "generated/production/rollback.md": "release-change",
        "generated/production/knowledge/releases.md": "release-change",
        "generated/production/knowledge/releases/lite-2026-08-12-2.md": "release-change",
        "architecture/lite-architecture.md": "reference",
        "architecture/lite-security-sqlite-design-lock.md": "reference",
        "operations/bootstrap-lite.md": "reference",
        "operations/devices-durable-enrollment.md": "reference",
        "operations/devices-production-readiness.md": "reference",
        "security/lite-security-model.md": "reference",
        "recovery/backup-restore.md": "reference",
        "validation/lite-validation.md": "reference",
    }
    if path in exact:
        return exact[path]
    for slug, spec in HUBS.items():
        if path == spec["path"]:
            return slug
    if path == "generated/enterprise/documentation-platform/index.md" or path.startswith("generated/enterprise/documentation-platform/"):
        return "documentation-platform"
    if path.startswith("generated/enterprise/journeys/"):
        slug = Path(path).stem
        return {"remote-access": "operate", "release": "release-change"}.get(slug, "use")
    if path.startswith("generated/enterprise/threat-model/"):
        return "security-assurance"
    if path.startswith("generated/enterprise/knowledgebase/") or path.startswith("generated/enterprise/architecture/"):
        return "understand"
    if path.startswith("generated/enterprise/release/"):
        return "release-change"
    if path.startswith("generated/enterprise/reference/"):
        return "reference"
    if path.startswith("generated/production/architecture/") or path.startswith("generated/production/knowledge/"):
        return "understand"
    if path.startswith("generated/production/intelligence/"):
        return "operate"
    if path.startswith("generated/production/"):
        return "operate"
    if path.startswith("generated/development/"):
        return "build-test"
    if path.startswith("reference/"):
        return "reference"
    if path.startswith("architecture/"):
        return "understand"
    if path.startswith("security/"):
        return "security-assurance"
    if path.startswith("recovery/") or path.startswith("operations/") or path.startswith("getting-started/"):
        return "operate"
    return "reference"


def _domain(path: str, title: str) -> str:
    lower = f"{path} {title}".lower()
    checks = [
        ("documentation-platform", ["documentation-platform", "documentation platform"]),
        ("remote-access", ["remote-access", "remote access", "tailscale", "tailnet"]),
        ("recovery", ["recovery", "backup", "restore"]),
        ("security", ["security", "threat", "safety", "vulnerability", "supply-chain"]),
        ("devices", ["device", "fleet", "agent", "invite"]),
        ("apps", ["app", "catalog", "photoprism"]),
        ("identity", ["identity", "password"]),
        ("rules", ["rules"]),
        ("release", ["release", "upgrade", "rollback", "provenance"]),
        ("architecture", ["architecture", "topology", "component"]),
        ("testing", ["test", "validation", "parity", "playwright", "accessibility"]),
        ("api", ["api", "openapi", "fastapi"]),
        ("events", ["event", "nats", "jetstream", "asyncapi"]),
        ("data", ["sqlite", "data", "projection"]),
    ]
    for domain, words in checks:
        if any(word in lower for word in words):
            return domain
    return "documentation"


def _page_type(path: str, fm: dict[str, str], title: str) -> str:
    declared = fm.get("page_type", "").strip().lower()
    mapping = {"domain": "overview", "threat-model": "architecture", "release": "evidence"}
    if declared in PAGE_TYPES:
        return declared
    if declared in mapping:
        return mapping[declared]
    lower = f"{path} {title}".lower()
    if "/journeys/" in path:
        return "journey"
    if "runbook" in lower or "troubleshooting" in lower:
        return "runbook"
    if "architecture" in lower or "topology" in lower:
        return "architecture"
    if "evidence" in lower or "assurance" in lower:
        return "evidence"
    if "catalog" in lower or "encyclopedia" in lower or "inventory" in lower:
        return "catalog"
    if "handbook" in lower or "task reference" in lower:
        return "handbook"
    if Path(path).name == "index.md" or path in {spec["path"] for spec in HUBS.values()}:
        return "overview"
    return "reference"


def _audience(path: str, fm: dict[str, str]) -> tuple[str, list[str]]:
    owner = _owner(path)
    owner_map = {
        "start-here": "user",
        "use": "user",
        "operate": "operator",
        "understand": "developer",
        "build-test": "developer",
        "security-assurance": "security-reviewer",
        "release-change": "release-reviewer",
        "reference": "developer",
        "documentation-platform": "documentation-maintainer",
    }
    primary = owner_map.get(owner, "developer")
    declared = fm.get("audience", "")
    additions: list[str] = []
    if declared == "production":
        additions = ["user", "operator"]
    elif declared == "development":
        additions = ["developer", "tester"]
    elif declared == "all":
        additions = list(AUDIENCES)
    additions = [x for x in additions if x != primary]
    return primary, additions


def _intents(path: str, page_type: str, owner: str) -> list[str]:
    base = {
        "start-here": ["learn", "use"],
        "use": ["use", "learn"],
        "operate": ["operate", "diagnose"],
        "understand": ["learn", "reference"],
        "build-test": ["build", "test"],
        "security-assurance": ["audit", "diagnose"],
        "release-change": ["audit", "operate", "reference"],
        "reference": ["reference"],
        "documentation-platform": ["build", "audit", "reference"],
    }.get(owner, ["reference"])
    if page_type == "runbook":
        base = ["diagnose", "operate"]
    elif page_type == "guide" and "use" not in base:
        base = ["use", *base]
    return sorted(set(base), key=INTENTS.index)


def _generator_for(path: str, generated: bool) -> str:
    if not generated:
        return path
    if path.startswith(("generated/enterprise/hubs/", "generated/enterprise/journeys/", "generated/enterprise/documentation-platform/")):
        return "scripts/docs/enterprise/documentation_ia.py"
    if path.startswith("generated/enterprise/"):
        return "scripts/docs/enterprise/generate_enterprise_documentation.py"
    if path.startswith("generated/production/architecture/"):
        return "scripts/docs/graphviz/generate_lite_architecture.py"
    if "/knowledge/" in path or path.startswith("generated/enterprise/knowledgebase/"):
        return "scripts/docs/knowledge/generate_knowledge.py"
    if "/intelligence/" in path:
        return "scripts/docs/intelligence/generate_documentation_intelligence.py"
    if path.startswith("generated/production/") or path.startswith("generated/development/"):
        return "scripts/docs/lite/generate_docs.py"
    return "derived-generator-not-specialized"


def build_page_inventory(root: Path, planned_outputs: dict[Path, str]) -> list[dict[str, Any]]:
    texts: dict[str, str] = {}
    for path in sorted((root / "docs").rglob("*.md")):
        texts[path.relative_to(root / "docs").as_posix()] = path.read_text(encoding="utf-8", errors="ignore")
    for path, text in planned_outputs.items():
        if path.suffix == ".md" and path.is_relative_to(root / "docs"):
            texts[path.relative_to(root / "docs").as_posix()] = text

    inventory: list[dict[str, Any]] = []
    hub_related: dict[str, list[str]] = defaultdict(list)
    for hub in HUBS.values():
        for _, target, _ in hub["links"]:
            hub_related[target].append(hub["path"])

    for path in sorted(texts):
        text = texts[path]
        fm = _parse_frontmatter(text)
        title = _title_from_text(path, text)
        generated = fm.get("generated", "false").lower() == "true" or path.startswith("generated/")
        owner = _owner(path)
        ptype = _page_type(path, fm, title)
        primary, additional = _audience(path, fm)
        domain = _domain(path, title)
        generator = _generator_for(path, generated)
        authority = "derived" if generated else "canonical-source"
        inventory.append({
            "id": page_id(path),
            "title": title,
            "path": path,
            "url": page_url(path),
            "primary_audience": primary,
            "additional_audiences": additional,
            "intents": _intents(path, ptype, owner),
            "page_type": ptype,
            "domain": domain,
            "authority": authority,
            "confidence": fm.get("confidence") or ("generated" if generated else "source-derived"),
            "source_or_generator": generator,
            "canonical_source_references": [generator],
            "generated": generated,
            "primary_navigation_owner": owner,
            "contextual_navigation_owners": sorted({Path(x).stem for x in hub_related.get(path, [])}),
            "related_pages": sorted(page_id(x) for x in hub_related.get(path, [])),
        })
    return inventory


def build_cross_links(root: Path, journeys: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    links: list[dict[str, Any]] = []
    for slug, spec in HUBS.items():
        for label, target, _ in spec["links"]:
            links.append({
                "id": f"link:hub:{slug}:{page_id(target)}",
                "source": page_id(spec["path"]),
                "relation_type": "contextual-link",
                "target": page_id(target),
                "target_type": "page",
                "label": label,
                "evidence": ["scripts/docs/enterprise/documentation_ia.py"],
            })
    for slug, model in journeys.items():
        source = page_id(f"generated/enterprise/journeys/{slug}.md")
        for kind, path in (("guide", model["guide"]), ("architecture", model["architecture"])):
            links.append({
                "id": f"link:journey:{slug}:{kind}",
                "source": source,
                "relation_type": f"links-{kind}",
                "target": page_id(path),
                "target_type": "page",
                "label": kind,
                "evidence": ["scripts/docs/enterprise/documentation_ia.py", "contracts/generated/knowledge/journeys.json"],
            })
        for edge in model["expanded_relations"]:
            target_type = edge["target"].split(":", 1)[0]
            links.append({
                "id": "link:journey:" + slug + ":" + digest(edge)[:16],
                "source": source,
                "relation_type": edge["relation_type"],
                "target": edge["target"],
                "target_type": target_type,
                "depth": edge["depth"],
                "evidence": ["contracts/generated/knowledge/cross-references.json"],
            })
        for subject in model["events"]:
            links.append({
                "id": "link:journey:" + slug + ":event:" + digest(subject)[:16],
                "source": source,
                "relation_type": "emits-or-observes",
                "target": subject,
                "target_type": "event",
                "evidence": ["contracts/generated/documentation-enterprise/api-ui-trace.json", "contracts/generated/documentation-enterprise/event-encyclopedia.json"],
            })
        for table in model["data_tables"]:
            links.append({
                "id": "link:journey:" + slug + ":data:" + digest(table)[:16],
                "source": source,
                "relation_type": "owns-or-projects-data",
                "target": table,
                "target_type": "table",
                "evidence": ["contracts/generated/knowledge/data-lineage.json"],
            })
        for control in model["security_controls"]:
            links.append({
                "id": f"link:journey:{slug}:control:{control}",
                "source": source,
                "relation_type": "protected-by",
                "target": control,
                "target_type": "control",
                "evidence": ["contracts/generated/documentation-enterprise/security-controls.json", "contracts/generated/knowledge/cross-references.json"],
            })
    dedup = {row["id"]: row for row in links}
    return [dedup[key] for key in sorted(dedup)]


def build_search_contract() -> dict[str, Any]:
    entries = []
    for canonical in sorted(SEARCH_ALIASES):
        entries.append({
            "canonical": canonical,
            "aliases": sorted(set(SEARCH_ALIASES[canonical])),
            "destinations": SEARCH_DESTINATIONS[canonical],
            "intent_priority": "operator-diagnostic" if canonical in {"device offline", "remote access not ready", "security scan", "backup restore"} else "canonical-reference",
        })
    return {
        "schema_version": "1.0.0",
        "implementation": "static-local-search-metadata",
        "runtime_indexing": False,
        "ranking_model": {
            "algorithm": "weighted-lexical-static",
            "weights": {"exact_title": 100, "alias_match": 80, "intent_match": 30, "domain_match": 20, "page_type_priority": 10, "audience_match": 10, "canonical_bonus": 5, "limitation_penalty": -5},
            "note": "MkDocs remains the local search engine; hub/search-term content is generated so task-intent pages are indexed before deep repository internals where practical.",
        },
        "entries": entries,
    }


def render_documentation_platform_pages(contract: dict[str, Any], cross_links: list[dict[str, Any]], search: dict[str, Any]) -> dict[Path, str]:
    def page(name: str, desc: str, body: str, ptype: str = "reference") -> str:
        return frontmatter(name, desc, "documentation-maintainer", ptype) + body.strip() + "\n"

    authority_rows = [
        ("Architecture", "Canonical architecture metadata", "Generated architecture can project it; it cannot redefine it."),
        ("API", "FastAPI/OpenAPI contracts", "Generated docs cannot invent endpoints or compatibility."),
        ("Events", "AsyncAPI/canonical event metadata", "Generated docs cannot invent publishers, subscribers, durability, or ordering."),
        ("Runtime", "Explicitly promoted sanitized runtime evidence", "Repository HEAD never substitutes for promoted runtime."),
        ("Security", "Canonical threat/control models + promoted normalized evidence", "Modeled threat is not a confirmed exploit; residual risk remains human review."),
        ("Release", "Verified release records and release evidence", "Source HEAD is not a verified release baseline."),
        ("Generated documentation", "Derived projection only", "Generated Markdown/JSON does not become source authority."),
        ("Human risk acceptance", "Human review only", "Automation may surface evidence; it may not accept risk."),
    ]
    sources_table = "\n".join(f"| {a} | {b} | {c} |" for a, b, c in authority_rows)

    outputs: dict[Path, str] = {}
    outputs[DOC / "documentation-platform/index.md"] = page(
        "Documentation Platform",
        "How Pocket Lab Lite documentation is generated, governed, validated, and secured.",
        """# Documentation Platform

Pocket Lab Lite documentation is a deterministic engineering knowledge projection, not a control plane.

## Start with the system manual

<div class="pl-card-grid">
<article class="pl-card"><span class="pl-card-kicker">Architecture</span><p>Understand sources, contracts, generators, promotion, validation, and MkDocs boundaries.</p><a class="pl-intent-link" href="architecture/">Open architecture</a></article>
<article class="pl-card"><span class="pl-card-kicker">Information Architecture</span><p>See audience, intent, primary navigation ownership, contextual links, and feature journeys.</p><a class="pl-intent-link" href="information-architecture/">Open IA</a></article>
<article class="pl-card"><span class="pl-card-kicker">Sources of truth</span><p>Know which authority wins when source, generated docs, runtime evidence, and human review differ.</p><a class="pl-intent-link" href="sources-of-truth/">Open sources</a></article>
<article class="pl-card"><span class="pl-card-kicker">Validation</span><p>Understand determinism, drift, navigation, redaction, browser, and security fences.</p><a class="pl-intent-link" href="validation-testing/">Open validation</a></article>
<article class="pl-card"><span class="pl-card-kicker">Codebase Map</span><p>Inspect the Git-tracked repository model, ownership, source relationships, documentation health, and bounded static impact.</p><a class="pl-intent-link" href="../../development/knowledge/codebase-map/">Open Codebase Map</a></article>
</div>

The Codebase Map is a Documentation Platform projection. It consumes Git-tracked source plus existing Knowledge and Architecture contracts; it does not become a parallel runtime or architecture authority.

## Security boundary

MkDocs does not capture runtime, poll NATS, run scanners, promote evidence, execute shell commands, or access backend secrets.

## Generation lifecycle

`repository-owned source → canonical contracts → explicit capture → sanitization → explicit promotion → deterministic generators → knowledge/intelligence/architecture/enterprise projections → validation → MkDocs`
""",
        "overview",
    )
    outputs[DOC / "documentation-platform/how-to-use.md"] = page(
        "How to use these docs",
        "Audience- and task-oriented entry points for Pocket Lab Lite documentation.",
        """# How to use these docs

## Choose by question

- **What is it?** → Start Here.
- **How do I use it?** → Use.
- **How do I operate or recover it?** → Operate.
- **How does it work?** → Understand.
- **How do I change or test it?** → Build & Test.
- **How is it secured?** → Security & Assurance.
- **What changed?** → Release & Change.
- **What is the exact technical definition?** → Reference.

## Reading order

Use overview/hub pages first, follow Feature Journeys for cross-system orchestration, then open specialist canonical pages for exact definitions and evidence.
""",
        "guide",
    )
    outputs[DOC / "documentation-platform/architecture.md"] = page(
        "Documentation Platform Architecture",
        "Static generation architecture and authority boundaries.",
        """# Documentation Platform Architecture

## Purpose

Turn repository-owned engineering truth into deterministic, local/static documentation without becoming a runtime control plane.

## Flow

`source → canonical contracts → explicit capture/promotion boundary → deterministic generators → generated contracts/pages → validation → MkDocs`

## Ownership

- Canonical source owns architecture, API, event, policy, and release semantics.
- Explicit capture/promotion tools own promoted evidence ingestion.
- Generators own deterministic derived projections.
- MkDocs owns static presentation/search/navigation only.

## Failure behavior

Generation fails closed on drift, dangling IA relations, invalid classification, unsafe path/secret exposure, or missing required canonical navigation targets.
""",
        "architecture",
    )
    outputs[DOC / "documentation-platform/information-architecture.md"] = page(
        "Information Architecture",
        "Audience, intent, page inventory, navigation ownership, and hub model.",
        f"""# Information Architecture

## Top-level model

{', '.join('`' + x + '`' for x in contract['top_level'])}

## Inventory

- Pages: **{len(contract['pages'])}**
- Top-level hubs: **{len(contract['top_level'])}**
- Feature Journeys: **{len(contract['feature_journeys'])}**
- Cross-links: **{len(cross_links)}**

Every canonical page has one primary navigation owner. Other hubs may link contextually without duplicating the canonical destination.

## Machine contract

`contracts/generated/documentation-enterprise/information-architecture.json`
""",
    )
    outputs[DOC / "documentation-platform/audience-intent.md"] = page(
        "Audience & intent model",
        "Supported reader roles and documentation intents.",
        "# Audience & intent model\n\n## Audiences\n\n" + "\n".join(f"- `{x}`" for x in AUDIENCES) + "\n\n## Intents\n\n" + "\n".join(f"- `{x}`" for x in INTENTS) + "\n\nAudience is a discovery aid, not a new source-of-truth boundary.\n",
    )
    outputs[DOC / "documentation-platform/sources-of-truth.md"] = page(
        "Sources of Truth",
        "Explicit authority ordering and what may not override what.",
        "# Sources of Truth\n\n| Area | Authority | What may not override it |\n| --- | --- | --- |\n" + sources_table + "\n\n## What may not override what\n\nGenerated output cannot override canonical source. Documentation Intelligence cannot mutate source/runtime. Threat Model overlays cannot redefine architecture topology. Knowledge Graph relations cannot be invented when source relations are missing. MkDocs cannot capture or promote evidence.\n",
    )
    outputs[DOC / "documentation-platform/content-model.md"] = page(
        "Content model",
        "How canonical source, derived projections, journeys, runbooks, evidence, and references relate.",
        """# Content model

## Principle

A page is either a canonical source/reference surface or a derived orchestration/presentation surface. Feature Journeys and hubs link canonical truth rather than copy it.

## Relationship model

`page → canonical source`, `feature → architecture/API/event/data/test/evidence/control/runbook`, and specialist relations are emitted only when canonical contracts prove them.
""",
    )
    outputs[DOC / "documentation-platform/page-types.md"] = page(
        "Documentation page types",
        "Progressively adopted page anatomy contract.",
        "# Documentation page types\n\n" + "\n".join(f"## {x.replace('-', ' ').title()}\n\nMachine classification: `{x}`.\n" for x in PAGE_TYPES) + "\nLegacy pages may adopt the contract progressively; generation does not force a wholesale frontmatter rewrite.\n",
    )
    outputs[DOC / "documentation-platform/generation-pipeline.md"] = page(
        "Generation lifecycle",
        "Deterministic documentation generation and explicit evidence-promotion boundary.",
        """# Generation lifecycle

`repository source → canonical contracts → explicit runtime/security capture → sanitization → explicit promotion → deterministic generation → validation → MkDocs`

## Hard boundary

`task lite:docs:sync` regenerates/checks documentation. It does not capture runtime, promote evidence, run heavy scanners, or access secrets.

Generated output remains derived and reproducible; it never becomes source authority.
""",
    )
    outputs[DOC / "documentation-platform/evidence-model.md"] = page(
        "Evidence & promotion model",
        "Evidence authority, freshness, sanitization, and explicit promotion boundaries.",
        """# Evidence & promotion model

Source-derived semantics, promoted runtime observations, security/scanner evidence, validation evidence, and release manifests remain distinct authorities.

Missing, partial, stale, or unvalidated evidence stays explicit. Presentation logic may not upgrade it to verified or healthy.
""",
        "evidence",
    )
    outputs[DOC / "documentation-platform/cross-link-model.md"] = page(
        "Cross-link model",
        "Deterministic bounded relationship joins for navigation and Feature Journeys.",
        f"""# Cross-link model

Cross-links are generated from canonical page targets and the Knowledge Graph cross-reference index. The current contract contains **{len(cross_links)}** stable relations.

## Algorithm

- build adjacency/reverse indexes once;
- use deterministic set joins;
- use bounded BFS only where contextual expansion adds value;
- max depth 2, strict result caps, cycle detection;
- never perform runtime traversal or network calls;
- never invent a missing relationship.

Machine contract: `contracts/generated/documentation-enterprise/documentation-cross-links.json`.
""",
    )
    outputs[DOC / "documentation-platform/search-model.md"] = page(
        "Search & discovery",
        "Static local search metadata, aliases, and weighted intent model.",
        f"""# Search & discovery

Search remains local/static. No hosted search, vector database, RAG service, or runtime indexer is required.

## Ranking model

`{search['ranking_model']['algorithm']}` with deterministic title/alias/intent/domain/page-type/audience/canonical weighting.

## Alias groups

{len(search['entries'])} task-oriented alias groups are emitted into the machine contract and surfaced in hub content so MkDocs local search can discover operator/user entry points before deep implementation pages where practical.

Machine contract: `contracts/generated/documentation-enterprise/documentation-search.json`.
""",
    )
    outputs[DOC / "documentation-platform/design-system.md"] = page(
        "Design system",
        "Shared static documentation visual language and progressive disclosure rules.",
        """# Design system

Use existing Pocket Lab cards, chips, status semantics, responsive layouts, semantic HTML, keyboard-safe navigation, local assets, and reduced-motion support. Avoid remote fonts/scripts, giant tables without responsive treatment, continuous animation, or blanket overflow hiding.
""",
    )
    outputs[DOC / "documentation-platform/validation-testing.md"] = page(
        "Validation & testing",
        "Determinism, IA, security, navigation, browser, and drift validation.",
        """# Validation & testing

Validation covers duplicate IDs/owners, dangling links/relations, invalid taxonomy values, source-path validity, generated/manual classification, private-path/secret exposure, deterministic ordering, regeneration drift, strict MkDocs, desktop/mobile navigation, accessibility, search discoverability, specialist deep links, and bounded relationship expansion.

Pairwise/combinatorial browser coverage is bounded; no full Cartesian-product runtime suite is generated.
""",
        "handbook",
    )
    outputs[DOC / "documentation-platform/contribution.md"] = page(
        "Contribution",
        "How to change documentation source, generators, navigation, and generated artifacts safely.",
        """# Contribution

1. Change canonical source/metadata or the owning generator first.
2. Regenerate tracked artifacts.
3. Run focused tests, deterministic generation checks, strict MkDocs, and browser tests.
4. Stage only intentional source/generated/test/navigation changes.
5. Never hand-edit generated artifacts as the authority.
""",
        "guide",
    )
    outputs[DOC / "documentation-platform/operations-troubleshooting.md"] = page(
        "Operations & troubleshooting",
        "Documentation generation/drift troubleshooting without runtime side effects.",
        """# Operations & troubleshooting

## Generated drift

Run the owning generator in check mode, then regenerate from canonical source. Do not patch generated Markdown by hand.

## Broken navigation or relation

Use the IA validation error to identify the missing path/entity or duplicate owner. Fix source metadata/navigation and regenerate.

## Evidence mismatch

Verify capture/promotion inputs outside MkDocs. Documentation generation must never compensate by reading live runtime or substituting repository HEAD.
""",
        "reference",
    )
    outputs[DOC / "documentation-platform/security-boundaries.md"] = page(
        "Security boundaries",
        "Documentation Platform security invariants and prohibited behaviors.",
        """# Security boundaries

- MkDocs does not capture runtime, poll NATS, run scanners, promote evidence, execute shell commands, or access backend secrets.
- Generated IA/search/cross-link contracts reject private machine paths and secret-like values before writing.
- Knowledge Graph and Feature Journeys may only emit relationships backed by canonical repository contracts.
- Runtime/security evidence must be explicitly sanitized and promoted before documentation ingestion.
""",
        "architecture",
    )
    outputs[DOC / "documentation-platform/known-limitations.md"] = page(
        "Known limitations",
        "Explicit Documentation Platform limitations and non-goals.",
        """# Known limitations

- Local MkDocs search is lexical; no semantic/vector retrieval is claimed.
- Feature Journeys remain incomplete where canonical relations are missing; missing relations are not fabricated.
- Generated documentation is a projection and may be stale until regeneration/promotion occurs.
- Human risk acceptance, ambiguous architecture interpretation, and evidence sufficiency remain human-review responsibilities.
""",
    )
    return outputs


def build(root: Path = ROOT, overrides: dict[str, Any] | None = None) -> tuple[dict[Path, str], dict[str, Any], dict[str, Any], dict[str, Any]]:
    outputs: dict[Path, str] = {}
    for slug, spec in HUBS.items():
        outputs[root / "docs" / spec["path"]] = render_hub(slug, spec)

    overrides = overrides or {}
    sources = _source_documents(root, overrides)
    journey_models = {slug: _journey_model(root, slug, spec, sources) for slug, spec in JOURNEYS.items()}
    for slug, model in journey_models.items():
        outputs[root / "docs/generated/enterprise/journeys" / f"{slug}.md"] = render_journey(model)

    cross_links = build_cross_links(root, journey_models)
    search_contract = build_search_contract()

    # Build a provisional inventory that already includes new hubs/journeys. Documentation
    # Platform self-pages are added before the final inventory pass below.
    provisional_contract = {
        "schema_version": "1.0.0",
        "generator": "scripts/docs/enterprise/documentation_ia.py",
        "top_level": list(TOP_LEVEL),
        "audiences": list(AUDIENCES),
        "intents": list(INTENTS),
        "page_types": list(PAGE_TYPES),
        "authorities": list(AUTHORITIES),
        "pages": [],
        "feature_journeys": [journey_models[key] for key in sorted(journey_models)],
        "algorithms": {
            "page_indexing": "single-pass O(N) classification with precomputed maps",
            "relationship_expansion": "bounded deterministic BFS depth<=2, capped results, cycle detection",
            "cross_link_join": "indexed set intersection and exact entity/path joins",
            "serialization": "stable sorted JSON",
            "memoization": "contracts parsed once per generation invocation",
            "test_matrix": "bounded pairwise/covering combinations; no runtime Cartesian explosion",
        },
    }
    outputs.update(render_documentation_platform_pages(provisional_contract, cross_links, search_contract))
    pages = build_page_inventory(root, outputs)
    contract = dict(provisional_contract)
    contract["pages"] = pages
    contract["page_count"] = len(pages)
    contract["cross_link_count"] = len(cross_links)
    contract["source_fingerprint"] = digest({"pages": pages, "journeys": contract["feature_journeys"], "top_level": contract["top_level"]})

    # Re-render IA self-documentation with final page counts.
    outputs.update(render_documentation_platform_pages(contract, cross_links, search_contract))
    # Rebuild inventory after final self-page content. IDs/classification are unchanged, but
    # this makes the contract explicitly based on the exact generated page set.
    contract["pages"] = build_page_inventory(root, outputs)
    contract["page_count"] = len(contract["pages"])
    contract["source_fingerprint"] = digest({"pages": contract["pages"], "journeys": contract["feature_journeys"], "top_level": contract["top_level"]})

    cross_contract = {
        "schema_version": "1.0.0",
        "generator": "scripts/docs/enterprise/documentation_ia.py",
        "algorithm": {"adjacency_index": True, "max_depth": 2, "max_results_per_feature": 80, "cycle_detection": True, "runtime_traversal": False},
        "relations": cross_links,
    }
    outputs[root / "contracts/generated/documentation-enterprise/information-architecture.json"] = stable(contract)
    outputs[root / "contracts/generated/documentation-enterprise/documentation-cross-links.json"] = stable(cross_contract)
    outputs[root / "contracts/generated/documentation-enterprise/documentation-search.json"] = stable(search_contract)

    errors = validate(root, outputs, contract, cross_contract, search_contract, overrides=overrides)
    if errors:
        raise ValueError("Documentation IA validation failed:\n" + "\n".join(f"- {x}" for x in errors))
    return outputs, contract, cross_contract, search_contract


def _nav_markdown_targets(mkdocs_text: str) -> list[str]:
    return sorted(set(re.findall(r":\s*([^\s#]+\.md)\s*$", mkdocs_text, re.M)))


def _nav_primary_assignments(mkdocs_text: str) -> dict[str, list[str]]:
    label_to_owner = {
        "Start Here": "start-here",
        "Use": "use",
        "Operate": "operate",
        "Understand": "understand",
        "Build & Test": "build-test",
        "Security & Assurance": "security-assurance",
        "Release & Change": "release-change",
        "Reference": "reference",
        "Documentation Platform": "documentation-platform",
    }
    assignments: dict[str, list[str]] = defaultdict(list)
    current_owner = ""
    in_nav = False
    for line in mkdocs_text.splitlines():
        if line == "nav:":
            in_nav = True
            continue
        if not in_nav:
            continue
        top = re.match(r"^  - ([^:]+):(?:\s*([^\s#]+\.md))?\s*$", line)
        if top:
            label = top.group(1).strip()
            current_owner = label_to_owner.get(label, "")
            target = top.group(2)
            if current_owner and target:
                assignments[target].append(current_owner)
            continue
        target = re.search(r":\s*([^\s#]+\.md)\s*$", line)
        if current_owner and target:
            assignments[target.group(1)].append(current_owner)
    return {key: value for key, value in sorted(assignments.items())}


def validate(root: Path, outputs: dict[Path, str], contract: dict[str, Any], cross_contract: dict[str, Any], search_contract: dict[str, Any], *, overrides: dict[str, Any] | None = None) -> list[str]:
    errors: list[str] = []
    planned = {path.relative_to(root / "docs").as_posix() for path in outputs if path.suffix == ".md" and path.is_relative_to(root / "docs")}
    existing = {path.relative_to(root / "docs").as_posix() for path in (root / "docs").rglob("*.md")}
    all_pages = existing | planned

    ids: set[str] = set()
    path_to_owner: dict[str, str] = {}
    allowed_domains_doc = read_json(root / "contracts/generated/knowledge/domains.json", {}) or {}
    allowed_domains = {str(x.get("domain")) for x in allowed_domains_doc.get("items", []) if isinstance(x, dict) and x.get("domain")}
    allowed_domains |= {"documentation", "documentation-platform", "architecture", "testing", "data", "events", "api", "release", "platform", "remote-access"}

    for page in contract.get("pages", []):
        pid = str(page.get("id"))
        path = str(page.get("path"))
        if pid in ids:
            errors.append(f"duplicate page id: {pid}")
        ids.add(pid)
        owner = str(page.get("primary_navigation_owner"))
        if owner not in TOP_LEVEL:
            errors.append(f"unknown primary navigation owner for {path}: {owner}")
        if path in path_to_owner and path_to_owner[path] != owner:
            errors.append(f"duplicate canonical navigation ownership for {path}: {path_to_owner[path]} vs {owner}")
        path_to_owner[path] = owner
        if page.get("primary_audience") not in AUDIENCES or any(x not in AUDIENCES for x in page.get("additional_audiences", [])):
            errors.append(f"unknown audience classification: {path}")
        if any(x not in INTENTS for x in page.get("intents", [])):
            errors.append(f"unknown intent classification: {path}")
        if page.get("page_type") not in PAGE_TYPES:
            errors.append(f"unknown page type: {path}: {page.get('page_type')}")
        if page.get("authority") not in AUTHORITIES:
            errors.append(f"unknown authority: {path}: {page.get('authority')}")
        if page.get("domain") not in allowed_domains:
            errors.append(f"unknown domain: {path}: {page.get('domain')}")
        if path not in all_pages:
            errors.append(f"page inventory path missing: {path}")
        generator = str(page.get("source_or_generator") or "")
        if page.get("generated") and generator != "derived-generator-not-specialized" and not (root / generator).exists():
            errors.append(f"invalid generator/source path for {path}: {generator}")
        if not page.get("generated") and not (root / "docs" / path).exists():
            errors.append(f"invalid manual page classification: {path}")

    required = [spec["path"] for spec in HUBS.values()] + ["generated/enterprise/documentation-platform/index.md"]
    for path in required:
        if path not in all_pages:
            errors.append(f"orphaned required hub: {path}")

    xrefs_doc = read_json(root / "contracts/generated/knowledge/cross-references.json", {}) or {}
    xitems = xrefs_doc.get("items") or {}
    known_entities = set((xitems.get("incoming") or {}).keys()) | set((xitems.get("outgoing") or {}).keys())
    for rows in (xitems.get("outgoing") or {}).values():
        for row in rows or []:
            if isinstance(row, dict) and row.get("target"):
                known_entities.add(str(row["target"]))
    overrides = overrides or {}
    event_source = overrides.get("event-encyclopedia") or read_json(root / "contracts/generated/documentation-enterprise/event-encyclopedia.json", {}) or {}
    control_source = overrides.get("security-controls") or read_json(root / "contracts/generated/documentation-enterprise/security-controls.json", {}) or {}
    event_subjects = {str(x.get("nats_subject")) for x in event_source.get("items", []) if isinstance(x, dict) and x.get("nats_subject")}
    control_ids = {str(x.get("id")) for x in control_source.get("items", []) if isinstance(x, dict) and x.get("id")}
    data_tables = {str(t) for row in (read_json(root / "contracts/generated/knowledge/data-lineage.json", {}) or {}).get("items", []) if isinstance(row, dict) for t in (row.get("sqlite") or [])}

    relation_ids: set[str] = set()
    for row in cross_contract.get("relations", []):
        rid = str(row.get("id"))
        if rid in relation_ids:
            errors.append(f"duplicate relation id: {rid}")
        relation_ids.add(rid)
        source = str(row.get("source"))
        if source.startswith("page:") and source not in ids:
            errors.append(f"relation source page missing: {rid}: {source}")
        target = str(row.get("target"))
        target_type = str(row.get("target_type"))
        if target_type == "page" and target not in ids:
            errors.append(f"relation target page missing: {rid}: {target}")
        elif target_type == "event" and target not in event_subjects:
            errors.append(f"relation event target missing: {rid}: {target}")
        elif target_type == "control" and target not in control_ids:
            errors.append(f"relation control target missing: {rid}: {target}")
        elif target_type == "table" and target not in data_tables and target not in known_entities:
            errors.append(f"relation data target missing: {rid}: {target}")
        elif target_type not in {"page", "event", "control", "table"} and target not in known_entities:
            errors.append(f"relation entity target missing: {rid}: {target}")

    for entry in search_contract.get("entries", []):
        for destination in entry.get("destinations", []):
            if destination not in all_pages:
                errors.append(f"search destination missing: {entry.get('canonical')}: {destination}")

    # Validate the rendered IA links themselves, not only the source relationship contract.
    # Relative links are resolved from the rendered page route because MkDocs serves each
    # Markdown page as a directory URL.
    known_routes = {_route(path) for path in all_pages}
    for output_path, text in outputs.items():
        if output_path.suffix != ".md" or not output_path.is_relative_to(root / "docs"):
            continue
        source_path = output_path.relative_to(root / "docs").as_posix()
        source_route = _route(source_path)

        # Raw HTML href values are browser-route-relative. Markdown links
        # are source-file-relative and retain their .md filename.
        html_links = re.findall(r'href="([^"]+)"', text)
        markdown_links = re.findall(r"\]\(([^)]+)\)", text)

        for href in html_links:
            href = href.strip()
            if not href or href.startswith(("#", "http://", "https://", "mailto:")):
                continue

            clean_href = href.split("#", 1)[0].split("?", 1)[0].rstrip("/")
            if not clean_href:
                continue

            if clean_href.startswith("/"):
                resolved = clean_href.strip("/")
            else:
                resolved = posixpath.normpath(
                    posixpath.join(source_route or ".", clean_href)
                )

            if resolved == ".":
                resolved = ""

            if resolved not in known_routes:
                errors.append(
                    f"broken generated IA html link: "
                    f"{source_path}: {href} -> {resolved}"
                )

        source_dir = posixpath.dirname(source_path)

        for href in markdown_links:
            href = href.strip()
            if not href or href.startswith(("#", "http://", "https://", "mailto:")):
                continue

            clean_href = href.split("#", 1)[0].split("?", 1)[0]
            if not clean_href:
                continue

            if clean_href.startswith("/"):
                resolved_source = clean_href.strip("/")
            else:
                resolved_source = posixpath.normpath(
                    posixpath.join(source_dir or ".", clean_href)
                )

            resolved = _route(resolved_source)

            if resolved not in known_routes:
                errors.append(
                    f"broken generated IA markdown link: "
                    f"{source_path}: {href} -> {resolved_source}"
                )

    # The new IA owns the top-level navigation. Existing specialist pages remain available by
    # stable URL even when no longer expanded in the global nav.
    mkdocs = (root / "mkdocs.yml").read_text(encoding="utf-8", errors="ignore") if (root / "mkdocs.yml").exists() else ""
    if mkdocs:
        for path in _nav_markdown_targets(mkdocs):
            if path not in all_pages:
                errors.append(f"mkdocs nav target missing: {path}")
        assignments = _nav_primary_assignments(mkdocs)
        expected_top_level = {
            "  - Start Here:",
            "  - Use:",
            "  - Operate:",
            "  - Understand:",
            "  - Build & Test:",
            "  - Security & Assurance:",
            "  - Release & Change:",
            "  - Reference:",
            "  - Documentation Platform:",
        }
        nav_text = mkdocs.split("\nnav:\n", 1)[1] if "\nnav:\n" in mkdocs else mkdocs
        actual_top_level = {line for line in nav_text.splitlines() if re.match(r"^  - [^:]+:\s*$", line)}
        if actual_top_level != expected_top_level:
            errors.append(f"unexpected top-level navigation: {sorted(actual_top_level)}")
        for path, owners in assignments.items():
            if len(owners) != 1:
                errors.append(f"duplicate canonical nav destination: {path}: {owners}")
                continue
            expected_owner = path_to_owner.get(path)
            if expected_owner and owners[0] != expected_owner:
                errors.append(f"nav owner mismatch for {path}: contract={expected_owner} nav={owners[0]}")

    payloads = [stable(contract), stable(cross_contract), stable(search_contract), *outputs.values()]
    for index, text in enumerate(payloads):
        if PRIVATE.search(text) or ABSOLUTE_MACHINE_PATH.search(text):
            errors.append(f"unsafe private machine path in IA output #{index}")
        if SECRET.search(text):
            errors.append(f"secret-like value in IA output #{index}")
        if LOCALHOST_LEAK.search(text):
            errors.append(f"localhost-only implementation leak in IA output #{index}")
        if REMOTE_ASSET.search(text):
            errors.append(f"remote documentation asset dependency in IA output #{index}")

    if contract.get("pages") != sorted(contract.get("pages", []), key=lambda x: str(x.get("path"))):
        errors.append("page inventory ordering is not deterministic")
    if cross_contract.get("relations") != sorted(cross_contract.get("relations", []), key=lambda x: str(x.get("id"))):
        errors.append("cross-link ordering is not deterministic")
    return sorted(set(errors))


def write(outputs: dict[Path, str]) -> int:
    changed = 0
    for path, text in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists() or path.read_text(encoding="utf-8") != text:
            path.write_text(text, encoding="utf-8")
            changed += 1
    return changed


def check(outputs: dict[Path, str]) -> list[str]:
    errors = []
    for path, text in outputs.items():
        if not path.exists():
            errors.append(f"missing generated output: {rel(path)}")
        elif path.read_text(encoding="utf-8") != text:
            errors.append(f"generated drift: {rel(path)}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["generate", "check"])
    args = parser.parse_args()
    try:
        outputs, contract, cross, search = build(ROOT)
    except ValueError as exc:
        print(f"FAIL documentation IA validation\n{exc}")
        return 1
    if args.mode == "generate":
        changed = write(outputs)
        print(f"PASS documentation IA generated: {len(outputs)} artifacts ({changed} changed), {len(contract['pages'])} pages, {len(cross['relations'])} relations")
        return 0
    errors = check(outputs)
    if errors:
        print("FAIL documentation IA check")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"PASS documentation IA check: {len(outputs)} deterministic artifacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
