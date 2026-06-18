#!/usr/bin/env python3
from __future__ import annotations

from runbook_catalog_lib import CATALOG_JSON, ROOT, write_catalog


def main() -> None:
    write_catalog()
    print(f"Wrote {CATALOG_JSON.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
