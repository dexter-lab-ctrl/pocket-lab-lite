from __future__ import annotations

import inspect
import io
import json
import os
import sys
import zipfile
from pathlib import Path

import pytest

from pocket_lab_test_utils import ensure_runtime_path


def _module():
    ensure_runtime_path()
    import scripts.dev.lite.security_assurance_toolchain as toolchain

    return toolchain


def test_tool_registry_promotes_all_required_tools_to_fixed_harness_contracts():
    toolchain = _module()
    registry = toolchain._registry()
    assert len(registry["toolchain"]) == 31
    assert all(item.get("harness_status") == "ACTIVE" for item in registry["toolchain"].values())
    assert all(item.get("execution_lane") in {"server_phone_worker", "dev_pc_static", "dev_pc_live_runtime"} for item in registry["toolchain"].values())
    assert all(item.get("command_id") and item.get("fixed_target") for item in registry["toolchain"].values())
    assert not any("deferred" in json.dumps(item).casefold() or "inventory_only" in json.dumps(item).casefold() for item in registry["toolchain"].values())
    assert toolchain.TOOL_EXECUTION_ORDER.index("syft") < toolchain.TOOL_EXECUTION_ORDER.index("grype")


def test_check_status_uses_only_terminal_toolchain_vocabulary():
    toolchain = _module()
    result = toolchain.check_toolchain()
    assert result["required_status_vocabulary"] == ["READY", "NOT_APPLICABLE", "FAILED"]
    assert len(result["tools"]) == 31
    assert {item["status"] for item in result["tools"]} <= {"READY", "NOT_APPLICABLE", "FAILED"}
    assert all("binary_path" not in item or not str(item["binary_path"]).startswith("/home/") for item in result["tools"])


def test_fixed_runtime_commands_have_no_caller_target_or_argv_inputs(tmp_path: Path, monkeypatch):
    toolchain = _module()
    monkeypatch.setattr(toolchain, "MANAGED_ROOT", tmp_path / "managed")
    toolchain.MANAGED_ROOT.mkdir()
    sni_file = tmp_path / "caddy-sni"
    sni_file.write_text("qualification.example.test\n", encoding="ascii")
    monkeypatch.setattr(toolchain, "TLS_SNI_FILE", sni_file)
    binary = Path(sys.executable)
    command, _ = toolchain._run_command_for_tool("nmap", "deep", binary, tmp_path, toolchain._fixed_env())
    assert command[-1] == toolchain.APPROVED_NMAP_TARGET
    assert command[command.index("-p") + 1] == toolchain.APPROVED_PORTS
    assert toolchain.APPROVED_PORT_FORWARD_MAP == {
        14222: "server_phone_nats_4222",
        18080: "server_phone_api_8080",
        18181: "server_phone_opa_8181",
        18222: "server_phone_nats_monitor_8222",
        18443: "server_phone_caddy_tls_443",
    }
    assert "http://attacker.invalid" not in command
    command, _ = toolchain._run_command_for_tool("testssl.sh", "standard", binary, tmp_path, toolchain._fixed_env())
    assert command[-1] == "qualification.example.test:18443"
    assert command[command.index("--ip") + 1] == "127.0.0.1"
    assert command[-1] == "qualification.example.test:18443"
    displayed = toolchain._display_argv(command)
    assert "qualification.example.test:18443" not in displayed
    assert displayed[-1] == "FIXED_CADDY_TLS_IDENTITY:FIXED_CADDY_TLS_PORT"


    runtime_command, _ = toolchain._run_command_for_tool(
        "pocketlab-runtime-360",
        "adversarial",
        Path(sys.executable),
        tmp_path,
        toolchain._fixed_env(tool_id="pocketlab-runtime-360"),
    )
    assert runtime_command == [
        str(Path(sys.executable)),
        str(toolchain.LIVE_360_SCRIPT),
        "adversarial",
    ]
    assert "attacker.invalid" not in " ".join(runtime_command)

    browser_command, _ = toolchain._run_command_for_tool(
        "playwright-runtime",
        "standard",
        Path("/usr/bin/node"),
        tmp_path,
        toolchain._fixed_env(tool_id="playwright-runtime"),
    )
    assert browser_command == [
        "/usr/bin/node",
        str(toolchain.BROWSER_360_SCRIPT),
        "standard",
    ]


