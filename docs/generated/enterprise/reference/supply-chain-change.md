---
title: "Supply-chain Change Intelligence"
description: "Current promoted supply-chain snapshot, tool coverage, repository posture, baseline readiness and verified release-to-release deltas."
generated: true
audience: development
page_type: reference
confidence: generated
---

# Supply-chain Change Intelligence

Current promoted evidence and historical change are intentionally separate authorities. This page never reads transient scanner output and never fabricates an N-1 delta.

## Current promoted snapshot

| Signal | Value |
| --- | --- |
| Capture status | complete |
| Run ID | local-20260829T193652Z-2392471 |
| Source commit | 9cf5e2fcff9179d3c97199ff04f48c0031375e67 |
| Qualification surface | local-or-ci-diagnostic |
| Development SBOM components | 2379 |
| Release SBOM components | 0 |
| Runtime SBOM components | 0 |
| Vulnerability evidence | observed (622 normalized findings) |
| Package-license coverage | observed via syft+trivy |
| Package rows | 2379 |
| Trivy license rows | 26 |
| Deep source-license coverage | not-run |
| Gitleaks findings | 7068 |
| Semgrep findings | 0 |
| Scorecard posture | observed-with-provider-limitations |

### Tool coverage

| Step | Status | Exit | Duration (s) |
| --- | --- | --- | --- |
| gitleaks-release | completed | 0 | 0.724 |
| gitleaks-worktree | findings-or-tool-nonzero | 1 | 472.482 |
| grype-sbom-dev | completed | 0 | 84.639 |
| osv-sbom-dev | findings-or-tool-nonzero | 1 | 4.33 |
| osv-source | findings-or-tool-nonzero | 1 | 28.184 |
| scorecard | completed | 0 | 7.538 |
| semgrep | completed | 0 | 20.575 |
| syft-dev | completed | 0 | 327.535 |
| syft-release | completed | 0 | 1.571 |
| trivy-sbom-dev | completed | 0 | 0.419 |
| trivy-source | completed | 0 | 30.893 |

### Repository posture

| Control | Status | Score | Reason |
| --- | --- | --- | --- |
| Branch-Protection | provider-unavailable | — | scorecard-provider-unsupported-request-type |
| Dangerous-Workflow | observed | 10 | recorded-by-scorecard |
| Maintained | provider-unavailable | — | scorecard-provider-unsupported-request-type |
| Pinned-Dependencies | observed | 2 | recorded-by-scorecard |
| Signed-Releases | provider-unavailable | — | scorecard-provider-unsupported-request-type |
| Token-Permissions | observed | 0 | recorded-by-scorecard |

## Baseline readiness

| Signal | Value |
| --- | --- |
| Readiness | ready |
| Verified candidates | 3 |
| Selected baseline | lite-2026.08.19.2 |
| Selected commit | 950cee9e89febf1feb5d1072eecb8aa30a4026ad |
| Policy | two verified canonical release records + matching reachable Git tag/commit/tree; release-to-HEAD comparison is forbidden |
| Reason | comparable verified prior release selected |

## Historical comparison

Compared **lite-2026.08.19.2** → **current-source** using verified canonical evidence.

### Dependencies added

No dependency additions observed.

### Dependencies removed

| Ecosystem | Name | Version |
| --- | --- | --- |
| PyPI | -r | requirements-docs.txt |

### Versions changed

