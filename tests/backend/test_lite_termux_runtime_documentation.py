from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RUNTIME_DIR = ROOT / "scripts/docs/runtime"
FIXTURE_DIR = ROOT / "tests/fixtures/runtime/termux"

sys.path.insert(0, str(RUNTIME_DIR))

from normalize_termux_runtime import normalize_capture  # noqa: E402
from runtime_common import (  # noqa: E402
    BASELINE_SCHEMA_PATH,
    RAW_SCHEMA_PATH,
    SANITIZED_SCHEMA_PATH,
    read_json,
    runtime_mismatches,
    validate_json,
)
from runtime_redaction import RuntimeSafetyError, assert_safe, forbidden_categories  # noqa: E402


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_runtime_schemas_and_promoted_unavailable_baseline_are_valid():
    raw = read_json(FIXTURE_DIR / "raw-capture-a.json")
    validate_json(raw, RAW_SCHEMA_PATH)
    sanitized = normalize_capture(raw)
    validate_json(sanitized, SANITIZED_SCHEMA_PATH)
    baseline = read_json(ROOT / "architecture/runtime-baselines/server-phone.json")
    validate_json(baseline, BASELINE_SCHEMA_PATH)
    assert baseline["verification"]["runtime_verification_state"] == "unavailable"
    assert baseline["semantic_fingerprint"]


def test_normalization_is_byte_deterministic_for_volatile_capture_changes():
    first = normalize_capture(read_json(FIXTURE_DIR / "raw-capture-a.json"))
    second = normalize_capture(read_json(FIXTURE_DIR / "raw-capture-b.json"))
    assert json.dumps(first, sort_keys=True, separators=(",", ":")) == json.dumps(
        second, sort_keys=True, separators=(",", ":")
    )


def test_real_semantic_runtime_change_changes_output_and_reports_mismatch():
    raw = read_json(FIXTURE_DIR / "raw-capture-a.json")
    expected = normalize_capture(raw)
    raw["probes"]["pm2"]["processes"] = [
        item for item in raw["probes"]["pm2"]["processes"] if item["name"] != "pocket-worker"
    ]
    changed = normalize_capture(raw)
    assert changed["semantic_fingerprint"] != expected["semantic_fingerprint"]
    assert changed["verification"]["runtime_verification_state"] == "mismatch"
    assert any("services.worker" in item for item in changed["verification"]["unresolved_mismatches"])


@pytest.mark.parametrize(
    "payload",
    [
        {"note": "100.64.1.2"},
        {"note": "192.168.1.20"},
        {"note": "fd7a:115c:a1e0::1"},
        {"note": "server.example.ts.net"},
        {"username": "operator"},
        {"serial": "R58N123456789"},
        {"note": "/data/data/com.termux/files/home/pocket-lab-lite"},
        {"note": "/storage/emulated/0/DCIM/private.jpg"},
        {"note": "/safe/certs/server.key"},
        {"note": "-----BEGIN OPENSSH PRIVATE KEY-----"},
        {"note": "api_key=abcdef123456"},
        {"note": "nats://worker:password@example.invalid:4222"},
        {"note": "invite_token=abcdef123456"},
        {"note": "password=hunter2"},
        {"note": "Bearer abcdefghijklmnop"},
        {"note": "Cookie=sessionvalue"},
        {"note": "https://user:password@example.invalid/path"},
    ],
)
def test_redaction_matrix_fails_closed_without_echoing_sensitive_values(payload):
    categories = forbidden_categories(payload)
    assert categories
    with pytest.raises(RuntimeSafetyError) as exc:
        assert_safe(payload)
    message = str(exc.value)
    for value in payload.values():
        assert str(value) not in message


