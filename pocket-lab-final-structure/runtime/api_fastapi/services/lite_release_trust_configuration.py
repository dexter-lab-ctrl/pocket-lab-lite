"""Prepared trust configuration and same-boot trusted time.

Configuration is an explicit local operator input, never candidate supplied.
A latch is not a verified root. Removing configuration suspends, not disables.
No filesystem or network I/O occurs on the prepared read path.
"""
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import re
import time

def _boot():
    try:
        return Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    except OSError:
        return ""

BOOT_ID = _boot()

def boot_time_ns():
    # CLOCK_BOOTTIME includes suspend; monotonic alone may stop during sleep.
    try:
        return time.clock_gettime_ns(time.CLOCK_BOOTTIME)
    except (AttributeError, OSError, ValueError):
        return None

def configured():
    return (os.environ.get("POCKETLAB_RELEASE_ROOT_SHA256", ""),
            os.environ.get("POCKETLAB_RELEASE_ATTESTATION_ROOT_SHA256", ""))

def configuration(conn):
    return conn.execute("SELECT * FROM lite_release_trust_configuration WHERE singleton_id=1").fetchone()

def reconcile_configuration(tx):
    old = configuration(tx)
    root, attestation = configured()
    if not old and not root and not attestation:
        return
    valid = all(re.fullmatch(r"[0-9a-f]{64}", value) for value in (root, attestation))
    state = "configured" if valid and os.environ.get("POCKETLAB_RELEASE_TRUST_SUSPENDED") != "1" else "suspended"
    # Before the first accepted candidate, changing the independently
    # approved initial root is not an implicit bootstrap reset.
    if old and old["root_sha256"] and root != old["root_sha256"]:
        accepted = tx.execute("SELECT root_sha256 FROM lite_release_trust_pin WHERE singleton_id=1").fetchone()
        if not accepted:
            valid, state = False, "suspended"
    values = (root if valid else (old["root_sha256"] if old else ""),
              attestation if valid else (old["attestation_root_sha256"] if old else ""), state)
    if old and tuple(old[k] for k in ("root_sha256","attestation_root_sha256","state")) == values:
        return
    tx.execute("""INSERT INTO lite_release_trust_configuration VALUES(1,?,?,?,?)
        ON CONFLICT(singleton_id) DO UPDATE SET root_sha256=excluded.root_sha256,
        attestation_root_sha256=excluded.attestation_root_sha256,state=excluded.state,revision=excluded.revision""",
        (*values, old["revision"] + 1 if old else 1))
    from .lite_control_plane_store import _bump_revision
    stamp = datetime.now(timezone.utc).isoformat()
    tx.execute("INSERT INTO lite_release_trust_transitions(state,reason_code,occurred_at,release_tag) VALUES(?,?,?,'')",
               (state, "operator_configuration_changed", stamp))
    tx.execute("DELETE FROM lite_release_trust_transitions WHERE event_id NOT IN (SELECT event_id FROM lite_release_trust_transitions ORDER BY event_id DESC LIMIT 200)")
    _bump_revision(tx, "audit", stamp, changed_ids=["trusted-lifecycle"], reason="audit_state_changed")

def latched(conn):
    return configuration(conn) is not None or bool(any(configured()))

def current_configuration(conn, receipt):
    row = configuration(conn)
    return bool(row and row["state"] == "configured"
        and os.environ.get("POCKETLAB_RELEASE_TRUST_SUSPENDED") != "1"
        and configured() == (row["root_sha256"], row["attestation_root_sha256"])
        and receipt.get("configuration_revision") == row["revision"]
        and receipt.get("root_sha256") == row["root_sha256"]
        and receipt.get("attestation_root_sha256") == row["attestation_root_sha256"])

def prepared_now(conn, receipt):
    """No wall-clock fallback. Same boot, bounded anchor, durable high-water."""
    if not current_configuration(conn, receipt) or not BOOT_ID or receipt.get("clock_boot_id") != BOOT_ID:
        return None
    try:
        sample = boot_time_ns()
        if sample is None or receipt.get("clock_basis") != "boottime":
            return None
        elapsed = sample - int(receipt["clock_sample_ns"])
        if elapsed < 0 or elapsed > int(receipt["clock_remaining_ns"]):
            return None
        now = datetime.fromisoformat(receipt["checked_at"]) + timedelta(microseconds=elapsed // 1000)
        row = conn.execute("SELECT trusted_at FROM lite_release_trusted_time WHERE singleton_id=1").fetchone()
        if row and now < datetime.fromisoformat(row["trusted_at"]):
            return None
        return now
    except (ValueError, TypeError, KeyError, OverflowError):
        return None

def future(value, now):
    try:
        return now is not None and datetime.fromisoformat(value.replace("Z","+00:00")) > now
    except (ValueError, TypeError, AttributeError):
        return False