def test_osv_and_zap_use_bounded_structured_artifacts(tmp_path: Path):
    toolchain = _module()
    binary = Path(sys.executable)
    osv_command, osv_artifact = toolchain._run_command_for_tool("osv-scanner", "standard", binary, tmp_path, toolchain._fixed_env())
    assert osv_artifact is not None and osv_artifact.name == "osv.json"
    assert "--output-file" in osv_command
    assert str(osv_artifact) in osv_command
    zap_command, zap_artifact = toolchain._run_command_for_tool("owasp-zap", "deep", binary, tmp_path, toolchain._fixed_env())
    assert zap_artifact is not None and zap_artifact.name == "zap-report.json"
    assert "-quickout" in zap_command
    assert str(zap_artifact) in zap_command
    assert "-silent" in zap_command


def test_structured_zap_alerts_are_normalized_without_raw_details(tmp_path: Path):
    toolchain = _module()
    payload = {
        "site": [{"alerts": [{"alert": "Example alert", "riskcode": "2", "pluginid": "10001", "url": "http://secret.invalid/path"}]}]
    }
    findings = toolchain._parse_findings("owasp-zap", "deep", "", "", tmp_path, artifact_payload=payload)
    assert len(findings) == 1
    assert findings[0]["severity"] == "medium"
    assert "secret.invalid" not in json.dumps(findings[0])
    assert findings[0]["runtime_target"] == "local_server_host_only"


def test_nmap_result_keeps_only_fixed_listener_provenance(tmp_path: Path, monkeypatch):
    toolchain = _module()
    monkeypatch.setattr(toolchain, "_live_target_probe", lambda _tool_id: {"available": True, "sanitized": True})
    monkeypatch.setattr(toolchain, "_probe_version", lambda _tool_id, _binary: {"status": "READY", "version": "7.98", "version_status": "verified"})
    monkeypatch.setattr(toolchain, "_run_command_for_tool", lambda *_args: ([sys.executable, "-c", ""], None))
    monkeypatch.setattr(toolchain, "_bounded_run", lambda *_args, **_kwargs: {"status": "PASS", "exit_code": 0, "duration_ms": 1, "stdout": "", "stderr": ""})
    result = toolchain._tool_result(
        "nmap",
        "deep",
        Path(sys.executable),
        tmp_path,
        toolchain._fixed_env(tool_id="nmap"),
    )
    assert result["port_forward_map"] == toolchain.APPROVED_PORT_FORWARD_MAP


def test_gitleaks_uses_a_fixed_excluded_tracked_file_view(tmp_path: Path, monkeypatch):
    toolchain = _module()
    fixed_source = tmp_path / "tracked-only"
    fixed_source.mkdir()
    monkeypatch.setattr(toolchain, "_gitleaks_source", lambda _workspace: fixed_source)
    command, _ = toolchain._run_command_for_tool("gitleaks", "smoke", Path(sys.executable), tmp_path, toolchain._fixed_env())
    assert command[command.index("--source") + 1] == str(fixed_source)
    assert Path(command[command.index("--source") + 1]).resolve() != toolchain.ROOT.resolve()
    assert "--no-git" in command


