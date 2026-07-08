from __future__ import annotations

import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any


COMMAND_SUBJECT = "pocketlab.commands.lite.security.scan"

SCAN_PROFILE_QUICK = "quick"
VALID_SCAN_PROFILES = {SCAN_PROFILE_QUICK}

def normalize_scan_profile(value: Any = None) -> str:
    profile = str(value or SCAN_PROFILE_QUICK).strip().lower().replace("-", "_")
    if not profile:
        return SCAN_PROFILE_QUICK
    if profile in VALID_SCAN_PROFILES:
        return profile
    raise ValueError(f"Unsupported Security scan profile: {profile}")

SEVERITIES = ("critical", "high", "medium", "low", "info")
SCORE_WEIGHTS = {"critical": 30, "high": 15, "medium": 5, "low": 1, "info": 0}

TIMEOUTS = {
    "lynis": int(os.environ.get("POCKETLAB_LITE_SECURITY_LYNIS_TIMEOUT", "300")),
    "trivy_vuln_misconfig": int(os.environ.get("POCKETLAB_LITE_SECURITY_TRIVY_TIMEOUT", "420")),
    "trivy_secret": int(os.environ.get("POCKETLAB_LITE_SECURITY_TRIVY_SECRET_TIMEOUT", "240")),
    "trivy_sbom": int(os.environ.get("POCKETLAB_LITE_SECURITY_SBOM_TIMEOUT", "240")),
    "overall": int(os.environ.get("POCKETLAB_LITE_SECURITY_OVERALL_TIMEOUT", "900")),
}

EXCLUDED_DIRS = [
    "node_modules",
    ".git",
    "dist",
    "pwa_dist",
    "pwa_dist.previous.*",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".cache",
    ".npm",
    ".pocketlab-dev",
    ".pocket_lab/trivy-cache",
    ".pocket_lab/lynis-tmp",
    ".pm2/logs",
    "go/pkg",
    "pocket-lab-lite-backups",
    "restore-checkpoints",
    "restore-runs",
    "backups",
    "logs",
    "tmp",
    "temp",
    "state/workflows",
    "state/runs",
    "state/operations",
    "state/runner_events",
    "state/security/evidence",
    "vault/data",
    "gitea/data",
    "gitea/log",
    "observability_configs/*_data",
    "proot-distro/containers/ubuntu/rootfs",
    "var/lib/proot-distro/containers/ubuntu/rootfs",
    "mnt/sdcard",
    "sdcard",
    "storage",
    ".pocket_lab/lite/apps/photoprism/import",
    ".pocket_lab/lite/apps/photoprism/originals",
    ".pocket_lab/lite/apps/photoprism/storage/cache",
    ".pocket_lab/lite/apps/photoprism/storage/cache/media",
    ".pocket_lab/lite/apps/photoprism/storage/cache/thumbnails",
    ".pocket_lab/lite/apps/photoprism/storage/sidecar",
    ".pocket_lab/lite/apps/photoprism/logs",
]

EXCLUDED_FILES = [
    "*.pyc",
    "index.db",
    "photoprism/index.db",
]

QUICK_EXCLUDED_GROUPS = [
    "Photo library/media",
    "Backup payloads and restore checkpoints",
    "PROot Ubuntu full filesystem",
    "Go/npm/cache folders",
    "Old PWA builds",
    "Large runtime histories",
    "Scanner caches and generated logs",
]

