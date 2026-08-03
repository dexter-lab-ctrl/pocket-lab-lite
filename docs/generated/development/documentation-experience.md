---
title: "Documentation experience"
description: "The MkDocs Material portal is a tested product surface with separate Development and Production navigation, responsive behavior, accessible status semantics, and strict generated-content ownership."
status: verified
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 8f8afc8abd2efd3a6fa02fae02e6d916c7afea569468f48225b6a7f96ab99c4e
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
