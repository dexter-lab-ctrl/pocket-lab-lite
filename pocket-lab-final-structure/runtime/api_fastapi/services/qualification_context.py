"""Fail-closed context for the disposable candidate qualification lane.

This module is intentionally small and boring.  It is not a second control
plane and it does not turn the normal production destination into a user
configurable URL.  The only caller that can enable it is the qualification
controller, which supplies a run-bound root, loopback HTTPS origin, candidate
SHA, and an ephemeral context token.  Any missing, malformed, or unsafe value
leaves the context disabled (or raises when a partially configured context is
observed).
"""
from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from urllib.parse import urlsplit


CONTEXT_VERSION = "isolated-runtime-v1"
DESTINATION_ID = "server-photoprism-originals"
_RUN_ID_RE = re.compile(r"^[a-f0-9]{12,64}$")
_SHA_RE = re.compile(r"^[a-f0-9]{40}$")
_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{32,256}$")
_USER_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


class QualificationContextError(RuntimeError):
    """The process attempted to use an unsafe or incomplete test context."""


def _value(name: str) -> str:
    return os.environ.get(name, "").strip()


def _contained(path: Path, root: Path) -> bool:
    try:
        return os.path.commonpath((str(path), str(root))) == str(root)
    except (OSError, ValueError):
        return False


def _resolved_without_symlink_escape(path: Path, root: Path) -> Path:
    root_real = root.resolve(strict=True)
    if root.is_symlink():
        raise QualificationContextError("qualification root must not be a symlink")
    candidate = path
    # Resolve existing parents one component at a time.  A symlink in the
    # writable tree is an escape even if the final target happens to be below
    # the root today.
    current = root_real
    try:
        relative = path.absolute().relative_to(root.absolute())
    except ValueError as exc:
        raise QualificationContextError("qualification path is outside the run root") from exc
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise QualificationContextError("qualification writable paths may not contain symlinks")
    resolved = candidate.resolve(strict=False)
    if not _contained(resolved, root_real):
        raise QualificationContextError("qualification path escapes the run root")
    return resolved


def configured() -> bool:
    """Return true when any qualification binding was supplied."""
    return any(name.startswith("POCKETLAB_QUALIFICATION_") for name in os.environ)


def enabled() -> bool:
    """Return true only for the complete, explicitly armed lane context."""
    if not configured():
        return False
    assert_safe()
    return True


def assert_safe() -> None:
    """Validate every mutable qualification binding before it is consumed."""
    if _value("POCKETLAB_ENVIRONMENT").casefold() != "qualification":
        raise QualificationContextError("qualification context requires the qualification environment")
    if _value("POCKETLAB_QUALIFICATION_CONTEXT") != CONTEXT_VERSION:
        raise QualificationContextError("qualification context version is missing or unsupported")
    run_id = _value("POCKETLAB_QUALIFICATION_RUN_ID")
    candidate_sha = _value("POCKETLAB_QUALIFICATION_CANDIDATE_SHA").casefold()
    if not _RUN_ID_RE.fullmatch(run_id):
        raise QualificationContextError("qualification run identity is invalid")
    if not _SHA_RE.fullmatch(candidate_sha) or candidate_sha == "0" * 40:
        raise QualificationContextError("qualification candidate SHA is invalid")
    if _value("POCKETLAB_QUALIFICATION_ALLOW_TEST_DESTINATION") != "1":
        raise QualificationContextError("qualification test destination is not explicitly enabled")
    if not _TOKEN_RE.fullmatch(_value("POCKETLAB_QUALIFICATION_CONTEXT_TOKEN")):
        raise QualificationContextError("qualification context token is missing or malformed")
    if not _TOKEN_RE.fullmatch(_value("POCKETLAB_QUALIFICATION_WEBDAV_PASSWORD")):
        raise QualificationContextError("qualification WebDAV credential is missing or malformed")
    username = _value("POCKETLAB_QUALIFICATION_WEBDAV_USER") or "qualification"
    if not _USER_RE.fullmatch(username):
        raise QualificationContextError("qualification WebDAV username is malformed")

    root_raw = _value("POCKETLAB_QUALIFICATION_ROOT")
    destination_raw = _value("POCKETLAB_QUALIFICATION_DESTINATION_ROOT")
    if not root_raw or not destination_raw:
        raise QualificationContextError("qualification writable roots are incomplete")
    root = Path(root_raw).expanduser()
    if not root.exists() or not root.is_dir():
        raise QualificationContextError("qualification root is not a directory")
    root = root.resolve(strict=True)
    destination = Path(destination_raw).expanduser()
    destination = _resolved_without_symlink_escape(destination, root)
    if destination == root:
        raise QualificationContextError("qualification destination must be a child of the run root")

    # A test destination must never alias the installed PhotoPrism originals
    # path, even if a caller accidentally points the run root at a familiar
    # production location.
    production = (
        Path.home()
        / ".pocket_lab"
        / "lite"
        / "apps"
        / "photoprism"
        / "originals"
    ).expanduser().resolve(strict=False)
    if destination == production or _contained(destination, production) or _contained(production, destination):
        raise QualificationContextError("qualification destination aliases the production originals path")

    _assert_loopback_origin(
        _value("POCKETLAB_QUALIFICATION_TEST_ORIGIN"),
        label="WebDAV",
    )
    _assert_loopback_origin(
        _value("POCKETLAB_QUALIFICATION_CONTROL_ORIGIN"),
        label="control API",
    )


