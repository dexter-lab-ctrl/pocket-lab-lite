"""Bounded fixed-cadence availability samples from prepared evidence only.

A missing worker tick is missing coverage. The sample is not continuous uptime.
No sampling is done from a GET and no historical samples are synthesized.
"""
from __future__ import annotations
from datetime import datetime, timezone
import time
from ..db.connection import connection, begin_immediate
from . import lite_system_health as health

SERVICES = ("api","nats","worker","gateway","policy","agent","monitoring","supervisor")
BUCKET_SECONDS = 60
WINDOW = 24 * 60


def capture() -> None:
    from . import lite_infrastructure_read_model as model
    bucket = int(time.time()) // BUCKET_SECONDS
    if health._read("SELECT 1 FROM lite_system_health_availability_samples WHERE bucket=? LIMIT 1",(bucket,)):
        return
    rows = {item["id"]:item for item in model._services(model._snapshots())}
    samples = []
    for service in SERVICES:
        row = rows.get(service,{})
        status = row.get("status")
        state = ("healthy" if status in health.HEALTHY else "unhealthy" if status in health.UNHEALTHY else "unknown") if row.get("freshness")=="current" else "unknown"
        samples.append((bucket,service,state))
    with connection() as conn:
        with begin_immediate(conn):
            conn.executemany("INSERT OR IGNORE INTO lite_system_health_availability_samples VALUES(?,?,?)",samples)
            conn.execute("DELETE FROM lite_system_health_availability_samples WHERE bucket<?",(bucket-WINDOW,))


def statistics() -> dict:
    # Exclude the current incomplete minute; all eight fixed services have
    # the same denominator. Never count unknown or missing samples as healthy.
    end = int(time.time()) // BUCKET_SECONDS
    rows = health._read("""SELECT service_id,state,COUNT(*) AS n FROM lite_system_health_availability_samples
        WHERE bucket>=? AND bucket<? GROUP BY service_id,state""",(end-WINDOW,end))
    per_service = {key:{"healthy":0,"unhealthy":0,"unknown":0} for key in SERVICES}
    for row in rows:
        if row["service_id"] in per_service and row["state"] in per_service[row["service_id"]]:
            per_service[row["service_id"]][row["state"]] = min(WINDOW,int(row["n"]))
    known = healthy = 0
    result = []
    for key, counts in per_service.items():
        observed = counts["healthy"] + counts["unhealthy"]
        known += observed
        healthy += counts["healthy"]
        result.append({"service_id":key,"observed_samples":observed,
            "coverage":round(observed/WINDOW,4),
            "sampled_availability":round(counts["healthy"]/observed,4) if observed else None})
    # Incident timing is generation-specific. Missing start events (retention)
    # cannot be used; a resolved observation is not evidence of an executed repair.
    durations = health._read("""SELECT (julianday(e.created_at)-julianday(s.created_at))*86400 AS seconds
        FROM lite_system_health_events e JOIN lite_system_health_events s
        ON s.incident_id=e.incident_id AND s.generation=e.generation
        WHERE e.event_type='observed_healthy' AND s.event_type IN ('detected','reopened')
          AND julianday(e.created_at)>=julianday('now')-30
          AND julianday(e.created_at)>=julianday(s.created_at)
        ORDER BY e.created_at DESC LIMIT 100""")
    seconds=[r["seconds"] for r in durations if isinstance(r["seconds"],(int,float)) and r["seconds"]>=0]
    return {"scope":"fixed_core_service_samples_24h","expected_samples":WINDOW*len(SERVICES),
        "known_samples":known,"observation_coverage":round(known/(WINDOW*len(SERVICES)),4),
        "observed_availability":round(healthy/known,4) if known else None,
        "continuous_uptime":None,"services":result,
        "mean_observed_incident_resolution_seconds":round(sum(seconds)/len(seconds),1) if seconds else None,
        "incident_timing_samples":len(seconds),"incident_window_days":30}
