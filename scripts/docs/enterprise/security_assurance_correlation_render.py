"""Static Markdown rendering for Security Assurance correlation data."""
from __future__ import annotations
import html, json, re
from collections import defaultdict
from typing import Any, Iterable, Mapping
from security_assurance_correlation_data import SUITE_ORDER, WALKTHROUGHS

def stable(v:Any):return json.dumps(v,ensure_ascii=False,sort_keys=True,indent=2,separators=(',',': '))+'\n'
def anchor(v:str):return re.sub(r'[^a-z0-9-]+','-',v.lower()).strip('-')
def cell(v:Any):
    if v is None or v=='':return '—'
    if isinstance(v,bool):return 'yes' if v else 'no'
    if isinstance(v,(list,tuple,set)):v=', '.join(map(str,v)) if v else '—'
    return str(v).replace('\n',' ').replace('|','\\|')
def table(headers:list[str],rows:Iterable[Iterable[Any]]):
    out=['| '+' | '.join(headers)+' |','| '+' | '.join('---' for _ in headers)+' |']
    out += ['| '+' | '.join(cell(x) for x in row)+' |' for row in rows]
    return '\n'.join(out)
def fm(title,description,page_type='reference'):
    return f'---\ntitle: "{title}"\ndescription: "{description}"\ngenerated: true\naudience: development\npage_type: {page_type}\nconfidence: generated\n---\n\n'
def latest_rows(m):
    rows=[]
    for suite in SUITE_ORDER:
        x=(m.get('latest_by_suite') or {}).get(suite)
        rows.append((suite.title(),x.get('status'),str(x.get('runtime_sha') or '')[:10],x.get('qualification_id'),x.get('completed_at'),'current registries' if x.get('current_registry_match') else 'historical registry')) if x else rows.append((suite.title(),'No published evidence','—','—','—','—'))
    return rows

def hub(m):
    latest=m.get('latest_by_suite') or {}; count=int(m.get('published_report_count') or 0); hist=max(count-len([x for x in latest.values() if x]),0)
    compat='The latest suite set uses one runtime SHA.' if m.get('latest_suite_set_same_runtime_sha') else 'Latest suite evidence spans different runtime SHAs; do not collapse it into one qualification verdict.'
    cards=[('Security Assurance Reports','security-assurance/reports/index.md','Per-qualification sanitized reports with exact runtime SHA and bounded verdicts.'),('How the Security Model and Assurance Evidence Fit Together','security-assurance/model-and-evidence.md','Threat model, assurance definition, and exact qualification evidence.'),('Scenario Walkthroughs','security-assurance/scenario-walkthroughs.md','Trace AP-01, AP-02, AP-06, and AP-11 from model to evidence.'),('STRIDE: Model vs Qualification Evidence','security-assurance/stride-evidence.md','STRIDE categories beside executed evidence; no security score.'),('OWASP: Model vs Qualification Evidence','security-assurance/owasp-evidence.md','Secondary OWASP lens with explicit uncertainty.'),('Model ↔ Assurance Evidence','security-assurance/model-assurance-evidence.md','AP, control, scenario, suite, finding, SHA, and human-review joins.'),('Scenario → Model','security-assurance/scenario-model.md','Registered scenarios and exact model relationships.'),('How to Read Security Documentation','security-assurance/how-to-read.md','Question-to-destination guide and truth-boundary vocabulary.'),('Threat Model','../threat-model/index.md','Canonical threats, paths, controls, assets, and boundaries.'),('Security Atlas','../threat-model/catalog.md','Static model catalog; modeled, not live traffic.'),('Trust Boundaries','../../production/architecture/network-boundaries.md','Architecture-owned trust boundaries.'),('Security Controls','../reference/security-controls.md','Canonical control posture and implementation references.'),('Assets & Guardrails','../threat-model/assets-guardrails.md','Protected assets and model guardrails.'),('Evidence & Provenance','../threat-model/evidence.md','Evidence provenance and residual uncertainty.'),('Supply Chain','../reference/supply-chain.md','Normalized supply-chain evidence.'),('Human Review','../threat-model/evidence.md','Residual risk and human-governed assurance decisions.')]
    body=['# Security & Assurance','', '<div class="pl-page-lede"><strong>Model what could go wrong. Define how to test it safely. Preserve what actually happened.</strong><p>This hub correlates existing canonical security sources and sanitized qualification evidence. It does not create a second threat model or a live monitoring surface.</p></div>','', '## Latest Security Assurance','',f'Published qualification artifacts: **{count}**. Historical artifacts outside the latest-per-suite set: **{hist}**.','',compat,'',table(['Suite','Result','Runtime SHA','Qualification','Completed UTC','Registry relationship'],latest_rows(m)),'','> **Truth boundary:** PASS means the registered invariant held for that exact qualification evidence. It is not a universal security guarantee. PARTIAL means valid evidence exists but coverage or the resulting condition is incomplete.','','## Navigate by question','','<div class="pl-card-grid">']
    for title,path,desc in cards:body.append(f'<article class="pl-card"><span class="pl-card-kicker">{html.escape(title)}</span><p>{html.escape(desc)}</p><a class="pl-intent-link" href="{html.escape(path)}">Open {html.escape(title)}</a></article>')
    body+=['</div>','','## Authority','','Canonical threat, scenario, suite, tool, architecture, and per-qualification report sources retain authority. This hub is a deterministic correlation/navigation projection.']
    return fm('Security & Assurance','Threat model, assurance definition, exact qualification evidence, and uncertainty in one correlated static view.','overview')+'\n'.join(body)+'\n'

