from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SHARED = ROOT / "scripts/dev/lite/windows-adb.ps1"
CANDIDATE = ROOT / "scripts/dev/lite/prepare-ui-performance-android-candidate.ps1"
CANDIDATE_RUNNER = ROOT / "scripts/dev/lite/run-ui-performance-android-candidate.sh"
CDP = ROOT / "scripts/dev/lite/prepare-ui-performance-android-cdp.ps1"
ANDROID_QUALIFIER = ROOT / "scripts/dev/lite/qualify-ui-performance-android-cdp.mjs"


def test_windows_adb_resolver_is_deterministic_and_captures_console_output():
    source = SHARED.read_text(encoding="utf-8")

    assert "POCKETLAB_WINDOWS_ADB" in source
    assert "Get-Command adb.exe -All" in source
    assert "Android\\Sdk\\platform-tools\\adb.exe" in source
    assert "Downloads\\platform-tools-latest-windows\\platform-tools\\adb.exe" in source
    assert "Start-Process -FilePath $AdbPath" in source
    assert "-RedirectStandardOutput $stdoutPath" in source
    assert "-RedirectStandardError $stderrPath" in source
    assert "adb_transport_failed" in source


def test_candidate_helper_uses_shared_adb_and_reports_specific_device_states():
    source = CANDIDATE.read_text(encoding="utf-8")

    assert "windows-adb.ps1" in source
    assert "[string]$AdbPath = ''" in source
    assert "$env:POCKETLAB_WINDOWS_ADB = $AdbPath" in source
    assert "Resolve-PocketLabWindowsAdb" in source
    assert "Get-PocketLabAndroidDeviceRecords" in source
    assert "Select-PocketLabAndroidDevice" in source
    assert "no_android_device" in SHARED.read_text(encoding="utf-8")
    assert "android_device_unauthorized" in SHARED.read_text(encoding="utf-8")
    assert "android_device_offline" in SHARED.read_text(encoding="utf-8")
    assert "multiple_android_devices" in SHARED.read_text(encoding="utf-8")
    assert "requested_android_device_not_found" in SHARED.read_text(encoding="utf-8")
    assert "function Wake-PocketLabAndroidDevice" in SHARED.read_text(encoding="utf-8")
    assert "KEYCODE_WAKEUP" in SHARED.read_text(encoding="utf-8")
    assert "dumpsys" in SHARED.read_text(encoding="utf-8")
    assert "mWakefulness" in SHARED.read_text(encoding="utf-8")
    assert "KEYCODE_POWER" in SHARED.read_text(encoding="utf-8")
    assert "android_device_not_awake" in SHARED.read_text(encoding="utf-8")
    assert "function Open-PocketLabAndroidCandidate" in SHARED.read_text(encoding="utf-8")
    assert "$OpenCandidate" in source
    assert "$Wake" in source
    assert "-OpenCandidate" in CANDIDATE_RUNNER.read_text(encoding="utf-8")
    assert "-Wake" in Path("scripts/dev/lite/run-ui-performance-android-cdp.sh").read_text(encoding="utf-8")
    assert "-Wake -OpenCandidate" in Path("scripts/dev/lite/run-ui-performance-android-cdp.sh").read_text(encoding="utf-8")
    assert "Wake-PocketLabAndroidDevice" in source
    assert "& $adb" not in source


def test_cdp_helper_shares_adb_transport_and_does_not_use_path_only_lookup():
    source = CDP.read_text(encoding="utf-8")

    assert "windows-adb.ps1" in source
    assert "[string]$AdbPath = ''" in source
    assert "$env:POCKETLAB_WINDOWS_ADB = $AdbPath" in source
    assert "Resolve-PocketLabWindowsAdb" in source
    assert "Get-PocketLabAndroidDeviceRecords" in source
    assert "Invoke-PocketLabWindowsAdb" in source
    assert "Wake-PocketLabAndroidDevice" in source
    assert "Get-Command adb" not in source
    assert "& adb" not in source


def test_android_qualifier_proves_fresh_origin_and_foreground_renderer():
    source = ANDROID_QUALIFIER.read_text(encoding="utf-8")

    assert "pocketlab_qualification_bootstrap=1" in source
    assert "registration.unregister()" in source
    assert "caches.delete(cacheName)" in source
    assert "receivesAnimationFrames" in source
    assert "navigator.wakeLock.request('screen')" in source
    assert "browser.version()" in source
    assert "candidate_manifest_verified: true" in source
    assert "candidate_manifest_response_header_verified" in source
    assert "candidate_page_response_header_verified" in source
    assert "candidate_page_meta_verified" in source
    assert "rendering_surface: 'physical-android-chrome'" in source
    assert "data-lite-sw-update-ready" in source
    assert "removeQualificationUpdateNotice" in source
    assert "MAX_MINIMUM_FRAME_EXTENSION_MS" in source
    assert "MINIMUM_SAMPLER_INTERVAL_COUNT" in source
    assert "count()" in source
    assert "#recovery-manage-tab-history" in source
    assert "#recovery-manage-tab-restore" in source
    assert "recoveryHistoryTab.waitFor({ state: 'visible'" in source
    assert "firstVisibleOrNull" in source
    assert "UNAVAILABLE identity Manage Access" in source
    assert "UNAVAILABLE Rules Manage" in source
    assert "UNAVAILABLE Security finding details" in source
    assert "unavailableSurfaces" in source


def test_android_candidate_server_is_ready_before_chrome_is_opened():
    source = CANDIDATE_RUNNER.read_text(encoding="utf-8")
    assert "for _ in {1..240}; do" in source
    server_start = source.index("ui_performance_candidate_server.py")
    server_probe = source.index("candidate server did not expose its exact-SHA manifest")
    chrome_open = source.index("prepare-ui-performance-android-candidate.ps1 -OpenCandidate")
    assert server_start < server_probe < chrome_open
