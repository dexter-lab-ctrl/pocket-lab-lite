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
| Run ID | runtime-assurance-fixed-20260914T0010Z-776566 |
| Source commit | 3f4f277de5fc8c99d01b0d07baa7376b608d1bd7 |
| Qualification surface | local-or-ci-diagnostic |
| Development SBOM components | 54 |
| Release SBOM components | 0 |
| Runtime SBOM components | 0 |
| Vulnerability evidence | observed (139 normalized findings) |
| Package-license coverage | observed via syft+trivy |
| Package rows | 54 |
| Trivy license rows | 26 |
| Deep source-license coverage | not-run |
| Gitleaks findings | 3 |
| Semgrep findings | 0 |
| Scorecard posture | observed-with-provider-limitations |

### Tool coverage

| Step | Status | Exit | Duration (s) |
| --- | --- | --- | --- |
| gitleaks-release | completed | 0 | 0.673 |
| gitleaks-worktree | findings-or-tool-nonzero | 1 | 2.129 |
| grype-sbom-dev | completed | 0 | 1.773 |
| osv-sbom-dev | completed | 0 | 0.67 |
| osv-source | findings-or-tool-nonzero | 1 | 25.878 |
| scorecard | completed | 0 | 9.092 |
| semgrep | completed | 0 | 18.815 |
| syft-dev | completed | 0 | 1.774 |
| syft-release | completed | 0 | 1.172 |
| trivy-sbom-dev | completed | 0 | 0.068 |
| trivy-source | completed | 0 | 23.487 |

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

| Ecosystem | Name | Version |
| --- | --- | --- |
| PyPI | cryptography | 42.0.0 |

### Dependencies removed

| Ecosystem | Name | Version |
| --- | --- | --- |
| PyPI | -r | requirements-docs.txt |

### Versions changed

