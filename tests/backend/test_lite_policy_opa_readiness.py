from __future__ import annotations

import contextlib
import importlib.util
from pathlib import Path
import sqlite3
import sys


ROOT = Path(__file__).resolve().parents[2]
SUPERVISOR = ROOT / "pocket-lab-final-structure/runtime/supervisors/pocketlab_core_supervisor.py"


def _supervisor_module():
    spec = importlib.util.spec_from_file_location("pocketlab_core_supervisor_opa_readiness", SUPERVISOR)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_wait_for_opa_revision_tolerates_transient_restart(monkeypatch, tmp_path):
    monkeypatch.setenv("POCKETLAB_STATE_DIR", str(tmp_path / "state"))
    module = _supervisor_module()
    supervisor = module.LiteCoreSupervisor()
    expected = "plr-candidate-ready"
    calls = {"health": 0, "revision": 0}

    def fake_fetch(url: str, timeout: float = 4.0):
        assert 0 < timeout <= 1.0
        if url.endswith("/health"):
            calls["health"] += 1
            return None if calls["health"] == 1 else {}
        calls["revision"] += 1
        return {"result": "plr-old-known-good" if calls["revision"] == 1 else expected}

    monkeypatch.setattr(module, "fetch_json", fake_fetch)

    proof = supervisor._wait_for_opa_revision(
        expected,
        timeout_seconds=1.0,
        interval_seconds=0.0,
    )

    assert proof == {
        "proved": True,
        "observed_revision": expected,
        "health_ready": True,
        "attempts": 2,
    }


def test_wait_for_opa_revision_timeout_is_bounded(monkeypatch, tmp_path):
    monkeypatch.setenv("POCKETLAB_STATE_DIR", str(tmp_path / "state"))
    module = _supervisor_module()
    supervisor = module.LiteCoreSupervisor()
    monkeypatch.setattr(
        module,
        "fetch_json",
        lambda url, timeout=4.0: {} if url.endswith("/health") else {"result": "plr-stale-revision"},
    )

    proof = supervisor._wait_for_opa_revision(
        "plr-expected-revision",
        timeout_seconds=0.0,
        interval_seconds=0.0,
    )

    assert proof["proved"] is False
    assert proof["health_ready"] is True
    assert proof["observed_revision"] == "plr-stale-revision"
    assert proof["attempts"] == 1


def test_reconcile_uses_bounded_readiness_helper_for_candidate():
    module = _supervisor_module()
    source = __import__("inspect").getsource(module.LiteCoreSupervisor.reconcile_policy_activation)
    assert "_wait_for_opa_revision(op[\"candidate_revision_id\"])" in source
    assert 'fetch_json("http://127.0.0.1:8181/health")' not in source


def test_rollback_waits_for_known_good_and_repairs_runtime_state(monkeypatch, tmp_path):
    monkeypatch.setenv("POCKETLAB_STATE_DIR", str(tmp_path / "state"))
    module = _supervisor_module()
    supervisor = module.LiteCoreSupervisor()
    old_revision = "plr-old-known-good"
    waits: list[str] = []
    repairs: list[tuple[str, str]] = []
    updates: list[tuple[tuple[object, ...], dict[str, object]]] = []

    monkeypatch.setattr(supervisor, "_stage_is_valid", lambda revision: revision == old_revision)
    monkeypatch.setattr(
        supervisor,
        "_prepare_policy",
        lambda action, revision, template_json="": action == "activate" and revision == old_revision,
    )
    monkeypatch.setattr(supervisor, "restart_pm2", lambda *_args, **_kwargs: {"acted": True})
    monkeypatch.setattr(
        supervisor,
        "_wait_for_opa_revision",
        lambda revision: waits.append(revision) or {
            "proved": True,
            "observed_revision": revision,
            "health_ready": True,
            "attempts": 2,
        },
    )
    monkeypatch.setattr(
        supervisor,
        "_restore_policy_runtime_state_after_rollback",
        lambda op, revision: repairs.append((op["operation_id"], revision)) or True,
    )
    monkeypatch.setattr(supervisor, "_set_policy_operation", lambda *args, **kwargs: updates.append((args, kwargs)))
    monkeypatch.setattr(supervisor, "_append_event", lambda *_args, **_kwargs: None)

    result = supervisor._rollback_policy(
        {
            "operation_id": "plo-readiness-race",
            "candidate_revision_id": "plr-candidate",
            "prior_known_good_revision_id": old_revision,
        },
        "opa_revision_mismatch",
        observed="plr-candidate",
    )

    assert result["event"] == "policy_activation_rolled_back"
    assert waits == [old_revision]
    assert repairs == [("plo-readiness-race", old_revision)]
    assert updates[-1][0][1] == "rolled_back"
    assert updates[-1][1]["opa"] == old_revision
    assert updates[-1][1]["evidence"] == "policy:rollback-proved"


