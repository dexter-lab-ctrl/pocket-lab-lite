#!/usr/bin/env python3
"""Generate deterministic, data-free SQLite documentation through SchemaSpy."""
from __future__ import annotations

import argparse
import filecmp
import hashlib
import html
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Iterable
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = ROOT / "docs" / "generated" / "schemaspy"
SETUP = ROOT / "scripts" / "dev" / "lite" / "setup-documentation-tools.sh"
PLATFORM_GENERATOR = ROOT / "scripts" / "docs" / "lite" / "generate_platform_catalogs.py"
MIGRATIONS = ROOT / "pocket-lab-final-structure" / "runtime" / "api_fastapi" / "db" / "schema"
TEXT_SUFFIXES = {".html", ".htm", ".css", ".js", ".json", ".xml", ".txt", ".csv", ".dot", ".svg", ".md"}

# Only generated semantic documents are safety-scanned. SchemaSpy's bundled
# CSS/JavaScript/font assets are pinned third-party application resources and
# contain normal identifiers such as "token" and "password" that are not
# Pocket Lab runtime values.
SAFETY_TEXT_SUFFIXES = {
    ".html",
    ".htm",
    ".json",
    ".xml",
    ".txt",
    ".csv",
    ".dot",
    ".svg",
    ".md",
}
VENDORED_PREFIXES = ("bower/", "fonts/")

# Match concrete machine-specific roots rather than generic URL/CSS fragments.
ABSOLUTE_PATH = re.compile(
    r"(?<![A-Za-z0-9])(?:file:(?://)?)?(?:"
    r"/data/data/[^/\s\"'<>]+/|"
    r"/home/[^/\s\"'<>]+/|"
    r"/mnt/[A-Za-z]/|"
    r"[A-Za-z]:[\\/](?:Users|home)[\\/]"
    r")"
)

# Detect only high-confidence secret material. Generic JavaScript object keys
# such as token: function (...) are not secret values.
SECRET_VALUE = re.compile(
    r"(?:Bearer\s+[A-Za-z0-9._~+/=-]{8,}|"
    r"-----BEGIN [^-]+PRIVATE KEY-----|"
    r"nats://[^\s/@:]+:[^\s/@]+@|"
    r"tskey-[A-Za-z0-9_-]+)",
    re.I,
)


def load_build_empty_database():
    spec = importlib.util.spec_from_file_location("pocketlab_docs_platform", PLATFORM_GENERATOR)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load the canonical SQLite migration generator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build_empty_database


def cache_root() -> Path:
    explicit = os.environ.get("POCKETLAB_DOCS_TOOLS_CACHE", "").strip()
    if explicit:
        return Path(explicit).expanduser()
    xdg = os.environ.get("XDG_CACHE_HOME", "").strip()
    return (Path(xdg).expanduser() if xdg else Path.home() / ".cache") / "pocket-lab-lite" / "docs-tools"


def tool_paths() -> tuple[Path, Path]:
    root = cache_root()
    schemaspy = Path(os.environ.get("POCKETLAB_SCHEMASPY_JAR", root / "schemaspy-6.2.4-app.jar")).expanduser()
    sqlite_jdbc = Path(os.environ.get("POCKETLAB_SQLITE_JDBC_JAR", root / "sqlite-jdbc-3.46.1.0.jar")).expanduser()
    return schemaspy, sqlite_jdbc


