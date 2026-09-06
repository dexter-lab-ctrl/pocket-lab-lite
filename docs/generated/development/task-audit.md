---
title: "Task ownership audit"
description: "The old root Taskfile exposed full-product tasks that were not a truthful Lite command surface. The repository search below drove the replacement."
status: verified
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: f395bcea9154f56908d6334ff8a318182bac9a3a0769b31a98339a49cf6f2733
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

- `lite:a11y:check`
- `lite:allure`
- `lite:api:breaking-changes`
- `lite:api:check`
- `lite:api:read-latency`
- `lite:api:schemathesis`
- `lite:api:schemathesis:discovery`
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
- `lite:dev:scratch:check`
- `lite:dev:scratch:prepare`
- `lite:dev:status`
- `lite:dev:up`
- `lite:dev:worker`
- `lite:docs:architecture:check`
- `lite:docs:architecture:generate`
- `lite:docs:architecture:icons:check`
- `lite:docs:architecture:validate`
- `lite:docs:backend-tests`
- `lite:docs:bootstrap`
- `lite:docs:capabilities`
- `lite:docs:check`
- `lite:docs:codebase-map:check`
- `lite:docs:codebase-map:generate`
- `lite:docs:configuration`
- `lite:docs:development:check`
- `lite:docs:development:generate`
- `lite:docs:diagrams:check`
- `lite:docs:diagrams:generate`
- `lite:docs:enterprise-tools:check`
- `lite:docs:enterprise-tools:plan`
- `lite:docs:enterprise-tools:setup`
- `lite:docs:enterprise-tools:update`
- `lite:docs:enterprise:check`
- `lite:docs:enterprise:generate`
- `lite:docs:events`
- `lite:docs:frontend-api`
- `lite:docs:generate`
- `lite:docs:health:check`
- `lite:docs:health:generate`
- `lite:docs:ia:check`
- `lite:docs:ia:generate`
- `lite:docs:intelligence:check`
- `lite:docs:intelligence:generate`
- `lite:docs:knowledge:ai-export`
- `lite:docs:knowledge:check`
- `lite:docs:knowledge:generate`
- `lite:docs:knowledge:graph`
- `lite:docs:knowledge:health`
- `lite:docs:knowledge:releases`
- `lite:docs:knowledge:traceability`
- `lite:docs:openapi`
- `lite:docs:parity:check`
- `lite:docs:parity:generate`
- `lite:docs:parity:local`
- `lite:docs:parity:local:check`
- `lite:docs:platform:check`
- `lite:docs:platform:generate`
- `lite:docs:production:check`
- `lite:docs:production:generate`
- `lite:docs:projections`
- `lite:docs:provenance:generate`
- `lite:docs:provenance:sign`
- `lite:docs:provenance:sign-release-set`
- `lite:docs:provenance:verify`
- `lite:docs:provenance:verify-release-set`
- `lite:docs:reason-codes`
- `lite:docs:recovery`
- `lite:docs:redaction`
- `lite:docs:release-assurance:capture`
- `lite:docs:release-assurance:check`
- `lite:docs:release-assurance:promote`
- `lite:docs:release-evidence`
- `lite:docs:runtime-network:check`
- `lite:docs:runtime:check`
- `lite:docs:runtime:generate`
- `lite:docs:security`
- `lite:docs:security-tools:check`
- `lite:docs:security-tools:plan`
- `lite:docs:security-tools:setup`
- `lite:docs:security-tools:update`
- `lite:docs:serve`
- `lite:docs:services`
- `lite:docs:sqlite`
- `lite:docs:sqlite:check`
- `lite:docs:supply-chain:capture`
- `lite:docs:supply-chain:check`
- `lite:docs:supply-chain:dependency-track:export`
- `lite:docs:supply-chain:promote`
- `lite:docs:supply-chain:qualify`
- `lite:docs:supply-chain:qualify:local`
- `lite:docs:supply-chain:resume`
- `lite:docs:supply-chain:status`
- `lite:docs:sync`
- `lite:docs:tools:check`
- `lite:docs:ui`
- `lite:docs:ui:screenshots`
- `lite:docs:validation`
- `lite:evidence:parity:check`
- `lite:evidence:parity:generate`
- `lite:evidence:runtime:check`
- `lite:evidence:runtime:preflight`
- `lite:evidence:runtime:promote`
- `lite:har:inspect`
- `lite:har:sanitize`
- `lite:parity:api`
- `lite:parity:backend`
- `lite:parity:check`
- `lite:parity:contracts:check`
- `lite:parity:contracts:generate`
- `lite:parity:fixtures:check`
- `lite:parity:fixtures:generate`
- `lite:parity:model:check`
- `lite:parity:playwright:live`
- `lite:parity:playwright:mocked`
- `lite:parity:runtime:capture`
- `lite:parity:runtime:compare`
- `lite:parity:selectors`
- `lite:parity:storybook`
- `lite:parity:termux`
- `lite:parity:tools:check`
- `lite:performance:edge`
- `lite:performance:wsl`
- `lite:playwright:preflight`
- `lite:release:artifact-check`
- `lite:release:dry-run`
- `lite:runtime:ssh:check`
- `lite:runtime:ssh:setup`
- `lite:runtime:termux:capture`
- `lite:runtime:termux:clean`
- `lite:runtime:termux:diff`
- `lite:runtime:termux:inspect`
- `lite:runtime:termux:promote`
- `lite:runtime:termux:validate`
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
- `lite:visual:check`
- `lite:windows:host:check`
- `lite:windows:vscode:check`
- `lite:windows:wsl:check`
