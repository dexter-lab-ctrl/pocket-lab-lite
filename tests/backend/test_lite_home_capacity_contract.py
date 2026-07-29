from pocket_lab_test_utils import ensure_runtime_path


def test_lite_status_preserves_home_capacity_fields():
    ensure_runtime_path()
    from api_fastapi.services.lite_status import _lite_telemetry

    result = _lite_telemetry({
        "status": "healthy",
        "cpu_temp_c": 35.2,
        "cpu_usage_percent": 7.5,
        "free_space_mb": 135_569,
        "total_space_mb": 228_000,
        "memory_usage_mb": 4_054,
        "memory_total_mb": 7_900,
        "memory_free_mb": 3_846,
    })

    assert result["free_space_mb"] == 135_569
    assert result["total_space_mb"] == 228_000
    assert result["memory_usage_mb"] == 4_054
    assert result["memory_total_mb"] == 7_900
    assert result["memory_free_mb"] == 3_846
    assert result["cpu_usage_percent"] == 7.5
    assert result["cpu_temp_c"] == 35.2


def test_lite_status_accepts_legacy_capacity_aliases():
    ensure_runtime_path()
    from api_fastapi.services.lite_status import _lite_telemetry

    result = _lite_telemetry({
        "freeSpaceMB": 10,
        "totalSpaceMB": 20,
        "memoryTotalMB": 30,
        "memoryFreeMB": 12,
    })

    assert result["free_space_mb"] == 10
    assert result["total_space_mb"] == 20
    assert result["memory_total_mb"] == 30
    assert result["memory_free_mb"] == 12
