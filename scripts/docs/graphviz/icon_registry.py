#!/usr/bin/env python3
"""Validate and safely vendor repository-owned architecture icons.

This tool is development/CI-only. Production architecture generation consumes local SVGs and
never performs network access.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[3]
ICON_ROOT = ROOT / "architecture" / "icons"
REGISTRY_PATH = ROOT / "architecture" / "metadata" / "icon-sources.json"
LICENSES_PATH = ROOT / "architecture" / "metadata" / "icon-licenses.json"
ALLOWED_SCHEMA_REVISION = 2
VALID_ICON_CLASSES = {"brand", "semantic"}
FORBIDDEN_SVG_PATTERNS = (
    re.compile(r"<\s*script\b", re.I),
    re.compile(r"\bon[a-z]+\s*=", re.I),
    re.compile(r"(?:href|xlink:href)\s*=\s*[\"']\s*(?:https?:|//|data:|javascript:)", re.I),
    re.compile(r"url\(\s*[\"']?\s*(?:https?:|//|data:|javascript:)", re.I),
    re.compile(r"<\s*(?:foreignObject|iframe|object|embed|audio|video|canvas)\b", re.I),
    re.compile(r"@font-face|<\s*font\b", re.I),
    re.compile(r"<\s*image\b", re.I),
    re.compile(r"<!DOCTYPE|<!ENTITY", re.I),
    re.compile(r"<\?xml-stylesheet", re.I),
)


class IconRegistryError(ValueError):
    """Raised when icon metadata or an SVG asset is unsafe or inconsistent."""


@dataclass(frozen=True)
class IconRecord:
    id: str
    icon_class: str
    display_name: str
    source_type: str
    source_url: str
    download_url: str
    upstream_project: str
    version: str
    source_revision: str
    license: str
    license_url: str
    trademark_note: str
    attribution: str
    sha256: str
    expected_content_type: str
    maximum_size_bytes: int
    local_path: str
    fallback_icon: str
    allowed_redirect_hosts: tuple[str, ...]
    monochrome_suitable: bool
    dark_mode_suitable: bool
    light_mode_suitable: bool
    generated_svg: str | None = None

    @property
    def path(self) -> Path:
        return ROOT / self.local_path


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise IconRegistryError(f"Missing icon metadata: {path.relative_to(ROOT)}") from exc
    except json.JSONDecodeError as exc:
        raise IconRegistryError(f"Invalid JSON in {path.relative_to(ROOT)}: {exc}") from exc
    if not isinstance(data, dict):
        raise IconRegistryError(f"Expected an object in {path.relative_to(ROOT)}")
    return data


def _safe_icon_path(local_path: str) -> Path:
    if "\\" in local_path or Path(local_path).is_absolute() or ".." in Path(local_path).parts:
        raise IconRegistryError(f"Unsafe icon path: {local_path!r}")
    candidate = (ROOT / local_path).resolve(strict=False)
    icon_root = ICON_ROOT.resolve(strict=False)
    if candidate == icon_root or icon_root not in candidate.parents:
        raise IconRegistryError(f"Icon must live under architecture/icons: {local_path}")
    if candidate.suffix.lower() != ".svg":
        raise IconRegistryError(f"Icon target must use .svg: {local_path}")
    current = candidate
    while current != icon_root:
        if current.is_symlink():
            raise IconRegistryError(f"Icon target path may not contain symlinks: {local_path}")
        current = current.parent
    return candidate


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, IconRecord]:
    data = _read_json(path)
    if data.get("schema_revision") != ALLOWED_SCHEMA_REVISION:
        raise IconRegistryError(
            f"Unsupported icon registry schema revision: {data.get('schema_revision')!r}"
        )
    licenses = _read_json(LICENSES_PATH)
    if licenses.get("schema_revision") != ALLOWED_SCHEMA_REVISION:
        raise IconRegistryError("Icon license metadata schema revision does not match registry")
    known_licenses = set((licenses.get("licenses") or {}).keys())
    raw_icons = data.get("icons")
    if not isinstance(raw_icons, list) or not raw_icons:
        raise IconRegistryError("Icon registry must contain a non-empty icons list")
    records: dict[str, IconRecord] = {}
    registered_paths: set[str] = set()
    generated_names: set[str] = set()
    required = {
        "id", "icon_class", "display_name", "source_type", "source_url", "download_url",
        "upstream_project", "version", "source_revision", "license", "license_url",
        "trademark_note", "attribution", "sha256", "expected_content_type",
        "maximum_size_bytes", "local_path", "fallback_icon", "allowed_redirect_hosts",
        "monochrome_suitable", "dark_mode_suitable", "light_mode_suitable",
    }
    for index, raw in enumerate(raw_icons):
        if not isinstance(raw, dict):
            raise IconRegistryError(f"Icon record {index} is not an object")
        missing = sorted(required - raw.keys())
        if missing:
            raise IconRegistryError(f"Icon record {index} is missing: {', '.join(missing)}")
        icon_id = str(raw["id"])
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,63}", icon_id):
            raise IconRegistryError(f"Invalid icon id: {icon_id!r}")
        if icon_id in records:
            raise IconRegistryError(f"Duplicate icon id: {icon_id}")
        icon_class = str(raw["icon_class"])
        if icon_class not in VALID_ICON_CLASSES:
            raise IconRegistryError(f"Icon {icon_id} has invalid icon_class {icon_class!r}")
        for field in (
            "display_name", "source_url", "download_url", "upstream_project", "version",
            "source_revision", "license", "license_url", "trademark_note", "attribution",
        ):
            if not isinstance(raw.get(field), str) or not raw[field].strip():
                raise IconRegistryError(f"Icon {icon_id} has empty provenance field {field}")
        if raw["license"] not in known_licenses:
            raise IconRegistryError(f"Icon {icon_id} uses unknown license {raw['license']!r}")
        if not re.fullmatch(r"[0-9a-f]{64}", str(raw["sha256"])):
            raise IconRegistryError(f"Icon {icon_id} has an invalid SHA256")
        maximum_size = int(raw["maximum_size_bytes"])
        if maximum_size <= 0 or maximum_size > 1_048_576:
            raise IconRegistryError(f"Icon {icon_id} has an unsafe maximum size")
        local_path = str(raw["local_path"])
        safe_path = _safe_icon_path(local_path)
        if local_path in registered_paths:
            raise IconRegistryError(f"Duplicate icon local_path: {local_path}")
        registered_paths.add(local_path)
        if safe_path.name in generated_names:
            raise IconRegistryError(
                f"Duplicate generated icon filename {safe_path.name!r}; diagram copies are flat"
            )
        generated_names.add(safe_path.name)
        source_type = str(raw["source_type"])
        if source_type not in {"generated", "remote"}:
            raise IconRegistryError(f"Icon {icon_id} has unsupported source_type {source_type!r}")
        generated_svg = raw.get("generated_svg")
        if source_type == "generated" and not isinstance(generated_svg, str):
            raise IconRegistryError(f"Generated icon {icon_id} is missing generated_svg")
        allowed_raw = raw["allowed_redirect_hosts"]
        if not isinstance(allowed_raw, list) or any(not isinstance(item, str) for item in allowed_raw):
            raise IconRegistryError(f"Icon {icon_id} allowed_redirect_hosts must be strings")
        allowed_hosts = tuple(sorted({item.lower() for item in allowed_raw if item.strip()}))
        if source_type == "remote":
            parsed = urlparse(str(raw["download_url"]))
            if parsed.scheme != "https" or not parsed.hostname:
                raise IconRegistryError(f"Remote icon {icon_id} must use a pinned HTTPS URL")
            if parsed.hostname.lower() not in allowed_hosts:
                raise IconRegistryError(f"Remote icon {icon_id} download host is not allowlisted")
            if icon_class == "brand" and (
                not raw["upstream_project"].strip() or not raw["source_revision"].strip()
                or not raw["trademark_note"].strip()
            ):
                raise IconRegistryError(f"Brand icon {icon_id} lacks provenance/trademark metadata")
        suitability = tuple(raw[field] for field in (
            "monochrome_suitable", "dark_mode_suitable", "light_mode_suitable"
        ))
        if any(not isinstance(value, bool) for value in suitability):
            raise IconRegistryError(f"Icon {icon_id} theme suitability fields must be boolean")
        records[icon_id] = IconRecord(
            id=icon_id, icon_class=icon_class, display_name=str(raw["display_name"]),
            source_type=source_type, source_url=str(raw["source_url"]),
            download_url=str(raw["download_url"]), upstream_project=str(raw["upstream_project"]),
            version=str(raw["version"]), source_revision=str(raw["source_revision"]),
            license=str(raw["license"]), license_url=str(raw["license_url"]),
            trademark_note=str(raw["trademark_note"]), attribution=str(raw["attribution"]),
            sha256=str(raw["sha256"]), expected_content_type=str(raw["expected_content_type"]),
            maximum_size_bytes=maximum_size, local_path=local_path,
            fallback_icon=str(raw["fallback_icon"]), allowed_redirect_hosts=allowed_hosts,
            monochrome_suitable=bool(raw["monochrome_suitable"]),
            dark_mode_suitable=bool(raw["dark_mode_suitable"]),
            light_mode_suitable=bool(raw["light_mode_suitable"]),
            generated_svg=generated_svg if isinstance(generated_svg, str) else None,
        )
    license_ids = licenses.get("icon_ids")
    if not isinstance(license_ids, list) or sorted(license_ids) != sorted(records):
        raise IconRegistryError("icon-licenses.json icon_ids must exactly match the icon registry")
    for record in records.values():
        if record.fallback_icon not in records:
            raise IconRegistryError(
                f"Icon {record.id} references unknown fallback {record.fallback_icon}"
            )
    return records


def validate_svg_structure(payload: bytes, *, icon_id: str, maximum_size_bytes: int) -> str:
    if not payload:
        raise IconRegistryError(f"Icon {icon_id} is empty")
    if len(payload) > maximum_size_bytes:
        raise IconRegistryError(f"Icon {icon_id} exceeds {maximum_size_bytes} bytes")
    prefix = payload[:512].lstrip().lower()
    if prefix.startswith((b"<!doctype html", b"<html", b"{", b"[")):
        raise IconRegistryError(f"Icon {icon_id} is an HTML/JSON response, not SVG")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise IconRegistryError(f"Icon {icon_id} is not UTF-8 SVG") from exc
    if not re.search(r"<svg\b", text, re.I):
        raise IconRegistryError(f"Icon {icon_id} has no SVG root")
    for pattern in FORBIDDEN_SVG_PATTERNS:
        if pattern.search(text):
            raise IconRegistryError(
                f"Icon {icon_id} contains unsafe SVG content matching {pattern.pattern!r}"
            )
    if re.search(r"\b(?:href|xlink:href)\s*=", text, re.I):
        raise IconRegistryError(f"Icon {icon_id} contains an embedded reference")
    return text


def validate_svg_bytes(payload: bytes, record: IconRecord, *, verify_checksum: bool = True) -> None:
    validate_svg_structure(
        payload, icon_id=record.id, maximum_size_bytes=record.maximum_size_bytes
    )
    if verify_checksum and hashlib.sha256(payload).hexdigest() != record.sha256:
        raise IconRegistryError(f"Icon {record.id} checksum mismatch")


def validate_icon(record: IconRecord) -> None:
    try:
        if record.path.is_symlink():
            raise IconRegistryError(f"Icon {record.id} may not be a symlink")
        payload = record.path.read_bytes()
    except FileNotFoundError as exc:
        raise IconRegistryError(f"Missing icon {record.id}: {record.local_path}") from exc
    validate_svg_bytes(payload, record)


def _download_url(
    *, icon_id: str, url: str, destination: Path, maximum_size_bytes: int,
    allowed_hosts: Iterable[str], expected_content_type: str,
) -> None:
    parsed = urlparse(url)
    allowed = {item.lower() for item in allowed_hosts}
    if parsed.scheme != "https" or not parsed.hostname:
        raise IconRegistryError(f"Download URL for {icon_id} must use HTTPS")
    if parsed.hostname.lower() not in allowed:
        raise IconRegistryError(
            f"Download host {parsed.hostname!r} for {icon_id} is not explicitly allowlisted"
        )
    curl = os.environ.get("CURL", "curl")
    command = [
        curl, "--fail", "--silent", "--show-error", "--location", "--proto", "=https",
        "--tlsv1.2", "--retry", "3", "--retry-all-errors", "--retry-delay", "1",
        "--connect-timeout", "10", "--max-time", "45", "--max-filesize",
        str(maximum_size_bytes), "--header", "Accept: image/svg+xml", "--output",
        str(destination), "--write-out", "%{url_effective}\n%{content_type}\n%{size_download}\n", url,
    ]
    completed = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if completed.returncode != 0:
        raise IconRegistryError(
            f"Download failed for {icon_id}: {completed.stderr.strip() or 'curl failed'}"
        )
    lines = completed.stdout.strip().splitlines()
    if len(lines) < 3:
        raise IconRegistryError(f"Download metadata missing for {icon_id}")
    final_url, content_type, size_text = lines[-3], lines[-2], lines[-1]
    final_host = (urlparse(final_url).hostname or "").lower()
    if final_host not in allowed:
        raise IconRegistryError(f"Icon {icon_id} redirected to unexpected host {final_host!r}")
    normalized_type = content_type.split(";", 1)[0].strip().lower()
    if normalized_type != expected_content_type.lower():
        raise IconRegistryError(
            f"Icon {icon_id} content type {normalized_type!r} does not match "
            f"{expected_content_type!r}"
        )
    try:
        downloaded_size = int(float(size_text))
    except ValueError as exc:
        raise IconRegistryError(f"Icon {icon_id} download size is invalid") from exc
    if downloaded_size <= 0 or downloaded_size > maximum_size_bytes:
        raise IconRegistryError(f"Icon {icon_id} download size is unsafe: {downloaded_size}")


def _atomic_write(path: Path, payload: bytes) -> None:
    _safe_icon_path(path.relative_to(ROOT).as_posix())
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        temporary.write_bytes(payload)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _update_registered_checksum(icon_id: str, digest: str) -> None:
    data = _read_json(REGISTRY_PATH)
    matched = False
    for raw in data.get("icons", []):
        if raw.get("id") == icon_id:
            raw["sha256"] = digest
            matched = True
            break
    if not matched:
        raise IconRegistryError(f"Cannot update checksum for unknown icon {icon_id}")
    payload = (json.dumps(data, indent=2, sort_keys=True) + "\n").encode("utf-8")
    fd, name = tempfile.mkstemp(prefix=".icon-sources.", suffix=".json.tmp", dir=REGISTRY_PATH.parent)
    os.close(fd)
    temporary = Path(name)
    try:
        temporary.write_bytes(payload)
        os.replace(temporary, REGISTRY_PATH)
    finally:
        temporary.unlink(missing_ok=True)


def install_icon(
    record: IconRecord, *, url_override: str | None = None,
    allow_hosts: Iterable[str] = (), update_checksum: bool = False,
) -> IconRecord:
    record.path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{record.id}.", suffix=".svg.tmp", dir=record.path.parent
    )
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        if record.source_type == "generated" and not url_override:
            temporary.write_text(record.generated_svg or "", encoding="utf-8")
        else:
            url = url_override or record.download_url
            hosts = set(record.allowed_redirect_hosts)
            hosts.update(item.lower() for item in allow_hosts if item)
            _download_url(
                icon_id=record.id, url=url, destination=temporary,
                maximum_size_bytes=record.maximum_size_bytes, allowed_hosts=hosts,
                expected_content_type=record.expected_content_type,
            )
        payload = temporary.read_bytes()
        validate_svg_bytes(payload, record, verify_checksum=not update_checksum)
        digest = hashlib.sha256(payload).hexdigest()
        if update_checksum and digest != record.sha256:
            _update_registered_checksum(record.id, digest)
            record = replace(record, sha256=digest)
        _atomic_write(record.path, payload)
        return record
    finally:
        temporary.unlink(missing_ok=True)


def select_records(records: dict[str, IconRecord], icon_id: str | None) -> list[IconRecord]:
    if icon_id is None:
        return [records[key] for key in sorted(records)]
    resolved_id = icon_id
    if resolved_id not in records and f"brand-{icon_id}" in records:
        resolved_id = f"brand-{icon_id}"
    if resolved_id not in records and f"semantic-{icon_id}" in records:
        resolved_id = f"semantic-{icon_id}"
    if resolved_id not in records:
        raise IconRegistryError(f"Unknown icon id: {icon_id}")
    return [records[resolved_id]]


def check_records(records: Iterable[IconRecord]) -> list[str]:
    failures: list[str] = []
    for record in records:
        try:
            validate_icon(record)
            print(
                f"OK {record.id}: {record.icon_class}, checksum, provenance, license, "
                "theme suitability, and SVG safety verified"
            )
        except IconRegistryError as exc:
            failures.append(str(exc))
            print(f"FAIL {exc}")
    return failures


def run(
    mode: str, *, icon_id: str | None = None, url_override: str | None = None,
    allow_hosts: Iterable[str] = (), update_checksum: bool = False,
) -> int:
    records = load_registry()
    selected = select_records(records, icon_id)
    if url_override and len(selected) != 1:
        raise IconRegistryError("--url requires exactly one registered --icon")
    if mode == "check":
        if url_override or update_checksum:
            raise IconRegistryError("--check does not accept --url or --update-checksum")
        failures = check_records(selected)
        if failures:
            print("Run setup-architecture-icons.sh --install-missing or --icon <id> --repair")
            return 1
        print(f"PASS {len(selected)} architecture icons are ready")
        return 0
    if mode not in {"install-missing", "repair", "all"}:
        raise IconRegistryError(f"Unsupported mode: {mode}")
    for original in selected:
        needs_install = mode in {"repair", "all"} or bool(url_override)
        if not needs_install:
            try:
                validate_icon(original)
                print(f"OK {original.id}: already valid")
                continue
            except IconRegistryError:
                needs_install = True
        if needs_install:
            source = url_override or original.source_url
            print(f"Installing {original.id} from {source}")
            updated = install_icon(
                original, url_override=url_override, allow_hosts=allow_hosts,
                update_checksum=update_checksum,
            )
            validate_icon(updated)
            print(f"OK {updated.id}: installed atomically and verified")
    refreshed = load_registry()
    failures = check_records(select_records(refreshed, icon_id))
    if failures:
        return 1
    print(f"PASS {len(selected)} architecture icons are ready")
    return 0


def add_arbitrary_icon(
    *, icon_id: str, name: str, url: str, output: str, allow_hosts: Iterable[str],
    maximum_size_bytes: int,
) -> int:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,63}", icon_id):
        raise IconRegistryError(f"Invalid icon id: {icon_id!r}")
    if not name.strip():
        raise IconRegistryError("--name must not be empty")
    destination = _safe_icon_path(output)
    if destination.exists() and destination.is_symlink():
        raise IconRegistryError("--output may not replace a symlink")
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    allowed = {item.lower() for item in allow_hosts}
    if not allowed or host not in allowed:
        raise IconRegistryError(
            "--add requires --allow-host matching the HTTPS URL host; redirects are restricted to it"
        )
    fd, name_tmp = tempfile.mkstemp(prefix=f".{icon_id}.", suffix=".svg.tmp", dir=ICON_ROOT)
    os.close(fd)
    temporary = Path(name_tmp)
    try:
        _download_url(
            icon_id=icon_id, url=url, destination=temporary,
            maximum_size_bytes=maximum_size_bytes, allowed_hosts=allowed,
            expected_content_type="image/svg+xml",
        )
        payload = temporary.read_bytes()
        validate_svg_structure(
            payload, icon_id=icon_id, maximum_size_bytes=maximum_size_bytes
        )
        _atomic_write(destination, payload)
    finally:
        temporary.unlink(missing_ok=True)
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    print(f"PASS downloaded and validated {icon_id} -> {destination.relative_to(ROOT)}")
    print(f"SHA256 {digest}")
    print(
        "The asset is intentionally not auto-registered. Add reviewed license, trademark, "
        "upstream, immutable revision, fallback, and suitability metadata before generator use."
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Development/CI-only architecture icon vendor and validator. With no mode, "
            "all registered icons are refreshed from immutable sources."
        )
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true", help="Validate metadata and local assets only")
    group.add_argument("--install-missing", action="store_true", help="Install only missing/invalid assets")
    group.add_argument("--repair", action="store_true", help="Refresh selected/all assets")
    group.add_argument("--all", action="store_true", help="Refresh all registered assets (default)")
    group.add_argument("--add", action="store_true", help="Validate and vendor an arbitrary SVG without registering it")
    parser.add_argument("--icon", help="Registered icon id")
    parser.add_argument("--url", help="Explicit HTTPS source URL for --icon or --add")
    parser.add_argument("--id", dest="new_id", help="New arbitrary icon id for --add")
    parser.add_argument("--name", dest="new_name", help="New arbitrary icon display name for --add")
    parser.add_argument("--output", help="Repository-contained architecture/icons/**/*.svg target for --add")
    parser.add_argument(
        "--allow-host", action="append", default=[],
        help="Explicit allowed source/redirect host; may be repeated",
    )
    parser.add_argument(
        "--update-checksum", action="store_true",
        help="Explicitly accept a reviewed checksum change for one registered --icon",
    )
    parser.add_argument("--maximum-size-bytes", type=int, default=65536)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.add:
            missing = [name for name, value in (
                ("--id", args.new_id), ("--name", args.new_name),
                ("--url", args.url), ("--output", args.output),
            ) if not value]
            if missing:
                raise IconRegistryError(f"--add requires: {', '.join(missing)}")
            return add_arbitrary_icon(
                icon_id=args.new_id, name=args.new_name, url=args.url,
                output=args.output, allow_hosts=args.allow_host,
                maximum_size_bytes=args.maximum_size_bytes,
            )
        mode = (
            "check" if args.check else "install-missing" if args.install_missing
            else "repair" if args.repair else "all"
        )
        if args.update_checksum and not args.icon:
            raise IconRegistryError("--update-checksum requires one registered --icon")
        if args.url and not args.icon:
            raise IconRegistryError("Registered --url override requires --icon")
        return run(
            mode, icon_id=args.icon, url_override=args.url,
            allow_hosts=args.allow_host, update_checksum=args.update_checksum,
        )
    except IconRegistryError as exc:
        print(f"ERROR: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
