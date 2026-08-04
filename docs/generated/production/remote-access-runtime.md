---
title: "Remote access runtime verification"
description: "Sanitized Tailscale, Caddy, NATS, and app-route runtime evidence."
audience: production
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

# Remote access runtime verification

**Current classification:** Promoted runtime verified.

| Route | Presence | HTTPS owner | HTTPS mode | Order | Upstream kind | Peer reachability |
| --- | --- | --- | --- | --- | --- | --- |
| api-lite | present | caddy | explicit-files | api-before-pwa | loopback-fastapi | not-applicable |
| managed-app | present | caddy | explicit-files | api-before-pwa | loopback-app | not-applicable |
| pwa | present | caddy | explicit-files | api-before-pwa | static-assets | not-applicable |
| remote-access | present | caddy | explicit-files | not-applicable | private-network | ready |

| Runtime check | Classification |
| --- | --- |
| Tailscale command variant | tailscale-cli |
| Daemon running | True |
| Tailnet IPv4 ready | True |
| Private connectivity ready | True |
| Peer reachability | ready |
| NATS listener | present |
| NATS bind scope | private-or-all |
| JetStream | enabled |

Remote access evidence stores readiness classifications only. It never stores a Tailscale IP, LAN IP, FQDN, Tailnet name, peer name, login, node key, control URL, certificate path, or certificate content.

When evidence is unavailable, the product and documentation use **Remote access not ready** or **runtime evidence unavailable** rather than inferring that Tailscale, Caddy, or the managed app is absent from the canonical architecture.
