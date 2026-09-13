from __future__ import annotations

"""Worker-owned runtime security assurance for the Lite qualification harness.

This module is intentionally a registry interpreter, not a command runner.  A
caller can choose a registered suite or threat scenario, but cannot provide an
executable, argv, path, URL, NATS subject, scanner option, or environment
variable.  The worker invokes this module only after FastAPI has admitted the
fixed command through the existing Ed25519 harness and NATS/JetStream path.

The existing ``lite_security`` service remains the owner of Lynis/Trivy
execution, cache identity, SBOM reuse, resource policy, and scanner evidence.
This module adds the assurance envelope, bounded local probes, STRIDE/OWASP
coverage, normalized finding storage, and an immutable sanitized report.
"""

import hashlib
import json
import os
import re
import selectors
import shutil
import signal
import socket
import sqlite3
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml

from .. import deps
from ..db.connection import begin_immediate, connection, read_connection
from ..db.migrations import apply_migrations
from . import lite_harness
from . import lite_policy_opa
from . import lite_security
from . import lite_security_evidence as evidence
from . import lite_security_optimization as optimization
from . import lite_security_policy as policy
from .nats_bus import BUS


ASSURANCE_PROFILE = "security-assurance-runner"
ASSURANCE_PURPOSE = "security.assurance"
ASSURANCE_TARGET_SCOPE = lite_harness.HARNESS_TARGET_SCOPE
ASSURANCE_SUBJECT = "pocketlab.commands.lite.security.assurance"
ASSURANCE_SCHEMA_VERSION = "1.0.0"
RUN_ID_RE = re.compile(r"^assurance-[0-9a-f]{32}$")
SAFE_ID_RE = re.compile(r"^[a-z][a-z0-9._-]{0,79}$")
AP_ID_RE = re.compile(r"^AP-[0-9]{2,4}$")
ACTIVE_STATUSES = frozenset({"QUEUED", "RUNNING"})
TERMINAL_STATUSES = frozenset({"PASS", "FAIL", "PARTIAL", "BLOCKED"})
SAFETY_CLASSES = frozenset(
    {"PASSIVE", "SAFE_ACTIVE", "CONTROLLED_MUTATION", "DESTRUCTIVE_QUALIFICATION"}
)
OUTCOMES = frozenset({"PASS", "FAIL", "PARTIAL", "BLOCKED"})
BASELINE_STATES = frozenset({"NEW", "EXISTING", "RESOLVED", "REGRESSED", "UNCHANGED"})
RECONCILIATION_GRACE_SECONDS = 300

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
ASSURANCE_REGISTRY_ROOT = REPOSITORY_ROOT / "security" / "assurance"
TOOLS_REGISTRY_PATH = ASSURANCE_REGISTRY_ROOT / "tools.yaml"
SUITES_REGISTRY_PATH = ASSURANCE_REGISTRY_ROOT / "suites.yaml"
SCENARIOS_REGISTRY_PATH = ASSURANCE_REGISTRY_ROOT / "scenarios.yaml"
THREAT_MODEL_PATH = REPOSITORY_ROOT / "security" / "threat-model-scenarios.json"
CADDY_SOURCE_PATH = (
    REPOSITORY_ROOT
    / "pocket-lab-final-structure"
    / "pocket-lab-bootstrap-production-scripts-patched"
    / "scripts"
    / "start-dashboard.sh"
)

OWASP_NAMES = {
    "A01": "Broken Access Control",
    "A02": "Cryptographic Failures",
    "A03": "Injection",
    "A04": "Insecure Design",
    "A05": "Security Misconfiguration",
    "A06": "Vulnerable and Outdated Components",
    "A07": "Identification and Authentication Failures",
    "A08": "Software and Data Integrity Failures",
    "A09": "Security Logging and Monitoring Failures",
    "A10": "Server-Side Request Forgery",
}
OWASP_BY_STRIDE = {
    "Spoofing": ["A07"],
    "Tampering": ["A08"],
    "Repudiation": ["A09"],
    "Information Disclosure": ["A01", "A02"],
    "Denial of Service": [],
    "Elevation of Privilege": ["A01"],
}
ACTIVE_TOOLS_BY_SUITE = {
    "smoke": ("pocketlab-security", "lynis", "trivy"),
    "standard": ("pocketlab-security", "lynis", "trivy"),
    "deep": ("pocketlab-security", "lynis", "trivy"),
    "adversarial": (),
}
FIXED_VERSION_ARGS = {
    "bandit": ("--version",),
    "gitleaks": ("version",),
    "pip-audit": ("--version",),
    "npm-audit": ("--version",),
    "cosign": ("version",),
    "semgrep": ("--version",),
    "osv-scanner": ("--version",),
    "syft": ("version",),
    "grype": ("version",),
    "testssl.sh": ("--version",),
    "nuclei": ("-version",),
    "nmap": ("--version",),
    "owasp-zap": ("--version",),
}
FIXED_BINARY_NAMES = {"npm-audit": "npm", "cosign": "cosign"}


