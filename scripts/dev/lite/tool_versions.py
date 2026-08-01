#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import subprocess
from pathlib import Path

COMMANDS = {
    "node": ["node", "--version"],
    "npm": ["npm", "--version"],
    "python": ["python3", "--version"],
    "java": ["java", "-version"],
    "task": ["task", "--version"],
    "chrome": ["/usr/bin/google-chrome", "--version"],
    "playwright": ["npx", "--no-install", "playwright", "--version"],
    "storybook": ["npx", "--no-install", "storybook", "--version"],
    "redocly": ["npx", "--no-install", "redocly", "--version"],
    "mkdocs": [".venv/bin/python", "-m", "mkdocs", "--version"],
}
EXPECTED = {
    "node": "24.16.0",
    "npm": "11.13.0",
    "python": "3.14.4",
    "java": "17.0.19",
    "task": "3.50.0",
    "chrome": "149.0.7827.102",
    "playwright": "1.60.0",
    "storybook": "8.6.18",
    "redocly": "2.31.6",
    "mkdocs": "1.6.1",
}


def version_from(value: str) -> str:
    match = re.search(r"(?<!\d)(\d+\.\d+(?:\.\d+){0,2})(?!\d)", value)
    return match.group(1) if match else ""


def is_wsl() -> bool:
    return "microsoft" in platform.release().lower()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=".pocketlab-dev/validation/protected-tool-versions.json")
    parser.add_argument("--enforce", action="store_true")
    args = parser.parse_args()
    enforce = args.enforce or os.environ.get("POCKETLAB_ENFORCE_PROTECTED_VERSIONS") == "1" or (is_wsl() and not os.environ.get("CI"))
    results = {}
    failed = False
    for name, command in COMMANDS.items():
        expected = EXPECTED[name]
        if name == "chrome" and not Path(command[0]).exists():
            results[name] = {
                "status": "not-applicable" if os.environ.get("CI") else "failed",
                "expected_before": expected,
                "observed_after": None,
                "changed": None,
                "value": "external browser required on WSL2; CI may use Playwright-managed Chromium",
            }
            failed |= enforce and not os.environ.get("CI")
            continue
        try:
            run = subprocess.run(command, text=True, capture_output=True, timeout=20)
        except (OSError, subprocess.TimeoutExpired) as exc:
            results[name] = {
                "status": "failed",
                "expected_before": expected,
                "observed_after": None,
                "changed": None,
                "value": type(exc).__name__,
            }
            failed = True
            continue
        raw = (run.stdout or run.stderr).strip()
        first_line = raw.splitlines()[0] if raw else ""
        observed = version_from(raw)
        matches = observed == expected
        status = "passed" if run.returncode == 0 and (matches or not enforce) else "failed"
        results[name] = {
            "status": status,
            "expected_before": expected,
            "observed_after": observed or None,
            "changed": False if matches else True,
            "value": first_line,
            "strictly_enforced": enforce,
        }
        failed |= run.returncode != 0 or (enforce and not matches)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 2,
        "baseline_verified_at": "2026-08-01",
        "baseline_environment": "Ubuntu 26.04 under WSL2",
        "strictly_enforced": enforce,
        "protected_tools": results,
    }
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(results, indent=2, sort_keys=True))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
