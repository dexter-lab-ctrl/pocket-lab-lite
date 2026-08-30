"""Immutable validation allow-list for the Pocket Lab developer MCP."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True)
class ValidationTarget:
    identifier: str
    description: str
    command_label: str
    argv: tuple[str, ...]
    timeout_seconds: int
    side_effect_class: str


class UnknownValidationTarget(ValueError):
    """Raised before execution for any non-allow-listed validation id."""


def build_validation_targets(
    python_executable: str | None = None,
) -> Mapping[str, ValidationTarget]:
    """Build fixed argv definitions from commands confirmed in this repository."""

    python = python_executable or sys.executable
    targets = (
        ValidationTarget(
            "mcp_unit_tests",
            "Run the isolated Pocket Lab MCP unit tests.",
            "MCP unit tests",
            (python, "-m", "pytest", "-q", "tools/mcp/pocketlab_dev/tests"),
            120,
            "development-test-cache",
        ),
        ValidationTarget(
            "mcp_python_compile",
            "Compile the Pocket Lab MCP Python modules.",
            "MCP Python compile",
            (
                python,
                "-m",
                "py_compile",
                "tools/mcp/pocketlab_dev/pocketlab_dev_mcp/__init__.py",
                "tools/mcp/pocketlab_dev/pocketlab_dev_mcp/config.py",
                "tools/mcp/pocketlab_dev/pocketlab_dev_mcp/policy.py",
                "tools/mcp/pocketlab_dev/pocketlab_dev_mcp/redaction.py",
                "tools/mcp/pocketlab_dev/pocketlab_dev_mcp/runner.py",
                "tools/mcp/pocketlab_dev/pocketlab_dev_mcp/server.py",
                "tools/mcp/pocketlab_dev/pocketlab_dev_mcp/tools/__init__.py",
                "tools/mcp/pocketlab_dev/pocketlab_dev_mcp/tools/repository.py",
                "tools/mcp/pocketlab_dev/pocketlab_dev_mcp/tools/validation.py",
            ),
            30,
            "none",
        ),
        ValidationTarget(
            "mcp_shell_syntax",
            "Check the Pocket Lab MCP launcher and transport-check shell syntax.",
            "MCP shell syntax",
            (
                "bash",
                "-n",
                "scripts/dev/codex/run_pocketlab_mcp.sh",
                "scripts/dev/codex/check_mcp_dev.sh",
            ),
            30,
            "none",
        ),
        ValidationTarget(
            "git_diff_check",
            "Check the current working-tree diff for whitespace errors.",
            "Git diff check",
            ("git", "diff", "--check"),
            30,
            "none",
        ),
        ValidationTarget(
            "backend_lite_api",
            "Run the focused Lite API regression test.",
            "Focused Lite API test",
            ("python3", "-m", "pytest", "-q", "tests/backend/test_lite_api.py"),
            180,
            "development-test-state",
        ),
        ValidationTarget(
            "frontend_build",
            "Build the repository frontend.",
            "Frontend build",
            ("npm", "run", "build"),
            300,
            "build-artifacts",
        ),
        ValidationTarget(
            "lite_api_check",
            "Run the established Lite API task.",
            "Lite API task",
            ("task", "lite:api:check"),
            300,
            "development-test-state",
        ),
        ValidationTarget(
            "docs_check",
            "Run the strict documentation check task.",
            "Documentation check",
            ("task", "lite:docs:check"),
            900,
            "development-test-cache",
        ),
        ValidationTarget(
            "lite_check",
            "Run the full local Lite validation task.",
            "Full Lite check",
            ("task", "lite:check"),
            1800,
            "development-test-cache-and-build-artifacts",
        ),
    )
    return MappingProxyType({target.identifier: target for target in targets})


VALIDATION_TARGETS = build_validation_targets()


def get_validation_target(target: str) -> ValidationTarget:
    try:
        return VALIDATION_TARGETS[target]
    except KeyError as exc:
        raise UnknownValidationTarget(f"unknown validation target: {target}") from exc


def validation_target_metadata() -> list[dict[str, object]]:
    return [
        {
            "id": target.identifier,
            "description": target.description,
            "command_label": target.command_label,
            "timeout_seconds": target.timeout_seconds,
            "side_effect_class": target.side_effect_class,
        }
        for target in VALIDATION_TARGETS.values()
    ]
