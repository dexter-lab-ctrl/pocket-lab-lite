from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

MEDIA_EXTENSIONS = frozenset({
    ".jpg", ".jpeg", ".png", ".gif", ".webp",
    ".heic", ".heif", ".avif", ".dng",
    ".tif", ".tiff", ".bmp",
    ".mp4", ".mov", ".m4v", ".3gp", ".webm", ".mkv", ".avi",
})
COLLECTION_ROOTS = {
    "camera": ("shared", "DCIM"),
    "pictures": ("shared", "Pictures"),
    "videos": ("shared", "Movies"),
}
COLLECTION_DESTINATIONS = {
    "camera": "DCIM",
    "pictures": "Pictures",
    "videos": "Movies",
}
EXCLUDED_DIR_NAMES = frozenset({
    ".thumbnails", "thumbnails", ".cache", "cache",
    "tmp", "temp", "trash", ".trash", ".trashed",
    "documents", "document", "downloads", "download",
    "whatsapp documents", "stickers",
})
TERMINAL_STATUSES = frozenset({
    "completed",
    "partial_storage_limit",
    "cancelled",
    "failed",
    "interrupted",
    "source_offline",
    "destination_unavailable",
})
MAX_REMOTE_LISTING_BYTES = 32 * 1024 * 1024


def _now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _safe_version(text: str) -> str:
    first = (
        str(text or "").splitlines()[0].strip()
        if text
        else ""
    )
    return (
        first[:80]
        if first.lower().startswith("rclone ")
        else "Available"
    )


def _collection_path(collection: str) -> Path:
    parts = COLLECTION_ROOTS[collection]
    return Path.home().joinpath("storage", *parts)


def collect_photo_backup_capabilities() -> dict[str, Any]:
    binary = shutil.which("rclone")
    available_collections = []
    for name in COLLECTION_ROOTS:
        root = _collection_path(name)
        try:
            if (
                root.is_dir()
                and os.access(root, os.R_OK | os.X_OK)
            ):
                available_collections.append(name)
        except OSError:
            continue

    version = "Unavailable"
    if binary:
        try:
            result = subprocess.run(
                [binary, "version"],
                check=False,
                capture_output=True,
                text=True,
                timeout=4,
            )
            if result.returncode == 0:
                version = _safe_version(result.stdout)
        except Exception:
            version = "Available"

    storage_access = bool(available_collections)
    return {
        "rclone_available": bool(binary),
        "rclone_version": version,
        "photo_storage_access": storage_access,
        "collections": available_collections,
        "status": (
            "ready"
            if binary and storage_access
            else "needs_attention"
        ),
        "summary": (
            "Ready to back up photos."
            if binary and storage_access
            else (
                "Allow photo access on this device."
                if binary
                else (
                    "Photo backup tools are not ready "
                    "on this device."
                )
            )
        ),
        "sanitized": True,
    }


def repair_rclone() -> dict[str, Any]:
    """Run only the predefined Termux package repair; never expose installer logs."""
    existing = collect_photo_backup_capabilities()
    if existing["rclone_available"]:
        return {"status": "already_installed", "reason_code": None,
                "summary": "Photo backup tools are already installed.",
                **existing}
    pkg = shutil.which("pkg")
    if not pkg:
        return {"status": "unsupported_platform",
                "reason_code": "rclone_install_failed",
                "summary": "Automatic repair requires the Termux package manager.",
                "rclone_available": False, "sanitized": True}
    reason = None
    try:
        result = subprocess.run(
            [pkg, "install", "-y", "rclone"],
            check=False, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=300,
        )
        if result.returncode != 0:
            reason = "rclone_install_failed"
    except subprocess.TimeoutExpired:
        reason = "rclone_install_timeout"
    except (OSError, subprocess.SubprocessError):
        reason = "rclone_install_failed"
    caps = collect_photo_backup_capabilities()
    if reason is None and not caps["rclone_available"]:
        reason = "rclone_verification_failed"
    if reason is None and caps["rclone_version"] in ("Available", "Unavailable"):
        reason = "rclone_verification_failed"
    return {
        **caps,
        "status": "completed" if reason is None else "failed",
        "reason_code": reason,
        "summary": ("Photo backup tools are ready." if reason is None
                    else "Photo backup tool repair did not complete. Retry when the device and package repository are available."),
        "sanitized": True,
    }


