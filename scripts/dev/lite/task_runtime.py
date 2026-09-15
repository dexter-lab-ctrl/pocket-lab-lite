#!/usr/bin/env python3
"""Bounded Task runtime launcher for supported Pocket Lab Lite phone commands.

DEV-PC tasks keep the Taskfile-provided Python and development environment.
On Android/Termux, only the explicitly routed commands use the installed runtime
Python and scrub repository-development state so the production launcher owns
POCKETLAB_STATE_DIR and POCKETLAB_ENVIRONMENT.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

DEV_ONLY_ENV = (
    "STATE_DIR",
    "VALIDATION_DIR",
    "POCKETLAB_STATE_DIR",
    "POCKETLAB_ENV",
    "POCKETLAB_DEV_PYTHON",
    "POCKETLAB_DEV_TMPDIR",
)


def is_termux(env: dict[str, str] | None = None) -> bool:
    values = env if env is not None else os.environ
    return bool(values.get("TERMUX_VERSION")) or Path("/data/data/com.termux/files/usr").is_dir()


def runtime_python(env: dict[str, str] | None = None) -> str:
    values = env if env is not None else os.environ
    path = values.get("PATH")
    for name in ("python3", "python"):
        candidate = shutil.which(name, path=path)
        if candidate:
            return candidate
    raise RuntimeError("No supported runtime Python (python3/python) is available.")


def sanitized_phone_env(env: dict[str, str] | None = None) -> dict[str, str]:
    result = dict(env if env is not None else os.environ)
    for key in DEV_ONLY_ENV:
        result.pop(key, None)
    # Normal runtime remains production/default-off unless the explicit
    # qualification launcher sets POCKETLAB_ENVIRONMENT itself.
    result.pop("POCKETLAB_ENVIRONMENT", None)
    return result


def build_command(args: argparse.Namespace, env: dict[str, str] | None = None) -> tuple[list[str], dict[str, str]]:
    current = dict(env if env is not None else os.environ)
    phone = is_termux(current)
    child_env = sanitized_phone_env(current) if phone else current
    if args.mode == "python":
        executable = runtime_python(child_env) if phone else args.dev_python
        return [executable, *args.command], child_env
    if args.mode == "shell":
        shell = shutil.which("bash", path=child_env.get("PATH")) or "bash"
        return [shell, *args.command], child_env
    raise ValueError("unsupported task runtime mode")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("python", "shell"))
    parser.add_argument("--dev-python", default=".venv/bin/python")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.command and args.command[0] == "--":
        args.command = args.command[1:]
    if not args.command:
        parser.error("a fixed repository command is required")
    command, child_env = build_command(args)
    os.execvpe(command[0], command, child_env)
    return 127


if __name__ == "__main__":
    raise SystemExit(main())
