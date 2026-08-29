---
title: "Dependency health"
description: "Why each domain is healthy, degraded, or still unvalidated."
generated: true
audience: development
confidence: release-promoted
---

# Service and dependency health

Operational health and dependency evidence remain independent: a healthy domain does not silently mark every dependency healthy.

<figure class="pl-generated-diagram pl-generated-diagram--contained"><img src="../../../assets/enterprise/dependency-health-development.svg" alt="Generated dependency health graph" loading="lazy"><figcaption>Promoted dependency-state relationships; source paths and renderer directives are never shown as page content.</figcaption></figure>

## Apps

<div class="pl-status-strip" role="group" aria-label="Current evidence status">
<div><span>Health</span><span class="pl-intel-status pl-intel-status--healthy"><span aria-hidden="true">●</span> healthy</span></div>
<div><span>Parity</span><span class="pl-intel-status pl-intel-status--drift-detected"><span aria-hidden="true">○</span> drift-detected</span></div>
<div><span>Evidence</span><span class="pl-intel-status pl-intel-status--verified"><span aria-hidden="true">✓</span> verified</span></div>
<div><span>Freshness</span><span class="pl-intel-status pl-intel-status--verified"><span aria-hidden="true">✓</span> verified</span></div>
</div>

| Dependency | State | Evidence | Why |
| --- | --- | --- | --- |
| Caddy | healthy | verified-runtime-baseline | Runtime baseline reports healthy. |
| FastAPI | healthy | verified-runtime-baseline | Runtime baseline reports online. |
| NATS/JetStream | healthy | verified-runtime-baseline | Runtime baseline reports ready. |
| worker | healthy | verified-runtime-baseline | Runtime baseline reports online. |
| PhotoPrism runtime | healthy | verified-runtime-baseline | Runtime baseline reports online. |

## Devices

<div class="pl-status-strip" role="group" aria-label="Current evidence status">
<div><span>Health</span><span class="pl-intel-status pl-intel-status--healthy"><span aria-hidden="true">●</span> healthy</span></div>
<div><span>Parity</span><span class="pl-intel-status pl-intel-status--verified"><span aria-hidden="true">✓</span> verified</span></div>
<div><span>Evidence</span><span class="pl-intel-status pl-intel-status--verified"><span aria-hidden="true">✓</span> verified</span></div>
<div><span>Freshness</span><span class="pl-intel-status pl-intel-status--verified"><span aria-hidden="true">✓</span> verified</span></div>
</div>

| Dependency | State | Evidence | Why |
| --- | --- | --- | --- |
| FastAPI | healthy | verified-runtime-baseline | Runtime baseline reports online. |
| NATS/JetStream | healthy | verified-runtime-baseline | Runtime baseline reports ready. |
| node agent | healthy | verified-runtime-baseline | Runtime baseline reports online. |
| agent supervisor | unvalidated | source-derived | Dependency is canonical, but no dedicated promoted runtime health signal is available. |
| Tailscale | healthy | verified-runtime-baseline | Runtime baseline reports ready. |

## Home

<div class="pl-status-strip" role="group" aria-label="Current evidence status">
<div><span>Health</span><span class="pl-intel-status pl-intel-status--degraded"><span aria-hidden="true">▲</span> degraded</span></div>
<div><span>Parity</span><span class="pl-intel-status pl-intel-status--verified"><span aria-hidden="true">✓</span> verified</span></div>
<div><span>Evidence</span><span class="pl-intel-status pl-intel-status--verified"><span aria-hidden="true">✓</span> verified</span></div>
<div><span>Freshness</span><span class="pl-intel-status pl-intel-status--verified"><span aria-hidden="true">✓</span> verified</span></div>
</div>

**Current reason:** `read_degraded`

| Dependency | State | Evidence | Why |
| --- | --- | --- | --- |
| Caddy | healthy | verified-runtime-baseline | Runtime baseline reports healthy. |
| FastAPI | healthy | verified-runtime-baseline | Runtime baseline reports online. |
| NATS/JetStream | healthy | verified-runtime-baseline | Runtime baseline reports ready. |
| worker | healthy | verified-runtime-baseline | Runtime baseline reports online. |
| node agent | healthy | verified-runtime-baseline | Runtime baseline reports online. |
| core supervisor | healthy | verified-runtime-baseline | Runtime baseline reports online. |

## Identity & Access

<div class="pl-status-strip" role="group" aria-label="Current evidence status">
<div><span>Health</span><span class="pl-intel-status pl-intel-status--unvalidated"><span aria-hidden="true">○</span> unvalidated</span></div>
<div><span>Parity</span><span class="pl-intel-status pl-intel-status--partial"><span aria-hidden="true">◐</span> partial</span></div>
<div><span>Evidence</span><span class="pl-intel-status pl-intel-status--verified"><span aria-hidden="true">✓</span> verified</span></div>
<div><span>Freshness</span><span class="pl-intel-status pl-intel-status--verified"><span aria-hidden="true">✓</span> verified</span></div>
</div>

