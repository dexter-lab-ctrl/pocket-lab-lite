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
| Run ID | scorecard-compatible-20260811T100353Z |
| Source commit | 19d54e0bb84226f355865c32c6decee8ce010083 |
| Qualification surface | local-or-ci-diagnostic |
| Development SBOM components | 2366 |
| Release SBOM components | 7 |
| Runtime SBOM components | 0 |
| Vulnerability evidence | observed (580 normalized findings) |
| Package-license coverage | observed via syft+trivy |
| Package rows | 2366 |
| Trivy license rows | 26 |
| Deep source-license coverage | not-run |
| Gitleaks findings | 1035 |
| Semgrep findings | 0 |
| Scorecard posture | observed-with-provider-limitations |

### Tool coverage

| Step | Status | Exit | Duration (s) |
| --- | --- | --- | --- |
| gitleaks-release | completed | 0 | 0.671 |
| gitleaks-worktree | findings-or-tool-nonzero | 1 | 13.184 |
| grype-sbom-dev | completed | 0 | 5.45 |
| osv-sbom-dev | findings-or-tool-nonzero | 1 | 5.133 |
| osv-source | findings-or-tool-nonzero | 1 | 70.248 |
| scorecard | completed | 0 | 7.34 |
| semgrep | completed | 0 | 4.932 |
| syft-dev | completed | 0 | 129.844 |
| syft-release | completed | 0 | 2.173 |
| trivy-sbom-dev | completed | 0 | 0.419 |
| trivy-source | completed | 0 | 73.047 |

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
| Readiness | not-ready |
| Verified candidates | 1 |
| Selected baseline | none |
| Selected commit | none |
| Policy | two verified canonical release records + matching reachable Git tag/commit/tree; release-to-HEAD comparison is forbidden |
| Reason | no second verified canonical release is available for release-to-release comparison |

## Historical comparison

!!! info "No comparable verified prior release"
    Current promoted supply-chain evidence is available, but no verified N-1 canonical release baseline satisfies the tag + commit + tree + ancestry policy. Dependency, vulnerability, license, and upstream deltas therefore remain explicitly not comparable.

### Dependencies added

Historical comparison unavailable until a verified canonical prior-release baseline exists.

### Dependencies removed

Historical comparison unavailable until a verified canonical prior-release baseline exists.

### Versions changed

Historical comparison unavailable until a verified canonical prior-release baseline exists.

### Vulnerability changes

Historical comparison unavailable until a verified canonical prior-release baseline exists.

### License changes

Historical comparison unavailable until a verified canonical prior-release baseline exists.

### Upstream posture changes

Historical comparison unavailable until a verified canonical prior-release baseline exists.
