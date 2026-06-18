#!/usr/bin/env bash
set -Eeuo pipefail

# ==============================================================================
# Pocket Lab Documentation Placement Implementation
# ==============================================================================
#
# Purpose:
#   Consolidates Pocket Lab documentation into an enterprise-grade Dev/Prod
#   documentation structure.
#
# What it does:
#   1. Creates canonical docs/ structure:
#        docs/dev/
#        docs/prod/
#        docs/reference/original-updated-md/
#
#   2. Extracts consolidated Dev/Prod docs from:
#        pocketlab_consolidated_docs_dev_prod.zip
#
#   3. Extracts all updated Markdown documents from:
#        pocketlab_updated_markdown_documents_only.zip
#
#   4. Preserves original updated Markdown docs under:
#        docs/reference/original-updated-md/
#
#   5. Converts scattered/root report files into pointer documents.
#
#   6. Converts key component README files into short entry-point files.
#
#   7. Adds a documentation index to root README.md.
#
#   8. Produces validation output and a migration summary.
#
# Usage:
#   bash scripts/dev/implement-documentation-placement.sh
#
# Optional:
#   CONSOLIDATED_DOCS_ZIP=/path/to/pocketlab_consolidated_docs_dev_prod.zip \
#   UPDATED_MD_ZIP=/path/to/pocketlab_updated_markdown_documents_only.zip \
#   bash scripts/dev/implement-documentation-placement.sh
#
# ==============================================================================

ROOT_DIR="$(pwd)"
SCRIPT_NAME="$(basename "$0")"

CONSOLIDATED_DOCS_ZIP="${CONSOLIDATED_DOCS_ZIP:-pocketlab_consolidated_docs_dev_prod.zip}"
UPDATED_MD_ZIP="${UPDATED_MD_ZIP:-pocketlab_updated_markdown_documents_only.zip}"

TMP_DIR="/tmp/pocketlab-doc-placement"
TMP_CONSOLIDATED="$TMP_DIR/consolidated"
TMP_UPDATED_MD="$TMP_DIR/updated-md"

BACKUP_DIR=".pocketlab-dev/backups/docs-placement-$(date +%Y%m%d-%H%M%S)"

log() {
  printf '\033[1;34m[docs-placement]\033[0m %s\n' "$*"
}

warn() {
  printf '\033[1;33m[docs-placement:warn]\033[0m %s\n' "$*"
}

err() {
  printf '\033[1;31m[docs-placement:error]\033[0m %s\n' "$*" >&2
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    err "Required command not found: $1"
    exit 1
  fi
}

assert_repo_root() {
  if [[ ! -f "package.json" ]] || [[ ! -f "Taskfile.yml" ]]; then
    err "Run this script from the Pocket Lab repo root."
    err "Expected files: package.json and Taskfile.yml"
    exit 1
  fi
}

assert_file_exists() {
  local file="$1"
  local label="$2"

  if [[ ! -f "$file" ]]; then
    err "$label not found: $file"
    err "Place the ZIP in the repo root or pass it using environment variables."
    err "Example:"
    err "  CONSOLIDATED_DOCS_ZIP=/path/to/pocketlab_consolidated_docs_dev_prod.zip \\"
    err "  UPDATED_MD_ZIP=/path/to/pocketlab_updated_markdown_documents_only.zip \\"
    err "  bash scripts/dev/implement-documentation-placement.sh"
    exit 1
  fi
}

backup_existing_docs() {
  log "Creating backup at $BACKUP_DIR"

  mkdir -p "$BACKUP_DIR"

  for path in \
    README.md \
    docs \
    ENTERPRISE_NATS_HARDENING_REPORT.md \
    IAC_ARCHITECTURE_SYNC_REPORT.md \
    LEGACY_INTENT_REMOVAL_REPORT.md \
    PYTHON_API_RETIREMENT_REPORT.md \
    SANITIZATION_REPORT.md \
    SECOND_PASS_FASTAPI_NATS_ONLY_REPORT.md \
    UI_UX_ARCHITECTURE_SYNC_REPORT.md \
    pocket-lab-final-structure/runtime/api_fastapi/README.md \
    pocket-lab-final-structure/pocket-lab-iac-api-compatible/README.md \
    pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/README.md \
    src/mocks/README.md
  do
    if [[ -e "$path" ]]; then
      mkdir -p "$BACKUP_DIR/$(dirname "$path")"
      cp -a "$path" "$BACKUP_DIR/$path"
    fi
  done

  log "Backup completed."
}

