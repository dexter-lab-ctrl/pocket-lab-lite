---
title: "Playwright and browser resolution"
description: "WSL2 browser selection is a first-class preflight. The resolver checks explicit environment variables before auto-detecting `/usr/bin/google-chrome`; CI may use a verified Playwright-managed browser."
status: verified
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 1f7558299edb6b35ba0042c78d5e818f2a4c4cdfcafd785a0c9e510bff3808bc
schema_revision: 1
validation_status: generated
---

# Playwright and browser resolution

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Development guidance</span>
</div>

WSL2 browser selection is a first-class preflight. The resolver checks explicit environment variables before auto-detecting `/usr/bin/google-chrome`; CI may use a verified Playwright-managed browser.

## Projects

- mocked-desktop
- mocked-mobile
- live-desktop
- live-mobile

## Evidence

`.pocketlab-dev/validation/playwright-browser.json` records the actual executable, version, launch mode, and WSL detection. Raw HAR files are ignored; only sanitized HAR output may be retained.