| Ecosystem | Name | From | To |
| --- | --- | --- | --- |
| PyPI | PyYAML | 6.0.1 | 6.0.3 |
| PyPI | mkdocs-material | 9.7.6 | 9.7.7 |
| PyPI | pymdown-extensions | 10.21.3 | 11.0.1 |
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
| new | GHSA-2883-xcg3-v3hh |
| new | GHSA-2xp9-vwfh-vxw4 |
| new | GHSA-4mjr-xmp4-gh2g |
| new | GHSA-6w3j-5fw6-r9vr |
| new | GHSA-73wf-gq98-2v4g |
| new | GHSA-7pqw-9j4j-h8q3 |
| new | GHSA-82fw-gwwq-j7x9 |
| new | GHSA-c83g-rgw3-j3cx |
| new | GHSA-f65p-4m7j-42xc |
| new | GHSA-fph4-wmhf-6fwf |
| new | GHSA-gg4h-3hg2-grpc |
| new | GHSA-jmr9-qjv8-65gv |
| new | GHSA-jqff-g426-hqxp |
| new | GHSA-p293-qw3h-jr36 |
| new | GHSA-qxc2-j82w-r537 |
| new | GHSA-w4pp-8pjf-rmxw |
| new | GHSA-w5vr-8v7q-w6rv |
| new | GHSA-w9m9-85wc-3x92 |
| new | GHSA-x5fp-wj9c-mxmx |
| resolved | CVE-2023-39318 |
| resolved | CVE-2023-39319 |
| resolved | CVE-2023-39325 |
| resolved | CVE-2023-39326 |
| resolved | CVE-2023-45283 |
| resolved | CVE-2023-45284 |
| resolved | CVE-2023-45288 |
| resolved | CVE-2023-45289 |
| resolved | CVE-2023-45290 |
| resolved | CVE-2024-24783 |
| resolved | CVE-2024-24784 |
| resolved | CVE-2024-24785 |
| resolved | CVE-2024-24789 |
| resolved | CVE-2024-24790 |
| resolved | CVE-2024-24791 |
| resolved | CVE-2024-34155 |
| resolved | CVE-2024-34156 |
| resolved | CVE-2024-34158 |
| resolved | CVE-2024-45336 |
| resolved | CVE-2024-45341 |
| resolved | CVE-2025-0913 |
| resolved | CVE-2025-11579 |
| resolved | CVE-2025-12781 |
| resolved | CVE-2025-13462 |
| resolved | CVE-2025-15366 |
| resolved | CVE-2025-15367 |
| resolved | CVE-2025-22866 |
| resolved | CVE-2025-22870 |
| resolved | CVE-2025-22871 |
| resolved | CVE-2025-22873 |
| resolved | CVE-2025-4673 |
| resolved | CVE-2025-47906 |
| resolved | CVE-2025-47907 |
| resolved | CVE-2025-47912 |
| resolved | CVE-2025-47913 |
| resolved | CVE-2025-47914 |
| resolved | CVE-2025-58058 |
| resolved | CVE-2025-58181 |
| resolved | CVE-2025-58183 |
| resolved | CVE-2025-58185 |
| resolved | CVE-2025-58186 |
| resolved | CVE-2025-58187 |
| resolved | CVE-2025-58188 |
| resolved | CVE-2025-58189 |
| resolved | CVE-2025-6075 |
| resolved | CVE-2025-61723 |
| resolved | CVE-2025-61724 |
| resolved | CVE-2025-61725 |
| resolved | CVE-2025-61726 |
| resolved | CVE-2025-61727 |
| resolved | CVE-2025-61728 |
| resolved | CVE-2025-61729 |
| resolved | CVE-2025-61730 |
| resolved | CVE-2025-68121 |
| resolved | CVE-2025-8291 |
| resolved | CVE-2025-8869 |
| resolved | CVE-2026-0864 |
| resolved | CVE-2026-11332 |
| resolved | CVE-2026-11940 |
| resolved | CVE-2026-11972 |
| resolved | CVE-2026-12061 |
| resolved | CVE-2026-12072 |
| resolved | CVE-2026-12074 |
| resolved | CVE-2026-12075 |
| resolved | CVE-2026-1299 |
| resolved | CVE-2026-1502 |
| resolved | CVE-2026-15308 |
| resolved | CVE-2026-1703 |
| resolved | CVE-2026-2297 |
| resolved | CVE-2026-25679 |
| resolved | CVE-2026-25680 |
| resolved | CVE-2026-25681 |
| resolved | CVE-2026-27136 |
| resolved | CVE-2026-27139 |
| resolved | CVE-2026-27141 |
| resolved | CVE-2026-27142 |
| resolved | CVE-2026-27145 |
| resolved | CVE-2026-3219 |
| resolved | CVE-2026-32280 |
| resolved | CVE-2026-32281 |
| resolved | CVE-2026-32282 |
| resolved | CVE-2026-32283 |
| resolved | CVE-2026-32288 |
| resolved | CVE-2026-32289 |
| resolved | CVE-2026-3276 |
| resolved | CVE-2026-33747 |
| resolved | CVE-2026-33748 |
| resolved | CVE-2026-33811 |
| resolved | CVE-2026-33814 |
| resolved | CVE-2026-33997 |
| resolved | CVE-2026-34040 |
| resolved | CVE-2026-3446 |
| resolved | CVE-2026-3644 |
| resolved | CVE-2026-39820 |
| resolved | CVE-2026-39821 |
| resolved | CVE-2026-39822 |
| resolved | CVE-2026-39823 |
| resolved | CVE-2026-39824 |
| resolved | CVE-2026-39825 |
| resolved | CVE-2026-39826 |
| resolved | CVE-2026-39827 |
| resolved | CVE-2026-39828 |
| resolved | CVE-2026-39829 |
| resolved | CVE-2026-39830 |
| resolved | CVE-2026-39831 |
| resolved | CVE-2026-39832 |
| resolved | CVE-2026-39833 |
| resolved | CVE-2026-39834 |
| resolved | CVE-2026-39835 |
| resolved | CVE-2026-39836 |
| resolved | CVE-2026-41567 |
| resolved | CVE-2026-41568 |
| resolved | CVE-2026-4224 |
| resolved | CVE-2026-42306 |
| resolved | CVE-2026-42499 |
| resolved | CVE-2026-42502 |
| resolved | CVE-2026-42504 |
| resolved | CVE-2026-42505 |
| resolved | CVE-2026-42506 |
| resolved | CVE-2026-42507 |
| resolved | CVE-2026-42508 |
| resolved | CVE-2026-4360 |
| resolved | CVE-2026-44740 |
| resolved | CVE-2026-44973 |
| resolved | CVE-2026-45022 |
| resolved | CVE-2026-4519 |
| resolved | CVE-2026-45570 |
| resolved | CVE-2026-45571 |
| resolved | CVE-2026-46595 |
| resolved | CVE-2026-46597 |
| resolved | CVE-2026-46598 |
| resolved | CVE-2026-46600 |
| resolved | CVE-2026-46680 |
| resolved | CVE-2026-47262 |
| resolved | CVE-2026-4786 |
| resolved | CVE-2026-50163 |
| resolved | CVE-2026-52869 |
| resolved | CVE-2026-52870 |
| resolved | CVE-2026-53488 |
| resolved | CVE-2026-53508 |
| resolved | CVE-2026-54293 |
| resolved | CVE-2026-56852 |
| resolved | CVE-2026-5713 |
| resolved | CVE-2026-59890 |
| resolved | CVE-2026-59950 |
| resolved | CVE-2026-6019 |
| resolved | CVE-2026-6100 |
| resolved | CVE-2026-61632 |
| resolved | CVE-2026-6357 |
| resolved | CVE-2026-67422 |
| resolved | CVE-2026-6879 |
| resolved | CVE-2026-69247 |
| resolved | CVE-2026-71556 |
| resolved | CVE-2026-71557 |
| resolved | CVE-2026-7210 |
| resolved | CVE-2026-7774 |
| resolved | CVE-2026-8328 |
| resolved | CVE-2026-8643 |
| resolved | CVE-2026-9669 |
| resolved | GHSA-2f96-g7mh-g2hx |
| resolved | GHSA-2jcc-mxv7-p3f9 |
| resolved | GHSA-2v8p-3f2j-5mp7 |
| resolved | GHSA-389r-gv7p-r3rp |
| resolved | GHSA-3f7w-8rr8-f37f |
| resolved | GHSA-3rp5-jjmw-4wv2 |
| resolved | GHSA-3rrr-jr9j-h3q3 |
| resolved | GHSA-45gg-vh54-h5m9 |
| resolved | GHSA-4c29-8rgm-jvjj |
| resolved | GHSA-4gmw-gg2m-w46p |
| resolved | GHSA-4vrq-3vrq-g6gg |
| resolved | GHSA-4xh5-x5gv-qwph |
| resolved | GHSA-539m-9xh6-q6rr |
| resolved | GHSA-58qw-9mgm-455v |
| resolved | GHSA-5cgq-3rg8-m6cv |
| resolved | GHSA-5cv4-jp36-h3mw |
| resolved | GHSA-6hm5-jgcp-p838 |
| resolved | GHSA-6p8h-3wgx-97gf |
| resolved | GHSA-6v7p-g79w-8964 |
| resolved | GHSA-6vgw-5pg2-w6jp |
| resolved | GHSA-6x64-9x62-f2gx |
| resolved | GHSA-78mq-xcr3-xm33 |
| resolved | GHSA-89gr-r52h-f8rx |
| resolved | GHSA-94p4-4cq8-9g67 |
| resolved | GHSA-956x-8gvw-wg5v |
| resolved | GHSA-9m57-25v3-79x9 |
| resolved | GHSA-9rj7-rf2p-w77r |
| resolved | GHSA-9xwg-3r6f-jcx2 |
| resolved | GHSA-c4c3-pg64-4m4v |
| resolved | GHSA-crhj-59gh-8x96 |
| resolved | GHSA-f5wc-c3c7-36mc |
| resolved | GHSA-f6x5-jh6r-wrfv |
| resolved | GHSA-fg7f-2386-8897 |
| resolved | GHSA-fjr4-x663-mwxc |
| resolved | GHSA-fqw6-gf59-qr4w |
| resolved | GHSA-fxhp-mv3v-67qp |
| resolved | GHSA-g6cj-pr64-35w5 |
| resolved | GHSA-gm37-52c6-37mw |
| resolved | GHSA-h35f-9h28-mq5c |
| resolved | GHSA-hc8v-wwc9-vgxm |
| resolved | GHSA-hh9p-6wh2-4mfc |
| resolved | GHSA-hmq2-w58f-27jc |
| resolved | GHSA-hrxh-6v49-42gf |
| resolved | GHSA-hvrp-rf83-w775 |
| resolved | GHSA-j5w8-q4qc-rx2x |
| resolved | GHSA-jc7w-c686-c4v9 |
| resolved | GHSA-jm78-9fvv-mhgr |
| resolved | GHSA-jp4c-xjxw-mgf9 |
| resolved | GHSA-jpcc-p29g-p8mq |
| resolved | GHSA-jpcw-4wr7-c3vq |
| resolved | GHSA-jppx-rxg9-jmrx |
| resolved | GHSA-jpw9-pfvf-9f58 |
| resolved | GHSA-m3xc-h892-ggx6 |
| resolved | GHSA-m7cr-m3pv-hgrp |
| resolved | GHSA-p4gq-832x-fm9v |
| resolved | GHSA-p538-c434-8v24 |
| resolved | GHSA-pxq6-2prw-chj9 |
| resolved | GHSA-q4h4-gmj2-qvw2 |
| resolved | GHSA-qgq7-7hm3-q39j |
| resolved | GHSA-qpw4-5x99-6vjp |
| resolved | GHSA-qvv7-cg9c-w4x3 |
| resolved | GHSA-qw64-3x98-g7q2 |
| resolved | GHSA-r277-6w6q-xmqw |
| resolved | GHSA-r9mr-m37c-5fr3 |
| resolved | GHSA-rg2x-37c3-w2rh |
| resolved | GHSA-rhh3-jpg6-66xh |
| resolved | GHSA-rm3j-f69w-wqmq |
| resolved | GHSA-rwj8-pgh3-r573 |
| resolved | GHSA-rwvp-r38j-9rgg |
| resolved | GHSA-v396-v7q4-x2qj |
| resolved | GHSA-vgwf-h737-ff37 |
| resolved | GHSA-vj7q-gjh5-988w |
| resolved | GHSA-vp62-88p7-qqf5 |
| resolved | GHSA-w5pp-99ch-qj29 |
| resolved | GHSA-w879-237q-wc7r |
| resolved | GHSA-w8p5-mx5w-cpqj |
| resolved | GHSA-wf93-45jw-7689 |
| resolved | GHSA-wvpp-8hx9-p66j |
| resolved | GHSA-x527-x647-q7gg |
| resolved | GHSA-x744-4wpc-v9h2 |
| resolved | GHSA-x86f-5xw2-fm2r |
| resolved | GHSA-xh95-f55m-82fw |
| resolved | GHSA-xhf5-7wjv-pqxp |
| resolved | GO-2021-0142 |
| resolved | GO-2021-0159 |
| resolved | GO-2021-0163 |
| resolved | GO-2021-0172 |
| resolved | GO-2021-0223 |
| resolved | GO-2021-0224 |
| resolved | GO-2021-0226 |
| resolved | GO-2021-0234 |
| resolved | GO-2021-0235 |
| resolved | GO-2021-0239 |
| resolved | GO-2021-0240 |
| resolved | GO-2021-0241 |
| resolved | GO-2021-0242 |
| resolved | GO-2021-0243 |
| resolved | GO-2021-0245 |
| resolved | GO-2021-0263 |
| resolved | GO-2021-0264 |
| resolved | GO-2021-0317 |
| resolved | GO-2021-0319 |
| resolved | GO-2021-0347 |
| resolved | GO-2022-0166 |
| resolved | GO-2022-0171 |
| resolved | GO-2022-0191 |
| resolved | GO-2022-0211 |
| resolved | GO-2022-0212 |
| resolved | GO-2022-0213 |
| resolved | GO-2022-0217 |
| resolved | GO-2022-0220 |
| resolved | GO-2022-0229 |
| resolved | GO-2022-0236 |
| resolved | GO-2022-0273 |
| resolved | GO-2022-0288 |
| resolved | GO-2022-0289 |
| resolved | GO-2022-0433 |
| resolved | GO-2022-0435 |
| resolved | GO-2022-0477 |
| resolved | GO-2022-0493 |
| resolved | GO-2022-0515 |
| resolved | GO-2022-0520 |
| resolved | GO-2022-0521 |
| resolved | GO-2022-0522 |
| resolved | GO-2022-0523 |
| resolved | GO-2022-0524 |
| resolved | GO-2022-0525 |
| resolved | GO-2022-0526 |
| resolved | GO-2022-0527 |
| resolved | GO-2022-0531 |
| resolved | GO-2022-0532 |
| resolved | GO-2022-0533 |
| resolved | GO-2022-0535 |
| resolved | GO-2022-0536 |
| resolved | GO-2022-0537 |
| resolved | GO-2022-0761 |
| resolved | GO-2022-0969 |
| resolved | GO-2022-1037 |
| resolved | GO-2022-1038 |
| resolved | GO-2022-1039 |
| resolved | GO-2022-1095 |
| resolved | GO-2022-1143 |
| resolved | GO-2022-1144 |
| resolved | GO-2023-1568 |
| resolved | GO-2023-1569 |
| resolved | GO-2023-1570 |
| resolved | GO-2023-1571 |
| resolved | GO-2023-1621 |
| resolved | GO-2023-1702 |
| resolved | GO-2023-1703 |
| resolved | GO-2023-1704 |
| resolved | GO-2023-1705 |
| resolved | GO-2023-1751 |
| resolved | GO-2023-1752 |
| resolved | GO-2023-1753 |
| resolved | GO-2023-1840 |
| resolved | GO-2023-1878 |
| resolved | GO-2023-1987 |
| resolved | GO-2023-2041 |
| resolved | GO-2023-2043 |
| resolved | GO-2023-2102 |
| resolved | GO-2023-2185 |
| resolved | GO-2023-2186 |
| resolved | GO-2023-2375 |
| resolved | GO-2023-2382 |
| resolved | GO-2024-2598 |
| resolved | GO-2024-2599 |
| resolved | GO-2024-2600 |
| resolved | GO-2024-2609 |
| resolved | GO-2024-2610 |
| resolved | GO-2024-2687 |
| resolved | GO-2024-2887 |
| resolved | GO-2024-2888 |
| resolved | GO-2024-2963 |
| resolved | GO-2024-3105 |
| resolved | GO-2024-3106 |
| resolved | GO-2024-3107 |
| resolved | GO-2025-3373 |
| resolved | GO-2025-3420 |
| resolved | GO-2025-3447 |
| resolved | GO-2025-3503 |
| resolved | GO-2025-3563 |
| resolved | GO-2025-3750 |
| resolved | GO-2025-3751 |
| resolved | GO-2025-3849 |
| resolved | GO-2025-3922 |
| resolved | GO-2025-3956 |
| resolved | GO-2025-4006 |
| resolved | GO-2025-4007 |
| resolved | GO-2025-4008 |
| resolved | GO-2025-4009 |
| resolved | GO-2025-4010 |
| resolved | GO-2025-4011 |
| resolved | GO-2025-4012 |
| resolved | GO-2025-4013 |
| resolved | GO-2025-4014 |
| resolved | GO-2025-4015 |
| resolved | GO-2025-4020 |
| resolved | GO-2025-4116 |
| resolved | GO-2025-4134 |
| resolved | GO-2025-4135 |
| resolved | GO-2025-4155 |
| resolved | GO-2025-4175 |
| resolved | GO-2026-4337 |
| resolved | GO-2026-4340 |
| resolved | GO-2026-4341 |
| resolved | GO-2026-4342 |
| resolved | GO-2026-4403 |
| resolved | GO-2026-4559 |
| resolved | GO-2026-4601 |
| resolved | GO-2026-4602 |
| resolved | GO-2026-4603 |
| resolved | GO-2026-4858 |
| resolved | GO-2026-4859 |
| resolved | GO-2026-4864 |
| resolved | GO-2026-4865 |
| resolved | GO-2026-4869 |
| resolved | GO-2026-4870 |
| resolved | GO-2026-4883 |
| resolved | GO-2026-4887 |
| resolved | GO-2026-4918 |
| resolved | GO-2026-4919 |
| resolved | GO-2026-4946 |
| resolved | GO-2026-4947 |
| resolved | GO-2026-4970 |
| resolved | GO-2026-4971 |
| resolved | GO-2026-4976 |
| resolved | GO-2026-4977 |
| resolved | GO-2026-4980 |
| resolved | GO-2026-4981 |
| resolved | GO-2026-4982 |
| resolved | GO-2026-4986 |
| resolved | GO-2026-5005 |
| resolved | GO-2026-5006 |
| resolved | GO-2026-5013 |
| resolved | GO-2026-5014 |
| resolved | GO-2026-5015 |
| resolved | GO-2026-5016 |
| resolved | GO-2026-5017 |
| resolved | GO-2026-5018 |
| resolved | GO-2026-5019 |
| resolved | GO-2026-5020 |
| resolved | GO-2026-5021 |
| resolved | GO-2026-5023 |
| resolved | GO-2026-5024 |
| resolved | GO-2026-5025 |
| resolved | GO-2026-5026 |
| resolved | GO-2026-5027 |
| resolved | GO-2026-5028 |
| resolved | GO-2026-5029 |
| resolved | GO-2026-5030 |
| resolved | GO-2026-5033 |
| resolved | GO-2026-5037 |
| resolved | GO-2026-5038 |
| resolved | GO-2026-5039 |
| resolved | GO-2026-5064 |
| resolved | GO-2026-5074 |
| resolved | GO-2026-5158 |
| resolved | GO-2026-5336 |
| resolved | GO-2026-5338 |
| resolved | GO-2026-5378 |
| resolved | GO-2026-5475 |
| resolved | GO-2026-5490 |
| resolved | GO-2026-5496 |
| resolved | GO-2026-5597 |
| resolved | GO-2026-5617 |
| resolved | GO-2026-5622 |
| resolved | GO-2026-5668 |
| resolved | GO-2026-5693 |
| resolved | GO-2026-5746 |
| resolved | GO-2026-5758 |
| resolved | GO-2026-5841 |
| resolved | GO-2026-5856 |
| resolved | GO-2026-5880 |
| resolved | GO-2026-5932 |
| resolved | GO-2026-5937 |
| resolved | GO-2026-5942 |
| resolved | GO-2026-5970 |
| resolved | GO-2026-6061 |
| resolved | PYSEC-2026-1795 |
| resolved | PYSEC-2026-1796 |
| resolved | PYSEC-2026-196 |
| resolved | PYSEC-2026-2078 |
| resolved | PYSEC-2026-2875 |
| resolved | PYSEC-2026-2876 |
| resolved | PYSEC-2026-3447 |
| resolved | PYSEC-2026-3458 |
| resolved | PYSEC-2026-3481 |
| resolved | PYSEC-2026-3482 |
| resolved | PYSEC-2026-3483 |
| resolved | PYSEC-2026-3552 |
| resolved | PYSEC-2026-3581 |
| resolved | PYSEC-2026-3582 |
| resolved | PYSEC-2026-3583 |
| resolved | PYSEC-2026-3584 |
| resolved | PYSEC-2026-3609 |
| resolved | PYSEC-2026-3625 |
| resolved | PYSEC-2026-3654 |
| resolved | PYSEC-2026-597 |

