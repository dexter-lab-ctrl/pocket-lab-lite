from __future__ import annotations
import hashlib, importlib.util, json, sys
from pathlib import Path
import pytest, yaml

ROOT=Path(__file__).resolve().parents[2]; MOD=ROOT/'scripts/docs/enterprise/security_assurance_correlation.py'
sys.path.insert(0,str(MOD.parent)); spec=importlib.util.spec_from_file_location('security_assurance_correlation',MOD); c=importlib.util.module_from_spec(spec); assert spec.loader; spec.loader.exec_module(c)

def write(p,v):
    p.parent.mkdir(parents=True,exist_ok=True)
    if p.suffix in {'.yaml','.yml'}:p.write_text(yaml.safe_dump(v,sort_keys=False),encoding='utf-8')
    else:p.write_text(json.dumps(v,sort_keys=True,indent=2)+'\n',encoding='utf-8')

def fixture(tmp):
    sc=[
      {'id':'harness-auth-boundary','title':'Harness boundary','execution':'probe','safety_class':'SAFE_ACTIVE','suites':['smoke'],'stride':['Spoofing'],'owasp':['A01'],'controls':['CTRL-API-CONTROL'],'attack_paths':['AP-01'],'expected_invariant':'bounded'},
      {'id':'source-boundaries','title':'Source boundary','execution':'static','safety_class':'PASSIVE','suites':['standard'],'stride':['Tampering'],'owasp':['A08'],'controls':['CTRL-BROWSER-SHELL'],'attack_paths':['AP-02'],'expected_invariant':'no shell'},
      {'id':'evidence-redaction','title':'Evidence','execution':'redaction','safety_class':'PASSIVE','suites':['adversarial'],'stride':['Repudiation'],'owasp':['A09'],'controls':['CTRL-EVIDENCE-SANITIZE'],'attack_paths':['AP-06'],'expected_invariant':'sanitized'},
      {'id':'policy-readiness','title':'OPA','execution':'status','safety_class':'PASSIVE','suites':['deep'],'stride':['Elevation of Privilege'],'owasp':['A01'],'controls':['CTRL-OPA-FAIL-CLOSED'],'attack_paths':['AP-11'],'expected_invariant':'fail closed'}]
    paths=[]
    for ap,name,ctrl,stride in [('AP-01','Browser control-plane bypass','CTRL-API-CONTROL','Spoofing'),('AP-02','Browser shell execution','CTRL-BROWSER-SHELL','Tampering'),('AP-06','Evidence poisoning','CTRL-EVIDENCE-SANITIZE','Repudiation'),('AP-11','OPA authorization decision integrity failure','CTRL-OPA-FAIL-CLOSED','Elevation of Privilege')]:
        paths.append({'id':ap,'name':name,'path_nodes':['browser','target'],'boundaries':['browser','control-api'],'stride':[stride],'controls':[ctrl],'status':'modeled','review_status':'human-review-required'})
    write(tmp/c.SCENARIOS,{'scenarios':sc}); write(tmp/c.SUITES,{'profiles':{s:{} for s in ('smoke','standard','adversarial','deep')}}); write(tmp/c.TOOLS,{'name':'tools','toolchain':[]}); write(tmp/c.THREAT_MODEL,{'controls':[{'id':x,'boundaries':['control-api'],'status':'mitigation-source-derived'} for x in ('CTRL-API-CONTROL','CTRL-BROWSER-SHELL','CTRL-EVIDENCE-SANITIZE','CTRL-OPA-FAIL-CLOSED')],'attack_paths':paths}); write(tmp/c.ARCHITECTURE,{'components':[]})
    hashes=c._current_hashes(tmp); sha='a'*40; mapping={'smoke':('AP-01','harness-auth-boundary'),'standard':('AP-02','source-boundaries'),'adversarial':('AP-06','evidence-redaction'),'deep':('AP-11','policy-readiness')}
    for n,suite in enumerate(mapping,1):
        ap,sid=mapping[suite]; q='assurance-'+str(n)*32; rid=f'security-assurance-20260917T12000{n}Z-{sha[:10]}-{q}'
        report={'sanitized':True,'report_id':rid,'qualification_id':q,'qualification_completed_at':f'2026-09-17T12:00:0{n}Z','runtime_sha':sha,'source_sha':sha,'suite':suite,'overall_status':'PARTIAL' if suite=='deep' else 'PASS','registry_hashes':hashes,'severity_counts':{'critical':0,'high':0,'medium':0,'low':1 if suite=='deep' else 0},'metrics':{'scenario_coverage_percent':100.0},'scenarios':[{'scenario_id':sid,'status':'PASS','evidence_refs':['normalized']}],'attack_paths':[{'attack_path_id':ap,'classification':'PARTIALLY_EXECUTABLE','status':'PASS','human_review_required':True}],'findings':[{'finding_id':'low','attack_paths':[ap]}] if suite=='deep' else []}
        write(tmp/c.REPORTS/f'{rid}.json',report)
    return tmp

