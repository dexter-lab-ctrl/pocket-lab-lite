from __future__ import annotations

import re
from pathlib import Path

from scripts.test.parity.parity_common import ROOT, load_json, safe_openapi_operations


def test_schemathesis_filter_is_get_only_and_destructive_endpoint_free() -> None:
    script = (ROOT / "scripts" / "test" / "parity" / "run_schemathesis.sh").read_text(encoding="utf-8")
    assert "--include-method GET" in script
    assert "POCKETLAB_PARITY_ALLOW_WRITES" not in script
    for value in ("backup", "restore", "check", "restart", "remove", "install", "update", "repair", "invite"):
        assert value in script


def test_openapi_safe_operation_selector_excludes_writes() -> None:
    openapi = load_json(ROOT / "contracts" / "generated" / "lite-openapi.json")
    operations = safe_openapi_operations(openapi)
    assert operations
    assert all(method == "GET" for method, _path in operations)
    assert all(not re.search(r"/(backup|restore|check|restart|remove|install|update|repair|invite)(?:/|$)", path) for _method, path in operations)


def test_k6_profiles_are_bounded_for_edge_and_wsl() -> None:
    edge = (ROOT / "performance" / "parity" / "edge-readonly.js").read_text(encoding="utf-8")
    wsl = (ROOT / "performance" / "parity" / "wsl-readonly.js").read_text(encoding="utf-8")
    assert "vus: 1" in edge
    assert "duration: '30s'" in edge
    assert "vus: 3" in wsl
    assert "duration: '60s'" in wsl
    for source in (edge, wsl):
        assert "http.get" in source
        assert "http.post" not in source
        assert "/api/lite/recovery/summary" in source
        assert "/api/lite/fleet" in source


def test_live_termux_script_is_read_only_and_reports_unavailable() -> None:
    source = (ROOT / "scripts" / "test" / "parity" / "verify_termux_parity.sh").read_text(encoding="utf-8")
    assert "runtime-unavailable" in source
    assert "lite:runtime:ssh:check" in source
    assert "curl -fsS" in source
    for prohibited in (" rm ", " mv ", " cp ", "sed -i", "pm2 restart", "sqlite3", "nats pub"):
        assert prohibited not in source


def test_browser_sources_do_not_access_sqlite_nats_or_ssh() -> None:
    paths = list((ROOT / "src").rglob("*.js")) + list((ROOT / "src").rglob("*.jsx"))
    text = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in paths)
    forbidden_execution = ("child_process", "execSync(", "spawnSync(", "new WebSocket('nats", "fetch('nats://", 'fetch("nats://')
    for token in forbidden_execution:
        assert token not in text
    assert "sqlite3.connect(" not in text
