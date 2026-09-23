from __future__ import annotations

import importlib.util
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
SUPERVISORS = ROOT / "pocket-lab-final-structure" / "runtime" / "supervisors"


def _load(name: str):
    path = SUPERVISORS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    if name == "pocketlab_runtime_contract":
        original = module.build_runtime_contract

        def build_with_expected_spec_evidence(**kwargs):
            state_root = Path(kwargs["state_root"])
            processes = list(kwargs["processes"])
            desired_specs_override = kwargs.pop("_test_desired_spec_hashes", None)
            desired_launches_override = kwargs.pop("_test_desired_launch_hashes", None)
            evidence_path = state_root / "runtime" / "desired-process-specs.json"
            evidence_path.parent.mkdir(parents=True, exist_ok=True)
            desired_specs = (
                desired_specs_override
                if isinstance(desired_specs_override, dict)
                else {
                    str(item.get("name")): str((item.get("pm2_env") or {}).get("POCKETLAB_PROCESS_SPEC_HASH") or "")
                    for item in processes
                }
            )
            desired_launches = (
                desired_launches_override
                if isinstance(desired_launches_override, dict)
                else {
                    str(item.get("name")): module.launch_fingerprint(
                        str((item.get("pm2_env") or {}).get("pm_exec_path") or ""),
                        str((item.get("pm2_env") or {}).get("exec_interpreter") or ""),
                    )
                    for item in processes
                }
            )
            evidence_path.write_text(json.dumps({
                "schema": "pocketlab.pm2-desired-process-specs/v1",
                "schema_version": 1,
                "processes": desired_specs,
                "launches": desired_launches,
                "sanitized": True,
            }), encoding="utf-8")
            return original(processes=processes, **{key: value for key, value in kwargs.items() if key != "processes"})

        module.build_runtime_contract = build_with_expected_spec_evidence
    return module


def _managed_processes(registry, *, now: float, restart_time: int = 0):
    processes = []
    for service in registry.managed_service_specs(include_photoprism=False):
        policy = registry.policy_for(service.name)
        assert policy is not None
        env = {
            "status": "online",
            "version": "1.0.0+sha.test",
            "POCKETLAB_SERVICE_VERSION": "1.0.0+sha.test",
            "POCKETLAB_PROCESS_SPEC_HASH": hashlib.sha256(f"spec:{service.name}".encode()).hexdigest(),
            "pm_exec_path": f"/opt/pocketlab/{service.name}/exec",
            "exec_interpreter": "python3",
            "POCKETLAB_PM2_POLICY_FINGERPRINT": policy.fingerprint(),
            "min_uptime": policy.min_uptime_seconds * 1000,
            "max_restarts": policy.max_restarts,
            "kill_timeout": policy.kill_timeout_ms,
            "restart_delay": policy.restart_delay_ms or 0,
            "exp_backoff_restart_delay": policy.exp_backoff_restart_delay_ms or 0,
            "max_memory_restart": (
                policy.max_memory_restart_mb * 1024 * 1024
                if policy.max_memory_restart_mb is not None
                else 0
            ),
            "autorestart": policy.autorestart,
            "pm_uptime": int((now - 600) * 1000),
            "restart_time": restart_time,
            "unstable_restarts": 0,
            # Secrets may exist in PM2 env but must never reach contract evidence.
            "POCKETLAB_NATS_PASSWORD": "do-not-project-this",
        }
        processes.append({
            "name": service.name,
            "pm2_env": env,
            "monit": {"memory": 64 * 1024 * 1024, "cpu": 1},
        })
    return processes


def _healthy_probes():
    return {
        "nats": "ready",
        "opa": "ready",
        "api": "ready",
        "caddy": "ready",
        "photoprism_local": "ready",
        "photoprism_route": "ready",
    }


