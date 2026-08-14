---
title: "Modeled Attack Paths"
description: "Reviewed static attack-path scenarios and semantic deep links."
generated: true
audience: production
page_type: reference
confidence: generated
---

# Modeled attack paths

<nav class="pl-threat-subnav" aria-label="Threat Model sections"><a class="pl-intent-link" href="../">Overview</a><a class="pl-intent-link" href="../architecture/">Architecture &amp; trust zones</a><a class="pl-intent-link" href="../stride/">STRIDE</a><a class="pl-intent-link" href="../attack-paths/">Attack paths</a><a class="pl-intent-link" href="../controls/">Controls</a><a class="pl-intent-link" href="../assets-guardrails/">Assets &amp; guardrails</a><a class="pl-intent-link" href="../evidence/">Evidence &amp; provenance</a><a class="pl-intent-link" href="../catalog/">Security Atlas catalog</a></nav>

<div class="pl-page-lede"><strong>Trace reviewed scenarios through the saved architecture.</strong><p>Attack paths are modeled review paths, never confirmed exploits or live detections. Use semantic links to open the exact path in the Security Atlas.</p></div>

<div class="pl-threat-path-grid"><a class="pl-threat-path-card pl-intent-link" href="../catalog/?atlas-attack-path=AP-01#security-atlas"><span class="pl-card-kicker">AP-01</span><strong>Browser control-plane bypass</strong><small>Spoofing · Tampering · Elevation of Privilege</small><p>browser → nats-jetstream → worker</p></a><a class="pl-threat-path-card pl-intent-link" href="../catalog/?atlas-attack-path=AP-02#security-atlas"><span class="pl-card-kicker">AP-02</span><strong>Browser shell execution</strong><small>Tampering · Elevation of Privilege</small><p>browser → lite-api → server-host</p></a><a class="pl-threat-path-card pl-intent-link" href="../catalog/?atlas-attack-path=AP-03#security-atlas"><span class="pl-card-kicker">AP-03</span><strong>Forged managed-device identity</strong><small>Spoofing · Tampering · Elevation of Privilege</small><p>managed-device → lite-api → nats-jetstream → node-agent</p></a><a class="pl-threat-path-card pl-intent-link" href="../catalog/?atlas-attack-path=AP-04#security-atlas"><span class="pl-card-kicker">AP-04</span><strong>Messaging command tampering or replay</strong><small>Tampering · Repudiation · Denial of Service</small><p>lite-api → nats-jetstream → worker → node-agent</p></a><a class="pl-threat-path-card pl-intent-link" href="../catalog/?atlas-attack-path=AP-05#security-atlas"><span class="pl-card-kicker">AP-05</span><strong>Supply-chain artifact compromise</strong><small>Tampering · Information Disclosure · Elevation of Privilege</small><p>github-release → release-artifacts → server-host</p></a><a class="pl-threat-path-card pl-intent-link" href="../catalog/?atlas-attack-path=AP-06#security-atlas"><span class="pl-card-kicker">AP-06</span><strong>Evidence poisoning</strong><small>Tampering · Repudiation · Information Disclosure</small><p>scanner-evidence → promoted-evidence → documentation</p></a><a class="pl-threat-path-card pl-intent-link" href="../catalog/?atlas-attack-path=AP-07#security-atlas"><span class="pl-card-kicker">AP-07</span><strong>Tailnet/private-network exposure</strong><small>Spoofing · Information Disclosure · Denial of Service</small><p>private-network → tailscale → caddy → lite-api</p></a><a class="pl-threat-path-card pl-intent-link" href="../catalog/?atlas-attack-path=AP-08#security-atlas"><span class="pl-card-kicker">AP-08</span><strong>Recovery state tampering</strong><small>Tampering · Repudiation · Denial of Service</small><p>sqlite → recovery-state → lite-api</p></a></div>

## Review table

| Path | Entry | Target | STRIDE | Controls | Consequences | Review |
| --- | --- | --- | --- | --- | --- | --- |
| AP-01 | browser | nats-jetstream | Spoofing, Tampering, Elevation of Privilege | CTRL-BROWSER-NATS, CTRL-API-CONTROL | unauthorized command injection, control-plane bypass, loss of expected audit/control ownership | human-review-required |
| AP-02 | browser | server-host | Tampering, Elevation of Privilege | CTRL-BROWSER-SHELL, CTRL-API-CONTROL | host mutation, secret exposure, runtime integrity loss | human-review-required |
| AP-03 | managed-device | node-agent | Spoofing, Tampering, Elevation of Privilege | CTRL-API-CONTROL, CTRL-EXECUTION-OWNERS | unauthorized device enrollment, command execution under a forged identity, audit attribution failure | human-review-required |
| AP-04 | lite-api | node-agent | Tampering, Repudiation, Denial of Service | CTRL-API-CONTROL, CTRL-EXECUTION-OWNERS | incorrect or repeated device commands, loss of command integrity, device availability impact | human-review-required |
| AP-05 | github-release | server-host | Tampering, Information Disclosure, Elevation of Privilege | CTRL-SUPPLY-CHAIN, CTRL-EXPLICIT-PROMOTION, CTRL-EVIDENCE-SANITIZE | compromised release execution, dependency or artifact integrity loss, misleading release posture | human-review-required |
| AP-06 | scanner-evidence | documentation | Tampering, Repudiation, Information Disclosure | CTRL-EVIDENCE-SANITIZE, CTRL-EXPLICIT-PROMOTION | incorrect security posture, secret or private-path disclosure, loss of evidence trust | human-review-required |
| AP-07 | private-network | lite-api | Spoofing, Information Disclosure, Denial of Service | CTRL-API-CONTROL, CTRL-EXECUTION-OWNERS | unexpected control-plane reachability, service exposure, availability impact | human-review-required |
| AP-08 | sqlite | recovery-state | Tampering, Repudiation, Denial of Service | CTRL-EVIDENCE-SANITIZE, CTRL-EXPLICIT-PROMOTION, CTRL-API-CONTROL | unsafe restore decisions, loss of recovery evidence integrity, recovery unavailability | human-review-required |
