from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "dev" / "check-lite-runtime-resilience-server-phone.sh"


def test_server_phone_runtime_preflights_fail_with_explicit_diagnostics():
    source = SCRIPT.read_text(encoding="utf-8")

    expected = (
        "Termux:Boot entry missing or not executable",
        "external runtime guardian is not running",
        "PM2 pid file missing or empty",
        "PM2 pid file does not contain a numeric PID",
        "PM2 daemon PID",
        "Lite API /health and /ready did not remain reachable",
        "pm2 jlist failed while reading Lite runtime topology",
        "Tailscale is installed but tailscaled is not running",
        "PhotoPrism is installed but proot-distro is unavailable",
        "PhotoPrism is installed but Ubuntu PRoot is unavailable",
        "PhotoPrism PM2/local/same-origin runtime did not stabilize",
    )

    for message in expected:
        assert message in source


def test_server_phone_runtime_preflights_emit_positive_progress_markers():
    source = SCRIPT.read_text(encoding="utf-8")

    for marker in (
        "PASS Termux:Boot recovery entry installed",
        "PASS external runtime guardian running",
        "PASS PM2 daemon running",
        "PASS Lite API health reachable",
        "PASS Lite API readiness reachable",
        "PASS required Lite PM2 topology online",
        "PASS every required Lite PM2 service projects its exact installed version",
        "PASS legacy Pocket Lab PM2 services absent",
    ):
        assert marker in source


def test_server_phone_pm2_topology_does_not_use_large_environment_payload():
    source = SCRIPT.read_text(encoding="utf-8")
    start = source.index("remote_read_only() {")
    end = source.index("wait_pm2_service() {", start)
    read_only = source[start:end]

    assert 'PM2_JSON="$pm2_json"' not in read_only
    assert 'json.loads(os.environ["PM2_JSON"])' not in read_only
    assert 'pm2 jlist >"$pm2_json_file"' in read_only
    assert 'python3 - "$pm2_json_file"' in read_only
    assert 'trap \'rm -f "$pm2_json_file" "${topology_check_file:-}"\' EXIT' in read_only


def test_server_phone_qualification_waits_for_stable_pm2_and_photoprism_state():
    source = SCRIPT.read_text(encoding="utf-8")
    start = source.index("remote_read_only() {")
    end = source.index("wait_pm2_service() {", start)
    read_only = source[start:end]

    assert 'topology_check_file="$pm2_tmp_root/pocketlab-pm2-topology-check.$"' in read_only
    assert 'topology_stable=0' in read_only
    assert 'POCKETLAB_PHONE_TOPOLOGY_ATTEMPTS' in read_only
    assert '[[ "$topology_stable" -ge 2 ]]' in read_only
    assert 'Lite runtime did not reach a stable PM2 topology/version projection' in read_only

    assert 'photoprism_stable=0' in read_only
    assert 'POCKETLAB_PHONE_PHOTOPRISM_STABILIZATION_SECONDS' in read_only
    assert 'pm2 jlist >"$pm2_json_file"' in read_only
    assert 'http://127.0.0.1:2342/apps/photoprism/' in read_only
    assert 'http://127.0.0.1:8443/apps/photoprism/' in read_only
    assert '[[ "$photoprism_stable" -ge 2 ]]' in read_only
    assert 'PhotoPrism PM2/local/same-origin runtime did not stabilize' in read_only


def test_fault_waiter_uses_fresh_pm2_json_and_adaptive_stabilization():
    source = SCRIPT.read_text(encoding="utf-8")
    start = source.index("wait_pm2_service() {")
    end = source.index("fault_pm2_service() {", start)
    waiter = source[start:end]

    assert 'PM2_JSON="$data"' not in waiter
    assert 'json.loads(os.environ["PM2_JSON"])' not in waiter
    assert 'pm2 jlist >"$json_file"' in waiter
    assert 'python3 - "$json_file"' in waiter
    assert 'rm -f "$json_file"' in waiter
    assert 'POCKETLAB_PHONE_PM2_SERVICE_STABILIZATION_SECONDS' in waiter
    assert 'POCKETLAB_PHONE_PM2_SERVICE_BACKOFF_MAX_SECONDS' in waiter
    assert 'backoff_seconds=2' in waiter
    assert 'stable=0' in waiter
    assert '[[ "$stable" -ge 2 ]]' in waiter
    assert 'backoff_seconds=$((backoff_seconds * 2))' in waiter
    assert 'last_status=' in waiter
    assert 'service did not reach stable online state within' in waiter


def test_fault_qualification_waits_for_contract_stability_and_generation_advancement():
    source = SCRIPT.read_text(encoding="utf-8")
    service_fault = source[source.index("fault_pm2_service() {"):source.index("wait_pm2_daemon_without_starting_it() {")]
    daemon_fault = source[source.index("runtime_required_generation_csv() {"):source.index("run_faults() {")]
    assert 'generation_before="$(ssh "$SSH_ALIAS" python3' in service_fault
    assert 'assert generation_after > generation_before' in service_fault
    assert 'item.get("health") == "ready"' in service_fault
    assert 'stable.get("stable_observations")' in service_fault
    assert 'pm2 jlist >"$json_file"' in service_fault
    assert 'pm2_id="$(ssh "$SSH_ALIAS" bash -s -- "$service"' in service_fault
    assert 'pm2 delete "$pm2_id"' in service_fault
    assert 'wait_pm2_definition_absent "$service" "$pm2_id"' in service_fault
    assert 'absent_streak=0' in source
    assert 'absent_streak >= 3' in source
    assert 'PM2 fault identity was not numeric' in service_fault
    assert 'runtime_required_generation_csv' in daemon_fault
    assert 'wait_runtime_convergence_after_daemon_recovery' in daemon_fault
    assert 'assert generation > previous_generation' in daemon_fault


