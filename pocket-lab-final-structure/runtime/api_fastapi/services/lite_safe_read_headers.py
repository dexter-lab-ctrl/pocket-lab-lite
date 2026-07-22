from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from typing import Any

LITE_SAFE_READ_NONCE_HEADER = "x-pocketlab-read-nonce"
_NONCE_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{8,64}$")


def sanitize_lite_safe_read_nonce(value: str | bytes | None) -> str:
    if isinstance(value, bytes):
        try:
            value = value.decode("ascii", errors="strict")
        except UnicodeDecodeError:
            return ""
    nonce = str(value or "").strip()
    return nonce if _NONCE_PATTERN.fullmatch(nonce) else ""


class LiteSafeReadNonceMiddleware:
    """Echo a non-secret read nonce so the PWA can identify cached GET responses."""

    def __init__(self, app: Callable[..., Awaitable[Any]]) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Callable[..., Any], send: Callable[..., Any]) -> None:
        if scope.get("type") != "http" or str(scope.get("method") or "").upper() != "GET":
            await self.app(scope, receive, send)
            return
        path = str(scope.get("path") or "")
        if not path.startswith("/api/lite/"):
            await self.app(scope, receive, send)
            return

        request_headers = {
            bytes(key).lower(): bytes(value)
            for key, value in scope.get("headers") or []
        }
        nonce = sanitize_lite_safe_read_nonce(
            request_headers.get(LITE_SAFE_READ_NONCE_HEADER.encode("ascii"))
        )
        if not nonce:
            await self.app(scope, receive, send)
            return

        header_name = LITE_SAFE_READ_NONCE_HEADER.encode("ascii")
        header_value = nonce.encode("ascii")

        async def send_with_nonce(message: dict[str, Any]) -> None:
            if message.get("type") == "http.response.start":
                headers = [
                    (key, value)
                    for key, value in message.get("headers") or []
                    if bytes(key).lower() != header_name
                ]
                headers.append((header_name, header_value))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_nonce)
