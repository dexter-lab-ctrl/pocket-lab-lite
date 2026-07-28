from __future__ import annotations

"""Bounded Pocket Lab Lite release subprocess.

One compact request is accepted on stdin and one sanitized envelope is emitted on
stdout. Network access, hashing, ZIP inspection/extraction, staging, atomic PWA
pointer promotion, local/HTTP validation, and rollback live outside FastAPI.
"""

import hashlib
import json
import os
import re
from pathlib import Path
try:
    import resource  # type: ignore
except Exception:  # pragma: no cover
    resource = None  # type: ignore
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any, Mapping
import urllib.error
import urllib.parse
import urllib.request

from .lite_release_contract import (
    ARTIFACT_NAME,
    BUILD_IDENTITY_NAME,
    CHECKSUMS_NAME,
    MANIFEST_NAME,
    PRODUCT,
    LiteReleaseContractError,
    inspect_pwa_archive,
    newest_valid_release,
    parse_checksums,
    parse_lite_tag,
    safe_extract_zip,
    select_assets,
    sha256_file,
    validate_manifest,
)

_MAX_REQUEST_BYTES = 128 * 1024
_MAX_OUTPUT_BYTES = 256 * 1024


class ReleaseProcessFailure(RuntimeError):
    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = str(code or "release_process_failed")[:80]


def _fail_contract(exc: LiteReleaseContractError) -> ReleaseProcessFailure:
    return ReleaseProcessFailure(exc.code)


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


def _absolute_no_follow(value: Any) -> Path:
    path = Path(_safe_text(value, 4096)).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    return Path(os.path.abspath(path))


def _rss_bytes() -> int:
    if resource is None:
        return 0
    try:
        value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        return value if sys.platform == "darwin" else value * 1024
    except Exception:
        return 0


def _apply_resource_limits() -> None:
    if resource is None:
        return
    requested: list[tuple[int, int]] = []
    if hasattr(resource, "RLIMIT_CPU"):
        requested.append((resource.RLIMIT_CPU, _bounded_int("POCKETLAB_RELEASE_CHILD_CPU_SECONDS", 120, 2, 900)))
    address_space = _bounded_int("POCKETLAB_RELEASE_CHILD_MAX_ADDRESS_SPACE_BYTES", 0, 0, 8 * 1024**3)
    if address_space and hasattr(resource, "RLIMIT_AS"):
        requested.append((resource.RLIMIT_AS, address_space))
    if hasattr(resource, "RLIMIT_FSIZE"):
        requested.append((resource.RLIMIT_FSIZE, _bounded_int("POCKETLAB_RELEASE_CHILD_MAX_FILE_BYTES", 512 * 1024**2, 1024**2, 2 * 1024**3)))
    if hasattr(resource, "RLIMIT_NOFILE"):
        requested.append((resource.RLIMIT_NOFILE, _bounded_int("POCKETLAB_RELEASE_CHILD_MAX_FILES", 96, 16, 512)))
    for kind, soft in requested:
        try:
            _old_soft, hard = resource.getrlimit(kind)
            bounded_hard = soft if hard in {-1, resource.RLIM_INFINITY} else min(soft, hard)
            resource.setrlimit(kind, (min(soft, bounded_hard), bounded_hard))
        except (ValueError, OSError):
            continue


def _configured_allowed_hosts() -> set[str]:
    configured = {
        item.strip().lower()
        for item in os.environ.get(
            "POCKETLAB_RELEASE_ALLOWED_HOSTS",
            "api.github.com,github.com,objects.githubusercontent.com,release-assets.githubusercontent.com",
        ).split(",")
        if item.strip()
    }
    source = str(os.environ.get("POCKETLAB_GITHUB_RELEASES_API", "") or "").strip()
    if source:
        host = (urllib.parse.urlparse(source).hostname or "").lower()
        if host:
            configured.add(host)
    return configured


