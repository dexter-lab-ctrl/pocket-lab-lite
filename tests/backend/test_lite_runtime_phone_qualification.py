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
        "PhotoPrism local runtime is not reachable",
        "PhotoPrism same-origin route did not remain reachable through Caddy",
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


def test_server_phone_qualification_waits_for_stable_pm2_and_caddy_state():
    source = SCRIPT.read_text(encoding="utf-8")
    start = source.index("remote_read_only() {")
    end = source.index("wait_pm2_service() {", start)
    read_only = source[start:end]

    assert 'topology_check_file="$pm2_tmp_root/pocketlab-pm2-topology-check.$"' in read_only
    assert 'topology_stable=0' in read_only
    assert 'POCKETLAB_PHONE_TOPOLOGY_ATTEMPTS' in read_only
    assert '[[ "$topology_stable" -ge 2 ]]' in read_only
    assert 'Lite runtime did not reach a stable PM2 topology/version projection' in read_only

    assert 'caddy_route_stable=0' in read_only
    assert 'POCKETLAB_PHONE_CADDY_ROUTE_ATTEMPTS' in read_only
    assert '[[ "$caddy_route_stable" -ge 2 ]]' in read_only
    assert 'PhotoPrism same-origin route did not remain reachable through Caddy' in read_only


def test_fault_waiter_streams_pm2_json_instead_of_using_environment_payload():
    source = SCRIPT.read_text(encoding="utf-8")
    start = source.index("wait_pm2_service() {")
    end = source.index("fault_pm2_service() {", start)
    waiter = source[start:end]

    assert 'PM2_JSON="$data"' not in waiter
    assert 'json.loads(os.environ["PM2_JSON"])' not in waiter
    assert 'pm2 jlist >"$json_file"' in waiter
    assert 'python3 - "$json_file"' in waiter
    assert 'rm -f "$json_file"' in waiter


def test_server_phone_qualification_uses_adaptive_api_stabilization():
    source = SCRIPT.read_text(encoding="utf-8")
    start = source.index("remote_read_only() {")
    end = source.index("wait_pm2_service() {", start)
    read_only = source[start:end]

    assert 'api_policy="${2:-strict}"' in read_only
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


def test_fault_mode_downgrades_only_final_api_stabilization_to_advisory():
    source = SCRIPT.read_text(encoding="utf-8")
    faults = source[source.index("run_faults() {"):source.index("run_remote_access_fault() {")]

    assert 'remote_read_only --read-only' in faults
    assert 'remote_read_only --read-only advisory' in faults
    assert 'PASS fault injection recovery sequence completed' in faults
    assert 'ADVISORY Lite API health/readiness did not stabilize' in source
    assert 'All injected recovery scenarios completed' in source