def require_tools() -> tuple[str, Path, Path]:
    java = shutil.which("java")
    schemaspy, sqlite_jdbc = tool_paths()
    missing = []
    if not java:
        missing.append("Java 17+")
    if not schemaspy.is_file():
        missing.append(str(schemaspy))
    if not sqlite_jdbc.is_file():
        missing.append(str(sqlite_jdbc))
    if missing:
        raise RuntimeError(
            "SchemaSpy documentation tools are missing: " + ", ".join(missing) +
            f". Run: bash {SETUP.relative_to(ROOT)} --install-missing"
        )
    return java, schemaspy, sqlite_jdbc


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_text(text: str, replacements: dict[str, str]) -> str:
    result = text.replace("\r\n", "\n")
    for before, after in sorted(
        replacements.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        if not before:
            continue

        normalized = before.replace("\\", "/")
        variants = {
            before,
            normalized,
            normalized.replace("/", r"\/"),
            quote(normalized, safe=""),
            quote(normalized, safe="/"),
            normalized.replace("/", "&#47;"),
            normalized.replace("/", "&#x2F;"),
        }

        for variant in sorted(variants, key=len, reverse=True):
            result = result.replace(variant, after)
    result = re.sub(r"(?i)(generated|created|updated)(?:\s+on|\s+at)?\s*[:=-]?\s*\d{4}-\d{2}-\d{2}[T ][0-9:.+Z-]+", r"\1 from repository migrations", result)
    result = re.sub(r"(?i)SchemaSpy\s+Analysis\s+of\s+.*?\s+Generated\s+at\s+.*?(?=<)", "SchemaSpy analysis generated from repository migrations", result)
    result = re.sub(r"[ \t]+$", "", result, flags=re.M)
    # SchemaSpy HTML generated-on timestamp normalization.
    # Example: Generated on Sun Aug 02 11:10 UTC 2026
    result = re.sub(
        r"(?i)\bGenerated\s+on\s+"
        r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+"
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+"
        r"\d{1,2}\s+"
        r"\d{1,2}:\d{2}(?::\d{2})?\s+"
        r"[A-Z]{2,6}\s+"
        r"\d{4}\b",
        "Generated from repository migrations",
        result,
    )

    # SchemaSpy properties timestamp normalization.
    # info-html.txt contains a bare date=<timestamp> property that does not
    # include words such as generated/created/updated.
    result = re.sub(
        r"(?m)^date\s*=\s*"
        r"\d{4}-\d{2}-\d{2}\s+"
        r"\d{2}:\d{2}:\d{2}"
        r"(?:\.\d+)?"
        r"(?:Z|[+-]\d{4}|[+-]\d{2}:\d{2})"
        r"\s*$",
        "date=repository-schema",
        result,
    )

    # SchemaSpy deterministic runtime normalization.
    # These values describe the documentation-generation run rather than the
    # repository schema and must not cause committed documentation drift.
    result = re.sub(
        r"(?i)\b(?:generated|created|updated)"
        r"(?:\s+(?:on|at|by))?\s*[:=-]?\s*"
        r"\d{4}-\d{2}-\d{2}"
        r"(?:[T ][0-9]{1,2}:[0-9]{2}:[0-9]{2}"
        r"(?:\.[0-9]+)?(?:Z|[+-][0-9:]+)?)?",
        "generated from repository migrations",
        result,
    )
    result = re.sub(
        r"(?i)\b(?:generated|created|updated)"
        r"(?:\s+(?:on|at|by))?\s*[:=-]?\s*"
        r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun),?\s+"
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
        r"\s+\d{1,2},?\s+\d{4}"
        r"(?:\s+[0-9]{1,2}:[0-9]{2}:[0-9]{2}"
        r"(?:\s+[A-Z]{2,6})?)?",
        "generated from repository migrations",
        result,
    )
    result = re.sub(
        r"(?i)\b(?:generated|created|updated)"
        r"(?:\s+(?:on|at|by))?\s*[:=-]?\s*"
        r"\d{1,2}\s+"
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
        r"\s+\d{4}"
        r"(?:\s+[0-9]{1,2}:[0-9]{2}:[0-9]{2}"
        r"(?:\s+[A-Z]{2,6})?)?",
        "generated from repository migrations",
        result,
    )
    result = re.sub(
        r"(?i)\b(?:elapsed|duration|execution time|processing time|"
        r"generation time|analysis time|total time)"
        r"\s*[:=-]?\s*"
        r"\d+(?:\.\d+)?\s*"
        r"(?:milliseconds?|msecs?|ms|seconds?|secs?|minutes?|mins?)",
        "generation duration normalized",
        result,
    )
    result = re.sub(
        r"(?i)\b(?:completed|processed|generated|written|wrote)"
        r"([^<\n]{0,120}?)"
        r"\bin\s+\d+(?:\.\d+)?\s*"
        r"(?:milliseconds?|msecs?|ms|seconds?|secs?|minutes?|mins?)",
        lambda match: (
            match.group(0).split(" in ", 1)[0]
            + " in normalized duration"
        ),
        result,
    )
    result = re.sub(
        r"(?i)(SchemaSpy(?:\s+Analysis)?(?:\s+of)?[^<\n]{0,160}?)"
        r"\b(?:generated|created)\s+(?:on|at)\s+[^<\n]+",
        r"\1 generated from repository migrations",
        result,
    )
    return result.rstrip() + "\n"


