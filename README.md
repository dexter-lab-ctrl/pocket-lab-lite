# Pocket Lab Lite

Pocket Lab Lite is the lightweight variant of Pocket Lab for low-power Android/Termux and small edge devices.

It keeps the core Pocket Lab control-plane architecture while presenting a simpler appliance-style UI and a smaller runtime footprint.

```text
React / Vite PWA
→ FastAPI
→ NATS / JetStream
→ Workers
→ Events
→ FastAPI
→ UI
```

## Who it is for

Pocket Lab Lite is for users who want to run a local self-hosted control plane on constrained devices, including Android/Termux and small ARM64 edge systems.

## How it differs from full Pocket Lab

Full Pocket Lab targets stronger edge devices and can include deeper observability, enterprise governance, release workflows, generated evidence, and advanced operator views.

Pocket Lab Lite keeps the core control-plane model but focuses on:

- a simpler UI;
- fewer default services;
- built-in health summaries;
- lower memory usage;
- core app, identity, security, device, policy, and recovery workflows.

## Included by default

- FastAPI control API
- NATS / JetStream
- worker-owned typed operation execution
- Vault-backed identity and access workflows
- App Catalog workflows
- Device/fleet workflows
- Security and policy summaries
- Backup and recovery workflows
- lightweight local telemetry
- Caddy/static frontend serving where available

## Excluded by default

Pocket Lab Lite does not start the external observability stack by default:

- Prometheus
- Grafana
- Gatus
- Loki
- Promtail

Lite status should come from built-in service health checks and the `/api/lite/status` API.

## Android / Termux quick start

```bash
git clone https://github.com/dexter-lab-ctrl/pocket-lab-lite.git
cd pocket-lab-lite/pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched
bash scripts/bootstrap.sh --profile lite
```

If the lite profile has not been implemented yet, use this repository as the skeleton baseline and continue with the backend, frontend, and bootstrap lite patches.

## Documentation

Local docs:

```bash
mkdocs build --strict
mkdocs serve -a 127.0.0.1:8001
```
