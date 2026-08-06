---
title: "Coverage and Gap Analysis"
generated: true
audience: development
status: generated
source_revision: repository-source
semantic_fingerprint: 6416acf0e1764391a0818d34e899f07cdf587e197b13c5481b87128c5caaad57
generator: scripts/docs/parity/generate_parity.py
---

# Coverage and Gap Analysis
> Status vocabulary: **verified** is source/test confirmed; **partial** is source-derived but incomplete; **planned** is not implemented; **unvalidated** has not been run in the current environment.

| Domain | Status | Known gaps |
| --- | --- | --- |
| Backup & Restore | verified | Live Termux parity is opt-in and read-only.; Visual parity is semantic and not pixel equality.; App restore apply remains explicitly unsupported by the repository. |
| Devices | partial | Parity mappings are source-derived catalog entries only in this increment. |
| Apps | partial | PhotoPrism is cataloged; full cross-app parity remains planned. |
| Security | partial | Live scanner parity is not part of ordinary documentation generation. |
| Rules | planned | Repository exposes a partial product contract; authoritative mappings are planned. |
| Releases | partial | Release apply is excluded from parity property and live read-only gates. |

Backup & Restore is implemented end to end in this framework. Other domains are intentionally source-derived catalogs rather than fabricated full parity coverage.
