"""Static data model for the Security Assurance correlation projection."""
from __future__ import annotations
import hashlib, json, re
from pathlib import Path
from typing import Any, Mapping
import yaml

SCENARIOS=Path('security/assurance/scenarios.yaml'); SUITES=Path('security/assurance/suites.yaml'); TOOLS=Path('security/assurance/tools.yaml')
THREAT_MODEL=Path('security/threat-model-scenarios.json'); ARCHITECTURE=Path('architecture/metadata/pocket-lab-architecture.json')
REPORTS=Path('docs/generated/enterprise/hubs/security-assurance/reports')
SUITE_ORDER=('smoke','standard','adversarial','deep'); WALKTHROUGHS=('AP-01','AP-02','AP-06','AP-11')
REPORT_RE=re.compile(r'^security-assurance-[0-9]{8}T[0-9]{6}Z-[0-9a-f]{7,12}-assurance-[0-9a-f]{32}\.json$')

def read_json(p:Path,d:Any):
    try:return json.loads(p.read_text(encoding='utf-8'))
    except (OSError,json.JSONDecodeError):return d

def read_yaml(p:Path,d:Any):
    try:v=yaml.safe_load(p.read_text(encoding='utf-8'))
    except (OSError,yaml.YAMLError):return d
    return d if v is None else v

def file_hash(p:Path):
    try:return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
    except OSError:return None

def current_hashes(root:Path):
    return {'scenarios':file_hash(root/SCENARIOS),'suites':file_hash(root/SUITES),'tools':file_hash(root/TOOLS),'threat_model':file_hash(root/THREAT_MODEL)}

def compatible(report:Mapping[str,Any], hashes:Mapping[str,Any]):
    got=report.get('registry_hashes') if isinstance(report.get('registry_hashes'),Mapping) else {}
    match={k:bool(got.get(k) and v and got.get(k)==v) for k,v in hashes.items()}
    return {'current_registry_match':all(match.values()),'hash_matches':match}

def report_models(root:Path):
    out=[]; directory=root/REPORTS
    if not directory.is_dir():return out
    for p in sorted(directory.glob('security-assurance-*.json')):
        if not REPORT_RE.fullmatch(p.name) or p.stat().st_size>2*1024*1024:continue
        v=read_json(p,{})
        if not isinstance(v,Mapping) or v.get('sanitized') is not True or p.stem!=v.get('report_id'):continue
        if not re.fullmatch(r'assurance-[0-9a-f]{32}',str(v.get('qualification_id') or '')):continue
        if not re.fullmatch(r'[0-9a-f]{40}',str(v.get('runtime_sha') or '')):continue
        if str(v.get('suite') or '').lower() not in SUITE_ORDER:continue
        out.append(dict(v))
    return sorted(out,key=lambda r:(str(r.get('qualification_completed_at') or ''),str(r.get('report_id') or '')))

def _find(items,key,value):
    for item in items or []:
        if isinstance(item,Mapping) and str(item.get(key) or item.get('id') or '')==value:return dict(item)
    return None

def _findings(report:Mapping[str,Any],ap_id:str):
    return [dict(x) for x in report.get('findings') or [] if isinstance(x,Mapping) and ap_id in map(str,x.get('attack_paths') or [])]

