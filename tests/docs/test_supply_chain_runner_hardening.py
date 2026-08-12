from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "scripts" / "docs" / "enterprise" / "supply_chain_automation.py"

spec = importlib.util.spec_from_file_location("pocketlab_supply_chain_automation", MODULE)
assert spec and spec.loader
supply = importlib.util.module_from_spec(spec)
spec.loader.exec_module(supply)


def _snapshot(tmp_path: Path) -> dict[str, int | str | None]:
    return {
        "temp_root": str(tmp_path),
        "temp_free_bytes": 100 * 1024**3,
        "mem_available_bytes": 8 * 1024**3,
        "swap_total_bytes": 2 * 1024**3,
        "swap_free_bytes": 2 * 1024**3,
    }


def test_supply_chain_capture_requires_shared_disk_backed_scratch(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("POCKETLAB_DEV_TMPDIR", raising=False)
    with pytest.raises(SystemExit):
        supply.configured_scratch_root()


def test_scanner_invalid_or_empty_json_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(supply, "tool_path", lambda _name: sys.executable)
    monkeypatch.setattr(supply, "ensure_capture_resources", lambda **_kwargs: _snapshot(tmp_path))
    monkeypatch.setattr(supply, "resource_snapshot", lambda: _snapshot(tmp_path))
    monkeypatch.setattr(supply, "timeout_for", lambda _step: 10)
    monkeypatch.setattr(supply, "progress_interval", lambda: 5)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    output = run_dir / "raw" / "invalid.json"

    result = supply.run_tool(
        "syft-dev",
        "python",
        ["-c", "print('not-json')"],
        output,
        allow_nonzero=False,
        run_dir=run_dir,
    )

    assert result["status"] == "failed-invalid-output"
    assert result["output_validation"] == "invalid-json"


def test_scanner_timeout_is_process_isolated_and_checkpointable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(supply, "tool_path", lambda _name: sys.executable)
    monkeypatch.setattr(supply, "ensure_capture_resources", lambda **_kwargs: _snapshot(tmp_path))
    monkeypatch.setattr(supply, "resource_snapshot", lambda: _snapshot(tmp_path))
    monkeypatch.setattr(supply, "timeout_for", lambda _step: 1)
    monkeypatch.setattr(supply, "progress_interval", lambda: 1)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    output = run_dir / "raw" / "timeout.json"

    result = supply.run_tool(
        "scancode",
        "python",
        ["-c", "import time; time.sleep(30); print('{}')"],
        output,
        allow_nonzero=False,
        run_dir=run_dir,
    )

    assert result["status"] == "timed-out"
    assert result["exit_code"] == 124
    assert result["duration_seconds"] < 10


def test_resume_only_skips_valid_completed_step(tmp_path: Path):
    output = tmp_path / "raw.json"
    output.write_text("{}\n", encoding="utf-8")
    manifest = {
        "tools": [
            {
                "step_id": "syft-dev",
                "status": "completed",
                "exit_code": 0,
            }
        ]
    }
    assert supply.step_can_resume(manifest, "syft-dev", output) is True
    output.write_text("", encoding="utf-8")
    assert supply.step_can_resume(manifest, "syft-dev", output) is False


def test_scanner_selection_is_bounded_and_adds_dependencies():
    selected = supply.selected_steps(False, False, "trivy-sbom-dev")
    assert selected == {"syft-dev", "trivy-sbom-dev"}
    assert "scancode" not in selected


def test_partial_capture_is_never_promotable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    run_dir = tmp_path / "run"
    (run_dir / "raw").mkdir(parents=True)
    (run_dir / "capture-manifest.json").write_text(
        json.dumps(
            {
                "schema_version": supply.CAPTURE_SCHEMA_VERSION,
                "runtime_capture_performed": False,
                "capture_complete": False,
                "qualification_surface": "local-or-ci-diagnostic",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(supply, "is_termux", lambda: False)
    with pytest.raises(SystemExit):
        supply.promote(run_dir)


def test_release_qualification_is_ci_only():
    workflow = (ROOT / ".github" / "workflows" / "docs-security-supply-chain.yml").read_text(encoding="utf-8")
    taskfile = (ROOT / "tasks" / "Taskfile.docs.yml").read_text(encoding="utf-8")

    assert "POCKETLAB_DEV_TMPDIR" in workflow
    assert "dev-scratch.sh run security-tools --" in workflow
    assert "--release-qualification" in workflow
    assert "--require-release-qualification" in workflow
    assert "capture-diagnostics.json" in workflow
    assert "capture-manifest.json" not in workflow.split("Upload sanitized capture diagnostics on failure", 1)[1].split("Explicitly normalize", 1)[0]
    assert "raw/" not in workflow.split("Upload sanitized qualification evidence", 1)[1]

    qualify = taskfile.split("  lite:docs:supply-chain:qualify:\n", 1)[1].split("\n  lite:", 1)[0]
    assert "gh workflow run docs-security-supply-chain.yml" in qualify
    assert "supply_chain_automation.py capture" not in qualify
    assert "git status --porcelain" in qualify
    assert "origin/main" in qualify
    assert "gh watch" not in qualify


def test_local_capture_resume_and_diagnostics_are_scratch_wrapped():
    taskfile = (ROOT / "tasks" / "Taskfile.docs.yml").read_text(encoding="utf-8")
    assert "lite:docs:supply-chain:resume:" in taskfile
    assert "lite:docs:supply-chain:status:" in taskfile
    assert "lite:docs:supply-chain:qualify:local:" in taskfile
    assert taskfile.count("dev-scratch.sh run security-tools --") >= 3
    assert "--resume" in taskfile
    assert "--only {{.SCANNER}}" in taskfile


def test_scancode_process_count_is_bounded(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("POCKETLAB_SCANCODE_PROCESSES", raising=False)
    assert supply.scancode_processes() == 2

    monkeypatch.setenv("POCKETLAB_SCANCODE_PROCESSES", "1")
    assert supply.scancode_processes() == 1

    monkeypatch.setenv("POCKETLAB_SCANCODE_PROCESSES", "4")
    assert supply.scancode_processes() == 4

    for invalid in ("0", "5", "eight"):
        monkeypatch.setenv("POCKETLAB_SCANCODE_PROCESSES", invalid)
        with pytest.raises(SystemExit):
            supply.scancode_processes()


def test_scancode_preflight_memory_scales_with_workers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("POCKETLAB_SCANCODE_PROCESSES", "2")
    monkeypatch.setattr(supply, "configured_scratch_root", lambda: tmp_path.resolve())
    monkeypatch.setattr(supply.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(
        supply,
        "resource_snapshot",
        lambda: {
            "temp_root": str(tmp_path),
            "temp_free_bytes": 100 * 1024**3,
            "mem_available_bytes": 2500 * 1024**2,
            "swap_total_bytes": 2 * 1024**3,
            "swap_free_bytes": 2 * 1024**3,
        },
    )
    with pytest.raises(SystemExit):
        supply.ensure_capture_resources(step_id="scancode")

    monkeypatch.setattr(
        supply,
        "resource_snapshot",
        lambda: {
            "temp_root": str(tmp_path),
            "temp_free_bytes": 100 * 1024**3,
            "mem_available_bytes": 4 * 1024**3,
            "swap_total_bytes": 2 * 1024**3,
            "swap_free_bytes": 2 * 1024**3,
        },
    )
    snapshot = supply.ensure_capture_resources(step_id="scancode")
    assert snapshot["mem_available_bytes"] == 4 * 1024**3
    assert supply.scancode_preflight_mem_mib() == 3072


def test_scancode_runtime_guardrail_detects_low_memory_and_swap(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("POCKETLAB_SCANCODE_MIN_RUNTIME_MEM_MIB", "1536")
    monkeypatch.setenv("POCKETLAB_SCANCODE_MIN_RUNTIME_SWAP_MIB", "256")
    healthy = {
        "mem_available_bytes": 3 * 1024**3,
        "swap_total_bytes": 2 * 1024**3,
        "swap_free_bytes": 1024 * 1024**2,
    }
    assert supply.scancode_runtime_guardrail(healthy) is None

    low_mem = dict(healthy, mem_available_bytes=1024 * 1024**2)
    assert supply.scancode_runtime_guardrail(low_mem) == "mem_available_below_1536_mib"

    low_swap = dict(healthy, swap_free_bytes=128 * 1024**2)
    assert supply.scancode_runtime_guardrail(low_swap) == "swap_free_below_256_mib"


def test_running_checkpoint_is_reconciled_to_interrupted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    manifest = {
        "capture_complete": False,
        "tools": [
            {
                "step_id": "scancode",
                "tool": "scancode",
                "status": "running",
                "child_pid": 999999,
                "child_start_time_ticks": 1,
                "attempt": 1,
            }
        ],
    }
    monkeypatch.setattr(supply, "process_identity_alive", lambda _step: False)

    assert supply.reconcile_interrupted_steps(run_dir, manifest) is True
    step = manifest["tools"][0]
    assert step["status"] == "interrupted"
    assert step["interruption_reason"] == "recorded-process-not-running"
    assert manifest["failure"]["step_id"] == "scancode"
    persisted = json.loads((run_dir / "capture-manifest.json").read_text(encoding="utf-8"))
    assert persisted["tools"][0]["status"] == "interrupted"


def test_run_capture_step_checkpoints_start_before_tool_execution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    manifest = {"tools": [], "capture_complete": False}
    monkeypatch.setattr(supply, "ensure_capture_resources", lambda **_kwargs: _snapshot(tmp_path))
    monkeypatch.setattr(supply, "timeout_for", lambda _step: 60)

    def fake_run_tool(*_args, on_started=None, **_kwargs):
        current = supply.manifest_step(manifest, "scancode")
        assert current is not None
        assert current["status"] == "starting"
        assert current["attempt"] == 1
        assert current["scanner_config"]["processes"] == 2
        assert on_started is not None
        on_started({"child_pid": 1234, "child_start_time_ticks": 88})
        running = supply.manifest_step(manifest, "scancode")
        assert running["status"] == "running"
        return {
            "step_id": "scancode",
            "tool": "scancode",
            "status": "completed",
            "exit_code": 0,
            "duration_seconds": 1.0,
        }

    monkeypatch.setattr(supply, "run_tool", fake_run_tool)
    supply.run_capture_step(
        run_dir,
        manifest,
        resume=False,
        selected={"scancode"},
        step_id="scancode",
        tool="scancode",
        argv=["--processes", "2"],
        stdout_output=None,
        expected_output=None,
        allow_nonzero=False,
        scanner_config={"processes": 2},
    )
    assert supply.manifest_step(manifest, "scancode")["status"] == "completed"


def test_ci_pins_bounded_scancode_policy():
    workflow = (ROOT / ".github" / "workflows" / "docs-security-supply-chain.yml").read_text(encoding="utf-8")
    assert "POCKETLAB_SCANCODE_PROCESSES: '2'" in workflow
    assert "POCKETLAB_SUPPLY_CHAIN_MIN_MEM_MIB_SCANCODE: '3072'" in workflow
    assert "POCKETLAB_SCANCODE_MIN_RUNTIME_MEM_MIB: '1536'" in workflow
    assert "POCKETLAB_SCANCODE_MIN_RUNTIME_SWAP_MIB: '256'" in workflow


def test_scancode_is_optional_and_disabled_by_default():
    selected = supply.selected_steps(False, False, None)
    assert "scancode" not in selected
    enabled = supply.selected_steps(False, False, None, enable_scancode=True)
    assert "scancode" in enabled


def test_local_scancode_requires_explicit_host_risk_opt_in(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("POCKETLAB_ALLOW_LOCAL_SCANCODE", raising=False)
    with pytest.raises(SystemExit):
        supply.ensure_scancode_execution_allowed(enable_scancode=True, release_qualification=False)
    monkeypatch.setenv("POCKETLAB_ALLOW_LOCAL_SCANCODE", "1")
    supply.ensure_scancode_execution_allowed(enable_scancode=True, release_qualification=False)
    monkeypatch.delenv("POCKETLAB_ALLOW_LOCAL_SCANCODE", raising=False)
    supply.ensure_scancode_execution_allowed(enable_scancode=True, release_qualification=True)


def test_optional_scancode_failure_does_not_block_required_capture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    manifest = {"tools": [], "capture_complete": False}
    monkeypatch.setattr(supply, "ensure_capture_resources", lambda **_kwargs: _snapshot(tmp_path))
    monkeypatch.setattr(supply, "timeout_for", lambda _step: 60)
    monkeypatch.setattr(
        supply,
        "run_tool",
        lambda *_args, **_kwargs: {
            "step_id": "scancode",
            "tool": "scancode",
            "status": "failed-invalid-output",
            "exit_code": -11,
            "duration_seconds": 1.0,
        },
    )
    supply.run_capture_step(
        run_dir,
        manifest,
        resume=False,
        selected={"scancode"},
        step_id="scancode",
        tool="scancode",
        argv=["--processes", "2"],
        stdout_output=None,
        expected_output=None,
        allow_nonzero=False,
        scanner_config={"processes": 2},
        required=False,
    )
    assert supply.manifest_step(manifest, "scancode")["status"] == "failed-invalid-output"
    assert manifest["optional_failures"][0]["step_id"] == "scancode"
    assert "failure" not in manifest


def test_license_inventory_keeps_package_and_deep_coverage_separate():
    sbom = {
        "components": [
            {"name": "example", "version": "1.0", "licenses": [{"license": {"id": "MIT"}}]}
        ]
    }
    trivy = {
        "Results": [
            {"Licenses": [{"Name": "Apache-2.0", "PkgName": "other", "Category": "permissive", "Severity": "LOW"}]}
        ]
    }
    without_deep = supply.license_inventory(
        sbom,
        trivy,
        {},
        scancode_requested=False,
        scancode_status=None,
    )
    assert without_deep["package_license_coverage"]["required"] is True
    assert without_deep["package_license_coverage"]["authority"] == "syft+trivy"
    assert without_deep["deep_source_license_coverage"]["status"] == "not-run"
    assert without_deep["deep_source_license_coverage"]["required"] is False
    assert without_deep["scancode_detected_expressions"] == []
    assert without_deep["trivy_detected_licenses"][0]["license"] == "Apache-2.0"

    with_deep = supply.license_inventory(
        sbom,
        trivy,
        {"files": [{"license_detections": [{"license_expression": "MIT"}]}]},
        scancode_requested=True,
        scancode_status="completed",
    )
    assert with_deep["deep_source_license_coverage"]["status"] == "observed"
    assert with_deep["scancode_detected_expressions"][0]["expression"] == "MIT"


def test_required_trivy_capture_enables_standard_license_scanner():
    source = (ROOT / "scripts" / "docs" / "enterprise" / "supply_chain_automation.py").read_text(encoding="utf-8")
    assert '"vuln,misconfig,secret,license"' in source
    assert "--license-full" not in source


def test_ci_deep_license_scan_is_explicit_opt_in():
    workflow = (ROOT / ".github" / "workflows" / "docs-security-supply-chain.yml").read_text(encoding="utf-8")
    assert "deep_license_scan:" in workflow
    assert "default: false" in workflow
    assert "--enable-scancode" in workflow


def test_taskfile_exposes_explicit_scancode_opt_in_without_making_it_default():
    taskfile = (ROOT / "tasks" / "Taskfile.docs.yml").read_text(encoding="utf-8")
    capture = taskfile.split("  lite:docs:supply-chain:capture:\n", 1)[1].split("\n  lite:", 1)[0]
    resume = taskfile.split("  lite:docs:supply-chain:resume:\n", 1)[1].split("\n  lite:", 1)[0]
    qualify = taskfile.split("  lite:docs:supply-chain:qualify:\n", 1)[1].split("\n  lite:", 1)[0]
    assert "ENABLE_SCANCODE" in capture
    assert "ENABLE_SCANCODE" in resume
    assert "DEEP_LICENSE_SCAN" in qualify
    assert "deep_license_scan" in qualify


def test_scorecard_repository_slug_normalizes_supported_github_origins(monkeypatch: pytest.MonkeyPatch):
    for origin in (
        "https://github.com/dexter-lab-ctrl/pocket-lab-lite.git\n",
        "git@github.com:dexter-lab-ctrl/pocket-lab-lite.git\n",
        "ssh://git@github.com/dexter-lab-ctrl/pocket-lab-lite.git\n",
    ):
        monkeypatch.setattr(supply.subprocess, "check_output", lambda *_args, **_kwargs: origin)
        assert supply.scorecard_repository_slug() == "github.com/dexter-lab-ctrl/pocket-lab-lite"


def test_scorecard_repository_slug_rejects_non_github_origin(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        supply.subprocess,
        "check_output",
        lambda *_args, **_kwargs: "https://gitlab.example.invalid/team/repo.git\n",
    )
    with pytest.raises(SystemExit):
        supply.scorecard_repository_slug()


def test_scorecard_auth_env_prefers_existing_token_without_exposing_other_values(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token-value")
    monkeypatch.delenv("GITHUB_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("GH_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    assert supply.scorecard_auth_env() == {"GITHUB_AUTH_TOKEN": "test-token-value"}


def test_scorecard_summary_preserves_provider_unavailable_controls_without_scores():
    payload = {
        "checks": [
            {"name": "Pinned-Dependencies", "score": 8},
            {"name": "Dangerous-Workflow", "score": 10},
            {"name": "Token-Permissions", "score": 9},
        ]
    }
    summary = supply.scorecard_summary(payload)
    by_name = {item["name"]: item for item in summary["checks"]}
    assert summary["status"] == "observed-with-provider-limitations"
    assert set(summary["compatible_checks"]) == {
        "Pinned-Dependencies",
        "Dangerous-Workflow",
        "Token-Permissions",
    }
    for name in ("Branch-Protection", "Signed-Releases", "Maintained"):
        assert by_name[name]["status"] == "provider-unavailable"
        assert by_name[name]["score"] is None
        assert by_name[name]["blocking"] is False
        assert "not inferred" in by_name[name]["claim"]


def test_scorecard_runner_uses_repo_commit_and_compatible_checks_only():
    source = MODULE.read_text(encoding="utf-8")
    assert '"--repo"' in source
    assert '"--commit"' in source
    assert 'scorecard_checks = ",".join(SCORECARD_COMPATIBLE_CHECKS)' in source
    assert '"--local", "."' not in source
    assert "SCORECARD_PROVIDER_UNAVAILABLE_CHECKS" in source


def test_scorecard_ci_auth_is_child_environment_only():
    workflow = (ROOT / ".github" / "workflows" / "docs-security-supply-chain.yml").read_text(encoding="utf-8")
    assert "GITHUB_AUTH_TOKEN: ${{ github.token }}" in workflow
    assert "gh auth token" not in workflow


def test_scorecard_check_contract_rejects_fabricated_provider_unavailable_scores(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    scorecard = supply.scorecard_summary(
        {
            "checks": [
                {"name": "Pinned-Dependencies", "score": 8},
                {"name": "Dangerous-Workflow", "score": 10},
                {"name": "Token-Permissions", "score": 9},
            ]
        }
    )
    branch = next(item for item in scorecard["checks"] if item["name"] == "Branch-Protection")
    assert branch["reason"] == "scorecard-provider-unsupported-request-type"
    assert branch["score"] is None
    assert branch["blocking"] is False
