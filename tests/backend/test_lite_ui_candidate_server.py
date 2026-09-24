from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "scripts/dev/lite/ui_performance_candidate_server.py"


def _module():
    spec = importlib.util.spec_from_file_location("pocketlab_ui_performance_candidate_server", MODULE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_candidate_manifest_is_exact_sha_and_sanitized():
    candidate = _module()
    sha = "a" * 40
    manifest = candidate.candidate_manifest(sha)
    assert manifest["source_commit"] == sha
    assert manifest["qualification_surface"] == "devpc_candidate_loopback"
    assert manifest["runtime_transport"] == "ssh_loopback_to_server_phone_caddy"
    assert manifest["browser_secret_persisted"] is False
    assert manifest["sanitized"] is True
    assert not any("token" in key or "signature" in key for key in manifest)


def test_candidate_manifest_rejects_non_commit_identity():
    candidate = _module()
    with pytest.raises(candidate.CandidateServerError, match="candidate_source_commit_invalid"):
        candidate.candidate_manifest("not-a-sha")


@pytest.mark.parametrize(
    "path,allowed",
    [
        ("/api/lite/status", True),
        ("/api/lite/catalog?screen=home", True),
        ("/api/lite/harness/status", False),
        ("/api/lite/harness/browser/bridge", False),
        ("/api/status", False),
        ("/ws/events", False),
    ],
)
def test_candidate_proxy_is_lite_api_only(path, allowed):
    candidate = _module()
    assert candidate.is_allowed_api_path(path) is allowed


def test_candidate_static_path_stays_inside_dist(tmp_path):
    candidate = _module()
    (tmp_path / "index.html").write_text("candidate", encoding="utf-8")
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "app.js").write_text("asset", encoding="utf-8")
    assert candidate.safe_dist_file(tmp_path, "/") == (tmp_path / "index.html").resolve()
    assert candidate.safe_dist_file(tmp_path, "/assets/app.js") == (assets / "app.js").resolve()
    assert candidate.safe_dist_file(tmp_path, "/../outside.js") is None
    assert candidate.safe_dist_file(tmp_path, "/assets/../index.html") == (tmp_path / "index.html").resolve()

