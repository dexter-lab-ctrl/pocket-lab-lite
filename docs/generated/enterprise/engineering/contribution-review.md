---
title: "Contribution & Review"
description: "Developer onboarding from setup through release review."
generated: true
audience: development
page_type: handbook
confidence: generated
---

# Contribution & Review — developer onboarding

## Before coding
Inspect ownership, contracts, current generated state and architecture boundaries.

## During implementation
Change canonical source, not generated artifacts. Keep execution backend-owned and evidence sanitized.

## Testing
Use Change Impact Advisor plus focused tests, then the normal gates.

## Documentation
Regenerate deterministic outputs; MkDocs never captures/promotes runtime.

## Evidence
Capture runtime/security evidence only through explicit bounded workflows.

## Before commit
Run `git diff --check`, relevant tests and generated checks.

## PR review
Review source, contracts, generated delta, security implications and evidence status.

## Merge
Merge only validated source + generated outputs; keep `main` clean.

## Release
Use the existing annotated date tag + `dist.zip` workflow; release/runtime promotion remain distinct.

## Change-type matrix

| Change type | Contracts/tests/docs/evidence | Security review |
| --- | --- | --- |
| Backend API | ['OpenAPI', 'parity', 'reason codes', 'event metadata']; ['focused owner tests', 'task lite:docs:check', 'task lite:check']; ['regenerate canonical generated outputs', 'review release/change impact', 'never hand-edit generated docs']; ['source validation', 'promoted runtime/security evidence only through explicit capture/sanitize/promote when the change affects runtime truth'] | risk-based |
| Frontend | ['frontend API usage', 'safe snapshots', 'UX/documentation contracts']; ['focused owner tests', 'task lite:docs:check', 'task lite:check']; ['regenerate canonical generated outputs', 'review release/change impact', 'never hand-edit generated docs']; ['source validation', 'promoted runtime/security evidence only through explicit capture/sanitize/promote when the change affects runtime truth'] | risk-based |
| SQLite migration | ['SQLite schema', 'migration inventory', 'backup/recovery']; ['focused owner tests', 'task lite:docs:check', 'task lite:check']; ['regenerate canonical generated outputs', 'review release/change impact', 'never hand-edit generated docs']; ['source validation', 'promoted runtime/security evidence only through explicit capture/sanitize/promote when the change affects runtime truth'] | risk-based |
| NATS/event | ['AsyncAPI', 'event encyclopedia', 'delivery/reason contracts']; ['focused owner tests', 'task lite:docs:check', 'task lite:check']; ['regenerate canonical generated outputs', 'review release/change impact', 'never hand-edit generated docs']; ['source validation', 'promoted runtime/security evidence only through explicit capture/sanitize/promote when the change affects runtime truth'] | required |
| Worker | ['commands', 'events', 'evidence', 'runbooks']; ['focused owner tests', 'task lite:docs:check', 'task lite:check']; ['regenerate canonical generated outputs', 'review release/change impact', 'never hand-edit generated docs']; ['source validation', 'promoted runtime/security evidence only through explicit capture/sanitize/promote when the change affects runtime truth'] | risk-based |
| Node agent | ['device capability', 'heartbeat', 'command/evidence contracts']; ['focused owner tests', 'task lite:docs:check', 'task lite:check']; ['regenerate canonical generated outputs', 'review release/change impact', 'never hand-edit generated docs']; ['source validation', 'promoted runtime/security evidence only through explicit capture/sanitize/promote when the change affects runtime truth'] | required |
| Supervisor | ['recovery', 'reason codes', 'device health']; ['focused owner tests', 'task lite:docs:check', 'task lite:check']; ['regenerate canonical generated outputs', 'review release/change impact', 'never hand-edit generated docs']; ['source validation', 'promoted runtime/security evidence only through explicit capture/sanitize/promote when the change affects runtime truth'] | required |
| Security scanner | ['security evidence', 'Threat Model', 'SBOM/vulnerability evidence']; ['focused owner tests', 'task lite:docs:check', 'task lite:check']; ['regenerate canonical generated outputs', 'review release/change impact', 'never hand-edit generated docs']; ['source validation', 'promoted runtime/security evidence only through explicit capture/sanitize/promote when the change affects runtime truth'] | required |
| Device bootstrap | ['invite/bootstrap', 'identity', 'runtime configuration']; ['focused owner tests', 'task lite:docs:check', 'task lite:check']; ['regenerate canonical generated outputs', 'review release/change impact', 'never hand-edit generated docs']; ['source validation', 'promoted runtime/security evidence only through explicit capture/sanitize/promote when the change affects runtime truth'] | required |
| Tailscale | ['remote-access readiness', 'Threat Model', 'dependency health']; ['focused owner tests', 'task lite:docs:check', 'task lite:check']; ['regenerate canonical generated outputs', 'review release/change impact', 'never hand-edit generated docs']; ['source validation', 'promoted runtime/security evidence only through explicit capture/sanitize/promote when the change affects runtime truth'] | required |
| Application integration | ['app lifecycle', 'routes', 'backup/security/recovery evidence']; ['focused owner tests', 'task lite:docs:check', 'task lite:check']; ['regenerate canonical generated outputs', 'review release/change impact', 'never hand-edit generated docs']; ['source validation', 'promoted runtime/security evidence only through explicit capture/sanitize/promote when the change affects runtime truth'] | risk-based |
| Documentation generator | ['generated documentation', 'source fingerprints', 'page anatomy']; ['focused owner tests', 'task lite:docs:check', 'task lite:check']; ['regenerate canonical generated outputs', 'review release/change impact', 'never hand-edit generated docs']; ['source validation', 'promoted runtime/security evidence only through explicit capture/sanitize/promote when the change affects runtime truth'] | risk-based |
| Generated contracts | ['knowledge/parity/intelligence/release contracts']; ['focused owner tests', 'task lite:docs:check', 'task lite:check']; ['regenerate canonical generated outputs', 'review release/change impact', 'never hand-edit generated docs']; ['source validation', 'promoted runtime/security evidence only through explicit capture/sanitize/promote when the change affects runtime truth'] | risk-based |
| Release workflow | ['release manifest', 'checksums', 'SBOM', 'signing/provenance']; ['focused owner tests', 'task lite:docs:check', 'task lite:check']; ['regenerate canonical generated outputs', 'review release/change impact', 'never hand-edit generated docs']; ['source validation', 'promoted runtime/security evidence only through explicit capture/sanitize/promote when the change affects runtime truth'] | required |
