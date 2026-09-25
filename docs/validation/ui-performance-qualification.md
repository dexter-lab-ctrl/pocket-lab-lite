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

This exercises Home, Apps, Devices, Security, Identity & Access, Rules, Recovery, continuous active scrolling, cross-tab navigation, Home refresh feedback, and every tab's existing Manage surface on both mocked desktop and mocked mobile Playwright projects.

Mocked runs also require opt-in React Profiler evidence and enforce the declared React commit hard gate. Frame evidence is sampled during active work rather than padded with long idle windows.

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

A typical operator setup uses Android debugging to expose Chrome's DevTools socket to a loopback TCP port. The exact device serial, WSL addresses, Tailnet hostname, and other environment-specific values remain operator-owned and are never hardcoded in Pocket Lab Lite.

For Windows 10 + WSL2 DEV-PC qualification, the repository owns two helpers:

```text
scripts/dev/lite/prepare-ui-performance-android-cdp.ps1
scripts/dev/lite/run-ui-performance-android-cdp.sh
```

The elevated Windows PowerShell helper:

- discovers exactly one authorized Android device unless `-DeviceSerial` is supplied;
- requires Google Chrome to be running in a normal, non-Incognito window;
- discovers the active `chrome_devtools_remote` abstract socket;
- maintains the ADB forward on Windows loopback;
- discovers the current WSL2 gateway and IPv4 address;
- maintains only Pocket Lab's recorded Windows `portproxy` rule;
- restricts the Windows Firewall rule to the current WSL2 address;
- verifies that WSL can read Android Chrome's CDP version endpoint.

Run it from an elevated Windows PowerShell:

```powershell
& '<repo>\scripts\dev\lite\prepare-ui-performance-android-cdp.ps1'
```

The WSL runner discovers the Windows host, verifies the Windows bridge, starts a temporary loopback-only `socat` relay on `127.0.0.1:9222` when needed, checks that the advertised CDP WebSocket loops back through that local port, verifies `chromium.connectOverCDP()`, performs a read-only Pocket Lab Home smoke test when `LITE_BASE_URL` is set, records the exact source commit, then runs the physical qualifier.

Connectivity-only check:

```bash
export LITE_BASE_URL='<Pocket Lab Lite origin reachable by Android Chrome>'
npm run check:perf:android-cdp
```

Physical qualification:

```bash
export LITE_BASE_URL='<Pocket Lab Lite origin reachable by Android Chrome>'
npm run test:perf:android-cdp
```

`LITE_ANDROID_CDP_URL` is set by the WSL runner to its loopback-only relay. The optional environment variables `POCKETLAB_ANDROID_CDP_BRIDGE_PORT` and `POCKETLAB_ANDROID_CDP_LOCAL_PORT` override the default bridge and local ports when a DEV-PC has a legitimate port conflict.

The repository script:

```text
scripts/dev/lite/qualify-ui-performance-android-cdp.mjs
```

connects to the existing Android Chrome instance, opens a separate temporary tab, exercises all declared Phase 4 interaction IDs across real physical Android rendering surfaces, records requestAnimationFrame intervals plus Long Task, Long Animation Frame, and Event Timing data when supported, writes sanitized evidence, closes only the temporary tab, and exits without invoking Pocket Lab write actions. Write-dependent progress/toast semantics remain covered deterministically in mocked qualification; the physical runner maps those IDs onto truthful read-only transient feedback and records the exact interaction surface in evidence.

This is the preferred frame-rate qualification when the goal is to prove performance on the physical Android rendering hardware.


### 5. Baseline-normalized Android attribution

Absolute 60 FPS targets remain authoritative, but physical Android Chrome can add scheduler, compositor, thermal, refresh-rate, or DevTools cadence that is not caused by Pocket Lab UI work. Baseline normalization is an attribution layer; it never turns an absolute target or hard-gate miss into a pass.

