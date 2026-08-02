---
title: "Lite readiness evidence"
description: "Bounded recorded validation evidence; PASS is never synthesized."
status: verified
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_platform_catalogs.py
generator_version: 1
source_fingerprint: 249c0074e4683abfc085673d0adcbcfcf85b8888adec8968cba7edd8c03bacb1
schema_revision: 1
validation_status: generated
---

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Source generated</span>
</div>

# Lite readiness evidence

| Gate | Command | Commit | Platform | Result | Current | Artifact |
| --- | --- | --- | --- | --- | --- | --- |
| auto-detected |  |  |  |  | yes | .pocketlab-dev/validation/browser.json |
| allure-results | .venv/bin/python, scripts/dev/lite/validation_evidence.py, allure, --validation-dir, .pocketlab-dev/validation, --output, allure-results | d327d75308a9af03b57f44411b22aef1819cee45 | {'machine': 'x86_64', 'python': '3.14.4', 'release': '6.18.33.1-microsoft-standard-WSL2', 'system': 'Linux', 'wsl': 'true'} | passed | no | .pocketlab-dev/validation/commands/allure-results.json |
| browser-resolver | node, --test, tests/dev/browser-resolver.test.mjs | d327d75308a9af03b57f44411b22aef1819cee45 | {'machine': 'x86_64', 'python': '3.14.4', 'release': '6.18.33.1-microsoft-standard-WSL2', 'system': 'Linux', 'wsl': 'true'} | passed | no | .pocketlab-dev/validation/commands/browser-resolver.json |
| contracts | bash, scripts/dev/lite/check-contracts.sh | d327d75308a9af03b57f44411b22aef1819cee45 | {'machine': 'x86_64', 'python': '3.14.4', 'release': '6.18.33.1-microsoft-standard-WSL2', 'system': 'Linux', 'wsl': 'true'} | passed | no | .pocketlab-dev/validation/commands/contracts.json |
| diff-check | git, diff, --check | d327d75308a9af03b57f44411b22aef1819cee45 | {'machine': 'x86_64', 'python': '3.14.4', 'release': '6.18.33.1-microsoft-standard-WSL2', 'system': 'Linux', 'wsl': 'true'} | passed | no | .pocketlab-dev/validation/commands/diff-check.json |
| docs-development-drift | .venv/bin/python, scripts/docs/lite/generate_docs.py, check, --audience, development | d327d75308a9af03b57f44411b22aef1819cee45 | {'machine': 'x86_64', 'python': '3.14.4', 'release': '6.18.33.1-microsoft-standard-WSL2', 'system': 'Linux', 'wsl': 'true'} | passed | no | .pocketlab-dev/validation/commands/docs-development-drift.json |
| docs-production-drift | .venv/bin/python, scripts/docs/lite/generate_docs.py, check, --audience, production | d327d75308a9af03b57f44411b22aef1819cee45 | {'machine': 'x86_64', 'python': '3.14.4', 'release': '6.18.33.1-microsoft-standard-WSL2', 'system': 'Linux', 'wsl': 'true'} | passed | no | .pocketlab-dev/validation/commands/docs-production-drift.json |
| focused-backend | bash, -lc, PYTHONPATH=tests:pocket-lab-final-structure/runtime PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 '.venv/bin/python' -m pytest -q tests/backend/test_lite_api.py -k 'status or catalog or fleet or security or recovery or identity or policy' | d327d75308a9af03b57f44411b22aef1819cee45 | {'machine': 'x86_64', 'python': '3.14.4', 'release': '6.18.33.1-microsoft-standard-WSL2', 'system': 'Linux', 'wsl': 'true'} | passed | no | .pocketlab-dev/validation/commands/focused-backend.json |
| frontend-unit | npm, run, test:unit | d327d75308a9af03b57f44411b22aef1819cee45 | {'machine': 'x86_64', 'python': '3.14.4', 'release': '6.18.33.1-microsoft-standard-WSL2', 'system': 'Linux', 'wsl': 'true'} | passed | no | .pocketlab-dev/validation/commands/frontend-unit.json |
| protected-versions | bash, scripts/dev/lite/setup-check.sh | d327d75308a9af03b57f44411b22aef1819cee45 | {'machine': 'x86_64', 'python': '3.14.4', 'release': '6.18.33.1-microsoft-standard-WSL2', 'system': 'Linux', 'wsl': 'true'} | passed | no | .pocketlab-dev/validation/commands/protected-versions.json |
| pwa-build | npm, run, build | d327d75308a9af03b57f44411b22aef1819cee45 | {'machine': 'x86_64', 'python': '3.14.4', 'release': '6.18.33.1-microsoft-standard-WSL2', 'system': 'Linux', 'wsl': 'true'} | passed | no | .pocketlab-dev/validation/commands/pwa-build.json |
| python-compile | .venv/bin/python, -m, py_compile, scripts/docs/lite/generate_contracts.py, scripts/docs/lite/generate_docs.py, scripts/dev/lite/har_tool.py, scripts/dev/lite/redaction_check.py, scripts/dev/lite/validation_evidence.py, scripts/dev/lite/release_artifact_check.py | d327d75308a9af03b57f44411b22aef1819cee45 | {'machine': 'x86_64', 'python': '3.14.4', 'release': '6.18.33.1-microsoft-standard-WSL2', 'system': 'Linux', 'wsl': 'true'} | passed | no | .pocketlab-dev/validation/commands/python-compile.json |
| shell-syntax | bash, -lc, find scripts/dev/lite -maxdepth 1 -type f -name "*.sh" -print0 \| xargs -0 -r -n1 bash -n | d327d75308a9af03b57f44411b22aef1819cee45 | {'machine': 'x86_64', 'python': '3.14.4', 'release': '6.18.33.1-microsoft-standard-WSL2', 'system': 'Linux', 'wsl': 'true'} | passed | no | .pocketlab-dev/validation/commands/shell-syntax.json |
| auto-detected |  |  |  |  | yes | .pocketlab-dev/validation/playwright-browser.json |
| playwright-results |  |  |  |  | yes | .pocketlab-dev/validation/playwright-results.json |
| protected-tool-versions |  |  |  |  | yes | .pocketlab-dev/validation/protected-tool-versions.json |
| readiness-matrix |  | d327d75308a9af03b57f44411b22aef1819cee45 |  | passed | no | .pocketlab-dev/validation/readiness-matrix.json |
| test-artifact-index |  | d327d75308a9af03b57f44411b22aef1819cee45 |  |  | no | .pocketlab-dev/validation/test-artifact-index.json |
| validation-manifest |  | d327d75308a9af03b57f44411b22aef1819cee45 | {'machine': 'x86_64', 'python': '3.14.4', 'release': '6.18.33.1-microsoft-standard-WSL2', 'system': 'Linux', 'wsl': 'true'} |  | no | .pocketlab-dev/validation/validation-manifest.json |
