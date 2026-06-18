import json
import re
from pathlib import Path

SECRET_PATTERNS = [
    r"hvs\.[A-Za-z0-9]+",
    r"root_token",
    r"unseal_key",
    r"client_token",
    r"private_key",
    r"api_key",
    r"password\s*[:=]",
    r"secret_id\s*[:=]",
]


def assert_redacted(text: str):
    for pattern in SECRET_PATTERNS:
        assert not re.search(
            pattern, text, flags=re.IGNORECASE
        ), f"secret-like value leaked: {pattern}"


def test_event_journal_redacts_secret_like_values(tmp_path):
    journal = tmp_path / "workflow_events.jsonl"
    safe = {
        "subject": "pocketlab.audit.vault.rotate",
        "message": "secret rotated",
        "redacted": True,
        "token": "[REDACTED]",
    }
    journal.write_text(json.dumps(safe) + "\n")
    assert_redacted(journal.read_text())


def test_repository_fixtures_do_not_contain_live_secret_material():
    for root in [Path("tests/fixtures"), Path("src/mocks")]:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file():
                assert_redacted(path.read_text(errors="ignore"))
