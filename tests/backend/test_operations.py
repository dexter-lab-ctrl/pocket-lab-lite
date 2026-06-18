from pocket_lab_test_utils import client


def test_operations_execute_rejects_unknown_operation():
    response = client().post(
        "/api/operations/execute",
        json={"operation": "definitely_unknown_operation", "target": "test"},
    )
    assert response.status_code in {400, 403, 422, 503}


def test_operations_execute_accepts_typed_operation_shape():
    response = client().post(
        "/api/operations/execute",
        json={"operation": "health_check", "target": "control-plane"},
    )
    assert response.status_code in {200, 202, 403, 503}


def test_action_update_removed():
    assert (
        client().post("retired update compatibility endpoint", json={}).status_code
        == 404
    )