def build_model(root:Path):
    scenario_doc=read_yaml(root/SCENARIOS,{}) or {}; suite_doc=read_yaml(root/SUITES,{}) or {}; tool_doc=read_yaml(root/TOOLS,{}) or {}
    threat=read_json(root/THREAT_MODEL,{}) or {}; arch=read_json(root/ARCHITECTURE,{}) or {}; reports=report_models(root); hashes=current_hashes(root)
    latest={}
    for suite in SUITE_ORDER:
        rows=[r for r in reports if str(r.get('suite') or '').lower()==suite]
        if not rows:latest[suite]=None;continue
        r=rows[-1]; sev=r.get('severity_counts') if isinstance(r.get('severity_counts'),Mapping) else {}; metrics=r.get('metrics') if isinstance(r.get('metrics'),Mapping) else {}
        latest[suite]={'qualification_id':r.get('qualification_id'),'report_id':r.get('report_id'),'completed_at':r.get('qualification_completed_at'),'runtime_sha':r.get('runtime_sha'),'status':str(r.get('overall_status') or 'UNAVAILABLE').upper(),'critical':int(sev.get('critical') or 0),'high':int(sev.get('high') or 0),'medium':int(sev.get('medium') or 0),'low':int(sev.get('low') or 0),'scenario_coverage_percent':metrics.get('scenario_coverage_percent'),**compatible(r,hashes)}
    rindex={str(r.get('report_id')):r for r in reports}
    scenarios=[]
    for item in scenario_doc.get('scenarios') or []:
        if not isinstance(item,Mapping) or not item.get('id'):continue
        sid=str(item['id']); results=[]
        for suite,li in latest.items():
            if not li:continue
            report=rindex[str(li['report_id'])]; obs=_find(report.get('scenarios'),'scenario_id',sid)
            if obs:results.append({'suite':suite,'status':str(obs.get('status') or 'NOT_ASSESSED').upper(),'qualification_id':report.get('qualification_id'),'report_id':report.get('report_id'),'runtime_sha':report.get('runtime_sha'),'completed_at':report.get('qualification_completed_at'),'evidence_refs':list(obs.get('evidence_refs') or [])})
        scenarios.append({'id':sid,'title':item.get('title'),'purpose':item.get('expected_invariant') or item.get('title'),'execution':item.get('execution'),'safety_class':item.get('safety_class'),'suites':list(item.get('suites') or []),'stride':list(item.get('stride') or []),'owasp':list(item.get('owasp') or []),'attack_paths':list(item.get('attack_paths') or []),'controls':list(item.get('controls') or []),'tools':list(item.get('evidence_tools') or []),'normalized_evidence':item.get('normalized_evidence'),'latest_results':results})
    scenario_ids={s['id'] for s in scenarios}
    attack_paths=[]
    for p in threat.get('attack_paths') or []:
        if not isinstance(p,Mapping) or not p.get('id'):continue
        ap=str(p['id']); evidence=[]
        for suite,li in latest.items():
            if not li:continue
            report=rindex[str(li['report_id'])]; obs=_find(report.get('attack_paths'),'attack_path_id',ap); fs=_findings(report,ap)
            requires=bool(str(p.get('review_status') or '')=='human-review-required' or (obs or {}).get('human_review_required'))
            evidence.append({'suite':suite,'qualification_id':report.get('qualification_id'),'report_id':report.get('report_id'),'runtime_sha':report.get('runtime_sha'),'completed_at':report.get('qualification_completed_at'),'qualification_status':str(report.get('overall_status') or 'UNAVAILABLE').upper(),'automation_classification':(obs or {}).get('classification') or 'NOT_ASSESSED','automated_result':str((obs or {}).get('status') or 'NOT_ASSESSED').upper(),'human_review_required':requires,'human_assurance_decision':'HUMAN_REVIEW_REQUIRED' if requires else 'NOT_APPLICABLE','reason':(obs or {}).get('reason'),'findings':[f.get('finding_id') for f in fs if f.get('finding_id')]})
        attack_paths.append({'id':ap,'name':p.get('name'),'entry_point':p.get('entry_point'),'target':p.get('target'),'path_nodes':list(p.get('path_nodes') or []),'boundaries':list(p.get('boundaries') or []),'stride':list(p.get('stride') or []),'controls':list(p.get('controls') or []),'consequences':list(p.get('consequences') or []),'model_status':p.get('status'),'model_review_status':p.get('review_status'),'scenarios':[s['id'] for s in scenarios if ap in s['attack_paths'] and s['id'] in scenario_ids],'latest_evidence':evidence})
    tcontrols={str(c.get('id')):dict(c) for c in threat.get('controls') or [] if isinstance(c,Mapping) and c.get('id')}; controls=[]
    for cid in sorted(set(tcontrols)|{c for ap in attack_paths for c in ap['controls']}):
        c=tcontrols.get(cid,{})
        controls.append({'id':cid,'description':c.get('description'),'boundaries':list(c.get('boundaries') or []),'model_status':c.get('status') or 'source-derived-or-referenced','attack_paths':[a['id'] for a in attack_paths if cid in a['controls']],'scenarios':[s['id'] for s in scenarios if cid in s['controls']]})
    shas=sorted({str(v['runtime_sha']) for v in latest.values() if v})
    return {'schema_version':'1.0.0','kind':'security-assurance-correlation','authority':{'model':str(THREAT_MODEL),'scenarios':str(SCENARIOS),'suites':str(SUITES),'tools':str(TOOLS),'architecture':str(ARCHITECTURE),'qualification_evidence':str(REPORTS/'*.json'),'note':'Derived join layer only; canonical model, registries, and per-qualification reports retain authority.'},'truth_boundaries':{'threat_model':'Saved modeled threats and controls; not live monitoring.','scenario':'Registered invariant and safe execution definition; not a scanner product.','qualification':'Bounded evidence for one exact qualification and runtime SHA; not a universal security claim.','pass':'The registered invariant held for the observed qualification evidence; not proof it can never fail.','partial':'Valid evidence exists but coverage or resulting condition is incomplete.','coverage':'Evidence coverage ratio; never a security score.','human_review':'Human-governed review remains separate from automated checks and cannot be auto-promoted to PASS.'},'current_registry_hashes':hashes,'latest_by_suite':latest,'latest_suite_runtime_shas':shas,'latest_suite_set_same_runtime_sha':bool(shas) and len(shas)==1,'published_report_count':len(reports),'reports':[{'report_id':r.get('report_id'),'qualification_id':r.get('qualification_id'),'suite':r.get('suite'),'status':str(r.get('overall_status') or 'UNAVAILABLE').upper(),'runtime_sha':r.get('runtime_sha'),'completed_at':r.get('qualification_completed_at'),**compatible(r,hashes)} for r in reports],'scenarios':scenarios,'attack_paths':attack_paths,'controls':controls,'suite_definitions':suite_doc.get('profiles') or {},'tool_registry_name':tool_doc.get('name'),'architecture_present':bool(arch),'sanitized':True}
