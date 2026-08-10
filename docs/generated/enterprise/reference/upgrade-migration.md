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
| From | not-comparable |
| To | HEAD/current source |
| Database migrations | {'dimension': 'sqlite-schema-migrations', 'status': 'not-comparable', 'classification': 'not-comparable'} |
| Agent compatibility | review agent/supervisor and bootstrap source changes in release delta |
| Runtime changes | compare only promoted runtime evidence; current HEAD is not automatically runtime-promoted |
| Backup requirement | run/verify recovery backup according to release policy before destructive migration/update |
| API breaking changes | use existing oasdiff evidence plus OpenAPI release-delta dimension |
| Config changes | Configuration Intelligence + git release delta |
| Rollback | release rollback contract + verified backup/checkpoint where state changes |
| Verification | task lite:api:breaking-changes, task lite:docs:check, task lite:check |
