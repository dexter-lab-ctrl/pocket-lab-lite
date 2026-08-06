---
title: "Playwright Test Coverage Report"
generated: true
audience: development
status: generated
source_revision: repository-source
semantic_fingerprint: b7775f31c564307fda5d795c62195d03810206e330182eec14f52fa99bbf13f2
generator: scripts/docs/parity/generate_parity.py
---

# Playwright Test Coverage Report
> Status vocabulary: **verified** is source/test confirmed; **partial** is source-derived but incomplete; **planned** is not implemented; **unvalidated** has not been run in the current environment.

Mocked desktop/mobile projects use the existing external-browser resolver, retained failure traces, screenshots, JSON/JUnit evidence, and deterministic MSW scenarios. Live projects are read-only and opt-in.

| Project | Mode | Proves | Evidence |
| --- | --- | --- | --- |
| mocked-desktop/mobile | MSW | rendered meaning, stale/offline/error states | .pocketlab-dev/validation/playwright-results.json |
| live-desktop/mobile | Caddy/FastAPI | live browser/API integration | .pocketlab-dev/validation/playwright-results.json |
