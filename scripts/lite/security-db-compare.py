#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "pocket-lab-final-structure" / "runtime"
if str(RUNTIME) not in sys.path:
    sys.path.insert(0, str(RUNTIME))

from api_fastapi.services import lite_security_evidence  # noqa: E402
from api_fastapi.services.lite_security_store import (  # noqa: E402
    SecuritySQLiteRepository,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare bounded JSON and SQLite Security projections."
    )
    parser.add_argument(
        "--no-record",
        action="store_true",
        help="Do not record comparison metadata in SQLite.",
    )
    args = parser.parse_args()
    try:
        state = lite_security_evidence.read_state() or {}
        result = SecuritySQLiteRepository().compare_json_state(
            state, record=not args.no_record
        )
    except Exception as exc:  # CLI boundary: preserve JSON source privacy.
        print(
            json.dumps({"ok": False, "error_type": type(exc).__name__}, indent=2),
            file=sys.stderr,
        )
        return 2
    print(json.dumps({"ok": True, **result}, indent=2))
    return 0 if result.get("matched") else 3


if __name__ == "__main__":
    raise SystemExit(main())
