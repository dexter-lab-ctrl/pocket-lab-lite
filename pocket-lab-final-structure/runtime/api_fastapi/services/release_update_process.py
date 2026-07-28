from __future__ import annotations

"""Bounded release metadata/artifact subprocess.

The process accepts one compact JSON request on stdin and emits one sanitized
JSON envelope on stdout.  It owns network fetch, JSON parsing, checksum work,
and archive inspection.  It has no NATS credentials and never applies a release.
"""

import hashlib
import json
import os
from pathlib import Path
try:
    import resource  # type: ignore
except Exception:  # pragma: no cover - unavailable on Windows
    resource = None  # type: ignore
import sys
import tempfile
import time
from typing import Any, Mapping
import urllib.error
import urllib.parse
import urllib.request
import zipfile

_MAX_REQUEST_BYTES = 64 * 1024
_MAX_OUTPUT_BYTES = 128 * 1024


class ReleaseProcessFailure(RuntimeError):
    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = str(code or "release_process_failed")[:80]


def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(str(os.environ.get(name, default)).strip())
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def _bounded_float(value: Any, default: float, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def _safe_text(value: Any, limit: int = 240) -> str:
    return str(value or "").replace("\x00", " ").strip()[:limit]


def _rss_bytes() -> int:
    if resource is None:
        return 0
    try:
        usage = resource.getrusage(resource.RUSAGE_SELF)
        # Linux/Android reports KiB; macOS reports bytes.
        value = int(usage.ru_maxrss)
        return value if sys.platform == "darwin" else value * 1024
    except Exception:
        return 0


def _apply_resource_limits() -> None:
    if resource is None:
        return
    limits: list[tuple[int, int]] = []
    if hasattr(resource, "RLIMIT_CPU"):
        limits.append(
            (
                resource.RLIMIT_CPU,
                _bounded_int("POCKETLAB_RELEASE_CHILD_CPU_SECONDS", 15, 2, 120),
            )
        )
    address_space_limit = _bounded_int(
        "POCKETLAB_RELEASE_CHILD_MAX_ADDRESS_SPACE_BYTES",
        0,
        0,
        8 * 1024 * 1024 * 1024,
    )
    if address_space_limit and hasattr(resource, "RLIMIT_AS"):
        limits.append((resource.RLIMIT_AS, address_space_limit))
    if hasattr(resource, "RLIMIT_FSIZE"):
        limits.append(
            (
                resource.RLIMIT_FSIZE,
                _bounded_int(
                    "POCKETLAB_RELEASE_CHILD_MAX_FILE_BYTES",
                    256 * 1024 * 1024,
                    1024 * 1024,
                    2 * 1024 * 1024 * 1024,
                ),
            )
        )
    if hasattr(resource, "RLIMIT_NOFILE"):
        limits.append(
            (
                resource.RLIMIT_NOFILE,
                _bounded_int("POCKETLAB_RELEASE_CHILD_MAX_FILES", 64, 16, 512),
            )
        )
    for kind, requested in limits:
        try:
            current_soft, current_hard = resource.getrlimit(kind)
            hard = requested if current_hard in {-1, resource.RLIM_INFINITY} else min(requested, current_hard)
            resource.setrlimit(kind, (min(requested, hard), hard))
        except (ValueError, OSError):
            continue


def _configured_allowed_hosts() -> set[str]:
    configured = {
        item.strip().lower()
        for item in os.environ.get(
            "POCKETLAB_RELEASE_ALLOWED_HOSTS",
            "api.github.com,github.com,objects.githubusercontent.com",
        ).split(",")
        if item.strip()
    }
    # A self-hosted GitHub-compatible metadata endpoint may be configured by
    # the operator.  Admit exactly that configured host rather than silently
    # trusting whichever host appears in an arbitrary child request.
    source = str(os.environ.get("POCKETLAB_GITHUB_RELEASES_API", "") or "").strip()
    if source:
        source_host = (urllib.parse.urlparse(source).hostname or "").lower()
        if source_host:
            configured.add(source_host)
    return configured


def _allowed_host(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower()
    allow_insecure = os.environ.get("POCKETLAB_RELEASE_ALLOW_INSECURE_SOURCE", "").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if scheme not in ({"https", "http"} if allow_insecure else {"https"}):
        raise ReleaseProcessFailure("release_source_scheme_rejected")
    if not host:
        raise ReleaseProcessFailure("release_source_host_missing")
    if parsed.username or parsed.password:
        raise ReleaseProcessFailure("release_source_userinfo_rejected")
    if host not in _configured_allowed_hosts():
        raise ReleaseProcessFailure("release_source_host_rejected")
    return host


def _urlopen_bounded(url: str, *, timeout: float, max_bytes: int) -> tuple[bytes, int]:
    original_host = _allowed_host(url)
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json, application/json, application/octet-stream",
            "User-Agent": "Pocket-Lab-Release-Subprocess",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            final_url = str(response.geturl() or url)
            final_host = _allowed_host(final_url)
            if final_host != original_host and final_host not in _configured_allowed_hosts():
                raise ReleaseProcessFailure("release_redirect_host_rejected")
            declared = response.headers.get("Content-Length")
            if declared:
                try:
                    if int(declared) > max_bytes:
                        raise ReleaseProcessFailure("release_response_too_large")
                except ValueError:
                    pass
            body = response.read(max_bytes + 1)
    except urllib.error.HTTPError as exc:
        raise ReleaseProcessFailure(f"release_http_{int(exc.code)}") from exc
    except urllib.error.URLError as exc:
        raise ReleaseProcessFailure("release_source_unreachable") from exc
    if len(body) > max_bytes:
        raise ReleaseProcessFailure("release_response_too_large")
    return body, len(body)


def _artifact_summary(release: Mapping[str, Any], requested_name: str) -> dict[str, Any]:
    assets = release.get("assets") if isinstance(release.get("assets"), list) else []
    selected: Mapping[str, Any] = {}
    for item in assets[:64]:
        if isinstance(item, Mapping) and _safe_text(item.get("name"), 240) == requested_name:
            selected = item
            break
    digest = _safe_text(selected.get("digest"), 160)
    verification_status = "digest_available" if digest.lower().startswith("sha256:") else "metadata_only"
    return {
        "name": _safe_text(selected.get("name"), 240),
        "size": max(0, int(selected.get("size") or 0)),
        "digest": digest,
        "verification_status": verification_status,
        # Browser URL is intentionally returned only to the worker and is never
        # persisted in the prepared public projection.
        "download_url": _safe_text(selected.get("browser_download_url"), 2048),
    }


def _check(payload: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    url = _safe_text(payload.get("source_url"), 4096)
    timeout = _bounded_float(payload.get("network_timeout_seconds"), 10.0, 1.0, 60.0)
    max_bytes = max(
        16 * 1024,
        min(int(payload.get("max_metadata_bytes") or 2 * 1024 * 1024), 8 * 1024 * 1024),
    )
    body, bytes_read = _urlopen_bounded(url, timeout=timeout, max_bytes=max_bytes)
    try:
        release = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReleaseProcessFailure("release_metadata_invalid_json") from exc
    if not isinstance(release, dict):
        raise ReleaseProcessFailure("release_metadata_invalid_shape")
    tag_name = _safe_text(release.get("tag_name") or release.get("name") or "unknown", 120)
    current_tag = _safe_text(payload.get("current_tag") or "unknown", 120)
    artifact = _artifact_summary(
        release, _safe_text(payload.get("artifact_name") or "dist.zip", 240)
    )
    result = {
        "current_tag": current_tag,
        "latest_tag": tag_name or "unknown",
        "update_available": bool(tag_name and tag_name != current_tag),
        "auto_apply": bool(payload.get("auto_apply")),
        "latest_release": {
            "tag_name": tag_name or "unknown",
            "name": _safe_text(release.get("name") or tag_name, 240),
            "html_url": _safe_text(release.get("html_url"), 1024),
            "published_at": _safe_text(release.get("published_at"), 80) or None,
            "draft": bool(release.get("draft")),
            "prerelease": bool(release.get("prerelease")),
            "body_excerpt": _safe_text(release.get("body"), 1024),
            "artifact": artifact,
        },
        "sanitized": True,
    }
    return result, {"bytes_read": bytes_read, "files_examined": 0}


def _safe_staging_path(value: Any) -> Path:
    root = Path(
        os.environ.get("POCKETLAB_RELEASE_STAGING_DIR", "")
        or (Path(os.environ.get("POCKETLAB_STATE_DIR", ".")) / "release-staging")
    ).expanduser().resolve(strict=False)
    root.mkdir(parents=True, exist_ok=True)
    path = Path(_safe_text(value, 4096)).expanduser().resolve(strict=False)
    if root != path and root not in path.parents:
        raise ReleaseProcessFailure("release_staging_path_rejected")
    return path


def _download(payload: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    url = _safe_text(payload.get("download_url"), 4096)
    target = _safe_staging_path(payload.get("target_path"))
    max_bytes = max(
        1024 * 1024,
        min(
            int(payload.get("max_download_bytes") or 256 * 1024 * 1024),
            2 * 1024 * 1024 * 1024,
        ),
    )
    timeout = _bounded_float(payload.get("network_timeout_seconds"), 30.0, 2.0, 300.0)
    body, bytes_read = _urlopen_bounded(url, timeout=timeout, max_bytes=max_bytes)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="wb", dir=target.parent, prefix=f".{target.name}.", delete=False
    ) as handle:
        temporary = Path(handle.name)
        handle.write(body)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, target)
    digest = hashlib.sha256(body).hexdigest()
    return {
        "path": str(target),
        "bytes": len(body),
        "sha256": digest,
        "sanitized": True,
    }, {"bytes_read": bytes_read, "files_examined": 1}


def _validate_zip(path: Path) -> dict[str, Any]:
    max_entries = _bounded_int("POCKETLAB_RELEASE_ARCHIVE_MAX_ENTRIES", 4096, 1, 100_000)
    max_expanded = _bounded_int(
        "POCKETLAB_RELEASE_ARCHIVE_MAX_EXPANDED_BYTES",
        512 * 1024 * 1024,
        1024 * 1024,
        4 * 1024 * 1024 * 1024,
    )
    max_ratio = _bounded_float(
        os.environ.get("POCKETLAB_RELEASE_ARCHIVE_MAX_RATIO", "200"), 200.0, 2.0, 10_000.0
    )
    total_compressed = total_expanded = 0
    with zipfile.ZipFile(path, "r") as archive:
        infos = archive.infolist()
        if len(infos) > max_entries:
            raise ReleaseProcessFailure("release_archive_entry_limit")
        for info in infos:
            name = info.filename.replace("\\", "/")
            candidate = Path(name)
            if name.startswith("/") or ".." in candidate.parts:
                raise ReleaseProcessFailure("release_archive_path_traversal")
            mode = (info.external_attr >> 16) & 0o170000
            if mode == 0o120000:
                raise ReleaseProcessFailure("release_archive_symlink_rejected")
            total_compressed += max(0, int(info.compress_size))
            total_expanded += max(0, int(info.file_size))
            if total_expanded > max_expanded:
                raise ReleaseProcessFailure("release_archive_expanded_limit")
        ratio = total_expanded / max(1, total_compressed)
        if ratio > max_ratio:
            raise ReleaseProcessFailure("release_archive_ratio_limit")
    return {
        "entry_count": len(infos),
        "compressed_bytes": total_compressed,
        "expanded_bytes": total_expanded,
    }


def _verify(payload: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    path = _safe_staging_path(payload.get("path"))
    if not path.is_file():
        raise ReleaseProcessFailure("release_artifact_missing")
    max_bytes = _bounded_int(
        "POCKETLAB_RELEASE_VERIFY_MAX_BYTES",
        512 * 1024 * 1024,
        1024 * 1024,
        2 * 1024 * 1024 * 1024,
    )
    size = path.stat().st_size
    if size > max_bytes:
        raise ReleaseProcessFailure("release_artifact_size_limit")
    digest = hashlib.sha256()
    bytes_read = 0
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            bytes_read += len(chunk)
            if bytes_read > max_bytes:
                raise ReleaseProcessFailure("release_artifact_size_limit")
            digest.update(chunk)
    observed = digest.hexdigest()
    expected = _safe_text(payload.get("expected_sha256"), 160).lower().removeprefix("sha256:")
    if expected and observed != expected:
        raise ReleaseProcessFailure("release_checksum_mismatch")
    archive = _validate_zip(path) if path.suffix.lower() == ".zip" else {}
    return {
        "path": str(path),
        "sha256": observed,
        "checksum_status": "verified" if expected else "computed",
        "archive": archive,
        "sanitized": True,
    }, {"bytes_read": bytes_read, "files_examined": int(archive.get("entry_count") or 1)}


def _emit(payload: Mapping[str, Any]) -> None:
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    if len(encoded) > _MAX_OUTPUT_BYTES:
        encoded = json.dumps(
            {
                "ok": False,
                "error_code": "release_subprocess_output_too_large",
                "metrics": {"peak_rss_bytes": _rss_bytes()},
            },
            separators=(",", ":"),
        ).encode("utf-8")
    sys.stdout.buffer.write(encoded)
    sys.stdout.buffer.flush()


def main() -> int:
    _apply_resource_limits()
    started_wall = time.monotonic()
    started_cpu = time.process_time()
    metrics: dict[str, Any] = {
        "pid": os.getpid(),
        "bytes_read": 0,
        "files_examined": 0,
    }
    try:
        raw = sys.stdin.buffer.read(_MAX_REQUEST_BYTES + 1)
        if len(raw) > _MAX_REQUEST_BYTES:
            raise ReleaseProcessFailure("release_subprocess_request_too_large")
        request = json.loads(raw.decode("utf-8"))
        if not isinstance(request, dict):
            raise ReleaseProcessFailure("release_subprocess_request_invalid")
        operation = _safe_text(request.get("operation"), 32)
        if operation == "check":
            result, operation_metrics = _check(request)
        elif operation == "download":
            result, operation_metrics = _download(request)
        elif operation == "verify":
            result, operation_metrics = _verify(request)
        else:
            raise ReleaseProcessFailure("release_subprocess_operation_unsupported")
        metrics.update(operation_metrics)
        metrics.update(
            {
                "wall_ms": round((time.monotonic() - started_wall) * 1000.0, 3),
                "cpu_ms": round((time.process_time() - started_cpu) * 1000.0, 3),
                "peak_rss_bytes": _rss_bytes(),
            }
        )
        memory_budget = _bounded_int(
            "POCKETLAB_RELEASE_CHILD_MAX_RSS_BYTES",
            256 * 1024 * 1024,
            64 * 1024 * 1024,
            2 * 1024 * 1024 * 1024,
        )
        if int(metrics.get("peak_rss_bytes") or 0) > memory_budget:
            raise ReleaseProcessFailure("release_child_memory_budget_exceeded")
        _emit({"ok": True, "result": result, "metrics": metrics})
        return 0
    except ReleaseProcessFailure as exc:
        metrics.update(
            {
                "wall_ms": round((time.monotonic() - started_wall) * 1000.0, 3),
                "cpu_ms": round((time.process_time() - started_cpu) * 1000.0, 3),
                "peak_rss_bytes": _rss_bytes(),
            }
        )
        _emit({"ok": False, "error_code": exc.code, "metrics": metrics})
        return 2
    except Exception as exc:
        metrics.update(
            {
                "wall_ms": round((time.monotonic() - started_wall) * 1000.0, 3),
                "cpu_ms": round((time.process_time() - started_cpu) * 1000.0, 3),
                "peak_rss_bytes": _rss_bytes(),
            }
        )
        _emit(
            {
                "ok": False,
                "error_code": f"release_subprocess_{type(exc).__name__}"[:80],
                "metrics": metrics,
            }
        )
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
