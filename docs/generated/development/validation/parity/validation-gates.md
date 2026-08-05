---
title: "Validation Gate Catalog"
generated: true
audience: development
status: generated
source_revision: repository-source
semantic_fingerprint: 6416acf0e1764391a0818d34e899f07cdf587e197b13c5481b87128c5caaad57
generator: scripts/docs/parity/generate_parity.py
---

# Validation Gate Catalog
> Status vocabulary: **verified** is source/test confirmed; **partial** is source-derived but incomplete; **planned** is not implemented; **unvalidated** has not been run in the current environment.

| Gate | Task | Suite | Evidence | Blocking | Environment | Status |
| --- | --- | --- | --- | --- | --- | --- |
| Canonical contracts and schema | lite:parity:contracts:check | tests/parity/test_contract_generation.py | parity/contracts.json | True | wsl2-ci | verified |
| Fixture drift and sanitization | lite:parity:fixtures:check | tests/parity/test_contract_generation.py | parity/fixtures.json | True | wsl2-ci | verified |
| Backend authority to API mapping | lite:parity:backend | tests/parity/test_backup_recovery_parity.py | parity/backend.json | True | isolated-sqlite | verified |
| FastAPI recovery projection | lite:parity:api | tests/parity/test_backup_recovery_parity.py | parity/api.json | True | isolated-fastapi | verified |
| API to selector | lite:parity:selectors | src/lib/liteRecoveryParity.test.js | parity/selectors.json | True | vitest-jsdom | verified |
| Storybook registry linkage | lite:parity:storybook | src/lite/LiteRecoveryParity.stories.jsx | parity/storybook.json | True | storybook | patch-provided |
| Selector meaning to rendered UI | lite:parity:playwright:mocked | tests/e2e/lite-parity.spec.ts | playwright-results.json | True | external-chrome-mocked | patch-provided |
| Axe accessibility | lite:a11y:check | tests/e2e/lite-accessibility.spec.ts | playwright-junit.xml | True | external-chrome-mocked | patch-provided |
| Visual regression | lite:visual:check | tests/e2e/lite-visual.spec.ts | playwright-report | False | external-chrome-mocked | patch-provided |
| Read-only live Termux authority | lite:parity:termux | scripts/test/parity/verify_termux_parity.sh | parity/termux.json | False | wsl2-termux | unvalidated |
| Live browser projection | lite:parity:playwright:live | tests/e2e/lite-live.spec.ts | playwright-results.json | False | external-chrome-live | unvalidated |
| Safe OpenAPI property tests | lite:api:schemathesis | scripts/test/parity/run_schemathesis.sh | parity/schemathesis.xml | True | isolated-fastapi | patch-provided |
| OpenAPI breaking changes | lite:api:breaking-changes | scripts/test/parity/run_oasdiff.sh | parity/oasdiff.json | True | wsl2-ci | patch-provided |
| Bounded edge reads | lite:performance:edge | performance/parity/edge-readonly.js | parity/k6-edge.json | False | termux-edge | patch-provided |
| Generated parity documentation drift | lite:docs:parity:check | scripts/docs/parity/generate_parity.py check | parity/docs.json | True | wsl2-ci | verified |
| Parity release readiness | lite:parity:check | Taskfile aggregate | parity/evidence-manifest.json | True | wsl2-ci | partial |
