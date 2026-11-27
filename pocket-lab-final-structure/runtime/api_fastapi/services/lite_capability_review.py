"""Read-only per-capability change review using the existing T0 ceiling model."""
from __future__ import annotations

from .lite_lifecycle_contract import CAPABILITIES, Capability, Impact, _expands, inventory, canonical_bytes, digest

MAX_REVIEW_ROWS = 20


def compare_capabilities(old: tuple[Capability, ...], new: tuple[Capability, ...]):
    inventory(old)
    inventory(new)
    before = {c.id: c for c in old}
    after = {c.id: c for c in new}
    rows = []
    scopes = {}
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
        scope = {"id": key, "impact": impact.value, "before": old_fields or None, "after": new_fields or None}
        scopes[key] = scope
        rows.append({"id": key, "impact": impact.value, "scope_sha256": digest(scope),
                     "changed_fields": ", ".join(sorted(k for k in old_fields.keys() | new_fields.keys()
                                              if old_fields.get(k) != new_fields.get(k))),
                     "review_required": True, "execution_eligible": False})
    # Authority expansion and trust changes appear first. Bounded prepared read.
    priority = {"U5": 0, "U4": 1, "UX": 2, "U2": 3}
    rows.sort(key=lambda row: (priority[row["impact"]], row["id"]))
    # Bound exact scopes independently of the compact display rows and of the
    # release child protocol (128 KiB). Omitted scopes cannot be consented to.
    exact = []
    budget = 48 * 1024
    for row in rows[:MAX_REVIEW_ROWS]:
        scope = scopes[row["id"]]
        size = len(canonical_bytes(scope))
        if size <= budget:
            exact.append(scope)
            budget -= size
    return {"total": len(rows), "changes": rows[:MAX_REVIEW_ROWS],
            "exact_scopes": exact,
            "truncated": len(rows) > MAX_REVIEW_ROWS or len(exact) < min(len(rows), MAX_REVIEW_ROWS),
            "execution_eligible": False}


def exact_scopes_for_transport(review):
    """Reconstruct only strict typed capability data after generic redaction.

    The bounded trust child already checked the signed manifest. Generic
    release transport truncates nested objects and cannot preserve an exact
    scope digest. No other fields bypass the normal sanitizer.
    """
    if not isinstance(review, dict):
        return []
    rows = review.get("changes") or []
    scopes = review.get("exact_scopes") or []
    if not isinstance(rows, list) or not isinstance(scopes, list) or len(rows) > MAX_REVIEW_ROWS or len(scopes) > MAX_REVIEW_ROWS:
        raise ValueError("candidate_scope_transport_invalid")
    expected = {row["id"]: row["scope_sha256"] for row in rows}
    local = {cap.id: cap.model_dump(mode="json") for cap in CAPABILITIES}
    verified = []
    seen = set()
    for scope in scopes:
        if not isinstance(scope, dict) or set(scope) != {"id", "impact", "before", "after"}:
            raise ValueError("candidate_scope_transport_invalid")
        key = scope["id"]
        if key in seen or key not in expected or scope["before"] != local.get(key):
            raise ValueError("candidate_scope_transport_invalid")
        seen.add(key)
        for field in ("before", "after"):
            if scope[field] is not None:
                cap = Capability.model_validate_json(canonical_bytes(scope[field]))
                if cap.id != key or cap.model_dump(mode="json") != scope[field]:
                    raise ValueError("candidate_scope_transport_invalid")
        if scope["before"] == scope["after"] or scope["impact"] not in {"U2", "U4", "U5", "UX"} or digest(scope) != expected[key]:
            raise ValueError("candidate_scope_transport_invalid")
        verified.append(scope)
    if len(canonical_bytes(verified)) > 49 * 1024:
        raise ValueError("candidate_scope_transport_invalid")
    return verified


def public_review(review):
    if not isinstance(review, dict):
        return None
    scopes = {scope["id"]: digest(scope) for scope in review.get("exact_scopes", [])}
    return {"total": review.get("total"), "truncated": bool(review.get("truncated")),
            "execution_eligible": False,
            "changes": [{**row, "exact_scope_available": scopes.get(row["id"]) == row.get("scope_sha256") and row["id"] in scopes}
                        for row in review.get("changes", [])]}
