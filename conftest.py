"""Repository-wide pytest development scratch policy."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _pocketlab_dev_scratch_root() -> Path:
    configured = os.environ.get("POCKETLAB_DEV_TMPDIR")
    if configured:
        candidate = Path(configured).expanduser()
        if not candidate.is_absolute():
            candidate = ROOT / candidate
    else:
        candidate = ROOT / ".pocketlab-dev" / "tmp"
    return candidate.resolve()


def pytest_configure(config) -> None:
    """Keep pytest state off small WSL /tmp mounts by default."""
    if config.getoption("basetemp") is not None:
        return

    root = _pocketlab_dev_scratch_root()
    root.mkdir(parents=True, exist_ok=True)
    basetemp = root / "pytest"
    basetemp.mkdir(parents=True, exist_ok=True)
    config.option.basetemp = str(basetemp)
