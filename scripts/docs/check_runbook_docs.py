#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from generate_runbook_docs import GENERATED_DIR, MANIFEST_JSON, ROOT, slug
from runbook_catalog_lib import CATALOG_JSON, build_catalog, validate_all

RETIRED_PATTERNS = [
    "legacy" + "_" + "intent",
    "sync" + "_" + "bash",
    "tofu" + "_" + "deploy",
    "/" + "api" + "/" + "action" + "/" + "update",
    "dashboard" + "_" + "api",
]

REQUIRED_SHARED_PAGES = {
    "index.md",
    "operation-map.md",
    "approval-matrix.md",
    "evidence-matrix.md",
    "simple-mode.md",
}


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def validate_no_retired_text(path: Path) -> None:
    text = path.read_text(encoding="utf-8", errors="ignore")
    found = [pattern for pattern in RETIRED_PATTERNS if pattern in text]
    if found:
        fail(f"{rel(path)} contains retired architecture token(s)")


def main() -> None:
    validate_all()

    if not CATALOG_JSON.exists():
        fail(f"missing {rel(CATALOG_JSON)}; run task docs:runbooks")
    if not MANIFEST_JSON.exists():
        fail(f"missing {rel(MANIFEST_JSON)}; run task docs:runbooks")

    catalog = build_catalog()
    manifest = json.loads(MANIFEST_JSON.read_text(encoding="utf-8"))

    if manifest.get("kind") != "RunbookDocsManifest":
        fail("runbook docs manifest kind must be RunbookDocsManifest")
    if manifest.get("metadata", {}).get("tier") != "7B":
        fail("runbook docs manifest tier must be 7B")

    expected_runbook_pages = {f"{slug(runbook['name'])}.md" for runbook in catalog["runbooks"]}
    expected_pages = expected_runbook_pages | REQUIRED_SHARED_PAGES

    for page in expected_pages:
        path = GENERATED_DIR / page
        if not path.exists():
            fail(f"missing generated runbook documentation page: {rel(path)}")
        validate_no_retired_text(path)

    generated_pages = {path.name for path in GENERATED_DIR.glob("*.md")}
    allowed_auxiliary_pages = {"validation-gates.md"}
    stale_pages = sorted(generated_pages - expected_pages - allowed_auxiliary_pages)
    if stale_pages:
        fail("stale generated runbook docs found: " + ", ".join(stale_pages))

    manifest_pages = set(manifest.get("generatedPages", []))
    for page in expected_pages:
        rel_page = rel(GENERATED_DIR / page)
        if rel_page not in manifest_pages:
            fail(f"manifest missing generated page: {rel_page}")

    print("Runbook docs check passed")
    print(f"Runbooks: {catalog['summary']['runbookCount']}")
    print(f"Generated docs pages: {len(expected_pages)}")
    print(f"Typed operation step references: {catalog['summary']['operationReferenceCount']}")


if __name__ == "__main__":
    main()
