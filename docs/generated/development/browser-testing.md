---
title: "Playwright and browser resolution"
description: "WSL2 browser selection is a first-class preflight. The resolver checks explicit environment variables before auto-detecting `/usr/bin/google-chrome`; CI may use a verified Playwright-managed browser."
status: verified
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 37ee89db14b20c26cd201355869f9c32507333d2f2e95bb7c5c3b46d63b6045d
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
