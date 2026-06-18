#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'
SCRIPT_DIR="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/common.sh"
REPO="${POCKET_LAB_RELEASE_REPO:-dexter-lab-ctrl/pocket-lab}"
PWA_DIR="${PWA_DIR:-$POCKET_LAB_PWA_DIR}"
TMP_DIR="$TMP_ROOT/pwa_extract"
TMP_ZIP="$TMP_ROOT/dist.zip"

main() {
  SCRIPT_NAME="install-pwa-ui.sh"; acquire_lock "$SCRIPT_NAME"; ensure_root_dirs; require_cmd curl unzip
  ensure_dir_perm "$PWA_DIR" 755; rm -rf "$TMP_DIR"; mkdir -p "$TMP_DIR"
  log INFO "Querying GitHub latest release for $REPO"
  local url; url="$(curl -fsSL "https://api.github.com/repos/$REPO/releases/latest" | grep 'browser_download_url.*dist.zip' | head -1 | cut -d '"' -f 4 || true)"
  [[ -n "$url" ]] || die "Could not find dist.zip in latest release for $REPO"
  download_file "$url" "$TMP_ZIP"
  unzip -q -o "$TMP_ZIP" -d "$TMP_DIR"
  local src="$TMP_DIR"; [[ -d "$TMP_DIR/dist" ]] && src="$TMP_DIR/dist"
  [[ -f "$src/index.html" ]] || die "Downloaded UI artifact does not contain index.html"
  local backup
  backup="$PWA_DIR.previous.$(date -u +%Y%m%d%H%M%S)"
  if [[ -f "$PWA_DIR/index.html" ]]; then
    cp -a "$PWA_DIR" "$backup"
  fi
  if ! rsync -a --delete "$src/" "$PWA_DIR/" 2>/dev/null; then
    rm -rf "${PWA_DIR:?}/"*
    cp -a "$src/." "$PWA_DIR/"
  fi
  rm -rf "$TMP_DIR" "$TMP_ZIP"
  mark_done pwa_ui_ready
  log INFO "PWA UI assets installed atomically in $PWA_DIR"
}
main "$@"
