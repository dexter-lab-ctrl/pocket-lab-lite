#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'
SCRIPT_DIR="$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/common.sh"
GITEA_URL="${GITEA_URL:-http://127.0.0.1:3030}"; GITEA_ORG="${GITEA_ORG:-pocket_admin}"; REPO_NAME="${REPO_NAME:-pocket_lab_iac}"; SOURCE_DIR="${SOURCE_DIR:-$POCKET_LAB_IAC_DIR}"
TEMPLATE_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")/pocket-lab-iac-api-compatible"; SERVICE_SECRETS_FILE="${SERVICE_SECRETS_FILE:-$STATE_DIR/service-secrets.env}"; VAULT_ADDR="${VAULT_ADDR:-http://127.0.0.1:8200}"
get_creds() {
  local user="" pass=""
  if have vault && vault status >/dev/null 2>&1; then export VAULT_ADDR; user="$(vault kv get -field=username secret/gitea 2>/dev/null || true)"; pass="$(vault kv get -field=password secret/gitea 2>/dev/null || true)"; fi
  if [[ -z "$user" || -z "$pass" ]] && [[ -f "$SERVICE_SECRETS_FILE" ]]; then # shellcheck disable=SC1090
  source "$SERVICE_SECRETS_FILE"; user="pocket_admin"; pass="${GITEA_UI_PASS:-}"; fi
  printf '%s:%s' "$user" "$pass"
}
wait_for_gitea() { log INFO "Waiting for Gitea API"; wait_for_http "$GITEA_URL/api/swagger" 60 || die "Gitea did not become ready"; }
create_repo() {
  local user="$1" pass="$2" status
  status="$(curl -s -o /dev/null -w '%{http_code}' -u "$user:$pass" -H 'Content-Type: application/json' -d "{\"name\":\"$REPO_NAME\",\"private\":true}" "$GITEA_URL/api/v1/user/repos" || true)"
  if [[ "$status" == "201" || "$status" == "409" ]]; then
    log INFO "Repository ready: $REPO_NAME"
  else
    die "Failed to ensure repo; HTTP $status"
  fi
}
prepare_source_dir() {
  mkdir -p "$SOURCE_DIR"
  if [[ -d "$TEMPLATE_DIR" ]]; then
    log INFO "Syncing IaC template to $SOURCE_DIR"
    rsync -a --delete --exclude .git "$TEMPLATE_DIR/" "$SOURCE_DIR/" 2>/dev/null || cp -a "$TEMPLATE_DIR/." "$SOURCE_DIR/"
  else
    log WARN "IaC template not found; creating minimal inventory"
    mkdir -p "$SOURCE_DIR/inventory/dev"
    cat <<EOF > "$SOURCE_DIR/ansible.cfg"
[defaults]
inventory = inventory/dev/hosts.yml
roles_path = roles
stdout_callback = yaml
host_key_checking = False
retry_files_enabled = False
EOF
    cat <<EOF > "$SOURCE_DIR/inventory/dev/hosts.yml"
all:
  children:
    local:
      hosts:
        localhost:
          ansible_connection: local
EOF
  fi
}
git_remote_url() { local user="$1" pass="$2" epass; epass="$(printf '%s' "$pass" | jq -sRr @uri)"; printf 'http://%s:%s@127.0.0.1:3030/%s/%s.git' "$user" "$epass" "$GITEA_ORG" "$REPO_NAME"; }
seed_repo() {
  local user="$1" pass="$2" remote; remote="$(git_remote_url "$user" "$pass")"
  if [[ ! -d "$SOURCE_DIR/.git" ]]; then git -C "$SOURCE_DIR" init; git -C "$SOURCE_DIR" branch -M main || true; fi
  git -C "$SOURCE_DIR" config user.name "Pocket Lab Automation"; git -C "$SOURCE_DIR" config user.email "gitops@pocketlab.local"
  git -C "$SOURCE_DIR" remote set-url origin "$remote" 2>/dev/null || git -C "$SOURCE_DIR" remote add origin "$remote"
  if [[ -n "$(git -C "$SOURCE_DIR" status --porcelain)" ]]; then git -C "$SOURCE_DIR" add .; git -C "$SOURCE_DIR" commit -m "Seed or refresh Pocket Lab IaC"; else log INFO "No local GitOps changes to commit"; fi
  git -C "$SOURCE_DIR" push -u origin main || log WARN "Git push failed; local repo still prepared at $SOURCE_DIR"
}
main() {
  SCRIPT_NAME="seed-gitops-repo.sh"; acquire_lock "$SCRIPT_NAME"; ensure_root_dirs; require_cmd curl jq git
  local creds user pass; creds="$(get_creds)"; user="${creds%%:*}"; pass="${creds#*:}"; [[ -n "$user" && -n "$pass" ]] || die "Could not obtain Gitea credentials"
  wait_for_gitea; create_repo "$user" "$pass"; prepare_source_dir; seed_repo "$user" "$pass"; mark_done gitops_seeded; log INFO "GitOps repository is seeded/refreshed safely"
}
main "$@"