def model_and_evidence(m):
    t=table(['Suite','Result','Runtime SHA','Qualification','Completed UTC','Registry relationship'],latest_rows(m)); compat='one runtime SHA' if m.get('latest_suite_set_same_runtime_sha') else 'multiple runtime SHAs; keep suite qualifications separate'
    return fm('How the Security Model and Assurance Evidence Fit Together','Three security truth layers and how they correlate.')+f'''# How the Security Model and Assurance Evidence Fit Together

<div class="pl-page-lede"><strong>One security story, three different authorities.</strong><p>The Threat Model says what could go wrong. Assurance definitions say how Pocket Lab can test an assumption safely. Qualification evidence records what actually happened for one exact SHA.</p></div>

## Layer 1 — Threat Model / Security Atlas
Authority: `security/threat-model-scenarios.json` plus canonical architecture. It defines AP-* paths, boundaries, consequences, and CTRL-* controls. It is a saved model, not live monitoring.

## Layer 2 — Assurance Definition
Authority: `security/assurance/scenarios.yaml`, `suites.yaml`, and `tools.yaml`. Scenarios such as `harness-auth-boundary`, `caddy-proof-strip`, `source-boundaries`, and `security-projection` define safe registered invariants; they are not scanner products.

## Layer 3 — Qualification Evidence
Authority: sanitized per-qualification reports under `generated/enterprise/hubs/security-assurance/reports/`. Each preserves qualification ID, suite, runtime SHA, findings, result, and uncertainty.

## Conceptual join key
`AP-*` joins model → scenarios → exact qualification evidence without creating another registry.

## Human review is a different axis
Threat-model `human-review-required` is a human security-model/residual-risk decision. Qualification execution classification (`EXECUTABLE_NOW`, `PARTIALLY_EXECUTABLE`, `STATIC_EVIDENCE_ONLY`, `HUMAN_REVIEW_REQUIRED`) describes automation reach. Automated PASS never upgrades the human decision to PASS.

## Latest-suite compatibility
{t}

Latest suite evidence currently spans **{compat}**.
'''

def walkthroughs(m):
    idx={x['id']:x for x in m.get('attack_paths') or []}; out=['# Scenario Walkthroughs','','These use existing canonical IDs and latest published evidence. PASS is bounded to the exact qualification; it is not permanent proof.','']
    for apid in WALKTHROUGHS:
        a=idx.get(apid)
        if not a:continue
        out += [f'<a id="{anchor(apid)}"></a>',f'## {apid} — {a.get("name")}','',f'**Model path:** {" → ".join(a.get("path_nodes") or [])}','',f'**Boundaries:** {", ".join(a.get("boundaries") or []) or "—"}','',f'**Controls:** {", ".join(a.get("controls") or []) or "—"}','',f'**Assurance scenarios:** {", ".join(a.get("scenarios") or []) or "—"}','']
        ev=a.get('latest_evidence') or []
        out += [table(['Suite','Automation classification','Automated result','Qualification result','Runtime SHA','Human assurance decision','Findings'],[(e.get('suite'),e.get('automation_classification'),e.get('automated_result'),e.get('qualification_status'),str(e.get('runtime_sha') or '')[:10],e.get('human_assurance_decision'),', '.join(e.get('findings') or []) or 'none') for e in ev]) if ev else 'No published qualification evidence currently correlates to this path.','',f'[Open {apid} in the Security Atlas](../../threat-model/catalog.md?atlas-attack-path={apid}#security-atlas) · [Open full correlation](model-assurance-evidence.md#{anchor(apid)})','']
    return fm('Scenario Walkthroughs','Model-to-assurance walkthroughs for representative attack paths.')+'\n'.join(out)+'\n'

