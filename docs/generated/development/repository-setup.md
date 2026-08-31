---
title: "Repository and WSL2 setup"
description: "Development runs from the Linux filesystem under WSL2. Repository setup restores the committed lockfiles and does not search for or install newer tool versions."
status: verified
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_docs.py
source_fingerprint: 79b0e01b24665f059831d69eefd645ba0d3e38e7ada851fd964ef052494816e6
schema_revision: 1
validation_status: generated
---

# Repository and WSL2 setup

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Development guidance</span>
</div>

Development runs from the Linux filesystem under WSL2. Repository setup restores the committed lockfiles and does not search for or install newer tool versions.

```bash
cd ~/pocket-lab-lite
task lite:setup
task lite:setup:check
```

The setup task reuses the existing `.venv`, runs `npm ci` only when `node_modules` is absent, skips Playwright browser downloads, and installs Python requirements only when imports are missing.