def test_rollback_state_repair_failure_remains_uncertain(monkeypatch, tmp_path):
    monkeypatch.setenv("POCKETLAB_STATE_DIR", str(tmp_path / "state"))
    module = _supervisor_module()
    supervisor = module.LiteCoreSupervisor()
    old_revision = "plr-old-known-good"
    updates: list[tuple[tuple[object, ...], dict[str, object]]] = []

    monkeypatch.setattr(supervisor, "_stage_is_valid", lambda _revision: True)
    monkeypatch.setattr(supervisor, "_prepare_policy", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(supervisor, "restart_pm2", lambda *_args, **_kwargs: {"acted": True})
    monkeypatch.setattr(
        supervisor,
        "_wait_for_opa_revision",
        lambda revision: {
            "proved": True,
            "observed_revision": revision,
            "health_ready": True,
            "attempts": 1,
        },
    )
    monkeypatch.setattr(supervisor, "_restore_policy_runtime_state_after_rollback", lambda *_args: False)
    monkeypatch.setattr(supervisor, "_set_policy_operation", lambda *args, **kwargs: updates.append((args, kwargs)))
    monkeypatch.setattr(supervisor, "_append_event", lambda *_args, **_kwargs: None)

    result = supervisor._rollback_policy(
        {
            "operation_id": "plo-state-repair-failed",
            "candidate_revision_id": "plr-candidate",
            "prior_known_good_revision_id": old_revision,
        },
        "known_good_pointer_failed",
    )

    assert result == {
        "event": "policy_activation_uncertain",
        "reason": "rollback_unproved",
        "acted": False,
    }
    assert updates[-1][0][1] == "uncertain"
    assert updates[-1][1]["reason"] == "rollback_unproved"


def _sqlite_runtime_modules(db: sqlite3.Connection):
    @contextlib.contextmanager
    def connection():
        yield db

    @contextlib.contextmanager
    def begin_immediate(conn):
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield conn
        except Exception:
            conn.rollback()
            raise
        else:
            conn.commit()

    return begin_immediate, connection, None


def _runtime_db() -> sqlite3.Connection:
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript(
        """
        CREATE TABLE policy_revisions (
            revision_id TEXT PRIMARY KEY,
            lifecycle_status TEXT NOT NULL,
            activated_at TEXT
        );
        CREATE TABLE policy_runtime_state (
            state_id INTEGER PRIMARY KEY,
            active_revision_id TEXT,
            known_good_revision_id TEXT,
            updated_at TEXT NOT NULL,
            updated_by_operation_id TEXT
        );
        """
    )
    return db


def test_state_repair_restores_database_known_good(monkeypatch, tmp_path):
    monkeypatch.setenv("POCKETLAB_STATE_DIR", str(tmp_path / "state"))
    module = _supervisor_module()
    supervisor = module.LiteCoreSupervisor()
    db = _runtime_db()
    db.execute("INSERT INTO policy_revisions VALUES ('plr-old','superseded','2026-08-22T16:00:00Z')")
    db.execute("INSERT INTO policy_revisions VALUES ('plr-candidate','active','2026-08-22T17:00:00Z')")
    db.execute("INSERT INTO policy_runtime_state VALUES (1,'plr-candidate','plr-candidate','2026-08-22T17:00:00Z','plo-one')")
    db.commit()
    monkeypatch.setattr(supervisor, "_policy_runtime_modules", lambda: _sqlite_runtime_modules(db))

    assert supervisor._restore_policy_runtime_state_after_rollback(
        {"operation_id": "plo-one", "candidate_revision_id": "plr-candidate"},
        "plr-old",
    ) is True

    runtime = db.execute("SELECT * FROM policy_runtime_state WHERE state_id=1").fetchone()
    assert runtime["active_revision_id"] == "plr-old"
    assert runtime["known_good_revision_id"] == "plr-old"
    assert runtime["updated_by_operation_id"] == "plo-one"
    candidate = db.execute("SELECT * FROM policy_revisions WHERE revision_id='plr-candidate'").fetchone()
    old = db.execute("SELECT * FROM policy_revisions WHERE revision_id='plr-old'").fetchone()
    assert candidate["lifecycle_status"] == "validated"
    assert candidate["activated_at"] is None
    assert old["lifecycle_status"] == "active"


def test_state_repair_removes_bootstrap_runtime_row_when_known_good_predates_db(monkeypatch, tmp_path):
    monkeypatch.setenv("POCKETLAB_STATE_DIR", str(tmp_path / "state"))
    module = _supervisor_module()
    supervisor = module.LiteCoreSupervisor()
    db = _runtime_db()
    db.execute("INSERT INTO policy_revisions VALUES ('plr-candidate','active','2026-08-22T17:00:00Z')")
    db.execute("INSERT INTO policy_runtime_state VALUES (1,'plr-candidate','plr-candidate','2026-08-22T17:00:00Z','plo-bootstrap')")
    db.commit()
    monkeypatch.setattr(supervisor, "_policy_runtime_modules", lambda: _sqlite_runtime_modules(db))

    assert supervisor._restore_policy_runtime_state_after_rollback(
        {"operation_id": "plo-bootstrap", "candidate_revision_id": "plr-candidate"},
        "plr-pre-lifecycle-known-good",
    ) is True

    assert db.execute("SELECT * FROM policy_runtime_state WHERE state_id=1").fetchone() is None
    candidate = db.execute("SELECT * FROM policy_revisions WHERE revision_id='plr-candidate'").fetchone()
    assert candidate["lifecycle_status"] == "validated"
    assert candidate["activated_at"] is None
