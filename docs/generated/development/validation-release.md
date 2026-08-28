---
title: "Validation and release evidence"
description: "Lite validation commands write bounded command records under `.pocketlab-dev/validation`; `task lite:allure` converts those records into Allure-compatible JSON without adding a production dependency."
status: verified
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: ae852e970e2385b9f84509e4a446d978365eb0e16ee80c312f96ab8f18ee8983
schema_revision: 1
validation_status: generated
---

# Validation and release evidence

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Development guidance</span>
</div>

Lite validation commands write bounded command records under `.pocketlab-dev/validation`; `task lite:allure` converts those records into Allure-compatible JSON without adding a production dependency.

## Release artifact contract

- `dist.zip` contains only the PWA output.
- `checksums.txt` must match `dist.zip`.
- `pocketlab-lite-release.json`, when present, must identify product, release tag, source commit, target, and artifact digest.
- Storybook, MkDocs, Redocly, Playwright, Allure results, state databases, and secrets are excluded.
