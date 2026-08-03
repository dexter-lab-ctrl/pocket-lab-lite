---
title: "Task ownership audit"
description: "The old root Taskfile exposed full-product tasks that were not a truthful Lite command surface. The repository search below drove the replacement."
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

# Task ownership audit

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Development guidance</span>
</div>

The old root Taskfile exposed full-product tasks that were not a truthful Lite command surface. The repository search below drove the replacement.

## Verified Lite-ready before refactor

- `lite:check`
- `lite:api:check`
- `lite:docs:check`
- `lite:bootstrap:check`
- `android:smoke`
- `release:dry-run`
- `dev:up`
- `dev:down`
- `dev:status`
- `dev:backend`
- `dev:worker`
- `dev:frontend`
- `dev:nats`

## Adapted into the Lite task surface

- `setup`
- `check`
- `test:frontend`
- `test:backend`
- `test:e2e`
- `test:storybook`
- `test:visual`
- `test:lighthouse`
- `test:a11y`
- `test:redaction`
- `check:api-contract`
- `check:schemas`
- `docs:api`
- `docs:events`
- `docs:build`
- `docs:serve`
- `docs:check`
- `storybook:screenshots`
- `windows:host:check`
- `windows:vscode:check`
- `windows:wsl:check`

## Removed full-version-only tasks

- `check:iac`
- `test:iac`
- `test:websockets`
- `test:golden`
- `trace:operation`
- `docs:operations`
- `docs:operations:seed`
- `docs:operations:metadata:check`
- `docs:architecture:serve`
- `docs:architecture:export`
- `threatdragon:pull`
- `threatdragon:serve`
- `threatdragon:stop`
- `threatdragon:logs`
- `docs:threat-model`
- `docs:threat-model:check`
- `docs:operations:security:enrich`
- `docs:threat-model:drift:seal`
- `docs:threat-model:drift`
- `docs:threat-model:drift:docs`
- `docs:threat-model:sync`
- `docs:threat-model:sync:check`
- `docs:security:policies`
- `docs:security:policies:check`
- `docs:security:controls`
- `docs:security:controls:check`
- `docs:security:full-check`
- `docs:runbooks:catalog`
- `docs:runbooks`
- `docs:runbooks:check`
- `docs:runbooks:docs`
- `docs:runbooks:docs:check`
- `docs:runbooks:gates`
- `docs:runbooks:gates:check`
- `docs:runbooks:full-check`
- `test:runbooks:execution`
- `docs:deployment:ansible`
- `docs:deployment:ansible:check`

## Removed duplicate or legacy aliases

- `check:frontend`
- `check:backend`
- `check:bootstrap`
- `check:contracts`
- `check:supply-chain`
- `build:pwa`
- `dev:nats:down`
- `dev:observe`
- `observability:status`
- `docs:observability:runtime-snapshot`
- `dev:reset`
- `test:network`
- `test:flakes`
- `docs:ui:evidence`
- `docs:ui:evidence:check`

## Kept only as explicit release/device concepts

- `test:nats`
- `test:nats-permissions`
- `test:faults`
- `test:performance`
- `lite:security:s8:gate:termux`
- `lite:security:s8:gate:ubuntu`

## Current Lite task surface

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