| Ecosystem | Name | From | To |
| --- | --- | --- | --- |
| PyPI | PyYAML | 6.0.1 | 6.0.3 |
| npm | @asyncapi/specs | 5.1.0 | 6.11.1 |
| npm | @esbuild/aix-ppc64 | 0.21.5 | 0.25.12 |
| npm | @esbuild/android-arm | 0.21.5 | 0.25.12 |
| npm | @esbuild/android-arm64 | 0.21.5 | 0.25.12 |
| npm | @esbuild/android-x64 | 0.21.5 | 0.25.12 |
| npm | @esbuild/darwin-arm64 | 0.21.5 | 0.25.12 |
| npm | @esbuild/darwin-x64 | 0.21.5 | 0.25.12 |
| npm | @esbuild/freebsd-arm64 | 0.21.5 | 0.25.12 |
| npm | @esbuild/freebsd-x64 | 0.21.5 | 0.25.12 |
| npm | @esbuild/linux-arm | 0.21.5 | 0.25.12 |
| npm | @esbuild/linux-arm64 | 0.21.5 | 0.25.12 |
| npm | @esbuild/linux-ia32 | 0.21.5 | 0.25.12 |
| npm | @esbuild/linux-loong64 | 0.21.5 | 0.25.12 |
| npm | @esbuild/linux-mips64el | 0.21.5 | 0.25.12 |
| npm | @esbuild/linux-ppc64 | 0.21.5 | 0.25.12 |
| npm | @esbuild/linux-riscv64 | 0.21.5 | 0.25.12 |
| npm | @esbuild/linux-s390x | 0.21.5 | 0.25.12 |
| npm | @esbuild/linux-x64 | 0.21.5 | 0.25.12 |
| npm | @esbuild/netbsd-x64 | 0.21.5 | 0.25.12 |
| npm | @esbuild/openbsd-x64 | 0.21.5 | 0.25.12 |
| npm | @esbuild/sunos-x64 | 0.21.5 | 0.25.12 |
| npm | @esbuild/win32-arm64 | 0.21.5 | 0.25.12 |
| npm | @esbuild/win32-ia32 | 0.21.5 | 0.25.12 |
| npm | @esbuild/win32-x64 | 0.21.5 | 0.25.12 |
| npm | @eslint/js | 8.57.1 | 9.39.4 |
| npm | @inquirer/ansi | 1.0.2 | 2.0.7 |
| npm | @inquirer/confirm | 3.2.0 | 6.1.1 |
| npm | @inquirer/figures | 1.0.15 | 2.0.7 |
| npm | @inquirer/input | 2.3.0 | 4.3.1 |
| npm | @inquirer/select | 2.5.0 | 4.4.2 |
| npm | @inquirer/type | 1.5.5 | 4.0.7 |
| npm | @jridgewell/trace-mapping | 0.3.31 | 0.3.9 |
| npm | @npmcli/config | 10.10.0 | 8.3.4 |
| npm | @npmcli/run-script | 10.0.4 | 4.2.1 |
| npm | @opentelemetry/api-logs | 0.214.0 | 0.57.2 |
| npm | @opentelemetry/semantic-conventions | 1.40.0 | 1.41.1 |
| npm | @puppeteer/browsers | 2.13.2 | 2.3.0 |
| npm | @redocly/ajv | 8.11.2 | 8.18.3 |
| npm | @redocly/config | 0.22.0 | 0.49.0 |
| npm | @redocly/openapi-core | 1.34.15 | 2.31.6 |
| npm | @rollup/pluginutils | 3.1.0 | 5.4.0 |
| npm | @storybook/csf-plugin | 8.6.14 | 8.6.18 |
| npm | @types/node | 16.18.126 | 25.9.1 |
| npm | accepts | 1.3.8 | 2.0.0 |
| npm | ajv | 6.5.2 | 8.20.0 |
| npm | ajv-formats | 2.1.1 | 3.0.1 |
| npm | arg | 4.1.3 | 5.0.2 |
| npm | body-parser | 1.20.5 | 2.2.2 |
| npm | buffer-crc32 | 0.2.13 | 1.0.0 |
| npm | chardet | 0.7.0 | 2.1.1 |
| npm | chokidar | 3.6.0 | 4.0.3 |
| npm | color-convert | 1.9.3 | 3.1.3 |
| npm | color-name | 1.1.3 | 2.1.0 |
| npm | colorette | 1.4.0 | 2.0.20 |
| npm | commander | 2.20.3 | 8.3.0 |
| npm | content-disposition | 0.5.4 | 1.1.0 |
| npm | content-type | 1.0.5 | 2.0.0 |
| npm | cookie-signature | 1.0.7 | 1.2.2 |
| npm | d3-array | 2.12.1 | 3.2.4 |
| npm | d3-path | 1.0.9 | 3.1.0 |
| npm | data-uri-to-buffer | 2.0.2 | 6.0.2 |
| npm | debug | 2.6.9 | 4.4.3 |
| npm | doctrine | 2.1.0 | 3.0.0 |
| npm | dom-accessibility-api | 0.5.16 | 0.6.3 |
| npm | esbuild | 0.21.5 | 0.25.12 |
| npm | express | 4.22.2 | 5.2.1 |
| npm | fast-deep-equal | 2.0.1 | 3.1.3 |
| npm | fast-levenshtein | 2.0.6 | 3.0.0 |
| npm | figures | 2.0.0 | 3.2.0 |
| npm | finalhandler | 1.3.2 | 2.1.1 |
| npm | find-up | 4.1.0 | 5.0.0 |
| npm | for-in | 0.1.8 | 1.0.2 |
| npm | fresh | 0.5.2 | 2.0.0 |
| npm | fs-extra | 11.3.5 | 9.1.0 |
| npm | glob | 11.1.0 | 8.1.0 |
| npm | has-flag | 3.0.0 | 4.0.0 |
| npm | hosted-git-info | 5.2.1 | 9.0.3 |
| npm | iconv-lite | 0.6.3 | 0.7.2 |
| npm | inherits | 2.0.3 | 2.0.4 |
| npm | ini | 1.3.8 | 6.0.0 |
| npm | inquirer | 6.5.2 | 8.2.7 |
| npm | is-obj | 1.0.1 | 2.0.0 |
| npm | isarray | 1.0.0 | 2.0.5 |
| npm | js-yaml | 4.1.1 | 4.2.0 |
| npm | jsdom | 24.1.3 | 28.1.0 |
| npm | json-parse-even-better-errors | 2.3.1 | 5.0.0 |
| npm | json-schema-traverse | 0.4.1 | 1.0.0 |
| npm | jsonfile | 4.0.0 | 6.2.1 |
| npm | kind-of | 2.0.1 | 3.2.2 |
| npm | layout-base | 1.0.2 | 2.0.1 |
| npm | lazy-cache | 0.2.7 | 1.0.4 |
| npm | locate-path | 5.0.0 | 6.0.0 |
| npm | lru-cache | 11.5.1 | 7.18.3 |
| npm | marked | 16.4.2 | 4.3.0 |
| npm | media-typer | 0.3.0 | 1.1.0 |
| npm | merge-descriptors | 1.0.3 | 2.0.0 |
| npm | mime-db | 1.52.0 | 1.54.0 |
| npm | mime-types | 2.1.35 | 3.0.2 |
| npm | minimatch | 10.2.5 | 9.0.9 |
| npm | minipass | 3.3.6 | 7.1.3 |
| npm | minipass-flush | 1.0.6 | 1.0.7 |
| npm | ms | 2.0.0 | 2.1.3 |
| npm | mute-stream | 1.0.0 | 3.0.0 |
| npm | node-fetch | 2.6.7 | 2.7.0 |
| npm | node-gyp | 12.3.0 | 9.4.1 |
| npm | normalize-package-data | 4.0.1 | 6.0.2 |
| npm | npm-normalize-package-bin | 2.0.0 | 5.0.0 |
| npm | npm-package-arg | 13.0.2 | 9.1.2 |
| npm | npm-packlist | 10.0.4 | 5.1.3 |
| npm | npm-pick-manifest | 11.0.3 | 9.1.0 |
| npm | npm-run-path | 4.0.1 | 5.3.0 |
| npm | open | 7.4.2 | 8.4.2 |
| npm | p-limit | 2.3.0 | 3.1.0 |
| npm | p-locate | 4.1.0 | 5.0.0 |
| npm | parse-json | 4.0.0 | 5.2.0 |
| npm | parse5 | 7.3.0 | 8.0.1 |
| npm | path-key | 3.1.1 | 4.0.0 |
| npm | picomatch | 2.3.2 | 4.0.4 |
| npm | postcss-selector-parser | 6.1.2 | 7.1.1 |
| npm | pretty-bytes | 5.6.0 | 6.1.1 |
| npm | proxy-from-env | 1.1.0 | 2.1.0 |
| npm | raw-body | 2.5.3 | 3.0.2 |
| npm | readdirp | 3.6.0 | 4.1.2 |
| npm | resolve | 1.22.12 | 2.0.0-next.7 |
| npm | restore-cursor | 2.0.0 | 3.1.0 |
| npm | rimraf | 2.7.1 | 3.0.2 |
| npm | rrweb-cssom | 0.7.1 | 0.8.0 |
| npm | semver | 6.3.1 | 7.8.2 |
| npm | send | 0.19.2 | 1.2.1 |
| npm | serve-static | 1.16.3 | 2.2.1 |
| npm | signal-exit | 3.0.7 | 4.1.0 |
| npm | spdx-expression-parse | 3.0.1 | 4.0.0 |
| npm | ssri | 13.0.1 | 9.0.1 |
| npm | string-width | 4.2.3 | 5.1.2 |
| npm | supports-color | 7.2.0 | 8.1.1 |
| npm | tinyexec | 0.3.2 | 1.2.4 |
| npm | tough-cookie | 4.1.4 | 6.0.1 |
| npm | tr46 | 1.0.1 | 6.0.0 |
| npm | type-fest | 0.20.2 | 5.7.0 |
| npm | type-is | 1.6.18 | 2.1.0 |
| npm | typescript | 4.9.5 | 5.9.3 |
| npm | undici | 6.24.0 | 7.27.2 |
| npm | urlpattern-polyfill | 10.0.0 | 8.0.2 |
| npm | uuid | 8.3.2 | 9.0.1 |
| npm | validate-npm-package-name | 5.0.1 | 7.0.2 |
| npm | vite | 5.4.21 | 6.4.3 |
| npm | webidl-conversions | 4.0.2 | 8.0.1 |
| npm | whatwg-mimetype | 4.0.0 | 5.0.0 |
| npm | which | 2.0.2 | 6.0.1 |
| npm | write-file-atomic | 3.0.3 | 7.0.1 |
| npm | y18n | 4.0.3 | 5.0.8 |
| npm | yallist | 3.1.1 | 5.0.0 |
| npm | yargs | 15.4.1 | 17.7.2 |
| npm | yargs-parser | 18.1.3 | 21.1.1 |

