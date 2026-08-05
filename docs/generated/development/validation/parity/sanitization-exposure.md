---
title: "Sanitization and Data Exposure Report"
generated: true
audience: development
status: generated
source_revision: repository-source
semantic_fingerprint: 6416acf0e1764391a0818d34e899f07cdf587e197b13c5481b87128c5caaad57
generator: scripts/docs/parity/generate_parity.py
---

# Sanitization and Data Exposure Report
> Status vocabulary: **verified** is source/test confirmed; **partial** is source-derived but incomplete; **planned** is not implemented; **unvalidated** has not been run in the current environment.

Maximum evidence size: **262144 bytes**.

## Rejected classes

- credentials
- bearer tokens
- passwords
- private keys
- certificates
- IPv4
- IPv6
- Tailnet names
- hostnames
- usernames
- Android private paths
- WSL user paths
- SSH key paths
- credential URLs
- media paths
- environment dumps
- raw logs
- raw SQLite rows
- raw manifests
- full PM2 environments
- NATS credentials

All generated artifacts are allowlisted and scanned by the existing repository redaction checker plus parity-specific checks.
