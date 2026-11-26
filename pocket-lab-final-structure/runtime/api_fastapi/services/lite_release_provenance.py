"""Independent GitHub attestation verification in the release child only."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess

from .lite_release_contract import DEFAULT_REPOSITORY


def provenance(directory: Path, root_dir: Path, *, commit: str, tag: str):
    gh = shutil.which("gh")
    root = root_dir / "github-trusted-root.jsonl"
    bundle = directory / "pocketlab-lite-provenance.jsonl"
    pin = os.environ.get("POCKETLAB_RELEASE_ATTESTATION_ROOT_SHA256", "")
    if not gh or not pin or root.is_symlink() or bundle.is_symlink():
        return "unknown", "provenance_verifier_or_root_unavailable"
    try:
        if root.stat().st_size > 2 * 1024 * 1024 or bundle.stat().st_size > 2 * 1024 * 1024:
            return "failed", "provenance_size_invalid"
        if hashlib.sha256(root.read_bytes()).hexdigest() != pin:
            return "failed", "provenance_root_pin_mismatch"
        # No credentials or debug settings inherited. Local root and bundle
        # allow offline verification without contacting a release URL.
        env = {k: os.environ[k] for k in ("PATH", "HOME", "TMPDIR", "PREFIX", "SYSTEMROOT") if k in os.environ}
        env.update({"GH_PROMPT_DISABLED": "1", "GH_NO_UPDATE_NOTIFIER": "1", "GH_HOST": "github.com"})
        for subject in ("dist.zip", "pocketlab-lite-trust.dsse.json"):
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
    except (OSError, subprocess.TimeoutExpired):
        return "unknown", "provenance_verification_unavailable"
