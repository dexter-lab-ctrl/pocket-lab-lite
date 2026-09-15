# Evidence-artifact reference

The worker-owned report artifacts are fixed by the current Security Assurance
service. The file names below must remain stable for machine clients and
reviewers.

| Artifact | Machine use | Human review | Must never contain |
| --- | --- | --- | --- |
| `manifest.json` | bind run to source/runtime/suite/registry/correlation | verify exact-head identity | private keys, raw tokens, credentials |
| `environment.json` | record bounded platform/readiness posture | verify admission context | secret environment values, user data |
| `toolchain.json` | correlate tool ID/version/lane/receipt | verify tool provenance/status | secret installer material, raw output |
| `findings.json` | consume normalized finding schema | triage severity/confidence/delta | raw secret matches, unrestricted paths |
| `threat-coverage.json` | map scenarios to STRIDE/controls | review invariant/evidence coverage | hidden untested paths |
| `owasp-coverage.json` | map OWASP Top 10 2021 categories | distinguish tested/static/human/N/A | unsupported PASS claims |
| `attack-path-results.json` | map AP-* classifications | inspect residual risk and evidence | risk acceptance without authority |
| `controls.json` | correlate control outcomes | trace control to implementation | reusable credentials |
| `delta.json` | compare compatible baseline | identify new/regressed/resolved findings | misleading cross-registry comparisons |
| `performance.json` | record duration/resource facts | assess low-power impact | fabricated zeros or sensitive telemetry |
| `sanitization.json` | prove redaction policy/check result | approve safe publication | raw secret values |
| `checksums.json` | verify artifact integrity | preserve immutable evidence set | mutable/unverified references |
| `summary.md` | provide bounded human conclusion | review verdict, blockers, residual risk | prose unsupported by structured evidence |

## Integrity and retention

1. Preserve the complete sanitized directory under the run-specific evidence
   root configured by the runtime.
2. Validate `checksums.json` before copying or publishing the report.
3. Keep the source SHA, runtime identity, registry hashes, tool receipts, and
   sanitization status together with the evidence.
4. Retain only according to repository policy; remove temporary client keys and
   continuity state separately after revocation.

The former qualification dossier is historical evidence under
`docs/validation/evidence-history/`; the stable pointer at
`docs/validation/runtime-security-assurance-qualification.md` preserves its
old discoverability without presenting it as the current procedure.

## Redaction contract

Private keys, session/bootstrap tokens, passwords, cookies, CSRF material,
Authorization headers, NATS/Tailscale credentials, recovery encryption
material, raw scanner secret matches, backup payloads, and PhotoPrism/user
media are never report content. Deliberately removed material is marked
`[REDACTED BY SECURITY ASSURANCE POLICY]`.
