#!/usr/bin/env python3
"""Immutable publication and exact-byte draft recovery.

Run only from the protected release job, or authorized recovery using the
archived signed assets from the original run. Never overwrite a release asset.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

from prepare_trusted_release_candidate import metadata_version
from api_fastapi.services.lite_release_trust import Root, _parse, verify
from api_fastapi.services.lite_release_contract import parse_lite_tag

NAMES = ("dist.zip", "checksums.txt", "pocketlab-lite-release.json",
         "pocketlab-lite-capabilities.json", "pocketlab-lite-policy-inventory.json",
         "pocketlab-lite-migration-inventory.json", "pocketlab-lite-trust.dsse.json",
         "pocketlab-lite-provenance.jsonl")

def gh(*args):
    return subprocess.check_output(["gh", *args], text=True, timeout=180)

def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--channel", choices=("stable","preview"), required=True)
    parser.add_argument("--repair", choices=("true","false"), default="false")
    args = parser.parse_args()
    tag = parse_lite_tag(args.tag)
    root = _parse(Root, os.environ["POCKETLAB_RELEASE_PUBLIC_ROOT"].encode())
    paths = {name: args.assets / name for name in NAMES}
    hashes = {name: sha(path) for name, path in paths.items()}
    receipt = verify(paths["pocketlab-lite-trust.dsse.json"].read_bytes(), pinned_root=root,
        trusted_now=datetime.now(timezone.utc), highest_version=0, highest_root=root.version,
        expected_tag=args.tag, expected_commit=args.commit, channel=args.channel,
        observed_digests={"artifact_sha256":hashes["dist.zip"],
            "release_manifest_sha256":hashes["pocketlab-lite-release.json"],
            "policy_sha256":hashes["pocketlab-lite-policy-inventory.json"],
            "migration_inventory_sha256":hashes["pocketlab-lite-migration-inventory.json"]},
        capability_manifest=paths["pocketlab-lite-capabilities.json"].read_bytes())
    if receipt["metadata_version"] != metadata_version(args.tag):
        raise ValueError("metadata_version_conflict")
    if subprocess.check_output(["git","rev-list","-n","1",args.tag],text=True).strip() != args.commit:
        raise ValueError("tag_identity_mismatch")
    # A failure to enumerate is fatal, not interpreted as an empty repository.
    pages = json.loads(gh("api","--paginate","--slurp","repos/dexter-lab-ctrl/pocket-lab-lite/releases?per_page=100"))
    releases = [item for page in pages for item in page]
    existing = next((item for item in releases if item["tag_name"] == args.tag), None)
    for item in releases:
        if item["tag_name"] == args.tag or not item["tag_name"].startswith("lite-"):
            continue
        if any(asset["name"] == "pocketlab-lite-trust.dsse.json" for asset in item["assets"]):
            if parse_lite_tag(item["tag_name"]) > tag:
                raise ValueError("newer_trusted_release_exists")
    if existing and args.repair != "true":
        raise ValueError("explicit_recovery_required")
    if not existing:
        flags = ["--prerelease"] if args.channel == "preview" else []
        gh("release","create",args.tag,"--draft","--verify-tag","--title","Pocket Lab Lite " + args.tag,
           "--notes","Authenticated release metadata; review and qualification remain separate.",*flags)
    def state():
        return json.loads(gh("release","view",args.tag,"--json","isDraft,isPrerelease,assets"))
    current = state()
    if current["isPrerelease"] != (args.channel == "preview"):
        raise ValueError("channel_conflict")
    names = [asset["name"] for asset in current["assets"]]
    if len(names) != len(set(names)) or set(names) - set(NAMES):
        raise ValueError("existing_asset_conflict")
    def compare(names):
        with tempfile.TemporaryDirectory() as directory:
            for name in names:
                gh("release","download",args.tag,"--pattern",name,"--dir",directory)
                if sha(Path(directory)/name) != hashes[name]:
                    raise ValueError("existing_asset_conflict")
    compare(names)
    missing = [name for name in NAMES if name not in names]
    if not current["isDraft"]:
        if missing:
            raise ValueError("published_release_immutable")
        return
    for name in missing:
        gh("release","upload",args.tag,str(paths[name]))
    current = state()
    if not current["isDraft"] or sorted(asset["name"] for asset in current["assets"]) != sorted(NAMES):
        raise ValueError("draft_asset_set_changed")
    compare(NAMES)
    gh("release","edit",args.tag,"--draft=false")

if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("trusted publication refused; retain draft and original archived assets") from None
