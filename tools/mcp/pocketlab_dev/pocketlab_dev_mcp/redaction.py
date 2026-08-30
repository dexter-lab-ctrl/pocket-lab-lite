"""Fail-closed redaction for all developer-MCP subprocess output."""

from __future__ import annotations

import re

REDACTED = "[REDACTED]"


class OutputRedactor:
    """Mask common credential forms while retaining ordinary diagnostics."""

    def __init__(self) -> None:
        self._patterns = (
            (
                re.compile(
                    r"(?is)(-----BEGIN [^-]*(?:PRIVATE KEY|OPENSSH PRIVATE KEY)-----).*?"
                    r"(-----END [^-]*(?:PRIVATE KEY|OPENSSH PRIVATE KEY)-----)"
                ),
                REDACTED,
            ),
            (
                re.compile(r"(?im)(^\s*authorization\s*:\s*)[^\r\n]*"),
                r"\1" + REDACTED,
            ),
            (re.compile(r"(?i)(\bbearer\s+)[A-Za-z0-9._~+\-/=]+"), r"\1" + REDACTED),
            (
                re.compile(
                    r"(?i)\b(token|api[_-]?key|password|passwd|secret|"
                    r"authorization|cookie|credential|private[_-]?key|"
                    r"nats[_-]?creds?|tailscale[_-]?auth)"
                    r"\s*([:=])\s*(?:\"[^\"]*\"|'[^']*'|[^\s,;]+)"
                ),
                lambda match: f"{match.group(1)}{match.group(2)}{REDACTED}",
            ),
            (
                re.compile(r"(?i)(set-cookie\s*:\s*)[^\r\n]+"),
                r"\1" + REDACTED,
            ),
        )

    def redact(self, value: str) -> str:
        """Return sanitized text, or only a marker if redaction itself fails."""

        try:
            sanitized = value
            for pattern, replacement in self._patterns:
                sanitized = pattern.sub(replacement, sanitized)
            return sanitized
        except Exception:
            # Output may carry credentials; fail closed rather than return it.
            return REDACTED


DEFAULT_REDACTOR = OutputRedactor()
