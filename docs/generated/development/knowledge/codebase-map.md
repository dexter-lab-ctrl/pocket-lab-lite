---
title: "Codebase Map"
description: "Evidence-backed Git-tracked repository structure, ownership, relationships, symbols, and bounded impact analysis."
generated: true
audience: development
confidence: source-derived
source_commit: uncommitted
generator: scripts/docs/knowledge/generate_codebase_map.py
---

# Codebase Map

<div class="pl-page-lede"><strong>Understand what exists in Pocket Lab Lite, why it exists, and what is structurally connected to it.</strong><p>This is a static projection of Git-tracked repository structure plus deterministic source facts and existing Knowledge/Architecture contracts. It never scans the browser filesystem, probes runtime, calls GitHub, or invents missing semantics.</p></div>

<div class="pl-kpi-grid pl-codebase-kpis" role="group" aria-label="Codebase documentation health"><div class="pl-kpi"><span>Tracked files</span><strong>2519</strong><small>Git-owned inventory</small></div><div class="pl-kpi"><span>Folders</span><strong>226</strong><small>inferred from tracked paths</small></div><div class="pl-kpi"><span>Explained</span><strong>100.0%</strong><small>0 unvalidated</small></div><div class="pl-kpi"><span>Critical coverage</span><strong>100.0%</strong><small>967 critical files</small></div></div>

<section class="pl-codebase-map" data-pl-codebase-map="true" data-file-count="2519" data-node-count="2745" data-relationship-count="14356"><div class="pl-codebase-controls"><label class="pl-codebase-search">Search codebase<input type="search" data-cb-search autocomplete="off" placeholder="Path, purpose, role, symbol, task…"></label><label>Role<select data-cb-role><option value="">All roles</option></select></label><label>Language<select data-cb-language><option value="">All languages</option></select></label><label>Owner<select data-cb-owner><option value="">All owners</option></select></label><label>Confidence<select data-cb-confidence><option value="">All confidence</option></select></label><button type="button" class="md-button" data-cb-collapse>Collapse all</button></div><div class="pl-codebase-layout"><div class="pl-codebase-tree" data-cb-tree role="tree" aria-label="Repository tree"><div class="pl-empty-state"><strong>Loading repository model</strong><p>Reading one same-origin generated asset.</p></div></div><aside class="pl-codebase-inspector" data-cb-inspector aria-live="polite"><span class="pl-card-kicker">Inspector</span><strong>Select a file or folder</strong><p>Purpose, ownership, uses, used-by, tests, generated outputs, architecture, symbols, and bounded impact appear here.</p></aside></div></section>

## Documentation health

| Metric | Value |
| --- | ---: |
| Classified paths | 100.0% |
| Relationship coverage | 40.85% |
| Architecture mapping | 1.47% |
| Test mapping | 2.22% |
| Parser failures | 0 |

## Model boundaries

- **Physical structure:** `git ls-files`; untracked/local runtime material is excluded.
- **Facts:** deterministic parsers only; parser failures are explicit.
- **Explanations:** existing Knowledge/Architecture evidence first; otherwise clearly path-derived.
- **Impact:** bounded static dependency traversal; it does not claim runtime consequences.
- **SCIP:** optional and currently unavailable; the core model does not depend on it.
- **Git hotspots:** optional and currently unavailable; missing history is not treated as risk.

## Related authoritative views

- [Repository Map](repository-map.md) — reverse source→Knowledge lookup.
- [Knowledge Graph](../../enterprise/knowledgebase/knowledge-graph.md) — semantic relationships.
- [Architecture](../../production/architecture/index.md) — runtime/system operation.
- [Change Impact Advisor](../../enterprise/reference/change-advisor.md) — deterministic change consequence advisor.
