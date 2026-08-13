#!/usr/bin/env python3

from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "site"

DYNAMIC_SOURCE_MARKER = 'data-md-component="source"'
STATIC_SOURCE_MARKER = 'class="md-source"'

LOCAL_MERMAID_ASSET = (
    "javascripts/vendor/mermaid-11.16.1.min.js"
)

FORBIDDEN_MERMAID_RUNTIME_PREFIXES = (
    "https://unpkg.com/mermaid",
    "https://cdn.jsdelivr.net/npm/mermaid",
    "https://cdn.jsdelivr.net/mermaid",
    "https://cdnjs.cloudflare.com/ajax/libs/mermaid",
)

# Material's generated bundle may contain a dormant Mermaid CDN fallback
# string. Static presence in that upstream bundle is not treated as an
# executed network dependency. Playwright owns execution-time enforcement.
MATERIAL_BUNDLE_PATTERN = re.compile(
    r"(?:^|/)assets/javascripts/bundle\.[A-Za-z0-9_-]+\.min\.js$"
)

SCRIPT_SRC_PATTERN = re.compile(
    r"<script\b[^>]*\bsrc=[\"']([^\"']+)[\"']",
    re.IGNORECASE,
)

MODULE_IMPORT_PATTERN = re.compile(
    r"(?:import\s+(?:[^\"']+\s+from\s+)?|import\s*\()"
    r"\s*[\"']([^\"']+)[\"']",
    re.IGNORECASE,
)


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def read_utf8(path: Path) -> str:
    try:
        return path.read_text(
            encoding="utf-8",
            errors="strict",
        )
    except UnicodeDecodeError as exc:
        fail(
            "generated runtime file is not valid UTF-8: "
            f"{path.relative_to(ROOT)}: {exc}"
        )

    raise AssertionError("unreachable")


def is_forbidden_mermaid_url(value: str) -> bool:
    return value.startswith(
        FORBIDDEN_MERMAID_RUNTIME_PREFIXES
    )


def main() -> None:
    if not SITE.is_dir():
        fail(
            "generated documentation site is missing; "
            "run MkDocs generation before this check"
        )

    index = SITE / "index.html"

    if not index.is_file():
        fail("generated site/index.html is missing")

    html_files = sorted(SITE.rglob("*.html"))

    if not html_files:
        fail(
            "generated documentation site contains no HTML files"
        )

    dynamic_source_hits: list[str] = []
    external_script_hits: list[str] = []
    external_module_hits: list[str] = []
    repository_js_hits: list[str] = []

    local_mermaid_reference_found = False

    # ------------------------------------------------------------
    # Rendered HTML
    # ------------------------------------------------------------
    for html_file in html_files:
        text = read_utf8(html_file)
        relative = html_file.relative_to(ROOT).as_posix()

        if DYNAMIC_SOURCE_MARKER in text:
            dynamic_source_hits.append(relative)

        if LOCAL_MERMAID_ASSET in text:
            local_mermaid_reference_found = True

        for src in SCRIPT_SRC_PATTERN.findall(text):
            if is_forbidden_mermaid_url(src):
                external_script_hits.append(
                    f"{relative}: {src}"
                )

        for module_url in MODULE_IMPORT_PATTERN.findall(text):
            if is_forbidden_mermaid_url(module_url):
                external_module_hits.append(
                    f"{relative}: {module_url}"
                )

    # ------------------------------------------------------------
    # Pocket Lab-owned generated JavaScript.
    #
    # MkDocs copies docs/javascripts/** to site/javascripts/**.
    # These files are repository-controlled and must remain free of
    # external Mermaid runtime dependencies.
    #
    # Material's own site/assets/javascripts/bundle.*.min.js is upstream
    # theme code and is intentionally not scanned as repository-owned JS.
    # ------------------------------------------------------------
    repo_js_root = SITE / "javascripts"

    if repo_js_root.is_dir():
        js_files = sorted(
            [
                *repo_js_root.rglob("*.js"),
                *repo_js_root.rglob("*.mjs"),
            ]
        )

        for js_file in js_files:
            text = read_utf8(js_file)
            relative = js_file.relative_to(ROOT).as_posix()

            # The vendored Mermaid binary itself is allowed to contain
            # implementation strings from its upstream distribution.
            if relative.endswith(LOCAL_MERMAID_ASSET):
                continue

            for token in FORBIDDEN_MERMAID_RUNTIME_PREFIXES:
                if token in text:
                    repository_js_hits.append(
                        f"{relative}: {token}"
                    )

    # ------------------------------------------------------------
    # Document Material bundle boundary.
    # ------------------------------------------------------------
    for bundle in SITE.glob(
        "assets/javascripts/bundle.*.min.js"
    ):
        relative = bundle.relative_to(SITE).as_posix()

        if not MATERIAL_BUNDLE_PATTERN.search(relative):
            fail(
                "unexpected Material bundle naming pattern: "
                f"{bundle.relative_to(ROOT)}"
            )

    if dynamic_source_hits:
        print(
            "FAIL: Material runtime repository source hook was rendered:",
            file=sys.stderr,
        )

        for hit in dynamic_source_hits[:20]:
            print(f"  - {hit}", file=sys.stderr)

        raise SystemExit(1)

    if external_script_hits:
        print(
            "FAIL: rendered docs reference an external Mermaid script:",
            file=sys.stderr,
        )

        for hit in external_script_hits[:20]:
            print(f"  - {hit}", file=sys.stderr)

        raise SystemExit(1)

    if external_module_hits:
        print(
            "FAIL: rendered docs reference an external Mermaid module:",
            file=sys.stderr,
        )

        for hit in external_module_hits[:20]:
            print(f"  - {hit}", file=sys.stderr)

        raise SystemExit(1)

    if repository_js_hits:
        print(
            "FAIL: repository-owned generated JavaScript contains "
            "an external Mermaid dependency:",
            file=sys.stderr,
        )

        for hit in repository_js_hits[:20]:
            print(f"  - {hit}", file=sys.stderr)

        raise SystemExit(1)

    index_text = read_utf8(index)

    if STATIC_SOURCE_MARKER not in index_text:
        fail(
            "static repository source link is missing "
            "from site/index.html"
        )

    if not local_mermaid_reference_found:
        fail(
            "repository-owned pinned Mermaid runtime is not referenced "
            "by generated documentation HTML"
        )

    local_asset = SITE / LOCAL_MERMAID_ASSET

    if not local_asset.is_file():
        fail(
            "repository-owned pinned Mermaid runtime was referenced "
            "but is missing from the generated site"
        )

    if local_asset.stat().st_size == 0:
        fail(
            "repository-owned pinned Mermaid runtime is empty"
        )

    print(
        "PASS: generated docs are runtime-network-safe "
        "(static repository link present; "
        "Material source API hook absent; "
        "local Mermaid runtime present; "
        "no rendered external Mermaid dependency)"
    )


if __name__ == "__main__":
    main()