def test_phone_probe_is_streamed_allowlisted_read_only_and_bounded():
    probe = (RUNTIME_DIR / "termux_runtime_probe.sh").read_text(encoding="utf-8")
    capture = (RUNTIME_DIR / "capture_termux_runtime.sh").read_text(encoding="utf-8")
    assert "ssh" in capture and "'sh -s --'" in capture
    assert "< \"$SCRIPT_DIR/termux_runtime_probe.sh\"" in capture
    assert "MAX_CAPTURE_BYTES" in probe
    assert "timeout=" in probe
    assert "pm2\", \"jlist" in probe
    assert "PRAGMA integrity_check" in probe
    assert "SELECT name FROM sqlite_master" in probe
    assert "SELECT *" not in probe
    assert "printenv" not in probe
    assert not re.search(
        r"\b(?:rm|mv|kill|pkill)\b|pm2\s+(?:restart|stop|delete|save)|"
        r"(?:pkg|apt)\s+install|curl\s+.*(?:--upload-file|-T)|wget\s+.*--post-file|\beval\b",
        probe,
    )
    assert 'run(["truncate"' not in probe


def test_ssh_setup_is_managed_private_key_only_strict_and_idempotent_by_contract():
    setup = (RUNTIME_DIR / "setup_termux_ssh.sh").read_text(encoding="utf-8")
    for value in (
        "--prepare-key", "--check", "--configure", "--dry-run", "--discover", "--fingerprint",
        "BatchMode yes", "StrictHostKeyChecking yes", "PasswordAuthentication no",
        "PreferredAuthentications publickey", "ConnectTimeout 8", "BEGIN POCKET LAB LITE",
        "ssh-keygen -q -t ed25519", "ssh-keyscan -T 5", "runtime_ssh_candidates.py",
    ):
        assert value in setup
    assert "eval " not in setup
    assert "ssh-copy-id" not in setup
    assert "pm2 restart" not in setup
    result = subprocess.run(
        ["bash", str(RUNTIME_DIR / "setup_termux_ssh.sh"), "--help"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    assert "--configure" in result.stdout


def test_taskfile_dependency_order_live_opt_in_and_mkdocs_navigation():
    taskfile = (ROOT / "tasks/Taskfile.docs.yml").read_text(encoding="utf-8")
    for task in (
        "lite:runtime:ssh:setup", "lite:runtime:ssh:check", "lite:runtime:termux:capture",
        "lite:runtime:termux:inspect", "lite:runtime:termux:validate", "lite:runtime:termux:diff",
        "lite:runtime:termux:promote", "lite:runtime:termux:clean",
        "lite:docs:runtime:generate", "lite:docs:runtime:check",
    ):
        assert f"  {task}:" in taskfile
    generate_block = taskfile.split("  lite:docs:generate:", 1)[1].split("  lite:docs:check:", 1)[0]
    order = [
        generate_block.index("lite:contracts:generate"),
        generate_block.index("lite:docs:platform:generate"),
        generate_block.index("lite:docs:runtime:generate"),
        generate_block.index("lite:docs:architecture:generate"),
        generate_block.index("lite:docs:development:generate"),
        generate_block.index("lite:docs:production:generate"),
    ]
    assert order == sorted(order)
    assert "LITE_RUNTIME_PROMOTE=1" in (RUNTIME_DIR / "promote_termux_runtime.py").read_text()
    mkdocs = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    for page in (
        "generated/development/runtime-verification.md",
        "generated/production/android-termux-runtime.md",
        "generated/production/services-pm2-runtime.md",
        "generated/production/remote-access-runtime.md",
    ):
        assert page in mkdocs


def test_generator_depends_only_on_promoted_baseline_and_is_current(tmp_path):
    generator = load_module("termux_runtime_generator_test", RUNTIME_DIR / "generate_termux_runtime_docs.py")
    first = generator.build_outputs()
    second = generator.build_outputs()
    assert first == second
    assert generator.check_outputs(first) == 0
    # A volatile local capture must not alter tracked generation.
    local = ROOT / ".pocketlab-dev/runtime-captures/test/sanitized"
    local.mkdir(parents=True, exist_ok=True)
    (local / "termux-runtime.json").write_text((FIXTURE_DIR / "raw-capture-a.json").read_text())
    try:
        assert generator.build_outputs() == first
    finally:
        import shutil
        shutil.rmtree(ROOT / ".pocketlab-dev/runtime-captures/test", ignore_errors=True)
    for path, content in first.items():
        assert not forbidden_categories(content), path


def test_runtime_architecture_verifier_never_creates_components_and_reports_unavailable():
    verifier = load_module("runtime_architecture_verifier_test", RUNTIME_DIR / "runtime_architecture_verifier.py")
    result = verifier.verify_runtime_components()
    model = json.loads((ROOT / "architecture/metadata/pocket-lab-architecture.json").read_text())
    assert result["canonical_component_count"] == len(model["components"])
    assert {item["component_id"] for item in result["components"]} == set(model["components"])
    selected = [item for item in result["components"] if item["runtime_selector"]]
    assert selected
    assert all(item["classification"] == "runtime-unavailable" for item in selected)


def test_promotion_requires_opt_in_and_failure_preserves_previous_baseline(tmp_path, monkeypatch):
    promote = load_module("termux_runtime_promote_test", RUNTIME_DIR / "promote_termux_runtime.py")
    capture_root = tmp_path / "captures"
    sanitized = capture_root / "20260804T100000Z-test/sanitized/termux-runtime.json"
    sanitized.parent.mkdir(parents=True)
    normalized = normalize_capture(read_json(FIXTURE_DIR / "raw-capture-a.json"))
    sanitized.write_text(json.dumps(normalized, indent=2, sort_keys=True) + "\n")
    baseline_path = tmp_path / "server-phone.json"
    previous = (ROOT / "architecture/runtime-baselines/server-phone.json").read_text()
    baseline_path.write_text(previous)
    monkeypatch.setattr(promote, "CAPTURE_ROOT", capture_root)
    monkeypatch.setattr(promote, "BASELINE_PATH", baseline_path)
    monkeypatch.delenv("LITE_RUNTIME_PROMOTE", raising=False)
    with pytest.raises(RuntimeError):
        promote.promote()
    monkeypatch.setenv("LITE_RUNTIME_PROMOTE", "1")
    with pytest.raises(OSError):
        promote.promote(simulate_failure_after_backup=True)
    assert baseline_path.read_text() == previous



def test_promotion_mismatch_gate_includes_non_service_runtime_relationships():
    candidate = normalize_capture(read_json(FIXTURE_DIR / "raw-capture-a.json"))
    candidate["verification"]["unresolved_mismatches"] = ["routes.api-lite: required route mismatch"]
    assert "routes.api-lite: required route mismatch" in runtime_mismatches(candidate)

def test_cleanup_is_idempotent_and_removes_raw_layers(tmp_path, monkeypatch):
    promote = load_module("termux_runtime_clean_test", RUNTIME_DIR / "promote_termux_runtime.py")
    capture_root = tmp_path / "captures"
    for index in range(3):
        raw = capture_root / f"2026080{index}T000000Z-test/raw"
        raw.mkdir(parents=True)
        (raw / "termux-runtime.json").write_text("{}")
    monkeypatch.setattr(promote, "CAPTURE_ROOT", capture_root)
    monkeypatch.setenv("LITE_RUNTIME_MAX_CAPTURES", "2")
    assert promote.clean() == 0
    assert promote.clean() == 0
    assert not list(capture_root.glob("*/raw"))
    assert len([path for path in capture_root.iterdir() if path.is_dir()]) <= 2


def test_promoted_and_generated_artifacts_have_no_volatile_or_sensitive_fields():
    forbidden_keys = {
        "capture_started_at", "capture_duration_ms", "pid", "uptime", "memory_bytes",
        "restart_timestamp", "username", "hostname", "address", "fqdn", "serial",
        "certificate_path", "token", "password", "command_line", "environment",
    }
    paths = [ROOT / "architecture/runtime-baselines/server-phone.json", *sorted((ROOT / "contracts/generated/runtime").glob("*.json"))]
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        stack = [payload]
        keys = set()
        while stack:
            value = stack.pop()
            if isinstance(value, dict):
                keys.update(value)
                stack.extend(value.values())
            elif isinstance(value, list):
                stack.extend(value)
        assert not (keys & forbidden_keys), (path, keys & forbidden_keys)
        assert_safe(payload, context=str(path))


def test_private_ssh_candidate_ranking_is_deterministic_and_rejects_public_targets():
    candidates = load_module("runtime_ssh_candidates_test", RUNTIME_DIR / "runtime_ssh_candidates.py")
    text = "\n".join([
        "203.0.113.9", "192.168.10.50", "127.0.0.1", "100.99.2.3",
        "169.254.10.2", "10.0.0.8", "100.99.2.3",
    ])
    assert candidates.ranked_ipv4_candidates(text) == ["100.99.2.3", "10.0.0.8", "192.168.10.50"]
    assert candidates.ranked_ipv4_candidates("") == []
    assert candidates.is_safe_target("server.example.ts.net")
    assert candidates.is_safe_target("fd00::10")
    assert not candidates.is_safe_target("8.8.8.8")
    assert not candidates.is_safe_target("127.0.0.1")
    assert not candidates.is_safe_target("169.254.1.1")


def test_probe_registry_and_pm2_raw_capture_are_explicit_and_allowlisted():
    probe = (RUNTIME_DIR / "termux_runtime_probe.sh").read_text(encoding="utf-8")
    assert "PROBE_REGISTRY" in probe
    for field in ("capabilities", "timeout", "max_output_bytes", "parser", "sanitizer", "required", "failure"):
        assert f'"{field}"' in probe
    assert "APPROVED_PM2_NAMES" in probe
    assert "approved_pm2_name(name)" in probe
    raw = read_json(FIXTURE_DIR / "raw-capture-a.json")
    assert all("process_id" in item for item in raw["probes"]["pm2"]["processes"])
    sanitized = normalize_capture(raw)
    assert "process_id" not in json.dumps(sanitized)
    assert sanitized["messaging"]["jetstream_state"] == "enabled"
    assert sanitized["datastores"][0]["integrity"] == "ok"
    assert sanitized["runtime_relationships"][0]["recovery_capability"] == "supervised"


def test_schema_rejects_unknown_properties_unsupported_revision_and_oversized_arrays():
    raw = read_json(FIXTURE_DIR / "raw-capture-a.json")
    unknown = json.loads(json.dumps(raw))
    unknown["unexpected"] = True
    with pytest.raises(ValueError, match="schema validation failed"):
        validate_json(unknown, RAW_SCHEMA_PATH)
    unsupported = json.loads(json.dumps(raw))
    unsupported["schema_revision"] = 999
    with pytest.raises(ValueError, match="unsupported schema revision"):
        validate_json(unsupported, RAW_SCHEMA_PATH)
    oversized = json.loads(json.dumps(raw))
    oversized["probes"]["pm2"]["processes"] *= 20
    with pytest.raises(ValueError, match="schema validation failed"):
        validate_json(oversized, RAW_SCHEMA_PATH)


@pytest.mark.parametrize(
    ("mutator", "expected_fragment"),
    [
        (lambda raw: raw["probes"]["pm2"]["processes"].__setitem__(slice(None), [item for item in raw["probes"]["pm2"]["processes"] if item["name"] != "pocket-api"]), "services.lite-api"),
        (lambda raw: raw["probes"]["pm2"]["processes"].__setitem__(slice(None), [item for item in raw["probes"]["pm2"]["processes"] if item["name"] != "pocket-worker"]), "services.worker"),
        (lambda raw: raw["probes"]["nats"].update({"listener_present": False, "expected_client_port_present": False, "bind_scope": "missing"}), "services.nats"),
        (lambda raw: (raw["probes"]["agent_supervisor"].update({"core_supervisor_present": False, "recovery_capability": "unavailable"}), raw["probes"]["pm2"]["processes"].__setitem__(slice(None), [item for item in raw["probes"]["pm2"]["processes"] if item["name"] != "pocketlab-core-supervisor"])), "services.core-supervisor"),
        (lambda raw: raw["probes"]["caddy"]["routes"].update({"api_lite": False, "api_upstream_kind": "missing"}), "routes.api-lite"),
        (lambda raw: raw["probes"]["sqlite"].update({"integrity": "failed", "state": "partial"}), "services.sqlite"),
    ],
)
def test_required_runtime_semantic_failures_change_fingerprint_and_fail_closed(mutator, expected_fragment):
    original = read_json(FIXTURE_DIR / "raw-capture-a.json")
    baseline = normalize_capture(json.loads(json.dumps(original)))
    changed_raw = json.loads(json.dumps(original))
    mutator(changed_raw)
    changed = normalize_capture(changed_raw)
    assert changed["semantic_fingerprint"] != baseline["semantic_fingerprint"]
    assert changed["verification"]["runtime_verification_state"] == "mismatch"
    assert any(expected_fragment in item for item in changed["verification"]["unresolved_mismatches"])


@pytest.mark.parametrize(
    "mutator",
    [
        lambda raw: raw["probes"]["tailscale"].update({"state": "missing", "command_variant": "missing", "daemon_running": False, "ipv4_ready": False, "private_connectivity_ready": False, "peer_reachability": "unknown"}),
        lambda raw: raw["probes"]["proot_apps"].update({"state": "missing", "proot_present": False, "ubuntu_present": False, "photoprism_present": False, "photoprism_pm2_present": False, "photoprism_route_present": False}),
        lambda raw: raw["probes"]["pm2"]["processes"].__setitem__(slice(None), [item for item in raw["probes"]["pm2"]["processes"] if item["name"] != "pocketlab-app-photoprism"]),
    ],
)
def test_optional_runtime_changes_are_visible_without_deleting_canonical_components(mutator):
    raw = read_json(FIXTURE_DIR / "raw-capture-a.json")
    first = normalize_capture(json.loads(json.dumps(raw)))
    changed_raw = json.loads(json.dumps(raw))
    mutator(changed_raw)
    changed = normalize_capture(changed_raw)
    assert changed["semantic_fingerprint"] != first["semantic_fingerprint"]
    assert {item["id"] for item in changed["services"]} == {item["id"] for item in first["services"]}


def test_ssh_contract_is_wsl_only_requires_verified_port_and_managed_markers():
    setup = (RUNTIME_DIR / "setup_termux_ssh.sh").read_text(encoding="utf-8")
    assert "--prepare-key" in setup
    assert "must run from the WSL2 repository terminal" in setup
    assert "--port or POCKETLAB_TERMUX_SSH_PORT is required" in setup
    assert 'PORT_VALUE="${PORT_VALUE:-8022}"' not in setup
    assert "configured WSL public key is missing" in setup
    assert "managed SSH marker block is not configured" in setup
    assert "an unmanaged SSH alias with this name already exists" in setup
    assert "noninteractive config writes require --yes" in setup
    assert "Write the verified managed SSH alias block" in setup
    assert "runtime_ssh_candidates.py" in setup


def test_atomic_write_failure_preserves_existing_file(tmp_path, monkeypatch):
    common = load_module("runtime_common_atomic_test", RUNTIME_DIR / "runtime_common.py")
    target = tmp_path / "baseline.json"
    target.write_text("previous\n", encoding="utf-8")
    original_replace = common.os.replace

    def fail_replace(_source, _target):
        raise OSError("disk-full-simulation")

    monkeypatch.setattr(common.os, "replace", fail_replace)
    with pytest.raises(OSError, match="disk-full-simulation"):
        common.atomic_write(target, "replacement\n")
    assert target.read_text(encoding="utf-8") == "previous\n"
    monkeypatch.setattr(common.os, "replace", original_replace)


def test_normal_checks_do_not_capture_or_promote_live_runtime():
    docs_tasks = (ROOT / "tasks/Taskfile.docs.yml").read_text(encoding="utf-8")
    lite_tasks = (ROOT / "tasks/Taskfile.lite.yml").read_text(encoding="utf-8")
    check_block = docs_tasks.split("  lite:docs:check:", 1)[1].split("  lite:test:docs:", 1)[0]
    assert "lite:runtime:termux:capture" not in check_block
    assert "lite:runtime:termux:promote" not in check_block
    lite_check = lite_tasks.split("  lite:check:", 1)[1].split("  lite:check:release:", 1)[0]
    assert "runtime:termux:capture" not in lite_check
    assert "runtime:termux:promote" not in lite_check


def test_tracked_source_has_no_generated_cache_or_local_runtime_evidence():
    tracked = subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True).splitlines()
    assert not any("__pycache__" in item or item.endswith(".pyc") for item in tracked)
    assert not any(item.startswith(".pocketlab-dev/") for item in tracked)
    assert not any(item.endswith((".orig", ".rej")) for item in tracked)


def test_nats_probe_uses_layered_termux_safe_runtime_evidence():
    probe = (RUNTIME_DIR / "termux_runtime_probe.sh").read_text(encoding="utf-8")
    assert 'socket.create_connection(("127.0.0.1", 4222), timeout=2.0)' in probe
    assert "_nats_config_semantics" in probe
    assert "_fleet_server_nats_observation" in probe
    assert 'device.get("protected_server_host") is True or device.get("role") == "server_host"' in probe
    assert 'dependencies.get("nats_tailnet_reachable") is True' in probe
    assert '"listener_tool_visible": listener_tool_visible' in probe
    assert '"local_listener_reachable": local_listener_reachable' in probe
    assert '"fleet_listener_configured": fleet_listener_configured' in probe
    assert '"fleet_connectivity_observed": fleet_connectivity_observed' in probe
    assert "authorization" not in probe.split("def _nats_config_semantics", 1)[1].split("def _fleet_server_nats_observation", 1)[0]


def _nats_fixture(**updates):
    raw = read_json(FIXTURE_DIR / "raw-capture-a.json")
    raw["probes"]["nats"].update(updates)
    return raw


def test_nats_netstat_invisible_tcp_and_all_interface_config_still_verify():
    raw = _nats_fixture(
        listener_tool_visible=False,
        local_listener_reachable=True,
        listener_present=True,
        expected_client_port_present=True,
        fleet_listener_configured=True,
        fleet_connectivity_observed=True,
        bind_scope="private-or-all",
        state="ok",
    )
    normalized = normalize_capture(raw)
    assert normalized["messaging"]["client_listener_presence"] == "present"
    assert normalized["messaging"]["bind_scope"] == "private-or-all"
    assert normalized["verification"]["runtime_verification_state"] == "verified"
    assert not runtime_mismatches(normalized)


def test_nats_fleet_api_unavailable_does_not_override_local_and_config_truth():
    raw = _nats_fixture(
        listener_tool_visible=False,
        local_listener_reachable=True,
        listener_present=True,
        expected_client_port_present=True,
        fleet_listener_configured=True,
        fleet_connectivity_observed=None,
        bind_scope="private-or-all",
        state="ok",
    )
    normalized = normalize_capture(raw)
    assert normalized["verification"]["runtime_verification_state"] == "verified"
    assert not runtime_mismatches(normalized)


def test_nats_loopback_only_config_fails_closed_for_fleet_listener():
    raw = _nats_fixture(
        listener_tool_visible=False,
        local_listener_reachable=True,
        listener_present=True,
        expected_client_port_present=False,
        fleet_listener_configured=False,
        fleet_connectivity_observed=False,
        bind_scope="loopback",
        state="partial",
    )
    normalized = normalize_capture(raw)
    assert normalized["verification"]["runtime_verification_state"] == "mismatch"
    assert any("fleet listener not verified" in item for item in runtime_mismatches(normalized))


def test_nats_tcp_failure_remains_missing_even_when_config_claims_fleet_bind():
    raw = _nats_fixture(
        listener_tool_visible=False,
        local_listener_reachable=False,
        listener_present=False,
        expected_client_port_present=False,
        fleet_listener_configured=True,
        fleet_connectivity_observed=True,
        bind_scope="private-or-all",
        state="partial",
    )
    normalized = normalize_capture(raw)
    assert normalized["services"][[item["id"] for item in normalized["services"]].index("nats")]["presence"] == "missing"
    assert any("services.nats" in item for item in runtime_mismatches(normalized))


def test_nats_capture_schema_contains_only_sanitized_boolean_observations():
    schema = read_json(RAW_SCHEMA_PATH)
    nats = schema["$defs"]["nats"]
    for field in (
        "listener_tool_visible",
        "local_listener_reachable",
        "fleet_listener_configured",
        "fleet_connectivity_observed",
    ):
        assert field in nats["required"]
    forbidden = {"raw_config", "fleet_payload", "address", "hostname", "credentials", "authorization"}
    assert not forbidden.intersection(nats["properties"])
    validate_json(read_json(FIXTURE_DIR / "raw-capture-a.json"), RAW_SCHEMA_PATH)
