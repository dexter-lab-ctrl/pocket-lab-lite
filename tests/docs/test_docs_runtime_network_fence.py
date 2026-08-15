from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CHECKER = ROOT / "scripts/docs/check_docs_runtime_network_fence.py"
OVERRIDE = ROOT / "docs/overrides/partials/source.html"
RELEASE_BADGE = ROOT / "docs/overrides/partials/release-badge.html"
RELEASES = ROOT / "contracts/generated/knowledge/releases.json"


def test_runtime_network_fence_exists_and_fails_closed():
    checker = CHECKER.read_text(encoding="utf-8")

    assert 'data-md-component="source"' in checker
    assert 'class="md-source"' in checker
    assert "raise SystemExit(1)" in checker
    assert "site/index.html" in checker or 'SITE / "index.html"' in checker


def test_repository_source_override_remains_passive():
    source = OVERRIDE.read_text(encoding="utf-8")

    assert 'href="{{ config.repo_url }}"' in source
    assert 'class="md-source"' in source

    assert 'data-md-component="source"' not in source
    assert "api.github.com" not in source
    assert "fetch(" not in source
    assert "XMLHttpRequest" not in source
    assert "WebSocket" not in source
    assert "EventSource" not in source


def test_repository_source_release_is_static_and_promoted():
    import json

    source = OVERRIDE.read_text(encoding="utf-8")
    badge = RELEASE_BADGE.read_text(encoding="utf-8")
    releases = json.loads(RELEASES.read_text(encoding="utf-8"))

    promoted = [
        item
        for item in releases.get("items", [])
        if item.get("confidence") == "release-promoted"
        and item.get("sanitized") is True
    ]

    assert promoted
    expected = max(
        promoted,
        key=lambda item: (
            str(item.get("promoted_at") or ""),
            str(item.get("name") or ""),
        ),
    )["name"]

    assert '{% include "partials/release-badge.html" %}' in source
    assert 'class="pl-source-release"' in badge
    assert f'data-pl-release="{expected}"' in badge
    assert f">{expected}</span>" in badge

    # Restoring the release label must not restore Material's
    # runtime hosting-provider source component.
    combined = source + badge
    assert 'data-md-component="source"' not in combined
    assert "api.github.com" not in combined
    assert "fetch(" not in combined
    assert "XMLHttpRequest" not in combined



def test_mermaid_runtime_is_repository_owned_and_pinned():
    """Mermaid must be local, pinned, integrity-recorded, and loaded first."""
    from hashlib import sha256
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]

    mkdocs = (root / "mkdocs.yml").read_text(encoding="utf-8")

    asset = (
        root
        / "docs/javascripts/vendor/mermaid-11.16.1.min.js"
    )
    checksum_file = (
        root
        / "docs/javascripts/vendor/mermaid-11.16.1.sha256"
    )
    bootstrap = (
        root
        / "docs/javascripts/mermaid-local.js"
    )

    assert asset.is_file()
    assert asset.stat().st_size > 0
    assert checksum_file.is_file()
    assert bootstrap.is_file()

    expected_order = (
        "javascripts/vendor/mermaid-11.16.1.min.js",
        "javascripts/mermaid-local.js",
        "javascripts/docs.js",
        "javascripts/threat-model.js",
    )

    positions = [mkdocs.index(item) for item in expected_order]
    assert positions == sorted(positions)

    recorded = checksum_file.read_text(
        encoding="utf-8",
    ).split()[0]

    actual = sha256(asset.read_bytes()).hexdigest()

    assert actual == recorded

    bootstrap_text = bootstrap.read_text(encoding="utf-8")

    assert "window.mermaid" in bootstrap_text
    assert "startOnLoad: false" in bootstrap_text

    forbidden_bootstrap_tokens = (
        "fetch(",
        "XMLHttpRequest",
        "WebSocket",
        "EventSource",
        "setInterval(",
        "setTimeout(",
        "requestAnimationFrame(",
        "MutationObserver",
        "import(",
        "unpkg.com",
        "cdn.jsdelivr.net",
    )

    for token in forbidden_bootstrap_tokens:
        assert token not in bootstrap_text


def test_docs_source_has_no_external_mermaid_runtime():
    """Pocket Lab source must not introduce a Mermaid CDN runtime."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]

    candidates = [
        root / "mkdocs.yml",
    ]

    candidates.extend(
        path
        for path in (root / "docs/javascripts").rglob("*")
        if path.is_file()
        and path.suffix in {".js", ".mjs"}
    )

    candidates.extend(
        path
        for path in (root / "docs/overrides").rglob("*")
        if path.is_file()
        and path.suffix in {".html", ".js", ".mjs"}
    )

    forbidden = (
        "unpkg.com/mermaid",
        "cdn.jsdelivr.net/npm/mermaid",
        "cdn.jsdelivr.net/mermaid",
        "cdnjs.cloudflare.com/ajax/libs/mermaid",
    )

    violations = []

    for path in candidates:
        text = path.read_text(
            encoding="utf-8",
            errors="strict",
        )

        for token in forbidden:
            if token in text:
                violations.append(
                    f"{path.relative_to(root)}: {token}"
                )

    assert violations == [], (
        "External Mermaid runtime dependency detected:\n"
        + "\n".join(violations)
    )
