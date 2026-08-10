---
title: "Validation Coverage Dashboard"
description: "Repository-native validation coverage; never live CI polling."
generated: true
audience: development
page_type: reference
confidence: generated
---

# Validation Coverage Dashboard

| Gate | Implemented | Discoverable | Latest canonical status | Canonical evidence |
| --- | --- | --- | --- | --- |
| backend tests | implemented | yes | verified | {'kind': 'validation-gate', 'id': 'parity-backend', 'status': 'verified', 'evidence': 'parity/backend.json', 'task': 'lite:parity:backend'}, {'kind': 'validation-gate', 'id': 'parity-api', 'status': 'verified', 'evidence': 'parity/api.json', 'task': 'lite:parity:api'} |
| parity | implemented | yes | verified | {'kind': 'validation-gate', 'id': 'release-readiness', 'status': 'partial', 'evidence': 'parity/evidence-manifest.json', 'task': 'lite:parity:check'}, {'kind': 'validation-gate', 'id': 'parity-contracts', 'status': 'verified', 'evidence': 'parity/contracts.json', 'task': 'lite:parity:contracts:check'}, {'kind': 'validation-gate', 'id': 'parity-selectors', 'status': 'verified', 'evidence': 'parity/selectors.json', 'task': 'lite:parity:selectors'} |
| Playwright | implemented | yes | patch-provided | {'kind': 'validation-gate', 'id': 'parity-playwright-mocked', 'status': 'patch-provided', 'evidence': 'playwright-results.json', 'task': 'lite:parity:playwright:mocked'}, {'kind': 'validation-gate', 'id': 'parity-playwright-live', 'status': 'unvalidated', 'evidence': 'playwright-results.json', 'task': 'lite:parity:playwright:live'} |
| accessibility | implemented | yes | patch-provided | {'kind': 'validation-gate', 'id': 'parity-a11y', 'status': 'patch-provided', 'evidence': 'playwright-junit.xml', 'task': 'lite:a11y:check'} |
| OpenAPI | implemented | yes | promoted | {'kind': 'validation-gate', 'id': 'api-breaking', 'status': 'patch-provided', 'evidence': 'parity/oasdiff.json', 'task': 'lite:api:breaking-changes'}, {'kind': 'canonical-artifact', 'path': 'contracts/parity/openapi-baseline-promotion.json', 'status': 'promoted'} |
| Schemathesis | implemented | yes | patch-provided | {'kind': 'validation-gate', 'id': 'api-schemathesis', 'status': 'patch-provided', 'evidence': 'parity/schemathesis.xml', 'task': 'lite:api:schemathesis'} |
| oasdiff | implemented | yes | patch-provided | {'kind': 'validation-gate', 'id': 'api-breaking', 'status': 'patch-provided', 'evidence': 'parity/oasdiff.json', 'task': 'lite:api:breaking-changes'} |
| architecture drift | implemented | yes | observed | {'kind': 'canonical-artifact', 'path': 'contracts/generated/architecture-catalog.json', 'status': 'observed'} |
| knowledge determinism | implemented | yes | observed | {'kind': 'canonical-artifact', 'path': 'contracts/generated/knowledge/index.json', 'status': 'observed'} |
| runtime evidence | implemented | yes | promoted | {'kind': 'canonical-artifact', 'path': 'contracts/parity/runtime-verification-baseline.json', 'status': 'promoted'} |
| SBOM | implemented | yes | observed | {'kind': 'canonical-artifact', 'path': 'contracts/generated/supply-chain/sbom-dev.cdx.json', 'status': 'observed'} |
| vulnerability analysis | implemented | yes | observed | {'kind': 'canonical-artifact', 'path': 'contracts/generated/supply-chain/vulnerability-correlation.json', 'status': 'observed'} |
| secret scanning | implemented | no | observed | {'kind': 'canonical-artifact', 'path': 'contracts/generated/supply-chain/security-analysis.json', 'status': 'observed'} |
| static analysis | implemented | no | observed | {'kind': 'canonical-artifact', 'path': 'contracts/generated/supply-chain/security-analysis.json', 'status': 'observed'} |
| documentation strict build | implemented | yes | verified | {'kind': 'validation-gate', 'id': 'docs-parity', 'status': 'verified', 'evidence': 'parity/docs.json', 'task': 'lite:docs:parity:check'} |
