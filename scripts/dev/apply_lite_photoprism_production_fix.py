#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path.cwd()


def p(rel: str) -> Path:
    return ROOT / rel


def read(rel: str) -> str:
    path = p(rel)
    if not path.exists():
        raise SystemExit(f"Missing expected file: {rel}")
    return path.read_text()


def write(rel: str, content: str, executable: bool = False) -> None:
    path = p(rel)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    if executable:
        path.chmod(0o755)


def replace_one_line_function(content: str, name: str, replacement: str) -> str:
    lines = content.splitlines()
    out: list[str] = []
    replaced = False
    i = 0
    while i < len(lines):
        stripped = lines[i].lstrip()
        if not replaced and stripped.startswith(f"{name}(){{"):
            # Current source has these helpers as compact one-line functions.
            # If a previous hotfix made them multi-line, replace through the
            # first standalone closing brace after the function header.
            if lines[i].rstrip().endswith("}") and lines[i].count("{") <= lines[i].count("}"):
                out.extend(replacement.splitlines())
                i += 1
                replaced = True
                continue
            out.extend(replacement.splitlines())
            i += 1
            while i < len(lines) and lines[i].strip() != "}":
                i += 1
            if i < len(lines):
                i += 1
            replaced = True
            continue
        out.append(lines[i])
        i += 1
    if not replaced and replacement not in content:
        raise SystemExit(f"Could not patch {name}()")
    return "\n".join(out) + ("\n" if content.endswith("\n") else "")


def replace_main_function(content: str, replacement: str) -> str:
    lines = content.splitlines()
    start = None
    call = None
    for idx, line in enumerate(lines):
        if line.strip() == "main(){":
            start = idx
        if line.strip() == 'main "$@"':
            call = idx
            break
    if start is None or call is None or call <= start:
        if "PhotoPrism is already running" in content:
            return content
        raise SystemExit("Could not locate PhotoPrism main() block")
    new_lines = lines[:start] + replacement.splitlines() + lines[call:]
    return "\n".join(new_lines) + ("\n" if content.endswith("\n") else "")


def ensure_router_import(content: str) -> str:
    if "lite_catalog_live" in content:
        return content
    pattern = re.compile(r"from \.\.services import ([^\n]+)")
    match = pattern.search(content)
    if not match:
        raise SystemExit("Could not find lite router services import")
    modules = [part.strip() for part in match.group(1).split(",")]
    if "lite_catalog_live" not in modules:
        modules.append("lite_catalog_live")
    replacement = "from ..services import " + ", ".join(modules)
    return content[: match.start()] + replacement + content[match.end() :]


