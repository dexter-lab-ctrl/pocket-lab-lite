from __future__ import annotations

from contextlib import contextmanager
import hashlib
import fcntl
import json
import os
import signal
import shutil
import stat as stat_module
import subprocess
import tempfile
import threading
import time
import unicodedata
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
    # Android camera media belongs to the camera collection, not the whole
    # shared DCIM tree.  Keeping the boundary here prevents unrelated folders
    # under shared storage from entering the backup inventory.
    "camera": ("shared", "DCIM", "Camera"),
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
MAX_INVENTORY_ITEMS = 250_000
MAX_INVENTORY_SPOOL_BYTES = 256 * 1024 * 1024
MAX_LEDGER_ITEMS = MAX_INVENTORY_ITEMS


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


REPAIR_TIMEOUT_SECONDS = 300
REPAIR_STALE_SECONDS = REPAIR_TIMEOUT_SECONDS + 60
REPAIR_PHASES = frozenset({"installing", "verifying"})
REPAIR_REASONS = frozenset({
    "rclone_install_failed", "rclone_install_timeout",
    "rclone_verification_failed", "rclone_repair_in_progress",
    "rclone_repair_interrupted", "rclone_unsupported_platform",
    "rclone_repair_state_unavailable",
})


def _repair_paths() -> tuple[Path, Path]:
    directory = Path.home() / ".pocketlab-lite"
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory.chmod(0o700)
    return directory / "photo-backup-repair.lock", directory / "photo-backup-repair.json"


def _repair_record(path: Path, status: str, reason: str | None = None, *,
                   command_id: str = "", started_at: str = "") -> dict[str, Any]:
    """Atomic private progress checkpoint containing strictly enumerated fields."""
    if reason is not None and reason not in REPAIR_REASONS:
        reason = "rclone_install_failed"
    payload = {
        "schema_version": 2, "status": status, "reason_code": reason,
        "command_id": command_id if _repair_command_id(command_id) else "",
        "started_at": started_at or _now(), "checked_at": _now(),
        "sanitized": True,
    }
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent,
            prefix=".photo-backup-repair-", delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            os.chmod(temporary_path, 0o600)
            json.dump(payload, temporary, sort_keys=True)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, path)
        # Make phase transitions durable across abrupt Termux process restarts.
        directory_fd = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    return payload


def _repair_command_id(value: str) -> bool:
    import re
    return bool(re.fullmatch(r"repair-[a-f0-9]{18}", str(value or "")))


def photo_backup_repair_status() -> dict[str, Any]:
    """Read sanitized status; historical installer outcome is not live availability."""
    try:
        _, path = _repair_paths()
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("schema_version") not in {1, 2}:
            raise ValueError("invalid repair state")
        status = str(data.get("status") or "")
        if status not in {"installing", "verifying", "completed", "failed",
                          "already_installed", "interrupted", "unsupported_platform"}:
            raise ValueError("invalid repair status")
        reason = data.get("reason_code")
        if reason not in REPAIR_REASONS:
            reason = None
        return {
            "schema_version": 2, "status": status, "reason_code": reason,
            "started_at": str(data.get("started_at") or "")[:32],
            "checked_at": str(data.get("checked_at") or "")[:32],
            "sanitized": True,
        }
    except FileNotFoundError:
        return {"schema_version": 2, "status": "not_requested",
                "reason_code": None, "sanitized": True}
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {"schema_version": 2, "status": "unavailable",
                "reason_code": "rclone_repair_state_unavailable", "sanitized": True}


def _reconcile_repair(path: Path) -> None:
    """Caller holds the installer lock: old active checkpoint cannot still own it."""
    current = photo_backup_repair_status()
    if current["status"] in REPAIR_PHASES:
        _repair_record(path, "interrupted", "rclone_repair_interrupted",
                       started_at=current.get("started_at") or "")