def normalize_tree(path: Path, replacements: dict[str, str]) -> None:
    for file in sorted(p for p in path.rglob("*") if p.is_file()):
        if file.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            text = file.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        file.write_text(normalize_text(text, replacements), encoding="utf-8")



# SchemaSpy deterministic ordering normalization.
#
# SQLite metadata is logically unordered. SchemaSpy may enumerate tables and
# columns in a different order between identical runs, especially when its
# internal metadata work is parallelized. Canonicalize presentation-only
# ordering before hashes and drift checks are calculated.
def _find_json_array_end(text: str, start: int) -> int:
    depth = 0
    in_string = False
    escaped = False

    for index in range(start, len(text)):
        char = text[index]

        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return index

    raise RuntimeError("Unable to locate the end of SchemaSpy columns array")


def _plain_schema_name(value: object) -> str:
    text = str(value or "")
    text = text.replace(r"<\/i>", "")
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", text).strip().casefold()


def canonicalize_columns_html(path: Path) -> None:
    if not path.is_file():
        return

    text = path.read_text(encoding="utf-8")
    table_marker = '"tableName"'
    marker_index = text.find(table_marker)

    if marker_index < 0:
        raise RuntimeError(
            "SchemaSpy columns.html does not contain tableName metadata"
        )

    array_start = text.rfind("[", 0, marker_index)
    if array_start < 0:
        raise RuntimeError(
            "Unable to locate SchemaSpy columns metadata array"
        )

    array_end = _find_json_array_end(text, array_start)
    raw_array = text[array_start : array_end + 1]

    try:
        columns = json.loads(raw_array)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Unable to parse SchemaSpy columns metadata: {exc}"
        ) from exc

    if not isinstance(columns, list):
        raise RuntimeError("SchemaSpy columns metadata is not a list")

    if not all(isinstance(item, dict) for item in columns):
        raise RuntimeError(
            "SchemaSpy columns metadata contains an unexpected value"
        )

    columns.sort(
        key=lambda item: (
            str(item.get("tableName", "")).casefold(),
            _plain_schema_name(item.get("name", "")),
            str(item.get("type", "")).casefold(),
            str(item.get("keyClass", "")).casefold(),
            str(item.get("defaultValue", "")).casefold(),
            str(item.get("nullable", "")).casefold(),
        )
    )

    canonical = json.dumps(
        columns,
        ensure_ascii=False,
        indent=4,
    )

    path.write_text(
        text[:array_start] + canonical + text[array_end + 1 :],
        encoding="utf-8",
    )


def _table_row_sort_key(row: str) -> tuple[str, str]:
    link_match = re.search(
        r'href=["\']tables/([^"\']+)["\']',
        row,
        flags=re.I,
    )

    if link_match:
        return ("0", link_match.group(1).casefold())

    name_match = re.search(
        r"<td[^>]*>\s*(?:<a[^>]*>)?([^<]+)",
        row,
        flags=re.I,
    )

    return (
        "1",
        (name_match.group(1) if name_match else row).strip().casefold(),
    )




def canonicalize_index_html(path: Path) -> None:
    """Canonicalize SchemaSpy table-list rows by table name."""

    if not path.is_file():
        return

    text = path.read_text(encoding="utf-8")

    # Match only SchemaSpy's main table-list rows. Other links in index.html,
    # including navigation and relationship links, retain their original
    # semantic placement.
    row_pattern = re.compile(
        r'(?P<row>'
        r'^[ \t]*<tr\b'
        r'(?=[^>]*\bclass=["\'][^"\']*\btbl\b[^"\']*["\'])'
        r'[^>]*>'
        r'.*?'
        r'</tr>[ \t]*(?:\n|$)'
        r')',
        flags=re.I | re.S | re.M,
    )

    table_pattern = re.compile(
        r'href=["\']tables/(?P<table>[^"\']+)\.html["\']',
        flags=re.I,
    )

    matches = []

    for row_match in row_pattern.finditer(text):
        row = row_match.group("row")
        table_match = table_pattern.search(row)

        if table_match:
            matches.append(
                (
                    row_match,
                    table_match.group("table").casefold(),
                    row,
                )
            )

    if len(matches) < 2:
        raise RuntimeError(
            "SchemaSpy index.html did not expose the expected table-list rows"
        )

    ordered_rows = [
        item[2]
        for item in sorted(
            matches,
            key=lambda item: (
                item[1],
                re.sub(r"\s+", " ", item[2]).strip().casefold(),
            ),
        )
    ]

    pieces = []
    cursor = 0

    for (row_match, _, _), replacement_row in zip(
        matches,
        ordered_rows,
    ):
        pieces.append(text[cursor:row_match.start()])
        pieces.append(replacement_row)
        cursor = row_match.end()

    pieces.append(text[cursor:])

    normalized = "".join(pieces)

    path.write_text(
        normalized.rstrip() + "\n",
        encoding="utf-8",
    )

