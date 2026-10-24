# README visual sources and qualification plan

This guide is scoped to the repository README; it is **not** a second Documentation Platform or an assertion of runtime qualification.

## Current visual inventory

| README image | Source | Evidence status |
| --- | --- | --- |
| Desktop and mobile hero | `docs/assets/brand/readme-hero-{desktop,mobile}.svg` | Original illustrative artwork, **not** actual telemetry |
| Architecture | `docs/assets/diagrams/readme-control-flow.svg` | Simplified representation of canonical architecture |
| Home desktop/mobile | `tests/e2e/lite-azure-horizon-visual.spec.ts-snapshots/black-{desktop,mobile}-mocked-*-linux.png` | Existing, mocked Playwright baseline; source-inspected, not live-qualified here |
| Apps | `tests/e2e/lite-azure-horizon-apps-visual.spec.ts-snapshots/apps-dark-catalog-1280-mocked-desktop-linux.png` | Existing mocked UI baseline |
| Devices | `tests/e2e/lite-visual-states.spec.ts-snapshots/devices-repairing-mocked-desktop-linux.png` | Existing mocked recovery-state baseline |
| Security | `tests/e2e/lite-visual-states.spec.ts-snapshots/security-action-needed-mocked-desktop-linux.png` | Existing mocked finding-state baseline |
| Recovery | `tests/e2e/lite-recovery-premium-visual.spec.ts-snapshots/recovery-premium-preview-ready-desktop-mocked-desktop-linux.png` | Existing mocked preview-state baseline |

The README references these **original committed baseline paths**. Do not copy/rename them to pretend they are live screenshots. Visual baselines show actual UI components supplied deterministic mock API data. Status labels and health values are scenario fixtures.

The current source tree also has Identity/Rules visual stories and baselines, but the README links to their capability docs rather than implying complete unrestricted workflows.

## Deferred capture and publication

- `tests/e2e/lite-readme-capture.spec.ts` implements a separate, explicitly opt-in capture of Home, Devices, Apps, Safety and Recovery at desktop/mobile widths using the mocked E2E harness.
- Never capture or publish a live browser session with credential forms, access tokens, host identities, private Tailnet values, LAN IPs, invite commands, photo libraries, raw logs or original media visible.
- Any future runtime-authenticated screenshot must be redacted and reviewed before entering the README. Keep new captures separate from test snapshots, with source SHA, scenario type, capture date, viewport, redaction review, and approval recorded.
- For a short workflow demo, record only after a dedicated review of Home → Devices → Apps → Manage → Action Details. Prefer a small, silent video with a poster still; do not publish synthetic operations as real outcomes.
- Real server-phone/browser captures, visual viewport review and GitHub light/dark rendering verification are **deferred**.
- No screenshot-generation, preview, tests, or quality gates were run while authoring this change.

## Later dedicated qualification (not executed)

```bash
task lite:readme:check
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q tests/docs/test_readme_contract.py
VITE_POCKETLAB_MOCKS=1 LITE_E2E_MODE=mocked npx playwright test tests/docs/readme-responsive.spec.ts --project=mocked-desktop
VITE_POCKETLAB_MOCKS=1 LITE_E2E_MODE=mocked POCKETLAB_README_CAPTURE=1 npx playwright test tests/e2e/lite-readme-capture.spec.ts --project=mocked-desktop
```

Captured files under `.pocketlab-dev/readme-captures/` are intentionally local and **not** published or auto-committed. Human sign-off is required before replacing any README reference with a new visual. Browser rendering at 320, 375, 430, 768, 1024, 1440 and 1920 pixels and both GitHub appearances remains an independent human qualification step. `<picture>` media selection and GitHub's sanitization behavior are not declared verified until that step.

## Claim authority

`contracts/metadata/readme-claims.json` is a bounded **publication inventory**, not a new documentation-status schema. It names existing source/code/doc paths and limitations. It does not modify generator fingerprints, the `uncommitted` sentinel, authoritative claim reconciliation, or the meaning of `verified`. Later checks guard that sources remain present and scoped; they do not confer runtime verification.
