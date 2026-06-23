from __future__ import annotations

import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any


COMMAND_SUBJECT = "pocketlab.commands.lite.security.scan"

SEVERITIES = ("critical", "high", "medium", "low", "info")
SCORE_WEIGHTS = {"critical": 30, "high": 15, "medium": 5, "low": 1, "info": 0}

TIMEOUTS = {
    "lynis": int(os.environ.get("POCKETLAB_LITE_SECURITY_LYNIS_TIMEOUT", "180")),
    "trivy_vuln_misconfig": int(os.environ.get("POCKETLAB_LITE_SECURITY_TRIVY_TIMEOUT", "300")),
    "trivy_secret": int(os.environ.get("POCKETLAB_LITE_SECURITY_TRIVY_SECRET_TIMEOUT", "180")),
    "trivy_sbom": int(os.environ.get("POCKETLAB_LITE_SECURITY_SBOM_TIMEOUT", "180")),
    "overall": int(os.environ.get("POCKETLAB_LITE_SECURITY_OVERALL_TIMEOUT", "600")),
}

EXCLUDED_DIRS = [
    "node_modules",
    ".venv",
    "dist",
    ".pocketlab-dev",
    ".git",
    "pocket-lab-lite-backups",
    "backups",
    ".cache",
    "tmp",
    "temp",
    "logs",
]

SENSITIVE_KEY_RE = re.compile(
    r"(token|password|passwd|pwd|secret|api[_-]?key|authorization|bearer|vault|unseal|nats|invite|tailscale[_-]?auth|private[_-]?key)",
    re.IGNORECASE,
)


ANSI_ESCAPE_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
LEADING_E_RE = re.compile(r"^\s*-e\s+")
STATUS_PADDING_RE = re.compile(r"\s{2,}")

LYNIS_NOISE_PATTERNS = (
    re.compile(r"^$", re.IGNORECASE),
    re.compile(r"^warnings?\s*\(\d+\):?", re.IGNORECASE),
    re.compile(r"^suggestions?\s*\(\d+\):?", re.IGNORECASE),
    re.compile(r"^\[\+\]", re.IGNORECASE),
    re.compile(r"^hardening index\b", re.IGNORECASE),
    re.compile(r"^auditing, system hardening, and compliance", re.IGNORECASE),
    re.compile(r"^\*\s*article:\s*", re.IGNORECASE),
    re.compile(r"pid file exists", re.IGNORECASE),
    re.compile(r"had a long execution", re.IGNORECASE),
)

LYNIS_DEDUPE_PATTERNS = (
    (re.compile(r"consider hardening ssh configuration", re.IGNORECASE), "ssh-hardening"),
)

PROTECTED_RUNTIME_SECRET_TARGETS = (
    "gitea/conf/app.runtime.ini",
)

SECRET_VALUE_REPLACEMENTS = [
    re.compile(r"(Authorization\s*:\s*)(Bearer\s+)?[^\s'\"<>]+", re.IGNORECASE),
    re.compile(r"(token\s*[=:]\s*)[^\s'\"<>]+", re.IGNORECASE),
    re.compile(r"(password\s*[=:]\s*)[^\s'\"<>]+", re.IGNORECASE),
    re.compile(r"(api[_-]?key\s*[=:]\s*)[^\s'\"<>]+", re.IGNORECASE),
    re.compile(r"(secret\s*[=:]\s*)[^\s'\"<>]+", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.IGNORECASE | re.DOTALL),
    re.compile(r"tskey-[A-Za-z0-9_-]+", re.IGNORECASE),
    re.compile(r"s\.[A-Za-z0-9]{20,}"),
]


@dataclass(frozen=True)
class ComponentRule:
    component: str
    checks: tuple[str, ...]
    matchers: tuple[str, ...]


COMPONENT_RULES = (
    ComponentRule("Lite API", ("dependency scan", "runtime health", "config exposure"), ("api_fastapi", "fastapi", "lite api")),
    ComponentRule("React/Vite PWA bundle", ("dependency scan", "frontend bundle metadata"), ("src/", "package", "vite", "react")),
    ComponentRule("Caddy config", ("config exposure", "listener posture"), ("caddy", "caddyfile")),
    ComponentRule("NATS config", ("config exposure", "network exposure"), ("nats", "jetstream")),
    ComponentRule("PM2 process definitions", ("runtime process posture",), ("pm2", "process")),
    ComponentRule("Lite worker", ("command execution boundary", "runtime health"), ("worker", "workers")),
    ComponentRule("Lite node agent", ("device command boundary", "runtime health"), ("node_agent", "agent")),
    ComponentRule("Lite supervisor", ("agent recovery", "runtime health"), ("supervisor",)),
    ComponentRule("Bootstrap scripts", ("script posture", "secret exposure"), ("bootstrap", "scripts/")),
    ComponentRule("Recovery state/evidence", ("backup evidence", "secret exclusion"), ("recovery", "backup", "restore")),
    ComponentRule("Device invite state", ("invite exposure", "identity guard"), ("invite", "fleet")),
    ComponentRule("App catalog metadata", ("catalog metadata", "dependency scan"), ("catalog",)),
    ComponentRule("Rules/protection state", ("policy state", "misconfiguration"), ("policy", "opa", "rules")),
)