def projection(tmp):return c.build_projection(fixture(tmp))

def test_new_canonical_report_tree(tmp_path):
    out,m=projection(tmp_path); assert str(c.REPORTS).startswith('docs/generated/enterprise/hubs/security-assurance/reports'); assert m['published_report_count']==4

def test_legacy_route_is_pointer_only(tmp_path):
    out,_=projection(tmp_path); text=out[tmp_path/c.OLD_REPORT_INDEX]; assert 'moved' in text.lower() and 'No report content is duplicated' in text
@pytest.mark.parametrize('label',['Security Assurance Reports','How the Security Model and Assurance Evidence Fit Together','Scenario Walkthroughs','STRIDE: Model vs Qualification Evidence','OWASP: Model vs Qualification Evidence','Model ↔ Assurance Evidence','How to Read Security Documentation'])
def test_required_hub_cards(tmp_path,label):
    out,_=projection(tmp_path); assert label in out[tmp_path/c.HUB]
@pytest.mark.parametrize('ap',['AP-01','AP-02','AP-06','AP-11'])
def test_required_walkthroughs(tmp_path,ap):
    out,_=projection(tmp_path); assert ap in out[tmp_path/c.PAGES/'scenario-walkthroughs.md']

def test_exact_sha_per_suite_and_partial_preserved(tmp_path):
    _,m=projection(tmp_path); assert m['latest_suite_set_same_runtime_sha']; assert m['latest_by_suite']['deep']['status']=='PARTIAL'

def test_human_review_never_promoted_by_automation(tmp_path):
    _,m=projection(tmp_path); e=m['attack_paths'][0]['latest_evidence'][0]; assert e['automated_result']=='PASS' and e['human_assurance_decision']=='HUMAN_REVIEW_REQUIRED'

def test_stride_has_no_security_score(tmp_path):
    out,_=projection(tmp_path); text=out[tmp_path/c.PAGES/'stride-evidence.md'].lower(); assert 'does not compute a security score' in text

def test_owasp_tested_requires_evidence(tmp_path):
    out,_=projection(tmp_path); assert 'TESTED' in out[tmp_path/c.PAGES/'owasp-evidence.md']

def test_model_and_report_links_are_bidirectional(tmp_path):
    out,_=projection(tmp_path); assert 'Security Atlas' in out[tmp_path/c.PAGES/'model-assurance-evidence.md']; assert 'correlation' in out[tmp_path/c.THREAT_ASSURANCE]

def test_registry_hash_mismatch_is_explicit(tmp_path):
    root=fixture(tmp_path); first=next((root/c.REPORTS).glob('*.json')); v=json.loads(first.read_text()); v['registry_hashes']['scenarios']='sha256:bad'; write(first,v); _,m=c.build_projection(root); assert any(x and not x['current_registry_match'] for x in m['latest_by_suite'].values())

def test_unsanitized_report_fails_closed(tmp_path):
    root=fixture(tmp_path); first=next((root/c.REPORTS).glob('*.json')); v=json.loads(first.read_text()); v['sanitized']=False; write(first,v); _,m=c.build_projection(root); assert m['published_report_count']==3

def test_deterministic_projection(tmp_path):
    root=fixture(tmp_path); a=c.build_projection(root)[0]; b=c.build_projection(root)[0]; assert {p.relative_to(root):t for p,t in a.items()}=={p.relative_to(root):t for p,t in b.items()}

def test_truth_boundaries_are_machine_readable(tmp_path):
    _,m=projection(tmp_path); assert 'human_review' in m['truth_boundaries'] and m['sanitized'] is True
