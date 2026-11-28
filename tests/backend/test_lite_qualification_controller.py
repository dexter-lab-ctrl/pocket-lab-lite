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