GUIDANCE = [
    {
        "step": 1,
        "title": "Check local readiness",
        "summary": "Pocket Lab reviews local security and dependency posture.",
    },
    {
        "step": 2,
        "title": "Summarize what changed",
        "summary": "New issues are compared against the last safety check.",
    },
    {
        "step": 3,
        "title": "Show clear next steps",
        "summary": "Only actionable items are shown.",
    },
]


def repo_root() -> Path:
    configured = os.environ.get("POCKETLAB_LITE_SCAN_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[4]


def default_scan_roots(root: Path | None = None) -> list[Path]:
    base = (root or repo_root()).resolve()
    candidates = [
        base,
        base / "pocket-lab-final-structure",
        base / "scripts",
        base / "src",
        base / "package-lock.json",
        base / "package.json",
        base / "requirements.txt",
        base / "requirements-dev.txt",
        base / "Taskfile.yml",
        base / "pocket-lab-final-structure" / "pocket-lab-bootstrap-production-scripts-patched" / "scripts",
    ]
    return [item for item in candidates if item.exists()]


def allowed_scan_root(value: str | Path | None = None) -> Path:
    base = repo_root().resolve()
    if value is None or not str(value).strip() or str(value).strip() == "local":
        return base
    candidate = Path(value).expanduser().resolve()
    allowed = [base, *[p.resolve() for p in default_scan_roots(base) if p.is_dir()]]
    if any(candidate == root or root in candidate.parents for root in allowed):
        return candidate
    return base


def redact_text(value: str) -> str:
    redacted = str(value)
    for pattern in SECRET_VALUE_REPLACEMENTS:
        redacted = pattern.sub(lambda match: (match.group(1) if match.groups() else "") + "***REDACTED***", redacted)
    return redacted


def redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        clean: dict[str, Any] = {}
        for key, item in value.items():
            if SENSITIVE_KEY_RE.search(str(key)):
                clean[str(key)] = "***REDACTED***"
            else:
                clean[str(key)] = redact_value(item)
        return clean
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


def normalize_severity(value: Any) -> str:
    raw = str(value or "info").strip().lower()
    if raw in {"negligible", "unknown", "none"}:
        return "info"
    if raw in SEVERITIES:
        return raw
    return "info"


def score_for_counts(counts: dict[str, int]) -> int:
    score = 100
    for severity, weight in SCORE_WEIGHTS.items():
        score -= int(counts.get(severity, 0)) * weight
    return max(0, min(100, score))


def status_for_score(score: int, counts: dict[str, int]) -> tuple[str, str]:
    if int(counts.get("critical", 0)) > 0 or score <= 39:
        return "danger", "Urgent safety issue"
    if score <= 69:
        return "degraded", "Needs attention"
    if score <= 89:
        return "review", "Needs review"
    return "healthy", "Looks safe"


def clean_security_text(value: Any) -> str:
    cleaned = ANSI_ESCAPE_RE.sub("", str(value or ""))
    cleaned = LEADING_E_RE.sub("", cleaned).strip()
    cleaned = STATUS_PADDING_RE.sub(" ", cleaned)
    return redact_text(cleaned).strip()


def should_skip_lynis_text(value: str) -> bool:
    cleaned = clean_security_text(value)
    return any(pattern.search(cleaned) for pattern in LYNIS_NOISE_PATTERNS)


def lynis_dedupe_key(value: str) -> str:
    cleaned = clean_security_text(value).lower()
    for pattern, key in LYNIS_DEDUPE_PATTERNS:
        if pattern.search(cleaned):
            return key
    return cleaned


def _safe_mode(path: Path) -> int | None:
    try:
        return stat.S_IMODE(path.stat().st_mode)
    except OSError:
        return None


def is_protected_runtime_secret(target: str, root: Path | None = None) -> bool:
    raw_target = str(target or "").replace("\\", "/").lstrip("/")
    if raw_target not in PROTECTED_RUNTIME_SECRET_TARGETS:
        return False
    base = (root or repo_root()).resolve()
    candidate = (base / raw_target).resolve()
    try:
        candidate.relative_to(base)
    except ValueError:
        return False
    file_mode = _safe_mode(candidate)
    parent_mode = _safe_mode(candidate.parent)
    if file_mode is None or parent_mode is None:
        return False
    file_locked = (file_mode & 0o077) == 0
    parent_locked = (parent_mode & 0o077) == 0
    return file_locked and parent_locked
