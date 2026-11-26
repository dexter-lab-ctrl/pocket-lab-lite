from pocket_lab_test_utils import client


def test_retired_vault_operation_names_are_rejected_without_execution():
    for op in ["rotate_secret", "secret_read_dynamic"]:
        response = client().post(
            "/api/operations/execute", json={"operation": op, "target": "test"}
        )
        assert response.status_code == 410
        detail = response.json()
        assert detail["status"] == "retired"
        assert detail["accepted"] is False
        assert detail["executed"] is False
        assert detail["historical_record_preserved"] is True


def test_vault_response_does_not_expose_root_material():
    response = client().post(
        "/api/operations/execute",
        json={"operation": "rotate_secret", "target": "photoprism"},
    )
    assert response.status_code == 410
    assert "root_token" not in response.text
    assert "unseal_key" not in response.text


def test_retired_vault_preview_is_rejected():
    response = client().post(
        "/api/operations/preview",
        json={"operation": "secret_read_dynamic", "target": "test"},
    )
    assert response.status_code == 410
    assert response.json()["reason_code"] == "legacy_control_plane_retired"
