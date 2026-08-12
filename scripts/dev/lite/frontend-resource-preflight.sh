#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd -P)"
PROFILE="${1:-mocked}"

cd "$REPO_ROOT"

validate_integer_range() {
  local name="$1"
  local value="$2"
  local minimum="$3"
  local maximum="$4"

  if [[ ! "$value" =~ ^[0-9]+$ ]]; then
    printf 'ERROR %s must be an integer; got %q\n' "$name" "$value" >&2
    return 2
  fi
  if (( value < minimum || value > maximum )); then
    printf 'ERROR %s must be between %s and %s; got %s\n' \
      "$name" "$minimum" "$maximum" "$value" >&2
    return 2
  fi
}

MIN_MEMORY_MIB="${POCKETLAB_FRONTEND_MIN_MEMORY_MIB:-2048}"
MIN_SCRATCH_GIB="${POCKETLAB_FRONTEND_MIN_SCRATCH_GIB:-5}"
validate_integer_range POCKETLAB_FRONTEND_MIN_MEMORY_MIB "$MIN_MEMORY_MIB" 1024 6144
validate_integer_range POCKETLAB_FRONTEND_MIN_SCRATCH_GIB "$MIN_SCRATCH_GIB" 1 100

PLAYWRIGHT_SCRATCH="$(bash "$SCRIPT_DIR/dev-scratch.sh" path playwright)"
mkdir -p "$PLAYWRIGHT_SCRATCH"

mem_available_kib="$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)"
mem_available_mib="$((mem_available_kib / 1024))"
if (( mem_available_mib < MIN_MEMORY_MIB )); then
  printf 'ERROR frontend preflight: available memory is %s MiB; require at least %s MiB\n' \
    "$mem_available_mib" "$MIN_MEMORY_MIB" >&2
  printf 'INFO close heavy scanners/builds or restart WSL before retrying; no cleanup was performed\n' >&2
  exit 2
fi

scratch_free_kib="$(df -Pk "$PLAYWRIGHT_SCRATCH" | awk 'NR==2 {print $4}')"
scratch_free_gib="$((scratch_free_kib / 1024 / 1024))"
if (( scratch_free_gib < MIN_SCRATCH_GIB )); then
  printf 'ERROR frontend preflight: Playwright scratch has %s GiB free; require at least %s GiB\n' \
    "$scratch_free_gib" "$MIN_SCRATCH_GIB" >&2
  exit 2
fi

printf 'PASS frontend resource preflight profile=%s\n' "$PROFILE"
printf 'PASS available memory: %s MiB\n' "$mem_available_mib"
printf 'PASS Playwright scratch: %s\n' "$PLAYWRIGHT_SCRATCH"
printf 'PASS Playwright scratch free: %s GiB\n' "$scratch_free_gib"
printf 'PASS Playwright scratch filesystem: %s\n' "$(df -P "$PLAYWRIGHT_SCRATCH" | awk 'NR==2 {print $1}')"

if [[ -n "${NODE_OPTIONS:-}" ]] && [[ "$NODE_OPTIONS" == *"--max-old-space-size"* ]]; then
  printf 'WARN NODE_OPTIONS contains a max-old-space-size override; Pocket Lab does not require or set a global frontend heap override\n' >&2
fi

stale_scancode=()
while IFS= read -r path; do
  stale_scancode+=("$path")
done < <(
  find .pocketlab-dev/tmp \
    -maxdepth 1 \
    -mindepth 1 \
    -type d \
    -name 'scancode-*' \
    -print 2>/dev/null \
    | sort
)
if (( ${#stale_scancode[@]} > 0 )); then
  printf 'WARN found %s ScanCode scratch director%s under .pocketlab-dev/tmp; these are not frontend inputs and are ignored by Vite/VS Code\n' \
    "${#stale_scancode[@]}" "$([[ ${#stale_scancode[@]} -eq 1 ]] && printf 'y' || printf 'ies')" >&2
  printf 'WARN cleanup is intentionally manual; verify no scanner is running before removing stale scratch\n' >&2
fi

if command -v ss >/dev/null 2>&1 && ss -ltnH 'sport = :5173' 2>/dev/null | grep -q .; then
  printf 'INFO port 5173 is already listening; Playwright may reuse an existing compatible Vite server\n'
fi
