"""Read-only per-capability change review using the existing T0 ceiling model."""
from __future__ import annotations

from .lite_lifecycle_contract import Capability, Impact, _expands, inventory

MAX_REVIEW_ROWS = 20


def compare_capabilities(old: tuple[Capability, ...], new: tuple[Capability, ...]):
    inventory(old)
    inventory(new)
    before = {c.id: c for c in old}
    after = {c.id: c for c in new}
    rows = []
    for key in sorted(before.keys() | after.keys()):
        a, b = before.get(key), after.get(key)
        if a == b:
            continue
        if a is None:
            impact = Impact.U4
        elif b is None:
            impact = Impact.U2
        elif (a.owner, a.domain) != (b.owner, b.domain):
            impact = Impact.U5
        elif _expands(a, b):
            impact = Impact.U4
        elif a.version != b.version:
            impact = Impact.UX
        elif _expands(b, a):
            impact = Impact.U2
        else:
            impact = Impact.UX
        old_fields = a.model_dump(mode="json") if a else {}
        new_fields = b.model_dump(mode="json") if b else {}
        rows.append({"id": key, "impact": impact.value,
                     "changed_fields": sorted(k for k in old_fields.keys() | new_fields.keys()
                                              if old_fields.get(k) != new_fields.get(k)),
                     "review_required": True, "execution_eligible": False})
    # Authority expansion and trust changes appear first. Bounded prepared read.
    priority = {"U5": 0, "U4": 1, "UX": 2, "U2": 3}
    rows.sort(key=lambda row: (priority[row["impact"]], row["id"]))
    return {"total": len(rows), "changes": rows[:MAX_REVIEW_ROWS],
            "truncated": len(rows) > MAX_REVIEW_ROWS, "execution_eligible": False}