def stride(m):
    cats=defaultdict(list)
    for a in m.get('attack_paths') or []:
        for c in a.get('stride') or []:cats[str(c)].append(a)
    rows=[]
    for c,aps in sorted(cats.items()):
        ev=[e for a in aps for e in a.get('latest_evidence') or []]; rows.append((c,', '.join(a['id'] for a in aps),', '.join(sorted({s for a in aps for s in a.get('scenarios') or []})) or '—',', '.join(sorted({str(e.get('suite'))+':'+str(e.get('automated_result')) for e in ev})) or 'NOT_ASSESSED','Human review remains separate where required.'))
    return fm('STRIDE: Model vs Qualification Evidence','STRIDE threats beside bounded qualification evidence without a security score.')+'# STRIDE: Model vs Qualification Evidence\n\nSTRIDE is a modeling lens. Qualification status is evidence for registered invariants. This page intentionally does not compute a security score.\n\n'+table(['STRIDE category','Modeled APs','Registered scenarios','Latest automated evidence','Interpretation'],rows)+'\n'

def owasp(m):
    cats=defaultdict(lambda:{'aps':set(),'s':set(),'e':set()})
    for s in m.get('scenarios') or []:
        for c in s.get('owasp') or []:
            cats[str(c)]['s'].add(s['id']); cats[str(c)]['aps'].update(map(str,s.get('attack_paths') or [])); cats[str(c)]['e'].update(str(r.get('suite'))+':'+str(r.get('status')) for r in s.get('latest_results') or [])
    rows=[(c,'TESTED' if x['e'] else 'NOT_ASSESSED',', '.join(sorted(x['aps'])) or '—',', '.join(sorted(x['s'])) or '—',', '.join(sorted(x['e'])) or 'No published applicable evidence','EVIDENCE_PRESENT does not mean every possible weakness was tested.') for c,x in sorted(cats.items())]
    return fm('OWASP: Model vs Qualification Evidence','Secondary OWASP mapping with explicit evidence and uncertainty.')+'# OWASP: Model vs Qualification Evidence\n\nOWASP Top 10 is a secondary classification lens. TESTED appears only with applicable registered scenario evidence. NOT_ASSESSED and human-review-only gaps are never promoted to PASS.\n\n'+table(['OWASP','Evidence state','APs','Scenarios','Latest evidence','Truth boundary'],rows)+'\n'

def correlation_page(m):
    out=['# Model ↔ Assurance Evidence','','Generated join view over canonical IDs and sanitized report JSON. It is not a second threat, scenario, control, or risk database.','']
    for a in m.get('attack_paths') or []:
        out += [f'<a id="{anchor(a["id"])}"></a>',f'### {a["id"]} — {a.get("name")}','',f'**Trust boundaries:** {", ".join(a.get("boundaries") or []) or "—"}  ',f'**Controls:** {", ".join(a.get("controls") or []) or "—"}  ',f'**Scenarios:** {", ".join(a.get("scenarios") or []) or "—"}  ',f'**STRIDE:** {", ".join(a.get("stride") or []) or "—"}','']
        ev=a.get('latest_evidence') or []; out += [table(['Suite','Runtime SHA','Automation class','Automated result','Qualification','Human decision','Findings','Report'],[(e.get('suite'),str(e.get('runtime_sha') or '')[:10],e.get('automation_classification'),e.get('automated_result'),e.get('qualification_status'),e.get('human_assurance_decision'),', '.join(e.get('findings') or []) or 'none',f'[open](reports/{e.get("report_id")}.md)') for e in ev]) if ev else 'No published assurance evidence currently correlates to this path.','',f'[Open {a["id"]} in Security Atlas](../../threat-model/catalog.md?atlas-attack-path={a["id"]}#security-atlas)','']
    out += ['## Controls','',table(['Control','Boundaries','APs','Scenarios','Model posture'],[(c.get('id'),c.get('boundaries'),c.get('attack_paths'),c.get('scenarios'),c.get('model_status')) for c in m.get('controls') or []])]
    return fm('Model ↔ Assurance Evidence','AP, control, scenario, qualification, SHA, finding, and human-review correlation.')+'\n'.join(out)+'\n'

