#!/usr/bin/env bash
set -euo pipefail

echo "==> Organizing Pocket Lab MkDocs documentation"

mkdir -p \
  docs/history/documentation-project \
  docs/history/migration-reports \
  docs/history/reference-source-material \
  docs/history/prod-legacy \
  docs/history/dev-legacy \
  docs/adr \
  docs/architecture \
  docs/product \
  docs/api \
  docs/runtime

move_if_exists() {
  src="$1"
  dst="$2"
  if [ -e "$src" ]; then
    mkdir -p "$(dirname "$dst")"
    mv "$src" "$dst"
    echo "moved: $src -> $dst"
  fi
}

copy_if_missing() {
  src="$1"
  dst="$2"
  if [ -e "$src" ] && [ ! -e "$dst" ]; then
    mkdir -p "$(dirname "$dst")"
    cp "$src" "$dst"
    echo "copied: $src -> $dst"
  fi
}

# One-time documentation project artifacts.
move_if_exists docs/DOCUMENTATION_PLACEMENT_PLAN.md docs/history/documentation-project/DOCUMENTATION_PLACEMENT_PLAN.md
move_if_exists docs/DOCUMENTATION_IMPLEMENTATION_REPORT.md docs/history/documentation-project/DOCUMENTATION_IMPLEMENTATION_REPORT.md
move_if_exists docs/DOC_MIGRATION_MAP.md docs/history/documentation-project/DOC_MIGRATION_MAP.md

