from __future__ import annotations

"""Compatibility facade for the worker-owned release runtime.

The legacy implementation started ``pocket-lab-release-auto-update`` inside
FastAPI.  That duplicated worker ownership and allowed release metadata work to
hold the API interpreter GIL.  This facade intentionally never starts a thread.
All execution is owned by ``pocket-worker`` and its bounded release subprocess.
"""

import os
from pathlib import Path
from typing import Any, Callable, Optional


def _runtime_service() -> Any:
    from api_fastapi.services import release_runtime  # type: ignore

    return release_runtime


class ReleaseAutoUpdater:
    def __init__(
        self,
        *,
        state_dir: Path,
        operation_service: Any,
        refresh_catalog: Optional[Callable[[], Any]] = None,
        current_tag: Optional[str] = None,
        github_repo: Optional[str] = None,
        poll_interval: int = 180,
        auto_apply: Optional[bool] = None,
    ) -> None:
        self.state_dir = Path(state_dir)
        self.operation_service = operation_service
        self.refresh_catalog = refresh_catalog
        self.poll_interval = max(30, int(poll_interval or 180))
        self.current_tag_override = str(
            current_tag or os.environ.get("POCKETLAB_RELEASE_TAG", "v1.0.0")
        ).strip()
        self.github_repo = str(
            github_repo
            or os.environ.get(
                "POCKETLAB_GITHUB_REPO", "dexter-lab-ctrl/pocket-lab"
            )
        ).strip()
        self.auto_apply = bool(
            auto_apply
            if auto_apply is not None
            else str(os.environ.get("POCKETLAB_AUTO_RELEASE_APPLY", "true")).lower()
            in {"1", "true", "yes", "on"}
        )
        self._thread = None
        self._state = None

    def status(self) -> dict[str, Any]:
        return _runtime_service().read_release_status()

    def start(self) -> bool:
        # Deliberately fail closed in every role.  The worker starts the async
        # scheduler explicitly, so there is never a duplicate compatibility
        # thread hidden behind dependency construction.
        return False

    def stop(self) -> None:
        return None

    def check_once(self) -> dict[str, Any]:
        raise RuntimeError("release_check_is_worker_scheduler_owned")

    def apply_latest(self, *, force: bool = False) -> dict[str, Any]:
        raise RuntimeError("release_apply_is_worker_orchestrator_owned")

    def _set_state(self, **fields: Any) -> dict[str, Any]:
        return _runtime_service().compatibility_update_state(**fields)