extract_zip_inputs() {
  log "Preparing temporary workspace: $TMP_DIR"

  rm -rf "$TMP_DIR"
  mkdir -p "$TMP_CONSOLIDATED" "$TMP_UPDATED_MD"

  log "Extracting consolidated Dev/Prod docs from: $CONSOLIDATED_DOCS_ZIP"
  unzip -q -o "$CONSOLIDATED_DOCS_ZIP" -d "$TMP_CONSOLIDATED"

  log "Extracting updated Markdown docs from: $UPDATED_MD_ZIP"
  unzip -q -o "$UPDATED_MD_ZIP" -d "$TMP_UPDATED_MD"
}

install_canonical_docs() {
  log "Installing canonical docs/ structure"

  mkdir -p docs/dev docs/prod docs/reference/original-updated-md

  if [[ -d "$TMP_CONSOLIDATED/docs" ]]; then
    cp -a "$TMP_CONSOLIDATED/docs/." docs/
  else
    err "Could not find docs/ directory inside consolidated docs ZIP."
    err "Extracted contents:"
    find "$TMP_CONSOLIDATED" -maxdepth 3 -type f | sort >&2
    exit 1
  fi

  log "Canonical docs installed under docs/."
}

install_reference_docs() {
  log "Preserving updated Markdown source documents under docs/reference/original-updated-md/"

  mkdir -p docs/reference/original-updated-md

  local count
  count="$(find "$TMP_UPDATED_MD" -type f -name "*.md" | wc -l | tr -d ' ')"

  if [[ "$count" == "0" ]]; then
    err "No Markdown files found inside updated Markdown ZIP."
    exit 1
  fi

  find "$TMP_UPDATED_MD" -type f -name "*.md" -print0 |
    while IFS= read -r -d '' file; do
      cp "$file" "docs/reference/original-updated-md/$(basename "$file")"
    done

  log "Reference Markdown docs copied: $count"
}

