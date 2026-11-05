#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

repo_root="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$repo_root"

fail() {
  printf '[ui-performance-android-rules] ERROR: %s\n' "$*" >&2
  exit 1
}

need() {
  command -v "$1" >/dev/null 2>&1 || fail "Required command is not available: $1"
}

[[ "${1:-}" == "" ]] || fail 'Rules-only qualifier does not accept broad matrix options.'
for command_name in curl ip node npm powershell.exe python3 socat ss git; do
  need "$command_name"
done

if [[ -s "${NVM_DIR:-$HOME/.nvm}/nvm.sh" ]]; then
  # shellcheck disable=SC1090
  source "${NVM_DIR:-$HOME/.nvm}/nvm.sh"
  nvm use "${POCKETLAB_NODE_VERSION:-24.16.0}" >/dev/null 2>&1 || true
fi

source_commit="$(git rev-parse HEAD)"
[[ "$source_commit" =~ ^[0-9a-f]{40}$ ]] || fail 'The candidate source SHA is not exact.'
output_dir=".pocketlab-dev/performance/android-rules-${source_commit}"
candidate_process=''
candidate_owned=0
owned_socat_pid=''

cleanup() {
  set +e
  if [[ -n "$candidate_process" ]] && kill -0 "$candidate_process" 2>/dev/null; then
    kill "$candidate_process" 2>/dev/null || true
    wait "$candidate_process" 2>/dev/null || true
  fi
  if (( candidate_owned == 1 )); then
    powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass \
      -File scripts/dev/lite/prepare-ui-performance-android-candidate.ps1 -Cleanup >/dev/null 2>&1 || true
  fi
  if [[ -n "$owned_socat_pid" ]] && kill -0 "$owned_socat_pid" 2>/dev/null; then
    kill "$owned_socat_pid" 2>/dev/null || true
    wait "$owned_socat_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

candidate_state_probe="$(powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command '$path = Join-Path $env:LOCALAPPDATA "PocketLab\ui-performance-android-candidate.json"; if (Test-Path $path -PathType Leaf) { exit 1 } else { exit 0 }' 2>/dev/null; printf '%s' "$?")"
[[ "$candidate_state_probe" == "0" ]] || fail 'An existing Pocket Lab Android candidate state is present.'

printf '[ui-performance-android-rules] building exact source SHA %s\n' "$source_commit"
POCKETLAB_UI_PERF_CANDIDATE=1 \
VITE_POCKETLAB_UI_PERF_CANDIDATE=1 \
VITE_POCKETLAB_PERF_TEST=1 \
POCKETLAB_BUILD_ID="$source_commit" \
npm run build

mkdir -p "$output_dir"
python3 scripts/dev/lite/ui_performance_candidate_server.py --source-commit "$source_commit" >"$output_dir/candidate-server.log" 2>&1 &
candidate_process=$!
for _ in {1..240}; do
  if curl -fsS --connect-timeout 1 --max-time 2 \
      http://127.0.0.1:18765/__pocketlab_qualification__/candidate.json >/dev/null 2>&1; then
    break
  fi
  if ! kill -0 "$candidate_process" 2>/dev/null; then
    fail 'The candidate server exited before readiness.'
  fi
  sleep 0.25
done
curl -fsS --connect-timeout 1 --max-time 2 \
  http://127.0.0.1:18765/__pocketlab_qualification__/candidate.json >/dev/null \
  || fail 'The candidate server did not expose its exact-SHA manifest.'

candidate_owned=1
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass \
  -File scripts/dev/lite/prepare-ui-performance-android-candidate.ps1 -OpenCandidate

bridge_port="${POCKETLAB_ANDROID_CDP_BRIDGE_PORT:-19222}"
local_port="${POCKETLAB_ANDROID_CDP_LOCAL_PORT:-9222}"
windows_host="$(ip route | awk '/^default / {print $3; exit}')"
[[ -n "$windows_host" ]] || fail 'Could not determine the Windows host address.'
bridge_url="http://${windows_host}:${bridge_port}"
local_url="http://127.0.0.1:${local_port}"
curl -fsS --connect-timeout 3 --max-time 5 "$bridge_url/json/version" >/dev/null \
  || fail "Windows Android CDP bridge is not reachable at ${windows_host}:${bridge_port}."

if ! curl -fsS --connect-timeout 1 --max-time 2 "$local_url/json/version" >/dev/null 2>&1; then
  if ss -ltn 2>/dev/null | grep -Eq "127\.0\.0\.1:${local_port}[[:space:]]"; then
    fail "127.0.0.1:${local_port} is occupied by a non-CDP listener."
  fi
  nohup socat \
    "TCP-LISTEN:${local_port},bind=127.0.0.1,reuseaddr,fork" \
    "TCP:${windows_host}:${bridge_port}" \
    >"$output_dir/android-cdp-socat.log" 2>&1 &
  owned_socat_pid="$!"
  for _ in {1..20}; do
    if curl -fsS --connect-timeout 1 --max-time 2 "$local_url/json/version" >/dev/null 2>&1; then
      break
    fi
    sleep 0.25
  done
fi

version_json="$(curl -fsS --connect-timeout 3 --max-time 5 "$local_url/json/version")"
node - "$version_json" "$local_port" <<'NODE'
const payload = JSON.parse(process.argv[2]);
const port = Number(process.argv[3]);
if (payload['Android-Package'] !== 'com.android.chrome') throw new Error('local CDP endpoint is not Android Chrome');
const websocket = new URL(payload.webSocketDebuggerUrl);
if (!['127.0.0.1', 'localhost'].includes(websocket.hostname) || Number(websocket.port) !== port) throw new Error('CDP websocket is not looped back through WSL');
console.log('[ui-performance-android-rules] Android Chrome ' + (payload.Browser || 'version unknown') + ' via CDP ' + (payload['Protocol-Version'] || 'unknown'));
NODE

export LITE_ANDROID_CDP_URL="$local_url"
export LITE_BASE_URL='http://127.0.0.1:18765'
export LITE_PERF_SOURCE_COMMIT="$source_commit"
export LITE_ANDROID_RULES_OUTPUT_DIR="$output_dir"
export LITE_ANDROID_CDP_DEVICE_IDENTITY_VERIFIED=1
export LITE_ANDROID_CDP_BRIDGE_IDENTITY_VERIFIED=1
export LITE_ANDROID_CANDIDATE_REVERSE_VERIFIED=1
export LITE_ANDROID_RULES_ANONYMOUS_READ_ONLY=1

powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass \
  -File scripts/dev/lite/prepare-ui-performance-android-candidate.ps1 -Wake -OpenCandidate

windows_adb_script="$(wslpath -w "$repo_root/scripts/dev/lite/windows-adb.ps1")"
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass \
  -File scripts/dev/lite/prepare-ui-performance-android-candidate.ps1 -Wake -OpenCandidate

# Opening Chrome can restore the Android notification shade as the foreground
# window even after the bounded wake helper has cleared it. Reuse the
# repository-owned, fail-closed shade check after candidate activation so CDP
# foreground evidence is not mistaken for a renderable foreground surface.
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass \
  -Command ". '$windows_adb_script'; \$adb=Resolve-PocketLabWindowsAdb; \$records=@(Get-PocketLabAndroidDeviceRecords -AdbPath \$adb); \$device=Select-PocketLabAndroidDevice -Records \$records; \$result=Invoke-PocketLabWindowsAdb -AdbPath \$adb -Arguments @('-s',[string]\$device.Serial,'shell','wm','dismiss-keyguard'); if (\$result.ExitCode -ne 0) { throw 'android_keyguard_dismiss_failed' }; Clear-PocketLabAndroidNotificationShade -AdbPath \$adb -DeviceSerial \$device.Serial; \$windows=Invoke-PocketLabWindowsAdb -AdbPath \$adb -Arguments @('-s',\$device.Serial,'shell','dumpsys','window','displays'); if ([regex]::IsMatch([string]\$windows.Stdout,'(?m)^\s*mCurrentFocus=.*(?:Bouncer|Keyguard|NotificationShade)')) { throw 'android_keyguard_not_dismissed: Android keyguard or system shade remains foreground' }"

node scripts/dev/lite/qualify-ui-performance-android-rules.mjs