def _allowed_host(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    allow_insecure = str(os.environ.get("POCKETLAB_RELEASE_ALLOW_INSECURE_SOURCE", "")).lower() in {"1", "true", "yes", "on"}
    if parsed.scheme.lower() not in ({"https", "http"} if allow_insecure else {"https"}):
        raise ReleaseProcessFailure("release_source_scheme_rejected")
    if parsed.username or parsed.password:
        raise ReleaseProcessFailure("release_source_userinfo_rejected")
    host = (parsed.hostname or "").lower()
    if not host:
        raise ReleaseProcessFailure("release_source_host_missing")
    if host not in _configured_allowed_hosts():
        raise ReleaseProcessFailure("release_source_host_rejected")
    return host


def _request_headers(*, binary: bool = False) -> dict[str, str]:
    headers = {
        "Accept": "application/octet-stream" if binary else "application/vnd.github+json, application/json",
        "User-Agent": "Pocket-Lab-Lite-Release-Subprocess",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = str(os.environ.get("POCKETLAB_GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _open(url: str, *, timeout: float, binary: bool = False):
    original_host = _allowed_host(url)
    request = urllib.request.Request(url, headers=_request_headers(binary=binary))
    try:
        response = urllib.request.urlopen(request, timeout=timeout)
    except urllib.error.HTTPError as exc:
        if exc.code == 403 and exc.headers.get("X-RateLimit-Remaining") == "0":
            raise ReleaseProcessFailure("release_github_rate_limited") from exc
        raise ReleaseProcessFailure(f"release_http_{int(exc.code)}") from exc
    except urllib.error.URLError as exc:
        raise ReleaseProcessFailure("release_source_unreachable") from exc
    final_url = str(response.geturl() or url)
    final_host = _allowed_host(final_url)
    if final_host != original_host and final_host not in _configured_allowed_hosts():
        response.close()
        raise ReleaseProcessFailure("release_redirect_host_rejected")
    return response


def _urlopen_bounded(url: str, *, timeout: float, max_bytes: int, binary: bool = False) -> tuple[bytes, int]:
    with _open(url, timeout=timeout, binary=binary) as response:
        declared = response.headers.get("Content-Length")
        if declared:
            try:
                if int(declared) > max_bytes:
                    raise ReleaseProcessFailure("release_response_too_large")
            except ValueError:
                pass
        body = response.read(max_bytes + 1)
    if len(body) > max_bytes:
        raise ReleaseProcessFailure("release_response_too_large")
    return body, len(body)


def _download_to_file(url: str, target: Path, *, timeout: float, max_bytes: int) -> tuple[str, int]:
    target.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    total = 0
    temporary: Path | None = None
    try:
        with _open(url, timeout=timeout, binary=True) as response, tempfile.NamedTemporaryFile(
            mode="wb", dir=target.parent, prefix=f".{target.name}.", delete=False
        ) as handle:
            temporary = Path(handle.name)
            declared = response.headers.get("Content-Length")
            if declared:
                try:
                    if int(declared) > max_bytes:
                        raise ReleaseProcessFailure("release_response_too_large")
                except ValueError:
                    pass
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise ReleaseProcessFailure("release_response_too_large")
                digest.update(chunk)
                handle.write(chunk)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return digest.hexdigest(), total


def _safe_under(root_value: Any, path_value: Any, *, create_root: bool = True) -> tuple[Path, Path]:
    root = Path(_safe_text(root_value, 4096)).expanduser().resolve(strict=False)
    if not str(root):
        raise ReleaseProcessFailure("release_root_missing")
    if create_root:
        root.mkdir(parents=True, exist_ok=True)
    path = Path(_safe_text(path_value, 4096)).expanduser().resolve(strict=False)
    if root != path and root not in path.parents:
        raise ReleaseProcessFailure("release_staging_path_rejected")
    return root, path


def _json_body(url: str, *, timeout: float, max_bytes: int) -> tuple[Any, int]:
    body, read = _urlopen_bounded(url, timeout=timeout, max_bytes=max_bytes)
    try:
        return json.loads(body.decode("utf-8")), read
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReleaseProcessFailure("release_metadata_invalid_json") from exc


def _check(payload: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    timeout = _bounded_float(payload.get("network_timeout_seconds"), 15.0, 1.0, 90.0)
    metadata_limit = max(16 * 1024, min(int(payload.get("max_metadata_bytes") or 2 * 1024 * 1024), 8 * 1024 * 1024))
    releases, bytes_read = _json_body(_safe_text(payload.get("source_url"), 4096), timeout=timeout, max_bytes=metadata_limit)
    if not isinstance(releases, list):
        raise ReleaseProcessFailure("release_metadata_invalid_shape")
    try:
        selected = newest_valid_release(
            [item for item in releases if isinstance(item, Mapping)],
            allow_prerelease=bool(payload.get("allow_prerelease")),
        )
        tag = parse_lite_tag(selected.get("tag_name")).value
        assets = select_assets(selected)
    except LiteReleaseContractError as exc:
        raise _fail_contract(exc) from exc
    checksums_body, checksum_bytes = _urlopen_bounded(
        assets[CHECKSUMS_NAME]["download_url"], timeout=timeout, max_bytes=64 * 1024
    )
    manifest_body, manifest_bytes = _urlopen_bounded(
        assets[MANIFEST_NAME]["download_url"], timeout=timeout, max_bytes=64 * 1024
    )
    bytes_read += checksum_bytes + manifest_bytes
    try:
        checksums = parse_checksums(checksums_body.decode("utf-8"))
        manifest_raw = json.loads(manifest_body.decode("utf-8"))
        if not isinstance(manifest_raw, Mapping):
            raise LiteReleaseContractError("release_manifest_invalid_shape")
        manifest = validate_manifest(manifest_raw, release_tag=tag, checksum_sha256=checksums[ARTIFACT_NAME])
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReleaseProcessFailure("release_manifest_invalid_json") from exc
    except LiteReleaseContractError as exc:
        raise _fail_contract(exc) from exc
    install_mode = _safe_text(payload.get("install_mode") or "unknown", 16).lower()
    current_tag = _safe_text(payload.get("installed_release_tag"), 120)
    comparison = "unknown_installed_identity"
    update_available = False
    if install_mode == "release" and current_tag:
        try:
            installed = parse_lite_tag(current_tag)
            latest = parse_lite_tag(tag)
            comparison = "equal" if installed == latest else ("newer" if installed > latest else "older")
            update_available = comparison == "older"
        except LiteReleaseContractError:
            comparison = "invalid"
    elif install_mode == "source":
        comparison = "source_install"
    result = {
        "product": PRODUCT,
        "current_tag": current_tag or "",
        "latest_tag": tag,
        "comparison": comparison,
        "update_available": update_available,
        "auto_apply": bool(payload.get("auto_apply")),
        "manifest_verified": True,
        "artifact_verified": False,
        "latest_release": {
            "tag_name": tag,
            "name": _safe_text(selected.get("name") or f"Pocket Lab Lite {tag}", 240),
            "html_url": _safe_text(selected.get("html_url"), 1024),
            "published_at": _safe_text(selected.get("published_at"), 80) or None,
            "draft": False,
            "prerelease": bool(selected.get("prerelease")),
            "manifest": manifest,
            "assets": assets,
            "artifact": {
                "name": ARTIFACT_NAME,
                "size": int(assets[ARTIFACT_NAME]["size"]),
                "digest": "sha256:" + manifest["artifact_sha256"],
                "verification_status": "manifest_and_checksum_verified",
            },
        },
        "sanitized": True,
    }
    return result, {"bytes_read": bytes_read, "files_examined": 3}


def _fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def _prune_directories(root: Path, *, keep: int, protected: set[str] | None = None) -> int:
    protected_names = set(protected or set())
    if not root.exists():
        return 0
    candidates: list[tuple[float, Path]] = []
    for child in root.iterdir():
        if not child.is_dir() or child.name in protected_names or child.name.startswith("."):
            continue
        try:
            candidates.append((child.stat().st_mtime, child))
        except OSError:
            continue
    candidates.sort(key=lambda item: item[0], reverse=True)
    removed = 0
    for _mtime, child in candidates[max(0, keep):]:
        shutil.rmtree(child, ignore_errors=True)
        removed += 1
    return removed


def _verify_caddy_static_root(caddyfile_value: Any, current: Path) -> None:
    text_value = _safe_text(caddyfile_value, 4096)
    if not text_value:
        return
    caddyfile = Path(text_value).expanduser().resolve(strict=False)
    if not caddyfile.is_file():
        raise ReleaseProcessFailure("release_caddy_config_missing")
    try:
        if caddyfile.stat().st_size > 512 * 1024:
            raise ReleaseProcessFailure("release_caddy_config_too_large")
        text = caddyfile.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise ReleaseProcessFailure("release_caddy_config_unreadable") from exc
    expected = str(current)
    roots = [
        line.strip()[7:].strip()
        for line in text.splitlines()
        if line.strip().startswith("root * ")
    ]
    if expected not in roots:
        raise ReleaseProcessFailure("release_caddy_static_root_mismatch")


def _stage(payload: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        tag = parse_lite_tag(payload.get("release_tag")).value
    except LiteReleaseContractError as exc:
        raise _fail_contract(exc) from exc
    root, target = _safe_under(payload.get("staging_root"), payload.get("target_dir"))
    _prune_directories(
        root,
        keep=_bounded_int("POCKETLAB_RELEASE_RETAIN_STAGING_COUNT", 2, 1, 8),
        protected={target.name},
    )
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, mode=0o700)
    try:
        assets = payload.get("assets") if isinstance(payload.get("assets"), Mapping) else {}
        required = {ARTIFACT_NAME, CHECKSUMS_NAME, MANIFEST_NAME}
        if set(assets) != required:
            raise ReleaseProcessFailure("release_asset_missing")
        timeout = _bounded_float(payload.get("network_timeout_seconds"), 60.0, 2.0, 600.0)
        max_download = _bounded_int("POCKETLAB_RELEASE_MAX_DOWNLOAD_BYTES", 256 * 1024**2, 1024**2, 2 * 1024**3)
        bytes_read = 0
        downloaded: dict[str, Path] = {}
        for name in (CHECKSUMS_NAME, MANIFEST_NAME, ARTIFACT_NAME):
            item = assets.get(name) if isinstance(assets.get(name), Mapping) else {}
            url = _safe_text(item.get("download_url"), 4096)
            limit = 64 * 1024 if name != ARTIFACT_NAME else max_download
            _digest, size = _download_to_file(url, target / name, timeout=timeout, max_bytes=limit)
            declared_size = int(item.get("size") or 0)
            if declared_size <= 0 or size != declared_size:
                raise ReleaseProcessFailure("release_asset_size_mismatch")
            bytes_read += size
            downloaded[name] = target / name
        try:
            checksums = parse_checksums(downloaded[CHECKSUMS_NAME].read_text(encoding="utf-8"))
            manifest_raw = json.loads(downloaded[MANIFEST_NAME].read_text(encoding="utf-8"))
            if not isinstance(manifest_raw, Mapping):
                raise LiteReleaseContractError("release_manifest_invalid_shape")
            manifest = validate_manifest(manifest_raw, release_tag=tag, checksum_sha256=checksums[ARTIFACT_NAME])
        except (OSError, json.JSONDecodeError) as exc:
            raise ReleaseProcessFailure("release_manifest_invalid_json") from exc
        except LiteReleaseContractError as exc:
            raise _fail_contract(exc) from exc
        observed, artifact_size = sha256_file(downloaded[ARTIFACT_NAME], max_bytes=max_download)
        if observed != manifest["artifact_sha256"]:
            raise ReleaseProcessFailure("release_checksum_mismatch")
        free = shutil.disk_usage(root).free
        minimum_free = _bounded_int("POCKETLAB_RELEASE_MIN_FREE_BYTES", 256 * 1024**2, 32 * 1024**2, 8 * 1024**3)
        if free < minimum_free + artifact_size:
            raise ReleaseProcessFailure("release_disk_pressure")
        try:
            archive = inspect_pwa_archive(
                downloaded[ARTIFACT_NAME],
                max_entries=_bounded_int("POCKETLAB_RELEASE_ARCHIVE_MAX_ENTRIES", 4096, 1, 100_000),
                max_expanded_bytes=_bounded_int("POCKETLAB_RELEASE_ARCHIVE_MAX_EXPANDED_BYTES", 512 * 1024**2, 1024**2, 4 * 1024**3),
                max_ratio=_bounded_float(os.environ.get("POCKETLAB_RELEASE_ARCHIVE_MAX_RATIO", "200"), 200.0, 2.0, 10_000.0),
                max_depth=_bounded_int("POCKETLAB_RELEASE_ARCHIVE_MAX_DEPTH", 16, 2, 64),
            )
        except LiteReleaseContractError as exc:
            raise _fail_contract(exc) from exc
        content_temp = target / "content.preparing"
        content = target / "content"
        safe_extract_zip(downloaded[ARTIFACT_NAME], content_temp)
        embedded_identity = content_temp / BUILD_IDENTITY_NAME
        if not embedded_identity.is_file():
            raise ReleaseProcessFailure("release_archive_build_identity_missing")
        try:
            build_identity = json.loads(embedded_identity.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ReleaseProcessFailure("release_archive_build_identity_invalid") from exc
        if (
            not isinstance(build_identity, Mapping)
            or build_identity.get("product") != PRODUCT
            or build_identity.get("release_tag") != tag
            or str(build_identity.get("source_commit") or "").lower() != manifest["source_commit"]
        ):
            raise ReleaseProcessFailure("release_archive_build_identity_mismatch")
        os.replace(content_temp, content)
        _fsync_directory(content)
        _fsync_directory(target)
        ready = {
            "product": PRODUCT,
            "release_tag": tag,
            "artifact_sha256": observed,
            "source_commit": manifest["source_commit"],
            "archive": archive,
            "status": "ready",
        }
        ready_tmp = target / ".staging-ready.tmp"
        ready_tmp.write_text(json.dumps(ready, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        with ready_tmp.open("rb") as handle:
            os.fsync(handle.fileno())
        os.replace(ready_tmp, target / "staging-ready.json")
        _fsync_directory(target)
        return {
            **ready,
            "staged_path": str(target),
            "content_path": str(content),
            "manifest_verified": True,
            "artifact_verified": True,
            "sanitized": True,
        }, {"bytes_read": bytes_read + artifact_size, "files_examined": int(archive["entry_count"]) + 3}
    except Exception:
        shutil.rmtree(target, ignore_errors=True)
        raise


def _pm2_restart_snapshot() -> dict[str, int]:
    executable = shutil.which("pm2")
    if not executable:
        return {}
    try:
        completed = subprocess.run(
            [executable, "jlist"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=4.0,
        )
        payload = json.loads(completed.stdout) if completed.returncode == 0 else []
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return {}
    expected = {"pocket-api", "pocket-worker", "caddy-proxy"}
    result: dict[str, int] = {}
    for item in payload if isinstance(payload, list) else []:
        if not isinstance(item, Mapping):
            continue
        name = _safe_text(item.get("name"), 80)
        if name not in expected:
            continue
        environment = item.get("pm2_env") if isinstance(item.get("pm2_env"), Mapping) else {}
        result[name] = max(0, int(environment.get("restart_time") or 0))
    return result


def _copy_release_tree(source: Path, target: Path) -> None:
    temp = target.with_name(f".{target.name}.preparing-{os.getpid()}")
    if temp.exists():
        shutil.rmtree(temp)
    shutil.copytree(source, temp, symlinks=False)
    for directory, _dirs, files in os.walk(temp):
        for name in files:
            path = Path(directory) / name
            with path.open("rb") as handle:
                os.fsync(handle.fileno())
    os.replace(temp, target)


def _replace_symlink(link: Path, target: Path) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    temporary = link.with_name(f".{link.name}.next-{os.getpid()}")
    temporary.unlink(missing_ok=True)
    relative = os.path.relpath(target, link.parent)
    temporary.symlink_to(relative, target_is_directory=True)
    os.replace(temporary, link)
    _fsync_directory(link.parent)


def _promote(payload: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        tag = parse_lite_tag(payload.get("release_tag")).value
    except LiteReleaseContractError as exc:
        raise _fail_contract(exc) from exc
    source = Path(_safe_text(payload.get("content_path"), 4096)).expanduser().resolve(strict=True)
    current = _absolute_no_follow(payload.get("current_link"))
    releases = Path(_safe_text(payload.get("releases_dir"), 4096)).expanduser().resolve(strict=False)
    releases.mkdir(parents=True, exist_ok=True)
    if current.parent.resolve(strict=False) != releases.parent.resolve(strict=False):
        raise ReleaseProcessFailure("release_static_root_layout_invalid")
    _verify_caddy_static_root(payload.get("caddyfile"), current)
    pm2_restart_baseline = _pm2_restart_snapshot()
    target = releases / tag
    if not target.exists():
        _copy_release_tree(source, target)
    previous_target = ""
    if current.is_symlink():
        resolved = current.resolve(strict=False)
        if releases == resolved or releases not in resolved.parents:
            raise ReleaseProcessFailure("release_current_pointer_invalid")
        if resolved.name == tag:
            return {
                "product": PRODUCT,
                "release_tag": tag,
                "promotion_status": "already_current",
                "previous_release_tag": (current.parent / "previous").resolve(strict=False).name
                if (current.parent / "previous").is_symlink() else "",
                "rollback_available": (current.parent / "previous").is_symlink(),
                "pm2_restart_baseline": pm2_restart_baseline,
                "sanitized": True,
            }, {"bytes_read": 0, "files_examined": 1}
        previous_target = resolved.name
    elif current.exists():
        raise ReleaseProcessFailure("release_static_root_not_pointer")
    previous_link = current.parent / "previous"
    if previous_target:
        _replace_symlink(previous_link, releases / previous_target)
    _replace_symlink(current, target)
    _prune_directories(
        releases,
        keep=_bounded_int("POCKETLAB_RELEASE_RETAIN_COUNT", 3, 2, 10),
        protected={tag, previous_target},
    )
    return {
        "product": PRODUCT,
        "release_tag": tag,
        "promotion_status": "promoted",
        "previous_release_tag": previous_target,
        "rollback_available": bool(previous_target),
        "pm2_restart_baseline": pm2_restart_baseline,
        "sanitized": True,
    }, {"bytes_read": 0, "files_examined": 1}


def _http_get(url: str, *, timeout: float, max_bytes: int = 512 * 1024) -> bytes:
    parsed = urllib.parse.urlparse(url)
    if parsed.username or parsed.password:
        raise ReleaseProcessFailure("release_health_url_userinfo_rejected")
    host = (parsed.hostname or "").lower()
    loopback = host in {"127.0.0.1", "localhost", "::1"}
    if parsed.scheme.lower() != "https" and not (parsed.scheme.lower() == "http" and loopback):
        raise ReleaseProcessFailure("release_health_url_scheme_rejected")
    request = urllib.request.Request(
        url, headers={"Accept": "application/json,text/html,*/*", "User-Agent": "Pocket-Lab-Lite-Health-Validator"}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            final = urllib.parse.urlparse(str(response.geturl() or url))
            if (final.hostname or "").lower() != host or final.username or final.password:
                raise ReleaseProcessFailure("release_health_redirect_rejected")
            body = response.read(max_bytes + 1)
    except urllib.error.HTTPError as exc:
        raise ReleaseProcessFailure(f"release_health_http_{int(exc.code)}") from exc
    except urllib.error.URLError as exc:
        raise ReleaseProcessFailure("release_health_unreachable") from exc
    if len(body) > max_bytes:
        raise ReleaseProcessFailure("release_health_response_too_large")
    return body


def _validate(payload: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    raw_tag = _safe_text(payload.get("release_tag"), 120)
    install_mode = _safe_text(payload.get("install_mode") or "", 16).lower()
    if not install_mode:
        install_mode = "release" if raw_tag.startswith("lite-") else "source"
    if install_mode == "release":
        try:
            tag = parse_lite_tag(raw_tag).value
        except LiteReleaseContractError as exc:
            raise _fail_contract(exc) from exc
    elif install_mode == "source":
        if not raw_tag.startswith("source-") or not re.fullmatch(r"source-[A-Za-z0-9._-]{1,96}", raw_tag):
            raise ReleaseProcessFailure("release_source_identity_invalid")
        tag = raw_tag
    else:
        raise ReleaseProcessFailure("release_install_mode_invalid")
    current = _absolute_no_follow(payload.get("current_link"))
    if not current.is_symlink():
        raise ReleaseProcessFailure("release_current_pointer_missing")
    root = current.resolve(strict=True)
    required = ["index.html", "manifest.webmanifest", BUILD_IDENTITY_NAME]
    for name in required:
        if not (root / name).is_file():
            raise ReleaseProcessFailure("release_post_switch_asset_missing")
    try:
        embedded = json.loads((root / BUILD_IDENTITY_NAME).read_text(encoding="utf-8"))
        if not isinstance(embedded, Mapping) or embedded.get("product") != PRODUCT:
            raise ReleaseProcessFailure("release_post_switch_marker_mismatch")
        embedded_mode = _safe_text(embedded.get("install_mode") or "release", 16).lower()
        embedded_tag = _safe_text(embedded.get("release_tag"), 120)
        if install_mode == "release":
            if embedded_mode != "release" or parse_lite_tag(embedded_tag).value != tag:
                raise ReleaseProcessFailure("release_post_switch_marker_mismatch")
        elif embedded_mode != "source" or embedded_tag != tag:
            raise ReleaseProcessFailure("release_post_switch_marker_mismatch")
    except (OSError, json.JSONDecodeError, LiteReleaseContractError) as exc:
        if isinstance(exc, ReleaseProcessFailure):
            raise
        raise ReleaseProcessFailure("release_post_switch_marker_mismatch") from exc
    representative = payload.get("representative_assets") if isinstance(payload.get("representative_assets"), list) else []
    for name in representative[:8]:
        candidate = (root / _safe_text(name, 1024)).resolve(strict=False)
        if root != candidate and root not in candidate.parents:
            raise ReleaseProcessFailure("release_post_switch_asset_invalid")
        if not candidate.is_file():
            raise ReleaseProcessFailure("release_post_switch_asset_missing")
    base_url = _safe_text(payload.get("base_url"), 2048).rstrip("/")
    api_health_url = _safe_text(payload.get("api_health_url"), 2048)
    api_prepared_url = _safe_text(payload.get("api_prepared_url"), 2048)
    timeout = _bounded_float(payload.get("health_timeout_seconds"), 5.0, 1.0, 30.0)
    if base_url:
        index = _http_get(base_url + "/", timeout=timeout)
        if PRODUCT.replace("-", " ").encode() not in index.lower() and b"pocket lab lite" not in index.lower():
            raise ReleaseProcessFailure("release_post_switch_http_marker_missing")
        _http_get(base_url + "/manifest.webmanifest", timeout=timeout)
        _http_get(base_url + "/" + BUILD_IDENTITY_NAME, timeout=timeout)
        for name in representative[:4]:
            _http_get(base_url + "/" + _safe_text(name, 1024).lstrip("/"), timeout=timeout)
    if api_health_url:
        _http_get(api_health_url, timeout=timeout)
    if api_prepared_url:
        _http_get(api_prepared_url, timeout=timeout)
    baseline = payload.get("pm2_restart_baseline") if isinstance(payload.get("pm2_restart_baseline"), Mapping) else {}
    pm2_verified = False
    if baseline:
        observed = _pm2_restart_snapshot()
        if not observed or any(
            name not in observed or int(observed[name]) > int(value or 0)
            for name, value in baseline.items()
        ):
            raise ReleaseProcessFailure("release_unexpected_process_restart")
        pm2_verified = True
    return {
        "product": PRODUCT,
        "release_tag": tag,
        "install_mode": install_mode,
        "validation_status": "passed",
        "installed_marker_verified": True,
        "pm2_restart_verified": pm2_verified,
        "sanitized": True,
    }, {"bytes_read": 0, "files_examined": len(required) + len(representative)}


def _rollback(payload: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    current = _absolute_no_follow(payload.get("current_link"))
    previous = current.parent / "previous"
    releases = Path(_safe_text(payload.get("releases_dir"), 4096)).expanduser().resolve(strict=False)
    if not previous.is_symlink():
        raise ReleaseProcessFailure("release_previous_release_missing")
    target = previous.resolve(strict=True)
    if releases != target and releases not in target.parents:
        raise ReleaseProcessFailure("release_previous_pointer_invalid")
    failed_target = current.resolve(strict=False).name if current.is_symlink() else ""
    if current.is_symlink() and current.resolve(strict=False) == target:
        return {
            "rollback_status": "already_rolled_back",
            "restored_release_tag": target.name,
            "failed_release_tag": failed_target,
            "sanitized": True,
        }, {"bytes_read": 0, "files_examined": 1}
    _replace_symlink(current, target)
    return {
        "rollback_status": "rolled_back",
        "restored_release_tag": target.name,
        "failed_release_tag": failed_target,
        "sanitized": True,
    }, {"bytes_read": 0, "files_examined": 1}


def _recover(payload: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    generation = max(0, int(payload.get("generation") or 0))
    phase = _safe_text(payload.get("phase"), 32).lower()
    staging_root = _absolute_no_follow(payload.get("staging_root"))
    current = _absolute_no_follow(payload.get("current_link"))
    releases = _absolute_no_follow(payload.get("releases_dir"))
    removed = 0
    examined = 0

    if staging_root.exists():
        for child in list(staging_root.iterdir())[:256]:
            examined += 1
            matches_generation = bool(
                generation and child.name.startswith(f"generation-{generation}-")
            )
            matches_preparing = child.name.startswith(".") and "preparing" in child.name
            if not (matches_generation or matches_preparing):
                continue
            if child.is_symlink() or child.is_file():
                child.unlink(missing_ok=True)
            elif child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            removed += 1

    if releases.exists():
        for child in list(releases.iterdir())[:256]:
            examined += 1
            if not (child.name.startswith(".") and "preparing" in child.name):
                continue
            if child.is_symlink() or child.is_file():
                child.unlink(missing_ok=True)
            elif child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            removed += 1

    rollback_status = "not_required"
    restored_release_tag = ""
    promotion_phases = {"installing", "promoting", "validating"}
    if phase in promotion_phases:
        if current.parent.resolve(strict=False) != releases.parent.resolve(strict=False):
            raise ReleaseProcessFailure("release_static_root_layout_invalid")
        previous = current.parent / "previous"
        if previous.is_symlink():
            target = previous.resolve(strict=True)
            if releases != target and releases not in target.parents:
                raise ReleaseProcessFailure("release_previous_pointer_invalid")
            restored_release_tag = target.name
            if current.is_symlink() and current.resolve(strict=False) == target:
                rollback_status = "already_rolled_back"
            else:
                _replace_symlink(current, target)
                rollback_status = "rolled_back"
        else:
            rollback_status = "rollback_unavailable"

    return {
        "recovered": True,
        "generation": generation,
        "failure_stage": phase,
        "rollback_status": rollback_status,
        "restored_release_tag": restored_release_tag,
        "staging_removed": removed,
        "sanitized": True,
    }, {"bytes_read": 0, "files_examined": examined}


def _cleanup(payload: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    root = Path(_safe_text(payload.get("root"), 4096)).expanduser().resolve(strict=False)
    keep = _bounded_int("POCKETLAB_RELEASE_RETAIN_COUNT", int(payload.get("retain_count") or 3), 2, 10)
    removed = 0
    for child in sorted((p for p in root.glob("*") if p.is_dir()), key=lambda p: p.stat().st_mtime, reverse=True)[keep:]:
        shutil.rmtree(child, ignore_errors=True)
        removed += 1
    return {"removed": removed, "retained": keep, "sanitized": True}, {"bytes_read": 0, "files_examined": removed}


def _emit(payload: Mapping[str, Any]) -> None:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    if len(encoded) > _MAX_OUTPUT_BYTES:
        encoded = json.dumps({"ok": False, "error_code": "release_subprocess_output_too_large", "metrics": {"peak_rss_bytes": _rss_bytes()}}, separators=(",", ":")).encode("utf-8")
    sys.stdout.buffer.write(encoded)
    sys.stdout.buffer.flush()


def main() -> int:
    _apply_resource_limits()
    started_wall = time.monotonic()
    started_cpu = time.process_time()
    metrics: dict[str, Any] = {"pid": os.getpid(), "bytes_read": 0, "files_examined": 0}
    try:
        raw = sys.stdin.buffer.read(_MAX_REQUEST_BYTES + 1)
        if len(raw) > _MAX_REQUEST_BYTES:
            raise ReleaseProcessFailure("release_subprocess_request_too_large")
        request = json.loads(raw.decode("utf-8"))
        if not isinstance(request, dict):
            raise ReleaseProcessFailure("release_subprocess_request_invalid")
        operation = _safe_text(request.get("operation"), 32)
        handlers = {
            "check": _check,
            "stage": _stage,
            "promote": _promote,
            "validate": _validate,
            "rollback": _rollback,
            "recover": _recover,
            "cleanup": _cleanup,
        }
        handler = handlers.get(operation)
        if handler is None:
            raise ReleaseProcessFailure("release_subprocess_operation_unsupported")
        result, operation_metrics = handler(request)
        metrics.update(operation_metrics)
        metrics.update({
            "wall_ms": round((time.monotonic() - started_wall) * 1000.0, 3),
            "cpu_ms": round((time.process_time() - started_cpu) * 1000.0, 3),
            "peak_rss_bytes": _rss_bytes(),
        })
        if int(metrics["peak_rss_bytes"] or 0) > _bounded_int("POCKETLAB_RELEASE_CHILD_MAX_RSS_BYTES", 256 * 1024**2, 64 * 1024**2, 2 * 1024**3):
            raise ReleaseProcessFailure("release_child_memory_budget_exceeded")
        _emit({"ok": True, "result": result, "metrics": metrics})
        return 0
    except ReleaseProcessFailure as exc:
        metrics.update({
            "wall_ms": round((time.monotonic() - started_wall) * 1000.0, 3),
            "cpu_ms": round((time.process_time() - started_cpu) * 1000.0, 3),
            "peak_rss_bytes": _rss_bytes(),
        })
        _emit({"ok": False, "error_code": exc.code, "metrics": metrics})
        return 2
    except Exception as exc:
        metrics.update({
            "wall_ms": round((time.monotonic() - started_wall) * 1000.0, 3),
            "cpu_ms": round((time.process_time() - started_cpu) * 1000.0, 3),
            "peak_rss_bytes": _rss_bytes(),
        })
        _emit({"ok": False, "error_code": f"release_subprocess_{type(exc).__name__}"[:80], "metrics": metrics})
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
