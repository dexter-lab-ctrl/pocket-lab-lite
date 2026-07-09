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
    assert "Using local PWA dist.zip" in text
    assert "cp \"$LOCAL_DIST_ZIP\" \"$TMP_ZIP\"" in text


def test_install_pwa_ui_keeps_github_release_path_as_default():
    text = _script_text()
    assert "Querying GitHub latest release" in text
    assert "https://api.github.com/repos/$REPO/releases/latest" in text
    assert "download_file \"$url\" \"$TMP_ZIP\"" in text


def test_install_pwa_ui_requires_curl_only_for_github_path():
    text = _script_text()
    assert "require_cmd unzip" in text
    local_branch = text.split('if [[ -n "$LOCAL_DIST_ZIP" ]]', 1)[1].split("else", 1)[0]
    github_branch = text.split("else", 1)[1].split("fi", 1)[0]
    assert "require_cmd curl" not in local_branch
    assert "require_cmd curl" in github_branch
