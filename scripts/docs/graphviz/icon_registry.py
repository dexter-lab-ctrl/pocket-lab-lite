#!/usr/bin/env python3
"""Validate and install repository-owned architecture icons without runtime side effects."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[3]
REGISTRY_PATH = ROOT / "architecture" / "metadata" / "icon-sources.json"
LICENSES_PATH = ROOT / "architecture" / "metadata" / "icon-licenses.json"
ALLOWED_SCHEMA_REVISION = 1
FORBIDDEN_SVG_PATTERNS = (
    re.compile(r"<\s*script\b", re.I),
    re.compile(r"\bon[a-z]+\s*=", re.I),
    re.compile(r"(?:href|xlink:href)\s*=\s*[\"']\s*(?:https?:|//|data:)", re.I),
    re.compile(r"url\(\s*[\"']?\s*(?:https?:|//|data:)", re.I),
    re.compile(r"<\s*(?:foreignObject|iframe|object|embed|audio|video|canvas)\b", re.I),
    re.compile(r"@font-face|<\s*font\b", re.I),
    re.compile(r"<\s*image\b", re.I),
    re.compile(r"<!DOCTYPE|<!ENTITY", re.I),
)


class IconRegistryError(ValueError):
    """Raised when icon metadata or an SVG asset is unsafe or inconsistent."""


@dataclass(frozen=True)
class IconRecord:
    id: str
    display_name: str
    source_type: str
    source_url: str
    download_url: str
    version: str
    license: str
    license_url: str
    attribution: str
    sha256: str
    expected_content_type: str
    maximum_size_bytes: int
    local_path: str
    fallback_icon: str
    allowed_redirect_hosts: tuple[str, ...]
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


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, IconRecord]:
    data = _read_json(path)
    if data.get("schema_revision") != ALLOWED_SCHEMA_REVISION:
        raise IconRegistryError(
            f"Unsupported icon registry schema revision: {data.get('schema_revision')!r}"
        )
    licenses = _read_json(LICENSES_PATH)
    known_licenses = set((licenses.get("licenses") or {}).keys())
    raw_icons = data.get("icons")
    if not isinstance(raw_icons, list) or not raw_icons:
        raise IconRegistryError("Icon registry must contain a non-empty icons list")
    records: dict[str, IconRecord] = {}
    required = {
        "id", "display_name", "source_type", "source_url", "download_url", "version",
        "license", "license_url", "attribution", "sha256", "expected_content_type",
        "maximum_size_bytes", "local_path", "fallback_icon", "allowed_redirect_hosts",
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
        if raw["license"] not in known_licenses:
            raise IconRegistryError(f"Icon {icon_id} uses unknown license {raw['license']!r}")
        if not re.fullmatch(r"[0-9a-f]{64}", str(raw["sha256"])):
            raise IconRegistryError(f"Icon {icon_id} has an invalid SHA256")
        maximum_size = int(raw["maximum_size_bytes"])
        if maximum_size <= 0 or maximum_size > 1_048_576:
            raise IconRegistryError(f"Icon {icon_id} has an unsafe maximum size")
        local_path = str(raw["local_path"])
        candidate = (ROOT / local_path).resolve()
        icon_root = (ROOT / "architecture" / "icons").resolve()
        if icon_root not in candidate.parents:
            raise IconRegistryError(f"Icon {icon_id} must live under architecture/icons")
        source_type = str(raw["source_type"])
        if source_type not in {"generated", "remote"}:
            raise IconRegistryError(f"Icon {icon_id} has unsupported source_type {source_type!r}")
        generated_svg = raw.get("generated_svg")
        if source_type == "generated" and not isinstance(generated_svg, str):
            raise IconRegistryError(f"Generated icon {icon_id} is missing generated_svg")
        allowed_hosts = tuple(sorted({str(item).lower() for item in raw["allowed_redirect_hosts"]}))
        if source_type == "remote":
            parsed = urlparse(str(raw["download_url"]))
            if parsed.scheme != "https" or not parsed.hostname:
                raise IconRegistryError(f"Remote icon {icon_id} must use a pinned HTTPS URL")
            if parsed.hostname.lower() not in allowed_hosts:
                raise IconRegistryError(f"Remote icon {icon_id} download host is not allowlisted")
        records[icon_id] = IconRecord(
            id=icon_id,
            display_name=str(raw["display_name"]),
            source_type=source_type,
            source_url=str(raw["source_url"]),
            download_url=str(raw["download_url"]),
            version=str(raw["version"]),
            license=str(raw["license"]),
            license_url=str(raw["license_url"]),
            attribution=str(raw["attribution"]),
            sha256=str(raw["sha256"]),
            expected_content_type=str(raw["expected_content_type"]),
            maximum_size_bytes=maximum_size,
            local_path=local_path,
            fallback_icon=str(raw["fallback_icon"]),
            allowed_redirect_hosts=allowed_hosts,
            generated_svg=generated_svg if isinstance(generated_svg, str) else None,
        )
    for record in records.values():
        if record.fallback_icon not in records:
            raise IconRegistryError(
                f"Icon {record.id} references unknown fallback {record.fallback_icon}"
            )
    return records


def validate_svg_bytes(payload: bytes, record: IconRecord) -> None:
    if not payload:
        raise IconRegistryError(f"Icon {record.id} is empty")
    if len(payload) > record.maximum_size_bytes:
        raise IconRegistryError(
            f"Icon {record.id} exceeds {record.maximum_size_bytes} bytes"
        )
    if hashlib.sha256(payload).hexdigest() != record.sha256:
        raise IconRegistryError(f"Icon {record.id} checksum mismatch")
    prefix = payload[:256].lstrip().lower()
    if prefix.startswith(b"<!doctype html") or prefix.startswith(b"<html"):
        raise IconRegistryError(f"Icon {record.id} is HTML, not SVG")
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise IconRegistryError(f"Icon {record.id} is not UTF-8 SVG") from exc
    if not re.search(r"<svg\b", text, re.I):
        raise IconRegistryError(f"Icon {record.id} has no SVG root")
    for pattern in FORBIDDEN_SVG_PATTERNS:
        if pattern.search(text):
            raise IconRegistryError(
                f"Icon {record.id} contains unsafe SVG content matching {pattern.pattern!r}"
            )
    if re.search(r"\b(?:href|xlink:href)\s*=", text, re.I):
        raise IconRegistryError(f"Icon {record.id} contains an embedded reference")


def validate_icon(record: IconRecord) -> None:
    try:
        payload = record.path.read_bytes()
    except FileNotFoundError as exc:
        raise IconRegistryError(f"Missing icon {record.id}: {record.local_path}") from exc
    validate_svg_bytes(payload, record)


def _download_remote(record: IconRecord, destination: Path) -> None:
    curl = os.environ.get("CURL", "curl")
    command = [
        curl, "--fail", "--silent", "--show-error", "--location",
        "--proto", "=https", "--tlsv1.2", "--retry", "3", "--retry-delay", "1",
        "--connect-timeout", "10", "--max-time", "45",
        "--max-filesize", str(record.maximum_size_bytes),
        "--header", "Accept: image/svg+xml",
        "--output", str(destination),
        "--write-out", "%{url_effective}\n%{content_type}\n",
        record.download_url,
    ]
    completed = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if completed.returncode != 0:
        raise IconRegistryError(
            f"Download failed for {record.id}: {completed.stderr.strip() or 'curl failed'}"
        )
    lines = completed.stdout.strip().splitlines()
    if len(lines) < 2:
        raise IconRegistryError(f"Download metadata missing for {record.id}")
    final_url, content_type = lines[-2], lines[-1].split(";", 1)[0].strip().lower()
    final_host = (urlparse(final_url).hostname or "").lower()
    if final_host not in record.allowed_redirect_hosts:
        raise IconRegistryError(
            f"Icon {record.id} redirected to unexpected host {final_host!r}"
        )
    if content_type != record.expected_content_type.lower():
        raise IconRegistryError(
            f"Icon {record.id} content type {content_type!r} does not match "
            f"{record.expected_content_type!r}"
        )


def install_icon(record: IconRecord) -> None:
    record.path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{record.id}.", suffix=".svg.tmp", dir=record.path.parent
    )
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        if record.source_type == "generated":
            temporary.write_text(record.generated_svg or "", encoding="utf-8")
        else:
            _download_remote(record, temporary)
        validate_svg_bytes(temporary.read_bytes(), record)
        temporary.chmod(0o644)
        os.replace(temporary, record.path)
    finally:
        temporary.unlink(missing_ok=True)


def select_records(
    records: dict[str, IconRecord], icon_id: str | None
) -> list[IconRecord]:
    if icon_id is None:
        return [records[key] for key in sorted(records)]
    if icon_id not in records:
        raise IconRegistryError(f"Unknown icon id: {icon_id}")
    return [records[icon_id]]


def check_records(records: Iterable[IconRecord]) -> list[str]:
    failures: list[str] = []
    for record in records:
        try:
            validate_icon(record)
            print(f"OK {record.id}: checksum, license, and SVG safety verified")
        except IconRegistryError as exc:
            failures.append(str(exc))
            print(f"FAIL {exc}")
    return failures


def run(mode: str, *, icon_id: str | None = None) -> int:
    records = load_registry()
    selected = select_records(records, icon_id)
    if mode == "check":
        failures = check_records(selected)
        if failures:
            print("Run scripts/dev/lite/setup-architecture-icons.sh --install-missing or --repair")
            return 1
        print(f"PASS {len(selected)} architecture icons are ready")
        return 0
    if mode not in {"install-missing", "repair", "all"}:
        raise IconRegistryError(f"Unsupported mode: {mode}")
    for record in selected:
        needs_install = mode in {"repair", "all"}
        if not needs_install:
            try:
                validate_icon(record)
                print(f"OK {record.id}: already valid")
                continue
            except IconRegistryError:
                needs_install = True
        if needs_install:
            print(f"Installing {record.id} from {record.source_url}")
            install_icon(record)
            validate_icon(record)
            print(f"OK {record.id}: installed and verified")
    failures = check_records(selected)
    if failures:
        return 1
    print(f"PASS {len(selected)} architecture icons are ready")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true")
    group.add_argument("--install-missing", action="store_true")
    group.add_argument("--repair", action="store_true")
    group.add_argument("--all", action="store_true")
    parser.add_argument("--icon")
    args = parser.parse_args()
    mode = (
        "check" if args.check else "install-missing" if args.install_missing
        else "repair" if args.repair else "all"
    )
    try:
        return run(mode, icon_id=args.icon)
    except IconRegistryError as exc:
        print(f"ERROR: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
