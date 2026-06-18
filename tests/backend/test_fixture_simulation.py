from pocket_lab_test_utils import load_fixture


def test_telemetry_fixtures_match_expected_shape():
    for name in ["telemetry_normal.json", "telemetry_low_disk.json"]:
        payload = load_fixture(name)
        for key in [
            "cpu_usage_percent",
            "memory_usage_mb",
            "free_space_mb",
            "cpu_temp_c",
        ]:
            assert key in payload


def test_degraded_fixtures_cover_expected_cases():
    assert load_fixture("nats_down.json")["connected"] is False
    assert load_fixture("worker_down.json")["available"] is False
    assert (
        load_fixture("health_vault_sealed.json")["services"]["vault"]["status"]
        == "sealed"
    )
    assert load_fixture("drift_detected.json")["items"]
    assert load_fixture("release_failed.json")["status"] == "failed"
    assert load_fixture("backup_missing.json")["reason"] == "latest_backup_ref_missing"
    assert load_fixture("gatus_unhealthy.json")["overall"] == "unhealthy"