def test_bounded_runner_terminates_timeout_and_does_not_use_shell(tmp_path: Path, monkeypatch):
    toolchain = _module()
    monkeypatch.setattr(toolchain, "MANAGED_ROOT", tmp_path / "managed")
    calls = []
    real_popen = toolchain.subprocess.Popen

    def capture(*args, **kwargs):
        calls.append(kwargs.get("shell"))
        return real_popen(*args, **kwargs)

    monkeypatch.setattr(toolchain.subprocess, "Popen", capture)
    result = toolchain._bounded_run(
        [sys.executable, "-c", "import time; time.sleep(2)"],
        timeout_seconds=1,
        max_output_bytes=4096,
        env=toolchain._fixed_env(),
        cwd=tmp_path,
    )
    assert result["status"] == "PARTIAL"
    assert result["failure_code"] == "timed_out"
    assert calls == [False]


def test_secret_summaries_are_redacted_before_evidence():
    toolchain = _module()
    value = "Authorization: Bearer abc123 password=supersecret -----BEGIN PRIVATE KEY-----bytes-----END PRIVATE KEY-----"
    sanitized = toolchain._sanitize_text(value)
    assert "abc123" not in sanitized
    assert "supersecret" not in sanitized
    assert "BEGIN PRIVATE KEY" not in sanitized
    assert "REDACTED BY SECURITY ASSURANCE POLICY" in sanitized


def test_dependency_findings_corroborate_without_duplicate_identity():
    toolchain = _module()
    first = toolchain._base_finding(
        tool_id="osv-scanner",
        suite_id="deep",
        identity="CVE-2099-0001|demo",
        title="advisory",
        severity="medium",
        summary="bounded advisory",
        component="demo",
    )
    second = dict(first)
    second["tool"] = "grype"
    second["finding_id"] = toolchain._finding_key("grype", "CVE-2099-0001|demo")
    first["advisory_key"] = second["advisory_key"] = "CVE-2099-0001|demo"
    result = toolchain._correlate_findings([first, second])
    assert len(result) == 1
    assert result[0]["corroborating_tools"] == ["grype", "osv-scanner"]
    assert result[0]["confidence"] == "high"


def test_baseline_delta_is_stable_and_only_contains_finding_ids(tmp_path: Path, monkeypatch):
    toolchain = _module()
    toolchain.EVIDENCE_ROOT = tmp_path / "evidence"
    finding = toolchain._base_finding(
        tool_id="bandit",
        suite_id="standard",
        identity="B602|runtime.py|12",
        title="bounded finding",
        severity="low",
        summary="safe summary",
        component="runtime.py",
    )
    first = toolchain._baseline_delta([finding])
    second = toolchain._baseline_delta([finding])
    assert first["new"] == [finding["finding_id"]]
    assert second["existing"] == [finding["finding_id"]]
    stored = json.loads((tmp_path / "evidence/baseline.json").read_text())
    assert set(stored) == {"finding_digest", "finding_ids", "sanitized", "updated_at"}


def test_external_scenario_aggregation_preserves_not_assessed_and_fail_truth():
    toolchain = _module()
    definitions = toolchain._external_scenario_definitions("standard")
    ids = {item["id"] for item in definitions}
    assert "browser-origin-control-plane-bypass" in ids
    assert "owner-session-lifecycle" in ids

    rows = toolchain._aggregate_external_scenarios(
        "standard",
        [
            {
                "tool_id": "playwright-runtime",
                "scenario_results": {
                    "browser-origin-control-plane-bypass": {
                        "status": "PASS",
                        "evidence": "fixed browser evidence",
                    },
                    "owner-session-lifecycle": {
                        "status": "NOT_ASSESSED",
                        "evidence": "disposable identity required",
                    },
                },
            },
            {
                "tool_id": "pocketlab-runtime-360",
                "scenario_results": {
                    "browser-origin-control-plane-bypass": {
                        "status": "FAIL",
                        "evidence": "fixed runtime evidence",
                    }
                },
            },
        ],
    )
    by_id = {item["scenario_id"]: item for item in rows}
    assert by_id["browser-origin-control-plane-bypass"]["status"] == "FAIL"
    assert by_id["owner-session-lifecycle"]["status"] == "NOT_ASSESSED"


