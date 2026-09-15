# Security Assurance scenario catalog

This catalog is generated for review from the source file
`security/assurance/scenarios.yaml`.
The YAML file is authoritative for IDs, capability, suite membership, and
mappings.

| Scenario ID | Title | Safety / execution | Capability | Suites | STRIDE | OWASP | AP paths |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `harness-default-off` | Harness default-off and production fail-closed state | PASSIVE / configuration posture | `security.assurance.passive` | smoke, standard, deep | Spoofing; Elevation of Privilege | A07; A01 | AP-01; AP-02; AP-03 |
| `harness-auth-boundary` | Synthetic Ed25519 session and capability boundary | SAFE_ACTIVE / authenticated admission posture | `security.assurance.runtime` | smoke, standard, deep, adversarial | Spoofing; Tampering; Elevation of Privilege | A07; A01 | AP-01; AP-02; AP-03; AP-04; AP-09; AP-10 |
| `caddy-proof-strip` | Caddy never forwards qualification proof into FastAPI authority | SAFE_ACTIVE / fixed Caddy probe | `security.assurance.api` | smoke, standard, deep, adversarial | Spoofing; Tampering; Elevation of Privilege | A07; A01 | AP-01; AP-02; AP-07; AP-09 |
| `runtime-readiness` | API health/readiness and PM2 readiness distinction | PASSIVE / fixed local health probe | `security.assurance.runtime` | smoke, standard, deep, adversarial | Denial of Service | — | AP-07; AP-11; AP-12 |
| `control-plane-ownership` | Assurance execution remains FastAPI to NATS to worker owned | PASSIVE / worker execution receipt | `security.assurance.runtime` | smoke, standard, deep | Tampering; Repudiation; Elevation of Privilege | A01; A08; A09 | AP-01; AP-02; AP-04; AP-06 |
| `evidence-redaction` | Assurance evidence contains only normalized sanitized output | PASSIVE / redaction contract | `security.assurance.passive` | smoke, standard, deep, adversarial | Repudiation; Information Disclosure; Tampering | A02; A05; A08; A09 | AP-05; AP-06; AP-08 |
| `security-projection` | Existing Security projection and scanner lifecycle are available | PASSIVE / existing Security projection | `security.assurance.sca` | smoke, standard, deep | Tampering; Repudiation; Denial of Service | A06; A08; A09 | AP-04; AP-05; AP-06; AP-08 |
| `policy-readiness` | OPA loopback readiness and policy revision consistency | PASSIVE / existing OPA status | `security.assurance.runtime` | standard, deep | Tampering; Denial of Service; Elevation of Privilege | A01; A08 | AP-11; AP-12; AP-14 |
| `source-boundaries` | Canonical source preserves browser, shell, NATS, and user-media boundaries | PASSIVE / fixed source assertions | `security.assurance.sast` | standard, deep, adversarial | Tampering; Information Disclosure; Elevation of Privilege | A01; A02; A05; A08 | AP-01; AP-02; AP-04; AP-05; AP-07 |
| `adversarial-negative-auth-probes` | Fixed malformed authentication and input probes remain denied | SAFE_ACTIVE / fixed negative auth probes | `security.assurance.api` | adversarial | Spoofing; Tampering; Elevation of Privilege | A01; A03; A07 | AP-01; AP-02; AP-03; AP-04; AP-09; AP-10 |
| `threat-model-integrity` | Current canonical threat model is complete and executable statuses are explicit | PASSIVE / threat-model integrity | `security.assurance.threat_scenario` | smoke, standard, deep | Tampering; Repudiation | A08; A09 | AP-01 through AP-14 |
| `attack-path-inventory` | Every current AP path has a bounded execution classification | PASSIVE / attack-path inventory | `security.assurance.threat_scenario` | standard, deep | all STRIDE categories | A01; A02; A07; A08; A09 | AP-01 through AP-14 |

## Execution rules

The caller selects a registered suite or one registered scenario through the
supported CLI/API. It cannot supply a shell command, argv, target, URL, port,
NATS subject, ruleset, template, or environment. A scenario result is
independent from the aggregate suite result; an infrastructure prerequisite
can make the run `BLOCKED` without creating a vulnerability finding.

The threat model contains 14 AP paths. Paths marked human review or static
evidence in the [STRIDE/OWASP playbook](../security-assurance/13-stride-owasp-attack-paths.md)
remain visible and are not silently treated as runtime PASS.
