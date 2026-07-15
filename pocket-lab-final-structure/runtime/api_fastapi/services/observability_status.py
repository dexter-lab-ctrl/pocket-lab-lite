from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import os
import time
from typing import Any

from .workload_admission import WORKLOAD_ADMISSION
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

DEFAULT_TIMEOUT_SECONDS = 1.5
DEFAULT_CACHE_TTL_SECONDS = 30
MAX_BODY_BYTES = 256_000
MAX_DOWN_TARGETS = 10
PROMTAIL_RECENT_WINDOW_SECONDS = 300

_CACHE: dict[str, Any] = {"snapshot": None, "expires_at": 0.0}


class ProbeResult(dict):
    """Dictionary marker used to keep probe responses bounded and explicit."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _base_url(env_name: str, default: str) -> str:
    return os.environ.get(env_name, default).rstrip("/")



def _redact_url(url: str) -> str:
    try:
        parts = urlsplit(url)
    except ValueError:
        return url
    if "@" not in parts.netloc:
        return url
    host = parts.hostname or "redacted-host"
    if parts.port:
        host = f"{host}:{parts.port}"
    return urlunsplit((parts.scheme, host, parts.path, parts.query, parts.fragment))

def _safe_reason(value: Any, *, limit: int = 220) -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    return text[:limit] if text else "No detail returned"


def _http_get(url: str, *, timeout: float) -> dict[str, Any]:
    start = time.perf_counter()
    try:
        request = Request(url, headers={"Accept": "application/json,text/plain,*/*"})
        with urlopen(request, timeout=timeout) as response:  # nosec B310 - bounded loopback probe URLs are configured locally.
            body = response.read(MAX_BODY_BYTES + 1)
            truncated = len(body) > MAX_BODY_BYTES
            if truncated:
                body = body[:MAX_BODY_BYTES]
            latency_ms = int((time.perf_counter() - start) * 1000)
            return {
                "ok": 200 <= response.status < 300,
                "status_code": response.status,
                "latency_ms": latency_ms,
                "body": body.decode("utf-8", errors="replace"),
                "truncated": truncated,
                "error": "",
            }
    except HTTPError as exc:
        latency_ms = int((time.perf_counter() - start) * 1000)
        return {
            "ok": False,
            "status_code": exc.code,
            "latency_ms": latency_ms,
            "body": "",
            "truncated": False,
            "error": _safe_reason(exc.reason or exc),
        }
    except (TimeoutError, URLError, OSError) as exc:
        latency_ms = int((time.perf_counter() - start) * 1000)
        return {
            "ok": False,
            "status_code": None,
            "latency_ms": latency_ms,
            "body": "",
            "truncated": False,
            "error": _safe_reason(exc),
        }


def _json_body(probe: dict[str, Any]) -> dict[str, Any]:
    try:
        parsed = json.loads(probe.get("body") or "{}")
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def _simple_ready_service(
    name: str,
    endpoint: str,
    *,
    timeout: float,
    healthy_reason: str,
    source: str,
) -> dict[str, Any]:
    probe = _http_get(endpoint, timeout=timeout)
    healthy = bool(probe["ok"])
    return {
        "status": "healthy" if healthy else "unavailable",
        "ready": healthy,
        "endpoint": _redact_url(endpoint),
        "latency_ms": probe["latency_ms"],
        "reason": healthy_reason if healthy else _safe_reason(probe.get("error") or f"{name} returned HTTP {probe.get('status_code') or 'no response'}"),
        "source": source,
    }


def _grafana_health(endpoint: str, *, timeout: float) -> dict[str, Any]:
    probe = _http_get(endpoint, timeout=timeout)
    data = _json_body(probe)
    status_value = str(data.get("database") or data.get("status") or "").lower()
    healthy = bool(probe["ok"] and (not status_value or status_value in {"ok", "healthy"}))
    reason = "Grafana health endpoint returned ok"
    if not healthy:
        reason = _safe_reason(probe.get("error") or data.get("message") or f"Grafana returned HTTP {probe.get('status_code') or 'no response'}")
    return {
        "status": "healthy" if healthy else "unavailable",
        "healthy": healthy,
        "endpoint": _redact_url(endpoint),
        "latency_ms": probe["latency_ms"],
        "reason": reason,
        "source": "grafana_api_health",
    }


def _prometheus_targets(endpoint: str, *, timeout: float) -> dict[str, Any]:
    probe = _http_get(endpoint, timeout=timeout)
    if not probe["ok"]:
        return {
            "status": "unavailable",
            "endpoint": _redact_url(endpoint),
            "up": 0,
            "down": 0,
            "total": 0,
            "down_targets": [],
            "latency_ms": probe["latency_ms"],
            "reason": _safe_reason(probe.get("error") or f"Prometheus targets returned HTTP {probe.get('status_code') or 'no response'}"),
            "source": "prometheus_api_targets",
        }

    data = _json_body(probe)
    active = data.get("data", {}).get("activeTargets", []) if isinstance(data.get("data"), dict) else []
    active = active if isinstance(active, list) else []
    down_targets: list[dict[str, Any]] = []
    up = 0
    for target in active:
        if not isinstance(target, dict):
            continue
        health = str(target.get("health", "unknown")).lower()
        if health == "up":
            up += 1
            continue
        labels = target.get("labels", {}) if isinstance(target.get("labels"), dict) else {}
        down_targets.append(
            {
                "job": labels.get("job") or target.get("scrapePool") or "unknown",
                "instance": labels.get("instance") or target.get("scrapeUrl") or "unknown",
                "health": health or "unknown",
                "last_error": _safe_reason(target.get("lastError") or target.get("lastScrapeError") or ""),
            }
        )
    total = len(active)
    down = max(0, total - up)
    return {
        "status": "healthy" if total > 0 and down == 0 else "degraded" if total > 0 else "unknown",
        "endpoint": _redact_url(endpoint),
        "up": up,
        "down": down,
        "total": total,
        "down_targets": down_targets[:MAX_DOWN_TARGETS],
        "latency_ms": probe["latency_ms"],
        "reason": f"Prometheus reported {up}/{total} targets UP" if total else "Prometheus returned no active targets",
        "source": "prometheus_api_targets",
    }


def _promtail_shipping(loki_base: str, *, timeout: float) -> dict[str, Any]:
    now_ns = int(time.time() * 1_000_000_000)
    start_ns = now_ns - (PROMTAIL_RECENT_WINDOW_SECONDS * 1_000_000_000)
    params = urlencode(
        {
            "query": '{job="pm2_logs"}',
            "limit": "5",
            "start": str(start_ns),
            "end": str(now_ns),
            "direction": "backward",
        }
    )
    endpoint = f"{loki_base}/loki/api/v1/query_range?{params}"
    probe = _http_get(endpoint, timeout=timeout)
    if not probe["ok"]:
        return {
            "status": "unknown",
            "shipping_logs": False,
            "inferred": True,
            "recent_log_count": 0,
            "endpoint": _redact_url(f"{loki_base}/loki/api/v1/query_range"),
            "latency_ms": probe["latency_ms"],
            "reason": _safe_reason(probe.get("error") or f"Loki log query returned HTTP {probe.get('status_code') or 'no response'}"),
            "source": "loki_query_range_pm2_logs",
        }

    data = _json_body(probe)
    streams = data.get("data", {}).get("result", []) if isinstance(data.get("data"), dict) else []
    streams = streams if isinstance(streams, list) else []
    count = 0
    for stream in streams:
        values = stream.get("values", []) if isinstance(stream, dict) else []
        if isinstance(values, list):
            count += len(values)
    shipping = count > 0
    return {
        "status": "healthy" if shipping else "degraded",
        "shipping_logs": shipping,
        "inferred": True,
        "recent_log_count": count,
        "endpoint": _redact_url(f"{loki_base}/loki/api/v1/query_range"),
        "latency_ms": probe["latency_ms"],
        "reason": "Recent pm2_logs entries found in Loki" if shipping else "No recent pm2_logs entries found in Loki",
        "source": "loki_query_range_pm2_logs",
    }


def _overall_status(snapshot: dict[str, Any]) -> str:
    statuses = [svc.get("status", "unknown") for svc in snapshot.get("services", {}).values()]
    statuses.append(snapshot.get("prometheus_targets", {}).get("status", "unknown"))
    if statuses and all(status == "healthy" for status in statuses):
        return "healthy"
    if any(status == "healthy" for status in statuses):
        return "degraded"
    if any(status == "degraded" for status in statuses):
        return "degraded"
    return "unavailable"


def clear_observability_status_cache() -> None:
    _CACHE["snapshot"] = None
    _CACHE["expires_at"] = 0.0


def build_observability_status_snapshot(*, use_cache: bool = True) -> dict[str, Any]:
    cache_ttl = max(1, _env_int("POCKETLAB_OBSERVABILITY_STATUS_CACHE_TTL_SECONDS", DEFAULT_CACHE_TTL_SECONDS))
    now = time.time()
    if use_cache and _CACHE.get("snapshot") and now < float(_CACHE.get("expires_at", 0)):
        cached = deepcopy(_CACHE["snapshot"])
        cached["cached"] = True
        cached["cache_expires_at"] = datetime.fromtimestamp(float(_CACHE["expires_at"]), timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        return cached

    timeout = max(0.2, _env_float("POCKETLAB_OBSERVABILITY_PROBE_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS))
    prometheus = _base_url("POCKETLAB_PROMETHEUS_URL", "http://127.0.0.1:9090")
    loki = _base_url("POCKETLAB_LOKI_URL", "http://127.0.0.1:3100")
    grafana = _base_url("POCKETLAB_GRAFANA_URL", "http://127.0.0.1:3050")
    gatus = _base_url("POCKETLAB_GATUS_URL", "http://127.0.0.1:8081")

    services = {
        "prometheus": _simple_ready_service(
            "Prometheus",
            f"{prometheus}/-/ready",
            timeout=timeout,
            healthy_reason="Prometheus ready endpoint returned 200",
            source="prometheus_ready_endpoint",
        ),
        "loki": _simple_ready_service(
            "Loki",
            f"{loki}/ready",
            timeout=timeout,
            healthy_reason="Loki ready endpoint returned 200",
            source="loki_ready_endpoint",
        ),
        "grafana": _grafana_health(f"{grafana}/api/health", timeout=timeout),
        "gatus": _simple_ready_service(
            "Gatus",
            f"{gatus}/health",
            timeout=timeout,
            healthy_reason="Gatus health endpoint returned 200",
            source="gatus_health_endpoint",
        ),
        "promtail": _promtail_shipping(loki, timeout=timeout),
    }
    snapshot: dict[str, Any] = {
        "status": "unknown",
        "checked_at": _utc_now(),
        "cached": False,
        "cache_ttl_seconds": cache_ttl,
        "services": services,
        "prometheus_targets": _prometheus_targets(f"{prometheus}/api/v1/targets", timeout=timeout),
        "warnings": [],
    }
    if snapshot["services"]["promtail"].get("inferred"):
        snapshot["warnings"].append("Promtail shipping status is inferred from recent Loki pm2_logs entries.")
    snapshot["status"] = _overall_status(snapshot)
    _CACHE["snapshot"] = deepcopy(snapshot)
    _CACHE["expires_at"] = now + cache_ttl
    return snapshot


async def get_observability_status_snapshot(*, use_cache: bool = True) -> dict[str, Any]:
    snapshot, _ = await WORKLOAD_ADMISSION.run(
        "system.observability_probe",
        build_observability_status_snapshot,
        use_cache=use_cache,
    )
    return snapshot
