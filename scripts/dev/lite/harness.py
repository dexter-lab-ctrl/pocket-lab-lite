#!/usr/bin/env python3
"""Small loopback client for the Pocket Lab synthetic harness API.

The backend remains the only authority. This client creates local Ed25519
material, signs the backend-issued challenge, and keeps bearer/session output
explicit so callers do not hand-build protocol payloads.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import stat
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

DEFAULT_API_URL = "http://127.0.0.1:8080"
SESSION_ENV = "POCKETLAB_HARNESS_SESSION"


def _b64u(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _api_url() -> str:
    value = os.environ.get("POCKETLAB_HARNESS_API_URL", DEFAULT_API_URL).strip().rstrip("/")
    parsed = urlsplit(value)
    host = (parsed.hostname or "").casefold()
    if parsed.scheme != "http" or host not in {"127.0.0.1", "::1", "localhost"} or parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise ValueError("POCKETLAB_HARNESS_API_URL must be an http loopback URL")
    if parsed.port is None or not 1 <= parsed.port <= 65535:
        raise ValueError("POCKETLAB_HARNESS_API_URL must include a valid loopback port")
    return value


def _timeout() -> float:
    try:
        value = float(os.environ.get("POCKETLAB_HARNESS_CLI_TIMEOUT_SECONDS", "5"))
    except ValueError:
        value = 5.0
    return max(1.0, min(value, 15.0))


def _request(method: str, path: str, payload: dict | None = None, headers: dict[str, str] | None = None) -> dict:
    body = None
    request_headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    request_headers.update(headers or {})
    request = urllib.request.Request(_api_url() + path, data=body, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=_timeout()) as response:
            raw = response.read(128 * 1024)
            result = json.loads(raw.decode("utf-8")) if raw else {}
            return result if isinstance(result, dict) else {"result": result}
    except urllib.error.HTTPError as exc:
        raw = exc.read(16 * 1024)
        try:
            detail = json.loads(raw.decode("utf-8")) if raw else {}
        except (UnicodeDecodeError, json.JSONDecodeError):
            detail = {}
        message = detail.get("message") or detail.get("detail") or "harness request rejected"
        reason = detail.get("reason_code") or "harness_request_failed"
        raise RuntimeError(f"{reason}: {str(message)[:240]}") from None
    except (OSError, urllib.error.URLError) as exc:
        raise RuntimeError(f"harness_transport_unavailable: {type(exc).__name__}") from None


def _private_key(path: str) -> Ed25519PrivateKey:
    raw = Path(path).expanduser().read_bytes()
    if len(raw) != 32:
        raise ValueError("key file must contain exactly 32 raw Ed25519 private-key bytes")
    return Ed25519PrivateKey.from_private_bytes(raw)


def _write_private_key(path: Path, raw: bytes, *, force: bool) -> None:
    path = path.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | (os.O_TRUNC if force else os.O_EXCL)
    old_umask = os.umask(0o177)
    try:
        fd = os.open(path, flags, 0o600)
        try:
            os.write(fd, raw)
        finally:
            os.close(fd)
    finally:
        os.umask(old_umask)
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)


def cmd_keygen(args: argparse.Namespace) -> dict:
    path = Path(args.key_file).expanduser()
    key = Ed25519PrivateKey.generate()
    raw_private = key.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
    _write_private_key(path, raw_private, force=args.force)
    public = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return {
        "status": "created",
        "private_key_path": str(path),
        "private_key_mode": oct(stat.S_IMODE(path.stat().st_mode)),
        "algorithm": "ed25519",
        "public_key": _b64u(public),
        "public_key_fingerprint": "sha256:" + hashlib.sha256(public).hexdigest(),
        "private_key_returned": False,
    }


def _provisioning_headers() -> dict[str, str]:
    token = os.environ.get("POCKETLAB_HARNESS_PROVISIONING_TOKEN", "").strip()
    if not token:
        raise ValueError("POCKETLAB_HARNESS_PROVISIONING_TOKEN is required")
    return {
        "X-Pocket-Lab-Harness-Provisioning": "1",
        "X-Pocket-Lab-Harness-Provisioning-Token": token,
    }


def cmd_principal_create(args: argparse.Namespace) -> dict:
    key = _private_key(args.key_file)
    public = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    profiles = [item.strip().casefold() for item in args.profile if item.strip()]
    if not profiles:
        raise ValueError("at least one --profile is required")
    return _request(
        "POST",
        "/api/lite/harness/principals",
        {
            "principal_id": args.principal_id,
            "display_name": args.display_name,
            "public_key": _b64u(public),
            "profiles": profiles,
            "algorithm": "ed25519",
            "expires_in_seconds": args.expires_in_seconds,
        },
        _provisioning_headers(),
    )


def cmd_principal_revoke(args: argparse.Namespace) -> dict:
    return _request("POST", f"/api/lite/harness/principals/{args.principal_id}/revoke", headers=_provisioning_headers())


def cmd_session_start(args: argparse.Namespace) -> dict:
    challenge = _request(
        "POST",
        "/api/lite/harness/challenge",
        {
            "principal_id": args.principal_id,
            "purpose": args.purpose,
            "profile": args.profile,
            "target_scope": "local_server_host_only",
        },
    )
    key = _private_key(args.key_file)
    signature = _b64u(key.sign(str(challenge["signing_payload"]).encode("utf-8")))
    return _request(
        "POST",
        "/api/lite/harness/session",
        {
            "challenge_id": challenge["challenge_id"],
            "signing_payload": challenge["signing_payload"],
            "signature": signature,
            "principal_id": args.principal_id,
            "profile": args.profile,
        },
    )


def _session_headers(args: argparse.Namespace) -> dict[str, str]:
    token = (args.session_token or os.environ.get(SESSION_ENV, "")).strip()
    if not token:
        raise ValueError(f"--session-token or {SESSION_ENV} is required")
    return {"X-Pocket-Lab-Harness-Session": token}


def cmd_session_status(args: argparse.Namespace) -> dict:
    return _request("GET", f"/api/lite/harness/session/{args.session_id}", headers=_session_headers(args))


def cmd_session_stop(args: argparse.Namespace) -> dict:
    return _request("DELETE", f"/api/lite/harness/session/{args.session_id}", headers=_session_headers(args))


def cmd_status(_args: argparse.Namespace) -> dict:
    return _request("GET", "/api/lite/harness/status")


def cmd_profiles(_args: argparse.Namespace) -> dict:
    return _request("GET", "/api/lite/harness/capabilities")


def cmd_verify_off(_args: argparse.Namespace) -> dict:
    result = cmd_status(_args)
    if any(result.get(key) for key in ("enabled", "destructive_gate", "qualification_owner", "test_auth_bypass")):
        raise RuntimeError("harness_not_disabled: runtime reports an enabled synthetic authority")
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Pocket Lab loopback synthetic-harness client")
    commands = parser.add_subparsers(dest="command", required=True)
    keygen = commands.add_parser("keygen", help="create 0600 raw Ed25519 key material")
    keygen.add_argument("--key-file", required=True)
    keygen.add_argument("--force", action="store_true")
    keygen.set_defaults(handler=cmd_keygen)
    principal = commands.add_parser("principal-create", help="register a public key and server-owned profile")
    principal.add_argument("--principal-id", required=True)
    principal.add_argument("--display-name", required=True)
    principal.add_argument("--key-file", required=True)
    principal.add_argument("--profile", action="append", required=True)
    principal.add_argument("--expires-in-seconds", type=int, default=86400)
    principal.set_defaults(handler=cmd_principal_create)
    revoke = commands.add_parser("principal-revoke", help="revoke a principal and its active sessions")
    revoke.add_argument("--principal-id", required=True)
    revoke.set_defaults(handler=cmd_principal_revoke)
    start = commands.add_parser("session-start", help="obtain and sign a short-lived harness session")
    start.add_argument("--principal-id", required=True)
    start.add_argument("--profile", required=True)
    start.add_argument("--purpose", required=True)
    start.add_argument("--key-file", required=True)
    start.set_defaults(handler=cmd_session_start)
    for name, handler in (("session-status", cmd_session_status), ("session-stop", cmd_session_stop)):
        command = commands.add_parser(name)
        command.add_argument("--session-id", required=True)
        command.add_argument("--session-token")
        command.set_defaults(handler=handler)
    status = commands.add_parser("status", help="show bounded backend harness status")
    status.set_defaults(handler=cmd_status)
    profiles = commands.add_parser("profiles", help="show server-owned capability profiles")
    profiles.set_defaults(handler=cmd_profiles)
    off = commands.add_parser("verify-off", help="prove all harness authority flags are disabled")
    off.set_defaults(handler=cmd_verify_off)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        result = args.handler(args)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"ERROR {str(exc)[:320]}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
