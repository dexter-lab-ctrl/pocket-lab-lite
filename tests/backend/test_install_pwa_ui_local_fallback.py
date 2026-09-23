import json
from pathlib import Path
import re
import subprocess
import sys



SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "pocket-lab-final-structure"
    / "pocket-lab-bootstrap-production-scripts-patched"
    / "scripts"
    / "install-pwa-ui.sh"
)


def _script_text() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_install_pwa_ui_supports_local_dist_zip_override():
    text = _script_text()
    assert "POCKETLAB_LOCAL_DIST_ZIP" in text
    assert "POCKET_LAB_LOCAL_DIST_ZIP" in text
    assert '[[ -r "$LOCAL_DIST_ZIP" ]]' in text
    assert 'cp "$LOCAL_DIST_ZIP" "$archive"' in text
    assert 'source-bootstrap-' in text


def test_install_pwa_ui_filters_the_lite_release_stream():
    text = _script_text()
    assert "https://api.github.com/repos/$REPO/releases?per_page=100" in text
    assert "/releases/latest" not in text
    assert "resolve_release_candidates" in text
    assert "resolve_release_assets" in text
    assert "pocketlab-lite-release.json" in text
    assert "validate_manifest" in text


def test_install_pwa_ui_uses_bounded_https_and_safe_zip_extraction():
    text = _script_text()
    assert "require_cmd python3" in text
    assert "download_https" in text
    assert "RestrictedRedirect" in text
    assert "release-assets.githubusercontent.com" in text
    assert "safe_extract_pwa" in text
    assert "safe_extract_zip" in text
    assert "unzip -q" not in text
    assert '"install_mode":"source"' in text


def _embedded_python(function_name: str) -> str:
    text = _script_text()
    function_marker = f"{function_name}() {{"
    start = text.find(function_marker)
    assert start >= 0, f"Could not find function {function_name}"

    heredoc = re.search(r"<<'([A-Z0-9_]+)'\n", text[start:])
    assert heredoc, f"Could not find Python heredoc for {function_name}"

    delimiter = heredoc.group(1)
    body_start = start + heredoc.end()
    body_end = text.find(f"\n{delimiter}\n", body_start)
    assert body_end >= 0, f"Could not find heredoc terminator for {function_name}"
    return text[body_start:body_end]


def _run_embedded_python(function_name: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-", *args],
        input=_embedded_python(function_name),
        text=True,
        capture_output=True,
        check=False,
    )


def _release(tag: str, release_id: int, assets: list[dict] | None = None) -> dict:
    return {
        "id": release_id,
        "tag_name": tag,
        "draft": False,
        "prerelease": False,
        "assets_url": (
            f"https://api.github.com/repos/dexter-lab-ctrl/pocket-lab-lite/"
            f"releases/{release_id}/assets"
        ),
        "assets": assets or [],
    }


def _asset(name: str, url: str | None = None) -> dict:
    return {
        "name": name,
        "browser_download_url": url
        or f"https://github.com/dexter-lab-ctrl/pocket-lab-lite/releases/download/"
        f"lite-2026.09.23.1/{name}",
    }


def test_release_candidates_keep_newest_release_when_embedded_assets_are_empty(tmp_path):
    metadata = tmp_path / "releases.json"
    metadata.write_text(
        json.dumps(
            [
                _release("lite-2026.09.23.1", 394417401),
                _release(
                    "lite-2026.09.10.2",
                    386481814,
                    [
                        _asset("dist.zip"),
                        _asset("checksums.txt"),
                        _asset("pocketlab-lite-release.json"),
                    ],
                ),
            ]
        ),
        encoding="utf-8",
    )

    result = _run_embedded_python(
        "resolve_release_candidates",
        str(metadata),
        "dexter-lab-ctrl/pocket-lab-lite",
    )

    assert result.returncode == 0, result.stderr
    lines = result.stdout.splitlines()
    assert lines[:6] == [
        "lite-2026.09.23.1",
        "https://api.github.com/repos/dexter-lab-ctrl/pocket-lab-lite/releases/394417401/assets",
        "",
        "",
        "",
        "0",
    ]
    assert lines[6] == "lite-2026.09.10.2"
    assert lines[11] == "1"


def test_dedicated_release_assets_accept_complete_trusted_asset_set(tmp_path):
    metadata = tmp_path / "assets.json"
    metadata.write_text(
        json.dumps(
            [
                _asset("dist.zip"),
                _asset("checksums.txt"),
                _asset("pocketlab-lite-release.json"),
            ]
        ),
        encoding="utf-8",
    )

    result = _run_embedded_python("resolve_release_assets", str(metadata))

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        _asset("dist.zip")["browser_download_url"],
        _asset("checksums.txt")["browser_download_url"],
        _asset("pocketlab-lite-release.json")["browser_download_url"],
    ]


def test_dedicated_release_assets_reject_incomplete_asset_set(tmp_path):
    metadata = tmp_path / "assets.json"
    metadata.write_text(
        json.dumps([_asset("dist.zip"), _asset("checksums.txt")]),
        encoding="utf-8",
    )

    result = _run_embedded_python("resolve_release_assets", str(metadata))

    assert result.returncode != 0
    assert "incomplete or invalid" in result.stderr


def test_dedicated_release_assets_reject_duplicate_required_asset(tmp_path):
    metadata = tmp_path / "assets.json"
    metadata.write_text(
        json.dumps(
            [
                _asset("dist.zip"),
                _asset("dist.zip"),
                _asset("checksums.txt"),
                _asset("pocketlab-lite-release.json"),
            ]
        ),
        encoding="utf-8",
    )

    result = _run_embedded_python("resolve_release_assets", str(metadata))

    assert result.returncode != 0
    assert "incomplete or invalid" in result.stderr


def test_dedicated_release_assets_reject_unapproved_download_host(tmp_path):
    metadata = tmp_path / "assets.json"
    metadata.write_text(
        json.dumps(
            [
                _asset("dist.zip", "https://example.com/dist.zip"),
                _asset("checksums.txt"),
                _asset("pocketlab-lite-release.json"),
            ]
        ),
        encoding="utf-8",
    )

    result = _run_embedded_python("resolve_release_assets", str(metadata))

    assert result.returncode != 0
    assert "incomplete or invalid" in result.stderr


def test_install_pwa_ui_recovers_missing_embedded_assets_and_logs_selected_release():
    text = _script_text()
    assert "resolve_release_candidates" in text
    assert "resolve_release_assets" in text
    assert 'checking the dedicated GitHub release assets endpoint' in text
    assert 'Skipping release $candidate_tag because its dedicated release assets are incomplete or invalid' in text
    assert 'Selected Pocket Lab Lite release: $tag' in text
    assert 'Pocket Lab Lite PWA pointer is ready: $tag' in text