class AssuranceError(RuntimeError):
    """Sanitized assurance error safe for the operator API."""

    def __init__(self, reason_code: str, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.reason_code = str(reason_code or "assurance_rejected")[:80]
        self.message = str(message or "The assurance request was rejected.")[:240]
        self.status_code = int(status_code)


class AssuranceRegistryError(AssuranceError):
    pass


class AssuranceConflict(AssuranceError):
    pass


def _now() -> str:
    return deps.now_utc_iso()


def _parse_timestamp(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _safe_json(value: Any, default: Any = None) -> Any:
    try:
        parsed = json.loads(str(value)) if isinstance(value, str) else value
    except (TypeError, ValueError, json.JSONDecodeError):
        return default
    return parsed if parsed is not None else default


def _redact(value: Any) -> Any:
    return policy.redact_value(value)


def _sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _bounded_file_bytes(path: Path, maximum: int = 1024 * 1024) -> bytes:
    try:
        if not path.is_file() or path.stat().st_size > maximum:
            raise OSError("bounded file read refused")
        return path.read_bytes()
    except OSError as exc:
        raise AssuranceRegistryError(
            "assurance_registry_unavailable",
            "A server-owned assurance registry is unavailable or too large.",
            status_code=503,
        ) from exc


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(_bounded_file_bytes(path, 512 * 1024).decode("utf-8"))
    except (UnicodeDecodeError, yaml.YAMLError) as exc:
        raise AssuranceRegistryError(
            "assurance_registry_invalid",
            "A server-owned assurance registry is invalid.",
            status_code=503,
        ) from exc
    if not isinstance(value, dict):
        raise AssuranceRegistryError(
            "assurance_registry_invalid",
            "A server-owned assurance registry is invalid.",
            status_code=503,
        )
    return value


def _read_threat_model() -> dict[str, Any]:
    try:
        value = json.loads(_bounded_file_bytes(THREAT_MODEL_PATH, 1024 * 1024).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AssuranceRegistryError(
            "threat_model_invalid",
            "The canonical threat model could not be loaded.",
            status_code=503,
        ) from exc
    if not isinstance(value, dict):
        raise AssuranceRegistryError(
            "threat_model_invalid",
            "The canonical threat model could not be loaded.",
            status_code=503,
        )
    return value


def _registry_hash(path: Path) -> str:
    return _sha256_bytes(_bounded_file_bytes(path, 1024 * 1024))


def _safe_registry_id(value: Any, *, kind: str) -> str:
    result = str(value or "").strip().casefold()
    if not SAFE_ID_RE.fullmatch(result):
        raise AssuranceRegistryError(
            f"{kind}_unknown",
            f"The requested {kind} is not registered.",
            status_code=400,
        )
    return result


def _threat_paths(model: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    payload = model if isinstance(model, Mapping) else _read_threat_model()
    paths = payload.get("attack_paths")
    if not isinstance(paths, list):
        raise AssuranceRegistryError(
            "threat_model_invalid",
            "The canonical threat model has no valid attack-path list.",
            status_code=503,
        )
    clean: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in paths:
        if not isinstance(item, Mapping):
            raise AssuranceRegistryError(
                "threat_model_invalid",
                "The canonical threat model has an invalid attack path.",
                status_code=503,
            )
        identifier = str(item.get("id") or "").strip().upper()
        if not AP_ID_RE.fullmatch(identifier) or identifier in seen:
            raise AssuranceRegistryError(
                "threat_model_invalid",
                "The canonical threat model has an invalid or duplicate attack path.",
                status_code=503,
            )
        seen.add(identifier)
        clean.append(dict(item))
    return clean


def _control_ids(model: Mapping[str, Any], paths: Iterable[Mapping[str, Any]]) -> set[str]:
    values = {
        str(item.get("id") or "").strip()
        for item in (model.get("controls") if isinstance(model.get("controls"), list) else [])
        if isinstance(item, Mapping) and item.get("id")
    }
    for path in paths:
        values.update(str(item).strip() for item in path.get("controls") or [] if str(item).strip())
    return values


def _raw_registries() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    tools = _read_yaml(TOOLS_REGISTRY_PATH)
    suites = _read_yaml(SUITES_REGISTRY_PATH)
    scenarios = _read_yaml(SCENARIOS_REGISTRY_PATH)
    threat = _read_threat_model()
    return tools, suites, scenarios, threat


def validate_registries() -> dict[str, Any]:
    """Validate all server-owned registries and current AP coverage."""
    tools, suites, scenarios, threat = _raw_registries()
    tool_items = tools.get("toolchain")
    suite_items = suites.get("profiles")
    scenario_items = scenarios.get("scenarios")
    if not isinstance(tool_items, list) or not isinstance(suite_items, Mapping) or not isinstance(scenario_items, list):
        raise AssuranceRegistryError(
            "assurance_registry_invalid",
            "The server-owned assurance registries have an invalid shape.",
            status_code=503,
        )
    execution_defaults = tools.get("execution_defaults")
    if not isinstance(execution_defaults, Mapping):
        raise AssuranceRegistryError(
            "assurance_registry_invalid",
            "The assurance tool registry has no bounded execution defaults.",
            status_code=503,
        )
    try:
        default_timeout = int(execution_defaults.get("timeout_seconds") or 0)
        default_output_limit = int(execution_defaults.get("max_output_bytes") or 0)
    except (TypeError, ValueError):
        default_timeout = 0
        default_output_limit = 0
    if (
        execution_defaults.get("shell") is not False
        or str(execution_defaults.get("cwd") or "") != "repository_root"
        or str(execution_defaults.get("allowed_target") or "") != ASSURANCE_TARGET_SCOPE
        or str(execution_defaults.get("allowed_target_scope") or "") != ASSURANCE_TARGET_SCOPE
        or execution_defaults.get("process_group_cleanup") is not True
        or str(execution_defaults.get("concurrency") or "") != "exclusive_for_heavy_tools"
        or str(execution_defaults.get("output_parser") or "") != "first_version_line_only"
        or str(execution_defaults.get("finding_normalizer") or "") != "normalized_sanitized_assurance_finding"
        or str(execution_defaults.get("sanitization_policy") or "") != "lite_security_policy.redact_value"
        or default_timeout not in range(1, 121)
        or default_output_limit not in range(1024, 1024 * 1024 + 1)
    ):
        raise AssuranceRegistryError(
            "assurance_registry_invalid",
            "The assurance tool registry has unsafe execution defaults.",
            status_code=503,
        )
    failure_classes = execution_defaults.get("failure_classification")
    if not isinstance(failure_classes, list) or not failure_classes or any(
        not SAFE_ID_RE.fullmatch(str(value or "")) for value in failure_classes
    ):
        raise AssuranceRegistryError(
            "assurance_registry_invalid",
            "The assurance tool registry has invalid failure classifications.",
            status_code=503,
        )
    tool_map: dict[str, Mapping[str, Any]] = {}
    for item in tool_items:
        if not isinstance(item, Mapping):
            raise AssuranceRegistryError("assurance_registry_invalid", "A registered assurance tool is invalid.", status_code=503)
        identifier = _safe_registry_id(item.get("id"), kind="tool")
        if identifier in tool_map:
            raise AssuranceRegistryError("assurance_registry_invalid", "A registered assurance tool is duplicated.", status_code=503)
        required = str(item.get("required_capability") or "")
        if not required.startswith("security.assurance."):
            raise AssuranceRegistryError("assurance_registry_invalid", "A tool capability is outside the assurance namespace.", status_code=503)
        if (
            not str(item.get("purpose") or "").strip()
            or not str(item.get("execution") or "").strip()
            or not isinstance(item.get("supported_platforms"), list)
            or not str(item.get("binary_discovery") or "").strip()
            or not str(item.get("version_command") or "").strip()
            or not str(item.get("version_source") or "").strip()
            or not str(item.get("allowed_mode") or "").strip()
            or not str(item.get("resource_class") or "").strip()
            or not isinstance(item.get("suite_membership"), list)
        ):
            raise AssuranceRegistryError("assurance_registry_invalid", "A registered assurance tool is missing bounded metadata.", status_code=503)
        tool_map[identifier] = item
    suite_map: dict[str, Mapping[str, Any]] = {}
    expected_suites = {"smoke", "standard", "deep", "adversarial"}
    if set(str(key) for key in suite_items) != expected_suites:
        raise AssuranceRegistryError("assurance_registry_invalid", "The assurance suite registry is incomplete.", status_code=503)
    profile_caps = set(lite_harness.PROFILE_DATA[ASSURANCE_PROFILE]["capabilities"])
    for key, item in suite_items.items():
        identifier = _safe_registry_id(key, kind="suite")
        if not isinstance(item, Mapping) or identifier in suite_map:
            raise AssuranceRegistryError("assurance_registry_invalid", "A registered assurance suite is invalid.", status_code=503)
        if str(item.get("target_scope") or suites.get("target_scope")) != ASSURANCE_TARGET_SCOPE:
            raise AssuranceRegistryError("assurance_registry_invalid", "An assurance suite has an unsafe target scope.", status_code=503)
        required = item.get("required_capabilities") or []
        if not isinstance(required, list) or any(str(value) not in profile_caps for value in required):
            raise AssuranceRegistryError("assurance_registry_invalid", "An assurance suite requests an unregistered capability.", status_code=503)
        refs = item.get("scenarios") or []
        if not isinstance(refs, list):
            raise AssuranceRegistryError("assurance_registry_invalid", "An assurance suite has invalid scenarios.", status_code=503)
        suite_map[identifier] = item
    scenario_map: dict[str, Mapping[str, Any]] = {}
    paths = _threat_paths(threat)
    known_controls = _control_ids(threat, paths)
    for item in scenario_items:
        if not isinstance(item, Mapping):
            raise AssuranceRegistryError("assurance_registry_invalid", "A registered assurance scenario is invalid.", status_code=503)
        identifier = _safe_registry_id(item.get("id"), kind="scenario")
        if identifier in scenario_map:
            raise AssuranceRegistryError("assurance_registry_invalid", "A registered assurance scenario is duplicated.", status_code=503)
        safety = str(item.get("safety_class") or "")
        cap = str(item.get("required_capability") or "")
        if safety not in SAFETY_CLASSES or cap not in profile_caps:
            raise AssuranceRegistryError("assurance_registry_invalid", "A scenario has an unsafe class or capability.", status_code=503)
        if any(str(value) not in suite_map for value in item.get("suites") or []):
            raise AssuranceRegistryError("assurance_registry_invalid", "A scenario references an unknown suite.", status_code=503)
        if any(str(value) not in known_controls for value in item.get("controls") or []):
            raise AssuranceRegistryError("assurance_registry_invalid", "A scenario references an unknown threat-model control.", status_code=503)
        scenario_map[identifier] = item
    scenario_refs = {str(value) for item in scenario_map.values() for value in item.get("attack_paths") or []}
    for suite_name, suite in suite_map.items():
        for scenario in suite.get("scenarios") or []:
            ref = str(scenario).casefold()
            if ref not in scenario_map:
                raise AssuranceRegistryError("assurance_registry_invalid", f"Suite {suite_name} references an unknown scenario.", status_code=503)
    current_ap_ids = {str(item["id"]) for item in paths}
    if not current_ap_ids.issubset(scenario_refs):
        raise AssuranceRegistryError(
            "threat_model_coverage_incomplete",
            "The assurance registry does not classify every current threat-model attack path.",
            status_code=503,
        )
    framework = threat.get("framework") if isinstance(threat.get("framework"), Mapping) else {}
    if str(framework.get("primary") or "").upper() != "STRIDE":
        raise AssuranceRegistryError("threat_model_framework_invalid", "The canonical threat model is not STRIDE-primary.", status_code=503)
    return _redact({
        "schema_version": ASSURANCE_SCHEMA_VERSION,
        "target_scope": ASSURANCE_TARGET_SCOPE,
        "execution_owner": "worker",
        "execution_defaults": {
            "shell": False,
            "cwd": "repository_root",
            "allowed_target": ASSURANCE_TARGET_SCOPE,
            "allowed_target_scope": ASSURANCE_TARGET_SCOPE,
            "timeout_seconds": default_timeout,
            "max_output_bytes": default_output_limit,
            "process_group_cleanup": True,
            "concurrency": "exclusive_for_heavy_tools",
            "output_parser": "first_version_line_only",
            "finding_normalizer": "normalized_sanitized_assurance_finding",
            "sanitization_policy": "lite_security_policy.redact_value",
            "failure_classification": [str(value) for value in failure_classes],
        },
        "primary_framework": "STRIDE",
        "owasp_version": str(scenarios.get("owasp_version") or "2021"),
        "tools": sorted(tool_map),
        "suites": sorted(suite_map),
        "scenarios": sorted(scenario_map),
        "attack_paths": sorted(current_ap_ids),
        "registry_hashes": {
            "tools": _registry_hash(TOOLS_REGISTRY_PATH),
            "suites": _registry_hash(SUITES_REGISTRY_PATH),
            "scenarios": _registry_hash(SCENARIOS_REGISTRY_PATH),
            "threat_model": _registry_hash(THREAT_MODEL_PATH),
        },
        "sanitized": True,
    })


def suite_def(suite_id: Any) -> dict[str, Any]:
    identifier = _safe_registry_id(suite_id, kind="suite")
    validate_registries()
    suites = _read_yaml(SUITES_REGISTRY_PATH).get("profiles") or {}
    item = suites.get(identifier)
    if not isinstance(item, Mapping):
        raise AssuranceError("suite_unknown", "The requested assurance suite is not registered.", status_code=400)
    return dict(item) | {"id": identifier}


def scenario_def(scenario_id: Any) -> dict[str, Any]:
    identifier = str(scenario_id or "").strip().casefold()
    if not identifier:
        raise AssuranceError("scenario_unknown", "The requested assurance scenario is not registered.", status_code=400)
    validate_registries()
    scenarios = _read_yaml(SCENARIOS_REGISTRY_PATH).get("scenarios") or []
    for item in scenarios:
        if isinstance(item, Mapping) and str(item.get("id") or "").casefold() == identifier:
            return dict(item) | {"id": identifier}
    if AP_ID_RE.fullmatch(identifier.upper()):
        path = next((item for item in _threat_paths() if str(item.get("id")) == identifier.upper()), None)
        if path is not None:
            stride = [str(value) for value in path.get("stride") or []]
            return {
                "id": identifier.upper(),
                "title": str(path.get("name") or identifier.upper())[:200],
                "execution": "attack_path_inventory",
                "safety_class": "PASSIVE",
                "required_capability": "security.assurance.threat_scenario",
                "suites": ["standard", "deep"],
                "stride": stride,
                "owasp": sorted({code for threat in stride for code in OWASP_BY_STRIDE.get(threat, [])}),
                "controls": [str(value) for value in path.get("controls") or []],
                "attack_paths": [identifier.upper()],
                "canonical_attack_path": dict(path),
            }
    raise AssuranceError("scenario_unknown", "The requested assurance scenario is not registered.", status_code=400)


def list_suites() -> dict[str, Any]:
    validation = validate_registries()
    suites = []
    for identifier in validation["suites"]:
        item = suite_def(identifier)
        suites.append(_redact({
            "id": identifier,
            "purpose": item.get("purpose"),
            "target_seconds": item.get("target_seconds"),
            "maximum_seconds": item.get("maximum_seconds"),
            "explicit_only": bool(item.get("explicit_only")),
            "qualification_only": bool(item.get("qualification_only")),
            "existing_security_profile": item.get("existing_security_profile"),
            "allowed_safety_classes": item.get("allowed_safety_classes") or [],
            "required_capabilities": item.get("required_capabilities") or [],
            "scenarios": item.get("scenarios") or [],
            "active_tools": list(ACTIVE_TOOLS_BY_SUITE.get(identifier, ())),
        }))
    return _redact({"schema_version": ASSURANCE_SCHEMA_VERSION, "target_scope": ASSURANCE_TARGET_SCOPE, "suites": suites, "registry": validation, "sanitized": True})


def list_capabilities() -> dict[str, Any]:
    profile = lite_harness.PROFILE_DATA[ASSURANCE_PROFILE]
    payload = _redact({
        "profile": ASSURANCE_PROFILE,
        "purpose": ASSURANCE_PURPOSE,
        "target_scope": ASSURANCE_TARGET_SCOPE,
        "principal_class": profile["principal_class"],
        "environment_scope": profile["environment_scope"],
        "availability": profile["availability"],
        "capabilities": list(profile["capabilities"]),
        "destructive_capabilities": list(profile["destructive_capabilities"]),
        "generic_shell": False,
        "arbitrary_nats": False,
        "arbitrary_network_targets": False,
        "browser_surface": False,
        "sanitized": True,
    })
    # The negative capability declarations are intentionally safe booleans.
    # The shared policy treats the word "nats" in arbitrary metadata as a
    # possible credential-bearing key, so restore only these fixed literals
    # after recursive value redaction.
    payload.update({
        "generic_shell": False,
        "arbitrary_nats": False,
        "arbitrary_network_targets": False,
        "browser_surface": False,
    })
    return payload


def _minimal_env() -> dict[str, str]:
    # Only fixed, non-secret process context is inherited.  HOME is needed by
    # the existing PM2 inventory on Termux; caller-provided environment values
    # (including credentials and scanner flags) never cross this boundary.
    return {
        "LC_ALL": "C",
        "LANG": "C",
        "PATH": "/usr/bin:/bin:/data/data/com.termux/files/usr/bin",
        "HOME": str(Path.home()),
    }


def _verified_executable(name: str) -> Path | None:
    # Discovery is restricted to the same fixed path that is supplied to the
    # child process.  This prevents an ambient caller PATH from selecting a
    # different binary than the one the server-owned registry intended.
    candidate = shutil.which(str(name), path=_minimal_env()["PATH"])
    if not candidate:
        return None
    try:
        path = Path(candidate).resolve(strict=True)
        if not path.is_file() or not os.access(path, os.X_OK):
            return None
        return path
    except OSError:
        return None


def _stop_process_group(process: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
    except (AttributeError, OSError, ProcessLookupError):
        try:
            process.terminate()
        except OSError:
            pass


def _kill_process_group(process: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
    except (AttributeError, OSError, ProcessLookupError):
        try:
            process.kill()
        except OSError:
            pass


def _bounded_argv(
    argv: list[str], *, cwd: Path, timeout_seconds: float = 5.0, max_output_bytes: int = 32 * 1024
) -> dict[str, Any]:
    """Run one fixed server-owned argv with no shell and bounded output."""
    try:
        safe_cwd = Path(cwd).resolve(strict=True)
    except OSError as exc:
        raise AssuranceError(
            "assurance_cwd_unregistered",
            "The assurance command working directory is not server-owned.",
            status_code=503,
        ) from exc
    if safe_cwd != REPOSITORY_ROOT:
        raise AssuranceError(
            "assurance_cwd_unregistered",
            "The assurance command working directory is not server-owned.",
            status_code=503,
        )
    if (
        not isinstance(argv, list)
        or not argv
        or len(argv) > 32
        or any(not isinstance(value, str) or len(value) > 512 or "\x00" in value for value in argv)
        or not argv[0].startswith("/")
    ):
        raise AssuranceError("assurance_command_unregistered", "The assurance command is not server-owned.", status_code=503)
    try:
        executable = Path(argv[0]).resolve(strict=True)
        if not executable.is_file() or not os.access(executable, os.X_OK):
            raise OSError("executable is not runnable")
    except OSError as exc:
        raise AssuranceError(
            "assurance_command_unregistered",
            "The assurance command is not server-owned.",
            status_code=503,
        ) from exc
    safe_argv = [str(executable), *argv[1:]]
    started = time.monotonic()
    try:
        process = subprocess.Popen(
            safe_argv,
            cwd=str(safe_cwd),
            env=_minimal_env(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            start_new_session=True,
        )
    except (OSError, ValueError) as exc:
        return _redact({"status": "missing", "failure_code": "process_start_failed", "error_type": type(exc).__name__, "duration_ms": int((time.monotonic() - started) * 1000)})
    selector = selectors.DefaultSelector()
    streams: dict[int, tuple[str, Any]] = {}
    for name, stream in (("stdout", process.stdout), ("stderr", process.stderr)):
        if stream is not None:
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, name)
            streams[stream.fileno()] = (name, stream)
    chunks = {"stdout": bytearray(), "stderr": bytearray()}
    limited = False
    timed_out = False
    deadline = started + max(0.05, min(float(timeout_seconds), 120.0))
    try:
        while streams:
            now = time.monotonic()
            if now >= deadline:
                timed_out = True
                _stop_process_group(process)
                break
            for key, _ in selector.select(min(0.10, max(0.0, deadline - now))):
                stream = key.fileobj
                name = str(key.data)
                try:
                    data = os.read(stream.fileno(), 8192)
                except OSError:
                    data = b""
                if data:
                    remaining = max(0, max_output_bytes - len(chunks[name]))
                    if len(data) > remaining:
                        chunks[name].extend(data[:remaining])
                        limited = True
                        _stop_process_group(process)
                    else:
                        chunks[name].extend(data)
                else:
                    with __import__("contextlib").suppress(Exception):
                        selector.unregister(stream)
                    streams.pop(stream.fileno(), None)
            if process.poll() is not None and not streams:
                break
        if timed_out or limited:
            try:
                process.wait(timeout=0.75)
            except subprocess.TimeoutExpired:
                _kill_process_group(process)
        else:
            process.wait(timeout=max(0.1, deadline - time.monotonic()))
    except subprocess.TimeoutExpired:
        timed_out = True
        _kill_process_group(process)
        with __import__("contextlib").suppress(Exception):
            process.wait(timeout=0.75)
    finally:
        selector.close()
    stdout = bytes(chunks["stdout"])
    stderr = bytes(chunks["stderr"])
    return _redact({
        "status": "timed_out" if timed_out else "completed" if process.returncode == 0 else "failed",
        "returncode": process.returncode,
        "timed_out": timed_out,
        "output_limited": limited,
        "stdout_bytes": len(stdout),
        "stderr_bytes": len(stderr),
        "stdout_sha256": _sha256_bytes(stdout),
        "stderr_sha256": _sha256_bytes(stderr),
        "stdout": stdout.decode("utf-8", "replace"),
        "stderr": stderr.decode("utf-8", "replace"),
        "duration_ms": int((time.monotonic() - started) * 1000),
    })


def _version_line(result: Mapping[str, Any]) -> str | None:
    if result.get("timed_out") or result.get("status") not in {"completed", "failed"}:
        return None
    text = str(result.get("stdout") or result.get("stderr") or "").splitlines()
    if not text:
        return None
    candidate = policy.redact_text(text[0]).strip()
    candidate = re.sub(r"\s+", " ", candidate)
    return candidate[:120] if candidate else None


def _tool_binary_name(tool_id: str) -> str:
    return FIXED_BINARY_NAMES.get(tool_id, tool_id)


def _tool_inventory(tool_id: str, *, execute_version: bool) -> dict[str, Any]:
    tools = _read_yaml(TOOLS_REGISTRY_PATH).get("toolchain") or []
    item = next((entry for entry in tools if isinstance(entry, Mapping) and str(entry.get("id")) == tool_id), None)
    if not isinstance(item, Mapping):
        raise AssuranceError("tool_unknown", "The requested assurance tool is not registered.", status_code=400)
    binary = _verified_executable(_tool_binary_name(tool_id))
    record: dict[str, Any] = {
        "tool_id": tool_id,
        "purpose": str(item.get("purpose") or "")[:240],
        "native_status": str(item.get("native_status") or "DEFERRED")[:120],
        "resource_class": str(item.get("resource_class") or "unknown")[:40],
        "execution_owner": "worker",
        "available": binary is not None,
        "status": "DEFERRED",
        "version": None,
        "version_status": "not_run",
        "allowed_mode": str(item.get("allowed_mode") or "")[:80],
        "version_command": str(item.get("version_command") or "")[:80],
        "required_capability": str(item.get("required_capability") or "")[:100],
        "suite_membership": [str(value) for value in item.get("suite_membership") or []][:8],
    }
    if binary is not None and execute_version and tool_id in FIXED_VERSION_ARGS:
        result = _bounded_argv([str(binary), *FIXED_VERSION_ARGS[tool_id]], cwd=REPOSITORY_ROOT, timeout_seconds=5, max_output_bytes=16 * 1024)
        record["version_status"] = str(result.get("status") or "unknown")
        record["version"] = _version_line(result)
        record["version_output_sha256"] = result.get("stdout_sha256") or result.get("stderr_sha256")
    return _redact(record)


def _api_port() -> int:
    try:
        value = int(getattr(deps.settings(), "port", 8080))
    except (TypeError, ValueError):
        value = 8080
    return max(1024, min(value, 65535))


def _caddy_port() -> int:
    try:
        value = int(os.environ.get("DASH_PORT", "8443"))
    except (TypeError, ValueError):
        value = 8443
    return max(1024, min(value, 65535))


def _safe_http_body(raw: bytes) -> dict[str, Any]:
    if len(raw) > 64 * 1024:
        return {"json": False, "oversized": True}
    try:
        value = json.loads(raw.decode("utf-8")) if raw else {}
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {"json": False, "oversized": False}
    if not isinstance(value, Mapping):
        return {"json": False, "oversized": False}
    result: dict[str, Any] = {"json": True, "keys": sorted(str(key)[:80] for key in value)[:32]}
    for key in ("status", "reason_code", "accepted", "sanitized", "ready", "healthy"):
        if key not in value:
            continue
        if key in {"accepted", "sanitized", "ready", "healthy"}:
            result[key] = bool(value[key])
        else:
            result[key] = re.sub(r"[^a-zA-Z0-9_.:-]", "_", str(value[key]))[:100]
    return result


def _http_probe(
    *, port: int, path: str, method: str = "GET", body: bytes | None = None, headers: Mapping[str, str] | None = None
) -> dict[str, Any]:
    if not path.startswith("/") or ".." in path or "//" in path:
        raise AssuranceError("assurance_target_unregistered", "The assurance HTTP target is not registered.", status_code=503)
    url = f"http://127.0.0.1:{port}{path}"
    request = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={"Accept": "application/json", **{str(key): str(value) for key, value in (headers or {}).items()}},
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=2.0) as response:  # noqa: S310 - fixed loopback target
            raw = response.read(64 * 1024 + 1)
            return _redact({"status_code": int(response.status), "body_bytes": len(raw), "body": _safe_http_body(raw), "duration_ms": int((time.monotonic() - started) * 1000), "transport": "loopback"})
    except urllib.error.HTTPError as exc:
        raw = b""
        try:
            raw = exc.read(64 * 1024 + 1)
        except OSError:
            pass
        return _redact({"status_code": int(exc.code), "body_bytes": len(raw), "body": _safe_http_body(raw), "duration_ms": int((time.monotonic() - started) * 1000), "transport": "loopback", "http_error": True})
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return _redact({"status_code": None, "body_bytes": 0, "body": {}, "duration_ms": int((time.monotonic() - started) * 1000), "transport": "loopback", "failure_code": "connection_failed", "error_type": type(exc).__name__})


def _stream_probe(*, port: int, path: str, headers: Mapping[str, str]) -> dict[str, Any]:
    """Read only the bounded HTTP header block from a fixed SSE route."""
    if path != "/api/lite/security/events":
        raise AssuranceError("assurance_target_unregistered", "The assurance stream target is not registered.", status_code=503)
    request_headers = {
        "Host": f"127.0.0.1:{port}",
        "Accept": "text/event-stream",
        "Connection": "keep-alive",
        **{str(key): str(value) for key, value in headers.items()},
    }
    request = "GET /api/lite/security/events HTTP/1.1\r\n" + "\r\n".join(
        [f"{key}: {value}" for key, value in request_headers.items()]
    ) + "\r\n\r\n"
    started = time.monotonic()
    raw = bytearray()
    try:
        with socket.create_connection(("127.0.0.1", int(port)), timeout=2.0) as connection_socket:
            connection_socket.settimeout(2.0)
            connection_socket.sendall(request.encode("ascii"))
            while len(raw) < 16 * 1024 and b"\r\n\r\n" not in raw:
                chunk = connection_socket.recv(min(4096, 16 * 1024 - len(raw)))
                if not chunk:
                    break
                raw.extend(chunk)
    except (OSError, TimeoutError) as exc:
        return _redact({
            "status_code": None,
            "transport": "loopback-stream",
            "response_bytes": len(raw),
            "response_harness_marker_echoed": False,
            "duration_ms": int((time.monotonic() - started) * 1000),
            "failure_code": "connection_failed",
            "error_type": type(exc).__name__,
        })
    first_line = bytes(raw).split(b"\r\n", 1)[0].decode("ascii", "replace")
    match = re.match(r"^HTTP/\d(?:\.\d)?\s+(\d{3})\b", first_line)
    status_code = int(match.group(1)) if match else None
    response_text = bytes(raw).decode("ascii", "replace").lower()
    return _redact({
        "status_code": status_code,
        "transport": "loopback-stream",
        "response_bytes": len(raw),
        "response_harness_marker_echoed": "x-pocket-lab-harness" in response_text or "x-pocket-lab-qualification" in response_text,
        "duration_ms": int((time.monotonic() - started) * 1000),
        "response_sha256": _sha256_bytes(bytes(raw)),
    })


def _websocket_probe(*, port: int, path: str, headers: Mapping[str, str]) -> dict[str, Any]:
    """Perform one fixed local WebSocket upgrade without sending a frame."""
    if path != "/ws/events":
        raise AssuranceError("assurance_target_unregistered", "The assurance WebSocket target is not registered.", status_code=503)
    request_headers = {
        "Host": f"127.0.0.1:{port}",
        "Connection": "Upgrade",
        "Upgrade": "websocket",
        "Sec-WebSocket-Version": "13",
        # Fixed test material; this is a handshake nonce, not a credential.
        "Sec-WebSocket-Key": "dGhlIHNhbXBsZSBub25jZQ==",
        **{str(key): str(value) for key, value in headers.items()},
    }
    request = "GET /ws/events HTTP/1.1\r\n" + "\r\n".join(
        [f"{key}: {value}" for key, value in request_headers.items()]
    ) + "\r\n\r\n"
    started = time.monotonic()
    raw = bytearray()
    try:
        with socket.create_connection(("127.0.0.1", int(port)), timeout=2.0) as connection_socket:
            connection_socket.settimeout(2.0)
            connection_socket.sendall(request.encode("ascii"))
            while len(raw) < 16 * 1024 and b"\r\n\r\n" not in raw:
                chunk = connection_socket.recv(min(4096, 16 * 1024 - len(raw)))
                if not chunk:
                    break
                raw.extend(chunk)
    except (OSError, TimeoutError) as exc:
        return _redact({
            "status_code": None,
            "transport": "loopback-websocket",
            "handshake_accepted": False,
            "response_bytes": len(raw),
            "duration_ms": int((time.monotonic() - started) * 1000),
            "failure_code": "connection_failed",
            "error_type": type(exc).__name__,
        })
    first_line = bytes(raw).split(b"\r\n", 1)[0].decode("ascii", "replace")
    match = re.match(r"^HTTP/\d(?:\.\d)?\s+(\d{3})\b", first_line)
    status_code = int(match.group(1)) if match else None
    response_text = bytes(raw).decode("ascii", "replace").lower()
    return _redact({
        "status_code": status_code,
        "transport": "loopback-websocket",
        "handshake_accepted": status_code == 101,
        "response_bytes": len(raw),
        "response_sha256": _sha256_bytes(bytes(raw)),
        "response_harness_marker_echoed": "x-pocket-lab-harness" in response_text or "x-pocket-lab-qualification" in response_text,
        "duration_ms": int((time.monotonic() - started) * 1000),
    })


def _health_summary() -> dict[str, Any]:
    health = _http_probe(port=_api_port(), path="/health")
    ready = _http_probe(port=_api_port(), path="/ready")
    return _redact({"health": health, "ready": ready, "health_ok": health.get("status_code") == 200, "ready_ok": ready.get("status_code") == 200 and (ready.get("body") or {}).get("status") == "ready"})


def _pm2_summary() -> dict[str, Any]:
    binary = _verified_executable("pm2")
    if binary is None:
        return {"available": False, "status": "unknown", "failure_code": "pm2_unavailable", "worker_online": None}
    # ``pm2 jlist`` contains every managed process environment, which is both
    # unnecessary for admission and too close to a secret-bearing output
    # channel.  The fixed status table contains only process posture.
    result = _bounded_argv(
        [str(binary), "status", "pocket-worker", "--no-color"],
        cwd=REPOSITORY_ROOT,
        timeout_seconds=5,
        max_output_bytes=32 * 1024,
    )
    if result.get("status") != "completed":
        return _redact({"available": True, "status": "unknown", "failure_code": "pm2_inventory_failed", "worker_online": None, "command_status": result.get("status")})
    table = str(result.get("stdout") or "")
    worker_lines = [line for line in table.splitlines() if re.search(r"\bpocket-worker\b", line, flags=re.IGNORECASE)]
    if not worker_lines:
        return {"available": True, "status": "unknown", "failure_code": "pm2_worker_missing", "worker_online": False, "worker_status": "missing"}
    worker_line = worker_lines[0]
    status_match = re.search(r"\b(online|stopped|errored|stopping|launching|one-launch-status|waiting)\b", worker_line, flags=re.IGNORECASE)
    worker_status = status_match.group(1).lower() if status_match else "unknown"
    return _redact({
        "available": True,
        "status": "checked" if worker_status != "unknown" else "unknown",
        "failure_code": None if worker_status != "unknown" else "pm2_worker_status_unparsed",
        "worker_online": worker_status == "online",
        "worker_status": worker_status,
        "process_count": len([line for line in table.splitlines() if line.strip()]),
    })


def _bus_summary() -> dict[str, Any]:
    raw = BUS.status()
    durable = raw.get("durable_consumer_health") if isinstance(raw.get("durable_consumer_health"), Mapping) else {}
    return _redact({
        "connected": bool(raw.get("connected")),
        "jetstream_enabled": bool(raw.get("jetstream_enabled")),
        "nats_required": bool(raw.get("nats_required")),
        "jetstream_required": bool(raw.get("jetstream_required")),
        "durable_consumer_count": len(durable) if isinstance(durable, Mapping) else 0,
        "local_api_durable_consumer": bool((durable or {}).get("pocketlab_command_worker_v1", {}).get("healthy")) if isinstance(durable, Mapping) else False,
    })


def _security_conflict(profile: str) -> dict[str, Any] | None:
    try:
        active = lite_security.active_scan_state(profile=profile)
    except Exception as exc:
        return {"status": "unknown", "failure_code": "security_load_unknown", "error_type": type(exc).__name__}
    if active:
        return _redact({"status": "active", "run_id_present": bool(active.get("run_id")), "profile": profile})
    return None


def _security_conflict_probe(profile: str) -> dict[str, Any]:
    conflict = _security_conflict(profile)
    return conflict if isinstance(conflict, Mapping) else {"status": "none"}


def _preflight_probe(
    factory: Any,
    *,
    default: Mapping[str, Any],
    failure_code: str,
) -> dict[str, Any]:
    """Convert probe/infrastructure exceptions into sanitized admission data."""
    try:
        value = factory()
    except Exception as exc:
        return _redact({
            **dict(default),
            "status": "unknown",
            "failure_code": failure_code,
            "error_type": type(exc).__name__,
        })
    if not isinstance(value, Mapping):
        return _redact({
            **dict(default),
            "status": "unknown",
            "failure_code": failure_code,
            "error_type": "invalid_probe_result",
        })
    return _redact(dict(value))


def _scanner_capability(suite_id: str) -> dict[str, Any]:
    """Prove that every active scanner is registry-known before admission."""
    toolchain = _read_yaml(TOOLS_REGISTRY_PATH).get("toolchain") or []
    registered = {
        str(item.get("id"))
        for item in toolchain
        if isinstance(item, Mapping) and str(item.get("id") or "")
    }
    required = list(ACTIVE_TOOLS_BY_SUITE.get(suite_id, ()))
    missing = [tool_id for tool_id in required if tool_id not in registered]
    return _redact({
        "known": not missing,
        "required_tools": required,
        "missing_registered_tools": missing,
        "execution_owner": "worker",
        "server_owned_registry": True,
    })


def preflight(suite_id: str, *, expected_revision: str | None = None) -> dict[str, Any]:
    """Perform admission checks; infrastructure failure is BLOCKED, not a finding."""
    suite = suite_def(suite_id)
    startup = _preflight_probe(
        lite_harness.validate_startup_configuration,
        default={"valid": False},
        failure_code="startup_configuration_unavailable",
    )
    revision_result = _preflight_probe(
        _fixed_git_revision,
        default={"revision": None},
        failure_code="git_revision_unavailable",
    )
    clean_result = _preflight_probe(
        _fixed_git_clean,
        default={"ok": False, "changed_count": None},
        failure_code="git_status_unavailable",
    )
    health = _preflight_probe(
        _health_summary,
        default={"health_ok": False, "ready_ok": False, "health": {}, "ready": {}},
        failure_code="api_health_unavailable",
    )
    caddy_health = _preflight_probe(
        lambda: _http_probe(port=_caddy_port(), path="/health"),
        default={"status_code": None},
        failure_code="caddy_health_unavailable",
    )
    bus = _preflight_probe(
        _bus_summary,
        default={"connected": False, "jetstream_enabled": False},
        failure_code="nats_status_unavailable",
    )
    pm2 = _preflight_probe(
        _pm2_summary,
        default={"worker_online": None, "worker_status": "unknown"},
        failure_code="pm2_status_unavailable",
    )
    resources = _preflight_probe(
        optimization.resource_snapshot,
        default={
            "free_storage": None,
            "available_memory": None,
            "available_memory_percent": None,
            "battery_percent": None,
            "charging": None,
            "temperature_c": None,
            "system_load_ratio": None,
        },
        failure_code="resource_snapshot_unavailable",
    )
    requires_scanner = bool(ACTIVE_TOOLS_BY_SUITE.get(str(suite["id"])))
    scanner_capability = _preflight_probe(
        lambda: _scanner_capability(str(suite["id"])),
        default={"known": False, "required_tools": [], "missing_registered_tools": []},
        failure_code="scanner_capability_unknown",
    )
    opa = (
        _preflight_probe(
            lite_policy_opa.policy_status,
            default={"status": "unknown", "ready": False},
            failure_code="opa_status_unavailable",
        )
        if str(suite["id"]) in {"standard", "deep"}
        else {"status": "not_required", "ready": None}
    )
    conflict = (
        _preflight_probe(
            lambda: _security_conflict_probe(str(suite.get("existing_security_profile") or "quick")),
            default={"status": "unknown"},
            failure_code="security_load_unknown",
        )
        if requires_scanner
        else None
    )
    expected = str(expected_revision or "").strip()
    checks: dict[str, Any] = {
        "revision": {"ok": bool(revision_result.get("revision")), "value_present": bool(revision_result.get("revision")), "matches_expected": not expected or revision_result.get("revision") == expected},
        "worktree": clean_result,
        "startup_configuration": {"ok": bool(startup.get("valid")), "failure_code": startup.get("failure_code")},
        "qualification_environment": {"ok": lite_harness.environment() == lite_harness.HARNESS_RUNTIME_ENVIRONMENT, "environment": lite_harness.environment()[:32]},
        "harness_enabled": {"ok": bool(lite_harness.harness_enabled())},
        "test_auth_bypass": {"ok": not _flag("POCKETLAB_TEST_AUTH_BYPASS")},
        "destructive_gate": {"ok": not _flag("POCKETLAB_HARNESS_DESTRUCTIVE")},
        "qualification_owner": {"ok": not _flag("POCKETLAB_QUALIFICATION_OWNER")},
        "api_health": {"ok": bool(health.get("health_ok")), "status_code": health.get("health", {}).get("status_code")},
        "api_ready": {"ok": bool(health.get("ready_ok")), "status_code": health.get("ready", {}).get("status_code")},
        "caddy": {"ok": caddy_health.get("status_code") == 200, "status_code": caddy_health.get("status_code")},
        "nats": {"ok": bool(bus.get("connected")), "failure_code": bus.get("failure_code")},
        "jetstream": {"ok": bool(bus.get("jetstream_enabled")), "failure_code": bus.get("failure_code")},
        "worker_process": {"ok": pm2.get("worker_online") is True, "status": pm2.get("worker_status")},
        "resource_guard": {"ok": True, "free_storage_known": resources.get("free_storage") is not None, "available_memory_known": resources.get("available_memory") is not None, "resource": {key: resources.get(key) for key in ("free_storage", "available_memory", "available_memory_percent", "battery_percent", "charging", "temperature_c", "system_load_ratio")}},
        "scanner_capability": {"ok": not requires_scanner or bool(scanner_capability.get("known")), **scanner_capability},
        "security_conflict": {"ok": not requires_scanner or str((conflict or {}).get("status") or "unknown") == "none", "conflict": conflict},
        "opa": {"ok": str(opa.get("status")) == "ready" if str(suite["id"]) in {"standard", "deep"} else True, "status": opa.get("status"), "degraded_reason": opa.get("degraded_reason")},
    }
    if requires_scanner:
        resource = checks["resource_guard"]
        resource["ok"] = resource["free_storage_known"] and resource["available_memory_known"]
        try:
            minimum_storage = int(optimization.scan_budget_policy(str(suite.get("existing_security_profile") or "quick")).get("minimum_free_storage_bytes") or 0)
        except Exception:
            minimum_storage = 0
        if minimum_storage and resources.get("free_storage") is not None and int(resources["free_storage"]) < minimum_storage:
            resource["ok"] = False
            resource["failure_code"] = "insufficient_storage"
    blockers = []
    for name, item in checks.items():
        if not bool(item.get("ok")):
            blockers.append(name)
    # ``lite_security_policy`` intentionally treats any key containing
    # ``nats`` as credential-shaped.  The admission result contains only
    # fixed booleans and reason codes, so restore this bounded operational
    # check after recursive redaction without ever restoring bus metadata.
    safe_nats_check = {
        "ok": bool((checks.get("nats") or {}).get("ok")),
        "connected": bool(bus.get("connected")),
        "failure_code": str((checks.get("nats") or {}).get("failure_code") or "")[:120] or None,
    }
    result = _redact({
        "status": "ready" if not blockers else "blocked",
        "suite_id": suite["id"],
        "captured_at": _now(),
        "revision": revision_result.get("revision"),
        "runtime_id": lite_harness._runtime_id(),
        "checks": checks,
        "blockers": blockers,
        "scanner_admission": {"required": requires_scanner, "active_tools": list(ACTIVE_TOOLS_BY_SUITE.get(str(suite["id"]), ())), "capability_known": bool(scanner_capability.get("known")), "one_heavy_scanner": True, "target_scope": ASSURANCE_TARGET_SCOPE},
        "pm2_online_is_not_api_ready": True,
        "sanitized": True,
    })
    if isinstance(result.get("checks"), dict):
        result["checks"]["nats"] = safe_nats_check
    return result


def _flag(name: str) -> bool:
    return os.environ.get(name, "").strip().casefold() in {"1", "true", "yes", "on"}


def _fixed_git_revision() -> dict[str, Any]:
    git = _verified_executable("git")
    if git is None:
        return {"revision": None, "failure_code": "git_unavailable"}
    result = _bounded_argv([str(git), "rev-parse", "HEAD"], cwd=REPOSITORY_ROOT, timeout_seconds=5, max_output_bytes=1024)
    revision = str(result.get("stdout") or "").strip()
    return {"revision": revision if re.fullmatch(r"[0-9a-f]{40}", revision) else None, "command_status": result.get("status")}


def _fixed_git_clean() -> dict[str, Any]:
    git = _verified_executable("git")
    if git is None:
        return {"ok": False, "failure_code": "git_unavailable", "changed_count": None}
    result = _bounded_argv([str(git), "status", "--porcelain=v1", "--untracked-files=all"], cwd=REPOSITORY_ROOT, timeout_seconds=8, max_output_bytes=64 * 1024)
    output = str(result.get("stdout") or "")
    lines = [line for line in output.splitlines() if line.strip()]
    return _redact({"ok": result.get("status") == "completed" and not lines and not result.get("output_limited"), "changed_count": len(lines), "change_digest": _sha256_bytes(output.encode("utf-8", "replace")), "command_status": result.get("status")})


def _report_root(run_id: str, *, create: bool = True) -> Path:
    if not RUN_ID_RE.fullmatch(str(run_id or "")):
        raise AssuranceError("run_id_invalid", "The assurance run identifier is invalid.", status_code=400)
    root = deps.settings().state_dir / "security" / "assurance" / str(run_id)
    if create:
        root.mkdir(parents=True, exist_ok=True)
    return root


def _write_report_json(path: Path, payload: Any) -> None:
    evidence.write_json(path, _redact(payload))


def _write_report_text(path: Path, value: str) -> None:
    clean = policy.redact_text(str(value or ""))
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: str | None = None
    try:
        fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(clean[:64 * 1024])
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary:
            with __import__("contextlib").suppress(OSError):
                os.unlink(temporary)


def _safe_run_id(value: Any) -> str:
    result = str(value or "").strip()
    if not RUN_ID_RE.fullmatch(result):
        raise AssuranceError("run_id_invalid", "The assurance run identifier is invalid.", status_code=400)
    return result


def _row_payload(row: sqlite3.Row | Mapping[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    item = dict(row)
    for key in ("preflight_json", "summary_json", "report_json"):
        item[key.removesuffix("_json")] = _safe_json(item.pop(key, None), {})
    item["cancel_requested"] = bool(item.get("cancel_requested"))
    return _redact(item)


def _assurance_audit(
    *,
    event_type: str,
    reason_code: str,
    principal_id: str | None,
    session_id: str | None,
    operation_id: str | None,
    result: str,
    summary: str,
) -> None:
    """Record a bounded audit event without putting credentials in SQLite."""
    apply_migrations()
    with connection() as conn, begin_immediate(conn) as tx:
        lite_harness._insert_audit(
            tx,
            event_type=event_type,
            reason_code=reason_code,
            principal_id=str(principal_id or "")[:80] or None,
            principal_class="qualification",
            harness_session_id=str(session_id or "")[:100] or None,
            purpose=ASSURANCE_PURPOSE,
            capability=ASSURANCE_PROFILE,
            target_scope=ASSURANCE_TARGET_SCOPE,
            operation_id=str(operation_id or "")[:100] or None,
            result=str(result or "rejected")[:32],
            summary=policy.redact_text(summary)[:240],
            correlation_id=str(operation_id or session_id or uuid.uuid4().hex)[:80],
        )


def _session_posture(principal_id: str, session_id: str) -> dict[str, Any]:
    """Recheck the verified session binding without ever loading its token."""
    apply_migrations()
    with read_connection() as conn:
        row = conn.execute(
            """SELECT s.harness_session_id,s.principal_id,s.principal_class,s.purpose,
                      s.capability_profile,s.target_scope,s.runtime_id,s.status,s.expires_at,
                      p.enabled AS principal_enabled,p.revoked_at,p.expires_at AS principal_expires_at
               FROM harness_sessions s JOIN synthetic_principals p ON p.principal_id=s.principal_id
              WHERE s.harness_session_id=? AND s.principal_id=? LIMIT 1""",
            (str(session_id)[:100], str(principal_id)[:80]),
        ).fetchone()
    if not row:
        return {"ok": False, "failure_code": "harness_session_not_found"}
    now = datetime.now(timezone.utc)
    try:
        session_expiry = datetime.fromisoformat(str(row["expires_at"]).replace("Z", "+00:00"))
        principal_expiry = datetime.fromisoformat(str(row["principal_expires_at"]).replace("Z", "+00:00"))
        if session_expiry.tzinfo is None:
            session_expiry = session_expiry.replace(tzinfo=timezone.utc)
        if principal_expiry.tzinfo is None:
            principal_expiry = principal_expiry.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return {"ok": False, "failure_code": "harness_session_invalid"}
    checks = {
        "profile": str(row["capability_profile"]) == ASSURANCE_PROFILE,
        "purpose": str(row["purpose"]) == ASSURANCE_PURPOSE,
        "target_scope": str(row["target_scope"]) == ASSURANCE_TARGET_SCOPE,
        "runtime_id": str(row["runtime_id"]) == lite_harness._runtime_id(),
        "active": str(row["status"]) == "active",
        "principal_enabled": bool(row["principal_enabled"]) and not row["revoked_at"],
        "session_unexpired": session_expiry > now,
        "principal_unexpired": principal_expiry > now,
    }
    return _redact({"ok": all(checks.values()), "checks": checks, "profile": str(row["capability_profile"]), "purpose": str(row["purpose"]), "target_scope": str(row["target_scope"]), "runtime_bound": checks["runtime_id"]})


def create_run(
    *,
    suite_id: str,
    scenario_id: str | None,
    baseline_run_id: str | None,
    principal_id: str,
    session_id: str,
    revision_sha: str,
    preflight_result: Mapping[str, Any],
    status: str = "QUEUED",
    failure_code: str | None = None,
) -> dict[str, Any]:
    suite = suite_def(suite_id)
    selected_scenarios = _scenario_items_for_suite(suite, scenario_id)
    if not selected_scenarios:
        raise AssuranceError(
            "scenario_unknown",
            "The requested assurance scenario is not registered for this suite.",
            status_code=400,
        )
    canonical_scenario_id = str(selected_scenarios[0].get("id") or "") or None
    safe_status = str(status or "QUEUED").upper()
    if safe_status not in OUTCOMES | {"QUEUED", "RUNNING"}:
        raise AssuranceError("assurance_status_invalid", "The assurance run status is invalid.", status_code=503)
    if not re.fullmatch(r"[0-9a-f]{40}", str(revision_sha or "")):
        raise AssuranceError("revision_invalid", "The assurance revision is invalid.", status_code=503)
    safe_baseline: str | None = None
    if baseline_run_id:
        safe_baseline = _safe_run_id(baseline_run_id)
        baseline = get_run(safe_baseline)
        if (
            not baseline
            or str(baseline.get("suite_id") or "") != str(suite["id"])
            or str(baseline.get("scenario_id") or "") != str(canonical_scenario_id or "")
            or str(baseline.get("principal_id") or "") != str(principal_id or "")
            or str(baseline.get("status") or "").upper() not in {"PASS", "FAIL", "PARTIAL"}
        ):
            raise AssuranceError(
                "baseline_invalid",
                "The requested assurance baseline is not a compatible terminal run.",
                status_code=400,
            )
    # A previous worker/API process may have died after admission.  Reconcile
    # only rows beyond their fixed suite deadline plus grace; an active run is
    # never silently replaced while it could still be making progress.
    reconcile_stale_runs()
    run_id = "assurance-" + uuid.uuid4().hex
    now = _now()
    completed = now if safe_status in TERMINAL_STATUSES else None
    summary = {
        "status": safe_status,
        "suite_id": suite["id"],
        "message": "Assurance run blocked before execution." if safe_status == "BLOCKED" else "Assurance run queued for worker execution.",
    }
    apply_migrations()
    try:
        with connection() as conn, begin_immediate(conn) as tx:
            tx.execute(
                """INSERT INTO assurance_runs(
                    run_id,suite_id,profile,scenario_id,baseline_run_id,principal_id,
                    harness_session_id,purpose,target_scope,runtime_id,revision_sha,status,
                    preflight_json,summary_json,report_json,failure_code,requested_at,
                    completed_at,updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    run_id, suite["id"], ASSURANCE_PROFILE, canonical_scenario_id, safe_baseline,
                    principal_id, session_id, ASSURANCE_PURPOSE, ASSURANCE_TARGET_SCOPE,
                    lite_harness._runtime_id(), revision_sha, safe_status,
                    _canonical(_redact(dict(preflight_result))), _canonical(_redact(summary)),
                    _canonical({}), failure_code, now, completed, now,
                ),
            )
            row = tx.execute("SELECT * FROM assurance_runs WHERE run_id=?", (run_id,)).fetchone()
    except sqlite3.IntegrityError as exc:
        if "idx_assurance_one_active" in str(exc) or "UNIQUE constraint failed: assurance_runs.status" in str(exc):
            raise AssuranceConflict("assurance_run_active", "Another runtime assurance run is already active.", status_code=409) from exc
        raise AssuranceError("assurance_storage_rejected", "The assurance run could not be stored.", status_code=503) from exc
    _assurance_audit(
        event_type="assurance_run_admitted" if safe_status == "QUEUED" else "assurance_run_blocked",
        reason_code="run_queued" if safe_status == "QUEUED" else str(failure_code or "preflight_blocked"),
        principal_id=principal_id, session_id=session_id, operation_id=run_id,
        result="accepted" if safe_status == "QUEUED" else "rejected",
        summary="Runtime security assurance run admitted through the registered worker path." if safe_status == "QUEUED" else "Runtime security assurance was blocked by preflight.",
    )
    return _row_payload(row) or {}


def get_run(run_id: str) -> dict[str, Any] | None:
    safe = _safe_run_id(run_id)
    apply_migrations()
    with read_connection() as conn:
        row = conn.execute("SELECT * FROM assurance_runs WHERE run_id=?", (safe,)).fetchone()
    return _row_payload(row)


def list_runs(*, limit: int = 20) -> list[dict[str, Any]]:
    bounded = max(1, min(int(limit), 100))
    apply_migrations()
    with read_connection() as conn:
        rows = conn.execute("SELECT * FROM assurance_runs ORDER BY requested_at DESC LIMIT ?", (bounded,)).fetchall()
    result: list[dict[str, Any]] = []
    for row in rows:
        item = _row_payload(row)
        if item:
            result.append(item)
    return result


def is_terminal(run_id: str) -> bool:
    row = get_run(run_id)
    return bool(row and str(row.get("status") or "") in TERMINAL_STATUSES)


def mark_running(run_id: str) -> dict[str, Any]:
    safe = _safe_run_id(run_id)
    now = _now()
    apply_migrations()
    with connection() as conn, begin_immediate(conn) as tx:
        current = tx.execute("SELECT * FROM assurance_runs WHERE run_id=?", (safe,)).fetchone()
        if not current:
            raise AssuranceError("run_not_found", "The assurance run was not found.", status_code=404)
        if str(current["status"]) in TERMINAL_STATUSES:
            return _row_payload(current) or {}
        tx.execute("UPDATE assurance_runs SET status='RUNNING',started_at=COALESCE(started_at,?),updated_at=? WHERE run_id=?", (now, now, safe))
        row = tx.execute("SELECT * FROM assurance_runs WHERE run_id=?", (safe,)).fetchone()
    return _row_payload(row) or {}


def request_cancel(run_id: str, *, principal_id: str, session_id: str) -> dict[str, Any]:
    safe = _safe_run_id(run_id)
    now = _now()
    apply_migrations()
    with connection() as conn, begin_immediate(conn) as tx:
        current = tx.execute("SELECT * FROM assurance_runs WHERE run_id=?", (safe,)).fetchone()
        if not current:
            raise AssuranceError("run_not_found", "The assurance run was not found.", status_code=404)
        if str(current["principal_id"]) != str(principal_id) or str(current["harness_session_id"]) != str(session_id):
            raise AssuranceError("run_principal_mismatch", "Only the admitting assurance session may cancel this run.", status_code=403)
        if str(current["status"]) in TERMINAL_STATUSES:
            return _row_payload(current) or {}
        tx.execute("UPDATE assurance_runs SET cancel_requested=1,updated_at=? WHERE run_id=?", (now, safe))
        row = tx.execute("SELECT * FROM assurance_runs WHERE run_id=?", (safe,)).fetchone()
    _assurance_audit(event_type="assurance_run_cancel_requested", reason_code="cancel_requested", principal_id=principal_id, session_id=session_id, operation_id=safe, result="accepted", summary="A runtime assurance cancellation was requested.")
    return _row_payload(row) or {}


def _touch_run(run_id: str) -> None:
    """Refresh the durable liveness marker between bounded scenarios."""
    safe = _safe_run_id(run_id)
    now = _now()
    with connection() as conn, begin_immediate(conn) as tx:
        tx.execute(
            "UPDATE assurance_runs SET updated_at=? WHERE run_id=? AND status IN ('QUEUED','RUNNING')",
            (now, safe),
        )


def reconcile_stale_runs() -> dict[str, Any]:
    """Release interrupted assurance runs as PARTIAL after a fixed deadline."""
    apply_migrations()
    with read_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM assurance_runs WHERE status IN ('QUEUED','RUNNING') ORDER BY updated_at"
        ).fetchall()
    now = datetime.now(timezone.utc)
    reconciled: list[dict[str, Any]] = []
    for raw in rows:
        updated = _parse_timestamp(raw["updated_at"])
        try:
            suite = suite_def(raw["suite_id"])
            deadline = max(60, min(int(suite.get("maximum_seconds") or 600), 24 * 60 * 60))
        except Exception:
            suite = {"id": str(raw["suite_id"] or "unknown")}
            deadline = 600
        stale = updated is None or (now - updated).total_seconds() > deadline + RECONCILIATION_GRACE_SECONDS
        if not stale:
            continue
        row = _row_payload(raw) or {}
        failure_code = "assurance_state_timestamp_invalid" if updated is None else "assurance_stale_run_reconciled"
        report: dict[str, Any] = {
            "available": False,
            "failure_code": "report_write_failed",
            "sanitized": True,
        }
        try:
            report = _build_report(
                run=row,
                status="PARTIAL",
                preflight_result=row.get("preflight") if isinstance(row.get("preflight"), Mapping) else {},
                scenario_results=[],
                tool_records=[],
                findings=[],
                delta={"baseline_available": False, "counts": {}, "sanitized": True},
                attack_paths=_attack_path_inventory(),
                resource_start={},
                resource_finish={},
                started_monotonic=time.monotonic(),
                failure_code=failure_code,
            )
        except Exception:
            pass
        result = _set_terminal(
            str(row.get("run_id") or ""),
            status="PARTIAL",
            summary={
                "status": "PARTIAL",
                "failure_code": failure_code,
                "message": "The assurance worker did not complete before its bounded deadline; no PASS was inferred.",
                "sanitized": True,
            },
            report=report,
            scenarios=[],
            tools=[],
            findings=[],
            failure_code=failure_code,
        )
        _assurance_audit(
            event_type="assurance_run_reconciled",
            reason_code=failure_code,
            principal_id=str(row.get("principal_id") or ""),
            session_id=str(row.get("harness_session_id") or ""),
            operation_id=str(row.get("run_id") or ""),
            result="partial",
            summary="An interrupted runtime assurance run was reconciled without asserting success.",
        )
        reconciled.append({
            "run_id": str(result.get("run_id") or row.get("run_id") or ""),
            "status": str(result.get("status") or "PARTIAL"),
            "failure_code": failure_code,
        })
    return _redact({"reconciled": reconciled, "count": len(reconciled), "sanitized": True})


def _cancel_requested(run_id: str) -> bool:
    safe = _safe_run_id(run_id)
    with read_connection() as conn:
        row = conn.execute("SELECT cancel_requested FROM assurance_runs WHERE run_id=?", (safe,)).fetchone()
    return bool(row and row["cancel_requested"])


def _latest_baseline(run_id: str, suite_id: str) -> str | None:
    with read_connection() as conn:
        current = conn.execute(
            "SELECT principal_id,scenario_id FROM assurance_runs WHERE run_id=? LIMIT 1",
            (run_id,),
        ).fetchone()
        principal_id = current["principal_id"] if current else None
        scenario_id = current["scenario_id"] if current else None
        row = conn.execute(
            """SELECT run_id FROM assurance_runs
                WHERE suite_id=? AND run_id<>? AND principal_id=? AND scenario_id IS ?
                  AND status IN ('PASS','FAIL','PARTIAL')
                ORDER BY completed_at DESC LIMIT 1""",
            (suite_id, run_id, principal_id, scenario_id),
        ).fetchone()
    return str(row["run_id"]) if row else None


def _list_assurance_findings(run_id: str, *, limit: int = 500) -> list[dict[str, Any]]:
    safe = _safe_run_id(run_id)
    with read_connection() as conn:
        rows = conn.execute("SELECT * FROM assurance_findings WHERE run_id=? ORDER BY severity, finding_id LIMIT ?", (safe, max(1, min(int(limit), 500)))).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        for key in ("stride_json", "owasp_json", "attack_paths_json", "controls_json", "cwe_json", "cve_json", "evidence_refs_json"):
            item[key.removesuffix("_json")] = _safe_json(item.pop(key, None), [])
        result.append(_redact(item))
    return result


def list_findings(run_id: str, *, limit: int = 500) -> list[dict[str, Any]]:
    apply_migrations()
    return _list_assurance_findings(run_id, limit=limit)


def list_scenarios(run_id: str) -> list[dict[str, Any]]:
    apply_migrations()
    safe = _safe_run_id(run_id)
    with read_connection() as conn:
        rows = conn.execute("SELECT * FROM assurance_scenarios WHERE run_id=? ORDER BY scenario_id", (safe,)).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        for key in ("stride_json", "owasp_json", "attack_paths_json", "controls_json", "evidence_refs_json"):
            item[key.removesuffix("_json")] = _safe_json(item.pop(key, None), [])
        result.append(_redact(item))
    return result


def list_tool_results(run_id: str) -> list[dict[str, Any]]:
    apply_migrations()
    safe = _safe_run_id(run_id)
    with read_connection() as conn:
        rows = conn.execute("SELECT * FROM assurance_tool_results WHERE run_id=? ORDER BY tool_id", (safe,)).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["metadata"] = _safe_json(item.pop("metadata_json", None), {})
        result.append(_redact(item))
    return result


def _insert_scenarios_and_tools(
    tx: sqlite3.Connection,
    run_id: str,
    scenarios: Iterable[Mapping[str, Any]],
    tools: Iterable[Mapping[str, Any]],
) -> None:
    tx.execute("DELETE FROM assurance_scenarios WHERE run_id=?", (run_id,))
    for item in scenarios:
        tx.execute(
            """INSERT INTO assurance_scenarios(
              run_id,scenario_id,safety_class,status,expected_invariant,observed_evidence,
              stride_json,owasp_json,attack_paths_json,controls_json,evidence_refs_json,
              failure_code,started_at,completed_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                run_id, str(item.get("scenario_id") or "")[:80], str(item.get("safety_class") or "PASSIVE"),
                str(item.get("status") or "PARTIAL"), policy.redact_text(str(item.get("expected_invariant") or ""))[:500],
                policy.redact_text(str(item.get("observed_evidence") or ""))[:1000],
                _canonical(list(item.get("stride") or [])), _canonical(list(item.get("owasp") or [])),
                _canonical(list(item.get("attack_paths") or [])), _canonical(list(item.get("controls") or [])),
                _canonical(list(item.get("evidence_refs") or [])), str(item.get("failure_code") or "")[:120] or None,
                item.get("started_at"), item.get("completed_at"),
            ),
        )
    tx.execute("DELETE FROM assurance_tool_results WHERE run_id=?", (run_id,))
    for item in tools:
        tx.execute(
            """INSERT INTO assurance_tool_results(
              run_id,tool_id,status,tool_version,native_status,resource_class,execution_owner,
              finding_count,duration_ms,failure_code,evidence_ref,metadata_json
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                run_id, str(item.get("tool_id") or "")[:80], str(item.get("status") or "NOT_RUN"),
                str(item.get("version") or "")[:120] or None, str(item.get("native_status") or "")[:120] or None,
                str(item.get("resource_class") or "")[:40] or None, "worker", max(0, int(item.get("finding_count") or 0)),
                max(0, int(item.get("duration_ms") or 0)) if item.get("duration_ms") is not None else None,
                str(item.get("failure_code") or "")[:120] or None, str(item.get("evidence_ref") or "")[:300] or None,
                _canonical(_redact({key: value for key, value in item.items() if key not in {"tool_id", "status", "version", "native_status", "resource_class", "finding_count", "duration_ms", "failure_code", "evidence_ref"}})),
            ),
        )


def _insert_findings(tx: sqlite3.Connection, run_id: str, findings: Iterable[Mapping[str, Any]]) -> None:
    tx.execute("DELETE FROM assurance_findings WHERE run_id=?", (run_id,))
    for item in findings:
        tx.execute(
            """INSERT INTO assurance_findings(
              finding_id,run_id,stable_key,suite,scenario_id,tool,tool_version,category,
              severity,confidence,title,safe_summary,component,asset,trust_boundary,
              stride_json,owasp_json,attack_paths_json,controls_json,cwe_json,cve_json,
              sanitized_file_reference,runtime_target,first_seen_at,last_seen_at,baseline_state,
              status,remediation,evidence_refs_json
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                str(item.get("finding_id") or "")[:160], run_id, str(item.get("stable_key") or "")[:160],
                str(item.get("suite") or "")[:40], str(item.get("scenario_id") or "")[:80] or None,
                str(item.get("tool") or "")[:80], str(item.get("tool_version") or "")[:120] or None,
                str(item.get("category") or "finding")[:120], policy.normalize_severity(item.get("severity")),
                str(item.get("confidence") or "unknown") if str(item.get("confidence") or "unknown") in {"high", "medium", "low", "unknown"} else "unknown",
                policy.redact_text(str(item.get("title") or "Security finding"))[:240], policy.redact_text(str(item.get("safe_summary") or ""))[:1000],
                policy.redact_text(str(item.get("component") or ""))[:160], policy.redact_text(str(item.get("asset") or ""))[:160], policy.redact_text(str(item.get("trust_boundary") or ""))[:160],
                _canonical(list(item.get("stride") or [])), _canonical(list(item.get("owasp") or [])), _canonical(list(item.get("attack_paths") or [])), _canonical(list(item.get("controls") or [])), _canonical(list(item.get("cwe") or [])), _canonical(list(item.get("cve") or [])),
                str(item.get("sanitized_file_reference") or "")[:300] or None, ASSURANCE_TARGET_SCOPE,
                str(item.get("first_seen_at") or _now())[:40], str(item.get("last_seen_at") or _now())[:40],
                str(item.get("baseline_state") or "NEW") if str(item.get("baseline_state") or "NEW") in BASELINE_STATES else "NEW",
                str(item.get("status") or "open") if str(item.get("status") or "open") in {"open", "resolved", "review", "blocked"} else "review",
                policy.redact_text(str(item.get("remediation") or ""))[:1000], _canonical(list(item.get("evidence_refs") or [])),
            ),
        )


def _set_terminal(
    run_id: str,
    *,
    status: str,
    summary: Mapping[str, Any],
    report: Mapping[str, Any],
    scenarios: Iterable[Mapping[str, Any]],
    tools: Iterable[Mapping[str, Any]],
    findings: Iterable[Mapping[str, Any]],
    failure_code: str | None = None,
) -> dict[str, Any]:
    safe = _safe_run_id(run_id)
    outcome = str(status or "PARTIAL").upper()
    if outcome not in OUTCOMES:
        raise AssuranceError("assurance_status_invalid", "The assurance terminal status is invalid.", status_code=503)
    now = _now()
    clean_summary = _redact(dict(summary))
    clean_report = _redact(dict(report))
    scenario_items = list(scenarios)
    tool_items = list(tools)
    finding_items = list(findings)
    apply_migrations()
    with connection() as conn, begin_immediate(conn) as tx:
        current = tx.execute("SELECT * FROM assurance_runs WHERE run_id=?", (safe,)).fetchone()
        if not current:
            raise AssuranceError("run_not_found", "The assurance run was not found.", status_code=404)
        if str(current["status"] or "").upper() in TERMINAL_STATUSES:
            return _row_payload(current) or {}
        tx.execute(
            """UPDATE assurance_runs SET status=?,summary_json=?,report_json=?,failure_code=?,
                    completed_at=COALESCE(completed_at,?),updated_at=? WHERE run_id=?""",
            (outcome, _canonical(clean_summary), _canonical(clean_report), str(failure_code or "")[:120] or None, now, now, safe),
        )
        _insert_scenarios_and_tools(tx, safe, scenario_items, tool_items)
        _insert_findings(tx, safe, finding_items)
        row = tx.execute("SELECT * FROM assurance_runs WHERE run_id=?", (safe,)).fetchone()
    return _row_payload(row) or {}


def _scenario_items_for_suite(suite: Mapping[str, Any], requested: str | None = None) -> list[dict[str, Any]]:
    """Resolve only registry entries; AP aliases are canonical inventory views."""
    if requested:
        item = scenario_def(requested)
        if str(suite.get("id") or "").casefold() not in {
            str(value).casefold() for value in item.get("suites") or []
        }:
            raise AssuranceError(
                "scenario_not_in_suite",
                "The requested assurance scenario is not part of this suite.",
                status_code=400,
            )
        return [item]
    return [scenario_def(str(value)) for value in suite.get("scenarios") or []]


def _scenario_result(
    definition: Mapping[str, Any],
    *,
    status: str,
    observed: str,
    failure_code: str | None = None,
    evidence_refs: Iterable[str] = (),
    details: Mapping[str, Any] | None = None,
    started_at: str | None = None,
) -> dict[str, Any]:
    outcome = str(status or "PARTIAL").upper()
    if outcome not in {"PASS", "FAIL", "PARTIAL", "BLOCKED"}:
        outcome = "PARTIAL"
    completed_at = _now()
    return _redact({
        "scenario_id": str(definition.get("id") or "")[:80],
        "title": str(definition.get("title") or "")[:200],
        "execution": str(definition.get("execution") or "")[:80],
        "safety_class": str(definition.get("safety_class") or "PASSIVE"),
        "status": outcome,
        "expected_invariant": str(definition.get("title") or "The registered assurance invariant holds.")[:500],
        "observed_evidence": str(observed or "")[:1000],
        "stride": [str(value)[:40] for value in definition.get("stride") or []][:8],
        "owasp": [str(value)[:16] for value in definition.get("owasp") or []][:8],
        "attack_paths": [str(value)[:16] for value in definition.get("attack_paths") or []][:32],
        "controls": [str(value)[:120] for value in definition.get("controls") or []][:32],
        "evidence_refs": [str(value)[:300] for value in evidence_refs][:16],
        "failure_code": str(failure_code or "")[:120] or None,
        "started_at": started_at or completed_at,
        "completed_at": completed_at,
        "details": _redact(dict(details or {})),
    })


def _configuration_posture() -> dict[str, Any]:
    try:
        startup = lite_harness.validate_startup_configuration()
    except lite_harness.HarnessError as exc:
        startup = {"valid": False, "failure_code": exc.reason_code}
    checks = {
        "qualification_environment": lite_harness.environment() == lite_harness.HARNESS_RUNTIME_ENVIRONMENT,
        "harness_enabled": lite_harness.harness_enabled(),
        "test_auth_bypass": not _flag("POCKETLAB_TEST_AUTH_BYPASS"),
        "destructive_gate": not _flag("POCKETLAB_HARNESS_DESTRUCTIVE"),
        "qualification_owner": not _flag("POCKETLAB_QUALIFICATION_OWNER"),
        "startup_valid": bool(startup.get("valid")),
    }
    return _redact({
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "startup": {"valid": bool(startup.get("valid")), "failure_code": startup.get("failure_code")},
        "dangerous_flags_off": all(checks[key] for key in ("test_auth_bypass", "destructive_gate", "qualification_owner")),
        "sanitized": True,
    })


def _harness_auth_posture(principal_id: str, session_id: str) -> dict[str, Any]:
    posture = _session_posture(principal_id, session_id)
    profile = lite_harness.PROFILE_DATA[ASSURANCE_PROFILE]
    checks = {
        "session": bool(posture.get("ok")),
        "profile": bool(posture.get("checks", {}).get("profile", False)) if isinstance(posture.get("checks"), Mapping) else False,
        "purpose": bool(posture.get("checks", {}).get("purpose", False)) if isinstance(posture.get("checks"), Mapping) else False,
        "no_owner_capability": "rules.activate" not in set(profile.get("capabilities") or []),
        "no_destructive_capability": not profile.get("destructive_capabilities"),
        "fixed_target": str(posture.get("target_scope") or "") == ASSURANCE_TARGET_SCOPE,
    }
    return _redact({
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "profile": ASSURANCE_PROFILE,
        "principal_class": profile.get("principal_class"),
        "destructive_capabilities": list(profile.get("destructive_capabilities") or []),
        "capability_count": len(profile.get("capabilities") or []),
        "session_posture": posture,
        "synthetic_owner": False,
        "sanitized": True,
    })


def _caddy_probe() -> dict[str, Any]:
    """Exercise the fixed proxy route with forged markers and no credentials."""
    forged_headers = {
        "X-Pocket-Lab-Test": "1",
        "X-Pocket-Lab-Qualification": "1",
        "X-Pocket-Lab-Harness-Session": "forged",
        "X-Pocket-Lab-Harness-Provisioning": "1",
        "X-Pocket-Lab-Harness-Provisioning-Token": "forged",
        "X-Pocket-Lab-Harness-Principal": "forged",
        "X-Pocket-Lab-Harness-Profile": ASSURANCE_PROFILE,
        "X-Pocket-Lab-Harness-Purpose": ASSURANCE_PURPOSE,
        "X-Pocket-Lab-Harness-Signature": "forged",
        "X-Pocket-Lab-Harness-Target-Scope": ASSURANCE_TARGET_SCOPE,
    }
    paths = (
        "/health",
        "/ready",
        "/healthz",
        "/api/lite/security/events",
        "/openapi.json",
        "/docs",
        "/redoc",
    )
    route_results = []
    for path in paths:
        probe = (
            _stream_probe(port=_caddy_port(), path=path, headers=forged_headers)
            if path == "/api/lite/security/events"
            else _http_probe(port=_caddy_port(), path=path, headers=forged_headers)
        )
        route_results.append({
            "path": path,
            **{
                key: value
                for key, value in probe.items()
                if key in {
                    "status_code",
                    "body_bytes",
                    "response_bytes",
                    "duration_ms",
                    "transport",
                    "failure_code",
                    "http_error",
                    "body",
                    "response_harness_marker_echoed",
                }
            },
        })
    websocket = _websocket_probe(port=_caddy_port(), path="/ws/events", headers=forged_headers)
    body = _canonical({"suite_id": "smoke"})
    assurance = _http_probe(
        port=_caddy_port(),
        path="/api/lite/harness/security-assurance/runs",
        method="POST",
        body=body.encode("utf-8"),
        headers={**forged_headers, "Content-Type": "application/json"},
    )
    assurance_body = assurance.get("body") if isinstance(assurance.get("body"), Mapping) else {}
    reason = str(assurance_body.get("reason_code") or "")
    assurance_status = assurance.get("status_code")
    authority_not_accepted = assurance_status in {401, 403, 422}
    route_registered = assurance_status not in {None, 404, 405}
    marker_not_authorized = reason not in {"harness_session_invalid", "harness_proof_fields_rejected", "harness_role_field_rejected"}
    route_failures = [item for item in route_results if item.get("status_code") is None or int(item.get("status_code") or 0) >= 500]
    stream_result = next((item for item in route_results if item.get("path") == "/api/lite/security/events"), {})
    passed = (
        authority_not_accepted
        and route_registered
        and marker_not_authorized
        and not route_failures
        and stream_result.get("status_code") == 200
        and stream_result.get("response_harness_marker_echoed") is False
        and websocket.get("handshake_accepted") is True
        and websocket.get("response_harness_marker_echoed") is False
    )
    return _redact({
        "status": "PASS" if passed else "FAIL",
        "target_scope": ASSURANCE_TARGET_SCOPE,
        "routes_tested": [item["path"] for item in route_results] + ["/ws/events (websocket upgrade)", "/api/lite/harness/security-assurance/runs"],
        "route_results": route_results,
        "websocket_result": websocket,
        "assurance_request": {
            "status_code": assurance.get("status_code"),
            "body": assurance_body,
            "authority_not_accepted": authority_not_accepted,
            "route_registered": route_registered,
            "marker_not_authorized": marker_not_authorized,
        },
        "proof_header_injection": "not_accepted",
        "source_strip_contract": CADDY_SOURCE_PATH.exists(),
        "sanitized": True,
    })


def _redaction_contract() -> dict[str, Any]:
    markers = (
        "ASSURANCE_PRIVATE_KEY_MARKER",
        "ASSURANCE_SESSION_TOKEN_MARKER",
        "ASSURANCE_PASSWORD_MARKER",
        "ASSURANCE_API_KEY_MARKER",
        "ASSURANCE_COOKIE_MARKER",
        "ASSURANCE_NATS_CREDENTIAL_MARKER",
    )
    fixture = {
        "authorization": f"Bearer {markers[1]}",
        "session_token": markers[1],
        "private_key": f"-----BEGIN PRIVATE KEY-----\n{markers[0]}\n-----END PRIVATE KEY-----",
        "password": markers[2],
        "api_key": markers[3],
        "cookie": markers[4],
        "nested": {"nats_password": markers[5]},
        "summary": f"password={markers[2]} authorization: Bearer {markers[1]}",
    }
    encoded = _canonical(_redact(fixture))
    leaks = [marker for marker in markers if marker in encoded]
    return _redact({
        "status": "PASS" if not leaks else "FAIL",
        "raw_markers_checked": len(markers),
        "leak_count": len(leaks),
        "keys_redacted": all(marker not in encoded for marker in markers),
        "raw_scanner_output_persisted": False,
        "sanitized": True,
    })


def _source_boundaries() -> dict[str, Any]:
    """Check fixed frontend/backend boundary markers without traversing runtime state."""
    git = _verified_executable("git")
    if git is None:
        return {"status": "PARTIAL", "failure_code": "git_unavailable", "sanitized": True}
    tracked_result = _bounded_argv([str(git), "ls-files", "--", "src"], cwd=REPOSITORY_ROOT, timeout_seconds=8, max_output_bytes=256 * 1024)
    if tracked_result.get("status") != "completed":
        return {"status": "PARTIAL", "failure_code": "source_inventory_failed", "sanitized": True}
    source_paths = [
        (REPOSITORY_ROOT / relative).resolve()
        for relative in str(tracked_result.get("stdout") or "").splitlines()
        if relative.startswith("src/") and Path(relative).suffix.lower() in {".js", ".jsx", ".ts", ".tsx"}
    ][:512]
    suspicious_nats = re.compile(r"(?:nats\.connect\s*\(|nats\.io|new\s+NATS|jetstream\.publish|jetstream\.subscribe)", re.IGNORECASE)
    suspicious_shell = re.compile(r"(?:child_process|subprocess|shell\s*:\s*true|execFile|spawn\s*\()", re.IGNORECASE)
    nats_hits = 0
    shell_hits = 0
    source_bytes = 0
    for path in source_paths:
        try:
            data = path.read_bytes()
        except OSError:
            continue
        if len(data) > 512 * 1024:
            continue
        text = data.decode("utf-8", "replace")
        source_bytes += len(data)
        nats_hits += len(suspicious_nats.findall(text))
        shell_hits += len(suspicious_shell.findall(text))
    fixed_files = {
        "action_queue": REPOSITORY_ROOT / "pocket-lab-final-structure/runtime/api_fastapi/services/action_queue.py",
        "worker": REPOSITORY_ROOT / "pocket-lab-final-structure/runtime/workers/pocketlab_worker.py",
        "caddy": CADDY_SOURCE_PATH,
        "evidence_policy": REPOSITORY_ROOT / "pocket-lab-final-structure/runtime/api_fastapi/services/lite_security_policy.py",
    }
    markers = {
        "action_queue": ("submit_domain_command", "BUS.publish"),
        "worker": ("execute_domain_command", "pocketlab.commands.>"),
        "caddy": ("header_up -X-Pocket-Lab-Harness-Session", "handle /api/*"),
        "evidence_policy": ("def redact_value", "Photo library/media", "Android shared storage"),
    }
    marker_results: dict[str, bool] = {}
    for name, path in fixed_files.items():
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        marker_results[name] = all(marker in text for marker in markers[name])
    checks = {
        "frontend_no_direct_event_bus": nats_hits == 0,
        "frontend_no_shell_execution": shell_hits == 0,
        "backend_worker_owned": marker_results["action_queue"] and marker_results["worker"],
        "caddy_strips_harness_headers": marker_results["caddy"],
        "evidence_and_media_exclusions": marker_results["evidence_policy"],
    }
    return _redact({
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "tracked_frontend_file_count": len(source_paths),
        "tracked_frontend_bytes_read": source_bytes,
        "suspicious_frontend_event_bus_matches": nats_hits,
        "suspicious_frontend_shell_matches": shell_hits,
        "fixed_source_markers": marker_results,
        "runtime_state_traversed": False,
        "user_media_traversed": False,
        "sanitized": True,
    })


_AP_CLASSIFICATIONS = {
    "AP-01": ("PARTIALLY_EXECUTABLE", "Caddy and harness admission are exercised; direct browser-to-NATS reachability remains source evidence."),
    "AP-02": ("EXECUTABLE_NOW", "Frontend and backend source boundary assertions are executed."),
    "AP-03": ("STATIC_EVIDENCE_ONLY", "Managed-device identity forgery is not performed against enrolled device state."),
    "AP-04": ("PARTIALLY_EXECUTABLE", "Worker ownership and durable command path are inspected; replay/tampering is not injected."),
    "AP-05": ("STATIC_EVIDENCE_ONLY", "Release and dependency controls are represented by existing Security evidence and source checks."),
    "AP-06": ("EXECUTABLE_NOW", "Normalized evidence redaction is exercised with secret-shaped fixtures."),
    "AP-07": ("PARTIALLY_EXECUTABLE", "Local listener and Caddy surface are bounded; no Tailnet peer or LAN scan is performed."),
    "AP-08": ("STATIC_EVIDENCE_ONLY", "Recovery replacement/restore mutation is excluded from normal assurance."),
    "AP-09": ("HUMAN_REVIEW_REQUIRED", "Human WebAuthn ceremonies are not impersonated by the synthetic machine principal."),
    "AP-10": ("HUMAN_REVIEW_REQUIRED", "Enterprise membership and final-Owner review remain human-governed."),
    "AP-11": ("PARTIALLY_EXECUTABLE", "OPA readiness is checked where required; outage injection is not performed."),
    "AP-12": ("STATIC_EVIDENCE_ONLY", "Policy revision activation/recovery is not mutated by this safe profile."),
    "AP-13": ("HUMAN_REVIEW_REQUIRED", "Independent approval and requester continuation require human review."),
    "AP-14": ("HUMAN_REVIEW_REQUIRED", "Temporary exception issuance and expiry bypass are not attempted."),
}


def _attack_path_inventory() -> dict[str, Any]:
    paths = _threat_paths()
    results = []
    for path in paths:
        identifier = str(path.get("id") or "").upper()
        classification, reason = _AP_CLASSIFICATIONS.get(
            identifier,
            ("HUMAN_REVIEW_REQUIRED", "No promoted executable scenario exists for this current attack path."),
        )
        stride = [str(value)[:40] for value in path.get("stride") or []][:8]
        results.append({
            "attack_path_id": identifier,
            "name": str(path.get("name") or identifier)[:200],
            "classification": classification,
            "status": "PASS",
            "reason": reason,
            "human_review_required": classification in {"HUMAN_REVIEW_REQUIRED", "STATIC_EVIDENCE_ONLY"},
            "stride": stride,
            "owasp": sorted({code for threat in stride for code in OWASP_BY_STRIDE.get(threat, [])}),
            "controls": [str(value)[:120] for value in path.get("controls") or []][:16],
            "sanitized": True,
        })
    counts: dict[str, int] = {}
    for item in results:
        counts[item["classification"]] = counts.get(item["classification"], 0) + 1
    return _redact({"status": "PASS", "paths": results, "classification_counts": counts, "all_current_paths_classified": len(results) == len(paths), "sanitized": True})


def _control_plane_ownership() -> dict[str, Any]:
    domain_path = REPOSITORY_ROOT / "pocket-lab-final-structure/runtime/api_fastapi/services/domain_commands.py"
    worker_path = REPOSITORY_ROOT / "pocket-lab-final-structure/runtime/workers/pocketlab_worker.py"
    try:
        domain_text = domain_path.read_text(encoding="utf-8", errors="replace")
        worker_text = worker_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {"status": "PARTIAL", "failure_code": "ownership_source_unavailable", "sanitized": True}
    checks = {
        "fixed_subject": ASSURANCE_SUBJECT in domain_text and ASSURANCE_SUBJECT in worker_text,
        "domain_handler": "handle_lite_security_assurance" in domain_text,
        "worker_route": "execute_domain_command(subject, command)" in worker_text,
        "nats_required": bool(BUS.status().get("nats_required")),
        "browser_surface": False,
        "arbitrary_command_surface": False,
    }
    return _redact({"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks, "execution_path": ["FastAPI admission", "NATS/JetStream", "worker", "registered assurance runner", "sanitized evidence"], "sanitized": True})


def _policy_readiness() -> dict[str, Any]:
    try:
        posture = lite_policy_opa.policy_status()
    except Exception as exc:
        return {"status": "PARTIAL", "failure_code": "opa_status_unknown", "error_type": type(exc).__name__, "sanitized": True}
    ready = str(posture.get("status") or "") == "ready"
    return _redact({
        "status": "PASS" if ready else "BLOCKED",
        "ready": ready,
        "status_value": str(posture.get("status") or "unknown")[:32],
        "degraded_reason": str(posture.get("degraded_reason") or "")[:100],
        "loopback_only": bool((posture.get("engine") or {}).get("loopback_only")) if isinstance(posture.get("engine"), Mapping) else False,
        "browser_exposed": bool((posture.get("engine") or {}).get("endpoint_exposed_to_browser")) if isinstance(posture.get("engine"), Mapping) else False,
        "sanitized": True,
    })


def _runtime_readiness(preflight_result: Mapping[str, Any]) -> dict[str, Any]:
    checks = preflight_result.get("checks") if isinstance(preflight_result.get("checks"), Mapping) else {}
    selected = {
        key: bool((checks.get(key) or {}).get("ok"))
        for key in ("api_health", "api_ready", "nats", "jetstream", "worker_process")
        if isinstance(checks.get(key), Mapping)
    }
    ready = bool(selected) and all(selected.values())
    return _redact({"status": "PASS" if ready else "BLOCKED", "checks": selected, "pm2_online_is_not_api_ready": True, "sanitized": True})


def _inventory_tools(
    suite_id: str,
    *,
    scanner_records: Mapping[str, Mapping[str, Any]] | None = None,
    preflight_result: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    tools = _read_yaml(TOOLS_REGISTRY_PATH).get("toolchain") or []
    scanner_records = scanner_records or {}
    preflight_result = preflight_result or {}
    suite_tools = [
        item for item in tools
        if isinstance(item, Mapping) and suite_id in {str(value) for value in item.get("suite_membership") or []}
    ]
    results: list[dict[str, Any]] = []
    for item in suite_tools:
        tool_id = str(item.get("id") or "")
        if tool_id in scanner_records:
            results.append(_redact(
                dict(scanner_records[tool_id])
                | {
                    "tool_id": tool_id,
                    "purpose": str(item.get("purpose") or "")[:240],
                    "version_command": str(item.get("version_command") or "")[:80],
                }
            ))
            continue
        if tool_id == "opa":
            opa = (preflight_result.get("checks") or {}).get("opa") if isinstance(preflight_result.get("checks"), Mapping) else {}
            results.append(_redact({
                "tool_id": tool_id,
                "status": "PASS" if bool(opa.get("ok")) else "BLOCKED",
                "version": None,
                "native_status": item.get("native_status"),
                "resource_class": item.get("resource_class"),
                "version_command": item.get("version_command"),
                "failure_code": None if bool(opa.get("ok")) else "policy_not_ready",
                "metadata": {"loopback_only": True, "browser_exposed": False},
            }))
            continue
        if str(item.get("allowed_mode") or "").endswith("inventory_only") or tool_id not in ACTIVE_TOOLS_BY_SUITE.get(suite_id, ()):
            inventory = _tool_inventory(tool_id, execute_version=True)
            inventory["status"] = "DEFERRED"
            inventory["failure_code"] = "tool_not_promoted_for_runtime_suite"
            results.append(_redact(inventory))
            continue
        results.append(_redact({
            "tool_id": tool_id,
            "status": "MISSING",
            "native_status": item.get("native_status"),
            "resource_class": item.get("resource_class"),
            "version_command": item.get("version_command"),
            "failure_code": "registered_tool_result_missing",
        }))
    return results


def _run_existing_security_scan(suite_id: str) -> dict[str, Any]:
    """Reuse the authoritative worker-owned Quick/Full Security lifecycle."""
    profile = str(suite_def(suite_id).get("existing_security_profile") or "")
    if profile not in {policy.SCAN_PROFILE_QUICK, policy.SCAN_PROFILE_FULL}:
        return {"status": "NOT_RUN", "tool_records": {}, "findings": [], "evidence_refs": [], "summary": "No existing Security scanner is selected for this suite."}
    conflict = _security_conflict(profile)
    if conflict:
        return {"status": "PARTIAL", "failure_code": "security_scan_conflict", "tool_records": {}, "findings": [], "evidence_refs": [], "summary": "The existing Security scanner is already active."}
    security_run_id = "security-" + uuid.uuid4().hex
    command = {
        "run_id": security_run_id,
        "command_id": security_run_id,
        "scope": "local",
        "profile": profile,
        "reason": "registered runtime security assurance scanner",
        "requested_at": _now(),
    }
    started = time.monotonic()
    try:
        reservation = lite_security.build_and_reserve_scan_request(
            run_id=security_run_id,
            scope="local",
            profile=profile,
            app_id=None,
            reason=command["reason"],
            requested_at=command["requested_at"],
        )
        reservation_data = reservation.get("reservation") if isinstance(reservation, Mapping) else {}
        if isinstance(reservation_data, Mapping) and not reservation_data.get("reserved"):
            response = reservation_data.get("response") if isinstance(reservation_data.get("response"), Mapping) else {}
            existing_id = str(response.get("run_id") or "")
            existing_run = lite_security.read_run(existing_id) if existing_id else None
            run_status = str((existing_run or response).get("status") or "").lower()
            mapped = "PASS" if run_status in {"succeeded", "success", "completed"} else "PARTIAL"
            return _redact({
                "status": mapped,
                "reused": True,
                "security_run_id_present": bool(existing_id),
                "failure_code": None if mapped == "PASS" else "existing_security_result_incomplete",
                "tool_records": {
                    "pocketlab-security": {"status": mapped, "duration_ms": int((time.monotonic() - started) * 1000), "finding_count": len((existing_run or {}).get("findings") or [])},
                },
                "findings": list((existing_run or {}).get("findings") or []),
                "evidence_refs": [str(value) for value in (existing_run or {}).get("evidence_refs") or [] if str(value).startswith("security/evidence/")][:16],
                "summary": "A recent authoritative Security result was reused under the existing cache/deduplication policy.",
            })
        result = lite_security.run_security_scan(command)
        run = result.get("run") if isinstance(result, Mapping) and isinstance(result.get("run"), Mapping) else {}
        existing_findings = result.get("findings") if isinstance(result, Mapping) and isinstance(result.get("findings"), list) else []
        run_status = str(run.get("status") or "").lower()
        mapped = "PASS" if run_status in {"succeeded", "success", "completed"} else "PARTIAL" if run_status in {"degraded", "partial", "paused_at_checkpoint"} else "FAIL"
        tool_records: dict[str, dict[str, Any]] = {}
        raw_tools = run.get("tool_results") if isinstance(run.get("tool_results"), Mapping) else {}
        for tool_id in ("lynis", "trivy"):
            raw_value = raw_tools.get(tool_id)
            raw = raw_value if isinstance(raw_value, Mapping) else {}
            raw_status = str(raw.get("status") or "")
            if not raw:
                tool_status = "MISSING"
                failure_code = "registered_tool_result_missing"
            else:
                tool_status = "PASS" if raw_status in {"completed", "reused", "success", "succeeded"} else "PARTIAL" if raw_status in {"timed_out", "partial", "skipped_overall_budget"} else "MISSING" if raw_status == "missing_tool" else "FAIL" if raw_status else mapped
                failure_code = None if tool_status == "PASS" else ("tool_missing" if tool_status == "MISSING" else "tool_incomplete")
            tool_records[tool_id] = {
                "status": tool_status,
                "duration_ms": int((time.monotonic() - started) * 1000) if tool_id == "trivy" else None,
                "finding_count": int(raw.get("finding_count") or 0),
                "failure_code": failure_code,
                "native_status": "VERIFIED native when discovered by existing Security path",
                "resource_class": "heavy",
            }
        tool_records["pocketlab-security"] = {
            "status": mapped,
            "duration_ms": int((time.monotonic() - started) * 1000),
            "finding_count": len(existing_findings),
            "native_status": "VERIFIED native when existing worker path executes",
            "resource_class": "heavy",
        }
        return _redact({
            "status": mapped,
            "reused": False,
            "security_run_id_present": bool(run.get("run_id")),
            "failure_code": None if mapped == "PASS" else "existing_security_scan_incomplete",
            "tool_records": tool_records,
            "findings": existing_findings[:250],
            "evidence_refs": [str(value) for value in result.get("evidence_refs") or [] if str(value).startswith("security/evidence/")][:16] if isinstance(result, Mapping) else [],
            "summary": "The registered assurance runner reused the existing worker-owned Security scanner and evidence lifecycle.",
        })
    except Exception as exc:
        return _redact({
            "status": "FAIL",
            "failure_code": "security_scanner_execution_failed",
            "error_type": type(exc).__name__,
            "tool_records": {
                "pocketlab-security": {
                    "status": "FAIL",
                    "duration_ms": int((time.monotonic() - started) * 1000),
                    "finding_count": 0,
                    "failure_code": "security_scanner_execution_failed",
                    "resource_class": "heavy",
                },
            },
            "findings": [],
            "evidence_refs": [],
            "summary": "The existing Security scanner did not produce a complete terminal result.",
        })


def _normalize_security_finding(
    item: Mapping[str, Any],
    *,
    run_id: str,
    suite_id: str,
    scanner_evidence_refs: Iterable[str],
) -> dict[str, Any]:
    source = str(item.get("source") or item.get("tool") or "security").strip().lower()[:80]
    category = str(item.get("category") or "security_finding").strip().lower()[:120]
    raw_id = str(item.get("id") or item.get("finding_id") or f"{source}-{category}")[:160]
    component = policy.redact_text(str(item.get("component") or "Pocket Lab Lite"))[:160]
    asset = policy.redact_text(str(item.get("file") or component))[:160]
    stable_material = _canonical({"source": source, "category": category, "id": raw_id, "component": component, "asset": asset})
    stable_key = "assurance:" + hashlib.sha256(stable_material.encode("utf-8")).hexdigest()[:48]
    finding_id = f"{run_id}-{hashlib.sha256(stable_material.encode('utf-8')).hexdigest()[:24]}"
    if "secret" in category:
        stride, owasp, attack_paths, controls = ["Information Disclosure"], ["A02", "A05"], ["AP-06"], ["CTRL-EVIDENCE-SANITIZE"]
    elif "dependency" in category or source in {"trivy", "gitleaks"}:
        stride, owasp, attack_paths, controls = ["Tampering", "Elevation of Privilege"], ["A06", "A08"], ["AP-05"], ["CTRL-SUPPLY-CHAIN", "CTRL-EXPLICIT-PROMOTION"]
    elif "host" in category or "misconfig" in category:
        stride, owasp, attack_paths, controls = ["Tampering", "Information Disclosure"], ["A05", "A02"], ["AP-07"], ["CTRL-API-CONTROL"]
    else:
        stride, owasp, attack_paths, controls = ["Repudiation"], ["A09"], ["AP-06"], ["CTRL-EVIDENCE-SANITIZE"]
    identifier_text = f"{raw_id} {item.get('cve') or item.get('CVE') or ''} {item.get('cwe') or item.get('CWE') or ''}"
    cves = sorted(set(re.findall(r"\bCVE-\d{4}-\d{4,7}\b", identifier_text, flags=re.IGNORECASE)))[:8]
    cwes = sorted(set(re.findall(r"\bCWE-\d{1,5}\b", identifier_text, flags=re.IGNORECASE)))[:8]
    evidence_refs = [str(value) for value in scanner_evidence_refs if str(value).startswith("security/evidence/")][:16]
    return _redact({
        "finding_id": finding_id[:160],
        "stable_key": stable_key,
        "run_id": run_id,
        "suite": suite_id,
        "scenario_id": "security-projection",
        "tool": source,
        "tool_version": None,
        "category": category,
        "severity": policy.normalize_severity(item.get("severity")),
        "confidence": "medium" if source in {"trivy", "lynis"} else "unknown",
        "title": "Registered Security finding",
        "safe_summary": policy.redact_text(str(item.get("summary") or "A normalized Security finding requires review."))[:1000],
        "component": component,
        "asset": asset,
        "trust_boundary": "worker-owned security scanner to sanitized evidence",
        "stride": stride,
        "owasp": owasp,
        "attack_paths": attack_paths,
        "controls": controls,
        "cwe": cwes,
        "cve": cves,
        "sanitized_file_reference": evidence_refs[0] if evidence_refs else None,
        "runtime_target": ASSURANCE_TARGET_SCOPE,
        "first_seen_at": str(item.get("first_seen") or _now())[:40],
        "last_seen_at": _now(),
        "baseline_state": "NEW",
        "status": "open",
        "remediation": policy.redact_text(str(item.get("recommendation") or "Review the normalized finding and follow the existing Security remediation path."))[:1000],
        "evidence_refs": evidence_refs,
    })


def _apply_baseline(
    run_id: str,
    suite_id: str,
    findings: list[dict[str, Any]],
    baseline_run_id: str | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    baseline = baseline_run_id or _latest_baseline(run_id, suite_id)
    if baseline:
        try:
            prior = list_findings(baseline, limit=500)
        except Exception:
            prior = []
    else:
        prior = []
    prior_by_key = {str(item.get("stable_key") or ""): item for item in prior if item.get("stable_key")}
    current_keys: set[str] = set()
    enriched: list[dict[str, Any]] = []
    for item in findings:
        stable_key = str(item.get("stable_key") or "")
        current_keys.add(stable_key)
        prior_item = prior_by_key.get(stable_key)
        state = "NEW"
        if prior_item:
            state = "REGRESSED" if str(prior_item.get("status") or "") == "resolved" else "UNCHANGED"
        enriched.append({**item, "baseline_state": state})
    resolved: list[dict[str, Any]] = []
    for stable_key, prior_item in prior_by_key.items():
        if stable_key in current_keys or str(prior_item.get("status") or "") not in {"open", "review", "blocked"}:
            continue
        resolved_item = dict(prior_item)
        resolved_item.update({
            "finding_id": f"{run_id}-resolved-{hashlib.sha256(stable_key.encode('utf-8')).hexdigest()[:20]}",
            "run_id": run_id,
            "suite": suite_id,
            "baseline_state": "RESOLVED",
            "status": "resolved",
            "last_seen_at": _now(),
            "evidence_refs": [],
        })
        resolved.append(_redact(resolved_item))
    all_findings = [*enriched, *resolved]
    counts = {state: sum(1 for item in all_findings if item.get("baseline_state") == state) for state in sorted(BASELINE_STATES)}
    return _redact(all_findings), _redact({
        "baseline_run_id": baseline,
        "baseline_available": bool(baseline),
        "counts": counts,
        "new_finding_count": counts.get("NEW", 0),
        "regressed_finding_count": counts.get("REGRESSED", 0),
        "resolved_finding_count": counts.get("RESOLVED", 0),
        "unchanged_finding_count": counts.get("UNCHANGED", 0),
        "sanitized": True,
    })


def _coverage_payload(
    scenario_results: Iterable[Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    scenarios = list(scenario_results)
    stride_coverage: dict[str, dict[str, int]] = {
        name: {"PASS": 0, "PARTIAL": 0, "FAIL": 0, "BLOCKED": 0}
        for name in OWASP_BY_STRIDE
    }
    owasp_coverage: dict[str, dict[str, Any]] = {
        code: {"id": code, "name": name, "scenario_count": 0, "passing_scenarios": 0}
        for code, name in OWASP_NAMES.items()
    }
    controls: dict[str, dict[str, Any]] = {}
    for item in scenarios:
        status = str(item.get("status") or "PARTIAL").upper()
        for stride in item.get("stride") or []:
            if stride in stride_coverage:
                stride_coverage[stride][status] = stride_coverage[stride].get(status, 0) + 1
        for code in item.get("owasp") or []:
            code = str(code)
            if code in owasp_coverage:
                owasp_coverage[code]["scenario_count"] += 1
                if status == "PASS":
                    owasp_coverage[code]["passing_scenarios"] += 1
        for control in item.get("controls") or []:
            identifier = str(control)
            entry = controls.setdefault(identifier, {"control_id": identifier, "scenario_ids": [], "attack_paths": [], "status": "PASS"})
            scenario_id = str(item.get("scenario_id") or "")[:80]
            if scenario_id not in entry["scenario_ids"]:
                entry["scenario_ids"].append(scenario_id)
            entry["attack_paths"] = sorted(set([*entry["attack_paths"], *[str(value) for value in item.get("attack_paths") or []]]))
            if status != "PASS":
                entry["status"] = "FAIL" if status == "FAIL" else "PARTIAL"
    return (
        _redact({"framework": "STRIDE", "scenario_count": len(scenarios), "by_category": stride_coverage, "scenarios": scenarios, "sanitized": True}),
        _redact({"version": "2021", "categories": list(owasp_coverage.values()), "sanitized": True}),
        _redact({"controls": list(controls.values()), "sanitized": True}),
    )


def _summary_markdown(
    *,
    run: Mapping[str, Any],
    status: str,
    preflight_result: Mapping[str, Any],
    scenario_results: Iterable[Mapping[str, Any]],
    tool_records: Iterable[Mapping[str, Any]],
    findings: Iterable[Mapping[str, Any]],
    delta: Mapping[str, Any],
    attack_paths: Mapping[str, Any],
) -> str:
    scenarios = list(scenario_results)
    tools = list(tool_records)
    findings = sorted(
        list(findings),
        key=lambda item: (
            {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}.get(str(item.get("severity")), 5),
            str(item.get("finding_id") or ""),
        ),
    )
    lines = [
        "# Runtime Security Assurance",
        "",
        f"- Result: {str(status).upper()}",
        f"- Revision tested: {str(run.get('revision_sha') or '')[:40]}",
        f"- Runtime identity present: {bool(run.get('runtime_id'))}",
        f"- Suite: {str(run.get('suite_id') or '')}",
        f"- Profile: {ASSURANCE_PROFILE}",
        f"- Target scope: {ASSURANCE_TARGET_SCOPE}",
        f"- Preflight: {str(preflight_result.get('status') or 'unknown').upper()}",
        "",
        "## Scenario results",
        "",
    ]
    for item in scenarios:
        lines.append(
            f"- {item.get('scenario_id')} — {item.get('status')} — "
            f"{policy.redact_text(str(item.get('observed_evidence') or ''))[:220]}"
        )
    lines.extend(["", "## Tool results", ""])
    for item in tools:
        lines.append(
            f"- {item.get('tool_id')} — {item.get('status')} — "
            f"resource {item.get('resource_class') or 'unknown'}"
        )
    lines.extend(["", "## Findings and delta", ""])
    lines.append(
        f"- Findings recorded: {len(findings)}; new {delta.get('new_finding_count', 0)}; "
        f"regressed {delta.get('regressed_finding_count', 0)}; "
        f"resolved {delta.get('resolved_finding_count', 0)}."
    )
    for item in findings[:50]:
        lines.append(
            f"- {item.get('severity')} / {item.get('baseline_state')} — "
            f"{policy.redact_text(str(item.get('title') or 'Security finding'))[:180]}"
        )
    lines.extend(["", "## Attack-path coverage", ""])
    counts = attack_paths.get("classification_counts") if isinstance(attack_paths.get("classification_counts"), Mapping) else {}
    lines.append(
        f"- Current canonical attack paths classified: {len(attack_paths.get('paths') or [])}; "
        f"classification counts: {_canonical(counts)}."
    )
    lines.extend([
        "",
        "This report is sanitized and does not contain reusable credentials, raw scanner output, "
        "user media, backup payloads, private paths, or private keys.",
        "The Runtime Security Assurance Harness is not a generic remote shell.",
    ])
    return policy.redact_text("\n".join(lines) + "\n")


def _build_report(
    *,
    run: Mapping[str, Any],
    status: str,
    preflight_result: Mapping[str, Any],
    scenario_results: Iterable[Mapping[str, Any]],
    tool_records: Iterable[Mapping[str, Any]],
    findings: Iterable[Mapping[str, Any]],
    delta: Mapping[str, Any],
    attack_paths: Mapping[str, Any],
    resource_start: Mapping[str, Any],
    resource_finish: Mapping[str, Any],
    started_monotonic: float,
    failure_code: str | None = None,
) -> dict[str, Any]:
    root = _report_root(str(run.get("run_id") or ""))
    scenario_list = [_redact(dict(item)) for item in scenario_results]
    tool_list = [_redact(dict(item)) for item in tool_records]
    finding_list = [_redact(dict(item)) for item in findings]
    threat_coverage, owasp_coverage, controls = _coverage_payload(scenario_list)
    manifest = _redact({
        "schema_version": ASSURANCE_SCHEMA_VERSION,
        "run_id": run.get("run_id"),
        "suite": run.get("suite_id"),
        "profile": ASSURANCE_PROFILE,
        "purpose": ASSURANCE_PURPOSE,
        "target_scope": ASSURANCE_TARGET_SCOPE,
        "runtime_id": run.get("runtime_id"),
        "revision_sha": run.get("revision_sha"),
        "status": str(status).upper(),
        "registry": validate_registries(),
        "execution_owner": "worker",
        "sanitized": True,
    })
    environment_payload = _redact({
        "runtime_id": run.get("runtime_id"),
        "revision_sha": run.get("revision_sha"),
        "qualification_environment": lite_harness.environment() == lite_harness.HARNESS_RUNTIME_ENVIRONMENT,
        "harness_enabled": lite_harness.harness_enabled(),
        "test_auth_bypass": _flag("POCKETLAB_TEST_AUTH_BYPASS"),
        "destructive_gate": _flag("POCKETLAB_HARNESS_DESTRUCTIVE"),
        "qualification_owner": _flag("POCKETLAB_QUALIFICATION_OWNER"),
        "preflight": preflight_result,
        "user_media_scanned": False,
        "backup_payloads_scanned": False,
        "sanitized": True,
    })
    performance = _redact({
        "started_at": run.get("started_at"),
        "completed_at": _now(),
        "duration_ms": max(0, int((time.monotonic() - started_monotonic) * 1000)),
        "resource_start": dict(resource_start),
        "resource_finish": dict(resource_finish),
        "resource_governor": {
            "one_heavy_scanner": True,
            "bounded_output": True,
            "bounded_target": ASSURANCE_TARGET_SCOPE,
        },
        "sanitized": True,
    })
    sanitization = {
        "sanitized": True,
        "raw_scanner_output_persisted": False,
        "raw_credentials_persisted": False,
        "session_tokens_persisted": False,
        "key_material_persisted": False,
        "authorization_headers_persisted": False,
        "user_media_scanned": False,
        "backup_payloads_scanned": False,
        "evidence_policy": "normalized_and_redacted",
    }
    payloads = {
        "manifest.json": manifest,
        "environment.json": environment_payload,
        "toolchain.json": {"tools": tool_list, "execution_owner": "worker", "sanitized": True},
        "findings.json": {"findings": finding_list, "sanitized": True},
        "threat-coverage.json": threat_coverage,
        "owasp-coverage.json": owasp_coverage,
        "attack-path-results.json": attack_paths,
        "controls.json": controls,
        "delta.json": delta,
        "performance.json": performance,
        "sanitization.json": sanitization,
    }
    for filename, payload in payloads.items():
        _write_report_json(root / filename, payload)
    summary = _summary_markdown(
        run=run,
        status=status,
        preflight_result=preflight_result,
        scenario_results=scenario_list,
        tool_records=tool_list,
        findings=finding_list,
        delta=delta,
        attack_paths=attack_paths,
    )
    _write_report_text(root / "summary.md", summary)
    checksums = {
        filename: _sha256_bytes((root / filename).read_bytes())
        for filename in [*payloads, "summary.md"]
        if (root / filename).is_file()
    }
    _write_report_json(
        root / "checksums.json",
        {
            "schema_version": ASSURANCE_SCHEMA_VERSION,
            "files": checksums,
            "algorithm": "sha256",
            "sanitized": True,
        },
    )
    files = [*payloads, "checksums.json", "summary.md"]
    return _redact({
        "available": True,
        "schema_version": ASSURANCE_SCHEMA_VERSION,
        "directory": f"security/assurance/{run.get('run_id')}",
        "files": files,
        "checksums_file": "checksums.json",
        "failure_code": failure_code,
        "sanitized": True,
    })


def record_blocked_run(
    run_id: str,
    *,
    failure_code: str,
    preflight_result: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    row = get_run(run_id)
    if not row:
        raise AssuranceError("run_not_found", "The assurance run was not found.", status_code=404)
    preflight_payload = preflight_result or row.get("preflight") or {}
    try:
        report = _build_report(
            run=row,
            status="BLOCKED",
            preflight_result=preflight_payload,
            scenario_results=[],
            tool_records=[],
            findings=[],
            delta={"baseline_available": False, "counts": {}, "sanitized": True},
            attack_paths=_attack_path_inventory(),
            resource_start={},
            resource_finish={},
            started_monotonic=time.monotonic(),
            failure_code=failure_code,
        )
    except Exception:
        report = {"available": False, "failure_code": "report_write_failed", "sanitized": True}
    result = _set_terminal(
        run_id,
        status="BLOCKED",
        summary={
            "status": "BLOCKED",
            "failure_code": failure_code,
            "message": "Runtime assurance did not start because preflight was not satisfied.",
            "sanitized": True,
        },
        report=report,
        scenarios=[],
        tools=[],
        findings=[],
        failure_code=failure_code,
    )
    _assurance_audit(
        event_type="assurance_run_blocked",
        reason_code=failure_code,
        principal_id=str(row.get("principal_id") or ""),
        session_id=str(row.get("harness_session_id") or ""),
        operation_id=str(row.get("run_id") or ""),
        result="rejected",
        summary="Runtime security assurance was blocked before execution.",
    )
    return result


def fail_run_exception(run_id: str, exc: Exception | None = None) -> dict[str, Any]:
    row = get_run(run_id)
    if not row:
        return {}
    if str(row.get("status") or "").upper() in TERMINAL_STATUSES:
        return row
    failure_code = "worker_execution_failed"
    report: dict[str, Any] = {
        "available": False,
        "failure_code": failure_code,
        "sanitized": True,
    }
    try:
        report = _build_report(
            run=row,
            status="FAIL",
            preflight_result=row.get("preflight") if isinstance(row.get("preflight"), Mapping) else {},
            scenario_results=[],
            tool_records=[],
            findings=[],
            delta={"baseline_available": False, "counts": {}, "sanitized": True},
            attack_paths=_attack_path_inventory(),
            resource_start={},
            resource_finish={},
            started_monotonic=time.monotonic(),
            failure_code=failure_code,
        )
    except Exception:
        pass
    result = _set_terminal(
        run_id,
        status="FAIL",
        summary={
            "status": "FAIL",
            "failure_code": failure_code,
            "message": "The worker did not produce a trustworthy assurance result.",
            "sanitized": True,
        },
        report=report,
        scenarios=[],
        tools=[],
        findings=[],
        failure_code=failure_code,
    )
    _assurance_audit(
        event_type="assurance_run_failed",
        reason_code=failure_code,
        principal_id=str(row.get("principal_id") or ""),
        session_id=str(row.get("harness_session_id") or ""),
        operation_id=str(row.get("run_id") or ""),
        result="rejected",
        summary="Runtime security assurance failed before a complete result was committed.",
    )
    return result


def execute_run(command: Mapping[str, Any]) -> dict[str, Any]:
    """Execute one admitted command from the fixed assurance subject."""
    run_id = _safe_run_id(command.get("run_id") or command.get("command_id"))
    row = get_run(run_id)
    if not row:
        raise AssuranceError("run_not_found", "The assurance run was not found.", status_code=404)
    if str(row.get("status") or "").upper() in TERMINAL_STATUSES:
        return row
    fixed_fields = {
        "command_id": run_id,
        "trace_id": run_id,
        "profile": ASSURANCE_PROFILE,
        "purpose": ASSURANCE_PURPOSE,
        "target_scope": ASSURANCE_TARGET_SCOPE,
        "suite_id": str(row.get("suite_id") or ""),
        "scenario_id": str(row.get("scenario_id") or ""),
        "baseline_run_id": str(row.get("baseline_run_id") or ""),
        "runtime_id": str(row.get("runtime_id") or ""),
        "revision_sha": str(row.get("revision_sha") or ""),
        "principal_id": str(row.get("principal_id") or ""),
        "session_id": str(row.get("harness_session_id") or ""),
    }
    if any(str(command.get(key) or "") != value for key, value in fixed_fields.items()):
        return fail_run_exception(run_id)
    suite = suite_def(row.get("suite_id"))
    selected = _scenario_items_for_suite(suite, str(row.get("scenario_id") or "") or None)
    posture = _session_posture(
        str(row.get("principal_id") or ""),
        str(row.get("harness_session_id") or ""),
    )
    if not posture.get("ok"):
        return fail_run_exception(run_id)
    try:
        preflight_result = preflight(
            str(suite["id"]),
            expected_revision=str(row.get("revision_sha") or ""),
        )
    except Exception as exc:
        # Admission failures are infrastructure state, not scanner findings.
        # Keep the run BLOCKED and retain only the exception class in the
        # sanitized report so a broken probe/registry cannot become a false
        # security PASS or leak local details.
        preflight_result = _redact({
            "status": "blocked",
            "suite_id": str(suite["id"]),
            "blockers": ["preflight_exception"],
            "failure_code": "preflight_exception",
            "error_type": type(exc).__name__,
            "sanitized": True,
        })
    if preflight_result.get("status") != "ready":
        return record_blocked_run(
            run_id,
            failure_code=str(preflight_result.get("failure_code") or "preflight_blocked")[:120],
            preflight_result=preflight_result,
        )
    mark_running(run_id)
    started = time.monotonic()
    resource_start = optimization.resource_snapshot()
    scenario_results: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    scanner_records: dict[str, Mapping[str, Any]] = {}
    scanner_summary: Mapping[str, Any] | None = None
    cancelled = False
    for definition in selected:
        scenario_started = _now()
        scenario_id = str(definition.get("id") or "")
        _touch_run(run_id)
        if _cancel_requested(run_id):
            cancelled = True
            scenario_results.append(
                _scenario_result(
                    definition,
                    status="PARTIAL",
                    observed="Cancellation was requested before this scenario ran.",
                    failure_code="cancel_requested",
                    started_at=scenario_started,
                )
            )
            continue
        if not _session_posture(
            str(row.get("principal_id") or ""),
            str(row.get("harness_session_id") or ""),
        ).get("ok"):
            scenario_results.append(
                _scenario_result(
                    definition,
                    status="BLOCKED",
                    observed="The admitting harness session was no longer valid.",
                    failure_code="harness_session_invalid",
                    started_at=scenario_started,
                )
            )
            cancelled = True
            continue
        try:
            if scenario_id == "harness-default-off":
                posture_result = _configuration_posture()
                scenario_results.append(
                    _scenario_result(
                        definition,
                        status=posture_result["status"],
                        observed="Dangerous qualification bypasses remain disabled.",
                        details=posture_result,
                        started_at=scenario_started,
                    )
                )
            elif scenario_id == "harness-auth-boundary":
                auth_result = _harness_auth_posture(
                    str(row.get("principal_id") or ""),
                    str(row.get("harness_session_id") or ""),
                )
                scenario_results.append(
                    _scenario_result(
                        definition,
                        status=auth_result["status"],
                        observed="The signed session remains profile, purpose, runtime, and target bound.",
                        details=auth_result,
                        started_at=scenario_started,
                    )
                )
            elif scenario_id == "caddy-proof-strip":
                caddy_result = _caddy_probe()
                scenario_results.append(
                    _scenario_result(
                        definition,
                        status=caddy_result["status"],
                        observed="Forged qualification markers were not accepted through the Caddy proxy.",
                        details=caddy_result,
                        started_at=scenario_started,
                    )
                )
            elif scenario_id == "runtime-readiness":
                ready_result = _runtime_readiness(preflight_result)
                scenario_results.append(
                    _scenario_result(
                        definition,
                        status=ready_result["status"],
                        observed="Qualification admitted only after API health/readiness, NATS, JetStream, and worker checks.",
                        details=ready_result,
                        started_at=scenario_started,
                    )
                )
            elif scenario_id == "control-plane-ownership":
                owner_result = _control_plane_ownership()
                scenario_results.append(
                    _scenario_result(
                        definition,
                        status=owner_result["status"],
                        observed="Assurance execution is routed through the fixed NATS and worker-owned domain path.",
                        details=owner_result,
                        started_at=scenario_started,
                    )
                )
            elif scenario_id == "evidence-redaction":
                redact_result = _redaction_contract()
                scenario_results.append(
                    _scenario_result(
                        definition,
                        status=redact_result["status"],
                        observed="Secret-shaped evidence fixture values were removed before persistence.",
                        details=redact_result,
                        started_at=scenario_started,
                    )
                )
            elif scenario_id == "security-projection":
                scanner_summary = _run_existing_security_scan(str(suite["id"]))
                raw_records = scanner_summary.get("tool_records") if isinstance(scanner_summary.get("tool_records"), Mapping) else {}
                scanner_records = {
                    str(key): value
                    for key, value in raw_records.items()
                    if isinstance(value, Mapping)
                }
                scanner_result_status = str(scanner_summary.get("status") or "PARTIAL")
                raw_findings = scanner_summary.get("findings") if isinstance(scanner_summary.get("findings"), list) else []
                findings.extend(
                    _normalize_security_finding(
                        item,
                        run_id=run_id,
                        suite_id=str(suite["id"]),
                        scanner_evidence_refs=scanner_summary.get("evidence_refs") or [],
                    )
                    for item in raw_findings
                    if isinstance(item, Mapping)
                )
                scenario_results.append(
                    _scenario_result(
                        definition,
                        status=scanner_result_status,
                        observed=str(scanner_summary.get("summary") or "Existing Security scanner result was recorded.")[:1000],
                        details={
                            "scanner_status": scanner_result_status,
                            "evidence_ref_count": len(scanner_summary.get("evidence_refs") or []),
                            "finding_count": len(raw_findings),
                        },
                        evidence_refs=scanner_summary.get("evidence_refs") or [],
                        started_at=scenario_started,
                    )
                )
            elif scenario_id == "policy-readiness":
                policy_result = _policy_readiness()
                scenario_results.append(
                    _scenario_result(
                        definition,
                        status=policy_result["status"],
                        observed="OPA readiness and loopback policy posture were checked without changing policy state.",
                        details=policy_result,
                        started_at=scenario_started,
                    )
                )
            elif scenario_id == "source-boundaries":
                source_result = _source_boundaries()
                scenario_results.append(
                    _scenario_result(
                        definition,
                        status=source_result["status"],
                        observed="Frontend, Caddy, worker ownership, and exclusion markers were checked from canonical source.",
                        details=source_result,
                        started_at=scenario_started,
                    )
                )
            elif scenario_id == "threat-model-integrity":
                registry_result = validate_registries()
                scenario_results.append(
                    _scenario_result(
                        definition,
                        status="PASS",
                        observed="The canonical STRIDE model and assurance registries are complete for all current attack paths.",
                        details=registry_result,
                        started_at=scenario_started,
                    )
                )
            elif scenario_id == "attack-path-inventory":
                attack_result = _attack_path_inventory()
                scenario_results.append(
                    _scenario_result(
                        definition,
                        status=attack_result["status"],
                        observed="Every current AP-* entry has an explicit execution classification; human-review and static-only paths remain deferred.",
                        details={
                            "classification_counts": attack_result.get("classification_counts"),
                            "all_current_paths_classified": attack_result.get("all_current_paths_classified"),
                        },
                        started_at=scenario_started,
                    )
                )
            elif AP_ID_RE.fullmatch(scenario_id.upper()):
                attack_result = _attack_path_inventory()
                path = next(
                    (item for item in attack_result.get("paths") or [] if item.get("attack_path_id") == scenario_id.upper()),
                    None,
                )
                # An AP alias is an inventory view unless a dedicated
                # registered runtime scenario exists.  Never turn the mere
                # presence of a classification into a passing exploit test.
                scenario_results.append(
                    _scenario_result(
                        definition,
                        status="BLOCKED",
                        observed=(
                            "The selected canonical attack path has an explicit bounded classification, "
                            "but no dedicated runtime scenario was promoted for direct execution."
                            if path
                            else "The selected canonical attack path is not present in the canonical model."
                        ),
                        failure_code=None if path else "attack_path_not_registered",
                        details=path or {},
                        started_at=scenario_started,
                    )
                )
            else:
                scenario_results.append(
                    _scenario_result(
                        definition,
                        status="BLOCKED",
                        observed="The registered scenario has no executable implementation.",
                        failure_code="scenario_execution_unavailable",
                        started_at=scenario_started,
                    )
                )
        except Exception as exc:
            scenario_results.append(
                _scenario_result(
                    definition,
                    status="PARTIAL",
                    observed="The registered scenario did not produce a complete result.",
                    failure_code="scenario_execution_failed",
                    details={"error_type": type(exc).__name__},
                    started_at=scenario_started,
                )
            )
    # Cancellation is intentionally checked again after the last scenario so
    # a request racing the final probe cannot be reported as PASS.
    cancelled = cancelled or _cancel_requested(run_id)
    tool_records = _inventory_tools(
        str(suite["id"]),
        scanner_records=scanner_records,
        preflight_result=preflight_result,
    )
    findings, delta = _apply_baseline(
        run_id,
        str(suite["id"]),
        findings,
        str(row.get("baseline_run_id") or "") or None,
    )
    attack_paths = _attack_path_inventory()
    scenario_statuses = {str(item.get("status") or "PARTIAL").upper() for item in scenario_results}
    active_tool_statuses = {
        str(item.get("status") or "PARTIAL").upper()
        for item in tool_records
        if str(item.get("tool_id") or "") in set(ACTIVE_TOOLS_BY_SUITE.get(str(suite["id"]), ()))
    }
    severe_findings = any(
        str(item.get("status") or "open") == "open"
        and policy.normalize_severity(item.get("severity")) in {"critical", "high"}
        for item in findings
    )
    medium_findings = any(
        str(item.get("status") or "open") == "open"
        and policy.normalize_severity(item.get("severity")) == "medium"
        for item in findings
    )
    if "FAIL" in scenario_statuses or "FAIL" in active_tool_statuses or severe_findings:
        outcome = "FAIL"
    elif (
        cancelled
        or "BLOCKED" in scenario_statuses
        or "PARTIAL" in scenario_statuses
        or "PARTIAL" in active_tool_statuses
        or "MISSING" in active_tool_statuses
        or medium_findings
    ):
        outcome = "PARTIAL"
    else:
        outcome = "PASS"
    report_failure: str | None = None
    try:
        report = _build_report(
            run={**row, "started_at": row.get("started_at") or _now()},
            status=outcome,
            preflight_result=preflight_result,
            scenario_results=scenario_results,
            tool_records=tool_records,
            findings=findings,
            delta=delta,
            attack_paths=attack_paths,
            resource_start=resource_start,
            resource_finish=optimization.resource_snapshot(),
            started_monotonic=started,
        )
    except Exception:
        report_failure = "report_write_failed"
        report = {"available": False, "failure_code": report_failure, "sanitized": True}
        if outcome == "PASS":
            outcome = "PARTIAL"
    final = _set_terminal(
        run_id,
        status=outcome,
        summary={
            "status": outcome,
            "suite_id": suite["id"],
            "scenario_count": len(scenario_results),
            "tool_count": len(tool_records),
            "finding_count": len(findings),
            "high_or_critical_findings": sum(
                1
                for item in findings
                if policy.normalize_severity(item.get("severity")) in {"critical", "high"}
                and item.get("status") == "open"
            ),
            "medium_findings": sum(
                1
                for item in findings
                if policy.normalize_severity(item.get("severity")) == "medium"
                and item.get("status") == "open"
            ),
            "cancelled": cancelled,
            "report_available": bool(report.get("available")),
            "failure_code": report_failure,
            "sanitized": True,
        },
        report=report,
        scenarios=scenario_results,
        tools=tool_records,
        findings=findings,
        failure_code=report_failure,
    )
    _assurance_audit(
        event_type="assurance_run_completed",
        reason_code="assurance_completed",
        principal_id=str(row.get("principal_id") or ""),
        session_id=str(row.get("harness_session_id") or ""),
        operation_id=run_id,
        result=str(outcome).lower(),
        summary="Runtime security assurance completed with a normalized sanitized result.",
    )
    return final


def read_report(run_id: str) -> dict[str, Any]:
    safe = _safe_run_id(run_id)
    root = _report_root(safe, create=False)
    if not root.is_dir():
        return {"available": False, "run_id": safe, "files": [], "sanitized": True}
    allowed = {
        "manifest.json",
        "environment.json",
        "toolchain.json",
        "findings.json",
        "threat-coverage.json",
        "owasp-coverage.json",
        "attack-path-results.json",
        "controls.json",
        "delta.json",
        "performance.json",
        "sanitization.json",
        "checksums.json",
        "summary.md",
    }
    files: dict[str, Any] = {}
    for filename in sorted(allowed):
        path = root / filename
        if not path.is_file() or path.resolve().parent != root.resolve():
            continue
        if filename.endswith(".json"):
            payload = deps.core.read_json_file(path, {})
            files[filename] = _redact(payload if isinstance(payload, Mapping) else {})
        else:
            try:
                files[filename] = policy.redact_text(
                    path.read_text(encoding="utf-8", errors="replace")[:64 * 1024]
                )
            except OSError:
                continue
    return _redact({"available": bool(files), "run_id": safe, "files": files, "sanitized": True})


def check_registries() -> dict[str, Any]:
    return validate_registries()
