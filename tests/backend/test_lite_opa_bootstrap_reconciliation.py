from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
BOOTSTRAP = ROOT / "pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/bootstrap.sh"
START_DASHBOARD = ROOT / "pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/start-dashboard.sh"
HEALTH = ROOT / "pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/lite/bootstrap-stage-health.sh"
OPA_STARTUP_RESOLVER = ROOT / "pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/lite/resolve-opa-startup-policy.py"
OPA_RUNTIME_START = ROOT / "pocket-lab-final-structure/pocket-lab-bootstrap-production-scripts-patched/scripts/lite/start-opa-runtime.sh"


def _run_helper(
    tmp_path: Path,
    body: str,
    *,
    use_canonical_lite_base: bool = False,
) -> subprocess.CompletedProcess[str]:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir(parents=True)

    opa = fake_bin / "opa"
    opa.write_text("#!/usr/bin/env bash\n[[ ${1:-} == version ]] && { echo 'Version: 1.19.0'; exit 0; }\nexit 0\n")
    opa.chmod(0o755)

    pm2 = fake_bin / "pm2"
    pm2.write_text("#!/usr/bin/env bash\n[[ ${1:-} == describe && ${2:-} == pocket-opa ]]\n")
    pm2.chmod(0o755)

    curl = fake_bin / "curl"
    curl.write_text(
        "#!/usr/bin/env bash\n"
        "url=${@: -1}\n"
        "case $url in\n"
        "  http://127.0.0.1:8181/health) printf '{}';;\n"
        "  http://127.0.0.1:8181/v1/data/pocketlab/meta/revision) printf '{\"result\":\"test-revision\"}';;\n"
        "  http://127.0.0.1:8080/api/lite/policy)\n"
        "    if [[ -n ${FAKE_POLICY_JSON:-} ]]; then\n"
        "      printf '%s' \"$FAKE_POLICY_JSON\"\n"
        "    else\n"
        "      printf '{}'\n"
        "    fi\n"
        "    ;;\n"
        "  *) exit 22;;\n"
        "esac\n"
    )
    curl.chmod(0o755)

    lite_base = tmp_path / "pocket-lab-lite" if use_canonical_lite_base else tmp_path
    state = lite_base / "state"
    active = state / "opa" / "active"
    active.mkdir(parents=True)
    (active / "pocketlab.rego").write_text("package pocketlab\n")
    (active / "revision.txt").write_text("test-revision\n")

    if use_canonical_lite_base:
        state_exports = f"""
unset POCKETLAB_BASE_DIR POCKETLAB_STATE_DIR POCKETLAB_OPA_ACTIVE_POLICY_DIR
export POCKET_LAB_BASE_DIR={lite_base!s}
"""
    else:
        state_exports = f"export POCKETLAB_STATE_DIR={state!s}"

    script = f"""
set -Eeuo pipefail
is_done() {{ [[ \"${{1:-}}\" == lite_opa_ready ]]; }}
source {HEALTH!s}
export PATH={fake_bin!s}:$PATH
{state_exports}
{body}
"""
    return subprocess.run(
        ["bash", "-c", script],
        cwd=ROOT,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        check=False,
    )


