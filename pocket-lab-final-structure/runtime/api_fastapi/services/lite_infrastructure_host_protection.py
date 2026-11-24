"""Local host protection evidence, collected by the existing worker.
No external network fetch, privileged access, or read-path side effects.
"""
from __future__ import annotations
from datetime import datetime, timezone
import json
import os
import re
import socket
import ssl
import hashlib
import subprocess
from pathlib import Path
import time
from ..db.connection import connection, begin_immediate
from . import lite_system_health as health
from . import lite_infrastructure_authority as authority

_last_clock: tuple[float,float] | None = None
_pressure_since: float | None = None
_clear_since: float | None = None
_pressure = False


def _small(path: Path) -> str:
    with path.open("r",encoding="ascii") as stream:
        value=stream.read(129)
    if len(value)>128:
        raise ValueError("invalid_sysfs_value")
    return value.strip()


def battery(root: Path=Path("/sys/class/power_supply")) -> dict:
    """Report only a single unambiguous system battery. No simulated values."""
    try:
        with os.scandir(root) as items:
            entries=[]
            for index,item in enumerate(items):
                if index>=16:
                    return {"state":"unknown","percent":None,"charging":"unknown"}
                # Power-supply entries are directories.  Ignore unrelated
                # files in the bounded root (for example the worker's local
                # state file) and do not follow symlinked directories into an
                # untrusted tree.
                if item.is_dir(follow_symlinks=False):
                    entries.append(Path(item.path))
        batteries=[p for p in entries if _small(p/"type")=="Battery"]
        if len(batteries)!=1:
            return {"state":"unsupported" if not batteries else "unknown","percent":None,"charging":"unknown"}
        p=batteries[0]
        percent=int(_small(p/"capacity"))
        status=_small(p/"status").casefold()
        if not 0<=percent<=100:
            raise ValueError("invalid_battery")
        charging={"charging":"charging","discharging":"discharging","full":"full","not charging":"not_charging"}.get(status,"unknown")
        return {"state":"available","percent":percent,"charging":charging}
    except FileNotFoundError:
        return {"state":"unsupported","percent":None,"charging":"unknown"}
    except PermissionError:
        return {"state":"unavailable","percent":None,"charging":"unknown"}
    except (OSError,ValueError,UnicodeError):
        return {"state":"unknown","percent":None,"charging":"unknown"}


def _clock() -> str:
    global _last_clock
    pair=(time.time(),time.monotonic())
    previous=_last_clock
    _last_clock=pair
    if previous is None or pair[1]-previous[1]>180 or pair[1]<=previous[1]:
        return "unknown"
    return "clock_step_detected" if abs((pair[0]-previous[0])-(pair[1]-previous[1]))>5 else "no_step_observed"


def certificate(root: Path | None=None) -> str:
    """Inspect the existing public certificate only, not the private key.
    This establishes local expiry, never live TLS/hostname/trust validation.
    """
    root=root or Path.home()/".pocket_lab"/"tailscale-certs"
    try:
        if root.is_symlink():
            return "unknown"
        with os.scandir(root) as entries:
            candidates=[]
            for index,item in enumerate(entries):
                if index>=32:
                    return "unknown"
                if item.name.endswith(".ts.net.crt") and item.is_file(follow_symlinks=False):
                    candidates.append(Path(item.path))
        if len(candidates)!=1:
            return "not_configured" if not candidates else "unknown"
        from cryptography import x509
        fd=os.open(candidates[0],os.O_RDONLY|os.O_NOFOLLOW)
        with os.fdopen(fd,"rb") as stream:
            data=stream.read(65537)
        if len(data)>65536:
            return "unknown"
        cert=x509.load_pem_x509_certificate(data)
        now=datetime.now(timezone.utc)
        start=cert.not_valid_before_utc
        end=cert.not_valid_after_utc
        if now<start or now>=end:
            return "expired" if now>=end else "not_ready"
        return "watch" if (end-now).total_seconds()<14*86400 else "ready"
    except FileNotFoundError:
        return "not_configured"
    except Exception:
        return "unknown"


def local_tls(root: Path | None=None) -> str:
    """Verify the configured tailnet certificate on the local HTTPS listener.
    No remote DNS resolution, external request, or disabled certificate check.
    """
    root=root or Path.home()/".pocket_lab"/"tailscale-certs"
    try:
        if root.is_symlink():
            return "unknown"
        with os.scandir(root) as entries:
            candidates=[]
            for index,item in enumerate(entries):
                if index>=32:
                    return "unknown"
                if item.name.endswith(".ts.net.crt") and item.is_file(follow_symlinks=False):
                    candidates.append(Path(item.path))
        if len(candidates)!=1:
            return "not_configured" if not candidates else "unknown"
        name=candidates[0].name.removesuffix(".crt")
        if not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]{0,249})\.ts\.net",name):
            return "unknown"
        fd=os.open(candidates[0],os.O_RDONLY|os.O_NOFOLLOW)
        with os.fdopen(fd,"r",encoding="ascii") as stream:
            pem=stream.read(65537)
        if len(pem)>65536:
            return "unknown"
        # Existing Caddy site uses the standard HTTPS listener. The local
        # address does not require Tailnet DNS or route reachability.
        expected=hashlib.sha256(ssl.PEM_cert_to_DER_cert(pem)).digest()
        context=ssl.create_default_context()
        with socket.create_connection(("localhost",443),timeout=2) as plain:
            with context.wrap_socket(plain,server_hostname=name) as secure:
                served=secure.getpeercert(binary_form=True)
                return "ready" if served and hashlib.sha256(served).digest()==expected else "not_ready"
    except FileNotFoundError:
        return "not_configured"
    except (OSError,ValueError,ssl.SSLError,UnicodeError):
        return "not_ready"


