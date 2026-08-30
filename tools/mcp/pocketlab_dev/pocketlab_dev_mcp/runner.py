"""Centralized, bounded subprocess execution for approved MCP operations."""

from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Sequence

from .config import validate_repository_root
from .redaction import DEFAULT_REDACTOR, OutputRedactor

STDOUT_LIMIT_BYTES = 12 * 1024
STDERR_LIMIT_BYTES = 12 * 1024
PROCESS_TERMINATION_GRACE_SECONDS = 2
READER_JOIN_GRACE_SECONDS = 2
SAFE_ENVIRONMENT_NAMES = ("PATH", "HOME", "USER", "LANG", "LC_ALL", "VIRTUAL_ENV", "TERM")
SENSITIVE_ENVIRONMENT_MARKERS = (
    "TOKEN",
    "SECRET",
    "PASSWORD",
    "PASSWD",
    "AUTH",
    "AUTHORIZATION",
    "COOKIE",
    "CREDENTIAL",
    "PRIVATE_KEY",
    "API_KEY",
    "NATS_CREDS",
    "TAILSCALE_AUTH",
)


@dataclass(frozen=True)
class ProcessResult:
    exit_code: int | None
    duration_ms: int
    stdout_tail: str
    stderr_tail: str
    timed_out: bool
    truncated: bool


class _CappedReader(threading.Thread):
    def __init__(self, stream: BinaryIO, limit: int) -> None:
        super().__init__(daemon=True)
        self._stream = stream
        self._limit = limit
        self.data = bytearray()
        self.truncated = False

    def run(self) -> None:
        try:
            while chunk := self._stream.read(4096):
                remaining = self._limit - len(self.data)
                if remaining > 0:
                    self.data.extend(chunk[:remaining])
                if len(chunk) > remaining:
                    self.truncated = True
        except (OSError, ValueError):
            # The runner closes pipes after a bounded timeout cleanup.
            self.truncated = True


def filtered_environment(source: dict[str, str] | None = None) -> dict[str, str]:
    """Create the minimal child environment without forwarding secrets."""

    source = os.environ if source is None else source
    environment: dict[str, str] = {}
    for name in SAFE_ENVIRONMENT_NAMES:
        value = source.get(name)
        if value is None:
            continue
        upper_name = name.upper()
        if any(marker in upper_name for marker in SENSITIVE_ENVIRONMENT_MARKERS):
            continue
        environment[name] = value
    return environment


class ProcessRunner:
    """Run fixed argv commands from a validated root with bounded safe output."""

    def __init__(
        self,
        repository_root: Path,
        *,
        redactor: OutputRedactor = DEFAULT_REDACTOR,
        environment: dict[str, str] | None = None,
    ) -> None:
        self.repository_root = validate_repository_root(repository_root)
        self._redactor = redactor
        self._environment = filtered_environment(environment)

    def run(self, argv: Sequence[str], *, timeout_seconds: float) -> ProcessResult:
        """Execute a policy-built argument vector; callers cannot supply shell text."""

        if not argv or isinstance(argv, str) or not all(isinstance(item, str) for item in argv):
            raise ValueError("argv must be a non-empty sequence of strings")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

        started = time.monotonic()
        process = subprocess.Popen(
            list(argv),
            cwd=str(self.repository_root),
            env=self._environment,
            shell=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        assert process.stdout is not None
        assert process.stderr is not None
        stdout_reader = _CappedReader(process.stdout, STDOUT_LIMIT_BYTES)
        stderr_reader = _CappedReader(process.stderr, STDERR_LIMIT_BYTES)
        stdout_reader.start()
        stderr_reader.start()

        timed_out = False
        try:
            process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=PROCESS_TERMINATION_GRACE_SECONDS)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait(timeout=PROCESS_TERMINATION_GRACE_SECONDS)
        finally:
            process.stdout.close()
            process.stderr.close()
            stdout_reader.join(timeout=READER_JOIN_GRACE_SECONDS)
            stderr_reader.join(timeout=READER_JOIN_GRACE_SECONDS)

        duration_ms = int((time.monotonic() - started) * 1000)
        stdout = bytes(stdout_reader.data).decode("utf-8", errors="replace")
        stderr = bytes(stderr_reader.data).decode("utf-8", errors="replace")
        return ProcessResult(
            exit_code=None if timed_out else process.returncode,
            duration_ms=duration_ms,
            stdout_tail=self._redactor.redact(stdout),
            stderr_tail=self._redactor.redact(stderr),
            timed_out=timed_out,
            truncated=(
                stdout_reader.truncated
                or stderr_reader.truncated
                or stdout_reader.is_alive()
                or stderr_reader.is_alive()
            ),
        )
