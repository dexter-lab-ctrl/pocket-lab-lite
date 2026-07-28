from __future__ import annotations

"""Pure Pocket Lab Lite release identity and artifact validation helpers."""

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
from typing import Any, Iterable, Mapping
from urllib.parse import urlparse
import zipfile

PRODUCT = "pocket-lab-lite"
DEFAULT_REPOSITORY = "dexter-lab-ctrl/pocket-lab-lite"
MANIFEST_NAME = "pocketlab-lite-release.json"
BUILD_IDENTITY_NAME = "pocketlab-lite-build.json"
ARTIFACT_NAME = "dist.zip"
CHECKSUMS_NAME = "checksums.txt"
TAG_RE = re.compile(r"^lite-([0-9]{4})\.([0-9]{2})\.([0-9]{2})\.([1-9][0-9]*)$")
REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
HEX_RE = re.compile(r"^[0-9a-fA-F]{7,64}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

FORBIDDEN_ARCHIVE_PARTS = {
    ".git", ".github", ".env", "ansible", "gitea", "pocket_lab_iac",
    "site.yml", "operations", "runbooks", "security", "contracts", "tests",
    "api_fastapi", "workers", "agents", "supervisors",
}


class LiteReleaseContractError(ValueError):
    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = str(code or "release_contract_invalid")[:80]


def _archive_member_name(value: Any) -> tuple[str, PurePosixPath]:
    raw = str(value or "").replace("\\", "/")
    while raw.startswith("./"):
        raw = raw[2:]
    candidate = PurePosixPath(raw)
    first = candidate.parts[0] if candidate.parts else ""
    if (
        not raw
        or raw.startswith("/")
        or candidate.is_absolute()
        or ".." in candidate.parts
        or first.endswith(":")
    ):
        raise LiteReleaseContractError("release_archive_path_traversal")
    return raw, candidate


@dataclass(frozen=True, order=True)
class LiteTag:
    year: int
    month: int
    day: int
    sequence: int

    @property
    def value(self) -> str:
        return f"lite-{self.year:04d}.{self.month:02d}.{self.day:02d}.{self.sequence}"


def parse_lite_tag(value: Any) -> LiteTag:
    text = str(value or "").strip()
    match = TAG_RE.fullmatch(text)
    if not match:
        raise LiteReleaseContractError("release_tag_invalid")
    year, month, day, sequence = (int(part) for part in match.groups())
    if year < 2020 or year > 9999 or sequence < 1 or sequence > 999_999:
        raise LiteReleaseContractError("release_tag_invalid")
    try:
        datetime(year, month, day)
    except ValueError as exc:
        raise LiteReleaseContractError("release_tag_calendar_invalid") from exc
    return LiteTag(year, month, day, sequence)


def compare_release_identity(
    *, install_mode: str, installed_tag: Any, latest_tag: Any
) -> str:
    mode = str(install_mode or "unknown").strip().lower()
    if mode == "source":
        return "source_install"
    if mode != "release":
        return "unknown_installed_identity"
    try:
        installed = parse_lite_tag(installed_tag)
        latest = parse_lite_tag(latest_tag)
    except LiteReleaseContractError:
        return "invalid"
    if installed == latest:
        return "equal"
    return "newer" if installed > latest else "older"


def normalize_repository(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text.startswith("git@github.com:"):
        text = text.split(":", 1)[1]
    elif text.startswith("ssh://") or text.startswith("https://") or text.startswith("http://"):
        parsed = urlparse(text)
        if (parsed.hostname or "").lower() != "github.com" or parsed.username not in {None, "git"}:
            return ""
        text = parsed.path.lstrip("/")
    text = text.removesuffix(".git").strip("/")
    if not REPOSITORY_RE.fullmatch(text):
        return ""
    return text.lower()


def verify_repository(configured: Any, origin: Any) -> dict[str, Any]:
    configured_repo = normalize_repository(configured)
    origin_repo = normalize_repository(origin)
    match = bool(configured_repo and origin_repo and configured_repo == origin_repo)
    product_match = configured_repo.endswith("/" + PRODUCT) if configured_repo else False
    return {
        "product": PRODUCT,
        "configured_repository": configured_repo,
        "verified_repository": origin_repo,
        "repository_match": match and product_match,
        "product_match": product_match,
        "failure_code": "" if match and product_match else "release_product_mismatch",
    }


def parse_checksums(text: str) -> dict[str, str]:
    if len(text.encode("utf-8")) > 64 * 1024:
        raise LiteReleaseContractError("release_checksums_too_large")
    result: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 2:
            raise LiteReleaseContractError("release_checksums_invalid")
        digest, name = parts
        name = name.lstrip("*")
        digest = digest.lower()
        if not SHA256_RE.fullmatch(digest) or PurePosixPath(name).name != name:
            raise LiteReleaseContractError("release_checksums_invalid")
        if name in result:
            raise LiteReleaseContractError("release_asset_duplicate")
        result[name] = digest
    if ARTIFACT_NAME not in result:
        raise LiteReleaseContractError("release_checksum_missing")
    return result


def validate_manifest(
    payload: Mapping[str, Any], *, release_tag: str, checksum_sha256: str
) -> dict[str, Any]:
    if str(payload.get("product") or "") != PRODUCT:
        raise LiteReleaseContractError("release_manifest_wrong_product")
    if int(payload.get("schema_version") or 0) != 1:
        raise LiteReleaseContractError("release_manifest_schema_unsupported")
    parsed_tag = parse_lite_tag(payload.get("release_tag"))
    if parsed_tag.value != parse_lite_tag(release_tag).value:
        raise LiteReleaseContractError("release_manifest_tag_mismatch")
    if str(payload.get("artifact") or "") != ARTIFACT_NAME:
        raise LiteReleaseContractError("release_manifest_artifact_mismatch")
    digest = str(payload.get("artifact_sha256") or "").lower()
    if not SHA256_RE.fullmatch(digest) or digest != checksum_sha256.lower():
        raise LiteReleaseContractError("release_manifest_checksum_mismatch")
    commit = str(payload.get("source_commit") or "").strip()
    if not HEX_RE.fullmatch(commit):
        raise LiteReleaseContractError("release_manifest_source_commit_invalid")
    if str(payload.get("target") or "") != "web-pwa":
        raise LiteReleaseContractError("release_manifest_target_invalid")
    created_at = str(payload.get("created_at") or "").strip()
    try:
        datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise LiteReleaseContractError("release_manifest_created_at_invalid") from exc
    return {
        "product": PRODUCT,
        "schema_version": 1,
        "release_tag": parsed_tag.value,
        "artifact": ARTIFACT_NAME,
        "artifact_sha256": digest,
        "source_commit": commit.lower(),
        "target": "web-pwa",
        "minimum_runtime_version": str(payload.get("minimum_runtime_version") or "").strip()[:80],
        "created_at": created_at[:80],
    }


def select_assets(release: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    assets = release.get("assets") if isinstance(release.get("assets"), list) else []
    selected: dict[str, dict[str, Any]] = {}
    for item in assets[:128]:
        if not isinstance(item, Mapping):
            continue
        name = str(item.get("name") or "").strip()
        if name not in {ARTIFACT_NAME, CHECKSUMS_NAME, MANIFEST_NAME}:
            continue
        if name in selected:
            raise LiteReleaseContractError("release_asset_duplicate")
        size = int(item.get("size") or 0)
        if size <= 0:
            raise LiteReleaseContractError("release_asset_size_invalid")
        selected[name] = {
            "name": name,
            "size": size,
            "download_url": str(item.get("browser_download_url") or "").strip(),
        }
    missing = [name for name in (ARTIFACT_NAME, CHECKSUMS_NAME, MANIFEST_NAME) if name not in selected]
    if missing:
        raise LiteReleaseContractError("release_asset_missing")
    return selected


def sha256_file(path: Path, *, max_bytes: int) -> tuple[str, int]:
    digest = hashlib.sha256()
    total = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            total += len(chunk)
            if total > max_bytes:
                raise LiteReleaseContractError("release_artifact_size_limit")
            digest.update(chunk)
    return digest.hexdigest(), total


def inspect_pwa_archive(
    path: Path,
    *, max_entries: int = 4096,
    max_expanded_bytes: int = 512 * 1024**2,
    max_ratio: float = 200.0,
    max_depth: int = 16,
) -> dict[str, Any]:
    required = {"index.html", "manifest.webmanifest", BUILD_IDENTITY_NAME}
    names: set[str] = set()
    js_assets: list[str] = []
    css_assets: list[str] = []
    service_workers: list[str] = []
    compressed = expanded = 0
    with zipfile.ZipFile(path, "r") as archive:
        infos = archive.infolist()
        if not infos or len(infos) > max_entries:
            raise LiteReleaseContractError("release_archive_entry_limit")
        for info in infos:
            name, candidate = _archive_member_name(info.filename)
            if len(candidate.parts) > max_depth:
                raise LiteReleaseContractError("release_archive_nesting_limit")
            mode = (info.external_attr >> 16) & 0o170000
            if mode in {stat.S_IFLNK, stat.S_IFCHR, stat.S_IFBLK, stat.S_IFIFO, stat.S_IFSOCK}:
                raise LiteReleaseContractError("release_archive_special_file_rejected")
            lowered = {part.lower() for part in candidate.parts}
            if lowered & FORBIDDEN_ARCHIVE_PARTS or any(part.lower().endswith(".env") for part in candidate.parts):
                raise LiteReleaseContractError("release_archive_wrong_product_content")
            compressed += max(0, int(info.compress_size))
            expanded += max(0, int(info.file_size))
            if expanded > max_expanded_bytes:
                raise LiteReleaseContractError("release_archive_expanded_limit")
            if info.is_dir():
                continue
            names.add(name)
            if name.endswith(".js"):
                js_assets.append(name)
            elif name.endswith(".css"):
                css_assets.append(name)
            if candidate.name in {"sw.js", "registerSW.js"} or candidate.name.startswith("workbox-"):
                service_workers.append(name)
        if expanded / max(1, compressed) > max_ratio:
            raise LiteReleaseContractError("release_archive_ratio_limit")
        if not required.issubset(names):
            raise LiteReleaseContractError("release_archive_pwa_required_file_missing")
        index_text = archive.read("index.html").decode("utf-8", errors="replace")[:256 * 1024]
        manifest_payload = json.loads(archive.read("manifest.webmanifest").decode("utf-8"))
        build_identity = json.loads(archive.read(BUILD_IDENTITY_NAME).decode("utf-8"))
    if not isinstance(build_identity, dict) or build_identity.get("product") != PRODUCT:
        raise LiteReleaseContractError("release_archive_product_marker_missing")
    try:
        parse_lite_tag(build_identity.get("release_tag"))
    except LiteReleaseContractError as exc:
        raise LiteReleaseContractError("release_archive_build_identity_invalid") from exc
    marker = "pocket lab lite" in index_text.lower() or "pocket-lab-lite" in index_text.lower()
    manifest_name = str(manifest_payload.get("name") or "").lower() if isinstance(manifest_payload, dict) else ""
    if not marker and "pocket lab lite" not in manifest_name:
        raise LiteReleaseContractError("release_archive_product_marker_missing")
    if not js_assets or not css_assets:
        raise LiteReleaseContractError("release_archive_pwa_assets_missing")
    if not service_workers:
        raise LiteReleaseContractError("release_archive_service_worker_missing")
    return {
        "entry_count": len(names),
        "compressed_bytes": compressed,
        "expanded_bytes": expanded,
        "representative_js": sorted(js_assets)[:1],
        "representative_css": sorted(css_assets)[:1],
        "service_worker": sorted(service_workers)[:1],
        "pwa_identity": PRODUCT,
    }


def safe_extract_zip(
    path: Path,
    destination: Path,
    *,
    max_entries: int = 4096,
    max_expanded_bytes: int = 512 * 1024**2,
    max_ratio: float = 200.0,
    max_depth: int = 16,
) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    seen: set[str] = set()
    with zipfile.ZipFile(path, "r") as archive:
        infos = archive.infolist()
        if not infos or len(infos) > max_entries:
            raise LiteReleaseContractError("release_archive_entry_limit")
        compressed = sum(max(0, int(info.compress_size)) for info in infos)
        expanded = sum(max(0, int(info.file_size)) for info in infos)
        if expanded > max_expanded_bytes:
            raise LiteReleaseContractError("release_archive_expanded_limit")
        if expanded / max(1, compressed) > max_ratio:
            raise LiteReleaseContractError("release_archive_ratio_limit")
        for info in infos:
            name, candidate = _archive_member_name(info.filename)
            if name in seen:
                raise LiteReleaseContractError("release_archive_duplicate_path")
            seen.add(name)
            if len(candidate.parts) > max_depth:
                raise LiteReleaseContractError("release_archive_nesting_limit")
            lowered = {part.lower() for part in candidate.parts}
            if lowered & FORBIDDEN_ARCHIVE_PARTS or any(part.lower().endswith(".env") for part in candidate.parts):
                raise LiteReleaseContractError("release_archive_wrong_product_content")
            mode = (info.external_attr >> 16) & 0o170000
            if mode in {stat.S_IFLNK, stat.S_IFCHR, stat.S_IFBLK, stat.S_IFIFO, stat.S_IFSOCK}:
                raise LiteReleaseContractError("release_archive_special_file_rejected")
            target = (destination / candidate).resolve(strict=False)
            if root != target and root not in target.parents:
                raise LiteReleaseContractError("release_archive_path_traversal")
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            written = 0
            with archive.open(info, "r") as source, target.open("wb") as sink:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    written += len(chunk)
                    if written > int(info.file_size):
                        raise LiteReleaseContractError("release_archive_entry_size_mismatch")
                    sink.write(chunk)
                if written != int(info.file_size):
                    raise LiteReleaseContractError("release_archive_entry_size_mismatch")
                sink.flush()
                try:
                    import os
                    os.fsync(sink.fileno())
                except OSError:
                    pass
            target.chmod(0o644)


def canonical_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def newest_valid_release(releases: Iterable[Mapping[str, Any]], *, allow_prerelease: bool) -> Mapping[str, Any]:
    candidates: list[tuple[LiteTag, Mapping[str, Any]]] = []
    for release in releases:
        if bool(release.get("draft")) or (bool(release.get("prerelease")) and not allow_prerelease):
            continue
        try:
            parsed = parse_lite_tag(release.get("tag_name"))
        except LiteReleaseContractError:
            continue
        candidates.append((parsed, release))
    if not candidates:
        raise LiteReleaseContractError("release_lite_tag_not_found")
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]