def test_http_health_probe_rejects_client_and_server_error_responses(monkeypatch):
    _load("pocketlab_runtime_registry")
    contract = _load("pocketlab_runtime_contract")

    class Response:
        def __init__(self, status):
            self.status = status

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(contract.urllib.request, "urlopen", lambda *_args, **_kwargs: Response(204))
    assert contract._http_ready("http://127.0.0.1:8181/health") is True
    for status in (401, 404, 503):
        monkeypatch.setattr(
            contract.urllib.request,
            "urlopen",
            lambda *_args, selected=status, **_kwargs: Response(selected),
        )
        assert contract._http_ready("http://127.0.0.1:8181/health") is False


def test_pm2_policy_registry_covers_required_lite_runtime():
    registry = _load("pocketlab_runtime_registry")
    expected = {
        "pocket-nats",
        "pocket-opa",
        "pocket-worker",
        "pocket-api",
        "pocket-node-agent",
        "caddy-proxy",
        "pocket-telemetry",
        "pocketlab-core-supervisor",
        "pocketlab-runtime-reconciler",
        "pocketlab-app-photoprism",
    }
    assert set(registry.PM2_POLICIES) == expected
    assert registry.policy_for("pocket-api").max_memory_restart_mb == 384
    assert registry.policy_for("pocket-worker").max_memory_restart_mb == 320
    assert registry.policy_for("pocket-nats").max_memory_restart_mb is None
    assert registry.policy_for("pocketlab-app-photoprism").max_memory_restart_mb is None
    assert all(registry.policy_for(name).min_uptime_seconds >= 10 for name in expected)
    assert all(registry.policy_for(name).max_restarts >= 1 for name in expected)
    assert all(registry.policy_for(name).kill_timeout_ms >= 1000 for name in expected)


def test_policy_fingerprint_changes_only_for_desired_policy(monkeypatch):
    registry = _load("pocketlab_runtime_registry")
    baseline = registry.policy_fingerprint("pocket-api", {})
    runtime_only = registry.policy_fingerprint(
        "pocket-api",
        {
            "PM2_PID": "999",
            "PM2_CPU": "87",
            "POCKETLAB_RUNTIME_OBSERVED_RSS_MB": "9999",
        },
    )
    changed = registry.policy_fingerprint(
        "pocket-api",
        {"POCKETLAB_PM2_POCKET_API_KILL_TIMEOUT_MS": "17000"},
    )
    assert baseline == runtime_only
    assert changed != baseline


def test_policy_match_detects_pm2_drift():
    registry = _load("pocketlab_runtime_registry")
    policy = registry.policy_for("pocket-api")
    env = {
        "autorestart": True,
        "min_uptime": policy.min_uptime_seconds * 1000,
        "max_restarts": policy.max_restarts,
        "kill_timeout": policy.kill_timeout_ms,
        "max_memory_restart": policy.max_memory_restart_mb * 1024 * 1024,
        "restart_delay": 0,
        "exp_backoff_restart_delay": policy.exp_backoff_restart_delay_ms,
    }
    matches, fields = registry.policy_match("pocket-api", env)
    assert matches is True
    assert fields == ()
    env["kill_timeout"] = policy.kill_timeout_ms + 1
    matches, fields = registry.policy_match("pocket-api", env)
    assert matches is False
    assert "kill_timeout_ms" in fields


def test_ecosystem_config_maps_policy_without_serializing_environment_secrets(tmp_path):
    registry = _load("pocketlab_runtime_registry")
    config = registry.ecosystem_config_for(
        "pocket-api",
        "/opt/pocket-api/server.py",
        interpreter="python3",
        cwd=str(tmp_path),
        app_args=["--safe-mode", "true"],
        environ={"POCKETLAB_NATS_PASSWORD": "test-secret-value"},
    )
    app = config["apps"][0]
    assert app["script"] == "/opt/pocket-api/server.py"
    assert app["interpreter"] == "python3"
    assert app["cwd"] == str(tmp_path)
    assert app["args"] == ["--safe-mode", "true"]
    assert app["min_uptime"] == "20s"
    assert app["max_restarts"] == 6
    assert app["kill_timeout"] == 15000
    assert app["max_memory_restart"] == "384M"
    assert app["exp_backoff_restart_delay"] == 250
    assert "env" not in app
    assert "test-secret-value" not in json.dumps(config)


