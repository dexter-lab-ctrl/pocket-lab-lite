# Pocket Lab Lite UI Performance Qualification

## Status

**Implementation status:** repository-owned qualification tooling.

**Validation status:** the tooling must be run on the exact feature/PR head and, for production qualification, against a prepared live runtime and an actual Android Chromium rendering surface. Repository implementation alone does not prove that a particular phone sustains the target.

## Objective

Pocket Lab Lite targets smooth interaction on 60 Hz Android/Termux and low-power devices without redesigning the UI or moving execution into the browser.

The frame budget is:

- nominal 60 Hz frame budget: **16.67 ms**;
- target p95 frame interval: **20 ms or less**;
- target smooth-frame ratio: **95% or more at 20 ms**;
- target severe-frame ratio: **1% or less above 33.34 ms**;
- long-task target: **no task above 50 ms**;
- Long Animation Frame target when Chromium exposes LoAF: **no frame above 50 ms**;
- event-duration target: **200 ms or less**.

A slightly wider automated hard gate exists to keep CI and heterogeneous real-device runs from becoming flaky. Target misses are still recorded in evidence and must be reviewed for production qualification.

## Architecture boundary

Performance qualification does not change the Pocket Lab Lite control plane:

```text
React/Vite PWA
→ Caddy
→ FastAPI /api/lite/*
→ NATS/JetStream
→ worker/agent/supervisor
→ events/evidence
→ FastAPI
→ UI
```

The performance harness does not:

- execute shell commands from the frontend;
- talk directly to NATS;
- cache or emit backend secrets;
- submit Security checks;
- start backups or restores;
- restart agents;
- add/remove devices;
- activate Rules;
- change passwords;
- install/update/repair/remove apps;
- fake progress;
- add another animation framework.

## Qualification layers

### 1. Component/contract tests

Run:

```bash
npm run test:perf:components
```

This verifies the frame-budget math and source-level policy guards.

### 2. Deterministic mocked browser qualification

Run:

```bash
npm run test:perf:mocked
```

This exercises Home, Apps, Devices, Security, Identity & Access, Rules, Recovery, cross-tab navigation, and App Catalog Manage on both mocked desktop and mocked mobile Playwright projects.

Evidence is written under:

```text
.pocketlab-dev/performance/
```

The evidence contains only sanitized timing metadata.

### 3. Live runtime qualification

This verifies the real Pocket Lab Lite Caddy/FastAPI/runtime projection while the browser is controlled by Playwright.

Preconditions:

- the exact branch/commit is deployed;
- Caddy is healthy;
- FastAPI is healthy;
- the live PWA is reachable;
- no destructive qualification is in progress.

Run from the DEV-PC/WSL repo:

```bash
export LITE_E2E_LIVE=1
export LITE_BASE_URL='<prepared Pocket Lab Lite origin>'
bash scripts/dev/lite/run-ui-performance-live.sh
```

The live Playwright suite performs navigation and scrolling only. It must remain read-only.

**Important:** this layer measures the Playwright browser that is rendering the UI. If Playwright is running on the DEV-PC against a Server Phone backend, it proves live-backend UI behavior but not the Server Phone GPU/rendering performance.

### 4. Physical Android rendering qualification through Chrome DevTools Protocol

For a true physical-device render measurement, attach Playwright to Android Chrome over CDP.

A typical operator setup uses Android debugging to expose Chrome's DevTools socket to a loopback TCP port. The exact ADB/device preparation is environment-owned and intentionally not hardcoded in Pocket Lab Lite.

After the Android Chrome CDP endpoint is available:

```bash
export LITE_ANDROID_CDP_URL='http://127.0.0.1:<forwarded-cdp-port>'
export LITE_BASE_URL='<Pocket Lab Lite origin reachable by that Android Chrome>'
npm run test:perf:android-cdp
```

The repository script:

```text
scripts/dev/lite/qualify-ui-performance-android-cdp.mjs
```

connects to the existing Android Chrome instance, opens a separate temporary tab, checks all seven Lite screens, scrolls them, records requestAnimationFrame intervals, Long Task/Event Timing data when supported, writes sanitized evidence, closes only the temporary tab, and exits without invoking Pocket Lab write actions.

This is the preferred frame-rate qualification when the goal is to prove performance on the physical Android rendering hardware.

## Codex production-qualification workflow

Codex should:

1. resolve and record the exact Git SHA under qualification;
2. confirm the worktree/branch is the intended candidate;
3. run `npm run test:perf:components`;
4. run `npm run build:budget`;
5. run `npm run test:perf:mocked`;
6. verify the live runtime is healthy;
7. run the live read-only qualification;
8. when Android CDP is available, run the physical Android rendering qualification;
9. inspect every performance evidence file;
10. distinguish **hard-gate pass**, **target met**, and **target miss**;
11. record any browser/API limitation such as unsupported Long Task/Event Timing data;
12. never report 60 FPS qualification from a DEV-PC browser as proof of Android-device rendering performance.

## Validation commands

```bash
npm run test:perf:components
npm run build:budget
npm run test:perf:mocked
npm run test:a11y
npm run test:a11y:states
npm run test:visual
npm run test:visual:states
npm run test:visual:overlays
npm run test:content-stress
npm run test:e2e:mocked
task lite:check
```

Live runtime:

```bash
LITE_E2E_LIVE=1 LITE_BASE_URL='<origin>' bash scripts/dev/lite/run-ui-performance-live.sh
```

Physical Android renderer:

```bash
LITE_ANDROID_CDP_URL='http://127.0.0.1:<port>' \
LITE_BASE_URL='<origin>' \
npm run test:perf:android-cdp
```

## Expected evidence interpretation

A report contains:

- `p50_frame_ms`;
- `p95_frame_ms`;
- `max_frame_ms`;
- target and gate smooth-frame ratios;
- target and gate severe-frame ratios;
- long-task count/max duration;
- Long Animation Frame count/max duration when supported;
- maximum Event Timing duration when supported;
- `target_met`;
- `gate_passed`;
- explicit target misses/gate violations.

A hard-gate failure blocks UI performance qualification.

A hard-gate pass with target misses is **not** equivalent to meeting the 60 FPS target; it is a regression-safe result that still needs tuning or an explicitly documented device-specific exception.

## Rollback

The implementation is frontend/test tooling only. Rollback is the normal Git revert of the performance commits/PR. It does not require schema rollback, NATS migration, device re-enrollment, or backend state repair.
