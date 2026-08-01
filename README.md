# Pocket Lab Lite

Pocket Lab Lite is an edge-first, self-hostable local control plane for Android/Termux, ARM64, low-power devices, Ubuntu/WSL2 development, and private self-hosting.

```text
React / Vite PWA
→ Caddy same-origin proxy
→ FastAPI /api/lite/*
→ SQLite + NATS / JetStream
→ worker / agent / supervisor
→ events, heartbeats, sanitized evidence
→ FastAPI prepared reads
→ UI
```

The frontend never talks directly to NATS, executes shell commands, or stores backend secrets. FastAPI remains the control API; workers, agents, and supervisors own execution and recovery.

## Current product areas

- Home
- Devices
- Apps / App Catalog
- Backup & Restore / Recovery
- Security / Safety
- Identity
- Rules

Identity and Rules are present but remain partial where the current repository does not provide complete production behavior. Documentation and fixtures mark those states explicitly rather than inventing routes or execution.

## Android / Termux quick start

```bash
git clone https://github.com/dexter-lab-ctrl/pocket-lab-lite.git
cd pocket-lab-lite/pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched
bash scripts/bootstrap.sh --profile lite
```

Use backend-generated device bootstrap commands for secondary-device enrollment. Never publish invite material, runtime environment values, or generated secrets.

## Development PC

Daily development should run from the Linux filesystem inside Ubuntu/WSL2.

```bash
task lite:setup:check
task lite:playwright:preflight
task lite:check:quick
```

The WSL2 browser resolver prefers the verified external Chrome binary and records the actual executable and version. It does not silently fall back to an unusable Playwright-downloaded browser on WSL2.

## Documentation

Development and Production documentation are generated independently and built together with MkDocs:

```bash
task lite:docs:development:generate
task lite:docs:production:generate
task lite:docs:check
task lite:docs:serve
```

Development tooling such as Storybook, Playwright, Redocly, MkDocs, and Allure-compatible result generation is not required on the Android server phone and is not included in `dist.zip`.

## Validation tiers

```bash
# Frequent local work
task lite:check:quick

# Full Development-PC qualification
task lite:check

# Explicit live/release qualification
task lite:check:release
```

The release tier requires a running isolated Lite stack and explicit opt-in for live and Android/Termux checks. It never treats desktop-only measurements as Android production evidence.

## Release artifact

```bash
task lite:release:dry-run
task lite:release:artifact-check
```

The validated release assets are `dist.zip`, `checksums.txt`, and the optional Pocket Lab Lite release manifest. Development documentation, state databases, raw HARs, traces, and secrets are excluded.
