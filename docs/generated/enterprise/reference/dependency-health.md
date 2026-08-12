---
title: "Dependency Health"
description: "Graphviz dependency-health visualization derived from canonical metadata and promoted evidence."
generated: true
audience: development
page_type: reference
confidence: generated
---

# Dependency Health

<div class="pl-page-lede"><strong>Trace degradation without leaking implementation paths.</strong><p>Domain health and child dependency evidence stay independent. The diagram is rendered as a contained asset; local filesystem prefixes and Markdown renderer directives are never emitted as visible content.</p></div>

<div class="pl-kpi-grid"><div class="pl-kpi"><span>Healthy</span><strong>22</strong><small>dependency observations</small></div><div class="pl-kpi"><span>Unvalidated</span><strong>4</strong><small>dependency observations</small></div></div>

<figure class="pl-generated-diagram pl-generated-diagram--contained"><img src="../../../assets/enterprise/dependency-health-development.svg" alt="Detailed dependency health" loading="lazy"><figcaption>Promoted dependency relationships and evidence authority.</figcaption></figure>

<div class="pl-wide-data">
| Domain | Dependency | State | Evidence authority | Blocking | Root cause |
| --- | --- | --- | --- | --- | --- |
| Apps | Caddy | healthy | verified-runtime-baseline | no | Runtime baseline reports healthy. |
| Apps | FastAPI | healthy | verified-runtime-baseline | yes | Runtime baseline reports online. |
| Apps | NATS/JetStream | healthy | verified-runtime-baseline | yes | Runtime baseline reports ready. |
| Apps | worker | healthy | verified-runtime-baseline | yes | Runtime baseline reports online. |
| Apps | PhotoPrism runtime | healthy | verified-runtime-baseline | no | Runtime baseline reports online. |
| Devices | FastAPI | healthy | verified-runtime-baseline | yes | Runtime baseline reports online. |
| Devices | NATS/JetStream | healthy | verified-runtime-baseline | yes | Runtime baseline reports ready. |
| Devices | node agent | healthy | verified-runtime-baseline | no | Runtime baseline reports online. |
| Devices | agent supervisor | unvalidated | source-derived | no | Dependency is canonical, but no dedicated promoted runtime health signal is available. |
| Devices | Tailscale | healthy | verified-runtime-baseline | no | Runtime baseline reports ready. |
| Home | Caddy | healthy | verified-runtime-baseline | no | Runtime baseline reports healthy. |
| Home | FastAPI | healthy | verified-runtime-baseline | yes | Runtime baseline reports online. |
| Home | NATS/JetStream | healthy | verified-runtime-baseline | yes | Runtime baseline reports ready. |
| Home | worker | healthy | verified-runtime-baseline | yes | Runtime baseline reports online. |
| Home | node agent | healthy | verified-runtime-baseline | no | Runtime baseline reports online. |
| Home | core supervisor | healthy | verified-runtime-baseline | no | Runtime baseline reports online. |
| Backup & Restore | FastAPI | healthy | verified-runtime-baseline | yes | Runtime baseline reports online. |
| Backup & Restore | NATS/JetStream | healthy | verified-runtime-baseline | yes | Runtime baseline reports ready. |
| Backup & Restore | worker | healthy | verified-runtime-baseline | yes | Runtime baseline reports online. |
| Backup & Restore | SQLite | healthy | verified-runtime-baseline | yes | Runtime baseline reports healthy. |
| Backup & Restore | restic | unvalidated | source-derived | no | Dependency is canonical, but no dedicated promoted runtime health signal is available. |
| Security | FastAPI | healthy | verified-runtime-baseline | yes | Runtime baseline reports online. |
| Security | NATS/JetStream | healthy | verified-runtime-baseline | yes | Runtime baseline reports ready. |
| Security | worker | healthy | verified-runtime-baseline | yes | Runtime baseline reports online. |
| Security | Lynis | unvalidated | source-derived | no | Dependency is canonical, but no dedicated promoted runtime health signal is available. |
| Security | Trivy | unvalidated | source-derived | no | Dependency is canonical, but no dedicated promoted runtime health signal is available. |
</div>
