from __future__ import annotations
import json
import subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
GEN=ROOT/'scripts/docs/enterprise/generate_enterprise_documentation.py'

def test_enterprise_generator_check_is_green():
    result=subprocess.run(['python3',str(GEN),'check'],cwd=ROOT,text=True,capture_output=True)
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
    assert delta['status'] in {'no-comparable-verified-prior-release','comparable'}
    if delta['status'] != 'comparable':
        assert all(x['status'] == 'not-comparable' for x in delta['dimensions'])

def test_dependency_health_has_development_and_production_svg():
    for name in ['dependency-health-development.svg','dependency-health-production.svg']:
        text=(ROOT/'docs/generated/assets/enterprise'/name).read_text(encoding='utf-8')
        assert '<svg' in text
        assert 'Pocket Lab Lite dependency health' in text

def test_tool_metadata_keeps_heavy_work_off_termux():
    meta=json.loads((ROOT/'contracts/metadata/documentation-security-tools.json').read_text())
    assert meta['execution_policy']['heavy_default_surface'] == 'WSL2/CI'
    assert meta['execution_policy']['docs_check_runs_heavy_tools'] is False
