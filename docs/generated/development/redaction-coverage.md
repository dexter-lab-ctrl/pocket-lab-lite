---
title: "Redaction coverage"
description: "Consolidated source-owned redaction and generated-artifact secret-safety coverage."
status: verified
generated: true
audience: development
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/lite/generate_platform_catalogs.py
generator_version: 1
source_fingerprint: bc320217385d0c6c6732ad73e7c060620cd8585c648b3567bba515cd527e43a3
schema_revision: 1
validation_status: generated
---

<div class="pl-page-meta" markdown>
<span class="pl-status pl-status--verified">Verified</span>
<span class="pl-status pl-status--patch-provided">Source generated</span>
</div>

# Redaction coverage

| Area | Coverage |
| --- | --- |
| Coverage Sources | scripts/dev/lite/redaction_check.py, scripts/dev/lite/har_tool.py, tests/backend/test_lite_api.py, tests/backend/test_lite_security.py |
| Sensitive Key Patterns | password, token, secret, credential, authorization, cookie, private_key, api_key, nats_url, restic |
| Sensitive Value Patterns | Bearer <token>, private key PEM, credentialed NATS URL, Tailscale auth key, absolute Android private path |
| Redacted Api Fields | derived from response sanitizers and tests |
| Redacted Event Fields | event catalog redacted_fields metadata |
| Log Redaction Tests | tests/backend/test_lite_api.py, tests/backend/test_lite_security.py |
| Har Redaction Tests | scripts/dev/lite/har_tool.py |
| Schema Spy No Data Check | temporary database row count is zero before SchemaSpy |
| Generated Document Secret Scan | platform check scans generated Markdown, JSON, HTML, DOT and SVG |
| Unresolved Coverage Gaps | runtime-only third-party output remains subject to the existing redaction gate |
