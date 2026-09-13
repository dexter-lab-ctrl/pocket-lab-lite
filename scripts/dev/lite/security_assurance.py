#!/usr/bin/env python3
"""Bounded loopback client for the server-owned Runtime Security Assurance API.

The client submits only a registered suite/scenario and never accepts a URL,
command, argv, target, scanner option, filesystem path, or NATS subject.  The
private Ed25519 key is used only by the existing harness client; this client
receives a short-lived session through an environment variable and never
prints it.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


API_URL = "http://127.0.0.1:8080"
SESSION_ENV = "POCKETLAB_HARNESS_SESSION"
RUN_ID_RE = re.compile(r"^assurance-[0-9a-f]{32}$")
POLL_SECONDS = 2.0
MAX_POLL_SECONDS = 2 * 60 * 60


def _request(method: str, path: str, payload: dict | None = None, *, authenticated: bool = False) -> dict:
    if not path.startswith("/api/lite/harness/security-assurance/") or ".." in path or "//" in path:
        raise ValueError("assurance API path is not registered")
    body = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if authenticated:
        token = os.environ.get(SESSION_ENV, "").strip()
        if not token:
            raise ValueError(f"{SESSION_ENV} is required")
        headers["X-Pocket-Lab-Harness-Session"] = token
    request = urllib.request.Request(API_URL + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            raw = response.read(256 * 1024)
            result = json.loads(raw.decode("utf-8")) if raw else {}
            return result if isinstance(result, dict) else {"result": result}
    except urllib.error.HTTPError as exc:
        raw = exc.read(32 * 1024)
        try:
            detail = json.loads(raw.decode("utf-8")) if raw else {}
        except (UnicodeDecodeError, json.JSONDecodeError):
            detail = {}
        if isinstance(detail.get("detail"), dict):
            detail = detail["detail"]
        reason = str(detail.get("reason_code") or "assurance_request_failed")[:80]
        raise RuntimeError(f"{reason}: the assurance request was rejected") from None
    except (OSError, urllib.error.URLError) as exc:
        raise RuntimeError(f"assurance_transport_unavailable: {type(exc).__name__}") from None


def _safe_run_id(value: str) -> str:
    if not RUN_ID_RE.fullmatch(str(value or "").strip()):
        raise ValueError("run identifier is invalid")
    return str(value).strip()


def cmd_check(_args: argparse.Namespace) -> dict:
    runtime = Path(__file__).resolve().parents[3] / "pocket-lab-final-structure" / "runtime"
    sys.path.insert(0, str(runtime))
    from api_fastapi.services import lite_security_assurance

    return {"registry": lite_security_assurance.check_registries(), "sanitized": True}


def cmd_preflight(args: argparse.Namespace) -> dict:
    suite = str(args.suite_id)
    return _request("GET", f"/api/lite/harness/security-assurance/preflight?suite_id={suite}", authenticated=True)


def _terminal_status(result: dict) -> str:
    return str(result.get("status") or "").upper()


def _poll(run_id: str) -> dict:
    deadline = time.monotonic() + MAX_POLL_SECONDS
    result: dict = {}
    while time.monotonic() < deadline:
        result = _request("GET", f"/api/lite/harness/security-assurance/runs/{run_id}", authenticated=True)
        if _terminal_status(result) not in {"QUEUED", "RUNNING"}:
            return result
        time.sleep(POLL_SECONDS)
    raise RuntimeError("assurance_poll_timeout: the run did not reach a terminal state")


def cmd_run(args: argparse.Namespace) -> dict:
    payload = {"suite_id": args.suite_id}
    if args.scenario_id:
        payload["scenario_id"] = args.scenario_id
    if args.baseline_run_id:
        payload["baseline_run_id"] = _safe_run_id(args.baseline_run_id)
    queued = _request("POST", "/api/lite/harness/security-assurance/runs", payload, authenticated=True)
    run_id = _safe_run_id(str(queued.get("run_id") or ""))
    result = _poll(run_id)
    return {
        "run": result,
        "run_id": run_id,
        "report": _request("GET", f"/api/lite/harness/security-assurance/runs/{run_id}/report", authenticated=True),
        "sanitized": True,
    }


def cmd_report(args: argparse.Namespace) -> dict:
    run_id = _safe_run_id(args.run_id)
    return _request("GET", f"/api/lite/harness/security-assurance/runs/{run_id}/report", authenticated=True)


def cmd_compare(args: argparse.Namespace) -> dict:
    report = cmd_report(args)
    files = report.get("files") if isinstance(report.get("files"), dict) else {}
    return {"run_id": args.run_id, "delta": files.get("delta.json", {}), "sanitized": True}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Pocket Lab loopback Runtime Security Assurance client")
    commands = parser.add_subparsers(dest="command", required=True)

    check = commands.add_parser("check", help="show registered assurance capabilities and suites")
    check.set_defaults(handler=cmd_check, success_status=True)

    preflight = commands.add_parser("preflight", help="run fixed local admission checks")
    preflight.add_argument("suite_id", choices=("smoke", "standard", "deep", "adversarial"))
    preflight.set_defaults(handler=cmd_preflight, success_status=False)

    run = commands.add_parser("run", help="run one registered assurance suite")
    run.add_argument("suite_id", choices=("smoke", "standard", "deep", "adversarial"))
    run.add_argument("--scenario-id", dest="scenario_id")
    run.add_argument("--baseline-run-id", dest="baseline_run_id")
    run.set_defaults(handler=cmd_run, success_status=False)

    scenario = commands.add_parser("scenario", help="run one registered scenario in Standard")
    scenario.add_argument("scenario_id")
    scenario.set_defaults(handler=lambda args: cmd_run(argparse.Namespace(
        suite_id="standard",
        scenario_id=args.scenario_id,
        baseline_run_id=None,
    )), success_status=False)

    report = commands.add_parser("report", help="read a sanitized report")
    report.add_argument("run_id")
    report.set_defaults(handler=cmd_report, success_status=True)

    compare = commands.add_parser("compare", help="show the normalized baseline delta")
    compare.add_argument("run_id")
    compare.set_defaults(handler=cmd_compare, success_status=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = args.handler(args)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"ERROR {str(exc)[:320]}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2))
    if args.success_status:
        return 0
    status = _terminal_status(result.get("run") if isinstance(result.get("run"), dict) else result)
    if status in {"READY", "PASS", "SUCCEEDED", "SUCCESS", "COMPLETED"}:
        return 0
    return {"FAIL": 10, "PARTIAL": 11, "BLOCKED": 12, "DEGRADED": 11}.get(status, 0)


if __name__ == "__main__":
    raise SystemExit(main())