def _create_policy_schema(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE policy_revisions (
            revision_id TEXT PRIMARY KEY,
            manifest_json TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            validation_status TEXT NOT NULL,
            lifecycle_status TEXT NOT NULL
        );
        CREATE TABLE policy_runtime_state (
            state_id INTEGER PRIMARY KEY,
            active_revision_id TEXT,
            known_good_revision_id TEXT
        );
        CREATE TABLE policy_activation_operations (
            state TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )
    return conn


def _write_policy_stage(
    state: Path,
    revision: str,
    tree: dict[str, str],
) -> tuple[str, str]:
    stage = state / "opa" / "stage" / revision
    stage.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, str]] = []
    for relative, contents in sorted(tree.items()):
        path = stage / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")
        entries.append(
            {
                "path": relative,
                "sha256": hashlib.sha256(contents.encode("utf-8")).hexdigest(),
            }
        )
    candidate_hash = hashlib.sha256(
        json.dumps(entries, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    (stage / "revision.txt").write_text(f"{revision}\n", encoding="utf-8")
    (stage / "manifest.json").write_text(
        json.dumps(
            {"revision": revision, "candidate_hash": candidate_hash, "files": entries},
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    durable_manifest = json.dumps(
        {"files": entries, "candidate_hash": candidate_hash},
        sort_keys=True,
        separators=(",", ":"),
    )
    return durable_manifest, candidate_hash


def _insert_durable_policy(
    conn: sqlite3.Connection,
    *,
    revision: str,
    manifest_json: str,
    content_hash: str,
    validation_status: str = "valid",
    lifecycle_status: str = "active",
    known_good_revision: str | None = None,
) -> None:
    conn.execute(
        "INSERT INTO policy_revisions VALUES (?,?,?,?,?)",
        (revision, manifest_json, content_hash, validation_status, lifecycle_status),
    )
    conn.execute(
        "INSERT INTO policy_runtime_state VALUES (1,?,?)",
        (revision, known_good_revision if known_good_revision is not None else revision),
    )
    conn.commit()


def _resolve_policy(state: Path, database: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "POCKETLAB_STATE_DIR": str(state),
            "POCKETLAB_LITE_DB_PATH": str(database),
        }
    )
    result = subprocess.run(
        [sys.executable, str(OPA_STARTUP_RESOLVER)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _prepare_runtime_harness(tmp_path: Path) -> tuple[Path, dict[str, str], Path]:
    scripts = tmp_path / "scripts"
    lite = scripts / "lite"
    lib = scripts / "lib"
    fake_bin = tmp_path / "bin"
    lite.mkdir(parents=True)
    lib.mkdir(parents=True)
    fake_bin.mkdir(parents=True)

    runtime = lite / "start-opa-runtime.sh"
    runtime.write_text(OPA_RUNTIME_START.read_text(encoding="utf-8"), encoding="utf-8")
    (lite / "resolve-opa-startup-policy.py").write_text("# test placeholder\n", encoding="utf-8")
    action_log = tmp_path / "actions.log"
    (lib / "common.sh").write_text(
        """#!/usr/bin/env bash
log() { :; }
die() { printf '%s\\n' \"$*\" >&2; exit 1; }
require_cmd() { local c; for c in \"$@\"; do command -v \"$c\" >/dev/null 2>&1 || die \"missing $c\"; done; }
pm2_start_or_restart() { printf 'pm2:%s\\n' \"$1\" >> \"$FAKE_ACTION_LOG\"; return 0; }
""",
        encoding="utf-8",
    )
    prepare = lite / "prepare-opa-policy.sh"
    prepare.write_text(
        """#!/usr/bin/env bash
set -Eeuo pipefail
action=${1:-stage}
revision=${2:-}
if [[ $action == stage ]]; then
  printf 'stage\\n' >> \"$FAKE_ACTION_LOG\"
  [[ ${FAKE_STAGE_FAIL:-0} != 1 ]] || exit 1
  printf 'OPA candidate staged revision=%s\\n' \"$FAKE_STAGED_REVISION\"
  exit 0
fi
printf '%s:%s\\n' \"$action\" \"$revision\" >> \"$FAKE_ACTION_LOG\"
""",
        encoding="utf-8",
    )
    prepare.chmod(0o755)

    for name in ("opa", "pm2"):
        executable = fake_bin / name
        executable.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
        executable.chmod(0o755)
    curl = fake_bin / "curl"
    curl.write_text(
        """#!/usr/bin/env bash
url=${@: -1}
case \"$url\" in
  http://127.0.0.1:8181/health) printf '{}' ;;
  http://127.0.0.1:8181/v1/data/pocketlab/meta/revision) printf '{\"result\":\"%s\"}' \"$FAKE_OBSERVED_REVISION\" ;;
  *) exit 22 ;;
esac
""",
        encoding="utf-8",
    )
    curl.chmod(0o755)

    state = tmp_path / "state"
    state.mkdir()
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_bin}{os.pathsep}{env.get('PATH', '')}",
            "POCKET_LAB_BASE_DIR": str(tmp_path / "pocket-lab-lite"),
            "POCKETLAB_STATE_DIR": str(state),
            "POCKETLAB_LITE_DB_PATH": str(state / "pocketlab-lite.sqlite3"),
            "POCKETLAB_OPA_ACTIVE_POLICY_DIR": str(state / "opa" / "active"),
            "FAKE_ACTION_LOG": str(action_log),
        }
    )
    return runtime, env, action_log


def _run_runtime_under_lock(
    runtime: Path,
    env: dict[str, str],
    *,
    mode: str,
    revision: str = "",
    staged_revision: str = "plr-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    observed_revision: str = "",
    stage_fail: bool = False,
) -> subprocess.CompletedProcess[str]:
    scoped = env.copy()
    scoped.update(
        {
            "POCKETLAB_OPA_STARTUP_MODE": mode,
            "POCKETLAB_OPA_STARTUP_REVISION": revision,
            "POCKETLAB_OPA_STARTUP_REASON_CODE": "policy_activation_pending" if mode == "blocked" else "",
            "FAKE_STAGED_REVISION": staged_revision,
            "FAKE_OBSERVED_REVISION": observed_revision or revision or staged_revision,
            "FAKE_STAGE_FAIL": "1" if stage_fail else "0",
        }
    )
    return subprocess.run(
        ["bash", str(runtime), "--under-activation-lock"],
        env=scoped,
        capture_output=True,
        text=True,
        check=False,
    )


def test_bootstrap_invalidates_stale_lite_capability_markers() -> None:
    source = BOOTSTRAP.read_text(encoding="utf-8")
    assert 'source "$LITE_STAGE_HEALTH"' in source
    assert 'pocketlab_lite_stage_completion_is_valid "$id"' in source
    assert "Ignoring stale Lite bootstrap marker" in source
    assert "completed but its Lite capability contract is not satisfied" in source
    assert "current source/runtime contract" in source


def test_start_dashboard_delegates_opa_startup_to_governed_runner() -> None:
    source = START_DASHBOARD.read_text(encoding="utf-8")
    runtime = OPA_RUNTIME_START.read_text(encoding="utf-8")
    assert 'OPA_RUNTIME_START="$SCRIPT_DIR/lite/start-opa-runtime.sh"' in source
    assert 'bash "$OPA_RUNTIME_START"' in source
    assert '"$OPA_POLICY_PREP" activate "$staged_revision"' not in source
    assert '"$OPA_POLICY_PREP" known-good "$staged_revision"' not in source
    assert 'pm2_start_or_restart pocket-opa "$(command -v opa)"' in runtime
    assert '--interpreter bash -- run --server --addr=127.0.0.1:8181' in runtime


def test_opa_startup_resolver_preserves_personal_baseline_without_durable_state(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir()
    assert _resolve_policy(state, state / "missing.sqlite3") == {
        "mode": "baseline_bootstrap",
        "reason_code": "",
        "revision_id": "",
    }

    legacy = state / "legacy.sqlite3"
    conn = sqlite3.connect(legacy)
    conn.execute("CREATE TABLE unrelated_state(id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()
    assert _resolve_policy(state, legacy)["mode"] == "baseline_bootstrap"


def test_opa_startup_resolver_uses_proved_durable_revision_not_repository_candidate(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir()
    database = state / "policy.sqlite3"
    revision = "plr-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    manifest, content_hash = _write_policy_stage(
        state,
        revision,
        {"pocketlab.rego": "package pocketlab\n", "template.json": "{}\n"},
    )
    conn = _create_policy_schema(database)
    _insert_durable_policy(
        conn,
        revision=revision,
        manifest_json=manifest,
        content_hash=content_hash,
    )
    conn.close()
    assert _resolve_policy(state, database) == {
        "mode": "durable",
        "reason_code": "",
        "revision_id": revision,
    }


def test_opa_startup_resolver_blocks_mismatched_or_unproved_durable_state(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir()
    database = state / "policy.sqlite3"
    revision = "plr-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    other = "plr-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    manifest, content_hash = _write_policy_stage(state, revision, {"pocketlab.rego": "package pocketlab\n"})
    conn = _create_policy_schema(database)
    _insert_durable_policy(
        conn,
        revision=revision,
        manifest_json=manifest,
        content_hash=content_hash,
        known_good_revision=other,
    )
    conn.close()
    assert _resolve_policy(state, database)["reason_code"] == "policy_startup_runtime_state_mismatch"

    unproved_database = state / "unproved.sqlite3"
    conn = _create_policy_schema(unproved_database)
    _insert_durable_policy(
        conn,
        revision=revision,
        manifest_json=manifest,
        content_hash=content_hash,
        validation_status="pending",
        lifecycle_status="validated",
    )
    conn.close()
    assert _resolve_policy(state, unproved_database)["reason_code"] == "policy_startup_revision_unproved"


def test_opa_startup_resolver_blocks_nonterminal_and_uncertain_operations(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir()
    for operation_state, reason in (
        ("pending", "policy_activation_pending"),
        ("rolling_back", "policy_activation_pending"),
        ("uncertain", "policy_revision_uncertain"),
    ):
        database = state / f"{operation_state}.sqlite3"
        conn = _create_policy_schema(database)
        conn.execute(
            "INSERT INTO policy_activation_operations VALUES (?,?)",
            (operation_state, "2026-09-03T00:00:00Z"),
        )
        conn.commit()
        conn.close()
        result = _resolve_policy(state, database)
        assert result["mode"] == "blocked"
        assert result["reason_code"] == reason


def test_opa_startup_resolver_fails_closed_for_missing_corrupt_or_mismatched_durable_stage(tmp_path: Path) -> None:
    revision = "plr-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

    missing_state = tmp_path / "missing"
    missing_state.mkdir()
    missing_db = missing_state / "policy.sqlite3"
    conn = _create_policy_schema(missing_db)
    conn.execute(
        "INSERT INTO policy_revisions VALUES (?,?,?,?,?)",
        (revision, '{"files":[],"candidate_hash":"deadbeef"}', "deadbeef", "valid", "active"),
    )
    conn.execute("INSERT INTO policy_runtime_state VALUES (1,?,?)", (revision, revision))
    conn.commit()
    conn.close()
    assert _resolve_policy(missing_state, missing_db)["reason_code"] == "policy_startup_durable_stage_unavailable"

    corrupt_state = tmp_path / "corrupt"
    corrupt_state.mkdir()
    corrupt_db = corrupt_state / "policy.sqlite3"
    manifest, content_hash = _write_policy_stage(corrupt_state, revision, {"pocketlab.rego": "package pocketlab\n"})
    conn = _create_policy_schema(corrupt_db)
    _insert_durable_policy(conn, revision=revision, manifest_json=manifest, content_hash=content_hash)
    conn.close()
    (corrupt_state / "opa" / "stage" / revision / "pocketlab.rego").write_text("package changed\n", encoding="utf-8")
    assert _resolve_policy(corrupt_state, corrupt_db)["reason_code"] == "policy_startup_durable_stage_corrupt"

    mismatch_state = tmp_path / "mismatch"
    mismatch_state.mkdir()
    mismatch_db = mismatch_state / "policy.sqlite3"
    durable_manifest, durable_hash = _write_policy_stage(mismatch_state, revision, {"pocketlab.rego": "package original\n"})
    stage = mismatch_state / "opa" / "stage" / revision
    for child in stage.iterdir():
        child.unlink()
    _write_policy_stage(mismatch_state, revision, {"pocketlab.rego": "package other\n"})
    conn = _create_policy_schema(mismatch_db)
    _insert_durable_policy(conn, revision=revision, manifest_json=durable_manifest, content_hash=durable_hash)
    conn.close()
    assert _resolve_policy(mismatch_state, mismatch_db)["reason_code"] == "policy_startup_durable_stage_mismatch"


def test_opa_startup_resolver_lock_timeout_never_runs_pointer_child(tmp_path: Path) -> None:
    state = tmp_path / "state"
    lock = state / "opa" / "activation.lock"
    lock.parent.mkdir(parents=True)
    marker = tmp_path / "child-ran"
    env = os.environ.copy()
    env.update(
        {
            "POCKETLAB_STATE_DIR": str(state),
            "POCKETLAB_LITE_DB_PATH": str(state / "missing.sqlite3"),
            "POCKETLAB_OPA_STARTUP_LOCK_TIMEOUT_SECONDS": "1",
        }
    )
    with lock.open("a+") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = subprocess.run(
            [
                sys.executable,
                str(OPA_STARTUP_RESOLVER),
                "--locked-exec",
                "--",
                sys.executable,
                "-c",
                f"from pathlib import Path; Path({str(marker)!r}).write_text('ran')",
            ],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    assert result.returncode == 75
    assert json.loads(result.stdout)["reason_code"] == "policy_startup_activation_lock_timeout"
    assert not marker.exists()


def test_opa_startup_locked_exec_rechecks_and_exports_durable_authority(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir()
    database = state / "policy.sqlite3"
    revision = "plr-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    manifest, content_hash = _write_policy_stage(state, revision, {"pocketlab.rego": "package pocketlab\n"})
    conn = _create_policy_schema(database)
    _insert_durable_policy(conn, revision=revision, manifest_json=manifest, content_hash=content_hash)
    conn.close()
    env = os.environ.copy()
    env.update({"POCKETLAB_STATE_DIR": str(state), "POCKETLAB_LITE_DB_PATH": str(database)})
    child = (
        "import json,os; print(json.dumps({k:os.environ.get(k,'') for k in "
        "['POCKETLAB_OPA_STARTUP_MODE','POCKETLAB_OPA_STARTUP_REVISION','POCKETLAB_OPA_STARTUP_REASON_CODE']}, sort_keys=True))"
    )
    result = subprocess.run(
        [sys.executable, str(OPA_STARTUP_RESOLVER), "--locked-exec", "--", sys.executable, "-c", child],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    exported = json.loads(result.stdout)
    assert exported["POCKETLAB_OPA_STARTUP_MODE"] == "durable"
    assert exported["POCKETLAB_OPA_STARTUP_REVISION"] == revision
    assert exported["POCKETLAB_OPA_STARTUP_REASON_CODE"] == ""


def test_opa_runtime_personal_bootstrap_still_activates_and_proves_repository_baseline(tmp_path: Path) -> None:
    runtime, env, action_log = _prepare_runtime_harness(tmp_path)
    staged = "plr-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    result = _run_runtime_under_lock(runtime, env, mode="baseline_bootstrap", staged_revision=staged)
    assert result.returncode == 0, result.stderr
    actions = action_log.read_text(encoding="utf-8").splitlines()
    assert actions == ["stage", f"activate:{staged}", "pm2:pocket-opa", f"known-good:{staged}"]


def test_opa_runtime_enterprise_durable_revision_wins_over_new_repository_candidate(tmp_path: Path) -> None:
    runtime, env, action_log = _prepare_runtime_harness(tmp_path)
    durable = "plr-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    staged = "plr-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    result = _run_runtime_under_lock(
        runtime,
        env,
        mode="durable",
        revision=durable,
        staged_revision=staged,
        observed_revision=durable,
    )
    assert result.returncode == 0, result.stderr
    actions = action_log.read_text(encoding="utf-8").splitlines()
    assert actions == ["stage", f"activate:{durable}", "pm2:pocket-opa", f"known-good:{durable}"]
    assert f"activate:{staged}" not in actions
    assert f"known-good:{staged}" not in actions


def test_opa_runtime_bad_new_repository_candidate_does_not_take_down_proved_durable_revision(tmp_path: Path) -> None:
    runtime, env, action_log = _prepare_runtime_harness(tmp_path)
    durable = "plr-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    result = _run_runtime_under_lock(
        runtime,
        env,
        mode="durable",
        revision=durable,
        observed_revision=durable,
        stage_fail=True,
    )
    assert result.returncode == 0, result.stderr
    actions = action_log.read_text(encoding="utf-8").splitlines()
    assert actions == ["stage", f"activate:{durable}", "pm2:pocket-opa", f"known-good:{durable}"]


def test_opa_runtime_blocked_state_never_mutates_policy_pointers(tmp_path: Path) -> None:
    runtime, env, action_log = _prepare_runtime_harness(tmp_path)
    result = _run_runtime_under_lock(runtime, env, mode="blocked")
    assert result.returncode == 0, result.stderr
    actions = action_log.read_text(encoding="utf-8").splitlines()
    assert actions == ["pm2:pocket-opa"]
    assert not any(action.startswith("activate:") for action in actions)
    assert not any(action.startswith("known-good:") for action in actions)


def test_install_binaries_marker_requires_usable_opa(tmp_path: Path) -> None:
    result = _run_helper(
        tmp_path,
        'pocketlab_lite_stage_completion_is_valid install_binaries; printf "%s" "$POCKETLAB_LITE_STAGE_HEALTH_REASON"',
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""


def test_start_dashboard_marker_requires_current_ready_rules_projection(tmp_path: Path) -> None:
    healthy = _run_helper(
        tmp_path / "healthy",
        """
export FAKE_POLICY_JSON='{"status":"ready","engine":{"healthy":true,"endpoint_exposed_to_browser":false},"active_policy":{"bundle_ready":true}}'
pocketlab_lite_stage_completion_is_valid start_dashboard
""",
    )
    assert healthy.returncode == 0, healthy.stderr

    legacy = _run_helper(
        tmp_path / "legacy",
        """
export FAKE_POLICY_JSON='{"status":"healthy"}'
if pocketlab_lite_stage_completion_is_valid start_dashboard; then
  exit 9
fi
printf '%s' "$POCKETLAB_LITE_STAGE_HEALTH_REASON"
""",
    )
    assert legacy.returncode == 0, legacy.stderr
    assert legacy.stdout == "FastAPI Rules projection is not bound to the ready OPA runtime"


def test_start_dashboard_marker_uses_canonical_lite_state_root(tmp_path: Path) -> None:
    result = _run_helper(
        tmp_path,
        """
export FAKE_POLICY_JSON='{"status":"ready","engine":{"healthy":true,"endpoint_exposed_to_browser":false},"active_policy":{"bundle_ready":true}}'
pocketlab_lite_stage_completion_is_valid start_dashboard
""",
        use_canonical_lite_base=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""


def test_start_dashboard_marker_fails_when_opa_capability_marker_is_missing(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir(parents=True)
    opa = fake_bin / "opa"
    opa.write_text("#!/usr/bin/env bash\nexit 0\n")
    opa.chmod(0o755)

    script = f"""
set -Eeuo pipefail
is_done() {{ return 1; }}
source {HEALTH!s}
export PATH={fake_bin!s}:$PATH
if pocketlab_lite_stage_completion_is_valid install_binaries; then
  exit 9
fi
printf '%s' "$POCKETLAB_LITE_STAGE_HEALTH_REASON"
"""
    result = subprocess.run(
        ["bash", "-c", script],
        cwd=ROOT,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == "OPA capability marker is missing"
