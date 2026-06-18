#!/usr/bin/env python3
from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    subprocess.run(
        ["python3", "scripts/docs/generate_operations_contract.py"],
        cwd=ROOT,
        check=True,
    )
    print("Operation metadata validation passed.")


if __name__ == "__main__":
    main()