def test_server_phone_qualification_uses_adaptive_api_stabilization():
    source = SCRIPT.read_text(encoding="utf-8")
    start = source.index("remote_read_only() {")
    end = source.index("wait_pm2_service() {", start)
    read_only = source[start:end]

    assert 'verification_policy="${2:-strict}"' in read_only
    assert 'POCKETLAB_PHONE_API_STABILIZATION_SECONDS' in read_only
    assert 'POCKETLAB_PHONE_API_BACKOFF_MAX_SECONDS' in read_only
    assert 'api_backoff_seconds=2' in read_only
    assert 'api_backoff_seconds=$((api_backoff_seconds * 2))' in read_only
    assert 'sock = socket.socket()' in read_only
    assert 'sock.connect(("127.0.0.1", 8080))' in read_only
    assert 'http://127.0.0.1:8080/health' in read_only
    assert 'http://127.0.0.1:8080/ready' in read_only
    assert '[[ "$api_stable" -ge 2 ]]' in read_only
    assert 'Lite API /health and /ready did not remain reachable' in read_only


def test_fault_mode_downgrades_only_final_slow_service_stabilization_to_advisory():
    source = SCRIPT.read_text(encoding="utf-8")
    faults = source[source.index("run_faults() {"):source.index("run_remote_access_fault() {")]

    assert 'remote_read_only --read-only' in faults
    assert 'remote_read_only --read-only advisory' in faults
    assert 'PASS fault injection recovery sequence completed' in faults
    assert 'ADVISORY Lite API health/readiness did not stabilize' in source
    assert 'ADVISORY PhotoPrism did not fully stabilize' in source
    assert 'All injected recovery scenarios completed' in source
    assert 'Core fault recovery completed; PhotoPrism may still be finishing PRoot/application startup.' in source


def test_photoprism_qualification_refreshes_pm2_state_and_uses_adaptive_backoff():
    source = SCRIPT.read_text(encoding="utf-8")
    start = source.index('if [[ "$photoprism_expected" == "1" ]]')
    end = source.index('if [[ "$mode" == "--post-reboot" ]]', start)
    block = source[start:end]

    assert 'POCKETLAB_PHONE_PHOTOPRISM_STABILIZATION_SECONDS' in block
    assert 'POCKETLAB_PHONE_PHOTOPRISM_BACKOFF_MAX_SECONDS' in block
    assert 'photoprism_backoff_seconds=2' in block
    assert 'pm2 jlist >"$pm2_json_file"' in block
    assert 'status == "online"' in block
    assert 'version == declared' in block
    assert 'http://127.0.0.1:2342/apps/photoprism/' in block
    assert 'http://127.0.0.1:8443/apps/photoprism/' in block
    assert 'photoprism_backoff_seconds=$((photoprism_backoff_seconds * 2))' in block
    assert '[[ "$photoprism_stable" -ge 2 ]]' in block


def test_server_phone_qualification_checks_stable_runtime_contract_and_log_policy():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "pm2-runtime-contract.json" in source
    assert "pocketlab.pm2-runtime-contract/v1" in source
    assert 'data.get("state") == "stable"' in source
    assert 'int(data.get("stable_observations") or 0) >= 2' in source
    assert 'item.get("pm2_policy_match") is True' in source
    assert 'item.get("desired_state_match") is True' in source
    assert 'log_policy.get("within_policy") is True' in source
    assert 'stable_path = runtime_dir / "stable-convergence.json"' in source
    assert 'int(item.get("pm2_restart_budget_remaining") or 0) > 0' in source
    assert 'item.get("version") == item.get("declared_version")' in source
    assert 'log_policy.get("cleanup_interval_seconds")' in source
    assert 'largest_file = max(largest_file, metadata.st_size)' in source
    assert 'pm2-log-policy.json' in source
    assert '"/api/lite/runtime"' in source
    assert '"/api/lite/recovery/details"' in source
    assert 'recovery.get("stable") is True' in source
    assert 'socket.create_connection((sys.argv[1], port), timeout=3.0)' in source
    assert 'telemetry.get("pm2_restart_budget_remaining")' in source


def test_pm2_contract_fault_mode_is_explicitly_guarded_and_uses_bounded_canaries():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "--pm2-contract-faults" in source
    assert "POCKETLAB_RUNTIME_PM2_CONTRACT_FAULTS" in source
    assert "POCKETLAB_RUNTIME_MEMORY_FAULTS" in source
    assert "48 * 1024 * 1024" in source
    assert '"max_memory_restart":"32M"' in source
    assert '"max_restarts":3' in source
    assert 'status == "waiting restart" and not pid' in source
    assert 'restarts >= max(1, configured_max - 1)' in source
    assert 'pm2 start "$tmp_root/crash.ecosystem.json" --only "$crash_name"' in source
    assert 'pm2 start "$tmp_root/memory.ecosystem.json" --only "$memory_name"' in source
    assert "write_pm2_ecosystem()" in source
    assert "pm2 sendSignal SIGTERM" in source
    assert "pocketlab-qualification-crash-loop" in source
    assert "pocketlab-qualification-graceful-stop" in source
    assert "pocketlab-qualification-memory-ceiling" in source
    assert "fault_pm2_service pocket-node-agent" in source
    assert "fault_pm2_service caddy-proxy" in source
    assert "fault_pm2_service pocket-nats" in source
    assert "generation_before" in source
    assert "generation_after > generation_before" in source
    assert "Runtime Contract did not confirm stable recovery" in source
