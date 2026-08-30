"""Repository-owned MCP tooling for bounded Pocket Lab Lite development work."""

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.mcpserver import MCPServer


def create_server(repository_root: Path | None = None) -> "MCPServer":
    """Lazily expose the server factory without affecting ``python -m`` startup."""

    from .server import create_server as implementation

    return implementation(repository_root)


__all__ = ["create_server"]