def patch_installer() -> None:
    rel = "pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/lite/install-photoprism-proot.sh"
    content = read(rel)

    content = content.replace(
        'curl -fsS "http://127.0.0.1:2342/api/v1/status" >/dev/null 2>&1',
        'curl -fsS "http://127.0.0.1:2342/apps/photoprism/api/v1/status" >/dev/null 2>&1',
    )
    content = content.replace(
        'curl -fsS "http://127.0.0.1:2342/" >/dev/null 2>&1',
        'curl -fsS "http://127.0.0.1:2342/apps/photoprism/" >/dev/null 2>&1',
    )

    content = replace_one_line_function(
        content,
        "refresh_caddy_if_possible",
        '''refresh_caddy_if_possible(){
  local helper="$SCRIPT_DIR/restart-caddy-proxy.sh"
  if [[ -x "$helper" ]]; then
    "$helper" || log WARN "Caddy route refresh did not complete; PhotoPrism local health will still be checked"
    return 0
  fi

  require_cmd pm2
  require_cmd caddy
  caddy validate --config "$HOME/pocket-lab-lite/caddy/Caddyfile" >/dev/null 2>&1 || {
    log WARN "Caddyfile validation failed; PhotoPrism local health will still be checked"
    return 0
  }
  pm2 delete caddy-proxy >/dev/null 2>&1 || true
  pm2 start "$(command -v caddy)" --name caddy-proxy -- run --config "$HOME/pocket-lab-lite/caddy/Caddyfile" >/dev/null 2>&1 || {
    log WARN "Caddy route refresh did not complete; PhotoPrism local health will still be checked"
    return 0
  }
  sleep 3
}''',
    )

    content = replace_one_line_function(
        content,
        "wait_for_local_health",
        '''wait_for_local_health(){
  for _ in $(seq 1 90); do
    curl -fsS "http://127.0.0.1:2342/apps/photoprism/api/v1/status" >/dev/null 2>&1 && return 0
    curl -fsS "http://127.0.0.1:2342/apps/photoprism/" >/dev/null 2>&1 && return 0
    sleep 2
  done
  return 1
}''',
    )

    content = replace_one_line_function(
        content,
        "check_route_health",
        '''check_route_health(){
  if curl -fsS "http://127.0.0.1:8443/apps/photoprism/api/v1/status" >/dev/null 2>&1; then
    echo healthy
    return 0
  fi
  if curl -fsS "http://127.0.0.1:8443/apps/photoprism/" >/dev/null 2>&1; then
    echo healthy
    return 0
  fi
  [[ -z "$SECURE_ORIGIN" ]] && { echo unknown; return 0; }
  curl -fsS "$SECURE_ORIGIN$ROUTE_PATH" >/dev/null 2>&1 && echo healthy || echo unknown
}''',
    )

    content = replace_main_function(
        content,
        '''main(){
  [[ "$APP_ID" == "photoprism" ]] || fail_safe "Unsupported Lite app requested."
  require_termux
  require_cmd python3 curl tar

  local url version route_health
  url="$(arch_package_url)" || fail_safe "PhotoPrism package is not available for this architecture."

  if curl -fsS "http://127.0.0.1:2342/apps/photoprism/api/v1/status" >/dev/null 2>&1; then
    ensure_env_file
    write_route_registry
    refresh_caddy_if_possible
    wait_for_local_health || fail_safe "PhotoPrism did not pass local health checks after startup."
    version="$(photoprism_version)"
    route_health="$(check_route_health)"
    mark_route_health "$route_health"
    write_summary "succeeded" "PhotoPrism is ready." "${version:-detected-or-unknown}" "healthy" "$route_health"
    log INFO "PhotoPrism is already running. Credentials remain stored only on the server host."
    return 0
  fi

  ensure_ubuntu_ready
  install_photoprism_inside_ubuntu "$url"
  ensure_env_file
  write_route_registry
  start_photoprism_pm2
  refresh_caddy_if_possible
  wait_for_local_health || fail_safe "PhotoPrism did not pass local health checks after startup."

  version="$(photoprism_version)"
  route_health="$(check_route_health)"
  mark_route_health "$route_health"
  write_summary "succeeded" "PhotoPrism is ready." "${version:-detected-or-unknown}" "healthy" "$route_health"
  log INFO "PhotoPrism is ready. Credentials remain stored only on the server host."
}''',
    )

    write(rel, content, executable=True)


def patch_restart_helper() -> None:
    write(
        "pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/lite/restart-caddy-proxy.sh",
        '''#!/usr/bin/env bash
set -Eeuo pipefail

CADDYFILE="${POCKETLAB_CADDYFILE:-$HOME/pocket-lab-lite/caddy/Caddyfile}"

log() {
  printf '[%s] [restart-caddy-proxy] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >&2
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    log "Missing required command: $1"
    exit 1
  }
}

require_cmd python3
require_cmd caddy
require_cmd pm2

python3 - <<PY2
from pathlib import Path

p = Path("$CADDYFILE")
if not p.exists():
    raise SystemExit(f"Caddyfile not found: {p}")

s = p.read_text()
s = s.replace("handle_path /apps/photoprism/* {", "handle /apps/photoprism/* {")
p.write_text(s)
PY2

caddy validate --config "$CADDYFILE" >/dev/null
pm2 delete caddy-proxy >/dev/null 2>&1 || true
pm2 start "$(command -v caddy)" --name caddy-proxy -- run --config "$CADDYFILE" >/dev/null
sleep 3
curl -fsS http://127.0.0.1:8443/api/lite/catalog >/dev/null || {
  log "Caddy started but Lite API route is not reachable on 127.0.0.1:8443"
  exit 1
}
log "Caddy proxy is healthy on 127.0.0.1:8443"
''',
        executable=True,
    )


