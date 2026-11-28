"""Independent release provenance verification in the release child only.

Production uses the pinned GitHub attestation root.  The disposable
qualification lane has a separate, explicitly selected Ed25519 provenance
authority so an unpublished candidate can exercise the backend observation
path without pretending that a local fixture is GitHub Actions provenance.
"""
from datetime import datetime, timezone
import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .lite_lifecycle_contract import canonical_bytes
from .lite_release_contract import DEFAULT_REPOSITORY
from .lite_release_trust import _expiry, strict_json


QUALIFICATION_ROOT = "qualification-provenance-root.json"
QUALIFICATION_SCHEMA = "pocketlab.qualification-provenance/v1"
QUALIFICATION_ROOT_SCHEMA = "pocketlab.qualification-provenance-root/v1"
QUALIFICATION_DOMAIN = b"PocketLab qualification provenance v1\n"


def provenance_root_filename() -> str:
    """Return the root filename for the explicitly selected provenance lane."""
    if os.environ.get("POCKETLAB_RELEASE_PROVENANCE_SOURCE") == "qualification":
        return QUALIFICATION_ROOT
    return "github-trusted-root.jsonl"


def _decode(value: object, expected: int) -> bytes:
    try:
        decoded = base64.b64decode(str(value), validate=True)
    except (TypeError, ValueError) as exc:
        raise ValueError("qualification_provenance_encoding_invalid") from exc
    if len(decoded) != expected:
        raise ValueError("qualification_provenance_encoding_invalid")
    return decoded


def _bounded_read(root: Path, name: str, limit: int) -> bytes:
    """Read one private regular file without allowing path traversal."""
    if Path(name).name != name or name in {"", ".", ".."}:
        raise ValueError("qualification_provenance_filename_invalid")
    base = root.resolve(strict=True)
    root_info = base.stat()
    if root_info.st_uid != os.getuid() or root_info.st_mode & 0o077:
        raise ValueError("qualification_provenance_directory_invalid")
    candidate = base / name
    if candidate.is_symlink():
        raise ValueError("qualification_provenance_file_invalid")
    path = candidate.resolve(strict=True)
    info = path.stat()
    if path.parent != base or not path.is_file() or info.st_uid != os.getuid() or info.st_mode & 0o022 or info.st_nlink != 1:
        raise ValueError("qualification_provenance_file_invalid")
    if path.stat().st_size > limit:
        raise ValueError("qualification_provenance_file_too_large")
    return path.read_bytes()


def _qualification_provenance(directory: Path, root_dir: Path, *, commit: str, tag: str,
                              trusted_now: datetime | None):
    """Verify an ephemeral candidate-bound provenance bundle."""
    if trusted_now is None:
        return "unknown", "qualification_trusted_time_required"
    try:
        from . import qualification_context
        qualification_context.enabled()
        root_name = provenance_root_filename()
        root_bytes = _bounded_read(root_dir, root_name, 64 * 1024)
        pin = os.environ.get("POCKETLAB_RELEASE_ATTESTATION_ROOT_SHA256", "")
        if not pin or hashlib.sha256(root_bytes).hexdigest() != pin:
            return "failed", "qualification_provenance_root_pin_mismatch"
        root = strict_json(root_bytes)
        required_root = {"schema", "repository", "workflow", "key_id", "algorithm", "public_key", "expires"}
        if not isinstance(root, dict) or set(root) != required_root or root.get("schema") != QUALIFICATION_ROOT_SCHEMA:
            return "failed", "qualification_provenance_root_invalid"
        if root.get("repository") != DEFAULT_REPOSITORY or root.get("workflow") != ".github/workflows/release-dist.yml":
            return "failed", "qualification_provenance_identity_invalid"
        if root.get("algorithm") != "ed25519":
            return "failed", "qualification_provenance_algorithm_invalid"
        public = _decode(root.get("public_key"), 32)
        if hashlib.sha256(public).hexdigest() != root.get("key_id"):
            return "failed", "qualification_provenance_key_id_invalid"
        _expiry(str(root.get("expires") or ""), trusted_now.astimezone(timezone.utc))
        bundle = _bounded_read(directory, "pocketlab-lite-provenance.jsonl", 2 * 1024 * 1024)
        verifier = Ed25519PublicKey.from_public_bytes(public)
        observed: dict[str, dict] = {}
        for raw_line in bundle.splitlines():
            if not raw_line.strip():
                continue
            row = strict_json(raw_line)
            required = {"schema", "subject", "sha256", "source_commit", "release_tag", "repository", "workflow", "key_id", "signature"}
            if not isinstance(row, dict) or set(row) != required or row.get("schema") != QUALIFICATION_SCHEMA:
                return "failed", "qualification_provenance_entry_invalid"
            subject = str(row.get("subject") or "")
            if Path(subject).name != subject or not subject:
                return "failed", "qualification_provenance_subject_invalid"
            if subject in observed or row.get("source_commit") != commit or row.get("release_tag") != tag:
                return "failed", "qualification_provenance_identity_mismatch"
            if row.get("repository") != DEFAULT_REPOSITORY or row.get("workflow") != ".github/workflows/release-dist.yml" or row.get("key_id") != root.get("key_id"):
                return "failed", "qualification_provenance_identity_mismatch"
            try:
                signature = _decode(row.get("signature"), 64)
                signed = {key: value for key, value in row.items() if key != "signature"}
                verifier.verify(signature, QUALIFICATION_DOMAIN + canonical_bytes(signed))
            except (InvalidSignature, ValueError, TypeError):
                return "failed", "qualification_provenance_signature_invalid"
            subject_path = directory / subject
            if not subject_path.is_file() or hashlib.sha256(_bounded_read(directory, subject, 256 * 1024 * 1024)).hexdigest() != row.get("sha256"):
                return "failed", "qualification_provenance_subject_digest_mismatch"
            observed[subject] = row
        from .lite_release_package import SOURCE_ASSET
        expected = {"dist.zip", "pocketlab-lite-trust.dsse.json"}
        if (directory / SOURCE_ASSET).is_file():
            expected.add(SOURCE_ASSET)
        if set(observed) != expected:
            return "failed", "qualification_provenance_subject_set_invalid"
        return "verified", "qualification_provenance_verified"
    except (OSError, UnicodeError, ValueError, TypeError, RecursionError):
        return "unknown", "qualification_provenance_unavailable"


