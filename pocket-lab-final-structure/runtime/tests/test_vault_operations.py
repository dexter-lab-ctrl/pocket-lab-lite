from pocket_lab_test_utils import client


def test_vault_operation_names_are_typed():
    for op in ["rotate_secret", "secret_read_dynamic"]:
        response = client().post(
            "/api/operations/execute", json={"operation": op, "target": "test"}
        )
        assert response.status_code in {200, 202, 400, 403, 422, 503}
        assert "retired compatibility intent field" not in response.text
        assert "retired sync compatibility task" not in response.text
        assert "retired IaC deploy compatibility task" not in response.text


def test_vault_response_does_not_expose_root_material():
    response = client().post(
        "/api/operations/execute",
        json={"operation": "rotate_secret", "target": "photoprism"},
    )
    assert "root_token" not in response.text
    assert "unseal_key" not in response.text