def patch_start_dashboard() -> None:
    rel = "pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/start-dashboard.sh"
    content = read(rel)
    content = content.replace("handle_path /apps/photoprism/* {", "handle /apps/photoprism/* {")
    content = content.replace('print(f"  handle_path {path}* {{")', 'print(f"  handle {path}* {{")')
    content = content.replace(
        'pm2_start_or_restart caddy-proxy caddy -- run --config "$CADDYFILE"',
        'pm2_start_or_restart caddy-proxy "$(command -v caddy)" -- run --config "$CADDYFILE"',
    )
    write(rel, content, executable=True)


def patch_backend() -> None:
    write(
        "pocket-lab-final-structure/runtime/api_fastapi/services/lite_catalog_live.py",
        '''from __future__ import annotations

import copy
import json
import urllib.request
from typing import Any


PHOTOPRISM_ROUTE = "/apps/photoprism/"
PHOTOPRISM_STATUS_URL = "http://127.0.0.1:8443/apps/photoprism/api/v1/status"


def _url_json_healthy(url: str, *, timeout: float = 1.5) -> bool:
    try:
        request = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = int(getattr(response, "status", response.getcode()))
            if status < 200 or status >= 400:
                return False
            body = response.read(1024)
            payload = json.loads(body.decode("utf-8", errors="replace"))
            return payload.get("status") in {"operational", "healthy", "ok"}
    except Exception:
        return False


def _is_photoprism_ready(app: dict[str, Any]) -> bool:
    runtime = app.get("runtime") if isinstance(app.get("runtime"), dict) else {}
    return (
        app.get("id") == "photoprism"
        and (
            app.get("status") == "ready"
            or app.get("install_state") == "installed"
            or app.get("installed") is True
        )
        and runtime.get("health") == "healthy"
    )


def _hydrate_photoprism(app: dict[str, Any], *, route_ready: bool) -> None:
    if not _is_photoprism_ready(app):
        return
    runtime = app.setdefault("runtime", {})
    access = app.setdefault("access", {})
    actions = app.setdefault("actions", {})
    runtime["route"] = runtime.get("route") or PHOTOPRISM_ROUTE
    if route_ready:
        runtime["url"] = PHOTOPRISM_ROUTE
        access["route_ready"] = True
        access["open_url"] = PHOTOPRISM_ROUTE
        access["message"] = "Open is ready."
        actions["open"] = True
    else:
        access["route_ready"] = False
        access["open_url"] = None
        access["message"] = "Open is not ready yet."
        actions["open"] = False


def hydrate_catalog(payload: dict[str, Any]) -> dict[str, Any]:
    hydrated = copy.deepcopy(payload)
    route_ready = _url_json_healthy(PHOTOPRISM_STATUS_URL)
    for key in ("apps", "items"):
        apps = hydrated.get(key)
        if not isinstance(apps, list):
            continue
        for app in apps:
            if isinstance(app, dict):
                _hydrate_photoprism(app, route_ready=route_ready)
    return hydrated
''',
    )

    rel = "pocket-lab-final-structure/runtime/api_fastapi/services/lite_status.py"
    content = read(rel)
    content = re.sub(
        r"\n# ---- Pocket Lab Lite live App Catalog route hydration ----.*?# ---- End Pocket Lab Lite live App Catalog route hydration ----\n",
        "\n",
        content,
        flags=re.S,
    )
    write(rel, content)

    rel = "pocket-lab-final-structure/runtime/api_fastapi/routers/lite.py"
    content = read(rel)
    content = ensure_router_import(content)
    content = content.replace(
        "return lite_catalog.catalog_payload(request)",
        "return lite_catalog_live.hydrate_catalog(lite_catalog.catalog_payload(request))",
    )
    content = content.replace(
        "return lite_status.lite_catalog()",
        "return lite_catalog_live.hydrate_catalog(lite_status.lite_catalog())",
    )
    if "lite_catalog_live.hydrate_catalog" not in content:
        raise SystemExit("Could not patch Lite catalog route return")
    write(rel, content)


