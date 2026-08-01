from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_root_taskfile_is_lite_first_and_preserves_compatibility_aliases():
    root = (ROOT / "Taskfile.yml").read_text()
    task_text = "\n".join(path.read_text() for path in (ROOT / "tasks").glob("Taskfile.*.yml"))
    assert "tasks/Taskfile.lite.yml" in root
    for task in (
        "lite:setup", "lite:setup:check", "lite:playwright:preflight",
        "lite:check:quick", "lite:check", "lite:check:release",
        "lite:test:storybook", "lite:test:e2e:mocked", "lite:test:e2e:live",
        "lite:docs:development:generate", "lite:docs:production:generate",
        "lite:docs:generate", "lite:docs:check", "lite:release:dry-run",
        "lite:api:check",
    ):
        assert f"{task}:" in task_text
    for removed in ("test:websockets:", "test:iac:", "docs:operations:", "threatdragon:serve:"):
        assert removed not in root + task_text


def test_protected_versions_are_not_changed_by_package_delta():
    package = json.loads((ROOT / "package.json").read_text())
    lock = json.loads((ROOT / "package-lock.json").read_text())
    expected = {
        "@playwright/test": "1.60.0",
        "storybook": "8.6.18",
        "@storybook/react-vite": "8.6.18",
        "@storybook/addon-a11y": "8.6.18",
        "@redocly/cli": "2.31.6",
    }
    for name, version in expected.items():
        assert lock["packages"][f"node_modules/{name}"]["version"] == version
    assert ".nvmrc" not in {path.name for path in ROOT.iterdir()}
    assert package["scripts"]["test"] == "vitest run"


def test_storybook_covers_all_current_tabs_and_required_problem_classes():
    required = {
        "LiteHome.stories.jsx": ["Healthy", "ReviewRecommended", "ReleaseAvailable", "SavedOfflineSnapshot"],
        "LiteDevices.stories.jsx": ["ServerHostOnline", "JoinedDeviceOffline", "AgentStopped", "InviteIdentityMismatch"],
        "LiteCatalog.stories.jsx": ["CatalogReady", "AppStopped", "PreparedProjectionStale"],
        "LiteRecovery.stories.jsx": ["ProjectionTooOld", "LatestBackupVerified", "RestorePreviewReady", "RepositoryUnavailable"],
        "LiteSecurity.stories.jsx": ["QuickCheckReviewRecommended", "FullCheckRunning", "AppCheckHealthy", "UnsupportedAppProfileRoute"],
        "LiteIdentity.stories.jsx": ["IdentitySummary", "FutureRoleAwareState"],
        "LiteRules.stories.jsx": ["NoRules", "RuleValidationError", "FutureApprovalRequired"],
    }
    for filename, stories in required.items():
        text = (ROOT / "src/lite" / filename).read_text()
        for story in stories:
            assert re.search(rf"export const {story}\s*=", text)
    assert "src/stories/PocketLabTabs.stories.jsx" not in [path.relative_to(ROOT).as_posix() for path in ROOT.rglob("*.stories.jsx")]


def test_generated_fixture_metadata_and_recovery_security_scenarios_are_current():
    manifest = json.loads((ROOT / "src/test/fixtures/generated/manifest.json").read_text())
    assert manifest["metadata"]["generated"] is True
    inventory = {(item["domain"], item["scenario"]) for item in manifest["inventory"]}
    for item in (
        ("recovery", "recovery-projection-too-old"),
        ("recovery", "recovery-preview-ready"),
        ("recovery", "recovery-repository-unavailable"),
        ("security", "security-action-needed"),
        ("security", "security-app-check-healthy"),
        ("security", "security-unsupported-app-route"),
    ):
        assert item in inventory
    partial = json.loads((ROOT / "src/test/fixtures/generated/identity/identity-role-aware-fixture.json").read_text())
    assert partial["metadata"]["implementation_status"] == "partial"


def test_openapi_and_frontend_route_usage_outputs_exist():
    schema = json.loads((ROOT / "contracts/generated/lite-openapi.json").read_text())
    assert schema["paths"]
    assert all(path.startswith("/api/lite/") or path in {"/health", "/ready"} for path in schema["paths"])
    usage = (ROOT / "docs/generated/development/frontend-api-usage.md").read_text()
    assert "Unsupported frontend route references\n- None" in usage


def test_development_and_production_docs_are_independent_and_mark_partial_surfaces():
    mkdocs = (ROOT / "mkdocs.yml").read_text()
    assert re.search(r"^  - Development:", mkdocs, re.M)
    assert re.search(r"^  - Production:", mkdocs, re.M)
    for folder, audience in (("development", "development"), ("production", "production")):
        pages = list((ROOT / "docs/generated" / folder).glob("*.md"))
        assert pages
        for page in pages:
            text = page.read_text()
            assert f"audience: {audience}" in text
            for field in (
                "source_commit:", "generated_at:", "generator:",
                "source_fingerprint:", "schema_revision:", "validation_status:",
            ):
                assert field in text
        manifest = json.loads((ROOT / "docs/generated" / folder / "manifest.json").read_text())
        assert manifest["audience"] == audience
        assert manifest["generated_files"]
        assert manifest["source_fingerprints"]
    production = "\n".join(path.read_text() for path in (ROOT / "docs/generated/production").glob("*.md"))
    assert "advanced roles are not claimed" in production
    assert "advanced execution is not claimed" in production