def provenance(directory: Path, root_dir: Path, *, commit: str, tag: str,
               trusted_now: datetime | None = None):
    if os.environ.get("POCKETLAB_RELEASE_PROVENANCE_SOURCE") == "qualification":
        return _qualification_provenance(directory, root_dir, commit=commit, tag=tag, trusted_now=trusted_now)
    gh = shutil.which("gh")
    root = root_dir / "github-trusted-root.jsonl"
    bundle = directory / "pocketlab-lite-provenance.jsonl"
    pin = os.environ.get("POCKETLAB_RELEASE_ATTESTATION_ROOT_SHA256", "")
    if not gh or not pin or root.is_symlink() or bundle.is_symlink():
        return "unknown", "provenance_verifier_or_root_unavailable"
    try:
        if root.stat().st_size > 2 * 1024 * 1024 or bundle.stat().st_size > 2 * 1024 * 1024:
            return "failed", "provenance_size_invalid"
        from .lite_release_trust_runtime import _read
        root_bytes = _read(root_dir, root.name, 2 * 1024 * 1024)
        if hashlib.sha256(root_bytes).hexdigest() != pin:
            return "failed", "provenance_root_pin_mismatch"
        # No credentials or debug settings inherited. Local root and bundle
        # allow offline verification without contacting a release URL.
        root = directory / "verified-attestation-root.jsonl"
        with root.open("xb") as out:
            out.write(root_bytes)
        root.chmod(0o400)
        home = directory / "gh-home"
        home.mkdir(mode=0o700)
        env = {k: os.environ[k] for k in ("PATH", "TMPDIR", "PREFIX", "SYSTEMROOT") if k in os.environ}
        env.update({"HOME": str(home), "GH_CONFIG_DIR": str(home), "XDG_CONFIG_HOME": str(home),
                    "GH_PROMPT_DISABLED": "1", "GH_NO_UPDATE_NOTIFIER": "1", "GH_HOST": "github.com"})
        from .lite_release_package import SOURCE_ASSET
        subjects = ["dist.zip", "pocketlab-lite-trust.dsse.json"]
        if (directory / SOURCE_ASSET).is_file():
            subjects.append(SOURCE_ASSET)
        for subject in subjects:
            verified = False
            for ref in ("refs/heads/main", "refs/tags/" + tag):
                result = subprocess.run([gh, "attestation", "verify", str(directory / subject),
                    "--repo", DEFAULT_REPOSITORY, "--signer-workflow", DEFAULT_REPOSITORY + "/.github/workflows/release-dist.yml",
                    "--source-digest", commit, "--source-ref", ref, "--deny-self-hosted-runners",
                    "--predicate-type", "https://slsa.dev/provenance/v1",
                    "--bundle", str(bundle), "--custom-trusted-root", str(root)],
                    env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL, timeout=15, check=False)
                if result.returncode == 0:
                    verified = True
                    break
            if not verified:
                return "failed", "provenance_identity_or_signature_failed"
        return "verified", "provenance_verified"
    except FileNotFoundError:
        return "unknown", "provenance_bundle_or_root_unavailable"
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return "unknown", "provenance_verification_unavailable"
