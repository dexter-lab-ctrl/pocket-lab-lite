from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_n6b_manifest_identity_and_install_pipeline_are_lite_specific() -> None:
    manifest_source = read("src/lib/liteInstallManifest.js")
    vite_source = read("vite.config.js")
    html = read("index.html")

    assert "name: 'Pocket Lab Lite'" in manifest_source
    assert "short_name: 'Pocket Lab'" in manifest_source
    assert "id: LITE_INSTALL_ID" in manifest_source
    assert "export const LITE_INSTALL_ID = '/pocket-lab-lite/'" in manifest_source
    assert "display: 'standalone'" in manifest_source
    assert "display_override: ['window-controls-overlay', 'standalone', 'minimal-ui', 'browser']" in manifest_source
    assert "orientation: 'any'" in manifest_source
    assert "manifest: LITE_INSTALL_MANIFEST" in vite_source
    assert "Pocket Lab Admin Console" not in vite_source
    assert "?app=admin_console" not in vite_source
    assert '<title>Pocket Lab Lite</title>' in html
    assert '<meta name="theme-color" content="#f8fafc"' in html
    assert 'apple-touch-icon' in html


def test_n6b_manifest_shortcuts_share_the_phase1_screen_allowlist() -> None:
    metadata = read("src/lite/liteNavigationMetadata.js")
    manifest = read("src/lib/liteInstallManifest.js")

    for screen_id in ("catalog", "devices", "security", "recovery"):
        assert re.search(rf"id:\s*'{screen_id}'[\s\S]*?shortcut:", metadata)
    for forbidden in ("add_device", "restart", "backup_now", "restore_latest", "scan", "remove_app"):
        assert forbidden not in metadata.lower()
    assert "getLiteManifestShortcutDefinitions" in manifest
    assert "screen=(?:catalog|devices|security|recovery)" in manifest


def test_n6b_apps_routes_remain_outside_the_pwa_navigation_shell() -> None:
    vite_source = read("vite.config.js")
    offline_policy = read("src/lib/liteOfflineReadPolicy.js")

    assert "noPwaFallbackPattern" in vite_source
    assert "api|terminal|apps|gitea|docs" in vite_source
    assert "navigateFallbackDenylist: [noPwaFallbackPattern]" in vite_source
    assert "PWA_NAVIGATION_DENYLIST" in offline_policy
    assert "api|terminal|apps|gitea|docs" in offline_policy
    assert "pocketlab-lite-icons-images-v3" in offline_policy


def test_n6b_declared_svg_icons_exist_and_have_exact_square_dimensions() -> None:
    assets = {
        "public/icons/pocket-lab-lite-192.svg": 192,
        "public/icons/pocket-lab-lite-512.svg": 512,
        "public/icons/pocket-lab-lite-maskable-192.svg": 192,
        "public/icons/pocket-lab-lite-maskable-512.svg": 512,
        "public/icons/pocket-lab-lite-apple-touch.svg": 180,
        "public/icon.svg": 192,
    }
    for relative, expected in assets.items():
        path = ROOT / relative
        assert path.exists(), relative
        root = ET.fromstring(path.read_text(encoding="utf-8"))
        assert int(root.attrib["width"]) == expected
        assert int(root.attrib["height"]) == expected
        assert root.attrib["viewBox"] == f"0 0 {expected} {expected}"
        assert path.stat().st_size < 8_192


def test_n6b_install_update_badge_and_share_helpers_remain_browser_only() -> None:
    native_install = read("src/lib/liteNativeInstall.js")
    component = read("src/lite/LiteNativeInstallSurface.jsx")
    sw_runtime = read("src/lib/liteServiceWorkerRuntime.js")
    main = read("src/main.jsx")

    for forbidden in (
        "nats://",
        "subprocess",
        "child_process",
        "pm2 ",
        "tailscale ",
        "restic ",
        "lynis ",
        "trivy ",
        "/api/lite/",
    ):
        assert forbidden not in native_install.lower()
        assert forbidden not in component.lower()

    assert "beforeinstallprompt" in component
    assert "appinstalled" in component
    assert "canOfferLiteInstall" in component
    assert "liteQueryCacheHasRiskyWorkflow" in component
    assert "activeOverlay" in component
    assert "navigatorObject.setAppBadge" in native_install
    assert "navigatorObject.clearAppBadge" in native_install
    assert "navigatorObject.share" in native_install
    assert "navigatorObject.clipboard.writeText" in native_install
    assert "createLiteControlledServiceWorkerUpdate" in sw_runtime
    assert "controllerchange" in sw_runtime
    assert "updateServiceWorker(false)" in sw_runtime
    assert "createLiteControlledServiceWorkerUpdate" in main


def test_n6b_package_adds_only_a_focused_test_script() -> None:
    package = json.loads(read("package.json"))
    lock = json.loads(read("package-lock.json"))
    assert "test:n6b" in package["scripts"]
    assert package["dependencies"] == lock["packages"][""]["dependencies"]
    assert package["devDependencies"] == lock["packages"][""]["devDependencies"]
