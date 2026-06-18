#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


RESULT_DIR = Path(".pocketlab-dev/validation/command-results")


@dataclass(frozen=True)
class Gate:
    gate_id: str
    command: list[str]
    browser_heavy: bool = False


GATES: list[Gate] = [
    Gate("pytest-backend", ["task", "test:backend"]),
    Gate("pytest-performance", ["task", "test:performance"]),
    Gate("playwright-e2e", ["task", "test:e2e"], browser_heavy=True),
    Gate("playwright-visual", ["task", "test:visual"], browser_heavy=True),
    Gate("playwright-a11y", ["task", "test:a11y"], browser_heavy=True),
    Gate("playwright-network", ["task", "test:network"], browser_heavy=True),
    Gate("lighthouse", ["task", "test:lighthouse"], browser_heavy=True),
    Gate("nats-runtime", ["timeout", "--kill-after=15s", "180s", "task", "test:nats"]),
    Gate("nats-permissions", ["timeout", "--kill-after=15s", "180s", "task", "test:nats-permissions"]),
    Gate("redaction", ["timeout", "--kill-after=15s", "180s", "task", "test:redaction"]),
    Gate(
        "faults",
        [
            "bash",
            "scripts/dev/run-validation-gate.sh",
            "300",
            "env",
            "POCKETLAB_FAULTS_WORKERS=1",
            "task",
            "test:faults",
        ],
        browser_heavy=True,
    ),
    Gate(
        "flakes",
        [
            "bash",
            "scripts/dev/run-validation-gate.sh",
            "300",
            "env",
            "POCKETLAB_FLAKES_WORKERS=1",
            "POCKETLAB_FLAKES_REPEAT=1",
            "task",
            "test:flakes",
        ],
        browser_heavy=True,
    ),
    Gate("release-dry-run", ["timeout", "--kill-after=30s", "900s", "task", "release:dry-run"]),
]


def result_path(gate_id: str) -> Path:
    return RESULT_DIR / f"{gate_id}.json"


def already_passed(gate_id: str) -> bool:
    path = result_path(gate_id)
    if not path.exists():
        return False

    try:
        data = json.loads(path.read_text())
    except Exception:
        return False

    return data.get("exit_code") == 0


def cleanup_browser_processes() -> None:
    cleanup_script = Path("scripts/dev/run-validation-gate.sh")
    if cleanup_script.exists():
        subprocess.run(
            ["bash", str(cleanup_script), "5", "true"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )


def record_gate(gate: Gate) -> int:
    if gate.browser_heavy:
        cleanup_browser_processes()

    cmd = [
        sys.executable,
        "scripts/docs/record_validation_result.py",
        gate.gate_id,
        "--",
        *gate.command,
    ]

    print(f"Release gate: {gate.gate_id}")
    print(f"Command: {' '.join(gate.command)}")

    completed = subprocess.run(cmd, check=False)

    if gate.browser_heavy:
        cleanup_browser_processes()

    return completed.returncode


def is_wsl2() -> bool:
    try:
        return "microsoft" in Path("/proc/version").read_text().lower()
    except Exception:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Pocket Lab release validation gates with resume support.")
    parser.add_argument("--force", action="store_true", help="Run all non-browser gates even if prior evidence shows exit_code=0.")
    parser.add_argument("--force-browser-heavy", action="store_true", help="Also rerun browser-heavy gates when --force is used.")
    parser.add_argument("--only", action="append", default=[], help="Run only the specified gate id. Can be repeated.")
    args = parser.parse_args()

    RESULT_DIR.mkdir(parents=True, exist_ok=True)

    selected = set(args.only)
    failures: list[str] = []

    for gate in GATES:
        if selected and gate.gate_id not in selected:
            continue

        if already_passed(gate.gate_id):
            if not args.force:
                print(f"Release gate: {gate.gate_id} already passed; skipping.")
                continue

            if gate.browser_heavy and is_wsl2() and not args.force_browser_heavy:
                print(
                    f"Release gate: {gate.gate_id} already passed; "
                    "skipping browser-heavy WSL2 force rerun. "
                    "Use --force-browser-heavy to override."
                )
                continue

        rc = record_gate(gate)
        if rc != 0:
            failures.append(gate.gate_id)
            print(f"Release gate failed: {gate.gate_id} exit={rc}", file=sys.stderr)
            break

    if failures:
        print("Failed gates: " + ", ".join(failures), file=sys.stderr)
        return 1

    print("Release validation gates completed or resumed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