class MediaBackupProvider:
    provider_id = "base"

    def backup(
        self,
        *,
        backup_id: str,
        credential_ref: str,
        collections: list[str],
    ) -> dict[str, Any]:
        raise NotImplementedError

    def cancel(self, backup_id: str) -> None:
        raise NotImplementedError


class PhotoPrismWebDAVProvider(MediaBackupProvider):
    provider_id = "photoprism_webdav"

    def __init__(
        self,
        *,
        node_id: str,
        agent_token: str,
        control_origin: str,
        progress_callback: (
            Callable[[dict[str, Any]], None] | None
        ) = None,
    ) -> None:
        self.node_id = str(node_id or "").strip()
        self.agent_token = str(agent_token or "")
        self.control_origin = (
            str(control_origin or "").strip().rstrip("/")
        )
        self.progress_callback = progress_callback
        self.cancel_event = threading.Event()
        self._process_lock = threading.RLock()
        self._process: subprocess.Popen[str] | None = None
        self._active_backup_id = ""

    def _headers(self) -> dict[str, str]:
        return {
            "X-PocketLab-Node-Id": self.node_id,
            "X-PocketLab-Agent-Token": self.agent_token,
            "Accept": "application/json",
            "Cache-Control": "no-store",
        }

    def _request_json(
        self,
        path: str,
        *,
        method: str = "GET",
        body: dict[str, Any] | None = None,
        timeout: int = 10,
    ) -> dict[str, Any]:
        if not self.control_origin.startswith("https://"):
            raise RuntimeError(
                "secure_control_origin_required"
            )
        data = None
        headers = self._headers()
        if body is not None:
            data = json.dumps(
                body,
                separators=(",", ":"),
            ).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            f"{self.control_origin}{path}",
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=timeout,
            ) as response:
                payload = json.loads(
                    response.read().decode("utf-8")
                )
                return (
                    payload
                    if isinstance(payload, dict)
                    else {}
                )
        except (
            urllib.error.URLError,
            urllib.error.HTTPError,
            TimeoutError,
            json.JSONDecodeError,
        ) as exc:
            raise RuntimeError(
                "control_plane_unavailable"
            ) from exc

    def _credential(
        self,
        credential_ref: str,
        backup_id: str,
    ) -> dict[str, Any]:
        ref = urllib.parse.quote(
            str(credential_ref or ""),
            safe="",
        )
        backup = urllib.parse.quote(
            str(backup_id or ""),
            safe="",
        )
        return self._request_json(
            "/api/lite/internal/photo-backup/"
            f"credentials/{ref}?backup_id={backup}"
        )

    def _capacity(
        self,
        backup_id: str,
    ) -> dict[str, Any]:
        backup = urllib.parse.quote(
            str(backup_id or ""),
            safe="",
        )
        return self._request_json(
            "/api/lite/internal/photo-backup/"
            f"{backup}/capacity"
        )

    def _post_progress(
        self,
        backup_id: str,
        payload: dict[str, Any],
    ) -> bool:
        safe = {
            "status": str(
                payload.get("status")
                or "transferring"
            )[:40],
            "summary": str(
                payload.get("summary")
                or "Photo backup is running."
            )[:180],
            "items_total": max(
                0,
                int(payload.get("items_total") or 0),
            ),
            "items_transferred": max(
                0,
                int(
                    payload.get(
                        "items_transferred"
                    )
                    or 0
                ),
            ),
            "items_skipped": max(
                0,
                int(
                    payload.get("items_skipped")
                    or 0
                ),
            ),
            "items_remaining": max(
                0,
                int(
                    payload.get(
                        "items_remaining"
                    )
                    or 0
                ),
            ),
            "conflicts": max(
                0,
                int(payload.get("conflicts") or 0),
            ),
            "bytes_total": max(
                0,
                int(
                    payload.get("bytes_total")
                    or 0
                ),
            ),
            "bytes_total_planned": max(
                0,
                int(
                    payload.get(
                        "bytes_total_planned"
                    )
                    or 0
                ),
            ),
            "bytes_total_required": max(
                0,
                int(
                    payload.get(
                        "bytes_total_required"
                    )
                    or payload.get("bytes_total")
                    or 0
                ),
            ),
            "bytes_transferred": max(
                0,
                int(
                    payload.get(
                        "bytes_transferred"
                    )
                    or 0
                ),
            ),
            "bytes_remaining": max(
                0,
                int(
                    payload.get(
                        "bytes_remaining"
                    )
                    or 0
                ),
            ),
            "photo_processing_state": str(
                payload.get(
                    "photo_processing_state"
                )
                or ""
            )[:64],
            "partial": bool(
                payload.get("partial")
            ),
            "retryable": bool(
                payload.get("retryable")
            ),
            "reason_code": str(
                payload.get("reason_code")
                or ""
            )[:64],
            "progress": (
                payload.get("progress")
                if isinstance(
                    payload.get("progress"),
                    dict,
                )
                else {}
            ),
        }
        delivered = False
        try:
            self._request_json(
                "/api/lite/internal/photo-backup/"
                f"{urllib.parse.quote(backup_id, safe='')}"
                "/progress",
                method="POST",
                body=safe,
                timeout=8,
            )
            delivered = True
        except RuntimeError:
            # The node keeps its aggregate recovery marker so a later
            # reconnect can reconcile a terminal result safely.
            delivered = False
        if self.progress_callback:
            try:
                self.progress_callback(safe)
            except Exception:
                pass
        return delivered

    def _run(
        self,
        args: list[str],
        *,
        timeout: int = 300,
        input_text: str | None = None,
        capture: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        if self.cancel_event.is_set():
            raise InterruptedError("cancelled")
        stdout = (
            subprocess.PIPE
            if capture
            else subprocess.DEVNULL
        )
        stderr = (
            subprocess.PIPE
            if capture
            else subprocess.DEVNULL
        )
        process = subprocess.Popen(
            args,
            stdin=(
                subprocess.PIPE
                if input_text is not None
                else subprocess.DEVNULL
            ),
            stdout=stdout,
            stderr=stderr,
            text=True,
            close_fds=True,
        )
        with self._process_lock:
            self._process = process
        try:
            out, err = process.communicate(
                input=input_text,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
            raise RuntimeError("rclone_timeout")
        finally:
            with self._process_lock:
                if self._process is process:
                    self._process = None

        if self.cancel_event.is_set():
            raise InterruptedError("cancelled")
        return subprocess.CompletedProcess(
            args=args,
            returncode=process.returncode,
            stdout=out or "",
            stderr=err or "",
        )

    def cancel(self, backup_id: str) -> None:
        if (
            self._active_backup_id
            and backup_id
            and backup_id != self._active_backup_id
        ):
            return
        self.cancel_event.set()
        with self._process_lock:
            process = self._process
        if (
            process is not None
            and process.poll() is None
        ):
            try:
                process.terminate()
            except OSError:
                pass

    def _inventory(
        self,
        collections: list[str],
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for collection in collections:
            if collection not in COLLECTION_ROOTS:
                continue
            root = _collection_path(collection)
            if (
                not root.is_dir()
                or not os.access(
                    root,
                    os.R_OK | os.X_OK,
                )
            ):
                continue
            for current, dirs, files in os.walk(
                root,
                topdown=True,
                followlinks=False,
            ):
                current_path = Path(current)
                try:
                    if (
                        current_path / ".nomedia"
                    ).exists():
                        dirs[:] = []
                        continue
                except OSError:
                    pass
                dirs[:] = [
                    name
                    for name in dirs
                    if (
                        name.lower()
                        not in EXCLUDED_DIR_NAMES
                        and not name.startswith(".")
                    )
                ]
                for filename in files:
                    if filename.startswith("."):
                        continue
                    path = current_path / filename
                    if (
                        path.suffix.lower()
                        not in MEDIA_EXTENSIONS
                    ):
                        continue
                    try:
                        stat = path.stat()
                    except OSError:
                        continue
                    if (
                        not path.is_file()
                        or stat.st_size <= 0
                    ):
                        continue
                    try:
                        relative = (
                            path.relative_to(root)
                            .as_posix()
                        )
                    except ValueError:
                        continue
                    items.append({
                        "collection": collection,
                        "path": path,
                        "relative": relative,
                        "size": int(stat.st_size),
                        "mtime": float(stat.st_mtime),
                    })
        items.sort(
            key=lambda item: (
                -float(item["mtime"]),
                str(item["collection"]),
                str(item["relative"]).casefold(),
            )
        )
        return items

    @staticmethod
    def _remote_key(
        collection: str,
        relative: str,
    ) -> str:
        label = COLLECTION_DESTINATIONS.get(
            collection,
            collection,
        )
        return (
            f"{label}/{relative}"
            .replace("\\", "/")
            .lstrip("/")
        )

    @staticmethod
    def _parse_time(value: Any) -> float:
        text = str(value or "").strip()
        if not text:
            return 0.0
        try:
            return datetime.fromisoformat(
                text.replace("Z", "+00:00")
            ).timestamp()
        except (ValueError, TypeError):
            return 0.0

    def _remote_listing(
        self,
        rclone: str,
        config_path: Path,
        destination_prefix: str,
    ) -> dict[str, dict[str, Any]]:
        result = self._run(
            [
                rclone,
                "lsjson",
                f"photoprism:{destination_prefix}",
                "--recursive",
                "--files-only",
                "--config",
                str(config_path),
                "--checkers",
                "1",
            ],
            timeout=180,
            capture=True,
        )
        if result.returncode != 0:
            error_text = str(
                result.stderr or ""
            ).casefold()
            if (
                "directory not found" in error_text
                or "path not found" in error_text
                or "does not exist" in error_text
            ):
                # A per-device namespace is intentionally created lazily by
                # the first copy. Only a confirmed missing directory is an
                # empty destination; auth/network failures still fail closed.
                return {}
            raise RuntimeError(
                "remote_listing_failed"
            )
        raw = result.stdout or ""
        if (
            len(
                raw.encode(
                    "utf-8",
                    errors="ignore",
                )
            )
            > MAX_REMOTE_LISTING_BYTES
        ):
            raise RuntimeError(
                "remote_listing_too_large"
            )
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "remote_listing_invalid"
            ) from exc

        listing: dict[str, dict[str, Any]] = {}
        for item in (
            data
            if isinstance(data, list)
            else []
        ):
            if (
                not isinstance(item, dict)
                or item.get("IsDir")
            ):
                continue
            key = (
                str(item.get("Path") or "")
                .replace("\\", "/")
                .lstrip("/")
            )
            if key:
                listing[key] = {
                    "size": int(
                        item.get("Size") or 0
                    ),
                    "mtime": self._parse_time(
                        item.get("ModTime")
                    ),
                }
        return listing

    @staticmethod
    def _matches(
        remote: dict[str, Any] | None,
        item: dict[str, Any],
    ) -> bool:
        if not isinstance(remote, dict):
            return False
        if (
            int(remote.get("size") or -1)
            != int(item["size"])
        ):
            return False
        remote_mtime = float(
            remote.get("mtime") or 0
        )
        return bool(
            remote_mtime
            and abs(
                remote_mtime
                - float(item["mtime"])
            )
            <= 3.0
        )

    @staticmethod
    def _conflict_relative(
        relative: str,
        item: dict[str, Any],
    ) -> str:
        path = Path(relative)
        digest = hashlib.sha256(
            (
                f"{int(item['size'])}:"
                f"{int(float(item['mtime']))}"
            ).encode("utf-8")
        ).hexdigest()[:12]
        return str(
            path.with_name(
                f"{path.stem}."
                f"pocketlab-v{digest}"
                f"{path.suffix}"
            )
        ).replace("\\", "/")

    def _make_config(
        self,
        rclone: str,
        credential: dict[str, Any],
        root: Path,
    ) -> Path:
        password = str(
            credential.get("password") or ""
        )
        url = str(
            credential.get("webdav_url") or ""
        )
        username = str(
            credential.get("username")
            or "admin"
        )
        if (
            not password
            or not url.startswith("https://")
        ):
            raise RuntimeError(
                "credential_invalid"
            )

        obscured = self._run(
            [rclone, "obscure", "-"],
            timeout=10,
            input_text=password + "\n",
            capture=True,
        )
        password = ""
        if (
            obscured.returncode != 0
            or not obscured.stdout.strip()
        ):
            raise RuntimeError(
                "credential_obscure_failed"
            )

        config = root / "rclone.conf"
        config.write_text(
            "[photoprism]\n"
            "type = webdav\n"
            f"url = {url}\n"
            "vendor = other\n"
            f"user = {username}\n"
            f"pass = {obscured.stdout.strip()}\n",
            encoding="utf-8",
        )
        config.chmod(0o600)
        return config

    def _transfer_one(
        self,
        rclone: str,
        config_path: Path,
        item: dict[str, Any],
        remote_relative: str,
        destination_prefix: str,
    ) -> None:
        final = (
            f"{destination_prefix}/"
            f"{remote_relative}"
        ).replace("//", "/")
        temporary = (
            final + ".pocketlab-upload"
        )
        copied = self._run(
            [
                rclone,
                "copyto",
                str(item["path"]),
                f"photoprism:{temporary}",
                "--config",
                str(config_path),
                "--transfers",
                "1",
                "--checkers",
                "1",
                "--retries",
                "2",
                "--low-level-retries",
                "3",
                "--contimeout",
                "10s",
                "--timeout",
                "5m",
                "--no-traverse",
            ],
            timeout=900,
        )
        if copied.returncode != 0:
            raise RuntimeError("copy_failed")

        moved = self._run(
            [
                rclone,
                "moveto",
                f"photoprism:{temporary}",
                f"photoprism:{final}",
                "--config",
                str(config_path),
                "--checkers",
                "1",
                "--retries",
                "2",
            ],
            timeout=120,
        )
        if moved.returncode != 0:
            raise RuntimeError(
                "finalize_failed"
            )

    def backup(
        self,
        *,
        backup_id: str,
        credential_ref: str,
        collections: list[str],
    ) -> dict[str, Any]:
        self.cancel_event.clear()
        self._active_backup_id = backup_id
        rclone = shutil.which("rclone")
        if not rclone:
            result = {
                "status": "failed",
                "summary": (
                    "Photo backup tools are not "
                    "ready on this device."
                ),
                "reason_code": "rclone_unavailable",
                "retryable": True,
            }
            self._post_progress(
                backup_id,
                result,
            )
            return result

        selected_collections = [
            item
            for item in collections
            if item in COLLECTION_ROOTS
        ]
        if not selected_collections:
            selected_collections = list(
                COLLECTION_ROOTS
            )

        credential: dict[str, Any] = {}
        temp_root: Path | None = None
        try:
            credential = self._credential(
                credential_ref,
                backup_id,
            )
            capacity = (
                credential.get("capacity")
                if isinstance(
                    credential.get(
                        "capacity"
                    ),
                    dict,
                )
                else {}
            )
            planning_budget = max(
                0,
                int(
                    capacity.get(
                        "safe_upload_budget_bytes"
                    )
                    or 0
                ),
            )
            readable_collections = [
                name
                for name in selected_collections
                if (
                    _collection_path(name).is_dir()
                    and os.access(
                        _collection_path(name),
                        os.R_OK | os.X_OK,
                    )
                )
            ]
            if not readable_collections:
                result = {
                    "status": "source_offline",
                    "summary": (
                        "No readable photo folders "
                        "are available on this "
                        "device."
                    ),
                    "retryable": True,
                    "reason_code": (
                        "photo_storage_access_missing"
                    ),
                }
                self._post_progress(
                    backup_id,
                    result,
                )
                return result

            items = self._inventory(
                readable_collections
            )
            if not items:
                result = {
                    "status": "completed",
                    "summary": (
                        "No photos or videos need "
                        "backing up."
                    ),
                    "items_total": 0,
                    "items_transferred": 0,
                    "items_skipped": 0,
                    "items_remaining": 0,
                    "bytes_total": 0,
                    "bytes_total_planned": 0,
                    "bytes_total_required": 0,
                    "bytes_transferred": 0,
                    "bytes_remaining": 0,
                    "partial": False,
                    "retryable": False,
                    "reason_code": "",
                    "photo_processing_state": "not_needed",
                    "progress": {
                        "phase": "completed",
                        "percent": 100,
                        "step": "Nothing new to back up.",
                    },
                }
                self._post_progress(
                    backup_id,
                    result,
                )
                return result

            temp_root = Path(
                tempfile.mkdtemp(
                    prefix=(
                        "pocketlab-photo-backup-"
                    )
                )
            )
            temp_root.chmod(0o700)
            config_path = self._make_config(
                rclone,
                credential,
                temp_root,
            )
            credential["password"] = ""
            destination_prefix = str(
                credential.get(
                    "destination_prefix"
                )
                or f"PocketLab/Devices/{self.node_id}"
            ).strip("/")
            remote = self._remote_listing(
                rclone,
                config_path,
                destination_prefix,
            )

            plan: list[
                tuple[dict[str, Any], str]
            ] = []
            skipped = 0
            remaining = 0
            conflicts = 0
            remaining_bytes = 0
            required_bytes = 0
            planned_bytes = 0
            oversized_count = 0
            for item in items:
                regular_key = self._remote_key(
                    str(item["collection"]),
                    str(item["relative"]),
                )
                if self._matches(
                    remote.get(regular_key),
                    item,
                ):
                    skipped += 1
                    continue

                final_key = regular_key
                if regular_key in remote:
                    conflicts += 1
                    conflict_rel = (
                        self._conflict_relative(
                            str(item["relative"]),
                            item,
                        )
                    )
                    final_key = self._remote_key(
                        str(item["collection"]),
                        conflict_rel,
                    )
                    if self._matches(
                        remote.get(final_key),
                        item,
                    ):
                        skipped += 1
                        continue

                required_bytes += int(item["size"])
                if (
                    planned_bytes
                    + int(item["size"])
                    > planning_budget
                ):
                    remaining += 1
                    remaining_bytes += int(item["size"])
                    if int(item["size"]) > planning_budget:
                        oversized_count += 1
                    continue
                plan.append((item, final_key))
                planned_bytes += int(
                    item["size"]
                )

            total_candidates = (
                len(plan)
                + skipped
                + remaining
            )
            self._post_progress(
                backup_id,
                {
                    "status": "transferring",
                    "summary": "Backing up photos.",
                    "items_total": total_candidates,
                    "items_skipped": skipped,
                    "items_remaining": len(plan) + remaining,
                    "conflicts": conflicts,
                    "oversized_items": oversized_count,
                    "bytes_total": required_bytes,
                    "bytes_total_planned": planned_bytes,
                    "bytes_total_required": required_bytes,
                    "bytes_remaining": required_bytes,
                    "progress": {
                        "phase": "transferring",
                        "percent": 0,
                        "step": "Backup started.",
                    },
                },
            )

            transferred = 0
            bytes_transferred = 0
            last_report = 0.0
            for index, (
                item,
                final_key,
            ) in enumerate(plan):
                if self.cancel_event.is_set():
                    raise InterruptedError(
                        "cancelled"
                    )

                capacity_now = self._capacity(
                    backup_id
                )
                hard_budget = max(
                    0,
                    int(
                        capacity_now.get(
                            "hard_upload_budget_bytes"
                        )
                        or 0
                    ),
                )
                safe_budget = max(
                    0, int(capacity_now.get("safe_upload_budget_bytes") or 0)
                )
                # Defer this item but keep trying smaller eligible objects.
                # Space changes during the run must not consume the hard reserve.
                if int(item["size"]) > min(hard_budget, safe_budget):
                    remaining += 1
                    remaining_bytes += int(item["size"])
                    continue
                # Never upload an item modified after inventory.
                try:
                    current_stat = item["path"].stat()
                except OSError:
                    remaining += 1
                    remaining_bytes += int(item["size"])
                    continue
                if (current_stat.st_size != item["size"]
                        or current_stat.st_mtime != item["mtime"]):
                    remaining += 1
                    remaining_bytes += int(item["size"])
                    continue

                self._transfer_one(
                    rclone,
                    config_path,
                    item,
                    final_key,
                    destination_prefix,
                )
                transferred += 1
                bytes_transferred += int(
                    item["size"]
                )
                remote[final_key] = {
                    "size": int(item["size"]),
                    "mtime": float(item["mtime"]),
                }

                now = time.monotonic()
                if (
                    now - last_report >= 5.0
                    or transferred == len(plan)
                ):
                    percent = (
                        int(
                            (
                                bytes_transferred
                                / required_bytes
                            )
                            * 100
                        )
                        if required_bytes
                        else 100
                    )
                    self._post_progress(
                        backup_id,
                        {
                            "status": "transferring",
                            "summary": (
                                "Backing up photos."
                            ),
                            "items_total": (
                                total_candidates
                            ),
                            "items_transferred": (
                                transferred
                            ),
                            "items_skipped": skipped,
                            "items_remaining": (
                                max(0, len(plan) - transferred)
                                + remaining
                            ),
                            "conflicts": conflicts,
                            "bytes_total": (
                                required_bytes
                            ),
                            "bytes_total_planned": (
                                planned_bytes
                            ),
                            "bytes_total_required": (
                                required_bytes
                            ),
                            "bytes_transferred": (
                                bytes_transferred
                            ),
                            "bytes_remaining": (
                                max(
                                    0,
                                    required_bytes
                                    - bytes_transferred,
                                )
                            ),
                            "progress": {
                                "phase": (
                                    "transferring"
                                ),
                                "percent": max(
                                    0,
                                    min(99, percent),
                                ),
                                "step": (
                                    "Backing up photos."
                                ),
                            },
                        },
                    )
                    last_report = now

            partial = remaining > 0
            final_status = (
                "partial_storage_limit"
                if partial
                else "completed"
            )
            final = {
                "status": final_status,
                "summary": (
                    "Photos backed up. Some items "
                    "are waiting for more space."
                    if partial
                    else "Photos are backed up."
                ),
                "items_total": total_candidates,
                "items_transferred": transferred,
                "items_skipped": skipped,
                "items_remaining": remaining,
                "conflicts": conflicts,
                "oversized_items": oversized_count,
                "bytes_total": required_bytes,
                "bytes_total_planned": planned_bytes,
                "bytes_total_required": required_bytes,
                "bytes_transferred": (
                    bytes_transferred
                ),
                "bytes_remaining": max(
                    0,
                    required_bytes - bytes_transferred,
                ),
                "photo_processing_state": (
                    "processing"
                    if transferred > 0
                    else "not_needed"
                ),
                "partial": partial,
                "retryable": partial,
                "reason_code": (
                    "storage_limit"
                    if partial
                    else ""
                ),
                "progress": {
                    "phase": final_status,
                    "percent": (
                        100
                        if not partial
                        else (
                            int(
                                (
                                    bytes_transferred
                                    / required_bytes
                                )
                                * 100
                            )
                            if required_bytes
                            else 0
                        )
                    ),
                    "step": (
                        "Backup complete."
                        if not partial
                        else (
                            "Backup paused at the "
                            "protected storage limit."
                        )
                    ),
                },
            }
            self._post_progress(
                backup_id,
                final,
            )
            return final
        except InterruptedError:
            final = {
                "status": "cancelled",
                "summary": (
                    "Photo backup stopped. Files "
                    "already backed up were kept."
                ),
                "retryable": True,
                "reason_code": "cancelled",
            }
            self._post_progress(
                backup_id,
                final,
            )
            return final
        except Exception:
            final = {
                "status": "interrupted",
                "summary": (
                    "Photo backup was interrupted. "
                    "You can retry safely."
                ),
                "retryable": True,
                "reason_code": "interrupted",
            }
            self._post_progress(
                backup_id,
                final,
            )
            return final
        finally:
            credential["password"] = ""
            self._active_backup_id = ""
            if temp_root is not None:
                shutil.rmtree(
                    temp_root,
                    ignore_errors=True,
                )