def test_browser_resolver_and_playwright_config_fail_closed_on_wsl2():
    resolver = (ROOT / "scripts/dev/lite/resolve-browser.mjs").read_text()
    config = (ROOT / "playwright.config.ts").read_text()
    for variable in ("PLAYWRIGHT_EXECUTABLE_PATH", "CHROME_PATH", "CHROMIUM_PATH", "EDGE_PATH"):
        assert variable in resolver
    assert "/usr/bin/google-chrome" in resolver
    assert "external-wsl2" in resolver
    assert "resolveLiteBrowser" in config
    assert "playwright-browser.json" in (ROOT / "tests/e2e/global-setup.ts").read_text()


def test_generated_outputs_do_not_contain_known_secret_patterns():
    forbidden = [
        re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{8,}", re.I),
        re.compile(r"-----BEGIN [^-]+PRIVATE KEY-----", re.I),
        re.compile(r"nats://[^\s/@:]+:[^\s/@]+@", re.I),
        re.compile(r"tskey-[A-Za-z0-9_-]+", re.I),
    ]
    for root in (ROOT / "docs/generated", ROOT / "src/test/fixtures/generated", ROOT / "contracts/generated"):
        for file in root.rglob("*"):
            if not file.is_file() or file.suffix not in {".md", ".json", ".js"}:
                continue
            text = file.read_text(errors="ignore")
            assert not any(pattern.search(text) for pattern in forbidden), file


def test_vitest_does_not_collect_playwright_or_node_runner_suites():
    config = (ROOT / "vite.config.js").read_text()
    assert "include: ['src/**/*.{test,spec}.{js,jsx,ts,tsx}']" in config
    package = json.loads((ROOT / "package.json").read_text())
    assert package["scripts"]["test:unit"] == "vitest run"
    assert package["scripts"]["test:e2e:mocked"].endswith("run-playwright-mocked.sh")
    assert "npx playwright test" in (ROOT / "scripts/dev/lite/run-playwright-mocked.sh").read_text()
    assert "node --test tests/dev/browser-resolver.test.mjs" in (ROOT / "scripts/dev/lite/run-gate.sh").read_text()


def test_mocked_e2e_covers_current_compact_read_endpoints():
    handlers = (ROOT / "src/mocks/handlers.js").read_text(encoding="utf-8")
    for path in (
        "/api/lite/revisions",
        "/api/lite/events",
        "/api/lite/release",
        "/api/lite/security/summary",
        "/api/lite/security/freshness",
        "/api/lite/recovery/summary",
        "/api/lite/diagnostics/frontend-lifecycle/challenge",
    ):
        assert f"http.get('{path}'" in handlers


def test_mocked_e2e_assertions_are_scoped_to_visible_screen():
    source = (ROOT / "tests/e2e/lite-mocked.spec.ts").read_text(encoding="utf-8")
    assert "locator('[data-lite-screen-id=\"recovery\"]')).toContainText" in source
    assert "locator('[data-lite-screen-id=\"security\"]')).toContainText" in source
    assert "getByText(/saved|stale|projection|recovery/i).first()" not in source


def test_visual_baseline_update_is_explicit_and_separate():
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    assert "--update-snapshots" not in package["scripts"]["test:visual"]
    assert "--update-snapshots" in package["scripts"]["test:visual:update"]
    tasks = (ROOT / "tasks/Taskfile.ui.yml").read_text(encoding="utf-8")
    assert "lite:test:visual:update:" in tasks


def test_mocked_e2e_failure_watcher_deduplicates_unattributed_resource_404s():
    source = (ROOT / "tests/e2e/lite-test-helpers.ts").read_text(encoding="utf-8")
    assert "isGenericResource404" in source
    assert "!locationUrl.includes('/api/lite/')" in source
    assert "page.on('response'" in source
    assert "response.url().includes('/api/lite/')" in source


def test_visual_suite_waits_for_async_screen_height_to_settle():
    helper = (ROOT / "tests/e2e/lite-test-helpers.ts").read_text(encoding="utf-8")
    visual = (ROOT / "tests/e2e/lite-visual.spec.ts").read_text(encoding="utf-8")
    assert "waitForLiteScreenToSettle" in helper
    assert "element.scrollHeight" in helper
    assert "document.fonts.ready" in helper
    assert "await waitForLiteScreenToSettle(page, screenId)" in visual