def test_ecosystem_config_bounds_process_arguments():
    registry = _load("pocketlab_runtime_registry")
    with pytest.raises(ValueError, match="arguments"):
        registry.ecosystem_config_for("demo", "python3", app_args=["x"] * 129)
    with pytest.raises(ValueError, match="cwd"):
        registry.ecosystem_config_for("demo", "python3", cwd="relative/path")


def test_ecosystem_config_runs_termux_commands_as_binaries_without_node_interpreter():
    registry = _load("pocketlab_runtime_registry")
    for executable in ("nats-server", "/data/data/com.termux/files/usr/bin/opa", "bash"):
        app = registry.ecosystem_config_for("demo", executable)["apps"][0]
        assert app["interpreter"] == "none"
    javascript = registry.ecosystem_config_for("demo", "worker.js")["apps"][0]
    assert "interpreter" not in javascript


def test_launch_fingerprint_resolves_relative_script_and_tracks_interpreter(tmp_path):
    registry = _load("pocketlab_runtime_registry")
    relative = registry.launch_fingerprint("worker.py", "python3", str(tmp_path))
    absolute = registry.launch_fingerprint(str(tmp_path / "worker.py"), "python3")
    wrong_path = registry.launch_fingerprint(str(tmp_path / "other.py"), "python3")
    wrong_interpreter = registry.launch_fingerprint(str(tmp_path / "worker.py"), "python")
    assert relative == absolute
    assert relative != wrong_path
    assert relative != wrong_interpreter


