---
title: "Documentation experience"
description: "The MkDocs Material portal is a tested knowledge product with question-oriented navigation, a canonical UX contract, responsive intelligence views, accessible status semantics, and strict generated-content ownership."
status: verified
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 3bd1846004fa5a873680d41dd98c02813d700c3d91507c781e5de3b5baa151ca
schema_revision: 1
validation_status: generated
---

# Documentation experience

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Development guidance</span>
</div>

The MkDocs Material portal is a tested knowledge product with question-oriented navigation, a canonical UX contract, responsive intelligence views, accessible status semantics, and strict generated-content ownership.

## Design system

- `contracts/metadata/documentation-experience.json` is the canonical Documentation UX contract.
- Brand, component, intelligence, and print styles live outside generated directories.
- System fonts avoid external font requests.
- Status always uses text plus shape/symbol and color; color is never the only signal.
- Evidence-heavy pages use a consistent status hierarchy: health first, then implementation/runtime/parity, then freshness and evidence confidence.
- Summary → explanation → technical evidence is the default progressive-disclosure sequence.
- The home dashboard, role shortcuts, task-oriented entry points, evidence lineage, scorecards, and matrix views are generated from canonical source and promoted evidence.
- Motion is bounded and respects `prefers-reduced-motion`; continuous decorative animation is prohibited.

## Authoring conventions

!!! info "Context"
    Use informational notes for verified background.

!!! warning "Action required"
    Use warnings for service interruption, validation gaps, or state that needs user review.

```bash title="Documentation validation"
task lite:docs:generate
task lite:docs:check
task lite:docs:intelligence:check
task lite:test:docs
```

## Browser acceptance

The dedicated Playwright documentation suite checks the dashboard, question-oriented navigation, search, theme switching, mobile layouts, progressive disclosure, evidence lineage, matrix overflow, code-copy controls, console health, and serious/critical Axe findings.
