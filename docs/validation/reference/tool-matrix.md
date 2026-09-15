# Security Assurance tool matrix

This matrix is a reviewer-friendly projection of the source file
`security/assurance/tools.yaml`.
The YAML registry, receipts, and run output remain authoritative. All entries
are first-class harness contracts; a lane describes where the fixed command
runs, not a permission for the caller to supply a command.

| Tool ID | Version pin | Lane | Suite membership | Resource | Fixed command ID | Target/input | Receipt/signature |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `pocketlab-security` | runtime-reported | `server_phone_worker` | smoke, standard, deep | heavy | `security.existing_profile` | existing worker Security profile | existing Security receipt |
| `trivy` | runtime-reported | `server_phone_worker` | smoke, standard, deep | heavy | `security.trivy_profile` | existing Security profile | existing Security receipt |
| `lynis` | runtime-reported | `server_phone_worker` | smoke, standard, deep | heavy | `security.lynis_profile` | existing Security profile | existing Security receipt |
| `bandit` | 1.9.4 | `dev_pc_static` | standard, deep | medium | `security.bandit` | fixed runtime source tree | pinned manager receipt |
| `gitleaks` | 8.30.1 | `dev_pc_static` | smoke, standard, deep | medium | `security.gitleaks` | fixed current tree/exclusions | pinned manager receipt |
| `pip-audit` | 2.10.1 | `dev_pc_static` | standard, deep | small | `security.pip_audit` | fixed Python requirements | pinned manager receipt |
| `npm-audit` | 11.13.0 | `dev_pc_static` | standard, deep | medium | `security.npm_audit` | fixed package lock, bounded/offline | package-manager receipt |
| `opa` | runtime-reported | `server_phone_worker` | smoke, standard, deep, adversarial | small | `security.opa` | loopback health/revision/policy | runtime policy receipt |
| `schemathesis` | 4.23.0 | `dev_pc_live_runtime` | standard, deep | heavy | `security.schemathesis` | fixed OpenAPI and safe GET routes | pinned manager receipt |
| `cosign` | 3.1.3 | `dev_pc_static` | standard, deep | small | `security.cosign` | registered artifact only | signature/provenance or N/A |
| `semgrep` | 1.172.0 | `dev_pc_static` | standard, deep | heavy | `security.semgrep` | checked-in curated rules | pinned manager receipt |
| `osv-scanner` | 2.5.0 | `dev_pc_static` | standard, deep | medium | `security.osv_scanner` | fixed lockfiles/SBOM | pinned manager receipt |
| `syft` | 1.50.0 | `dev_pc_static` | deep | heavy | `security.syft` | bounded source, excluded media/cache | pinned manager receipt |
| `grype` | 0.116.1 | `dev_pc_static` | deep | heavy | `security.grype` | managed Syft SBOM only | pinned manager receipt |
| `testssl.sh` | 3.2.2 | `dev_pc_live_runtime` | standard, deep | medium | `security.testssl` | approved Caddy TLS tunnel | pinned manager receipt |
| `nuclei` | 3.8.0 | `dev_pc_live_runtime` | standard, deep | heavy | `security.nuclei` | checked-in safe template allow-list | pinned manager receipt |
| `nmap` | 7.98 | `dev_pc_live_runtime` | standard, deep | medium | `security.nmap` | loopback and fixed Pocket Lab ports | pinned manager receipt |
| `owasp-zap` | 2.17.0 | `dev_pc_live_runtime` | deep | heavy | `security.owasp_zap` | fixed API baseline/routes | pinned manager receipt |

## Contract fields

Every active registry entry also fixes shell behavior, cwd, output bound,
timeout, process-group cleanup, parser, sanitizer, failure classification,
retry safety, resume/checkpoint behavior, maximum attempts, exclusions, and
suite membership. The current registry uses `shell: false`, an approved
repository/managed cwd, `local_server_host_only`, and exclusive scheduling for
heavy tools.

## Installation and checking

Use `[DEV PC]`:

```bash
task lite:security:assurance:tools:install
task lite:security:assurance:tools:check
```

The manager owns `~/.pocketlab-lite/tools/security-assurance` outside Git,
records qualified receipts, rejects unknown downloads, and removes temporary
archives. Do not commit third-party binaries. Phone-native tools are
discovered through the existing worker-owned Security lifecycle; they are not
replaced by a local shell shortcut.

## Target and data restrictions

Static tools operate on the repository's bounded source/lockfile surface.
Runtime tools use only the fixed local Server Phone tunnel and route/port
allow-lists. No tool may scan PhotoPrism media, Android shared storage, backup
payloads, unrelated LAN/Tailnet hosts, the public Internet, or arbitrary
caller-selected URLs. Raw secret matches are replaced with
`[REDACTED BY SECURITY ASSURANCE POLICY]` before persistence.
