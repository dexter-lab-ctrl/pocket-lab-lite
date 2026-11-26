"""Reconcile trust fences in the isolated staged restore before promotion.

The live checkpoint is authoritative for local trust configuration and floor.
Restoring a backup never revives standing consent or a prepared clock receipt.
Rollback of a failed restore retains the existing checkpoint contract.
"""
import sqlite3
from contextlib import closing
from datetime import datetime, timezone

TABLES = ("lite_release_trust_configuration","lite_release_trust_floor",
          "lite_release_trust_pin","lite_release_trusted_time")

def fence_staged_restore(staged, checkpoint):
    with closing(sqlite3.connect(staged)) as db, closing(sqlite3.connect(checkpoint.resolve().as_uri() + "?mode=ro", uri=True)) as old:
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
                if table == "lite_release_trust_floor" and existing and (existing[1] > row[1] or existing[2] > row[2]
                        or (existing[1] == row[1] and existing[3:] != row[3:])):
                    raise ValueError("restore_trust_floor_conflict")
                if table == "lite_release_trusted_time" and existing and datetime.fromisoformat(existing[1]) > datetime.fromisoformat(row[1]):
                    raise ValueError("restore_trusted_time_conflict")
                db.execute(f"DELETE FROM {table}")
                db.execute(f"INSERT INTO {table} VALUES ({','.join('?' for _ in row)})", row)
        db.execute("UPDATE lite_release_trust_configuration SET state='suspended',revision=revision+1")
        db.execute("DELETE FROM lite_release_trust_observation")
        db.execute("UPDATE lite_lifecycle_grants SET revoked_at=COALESCE(revoked_at,?)", (stamp,))
        # The complete runtime schema includes ``human_identities``, which is
        # the parent of the boundary-scope owner foreign key.  Isolated
        # lifecycle restore fixtures intentionally contain only migrations
        # 0056-0063, so SQLite cannot resolve that parent while deleting from
        # the child table even when it is empty.  Keep the production FK
        # enforcement enabled: skip only an empty child table in a deliberately
        # partial fixture, and fail closed if scoped authority would otherwise
        # survive without its identity store.
        staged_tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "lite_lifecycle_boundary_scopes" in staged_tables:
            if "human_identities" in staged_tables:
                db.execute("DELETE FROM lite_lifecycle_boundary_scopes")
            elif db.execute("SELECT 1 FROM lite_lifecycle_boundary_scopes LIMIT 1").fetchone():
                raise ValueError("restore_identity_store_missing")
        live_epochs = (0, 0, 0)
        if "lite_lifecycle_workspace" in names:
            columns = {r[1] for r in old.execute("PRAGMA table_info(lite_lifecycle_workspace)")}
            live_epochs = tuple(old.execute(
                "SELECT " + ",".join(c if c in columns else "0" for c in
                                    ("authority_epoch","boundary_revision","delegation_revision")) +
                " FROM lite_lifecycle_workspace").fetchone() or live_epochs)
        db.execute("""UPDATE lite_lifecycle_workspace SET
            authority_epoch=MAX(authority_epoch,?)+1,
            boundary_revision=MAX(boundary_revision,?)+1,
            delegation_revision=MAX(delegation_revision,?)+1""", live_epochs)
        db.execute("INSERT INTO lite_release_trust_transitions(state,reason_code,occurred_at,release_tag) VALUES('suspended','database_restore_review_required',?,'')", (stamp,))
        db.commit()
        # Promotion copies the database file, not its WAL sidecars.
        checkpoint_result = db.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        if checkpoint_result and checkpoint_result[0]:
            raise RuntimeError("restore_lifecycle_checkpoint_busy")