def scenario_model(m):
    out=['# Scenario → Model','','Registered scenarios are safe invariant definitions. This catalog shows their canonical model relationships and latest bounded results.','']
    for s in m.get('scenarios') or []:
        out += [f'<a id="{anchor(s["id"])}"></a>',f'## `{s["id"]}` — {s.get("title")}','',f'**Purpose / invariant:** {s.get("purpose") or "—"}','',table(['Field','Value'],[('Suites',s.get('suites')),('Safety class',s.get('safety_class')),('Execution',s.get('execution')),('STRIDE',s.get('stride')),('OWASP',s.get('owasp')),('Attack paths',s.get('attack_paths')),('Controls',s.get('controls')),('Tools/evidence sources',s.get('tools')),('Normalized evidence',s.get('normalized_evidence'))]),'']
        rs=s.get('latest_results') or []; out += [table(['Suite','Result','Runtime SHA','Qualification','Evidence refs','Report'],[(r.get('suite'),r.get('status'),str(r.get('runtime_sha') or '')[:10],r.get('qualification_id'),r.get('evidence_refs') or 'sanitized evidence',f'[open](reports/{r.get("report_id")}.md)') for r in rs]) if rs else 'No published latest-suite result currently contains this scenario.','']
    return fm('Scenario → Model','Registered scenarios joined to model IDs and latest exact-SHA evidence.')+'\n'.join(out)+'\n'

def how_to_read(m):
    rows=[('What asset are we protecting?','Threat Model → Assets & Guardrails','../../threat-model/assets-guardrails.md'),('Which trust boundary is crossed?','Architecture → Trust Boundaries','../../../production/architecture/network-boundaries.md'),('What can go wrong?','Threat Model / Security Atlas','../../threat-model/index.md'),('Which control should mitigate it?','Security Controls','../../reference/security-controls.md'),('How do we test that assumption?','Scenario → Model','scenario-model.md'),('What happened in the latest qualification?','Security Assurance Reports','reports/index.md'),('Where do model and evidence meet?','Model ↔ Assurance Evidence','model-assurance-evidence.md'),('What remains uncertain or human-owned?','Evidence & Provenance / Human Review','../../threat-model/evidence.md')]
    return fm('How to Read Security Documentation','Question-to-destination navigation and security truth-boundary vocabulary.')+'# How to Read Security Documentation\n\nUse the question you are trying to answer; no page is a universal security verdict.\n\n'+table(['Question','Go here','Path'],rows)+'\n\n## Vocabulary\n\n'+table(['Term','Meaning'],[(k.replace('_',' ').title(),v) for k,v in (m.get('truth_boundaries') or {}).items()])+'\n'

def threat_assurance(m):
    rows=[]
    for a in m.get('attack_paths') or []:
        ev=a.get('latest_evidence') or []; latest=', '.join(f"{e.get('suite')}:{e.get('automated_result')}@{str(e.get('runtime_sha') or '')[:10]}" for e in ev) or 'No published evidence'
        rows.append((f'[{a["id"]}](catalog.md?atlas-attack-path={a["id"]}#security-atlas)',a.get('name'),a.get('scenarios'),latest,'HUMAN_REVIEW_REQUIRED' if a.get('model_review_status')=='human-review-required' else '—',f'[correlation](../hubs/security-assurance/model-assurance-evidence.md#{anchor(a["id"])})'))
    return fm('Threat Model → Assurance Evidence','Attack-path links into latest sanitized qualification evidence.')+'# Threat Model → Assurance Evidence\n\nAttack paths remain canonical model objects. Evidence is a bounded latest-per-suite projection, not live monitoring and not a replacement for human review.\n\n'+table(['AP','Threat','Scenarios','Latest automated evidence','Model review','Evidence'],rows)+'\n'
def migration():return '# Security Assurance Reports — moved\n\nThe canonical generated report location moved to the Security & Assurance hub. No report content is duplicated at this legacy route.\n\n[Open Security Assurance Reports](../../enterprise/hubs/security-assurance/reports/index.md)\n'