def time_sync() -> str:
    # Only the OS's own synchronization assertion; never infer from wall time.
    # Android/Termux generally lacks systemd, so report unsupported there.
    if not Path("/run/systemd/system").is_dir():
        return "unsupported"
    try:
        result=subprocess.run(["timedatectl","show","--property=NTPSynchronized","--value"],
                              capture_output=True,text=True,timeout=2,check=False)
        if result.returncode!=0:
            return "unknown"
        return {"yes":"ready","no":"not_ready"}.get(result.stdout.strip(),"unknown")
    except (OSError,subprocess.SubprocessError):
        return "unknown"


def _metadata() -> dict:
    from . import lite_security, lite_policy_opa
    from . import lite_infrastructure_read_model as model
    scanner=lite_security._trivy_database_status()
    scanner_status=scanner.get("status")
    # Require durable policy pointer agreement in addition to live OPA proof.
    rows=health._read("SELECT active_revision_id,known_good_revision_id FROM policy_runtime_state WHERE state_id=1")
    policy="unknown"
    if rows and rows[0]["active_revision_id"]:
        try:
            lite_policy_opa._require_loopback_opa()
            consistent,_,revision=lite_policy_opa._policy_consistency()
            policy="ready" if consistent and revision==rows[0]["active_revision_id"] else "not_ready"
        except Exception:
            policy="unknown"
    return {"scanner_database":scanner_status if scanner_status in {"fresh","stale","unavailable"} else "unknown",
            "scanner_valid_until":scanner.get("valid_until") if isinstance(scanner.get("valid_until"),str) else None,
            "policy_integrity":policy,"certificate_expiry":certificate(),"local_tls":local_tls(),"time_sync":time_sync()}


def snapshot() -> dict:
    rows=health._read("SELECT observed_at,metadata_observed_at,payload_json FROM lite_system_health_host_protection WHERE singleton_id=1")
    if not rows:
        return {}
    try:
        data=json.loads(rows[0]["payload_json"])
        return data | {"observed_at":rows[0]["observed_at"],"metadata_observed_at":rows[0]["metadata_observed_at"]}
    except (ValueError,TypeError):
        return {}


def _effective(preference: str, power: dict, *, thermal: str, enabled: bool, now: float) -> str:
    global _pressure_since,_clear_since,_pressure
    if not enabled:
        _pressure_since=_clear_since=None
        _pressure=False
        return "balanced"
    percent=power.get("percent")
    charging=power.get("charging")
    low=type(percent) is int and percent<=20 and charging=="discharging"
    clear=type(percent) is int and (percent>=30 or charging in {"charging","full"})
    thermal_high=thermal in {"elevated","critical"}
    # Missing telemetry cannot indefinitely latch automatic deferral.
    known=type(percent) is int or thermal in {"normal","watch","elevated","critical"}
    if not known:
        _pressure_since=_clear_since=None
        _pressure=False
    elif low or thermal_high:
        _clear_since=None
        if _pressure_since is None:
            _pressure_since=now
        if now-_pressure_since>=60:
            _pressure=True
    elif (clear or type(percent) is not int) and thermal in {"normal","unknown","unsupported"}:
        _pressure_since=None
        if _clear_since is None:
            _clear_since=now
        if now-_clear_since>=120:
            _pressure=False
    else:
        _pressure_since=_clear_since=None
    return "low_power" if _pressure and preference=="balanced" else preference


def capture() -> None:
    from .adaptive_runtime import ADAPTIVE_RUNTIME
    from . import lite_infrastructure_read_model as model
    from . import lite_security_maintenance as maintenance
    previous=snapshot()
    power=battery()
    clock=_clock()
    # Use only server-local thermal provider, not the worst remote-device band.
    try:
        from core.resource_telemetry import _temperature
        observation=_temperature(health._now())
        value=(observation.get("value") or {}).get("celsius")
        thermal=("critical" if value>=80 else "elevated" if value>=70 else "watch" if value>=60 else "normal") if observation.get("status")=="available" and isinstance(value,(float,int)) and 0<=value<=150 else "unknown"
    except Exception:
        thermal="unknown"
    preference=authority.preferences()["resource_mode"]
    effective=_effective(preference,power,thermal=thermal,enabled=authority.resource_preference_enabled(),now=time.monotonic())
    ADAPTIVE_RUNTIME.set_resource_preference(effective)
    stamp=previous.get("metadata_observed_at")
    metadata=previous.get("metadata",{})
    if not stamp or health.freshness(stamp)!="current":
        # Policy inspection and scanner metadata are bounded by this cadence,
        # not performed on every UI read or while maintenance/scan is active.
        if not maintenance.maintenance_state().get("active") and not maintenance.active_security_scan():
            try:
                metadata=_metadata()
            except Exception:
                metadata={}
            stamp=health._now()
    payload={"battery":power,"thermal":thermal,"clock_continuity":clock,
        "resource_preference":preference,"effective_resource_mode":effective,
        "automatic_pressure":_pressure,"metadata":metadata}
    with connection() as conn:
        with begin_immediate(conn):
            conn.execute("""INSERT INTO lite_system_health_host_protection VALUES(1,?,?,?)
              ON CONFLICT(singleton_id) DO UPDATE SET observed_at=excluded.observed_at,
              metadata_observed_at=excluded.metadata_observed_at,payload_json=excluded.payload_json""",
              (health._now(),stamp,json.dumps(payload,separators=(",",":"))))