The repository-owned baseline investigation reuses the complete physical Android interaction matrix instead of maintaining a second selector matrix. It runs the existing physical qualifier at least three times and surrounds every full matrix run with repeated measurements of a static, exact-SHA-bound control page served by the same candidate server and rendered by the same Android Chrome process.

Run the complete exact-SHA candidate investigation:

```bash
npm run test:perf:android-baseline
```

The runner records raw repeated runs under:

```text
.pocketlab-dev/android-performance-baseline/<source-commit>/
```

Each repetition contains:

- a three-sample static platform control before the interaction matrix;
- one complete existing physical Android interaction matrix;
- a three-sample static platform control after the interaction matrix;
- a sanitized Android device-state snapshot;
- the exact source commit.

The static control is:

```text
/__pocketlab_qualification__/baseline-control.html
```

It is generated by the candidate server, contains no script, API request, harness credential, backend secret, or NATS path, and carries the same candidate SHA response/meta proof as the application candidate.

Device-state capture is bounded to normalized fields such as screen state, foreground package, battery-saver state, battery level/plug state, thermal status when Android exposes it, configured refresh-rate bounds, and Android version. Raw `dumpsys` output and the device serial are not written into performance evidence.

Re-analyze an existing raw run without touching the phone:

```bash
npm run analyze:perf:android-baseline
```

Fail specifically when repeated evidence shows material application incremental cost:

```bash
npm run check:perf:android-baseline
```

The normalization policy is source-owned in:

```text
src/performance/liteAndroidBaselinePolicy.js
```

It compares repeated interaction samples with repeated contemporaneous controls and classifies each interaction as:

- `WITHIN_BASELINE` — absolute behavior is comparable to a healthy platform control;
- `PLATFORM_DOMINATED` — the platform control already misses the absolute target and the app adds no material delta;
- `APP_INCREMENTAL_COST` — the platform control is healthy but the app adds a material p95/smooth/severe/Long Task/LoAF delta;
- `MIXED` — both the platform baseline and application delta materially contribute;
- `INCONCLUSIVE` — there are fewer than the required repeated samples.

The comparison thresholds are attribution thresholds only. They do not replace or relax the existing 20 ms production p95 target, 24 ms hard p95 gate, smooth/severe frame requirements, Long Task limit, LoAF limit, Event Timing limit, or React commit budgets.

Normalized per-interaction evidence is written back to `.pocketlab-dev/performance/` with both absolute and baseline-relative fields, including:

- `repetition_count`;
- `platform_baseline_sample_count`;
- `platform_baseline`;
- `interaction_summary`;
- `baseline_delta`;
- `baseline_classification`;
- `baseline_reasons`;
- `device_state_samples`;
- absolute `target_met` / `target_misses`;
- absolute `gate_passed` / `gate_violations`.

The baseline summary is deliberately named `android-baseline-summary.json` rather than `ui-performance-*.json` because it is an aggregate report, not an individual interaction record.


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
npm run test:perf:interactions
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
LITE_BASE_URL='<origin reachable by Android Chrome>' npm run check:perf:android-cdp
LITE_BASE_URL='<origin reachable by Android Chrome>' npm run test:perf:android-cdp
npm run test:perf:android-baseline
npm run analyze:perf:android-baseline
npm run check:perf:android-baseline
```

Windows bridge cleanup, when explicitly desired:

```powershell
& '<repo>\scripts\dev\lite\prepare-ui-performance-android-cdp.ps1' -Cleanup
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
- baseline classification and baseline-relative deltas;
- repeated control/interaction sample counts;
- sanitized Android device-state samples for physical baseline runs.

A hard-gate failure blocks UI performance qualification.

A hard-gate pass with target misses is **not** equivalent to meeting the 60 FPS target; it is a regression-safe result that still needs tuning or an explicitly documented device-specific exception.

## Rollback

The implementation is frontend/test tooling only. Rollback is the normal Git revert of the performance commits/PR. It does not require schema rollback, NATS migration, device re-enrollment, or backend state repair.