### Vulnerability changes

| Direction | ID |
| --- | --- |
| new | CVE-2026-15806 |
| new | CVE-2026-17084 |
| new | CVE-2026-18503 |
| new | CVE-2026-19672 |
| new | CVE-2026-33818 |
| new | CVE-2026-56853 |
| new | CVE-2026-56854 |
| new | CVE-2026-56858 |
| new | CVE-2026-56859 |
| new | CVE-2026-56860 |
| new | CVE-2026-56862 |
| new | CVE-2026-56864 |
| new | CVE-2026-56865 |
| new | CVE-2026-61711 |
| new | CVE-2026-61712 |
| new | CVE-2026-73502 |
| new | CVE-2026-76905 |
| new | CVE-2026-77354 |
| new | GHSA-7236-3392-c5c6 |
| new | GHSA-72x6-4j93-7w86 |
| new | GHSA-jmr9-qjv8-65gv |
| new | GHSA-m42h-3232-vpv3 |
| new | GHSA-mmfr-pmjx-hw9w |
| new | GHSA-w4pp-8pjf-rmxw |
| new | GHSA-xhj3-7xw9-vr34 |
| new | GO-2026-5972 |
| new | GO-2026-6088 |
| new | GO-2026-6089 |
| new | GO-2026-6090 |
| new | GO-2026-6091 |
| new | GO-2026-6095 |
| new | GO-2026-6112 |
| new | GO-2026-6179 |
| new | GO-2026-6180 |
| new | GO-2026-6213 |
| new | GO-2026-6214 |
| new | GO-2026-6218 |
| new | GO-2026-6225 |
| new | GO-2026-6255 |
| new | GO-2026-6256 |
| new | GO-2026-6274 |
| new | GO-2026-6275 |
| new | GO-2026-6303 |
| new | PYSEC-2026-3721 |
| new | PYSEC-2026-3722 |
| new | PYSEC-2026-3723 |
| resolved | CVE-2026-34040 |
| resolved | GHSA-2v8p-3f2j-5mp7 |
| resolved | GHSA-3rrr-jr9j-h3q3 |
| resolved | GHSA-6x64-9x62-f2gx |
| resolved | GHSA-c4c3-pg64-4m4v |
| resolved | GHSA-rhh3-jpg6-66xh |
| resolved | GHSA-x744-4wpc-v9h2 |

### License changes

No comparable license changes observed, or the historical canonical license artifact is unavailable.

### Upstream posture changes

No comparable upstream posture changes observed, or the historical canonical Scorecard artifact is unavailable.

Scanner disagreement remains evidence, not an automatic release failure.
