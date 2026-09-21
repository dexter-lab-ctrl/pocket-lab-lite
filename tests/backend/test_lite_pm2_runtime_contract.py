from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SUPERVISORS = ROOT / "pocket-lab-final-structure" / "runtime" / "supervisors"


def _load(name: str):
    path = SUPERVISORS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
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
            "POCKETLAB_PROCESS_SPEC_HASH": f"spec-{service.name}",
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

    monkeypatch.setenv("POCKETLAB_PM2_LOG_FILE_CEILING_BYTES", str(1024 * 1024))
    monkeypatch.setenv("POCKETLAB_PM2_LOG_MAX_AGE_SECONDS", str(24 * 60 * 60))
    evidence = contract.enforce_log_policy(
        tmp_path / "state",
        now=now,
        pm2_home=pm2_home,
        force=True,
    )
    assert oversized.stat().st_size == 0
    assert not old.exists()
    assert evidence["files_truncated"] >= 1
    assert evidence["files_removed"] >= 1
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
    assert projected["services"][0]["status"] == "Recovered recently"
    assert "PM2" not in json.dumps(projected)
