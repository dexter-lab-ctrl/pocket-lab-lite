from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.dev.lite import qualification_controller as controller


def _run(tmp_path: Path, *, phase: str = "awaiting_owner", expires_at: str | None = None) -> dict:
    root = tmp_path / "run"
    root.mkdir(mode=0o700)
    for relative in ("baseline", "candidate", "runtime", "state", "base", "evidence"):
        (root / relative).mkdir(mode=0o700)
    run = {
        "schema": controller.SCHEMA,
        "run_id": "a" * 24,
        "status": "AWAITING_OPERATOR",
        "phase": phase,
        "next_action": "verify_candidate_https_then_request_owner_authentication",
        "baseline_sha": "b" * 40,
        "candidate_sha": "c" * 40,
        "run_root": str(root),
        "created_at": "2026-11-28T10:00:00Z",
        "updated_at": "2026-11-28T10:00:00Z",
        "expires_at": expires_at or "2999-01-01T00:00:00Z",
        "ports": {"api": 31001, "caddy": 31002, "nats": 31003, "monitor": 31004, "opa": 31005},
        "binaries": {},
        "pm2": {"path": str(root / "pm2"), "mode": "qualification_pm2_shim", "native_pm2_qualification": "not_run"},
        "node": str(root / "node"),
        "paths": {
            "baseline": "baseline",
            "candidate": "candidate",
            "runtime": "runtime",
            "state": "state",
            "base_dir": "base",
            "evidence": "evidence",
            "manifest": controller.MANIFEST_NAME,
        },
        "services": {"started": False, "owned": []},
        "authority": {"owner": "not_authenticated", "promotion": "not_issued", "recovery": "not_issued"},
        "origin": {"status": "not_verified", "url": None},
        "evidence": [],
        "cleanup_obligations": ["stop_run_owned_services", "remove_run_root"],
        "production_execution": False,
        "sanitized": True,
    }
    controller._atomic_json(root / controller.MANIFEST_NAME, run)
    return run


def test_manifest_round_trip_is_durable_and_does_not_store_credentials(tmp_path: Path):
    run = _run(tmp_path)
    loaded = controller._read_manifest(tmp_path / "run" / controller.MANIFEST_NAME)
    assert loaded["run_id"] == run["run_id"]
    serialized = json.dumps(loaded)
    assert all(secret not in serialized for secret in ("session_token", "cookie", "private_key", "signature"))
    assert controller._validate_run(loaded)["candidate_sha"] == "c" * 40


def test_manifest_rejects_same_baseline_and_candidate(tmp_path: Path):
    run = _run(tmp_path)
    run["baseline_sha"] = run["candidate_sha"]
    with pytest.raises(controller.QualificationControllerError, match="different exact commits"):
        controller._validate_run(run)


def test_manifest_rejects_expired_checkpoint(tmp_path: Path):
    run = _run(tmp_path, expires_at="2020-01-01T00:00:00Z")
    with pytest.raises(controller.QualificationControllerError, match="expired"):
        controller._validate_run(run)


def test_manifest_rejects_run_path_escape(tmp_path: Path):
    run = _run(tmp_path)
    run["paths"]["candidate"] = "../candidate"
    with pytest.raises(controller.QualificationControllerError, match="invalid"):
        controller._validate_run(run)


def test_owner_evidence_requires_backend_confirmation_and_candidate_binding(tmp_path: Path):
    run = _run(tmp_path)
    evidence = tmp_path / "owner.json"
    evidence.write_text(json.dumps({"sanitized": True, "candidate_sha": "c" * 40, "authentication": "browser_only"}), encoding="utf-8")
    with pytest.raises(controller.QualificationControllerError, match="backend has not confirmed"):
        controller._owner_evidence(run, evidence)


def test_owner_evidence_accepts_only_sanitized_backend_confirmation(tmp_path: Path):
    run = _run(tmp_path)
    evidence = tmp_path / "owner.json"
    evidence.write_text(json.dumps({
        "sanitized": True,
        "candidate_sha": "c" * 40,
        "authentication": "backend_confirmed_human_owner",
        "purpose": "lifecycle.release.prepare",
        "authority_epoch": 4,
        "policy_revision": "policy-revision",
        "expires_at": "2999-01-01T00:00:00Z",
    }), encoding="utf-8")
    assert controller._owner_evidence(run, evidence)["status"] == "PASS"


def test_controller_exit_codes_keep_awaiting_operator_distinct():
    assert controller.EXIT_SUCCESS != controller.EXIT_AWAITING_OPERATOR
    assert controller.EXIT_AWAITING_OPERATOR != controller.EXIT_BLOCKED
    assert controller.EXIT_FAILED != controller.EXIT_SUCCESS


def test_phase_transition_does_not_persist_internal_path_objects(tmp_path: Path):
    run = _run(tmp_path)
    updated = controller._write_phase(
        controller._validate_run(run),
        phase="cleaned",
        next_action="none",
        status="PASS",
    )
    assert "paths_resolved" not in updated
    persisted = controller._read_manifest(tmp_path / "run" / controller.MANIFEST_NAME)
    assert "paths_resolved" not in persisted
    assert persisted["phase"] == "cleaned"