def test_repository_owned_adapters_are_not_promoted_as_scanner_binaries(monkeypatch):
    toolchain = _module()
    checked = {
        "status": "READY",
        "version": "1.0.0",
        "version_status": "verified",
        "checksum_status": "not_managed",
        "signature_status": "not_applicable",
    }
    monkeypatch.setattr(toolchain, "_check_one", lambda tool_id, spec: {"tool_id": tool_id, **checked})
    monkeypatch.setattr(
        toolchain,
        "_candidate",
        lambda tool_id: Path(sys.executable) if tool_id in {"pocketlab-runtime-360", "playwright-runtime"} else None,
    )
    original_registry = toolchain._registry
    registry = original_registry()
    registry["toolchain"] = {
        key: value
        for key, value in registry["toolchain"].items()
        if key in {"pocketlab-runtime-360", "playwright-runtime"}
    }
    monkeypatch.setattr(toolchain, "_registry", lambda: registry)
    result = toolchain.install_toolchain()
    assert result["status"] == "PASS"
    assert {row["action"] for row in result["tools"]} == {"repository_owned_adapter"}


def test_consolidated_expansion_tools_are_registered():
    toolchain = _module()
    registry = toolchain._registry()["toolchain"]

    expected = {
        "playwright",
        "mitmdump",
        "hurl",
        "k6",
        "websocat",
        "katana",
        "httpx",
        "tlsx",
        "tshark",
        "ffuf",
        "nats-cli",
        "playwright-runtime",
        "pocketlab-runtime-360",
    }

    assert len(registry) == 31
    assert expected.issubset(registry)


def test_consolidated_high_live_finding_is_scenario_fail():
    toolchain = _module()

    rows = toolchain._aggregate_external_scenarios(
        "standard",
        [
            {
                "tool_id": "playwright",
                "status": "PASS",
                "findings": [
                    {
                        "finding_id": "x",
                        "severity": "high",
                    }
                ],
            },
            {
                "tool_id": "playwright-runtime",
                "status": "PASS",
                "findings": [],
                "scenario_results": {
                    "browser-origin-control-plane-bypass": {
                        "status": "PASS",
                        "evidence": "fixed browser observation",
                        "reason": None,
                    }
                },
            },
        ],
    )

    target = next(
        row
        for row in rows
        if row["scenario_id"]
        == "browser-origin-control-plane-bypass"
    )

    assert target["status"] == "FAIL"


def test_webauthn_human_review_never_auto_promotes_to_pass():
    toolchain = _module()

    rows = toolchain._aggregate_external_scenarios(
        "deep",
        [
            {
                "tool_id": "playwright",
                "status": "PASS",
                "findings": [],
            }
        ],
    )

    target = next(
        row
        for row in rows
        if row["scenario_id"]
        == "webauthn-origin-rpid-mismatch"
    )

    assert target["status"] == "PARTIAL"
    assert target["human_review_required"] is True

def test_installer_classifies_all_registered_tools_without_generic_fallback():
    toolchain = _module()
    registry = toolchain._registry()["toolchain"]
    allowed = {
        "server_worker_owned",
        "repository_owned_adapter",
        "repository_dependency",
        "managed_python_tool",
        "fixed_apt_package",
        "fixed_release_asset",
        "approved_system_dependency",
        "approved_existing_tool",
    }
    classifications = {
        tool_id: toolchain._installer_classification(tool_id, spec)
        for tool_id, spec in registry.items()
    }
    assert len(classifications) == 31
    assert set(classifications.values()) <= allowed
    assert classifications["pocketlab-runtime-360"] == "repository_owned_adapter"
    assert classifications["playwright-runtime"] == "repository_owned_adapter"
    assert classifications["playwright"] == "repository_dependency"
    assert classifications["mitmdump"] == "managed_python_tool"
    assert classifications["tshark"] == "approved_system_dependency"
    assert "no_approved_install_recipe" not in inspect.getsource(toolchain.install_toolchain)