def patch_vite() -> None:
    rel = "vite.config.js"
    content = read(rel)
    if "/^\\/apps\\//" not in content:
        content = re.sub(
            r"navigateFallbackDenylist:\s*\[([^\]]*)\]",
            lambda m: "navigateFallbackDenylist: [" + m.group(1).rstrip() + ", /^\\/apps\\//, /^\\/gitea\\//, /^\\/docs/, /^\\/openapi\\.json/]",
            content,
            count=1,
        )
    if "/^\\/apps\\//" not in content:
        raise SystemExit("Could not patch Vite PWA navigation denylist")
    write(rel, content)


def patch_lite_catalog() -> None:
    rel = "src/lite/LiteCatalog.jsx"
    content = read(rel)
    helper = '''
function resolveAppOpenUrl(item) {
  const raw =
    item?.access?.open_url ||
    item?.runtime?.url ||
    item?.runtime?.route ||
    '';

  if (!raw) return '';

  try {
    const url = new URL(raw, window.location.origin);
    if (!url.pathname.startsWith('/apps/')) {
      return '';
    }
    return url.toString();
  } catch {
    return '';
  }
}

function openCatalogApp(item) {
  const target = resolveAppOpenUrl(item);
  if (!target) return;
  window.location.assign(target);
}
'''
    if "function resolveAppOpenUrl(item)" not in content:
        marker = "export default function CatalogScreen()"
        if marker not in content:
            raise SystemExit("Could not find CatalogScreen marker in LiteCatalog.jsx")
        content = content.replace(marker, helper + "\n" + marker, 1)

    # Route existing Open behavior through the top-level same-origin navigation helper.
    content = content.replace("onClick={() => openApp(item)}", "onClick={() => openCatalogApp(item)}")
    content = content.replace("onClick={() => openApp(app)}", "onClick={() => openCatalogApp(app)}")
    content = content.replace("window.location.assign(openUrl)", "window.location.assign(resolveAppOpenUrl(item) || openUrl)")
    content = content.replace("window.location.href = openUrl", "window.location.assign(resolveAppOpenUrl(item) || openUrl)")

    # If the branch still only has Install/Installed, add Open next to Installed.
    if "openCatalogApp(item)" not in content:
        old = '''              <div className="lite-catalog-actions">
                <LiteButton
                  onClick={() => install(item)}
                  disabled={busyId === item.id || installed}
                  tone={installed ? 'secondary' : 'primary'}
                >
                  {busyId === item.id ? 'Starting...' : installed ? 'Installed' : 'Install'}
                </LiteButton>
              </div>'''
        new = '''              <div className="lite-catalog-actions">
                <LiteButton
                  onClick={() => install(item)}
                  disabled={busyId === item.id || installed}
                  tone={installed ? 'secondary' : 'primary'}
                >
                  {busyId === item.id ? 'Starting...' : installed ? 'Installed' : 'Install'}
                </LiteButton>
                {installed && item?.actions?.open ? (
                  <LiteButton
                    type="button"
                    tone="primary"
                    onClick={() => openCatalogApp(item)}
                    disabled={!resolveAppOpenUrl(item)}
                  >
                    Open
                  </LiteButton>
                ) : null}
              </div>'''
        if old in content:
            content = content.replace(old, new, 1)
    if "openCatalogApp" not in content:
        raise SystemExit("LiteCatalog.jsx still does not include openCatalogApp")
    write(rel, content)


def patch_caddyfile_if_present() -> None:
    rel = "caddy/Caddyfile"
    if p(rel).exists():
        content = read(rel).replace("handle_path /apps/photoprism/* {", "handle /apps/photoprism/* {")
        write(rel, content)


def main() -> None:
    patch_restart_helper()
    patch_installer()
    patch_start_dashboard()
    patch_backend()
    patch_vite()
    patch_lite_catalog()
    patch_caddyfile_if_present()
    print("Pocket Lab Lite PhotoPrism production fix v3 applied.")


if __name__ == "__main__":
    main()
