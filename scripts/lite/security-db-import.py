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

from api_fastapi.services.lite_security_store import (  # noqa: E402
    SecuritySQLiteRepository,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Preview or import legacy JSON Security state into the SQLite shadow store."
    )
    parser.add_argument(
        "--source-root",
        type=Path,
        help="Security directory containing security_state.json, runs/, and evidence/.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write the idempotent import. Without this flag the command is a preview.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-import unchanged source data. Valid only with --apply.",
    )
    parser.add_argument(
        "--reconcile",
        action="store_true",
        help=(
            "Make SQLite exactly match the canonical JSON run set, rebuild "
            "latest-profile projections, and roll back unless parity converges."
        ),
    )
    parser.add_argument(
        "--hash-small-evidence",
        action="store_true",
        help="Hash only evidence files within the configured bounded size limit.",
    )
    args = parser.parse_args()
    if args.force and not args.apply:
        parser.error("--force requires --apply")
    try:
        report = SecuritySQLiteRepository().import_legacy_state(
            source_root=args.source_root,
            preview=not args.apply,
            hash_evidence=bool(args.hash_small_evidence and args.apply),
            force=bool(args.force),
            reconcile=bool(args.reconcile),
        )
    except Exception as exc:  # CLI boundary: never print source payloads or paths.
        print(
            json.dumps({"ok": False, "error_type": type(exc).__name__}, indent=2),
            file=sys.stderr,
        )
        return 2
    print(json.dumps({"ok": True, **report}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