def test_all_active_dev_pc_tools_have_deterministic_installer_classification():
    toolchain = _module()
    registry = toolchain._registry()["toolchain"]
    dev_pc = {
        tool_id
        for tool_id, spec in registry.items()
        if spec.get("execution_lane") in {"dev_pc_static", "dev_pc_live_runtime"}
        and spec.get("harness_status") == "ACTIVE"
    }
    assert "cosign" in dev_pc
    assert "cosign" not in toolchain.TOOL_EXECUTION_ORDER
    assert dev_pc - {"cosign"} == set(toolchain.TOOL_EXECUTION_ORDER)
    assert all(toolchain._installer_classification(tool_id, registry[tool_id]) for tool_id in dev_pc)


def test_server_phone_tools_remain_server_owned():
    toolchain = _module()
    registry = toolchain._registry()["toolchain"]
    for tool_id in toolchain.PHONE_WORKER_TOOLS:
        assert toolchain._installer_classification(tool_id, registry[tool_id]) == "server_worker_owned"
        assert toolchain._check_one(tool_id, registry[tool_id])["status"] == "READY"


def test_repository_owned_adapters_cannot_reach_promotion(monkeypatch):
    toolchain = _module()
    registry = toolchain._registry()
    registry["toolchain"] = {
        key: value for key, value in registry["toolchain"].items()
        if key in toolchain.REPOSITORY_ADAPTERS
    }
    monkeypatch.setattr(toolchain, "_registry", lambda: registry)
    monkeypatch.setattr(
        toolchain,
        "_check_one",
        lambda tool_id, spec: {"tool_id": tool_id, "status": "READY"},
    )
    monkeypatch.setattr(
        toolchain,
        "_promote_source",
        lambda *args, **kwargs: pytest.fail("repository-owned adapter was promoted"),
    )
    result = toolchain.install_toolchain()
    assert result["status"] == "PASS"
    assert {row["action"] for row in result["tools"]} == {"repository_owned_adapter"}


def test_playwright_is_bound_to_repository_package_lock_and_does_not_install_browsers():
    toolchain = _module()
    metadata = toolchain._repository_dependency_metadata("playwright")
    registry = toolchain._registry()["toolchain"]["playwright"]
    assert metadata["status"] == "READY"
    assert metadata["version"] == "1.60.0"
    assert metadata["browser_payload_install"] is False
    assert registry["version_pin"] == "1.60.0"
    assert registry["installation_source"] == "repository_package_lock"
    assert toolchain._installer_classification("playwright", registry) == "repository_dependency"
    source = inspect.getsource(toolchain.install_toolchain)
    assert "playwright install" not in source
    assert "chromium" not in source.casefold()


def test_fixed_release_recipes_are_exact_pinned_and_checksum_bound():
    toolchain = _module()
    expected = {
        "hurl": "8.0.1",
        "k6": "2.2.0",
        "websocat": "1.14.1",
        "katana": "1.7.0",
        "httpx": "1.12.0",
        "tlsx": "1.4.0",
        "ffuf": "2.3.0",
        "nats-cli": "0.5.0",
    }
    registry = toolchain._registry()["toolchain"]
    for tool_id, version in expected.items():
        recipe = toolchain.GITHUB_RECIPES[tool_id]
        assert recipe["version"] == version
        assert registry[tool_id]["version_pin"] == version
        assert recipe["url"].startswith("https://github.com/")
        assert "/latest/" not in recipe["url"]
        assert len(recipe["sha256"]) == 64
        int(recipe["sha256"], 16)


def test_managed_python_recipe_is_exact_and_outside_repository():
    toolchain = _module()
    recipe = toolchain.MANAGED_PYTHON_RECIPES["mitmdump"]
    assert recipe["version"] == "12.2.3"
    assert recipe["wheel_url"].startswith("https://files.pythonhosted.org/")
    assert len(recipe["wheel_sha256"]) == 64
    int(recipe["wheel_sha256"], 16)
    assert toolchain._installer_classification(
        "mitmdump", toolchain._registry()["toolchain"]["mitmdump"]
    ) == "managed_python_tool"
    assert not str(toolchain.MANAGED_ROOT.resolve()).startswith(str(toolchain.ROOT.resolve()) + os.sep)


