"""Server-owned per-human durable history read position. No browser secrets or event copies."""
from __future__ import annotations
from datetime import datetime, timezone
import sqlite3
from ..db.connection import connection, begin_immediate
from ..db.migrations import apply_migrations

def read_cursor(human_id: str) -> dict:
    if not isinstance(human_id,str) or not human_id.strip():
        raise ValueError("Authenticated human identity required.")
    try:
        with connection() as conn:
            row=conn.execute("SELECT history_revision,last_reviewed_at FROM lite_home_activity_read_cursors WHERE human_id=?", (human_id,)).fetchone()
    except sqlite3.OperationalError as exc:
        if 'no such table' not in str(exc).lower():
            raise
        row=None
    return {"history_revision":int(row["history_revision"]),"last_reviewed_at":row["last_reviewed_at"]} if row else {"history_revision":0,"last_reviewed_at":None}

def mark_reviewed(human_id: str, revision: int) -> dict:
    if not isinstance(human_id,str) or not human_id.strip():
        raise ValueError("Authenticated human identity required.")
    if type(revision) is not int or revision < 0:
        raise ValueError("Invalid history revision.")
    apply_migrations()
    now=datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
    with connection() as conn:
        with begin_immediate(conn) as tx:
            tx.execute("""INSERT INTO lite_home_activity_read_cursors(human_id,history_revision,last_reviewed_at) VALUES (?,?,?)
                ON CONFLICT(human_id) DO UPDATE SET history_revision=MAX(history_revision,excluded.history_revision),
                last_reviewed_at=CASE WHEN excluded.history_revision>=history_revision THEN excluded.last_reviewed_at ELSE last_reviewed_at END""",
                (human_id,revision,now))
    return read_cursor(human_id)