def canonicalize_relationship_dot(path: Path) -> None:
    """Canonicalize SchemaSpy DOT node and simple edge ordering."""

    if not path.is_file():
        return

    text = path.read_text(encoding="utf-8")

    # SchemaSpy emits each table as a multi-line top-level DOT node block:
    #
    #   "table_name" [
    #      ...
    #   ];
    #
    # SQLite metadata enumeration can change the order of these blocks between
    # otherwise identical runs.
    node_pattern = re.compile(
        r'(?ms)^  "(?P<name>[^"]+)" \[\n'
        r'.*?'
        r'^  \];(?:\n|$)'
    )

    node_matches = list(node_pattern.finditer(text))

    if len(node_matches) > 1:
        ordered_blocks = sorted(
            (match.group(0) for match in node_matches),
            key=lambda block: (
                re.match(
                    r'^  "([^"]+)"',
                    block,
                ).group(1).casefold()
            ),
        )

        pieces = []
        cursor = 0

        for match, replacement in zip(
            node_matches,
            ordered_blocks,
        ):
            pieces.append(text[cursor : match.start()])
            pieces.append(replacement)
            cursor = match.end()

        pieces.append(text[cursor:])
        text = "".join(pieces)

    # Keep simple one-line edge statements deterministic as well.
    lines = text.splitlines()
    edge_indexes = [
        index
        for index, line in enumerate(lines)
        if re.match(
            r'^\s*"[^"]+"(?::[^ ]+)?\s*(?:->|--)\s*"[^"]+"',
            line,
        )
    ]

    if len(edge_indexes) > 1:
        ordered_edges = sorted(
            (lines[index] for index in edge_indexes),
            key=lambda line: re.sub(
                r"\s+",
                " ",
                line,
            ).strip().casefold(),
        )

        for index, replacement in zip(
            edge_indexes,
            ordered_edges,
        ):
            lines[index] = replacement

    path.write_text(
        "\n".join(lines).rstrip() + "\n",
        encoding="utf-8",
    )

def _html_row_sort_key(row: str) -> tuple[tuple[str, ...], str, str]:
    hrefs = tuple(
        value.casefold()
        for value in re.findall(
            r'href=["\']([^"\']+)["\']',
            row,
            flags=re.I,
        )
    )

    visible = re.sub(
        r"<script\b[^>]*>.*?</script>",
        " ",
        row,
        flags=re.I | re.S,
    )
    visible = re.sub(
        r"<style\b[^>]*>.*?</style>",
        " ",
        visible,
        flags=re.I | re.S,
    )
    visible = re.sub(r"<[^>]+>", " ", visible)
    visible = html.unescape(visible)
    visible = re.sub(r"\s+", " ", visible).strip().casefold()

    structural = re.sub(r"\s+", " ", row).strip().casefold()

    return hrefs, visible, structural



