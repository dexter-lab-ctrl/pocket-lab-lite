---
title: "Documentation experience"
description: "The MkDocs Material portal is a tested product surface with separate Development and Production navigation, responsive behavior, accessible status semantics, and strict generated-content ownership."
status: verified
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 6a7576a6242d285a8943d05aeb402cd27f1ee0cd4264c592d29b8dfebad04409
schema_revision: 1
validation_status: generated
---

# Documentation experience

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Development guidance</span>
</div>

The MkDocs Material portal is a tested product surface with separate Development and Production navigation, responsive behavior, accessible status semantics, and strict generated-content ownership.

## Design system

- Brand, component, and print styles live outside generated directories.
- System fonts avoid external font requests.
- Verified, inferred, patch-provided, missing, planned, and unvalidated states use text plus color.
- Cards, tables, code, admonitions, tabs, and Mermaid diagrams use shared tokens.

## Authoring conventions

!!! info "Context"
    Use informational notes for verified background.

!!! warning "Action required"
    Use warnings for service interruption, validation gaps, or state that needs user review.

```bash title="Documentation validation"
task lite:docs:generate
task lite:docs:check
task lite:test:docs
```

## Browser acceptance

The dedicated Playwright documentation suite checks Development and Production navigation, search, theme switching, mobile navigation, code-copy controls, console health, horizontal overflow, and serious/critical Axe findings.
