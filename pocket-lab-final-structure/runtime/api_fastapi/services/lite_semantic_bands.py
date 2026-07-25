from __future__ import annotations

"""Deterministic integer threshold bands with bounded hysteresis.

Raw measurements are converted to scaled integers before entering this module.
The helpers therefore avoid floating-point values in semantic revision inputs.
"""

from dataclasses import dataclass
from typing import Any

POLICY_VERSION = 1
BANDS = ("normal", "watch", "elevated", "critical")
_RANK = {name: index for index, name in enumerate(BANDS)}


@dataclass(frozen=True)
class ThresholdPolicy:
    watch: int
    elevated: int
    critical: int
    hysteresis: int = 0
    low_is_bad: bool = False
    version: int = POLICY_VERSION

    def normalized(self) -> "ThresholdPolicy":
        values = sorted((max(0, int(self.watch)), max(0, int(self.elevated)), max(0, int(self.critical))))
        if self.low_is_bad:
            critical, elevated, watch = values
        else:
            watch, elevated, critical = values
        return ThresholdPolicy(
            watch=watch,
            elevated=elevated,
            critical=critical,
            hysteresis=max(0, int(self.hysteresis)),
            low_is_bad=bool(self.low_is_bad),
            version=max(1, int(self.version)),
        )


def _raw_band(value: int, policy: ThresholdPolicy) -> str:
    if policy.low_is_bad:
        if value <= policy.critical:
            return "critical"
        if value <= policy.elevated:
            return "elevated"
        if value <= policy.watch:
            return "watch"
        return "normal"
    if value >= policy.critical:
        return "critical"
    if value >= policy.elevated:
        return "elevated"
    if value >= policy.watch:
        return "watch"
    return "normal"


def semantic_band(
    value: int | None,
    policy: ThresholdPolicy,
    *,
    previous: str = "unknown",
    supported: bool = True,
) -> str:
    """Return a stable band.

    Worsening transitions cross the configured threshold immediately. Recovery
    requires crossing the same boundary plus the configured hysteresis margin.
    """
    if not supported:
        return "unsupported"
    if value is None:
        return "unknown"
    normalized = policy.normalized()
    desired = _raw_band(int(value), normalized)
    prior = str(previous or "unknown").lower()
    if prior not in _RANK or desired == prior:
        return desired
    if _RANK[desired] > _RANK[prior]:
        return desired

    margin = normalized.hysteresis
    if normalized.low_is_bad:
        recovery_boundary = {
            "normal": normalized.watch,
            "watch": normalized.elevated,
            "elevated": normalized.critical,
        }[desired]
        return desired if int(value) >= recovery_boundary + margin else prior
    recovery_boundary = {
        "normal": normalized.watch,
        "watch": normalized.elevated,
        "elevated": normalized.critical,
    }[desired]
    return desired if int(value) <= recovery_boundary - margin else prior


def policy_material(policy: ThresholdPolicy) -> dict[str, Any]:
    normalized = policy.normalized()
    return {
        "watch": normalized.watch,
        "elevated": normalized.elevated,
        "critical": normalized.critical,
        "hysteresis": normalized.hysteresis,
        "low_is_bad": normalized.low_is_bad,
        "version": normalized.version,
    }
