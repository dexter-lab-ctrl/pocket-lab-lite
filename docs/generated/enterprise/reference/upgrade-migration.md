---
title: "Upgrade & Migration Intelligence"
description: "Release-comparable upgrade, migration, compatibility, rollback and backup guidance."
generated: true
audience: production
page_type: reference
confidence: generated
---

# Upgrade & Migration Intelligence

| Field | Value |
| --- | --- |
| From | lite-2026.08.12.2 |
| To | lite-2026.08.19.2 |
| Database migrations | {'dimension': 'sqlite-schema-migrations', 'status': 'not-comparable', 'classification': 'not-comparable', 'from_digest': None, 'to_digest': None, 'from_objects': 0, 'to_objects': 0, 'source_paths': ['pocket-lab-final-structure/runtime/api_fastapi/migrations', 'pocket-lab-final-structure/runtime/migrations'], 'details': {}} |
| Agent compatibility | review agent/supervisor and bootstrap source changes in release delta |
| Runtime changes | compare only promoted runtime evidence; repository HEAD is never treated as a release baseline |
| Backup requirement | run/verify recovery backup according to release policy before destructive migration/update |
| API breaking changes | use existing oasdiff evidence plus OpenAPI release-delta dimension |
| Config changes | Configuration Intelligence + verified release-to-release delta |
| Rollback | release rollback contract + verified backup/checkpoint where state changes |
| Verification | task lite:api:breaking-changes, task lite:docs:check, task lite:check |
