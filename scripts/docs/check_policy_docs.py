#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from generate_policy_evidence import ROOT
from generate_policy_docs import render_outputs


def main() -> int:
    stale = []
    for rel_path, expected in render_outputs().items():
        path = ROOT / rel_path
        if not path.exists():
            stale.append(f"missing: {rel_path}")
            continue
        actual = path.read_text(encoding="utf-8")
        if actual != expected:
            stale.append(f"stale: {rel_path}")
    if stale:
        print("Generated policy docs are stale. Run: task docs:security:policies")
        for item in stale:
            print(f"- {item}")
        return 1
    print("Generated policy docs are fresh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
