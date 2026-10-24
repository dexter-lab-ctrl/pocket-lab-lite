#!/usr/bin/env python3
"""Offline, opt-in README publication checks; not live runtime qualification."""
from __future__ import annotations
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[2]
HEADINGS = [
    "A look inside Pocket Lab Lite", "Why Pocket Lab Lite?", "Explore the features",
    "How it works", "Get started", "Platforms and compatibility",
    "Designed for private control", "Documentation", "Releases and support",
    "Contributing and license",
]
NAV_PATHS = [
    "getting-started/android-termux.md", "generated/production/devices.md",
    "generated/production/apps.md", "generated/production/security.md",
    "generated/production/recovery.md",
]
MD_LINK = re.compile(r"!?\[[^\]\n]*\]\(([^)\s]+)")
MD_IMAGE = re.compile(r"!\[([^\]\n]*)\]\(([^)\s]+)")
HTML_URL = re.compile(r"\b(?:src|srcset|href)\s*=\s*['\"]([^'\"]+)['\"]", re.I)
HTML_IMG = re.compile(r"<img\s+[^>]*>", re.I | re.S)
SECRET = re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----|gh[pousr]_[a-zA-Z0-9]{20,}")
BAD_CLAIMS = ("completely secure", "zero risk", "100% secure", "install any application", "supports every device")


def git_blob(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def local_path(root: Path, value: str) -> Path | None:
    if value.startswith(("https://", "http://", "mailto:", "#", "data:")):
        return None
    path = unquote(urlsplit(value).path)
    if not path:
        return None
    if path.startswith("/") or "\\" in path:
        raise ValueError("unsafe README path: " + value)
    resolved = (root / path).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError("README path escapes repository: " + value)
    return resolved


def check_svg(path: Path) -> list[str]:
    errors = []
    value = path.read_text(encoding="utf-8")
    if re.search(r"<(?:script|foreignObject|iframe|image)\b|@import|url\(\s*['\"]?\s*(?:https?:|data:)", value, re.I):
        errors.append("unsafe SVG element or dependency: " + str(path))
    try:
        tree = ElementTree.fromstring(value)
        if "viewBox" not in tree.attrib or not any(n.tag.endswith("title") for n in tree.iter()):
            errors.append("SVG lacks viewBox/title: " + str(path))
        for node in tree.iter():
            for raw_attr, attr_value in node.attrib.items():
                attr = raw_attr.rsplit("}", 1)[-1].lower()
                if attr.startswith("on") or attr == "href":
                    errors.append("unsafe SVG attribute: " + str(path))
                if attr not in {"xmlns"} and re.search(r"javascript:|https?://|data:", attr_value, re.I):
                    errors.append("external SVG URL: " + str(path))
    except ElementTree.ParseError as exc:
        errors.append("malformed SVG " + str(path) + ": " + str(exc))
    return errors


def run_checks(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    readme = (root / "README.md").read_text(encoding="utf-8")
    outside_code = re.sub(r"(?ms)^```.*?^```[ \t]*$", "", readme)
    headings = re.findall(r"(?m)^##\s+(.+)$", outside_code)
    if headings != HEADINGS:
        errors.append("README sections are missing or out of order")
    if "<picture>" not in outside_code or 'media="(max-width: 640px)"' not in outside_code:
        errors.append("mobile-responsive hero source is missing")
    if "mocked backend" not in readme or "Illustrative workspace overview" not in readme:
        errors.append("mock/illustration provenance disclosure absent")
    if SECRET.search(readme) or any(bad in readme.lower() for bad in BAD_CLAIMS):
        errors.append("README contains secret-like text or unsupported guarantee")
    if "releases/latest" not in readme or "checksums.txt" not in readme:
        errors.append("release guidance missing")
    urls = set(MD_LINK.findall(outside_code)) | set(HTML_URL.findall(outside_code))
    for url in urls:
        try:
            file = local_path(root, url)
            if file is not None and not file.is_file():
                errors.append("broken README local reference: " + url)
        except ValueError as exc:
            errors.append(str(exc))
    image_sources: set[str] = set()
    for alt, src in MD_IMAGE.findall(outside_code):
        image_sources.add(src)
        if len(alt.strip()) < 12:
            errors.append("Markdown image needs descriptive alt text: " + src)
    for tag in HTML_IMG.findall(outside_code):
        src = re.search(r"\bsrc=['\"]([^'\"]+)['\"]", tag, re.I)
        alt = re.search(r"\balt=['\"]([^'\"]+)['\"]", tag, re.I)
        if src is None or alt is None or len(alt.group(1).strip()) < 12:
            errors.append("HTML image needs src and descriptive alt")
        elif src:
            image_sources.add(src.group(1))
    for src in image_sources:
        file = local_path(root, src)
        if file is None:
            errors.append("external README image dependency: " + src)
        elif file.is_file():
            if file.suffix.lower() not in {".png", ".webp", ".svg"}:
                errors.append("invalid README image format: " + src)
            if file.stat().st_size > (150000 if file.suffix == ".svg" else 1500000):
                errors.append("oversized README image: " + src)
    for src in urls:
        file = local_path(root, src)
        if file is not None and file.is_file() and file.suffix == ".svg":
            errors.extend(check_svg(file))
    claims = json.loads((root / "contracts/metadata/readme-claims.json").read_text())
    if claims.get("schema_version") != 1 or not claims.get("documentation_authority"):
        errors.append("invalid README claims contract")
    ids = set()
    for claim in claims.get("claims", []):
        cid = claim.get("id", "")
        if cid in ids or not re.fullmatch("[a-z][a-z0-9_.-]+", cid):
            errors.append("duplicate/invalid README claim ID: " + cid)
        ids.add(cid)
        if claim.get("heading") not in readme:
            errors.append("README claim heading missing: " + cid)
        if not claim.get("scope") or not claim.get("limitation") or not claim.get("sources"):
            errors.append("claim provenance/limitation missing: " + cid)
        for source in claim.get("sources", []):
            if not (root / source).is_file():
                errors.append("claim authority source missing: " + source)
    nav = (root / "mkdocs.yml").read_text()
    for path in NAV_PATHS:
        if path not in nav:
            errors.append("canonical MkDocs navigation path missing: " + path)
    media = json.loads((root / "contracts/metadata/readme-media.json").read_text())
    images = set()
    for capture in media["captures"]:
        path = capture["path"]
        if path in images:
            errors.append("duplicate screenshot: " + path)
        images.add(path)
        if path not in readme or capture.get("environment") != "mocked":
            errors.append("unreferenced or unlabeled mocked screenshot: " + path)
        for filename, sha_field in ((path, "sha"), (capture["spec"], "spec_sha")):
            file = root / filename
            if not file.is_file():
                errors.append("screenshot or scenario source missing: " + filename)
            elif git_blob(file) != capture.get(sha_field):
                errors.append("screenshot/source changed; manual review required: " + filename)
    if {s for s in image_sources if s.endswith(".png")} != images:
        errors.append("screenshot manifest does not cover precisely the README PNGs")
    return errors


if __name__ == "__main__":
    failures = run_checks()
    if failures:
        for message in failures:
            print("README: " + message, file=sys.stderr)
        raise SystemExit(1)
    print("README static source gate: OK (not a runtime or browser qualification)")