def test_fixed_archive_extraction_rejects_traversal_and_missing_binary(tmp_path: Path):
    toolchain = _module()
    malicious = tmp_path / "malicious.zip"
    with zipfile.ZipFile(malicious, "w") as bundle:
        bundle.writestr("../hurl", b"bad")
    with pytest.raises(RuntimeError, match="path_traversal"):
        toolchain._extract_fixed_binary(malicious, "zip", "hurl", tmp_path / "out-a")

    missing = tmp_path / "missing.zip"
    with zipfile.ZipFile(missing, "w") as bundle:
        bundle.writestr("README.txt", b"safe")
    with pytest.raises(RuntimeError, match="binary_not_unique"):
        toolchain._extract_fixed_binary(missing, "zip", "hurl", tmp_path / "out-b")


def test_fixed_download_checksum_mismatch_fails_closed_and_cleans_partial(tmp_path: Path, monkeypatch):
    toolchain = _module()

    class Response:
        def __init__(self):
            self._stream = io.BytesIO(b"not-the-qualified-asset")
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self, size=-1):
            return self._stream.read(size)

    class Opener:
        def open(self, request, timeout=60):
            return Response()

    monkeypatch.setattr(toolchain.urllib.request, "build_opener", lambda *args, **kwargs: Opener())
    destination = tmp_path / "asset.zip"
    with pytest.raises(RuntimeError, match="checksum_mismatch"):
        toolchain._download_fixed(
            "https://github.com/example/tool/releases/download/v1/tool.zip",
            "0" * 64,
            destination,
        )
    assert not destination.exists()
    assert not list(tmp_path.glob("*.part"))


def test_failed_release_install_does_not_write_success_receipt(tmp_path: Path, monkeypatch):
    toolchain = _module()
    monkeypatch.setattr(toolchain, "MANAGED_ROOT", tmp_path / "managed")
    recipe = {
        "version": "1.0.0",
        "url": "https://github.com/example/hurl/releases/download/v1.0.0/hurl.zip",
        "sha256": "1" * 64,
        "archive": "zip",
        "binary_name": "hurl",
        "architectures": [os.uname().machine],
        "source": "example fixed release",
        "signature_status": "test_checksum",
    }
    monkeypatch.setitem(toolchain.GITHUB_RECIPES, "hurl", recipe)

    def fake_download(url, expected_sha256, destination):
        destination.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(destination, "w") as bundle:
            bundle.writestr("README.txt", b"no binary")

    monkeypatch.setattr(toolchain, "_download_fixed", fake_download)
    with pytest.raises(RuntimeError, match="binary_not_unique"):
        toolchain._install_github("hurl")
    assert not toolchain._receipt_path("hurl").exists()


def test_healthy_fixed_tool_is_idempotent_and_not_reinstalled(tmp_path: Path, monkeypatch):
    toolchain = _module()
    monkeypatch.setattr(toolchain, "MANAGED_ROOT", tmp_path / "managed")
    binary = toolchain._managed_candidate("hurl")
    binary.parent.mkdir(parents=True)
    binary.write_text("#!/bin/sh\necho 'hurl 8.0.1'\n", encoding="utf-8")
    binary.chmod(0o755)
    receipt = {
        "actual_checksum": f"sha256:{toolchain._sha256_file(binary)}",
        "expected_checksum": f"sha256:{toolchain.GITHUB_RECIPES['hurl']['sha256']}",
        "checksum_status": "verified_archive_checksum",
        "signature_status": "github_release_asset_sha256",
        "installation_source": "fixed test release",
    }
    toolchain._write_json(toolchain._receipt_path("hurl"), receipt)
    registry = toolchain._registry()
    registry["toolchain"] = {"hurl": registry["toolchain"]["hurl"]}
    monkeypatch.setattr(toolchain, "_registry", lambda: registry)
    monkeypatch.setattr(
        toolchain,
        "_install_github",
        lambda tool_id: pytest.fail("healthy qualified tool was reinstalled"),
    )
    result = toolchain.install_toolchain()
    assert result["status"] == "PASS"
    assert result["tools"][0]["action"] == "already_qualified"