write_root_pointer_reports() {
  log "Converting root-level report documents into canonical pointer files"

  cat > ENTERPRISE_NATS_HARDENING_REPORT.md <<'EOF'
# Enterprise NATS Hardening Report

This document has been consolidated.

Canonical documentation:

- [Production Runtime, NATS, JetStream, and Workflow Engine](docs/prod/runtime-nats-workflow-engine.md)
- [Production Security Hardening and Secrets](docs/prod/security-hardening-and-secrets.md)

Historical reference copy:

- [Reference Archive](docs/reference/original-updated-md/ENTERPRISE_NATS_HARDENING_REPORT.md)
EOF

  cat > IAC_ARCHITECTURE_SYNC_REPORT.md <<'EOF'
# IaC Architecture Sync Report

This document has been consolidated.

Canonical documentation:

- [Production Deployment, Bootstrap, and IaC](docs/prod/deployment-bootstrap-and-iac.md)
- [Production Architecture](docs/prod/production-architecture.md)

Historical reference copy:

- [Reference Archive](docs/reference/original-updated-md/IAC_ARCHITECTURE_SYNC_REPORT.md)
EOF

  cat > LEGACY_INTENT_REMOVAL_REPORT.md <<'EOF'
# Legacy Intent Removal Report

This document has been consolidated.

Canonical documentation:

- [Production Runtime, NATS, JetStream, and Workflow Engine](docs/prod/runtime-nats-workflow-engine.md)
- [Development Contracts, Schemas, and Mocks](docs/dev/contracts-schemas-and-mocks.md)

Historical reference copy:

- [Reference Archive](docs/reference/original-updated-md/LEGACY_INTENT_REMOVAL_REPORT.md)
EOF

  cat > PYTHON_API_RETIREMENT_REPORT.md <<'EOF'
# Python API Retirement Report

This document has been consolidated.

Canonical documentation:

- [Production Architecture](docs/prod/production-architecture.md)
- [Production Runtime, NATS, JetStream, and Workflow Engine](docs/prod/runtime-nats-workflow-engine.md)

Historical reference copy:

- [Reference Archive](docs/reference/original-updated-md/PYTHON_API_RETIREMENT_REPORT.md)
EOF

  cat > SANITIZATION_REPORT.md <<'EOF'
# Sanitization Report

This document has been consolidated.

Canonical documentation:

- [Production Security Hardening and Secrets](docs/prod/security-hardening-and-secrets.md)
- [Development Frontend/UI Quality Gates](docs/dev/frontend-ui-quality-gates.md)

Historical reference copy:

- [Reference Archive](docs/reference/original-updated-md/SANITIZATION_REPORT.md)
EOF

  cat > SECOND_PASS_FASTAPI_NATS_ONLY_REPORT.md <<'EOF'
# Second Pass FastAPI + NATS Only Report

This document has been consolidated.

Canonical documentation:

- [Production Runtime, NATS, JetStream, and Workflow Engine](docs/prod/runtime-nats-workflow-engine.md)
- [Production Architecture](docs/prod/production-architecture.md)

Historical reference copy:

- [Reference Archive](docs/reference/original-updated-md/SECOND_PASS_FASTAPI_NATS_ONLY_REPORT.md)
EOF

  cat > UI_UX_ARCHITECTURE_SYNC_REPORT.md <<'EOF'
# UI/UX Architecture Sync Report

This document has been consolidated.

Canonical documentation:

- [Development Frontend/UI Quality Gates](docs/dev/frontend-ui-quality-gates.md)
- [Development Environment and Validation](docs/dev/dev-environment-and-validation.md)

Historical reference copy:

- [Reference Archive](docs/reference/original-updated-md/UI_UX_ARCHITECTURE_SYNC_REPORT.md)
EOF
}

write_component_entrypoint_readmes() {
  log "Converting component-local READMEs into short canonical entry points"

  mkdir -p pocket-lab-final-structure/runtime/api_fastapi
  cat > pocket-lab-final-structure/runtime/api_fastapi/README.md <<'EOF'
# Pocket Lab FastAPI Runtime

This directory contains the FastAPI control-plane runtime, NATS/JetStream integration, worker-facing APIs, health endpoints, telemetry endpoints, and WebSocket/event-stream surfaces.

Canonical documentation:

- [Production Runtime, NATS, JetStream, and Workflow Engine](../../../docs/prod/runtime-nats-workflow-engine.md)
- [Production Architecture](../../../docs/prod/production-architecture.md)
- [Development Contracts, Schemas, and Mocks](../../../docs/dev/contracts-schemas-and-mocks.md)

Historical reference:

- [Runtime API FastAPI README Archive](../../../docs/reference/original-updated-md/pocket-lab-final-structure__runtime__api_fastapi__README.md)
EOF

  mkdir -p pocket-lab-final-structure/pocket-lab-iac-api-compatible
  cat > pocket-lab-final-structure/pocket-lab-iac-api-compatible/README.md <<'EOF'
# Pocket Lab IaC

This directory contains the API-compatible infrastructure automation layer, inventories, group variables, Ansible roles, and deployment topology for Pocket Lab.

Canonical documentation:

- [Production Deployment, Bootstrap, and IaC](../../docs/prod/deployment-bootstrap-and-iac.md)
- [Production Architecture](../../docs/prod/production-architecture.md)
- [Production Security Hardening and Secrets](../../docs/prod/security-hardening-and-secrets.md)

Historical reference:

- [IaC README Archive](../../docs/reference/original-updated-md/pocket-lab-final-structure__pocket-lab-iac-api-compatible__README.md)
EOF

  mkdir -p pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched
  cat > pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/README.md <<'EOF'
# Pocket Lab Bootstrap Scripts

This directory contains Day-0 bootstrap scripts and production initialization helpers for Pocket Lab.

Canonical documentation:

- [Production Deployment, Bootstrap, and IaC](../../docs/prod/deployment-bootstrap-and-iac.md)
- [Production Release Workflow and Readiness](../../docs/prod/release-workflow-and-readiness.md)

Historical reference:

- [Bootstrap README Archive](../../docs/reference/original-updated-md/pocket-lab-final-structure__pocket-lab-bootstrap-production-scripts-patched__README.md)
- [Bootstrap Idempotency Notes Archive](../../docs/reference/original-updated-md/pocket-lab-final-structure__pocket-lab-bootstrap-production-scripts-patched__BOOTSTRAP_IDEMPOTENCY_NOTES.md)
EOF

  mkdir -p src/mocks
  cat > src/mocks/README.md <<'EOF'
# Pocket Lab Frontend Mocks

This directory contains MSW handlers and deterministic frontend fixtures used by development, Storybook, contract validation, and Playwright tests.

Canonical documentation:

- [Development Contracts, Schemas, and Mocks](../../docs/dev/contracts-schemas-and-mocks.md)
- [Development Frontend/UI Quality Gates](../../docs/dev/frontend-ui-quality-gates.md)

Historical reference:

- [Mocks README Archive](../../docs/reference/original-updated-md/src__mocks__README.md)
EOF
}

