from __future__ import annotations

from pocket_lab_test_utils import client, load_fixture


FORBIDDEN_LEGACY_TERMS = (
    "legacy_intent",
    "sync_bash",
    "tofu_deploy",
    "/api/action/update",
    "local fallback",
)


def test_degraded_fixture_catalog_covers_release_blocker_scenarios():
    """The fault gate must cover the release-blocking degraded-mode classes."""
    assert load_fixture("nats_down.json")["connected"] is False
    assert load_fixture("worker_down.json")["available"] is False
    assert load_fixture("health_vault_sealed.json")["overall"] == "degraded"
    assert load_fixture("health_vault_sealed.json")["services"]["vault"]["status"] == "sealed"
    assert load_fixture("telemetry_low_disk.json")["free_space_mb"] < load_fixture("telemetry_normal.json")["free_space_mb"]
    assert load_fixture("release_failed.json")["status"] == "failed"
    assert load_fixture("backup_missing.json")["reason"] == "latest_backup_ref_missing"
    assert load_fixture("gatus_unhealthy.json")["overall"] == "unhealthy"
    assert any(agent.get("status") == "offline" for agent in load_fixture("fleet_agents.json").get("agents", []))


def test_write_path_fails_closed_without_legacy_fallback_language(monkeypatch):
    """Writes must never claim local execution when NATS/JetStream is unavailable."""
    monkeypatch.setenv("POCKETLAB_NATS_REQUIRED", "1")
    monkeypatch.setenv("POCKETLAB_NATS_REQUIRE_JETSTREAM", "1")

    response = client().post(
        "/api/operations/execute",
        json={
            "operation": "git_sync",
            "target": {"kind": "gitops_repo", "ref": "pocket_lab_iac"},
            "params": {"source": "fault-gate"},
        },
    )

    assert response.status_code in {202, 403, 503}
    body = response.text.lower()
    for term in FORBIDDEN_LEGACY_TERMS:
        assert term not in body

    if response.status_code == 202:
        data = response.json()
        assert data.get("execution_mode") == "worker"
        assert str(data.get("command_subject", "")).startswith("pocketlab.commands.")
    else:
        assert "nats" in body or "jetstream" in body or "worker" in body or "direct" in body


def test_ready_endpoint_reports_degraded_or_ready_without_legacy_terms():
    response = client().get("/ready")
    assert response.status_code in {200, 503}
    text = response.text.lower()
    assert any(word in text for word in ("ready", "degraded", "nats", "health_engine"))
    for term in FORBIDDEN_LEGACY_TERMS:
        assert term not in text
