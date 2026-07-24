#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

if [[ ! -f tests/pocket_lab_test_utils.py ]]; then
  echo "ERROR: tests/pocket_lab_test_utils.py is missing." >&2
  echo "Copy it from the full Pocket Lab repo or restore it from Patch 1 before running Lite API checks." >&2
  exit 1
fi

PYTHON_BIN="${PYTHON:-python3}"

PYTHONPATH="tests:pocket-lab-final-structure/runtime:." "$PYTHON_BIN" - <<'PY_INNER'
import time

from pocket_lab_test_utils import client
from api_fastapi.services.projection_scheduler import PROJECTION_SCHEDULER


READ_ENDPOINTS = (
    "/api/lite/status",
    "/api/lite/catalog",
    "/api/lite/identity",
    "/api/lite/security/summary",
    "/api/lite/fleet",
    "/api/lite/policy",
    "/api/lite/recovery",
)


def warming_payload(response):
    if response.status_code != 503:
        return None

    try:
        payload = response.json()
    except ValueError:
        return None

    if not isinstance(payload, dict):
        return None

    if payload.get("status") != "warming":
        return None

    if payload.get("retryable") is not True:
        return None

    if payload.get("refresh_pending") is not True:
        return None

    return payload


def read_with_bounded_warmup(
    test_client,
    path,
    *,
    timeout_seconds=20.0,
):
    deadline = time.monotonic() + timeout_seconds
    attempts = 0

    while True:
        attempts += 1
        response = test_client.get(path)

        if response.status_code == 200:
            return response, attempts, False

        payload = warming_payload(response)
        if payload is None:
            return response, attempts, False

        if time.monotonic() >= deadline:
            # A bounded, retryable warming response is a valid E3
            # prepared-read outcome when no safe snapshot exists yet.
            return response, attempts, True

        retry_after = payload.get("retry_after_seconds", 0.1)
        try:
            delay = float(retry_after)
        except (TypeError, ValueError):
            delay = 0.1

        # Keep the developer smoke check bounded and responsive rather
        # than sleeping for the full production-facing Retry-After value.
        time.sleep(max(0.05, min(delay, 0.25)))


def wait_for_projection_idle(*, timeout_seconds=15.0):
    deadline = time.monotonic() + timeout_seconds
    last = {}

    while time.monotonic() < deadline:
        last = PROJECTION_SCHEDULER.diagnostics()
        active = int(last.get("active_domains") or 0)
        queued = int(last.get("queued_domains") or 0)

        if active == 0 and queued == 0:
            return True, last

        time.sleep(0.05)

    return False, last


c = client()

try:
    for path in READ_ENDPOINTS:
        response, attempts, bounded_warming = read_with_bounded_warmup(c, path)

        if response.status_code == 200:
            continue

        payload = warming_payload(response)
        assert bounded_warming and payload is not None, (
            f"{path} returned {response.status_code}: {response.text}"
        )

        print(
            f"INFO: {path} remained in a valid bounded warming state "
            f"after {attempts} attempts"
        )

    remove = c.post("/api/lite/catalog/remove", json={"name": "demo"})
    assert remove.status_code == 501, (
        "catalog remove should fail closed with 501, "
        f"got {remove.status_code}: {remove.text}"
    )

    restore = c.post(
        "/api/lite/recovery/restore",
        json={"backup_id": "demo"},
    )
    assert restore.status_code in {400, 409, 422}, (
        "restore without confirmation should be blocked, "
        f"got {restore.status_code}: {restore.text}"
    )

    idle, diagnostics = wait_for_projection_idle()
    assert idle, (
        "projection scheduler did not become idle before smoke-test exit: "
        f"{diagnostics}"
    )

finally:
    # The test utility intentionally avoids the FastAPI lifespan because
    # the normal application lifespan requires production NATS. Explicitly
    # stop the scheduler so no projection thread survives interpreter exit.
    PROJECTION_SCHEDULER.shutdown(drain_seconds=5.0)
    close = getattr(c, "close", None)
    if callable(close):
        close()

print("Lite API checks passed")
PY_INNER
