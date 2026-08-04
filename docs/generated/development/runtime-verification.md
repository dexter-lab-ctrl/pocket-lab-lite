---
title: "Termux runtime verification"
description: "Development-only WSL2 SSH capture, redaction, promotion, and runtime/source comparison workflow."
audience: development
status: verified
generated: true
generated_at: uncommitted
source_commit: uncommitted
generator: scripts/docs/runtime/generate_termux_runtime_docs.py
generator_version: 1
schema_revision: 1
validation_status: verified
---

<div class="pl-page-meta"><span class="pl-status pl-status--verified">Source-derived</span><span class="pl-status pl-status--verified">Verified</span></div>

# Termux runtime verification

**Current classification:** Promoted runtime verified.

Documentation truth combines repository source, an explicitly promoted sanitized runtime baseline, and browser validation. Local live captures under `.pocketlab-dev` never become tracked documentation inputs automatically.

## Three-layer evidence model

| Layer | Location | Tracked | Used by normal checks |
| --- | --- | --- | --- |
| Raw transient capture | `.pocketlab-dev/runtime-captures/<capture-id>/raw/` | no | no |
| Sanitized local projection | `.pocketlab-dev/runtime-captures/<capture-id>/sanitized/` | no | no |
| Explicit promoted baseline | `architecture/runtime-baselines/server-phone.json` | yes | yes |

## Safe workflow

```bash
bash scripts/docs/runtime/setup_termux_ssh.sh --prepare-key
bash scripts/docs/runtime/setup_termux_ssh.sh --check
bash scripts/docs/runtime/capture_termux_runtime.sh
python3 scripts/docs/runtime/promote_termux_runtime.py inspect
python3 scripts/docs/runtime/promote_termux_runtime.py validate
python3 scripts/docs/runtime/promote_termux_runtime.py diff
LITE_RUNTIME_PROMOTE=1 python3 scripts/docs/runtime/promote_termux_runtime.py promote
python3 scripts/docs/runtime/generate_termux_runtime_docs.py generate
```

The streamed phone probe is read-only, allowlisted, bounded, and uses one SSH connection. Each probe has a fixed ID, capability requirement, timeout, output cap, parser, sanitizer, required/optional state, and semantic failure class. It does not install packages, restart processes, read secret files, copy databases, query live rows, collect raw logs, or scan user media.

## Canonical architecture comparison

| Canonical component | Classification | Runtime evidence |
| --- | --- | --- |
| Lite agent supervisor | source-and-runtime-verified | verified |
| Caddy same-origin proxy | source-and-runtime-verified | verified |
| FastAPI /api/lite/* | source-and-runtime-verified | verified |
| NATS / JetStream | source-and-runtime-verified | verified |
| Lite node agent | source-and-runtime-verified | verified |
| PhotoPrism | source-and-runtime-verified | verified |
| PM2 process manager | source-and-runtime-verified | verified |
| PROot Ubuntu application container | runtime-unavailable | unavailable |
| SQLite control-plane store | source-and-runtime-verified | verified |
| Tailscale remote access | source-and-runtime-verified | verified |
| tailscaled daemon | source-and-runtime-verified | verified |
| Worker process | source-and-runtime-verified | verified |

Browser-state libraries remain source/browser verified: TanStack Query owns live safe FastAPI cache, Dexie owns safe fallback snapshots, Zustand owns harmless UI coordination, and XState owns guided workflow state. Termux runtime evidence is not authoritative for browser IndexedDB or UI state.
