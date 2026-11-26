---
title: "Bootstrap stages"
description: "Source-inspected Day-0 stage graph, side-effect boundaries, retry and failure behavior."
status: verified
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_platform_catalogs.py
generator_version: 1
source_fingerprint: cd1cb9003e1ba0dc7a620a54482767ca49aaf5d0cb4856e792e3e948bcc465d9
schema_revision: 1
validation_status: generated
---

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Source generated</span>
</div>

# Bootstrap stages

Documentation generation inspects stage definitions only and never executes bootstrap stages.

| # | Stage | Script | Description | Safe retry | Failure behavior |
| --- | --- | --- | --- | --- | --- |
| 1 | `install_termux_packages` | `pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/install-termux-packages.sh` | Install Termux packages, base CLI tools, Node, PM2, Caddy, and build dependencies | yes | fail closed; later stages do not run |
| 2 | `install_proot_ubuntu` | `pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/install-proot-ubuntu.sh` | Install and prepare the proot Ubuntu compatibility layer | yes | fail closed; later stages do not run |
| 3 | `install_binaries` | `pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/install-binaries.sh` | Install Python runtime packages, NATS tooling, security tools, OPA, and profile-selected native binaries | yes | fail closed; later stages do not run |
| 4 | `install_tailscale` | `pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/install-tailscale.sh` | Install or prepare Tailscale connectivity for fleet access | yes | fail closed; later stages do not run |
| 5 | `install_pwa_ui` | `pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/install-pwa-ui.sh` | Install the production React/Vite PWA assets | yes | fail closed; later stages do not run |
| 6 | `start_dashboard` | `pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/start-dashboard.sh` | Start NATS/JetStream, FastAPI, worker, node agent, Caddy, and native Lite services | yes | fail closed; later stages do not run |
| 7 | `install_fleet_agent` | `pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/install-fleet-agent.sh` | Install the local NATS-backed fleet agent wrapper using generated NATS credentials | yes | fail closed; later stages do not run |
| 8 | `smoke_test` | `pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/smoke-test.sh` | Run profile-aware Day-0 smoke tests | yes | fail closed; later stages do not run |
| 9 | `install_lite_boot_recovery` | `pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/lite/install-boot-recovery.sh` | Install Pocket Lab Lite Android boot recovery and external PM2 guardian | yes | fail closed; later stages do not run |
