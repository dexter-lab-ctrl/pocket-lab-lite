---
title: "Playwright and browser resolution"
description: "WSL2 browser selection is a first-class preflight. The resolver checks explicit environment variables before auto-detecting `/usr/bin/google-chrome`; CI may use a verified Playwright-managed browser."
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
