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
source_fingerprint: 468182830771fbe9b37cb7ad3cfff267d80f61ebf5352f4d506b9eb2c502447f
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
| 1 | `install_termux_packages` | `pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/install-termux-packages.sh` | Install Termux packages, base CLI tools, Node, PM2, MariaDB, Gitea, Caddy, and build dependencies | yes | fail closed; later stages do not run |
| 2 | `install_proot_ubuntu` | `pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/install-proot-ubuntu.sh` | Install and prepare the proot Ubuntu compatibility layer | yes | fail closed; later stages do not run |
| 3 | `install_binaries` | `pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/install-binaries.sh` | Install Vault, act_runner, Python runtime packages, NATS tooling, and profile-selected optional binaries | yes | fail closed; later stages do not run |
| 4 | `init_vault` | `pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/init-vault.sh` | Start and initialize Vault, unseal it, enable engines, and seed initial platform secrets | yes | fail closed; later stages do not run |
| 5 | `init_mariadb` | `pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/init-mariadb.sh` | Initialize MariaDB, create Pocket Lab service users, and register Vault database integration | yes | fail closed; later stages do not run |
| 6 | `start_gitea` | `pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/start-gitea.sh` | Start Gitea and act_runner, create the admin user, and prepare GitOps repositories | yes | fail closed; later stages do not run |
| 7 | `seed_gitops_repo` | `pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/seed-gitops-repo.sh` | Seed or refresh the GitOps/IaC repository in local Gitea | yes | fail closed; later stages do not run |
| 8 | `install_tailscale` | `pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/install-tailscale.sh` | Install or prepare Tailscale connectivity for fleet access | yes | fail closed; later stages do not run |
| 9 | `install_pwa_ui` | `pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/install-pwa-ui.sh` | Install the production React/Vite PWA assets | yes | fail closed; later stages do not run |
| 10 | `start_dashboard` | `pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/start-dashboard.sh` | Start NATS/JetStream, FastAPI, worker, node agent, Caddy, and profile-selected services | yes | fail closed; later stages do not run |
| 11 | `install_fleet_agent` | `pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/install-fleet-agent.sh` | Install the local NATS-backed fleet agent wrapper using generated NATS credentials | yes | fail closed; later stages do not run |
| 12 | `smoke_test` | `pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/smoke-test.sh` | Run Day-0 smoke tests against Vault, Gitea, FastAPI, NATS, workflows, telemetry, MariaDB, and profile health | yes | fail closed; later stages do not run |
