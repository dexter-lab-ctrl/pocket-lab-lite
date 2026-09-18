# Security Assurance tool matrix

This matrix is a reviewer-friendly projection of the authoritative
`security/assurance/tools.yaml` registry. Registered commands, targets,
arguments, parsers, sanitizers, bounds and suite membership remain
source-owned and caller input cannot broaden them.

| Tool ID | Version pin | Lane | Suites | Resource | Command ID | Fixed target | Installation/provenance |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `pocketlab-security` | runtime-reported | `server_phone_worker` | smoke, standard, deep | heavy | `security.existing_profile` | `server_runtime_local` | existing_pocketlab_security_worker |
| `trivy` | runtime-reported | `server_phone_worker` | smoke, standard, deep | heavy | `security.trivy_profile` | `server_runtime_local` | existing_pocketlab_security_worker |
| `lynis` | runtime-reported | `server_phone_worker` | smoke, standard, deep | heavy | `security.lynis_profile` | `server_runtime_local` | existing_pocketlab_security_worker |
| `bandit` | 1.9.4 | `dev_pc_static` | standard, deep | medium | `source.bandit_runtime` | `repository_runtime_source` | python_venv_or_pypi_receipt |
| `gitleaks` | 8.30.1 | `dev_pc_static` | smoke, standard, deep | medium | `source.gitleaks_current_tree` | `repository_current_tree` | official_github_release_receipt |
| `pip-audit` | 2.10.1 | `dev_pc_static` | standard, deep | small | `dependency.pip_audit` | `repository_python_requirements` | python_venv_or_pypi_receipt |
| `npm-audit` | 11.13.0 | `dev_pc_static` | standard, deep | medium | `dependency.npm_audit_offline` | `repository_package_lock` | approved_node_toolchain |
| `opa` | runtime-reported | `server_phone_worker` | smoke, standard, deep, adversarial | small | `policy.health_revision` | `loopback_opa_service` | existing_loopback_policy_service |
| `schemathesis` | 4.23.0 | `dev_pc_live_runtime` | standard, deep, adversarial | heavy | `runtime.schemathesis_safe_get` | `approved_server_phone_api_tunnel` | approved_parity_python_venv |
| `cosign` | 3.1.3 | `dev_pc_static` | standard, deep | small | `supply_chain.cosign_registered_artifact` | `registered_signed_artifact` | official_github_release_receipt |
| `semgrep` | 1.172.0 | `dev_pc_static` | standard, deep | heavy | `source.semgrep_boundary_rules` | `repository_source_boundary` | official_pypi_wheelhouse_receipt |
| `osv-scanner` | 2.5.0 | `dev_pc_static` | standard, deep | medium | `dependency.osv_lockfiles` | `repository_lockfiles` | official_github_release_receipt |
| `syft` | 1.50.0 | `dev_pc_static` | deep | heavy | `supply_chain.syft_cyclonedx` | `repository_source_excluding_generated_caches` | official_github_release_receipt |
| `grype` | 0.116.1 | `dev_pc_static` | deep | heavy | `supply_chain.grype_sbom` | `managed_syft_sbom` | official_github_release_receipt |
| `testssl.sh` | 3.2.2 | `dev_pc_live_runtime` | standard, deep, adversarial | medium | `runtime.testssl_caddy` | `approved_server_phone_caddy_tls_tunnel` | official_testssl_release_receipt |
| `nuclei` | 3.8.0 | `dev_pc_live_runtime` | standard, deep, adversarial | heavy | `runtime.nuclei_safe_templates` | `approved_server_phone_api_tunnel` | official_nuclei_release_receipt |
| `nmap` | 7.98 | `dev_pc_live_runtime` | standard, deep, adversarial | medium | `runtime.nmap_owned_ports` | `approved_loopback_listener_set` | approved_os_package_or_release_receipt |
| `owasp-zap` | 2.17.0 | `dev_pc_live_runtime` | deep, adversarial | heavy | `runtime.zap_api_baseline` | `approved_server_phone_api_tunnel` | official_zap_release_receipt |
| `pocketlab-runtime-360` | 1.0.0 | `dev_pc_live_runtime` | standard, deep, adversarial | medium | `runtime.pocketlab_360` | `fixed_server_phone_runtime_tunnels` | repository_development_venv |
| `playwright-runtime` | 1.0.0 | `dev_pc_live_runtime` | standard, deep, adversarial | medium | `runtime.playwright_browser` | `fixed_caddy_browser_runtime` | repository_node_dependencies |
| `playwright` | runtime-discovered | `dev_pc_live_runtime` | standard, deep, adversarial | heavy | `runtime.playwright_security` | `approved_server_phone_caddy_tls_tunnel` | approved_existing_dev_pc_toolchain |
| `mitmdump` | runtime-discovered | `dev_pc_live_runtime` | standard, deep, adversarial | medium | `runtime.mitmdump_fixed_proxy` | `approved_server_phone_api_tunnel` | approved_existing_dev_pc_toolchain |
| `hurl` | runtime-discovered | `dev_pc_live_runtime` | standard, deep, adversarial | medium | `runtime.hurl_security_sequences` | `approved_server_phone_caddy_tls_tunnel` | approved_existing_dev_pc_toolchain |
| `k6` | runtime-discovered | `dev_pc_live_runtime` | deep, adversarial | heavy | `runtime.k6_bounded_resilience` | `approved_server_phone_caddy_tls_tunnel` | approved_existing_dev_pc_toolchain |
| `websocat` | runtime-discovered | `dev_pc_live_runtime` | standard, deep, adversarial | small | `runtime.websocat_auth_boundary` | `approved_server_phone_api_tunnel` | approved_existing_dev_pc_toolchain |
| `katana` | runtime-discovered | `dev_pc_live_runtime` | deep, adversarial | medium | `runtime.katana_route_inventory` | `approved_server_phone_caddy_tls_tunnel` | approved_existing_dev_pc_toolchain |
| `httpx` | runtime-discovered | `dev_pc_live_runtime` | standard, deep, adversarial | small | `runtime.httpx_exposure` | `approved_server_phone_api_tunnel` | approved_existing_dev_pc_toolchain |
| `tlsx` | runtime-discovered | `dev_pc_live_runtime` | standard, deep, adversarial | small | `runtime.tlsx_identity` | `approved_server_phone_caddy_tls_tunnel` | approved_existing_dev_pc_toolchain |
| `tshark` | runtime-discovered | `dev_pc_live_runtime` | standard, deep, adversarial | medium | `runtime.tshark_observer` | `approved_loopback_listener_set` | approved_existing_dev_pc_toolchain |
| `ffuf` | runtime-discovered | `dev_pc_live_runtime` | deep, adversarial | medium | `runtime.ffuf_tiny_wordlist` | `approved_server_phone_caddy_tls_tunnel` | approved_existing_dev_pc_toolchain |
| `nats-cli` | runtime-discovered | `dev_pc_live_runtime` | deep, adversarial | small | `runtime.nats_fixed_observer` | `approved_loopback_listener_set` | approved_existing_dev_pc_toolchain |

## Safety contract

Runtime tools remain restricted to repository-owned fixed DEV-PC tunnels,
registered Server Phone worker/harness controls and the operator-approved Caddy TLS identity.
`pocketlab-runtime-360` and `playwright-runtime` are repository-owned adapters and are not promoted as third-party scanner binaries.

```bash
task lite:security:assurance:tools:install
task lite:security:assurance:tools:check
```

No registered tool accepts an arbitrary caller-selected command, target, URL, host, port, NATS subject, wordlist, ruleset, scanner option or environment.
Raw credentials, cookies, authorization values, secret matches and user media must not be persisted in normalized evidence.