QUICK_SKIPPED_TARGETS = [
    "PhotoPrism media and originals",
    "Android shared storage",
    "Pocket Lab backup payloads",
    "PROot Ubuntu full rootfs",
    "Go module cache",
    "npm cache",
    "Trivy cache",
    "Lynis temp files",
    "Old PWA build folders",
    "Large runtime histories",
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
    re.compile(r"cannot open /proc/net/dev.*permission denied.*limited output", re.IGNORECASE),
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
    re.compile(r"s\.[A-Za-z0-9]{20,}")
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
        base / "pocket-lab-final-structure" / "pocket-lab-bootstrap-production-scripts-patched" / "scripts"
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


def _quick_target(root: Path, label: str, relative: str) -> dict[str, Any]:
    path = (root / relative).resolve()
    return {
        "label": label,
        "relative": relative,
        "present": path.exists(),
        "kind": "directory" if path.is_dir() else "file",
    }


def quick_scan_excludes() -> dict[str, Any]:
    return {
        "skip_dirs": list(EXCLUDED_DIRS),
        "skip_files": list(EXCLUDED_FILES),
        "excluded_groups": list(QUICK_EXCLUDED_GROUPS),
        "skipped_targets": list(QUICK_SKIPPED_TARGETS),
    }


def trivy_skip_args(root: Path, excludes: dict[str, Any] | None = None) -> list[str]:
    _ = root  # kept for future profile-specific absolute allowlist support
    plan = excludes or quick_scan_excludes()
    args: list[str] = []
    for item in plan.get("skip_dirs") or []:
        args.extend(["--skip-dirs", str(item)])
    for item in plan.get("skip_files") or []:
        args.extend(["--skip-files", str(item)])
    return args


def build_quick_scan_plan(root: Path | None = None) -> dict[str, Any]:
    base = (root or repo_root()).resolve()
    source_targets = [
        _quick_target(base, "package.json", "package.json"),
        _quick_target(base, "package-lock.json", "package-lock.json"),
        _quick_target(base, "Python dev requirements", "requirements-dev.txt"),
        _quick_target(base, "Lite API runtime requirements", "pocket-lab-final-structure/runtime/requirements.txt"),
        _quick_target(base, "Lite API dev requirements", "pocket-lab-final-structure/runtime/requirements-dev.txt"),
        _quick_target(base, "React/Vite source", "src"),
        _quick_target(base, "Scripts", "scripts"),
        _quick_target(base, "Lite API runtime", "pocket-lab-final-structure/runtime"),
        _quick_target(base, "Bootstrap scripts", "pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts"),
        _quick_target(base, "Caddy route config", "caddy/Caddyfile"),
        _quick_target(base, "Security policies", "security/policies"),
        _quick_target(base, "Operations metadata", "operations"),
        _quick_target(base, "Runbooks", "runbooks"),
        _quick_target(base, "Contracts", "contracts"),
    ]
    excludes = quick_scan_excludes()
    return {
        "profile": SCAN_PROFILE_QUICK,
        "scan_root_label": "Pocket Lab Lite repo",
        "target_groups": [
            "Termux host posture",
            "Pocket Lab Lite source/runtime config",
            "Runtime config posture",
        ],
        "source_targets": source_targets,
        "checked_targets": [
            "Termux host posture",
            "Pocket Lab Lite files",
            "Caddy route config",
            "NATS config posture",
            "Services summary",
            "Security evidence state",
        ],
        "skipped_targets": excludes["skipped_targets"],
        "excluded_groups": excludes["excluded_groups"],
        "skip_dirs": excludes["skip_dirs"],
        "skip_files": excludes["skip_files"],
    }


def redact_text(value: str) -> str:
    redacted = str(value)
    for pattern in SECRET_VALUE_REPLACEMENTS:
        redacted = pattern.sub(lambda match: (match.group(1) if match.groups() else "") + "***REDACTED***", redacted)
    return redacted


SAFE_SCANNER_METADATA_KEYS = {
    "returncode",
    "return_code",
    "exit_code",
    "vuln_returncode",
    "vulnerability_returncode",
    "misconfig_returncode",
    "secret_returncode",
    "lynis_returncode",
}


def is_safe_scanner_metadata_key(key: Any) -> bool:
    normalized = str(key or "").strip().lower().replace("-", "_")
    return normalized in SAFE_SCANNER_METADATA_KEYS or normalized.endswith("_returncode")


def redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        clean: dict[str, Any] = {}
        for key, item in value.items():
            if SENSITIVE_KEY_RE.search(str(key)) and not is_safe_scanner_metadata_key(key):
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