# Historical reference archive.
if [ -d docs/reference/original-updated-md ]; then
  mkdir -p docs/history/reference-source-material
  shopt -s dotglob nullglob
  mv docs/reference/original-updated-md/* docs/history/reference-source-material/ || true
  shopt -u dotglob nullglob
  rmdir docs/reference/original-updated-md 2>/dev/null || true
  rmdir docs/reference 2>/dev/null || true
  echo "moved: docs/reference/original-updated-md/* -> docs/history/reference-source-material/"
fi

# Legacy dev/prod consolidated docs become history unless later promoted.
if [ -d docs/dev ]; then
  mkdir -p docs/history/dev-legacy
  shopt -s dotglob nullglob
  mv docs/dev/* docs/history/dev-legacy/ || true
  shopt -u dotglob nullglob
  rmdir docs/dev 2>/dev/null || true
  echo "moved: docs/dev/* -> docs/history/dev-legacy/"
fi

if [ -d docs/prod ]; then
  mkdir -p docs/history/prod-legacy
  shopt -s dotglob nullglob
  mv docs/prod/* docs/history/prod-legacy/ || true
  shopt -u dotglob nullglob
  rmdir docs/prod 2>/dev/null || true
  echo "moved: docs/prod/* -> docs/history/prod-legacy/"
fi

# Promote report-style files into ADR/history equivalents if present.
move_if_exists docs/history/reference-source-material/ENTERPRISE_NATS_HARDENING_REPORT.md docs/adr/ADR-005-enterprise-nats-hardening.md
move_if_exists docs/history/reference-source-material/LEGACY_INTENT_REMOVAL_REPORT.md docs/adr/ADR-006-legacy-intent-removal.md
move_if_exists docs/history/reference-source-material/IAC_ARCHITECTURE_SYNC_REPORT.md docs/adr/ADR-007-iac-architecture-sync.md
move_if_exists docs/history/reference-source-material/UI_UX_ARCHITECTURE_SYNC_REPORT.md docs/adr/ADR-008-ui-ux-architecture-sync.md
move_if_exists docs/history/reference-source-material/PYTHON_API_RETIREMENT_REPORT.md docs/adr/ADR-009-python-api-retirement.md

# Keep copies of phase reports in history/migration-reports if still present.
for f in docs/history/reference-source-material/*PHASE*.md docs/history/reference-source-material/SECOND_PASS_FASTAPI_NATS_ONLY_REPORT.md docs/history/reference-source-material/SANITIZATION_REPORT.md; do
  [ -e "$f" ] || continue
  mv "$f" "docs/history/migration-reports/$(basename "$f")"
  echo "moved: $f -> docs/history/migration-reports/$(basename "$f")"
done

# Normalize current live-document filenames expected by mkdocs.yml.
move_if_exists docs/product/pocket_lab_ui_screen_reference_manual.md docs/product/ui-screen-reference.md
move_if_exists docs/api/pocket_lab_backend_api_contract_reference.md docs/api/backend-api-contract.md
move_if_exists docs/runtime/pocket_lab_nats_jetstream_event_contract.md docs/runtime/nats-jetstream-event-contract.md
move_if_exists docs/runtime/pocket_lab_typed_operations_catalog.md docs/runtime/typed-operations-catalog.md

# Architecture blueprint fallback: if only HTML exists, keep it in docs/architecture but nav will point to HTML.
if [ -e docs/architecture/pocket_lab_enterprise_architecture_blueprint.md ]; then
  move_if_exists docs/architecture/pocket_lab_enterprise_architecture_blueprint.md docs/architecture/enterprise-architecture-blueprint.md
fi

if [ -e docs/architecture/pocket_lab_enterprise_architecture_blueprint.html ]; then
  move_if_exists docs/architecture/pocket_lab_enterprise_architecture_blueprint.html docs/architecture/enterprise-architecture-blueprint.html
fi

# If architecture blueprint is currently missing but present in old generated names elsewhere, copy it.
copy_if_missing docs/history/prod-legacy/production-architecture.md docs/architecture/enterprise-architecture-blueprint.md

# Add section README files for history and ADR.
cat > docs/history/README.md <<'EOM'
# Historical Documentation Archive

This section stores historical implementation reports, migration records, and original source material that explain how Pocket Lab evolved.

These files are retained for auditability and maintainership, but they are not the primary operator documentation.
EOM

cat > docs/adr/README.md <<'EOM'
# Architecture Decision Records

This section captures major Pocket Lab architecture decisions, migrations, and retired compatibility paths.

Use ADRs to understand why the current FastAPI, NATS/JetStream, typed-operation, and event-sourced workflow architecture exists.
EOM

# Patch mkdocs.yml references and navigation.
python3 - <<'PY'
from pathlib import Path

p = Path("mkdocs.yml")
if not p.exists():
    raise SystemExit("mkdocs.yml not found")

text = p.read_text()

# Fix known stale nav references.
replacements = {
    "architecture/enterprise-architecture-blueprint.html": "architecture/enterprise-architecture-blueprint.html",
    "product/pocket_lab_ui_screen_reference_manual.md": "product/ui-screen-reference.md",
    "product/ui-screen-reference.md": "product/ui-screen-reference.md",
    "api/pocket_lab_backend_api_contract_reference.md": "api/backend-api-contract.md",
    "api/backend-api-contract.md": "api/backend-api-contract.md",
    "runtime/pocket_lab_nats_jetstream_event_contract.md": "runtime/nats-jetstream-event-contract.md",
    "runtime/nats-jetstream-event-contract.md": "runtime/nats-jetstream-event-contract.md",
    "runtime/pocket_lab_typed_operations_catalog.md": "runtime/typed-operations-catalog.md",
    "runtime/typed-operations-catalog.md": "runtime/typed-operations-catalog.md",
}

for old, new in replacements.items():
    text = text.replace(old, new)

# If markdown architecture exists, prefer markdown in nav; otherwise keep html.
if Path("docs/architecture/enterprise-architecture-blueprint.md").exists():
    text = text.replace(
        "architecture/enterprise-architecture-blueprint.html",
        "architecture/enterprise-architecture-blueprint.md",
    )

# Reduce noisy git plugin warnings.
text = text.replace(
"""  - git-revision-date-localized:
      enable_creation_date: true""",
"""  - git-revision-date-localized:
      enable_creation_date: true
      enable_git_follow: false"""
)

# Add History/ADR nav entries if not present.
if "  - History:" not in text:
    nav_insert = """
  - ADR:
      - Overview: adr/README.md

  - History:
      - Overview: history/README.md
"""
    marker = "\n  - Observability:"
    if marker in text:
        text = text.replace(marker, nav_insert + marker)
    else:
        text += nav_insert

p.write_text(text)
print("patched mkdocs.yml")
PY

echo
echo "==> Validating expected docs paths"
missing=0
for f in \
  docs/product/ui-screen-reference.md \
  docs/api/backend-api-contract.md \
  docs/runtime/nats-jetstream-event-contract.md \
  docs/runtime/typed-operations-catalog.md \
  docs/history/README.md \
  docs/adr/README.md
do
  if [ ! -e "$f" ]; then
    echo "MISSING: $f"
    missing=1
  else
    echo "OK: $f"
  fi
done

if [ "$missing" -ne 0 ]; then
  echo "Some expected docs are missing. Review moved files above."
  exit 1
fi

echo
echo "==> Done. Run: mkdocs build --strict"
