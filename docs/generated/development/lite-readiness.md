---
title: "Lite readiness contract"
description: "Stable source-owned validation contract. Local runtime evidence remains outside tracked generated documentation."
status: documented
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_platform_catalogs.py
generator_version: 1
source_fingerprint: 32d635a8f77706c04016dad7cdb74cbcf952888b988614e8a5b704dbcf285452
schema_revision: 1
validation_status: generated
---

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--documented">Documented</span>
<span class="pl-status pl-status--patch-provided">Source generated</span>
</div>

# Lite readiness contract

This page documents the available validation gates. It does not claim that the gates passed in the current checkout. Full local evidence remains under `.pocketlab-dev/validation`.

| Gate | Command | Generated status | Local evidence |
| --- | --- | --- | --- |
| accessibility | task lite:test:a11y | not evaluated in generated documentation | .pocketlab-dev/validation/commands/accessibility.json |
| android | task lite:test:android | not evaluated in generated documentation | .pocketlab-dev/validation/commands/android.json |
| backend-full | task lite:test:backend | not evaluated in generated documentation | .pocketlab-dev/validation/commands/backend-full.json |
| browser-resolver | node --test tests/dev/browser-resolver.test.mjs | not evaluated in generated documentation | .pocketlab-dev/validation/commands/browser-resolver.json |
| contracts | bash scripts/dev/lite/check-contracts.sh | not evaluated in generated documentation | .pocketlab-dev/validation/commands/contracts.json |
| diff-check | git diff --check | not evaluated in generated documentation | .pocketlab-dev/validation/commands/diff-check.json |
| docs-browser | task lite:test:docs | not evaluated in generated documentation | .pocketlab-dev/validation/commands/docs-browser.json |
| docs-development-drift | "$PYTHON" scripts/docs/lite/generate_docs.py check --audience development | not evaluated in generated documentation | .pocketlab-dev/validation/commands/docs-development-drift.json |
| docs-production-drift | "$PYTHON" scripts/docs/lite/generate_docs.py check --audience production | not evaluated in generated documentation | .pocketlab-dev/validation/commands/docs-production-drift.json |
| e2e-live | task lite:test:e2e:live | not evaluated in generated documentation | .pocketlab-dev/validation/commands/e2e-live.json |
| e2e-mocked | task lite:test:e2e:mocked | not evaluated in generated documentation | .pocketlab-dev/validation/commands/e2e-mocked.json |
| focused-backend | bash -lc "PYTHONPATH=tests:pocket-lab-final-structure/runtime PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 '$PYTHON' -m pytest -q tests/backend/test_lite_api.py -k 'status or catalog or fleet or security or recovery or identity or policy'" | not evaluated in generated documentation | .pocketlab-dev/validation/commands/focused-backend.json |
| frontend-unit | npm run test:unit | not evaluated in generated documentation | .pocketlab-dev/validation/commands/frontend-unit.json |
| protected-versions | bash scripts/dev/lite/setup-check.sh | not evaluated in generated documentation | .pocketlab-dev/validation/commands/protected-versions.json |
| pwa-build | npm run build | not evaluated in generated documentation | .pocketlab-dev/validation/commands/pwa-build.json |
| python-compile | "$PYTHON" -m py_compile \ | not evaluated in generated documentation | .pocketlab-dev/validation/commands/python-compile.json |
| redaction | task lite:test:redaction | not evaluated in generated documentation | .pocketlab-dev/validation/commands/redaction.json |
| release-dry-run | task lite:release:dry-run | not evaluated in generated documentation | .pocketlab-dev/validation/commands/release-dry-run.json |
| runtime | task lite:test:runtime | not evaluated in generated documentation | .pocketlab-dev/validation/commands/runtime.json |
| shell-syntax | bash -lc 'find scripts/dev/lite -maxdepth 1 -type f -name "*.sh" -print0 \| xargs -0 -r -n1 bash -n' | not evaluated in generated documentation | .pocketlab-dev/validation/commands/shell-syntax.json |
| storybook | task lite:test:storybook | not evaluated in generated documentation | .pocketlab-dev/validation/commands/storybook.json |
| visual | task lite:test:visual | not evaluated in generated documentation | .pocketlab-dev/validation/commands/visual.json |
