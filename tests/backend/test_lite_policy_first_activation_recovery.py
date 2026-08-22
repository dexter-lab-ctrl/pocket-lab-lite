from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SUPERVISOR = ROOT / "pocket-lab-final-structure/runtime/supervisors/pocketlab_core_supervisor.py"


def _supervisor_module():
    spec = importlib.util.spec_from_file_location("pocketlab_core_supervisor_bootstrap_recovery", SUPERVISOR)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_valid_stage(state: Path, revision: str) -> Path:
    stage = state / "opa" / "stage" / revision
    stage.mkdir(parents=True)
    (stage / "pocketlab.rego").write_text("package pocketlab\n", encoding="utf-8")
    (stage / "revision.txt").write_text(revision + "\n", encoding="utf-8")
    files = [
        {
            "path": "pocketlab.rego",
            "sha256": hashlib.sha256((stage / "pocketlab.rego").read_bytes()).hexdigest(),
        }
    ]
    candidate_hash = hashlib.sha256(
        json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    (stage / "manifest.json").write_text(
        json.dumps(
            {"revision": revision, "candidate_hash": candidate_hash, "files": files},
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    return stage


def test_filesystem_known_good_requires_valid_staged_symlink(tmp_path, monkeypatch):
    state = tmp_path / "state"
    monkeypatch.setenv("POCKETLAB_STATE_DIR", str(state))
    module = _supervisor_module()
    supervisor = module.LiteCoreSupervisor()

    revision = "plr-bootstrap-known-good"
    stage = _write_valid_stage(state, revision)
    pointer = state / "opa" / "known-good"
    pointer.symlink_to(stage)

    assert supervisor._filesystem_known_good_revision() == revision

    (stage / "pocketlab.rego").write_text("package tampered\n", encoding="utf-8")
    assert supervisor._filesystem_known_good_revision() == ""


def test_first_activation_rollback_uses_filesystem_known_good(tmp_path, monkeypatch):
    state = tmp_path / "state"
    monkeypatch.setenv("POCKETLAB_STATE_DIR", str(state))
    module = _supervisor_module()
    supervisor = module.LiteCoreSupervisor()

    old_revision = "plr-bootstrap-known-good"
    updates: list[tuple[tuple[object, ...], dict[str, object]]] = []

    monkeypatch.setattr(supervisor, "_filesystem_known_good_revision", lambda: old_revision)
    monkeypatch.setattr(supervisor, "_stage_is_valid", lambda revision: revision == old_revision)
    monkeypatch.setattr(supervisor, "_prepare_policy", lambda action, revision, template_json="": action == "activate" and revision == old_revision)
    monkeypatch.setattr(supervisor, "restart_pm2", lambda *_args, **_kwargs: {"acted": True})
    monkeypatch.setattr(supervisor, "_set_policy_operation", lambda *args, **kwargs: updates.append((args, kwargs)))
    monkeypatch.setattr(supervisor, "_append_event", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        module,
        "fetch_json",
        lambda url, **_kwargs: {} if url.endswith("/health") else {"result": old_revision},
    )

    result = supervisor._rollback_policy(
        {"operation_id": "plo-first", "prior_known_good_revision_id": None},
        "opa_restart_failed",
    )

    assert result == {
        "event": "policy_activation_rolled_back",
        "operation_id": "plo-first",
        "reason": "opa_restart_failed",
        "acted": True,
    }
    terminal = updates[-1]
    assert terminal[0][1] == "rolled_back"
    assert terminal[1]["filesystem"] == old_revision
    assert terminal[1]["opa"] == old_revision
    assert terminal[1]["evidence"] == "policy:rollback-proved:filesystem-known-good"


def test_uncertain_operation_is_quarantined_from_normal_reconciliation(tmp_path, monkeypatch):
    state = tmp_path / "state"
    monkeypatch.setenv("POCKETLAB_STATE_DIR", str(state))
    module = _supervisor_module()
    supervisor = module.LiteCoreSupervisor()
    queries: list[str] = []

    class FakeConnection:
        def execute(self, sql: str, _params=()):
            queries.append(sql)
            return self

        def fetchone(self):
            return None

    @contextlib.contextmanager
    def connection():
        yield FakeConnection()

    @contextlib.contextmanager
    def lock():
        yield True

    monkeypatch.setattr(supervisor, "_policy_runtime_modules", lambda: (None, connection, None))
    monkeypatch.setattr(supervisor, "_activation_lock", lock)

    assert supervisor.reconcile_policy_activation() is None
    assert queries
    assert "uncertain" not in queries[0]
    assert "rolling_back" in queries[0]
