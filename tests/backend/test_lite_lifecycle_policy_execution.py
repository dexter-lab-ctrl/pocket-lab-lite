"""Source-authored qualification fixtures; never contacts a production runtime."""
import base64
import hashlib
import sqlite3
import pytest
from pocket_lab_test_utils import ensure_runtime_path

ensure_runtime_path()
from api_fastapi.services import lite_lifecycle_policy_execution as execution
from api_fastapi.services import lite_release_migration_rehearsal as rehearsal
from api_fastapi.services.lite_lifecycle_contract import digest
from api_fastapi.services.lite_policy_compatibility import REGISTERED_MODULES


def test_execution_requires_complete_isolated_context(monkeypatch):
    monkeypatch.delenv("POCKETLAB_RELEASE_POLICY_EXECUTION", raising=False)
    assert execution.gate() is False
    monkeypatch.setenv("POCKETLAB_RELEASE_POLICY_EXECUTION", "1")
    monkeypatch.setenv("POCKETLAB_ENVIRONMENT", "qualification")
    monkeypatch.delenv("POCKETLAB_QUALIFICATION_CONTEXT", raising=False)
    assert execution.gate() is False


def test_exact_note_scope_cannot_change_policy_logic(monkeypatch):
    before = {name: b"package test\n" for name in REGISTERED_MODULES}
    tree = {name.rsplit("/",1)[-1]: data.decode() for name,data in before.items()}
    tree.update({"template.json": "{}\n", "revision.rego": "package meta\n"})
    monkeypatch.setattr(execution.lifecycle, "policy_source_tree", lambda *_: ("plr-old", tree.copy()))
    key = sorted(before)[0]
    note = b"# pocketlab-release-note: synthetic fixture\n"
    after = dict(before)
    after[key] += note
    expected = digest([{"path": name, "sha256": hashlib.sha256(raw).hexdigest()} for name,raw in sorted(after.items())])
    scope = {key.rsplit("/",1)[-1]: base64.b64encode(note).decode()}
    template = {"template_id":"test", "template_version":"1", "parameters":{}}
    _, candidate, _, _, _ = execution._render(template, scope, expected)
    assert candidate.startswith("plr-")
    with pytest.raises(ValueError):
        execution._render(template, scope, "0"*64)
    scope[key.rsplit("/",1)[-1]] = base64.b64encode(b"allow := true\n").decode()
    with pytest.raises(ValueError):
        execution._render(template, scope, expected)


@pytest.mark.parametrize("sql", ["ATTACH DATABASE ':memory:' AS extra", "PRAGMA writable_schema=ON",
    "SELECT load_extension('x')", "DELETE FROM schema_migrations", "CREATE VIRTUAL TABLE test USING fts5(body)"])
def test_synthetic_migration_rehearsal_denies_unsafe_sql(sql):
    with sqlite3.connect(":memory:") as db:
        db.execute("CREATE TABLE schema_migrations(version INTEGER)")
        db.set_authorizer(rehearsal._authorizer)
        with pytest.raises(sqlite3.DatabaseError):
            db.execute(sql)


def test_restrictive_candidate_is_exact_local_transformation():
    from api_fastapi.services import lite_policy_candidate_differential as diff
    before = {name: b"package test\n" for name in REGISTERED_MODULES}
    before[diff.MAIN_MODULE] += diff._RESTRICT_BEFORE + b"}\n"
    after = diff.restrictive_candidate(before, diff.RESTRICTIVE_EDIT)
    assert diff.locally_supported_evolution(before, after) == "locally_supported_restrictive_evolution"
    after[diff.MAIN_MODULE] += b"allow := true\n"
    assert diff.locally_supported_evolution(before, after) == "unknown_semantic_impact"


def test_restrictive_comparison_never_accepts_expansion_or_changed_allow():
    from api_fastapi.services import lite_policy_candidate_differential as diff
    cases = {"owner": {"action":{"id":diff.RESTRICTIVE_ACTION}, "actor":{"role":"Owner"}},
             "viewer": {"action":{"id":diff.RESTRICTIVE_ACTION}, "actor":{"role":"Viewer"}}}
    allow = {"allow": True, "constraints":["authenticated_actor"], "reason_code":"allowed"}
    deny = {"allow": False, "constraints":[], "reason_code":"denied"}
    old = {"owner":allow, "viewer":allow}
    new = {"owner":allow, "viewer":deny}
    evolution = "locally_supported_restrictive_evolution"
    assert diff.compare_corpus(cases, old, new, evolution)[0] == "sample_restrictive"
    assert diff.compare_corpus(cases, new, old, evolution)[0] == "differences_observed"
    assert diff.compare_corpus(cases, old, {**new,"owner":{**allow,"constraints":[]}}, evolution)[0] == "differences_observed"
