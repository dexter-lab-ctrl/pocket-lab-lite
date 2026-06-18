#!/usr/bin/env python3
from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WATCHED = [
    "contracts/operations/pocketlab-typed-operations.json",
    "docs/runtime/typed-operations-catalog.md",
    "docs/runtime/generated/typed-operations-catalog",
]


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, cwd=ROOT, check=True)


def diff() -> str:
    result = subprocess.run(
        ["git", "diff", "--", *WATCHED],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return result.stdout


def main() -> None:
    run(["python3", "scripts/docs/generate_operations_docs.py"])
    output = diff()
    if output.strip():
        print("Generated typed operations docs are not fresh.")
        print("Run: task docs:operations")
        print(output[:4000])
        raise SystemExit(1)

    print("Generated typed operations docs are fresh.")


if __name__ == "__main__":
    main()
