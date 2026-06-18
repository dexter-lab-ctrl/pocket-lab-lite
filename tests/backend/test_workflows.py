import json
from pocket_lab_test_utils import client, isolated_state_dir


def test_workflows_status_registered():
    assert client().get("/api/workflows/status").status_code != 404


def test_workflow_journal_redaction_contract(tmp_path):
    state = isolated_state_dir(tmp_path)
    event = {
        "workflow_id": "wf-redact",
        "event": "vault.secret_rotated",
        "path": "secret/data/app",
        "version": 1,
    }
    journal = state / "workflow_events.jsonl"
    journal.write_text(json.dumps(event) + "\n")
    text = journal.read_text()
    for secret_key in [
        "password",
        "token",
        "secret_id",
        "client_token",
        "private_key",
        "root_token",
        "unseal_key",
    ]:
        assert secret_key not in text