def repair_rclone(*, command_id: str = "",
                  progress_callback: Callable[[dict[str, Any]], None] | None = None
                  ) -> dict[str, Any]:
    """Bounded Termux-only installer; serialized, durable and output-free.

    Only fixed package-manager argv is permitted. A completed installer must
    pass independent rclone version verification before it can report success.
    """
    def emit(state: dict[str, Any]) -> None:
        if progress_callback is not None:
            try:
                progress_callback({
                    "status": state["status"], "reason_code": state.get("reason_code"),
                    "checked_at": state.get("checked_at"), "sanitized": True,
                })
            except Exception:
                pass

    try:
        lock_path, record_path = _repair_paths()
        fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
        try:
            os.fchmod(fd, 0o600)
        except OSError:
            pass
    except OSError:
        return {"status": "failed", "reason_code": "rclone_repair_state_unavailable",
                "summary": "Photo backup repair state is not writable.",
                "rclone_available": False, "sanitized": True}
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {"status": "already_running",
                    "reason_code": "rclone_repair_in_progress",
                    "summary": "Photo backup tools are already being repaired.",
                    "rclone_available": False, "sanitized": True}
        try:
            _reconcile_repair(record_path)
            started_at = _now()
            def phase(status: str, reason: str | None = None) -> None:
                emit(_repair_record(record_path, status, reason,
                                    command_id=command_id, started_at=started_at))
            existing = collect_photo_backup_capabilities()
            if (existing.get("rclone_available") and
                str(existing.get("rclone_version") or "").startswith("rclone ")):
                phase("already_installed")
                return {**existing, "status": "already_installed", "reason_code": None,
                        "summary": "Photo backup tools are already installed.", "sanitized": True}
            # 'pkg' is the Termux package manager. Never execute apt, curl, sh or
            # attacker supplied command paths for this repair.
            pkg = shutil.which("pkg")
            if not pkg or not (os.environ.get("PREFIX", "").startswith("/data/data/com.termux/")):
                phase("unsupported_platform", "rclone_unsupported_platform")
                return {"status": "unsupported_platform",
                        "reason_code": "rclone_unsupported_platform",
                        "summary": "Automatic repair is only supported in Termux.",
                        "rclone_available": False, "sanitized": True}
            phase("installing")
            reason = None
            try:
                result = subprocess.run(
                    [pkg, "install", "-y", "rclone"],
                    check=False, stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    timeout=REPAIR_TIMEOUT_SECONDS,
                )
                if result.returncode != 0:
                    reason = "rclone_install_failed"
            except subprocess.TimeoutExpired:
                reason = "rclone_install_timeout"
            except (OSError, subprocess.SubprocessError):
                reason = "rclone_install_failed"
            if reason is None:
                phase("verifying")
            caps = collect_photo_backup_capabilities()
            if reason is None and (
                not caps.get("rclone_available") or
                not str(caps.get("rclone_version") or "").startswith("rclone ")
            ):
                reason = "rclone_verification_failed"
            status = "completed" if reason is None else "failed"
            phase(status, reason)
            return {
                **caps, "status": status, "reason_code": reason,
                "summary": ("Photo backup tools are ready." if reason is None
                            else "Photo backup tool repair did not complete. You can retry."),
                "sanitized": True,
            }
        except (OSError, ValueError):
            return {"status": "failed", "reason_code": "rclone_repair_state_unavailable",
                    "summary": "Photo backup repair state could not be saved.",
                    "rclone_available": False, "sanitized": True}
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


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
        self._integrity_mode = "size_only"

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
        def count(value: Any) -> int:
            try:
                return max(0, int(value or 0))
            except (TypeError, ValueError, OverflowError):
                return 0

        safe = {
            "status": str(
                payload.get("status")
                or "transferring"
            )[:40],
            "summary": str(
                payload.get("summary")
                or "Photo backup is running."
            )[:180],
            "items_total": count(payload.get("items_total")),
            "items_transferred": count(payload.get("items_transferred")),
            "items_skipped": count(payload.get("items_skipped")),
            "items_remaining": count(payload.get("items_remaining")),
            "conflicts": count(payload.get("conflicts")),
            "oversized_items": count(payload.get("oversized_items")),
            "bytes_total": count(payload.get("bytes_total")),
            "bytes_total_planned": count(payload.get("bytes_total_planned")),
            "bytes_total_required": count(
                payload.get("bytes_total_required") or payload.get("bytes_total")
            ),
            "bytes_transferred": count(payload.get("bytes_transferred")),
            "bytes_remaining": count(payload.get("bytes_remaining")),
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
            "integrity_mode": (
                "sha256"
                if str(payload.get("integrity_mode") or self._integrity_mode) == "sha256"
                else "size_only"
            ),
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
            start_new_session=(os.name == "posix"),
        )
        with self._process_lock:
            self._process = process
        try:
            out, err = process.communicate(
                input=input_text,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            self._terminate_process_tree(process)
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._kill_process_tree(process)
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

    @staticmethod
    def _terminate_process_tree(process: subprocess.Popen[str]) -> None:
        try:
            if os.name == "posix":
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            else:
                process.terminate()
        except (AttributeError, OSError, ProcessLookupError):
            try:
                process.terminate()
            except OSError:
                pass

    @staticmethod
    def _kill_process_tree(process: subprocess.Popen[str]) -> None:
        try:
            if os.name == "posix":
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            else:
                process.kill()
        except (AttributeError, OSError, ProcessLookupError):
            try:
                process.kill()
            except OSError:
                pass

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
            self._terminate_process_tree(process)

    @staticmethod
    def _normalise_relative(path: Path, root: Path) -> str | None:
        """Return a safe, stable relative media name.

        Android filenames may contain Unicode in more than one equivalent
        form.  Normalising the destination name makes collision handling
        deterministic while the original Path remains the read source.  A
        relative path is rejected rather than repaired if it could escape its
        collection root.
        """
        try:
            relative = path.relative_to(root).as_posix()
        except ValueError:
            return None
        parts = []
        for part in relative.split("/"):
            normalised = unicodedata.normalize("NFC", part)
            if not normalised or normalised in {".", ".."} or "\x00" in normalised:
                return None
            parts.append(normalised)
        return "/".join(parts) if parts else None

    def _inventory(self, collections: list[str]):
        # Keep the public call eager enough for configuration errors while
        # returning a lazy stream for normal inventories.
        if MAX_INVENTORY_ITEMS <= 0:
            raise RuntimeError("source_inventory_limit_reached")
        return self._inventory_stream(collections)

    def _inventory_stream(self, collections: list[str]):
        """Yield media records without retaining the whole library in RAM.

        ``os.walk`` materialises each directory's file list and the previous
        implementation then retained every record until sorting completed.
        An explicit scandir stack keeps memory proportional to the current
        directory depth.  The backup planner spools records to a private,
        bounded JSONL file when it needs to make a second pass.
        """
        count = 0
        for collection in collections:
            if collection not in COLLECTION_ROOTS:
                continue
            root = _collection_path(collection)
            try:
                root_stat = root.stat(follow_symlinks=False)
                if (
                    not root.is_dir()
                    or root.is_symlink()
                    or not os.access(root, os.R_OK | os.X_OK)
                    or not getattr(root_stat, "st_mode", 0)
                ):
                    continue
            except OSError:
                continue

            pending = [root]
            while pending:
                current_path = pending.pop()
                try:
                    if (current_path / ".nomedia").is_file():
                        continue
                except OSError:
                    continue

                child_directories: list[Path] = []
                try:
                    entries = os.scandir(current_path)
                except OSError:
                    continue
                try:
                    for entry in entries:
                        name = entry.name
                        if not name or name.startswith("."):
                            continue
                        try:
                            if entry.is_dir(follow_symlinks=False):
                                if name.casefold() not in EXCLUDED_DIR_NAMES:
                                    child_directories.append(Path(entry.path))
                                continue
                            if (
                                not entry.is_file(follow_symlinks=False)
                                or Path(name).suffix.casefold() not in MEDIA_EXTENSIONS
                            ):
                                continue
                            stat_result = entry.stat(follow_symlinks=False)
                        except OSError:
                            # A removable-media directory can change while it
                            # is being inventoried.  Skip that entry and keep
                            # the rest of the bounded scan useful.
                            continue
                        if stat_result.st_size <= 0:
                            continue
                        path = Path(entry.path)
                        relative = self._normalise_relative(path, root)
                        if relative is None:
                            continue
                        if count >= MAX_INVENTORY_ITEMS:
                            raise RuntimeError("source_inventory_limit_reached")
                        count += 1
                        yield {
                            "collection": collection,
                            "path": path,
                            "relative": relative,
                            "size": int(stat_result.st_size),
                            "mtime": float(stat_result.st_mtime),
                            "mtime_ns": int(getattr(stat_result, "st_mtime_ns", 0)),
                        }
                finally:
                    entries.close()
                # Sorting only the child-directory names keeps traversal
                # deterministic without retaining media records.
                for child in sorted(child_directories, key=lambda item: item.name.casefold(), reverse=True):
                    pending.append(child)

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
                "--hash",
                "--hash-type",
                "SHA-256",
                "--config",
                str(config_path),
                "--checkers",
                "1",
            ],
            timeout=180,
            capture=True,
        )
        hash_error = str(result.stderr or "").casefold()
        if result.returncode != 0 and (
            "hash" in hash_error
            and ("unsupported" in hash_error or "not supported" in hash_error)
        ):
            # Plain WebDAV commonly has no checksum provider.  Fall back to
            # the same bounded listing without pretending that a digest exists.
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

        if not isinstance(data, list):
            raise RuntimeError("remote_listing_invalid")

        listing: dict[str, dict[str, Any]] = {}
        folded_keys: set[str] = set()
        for item in data:
            if not isinstance(item, dict):
                raise RuntimeError("remote_listing_invalid")
            if item.get("IsDir"):
                continue
            raw_key = str(item.get("Path") or "").replace("\\", "/")
            if raw_key.startswith("/") or raw_key.startswith("\\"):
                raise RuntimeError("remote_listing_invalid")
            key = "/".join(
                unicodedata.normalize("NFC", part)
                for part in raw_key.split("/")
                if part
            )
            parts = key.split("/") if key else []
            if not parts or any(part in {".", ".."} or "\x00" in part for part in parts):
                raise RuntimeError("remote_listing_invalid")
            folded = key.casefold()
            if folded in folded_keys:
                # A case-insensitive destination cannot safely represent two
                # objects that differ only by case.  Do not silently overwrite
                # one during inventory reconciliation.
                raise RuntimeError("remote_listing_invalid")
            try:
                size = int(item.get("Size") or 0)
            except (TypeError, ValueError) as exc:
                raise RuntimeError("remote_listing_invalid") from exc
            if size < 0:
                raise RuntimeError("remote_listing_invalid")
            if len(listing) >= MAX_INVENTORY_ITEMS:
                raise RuntimeError("remote_inventory_limit_reached")
            hashes = item.get("Hashes")
            sha256 = ""
            if isinstance(hashes, dict):
                candidate = hashes.get("SHA-256") or hashes.get("sha-256") or ""
                if candidate:
                    if len(str(candidate)) != 64:
                        raise RuntimeError("remote_listing_invalid")
                    try:
                        int(str(candidate), 16)
                    except ValueError:
                        raise RuntimeError("remote_listing_invalid") from None
                    sha256 = str(candidate).lower()
            folded_keys.add(folded)
            listing[key] = {
                "size": size,
                "mtime": self._parse_time(item.get("ModTime")),
                "sha256": sha256,
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
                f"{int(float(item['mtime']))}:"
                f"{unicodedata.normalize('NFC', str(item.get('relative') or ''))}"
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

    def _ledger_path(self) -> Path:
        root = Path.home() / ".pocketlab-lite" / "photo-backup-ledgers"
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        root.chmod(0o700)
        # Node IDs may be supplied by an external registry: never use them
        # directly as a filesystem path.
        digest = hashlib.sha256(self.node_id.encode("utf-8")).hexdigest()[:24]
        return root / (digest + ".json")

    @contextmanager
    def _ledger_lock(self):
        """Serialize ledger read/merge/write operations per device."""
        path = self._ledger_path().with_suffix(".lock")
        fd = os.open(
            str(path),
            os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        try:
            os.fchmod(fd, 0o600)
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)

    @staticmethod
    def _sanitised_ledger_entries(entries: dict[str, Any]) -> dict[str, Any]:
        clean: dict[str, Any] = {}
        for identity, entry in list(entries.items())[-MAX_LEDGER_ITEMS:]:
            if not isinstance(identity, str) or len(identity) != 64:
                continue
            if not isinstance(entry, dict):
                continue
            sha256 = str(entry.get("sha256") or "").lower()
            try:
                int(sha256, 16)
                size = int(entry.get("size"))
                mtime = int(entry.get("mtime"))
            except (TypeError, ValueError):
                continue
            if len(sha256) != 64 or size < 0 or mtime < 0:
                continue
            clean[identity] = {
                "size": size,
                "mtime": mtime,
                "mtime_ns": max(0, int(entry.get("mtime_ns") or 0)),
                "sha256": sha256,
                "verified_at": str(entry.get("verified_at") or "")[:32],
            }
        return clean

    def _ledger_load(self, destination_identity: str | None = None) -> dict[str, Any]:
        path = self._ledger_path()
        try:
            with self._ledger_lock():
                data = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(data, dict) or not isinstance(data.get("items"), dict):
                    return {}
                if data.get("schema_version") == 2:
                    if destination_identity is not None and data.get("destination_identity") != destination_identity:
                        return {}
                    return self._sanitised_ledger_entries(data["items"])
                # Schema 1 is only useful to direct compatibility callers. A
                # backup execution always supplies a destination identity and
                # therefore cannot trust a legacy ledger.
                if destination_identity is None and data.get("schema_version") == 1:
                    return self._sanitised_ledger_entries(data["items"])
        except (OSError, ValueError, TypeError, AttributeError):
            pass
        return {}

    def _ledger_save(
        self,
        entries: dict[str, Any],
        destination_identity: str | None = None,
    ) -> None:
        path = self._ledger_path()
        temp = None
        try:
            with self._ledger_lock():
                current: dict[str, Any] = {}
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    if (
                        isinstance(data, dict)
                        and data.get("schema_version") == 2
                        and data.get("destination_identity") == destination_identity
                        and isinstance(data.get("items"), dict)
                    ):
                        current = data["items"]
                except (OSError, ValueError, TypeError):
                    current = {}
                current.update(entries)
                clean = self._sanitised_ledger_entries(current)
                with tempfile.NamedTemporaryFile(
                    mode="w", encoding="utf-8", prefix=".ledger-",
                    dir=path.parent, delete=False,
                ) as stream:
                    temp = Path(stream.name)
                    os.chmod(temp, 0o600)
                    json.dump({
                        "schema_version": 2,
                        "destination_identity": destination_identity or "",
                        "items": clean,
                        "updated_at": _now(),
                        "sanitized": True,
                    }, stream, sort_keys=True, separators=(",", ":"))
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temp, path)
                directory_fd = os.open(str(path.parent), os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
        finally:
            if temp is not None:
                temp.unlink(missing_ok=True)

    @staticmethod
    def _item_identity(item: dict[str, Any], destination: str) -> str:
        # No filenames or source paths are persisted in the ledger.
        value = (
            unicodedata.normalize("NFC", str(item["collection"]))
            + "\x00"
            + unicodedata.normalize("NFC", str(item["relative"]))
            + "\x00"
            + unicodedata.normalize("NFC", destination)
        )
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _source_digest(path: Path, *, expected_size: int) -> str:
        h = hashlib.sha256()
        total = 0
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(str(path), flags)
        except OSError as exc:
            raise RuntimeError("source_changed") from exc
        try:
            descriptor_stat = os.fstat(descriptor)
            if (
                not stat_module.S_ISREG(descriptor_stat.st_mode)
                or int(descriptor_stat.st_size) != int(expected_size)
            ):
                raise RuntimeError("source_changed")
            with os.fdopen(descriptor, "rb", closefd=True) as stream:
                descriptor = -1
                while True:
                    block = stream.read(1024 * 1024)
                    if not block:
                        break
                    total += len(block)
                    if total > expected_size:
                        raise RuntimeError("source_changed")
                    h.update(block)
        finally:
            if descriptor >= 0:
                os.close(descriptor)
        if total != expected_size:
            raise RuntimeError("source_changed")
        return h.hexdigest()

    def _remote_metadata(
        self,
        rclone: str,
        config_path: Path,
        destination_prefix: str,
        remote_relative: str,
    ) -> dict[str, Any] | None:
        target = f"photoprism:{destination_prefix}/{remote_relative}"
        result = self._run([
            rclone, "lsjson", target, "--stat", "--hash", "--hash-type",
            "SHA-256", "--config", str(config_path), "--checkers", "1",
        ],
                           timeout=60, capture=True)
        hash_error = str(result.stderr or "").casefold()
        if result.returncode != 0 and (
            "hash" in hash_error
            and ("unsupported" in hash_error or "not supported" in hash_error)
        ):
            result = self._run([
                rclone, "lsjson", target, "--stat", "--config",
                str(config_path), "--checkers", "1",
            ], timeout=60, capture=True)
        raw = result.stdout or ""
        if result.returncode != 0 or len(raw.encode("utf-8")) > 4096:
            return None
        try:
            item = json.loads(raw)
            if isinstance(item, dict) and not item.get("IsDir"):
                size = int(item.get("Size", -1))
                if size < 0:
                    return None
                hashes = item.get("Hashes")
                sha256 = ""
                if isinstance(hashes, dict):
                    candidate = hashes.get("SHA-256") or hashes.get("sha-256") or ""
                    if candidate:
                        if len(str(candidate)) != 64:
                            return None
                        try:
                            int(str(candidate), 16)
                        except ValueError:
                            return None
                        sha256 = str(candidate).lower()
                return {
                    "size": size,
                    "mtime": self._parse_time(item.get("ModTime")),
                    "sha256": sha256,
                }
        except (ValueError, TypeError):
            pass
        return None

    def _remote_size(self, rclone: str, config_path: Path,
                     destination_prefix: str, remote_relative: str) -> int | None:
        metadata = self._remote_metadata(
            rclone, config_path, destination_prefix, remote_relative,
        )
        return int(metadata["size"]) if metadata else None

    def _cleanup_staging(self, rclone: str, config_path: Path,
                         destination_prefix: str, remote_relative: str) -> None:
        # Individual staging object only, not a recursive purge.
        path = f"photoprism:{destination_prefix}/{remote_relative}.pocketlab-upload"
        self._run([rclone, "deletefile", path, "--config", str(config_path),
                   "--retries", "1"], timeout=45)

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
        # Clean up only this exact deterministic staging object on retry.
        # Never delete the final destination or any other namespace.
        self._cleanup_staging(rclone, config_path, destination_prefix, remote_relative)
        try:
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

            # Size is always available. A SHA-256 comparison is used only
            # when the remote backend actually reports one; plain WebDAV does
            # not provide a trusted digest, so the result remains size-only.
            staged = self._remote_metadata(
                rclone, config_path, destination_prefix,
                remote_relative + ".pocketlab-upload",
            )
            expected_hash = str(getattr(self, "_expected_remote_sha256", "") or "")
            if not staged or int(staged.get("size", -1)) != int(item["size"]):
                raise RuntimeError("staging_integrity_failed")
            if expected_hash and staged.get("sha256") and staged["sha256"] != expected_hash:
                raise RuntimeError("remote_integrity_mismatch")
            self._integrity_mode = "sha256" if expected_hash and staged.get("sha256") else "size_only"
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
                raise RuntimeError("finalize_failed")
            finalized = self._remote_metadata(
                rclone, config_path, destination_prefix, remote_relative,
            )
            if not finalized or int(finalized.get("size", -1)) != int(item["size"]):
                raise RuntimeError("destination_integrity_failed")
            if expected_hash and finalized.get("sha256") and finalized["sha256"] != expected_hash:
                raise RuntimeError("remote_integrity_mismatch")
        finally:
            # This is an exact object cleanup, never a directory purge. It is
            # safe after a successful move and recovers staging after a crash
            # or failed finalization on the next retry.
            try:
                self._cleanup_staging(
                    rclone, config_path, destination_prefix, remote_relative,
                )
            except Exception:
                pass

    @staticmethod
    def _spool_record(item: dict[str, Any]) -> dict[str, Any]:
        return {
            "collection": str(item.get("collection") or ""),
            "path": str(item.get("path") or ""),
            "relative": str(item.get("relative") or ""),
            "size": int(item.get("size") or 0),
            "mtime": float(item.get("mtime") or 0),
            "mtime_ns": int(item.get("mtime_ns") or 0),
        }

    @staticmethod
    def _spool_item(record: dict[str, Any]) -> dict[str, Any]:
        return {
            "collection": str(record.get("collection") or ""),
            "path": Path(str(record.get("path") or "")),
            "relative": str(record.get("relative") or ""),
            "size": int(record.get("size") or 0),
            "mtime": float(record.get("mtime") or 0),
            "mtime_ns": int(record.get("mtime_ns") or 0),
        }

    def _write_inventory_spool(
        self,
        collections: list[str],
        destination: Path,
    ) -> int:
        count = 0
        with destination.open("w", encoding="utf-8", buffering=1024 * 1024) as stream:
            os.chmod(destination, 0o600)
            for item in self._inventory(collections):
                encoded = json.dumps(
                    self._spool_record(item),
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                stream.write(encoded + "\n")
                count += 1
                if stream.tell() > MAX_INVENTORY_SPOOL_BYTES:
                    raise RuntimeError("source_inventory_limit_reached")
        return count

    def _iter_spool(self, path: Path):
        with path.open("r", encoding="utf-8") as stream:
            for line in stream:
                try:
                    record = json.loads(line)
                except (TypeError, ValueError) as exc:
                    raise RuntimeError("source_inventory_limit_reached") from exc
                if not isinstance(record, dict):
                    raise RuntimeError("source_inventory_limit_reached")
                yield self._spool_item(record)

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
        transferred = 0
        bytes_transferred = 0
        skipped = 0
        remaining = 0
        conflicts = 0
        remaining_bytes = 0
        required_bytes = 0
        planned_bytes = 0
        oversized_count = 0
        planned_count = 0
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
            if str(capacity.get("status") or "").lower() in {"unavailable", "error"}:
                raise RuntimeError(
                    str(capacity.get("reason_code") or "destination_storage_unavailable")
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

            temp_root = Path(tempfile.mkdtemp(prefix="pocketlab-photo-backup-"))
            temp_root.chmod(0o700)
            inventory_path = temp_root / "inventory.jsonl"
            inventory_count = self._write_inventory_spool(
                readable_collections,
                inventory_path,
            )
            if inventory_count == 0:
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
            destination_parts = destination_prefix.split("/")
            if (
                not destination_prefix
                or any(
                    not part
                    or part in {".", ".."}
                    or "\x00" in part
                    for part in destination_parts
                )
            ):
                raise RuntimeError("destination_identity_mismatch")
            destination_id = str(credential.get("destination_id") or "").strip()
            ledger_identity = (
                hashlib.sha256(
                    (destination_id + "\x00" + destination_prefix).encode("utf-8")
                ).hexdigest()
                if destination_id
                else None
            )
            remote = self._remote_listing(
                rclone,
                config_path,
                destination_prefix,
            )

            ledger = self._ledger_load(ledger_identity) if ledger_identity else {}
            plan_path = temp_root / "plan.jsonl"
            seen_destination_keys: set[str] = set()
            with plan_path.open("w", encoding="utf-8", buffering=1024 * 1024) as plan_stream:
                os.chmod(plan_path, 0o600)
                for item in self._iter_spool(inventory_path):
                    regular_key = self._remote_key(
                        str(item["collection"]),
                        str(item["relative"]),
                    )
                    identity = self._item_identity(item, regular_key)
                    checkpoint = ledger.get(identity)
                    remote_item = remote.get(regular_key)
                    local_collision = regular_key.casefold() in seen_destination_keys
                    seen_destination_keys.add(regular_key.casefold())
                    source_digest = ""
                    if isinstance(checkpoint, dict) and remote_item:
                        try:
                            source_digest = self._source_digest(
                                item["path"], expected_size=int(item["size"]),
                            )
                        except RuntimeError as exc:
                            if str(exc) == "source_changed":
                                required_bytes += int(item["size"])
                                remaining += 1
                                remaining_bytes += int(item["size"])
                                continue
                            raise
                    if (
                        isinstance(checkpoint, dict)
                        and checkpoint.get("size") == int(item["size"])
                        and checkpoint.get("mtime") == int(item["mtime"])
                        and checkpoint.get("mtime_ns", 0) in {0, int(item.get("mtime_ns") or 0)}
                        and remote_item
                        and int(remote_item.get("size", -1)) == int(item["size"])
                        and checkpoint.get("sha256") == source_digest
                        and (
                            not remote_item.get("sha256")
                            or remote_item.get("sha256") == source_digest
                        )
                    ):
                        skipped += 1
                        continue
                    if self._matches(remote_item, item):
                        if remote_item.get("sha256"):
                            if not source_digest:
                                source_digest = self._source_digest(
                                    item["path"], expected_size=int(item["size"]),
                                )
                            if remote_item.get("sha256") != source_digest:
                                pass
                            else:
                                skipped += 1
                                continue
                        else:
                            skipped += 1
                            continue

                    final_key = regular_key
                    if regular_key in remote or local_collision:
                        conflicts += 1
                        conflict_rel = self._conflict_relative(
                            str(item["relative"]), item,
                        )
                        final_key = self._remote_key(
                            str(item["collection"]), conflict_rel,
                        )
                        if self._matches(remote.get(final_key), item):
                            skipped += 1
                            continue

                    required_bytes += int(item["size"])
                    if planned_bytes + int(item["size"]) > planning_budget:
                        remaining += 1
                        remaining_bytes += int(item["size"])
                        if int(item["size"]) > planning_budget:
                            oversized_count += 1
                        continue
                    plan_stream.write(json.dumps({
                        "item": self._spool_record(item),
                        "final_key": final_key,
                    }, ensure_ascii=False, separators=(",", ":")) + "\n")
                    planned_count += 1
                    planned_bytes += int(item["size"])
                if plan_stream.tell() > MAX_INVENTORY_SPOOL_BYTES:
                    raise RuntimeError("source_inventory_limit_reached")

            total_candidates = planned_count + skipped + remaining
            self._post_progress(
                backup_id,
                {
                    "status": "transferring",
                    "summary": "Backing up photos.",
                    "items_total": total_candidates,
                    "items_skipped": skipped,
                    "items_remaining": planned_count + remaining,
                    "conflicts": conflicts,
                    "oversized_items": oversized_count,
                    "integrity_mode": self._integrity_mode,
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
            with plan_path.open("r", encoding="utf-8") as plan_stream:
                for line in plan_stream:
                    try:
                        planned = json.loads(line)
                        item = self._spool_item(planned["item"])
                        final_key = str(planned["final_key"])
                    except (KeyError, TypeError, ValueError) as exc:
                        raise RuntimeError("source_inventory_limit_reached") from exc
                    if self.cancel_event.is_set():
                        raise InterruptedError("cancelled")

                    capacity_now = self._capacity(backup_id)
                    if (
                        str(capacity_now.get("status") or "").lower() in {"unavailable", "error"}
                        or "safe_upload_budget_bytes" not in capacity_now
                        or "hard_upload_budget_bytes" not in capacity_now
                    ):
                        raise RuntimeError(
                            str(capacity_now.get("reason_code") or "destination_storage_unavailable")
                        )
                    hard_budget = max(0, int(capacity_now.get("hard_upload_budget_bytes") or 0))
                    safe_budget = max(0, int(capacity_now.get("safe_upload_budget_bytes") or 0))
                    # Defer this item but keep trying smaller eligible objects.
                    if int(item["size"]) > min(hard_budget, safe_budget):
                        remaining += 1
                        remaining_bytes += int(item["size"])
                        continue

                    try:
                        current_stat = item["path"].stat()
                    except OSError:
                        remaining += 1
                        remaining_bytes += int(item["size"])
                        continue
                    if item["path"].is_symlink() or not stat_module.S_ISREG(current_stat.st_mode):
                        remaining += 1
                        remaining_bytes += int(item["size"])
                        continue
                    if (
                        current_stat.st_size != item["size"]
                        or current_stat.st_mtime != item["mtime"]
                        or (
                            item.get("mtime_ns")
                            and getattr(current_stat, "st_mtime_ns", 0) != item["mtime_ns"]
                        )
                    ):
                        remaining += 1
                        remaining_bytes += int(item["size"])
                        continue

                    source_hash = self._source_digest(
                        item["path"], expected_size=int(item["size"]),
                    )
                    self._expected_remote_sha256 = source_hash
                    self._transfer_one(
                        rclone, config_path, item, final_key, destination_prefix,
                    )
                    if self._source_digest(
                        item["path"], expected_size=int(item["size"]),
                    ) != source_hash:
                        raise RuntimeError("source_changed")
                    ledger[self._item_identity(item, final_key)] = {
                        "size": int(item["size"]),
                        "mtime": int(item["mtime"]),
                        "mtime_ns": int(item.get("mtime_ns") or 0),
                        "sha256": source_hash,
                        "verified_at": _now(),
                    }
                    if ledger_identity:
                        self._ledger_save(ledger, ledger_identity)
                    transferred += 1
                    bytes_transferred += int(item["size"])
                    remote[final_key] = {
                        "size": int(item["size"]),
                        "mtime": float(item["mtime"]),
                        # Plain WebDAV generally has no trusted checksum.
                        "sha256": "",
                    }

                    now = time.monotonic()
                    if now - last_report >= 5.0 or transferred == planned_count:
                        percent = int((bytes_transferred / required_bytes) * 100) if required_bytes else 100
                        self._post_progress(
                            backup_id,
                            {
                                "status": "transferring",
                                "summary": "Backing up photos.",
                                "items_total": total_candidates,
                                "items_transferred": transferred,
                                "items_skipped": skipped,
                                "items_remaining": max(0, planned_count - transferred) + remaining,
                                "conflicts": conflicts,
                                "oversized_items": oversized_count,
                                "integrity_mode": self._integrity_mode,
                                "bytes_total": required_bytes,
                                "bytes_total_planned": planned_bytes,
                                "bytes_total_required": required_bytes,
                                "bytes_transferred": bytes_transferred,
                                "bytes_remaining": max(0, required_bytes - bytes_transferred),
                                "progress": {
                                    "phase": "transferring",
                                    "percent": max(0, min(99, percent)),
                                    "step": "Backing up photos.",
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
                "integrity_mode": self._integrity_mode,
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
        except Exception as exc:
            reason = str(exc).strip() or "interrupted"
            if reason == "source_changed_during_transfer":
                reason = "source_changed"
            if reason in {"destination_storage_unavailable", "destination_identity_mismatch"}:
                final_status = "destination_unavailable"
            elif reason == "source_offline":
                final_status = "source_offline"
            else:
                final_status = "interrupted"
            percent = int((bytes_transferred / required_bytes) * 100) if required_bytes else 0
            final = {
                "status": final_status,
                "summary": (
                    "Photo backup could not finish safely. "
                    "Completed files were kept; you can retry."
                ),
                "items_total": planned_count + skipped + remaining,
                "items_transferred": transferred,
                "items_skipped": skipped,
                "items_remaining": max(0, planned_count - transferred) + remaining,
                "conflicts": conflicts,
                "oversized_items": oversized_count,
                "integrity_mode": self._integrity_mode,
                "bytes_total": required_bytes,
                "bytes_total_planned": planned_bytes,
                "bytes_total_required": required_bytes,
                "bytes_transferred": bytes_transferred,
                "bytes_remaining": max(0, required_bytes - bytes_transferred),
                "partial": bool(transferred or remaining),
                "retryable": True,
                "reason_code": reason if reason != "control_plane_unavailable" else "destination_unavailable",
                "progress": {
                    "phase": final_status,
                    "percent": max(0, min(99, percent)),
                    "step": "Backup stopped before completion.",
                },
            }
            self._post_progress(
                backup_id,
                final,
            )
            return final
        finally:
            credential["password"] = ""
            self._expected_remote_sha256 = ""
            self._integrity_mode = "size_only"
            self._active_backup_id = ""
            if temp_root is not None:
                shutil.rmtree(
                    temp_root,
                    ignore_errors=True,
                )
