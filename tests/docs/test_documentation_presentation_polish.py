from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_module(name: str, rel: str):
    path = ROOT / rel
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_dependency_health_uses_safe_html_image_instead_of_leaking_markdown_attribute():
    intelligence = load_module(
        "presentation_intelligence",
        "scripts/docs/intelligence/generate_documentation_intelligence.py",
    )
    experience = {
        "visual_status": {
            "healthy": {"symbol": "●", "label": "Healthy"},
            "verified": {"symbol": "●", "label": "Verified"},
            "unvalidated": {"symbol": "○", "label": "Unvalidated"},
        }
    }
    page = intelligence.render_dependency_page(
        [
            {
                "label": "Apps",
                "operational_health": "healthy",
                "semantic_parity": "verified",
                "evidence_status": "release-promoted",
                "freshness": "fresh",
                "reason": None,
                "dependencies": [
                    {
                        "name": "PhotoPrism runtime",
                        "state": "healthy",
                        "evidence_status": "release-promoted",
                        "note": "promoted evidence",
                    }
                ],
            }
        ],
        experience,
        "development",
    )
    assert '<img src="../../../assets/enterprise/dependency-health-development.svg"' in page
    assert 'loading="lazy"' in page
    assert "{ loading=lazy }" not in page
    assert "/home/" not in page
    assert "/data/data/com.termux" not in page


def test_technical_delta_and_provenance_use_structured_progressive_disclosure():
    source = (ROOT / "scripts/docs/intelligence/generate_documentation_intelligence.py").read_text(encoding="utf-8")
    assert 'pl-technical-panel' in source
    assert 'pl-technical-grid' in source
    assert 'pl-provenance-grid' in source
    assert 'Exact machine-oriented change sets' in source
    assert 'Release-bound evidence lineage' in source


def test_enterprise_reference_pages_use_scan_first_cards_and_contained_diagrams():
    completion = load_module(
        "presentation_completion",
        "scripts/docs/enterprise/enterprise_completion.py",
    )
    troubleshooting = completion.render_production_troubleshooting(
        [
            {
                "title": "Device appears offline",
                "symptom": "The device is not reporting a fresh heartbeat.",
                "impact": "Commands may be undeliverable.",
                "interpretation": "Check network and agent evidence before repair.",
                "safe_checks": [{"command": "pm2 status"}],
                "expected_result": "Agent and supervisor are online.",
                "next_diagnostic_step": "Open the device runbook.",
                "when_not_to_act": ["healthy online device"],
                "related_runbook": "runbooks/device-offline.md",
            }
        ]
    )
    assert "pl-troubleshooting-card" in troubleshooting
    assert "Diagnose first. Repair second." in troubleshooting
    assert "pl-command-stack" in troubleshooting

    adr = completion.render_adr_intelligence_page(
        {
            "entities": [
                {
                    "name": "Backend-owned execution",
                    "status": "accepted",
                    "context": "The browser must not execute shell commands.",
                    "selected_approach": "FastAPI and agents own execution.",
                    "reason": "Preserve control boundaries.",
                    "alternatives": ["browser execution"],
                    "consequences": ["auditable commands"],
                    "trade_offs": ["more backend plumbing"],
                    "security_implications": ["no browser-held shell authority"],
                    "runtime_implications": ["agents execute commands"],
                    "source_refs": ["architecture/metadata/pocket-lab-architecture.json"],
                }
            ]
        }
    )
    assert "pl-adr-card" in adr
    assert '<img src="../../../assets/enterprise/adr-relationships.svg"' in adr
    assert "{ loading=lazy }" not in adr

    trace = completion.render_api_ui_trace_page(
        [
            {
                "action": "Restart Agent",
                "api": [{"method": "POST", "path": "/api/lite/devices/restart"}],
                "ui_component": ["Devices"],
                "fastapi_handler": ["restart_agent"],
                "nats_or_event": ["lite.commands.agent.restart"],
                "worker_agent_supervisor": "node agent / supervisor",
                "frontend_projection": "command progress",
                "error_reason_codes": ["agent_offline"],
                "tests": ["tests/backend/test_lite_api.py"],
                "source_files": ["src/lite/Devices.tsx"],
            }
        ]
    )
    assert "pl-trace-card" in trace
    assert "pl-trace-flow" in trace
    assert "Restart Agent" in trace


def test_events_aliases_page_types_and_repository_pages_have_purpose_built_presentations():
    enterprise_source = (ROOT / "scripts/docs/enterprise/generate_enterprise_documentation.py").read_text(encoding="utf-8")
    completion_source = (ROOT / "scripts/docs/enterprise/enterprise_completion.py").read_text(encoding="utf-8")
    knowledge_source = (ROOT / "scripts/docs/knowledge/generate_knowledge.py").read_text(encoding="utf-8")

    assert "pl-event-card" in completion_source
    assert "## Event flow model" in completion_source
    assert "pl-alias-grid" in enterprise_source
    assert "pl-page-type-grid" in enterprise_source
    assert "pl-anatomy-flow" in enterprise_source
    assert "pl-journey-grid" in knowledge_source
    assert "pl-journey-flow" in knowledge_source
    assert "pl-repo-summary" in knowledge_source
    assert "pl-repository-grid" in knowledge_source


def test_enterprise_dependency_health_renderer_does_not_emit_markdown_attribute_literal():
    source = (ROOT / "scripts/docs/enterprise/generate_enterprise_documentation.py").read_text(encoding="utf-8")
    block = source.split('outputs[DOC/"reference/dependency-health.md"]=', 1)[0].rsplit("dep_summary =", 1)[-1]
    assert '<img src="../../../assets/enterprise/dependency-health-development.svg"' in block
    assert 'loading="lazy"' in block
    assert "{ loading=lazy }" not in block


def test_enterprise_polish_css_is_responsive_and_reduced_motion_safe():
    css = (ROOT / "docs/stylesheets/intelligence.css").read_text(encoding="utf-8")
    for selector in (
        ".pl-page-lede",
        ".pl-troubleshooting-grid",
        ".pl-trace-grid",
        ".pl-event-grid",
        ".pl-adr-grid",
        ".pl-page-type-grid",
        ".pl-alias-grid",
        ".pl-journey-grid",
        ".pl-repository-grid",
        ".pl-technical-panel",
        ".pl-provenance-grid",
    ):
        assert selector in css
    assert "@media screen and (max-width: 44.9844em)" in css
    assert "@media print" in css
