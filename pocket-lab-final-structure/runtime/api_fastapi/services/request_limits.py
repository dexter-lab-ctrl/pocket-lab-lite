from __future__ import annotations

"""Endpoint-specific bounded request-body limits for Lite control operations."""

from dataclasses import dataclass
import json
import os
import re
from typing import Any, Awaitable, Callable


ASGIApp = Callable[[dict[str, Any], Callable[[], Awaitable[dict[str, Any]]], Callable[[dict[str, Any]], Awaitable[None]]], Awaitable[None]]


def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


@dataclass(frozen=True, slots=True)
class RequestLimitRule:
    name: str
    pattern: re.Pattern[str]
    limit_bytes: int


def _rules() -> tuple[RequestLimitRule, ...]:
    kib = 1024
    return (
        RequestLimitRule("security_check", re.compile(r"^/api/lite/security(?:/check|/scan|/apps/[^/]+/check)$"), _bounded_int("POCKETLAB_REQUEST_LIMIT_SECURITY_BYTES", 4 * kib, 512, 64 * kib)),
        RequestLimitRule("device_invite", re.compile(r"^/api/lite/fleet/add-device$"), _bounded_int("POCKETLAB_REQUEST_LIMIT_DEVICE_INVITE_BYTES", 4 * kib, 512, 64 * kib)),
        RequestLimitRule("device_restart", re.compile(r"^/api/lite/fleet/devices/[^/]+/restart-agent$"), _bounded_int("POCKETLAB_REQUEST_LIMIT_DEVICE_RESTART_BYTES", 4 * kib, 512, 64 * kib)),
        RequestLimitRule("device_remove", re.compile(r"^/api/lite/fleet/remove-device$"), _bounded_int("POCKETLAB_REQUEST_LIMIT_DEVICE_REMOVE_BYTES", 4 * kib, 512, 64 * kib)),
        RequestLimitRule("app_action", re.compile(r"^/api/lite/(?:apps/[^/]+/(?:actions/[^/]+|backup|restore/preview|backup/storage-device|update/apply)|catalog/(?:install|remove)|apps/photoprism/storage-mappings)$"), _bounded_int("POCKETLAB_REQUEST_LIMIT_APP_ACTION_BYTES", 12 * kib, 1024, 128 * kib)),
        RequestLimitRule("recovery", re.compile(r"^/api/lite/recovery(?:/.*)?$"), _bounded_int("POCKETLAB_REQUEST_LIMIT_RECOVERY_BYTES", 12 * kib, 1024, 128 * kib)),
        RequestLimitRule("identity_access", re.compile(r"^/api/lite/(?:identity/rotate|policy/apply)$"), _bounded_int("POCKETLAB_REQUEST_LIMIT_ACCESS_BYTES", 8 * kib, 1024, 128 * kib)),
        RequestLimitRule("lite_write_default", re.compile(r"^/api/lite/"), _bounded_int("POCKETLAB_REQUEST_LIMIT_DEFAULT_BYTES", 16 * kib, 1024, 256 * kib)),
    )


REQUEST_LIMIT_RULES = _rules()
_WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def request_limit_for(method: str, path: str) -> tuple[str, int] | None:
    if str(method or "").upper() not in _WRITE_METHODS:
        return None
    safe_path = str(path or "")
    for rule in REQUEST_LIMIT_RULES:
        if rule.pattern.match(safe_path):
            return rule.name, rule.limit_bytes
    return None


def request_limit_snapshot() -> dict[str, Any]:
    return {
        "rules": [
            {"name": rule.name, "limit_bytes": rule.limit_bytes}
            for rule in REQUEST_LIMIT_RULES
        ],
        "sanitized": True,
    }


class _PayloadTooLarge(Exception):
    pass


class LiteRequestSizeLimitMiddleware:
    """Reject oversized Lite write bodies before Pydantic normalization.

    Content-Length is checked immediately. Chunked/unknown-length bodies are
    bounded incrementally by wrapping ASGI receive without retaining the body.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        method = str(scope.get("method") or "GET").upper()
        path = str(scope.get("path") or "")
        matched = request_limit_for(method, path)
        if matched is None:
            await self.app(scope, receive, send)
            return
        rule_name, limit_bytes = matched
        headers = {
            key.decode("latin-1").lower(): value.decode("latin-1")
            for key, value in scope.get("headers") or []
        }
        try:
            content_length = int(headers.get("content-length", "0") or "0")
        except ValueError:
            content_length = 0
        if content_length > limit_bytes:
            await self._send_rejection(send, limit_bytes, rule_name)
            return

        consumed = 0
        response_started = False

        async def limited_receive():
            nonlocal consumed
            message = await receive()
            if message.get("type") == "http.request":
                consumed += len(message.get("body") or b"")
                if consumed > limit_bytes:
                    raise _PayloadTooLarge()
            return message

        async def tracked_send(message):
            nonlocal response_started
            if message.get("type") == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracked_send)
        except _PayloadTooLarge:
            if not response_started:
                await self._send_rejection(send, limit_bytes, rule_name)

    @staticmethod
    async def _send_rejection(send, limit_bytes: int, rule_name: str) -> None:
        payload = json.dumps(
            {
                "status": "rejected",
                "accepted": False,
                "reason": "payload_too_large",
                "retryable": False,
                "operation": rule_name,
                "message": "This request is too large for Pocket Lab Lite.",
                "sanitized": True,
            },
            separators=(",", ":"),
        ).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(payload)).encode("ascii")),
                    (b"cache-control", b"no-store"),
                    (b"x-pocketlab-request-limit-bytes", str(limit_bytes).encode("ascii")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": payload, "more_body": False})
