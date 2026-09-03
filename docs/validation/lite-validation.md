# Lite Validation

Pocket Lab Lite keeps the core Pocket Lab control-plane model while reducing the default runtime footprint. Validation should prove that the Lite API, Lite UI, Lite bootstrap profile, and documentation build remain healthy without starting the heavyweight observability stack by default.

## What is validated

The Lite validation path checks:

- FastAPI imports and readiness routes;
- `/api/lite/*` read endpoints;
- fail-closed behavior for unsupported or risky Lite actions;
- `--profile lite` and `--lite` bootstrap selection;
- Lite bootstrap dry-run behavior;
- frontend production build;
- MkDocs strict build.

## Lite bootstrap checks

Run:

```bash
bash scripts/dev/check-lite-bootstrap.sh
```

Expected result:

```text
Bootstrap script syntax checks passed
Lite bootstrap profile checks passed
```

The check confirms that `install_proot_ubuntu` is skipped in Lite profile planning and that `--lite` selects `Profile: lite`.

## Lite API checks

Run:

```bash
bash scripts/dev/check-lite-api.sh
```

Expected result:

```text
Lite API checks passed
```

This uses the FastAPI test client. It does not require a live Android device or running NATS service.

## Full Lite local validation

Run:

```bash
task lite:check
```

or, without Taskfile:

```bash
bash scripts/dev/check-lite.sh
```

Expected result:

```text
Pocket Lab Lite validation passed
```

## Mocked UI/UX production regression coverage

The deterministic mocked regression layer complements the canonical healthy whole-tab screenshots and Phase 9 qualification. It does not replace live/runtime or physical-device qualification.

Run focused suites with:

```bash
npm run build-storybook
npm run test:phase9:qualification
npm run test:a11y
npm run test:a11y:states
npm run test:content-stress
npm run test:visual
npm run test:visual:states
npm run test:visual:overlays
```

Run the aggregate mocked regression set with:

```bash
npm run test:mock-regression
```

The additional suites cover representative high-risk states, responsive Manage/details surfaces, attention/error accessibility, a scoped color-contrast pilot, long-copy/content-density stress, exact small-screen viewports, and 200% root-text stress. The canonical `test:visual` suite remains the healthy whole-tab baseline and intentionally closes transient overlays before capture.

### Visual baseline acceptance discipline

Do not accept a screenshot only because `--update-snapshots` makes the test pass. Use this sequence for every new or changed baseline:

1. Run the functional/state test first and require it to pass.
2. Inspect the generated actual image and relevant diff image.
3. Decide whether every visible change is intended and truthful to the mocked state.
4. Update the baseline only when the visual change is intended.
5. Rerun the same test without `--update-snapshots`.
6. Require the clean rerun to pass before the baseline is considered accepted.

For example:

```bash
npm run test:visual:states -- --update-snapshots
npm run test:visual:states

npm run test:visual:overlays -- --update-snapshots
npm run test:visual:overlays
```

Never loosen screenshot tolerances merely to accept an unexplained difference. Current state/overlay suites use the same `maxDiffPixelRatio: 0.02` standard as the canonical Lite visual suite.

The global serious/critical Axe gate continues to keep `color-contrast` disabled to avoid changing an established gate without evidence. `test:a11y:states` separately enables `color-contrast` for a scoped Manage-surface pilot so contrast findings can be addressed deliberately rather than hidden by global noise.

## Manual runtime validation on Android / Termux

After the Lite bootstrap profile is ready on a device, validate with:

```bash
cd ~/pocket-lab-lite/pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched
bash scripts/bootstrap.sh --profile lite --list
bash scripts/bootstrap.sh --profile lite
curl -s http://127.0.0.1:8080/health
curl -s http://127.0.0.1:8080/ready
curl -s http://127.0.0.1:8080/api/lite/status
pm2 status
```

In Lite mode, PM2 should not show the heavyweight observability services:

```text
pocket-gatus
loki-kms
promtail-agent
prometheus-db
grafana-ui
```

## Validation boundaries

These checks validate local source, contracts, frontend build, docs, and dry-run bootstrap behavior. Mocked UI/UX regression checks validate deterministic browser presentation only. They do not prove live Android service startup, physical-device interaction, real WebAuthn ceremonies, live Security scans, live Recovery work, or live Rules mutation until those are separately qualified in the appropriate environment.
