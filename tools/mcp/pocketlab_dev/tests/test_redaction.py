from __future__ import annotations

import pytest

from pocketlab_dev_mcp.redaction import REDACTED, OutputRedactor


@pytest.mark.parametrize(
    "value",
    [
        "Authorization: Bearer secret-value",
        "Authorization: Token secret-value",
        'Authorization: Digest username="user", response="secret-value"',
        "authorization: bearer secret-value",
        "AUTHORIZATION: CUSTOM secret-value",
        "aUtHoRiZaTiOn: Negotiate secret-value",
        "normal output\nAuthorization: Token secret-value\nmore output",
        "token=secret-value",
        "password: secret-value",
        "api_key=secret-value",
        "Cookie: session=secret-value",
        "NATS_CREDS=secret-value",
        "-----BEGIN PRIVATE KEY-----\nsecret\n-----END PRIVATE KEY-----",
    ],
)
def test_redactor_masks_secret_bearing_output(value: str):
    redacted = OutputRedactor().redact(value)
    assert "secret-value" not in redacted
    assert REDACTED in redacted


def test_redactor_retains_ordinary_diagnostics():
    assert OutputRedactor().redact("42 tests passed in 1.2s") == "42 tests passed in 1.2s"
    assert OutputRedactor().redact("authorization policy loaded") == "authorization policy loaded"


def test_redaction_failure_fails_closed(monkeypatch):
    redactor = OutputRedactor()
    monkeypatch.setattr(redactor, "_patterns", ((None, None),))
    assert redactor.redact("token=leak") == REDACTED
