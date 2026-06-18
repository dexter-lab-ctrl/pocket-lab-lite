#!/usr/bin/env bash
set -Eeuo pipefail

# ==============================================================================
# Pocket Lab Documentation Consolidation Commit Prep
# ==============================================================================
#
# Purpose:
#   Prepare a clean documentation-only commit for the enterprise Dev/Prod
#   documentation structure.
#
# This script:
#   - Prefers/creates the docs/consolidate-dev-prod branch
#   - Excludes generated artifacts from docs commit
#   - Restores unrelated deleted local fix scripts
#   - Stages only documentation placement files
#   - Keeps app/test/runtime changes separate
#   - Optionally commits documentation changes when AUTO_COMMIT_DOCS=1
#
# Usage:
#   bash scripts/dev/prepare-docs-consolidation-commit.sh
#
# Optional:
#   AUTO_COMMIT_DOCS=1 bash scripts/dev/prepare-docs-consolidation-commit.sh
#
# ==============================================================================

DOCS_BRANCH="${DOCS_BRANCH:-docs/consolidate-dev-prod}"
AUTO_COMMIT_DOCS="${AUTO_COMMIT_DOCS:-0}"

log() {
  printf '\033[1;34m[docs-commit]\033[0m %s\n' "$*"
}

warn() {
  printf '\033[1;33m[docs-commit:warn]\033[0m %s\n' "$*"
}

err() {
  printf '\033[1;31m[docs-commit:error]\033[0m %s\n' "$*" >&2
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    err "Required command not found: $1"
    exit 1
  fi
}

assert_repo_root() {
  if [[ ! -f "Taskfile.yml" ]] || [[ ! -f "package.json" ]]; then
    err "Run this script from the Pocket Lab repo root."
    err "Expected files: Taskfile.yml and package.json"
    exit 1
  fi
}

ensure_git_repo() {
  if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    err "This directory is not a Git repository."
    exit 1
  fi
}

ensure_docs_branch() {
  local current_branch
  current_branch="$(git branch --show-current || true)"

  if [[ "$current_branch" == "$DOCS_BRANCH" ]]; then
    log "Already on documentation branch: $DOCS_BRANCH"
    return
  fi

  log "Switching documentation work to branch: $DOCS_BRANCH"

  if git show-ref --verify --quiet "refs/heads/$DOCS_BRANCH"; then
    git checkout "$DOCS_BRANCH"
  else
    git checkout -b "$DOCS_BRANCH"
  fi
}

unstage_everything_first() {
  log "Unstaging current index to avoid mixed commits"
  git reset
}

restore_unrelated_deleted_files() {
  log "Restoring unrelated deleted local helper/fix scripts"

  # These were temporary/local remediation scripts seen in the current Pocket Lab working tree.
  # They should not be deleted in the docs consolidation commit unless intentionally retired
  # in a separate cleanup PR.
  local maybe_deleted=(
    "pocketlab_backend_auth_test_fix.sh"
    "pocketlab_backend_final_alignment_fix.sh"
    "pocketlab_backend_test_alignment_fix.sh"
    "pocketlab_bootstrap_sc1091_final_fix.sh"
    "pocketlab_bootstrap_scripts_shellcheck_fix.sh"
    "pocketlab_contract_cleanup_local.sh"
    "pocketlab_deps_normalize_operation_fix.sh"
    "pocketlab_iac_validation_rolepath_fix.sh"
    "pocketlab_operations_target_shape_fix.sh"
    "pocketlab_photoprism_rolepath_fix.sh"
    "pocketlab_precommit_legacy_symbol_fix.sh"
    "pocketlab_split_python_requirements.sh"
    "pocketlab_ubuntu_dev_env_setup_v3_architecture_plus_contract_fix.sh"
    "pocketlab_vault_block_loop_fix.sh"
  )

  for file in "${maybe_deleted[@]}"; do
    if git ls-files --error-unmatch "$file" >/dev/null 2>&1; then
      if [[ ! -e "$file" ]]; then
        git restore "$file" || true
        log "Restored deleted file: $file"
      fi
    fi
  done
}

