#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'
SCRIPT_DIR="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/common.sh"

REPO="${POCKETLAB_LITE_RELEASE_REPO:-dexter-lab-ctrl/pocket-lab-lite}"
PWA_DIR="${PWA_DIR:-$POCKET_LAB_PWA_DIR}"
RELEASES_DIR="${POCKETLAB_LITE_PWA_RELEASES_DIR:-$PWA_DIR/releases}"
CURRENT_LINK="${POCKETLAB_LITE_PWA_CURRENT_LINK:-$PWA_DIR/current}"
TMP_DIR="$TMP_ROOT/pwa-release.$$"
LOCAL_DIST_ZIP="${POCKETLAB_LOCAL_DIST_ZIP:-${POCKET_LAB_LOCAL_DIST_ZIP:-}}"
RUNTIME_DIR="$(CDPATH='' cd -- "$SCRIPT_DIR/../../runtime" && pwd)"

download_https() {
  local url="$1" output="$2" max_bytes="$3"
  python3 - "$url" "$output" "$max_bytes" <<'PYDOWNLOAD'
import ipaddress, os, socket, sys, urllib.error, urllib.parse, urllib.request
from pathlib import Path
url, output, max_bytes = sys.argv[1], Path(sys.argv[2]), int(sys.argv[3])
allowed = {
    "api.github.com", "github.com", "objects.githubusercontent.com",
    "release-assets.githubusercontent.com", "github-releases.githubusercontent.com",
}
def allowed_host(host):
    host = (host or "").lower().rstrip(".")
    return host in allowed or host.endswith(".githubusercontent.com")
def validate(value):
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme.lower() != "https" or parsed.username or parsed.password or not allowed_host(parsed.hostname):
        raise SystemExit("Release URL rejected")
    try:
        for row in socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM):
            address = ipaddress.ip_address(row[4][0])
            if address.is_loopback or address.is_private or address.is_link_local or address.is_multicast or address.is_unspecified:
                raise SystemExit("Release URL resolved to a non-public address")
    except socket.gaierror as exc:
        raise SystemExit("Release host could not be resolved") from exc
    return parsed
class RestrictedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)
validate(url)
request = urllib.request.Request(url, headers={"Accept": "application/octet-stream,application/json", "User-Agent": "Pocket-Lab-Lite-Bootstrap"})
opener = urllib.request.build_opener(RestrictedRedirect())
try:
    with opener.open(request, timeout=90) as response, output.open("wb") as handle:
        validate(response.geturl())
        total = 0
        while True:
            block = response.read(min(1024 * 1024, max_bytes - total + 1))
            if not block:
                break
            total += len(block)
            if total > max_bytes:
                raise SystemExit("Release download exceeded the byte limit")
            handle.write(block)
        handle.flush()
        os.fsync(handle.fileno())
except (OSError, urllib.error.URLError) as exc:
    output.unlink(missing_ok=True)
    raise SystemExit("Release download failed") from exc
PYDOWNLOAD
}

safe_extract_pwa() {
  local archive="$1" destination="$2" release_mode="$3"
  PYTHONPATH="$RUNTIME_DIR${PYTHONPATH:+:$PYTHONPATH}" python3 - "$archive" "$destination" "$release_mode" <<'PYEXTRACT'
import sys
from pathlib import Path
from api_fastapi.services.lite_release_contract import inspect_pwa_archive, safe_extract_zip
archive, destination, release_mode = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3] == "release"
if release_mode:
    inspect_pwa_archive(archive)
safe_extract_zip(archive, destination)
PYEXTRACT
}

atomic_link() {
  local target="$1" link="$2" temp
  temp="$(dirname "$link")/.${link##*/}.next.$$"
  rm -f "$temp"
  ln -s "$(realpath --relative-to="$(dirname "$link")" "$target")" "$temp"
  mv -Tf "$temp" "$link"
}

resolve_remote_release() {
  local metadata="$1"
  python3 - "$metadata" <<'PY'
import datetime, json, re, sys, urllib.parse
path=sys.argv[1]
releases=json.load(open(path, encoding='utf-8'))
rx=re.compile(r'^lite-(\d{4})\.(\d{2})\.(\d{2})\.([1-9]\d*)$')
rows=[]
for release in releases if isinstance(releases, list) else []:
    if not isinstance(release, dict) or release.get('draft') or release.get('prerelease'):
        continue
    tag=str(release.get('tag_name') or '')
    m=rx.fullmatch(tag)
    if not m:
        continue
    y,mo,d,seq=map(int,m.groups())
    try: datetime.date(y,mo,d)
    except ValueError: continue
    assets={}
    duplicate=False
    for item in release.get('assets') or []:
        if not isinstance(item, dict): continue
        name=str(item.get('name') or '')
        if name in {'dist.zip','checksums.txt','pocketlab-lite-release.json'}:
            if name in assets: duplicate=True
            url=str(item.get('browser_download_url') or '')
            parsed=urllib.parse.urlparse(url)
            host=(parsed.hostname or '').lower()
            allowed=host in {'github.com','api.github.com','objects.githubusercontent.com','release-assets.githubusercontent.com','github-releases.githubusercontent.com'} or host.endswith('.githubusercontent.com')
            if parsed.scheme != 'https' or parsed.username or parsed.password or not allowed:
                duplicate=True
            assets[name]=url
    if duplicate or set(assets) != {'dist.zip','checksums.txt','pocketlab-lite-release.json'}:
        continue
    rows.append(((y,mo,d,seq),tag,assets))
if not rows:
    raise SystemExit('No valid Pocket Lab Lite release found')
_,tag,assets=max(rows,key=lambda row:row[0])
print(tag)
print(assets['dist.zip'])
print(assets['checksums.txt'])
print(assets['pocketlab-lite-release.json'])
PY
}

