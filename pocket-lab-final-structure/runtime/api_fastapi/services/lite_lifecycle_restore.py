"""Reconcile trust fences in the isolated staged restore before promotion.

The live checkpoint is authoritative for local trust configuration and floor.
Restoring a backup never revives standing consent or a prepared clock receipt.
Rollback of a failed restore retains the existing checkpoint contract.
"""
import sqlite3
from datetime import datetime, timezone

TABLES = ("lite_release_trust_configuration","lite_release_trust_floor",
          "lite_release_trust_pin","lite_release_trusted_time")

def fence_staged_restore(staged, checkpoint):
    with sqlite3.connect(staged) as db, sqlite3.connect(checkpoint.as_uri() + "?mode=ro", uri=True) as old:
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("BEGIN IMMEDIATE")
        names = {r[0] for r in old.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        stamp = datetime.now(timezone.utc).isoformat()
        for table in TABLES:
            if table not in names:
                continue
            row = old.execute(f"SELECT * FROM {table} WHERE singleton_id=1").fetchone()
            if row:
                # Preserve the local configuration and high-water, not the
                # backup's historical authority. A greater backup floor is
                # ambiguous and requires a separately reviewed recovery.
                existing = db.execute(f"SELECT * FROM {table} WHERE singleton_id=1").fetchone()
                if table == "lite_release_trust_floor" and existing and (existing[1] > row[1] or existing[2] > row[2]):
                    raise ValueError("restore_trust_floor_conflict")
                db.execute(f"DELETE FROM {table}")
                db.execute(f"INSERT INTO {table} VALUES ({','.join('?' for _ in row)})", row)
        db.execute("UPDATE lite_release_trust_configuration SET state='suspended',revision=revision+1")
        db.execute("DELETE FROM lite_release_trust_observation")
        db.execute("UPDATE lite_lifecycle_grants SET revoked_at=COALESCE(revoked_at,?)", (stamp,))
        db.execute("DELETE FROM lite_lifecycle_boundary_scopes")
        db.execute("UPDATE lite_lifecycle_workspace SET authority_epoch=authority_epoch+1,boundary_revision=boundary_revision+1,delegation_revision=delegation_revision+1")
        db.execute("INSERT INTO lite_release_trust_transitions(state,reason_code,occurred_at,release_tag) VALUES('suspended','database_restore_review_required',?,'')", (stamp,))
        db.commit()
