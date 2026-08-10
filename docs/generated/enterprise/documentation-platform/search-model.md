---
title: "Documentation search model"
description: "Generated deterministic search synonyms and destinations."
generated: true
audience: development
page_type: reference
confidence: generated
---

# Search model

| Canonical query | Synonyms | Destinations |
| --- | --- | --- |
| backup stale | old backup, recovery freshness | /generated/production/recovery/, /generated/production/intelligence/recovery-readiness/ |
| device offline | agent unreachable, fleet problem, node disconnected | /generated/production/devices/, /generated/production/intelligence/fleet-readiness/, /generated/production/troubleshooting/ |
| devices | agent, fleet, node, offline | /generated/production/devices/, /generated/production/intelligence/fleet-readiness/ |
| operational-health | degraded, health, stale, unavailable | /generated/production/intelligence/current-health/, /generated/development/knowledge/operational-health/ |
| recovery | backup, restore, restore readiness | /generated/production/recovery/, /generated/production/intelligence/recovery-readiness/ |
| release mismatch | installed release mismatch, runtime release drift | /generated/production/release/, /generated/production/intelligence/what-changed/ |
| release-impact | change impact, release delta, what changed | /generated/production/intelligence/what-changed/ |
| remote access not ready | tailnet problem, tailscale unavailable | /generated/production/remote-access/, /generated/production/troubleshooting/ |
| remote-access | remote access not ready, tailnet, tailscale | /generated/production/remote-access/ |
| security | lynis, safety, safety check, trivy | /generated/production/security/ |
| security check stuck | scan stuck, worker safety check | /generated/production/security/, /generated/production/troubleshooting/ |
