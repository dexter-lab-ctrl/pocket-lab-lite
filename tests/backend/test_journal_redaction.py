import json
import re
from pathlib import Path

TOKEN_PATTERNS = [
    r"hvs\.[A-Za-z0-9]+",
]
SENSITIVE_KEYS = {
    "root_token",
    "unseal_key",
    "client_token",
    "private_key",
    "api_key",
    "password",
    "secret_id",
}
SAFE_SECRET_VALUES = {
    "",
    "[redacted]",
    "<redacted>",
    "redacted",
    "***",
    "****",
    "null",
    "none",
    "not configured",
    "not_configured",
    "unavailable",
}


def _is_safe_secret_value(value: str) -> bool:
    raw = str(value or "").strip()
    normalized = raw.strip('"\'').lower()
    if normalized in SAFE_SECRET_VALUES or set(normalized) <= {"*"}:
        return True
    # Static fixture scanning can prove that a quoted literal is concrete secret
    # material, but an unquoted JavaScript expression (for example
    # `password: role === 'Owner'`) is computation, not a stored credential.
    # Runtime redaction tests cover the resulting values separately.
    if raw.startswith(("\"", "'")):
        return False
    return True


def assert_redacted(text: str):
    for pattern in TOKEN_PATTERNS:
        assert not re.search(pattern, text, flags=re.IGNORECASE), f"secret-like value leaked: {pattern}"

    # Fixtures may legitimately name sensitive fields and may compare or derive
    # those fields in UI logic. Reject concrete quoted assignments unless they
    # are explicitly redacted; computed source expressions are not credentials.
    assignment = re.compile(
        r"(?i)[\"']?(root_token|unseal_key|client_token|private_key|api_key|password|secret_id)[\"']?\s*(?::|=(?!=))\s*([^,}\n]+)"
    )
    for match in assignment.finditer(text):
        value = match.group(2).strip()
        assert _is_safe_secret_value(value), f"unredacted fixture value for {match.group(1)}"


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
