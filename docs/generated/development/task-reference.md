---
title: "Lite task reference"
description: "The root Taskfile uses included Lite task files and separates quick, full, release, UI, docs, and Windows/WSL2 workflows."
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

# Lite task reference

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Development guidance</span>
</div>

The root Taskfile uses included Lite task files and separates quick, full, release, UI, docs, and Windows/WSL2 workflows.

- `lite:allure`
- `lite:api:check`
- `lite:bootstrap:check`
- `lite:browser:detect`
- `lite:check`
- `lite:check:quick`
- `lite:check:release`
- `lite:contracts:check`
- `lite:contracts:generate`
- `lite:dev:backend`
- `lite:dev:down`
- `lite:dev:frontend`
- `lite:dev:frontend:mocked`
- `lite:dev:logs`
- `lite:dev:nats`
- `lite:dev:status`
- `lite:dev:up`
- `lite:dev:worker`
- `lite:docs:bootstrap`
- `lite:docs:capabilities`
- `lite:docs:check`
- `lite:docs:configuration`
- `lite:docs:development:check`
- `lite:docs:development:generate`
- `lite:docs:diagrams:check`
- `lite:docs:diagrams:generate`
- `lite:docs:events`
- `lite:docs:frontend-api`
- `lite:docs:generate`
- `lite:docs:openapi`
- `lite:docs:platform:check`
- `lite:docs:platform:generate`
- `lite:docs:production:check`
- `lite:docs:production:generate`
- `lite:docs:projections`
- `lite:docs:reason-codes`
- `lite:docs:recovery`
- `lite:docs:redaction`
- `lite:docs:release-evidence`
- `lite:docs:security`
- `lite:docs:serve`
- `lite:docs:services`
- `lite:docs:sqlite`
- `lite:docs:sqlite:check`
- `lite:docs:tools:check`
- `lite:docs:ui`
- `lite:docs:ui:screenshots`
- `lite:docs:validation`
- `lite:har:inspect`
- `lite:har:sanitize`
- `lite:playwright:preflight`
- `lite:release:artifact-check`
- `lite:release:dry-run`
- `lite:setup`
- `lite:setup:check`
- `lite:setup:system`
- `lite:storybook`
- `lite:storybook:build`
- `lite:storybook:screenshots`
- `lite:test:a11y`
- `lite:test:android`
- `lite:test:backend`
- `lite:test:contracts`
- `lite:test:docs`
- `lite:test:e2e:live`
- `lite:test:e2e:mocked`
- `lite:test:frontend`
- `lite:test:lighthouse`
- `lite:test:redaction`
- `lite:test:runtime`
- `lite:test:storybook`
- `lite:test:visual`
- `lite:test:visual:update`
- `lite:validation:check`
- `lite:validation:evidence`
- `lite:validation:record`
- `lite:windows:host:check`
- `lite:windows:vscode:check`
- `lite:windows:wsl:check`

## Task dependency graph

- `lite:allure` → `lite:validation:evidence`
- `lite:docs:check` → `lite:contracts:check`
- `lite:docs:check` → `lite:docs:development:check`
- `lite:docs:check` → `lite:docs:diagrams:check`
- `lite:docs:check` → `lite:docs:platform:check`
- `lite:docs:check` → `lite:docs:production:check`
- `lite:docs:check` → `lite:docs:tools:check`
- `lite:docs:generate` → `lite:contracts:generate`
- `lite:docs:generate` → `lite:docs:development:generate`
- `lite:docs:generate` → `lite:docs:diagrams:generate`
- `lite:docs:generate` → `lite:docs:platform:generate`
- `lite:docs:generate` → `lite:docs:production:generate`
- `lite:docs:generate` → `lite:docs:tools:check`
- `lite:docs:openapi` → `lite:contracts:generate`
- `lite:docs:ui:screenshots` → `lite:playwright:preflight`
- `lite:storybook:screenshots` → `lite:playwright:preflight`
- `lite:test:a11y` → `lite:playwright:preflight`
- `lite:test:docs` → `lite:playwright:preflight`
- `lite:test:e2e:live` → `lite:playwright:preflight`
- `lite:test:e2e:mocked` → `lite:playwright:preflight`
- `lite:test:lighthouse` → `lite:playwright:preflight`
- `lite:test:storybook` → `lite:playwright:preflight`
- `lite:test:visual` → `lite:playwright:preflight`
- `lite:test:visual:update` → `lite:playwright:preflight`

## Validation tiers

- Quick: compile, shell syntax, focused tests, contracts, PWA build, cheap generated-doc drift.
- Full: full Lite suites, Storybook, mocked Playwright, accessibility, redaction, Redocly, strict MkDocs.
- Release: live read-only browser checks, runtime/projection checks, optional Android evidence, release artifact validation, Allure-compatible evidence.
