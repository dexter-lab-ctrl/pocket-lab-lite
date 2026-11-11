#!/usr/bin/env python3
"""Run the backend-promotion qualifier on the existing Android/Termux host.

The phone receives only an exact-SHA artifact and this controller in a fresh,
inactive cache directory. The qualifier uses disposable SQLite state and a
simulation service owner; it never changes the phone checkout, production
database, PM2 definitions, or application runtime. A read-only admission
snapshot is collected separately so a blocked production preflight cannot be
mistaken for a successful candidate activation.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shlex
import subprocess
import sys
import uuid


ROOT = Path(__file__).resolve().parents[3]
CONTROLLER = ROOT / "scripts/dev/lite/backend_runtime_promotion.py"
DEFAULT_DEVICE_ID = "pocket-lab-lite-server"


def _run(command: list[str], *, input_text: str | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, input=input_text, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if check and result.returncode != 0:
        detail = result.stderr.strip().splitlines()[-1] if result.stderr.strip() else "command failed"
        raise RuntimeError(f"{command[0]} failed: {detail[:240]}")
    return result


def _json(text: str, label: str) -> dict:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{label} did not return JSON") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"{label} did not return an object")
    return value


def _ssh(alias: str, command: str, *, input_text: str | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    return _run(["ssh", alias, command], input_text=input_text, check=check)


def _scp(alias: str, remote_root: str, paths: list[Path]) -> None:
    _run(["scp", *[str(path) for path in paths], f"{alias}:{remote_root}/"])


def _summary(raw: dict) -> dict:
    isolated = raw.get("isolated") if isinstance(raw.get("isolated"), dict) else {}
    lifecycle = isolated.get("lifecycle") if isinstance(isolated.get("lifecycle"), dict) else {}
    migration = isolated.get("migration") if isinstance(isolated.get("migration"), dict) else {}
    preflight = raw.get("preflight") if isinstance(raw.get("preflight"), dict) else {}
    return {
        "status": "PASS" if isolated.get("status") == "PASS" and raw.get("phone_checkout_unchanged") is True and preflight.get("admitted") is True else "PARTIAL",
        "candidate_qualification": {
            "status": isolated.get("status"),
            "qualification": isolated.get("qualification"),
            "failure_mode": isolated.get("failure_mode"),
            "lifecycle_status": lifecycle.get("status"),
            "lifecycle_reason_code": lifecycle.get("reason_code"),
            "migration_source_schema": migration.get("source_schema"),
            "migration_target_schema": migration.get("target_schema"),
            "applied_migrations": migration.get("applied_migrations"),
            "production_touched": isolated.get("production_touched"),
            "phone_checkout_touched": isolated.get("phone_checkout_touched"),
        },
        "artifact": raw.get("verify"),
        "production_preflight": {
            "status": preflight.get("status"),
            "admitted": preflight.get("admitted"),
            "checks": preflight.get("checks"),
            "schema_version": (preflight.get("database") or {}).get("schema_version") if isinstance(preflight.get("database"), dict) else None,
            "database_integrity": (preflight.get("database") or {}).get("integrity_check") if isinstance(preflight.get("database"), dict) else None,
            "database_identity": preflight.get("database_identity"),
            "disk_free_bytes": preflight.get("disk_free_bytes"),
            "memory_available_bytes": preflight.get("memory_available_bytes"),
            "battery_percent": preflight.get("battery_percent"),
            "thermal_max_celsius": preflight.get("thermal_max_celsius"),
            "preflight_exit": raw.get("preflight_exit"),
        },
        "phone_checkout_before": raw.get("phone_checkout_before"),
        "phone_checkout_after": raw.get("phone_checkout_after"),
        "phone_checkout_unchanged": raw.get("phone_checkout_unchanged"),
        "temporary_candidate_cleaned": raw.get("temporary_candidate_cleaned"),
        "sanitized": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Qualify the exact-SHA backend promotion controller on Android/Termux")
    parser.add_argument("--ssh-alias", default="pocketlab-termux")
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--device-id", default=DEFAULT_DEVICE_ID)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    if len(args.candidate_sha) != 40 or any(character not in "0123456789abcdef" for character in args.candidate_sha.lower()):
        raise SystemExit("candidate SHA must be a full hexadecimal commit SHA")
    run_id = uuid.uuid4().hex[:12]
    output = args.output or (ROOT / ".pocketlab-dev/validation" / f"pr649-backend-promotion-android-{args.candidate_sha[:12]}.json")
    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    artifact_dir = ROOT / ".pocketlab-dev/validation" / f"pr649-backend-artifact-{args.candidate_sha[:12]}"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    prepared = _json(_run([sys.executable, str(CONTROLLER), "prepare", "--source-sha", args.candidate_sha, "--output-dir", str(artifact_dir)]).stdout, "artifact preparation")
    artifact = Path(prepared["artifact"])
    manifest = Path(prepared["manifest"])
    checksums = Path(prepared["checksums"])
    verified = _json(_run([sys.executable, str(CONTROLLER), "verify", "--artifact", str(artifact), "--manifest", str(manifest), "--checksums", str(checksums)]).stdout, "artifact verification")

    probe_script = r'''
set -eu
repo="$HOME/pocket-lab-lite"
branch="$(git -C "$repo" branch --show-current)"
sha="$(git -C "$repo" rev-parse HEAD)"
if [ -n "$(git -C "$repo" status --porcelain)" ]; then clean=false; else clean=true; fi
printf '{"branch":"%s","sha":"%s","clean":%s}\n' "$branch" "$sha" "$clean"
'''
    before = _json(_ssh(args.ssh_alias, "bash -s", input_text=probe_script).stdout, "phone checkout preflight")
    if before.get("branch") != "main" or before.get("clean") is not True:
        raise RuntimeError("the Server Phone checkout is not clean main; no candidate was transferred")

    remote_home = _ssh(args.ssh_alias, "printf '%s' \"$HOME\"").stdout.strip()
    if not remote_home.startswith("/") or any(character.isspace() for character in remote_home):
        raise RuntimeError("the Server Phone home path was not safe for staging")
    remote_root = f"{remote_home}/.cache/pocketlab-pr649-backend-promotion-{run_id}"
    _ssh(args.ssh_alias, f"mkdir -m 700 -p -- {shlex.quote(remote_root)}")
    _scp(args.ssh_alias, remote_root, [artifact, manifest, checksums, CONTROLLER])

    remote_script = r'''
set -eu
root="$1"
expected_device="$2"
repo="$HOME/pocket-lab-lite"
database="$repo/state/pocketlab-lite.sqlite3"
before_branch="$(git -C "$repo" branch --show-current)"
before_sha="$(git -C "$repo" rev-parse HEAD)"
if [ -n "$(git -C "$repo" status --porcelain)" ]; then before_clean=false; else before_clean=true; fi
artifact="$(find "$root" -maxdepth 1 -name 'pocketlab-lite-backend-*.zip' -type f -print -quit)"
manifest="$(find "$root" -maxdepth 1 -name 'pocketlab-lite-backend-*.manifest.json' -type f -print -quit)"
checksums="$(find "$root" -maxdepth 1 -name 'pocketlab-lite-backend-*.checksums.txt' -type f -print -quit)"
python3 "$root/backend_runtime_promotion.py" verify --artifact "$artifact" --manifest "$manifest" --checksums "$checksums" > "$root/verify.json"
python3 "$root/backend_runtime_promotion.py" qualify-isolated --artifact "$artifact" --manifest "$manifest" --checksums "$checksums" --workspace "$root/isolated" --device-id "$expected_device" > "$root/isolated.json"
candidate_sha="$(python3 -c "import json; print(json.load(open('$manifest'))['source_commit'])")"
artifact_sha256="$(sha256sum "$artifact" | awk '{print $1}')"
mkdir -m 700 -p "$root/preflight-staging"
set +e
python3 "$root/backend_runtime_promotion.py" preflight --database "$database" --current-sha "$before_sha" --candidate-sha "$candidate_sha" --artifact-sha256 "$artifact_sha256" --target-device-id "$expected_device" --expected-device-id "$expected_device" --staging-root "$root/preflight-staging" --manifest "$manifest" --output "$root/preflight.json" > "$root/preflight.stdout" 2> "$root/preflight.stderr"
preflight_exit=$?
set -e
after_branch="$(git -C "$repo" branch --show-current)"
after_sha="$(git -C "$repo" rev-parse HEAD)"
if [ -n "$(git -C "$repo" status --porcelain)" ]; then after_clean=false; else after_clean=true; fi
result="$(python3 - "$root" "$preflight_exit" "$before_branch" "$before_sha" "$before_clean" "$after_branch" "$after_sha" "$after_clean" <<'PY'
import json, pathlib, sys
root = pathlib.Path(sys.argv[1])
def load(name):
    return json.loads((root / name).read_text(encoding='utf-8'))
payload = {
    'verify': load('verify.json'),
    'isolated': load('isolated.json'),
    'preflight': load('preflight.json'),
    'preflight_exit': int(sys.argv[2]),
    'phone_checkout_before': {'branch': sys.argv[3], 'sha': sys.argv[4], 'clean': sys.argv[5] == 'true'},
    'phone_checkout_after': {'branch': sys.argv[6], 'sha': sys.argv[7], 'clean': sys.argv[8] == 'true'},
    'phone_checkout_unchanged': sys.argv[3] == sys.argv[6] and sys.argv[4] == sys.argv[7] and sys.argv[5] == sys.argv[8],
    'temporary_candidate_cleaned': False,
    'sanitized': True,
}
print(json.dumps(payload, ensure_ascii=True, sort_keys=True))
PY
)"
rm -rf -- "$root"
printf '%s\n' "$result" | sed 's/"temporary_candidate_cleaned":false/"temporary_candidate_cleaned":true/'
'''
    remote = _json(_ssh(args.ssh_alias, f"bash -s -- {shlex.quote(remote_root)} {shlex.quote(args.device_id)}", input_text=remote_script).stdout, "Android/Termux qualification")
    remote["verify"] = verified
    result = _summary(remote)
    result["candidate_sha"] = args.candidate_sha
    result["artifact_sha256"] = prepared.get("artifact_sha256")
    result["ssh_alias"] = args.ssh_alias
    result["output"] = str(output)
    output.write_text(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2))
    return 0 if result["status"] == "PASS" else 3


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc)[:240], "sanitized": True}, ensure_ascii=True), file=sys.stderr)
        raise SystemExit(2)
