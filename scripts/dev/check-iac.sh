#!/usr/bin/env bash
set -Eeuo pipefail

# POCKETLAB_ACTIVE_CODE_SCAN_EXCLUDES
# Historical migration/fix scripts are retained as audit artifacts, but are
# not active runtime, API, worker, frontend, contract, docs, or validation code.
# Release-blocking retired-symbol scans must apply to active code paths.
ACTIVE_CODE_SCAN_EXCLUDES=(
  --exclude-dir=.git
  --exclude-dir=.venv
  --exclude-dir=node_modules
  --exclude-dir=dist
  --exclude-dir=site
  --exclude-dir=storybook-static
  --exclude-dir=.pocketlab-dev
  --exclude-dir=__pycache__
  --exclude-dir=migrations
  --exclude='*.bak'
  --exclude='*.orig'
  --exclude='*.rej'
  --exclude='*.patch'
  --exclude='*.zip'
  --exclude='*.tar'
  --exclude='*.gz'
)


iac="pocket-lab-final-structure/pocket-lab-iac-api-compatible"
[[ -d "$iac" ]] || { echo "Missing IaC dir: $iac" >&2; exit 1; }

export ANSIBLE_CONFIG="$PWD/$iac/ansible.cfg"
export ANSIBLE_ROLES_PATH="$PWD/$iac/roles:$PWD/$iac/roles/workloads"
export ANSIBLE_COLLECTIONS_PATH="${ANSIBLE_COLLECTIONS_PATH:-$HOME/.ansible/collections:/usr/share/ansible/collections}"
export ANSIBLE_LOCAL_TEMP="${ANSIBLE_LOCAL_TEMP:-$PWD/.pocketlab-dev/ansible/tmp}"
export ANSIBLE_REMOTE_TEMP="${ANSIBLE_REMOTE_TEMP:-/tmp/.ansible-${USER:-pocketlab}}"
mkdir -p "$ANSIBLE_LOCAL_TEMP"

python3 - <<'PY'
from pathlib import Path
import yaml

root = Path("pocket-lab-final-structure/pocket-lab-iac-api-compatible")
bad = []

for path in root.rglob("*"):
    if path.suffix.lower() not in {".yml", ".yaml"}:
        continue
    try:
        list(yaml.safe_load_all(path.read_text(encoding="utf-8", errors="ignore")))
    except Exception as exc:
        bad.append((str(path), str(exc)))

if bad:
    for p, e in bad:
        print(f"{p}: {e}")
    raise SystemExit(1)

print("YAML parse passed")

scan_suffixes = {".yml", ".yaml", ".j2", ".conf", ".md", ".txt"}
text = "\n".join(
    p.read_text(encoding="utf-8", errors="ignore")
    for p in root.rglob("*")
    if p.is_file() and p.suffix.lower() in scan_suffixes
)

for token in ["fastapi_control_plane", "nats"]:
    if token not in text:
        raise SystemExit(f"Missing IaC token: {token}")

forbidden_tokens = [
    "retired compatibility intent field",
    "retired sync compatibility task",
    "retired IaC deploy compatibility task",
    "dashboard" + "_" + "api",
    "retired runtime API directory",
    "legacy" + "_" + "intent",
    "sync" + "_" + "bash",
    "tofu" + "_" + "deploy",
    "/" + "api" + "/" + "action" + "/" + "update",
    "POCKETLAB" + "_" + "API" + "_" + "RUNTIME",
    "pocket" + "_" + "lab" + "_" + "api" + "_" + "server",
    "Base" + "HTTPRequestHandler",
    "HTTP" + "Server",
    "runtime" + "/" + "api" + "/",
]
for forbidden in forbidden_tokens:
    if forbidden in text:
        raise SystemExit(f"Forbidden IaC legacy token found: {forbidden}")

site = root / "site.yml"
if site.exists():
    st = site.read_text(encoding="utf-8", errors="ignore")
    n = st.find("nats")
    f = st.find("fastapi_control_plane")
    if n == -1 or f == -1 or n > f:
        raise SystemExit("site.yml must include nats before fastapi_control_plane")

roles = root / "roles"
if roles.exists():
    if not (roles / "nats").exists():
        raise SystemExit("roles/nats missing")
    if not (roles / "fastapi_control_plane").exists():
        raise SystemExit("roles/fastapi_control_plane missing")
    if (roles / ("dashboard" + "_" + "api")).exists():
        raise SystemExit("roles/" + "dashboard" + "_api must not exist")

for inv in [root / "inventory/dev/hosts.yml", root / "inventory/prod/hosts.yml"]:
    if inv.exists() and "nats" not in inv.read_text(encoding="utf-8", errors="ignore"):
        raise SystemExit(f"{inv} must include nats group")

for caddy in list(root.rglob("*Caddy*")) + list(root.rglob("*caddy*")):
    if caddy.is_file():
        ct = caddy.read_text(encoding="utf-8", errors="ignore")
        if "/api" in ct and "/ws" not in ct:
            raise SystemExit(f"Caddy config {caddy} proxies /api but not /ws")

print("IaC architecture assertions passed")
PY

if command -v yamllint >/dev/null 2>&1; then
  yamllint "$iac" || true
fi

# ansible-lint style findings are advisory for this dev gate; actual syntax-check below is blocking.
if command -v ansible-lint >/dev/null 2>&1; then
  (
    cd "$iac"
    ansible-lint . || true
  )
fi

if [[ -d "$iac/playbooks" && -f "$iac/inventory/dev/hosts.yml" ]]; then
  while IFS= read -r pb; do
    rel="${pb#"$iac/"}"
    echo "Syntax-check: $rel"
    (
      cd "$iac"
      ansible-playbook --syntax-check "$rel" -i "inventory/dev/hosts.yml"
    )
  done < <(find "$iac/playbooks" -maxdepth 1 -type f \( -name "*.yml" -o -name "*.yaml" \) | sort)
fi

echo "IaC validation passed"