def _assert_loopback_origin(origin: str, *, label: str) -> None:
    parsed = urlsplit(origin.rstrip("/"))
    try:
        port = parsed.port
    except ValueError as exc:
        raise QualificationContextError(f"qualification {label} origin port is invalid") from exc
    if (
        parsed.scheme != "https"
        or parsed.hostname not in {"127.0.0.1", "::1", "localhost"}
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
        or not port
    ):
        raise QualificationContextError(f"qualification {label} origin must be an HTTPS loopback endpoint")


def root() -> Path:
    assert_safe()
    return Path(_value("POCKETLAB_QUALIFICATION_ROOT")).expanduser().resolve(strict=True)


def destination_root() -> Path:
    assert_safe()
    return _resolved_without_symlink_escape(
        Path(_value("POCKETLAB_QUALIFICATION_DESTINATION_ROOT")).expanduser(),
        root(),
    )


def test_origin() -> str:
    assert_safe()
    return _value("POCKETLAB_QUALIFICATION_TEST_ORIGIN").rstrip("/")


def control_origin() -> str:
    assert_safe()
    return _value("POCKETLAB_QUALIFICATION_CONTROL_ORIGIN").rstrip("/")


def synthetic_password() -> str:
    assert_safe()
    return _value("POCKETLAB_QUALIFICATION_WEBDAV_PASSWORD")


def synthetic_username() -> str:
    assert_safe()
    return _value("POCKETLAB_QUALIFICATION_WEBDAV_USER") or "qualification"


def synthetic_auth_id(node_id: str, backup_id: str) -> str:
    assert_safe()
    material = f"{_value('POCKETLAB_QUALIFICATION_RUN_ID')}:{node_id}:{backup_id}".encode()
    return "qualification-" + hashlib.sha256(material).hexdigest()[:32]


def credential_ttl_seconds(default: int = 5400) -> int:
    if not enabled():
        return max(3600, min(7200, int(os.environ.get("POCKETLAB_PHOTO_BACKUP_CREDENTIAL_TTL_SECONDS", str(default)))))
    raw = _value("POCKETLAB_PHOTO_BACKUP_CREDENTIAL_TTL_SECONDS") or "120"
    try:
        value = int(raw)
    except ValueError as exc:
        raise QualificationContextError("qualification credential TTL is invalid") from exc
    if not 30 <= value <= 900:
        raise QualificationContextError("qualification credential TTL is outside the bounded test range")
    return value


def public_summary() -> dict[str, object]:
    """Return evidence-safe context metadata without roots, URLs, or secrets."""
    if not enabled():
        return {"enabled": False}
    return {
        "enabled": True,
        "context": CONTEXT_VERSION,
        "run_id": _value("POCKETLAB_QUALIFICATION_RUN_ID"),
        "candidate_sha": _value("POCKETLAB_QUALIFICATION_CANDIDATE_SHA").casefold(),
        "destination_id": DESTINATION_ID,
        "origin_class": "https_loopback",
        "credential_scope": "synthetic_run_node_backup",
    }
