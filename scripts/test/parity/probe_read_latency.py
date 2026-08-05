#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

DEFAULT_PATHS = (
    "/api/lite/recovery/summary",
    "/api/lite/security",
    "/api/lite/security/apps",
)


def require_loopback(value: str) -> None:
    parsed = urlsplit(value)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "http" or parsed.username or parsed.password:
        raise SystemExit("ERROR latency probe requires an unauthenticated HTTP loopback URL")
    if host == "localhost":
        return
    try:
        import ipaddress

        if ipaddress.ip_address(host).is_loopback:
            return
    except ValueError:
        pass
    raise SystemExit(f"ERROR latency probe target is not loopback: {host or 'missing-host'}")


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(len(ordered) * fraction) - 1))
    return ordered[index]


def atomic_write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def sample(base_url: str, path: str, timeout: float) -> tuple[int, float]:
    request = Request(base_url.rstrip("/") + path, headers={"Accept": "application/json", "User-Agent": "PocketLab-Latency-Probe/1"})
    started = time.perf_counter()
    try:
        with urlopen(request, timeout=timeout) as response:
            response.read(256_000)
            return int(response.status), (time.perf_counter() - started) * 1000
    except HTTPError as exc:
        exc.read(64_000)
        return int(exc.code), (time.perf_counter() - started) * 1000


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()
    require_loopback(args.base_url)
    bounded_samples = max(2, min(args.samples, 5))
    results = []
    failures = 0
    for path in DEFAULT_PATHS:
        timings: list[float] = []
        statuses: list[int] = []
        for _ in range(bounded_samples):
            try:
                status, elapsed = sample(args.base_url, path, args.timeout)
                timings.append(elapsed)
                statuses.append(status)
            except (URLError, TimeoutError):
                failures += 1
            time.sleep(0.15)
        results.append({
            "path": path,
            "samples": len(timings),
            "statuses": statuses,
            "cold_ms": round(timings[0], 2) if timings else None,
            "warm_median_ms": round(statistics.median(timings[1:] or timings), 2) if timings else None,
            "p95_ms": round(percentile(timings, 0.95), 2) if timings else None,
            "max_ms": round(max(timings), 2) if timings else None,
        })
    payload = {
        "base_url": "loopback",
        "sample_count": bounded_samples,
        "endpoints": results,
        "network_failures": failures,
        "sanitized": True,
    }
    atomic_write(args.output, payload)
    print(f"PASS bounded read latency evidence: {len(results)} endpoints; failures={failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
