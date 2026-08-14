from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
GEN=ROOT/'scripts/docs/enterprise/generate_enterprise_documentation.py'

def test_enterprise_generator_check_is_green():
    result=subprocess.run([sys.executable,str(GEN),'check'],cwd=ROOT,text=True,capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr

def test_enterprise_generator_has_no_live_runtime_capture_or_promotion():
    text=GEN.read_text(encoding='utf-8')
    forbidden=['requests.get(', 'requests.post(', 'httpx.get(', 'httpx.post(', 'capture_termux_runtime', 'promote_termux_runtime.py", "promote']
    assert not any(token in text for token in forbidden)

def test_threat_model_is_canonical_and_requires_human_review():
    model=json.loads((ROOT/'contracts/security/threat-model.json').read_text())
    assert len(model['boundaries']) == 9
    assert {x['stride'] for x in model['threats']} == {'Spoofing','Tampering','Repudiation','Information Disclosure','Denial of Service','Elevation of Privilege'}
    assert 'risk acceptance' in model['human_review_required']
    assert model['posture'] == 'current-promoted-threat-posture'

def test_release_delta_fails_closed_without_two_verified_manifests():
    delta=json.loads((ROOT/'contracts/generated/documentation-enterprise/release-delta.json').read_text())
    assert delta['status'] in {'no-comparable-verified-prior-release','initial-canonical-comparison-baseline','comparison-evidence-unavailable','comparable'}
    if delta['status'] != 'comparable':
        assert all(x['status'] == 'not-comparable' for x in delta['dimensions'])
        assert all(x['classification'] == 'not-comparable' for x in delta['dimensions'])

def test_dependency_health_has_development_and_production_svg():
    for name in ['dependency-health-development.svg','dependency-health-production.svg']:
        text=(ROOT/'docs/generated/assets/enterprise'/name).read_text(encoding='utf-8')
        assert '<svg' in text
        assert 'Pocket Lab Lite dependency health' in text

def test_tool_metadata_keeps_heavy_work_off_termux():
    meta=json.loads((ROOT/'contracts/metadata/documentation-security-tools.json').read_text())
    assert meta['execution_policy']['heavy_default_surface'] == 'WSL2/CI'
    assert meta['execution_policy']['docs_check_runs_heavy_tools'] is False


def test_threat_model_experience_preserves_reference_content_across_split_pages():
    base = ROOT / "docs/generated/enterprise/threat-model"

    overview = (base / "index.md").read_text(encoding="utf-8")
    architecture = (base / "architecture.md").read_text(encoding="utf-8")
    stride = (base / "stride.md").read_text(encoding="utf-8")
    controls = (base / "controls.md").read_text(encoding="utf-8")
    attack_paths = (base / "attack-paths.md").read_text(encoding="utf-8")
    evidence = (base / "evidence.md").read_text(encoding="utf-8")
    catalog = (base / "catalog.md").read_text(encoding="utf-8")

    # Landing page stays intentionally simple and poster-oriented.
    for marker in [
        "# Threat Model",
        "How Pocket Lab protects control",
        "## Explore the model",
        "## Model provenance",
        'data-threat-poster-mode="understand"',
        'data-threat-guardrails="toggle"',
    ]:
        assert marker in overview

    # Detailed reference material remains present, but is distributed to
    # purpose-built pages instead of being duplicated on the landing page.
    for heading in [
        "## Threat Model Diagram",
        "## Trust zones",
        "## Architecture ownership",
    ]:
        assert heading in architecture

    for heading in [
        "## Threat framework",
        "## STRIDE definitions",
        "## How Pocket Lab applies STRIDE",
        "## Three truth layers",
    ]:
        assert heading in stride

    for heading in [
        "# Security controls",
        "## Control evidence",
        "## Where controls are used",
    ]:
        assert heading in controls

    for heading in [
        "# Modeled attack paths",
        "## Review table",
    ]:
        assert heading in attack_paths

    for heading in [
        "## Evidence lineage",
        "## Current promoted evidence posture",
        "## Truth boundary",
        "## What this threat model does not do",
        "## Consequences of not threat modelling",
        "## Human review required",
    ]:
        assert heading in evidence

    assert "Security Atlas Catalog" in catalog
    assert "../../production/architecture/index.md" in architecture
    assert "not a live monitor" in overview.lower()


def test_release_assurance_page_separates_evidence_authorities():
    page=(ROOT/'docs/generated/enterprise/engineering/release-evidence.md').read_text(encoding='utf-8')
    for heading in ['# Release Assurance', '## Evidence authorities', '## Assurance matrix', '## Artifact evidence', '## Evidence gaps', '## Evidence lineage']:
        assert heading in page
    assert 'Local repository' in page
    assert 'Runtime' in page
    assert 'Release' in page


def test_architecture_overview_embeds_the_generated_threat_overlay():
    page=(ROOT/'docs/generated/production/architecture/index.md').read_text(encoding='utf-8')
    assert '## Security / threat-model overlay' in page
    assert '../../enterprise/threat-model/index.md' in page
    assert '../../assets/enterprise/threat-model.svg' in page


def test_docs_repository_source_is_static_and_edge_safe():
    """Repository navigation must not require runtime GitHub API access."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    mkdocs = (root / "mkdocs.yml").read_text(encoding="utf-8")
    source = (
        root / "docs/overrides/partials/source.html"
    ).read_text(encoding="utf-8")

    # Preserve source/edit integration.
    assert "repo_url:" in mkdocs
    assert "repo_name:" in mkdocs
    assert "edit_uri:" in mkdocs

    # Preserve a visible static repository link.
    assert 'href="{{ config.repo_url }}"' in source
    assert 'class="md-source"' in source
    assert "config.repo_name" in source

    # Fail closed if Material's runtime repository-facts component is restored.
    assert 'data-md-component="source"' not in source

    # The override itself must remain passive.
    forbidden_runtime_dependencies = (
        "api.github.com",
        "releases/latest",
        "fetch(",
        "XMLHttpRequest",
        "WebSocket",
        "EventSource",
    )
    for token in forbidden_runtime_dependencies:
        assert token not in source
