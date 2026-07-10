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

from api_fastapi.db.health import database_health  # noqa: E402
from api_fastapi.db.migrations import apply_migrations  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Apply Pocket Lab Lite SQLite migrations safely."
    )
    parser.parse_args()
    try:
        applied = apply_migrations()
        health = database_health()
    except Exception as exc:  # CLI boundary: report only the sanitized error type.
        print(
            json.dumps({"ok": False, "error_type": type(exc).__name__}, indent=2),
            file=sys.stderr,
        )
        return 2
    print(json.dumps({"ok": True, "applied_versions": applied, "health": health}, indent=2))
    return 0 if health.get("schema_current") else 2


if __name__ == "__main__":
    raise SystemExit(main())
