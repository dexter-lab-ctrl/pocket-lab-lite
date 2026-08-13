---
title: "Quick, Full, and App safety checks"
description: "Defines bounded profile-specific targets, exclusions, timeouts, coverage summaries, and truthful partial/failed states."
generated: true
audience: knowledgebase
confidence: verified
source_commit: uncommitted
generated_at: uncommitted
generator: scripts/docs/knowledge/generate_knowledge.py
generator_version: 3
---

# Quick, Full, and App safety checks

Defines bounded profile-specific targets, exclusions, timeouts, coverage summaries, and truthful partial/failed states.

## Why it exists

Defines bounded profile-specific targets, exclusions, timeouts, coverage summaries, and truthful partial/failed states.

## Knowledge card

| Field | Value |
| --- | --- |
| Component ID | `component:security-profiles` |
| Owner | Security policy |
| Execution owner | Security coordinator |
| Data owner | Security state |
| Recovery owner | Explicit retry |
| Runtime owner | pocket-worker |
| Runtime process | Security coordinator |
| Runtime platform | Security worker |
| Security boundary | messaging-execution |
| Confidence | verified |

## Responsibilities

- Defines bounded profile-specific targets, exclusions, timeouts, coverage summaries, and truthful partial/failed states.

## Inputs

- Profile and optional app id

## Outputs

- Coverage and findings

## Health signals

- profile freshness

## Failure modes

- partial/missing target

## Recovery behavior

- truthful partial state
- explicit retry

## Evidence

- coverage_summary

## Supported platforms

- Android/Termux
- ARM64
- Ubuntu
- WSL2 development

## Depends on / uses

- depends_on: `Lynis and Trivy scanner adapters`
- depends_on: `security_profile_snapshots`
- protected_by: `Messaging and execution boundary`
- protected_by: `Messaging and execution boundary`
- related_to: `pocketlab.commands.lite.security.scan`
- verified_by: `tests/backend/test_lite_termux_runtime_documentation.py`
- verified_by: `tests/docs/test_documentation_presentation_polish.py`
- verified_by: `tests/docs/test_enterprise_completion.py`
- verified_by: `tests/docs/test_living_knowledgebase.py`

## Used by / backlinks

- depends_on: `Security scan coordinator`
- uses: `Security scan`

## Release history

No canonical component introduction/fix release is recorded, so release history remains unvalidated rather than inferred.

## Related architecture

- [Production architecture component page](../../../production/architecture/components/security-profiles.md)

## Canonical sources

- `architecture/metadata/pocket-lab-architecture.json`