def test_ecosystem_javascript_uses_runtime_environment_without_serializing_it(tmp_path):
    registry_path = SUPERVISORS / "pocketlab_runtime_registry.py"
    completed = subprocess.run(
        [
            sys.executable,
            str(registry_path),
            "--ecosystem-js",
            "pocket-api",
            "--script",
            "/opt/pocket-api/server.py",
            "--interpreter",
            "python3",
            "--cwd",
            str(tmp_path),
            "--app-args-json",
            '["--serve"]',
        ],
        env={**os.environ, "POCKETLAB_NATS_PASSWORD": "test-secret-value"},
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "app.env = process.env;" in completed.stdout
    assert "test-secret-value" not in completed.stdout
    encoded_app = completed.stdout.split("const app = ", 1)[1].split(";\napp.env", 1)[0]
    app = json.loads(encoded_app)
    assert app["name"] == "pocket-api"
    assert app["min_uptime"] == "20s"
    assert app["args"] == ["--serve"]


def test_memory_overrides_are_bounded_and_do_not_cap_nats_or_photoprism():
    registry = _load("pocketlab_runtime_registry")
    assert registry.policy_for(
        "pocket-api", {"POCKETLAB_PM2_POCKET_API_MAX_MEMORY_RESTART": "512M"}
    ).max_memory_restart_mb == 512

    for value in ("0", "32M", "2G", "999999999999999999999999999999999999999999999999999999M", "bad"):
        assert registry.policy_for(
            "pocket-api", {"POCKETLAB_PM2_POCKET_API_MAX_MEMORY_RESTART": value}
        ).max_memory_restart_mb == 384

    for name in ("pocket-nats", "pocketlab-app-photoprism"):
        key = f"POCKETLAB_PM2_{name.upper().replace('-', '_')}_MAX_MEMORY_RESTART"
        assert registry.policy_for(name, {key: "64M"}).max_memory_restart_mb is None


@pytest.mark.parametrize(
    ("scenario", "expected_reason"),
    (
        ("version", "version_drift"),
        ("policy", "pm2_policy_drift"),
        ("uptime", "minimum_stable_uptime_not_met"),
        ("dependency", "dependency_not_ready"),
        ("health", "semantic_health_not_ready"),
        ("memory", "memory_policy_exceeded"),
        ("memory_unknown", "memory_observation_unavailable"),
        ("stopped", "process_not_online"),
        ("budget", "restart_budget_exhausted"),
        ("pm2_budget", "restart_budget_exhausted"),
        ("spec", "desired_state_mismatch"),
        ("legacy", "forbidden_legacy_service_present"),
    ),
)
def test_online_process_drift_and_unhealthy_inputs_never_converge(
    tmp_path, monkeypatch, scenario, expected_reason
):
    registry = _load("pocketlab_runtime_registry")
    contract = _load("pocketlab_runtime_contract")
    monkeypatch.setenv("PM2_HOME", str(tmp_path / "pm2"))
    now = 1_700_050_000.0
    processes = _managed_processes(registry, now=now)
    health = _healthy_probes()
    legacy_present = False
    target = next(item for item in processes if item["name"] == "pocket-api")
    env = target["pm2_env"]

    if scenario == "version":
        env["version"] = "1.0.0+sha.old"
    elif scenario == "policy":
        env["kill_timeout"] += 1
    elif scenario == "uptime":
        env["pm_uptime"] = int(now * 1000)
    elif scenario == "dependency":
        health["nats"] = "not_ready"
    elif scenario == "health":
        health["api"] = "not_ready"
    elif scenario == "memory":
        target["monit"]["memory"] = 385 * 1024 * 1024
    elif scenario == "memory_unknown":
        target["monit"].pop("memory")
    elif scenario == "stopped":
        env["status"] = "stopped"
    elif scenario == "budget":
        env["status"] = "errored"
        env["unstable_restarts"] = env["max_restarts"]
    elif scenario == "pm2_budget":
        env["unstable_restarts"] = env["max_restarts"]
    elif scenario == "spec":
        env.pop("POCKETLAB_PROCESS_SPEC_HASH")
    elif scenario == "legacy":
        processes.append({"name": "vault", "pm2_env": {"status": "online"}})
        legacy_present = True

    result = contract.build_runtime_contract(
        processes=processes,
        state_root=tmp_path / "state",
        photoprism_expected=False,
        now=now,
        health=health,
    )
    assert result["stable"] is False
    assert result["state"] != "stable"
    if scenario == "legacy":
        assert legacy_present is True
        assert result["legacy_lite_services_present"] == ["vault"]
        assert expected_reason in result["reason_codes"]
    else:
        service = next(item for item in result["services"] if item["process"] == "pocket-api")
        assert expected_reason in service["reason_codes"]


def test_restart_generation_is_stable_across_repeated_observation_and_pm2_counter_reset(
    tmp_path, monkeypatch
):
    registry = _load("pocketlab_runtime_registry")
    contract = _load("pocketlab_runtime_contract")
    monkeypatch.setenv("PM2_HOME", str(tmp_path / "pm2"))
    now = 1_700_075_000.0
    processes = _managed_processes(registry, now=now, restart_time=4)

    initial = contract.build_runtime_contract(
        processes=processes,
        state_root=tmp_path / "state",
        photoprism_expected=False,
        now=now,
        health=_healthy_probes(),
    )
    api = next(item for item in initial["services"] if item["process"] == "pocket-api")
    assert api["restart_generation"] == 4

    repeated = contract.build_runtime_contract(
        processes=processes,
        state_root=tmp_path / "state",
        photoprism_expected=False,
        now=now + 10,
        health=_healthy_probes(),
    )
    repeated_api = next(item for item in repeated["services"] if item["process"] == "pocket-api")
    assert repeated_api["restart_generation"] == 4

    restarted = _managed_processes(registry, now=now + 20, restart_time=0)
    restarted_api_process = next(item for item in restarted if item["name"] == "pocket-api")
    restarted_api_process["pm2_env"]["pm_uptime"] = int((now + 20) * 1000)
    after_reset = contract.build_runtime_contract(
        processes=restarted,
        state_root=tmp_path / "state",
        photoprism_expected=False,
        now=now + 20,
        health=_healthy_probes(),
    )
    reset_api = next(item for item in after_reset["services"] if item["process"] == "pocket-api")
    assert reset_api["restart_generation"] == 5
    assert reset_api["recent_restarts"] == 5


def test_restart_window_ages_out_events_without_erasing_generation(tmp_path, monkeypatch):
    registry = _load("pocketlab_runtime_registry")
    contract = _load("pocketlab_runtime_contract")
    monkeypatch.setenv("PM2_HOME", str(tmp_path / "pm2"))
    monkeypatch.setenv("POCKETLAB_RUNTIME_RESTART_WINDOW_SECONDS", "300")
    now = 1_700_090_000.0
    first = _managed_processes(registry, now=now)
    contract.build_runtime_contract(
        processes=first,
        state_root=tmp_path / "state",
        photoprism_expected=False,
        now=now,
        health=_healthy_probes(),
    )
    restarted = _managed_processes(registry, now=now + 10, restart_time=1)
    restarted_api_process = next(item for item in restarted if item["name"] == "pocket-api")
    restarted_api_process["pm2_env"]["pm_uptime"] = int((now + 10) * 1000)
    contract.build_runtime_contract(
        processes=restarted,
        state_root=tmp_path / "state",
        photoprism_expected=False,
        now=now + 10,
        health=_healthy_probes(),
    )
    aged = contract.build_runtime_contract(
        processes=restarted,
        state_root=tmp_path / "state",
        photoprism_expected=False,
        now=now + 400,
        health=_healthy_probes(),
    )
    api = next(item for item in aged["services"] if item["process"] == "pocket-api")
    assert api["restart_generation"] == 1
    assert api["recent_restarts"] == 0


def test_runtime_contract_requires_two_stable_observations(tmp_path, monkeypatch):
    registry = _load("pocketlab_runtime_registry")
    contract = _load("pocketlab_runtime_contract")
    monkeypatch.setenv("PM2_HOME", str(tmp_path / "pm2"))
    monkeypatch.setenv("POCKETLAB_RUNTIME_STABLE_OBSERVATION_SECONDS", "5")
    now = 1_700_000_000.0
    processes = _managed_processes(registry, now=now)

    first = contract.build_runtime_contract(
        processes=processes,
        state_root=tmp_path / "state",
        photoprism_expected=False,
        now=now,
        health=_healthy_probes(),
    )
    assert first["state"] == "converging"
    assert first["stable"] is False

    second = contract.build_runtime_contract(
        processes=processes,
        state_root=tmp_path / "state",
        photoprism_expected=False,
        now=now + 6,
        health=_healthy_probes(),
    )
    assert second["state"] == "stable"
    assert second["stable"] is True
    assert second["stable_observations"] >= 2
    assert all(
        item["desired_state_match"] and item["pm2_policy_match"]
        for item in second["services"]
        if item["required"]
    )


def test_restart_generation_change_between_observations_resets_stability(tmp_path, monkeypatch):
    registry = _load("pocketlab_runtime_registry")
    contract = _load("pocketlab_runtime_contract")
    monkeypatch.setenv("PM2_HOME", str(tmp_path / "pm2"))
    monkeypatch.setenv("POCKETLAB_RUNTIME_STABLE_OBSERVATION_SECONDS", "5")
    now = 1_700_125_000.0
    stable = _managed_processes(registry, now=now)
    contract.build_runtime_contract(
        processes=stable,
        state_root=tmp_path / "state",
        photoprism_expected=False,
        now=now,
        health=_healthy_probes(),
    )
    restarted = _managed_processes(registry, now=now + 30, restart_time=1)
    api_process = next(item for item in restarted if item["name"] == "pocket-api")
    api_process["pm2_env"]["pm_uptime"] = int((now + 6) * 1000)
    after_restart = contract.build_runtime_contract(
        processes=restarted,
        state_root=tmp_path / "state",
        photoprism_expected=False,
        now=now + 30,
        health=_healthy_probes(),
    )
    assert after_restart["stable"] is False
    assert after_restart["stable_observations"] == 1

    stable_again = contract.build_runtime_contract(
        processes=restarted,
        state_root=tmp_path / "state",
        photoprism_expected=False,
        now=now + 36,
        health=_healthy_probes(),
    )
    assert stable_again["stable"] is True
    assert stable_again["stable_observations"] >= 2


def test_stable_observation_count_is_capped_at_the_required_evidence(tmp_path, monkeypatch):
    registry = _load("pocketlab_runtime_registry")
    contract = _load("pocketlab_runtime_contract")
    monkeypatch.setenv("PM2_HOME", str(tmp_path / "pm2"))
    now = 1_700_150_000.0
    processes = _managed_processes(registry, now=now)
    result = {}

    for observation in range(8):
        result = contract.build_runtime_contract(
            processes=processes,
            state_root=tmp_path / "state",
            photoprism_expected=False,
            now=now + observation * 30,
            health=_healthy_probes(),
        )

    assert result["stable"] is True
    assert result["stable_observations"] == result["required_stable_observations"]


def test_restart_generation_advances_and_is_bounded(tmp_path, monkeypatch):
    registry = _load("pocketlab_runtime_registry")
    contract = _load("pocketlab_runtime_contract")
    monkeypatch.setenv("PM2_HOME", str(tmp_path / "pm2"))
    now = 1_700_100_000.0

    contract.build_runtime_contract(
        processes=_managed_processes(registry, now=now, restart_time=0),
        state_root=tmp_path / "state",
        photoprism_expected=False,
        now=now,
        health=_healthy_probes(),
    )
    after = contract.build_runtime_contract(
        processes=_managed_processes(registry, now=now + 10, restart_time=1),
        state_root=tmp_path / "state",
        photoprism_expected=False,
        now=now + 10,
        health=_healthy_probes(),
    )
    api = next(item for item in after["services"] if item["process"] == "pocket-api")
    assert api["restart_generation"] == 1
    assert api["recent_restarts"] == 1
    ledger = json.loads((tmp_path / "state" / "runtime" / "restart-ledger.json").read_text())
    assert len(ledger["services"]["pocket-api"]["recent_restart_epochs"]) <= 16


def test_restart_budget_exhaustion_is_a_first_class_state(tmp_path, monkeypatch):
    registry = _load("pocketlab_runtime_registry")
    contract = _load("pocketlab_runtime_contract")
    monkeypatch.setenv("PM2_HOME", str(tmp_path / "pm2"))
    now = 1_700_200_000.0
    processes = _managed_processes(registry, now=now)
    target = next(item for item in processes if item["name"] == "pocket-node-agent")
    target["pm2_env"]["status"] = "errored"
    target["pm2_env"]["max_restarts"] = 3
    target["pm2_env"]["unstable_restarts"] = 3
    result = contract.build_runtime_contract(
        processes=processes,
        state_root=tmp_path / "state",
        photoprism_expected=False,
        now=now,
        health=_healthy_probes(),
    )
    assert result["state"] == "restart_budget_exhausted"
    node = next(item for item in result["services"] if item["process"] == "pocket-node-agent")
    assert "restart_budget_exhausted" in node["reason_codes"]
    assert node["pm2_restart_budget_remaining"] == 0


def test_runtime_contract_requires_current_desired_process_spec_hash(tmp_path, monkeypatch):
    registry = _load("pocketlab_runtime_registry")
    contract = _load("pocketlab_runtime_contract")
    monkeypatch.setenv("PM2_HOME", str(tmp_path / "pm2"))
    now = 1_700_250_000.0
    processes = _managed_processes(registry, now=now)
    result = contract.build_runtime_contract(
        processes=processes,
        state_root=tmp_path / "state",
        photoprism_expected=False,
        now=now,
        health=_healthy_probes(),
        _test_desired_spec_hashes={
            item["name"]: (
                "f" * 64
                if item["name"] == "pocket-api"
                else item["pm2_env"]["POCKETLAB_PROCESS_SPEC_HASH"]
            )
            for item in processes
        },
    )
    api = next(item for item in result["services"] if item["process"] == "pocket-api")
    assert api["desired_state_match"] is False
    assert "desired_state_mismatch" in api["reason_codes"]
    assert result["stable"] is False


def test_runtime_contract_rejects_launch_path_drift_even_when_hash_matches(tmp_path, monkeypatch):
    registry = _load("pocketlab_runtime_registry")
    contract = _load("pocketlab_runtime_contract")
    monkeypatch.setenv("PM2_HOME", str(tmp_path / "pm2"))
    now = 1_700_275_000.0
    processes = _managed_processes(registry, now=now)
    desired_launches = {
        item["name"]: registry.launch_fingerprint(
            item["pm2_env"]["pm_exec_path"], item["pm2_env"]["exec_interpreter"]
        )
        for item in processes
    }
    api_process = next(item for item in processes if item["name"] == "pocket-api")
    api_process["pm2_env"]["pm_exec_path"] = "/opt/pocketlab/pocketlab-runtime-reconciler/exec"

    result = contract.build_runtime_contract(
        processes=processes,
        state_root=tmp_path / "state",
        photoprism_expected=False,
        now=now,
        health=_healthy_probes(),
        _test_desired_launch_hashes=desired_launches,
    )
    api = next(item for item in result["services"] if item["process"] == "pocket-api")
    assert api["desired_state_match"] is False
    assert api["launch_spec_match"] is False
    assert "desired_state_mismatch" in api["reason_codes"]
    assert result["stable"] is False


def test_runtime_contract_never_projects_pm2_secret_values(tmp_path, monkeypatch):
    registry = _load("pocketlab_runtime_registry")
    contract = _load("pocketlab_runtime_contract")
    monkeypatch.setenv("PM2_HOME", str(tmp_path / "pm2"))
    now = 1_700_300_000.0
    result = contract.build_runtime_contract(
        processes=_managed_processes(registry, now=now),
        state_root=tmp_path / "state",
        photoprism_expected=False,
        now=now,
        health=_healthy_probes(),
    )
    encoded = json.dumps(result, sort_keys=True)
    assert "do-not-project-this" not in encoded
    assert "POCKETLAB_NATS_PASSWORD" not in encoded
    assert result["sanitized"] is True


def test_pm2_log_policy_is_bounded_idempotent_and_metadata_only(tmp_path, monkeypatch):
    contract = _load("pocketlab_runtime_contract")
    pm2_home = tmp_path / "pm2"
    logs = pm2_home / "logs"
    logs.mkdir(parents=True)
    oversized = logs / "pocket-api-out.log"
    oversized.write_bytes(b"x" * (1024 * 1024 + 32))
    old = logs / "old-error.log"
    old.write_bytes(b"sensitive-old-log-content")
    now = 1_700_400_000.0
    os.utime(old, (now - 3 * 24 * 60 * 60, now - 3 * 24 * 60 * 60))
    active_old = logs / "pocket-api-out-7.log"
    active_old.write_bytes(b"active-old-log-content")
    os.utime(active_old, (now - 3 * 24 * 60 * 60, now - 3 * 24 * 60 * 60))
    active_inode = active_old.stat().st_ino

    monkeypatch.setenv("POCKETLAB_PM2_LOG_FILE_CEILING_BYTES", str(1024 * 1024))
    monkeypatch.setenv("POCKETLAB_PM2_LOG_MAX_AGE_SECONDS", str(24 * 60 * 60))
    evidence = contract.enforce_log_policy(
        tmp_path / "state",
        now=now,
        pm2_home=pm2_home,
        active_log_paths=[active_old],
        force=True,
    )
    assert oversized.stat().st_size == 0
    assert not old.exists()
    assert active_old.exists()
    assert active_old.stat().st_ino == active_inode
    assert active_old.stat().st_size == 0
    assert evidence["files_truncated"] >= 2
    assert evidence["files_removed"] >= 1
    assert evidence["within_policy"] is True
    assert evidence["scan_complete"] is True
    assert evidence["pm2_log_largest_file_bytes"] <= evidence["pm2_log_file_ceiling_bytes"]
    assert "pm2_log_oldest_file_age_seconds" in evidence
    assert evidence["contains_log_contents"] is False
    assert "sensitive-old-log-content" not in json.dumps(evidence)

    cached = contract.enforce_log_policy(
        tmp_path / "state",
        now=now + 30,
        pm2_home=pm2_home,
        force=False,
    )
    assert cached["cleanup_performed"] is False
    assert cached["cleanup_epoch"] == evidence["cleanup_epoch"]


def test_pm2_log_policy_rejects_log_directory_symlink_and_ignores_file_symlinks(tmp_path):
    contract = _load("pocketlab_runtime_contract")
    outside = tmp_path / "outside.log"
    outside.write_text("sensitive", encoding="utf-8")
    pm2_home = tmp_path / "pm2"
    logs = pm2_home / "logs"
    logs.mkdir(parents=True)
    (logs / "escaped.log").symlink_to(outside)

    evidence = contract.enforce_log_policy(
        tmp_path / "state", now=1_700_500_000.0, pm2_home=pm2_home, force=True
    )
    assert evidence["files_observed"] == 0
    assert outside.read_text(encoding="utf-8") == "sensitive"

    linked_home = tmp_path / "linked-pm2"
    linked_home.mkdir()
    (linked_home / "logs").symlink_to(logs)
    with pytest.raises(ValueError, match="pm2_log_dir_symlink_rejected"):
        contract.enforce_log_policy(
            tmp_path / "other-state", now=1_700_500_000.0, pm2_home=linked_home, force=True
        )


def test_pm2_log_policy_handles_empty_logs_and_bounds_environment_overrides(tmp_path, monkeypatch):
    contract = _load("pocketlab_runtime_contract")
    for key, value in (
        ("POCKETLAB_PM2_LOG_CEILING_BYTES", "1"),
        ("POCKETLAB_PM2_LOG_FILE_CEILING_BYTES", "999999999999999999999999999999999999999999999999999999"),
        ("POCKETLAB_PM2_LOG_MAX_AGE_SECONDS", "bad"),
        ("POCKETLAB_PM2_LOG_CLEANUP_INTERVAL_SECONDS", "0"),
    ):
        monkeypatch.setenv(key, value)
    evidence = contract.enforce_log_policy(
        tmp_path / "state", now=1_700_600_000.0, pm2_home=tmp_path / "empty-pm2", force=True
    )
    assert evidence["pm2_log_bytes"] == 0
    assert evidence["within_policy"] is True
    assert evidence["pm2_log_ceiling_bytes"] == 8 * 1024 * 1024
    assert evidence["pm2_log_file_ceiling_bytes"] == 64 * 1024 * 1024
    assert evidence["pm2_log_max_age_seconds"] == contract.DEFAULT_LOG_MAX_AGE_SECONDS
    assert evidence["cleanup_interval_seconds"] == 300
    assert evidence["pm2_log_bytes"] <= evidence["pm2_log_ceiling_bytes"]


def test_public_runtime_projection_uses_lite_friendly_recovery_language():
    contract = _load("pocketlab_runtime_contract")
    projected = contract.public_projection({
        "schema_version": 1,
        "state": "stable",
        "stable": True,
        "reason_codes": [],
        "observed_at": "2026-09-21T00:00:00Z",
        "services": [{
            "process": "pocket-api",
            "role": "control-api",
            "stable": True,
            "restart_generation": 2,
            "recent_restarts": 1,
            "restart_budget_remaining": 2,
            "recovered_at": "2026-09-21T00:00:00Z",
            "reason_codes": [],
        }],
        "remote_access": {"state": "not_ready"},
        "log_policy": {"within_policy": True},
    })
    assert projected["summary"] == "System running normally"
    assert projected["schema"] == contract.SCHEMA_ID
    assert projected["services"][0]["status"] == "Recovered recently"
    assert "PM2" not in json.dumps(projected)