| Dependency | State | Evidence | Why |
| --- | --- | --- | --- |
| FastAPI | healthy | verified-runtime-baseline | Runtime baseline reports online. |
| SQLite | healthy | verified-runtime-baseline | Runtime baseline reports healthy. |
| WebAuthn assurance | unvalidated | source-derived | Dependency is canonical, but no dedicated promoted runtime health signal is available. |
| Enterprise membership controls | unvalidated | source-derived | Dependency is canonical, but no dedicated promoted runtime health signal is available. |

## Backup & Restore

<div class="pl-status-strip" role="group" aria-label="Current evidence status">
<div><span>Health</span><span class="pl-intel-status pl-intel-status--degraded"><span aria-hidden="true">▲</span> degraded</span></div>
<div><span>Parity</span><span class="pl-intel-status pl-intel-status--drift-detected"><span aria-hidden="true">○</span> drift-detected</span></div>
<div><span>Evidence</span><span class="pl-intel-status pl-intel-status--verified"><span aria-hidden="true">✓</span> verified</span></div>
<div><span>Freshness</span><span class="pl-intel-status pl-intel-status--stale"><span aria-hidden="true">◷</span> stale</span></div>
</div>

**Current reason:** `projection_too_old`

| Dependency | State | Evidence | Why |
| --- | --- | --- | --- |
| FastAPI | healthy | verified-runtime-baseline | Runtime baseline reports online. |
| NATS/JetStream | healthy | verified-runtime-baseline | Runtime baseline reports ready. |
| worker | healthy | verified-runtime-baseline | Runtime baseline reports online. |
| SQLite | healthy | verified-runtime-baseline | Runtime baseline reports healthy. |
| restic | unvalidated | source-derived | Dependency is canonical, but no dedicated promoted runtime health signal is available. |

## Rules

<div class="pl-status-strip" role="group" aria-label="Current evidence status">
<div><span>Health</span><span class="pl-intel-status pl-intel-status--unvalidated"><span aria-hidden="true">○</span> unvalidated</span></div>
<div><span>Parity</span><span class="pl-intel-status pl-intel-status--partial"><span aria-hidden="true">◐</span> partial</span></div>
<div><span>Evidence</span><span class="pl-intel-status pl-intel-status--verified"><span aria-hidden="true">✓</span> verified</span></div>
<div><span>Freshness</span><span class="pl-intel-status pl-intel-status--verified"><span aria-hidden="true">✓</span> verified</span></div>
</div>

| Dependency | State | Evidence | Why |
| --- | --- | --- | --- |
| FastAPI | healthy | verified-runtime-baseline | Runtime baseline reports online. |
| SQLite | healthy | verified-runtime-baseline | Runtime baseline reports healthy. |
| OPA policy engine | unvalidated | source-derived | Dependency is canonical, but no dedicated promoted runtime health signal is available. |
| Policy lifecycle | unvalidated | source-derived | Dependency is canonical, but no dedicated promoted runtime health signal is available. |
| Independent approvals | unvalidated | source-derived | Dependency is canonical, but no dedicated promoted runtime health signal is available. |
| Temporary exceptions | unvalidated | source-derived | Dependency is canonical, but no dedicated promoted runtime health signal is available. |

## Security

<div class="pl-status-strip" role="group" aria-label="Current evidence status">
<div><span>Health</span><span class="pl-intel-status pl-intel-status--healthy"><span aria-hidden="true">●</span> healthy</span></div>
<div><span>Parity</span><span class="pl-intel-status pl-intel-status--verified"><span aria-hidden="true">✓</span> verified</span></div>
<div><span>Evidence</span><span class="pl-intel-status pl-intel-status--verified"><span aria-hidden="true">✓</span> verified</span></div>
<div><span>Freshness</span><span class="pl-intel-status pl-intel-status--verified"><span aria-hidden="true">✓</span> verified</span></div>
</div>

| Dependency | State | Evidence | Why |
| --- | --- | --- | --- |
| FastAPI | healthy | verified-runtime-baseline | Runtime baseline reports online. |
| NATS/JetStream | healthy | verified-runtime-baseline | Runtime baseline reports ready. |
| worker | healthy | verified-runtime-baseline | Runtime baseline reports online. |
| Lynis | unvalidated | source-derived | Dependency is canonical, but no dedicated promoted runtime health signal is available. |
| Trivy | unvalidated | source-derived | Dependency is canonical, but no dedicated promoted runtime health signal is available. |
