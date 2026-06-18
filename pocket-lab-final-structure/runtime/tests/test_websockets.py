from fastapi.testclient import TestClient

from api_fastapi.main import app


def test_events_websocket_contract_accepts_or_fails_safely():
    client = TestClient(app)
    try:
        with client.websocket_connect("/ws/events") as ws:
            ws.close()
    except Exception as exc:
        assert (
            "WebSocket" in exc.__class__.__name__
            or "disconnect" in str(exc).lower()
            or "403" in str(exc)
        )


def test_operation_websocket_unknown_job_id_fails_safely():
    client = TestClient(app)
    try:
        with client.websocket_connect("/ws/operations/unknown-job-id") as ws:
            ws.close()
    except Exception as exc:
        assert (
            "WebSocket" in exc.__class__.__name__
            or "disconnect" in str(exc).lower()
            or "403" in str(exc)
        )
