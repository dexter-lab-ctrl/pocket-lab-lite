from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_home_uses_existing_server_state_layers_without_new_api_fanout() -> None:
    home = read("src/lite/LiteHome.jsx")
    app = read("src/lite/LiteApp.jsx")
    status_hook = read("src/hooks/useLiteStatus.js")
    snapshots = read("src/lib/liteSafeSnapshots.js")

    assert "buildLiteHomeOverview" in home
    assert 'data-home-state-source="tanstack-dexie-fastapi"' in home
    assert "useLiteResource" not in home
    assert "liteApi.status" not in home
    assert "liteApi.catalog" not in home
    assert "liteApi.fleet" not in home
    assert "useLiteStatus()" in app
    assert "savedStateOnly" in app
    assert "backendReachable" in app
    assert "lastUpdatedLabel" in app
    assert "useLiteQuery" in status_hook
    assert "liteQueryKeys.status()" in status_hook
    assert "Dexie" in snapshots or "liteOfflineDb" in snapshots


def test_home_presentation_removes_operational_jargon_from_visible_home_copy() -> None:
    home = read("src/lite/LiteHome.jsx")
    presentation = read("src/lib/liteHomePresentation.js")

    for forbidden in (
        "Command Bus",
        "Worker Execution",
        "Policy & Compliance",
        "NATS",
        "JetStream",
        "FastAPI",
        "SQLite",
        "backend-owned",
    ):
        assert forbidden not in home

    assert "Task delivery" in presentation
    assert "Background operations" in presentation
    assert "Protection rules" in presentation
    assert "Backups and recovery" in presentation
    assert "Actions stay protected" in presentation
    assert "recommended next step" in home.lower()


def test_home_and_primary_tabs_use_bounded_native_motion_and_haptics() -> None:
    home = read("src/lite/LiteHome.jsx")
    recovery = read("src/lite/LiteRecovery.jsx")
    security = read("src/lite/LiteSecurity.jsx")
    catalog = read("src/lite/catalog/AppCatalogScreen.jsx")
    css = read("src/index.css")

    assert "LiteElevationSurface" in home
    assert "LiteMotionReveal" in home
    assert "LitePressableButton" in home
    assert "LiteElevationSurface" in recovery
    assert "LiteMotionReveal" in recovery
    assert "triggerLiteHaptic('accepted')" in recovery
    assert "useSpring" in security
    assert 'data-security-native-polish="true"' in security
    assert "catalogEntranceSpring" in catalog
    assert "triggerLiteTactileFeedback('selection')" in catalog
    assert 'data-catalog-native-polish="true"' in catalog
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert "content-visibility: auto" in css


def test_existing_zustand_xstate_tanstack_dexie_and_worker_boundaries_are_preserved() -> None:
    recovery = read("src/lite/LiteRecovery.jsx")
    security = read("src/lite/LiteSecurity.jsx")
    catalog = read("src/lite/catalog/AppCatalogScreen.jsx")
    ui_store = read("src/stores/liteUiStore.js")
    mutation = read("src/hooks/useLiteMutation.js")
    combined = "\n".join((recovery, security, catalog))

    assert "useLiteUiStore" in combined
    assert "useLiteRecoveryFlow" in recovery
    assert "securityFlow" in security
    assert "useLiteAppActionFlow" in catalog
    assert "useLiteMutation" in catalog
    assert "LITE_UI_STORE_IS_UI_ONLY = true" in ui_store
    assert "LITE_BROWSER_ACTION_QUEUE_DISABLED = true" in mutation

    for forbidden in (
        "nats://",
        "child_process",
        "subprocess",
        "execSync(",
        "spawn(",
        "pm2 restart",
        "tailscale up",
        "restic backup",
    ):
        assert forbidden not in combined.lower()


def test_polish_adds_no_dependency_or_backend_contract_change() -> None:
    package = json.loads(read("package.json"))
    lock = json.loads(read("package-lock.json"))

    assert "test:premium-tabs" in package["scripts"]
    assert package["dependencies"] == lock["packages"][""]["dependencies"]
    assert package["devDependencies"] == lock["packages"][""]["devDependencies"]
    assert not (ROOT / "pocket-lab-final-structure/runtime/api_fastapi/services/lite_home.py").exists()
