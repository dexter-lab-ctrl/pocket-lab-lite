#!/usr/bin/env python3
"""Run bounded UI-performance qualification with renewable synthetic Owner authority.

The controller owns Ed25519 bootstrap/session/bridge material in process memory.
Each measured interaction runs in a separate child process so authority can be
rotated only BETWEEN interactions, never while a measurement is in progress.

Renewal policy:
- session remaining < 45 seconds -> establish a replacement signed session,
  mint its bridge, then revoke the old session before the next interaction.
- bridge remaining < 30 seconds -> mint a replacement bridge from the still
  healthy parent session before the next interaction.

No arbitrary command, URL, profile, capability, or destructive operation is
accepted. The browser receives only the short-lived bridge proof.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import urlopen

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import harness as harness_client
from security_assurance_runtime_tunnel import ui_performance_runtime_tunnel


PROFILE = "qualification-owner"
PURPOSE = "ui-performance-60fps"
TARGET_SCOPE = "local_server_host_only"
MIN_SESSION_TTL_SECONDS = 60
MAX_SESSION_TTL_SECONDS = 300
DEFAULT_SESSION_TTL_SECONDS = 180
SESSION_RENEWAL_THRESHOLD_SECONDS = 45
BRIDGE_RENEWAL_THRESHOLD_SECONDS = 30
RUN_TIMEOUT_SECONDS = 15 * 60
# A supported Server Phone runtime can restart the API under its bounded PM2
# memory policy.  The restart is safe, but startup includes projection warmup
# and can take about 45 seconds.  Preflight retries happen before the browser
# interaction starts, so waiting here never rotates authority mid-measurement.
PREFLIGHT_RETRY_ATTEMPTS = 15
PREFLIGHT_RETRY_DELAY_SECONDS = 5.0
CLEANUP_RETRY_ATTEMPTS = 10
CLEANUP_RETRY_DELAY_SECONDS = 1.0
CANDIDATE_BASE_URL = "http://127.0.0.1:18765"
PRINCIPAL_ID_RE = re.compile(r"^[a-z][a-z0-9._-]{2,79}$")
INTERACTION_ID_RE = re.compile(r"^[a-z0-9][a-z0-9:._-]{2,119}$")
DEFAULT_CONTROLLER_CHECKPOINT = REPO_ROOT / ".pocketlab-dev/ui-performance-qualified-controller.json"
DEFAULT_LIVE_INTERACTIONS = (
    "live-navigation:catalog",
    "live-navigation:devices",
    "live-navigation:security",
    "live-navigation:identity",
    "live-navigation:rules",
    "live-navigation:recovery",
    "live-scroll:home",
    "live-scroll:catalog",
    "live-scroll:devices",
    "live-scroll:security",
    "live-scroll:identity",
    "live-scroll:rules",
    "live-scroll:recovery",
    "live-deep:home-technical-open",
    "live-deep:home-technical-close",
    "live-deep:catalog-section-switch",
    "live-deep:catalog-action-details",
    "live-deep:devices-diagnostics-open",
    "live-deep:devices-health-history",
    "live-deep:devices-nested-scroll",
    "live-deep:security-history",
    "live-deep:security-finding-details",
    "live-deep:identity-confirmation",
    "live-deep:rules-technical-status",
    "live-deep:recovery-section-switch",
    "live-deep:recovery-action-details",
)
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
    "POCKETLAB_HARNESS_API_URL",
)
TRANSIENT_PREFLIGHT_MARKER = "status endpoint is not reachable"
TRANSIENT_CLEANUP_MARKERS = (
    "harness_transport_unavailable",
    "connectionreseterror",
    "connection refused",
    "timed out",
    "timeout",
    "502",
    "temporarily unavailable",
)


class Authority:
    def __init__(
        self,
        session_token: str,
        session_id: str,
        session_expires_at: datetime,
        bridge_token: str,
        bridge_expires_at: datetime,
    ) -> None:
        self.session_token = session_token
        self.session_id = session_id
        self.session_expires_at = session_expires_at
        self.bridge_token = bridge_token
        self.bridge_expires_at = bridge_expires_at


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().casefold() in {"1", "true", "yes", "on"}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_timestamp(value: object, *, label: str) -> datetime:
    raw = str(value or "").strip()
    if not raw:
        raise RuntimeError(f"{label} expiry is missing")
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RuntimeError(f"{label} expiry is invalid") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _remaining_seconds(expires_at: datetime, *, now: datetime | None = None) -> float:
    current = now or _utcnow()
    return (expires_at - current).total_seconds()


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


def _child_environment(
    bridge_token: str,
    *,
    mode: str,
    base_url: str,
    interaction: str | None,
) -> dict[str, str]:
    child = dict(os.environ)
    for key in SECRET_ENV_KEYS:
        child.pop(key, None)
    child["LITE_E2E_MODE"] = "live"
    child["LITE_E2E_LIVE"] = "1"
    child["LITE_BASE_URL"] = base_url
    child["LITE_QUALIFICATION_BROWSER_BRIDGE"] = "1"
    child["POCKETLAB_HARNESS_BROWSER_BRIDGE"] = bridge_token
    child["LITE_PERF_PRESERVE_EVIDENCE"] = "1"
    if interaction:
        child["LITE_QUALIFICATION_INTERACTION"] = interaction
    else:
        child.pop("LITE_QUALIFICATION_INTERACTION", None)
    if mode == "android-cdp":
        child.pop("LITE_ANDROID_CDP_URL", None)
    return child


def _base_url(mode: str, *, candidate_ui: bool = False) -> str:
    configured = os.environ.get("LITE_BASE_URL", "").strip()
    if candidate_ui:
        value = CANDIDATE_BASE_URL
        if configured and configured.rstrip("/") != value:
            raise ValueError("candidate UI qualification owns LITE_BASE_URL")
    else:
        value = configured or ("http://127.0.0.1:18444" if mode == "live" else "")
    if not value:
        raise ValueError("LITE_BASE_URL must identify the prepared live runtime")
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("LITE_BASE_URL must use http:// or https://")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("LITE_BASE_URL must not contain credentials or query state")
    return value.rstrip("/")


def _validate_operator_environment(mode: str, *, candidate_ui: bool = False) -> str:
    if _truthy(os.environ.get("POCKETLAB_TEST_AUTH_BYPASS")):
        raise ValueError("POCKETLAB_TEST_AUTH_BYPASS must remain disabled")
    if _truthy(os.environ.get("POCKETLAB_HARNESS_DESTRUCTIVE")):
        raise ValueError("destructive qualification authority must remain disabled")
    if os.environ.get("POCKETLAB_HARNESS_SESSION", "").strip():
        raise ValueError("POCKETLAB_HARNESS_SESSION must be unset; bootstrap is process-owned")
    if os.environ.get("POCKETLAB_HARNESS_BROWSER_BRIDGE", "").strip():
        raise ValueError("POCKETLAB_HARNESS_BROWSER_BRIDGE must be unset; bridge creation is process-owned")
    if mode not in {"live", "android-cdp"}:
        raise ValueError("unsupported UI-performance qualification mode")
    if candidate_ui and mode not in {"live", "android-cdp"}:
        raise ValueError("candidate UI qualification is available only for live or android-cdp mode")
    return _base_url(mode, candidate_ui=candidate_ui)


@contextlib.contextmanager
def _prepared_candidate_server(enabled: bool, *, source_commit: str):
    """Serve the exact current build while the controller owns the runtime tunnel."""
    if not enabled:
        yield
        return

    server_script = REPO_ROOT / "scripts/dev/lite/ui_performance_candidate_server.py"
    if not server_script.is_file():
        raise RuntimeError("the checked-in candidate server is unavailable")
    process = subprocess.Popen(
        [
            sys.executable,
            str(server_script),
            "--source-commit",
            source_commit,
            "--prepared-runtime",
        ],
        cwd=str(REPO_ROOT),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(Path.home()), "LC_ALL": "C", "LANG": "C"},
    )
    try:
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError("candidate server exited before readiness")
            try:
                with urlopen(f"{CANDIDATE_BASE_URL}/__pocketlab_qualification__/health", timeout=1.5) as response:
                    if response.status == 200:
                        break
            except OSError:
                pass
            time.sleep(0.15)
        else:
            raise RuntimeError("candidate server readiness failed")
        yield
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)


def _session_authority(response: dict) -> tuple[str, str, datetime]:
    token = str(response.get("session_token") or "").strip()
    session = response.get("session")
    if not token or not isinstance(session, dict):
        raise RuntimeError("key-bound qualification returned no usable session")
    session_id = str(session.get("harness_session_id") or "").strip()
    if not session_id:
        raise RuntimeError("key-bound qualification returned no session id")
    return token, session_id, _parse_timestamp(session.get("expires_at"), label="session")


def _bridge_authority(response: dict) -> tuple[str, datetime]:
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
    return token, _parse_timestamp(metadata.get("expires_at"), label="browser bridge")


def _mint_bridge(session_token: str) -> tuple[str, datetime]:
    return _bridge_authority(harness_client.browser_bridge(session_token=session_token))


def _bootstrap_authority(*, principal_id: str, key_file: str, ttl_seconds: int) -> Authority:
    response = harness_client.bootstrap_session(
        principal_id=principal_id,
        key_file=key_file,
        ttl_seconds=ttl_seconds,
    )
    session_token, session_id, session_expires = _session_authority(response)
    bridge_token, bridge_expires = _mint_bridge(session_token)
    return Authority(session_token, session_id, session_expires, bridge_token, bridge_expires)


def _renew_session(
    authority: Authority,
    *,
    principal_id: str,
    key_file: str,
    ttl_seconds: int,
) -> Authority:
    response = harness_client.start_session(
        principal_id=principal_id,
        profile=PROFILE,
        purpose=PURPOSE,
        key_file=key_file,
        ttl_seconds=ttl_seconds,
    )
    new_token, new_id, new_expires = _session_authority(response)
    new_bridge, new_bridge_expires = _mint_bridge(new_token)
    try:
        harness_client.stop_session(session_token=authority.session_token, session_id=authority.session_id)
    except (OSError, RuntimeError, ValueError):
        # The replacement authority is already valid. Cleanup of the principal
        # at the end revokes every remaining session. Do not discard a valid
        # replacement merely because the old session was already expired.
        pass
    return Authority(new_token, new_id, new_expires, new_bridge, new_bridge_expires)


def _before_owner_interaction(
    authority: Authority,
    *,
    principal_id: str,
    key_file: str,
    ttl_seconds: int,
    now: datetime | None = None,
) -> tuple[Authority, str]:
    current = now or _utcnow()
    if _remaining_seconds(authority.session_expires_at, now=current) < SESSION_RENEWAL_THRESHOLD_SECONDS:
        return (
            _renew_session(
                authority,
                principal_id=principal_id,
                key_file=key_file,
                ttl_seconds=ttl_seconds,
            ),
            "session_rotated",
        )
    if _remaining_seconds(authority.bridge_expires_at, now=current) < BRIDGE_RENEWAL_THRESHOLD_SECONDS:
        bridge_token, bridge_expires = _mint_bridge(authority.session_token)
        return (
            Authority(
                authority.session_token,
                authority.session_id,
                authority.session_expires_at,
                bridge_token,
                bridge_expires,
            ),
            "bridge_rotated",
        )
    return authority, "authority_healthy"


def _interactions(args: argparse.Namespace) -> tuple[str | None, ...]:
    requested = tuple(str(value or "").strip().casefold() for value in (args.interaction or ()) if str(value or "").strip())
    for item in requested:
        if not INTERACTION_ID_RE.fullmatch(item):
            raise ValueError(f"invalid interaction id: {item}")
    if requested:
        return requested
    if args.mode == "live":
        return DEFAULT_LIVE_INTERACTIONS
    # The physical Android runner owns its complete matrix internally today.
    # It remains one bounded interaction group until it exposes a per-measurement
    # selector; renewal therefore happens before that group, never mid-run.
    return (None,)


def _checkpoint_path(args: argparse.Namespace) -> Path:
    configured = str(args.controller_checkpoint or "").strip()
    path = Path(configured).expanduser() if configured else DEFAULT_CONTROLLER_CHECKPOINT
    resolved = path.resolve()
    try:
        resolved.relative_to(REPO_ROOT.resolve())
    except ValueError:
        raise ValueError("controller checkpoint must remain inside the repository working tree") from None
    return resolved


def _load_completed(path: Path, *, principal_id: str, mode: str) -> set[str]:
    if not path.exists():
        return set()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    if not isinstance(payload, dict):
        return set()
    if payload.get("principal_id") != principal_id or payload.get("mode") != mode:
        return set()
    values = payload.get("completed_interactions")
    if not isinstance(values, list):
        return set()
    return {str(value) for value in values if isinstance(value, str)}


def _write_checkpoint(
    path: Path,
    *,
    principal_id: str,
    mode: str,
    completed: set[str],
    next_interaction: str | None,
    status: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "1.0.0",
        "principal_id": principal_id,
        "mode": mode,
        "profile": PROFILE,
        "purpose": PURPOSE,
        "target_scope": TARGET_SCOPE,
        "completed_interactions": sorted(completed),
        "next_interaction": next_interaction,
        "status": status,
        "updated_at": _utcnow().isoformat().replace("+00:00", "Z"),
        "contains_secrets": False,
    }
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _clear_performance_evidence() -> None:
    target = REPO_ROOT / ".pocketlab-dev/performance"
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)


def _is_transient_preflight_failure(*, returncode: int, stdout: str, stderr: str) -> bool:
    if returncode == 0:
        return False
    output = f"{stdout}\n{stderr}".casefold()
    return TRANSIENT_PREFLIGHT_MARKER in output


def _is_transient_cleanup_error(exc: BaseException) -> bool:
    output = str(exc).casefold()
    return any(marker in output for marker in TRANSIENT_CLEANUP_MARKERS)


def _run_interaction(
    args: argparse.Namespace,
    *,
    base_url: str,
    authority: Authority,
    principal_id: str,
    key_file: str,
    ttl_seconds: int,
    interaction: str | None,
    secrets: list[str],
) -> tuple[int, Authority]:
    for attempt in range(PREFLIGHT_RETRY_ATTEMPTS):
        if attempt:
            try:
                authority, renewal = _before_owner_interaction(
                    authority,
                    principal_id=principal_id,
                    key_file=key_file,
                    ttl_seconds=ttl_seconds,
                )
                secrets.extend([authority.session_token, authority.bridge_token])
                if renewal != "authority_healthy":
                    print(
                        "[ui-performance-qualified] "
                        f"{renewal} while waiting for runtime preflight"
                    )
            except (OSError, RuntimeError, ValueError) as exc:
                # The runtime may still be restarting.  Keep the bounded
                # preflight retry alive and try authority renewal again at the
                # next safe boundary rather than failing on a transient
                # control-plane outage.
                print(
                    "[ui-performance-qualified] transient authority renewal "
                    "while waiting for runtime preflight: "
                    f"{_redact_output(str(exc)[:160], tuple(secrets))}",
                    file=sys.stderr,
                )
        child = subprocess.run(
            _runner_command(args.mode),
            cwd=str(REPO_ROOT),
            env=_child_environment(
                authority.bridge_token,
                mode=args.mode,
                base_url=base_url,
                interaction=interaction,
            ),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=RUN_TIMEOUT_SECONDS,
            check=False,
        )
        if child.stdout:
            sys.stdout.write(_redact_output(child.stdout, tuple(secrets)))
        if child.stderr:
            sys.stderr.write(_redact_output(child.stderr, tuple(secrets)))
        returncode = int(child.returncode)
        if not _is_transient_preflight_failure(
            returncode=returncode,
            stdout=child.stdout or "",
            stderr=child.stderr or "",
        ) or attempt + 1 >= PREFLIGHT_RETRY_ATTEMPTS:
            return returncode, authority
        print(
            "[ui-performance-qualified] transient runtime preflight failure; "
            f"retrying before measurement attempt={attempt + 2}/{PREFLIGHT_RETRY_ATTEMPTS}",
            file=sys.stderr,
        )
        time.sleep(PREFLIGHT_RETRY_DELAY_SECONDS)
    return 2, authority


def run(args: argparse.Namespace) -> int:
    base_url = _validate_operator_environment(args.mode, candidate_ui=args.candidate_ui)
    principal_id = str(args.principal_id or "").strip().casefold()
    if not PRINCIPAL_ID_RE.fullmatch(principal_id):
        raise ValueError("principal id must be a bounded disposable synthetic identifier")
    key_file = str(Path(args.key_file).expanduser())
    interactions = _interactions(args)
    checkpoint = _checkpoint_path(args)
    completed = _load_completed(checkpoint, principal_id=principal_id, mode=args.mode) if args.resume else set()

    authority: Authority | None = None
    child_returncode = 2
    cleanup_error = ""
    known_secrets: list[str] = []
    previous_api_url = os.environ.get("POCKETLAB_HARNESS_API_URL")
    _clear_performance_evidence()

    try:
        source_commit = ""
        if args.candidate_ui:
            source_commit = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=str(REPO_ROOT), text=True
            ).strip()
        with ui_performance_runtime_tunnel(), _prepared_candidate_server(
            args.candidate_ui,
            source_commit=source_commit,
        ):
            try:
                os.environ["POCKETLAB_HARNESS_API_URL"] = "http://127.0.0.1:18080"
                authority = _bootstrap_authority(
                    principal_id=principal_id,
                    key_file=key_file,
                    ttl_seconds=args.ttl_seconds,
                )
                known_secrets.extend([authority.session_token, authority.bridge_token])

                pending = [
                    interaction
                    for interaction in interactions
                    if interaction is None or interaction not in completed
                ]
                for index, interaction in enumerate(pending):
                    checkpoint_name = interaction or "android-cdp-matrix"
                    _write_checkpoint(
                        checkpoint,
                        principal_id=principal_id,
                        mode=args.mode,
                        completed=completed,
                        next_interaction=checkpoint_name,
                        status="before_interaction",
                    )
                    authority, renewal = _before_owner_interaction(
                        authority,
                        principal_id=principal_id,
                        key_file=key_file,
                        ttl_seconds=args.ttl_seconds,
                    )
                    known_secrets.extend([authority.session_token, authority.bridge_token])
                    print(
                        "[ui-performance-qualified] "
                        f"authority={renewal} interaction={checkpoint_name} "
                        f"session_remaining_s={max(0, int(_remaining_seconds(authority.session_expires_at)))} "
                        f"bridge_remaining_s={max(0, int(_remaining_seconds(authority.bridge_expires_at)))}"
                    )
                    child_returncode, authority = _run_interaction(
                        args,
                        base_url=base_url,
                        authority=authority,
                        principal_id=principal_id,
                        key_file=key_file,
                        ttl_seconds=args.ttl_seconds,
                        interaction=interaction,
                        secrets=known_secrets,
                    )
                    known_secrets.extend([authority.session_token, authority.bridge_token])
                    if child_returncode != 0:
                        _write_checkpoint(
                            checkpoint,
                            principal_id=principal_id,
                            mode=args.mode,
                            completed=completed,
                            next_interaction=checkpoint_name,
                            status=f"interaction_failed:{child_returncode}",
                        )
                        break
                    if interaction is not None:
                        completed.add(interaction)
                    next_name = None
                    if index + 1 < len(pending):
                        next_name = pending[index + 1] or "android-cdp-matrix"
                    _write_checkpoint(
                        checkpoint,
                        principal_id=principal_id,
                        mode=args.mode,
                        completed=completed,
                        next_interaction=next_name,
                        status="interaction_complete",
                    )
                else:
                    child_returncode = 0
                    _write_checkpoint(
                        checkpoint,
                        principal_id=principal_id,
                        mode=args.mode,
                        completed=completed,
                        next_interaction=None,
                        status="complete",
                    )
            finally:
                if authority is not None and authority.session_token:
                    for cleanup_attempt in range(CLEANUP_RETRY_ATTEMPTS):
                        try:
                            # Ensure cleanup authority is still usable. Session
                            # rotation is allowed here because no measurement is in
                            # progress.
                            authority, _ = _before_owner_interaction(
                                authority,
                                principal_id=principal_id,
                                key_file=key_file,
                                ttl_seconds=args.ttl_seconds,
                            )
                            harness_client.revoke_authenticated_principal(
                                session_token=authority.session_token
                            )
                            cleanup_error = ""
                            break
                        except (OSError, RuntimeError, ValueError) as exc:
                            cleanup_error = _redact_output(str(exc)[:240], tuple(known_secrets))
                            if (
                                not _is_transient_cleanup_error(exc)
                                or cleanup_attempt + 1 >= CLEANUP_RETRY_ATTEMPTS
                            ):
                                break
                            print(
                                "[ui-performance-qualified] transient cleanup transport failure; "
                                f"retrying attempt={cleanup_attempt + 2}/{CLEANUP_RETRY_ATTEMPTS}",
                                file=sys.stderr,
                            )
                            time.sleep(CLEANUP_RETRY_DELAY_SECONDS)
    except subprocess.TimeoutExpired:
        child_returncode = 124
        print("[ui-performance-qualified] ERROR fixed UI-performance interaction timed out", file=sys.stderr)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"[ui-performance-qualified] ERROR {str(exc)[:320]}", file=sys.stderr)
    finally:
        if previous_api_url is None:
            os.environ.pop("POCKETLAB_HARNESS_API_URL", None)
        else:
            os.environ["POCKETLAB_HARNESS_API_URL"] = previous_api_url

    if cleanup_error:
        print(f"[ui-performance-qualified] ERROR synthetic principal cleanup failed: {cleanup_error}", file=sys.stderr)
        return 2
    if child_returncode == 0:
        print(
            "[ui-performance-qualified] cleanup passed; profile=qualification-owner "
            "purpose=ui-performance-60fps target=local_server_host_only "
            f"ttl_seconds={args.ttl_seconds} session_renew_before={SESSION_RENEWAL_THRESHOLD_SECONDS}s "
            f"bridge_renew_before={BRIDGE_RENEWAL_THRESHOLD_SECONDS}s "
            "destructive=false test_auth_bypass=false"
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
    parser.add_argument(
        "--interaction",
        action="append",
        help="Run one bounded live interaction per child; may be repeated. Defaults to the fixed live matrix.",
    )
    parser.add_argument(
        "--controller-checkpoint",
        help="Untracked non-secret controller checkpoint path inside the repository.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip completed live interactions recorded in the non-secret controller checkpoint.",
    )
    parser.add_argument(
        "--candidate-ui",
        action="store_true",
        help="Serve the exact current dist build through the checked-in candidate proxy for live or android-cdp mode.",
    )
    return run(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