### License changes

| Direction | License |
| --- | --- |
| removed | 0BSD |
| removed | 3-Clause BSD License |
| removed | Apache 2.0 |
| removed | Apache License, Version 2.0 |
| removed | Apache Software License |
| removed | Artistic License |
| removed | BSD |
| removed | BSD License |
| removed | BSD-2-Clause |
| removed | BSD-2-Clause or Apache-2.0 |
| removed | BSD-3-Clause |
| removed | BSD-3-Clause and Public-Domain |
| removed | Dual License |
| removed | GPL-3.0-or-later |
| removed | ISC License |
| removed | LGPL-2.1-or-later |
| removed | LGPL-3.0-or-later |
| removed | LGPLv3 |
| removed | MIT License |
| removed | MIT and MPL-2.0 |
| removed | MIT license |
| removed | MIT-0 |
| removed | MPL 2.0 |
| removed | MPL-2.0 |
| removed | PSF-2.0 |
| removed | PSFL |
| removed | UNKNOWN |
| removed | apache-2.0 AND bsd-simplified |
| removed | apache-2.0 AND bsd-simplified-darwin AND (bsd-simplified AND public-domain AND bsd-new AND isc AND (bsd-new OR gpl-1.0-plus) AND bsd-original) |
| removed | apache-2.0 AND lgpl-2.1 and unrar and brian-gladman-3-clause |
| removed | sha256:6e5070d765031e0ad403a1cbf90ae6d19a0228f802e320b7acff460aa72ed47c |
| removed | sha256:9049f9f2fca9ff13140af12a552d015fda6d4db09ae38e5a0323d73f69874691 |

### Upstream posture changes

No comparable upstream posture changes observed, or the historical canonical Scorecard artifact is unavailable.

Scanner disagreement remains evidence, not an automatic release failure.
