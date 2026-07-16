from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import stat
import time
from pathlib import Path
from typing import Any

SUBMISSION_DELAY_SCENARIO = "submission-response-delay"
SUBMISSION_DELAY_HEADER = "x-pocketlab-gate-scenario"
SUBMISSION_TOKEN_HEADER = "x-pocketlab-gate-token"
MAX_SUBMISSION_DELAY_MS = 30_000


def _state_dir() -> Path:
    return Path(os.environ.get("POCKETLAB_STATE_DIR", Path.home() / "pocket-lab-lite" / "state")).expanduser()


def submission_delay_activation_path() -> Path:
    return _state_dir() / ".pocketlab-dev" / "gate-faults" / "submission-response-delay.json"


def _is_loopback(host: str) -> bool:
    value = str(host or "").strip().lower()
    return value in {"127.0.0.1", "::1", "localhost", "testclient"}


def _read_activation(path: Path) -> dict[str, Any] | None:
    try:
        mode = stat.S_IMODE(path.stat().st_mode)
        if mode & 0o077:
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def authorized_submission_delay_ms(request: Any, *, now_epoch: float | None = None) -> int:
    """Return a bounded gate-only response delay, otherwise zero.

    Authorization requires a loopback request, a fixed scenario marker, a random
    per-run token matching a short-lived owner-only activation file, and a valid
    bounded delay. The public UI cannot create the activation file or learn the
    token. The token is never returned or logged.
    """
    headers = getattr(request, "headers", {}) or {}
    if str(headers.get(SUBMISSION_DELAY_HEADER, "")) != SUBMISSION_DELAY_SCENARIO:
        return 0
    client = getattr(request, "client", None)
    if not _is_loopback(getattr(client, "host", "")):
        return 0
    token = str(headers.get(SUBMISSION_TOKEN_HEADER, ""))
    if len(token) < 24 or len(token) > 256:
        return 0
    activation = _read_activation(submission_delay_activation_path())
    if not activation or activation.get("scenario") != SUBMISSION_DELAY_SCENARIO:
        return 0
    now = time.time() if now_epoch is None else float(now_epoch)
    try:
        expires_at = float(activation.get("expires_at_epoch") or 0)
        delay_ms = int(activation.get("delay_ms") or 0)
    except (TypeError, ValueError):
        return 0
    if expires_at <= now or delay_ms < 1 or delay_ms > MAX_SUBMISSION_DELAY_MS:
        return 0
    expected = str(activation.get("token_sha256") or "")
    actual = hashlib.sha256(token.encode("utf-8")).hexdigest()
    if len(expected) != 64 or not hmac.compare_digest(expected, actual):
        return 0
    return delay_ms


async def maybe_delay_submission_response(request: Any) -> int:
    delay_ms = authorized_submission_delay_ms(request)
    if delay_ms:
        await asyncio.sleep(delay_ms / 1000.0)
    return delay_ms
