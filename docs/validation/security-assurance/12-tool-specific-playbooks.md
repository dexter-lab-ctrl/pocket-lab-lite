# 12. Tool-specific playbooks

The registry is authoritative for every command contract. The entries below
describe the security question, lane, target, and limitations without exposing
raw scanner output or permitting caller-selected arguments. Exact receipt and
version evidence belongs in the run report.

| Tool | Security question | Lane / suite | Fixed target or input | Normalized output and limits |
| --- | --- | --- | --- | --- |
| `pocketlab-security` | Does the existing Quick/Full Security lifecycle execute and persist safe evidence? | `server_phone_worker`; Smoke, Standard, Deep | existing worker-owned local Security profile | existing projection, cache/SBOM/fusion; no local CLI shortcut |
| `trivy` | Are bounded runtime vulnerabilities, misconfiguration, secrets-mode, and SBOM checks safe? | `server_phone_worker`; Smoke, Standard, Deep | existing Security profile | existing sanitized projection; reuse cache/SBOM; no user media |
| `lynis` | What host posture signals are relevant on the phone? | `server_phone_worker`; Smoke, Standard, Deep | existing worker-owned profile | sanitized posture summary; Android/Termux limitations remain visible |
| `opa` | Is the local policy ready, current, and fail-closed? | `server_phone_worker`; all suites | loopback policy service | fixed health/revision/policy status; unavailable is denial |
| `bandit` | Are Python runtime source patterns risky? | `dev_pc_static`; Standard, Deep | `pocket-lab-final-structure/runtime` | JSON findings with bounded/redacted paths; candidate warnings require triage |
| `gitleaks` | Does the current tree contain secret-like material? | `dev_pc_static`; Smoke, Standard, Deep | repository tree with exclusions | rule/path/line metadata only; raw matches are redacted |
| `pip-audit` | Do pinned Python requirements have known advisories? | `dev_pc_static`; Standard, Deep | runtime `requirements.txt` | package/advisory identity; corroborate, do not duplicate |
| `npm-audit` | Does the production package lock have known advisories? | `dev_pc_static`; Standard, Deep | package lock, offline mode | dependency-only JSON; no reproducible network refresh |
| `semgrep` | Do curated Pocket Lab boundary rules hold? | `dev_pc_static`; Standard, Deep | checked-in `security/assurance/semgrep-rules.yml` | redacted static findings; fixed rules only |
| `osv-scanner` | Do repository lockfiles corroborate dependency advisories? | `dev_pc_static`; Standard, Deep | fixed dependency manifests | normalized package/advisory key; source path bounded |
| `syft` | What is the bounded source SBOM identity? | `dev_pc_static`; Deep | repository excluding generated/cache paths | CycloneDX summary; feeds only managed Grype step |
| `grype` | Do managed SBOM components have known advisories? | `dev_pc_static`; Deep | managed Syft SBOM only | normalized package/advisory key; never an arbitrary directory scan |
| `cosign` | Is a registered Pocket Lab artifact signed/provenanced? | `dev_pc_static`; Standard, Deep | registered artifact metadata only | bounded verification or `NOT_APPLICABLE`; no signing/download |
| `schemathesis` | Do safe OpenAPI GET routes reject malformed/invalid input correctly? | `dev_pc_live_runtime`; Standard, Deep | fixed schema and approved phone tunnel | bounded examples, one worker, safe route allowlist |
| `testssl.sh` | Is the registered Caddy TLS posture acceptable? | `dev_pc_live_runtime`; Standard, Deep | fixed Caddy tunnel/SNI | TLS summary; no arbitrary host or port |
| `nuclei` | Are safe headers/exposure/debug checks clean? | `dev_pc_live_runtime`; Standard, Deep | checked-in `security/assurance/nuclei-safe-templates` | template ID/hash and redacted HTTP finding; no exploit templates |
| `nmap` | Are only expected Pocket Lab listeners exposed? | `dev_pc_live_runtime`; Standard, Deep | fixed loopback target and owned ports | fixed listener summary; no LAN/Tailnet/public scan |
| `owasp-zap` | Does a bounded API baseline reveal safe HTTP issues? | `dev_pc_live_runtime`; Deep only | fixed API endpoint/route profile | redacted alert summary; no active destructive rules, spidering, or credential attacks |

## Commands and retest

**[DEV PC]** Use the fixed manager rather than calling a tool directly:

```bash
task lite:security:assurance:tools:check
task lite:security:assurance:tools:run SUITE=standard
task lite:security:assurance:tools:run SUITE=deep
```

For a phone-native tool, use the registered assurance suite; its output will
identify the existing Security profile and worker correlation. For any finding,
follow [14 — findings and remediation](14-findings-remediation.md) and rerun
the narrowest affected suite/tool after publishing a new exact SHA.

## Common limitations

Static SAST/SCA is not runtime exploit proof. A tool may be unavailable on
Termux while still be first-class in the DEV-PC lane. A runtime lane may be
DEV-PC → actual Server Phone, not phone-native. A `NOT_APPLICABLE` Cosign result
means no signed artifact is registered, not that signature verification was
skipped silently. All limitations must remain visible in the report.

## Consolidated 360-degree runtime tool lanes

The registry below extends the existing detailed playbooks. Exact command,
target, timeout, parser and sanitizer contracts remain authoritative in
`security/assurance/tools.yaml`.

| Tool | Lane | Suites | Fixed target |
| --- | --- | --- | --- |
| `pocketlab-runtime-360` | `dev_pc_live_runtime` | standard, deep, adversarial | `fixed_server_phone_runtime_tunnels` |
| `playwright-runtime` | `dev_pc_live_runtime` | standard, deep, adversarial | `fixed_caddy_browser_runtime` |
| `playwright` | `dev_pc_live_runtime` | standard, deep, adversarial | `approved_server_phone_caddy_tls_tunnel` |
| `mitmdump` | `dev_pc_live_runtime` | standard, deep, adversarial | `approved_server_phone_api_tunnel` |
| `hurl` | `dev_pc_live_runtime` | standard, deep, adversarial | `approved_server_phone_caddy_tls_tunnel` |
| `k6` | `dev_pc_live_runtime` | deep, adversarial | `approved_server_phone_caddy_tls_tunnel` |
| `websocat` | `dev_pc_live_runtime` | standard, deep, adversarial | `approved_server_phone_api_tunnel` |
| `katana` | `dev_pc_live_runtime` | deep, adversarial | `approved_server_phone_caddy_tls_tunnel` |
| `httpx` | `dev_pc_live_runtime` | standard, deep, adversarial | `approved_server_phone_api_tunnel` |
| `tlsx` | `dev_pc_live_runtime` | standard, deep, adversarial | `approved_server_phone_caddy_tls_tunnel` |
| `tshark` | `dev_pc_live_runtime` | standard, deep, adversarial | `approved_loopback_listener_set` |
| `ffuf` | `dev_pc_live_runtime` | deep, adversarial | `approved_server_phone_caddy_tls_tunnel` |
| `nats-cli` | `dev_pc_live_runtime` | deep, adversarial | `approved_loopback_listener_set` |

These additions do not create a generic command runner. Server Phone is a
consumer/qualification target, never the development workspace.
