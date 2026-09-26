from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_android_baseline_runner_repeats_existing_physical_matrix():
    runner = (ROOT / "scripts/dev/lite/run-ui-performance-android-baseline.sh").read_text(encoding="utf-8")
    assert 'LITE_ANDROID_BASELINE_REPETITIONS:-3' in runner
    assert 'repetitions < 3' in runner
    assert 'qualify-ui-performance-android-cdp.mjs' in runner
    assert 'baseline-before.json' in runner
    assert 'baseline-after.json' in runner
    assert 'device-state.json' in runner
    assert 'ui-performance-android-cdp-*.json' in runner


def test_android_baseline_control_is_exact_sha_candidate_surface():
    runner = (ROOT / "scripts/dev/lite/qualify-ui-performance-android-baseline.mjs").read_text(encoding="utf-8")
    assert '/__pocketlab_qualification__/baseline-control.html' in runner
    assert "x-pocket-lab-candidate-sha" in runner
    assert 'pocketlab-candidate-sha' in runner
    assert 'MINIMUM_FRAME_COUNT = 20' in runner
    assert 'candidate_control_verified: true' in runner
    assert 'existingCandidatePages' in runner
    assert 'baseline_foreground_renderer_unavailable' in runner
    assert 'receivesAnimationFrames' in runner
    assert "navigator.wakeLock.request('screen')" in runner
    assert 'baseline_screen_wake_lock_unavailable' in runner


def test_android_device_state_capture_is_bounded_and_sanitized():
    source = (ROOT / "scripts/dev/lite/capture-ui-performance-android-state.ps1").read_text(encoding="utf-8")
    assert "dumpsys', 'battery" in source
    assert "dumpsys', 'power" in source
    assert "dumpsys', 'thermalservice" in source
    assert "foreground_package" in source
    assert "battery_saver" in source
    assert "thermal_status" in source
    assert "peak_refresh_rate_hz" in source
    assert "sanitized = $true" in source
    assert "device_serial" not in source
    assert "Stdout =" not in source


def test_android_baseline_policy_keeps_absolute_contract_separate():
    policy = (ROOT / "src/performance/liteAndroidBaselinePolicy.js").read_text(encoding="utf-8")
    budget = (ROOT / "src/performance/litePerformanceBudget.js").read_text(encoding="utf-8")
    assert "PLATFORM_DOMINATED" in policy
    assert "APP_INCREMENTAL_COST" in policy
    assert "MIXED" in policy
    assert "INCONCLUSIVE" in policy
    assert "maxComparableP95DeltaMs" in policy
    assert "maxP95FrameMs: 20" in budget
    assert "maxP95FrameMs: 24" in budget


def test_android_baseline_entry_points_are_repository_owned():
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    scripts = package["scripts"]
    assert scripts["test:perf:android-baseline"] == "bash scripts/dev/lite/run-ui-performance-android-candidate.sh --baseline"
    assert scripts["analyze:perf:android-baseline"] == "bash scripts/dev/lite/analyze-ui-performance-android-baseline.sh"
    assert scripts["check:perf:android-baseline"] == "bash scripts/dev/lite/analyze-ui-performance-android-baseline.sh --fail-on-app-cost"
    taskfile = (ROOT / "tasks/Taskfile.lite.yml").read_text(encoding="utf-8")
    assert "lite:ui:perf:android:baseline:" in taskfile
    assert "lite:ui:perf:android:baseline:analyze:" in taskfile
    assert "lite:ui:perf:android:baseline:check:" in taskfile