exclude_generated_artifacts() {
  log "Excluding generated/runtime artifacts from documentation commit"

  # Generated/runtime/state artifacts observed or expected in Pocket Lab.
  # These should not be included in a docs-only commit.
  local generated_paths=(
    ".pocketlab-dev"
    "pocket-lab-final-structure/.pocketlab-dev"
    "storybook-static"
    "dist"
    "coverage"
    "playwright-report"
    "test-results"
    ".nyc_output"
    ".pytest_cache"
    ".mypy_cache"
    ".ruff_cache"
    ".vite"
    "node_modules/.vite"
    "htmlcov"
    "__pycache__"
  )

  for path in "${generated_paths[@]}"; do
    if [[ -e "$path" ]]; then
      if git ls-files --error-unmatch "$path" >/dev/null 2>&1; then
        git restore "$path" || true
        log "Restored tracked generated path: $path"
      else
        rm -rf "$path"
        log "Removed untracked generated path: $path"
      fi
    fi
  done

  # Generated files / temporary local files.
  local generated_files=(
    "contracts/openapi.json"
    "pocketlab-ui-debug.mjs"
    "pocketlab_consolidated_docs_dev_prod.zip"
    "pocketlab_updated_markdown_documents_only.zip"
    "pocketlab_missing_reference_markdown_files.zip"
    "pocketlab_complete_reference_markdown_documents.zip"
    "apply_missing_reference_docs.sh"
  )

  for file in "${generated_files[@]}"; do
    if [[ -e "$file" ]]; then
      if git ls-files --error-unmatch "$file" >/dev/null 2>&1; then
        git restore "$file" || true
        log "Restored tracked generated file: $file"
      else
        rm -f "$file"
        log "Removed untracked generated file: $file"
      fi
    fi
  done

  # Common generated extensions.
  find . \
    -path ./.git -prune -o \
    -path ./node_modules -prune -o \
    -path ./.venv -prune -o \
    -type f \( \
      -name "*.zip" -o \
      -name "*.tar" -o \
      -name "*.tar.gz" -o \
      -name "*.tgz" -o \
      -name "*.log" -o \
      -name "*.tmp" -o \
      -name "*.bak" -o \
      -name "*.pyc" -o \
      -name "*.pyo" -o \
      -name "*.png" -path "./.pocketlab-dev/*" \
    \) -print0 | while IFS= read -r -d '' file; do
      if git ls-files --error-unmatch "$file" >/dev/null 2>&1; then
        git restore "$file" || true
        log "Restored tracked generated file: $file"
      else
        rm -f "$file"
        log "Removed untracked generated file: $file"
      fi
    done
}

restore_code_and_validation_fixes_from_docs_commit() {
  log "Keeping app/test/runtime fixes out of the documentation commit"

  # These are legitimate app/test/dev-gate fixes from your current validation work,
  # but they should be committed separately from docs.
  local non_doc_paths=(
    "scripts/dev/status.sh"
    "scripts/dev/up.sh"
    "src/hooks/useHealthEngine.js"
    "src/lib/health.js"
    "tests/e2e/visual-regression.spec.ts"
    "tests/e2e/visual-regression.spec.ts-snapshots"
    "vite.config.js"
    ".storybook/preview.jsx"
  )

  for path in "${non_doc_paths[@]}"; do
    if [[ -e "$path" ]] || git ls-files --error-unmatch "$path" >/dev/null 2>&1; then
      git restore --staged "$path" 2>/dev/null || true
      warn "Left out of docs commit: $path"
    fi
  done
}

stage_documentation_only() {
  log "Staging documentation-only changes"

  local doc_paths=(
    "README.md"
    "docs"

    "ENTERPRISE_NATS_HARDENING_REPORT.md"
    "IAC_ARCHITECTURE_SYNC_REPORT.md"
    "LEGACY_INTENT_REMOVAL_REPORT.md"
    "PYTHON_API_RETIREMENT_REPORT.md"
    "SANITIZATION_REPORT.md"
    "SECOND_PASS_FASTAPI_NATS_ONLY_REPORT.md"
    "UI_UX_ARCHITECTURE_SYNC_REPORT.md"

    "pocket-lab-final-structure/runtime/api_fastapi/README.md"
    "pocket-lab-final-structure/pocket-lab-iac-api-compatible/README.md"
    "pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/README.md"
    "pocket-lab-final-structure/pocket_lab_iac/README.md"

    "src/mocks/README.md"

    "scripts/dev/implement-documentation-placement.sh"
    "scripts/dev/prepare-docs-consolidation-commit.sh"
  )

  for path in "${doc_paths[@]}"; do
    if [[ -e "$path" ]]; then
      git add "$path"
    fi
  done

  restore_code_and_validation_fixes_from_docs_commit
}

