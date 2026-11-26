"""Independent GitHub attestation verification in the release child only."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

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
