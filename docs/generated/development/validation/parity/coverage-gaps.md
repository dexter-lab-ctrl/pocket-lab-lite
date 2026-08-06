---
title: "Coverage and Gap Analysis"
generated: true
audience: development
status: generated
source_revision: repository-source
semantic_fingerprint: b7775f31c564307fda5d795c62195d03810206e330182eec14f52fa99bbf13f2
generator: scripts/docs/parity/generate_parity.py
---

# Coverage and Gap Analysis
> Status vocabulary: **verified** is source/test confirmed; **partial** is source-derived but incomplete; **planned** is not implemented; **unvalidated** has not been run in the current environment.

| Domain | Status | Runtime parity | Known gaps |
| --- | --- | --- | --- |
| Home | partial | unvalidated | Live runtime semantic evidence remains explicit and release-bound. |
| Apps | partial | unvalidated | Application-owned media indexing is not a Pocket Lab parity authority. |
| Devices | partial | unvalidated | Per-device profile fields remain partial when the agent has not published them. |
| Security | partial | unvalidated | A missing scanner is runtime-unavailable, not semantic drift. |
| Identity | partial | unvalidated | The current tab is direct-rendered and has no dedicated selector layer. |
| Rules | partial | unvalidated | Per-rule identity and execution history are planned, not present in the current API. |
| Backup & Restore | ready-with-accepted-limitations | unvalidated | Live Termux and live browser semantic capture remain explicit; missing capture is not drift. |

Repository-derived contracts exist for all seven tabs. Successful, mapped, drifted, partial, failed, stale, unavailable, unsupported, and accepted-limitation outcomes remain distinct.
