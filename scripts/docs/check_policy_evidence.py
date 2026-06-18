#!/usr/bin/env python3
from __future__ import annotations

import json
from generate_policy_evidence import OUT, build_manifest


def main() -> int:
    expected = json.dumps(build_manifest(), indent=2, sort_keys=True) + "\n"
    if not OUT.exists():
        print(f"Missing {OUT}")
        return 1
    actual = OUT.read_text(encoding="utf-8")
    if actual != expected:
        print("Policy evidence manifest is stale. Run: task docs:security:policies")
        return 1
    data = json.loads(actual)
    validation = data.get("validation") or {}
    if validation.get("unknown_policy_operations") or validation.get("unknown_policy_runbooks"):
        print("Policy evidence manifest contains unknown policy mappings")
        print(json.dumps(validation, indent=2, sort_keys=True))
        return 1
    print("Policy evidence manifest is fresh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