insert_root_readme_documentation_index() {
  log "Ensuring root README.md has a documentation index"

  if [[ ! -f README.md ]]; then
    cat > README.md <<'EOF'
# Pocket Lab
EOF
  fi

  python3 - <<'PY'
from pathlib import Path

p = Path("README.md")
text = p.read_text()

section = """\n\n## Documentation\n\nPocket Lab documentation is consolidated under the repository-level [`docs/`](docs/) directory.\n\nPrimary entry points:\n\n- [Developer Documentation](docs/dev/README.md)\n- [Production Documentation](docs/prod/README.md)\n- [Documentation Placement Plan](docs/DOCUMENTATION_PLACEMENT_PLAN.md)\n- [Documentation Migration Map](docs/DOC_MIGRATION_MAP.md)\n\nHistorical report files are preserved under [`docs/reference/original-updated-md/`](docs/reference/original-updated-md/) and should not be treated as the active source of truth.\n"""

if "## Documentation" in text:
    print("README.md already contains a Documentation section; leaving existing section unchanged.")
else:
    lines = text.splitlines()
    if lines and lines[0].startswith("#"):
        text = "\n".join([lines[0], section] + lines[1:]) + "\n"
    else:
        text = "# Pocket Lab\n" + section + "\n" + text
    p.write_text(text)
    print("Inserted Documentation section into README.md.")
PY
}