validate_reference_archive() {
  log "Validating reference Markdown archive"

  local reference_dir="docs/reference/original-updated-md"

  if [[ ! -d "$reference_dir" ]]; then
    err "Missing reference archive directory: $reference_dir"
    exit 1
  fi

  local count
  count="$(find "$reference_dir" -maxdepth 1 -type f -name "*.md" | wc -l | tr -d ' ')"

  log "Reference Markdown count: $count"

  if [[ "$count" -lt 34 ]]; then
    warn "Expected 34 reference Markdown files, found $count."
    warn "You may still be missing reference docs."
  elif [[ "$count" -eq 34 ]]; then
    log "Reference archive is complete: 34 Markdown files."
  else
    warn "Reference archive has more than 34 Markdown files: $count."
    warn "Review for duplicates."
  fi
}

validate_docs_structure() {
  log "Validating canonical documentation structure"

  local required_files=(
    "docs/README.md"
    "docs/DOCUMENTATION_PLACEMENT_PLAN.md"
    "docs/DOC_MIGRATION_MAP.md"
    "docs/DOCUMENTATION_IMPLEMENTATION_REPORT.md"

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
  )

  local missing=0

  for file in "${required_files[@]}"; do
    if [[ ! -f "$file" ]]; then
      warn "Missing required docs file: $file"
      missing=1
    fi
  done

  if [[ "$missing" -eq 1 ]]; then
    err "Documentation structure is incomplete."
    exit 1
  fi

  log "Canonical docs structure is complete."
}

detect_bad_staged_files() {
  log "Checking staged files for generated artifacts or unrelated code changes"

  local bad=0
  local staged
  staged="$(git diff --cached --name-only)"

  if [[ -z "$staged" ]]; then
    warn "No staged changes found."
    return
  fi

  while IFS= read -r file; do
    case "$file" in
      .pocketlab-dev/*|pocket-lab-final-structure/.pocketlab-dev/*|dist/*|storybook-static/*|node_modules/*|coverage/*|playwright-report/*|test-results/*|.pytest_cache/*|.mypy_cache/*|.ruff_cache/*|contracts/openapi.json)
        err "Generated artifact staged unexpectedly: $file"
        bad=1
        ;;
      scripts/dev/status.sh|scripts/dev/up.sh|src/hooks/useHealthEngine.js|src/lib/health.js|tests/e2e/visual-regression.spec.ts|vite.config.js|.storybook/preview.jsx)
        err "Non-doc validation/code fix staged unexpectedly: $file"
        bad=1
        ;;
      *.zip|*.tar|*.tar.gz|*.tgz|*.log|*.tmp|*.bak|*.pyc|*.pyo)
        err "Generated/binary/temp file staged unexpectedly: $file"
        bad=1
        ;;
    esac
  done <<< "$staged"

  if [[ "$bad" -ne 0 ]]; then
    err "Bad staged files detected. Please review before committing."
    exit 1
  fi

  log "Staged files look documentation-only."
}

print_summary() {
  echo
  log "Documentation commit preparation complete."

  echo
  echo "Current branch:"
  git branch --show-current

  echo
  echo "Reference Markdown count:"
  find docs/reference/original-updated-md -maxdepth 1 -type f -name "*.md" | wc -l

  echo
  echo "Staged documentation changes:"
  git diff --cached --stat

  echo
  echo "Remaining unstaged changes kept separate:"
  git status --short
}

commit_if_requested() {
  if [[ "$AUTO_COMMIT_DOCS" == "1" ]]; then
    log "AUTO_COMMIT_DOCS=1 set. Creating documentation commit."

    git commit -m "Consolidate Pocket Lab documentation into Dev and Prod structure"

    log "Documentation commit created."
  else
    warn "AUTO_COMMIT_DOCS is not set. Review staged changes manually."
    echo
    echo "To commit after review:"
    echo
    echo "  git commit -m \"Consolidate Pocket Lab documentation into Dev and Prod structure\""
    echo
    echo "To auto-commit next time:"
    echo
    echo "  AUTO_COMMIT_DOCS=1 bash scripts/dev/prepare-docs-consolidation-commit.sh"
  fi
}

main() {
  require_cmd git
  require_cmd find
  require_cmd wc
  require_cmd rm

  assert_repo_root
  ensure_git_repo
  ensure_docs_branch

  unstage_everything_first
  restore_unrelated_deleted_files
  exclude_generated_artifacts
  validate_docs_structure
  validate_reference_archive
  stage_documentation_only
  detect_bad_staged_files
  print_summary
  commit_if_requested
}

main "$@"
