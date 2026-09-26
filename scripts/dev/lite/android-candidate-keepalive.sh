#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

repo_root="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$repo_root"

interval_seconds="${POCKETLAB_ANDROID_ACTIVITY_PULSE_INTERVAL_SECONDS:-0.8}"
case "$interval_seconds" in
  ''|*[!0-9.]*|0) exit 2 ;;
esac

while :; do
  powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass \
    -File scripts/dev/lite/prepare-ui-performance-android-candidate.ps1 -ActivityPulse \
    >/dev/null 2>&1
  sleep "$interval_seconds"
done