write_docs_validation_report() {
  log "Writing docs validation report"

  mkdir -p docs

  local canonical_count
  local reference_count
  local outside_count

  canonical_count="$(find docs/dev docs/prod -type f -name "*.md" 2>/dev/null | wc -l | tr -d ' ')"
  reference_count="$(find docs/reference/original-updated-md -maxdepth 1 -type f -name "*.md" 2>/dev/null | wc -l | tr -d ' ')"
  outside_count="$(find . \
    -path ./.git -prune -o \
    -path ./node_modules -prune -o \
    -path ./.venv -prune -o \
    -name "*.md" -not -path "./docs/*" -print | wc -l | tr -d ' ')"

  cat > docs/DOCUMENTATION_IMPLEMENTATION_REPORT.md <<EOF
# Pocket Lab Documentation Implementation Report

Generated by: \`$SCRIPT_NAME\`

## Result

Pocket Lab documentation has been reorganized into an enterprise-grade Dev/Prod structure.

## Canonical Documentation

- Developer documentation: \`docs/dev/\`
- Production documentation: \`docs/prod/\`
- Historical reference archive: \`docs/reference/original-updated-md/\`

## Counts

| Area | Count |
|---|---:|
| Canonical Dev/Prod Markdown files | $canonical_count |
| Reference Markdown files | $reference_count |
| Markdown files outside \`docs/\` | $outside_count |

## Backup

Previous documentation files were backed up under:

\`$BACKUP_DIR\`

## Source Packages

| Package | Path |
|---|---|
| Consolidated Dev/Prod docs | \`$CONSOLIDATED_DOCS_ZIP\` |
| Updated Markdown docs | \`$UPDATED_MD_ZIP\` |

## Source-of-Truth Rule

Going forward:

- Use \`docs/dev/\` for local development, validation, frontend quality gates, contracts, schemas, mocks, and runbooks.
- Use \`docs/prod/\` for production architecture, NATS/JetStream runtime, workflow engine, bootstrap, IaC, secrets, release workflow, and readiness.
- Use \`docs/reference/original-updated-md/\` only for historical traceability.
- Keep component-local READMEs short and link them to canonical docs.
EOF
}

validate_expected_files() {
  log "Validating expected documentation files"

  local missing=0

  local expected_files=(
    "docs/README.md"
    "docs/DOCUMENTATION_PLACEMENT_PLAN.md"
    "docs/DOC_MIGRATION_MAP.md"
    "docs/dev/README.md"
    "docs/dev/dev-environment-and-validation.md"
    "docs/dev/frontend-ui-quality-gates.md"
    "docs/dev/contracts-schemas-and-mocks.md"
    "docs/dev/local-runtime-runbook.md"
    "docs/prod/README.md"
    "docs/prod/production-architecture.md"
    "docs/prod/runtime-nats-workflow-engine.md"
    "docs/prod/deployment-bootstrap-and-iac.md"
    "docs/prod/security-hardening-and-secrets.md"
    "docs/prod/release-workflow-and-readiness.md"
    "docs/reference/original-updated-md/UPDATED_MARKDOWN_DOCUMENTS_MANIFEST.md"
  )

  for file in "${expected_files[@]}"; do
    if [[ ! -f "$file" ]]; then
      warn "Missing expected file: $file"
      missing=1
    fi
  done

  if [[ "$missing" -ne 0 ]]; then
    warn "Some expected files are missing. Review ZIP contents and docs/ layout."
  else
    log "Expected documentation files are present."
  fi
}

print_summary() {
  log "Documentation placement completed."

  echo
  echo "Canonical documentation:"
  find docs/dev docs/prod -type f -name "*.md" | sort

  echo
  echo "Reference docs count:"
  find docs/reference/original-updated-md -maxdepth 1 -type f -name "*.md" | wc -l

  echo
  echo "Documentation implementation report:"
  echo "  docs/DOCUMENTATION_IMPLEMENTATION_REPORT.md"

  echo
  echo "Recommended review commands:"
  cat <<'EOF'
  git status
  git diff --stat
  find docs -maxdepth 3 -type f -name "*.md" | sort
EOF

  echo
  echo "Recommended commit:"
  cat <<'EOF'
  git add README.md docs/ \
    ENTERPRISE_NATS_HARDENING_REPORT.md \
    IAC_ARCHITECTURE_SYNC_REPORT.md \
    LEGACY_INTENT_REMOVAL_REPORT.md \
    PYTHON_API_RETIREMENT_REPORT.md \
    SANITIZATION_REPORT.md \
    SECOND_PASS_FASTAPI_NATS_ONLY_REPORT.md \
    UI_UX_ARCHITECTURE_SYNC_REPORT.md \
    pocket-lab-final-structure/runtime/api_fastapi/README.md \
    pocket-lab-final-structure/pocket-lab-iac-api-compatible/README.md \
    pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/README.md \
    src/mocks/README.md

  git commit -m "Consolidate Pocket Lab documentation into Dev and Prod structure"
EOF
}

main() {
  log "Starting Pocket Lab documentation placement implementation"

  require_cmd unzip
  require_cmd find
  require_cmd cp
  require_cmd python3
  require_cmd date

  assert_repo_root
  assert_file_exists "$CONSOLIDATED_DOCS_ZIP" "Consolidated Dev/Prod docs ZIP"
  assert_file_exists "$UPDATED_MD_ZIP" "Updated Markdown docs ZIP"

  backup_existing_docs
  extract_zip_inputs
  install_canonical_docs
  install_reference_docs
  write_root_pointer_reports
  write_component_entrypoint_readmes
  insert_root_readme_documentation_index
  write_docs_validation_report
  validate_expected_files
  print_summary
}

main "$@"
