"""Repository-root validation for the Pocket Lab developer MCP."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


class RepositoryRootError(RuntimeError):
    """Raised when the server is not pointed at a Pocket Lab checkout."""


REQUIRED_MARKERS = (
    ".git",
    "AGENTS.md",
    "engineering/codex",
)


def _git_top_level(root: Path) -> Path:
    """Return the native Git top-level for ``root`` or reject the candidate."""

    environment = {name: os.environ[name] for name in ("PATH", "HOME", "LANG", "LC_ALL") if name in os.environ}
    try:
        result = subprocess.run(
            ("git", "rev-parse", "--show-toplevel"),
            cwd=root,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
            check=False,
            shell=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RepositoryRootError(f"native Git root validation failed at {root}") from exc
    if result.returncode != 0 or not result.stdout.strip():
        raise RepositoryRootError(f"native Git root validation failed at {root}")
    return Path(result.stdout.strip()).resolve()


def default_repository_root() -> Path:
    """Return the only configurable local repository candidate.

    The value is process configuration, not an MCP tool argument. It is still
    validated before it can become a subprocess working directory.
    """

    configured = os.environ.get("POCKETLAB_REPO")
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.home() / "pocket-lab-lite").resolve()


def validate_repository_root(candidate: Path) -> Path:
    """Resolve and validate the minimal Pocket Lab repository evidence."""

    root = candidate.expanduser().resolve()
    missing = [marker for marker in REQUIRED_MARKERS if not (root / marker).exists()]
    if missing:
        markers = ", ".join(missing)
        raise RepositoryRootError(
            f"Pocket Lab repository validation failed at {root}: missing {markers}"
        )
    if not root.is_dir():
        raise RepositoryRootError(f"Pocket Lab repository root is not a directory: {root}")
    if _git_top_level(root) != root:
        raise RepositoryRootError(f"Git top-level does not match Pocket Lab repository root: {root}")
    return root


def resolve_repository_root() -> Path:
    """Resolve the validated repository root used by every MCP operation."""

    return validate_repository_root(default_repository_root())
