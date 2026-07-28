from pathlib import Path


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
    assert "resolve_remote_release" in text
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
