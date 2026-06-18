#!/usr/bin/env python3
from __future__ import annotations

import json
from runbook_catalog_lib import CATALOG_JSON, ROOT, validate_all, write_catalog


def main() -> None:
    validate_all()
    catalog = write_catalog()
    if not CATALOG_JSON.exists():
        raise SystemExit(f"ERROR: missing generated catalog: {CATALOG_JSON.relative_to(ROOT)}")
    loaded = json.loads(CATALOG_JSON.read_text(encoding="utf-8"))
    if loaded.get("metadata", {}).get("name") != catalog.get("metadata", {}).get("name"):
        raise SystemExit("ERROR: generated runbook catalog metadata mismatch")
    print("Runbook catalog check passed")
    print(f"Runbooks: {catalog['summary']['runbookCount']}")
    print(f"Typed operation step references: {catalog['summary']['operationReferenceCount']}")


if __name__ == "__main__":
    main()