def canonicalize_relationship_html(path: Path) -> None:
    """Canonicalize SchemaSpy relationship image maps."""

    if not path.is_file():
        return

    text = path.read_text(encoding="utf-8")

    map_pattern = re.compile(
        r"(?P<open><map\b[^>]*>)"
        r"(?P<body>.*?)"
        r"(?P<close></map>)",
        flags=re.I | re.S,
    )

    area_pattern = re.compile(
        r"^[ \t]*<area\b[^>]*>[ \t]*$",
        flags=re.I | re.M,
    )

    def area_key(area: str) -> tuple[str, str, str]:
        href_match = re.search(
            r'\bhref=["\']([^"\']+)["\']',
            area,
            flags=re.I,
        )
        title_match = re.search(
            r'\btitle=["\']([^"\']*)["\']',
            area,
            flags=re.I,
        )

        return (
            href_match.group(1).casefold()
            if href_match
            else "",
            title_match.group(1).casefold()
            if title_match
            else "",
            re.sub(r"\s+", " ", area).strip().casefold(),
        )

    def normalize_map(match: re.Match[str]) -> str:
        body = match.group("body")
        areas = list(area_pattern.finditer(body))

        if len(areas) < 2:
            return match.group(0)

        ordered = sorted(
            (area.group(0) for area in areas),
            key=area_key,
        )

        # SchemaSpy's nodeN value is presentation-only and depends on metadata
        # enumeration order. Assign stable IDs after sorting by table href.
        normalized_areas = []

        for index, area in enumerate(ordered, start=1):
            normalized = re.sub(
                r'\bid=["\']node\d+["\']',
                f'id="node{index}"',
                area,
                count=1,
                flags=re.I,
            )
            normalized_areas.append(normalized)

        pieces = []
        cursor = 0

        for area_match, replacement in zip(
            areas,
            normalized_areas,
        ):
            pieces.append(body[cursor : area_match.start()])
            pieces.append(replacement)
            cursor = area_match.end()

        pieces.append(body[cursor:])

        return (
            match.group("open")
            + "".join(pieces)
            + match.group("close")
        )

    normalized = map_pattern.sub(normalize_map, text)

    path.write_text(
        normalized.rstrip() + "\n",
        encoding="utf-8",
    )


def canonicalize_schemaspy_output(path: Path) -> None:
    canonicalize_columns_html(path / "columns.html")

    # index.html owns table-list ordering. Do not pass it through the generic
    # relationship-map canonicalizer afterward.
    canonicalize_index_html(path / "index.html")

    canonicalize_relationship_html(
        path / "relationships.html"
    )

    summary_directory = path / "diagrams" / "summary"

    if summary_directory.is_dir():
        for dot_file in sorted(
            summary_directory.glob("relationships.*.dot")
        ):
            canonicalize_relationship_dot(dot_file)

def validate_tree(path: Path) -> None:
    errors = []

    for file in sorted(p for p in path.rglob("*") if p.is_file()):
        relative = file.relative_to(path).as_posix()

        # SchemaSpy ships these pinned frontend resources. They are not
        # generated Pocket Lab content and commonly contain benign words such
        # as token/password or SVG path syntax that resembles filesystem paths.
        if relative.startswith(VENDORED_PREFIXES):
            continue

        if file.suffix.lower() not in SAFETY_TEXT_SUFFIXES:
            continue

        try:
            content = file.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        if ABSOLUTE_PATH.search(content):
            errors.append(f"absolute machine path in {relative}")

        if SECRET_VALUE.search(content):
            errors.append(f"secret-like value in {relative}")

    if errors:
        raise RuntimeError(
            "Unsafe SchemaSpy output:\n"
            + "\n".join(f" - {item}" for item in errors)
        )


def directory_manifest(path: Path) -> list[dict[str, object]]:
    result = []
    for file in sorted(p for p in path.rglob("*") if p.is_file()):
        result.append({
            "path": file.relative_to(path).as_posix(),
            "sha256": sha256(file),
            "size_bytes": file.stat().st_size,
        })
    return result