def test_fixed_recipe_repairs_only_missing_or_invalid_provenance(tmp_path: Path, monkeypatch):
    toolchain = _module()
    registry = toolchain._registry()
    registry["toolchain"] = {"hurl": registry["toolchain"]["hurl"]}
    monkeypatch.setattr(toolchain, "_registry", lambda: registry)
    monkeypatch.setattr(toolchain, "_candidate", lambda tool_id: Path(sys.executable))
    monkeypatch.setattr(
        toolchain,
        "_check_one",
        lambda tool_id, spec: {"tool_id": tool_id, "status": "READY"},
    )
    state = {"receipt": {}, "installs": 0}
    monkeypatch.setattr(toolchain, "_load_receipt", lambda tool_id: dict(state["receipt"]))

    def install(tool_id):
        state["installs"] += 1
        state["receipt"] = {
            "expected_checksum": f"sha256:{toolchain.GITHUB_RECIPES['hurl']['sha256']}",
            "actual_checksum": "sha256:test",
        }
        return dict(state["receipt"])

    monkeypatch.setattr(toolchain, "_install_github", install)
    first = toolchain.install_toolchain()
    second = toolchain.install_toolchain()
    assert first["tools"][0]["action"] == "installed_fixed_release_asset"
    assert second["tools"][0]["action"] == "already_qualified"
    assert state["installs"] == 1


@pytest.mark.parametrize("flag", ["--url", "--version", "--argv", "--target", "--subject"])
def test_installer_cli_rejects_caller_controlled_provisioning_inputs(flag: str):
    toolchain = _module()
    with pytest.raises(SystemExit):
        toolchain.main(["install", flag, "attacker-controlled"])


def test_installer_source_contains_no_privileged_or_shell_true_and_managed_paths_are_external():
    toolchain = _module()
    source = inspect.getsource(toolchain)
    assert "shell=True" not in source
    assert "sudo " not in source
    assert "| sh" not in source
    assert "| bash" not in source
    assert not str(toolchain.MANAGED_ROOT.resolve()).startswith(str(toolchain.ROOT.resolve()) + os.sep)


def test_tshark_is_explicit_host_dependency_not_privileged_auto_install(monkeypatch):
    toolchain = _module()
    registry = toolchain._registry()["toolchain"]
    monkeypatch.setattr(toolchain, "_candidate", lambda tool_id: None)
    result = toolchain._check_one("tshark", registry["tshark"])
    assert result["status"] == "NOT_APPLICABLE"
    assert result["installer_classification"] == "approved_system_dependency"
    assert "/home/" not in json.dumps(result)


def test_registry_versions_and_installer_sources_match_source_owned_recipes():
    toolchain = _module()
    registry = toolchain._registry()["toolchain"]
    for tool_id, recipe in toolchain.GITHUB_RECIPES.items():
        assert registry[tool_id]["version_pin"] == str(recipe["version"])
    for tool_id, recipe in toolchain.MANAGED_PYTHON_RECIPES.items():
        assert registry[tool_id]["version_pin"] == str(recipe["version"])
    non_worker = {
        tool_id for tool_id, spec in registry.items()
        if spec.get("execution_lane") != "server_phone_worker"
    }
    assert "cosign" in non_worker
    assert "cosign" not in toolchain.TOOL_EXECUTION_ORDER
    assert non_worker - {"cosign"} == set(toolchain.TOOL_EXECUTION_ORDER)
    assert non_worker <= set(toolchain.VERSION_ARGS)

