#!/usr/bin/env python3
"""Prepare deterministic release-review assets, without publishing or provisioning trust.

Run only in a controlled developer/release environment with runtime dependencies.
An explicit external signer must sign the DSSE PAE bytes; unsigned output is
never a trusted release. The release job must independently bind provenance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
RUNTIME = ROOT / "pocket-lab-final-structure/runtime"
sys.path.insert(0, str(RUNTIME))
from api_fastapi.services.lite_lifecycle_contract import canonical_bytes, inventory
from api_fastapi.services.lite_release_trust import CapabilityManifest, ReleaseMetadata, MAX_BYTES, pae
from api_fastapi.services.lite_release_contract import parse_lite_tag


def file_hash(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write(out, name, value):
    raw = canonical_bytes(value)
    if len(raw) > MAX_BYTES:
        raise ValueError("metadata_size_invalid")
    (out / name).write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def metadata_version(tag):
    # Strictly ordered by date and sequence; independent of run scheduling,
    # retry attempts and mutable GitHub repository variables.
    parse_lite_tag(tag)
    date, sequence = tag.removeprefix("lite-").rsplit(".", 1)
    return int(date.replace(".", "")) * 1_000_000 + int(sequence)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--channel", choices=("stable", "preview"), required=True)
    parser.add_argument("--metadata-version", type=int, help="Optional assertion of the deterministic version")
    parser.add_argument("--root-version", type=int, required=True)
    parser.add_argument("--expires", required=True)
    parser.add_argument("--schema-min", type=int, required=True)
    parser.add_argument("--schema-max", type=int, required=True)
    args = parser.parse_args()
    version = metadata_version(args.tag)
    if args.metadata_version is not None and args.metadata_version != version:
        raise SystemExit("metadata version must match the release tag")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if head != args.commit or subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT, text=True
    ).strip():
        raise SystemExit("exact clean release source required")
    out = args.output.resolve()
    out.mkdir(mode=0o700, parents=True, exist_ok=False)
    digest = file_hash(args.assets / "dist.zip")
    manifest = json.loads((args.assets / "pocketlab-lite-release.json").read_bytes())
    if (manifest.get("release_tag") != args.tag or manifest.get("source_commit") != args.commit
            or manifest.get("artifact_sha256") != digest):
        raise SystemExit("release identity mismatch")
    cap = {"schema_version": 1, "release_tag": args.tag, "source_commit": args.commit,
           "artifact_sha256": digest, "capabilities": inventory()}
    CapabilityManifest.model_validate_json(canonical_bytes(cap))
    cap_digest = write(out, "pocketlab-lite-capabilities.json", cap)
    policy = ROOT / "security/policies/opa"
    migrations = RUNTIME / "api_fastapi/db/schema"
    def entries(paths):
        return [{"path": x.relative_to(ROOT).as_posix(), "sha256": file_hash(x)} for x in sorted(paths)]
    policy_digest = write(out, "pocketlab-lite-policy-inventory.json", entries(policy.rglob("*.rego")))
    migration_digest = write(out, "pocketlab-lite-migration-inventory.json", entries(migrations.glob("*.sql")))
    payload = {"schema_version": 1, "version": version, "root_version": args.root_version,
               "repository": "dexter-lab-ctrl/pocket-lab-lite", "workflow": ".github/workflows/release-dist.yml",
               "release_tag": args.tag, "source_commit": args.commit, "channel": args.channel,
               "expires": args.expires, "artifact_sha256": digest,
               "release_manifest_sha256": file_hash(args.assets / "pocketlab-lite-release.json"),
               "capability_manifest_sha256": cap_digest, "policy_sha256": policy_digest,
               "migration_inventory_sha256": migration_digest,
               "schema_min": args.schema_min, "schema_max": args.schema_max}
    ReleaseMetadata.model_validate_json(canonical_bytes(payload))
    if args.schema_min > args.schema_max:
        raise SystemExit("schema range invalid")
    write(out, "unsigned-release-metadata.json", payload)
    (out / "unsigned-release-metadata.pae").write_bytes(pae(canonical_bytes(payload)))
    print("UNSIGNED candidate prepared; signing, provenance and publishing are separate gates")


if __name__ == "__main__":
    main()
