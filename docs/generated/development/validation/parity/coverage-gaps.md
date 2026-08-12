---
title: "Coverage and Gap Analysis"
generated: true
audience: development
status: generated
source_revision: repository-source
semantic_fingerprint: 44a849b588fbdf72c3f81bf6f44ee5beef37bfd3c290bd1247a85d7ba4f0135c
generator: scripts/docs/parity/generate_parity.py
---

# Coverage and Gap Analysis
> Status vocabulary: **verified** is source/test confirmed; **partial** is source-derived but incomplete; **planned** is not implemented; **unvalidated** has not been run in the current environment.

| Domain | Status | Runtime parity | Known gaps |
| --- | --- | --- | --- |
| Home | verified | verified-with-mapped-presentation | Live runtime semantic evidence remains explicit and release-bound. |
| Apps | needs-review | drift-detected | Application-owned media indexing is not a Pocket Lab parity authority. |
| Devices | verified | verified-with-mapped-presentation | Per-device profile fields remain partial when the agent has not published them. |
| Security | verified | verified-with-mapped-presentation | A missing scanner is runtime-unavailable, not semantic drift. |
| Identity | partial | partial | The current tab is direct-rendered and has no dedicated selector layer.; Identity guard and protected server-host projections are not fully implemented. |
| Rules | partial | partial | Per-rule identity and execution history are planned, not present in the current API. |
| Backup & Restore | needs-review | drift-detected | Live Termux and live browser semantic capture remain explicit; missing capture is not drift. |

Repository-derived contracts exist for all seven tabs. Successful, mapped, drifted, partial, failed, stale, unavailable, unsupported, and accepted-limitation outcomes remain distinct.