validate_manifest() {
  local tag="$1" manifest="$2" checksums="$3" archive="$4"
  python3 - "$tag" "$manifest" "$checksums" "$archive" <<'PY'
import hashlib, json, re, sys
from pathlib import Path
tag, manifest_path, checksums_path, archive_path=sys.argv[1:]
manifest=json.load(open(manifest_path, encoding='utf-8'))
if manifest.get('product') != 'pocket-lab-lite' or manifest.get('schema_version') != 1:
    raise SystemExit('Release manifest product/schema mismatch')
if manifest.get('release_tag') != tag or manifest.get('artifact') != 'dist.zip':
    raise SystemExit('Release manifest tag/artifact mismatch')
checks={}
for line in Path(checksums_path).read_text(encoding='utf-8').splitlines():
    parts=line.split()
    if len(parts)!=2: raise SystemExit('Invalid checksums.txt')
    checks[parts[1].lstrip('*')]=parts[0].lower()
observed=hashlib.sha256(Path(archive_path).read_bytes()).hexdigest()
if checks.get('dist.zip') != observed or manifest.get('artifact_sha256') != observed:
    raise SystemExit('Release checksum mismatch')
if not re.fullmatch(r'[0-9a-fA-F]{7,64}', str(manifest.get('source_commit') or '')):
    raise SystemExit('Release source commit invalid')
PY
}

cleanup_release_install() {
  rm -rf "$TMP_DIR"
  find "$RELEASES_DIR" -mindepth 1 -maxdepth 1 -type d -name ".*.preparing.$$" -exec rm -rf {} + 2>/dev/null || true
}

reconcile_existing_release_identity() {
  local tag="$1" manifest="$2" archive="$3" target="$4"
  [[ "$tag" == lite-* ]] || return 0
  [[ -f "$target/pocketlab-lite-build.json" ]] || die "Installed PWA release is missing embedded build identity"
  PYTHONPATH="$RUNTIME_DIR${PYTHONPATH:+:$PYTHONPATH}" python3 - \
    "$tag" "$manifest" "$archive" "$target/pocketlab-lite-build.json" <<'PYIDENTITY'
import hashlib
import json
import sys

from api_fastapi.services.release_runtime import initialize_release_runtime, record_release_install

tag, manifest_path, archive_path, build_path = sys.argv[1:]
manifest = json.load(open(manifest_path, encoding="utf-8"))
build = json.load(open(build_path, encoding="utf-8"))
artifact_sha256 = hashlib.sha256(open(archive_path, "rb").read()).hexdigest()

if build.get("product") != "pocket-lab-lite" or build.get("install_mode") != "release":
    raise SystemExit("Installed PWA release identity is invalid")
if build.get("release_tag") != tag or manifest.get("release_tag") != tag:
    raise SystemExit("Installed PWA release tag does not match verified assets")
if build.get("source_commit") != manifest.get("source_commit"):
    raise SystemExit("Installed PWA source commit does not match verified manifest")
if manifest.get("artifact_sha256") != artifact_sha256:
    raise SystemExit("Installed PWA artifact digest does not match verified manifest")

initialize_release_runtime()
identity = record_release_install(
    release_tag=tag,
    source_repository="dexter-lab-ctrl/pocket-lab-lite",
    source_commit=str(manifest.get("source_commit") or ""),
    artifact_sha256=artifact_sha256,
)
if (
    identity.get("install_mode") != "release"
    or identity.get("release_tag") != tag
    or identity.get("artifact_sha256") != artifact_sha256
    or not identity.get("verified")
):
    raise SystemExit("Pocket Lab Lite installed release identity was not reconciled")
PYIDENTITY
}