def test_baseline_start_overlay_only_rebinds_legacy_nats_listeners(tmp_path: Path):
    run = _run(tmp_path)
    source = (
        tmp_path
        / "run"
        / "baseline"
        / "pocket-lab-final-structure"
        / "pocket-lab-bootstrap-production-scripts-patched"
        / "scripts"
        / "start-dashboard.sh"
    )
    source.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    candidate_common = (
        tmp_path
        / "run"
        / "candidate"
        / "pocket-lab-final-structure"
        / "pocket-lab-bootstrap-production-scripts-patched"
        / "scripts"
        / "lib"
        / "common.sh"
    )
    candidate_common.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    candidate_common.write_text("# candidate qualification common\n", encoding="utf-8")
    source.write_text(
        "#!/usr/bin/env bash\nsource \"$SCRIPT_DIR/lib/common.sh\"\ncat <<EOF\nlisten: 0.0.0.0:4222\nhttp: 127.0.0.1:8222\ncurl http://127.0.0.1:8222/healthz\nEOF\n",
        encoding="utf-8",
    )
    source.chmod(0o700)
    overlay = controller._baseline_start_script(run)
    assert overlay != source
    rendered = overlay.read_text(encoding="utf-8")
    assert "${POCKETLAB_LITE_NATS_PORT:-4222}" in rendered
    assert "${POCKETLAB_LITE_NATS_MONITOR_PORT:-8222}" in rendered
    assert "${POCKETLAB_LITE_NATS_MONITOR_PORT:-8222}/healthz" in rendered
    assert "listen: 0.0.0.0:4222" not in rendered
    assert 'source "$SCRIPT_DIR/lib/.qualification-common.sh"' in rendered
    assert (overlay.parent / "lib" / ".qualification-common.sh").read_text(encoding="utf-8") == "# candidate qualification common\n"


def test_package_inputs_bind_to_the_sealed_exact_sha(tmp_path: Path):
    run = _run(tmp_path)
    source_sha = run["baseline_sha"]
    package_root = tmp_path / "run" / "baseline-package" / "backend-artifact"
    package_root.mkdir(mode=0o700, parents=True)
    prefix = package_root / f"pocketlab-lite-backend-{source_sha}"
    for suffix in (".zip", ".manifest.json", ".checksums.txt"):
        (Path(str(prefix) + suffix)).write_text("sealed", encoding="utf-8")
    run["package"] = {"baseline": {"artifact": {"source_commit": source_sha}}}

    resolved = controller._package_inputs(run, "baseline", source_sha)

    assert resolved["verified"]["source_commit"] == source_sha
    assert set(resolved["prepared"]) == {"artifact", "manifest", "checksums"}
    assert all(Path(path).is_file() for path in resolved["prepared"].values())


def test_start_records_identity_anchors_before_owner_checkpoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    run = _run(tmp_path, phase="prepared")
    root = tmp_path / "run"
    source_sha = run["baseline_sha"]
    package_root = root / "baseline-package" / "backend-artifact"
    package_root.mkdir(mode=0o700, parents=True)
    prefix = package_root / f"pocketlab-lite-backend-{source_sha}"
    for suffix in (".zip", ".manifest.json", ".checksums.txt"):
        (Path(str(prefix) + suffix)).write_text("sealed", encoding="utf-8")
    run["package"] = {"baseline": {"artifact": {"source_commit": source_sha}}}
    identity_module = root / "baseline" / "pocket-lab-final-structure" / "runtime" / "api_fastapi" / "services" / "lite_runtime_identity.py"
    identity_module.parent.mkdir(mode=0o700, parents=True)
    identity_module.write_text("# identity contract", encoding="utf-8")
    for relative in ("home", "base/pwa/current", "state", "runtime"):
        (root / relative).mkdir(mode=0o700, parents=True, exist_ok=True)
    events: list[str] = []

    class FakeRunner:
        SERVICE_NAMES = ["pocket-api"]

        def _assert_isolated_environment(self, env, run_root):
            events.append("assert-isolated")

        def _install_backend_baseline(self, package, env, *, commit, run_id):
            events.append("install-backend")
            assert package["verified"]["source_commit"] == commit
            return {"status": "PASS", "source_commit": commit, "sanitized": True}

        def _seed_policy_baseline(self, env, *, run_id):
            events.append("seed-policy")
            return {"status": "PASS", "revision": "qualification-policy", "sanitized": True}

        def _observe(self, env, expected):
            events.append("observe")
            return {"all_required_online": True, "sanitized": True}

        def _http_json(self, url):
            events.append(url.rsplit("/", 1)[-1])
            if url.endswith("/api/lite/runtime"):
                return 200, {"stable": True}
            return 200, {}

        def _identity_projection(self, env):
            events.append("identity")
            return {"status": "stable", "sanitized": True}

    monkeypatch.setattr(controller, "_runner", lambda: FakeRunner())
    monkeypatch.setattr(controller, "_base_env", lambda value: {
        "HOME": str(root / "home"),
        "POCKETLAB_COORDINATED_API_URL": "http://127.0.0.1:1",
    })
    monkeypatch.setattr(controller, "_baseline_start_script", lambda value: root / "baseline-start.sh")
    monkeypatch.setattr(controller, "_run", lambda *args, **kwargs: type("Result", (), {"returncode": 0})())

    updated = controller._start(run)

    assert updated["phase"] == "awaiting_owner"
    assert updated["status"] == "AWAITING_OPERATOR"
    assert updated["baseline_identity"]["installed_artifact"]["status"] == "PASS"
    assert updated["baseline_identity"]["policy"]["revision"] == "qualification-policy"
    assert events.index("install-backend") < events.index("seed-policy") < events.index("observe")
    assert controller._read_manifest(root / controller.MANIFEST_NAME)["phase"] == "awaiting_owner"
