from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from contracts import OperationRequest, OperationTarget, utc_now_iso


def _env(name: str, default: str) -> str:
    value = os.environ.get(name, default)
    return value if value is not None else default


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _normalize_tag(tag: str) -> str:
    return (tag or "").strip()


def _fetch_json(url: str, timeout: float = 10.0) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json, application/json",
            "User-Agent": "Pocket-Lab-Release-Agent",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8")
        return json.loads(body or "{}")


@dataclass
class ReleaseUpdateState:
    phase: str = "idle"
    current_tag: str = "unknown"
    latest_tag: str = "unknown"
    latest_release: dict[str, Any] = field(default_factory=dict)
    applied_release: dict[str, Any] = field(default_factory=dict)
    update_available: bool = False
    auto_apply: bool = True
    last_checked_at: Optional[str] = None
    last_applied_at: Optional[str] = None
    error: Optional[str] = None
    operations: list[dict[str, Any]] = field(default_factory=list)

    def asdict(self) -> dict[str, Any]:
        return {
            "phase": self.phase,
            "current_tag": self.current_tag,
            "latest_tag": self.latest_tag,
            "latest_release": self.latest_release,
            "applied_release": self.applied_release,
            "update_available": self.update_available,
            "auto_apply": self.auto_apply,
            "last_checked_at": self.last_checked_at,
            "last_applied_at": self.last_applied_at,
            "error": self.error,
            "operations": self.operations,
        }


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
        self.state_path = self.state_dir / "release_auto_update.json"
        self.github_repo = (
            github_repo or _env("POCKETLAB_GITHUB_REPO", "dexter-lab-ctrl/pocket-lab")
        ).strip()
        self.github_api = _env(
            "POCKETLAB_GITHUB_RELEASES_API",
            f"https://api.github.com/repos/{self.github_repo}/releases/latest",
        )
        self.current_tag_override = _normalize_tag(
            current_tag or _env("POCKETLAB_RELEASE_TAG", "v1.0.0")
        )
        self.auto_apply = bool(
            auto_apply
            if auto_apply is not None
            else _env("POCKETLAB_AUTO_RELEASE_APPLY", "true").strip().lower()
            in {"1", "true", "yes", "on"}
        )
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._state = self._load_state()
        self._state.auto_apply = self.auto_apply
        if not self._state.current_tag or self._state.current_tag == "unknown":
            self._state.current_tag = self.current_tag_override
        self._save_state()

    def _load_state(self) -> ReleaseUpdateState:
        payload = _read_json(self.state_path, {})
        return ReleaseUpdateState(
            phase=str(payload.get("phase") or "idle"),
            current_tag=str(payload.get("current_tag") or self.current_tag_override),
            latest_tag=str(payload.get("latest_tag") or "unknown"),
            latest_release=dict(payload.get("latest_release") or {}),
            applied_release=dict(payload.get("applied_release") or {}),
            update_available=bool(payload.get("update_available", False)),
            auto_apply=bool(payload.get("auto_apply", self.auto_apply)),
            last_checked_at=payload.get("last_checked_at"),
            last_applied_at=payload.get("last_applied_at"),
            error=payload.get("error"),
            operations=list(payload.get("operations") or []),
        )

    def _save_state(self) -> None:
        _write_json(self.state_path, self._state.asdict())

    def _set_state(self, **fields: Any) -> dict[str, Any]:
        with self._lock:
            for key, value in fields.items():
                setattr(self._state, key, value)
            self._save_state()
            return self._state.asdict()

    def _current_tag(self) -> str:
        if self._state.current_tag and self._state.current_tag != "unknown":
            return self._state.current_tag
        if self.current_tag_override:
            return self.current_tag_override
        return "unknown"

    def _latest_release(self, timeout: float = 10.0) -> dict[str, Any]:
        try:
            release = _fetch_json(self.github_api, timeout=timeout)
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Unable to reach GitHub releases API: {exc}") from exc
        except Exception as exc:
            raise RuntimeError(
                f"Unable to load latest release metadata: {exc}"
            ) from exc

        tag_name = _normalize_tag(
            str(release.get("tag_name") or release.get("name") or "")
        )
        release["tag_name"] = tag_name or "unknown"
        release.setdefault("html_url", "")
        release.setdefault("name", release.get("tag_name", ""))
        release.setdefault("body", "")
        release.setdefault("published_at", None)
        release.setdefault("draft", False)
        release.setdefault("prerelease", False)
        return release

    def check_once(self) -> dict[str, Any]:
        latest = self._latest_release()
        latest_tag = _normalize_tag(str(latest.get("tag_name") or "unknown"))
        current_tag = _normalize_tag(self._current_tag())
        update_available = bool(latest_tag and latest_tag != current_tag)
        state = self._set_state(
            phase="available" if update_available else "current",
            current_tag=current_tag,
            latest_tag=latest_tag,
            latest_release=latest,
            update_available=update_available,
            last_checked_at=utc_now_iso(),
            error=None,
        )
        return state

    def _submit_operation(
        self,
        operation: str,
        target_type: str,
        target_ref: str,
        params: Optional[dict[str, Any]] = None,
        timeout: int = 900,
    ) -> dict[str, Any]:
        request = OperationRequest(
            operation=operation,
            target=OperationTarget(type=target_type, ref=target_ref),
            params=dict(params or {}),
            dry_run=False,
        )
        submitted = self.operation_service.submit(request)
        job_id = submitted.get("job_id")
        if not job_id:
            raise RuntimeError(f"{operation} did not return a job id")

        started = time.time()
        while time.time() - started < timeout:
            run = self.operation_service.get(job_id)
            if run and str(run.get("status")).lower() in {
                "succeeded",
                "failed",
                "canceled",
            }:
                if str(run.get("status")).lower() != "succeeded":
                    raise RuntimeError(
                        run.get("error") or run.get("stderr") or f"{operation} failed"
                    )
                return run
            time.sleep(0.5)
        raise TimeoutError(f"Timed out waiting for {operation} to complete")

    def apply_latest(self, *, force: bool = False) -> dict[str, Any]:
        with self._lock:
            state = self._state.asdict()
            if not force and not state.get("update_available"):
                return state
            self._set_state(phase="applying", error=None)

        operations: list[dict[str, Any]] = []
        try:
            prepare_run = self._submit_operation(
                "release_prepare", "backup", "release", {"scope": "full"}
            )
            operations.append(
                {
                    "operation": "release_prepare",
                    "job_id": prepare_run.get("job_id"),
                    "status": prepare_run.get("status"),
                }
            )

            sync_run = self._submit_operation(
                "release_sync", "repo", "pocket_lab_iac", {"branch": "main"}
            )
            operations.append(
                {
                    "operation": "release_sync",
                    "job_id": sync_run.get("job_id"),
                    "status": sync_run.get("status"),
                }
            )

            if self.refresh_catalog is not None:
                self.refresh_catalog()
                operations.append(
                    {
                        "operation": "catalog_refresh",
                        "job_id": None,
                        "status": "succeeded",
                    }
                )

            deploy_run = self._submit_operation(
                "release_deploy",
                "repo",
                "pocket_lab_iac",
                {
                    "playbook": "site.yml",
                    "source_type": "repo",
                    "source": "pocket_lab_iac",
                },
            )
            operations.append(
                {
                    "operation": "release_deploy",
                    "job_id": deploy_run.get("job_id"),
                    "status": deploy_run.get("status"),
                }
            )

            verify_run = self._submit_operation(
                "release_verify", "drift", "workspace", {"scope": "all"}
            )
            operations.append(
                {
                    "operation": "release_verify",
                    "job_id": verify_run.get("job_id"),
                    "status": verify_run.get("status"),
                }
            )

            latest = self._state.latest_release or self._latest_release()
            latest_tag = _normalize_tag(str(latest.get("tag_name") or "unknown"))
            current_tag = latest_tag or self._current_tag()
            state = self._set_state(
                phase="applied",
                current_tag=current_tag,
                latest_tag=latest_tag,
                latest_release=latest,
                applied_release=latest,
                update_available=False,
                last_applied_at=utc_now_iso(),
                error=None,
                operations=operations,
            )
            return state
        except Exception as exc:
            state = self._set_state(
                phase="error",
                error=str(exc),
                operations=operations,
            )
            return state

    def status(self) -> dict[str, Any]:
        with self._lock:
            state = self._state.asdict()
        if not state.get("current_tag") or state.get("current_tag") == "unknown":
            state["current_tag"] = self._current_tag()
        return state

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        def _loop() -> None:
            while not self._stop.is_set():
                try:
                    state = self.check_once()
                    if state.get("update_available") and state.get("auto_apply"):
                        self.apply_latest()
                except Exception as exc:
                    self._set_state(
                        phase="error", error=str(exc), last_checked_at=utc_now_iso()
                    )
                self._stop.wait(self.poll_interval)

        self._stop.clear()
        self._thread = threading.Thread(
            target=_loop, name="pocket-lab-release-auto-update", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
