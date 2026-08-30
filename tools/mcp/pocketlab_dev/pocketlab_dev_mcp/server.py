"""Stdio MCP server exposing bounded Pocket Lab developer tools."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from mcp.server.mcpserver import MCPServer
from mcp_types import ToolAnnotations

from .config import resolve_repository_root, validate_repository_root
from .tools.repository import RepositoryTools
from .tools.diagnostics import DiagnosticTools
from .tools.validation import ValidationTools

ValidationTargetId = Literal[
    "mcp_unit_tests",
    "mcp_python_compile",
    "mcp_shell_syntax",
    "git_diff_check",
    "backend_lite_api",
    "frontend_build",
    "lite_api_check",
    "docs_check",
    "lite_check",
]
DiagnosticTargetId = Literal[
    "docs_health",
    "generated_drift",
    "runtime_capture",
    "pm2_status",
    "nats_health",
    "openapi_routes",
    "security_summary",
    "pm2_summary",
    "security_run_summary",
]

READ_ONLY_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)
VALIDATION_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    openWorldHint=False,
)


def create_server(repository_root: Path | None = None) -> MCPServer:
    """Build a server only after the Pocket Lab root has been verified."""

    root = validate_repository_root(repository_root) if repository_root else resolve_repository_root()
    repository_tools = RepositoryTools(root)
    validation_tools = ValidationTools(root)
    diagnostic_tools = DiagnosticTools(root)
    server = MCPServer(
        "pocketlab-dev-mcp",
        title="Pocket Lab developer MCP",
        description="Bounded local repository status and validation tooling.",
    )

    @server.tool(
        name="repo_status",
        description="Return compact current local Git repository status.",
        annotations=READ_ONLY_ANNOTATIONS,
        structured_output=True,
    )
    def repo_status() -> dict[str, Any]:
        return repository_tools.repo_status()

    @server.tool(
        name="changed_files",
        description="Return bounded changed-file classifications from a fixed scope.",
        annotations=READ_ONLY_ANNOTATIONS,
        structured_output=True,
    )
    def changed_files(
        scope: Literal["working_tree", "branch_vs_origin_main"] = "working_tree",
    ) -> dict[str, Any]:
        return repository_tools.changed_files(scope)

    @server.tool(
        name="validation_targets",
        description="List the ordered, fixed validation allow-list.",
        annotations=READ_ONLY_ANNOTATIONS,
        structured_output=True,
    )
    def validation_targets() -> dict[str, Any]:
        return validation_tools.validation_targets()

    @server.tool(
        name="run_validation",
        description="Run one approved local validation target by identifier.",
        annotations=VALIDATION_ANNOTATIONS,
        structured_output=True,
    )
    def run_validation(target: ValidationTargetId) -> dict[str, Any]:
        return validation_tools.run_validation(target)

    @server.tool(
        name="diagnostic_targets",
        description="List the ordered, fixed read-only diagnostic allow-list.",
        annotations=READ_ONLY_ANNOTATIONS,
        structured_output=True,
    )
    def diagnostic_targets() -> dict[str, Any]:
        return diagnostic_tools.diagnostic_targets()

    @server.tool(
        name="diagnostic_summary",
        description="Return one bounded read-only developer diagnostic by identifier.",
        annotations=READ_ONLY_ANNOTATIONS,
        structured_output=True,
    )
    def diagnostic_summary(target: DiagnosticTargetId) -> dict[str, Any]:
        return diagnostic_tools.diagnostic_summary(target)

    return server


def main() -> None:
    """Run the server exclusively over stdio without startup output."""

    create_server().run(transport="stdio")


if __name__ == "__main__":  # pragma: no cover - exercised through stdio smoke check
    main()