main() {
  SCRIPT_NAME="install-pwa-ui.sh"
  acquire_lock "$SCRIPT_NAME"
  trap cleanup_release_install EXIT
  ensure_root_dirs
  require_cmd python3
  REPO="$(PYTHONPATH="$RUNTIME_DIR${PYTHONPATH:+:$PYTHONPATH}" python3 - "$REPO" <<'PYREPO'
import sys
from api_fastapi.services.lite_release_contract import DEFAULT_REPOSITORY, normalize_repository
repository = normalize_repository(sys.argv[1])
if repository != DEFAULT_REPOSITORY:
    raise SystemExit("Pocket Lab Lite release repository mismatch")
print(repository)
PYREPO
)"
  mkdir -p "$PWA_DIR" "$RELEASES_DIR" "$TMP_DIR"
  chmod 700 "$RELEASES_DIR" "$TMP_DIR" 2>/dev/null || true

  local tag archive="$TMP_DIR/dist.zip" manifest="$TMP_DIR/pocketlab-lite-release.json" checksums="$TMP_DIR/checksums.txt"
  if [[ -n "$LOCAL_DIST_ZIP" ]]; then
    [[ -r "$LOCAL_DIST_ZIP" ]] || die "Local dist.zip is not readable"
    tag="source-bootstrap-$(date -u +%Y%m%d%H%M%S)"
    cp "$LOCAL_DIST_ZIP" "$archive"
  else
    local metadata="$TMP_DIR/releases.json" lines=()
    download_https "https://api.github.com/repos/$REPO/releases?per_page=100" "$metadata" 2097152
    mapfile -t lines < <(resolve_remote_release "$metadata")
    [[ ${#lines[@]} -eq 4 ]] || die "Could not resolve a valid Pocket Lab Lite release"
    tag="${lines[0]}"
    download_https "${lines[1]}" "$archive" 268435456
    download_https "${lines[2]}" "$checksums" 65536
    download_https "${lines[3]}" "$manifest" 65536
    validate_manifest "$tag" "$manifest" "$checksums" "$archive"
  fi

  local preparing="$RELEASES_DIR/.${tag}.preparing.$$" target="$RELEASES_DIR/$tag"
  rm -rf "$preparing"
  mkdir -p "$preparing"
  safe_extract_pwa "$archive" "$preparing" "$([[ "$tag" == lite-* ]] && echo release || echo source)"
  [[ -f "$preparing/index.html" ]] || die "PWA artifact is missing index.html"
  [[ -f "$preparing/manifest.webmanifest" ]] || die "PWA artifact is missing manifest.webmanifest"
  if [[ "$tag" == lite-* ]]; then
    [[ -f "$preparing/pocketlab-lite-build.json" ]] || die "PWA artifact is missing embedded build identity"
    python3 - "$tag" "$manifest" "$preparing/pocketlab-lite-build.json" <<'PY'
import json, sys
tag, manifest_path, build_path=sys.argv[1:]
manifest=json.load(open(manifest_path, encoding='utf-8'))
build=json.load(open(build_path, encoding='utf-8'))
if build.get('product') != 'pocket-lab-lite' or build.get('install_mode') != 'release' or build.get('release_tag') != tag:
    raise SystemExit('Embedded build identity mismatch')
if build.get('source_commit') != manifest.get('source_commit'):
    raise SystemExit('Embedded source commit mismatch')
PY
  else
    python3 - "$preparing/pocketlab-lite-build.json" "$tag" "$POCKET_LAB_BASE_DIR" <<'PYSOURCE'
import json, subprocess, sys
from pathlib import Path
output, tag, repository = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
commit = "unknown"
try:
    value = subprocess.run(["git", "-C", repository, "rev-parse", "HEAD"], check=False, capture_output=True, text=True, timeout=2).stdout.strip().lower()
    if value and all(ch in "0123456789abcdef" for ch in value) and 7 <= len(value) <= 64:
        commit = value
except (OSError, subprocess.SubprocessError):
    pass
output.write_text(json.dumps({"product":"pocket-lab-lite","schema_version":1,"install_mode":"source","release_tag":tag,"source_commit":commit,"target":"web-pwa"}, sort_keys=True, separators=(",", ":")), encoding="utf-8")
PYSOURCE
  fi
  if [[ ! -d "$target" ]]; then
    mv "$preparing" "$target"
  else
    # Release tags are immutable. Reuse only an existing target whose embedded
    # identity matches the newly verified manifest; otherwise fail closed.
    python3 - "$tag" "$manifest" "$target/pocketlab-lite-build.json" <<'PYREUSE'
import json
import sys

tag, manifest_path, build_path = sys.argv[1:]
manifest = json.load(open(manifest_path, encoding="utf-8"))
build = json.load(open(build_path, encoding="utf-8"))
if (
    build.get("product") != "pocket-lab-lite"
    or build.get("install_mode") != "release"
    or build.get("release_tag") != tag
    or build.get("source_commit") != manifest.get("source_commit")
):
    raise SystemExit("Existing PWA release target does not match verified release identity")
PYREUSE
    rm -rf "$preparing"
  fi
  atomic_link "$target" "$CURRENT_LINK"
  reconcile_existing_release_identity "$tag" "$manifest" "$archive" "$target"
  rm -rf "$TMP_DIR"
  mark_done pwa_ui_ready
  log INFO "Pocket Lab Lite PWA pointer is ready"
}
main "$@"
