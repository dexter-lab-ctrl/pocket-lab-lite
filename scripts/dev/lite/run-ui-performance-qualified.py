#!/usr/bin/env python3
"""Run the fixed UI-performance browser lane with a short-lived harness bridge.

The key-bound bootstrap, browser projection, and principal cleanup stay in this
process.  The child receives only the short-lived bridge header through its
environment; the PWA never receives a harness session or provisioning token.
No arbitrary command, URL, profile, capability, or destructive operation is
accepted by this runner.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import harness as harness_client


PROFILE = "qualification-owner"
PURPOSE = "ui-performance-60fps"
TARGET_SCOPE = "local_server_host_only"
MIN_SESSION_TTL_SECONDS = 60
MAX_SESSION_TTL_SECONDS = 300
DEFAULT_SESSION_TTL_SECONDS = 180
RUN_TIMEOUT_SECONDS = 15 * 60
PRINCIPAL_ID_RE = re.compile(r"^[a-z][a-z0-9._-]{2,79}$")
SECRET_ENV_KEYS = (
    "POCKETLAB_HARNESS_SESSION",
    "POCKETLAB_HARNESS_PROVISIONING_TOKEN",
    "POCKETLAB_HARNESS_BOOTSTRAP_APPROVED",
    "POCKETLAB_HARNESS_BOOTSTRAP_PRINCIPAL_ID",
    "POCKETLAB_HARNESS_BOOTSTRAP_PUBLIC_KEY_FINGERPRINT",
    "POCKETLAB_HARNESS_BOOTSTRAP_PROFILE",
    "POCKETLAB_HARNESS_DESTRUCTIVE",
    "POCKETLAB_HARNESS_ENABLED",
    "POCKETLAB_QUALIFICATION_OWNER",
    "POCKETLAB_TEST_AUTH_BYPASS",
)


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().casefold() in {"1", "true", "yes", "on"}


def _redact_output(value: object, secrets: tuple[str, ...]) -> str:
    text = str(value or "")
    for secret in secrets:
        if secret:
            text = text.replace(secret, "[REDACTED]")
    return text


def _runner_command(mode: str) -> list[str]:
    shell = shutil.which("bash")
    if not shell:
        raise RuntimeError("bash is required for the fixed UI-performance runner")
    scripts = {
        "live": REPO_ROOT / "scripts/dev/lite/run-ui-performance-live.sh",
        "android-cdp": REPO_ROOT / "scripts/dev/lite/run-ui-performance-android-cdp.sh",
    }
    script = scripts.get(mode)
    if script is None or not script.is_file():
        raise RuntimeError("the selected checked-in UI-performance runner is unavailable")
    return [shell, str(script)]


def _child_environment(bridge_token: str, *, mode: str) -> dict[str, str]:
    child = dict(os.environ)
    for key in SECRET_ENV_KEYS:
        child.pop(key, None)
    child["LITE_E2E_MODE"] = "live"
    child["LITE_E2E_LIVE"] = "1"
    child["LITE_QUALIFICATION_BROWSER_BRIDGE"] = "1"
    child["POCKETLAB_HARNESS_BROWSER_BRIDGE"] = bridge_token
    if mode == "android-cdp":
        child.pop("LITE_ANDROID_CDP_URL", None)
    return child


def _validate_operator_environment(mode: str) -> None:
    if _truthy(os.environ.get("POCKETLAB_TEST_AUTH_BYPASS")):
        raise ValueError("POCKETLAB_TEST_AUTH_BYPASS must remain disabled")
    if _truthy(os.environ.get("POCKETLAB_HARNESS_DESTRUCTIVE")):
        raise ValueError("destructive qualification authority must remain disabled")
    if os.environ.get("POCKETLAB_HARNESS_SESSION", "").strip():
        raise ValueError("POCKETLAB_HARNESS_SESSION must be unset; bootstrap is process-owned")
    if os.environ.get("POCKETLAB_HARNESS_BROWSER_BRIDGE", "").strip():
        raise ValueError("POCKETLAB_HARNESS_BROWSER_BRIDGE must be unset; bridge creation is process-owned")
    if not os.environ.get("LITE_BASE_URL", "").strip():
        raise ValueError("LITE_BASE_URL must identify the prepared live runtime")
    if mode not in {"live", "android-cdp"}:
        raise ValueError("unsupported UI-performance qualification mode")


def _bridge_token(response: dict) -> str:
    metadata = response.get("browser_bridge")
    token = str(response.get("browser_bridge_token") or "").strip()
    if not isinstance(metadata, dict) or token == "":
        raise RuntimeError("the backend returned no browser qualification bridge")
    expected = {
        "profile": PROFILE,
        "purpose": PURPOSE,
        "target_scope": TARGET_SCOPE,
    }
    if any(str(metadata.get(key) or "") != value for key, value in expected.items()):
        raise RuntimeError("the browser qualification bridge binding was not accepted")
    return token


def run(args: argparse.Namespace) -> int:
    _validate_operator_environment(args.mode)
    principal_id = str(args.principal_id or "").strip().casefold()
    if not PRINCIPAL_ID_RE.fullmatch(principal_id):
        raise ValueError("principal id must be a bounded disposable synthetic identifier")

    session_token = ""
    bridge_token = ""
    child_returncode = 2
    cleanup_error = ""
    output_secrets: tuple[str, ...] = ()
    try:
        session = harness_client.bootstrap_session(
            principal_id=principal_id,
            key_file=str(Path(args.key_file).expanduser()),
            ttl_seconds=args.ttl_seconds,
        )
        session_token = str(session.get("session_token") or "").strip()
        if not session_token:
            raise RuntimeError("key-bound bootstrap returned no session")
        bridge_token = _bridge_token(harness_client.browser_bridge(session_token=session_token))
        output_secrets = (session_token, bridge_token)
        child = subprocess.run(
            _runner_command(args.mode),
            cwd=str(REPO_ROOT),
            env=_child_environment(bridge_token, mode=args.mode),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=RUN_TIMEOUT_SECONDS,
            check=False,
        )
        if child.stdout:
            sys.stdout.write(_redact_output(child.stdout, output_secrets))
        if child.stderr:
            sys.stderr.write(_redact_output(child.stderr, output_secrets))
        child_returncode = int(child.returncode)
    except subprocess.TimeoutExpired:
        child_returncode = 124
        print("[ui-performance-qualified] ERROR fixed UI-performance runner timed out", file=sys.stderr)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"[ui-performance-qualified] ERROR {str(exc)[:320]}", file=sys.stderr)
    finally:
        if session_token:
            try:
                harness_client.revoke_authenticated_principal(session_token=session_token)
            except (OSError, RuntimeError, ValueError) as exc:
                cleanup_error = str(exc)[:240]

    if cleanup_error:
        print(f"[ui-performance-qualified] ERROR synthetic principal cleanup failed: {cleanup_error}", file=sys.stderr)
        return 2
    if child_returncode == 0:
        print(
            "[ui-performance-qualified] cleanup passed; profile=qualification-owner "
            "purpose=ui-performance-60fps target=local_server_host_only "
            f"ttl_seconds={args.ttl_seconds} destructive=false test_auth_bypass=false"
        )
    return child_returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("live", "android-cdp"), required=True)
    parser.add_argument("--principal-id", required=True)
    parser.add_argument("--key-file", required=True)
    parser.add_argument(
        "--ttl-seconds",
        type=int,
        choices=range(MIN_SESSION_TTL_SECONDS, MAX_SESSION_TTL_SECONDS + 1),
        default=DEFAULT_SESSION_TTL_SECONDS,
    )
    return run(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
