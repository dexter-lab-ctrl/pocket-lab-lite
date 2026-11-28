"""Source-only qualification fixtures for the exact isolated release grant."""
import copy
import hashlib

import pytest
from pocket_lab_test_utils import ensure_runtime_path

ensure_runtime_path()
from api_fastapi.services import lite_lifecycle_release_execution as execution
from api_fastapi.services.lite_lifecycle_contract import (
    canonical_bytes, digest, execution_capability_binding, registry_revision,
)


@pytest.fixture
def receipt():
    return {
        "source_package":{"state":"verified_for_review","sha256":"a"*64},
        "provenance":"verified","authenticity":"verified","integrity":"verified",
        "schema_range_matches":True,"registry_revision":registry_revision(),
        "capability_review":{"total":0},
        "migration_review":{"state":"unchanged","applied_ledger":{"state":"ledger_matches"},"target_schema":66},
        "coordinated_preflight":{"state":"isolated_preflight_checked",
                                 "migration_execution":{"state":"synthetic_schema_rehearsed"}},
        "policy_review":{"state":"source_unchanged"},
        "policy_runtime_observation":{"state":"modules_match","manifest_data_identity":"registered_roots_match",
                                      "data_identity":"registered_template_matches","observed_revision":"policy-v1"},
        "metadata_sha256":"b"*64,"artifact_sha256":"c"*64,"policy_sha256":"d"*64,
        "migration_inventory_sha256":"e"*64,"source_commit":"f"*40,
        "release_tag":"lite-2026.11.27.1","current_schema":66,
    }


def test_execution_default_disabled(monkeypatch):
    monkeypatch.delenv("POCKETLAB_RELEASE_COORDINATED_EXECUTION", raising=False)
    assert not execution.gate()


def test_review_path_tolerates_pre_execution_schema_without_grant_rows():
    """A schema-63 baseline may review trust before candidate migrations run."""
    class Transaction:
        def __init__(self):
            self.statements = []

        def execute(self, sql, params=()):
            self.statements.append((sql, params))
            return self

        def fetchone(self):
            return None

    tx = Transaction()
    lease = type("Lease", (), {"generation": 1, "worker_generation": "worker", "command_id": "check"})()
    execution.finish(tx, lease, {})
    assert len(tx.statements) == 1
    with pytest.raises(PermissionError, match="release_preparation_schema_unavailable"):
        execution.current(tx, "1" * 32)


def test_release_and_policy_capabilities_are_independent(receipt):
    scope = execution._scope(receipt,"1"*40)
    assert scope["capability_sha256"] == execution_capability_binding(execution.ACTION)["capability_sha256"]
    assert scope["capability_sha256"] != execution_capability_binding("lifecycle.policy.activate")["capability_sha256"]
    with pytest.raises(PermissionError):
        execution_capability_binding("app.update.check")


@pytest.mark.parametrize("field,value",[
    ("registry_revision","0"*64),("provenance","unknown"),("integrity","unknown"),
    ("capability_review",{"total":1}),("schema_range_matches",False),
    ("migration_review",{"state":"unknown"}),
    ("coordinated_preflight",{"state":"isolated_preflight_checked"}),
    ("policy_runtime_observation",{"state":"modules_match"}),
])
def test_unproved_candidate_cannot_be_prepared(receipt,field,value):
    candidate=copy.deepcopy(receipt)
    candidate[field]=value
    with pytest.raises(PermissionError):
        execution._scope(candidate,"1"*40)


def test_handoff_rejects_tampered_bytes(tmp_path,monkeypatch):
    root=tmp_path/"private"
    root.mkdir(mode=0o700)
    grant="1"*32
    monkeypatch.setattr(execution,"handoff_directory",lambda value:root)
    monkeypatch.setattr(execution,"_asset_limits",lambda:{"dist.zip":128})
    raw=b"authenticated fixture"
    asset=root/"dist.zip"
    asset.write_bytes(raw)
    asset.chmod(0o400)
    doc={"schema_version":1,"grant_id":grant,"assets":[{"name":"dist.zip",
         "sha256":hashlib.sha256(raw).hexdigest(),"size_bytes":len(raw)}]}
    manifest=root/"handoff.json"
    manifest.write_bytes(canonical_bytes(doc))
    manifest.chmod(0o400)
    assert execution.read_handoff(grant,digest(doc))[1]==doc
    asset.chmod(0o600)
    asset.write_bytes(b"tampered")
    asset.chmod(0o400)
    with pytest.raises(PermissionError):
        execution.read_handoff(grant,digest(doc))


def test_external_claim_rejects_unowned_caller(monkeypatch):
    monkeypatch.setenv("POCKETLAB_PROCESS_ROLE","api")
    with pytest.raises(PermissionError):
        execution.claim_cutover("1"*32,"2"*64,"3"*64)


def test_cutover_finalization_is_fenced_by_current_authority(monkeypatch):
    """Exercise the terminal transaction without a live device or real grant."""
    from contextlib import contextmanager

    class Transaction:
        updates = []
        def execute(self, sql, params=()):
            if sql.startswith("SELECT *"):
                return self
            self.updates.append((sql, params))
            return self
        def fetchone(self):
            return {"state": "cutover_claimed", "cutover_authorization_sha256": "3"*64,
                    "owner_id": "fixture-owner", "revoked_at": None}

    tx = Transaction()

    @contextmanager
    def context(*args):
        yield tx

    monkeypatch.setenv("POCKETLAB_PROCESS_ROLE", "coordinated-promotion-controller")
    monkeypatch.setattr(execution, "gate", lambda: True)
    monkeypatch.setattr(execution, "connection", context)
    monkeypatch.setattr(execution, "begin_immediate", context)
    monkeypatch.setattr(execution.authority, "_workspace", lambda conn: {"boundary_revision": 1})
    monkeypatch.setattr(execution.authority, "_audit", lambda *args, **kwargs: None)

    def stale(*args, **kwargs):
        raise PermissionError("release_preparation_binding_changed")

    monkeypatch.setattr(execution, "current", stale)
    assert execution.finish_cutover("1"*32, "3"*64, rehearsed=True) == "failed"
    assert tx.updates[-1][1][0] == "failed"
    monkeypatch.setattr(execution, "current", lambda *args, **kwargs: ({}, {}))
    assert execution.finish_cutover("1"*32, "3"*64, rehearsed=True) == "rehearsed"
    assert tx.updates[-1][1][0] == "rehearsed"


@pytest.mark.parametrize("current,target,state", [
    (True, 66, "unchanged"), (66, 65, "review_required"),
    (66, 67, "unchanged"), (66, 66, "review_required"),
    (66, 513, "review_required"),
])
def test_invalid_schema_scope_cannot_be_prepared(receipt, current, target, state):
    receipt["current_schema"] = current
    receipt["migration_review"].update(target_schema=target, state=state)
    with pytest.raises(PermissionError, match="coordinated_schema_binding_invalid"):
        execution._scope(receipt, "1"*40)