def generate_to(destination: Path) -> None:
    java, schemaspy, sqlite_jdbc = require_tools()
    build_empty_database = load_build_empty_database()
    with tempfile.TemporaryDirectory(prefix="pocketlab-schemaspy-") as temporary:
        temp_root = Path(temporary)
        database = temp_root / "pocketlab-lite-schema.sqlite3"
        raw_output = temp_root / "schemaspy-output"
        raw_output.mkdir()
        migrations = build_empty_database(database)
        command = [
            java,
            "-Dfile.encoding=UTF-8",
            "-jar", str(schemaspy),
            "-t", "sqlite-xerial",
            "-dp", str(sqlite_jdbc),
            "-db", str(database),
            "-cat", "%",
            "-s", "main",
            "-u", "pocketlab-docs",
            "-o", str(raw_output),
            "-norows",
            "-hq",
        ]
        completed = subprocess.run(
            command,
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
            env={**os.environ, "LC_ALL": "C", "LANG": "C", "TZ": "UTC"},
        )
        if completed.returncode != 0:
            sanitized = normalize_text(completed.stdout, {
                str(temp_root): "<temporary-directory>",
                str(ROOT): "<repository-root>",
                str(Path.home()): "<home>",
            })
            raise RuntimeError(f"SchemaSpy failed with exit code {completed.returncode}:\n{sanitized[-4000:]}")
        if not (raw_output / "index.html").is_file():
            raise RuntimeError("SchemaSpy did not produce index.html")
        normalize_tree(raw_output, {
            str(temp_root): "<temporary-directory>",
            str(database): "<temporary-schema.sqlite3>",
            str(ROOT): "<repository-root>",
            str(Path.home()): "<home>",
            str(schemaspy): "<schemaspy-app.jar>",
            str(sqlite_jdbc): "<sqlite-jdbc.jar>",
        })

        canonicalize_schemaspy_output(raw_output)

        metadata = {
            "schema_revision": 1,
            "generator": "scripts/docs/sqlite/generate_schemaspy.py",
            "database": "temporary data-free SQLite generated from repository migrations",
            "row_count_enforced": 0,
            "migration_count": len(migrations),
            "migrations": [migration.relative_to(ROOT).as_posix() for migration in migrations],
            "migration_fingerprints": {migration.relative_to(ROOT).as_posix(): sha256(migration) for migration in migrations},
            "schemaspy_jar_sha256": sha256(schemaspy),
            "sqlite_jdbc_jar_sha256": sha256(sqlite_jdbc),
            "source_commit": os.environ.get("SOURCE_COMMIT", "").strip() or "uncommitted",
            "generated_at": os.environ.get("SOURCE_GENERATED_AT", "").strip() or "uncommitted",
            "validation_state": "generated",
        }
        (raw_output / "source-metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        validate_tree(raw_output)
        manifest = directory_manifest(raw_output)
        (raw_output / "artifact-manifest.json").write_text(json.dumps({"artifacts": manifest}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        validate_tree(raw_output)
        if destination.exists():
            shutil.rmtree(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(raw_output, destination)


def compare_directories(expected: Path, actual: Path) -> list[str]:
    differences = []
    expected_files = {p.relative_to(expected).as_posix(): p for p in expected.rglob("*") if p.is_file()}
    actual_files = {p.relative_to(actual).as_posix(): p for p in actual.rglob("*") if p.is_file()} if actual.exists() else {}
    for name in sorted(set(expected_files) | set(actual_files)):
        if name not in actual_files:
            differences.append(f"missing {name}")
        elif name not in expected_files:
            differences.append(f"unexpected {name}")
        elif expected_files[name].read_bytes() != actual_files[name].read_bytes():
            differences.append(f"changed {name}")
    return differences


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("generate", "check"))
    args = parser.parse_args()
    if args.command == "generate":
        # Promotion must occur on the same filesystem as the committed output.
        # os.replace()/Path.replace() cannot atomically rename from /tmp when
        # /tmp and the repository are mounted on different filesystems.
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(
            prefix=".pocketlab-schemaspy-promote-",
            dir=OUTPUT.parent,
        ) as temporary:
            staged = Path(temporary) / "schemaspy"
            generate_to(staged)

            backup = OUTPUT.with_name(OUTPUT.name + ".previous")

            if backup.exists():
                shutil.rmtree(backup)

            try:
                if OUTPUT.exists():
                    OUTPUT.replace(backup)

                staged.replace(OUTPUT)
            except Exception:
                # Restore the last known generated output if promotion fails.
                if not OUTPUT.exists() and backup.exists():
                    backup.replace(OUTPUT)
                raise
            else:
                if backup.exists():
                    shutil.rmtree(backup)

        print(
            "Generated data-free SchemaSpy documentation at "
            f"{OUTPUT.relative_to(ROOT)}"
        )
        return 0
    with tempfile.TemporaryDirectory(prefix="pocketlab-schemaspy-check-") as temporary:
        expected = Path(temporary) / "schemaspy"
        generate_to(expected)
        differences = compare_directories(expected, OUTPUT)
    if differences:
        print("SchemaSpy documentation drift detected:")
        for difference in differences:
            print(f" - {difference}")
        return 1
    print("PASS SchemaSpy documentation is current and data-free")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
