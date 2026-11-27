from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/dev/lite/coordinated_runtime_promotion.py"


def _module():
    spec = importlib.util.spec_from_file_location("pocketlab_coordinated_runtime_promotion", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Qualification:
    def __init__(self, root: Path):
        self._root = root

    def root(self):
        return self._root

    def assert_safe(self):
        return None


def test_live_coordinated_owner_is_disabled_without_explicit_gate(monkeypatch, tmp_path):
    module = _module()
    monkeypatch.delenv("POCKETLAB_COORDINATED_LIVE_QUALIFICATION", raising=False)
    assert module._live_binding(_Qualification(tmp_path), tmp_path / "state/db.sqlite3") is None


def test_live_coordinated_owner_requires_qualification_and_contained_paths(monkeypatch, tmp_path):
    module = _module()
    root = tmp_path / "run"
    root.mkdir()
    state = root / "state"
    state.mkdir()
    pm2 = root / "pm2"
    pm2.mkdir()
    runtime = root / "runtime"
    runtime.mkdir()
    caddy = root / "caddy/Caddyfile"
    caddy.parent.mkdir()
    caddy.write_text(":8443 {}\n", encoding="utf-8")
    database = state / "pocketlab-lite.sqlite3"
    database.touch()
    monkeypatch.setenv("POCKETLAB_COORDINATED_LIVE_QUALIFICATION", "1")
    monkeypatch.setenv("POCKETLAB_ENVIRONMENT", "production")
    with pytest.raises(PermissionError, match="qualification_environment"):
        module._live_binding(_Qualification(root), database)

    monkeypatch.setenv("POCKETLAB_ENVIRONMENT", "qualification")
    monkeypatch.setenv("POCKETLAB_STATE_DIR", str(state))
    monkeypatch.setenv("PM2_HOME", str(pm2))
    monkeypatch.setenv("POCKETLAB_COORDINATED_RUNTIME_ROOT", str(runtime))
    monkeypatch.setenv("POCKETLAB_CADDYFILE", str(caddy))
    monkeypatch.setenv("POCKETLAB_COORDINATED_API_URL", "http://127.0.0.1:18080")
    monkeypatch.setenv("POCKETLAB_COORDINATED_PROXY_URL", "http://127.0.0.1:18443")
    monkeypatch.setenv("POCKETLAB_OPA_URL", "http://127.0.0.1:18181")
    monkeypatch.setenv("POCKETLAB_QUALIFICATION_RUN_ID", "a" * 24)
    binding = module._live_binding(_Qualification(root), database)
    assert binding["database"] == database
    assert binding["runtime_root"] == runtime

    monkeypatch.setenv("POCKETLAB_COORDINATED_API_URL", "https://example.invalid:18080")
    with pytest.raises(PermissionError, match="coordinated_api_must_be_loopback"):
        module._live_binding(_Qualification(root), database)


def test_live_owner_materializes_only_regular_candidate_tree(tmp_path):
    module = _module()
    source = tmp_path / "source"
    (source / "pocket-lab-final-structure/runtime").mkdir(parents=True)
    (source / "pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts").mkdir(parents=True)
    (source / "security/policies").mkdir(parents=True)
    (source / "scripts/dev/lite").mkdir(parents=True)
    (source / "pocket-lab-final-structure/runtime/service.py").write_text("x", encoding="utf-8")
    (source / "pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/run.sh").write_text("x", encoding="utf-8")
    (source / "security/policies/policy.rego").write_text("x", encoding="utf-8")
    (source / "scripts/dev/lite/owner.py").write_text("x", encoding="utf-8")
    target = module._materialize_runtime_tree(source, tmp_path / "runtime")
    assert (target / "runtime/service.py").is_file()
    assert (target / "bootstrap/scripts/run.sh").is_file()
    assert (target / "security/policies/policy.rego").is_file()
    assert (target / "scripts/dev/lite/owner.py").is_file()
