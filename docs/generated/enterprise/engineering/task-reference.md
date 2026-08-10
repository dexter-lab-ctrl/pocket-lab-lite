---
title: "Task Reference"
description: "Executable engineering handbook generated from Taskfiles."
generated: true
audience: development
page_type: handbook
confidence: generated
---

# Task Reference — executable engineering handbook

## Workflow map

Tasks remain source-derived; commands are documented but never executed by this page.

| Workflow | Task count |
| --- | --- |
| Development loop | 50 |
| Documentation loop | 45 |
| API-validation loop | 12 |
| Runtime-evidence loop | 24 |
| Security-analysis loop | 7 |
| Release loop | 14 |
| Recovery-diagnostics loop | 6 |

## `default`

**Purpose:** List Pocket Lab Lite development tasks

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `task --list`

**Environment:** None source-discovered

**Inputs:** No explicit file inputs discovered

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** --list

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** not-a-validation-task

**Example:** `task default`

## `lite`

**Purpose:** Compatibility alias for lite:check

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `task lite:check`

**Environment:** None source-discovered

**Inputs:** No explicit file inputs discovered

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** lite:check

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** not-a-validation-task

**Example:** `task lite`

## `lite:dev:scratch:check`

**Purpose:** Validate the repo-local Pocket Lab development scratch policy and filesystem

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `bash scripts/dev/lite/dev-scratch.sh check manual`

**Environment:** None source-discovered

**Inputs:** scripts/dev/lite/dev-scratch.sh

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** gate-defined

**Example:** `task lite:dev:scratch:check`

## `lite:dev:scratch:prepare`

**Purpose:** Prepare the repo-local development scratch root used by WSL2/CI tooling

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `bash scripts/dev/lite/dev-scratch.sh check task`

**Environment:** None source-discovered

**Inputs:** scripts/dev/lite/dev-scratch.sh

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** not-a-validation-task

**Example:** `task lite:dev:scratch:prepare`

## `lite:contracts:check`

**Purpose:** Check OpenAPI and fixture drift without modifying source

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/docs/lite/generate_contracts.py check`
- `npx redocly lint contracts/generated/lite-openapi.json`

**Environment:** None source-discovered

**Inputs:** scripts/docs/lite/generate_contracts.py

**Outputs:** contracts/generated/lite-openapi.json

**Generated artifacts:** contracts/generated/lite-openapi.json

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** gate-defined

**Example:** `task lite:contracts:check`

## `lite:contracts:generate`

**Purpose:** Export the FastAPI Lite OpenAPI contract and generate sanitized canonical fixtures

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/docs/lite/generate_contracts.py generate`

**Environment:** None source-discovered

**Inputs:** scripts/docs/lite/generate_contracts.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** not-a-validation-task

**Example:** `task lite:contracts:generate`

## `lite:docs:architecture:check`

**Purpose:** Check Production architecture model and generated artifact drift

**Audience:** developer

**Dependencies:** lite:docs:architecture:validate

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/docs/graphviz/generate_lite_architecture.py check`

**Environment:** None source-discovered

**Inputs:** scripts/docs/graphviz/generate_lite_architecture.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=True; safe local=True; class=heavy-dev

**Related tasks:** lite:docs:architecture:validate

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** gate-defined

**Example:** `task lite:docs:architecture:check`

## `lite:docs:architecture:generate`

**Purpose:** Generate Production architecture pages, catalogs, and light/dark Graphviz diagrams

**Audience:** developer

**Dependencies:** lite:docs:architecture:icons:check

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/docs/graphviz/generate_lite_architecture.py generate`

**Environment:** None source-discovered

**Inputs:** scripts/docs/graphviz/generate_lite_architecture.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=True; safe local=True; class=heavy-dev

**Related tasks:** lite:docs:architecture:icons:check

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** not-a-validation-task

**Example:** `task lite:docs:architecture:generate`

## `lite:docs:architecture:icons:check`

**Purpose:** Verify pinned repository-owned architecture icons without network access

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `bash scripts/dev/lite/setup-architecture-icons.sh --check`

**Environment:** None source-discovered

**Inputs:** scripts/dev/lite/setup-architecture-icons.sh

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** gate-defined

**Example:** `task lite:docs:architecture:icons:check`

## `lite:docs:architecture:validate`

**Purpose:** Validate canonical architecture metadata, sources, icons, links, and accessibility

**Audience:** developer

**Dependencies:** lite:docs:architecture:icons:check

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/docs/graphviz/generate_lite_architecture.py validate`

**Environment:** None source-discovered

**Inputs:** scripts/docs/graphviz/generate_lite_architecture.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=True; safe local=True; class=heavy-dev

**Related tasks:** lite:docs:architecture:icons:check

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** gate-defined

**Example:** `task lite:docs:architecture:validate`

## `lite:docs:bootstrap`

**Purpose:** Generate bootstrap-stage documentation without executing any stage

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/docs/lite/generate_platform_catalogs.py generate --section bootstrap`

**Environment:** None source-discovered

**Inputs:** scripts/docs/lite/generate_platform_catalogs.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=True; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=False; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** not-a-validation-task

**Example:** `task lite:docs:bootstrap`

## `lite:docs:capabilities`

**Purpose:** Generate canonical device capability and role catalogs

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/docs/lite/generate_platform_catalogs.py generate --section capabilities`

**Environment:** None source-discovered

**Inputs:** scripts/docs/lite/generate_platform_catalogs.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** not-a-validation-task

**Example:** `task lite:docs:capabilities`

## `lite:docs:check`

**Purpose:** Strict combined documentation, schema, runtime, diagram, contract, safety, and MkDocs gate

**Audience:** developer

**Dependencies:** lite:dev:scratch:prepare

**Aliases:** None

**Commands:**

- `task lite:docs:tools:check`
- `task lite:contracts:check`
- `task lite:docs:platform:check`
- `task lite:docs:runtime:check`
- `task lite:docs:parity:check`
- `task lite:docs:health:check`
- `task lite:docs:knowledge:check`
- `task lite:docs:intelligence:check`
- `task lite:docs:enterprise:check`
- `task lite:docs:architecture:check`
- `task lite:docs:development:check`
- `task lite:docs:production:check`
- `{{.PYTHON}} scripts/docs/sqlite/generate_schemaspy.py check`
- `task lite:docs:diagrams:check`
- `{{.PYTHON}} -m mkdocs build --strict`

**Environment:** None source-discovered

**Inputs:** scripts/docs/sqlite/generate_schemaspy.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=True; safe local=True; class=heavy-dev

**Related tasks:** lite:contracts:check, lite:dev:scratch:prepare, lite:docs:architecture:check, lite:docs:development:check, lite:docs:diagrams:check, lite:docs:enterprise:check, lite:docs:health:check, lite:docs:intelligence:check, lite:docs:knowledge:check, lite:docs:parity:check, lite:docs:platform:check, lite:docs:production:check, lite:docs:runtime:check, lite:docs:tools:check

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** gate-defined

**Example:** `task lite:docs:check`

## `lite:docs:configuration`

**Purpose:** Generate sanitized environment-variable documentation

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/docs/lite/generate_platform_catalogs.py generate --section configuration`

**Environment:** None source-discovered

**Inputs:** scripts/docs/lite/generate_platform_catalogs.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** not-a-validation-task

**Example:** `task lite:docs:configuration`

## `lite:docs:development:check`

**Purpose:** Check Development documentation drift and safety

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/docs/lite/generate_docs.py check --audience development`

**Environment:** None source-discovered

**Inputs:** scripts/docs/lite/generate_docs.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** gate-defined

**Example:** `task lite:docs:development:check`

## `lite:docs:development:generate`

**Purpose:** Generate source-grounded Development documentation

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/docs/lite/generate_docs.py generate --audience development`

**Environment:** None source-discovered

**Inputs:** scripts/docs/lite/generate_docs.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** not-a-validation-task

**Example:** `task lite:docs:development:generate`

## `lite:docs:diagrams:check`

**Purpose:** Check Graphviz source and SVG drift

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/docs/graphviz/generate_lite_diagrams.py check`

**Environment:** None source-discovered

**Inputs:** scripts/docs/graphviz/generate_lite_diagrams.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=True; safe local=True; class=heavy-dev

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** gate-defined

**Example:** `task lite:docs:diagrams:check`

## `lite:docs:diagrams:generate`

**Purpose:** Generate linked light and dark Graphviz architecture diagrams

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/docs/graphviz/generate_lite_diagrams.py generate`

**Environment:** None source-discovered

**Inputs:** scripts/docs/graphviz/generate_lite_diagrams.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=True; safe local=True; class=heavy-dev

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** not-a-validation-task

**Example:** `task lite:docs:diagrams:generate`

## `lite:docs:enterprise:check`

**Purpose:** Check enterprise Documentation Platform determinism, page anatomy, search synonyms, sanitization, and canonical threat/release/supply-chain projections

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/docs/enterprise/generate_enterprise_documentation.py check`
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 {{.PYTHON}} -m pytest -q tests/docs/test_enterprise_documentation.py tests/docs/test_enterprise_completion.py`

**Environment:** None source-discovered

**Inputs:** scripts/docs/enterprise/generate_enterprise_documentation.py, tests/docs/test_enterprise_completion.py, tests/docs/test_enterprise_documentation.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** gate-defined

**Example:** `task lite:docs:enterprise:check`

## `lite:docs:enterprise:generate`

**Purpose:** Generate enterprise documentation intelligence, threat model, dependency visualizations, engineering handbooks, and fail-closed release/supply-chain projections

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/docs/enterprise/generate_enterprise_documentation.py generate`

**Environment:** None source-discovered

**Inputs:** scripts/docs/enterprise/generate_enterprise_documentation.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** not-a-validation-task

**Example:** `task lite:docs:enterprise:generate`

## `lite:docs:events`

**Purpose:** Generate the Lite NATS and AsyncAPI event catalog

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/docs/lite/generate_platform_catalogs.py generate --section events`

**Environment:** None source-discovered

**Inputs:** scripts/docs/lite/generate_platform_catalogs.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** not-a-validation-task

**Example:** `task lite:docs:events`

## `lite:docs:frontend-api`

**Purpose:** Generate frontend/API ownership and field-level compatibility reports

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/docs/lite/generate_platform_catalogs.py generate --section frontend-api`

**Environment:** None source-discovered

**Inputs:** scripts/docs/lite/generate_platform_catalogs.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** not-a-validation-task

**Example:** `task lite:docs:frontend-api`

## `lite:docs:generate`

**Purpose:** Generate contracts, catalogs, runtime evidence, architecture, Development/Production docs, SchemaSpy, and diagrams

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `task lite:docs:tools:check`
- `task lite:contracts:generate`
- `task lite:docs:platform:generate`
- `task lite:docs:runtime:generate`
- `task lite:docs:parity:generate`
- `task lite:docs:health:generate`
- `task lite:docs:knowledge:generate`
- `task lite:docs:intelligence:generate`
- `task lite:docs:enterprise:generate`
- `task lite:docs:architecture:generate`
- `task lite:docs:development:generate`
- `task lite:docs:production:generate`
- `{{.PYTHON}} scripts/docs/sqlite/generate_schemaspy.py generate`
- `task lite:docs:diagrams:generate`

**Environment:** None source-discovered

**Inputs:** scripts/docs/sqlite/generate_schemaspy.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=True; safe local=True; class=heavy-dev

**Related tasks:** lite:contracts:generate, lite:docs:architecture:generate, lite:docs:development:generate, lite:docs:diagrams:generate, lite:docs:enterprise:generate, lite:docs:health:generate, lite:docs:intelligence:generate, lite:docs:knowledge:generate, lite:docs:parity:generate, lite:docs:platform:generate, lite:docs:production:generate, lite:docs:runtime:generate, lite:docs:tools:check

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** not-a-validation-task

**Example:** `task lite:docs:generate`

## `lite:docs:health:check`

**Purpose:** Check release binding, schema, health/parity independence, capability roles, sanitization, and deterministic operational-health drift

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/docs/runtime/generate_domain_operational_health.py check`
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 {{.PYTHON}} -m pytest -q tests/docs/test_operational_health_bridge.py`

**Environment:** None source-discovered

**Inputs:** scripts/docs/runtime/generate_domain_operational_health.py, tests/docs/test_operational_health_bridge.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** gate-defined

**Example:** `task lite:docs:health:check`

## `lite:docs:health:generate`

**Purpose:** Generate release-bound Lite domain operational health and platform capability evidence from promoted sanitized runtime verification

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/docs/runtime/generate_domain_operational_health.py generate`

**Environment:** None source-discovered

**Inputs:** scripts/docs/runtime/generate_domain_operational_health.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** not-a-validation-task

**Example:** `task lite:docs:health:generate`

## `lite:docs:intelligence:check`

**Purpose:** Check Documentation Intelligence, UX contract, performance budgets, sanitization, and generated drift

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/docs/intelligence/generate_documentation_intelligence.py check`
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 {{.PYTHON}} -m pytest -q tests/docs/test_documentation_intelligence.py`

**Environment:** None source-discovered

**Inputs:** scripts/docs/intelligence/generate_documentation_intelligence.py, tests/docs/test_documentation_intelligence.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** gate-defined

**Example:** `task lite:docs:intelligence:check`

## `lite:docs:intelligence:generate`

**Purpose:** Generate diagnostic Documentation Intelligence and Experience views from canonical source and promoted evidence

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/docs/intelligence/generate_documentation_intelligence.py generate`

**Environment:** None source-discovered

**Inputs:** scripts/docs/intelligence/generate_documentation_intelligence.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** not-a-validation-task

**Example:** `task lite:docs:intelligence:generate`

## `lite:docs:knowledge:ai-export`

**Purpose:** Validate the sanitized deterministic AI-ready knowledge export

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/docs/knowledge/generate_knowledge.py ai-export`

**Environment:** None source-discovered

**Inputs:** scripts/docs/knowledge/generate_knowledge.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** not-a-validation-task

**Example:** `task lite:docs:knowledge:ai-export`

## `lite:docs:knowledge:check`

**Purpose:** Check knowledge schemas, graph integrity, links, sanitization, and generated drift

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/docs/knowledge/generate_knowledge.py check`

**Environment:** None source-discovered

**Inputs:** scripts/docs/knowledge/generate_knowledge.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** gate-defined

**Example:** `task lite:docs:knowledge:check`

## `lite:docs:knowledge:generate`

**Purpose:** Generate the living Pocket Lab Lite knowledge graph, AI export, and Development/Production pages

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/docs/knowledge/generate_knowledge.py generate`

**Environment:** None source-discovered

**Inputs:** scripts/docs/knowledge/generate_knowledge.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** not-a-validation-task

**Example:** `task lite:docs:knowledge:generate`

## `lite:docs:knowledge:graph`

**Purpose:** Validate the canonical knowledge graph and backlinks

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/docs/knowledge/generate_knowledge.py graph`

**Environment:** None source-discovered

**Inputs:** scripts/docs/knowledge/generate_knowledge.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** not-a-validation-task

**Example:** `task lite:docs:knowledge:graph`

## `lite:docs:knowledge:health`

**Purpose:** Validate the generated operational-health encyclopedia

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/docs/knowledge/generate_knowledge.py health`

**Environment:** None source-discovered

**Inputs:** scripts/docs/knowledge/generate_knowledge.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** not-a-validation-task

**Example:** `task lite:docs:knowledge:health`

## `lite:docs:knowledge:releases`

**Purpose:** Validate release knowledge and semantic change metadata

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/docs/knowledge/generate_knowledge.py releases`

**Environment:** None source-discovered

**Inputs:** scripts/docs/knowledge/generate_knowledge.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** not-a-validation-task

**Example:** `task lite:docs:knowledge:releases`

## `lite:docs:knowledge:traceability`

**Purpose:** Validate requirement, implementation, and test traceability

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/docs/knowledge/generate_knowledge.py traceability`

**Environment:** None source-discovered

**Inputs:** scripts/docs/knowledge/generate_knowledge.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** not-a-validation-task

**Example:** `task lite:docs:knowledge:traceability`

## `lite:docs:openapi`

**Purpose:** Export OpenAPI, generate the detailed Lite API reference, and run Redocly

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `task lite:contracts:generate`
- `{{.PYTHON}} scripts/docs/lite/generate_platform_catalogs.py generate --section openapi`
- `npx redocly lint contracts/generated/lite-openapi.json`

**Environment:** None source-discovered

**Inputs:** scripts/docs/lite/generate_platform_catalogs.py

**Outputs:** contracts/generated/lite-openapi.json

**Generated artifacts:** contracts/generated/lite-openapi.json

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** lite:contracts:generate

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** not-a-validation-task

**Example:** `task lite:docs:openapi`

## `lite:docs:platform:check`

**Purpose:** Check all lightweight source-derived catalog drift and safety

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/docs/lite/generate_platform_catalogs.py check --section all`

**Environment:** None source-discovered

**Inputs:** scripts/docs/lite/generate_platform_catalogs.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** gate-defined

**Example:** `task lite:docs:platform:check`

## `lite:docs:platform:generate`

**Purpose:** Generate all lightweight source-derived catalogs in one bounded process

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/docs/lite/generate_platform_catalogs.py generate --section all`

**Environment:** None source-discovered

**Inputs:** scripts/docs/lite/generate_platform_catalogs.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** not-a-validation-task

**Example:** `task lite:docs:platform:generate`

## `lite:docs:production:check`

**Purpose:** Check Production documentation drift and partial/planned boundaries

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/docs/lite/generate_docs.py check --audience production`

**Environment:** None source-discovered

**Inputs:** scripts/docs/lite/generate_docs.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** gate-defined

**Example:** `task lite:docs:production:check`

## `lite:docs:production:generate`

**Purpose:** Generate verified deployable Production user documentation

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/docs/lite/generate_docs.py generate --audience production`

**Environment:** None source-discovered

**Inputs:** scripts/docs/lite/generate_docs.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** not-a-validation-task

**Example:** `task lite:docs:production:generate`

## `lite:docs:projections`

**Purpose:** Generate the prepared-projection ownership and freshness catalog

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/docs/lite/generate_platform_catalogs.py generate --section projections`

**Environment:** None source-discovered

**Inputs:** scripts/docs/lite/generate_platform_catalogs.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** not-a-validation-task

**Example:** `task lite:docs:projections`

## `lite:docs:provenance:generate`

**Purpose:** Generate SLSA-style release provenance metadata without claiming a formal SLSA level or signing implicitly

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/docs/enterprise/release_provenance.py generate`

**Environment:** None source-discovered

**Inputs:** scripts/docs/enterprise/release_provenance.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** not-a-validation-task

**Example:** `task lite:docs:provenance:generate`

## `lite:docs:provenance:sign`

**Purpose:** Explicitly sign a release artifact with Cosign keyless/default Sigstore flow; ARTIFACT and BUNDLE are required and no private key is stored by the task

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `test -n "{{.ARTIFACT}}" && test -n "{{.BUNDLE}}" || (echo "ARTIFACT and BUNDLE are required" >&2; exit 2)`
- `{{.PYTHON}} scripts/docs/enterprise/release_provenance.py sign --artifact {{.ARTIFACT}} --bundle {{.BUNDLE}}`

**Environment:** None source-discovered

**Inputs:** scripts/docs/enterprise/release_provenance.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** not-a-validation-task

**Example:** `task lite:docs:provenance:sign`

## `lite:docs:provenance:sign-release-set`

**Purpose:** Explicitly sign all applicable local release artifacts (dist.zip, release manifest, CycloneDX SBOMs, provenance) into transient Sigstore bundles

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/docs/enterprise/release_provenance.py sign-release-set {{if .SIGNATURE_DIR}}--directory {{.SIGNATURE_DIR}}{{end}}`

**Environment:** None source-discovered

**Inputs:** scripts/docs/enterprise/release_provenance.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** not-a-validation-task

**Example:** `task lite:docs:provenance:sign-release-set`

## `lite:docs:provenance:verify`

**Purpose:** Explicitly verify a Cosign/Sigstore blob bundle against the expected certificate identity and OIDC issuer

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `test -n "{{.ARTIFACT}}" && test -n "{{.BUNDLE}}" && test -n "{{.IDENTITY}}" && test -n "{{.ISSUER}}" || (echo "ARTIFACT, BUNDLE, IDENTITY and ISSUER are required" >&2; exit 2)`
- `{{.PYTHON}} scripts/docs/enterprise/release_provenance.py verify --artifact {{.ARTIFACT}} --bundle {{.BUNDLE}} --identity {{.IDENTITY}} --issuer {{.ISSUER}}`

**Environment:** None source-discovered

**Inputs:** scripts/docs/enterprise/release_provenance.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** gate-defined

**Example:** `task lite:docs:provenance:verify`

## `lite:docs:provenance:verify-release-set`

**Purpose:** Verify every release-set Sigstore bundle and optionally promote only sanitized verification evidence into the canonical release documentation contract

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `test -n "{{.IDENTITY}}" && test -n "{{.ISSUER}}" || (echo "IDENTITY and ISSUER are required" >&2; exit 2)`
- `{{.PYTHON}} scripts/docs/enterprise/release_provenance.py verify-release-set {{if .SIGNATURE_DIR}}--directory {{.SIGNATURE_DIR}}{{end}} --identity {{.IDENTITY}} --issuer {{.ISSUER}} {{if .PROMOTE}}--promote{{end}}`

**Environment:** None source-discovered

**Inputs:** scripts/docs/enterprise/release_provenance.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** gate-defined

**Example:** `task lite:docs:provenance:verify-release-set`

## `lite:docs:reason-codes`

**Purpose:** Generate and validate the canonical reason-code registry

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/docs/lite/generate_platform_catalogs.py generate --section reason-codes`

**Environment:** None source-discovered

**Inputs:** scripts/docs/lite/generate_platform_catalogs.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** not-a-validation-task

**Example:** `task lite:docs:reason-codes`

## `lite:docs:recovery`

**Purpose:** Generate Recovery contract and state-machine references

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/docs/lite/generate_platform_catalogs.py generate --section recovery`

**Environment:** None source-discovered

**Inputs:** scripts/docs/lite/generate_platform_catalogs.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** not-a-validation-task

**Example:** `task lite:docs:recovery`

## `lite:docs:redaction`

**Purpose:** Generate consolidated redaction and secret-safety coverage

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/docs/lite/generate_platform_catalogs.py generate --section redaction`

**Environment:** None source-discovered

**Inputs:** scripts/docs/lite/generate_platform_catalogs.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** not-a-validation-task

**Example:** `task lite:docs:redaction`

## `lite:docs:release-evidence`

**Purpose:** Generate release documents only from verified release manifests

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/docs/lite/generate_platform_catalogs.py generate --section release`

**Environment:** None source-discovered

**Inputs:** scripts/docs/lite/generate_platform_catalogs.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** not-a-validation-task

**Example:** `task lite:docs:release-evidence`

## `lite:docs:runtime:check`

**Purpose:** Check promoted runtime baseline schemas, redaction, determinism, and generated drift

**Audience:** developer/operator

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/docs/runtime/generate_termux_runtime_docs.py check`
- `{{.PYTHON}} scripts/docs/runtime/runtime_redaction.py --paths architecture/runtime-baselines contracts/generated/runtime docs/generated/development/runtime-verification.md docs/generated/production/android-termux-runtime.md docs/generated/production/services-pm2-runtime.md docs/generated/production/remote-access-runtime.md`

**Environment:** None source-discovered

**Inputs:** architecture/runtime-baselines, scripts/docs/runtime/generate_termux_runtime_docs.py, scripts/docs/runtime/runtime_redaction.py

**Outputs:** contracts/generated/runtime, docs/generated/development/runtime-verification.md, docs/generated/production/android-termux-runtime.md, docs/generated/production/remote-access-runtime.md, docs/generated/production/services-pm2-runtime.md

**Generated artifacts:** contracts/generated/runtime, docs/generated/development/runtime-verification.md, docs/generated/production/android-termux-runtime.md, docs/generated/production/remote-access-runtime.md, docs/generated/production/services-pm2-runtime.md

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** gate-defined

**Example:** `task lite:docs:runtime:check`

## `lite:docs:runtime:generate`

**Purpose:** Generate tracked runtime contracts and pages from the promoted baseline only

**Audience:** developer/operator

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/docs/runtime/generate_termux_runtime_docs.py generate`

**Environment:** None source-discovered

**Inputs:** scripts/docs/runtime/generate_termux_runtime_docs.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** not-a-validation-task

**Example:** `task lite:docs:runtime:generate`

## `lite:docs:security`

**Purpose:** Generate canonical Security profile documentation

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/docs/lite/generate_platform_catalogs.py generate --section security`

**Environment:** None source-discovered

**Inputs:** scripts/docs/lite/generate_platform_catalogs.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** not-a-validation-task

**Example:** `task lite:docs:security`

## `lite:docs:security-tools:check`

**Purpose:** Check existing Graphviz/SchemaSpy prerequisites plus pinned heavy Documentation Platform security/supply-chain tools on WSL2/CI without installing or upgrading them

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `bash scripts/dev/lite/setup-documentation-tools.sh --check`
- `bash scripts/dev/lite/check-documentation-security-tools.sh`

**Environment:** None source-discovered

**Inputs:** scripts/dev/lite/check-documentation-security-tools.sh, scripts/dev/lite/setup-documentation-tools.sh

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** gate-defined

**Example:** `task lite:docs:security-tools:check`

## `lite:docs:security-tools:plan`

**Purpose:** Show the pinned architecture-aware WSL2/CI security-tool installation plan without downloading anything

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `bash scripts/dev/lite/setup-documentation-security-tools.sh --plan`

**Environment:** None source-discovered

**Inputs:** scripts/dev/lite/setup-documentation-security-tools.sh

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** not-a-validation-task

**Example:** `task lite:docs:security-tools:plan`

## `lite:docs:security-tools:setup`

**Purpose:** Install missing pinned Documentation Platform security/supply-chain tools plus the existing Graphviz/SchemaSpy documentation prerequisites on WSL2/CI without upgrading working tools

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `bash scripts/dev/lite/setup-documentation-tools.sh --install-missing`
- `bash scripts/dev/lite/setup-documentation-security-tools.sh --install-missing`

**Environment:** None source-discovered

**Inputs:** scripts/dev/lite/setup-documentation-security-tools.sh, scripts/dev/lite/setup-documentation-tools.sh

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=True; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=False; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** not-a-validation-task

**Example:** `task lite:docs:security-tools:setup`

## `lite:docs:security-tools:update`

**Purpose:** Explicitly update/replace mismatched Documentation Platform security tools to the canonical reviewed pins; never runs automatically

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `bash scripts/dev/lite/setup-documentation-security-tools.sh --update`

**Environment:** None source-discovered

**Inputs:** scripts/dev/lite/setup-documentation-security-tools.sh

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** not-a-validation-task

**Example:** `task lite:docs:security-tools:update`

## `lite:docs:serve`

**Purpose:** Serve combined Development and Production docs locally

**Audience:** developer

**Dependencies:** lite:dev:scratch:prepare

**Aliases:** None

**Commands:**

- `bash scripts/dev/lite/serve-docs.sh`

**Environment:** None source-discovered

**Inputs:** scripts/dev/lite/serve-docs.sh

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** lite:dev:scratch:prepare

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** not-a-validation-task

**Example:** `task lite:docs:serve`

## `lite:docs:services`

**Purpose:** Generate the approved PM2 service catalog

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/docs/lite/generate_platform_catalogs.py generate --section services`

**Environment:** None source-discovered

**Inputs:** scripts/docs/lite/generate_platform_catalogs.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** not-a-validation-task

**Example:** `task lite:docs:services`

## `lite:docs:sqlite`

**Purpose:** Generate data-free SQLite metadata and normalized SchemaSpy documentation

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/docs/lite/generate_platform_catalogs.py generate --section sqlite`
- `{{.PYTHON}} scripts/docs/sqlite/generate_schemaspy.py generate`

**Environment:** None source-discovered

**Inputs:** scripts/docs/lite/generate_platform_catalogs.py, scripts/docs/sqlite/generate_schemaspy.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=True; safe local=True; class=heavy-dev

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** not-a-validation-task

**Example:** `task lite:docs:sqlite`

## `lite:docs:sqlite:check`

**Purpose:** Check data-free SQLite metadata and SchemaSpy drift

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/docs/lite/generate_platform_catalogs.py check --section sqlite`
- `{{.PYTHON}} scripts/docs/sqlite/generate_schemaspy.py check`

**Environment:** None source-discovered

**Inputs:** scripts/docs/lite/generate_platform_catalogs.py, scripts/docs/sqlite/generate_schemaspy.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=True; safe local=True; class=heavy-dev

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** gate-defined

**Example:** `task lite:docs:sqlite:check`

## `lite:docs:supply-chain:capture`

**Purpose:** Explicitly run heavy WSL2/CI SBOM, vulnerability, secret, static-analysis, licensing and Scorecard capture into transient .pocketlab-dev evidence; never invoked by docs generation

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/docs/enterprise/supply_chain_automation.py capture {{if .RUN_DIR}}--run-dir {{.RUN_DIR}}{{end}} {{if .INCLUDE_GIT_HISTORY}}--include-git-history{{end}}`

**Environment:** None source-discovered

**Inputs:** scripts/docs/enterprise/supply_chain_automation.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** not-a-validation-task

**Example:** `task lite:docs:supply-chain:capture`

## `lite:docs:supply-chain:check`

**Purpose:** Validate already-promoted canonical supply-chain evidence without running scanners or accessing runtime

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/docs/enterprise/supply_chain_automation.py check`

**Environment:** None source-discovered

**Inputs:** scripts/docs/enterprise/supply_chain_automation.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** gate-defined

**Example:** `task lite:docs:supply-chain:check`

## `lite:docs:supply-chain:dependency-track:export`

**Purpose:** Stage canonical CycloneDX files for optional Dependency-Track import; MkDocs never depends on the external service

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/docs/enterprise/supply_chain_automation.py dependency-track-export`

**Environment:** None source-discovered

**Inputs:** scripts/docs/enterprise/supply_chain_automation.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** not-a-validation-task

**Example:** `task lite:docs:supply-chain:dependency-track:export`

## `lite:docs:supply-chain:promote`

**Purpose:** Explicitly normalize and promote a reviewed WSL2/CI supply-chain capture into sanitized canonical CycloneDX/security contracts

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `test -n "{{.RUN_DIR}}" || (echo "RUN_DIR is required, e.g. task lite:docs:supply-chain:promote RUN_DIR=.pocketlab-dev/documentation-security/runs/<run>" >&2; exit 2)`
- `{{.PYTHON}} scripts/docs/enterprise/supply_chain_automation.py promote --run-dir {{.RUN_DIR}}`

**Environment:** None source-discovered

**Inputs:** scripts/docs/enterprise/supply_chain_automation.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=True

**Runtime:** requires Termux=False; requires WSL2=False; safe local=False; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** not-a-validation-task

**Example:** `task lite:docs:supply-chain:promote`

## `lite:docs:supply-chain:qualify`

**Purpose:** Explicitly run heavy WSL2/CI supply-chain capture, normalize/promote sanitized evidence, and validate canonical outputs in one operator-invoked workflow

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `set -euo pipefail
run_dir=".pocketlab-dev/documentation-security/runs/manual-$(date -u +%Y%m%dT%H%M%SZ)-$$"
history_arg=""
if [ -n "{{.INCLUDE_GIT_HISTORY}}" ]; then history_arg="--include-git-history"; fi
{{.PYTHON}} scripts/docs/enterprise/supply_chain_automation.py capture --run-dir "$run_dir" $history_arg
{{.PYTHON}} scripts/docs/enterprise/supply_chain_automation.py promote --run-dir "$run_dir"
{{.PYTHON}} scripts/docs/enterprise/supply_chain_automation.py check
printf 'Canonical supply-chain evidence promoted from %s\n' "$run_dir"
`

**Environment:** None source-discovered

**Inputs:** scripts/docs/enterprise/supply_chain_automation.py

**Outputs:** .pocketlab-dev/documentation-security/runs/manual-

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=True; promotes evidence=True

**Runtime:** requires Termux=False; requires WSL2=False; safe local=False; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** not-a-validation-task

**Example:** `task lite:docs:supply-chain:qualify`

## `lite:docs:sync`

**Purpose:** Regenerate the complete tracked Documentation Platform from canonical sources and the promoted runtime baseline, then run the strict drift/safety/MkDocs gate

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `task lite:docs:generate`
- `task lite:docs:check`

**Environment:** None source-discovered

**Inputs:** No explicit file inputs discovered

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** lite:docs:check, lite:docs:generate

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** not-a-validation-task

**Example:** `task lite:docs:sync`

## `lite:docs:tools:check`

**Purpose:** Verify pinned development-only documentation tools without changing the host

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `bash scripts/dev/lite/setup-documentation-tools.sh --check`

**Environment:** None source-discovered

**Inputs:** scripts/dev/lite/setup-documentation-tools.sh

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** gate-defined

**Example:** `task lite:docs:tools:check`

## `lite:docs:ui`

**Purpose:** Generate the canonical Storybook UI-state catalog

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/docs/lite/generate_platform_catalogs.py generate --section ui`

**Environment:** None source-discovered

**Inputs:** scripts/docs/lite/generate_platform_catalogs.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** not-a-validation-task

**Example:** `task lite:docs:ui`

## `lite:docs:ui:screenshots`

**Purpose:** Build Storybook once and capture bounded mobile and desktop documentation screenshots

**Audience:** developer

**Dependencies:** lite:playwright:preflight

**Aliases:** None

**Commands:**

- `npm run build-storybook`
- `node scripts/docs/lite/capture-storybook.mjs`

**Environment:** None source-discovered

**Inputs:** scripts/docs/lite/capture-storybook.mjs

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** lite:playwright:preflight

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** not-a-validation-task

**Example:** `task lite:docs:ui:screenshots`

## `lite:docs:validation`

**Purpose:** Generate readiness documentation only from recorded validation evidence

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/docs/lite/generate_platform_catalogs.py generate --section validation`

**Environment:** None source-discovered

**Inputs:** scripts/docs/lite/generate_platform_catalogs.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** not-a-validation-task

**Example:** `task lite:docs:validation`

## `lite:runtime:ssh:check`

**Purpose:** Verify the managed private, key-only, host-key-checked Termux SSH alias

**Audience:** developer/operator

**Dependencies:** None

**Aliases:** None

**Commands:**

- `bash scripts/docs/runtime/check_termux_ssh.sh`

**Environment:** None source-discovered

**Inputs:** scripts/docs/runtime/check_termux_ssh.sh

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** gate-defined

**Example:** `task lite:runtime:ssh:check`

## `lite:runtime:ssh:setup`

**Purpose:** Configure the managed WSL-only Termux SSH alias after explicit host-key approval

**Audience:** developer/operator

**Dependencies:** None

**Aliases:** None

**Commands:**

- `bash scripts/docs/runtime/setup_termux_ssh.sh --configure`

**Environment:** None source-discovered

**Inputs:** scripts/docs/runtime/setup_termux_ssh.sh

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** not-a-validation-task

**Example:** `task lite:runtime:ssh:setup`

## `lite:runtime:termux:capture`

**Purpose:** Run one bounded read-only SSH probe and create a local sanitized projection

**Audience:** developer/operator

**Dependencies:** None

**Aliases:** None

**Commands:**

- `bash scripts/docs/runtime/capture_termux_runtime.sh`

**Environment:** None source-discovered

**Inputs:** scripts/docs/runtime/capture_termux_runtime.sh

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=True; promotes evidence=False

**Runtime:** requires Termux=True; requires WSL2=False; safe local=False; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** not-a-validation-task

**Example:** `task lite:runtime:termux:capture`

## `lite:runtime:termux:clean`

**Purpose:** Remove transient raw layers and stale local captures idempotently

**Audience:** developer/operator

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/docs/runtime/promote_termux_runtime.py clean`

**Environment:** None source-discovered

**Inputs:** scripts/docs/runtime/promote_termux_runtime.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=True

**Runtime:** requires Termux=False; requires WSL2=False; safe local=False; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** not-a-validation-task

**Example:** `task lite:runtime:termux:clean`

## `lite:runtime:termux:diff`

**Purpose:** Show a semantic path-only diff against the promoted runtime baseline

**Audience:** developer/operator

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/docs/runtime/promote_termux_runtime.py diff`

**Environment:** None source-discovered

**Inputs:** scripts/docs/runtime/promote_termux_runtime.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=True

**Runtime:** requires Termux=False; requires WSL2=False; safe local=False; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** not-a-validation-task

**Example:** `task lite:runtime:termux:diff`

## `lite:runtime:termux:inspect`

**Purpose:** Inspect the latest safe local Termux projection without printing identities

**Audience:** developer/operator

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/docs/runtime/promote_termux_runtime.py inspect`

**Environment:** None source-discovered

**Inputs:** scripts/docs/runtime/promote_termux_runtime.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=True

**Runtime:** requires Termux=False; requires WSL2=False; safe local=False; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** not-a-validation-task

**Example:** `task lite:runtime:termux:inspect`

## `lite:runtime:termux:promote`

**Purpose:** Explicitly promote the latest safe projection; requires LITE_RUNTIME_PROMOTE=1

**Audience:** developer/operator

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/docs/runtime/promote_termux_runtime.py promote`

**Environment:** None source-discovered

**Inputs:** scripts/docs/runtime/promote_termux_runtime.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=True

**Runtime:** requires Termux=False; requires WSL2=False; safe local=False; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** not-a-validation-task

**Example:** `task lite:runtime:termux:promote`

## `lite:runtime:termux:validate`

**Purpose:** Validate the latest sanitized projection and candidate baseline

**Audience:** developer/operator

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/docs/runtime/promote_termux_runtime.py validate`

**Environment:** None source-discovered

**Inputs:** scripts/docs/runtime/promote_termux_runtime.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=True

**Runtime:** requires Termux=False; requires WSL2=False; safe local=False; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** gate-defined

**Example:** `task lite:runtime:termux:validate`

## `lite:test:docs`

**Purpose:** Validate the MkDocs portal in external Chrome on desktop and mobile

**Audience:** developer

**Dependencies:** lite:dev:scratch:prepare, lite:playwright:preflight

**Aliases:** None

**Commands:**

- `npm run test:docs`

**Environment:** None source-discovered

**Inputs:** No explicit file inputs discovered

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** lite:dev:scratch:prepare, lite:playwright:preflight

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** gate-defined

**Example:** `task lite:test:docs`

## `lite:allure`

**Purpose:** Generate Allure-compatible results plus a bounded local HTML evidence index

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `task lite:validation:evidence`
- `{{.PYTHON}} scripts/dev/lite/validation_evidence.py html --validation-dir "{{.VALIDATION_DIR}}" --output allure-report`

**Environment:** None source-discovered

**Inputs:** scripts/dev/lite/validation_evidence.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** lite:validation:evidence

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** not-a-validation-task

**Example:** `task lite:allure`

## `lite:api:check`

**Purpose:** Compatibility alias for the established Lite API check

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `bash scripts/dev/check-lite-api.sh`

**Environment:** None source-discovered

**Inputs:** scripts/dev/check-lite-api.sh

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** gate-defined

**Example:** `task lite:api:check`

## `lite:bootstrap:check`

**Purpose:** Validate Lite bootstrap profile selection and dry-run behavior

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `bash scripts/dev/check-lite-bootstrap.sh`

**Environment:** None source-discovered

**Inputs:** scripts/dev/check-lite-bootstrap.sh

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=True; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=False; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** gate-defined

**Example:** `task lite:bootstrap:check`

## `lite:browser:detect`

**Purpose:** Resolve and print the supported browser used by WSL2 development tasks

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `node scripts/dev/lite/resolve-browser.mjs --json`

**Environment:** None source-discovered

**Inputs:** scripts/dev/lite/resolve-browser.mjs

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** not-a-validation-task

**Example:** `task lite:browser:detect`

## `lite:check`

**Purpose:** Full local Lite gate including backend/frontend, Storybook, mocked browser, redaction, contracts, and strict docs

**Audience:** developer

**Dependencies:** lite:dev:scratch:prepare

**Aliases:** None

**Commands:**

- `bash scripts/dev/lite/run-gate.sh full`

**Environment:** None source-discovered

**Inputs:** scripts/dev/lite/run-gate.sh

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** lite:dev:scratch:prepare

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** gate-defined

**Example:** `task lite:check`

## `lite:check:quick`

**Purpose:** Fast developer gate: compile, shell syntax, focused tests, contracts, PWA build, and cheap doc drift

**Audience:** developer

**Dependencies:** lite:dev:scratch:prepare

**Aliases:** None

**Commands:**

- `bash scripts/dev/lite/run-gate.sh quick`

**Environment:** None source-discovered

**Inputs:** scripts/dev/lite/run-gate.sh

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** lite:dev:scratch:prepare

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** gate-defined

**Example:** `task lite:check:quick`

## `lite:check:release`

**Purpose:** Release qualification gate; requires an explicitly running live Lite stack

**Audience:** developer

**Dependencies:** lite:dev:scratch:prepare

**Aliases:** None

**Commands:**

- `bash scripts/dev/lite/run-gate.sh release`

**Environment:** None source-discovered

**Inputs:** scripts/dev/lite/run-gate.sh

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** lite:dev:scratch:prepare

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** gate-defined

**Example:** `task lite:check:release`

## `lite:dev:backend`

**Purpose:** Start FastAPI directly for development

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `bash scripts/dev/run-fastapi-dev.sh`

**Environment:** None source-discovered

**Inputs:** scripts/dev/run-fastapi-dev.sh

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** not-a-validation-task

**Example:** `task lite:dev:backend`

## `lite:dev:down`

**Purpose:** Stop the Lite development stack

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `bash scripts/dev/down.sh`

**Environment:** None source-discovered

**Inputs:** scripts/dev/down.sh

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** not-a-validation-task

**Example:** `task lite:dev:down`

## `lite:dev:frontend`

**Purpose:** Start Vite on the configured development URL

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `npm run dev -- --host 127.0.0.1`

**Environment:** None source-discovered

**Inputs:** No explicit file inputs discovered

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** not-a-validation-task

**Example:** `task lite:dev:frontend`

## `lite:dev:frontend:mocked`

**Purpose:** Start Vite with deterministic Lite MSW scenarios

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `npm run dev:mock`

**Environment:** None source-discovered

**Inputs:** No explicit file inputs discovered

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** not-a-validation-task

**Example:** `task lite:dev:frontend:mocked`

## `lite:dev:logs`

**Purpose:** Tail Lite development stack logs

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `bash scripts/dev/logs.sh`

**Environment:** None source-discovered

**Inputs:** scripts/dev/logs.sh

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** not-a-validation-task

**Example:** `task lite:dev:logs`

## `lite:dev:nats`

**Purpose:** Start the Lite NATS/JetStream development service

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `bash scripts/dev/run-nats-dev.sh`

**Environment:** None source-discovered

**Inputs:** scripts/dev/run-nats-dev.sh

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** not-a-validation-task

**Example:** `task lite:dev:nats`

## `lite:dev:status`

**Purpose:** Show Lite development stack status

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `bash scripts/dev/status.sh`

**Environment:** None source-discovered

**Inputs:** scripts/dev/status.sh

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** not-a-validation-task

**Example:** `task lite:dev:status`

## `lite:dev:up`

**Purpose:** Start the existing Lite NATS, FastAPI, worker, and Vite development stack

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `bash scripts/dev/up.sh`

**Environment:** None source-discovered

**Inputs:** scripts/dev/up.sh

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** not-a-validation-task

**Example:** `task lite:dev:up`

## `lite:dev:worker`

**Purpose:** Start the Lite worker directly for development

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `bash scripts/dev/run-worker-dev.sh`

**Environment:** None source-discovered

**Inputs:** scripts/dev/run-worker-dev.sh

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** not-a-validation-task

**Example:** `task lite:dev:worker`

## `lite:har:inspect`

**Purpose:** Inspect a sanitized HAR for sync, duplicates, failures, and heavy first-paint requests

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/dev/lite/har_tool.py inspect --input "{{.INPUT}}"`

**Environment:** None source-discovered

**Inputs:** scripts/dev/lite/har_tool.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** not-a-validation-task

**Example:** `task lite:har:inspect`

## `lite:har:sanitize`

**Purpose:** Sanitize a Playwright HAR. Usage: task lite:har:sanitize INPUT=path.har OUTPUT=path.sanitized.har

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/dev/lite/har_tool.py sanitize --input "{{.INPUT}}" {{if .OUTPUT}}--output "{{.OUTPUT}}"{{end}}`

**Environment:** None source-discovered

**Inputs:** scripts/dev/lite/har_tool.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** not-a-validation-task

**Example:** `task lite:har:sanitize`

## `lite:playwright:preflight`

**Purpose:** Validate the external WSL2 browser and record path/version evidence

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `node scripts/dev/lite/resolve-browser.mjs --write-evidence "{{.VALIDATION_DIR}}/browser.json"`

**Environment:** None source-discovered

**Inputs:** scripts/dev/lite/resolve-browser.mjs

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=True; safe local=True; class=heavy-dev

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** not-a-validation-task

**Example:** `task lite:playwright:preflight`

## `lite:setup`

**Purpose:** Install only missing repository development dependencies without upgrading protected tools

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `bash scripts/dev/lite/setup.sh`

**Environment:** None source-discovered

**Inputs:** scripts/dev/lite/setup.sh

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** not-a-validation-task

**Example:** `task lite:setup`

## `lite:setup:check`

**Purpose:** Verify repository dependencies and protected development-tool versions

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `bash scripts/dev/lite/setup-check.sh`

**Environment:** None source-discovered

**Inputs:** scripts/dev/lite/setup-check.sh

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** gate-defined

**Example:** `task lite:setup:check`

## `lite:setup:system`

**Purpose:** Explain optional system packages; never installs or invokes sudo silently

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `bash scripts/dev/lite/setup-system.sh`

**Environment:** None source-discovered

**Inputs:** scripts/dev/lite/setup-system.sh

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** not-a-validation-task

**Example:** `task lite:setup:system`

## `lite:test:android`

**Purpose:** Run the existing Android/Termux smoke helper; requires explicit SSH/device configuration

**Audience:** developer/operator

**Dependencies:** None

**Aliases:** None

**Commands:**

- `bash scripts/dev/android-termux-smoke.sh`

**Environment:** None source-discovered

**Inputs:** scripts/dev/android-termux-smoke.sh

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** gate-defined

**Example:** `task lite:test:android`

## `lite:test:backend`

**Purpose:** Run the focused Lite backend API, Recovery, and Security suites

**Audience:** developer

**Dependencies:** lite:dev:scratch:prepare

**Aliases:** None

**Commands:**

- `PYTHONPATH=tests:pocket-lab-final-structure/runtime PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 {{.PYTHON}} -m pytest -q tests/backend/test_lite_api.py tests/backend/test_lite_recovery.py tests/backend/test_lite_security.py`

**Environment:** None source-discovered

**Inputs:** tests/backend/test_lite_api.py, tests/backend/test_lite_recovery.py, tests/backend/test_lite_security.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** lite:dev:scratch:prepare

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** gate-defined

**Example:** `task lite:test:backend`

## `lite:test:contracts`

**Purpose:** Export and validate Lite OpenAPI, fixtures, frontend routes, reason codes, and compatibility

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `bash scripts/dev/lite/check-contracts.sh`

**Environment:** None source-discovered

**Inputs:** scripts/dev/lite/check-contracts.sh

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** gate-defined

**Example:** `task lite:test:contracts`

## `lite:test:frontend`

**Purpose:** Run all frontend unit tests

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `npm run test:unit`

**Environment:** None source-discovered

**Inputs:** No explicit file inputs discovered

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** gate-defined

**Example:** `task lite:test:frontend`

## `lite:test:redaction`

**Purpose:** Check generated docs, fixtures, HARs, traces, and validation evidence for forbidden secret material

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/dev/lite/redaction_check.py --paths contracts/generated src/test/fixtures/generated docs/generated "{{.VALIDATION_DIR}}"`

**Environment:** None source-discovered

**Inputs:** scripts/dev/lite/redaction_check.py, src/test/fixtures/generated

**Outputs:** contracts/generated, docs/generated

**Generated artifacts:** contracts/generated, docs/generated

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** gate-defined

**Example:** `task lite:test:redaction`

## `lite:test:runtime`

**Purpose:** Run non-destructive Lite runtime and prepared-projection contract tests

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `PYTHONPATH=tests:pocket-lab-final-structure/runtime PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 {{.PYTHON}} -m pytest -q tests/backend/test_lite_fastapi_runtime_diagnostics.py tests/backend/test_lite_projection_semantic_hardening.py tests/backend/test_nats_required.py`

**Environment:** None source-discovered

**Inputs:** tests/backend/test_lite_fastapi_runtime_diagnostics.py, tests/backend/test_lite_projection_semantic_hardening.py, tests/backend/test_nats_required.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** gate-defined

**Example:** `task lite:test:runtime`

## `lite:validation:check`

**Purpose:** Verify validation evidence is sanitized and contains no unrecorded PASS claims

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/dev/lite/redaction_check.py --paths "{{.VALIDATION_DIR}}" allure-results allure-report`
- `{{.PYTHON}} -c "import json,pathlib; p=pathlib.Path(\"{{.VALIDATION_DIR}}/readiness-matrix.json\"); d=json.loads(p.read_text()); assert d[\"status\"] in {\"passed\",\"failed\",\"not_run\"}; print(\"PASS validation evidence index is coherent\")"`

**Environment:** None source-discovered

**Inputs:** scripts/dev/lite/redaction_check.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** gate-defined

**Example:** `task lite:validation:check`

## `lite:validation:evidence`

**Purpose:** Generate Allure-compatible results, validation manifest, readiness matrix, and artifact index

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/dev/lite/validation_evidence.py allure --validation-dir "{{.VALIDATION_DIR}}" --output allure-results`

**Environment:** None source-discovered

**Inputs:** scripts/dev/lite/validation_evidence.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** not-a-validation-task

**Example:** `task lite:validation:evidence`

## `lite:validation:record`

**Purpose:** Record one bounded validation command. Usage: task lite:validation:record NAME=gate COMMAND="command args"

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/dev/lite/validation_evidence.py run --name "{{.NAME}}" --validation-dir "{{.VALIDATION_DIR}}" -- bash -lc "{{.COMMAND}}"`

**Environment:** None source-discovered

**Inputs:** scripts/dev/lite/validation_evidence.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** not-a-validation-task

**Example:** `task lite:validation:record`

## `lite:a11y:check`

**Purpose:** Run the existing mocked accessibility gate

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `task lite:test:a11y`

**Environment:** None source-discovered

**Inputs:** No explicit file inputs discovered

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** lite:test:a11y

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** gate-defined

**Example:** `task lite:a11y:check`

## `lite:api:breaking-changes`

**Purpose:** Check the current OpenAPI contract against an explicitly promoted baseline

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `bash scripts/test/parity/run_oasdiff.sh`

**Environment:** None source-discovered

**Inputs:** scripts/test/parity/run_oasdiff.sh

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=True; safe local=True; class=heavy-dev

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** not-a-validation-task

**Example:** `task lite:api:breaking-changes`

## `lite:api:read-latency`

**Purpose:** Capture bounded cold and warm read latency evidence from the configured loopback API

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/test/parity/probe_read_latency.py --base-url "{{.LITE_PARITY_API_URL}}" --output "{{.VALIDATION_DIR}}/parity/read-latency.json" --samples 3 --timeout 30`

**Environment:** LITE_PARITY_API_URL

**Inputs:** scripts/test/parity/probe_read_latency.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** not-a-validation-task

**Example:** `task lite:api:read-latency`

## `lite:api:schemathesis`

**Purpose:** Run bounded read-only Schemathesis checks against safe Recovery GET endpoints

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `LITE_API_DIRECT_URL="{{.LITE_PARITY_API_URL}}" LITE_PARITY_OPENAPI_URL="{{.LITE_PARITY_API_URL}}/openapi.json" bash scripts/test/parity/run_schemathesis.sh`

**Environment:** LITE_API_DIRECT_URL, LITE_PARITY_API_URL, LITE_PARITY_OPENAPI_URL

**Inputs:** scripts/test/parity/run_schemathesis.sh

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=True; safe local=True; class=heavy-dev

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** not-a-validation-task

**Example:** `task lite:api:schemathesis`

## `lite:api:schemathesis:discovery`

**Purpose:** Record broad read-only API/OpenAPI conformance findings without gating parity

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `LITE_API_DIRECT_URL="{{.LITE_PARITY_API_URL}}" LITE_PARITY_OPENAPI_URL="{{.LITE_PARITY_API_URL}}/openapi.json" bash scripts/test/parity/run_schemathesis_discovery.sh`

**Environment:** LITE_API_DIRECT_URL, LITE_PARITY_API_URL, LITE_PARITY_OPENAPI_URL

**Inputs:** scripts/test/parity/run_schemathesis_discovery.sh

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=True; safe local=True; class=heavy-dev

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** not-a-validation-task

**Example:** `task lite:api:schemathesis:discovery`

## `lite:docs:parity:check`

**Purpose:** Check deterministic generated parity documentation and MkDocs navigation linkage

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/docs/parity/generate_parity.py check`
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 {{.PYTHON}} -m pytest -q tests/parity/test_contract_generation.py -k generated_documentation`

**Environment:** None source-discovered

**Inputs:** scripts/docs/parity/generate_parity.py, tests/parity/test_contract_generation.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** gate-defined

**Example:** `task lite:docs:parity:check`

## `lite:docs:parity:generate`

**Purpose:** Generate the complete Development parity portfolio and Production readiness page

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/docs/parity/generate_parity.py generate`

**Environment:** None source-discovered

**Inputs:** scripts/docs/parity/generate_parity.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** not-a-validation-task

**Example:** `task lite:docs:parity:generate`

## `lite:docs:parity:local`

**Purpose:** Render the latest sanitized local runtime comparison without promoting it

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `.venv/bin/python scripts/docs/parity/render_local_runtime_comparison.py generate`

**Environment:** None source-discovered

**Inputs:** .venv/bin/python, scripts/docs/parity/render_local_runtime_comparison.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** not-a-validation-task

**Example:** `task lite:docs:parity:local`

## `lite:docs:parity:local:check`

**Purpose:** Check the latest local runtime comparison report against current local evidence

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `.venv/bin/python scripts/docs/parity/render_local_runtime_comparison.py check`
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -q tests/parity/test_local_runtime_report.py`
- `node --test tests/dev/runtime-evidence-sanitizer.test.mjs`

**Environment:** None source-discovered

**Inputs:** .venv/bin/python, scripts/docs/parity/render_local_runtime_comparison.py, tests/dev/runtime-evidence-sanitizer.test.mjs, tests/parity/test_local_runtime_report.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** gate-defined

**Example:** `task lite:docs:parity:local:check`

## `lite:evidence:parity:check`

**Purpose:** Validate parity evidence schemas, bounds, linkage, and redaction

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/test/parity/parity_evidence.py check`

**Environment:** None source-discovered

**Inputs:** scripts/test/parity/parity_evidence.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** gate-defined

**Example:** `task lite:evidence:parity:check`

## `lite:evidence:parity:generate`

**Purpose:** Generate sanitized unvalidated evidence templates without fabricating PASS results

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/test/parity/parity_evidence.py generate`

**Environment:** None source-discovered

**Inputs:** scripts/test/parity/parity_evidence.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** not-a-validation-task

**Example:** `task lite:evidence:parity:generate`

## `lite:evidence:runtime:check`

**Purpose:** Validate the committed sanitized runtime verification baseline

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/test/parity/promote_runtime_verification.py check`
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 {{.PYTHON}} -m pytest -q tests/parity/test_runtime_verification_promotion.py`

**Environment:** None source-discovered

**Inputs:** scripts/test/parity/promote_runtime_verification.py, tests/parity/test_runtime_verification_promotion.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=True

**Runtime:** requires Termux=False; requires WSL2=False; safe local=False; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** gate-defined

**Example:** `task lite:evidence:runtime:check`

## `lite:evidence:runtime:preflight`

**Purpose:** Fail-closed release, Git, and live-evidence checks before runtime promotion

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/test/parity/preflight_runtime_promotion.py --release-tag "{{.LITE_PARITY_RELEASE_TAG}}"`

**Environment:** LITE_PARITY_RELEASE_TAG

**Inputs:** scripts/test/parity/preflight_runtime_promotion.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** not-a-validation-task

**Example:** `task lite:evidence:runtime:preflight`

## `lite:evidence:runtime:promote`

**Purpose:** Explicitly promote sanitized all-tab semantic evidence, including truthful drift, for a tagged release

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `task lite:evidence:runtime:preflight`
- `{{.PYTHON}} scripts/test/parity/promote_runtime_verification.py promote --release-tag "{{.LITE_PARITY_RELEASE_TAG}}"`
- `task lite:docs:health:generate`
- `{{.PYTHON}} scripts/docs/parity/generate_parity.py generate`

**Environment:** LITE_PARITY_RELEASE_TAG

**Inputs:** scripts/docs/parity/generate_parity.py, scripts/test/parity/promote_runtime_verification.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=True

**Runtime:** requires Termux=False; requires WSL2=False; safe local=False; class=bounded

**Related tasks:** lite:docs:health:generate, lite:evidence:runtime:preflight

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** not-a-validation-task

**Example:** `task lite:evidence:runtime:promote`

## `lite:parity:api`

**Purpose:** Verify Recovery API contracts, pagination, property-test guardrails, and safe GET filters

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 {{.PYTHON}} -m pytest -q tests/parity/test_guardrails.py tests/parity/test_api_contract_fences.py`

**Environment:** None source-discovered

**Inputs:** tests/parity/test_api_contract_fences.py, tests/parity/test_guardrails.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** not-a-validation-task

**Example:** `task lite:parity:api`

## `lite:parity:backend`

**Purpose:** Verify Recovery backend authority to allowlisted API projection parity

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 {{.PYTHON}} -m pytest -q tests/parity/test_backup_recovery_parity.py tests/backend/test_lite_recovery.py`

**Environment:** None source-discovered

**Inputs:** tests/backend/test_lite_recovery.py, tests/parity/test_backup_recovery_parity.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** not-a-validation-task

**Example:** `task lite:parity:backend`

## `lite:parity:check`

**Purpose:** Aggregate deterministic Backend-to-Frontend parity readiness gate; live phone checks remain separate

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `task lite:parity:tools:check`
- `task lite:parity:model:check`
- `task lite:parity:contracts:check`
- `task lite:parity:fixtures:check`
- `task lite:parity:backend`
- `task lite:parity:api`
- `task lite:parity:selectors`
- `task lite:parity:storybook`
- `task lite:parity:playwright:mocked`
- `task lite:a11y:check`
- `task lite:visual:check`
- `task lite:evidence:parity:generate`
- `task lite:evidence:parity:check`
- `task lite:evidence:runtime:check`
- `task lite:docs:parity:check`

**Environment:** None source-discovered

**Inputs:** No explicit file inputs discovered

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=True; safe local=True; class=heavy-dev

**Related tasks:** lite:a11y:check, lite:docs:parity:check, lite:evidence:parity:check, lite:evidence:parity:generate, lite:evidence:runtime:check, lite:parity:api, lite:parity:backend, lite:parity:contracts:check, lite:parity:fixtures:check, lite:parity:model:check, lite:parity:playwright:mocked, lite:parity:selectors, lite:parity:storybook, lite:parity:tools:check, lite:visual:check

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** gate-defined

**Example:** `task lite:parity:check`

## `lite:parity:contracts:check`

**Purpose:** Validate parity schemas, fingerprints, linkage, redaction, and contract drift

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/docs/parity/generate_parity.py check`
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 {{.PYTHON}} -m pytest -q tests/parity/test_contract_generation.py`

**Environment:** None source-discovered

**Inputs:** scripts/docs/parity/generate_parity.py, tests/parity/test_contract_generation.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** gate-defined

**Example:** `task lite:parity:contracts:check`

## `lite:parity:contracts:generate`

**Purpose:** Generate canonical seven-tab parity contracts from one repository-owned model

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/docs/parity/generate_parity.py generate`

**Environment:** None source-discovered

**Inputs:** scripts/docs/parity/generate_parity.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** not-a-validation-task

**Example:** `task lite:parity:contracts:generate`

## `lite:parity:fixtures:check`

**Purpose:** Check generated fixtures plus real all-tab selector/presentation linkage

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/docs/parity/generate_parity.py check`
- `node scripts/test/parity/check_recovery_selector.mjs`
- `node scripts/test/parity/check_domain_selectors.mjs`
- `npm run test:parity:selectors`

**Environment:** None source-discovered

**Inputs:** scripts/docs/parity/generate_parity.py, scripts/test/parity/check_domain_selectors.mjs, scripts/test/parity/check_recovery_selector.mjs

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** gate-defined

**Example:** `task lite:parity:fixtures:check`

## `lite:parity:fixtures:generate`

**Purpose:** Preserve deterministic Recovery fixtures and generate the all-tab semantic scenario registries

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/docs/parity/generate_parity.py generate`

**Environment:** None source-discovered

**Inputs:** scripts/docs/parity/generate_parity.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** not-a-validation-task

**Example:** `task lite:parity:fixtures:generate`

## `lite:parity:model:check`

**Purpose:** Validate the canonical seven-tab parity model, comparators, runtime scenarios, and bounded pairwise catalog

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/docs/parity/generate_parity.py fingerprint`
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 {{.PYTHON}} -m pytest -q tests/parity/test_intelligent_runtime_parity.py -k model`

**Environment:** None source-discovered

**Inputs:** scripts/docs/parity/generate_parity.py, tests/parity/test_intelligent_runtime_parity.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** gate-defined

**Example:** `task lite:parity:model:check`

## `lite:parity:playwright:live`

**Purpose:** Run existing live read-only browser verification against the configured Lite origin

**Audience:** developer

**Dependencies:** lite:playwright:preflight

**Aliases:** None

**Commands:**

- `LITE_E2E_LIVE=1 LITE_E2E_MODE=live npx playwright test tests/e2e/lite-live.spec.ts --project=live-desktop --project=live-mobile`

**Environment:** LITE_E2E_LIVE, LITE_E2E_MODE

**Inputs:** tests/e2e/lite-live.spec.ts

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=True; safe local=True; class=heavy-dev

**Related tasks:** lite:playwright:preflight

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** not-a-validation-task

**Example:** `task lite:parity:playwright:live`

## `lite:parity:playwright:mocked`

**Purpose:** Run deterministic mocked semantic parity in desktop and mobile Chromium

**Audience:** developer

**Dependencies:** lite:playwright:preflight

**Aliases:** None

**Commands:**

- `npm run test:e2e:parity`

**Environment:** None source-discovered

**Inputs:** No explicit file inputs discovered

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=True; safe local=True; class=heavy-dev

**Related tasks:** lite:playwright:preflight

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** not-a-validation-task

**Example:** `task lite:parity:playwright:mocked`

## `lite:parity:runtime:capture`

**Purpose:** Capture bounded sanitized backend observations for all seven Lite tabs

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/test/parity/capture_runtime_parity.py --kind backend --base-url "{{.LITE_PARITY_API_URL}}" --release-tag "{{.LITE_PARITY_RELEASE_TAG}}"`

**Environment:** LITE_PARITY_API_URL, LITE_PARITY_RELEASE_TAG

**Inputs:** scripts/test/parity/capture_runtime_parity.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=True; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=False; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** not-a-validation-task

**Example:** `task lite:parity:runtime:capture`

## `lite:parity:runtime:compare`

**Purpose:** Compare backend, Termux, live desktop, and live mobile observations semantically without changing app behavior

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/test/parity/compare_runtime_parity.py`

**Environment:** None source-discovered

**Inputs:** scripts/test/parity/compare_runtime_parity.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** not-a-validation-task

**Example:** `task lite:parity:runtime:compare`

## `lite:parity:selectors`

**Purpose:** Verify repository-derived all-tab selector and direct-render presentation contracts

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `node scripts/test/parity/check_recovery_selector.mjs`
- `node scripts/test/parity/check_domain_selectors.mjs`
- `npm run test:parity:selectors`

**Environment:** None source-discovered

**Inputs:** scripts/test/parity/check_domain_selectors.mjs, scripts/test/parity/check_recovery_selector.mjs

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** not-a-validation-task

**Example:** `task lite:parity:selectors`

## `lite:parity:storybook`

**Purpose:** Build Storybook and verify repository-linked parity story coverage

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `npm run build-storybook`
- `test -f storybook-static/index.html`

**Environment:** None source-discovered

**Inputs:** storybook-static/index.html

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** not-a-validation-task

**Example:** `task lite:parity:storybook`

## `lite:parity:termux`

**Purpose:** Capture bounded sanitized all-tab observations through the managed read-only Termux SSH loopback

**Audience:** developer/operator

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/test/parity/capture_runtime_parity.py --kind termux --ssh-alias "{{.POCKETLAB_TERMUX_SSH_ALIAS}}" --base-url "{{.LITE_PARITY_TERMUX_API_URL}}" --release-tag "{{.LITE_PARITY_RELEASE_TAG}}"`

**Environment:** LITE_PARITY_RELEASE_TAG, LITE_PARITY_TERMUX_API_URL, POCKETLAB_TERMUX_SSH_ALIAS

**Inputs:** scripts/test/parity/capture_runtime_parity.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=True; promotes evidence=False

**Runtime:** requires Termux=True; requires WSL2=False; safe local=False; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** not-a-validation-task

**Example:** `task lite:parity:termux`

## `lite:parity:tools:check`

**Purpose:** Verify locally pinned parity tools without changing the host

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `bash scripts/dev/lite/setup-parity-tools.sh --check`

**Environment:** None source-discovered

**Inputs:** scripts/dev/lite/setup-parity-tools.sh

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** gate-defined

**Example:** `task lite:parity:tools:check`

## `lite:performance:edge`

**Purpose:** Run one-VU bounded read-only parity checks for edge hardware

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PARITY_TOOLS}}/k6 run performance/parity/edge-readonly.js`

**Environment:** None source-discovered

**Inputs:** performance/parity/edge-readonly.js

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** not-a-validation-task

**Example:** `task lite:performance:edge`

## `lite:performance:wsl`

**Purpose:** Run three-VU bounded read-only parity checks from WSL2

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PARITY_TOOLS}}/k6 run performance/parity/wsl-readonly.js`

**Environment:** None source-discovered

**Inputs:** performance/parity/wsl-readonly.js

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** not-a-validation-task

**Example:** `task lite:performance:wsl`

## `lite:visual:check`

**Purpose:** Run the existing mocked visual-regression gate

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `task lite:test:visual`

**Environment:** None source-discovered

**Inputs:** No explicit file inputs discovered

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** lite:test:visual

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** gate-defined

**Example:** `task lite:visual:check`

## `lite:release:artifact-check`

**Purpose:** Validate an existing dist.zip, checksums.txt, and optional Lite release manifest

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `{{.PYTHON}} scripts/dev/lite/release_artifact_check.py --root .`

**Environment:** None source-discovered

**Inputs:** scripts/dev/lite/release_artifact_check.py

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** not-a-validation-task

**Example:** `task lite:release:artifact-check`

## `lite:release:dry-run`

**Purpose:** Build dist.zip and validate the Lite release manifest/checksum without publishing

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `bash scripts/dev/release-dry-run.sh`
- `{{.PYTHON}} scripts/dev/lite/release_artifact_check.py --root .`

**Environment:** None source-discovered

**Inputs:** scripts/dev/lite/release_artifact_check.py, scripts/dev/release-dry-run.sh

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** not-a-validation-task

**Example:** `task lite:release:dry-run`

## `lite:storybook`

**Purpose:** Start Lite Storybook with deterministic MSW fixtures

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `npm run storybook -- --host 127.0.0.1`

**Environment:** None source-discovered

**Inputs:** No explicit file inputs discovered

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** not-a-validation-task

**Example:** `task lite:storybook`

## `lite:storybook:build`

**Purpose:** Build the Lite Storybook static site

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `npm run build-storybook`

**Environment:** None source-discovered

**Inputs:** No explicit file inputs discovered

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** not-a-validation-task

**Example:** `task lite:storybook:build`

## `lite:storybook:screenshots`

**Purpose:** Capture canonical Lite Storybook screenshots with the verified browser resolver

**Audience:** developer

**Dependencies:** lite:dev:scratch:prepare, lite:playwright:preflight

**Aliases:** None

**Commands:**

- `node scripts/docs/lite/capture-storybook.mjs`

**Environment:** None source-discovered

**Inputs:** scripts/docs/lite/capture-storybook.mjs

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** lite:dev:scratch:prepare, lite:playwright:preflight

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** not-a-validation-task

**Example:** `task lite:storybook:screenshots`

## `lite:test:a11y`

**Purpose:** Run Playwright Axe checks for every Lite tab at mobile and desktop widths

**Audience:** developer

**Dependencies:** lite:dev:scratch:prepare, lite:playwright:preflight

**Aliases:** None

**Commands:**

- `npm run test:a11y`

**Environment:** None source-discovered

**Inputs:** No explicit file inputs discovered

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** lite:dev:scratch:prepare, lite:playwright:preflight

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** gate-defined

**Example:** `task lite:test:a11y`

## `lite:test:e2e:live`

**Purpose:** Run read-only live integration tests against Caddy/FastAPI; requires LITE_E2E_LIVE=1

**Audience:** developer

**Dependencies:** lite:dev:scratch:prepare, lite:playwright:preflight

**Aliases:** None

**Commands:**

- `npm run test:e2e:live`

**Environment:** None source-discovered

**Inputs:** No explicit file inputs discovered

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** lite:dev:scratch:prepare, lite:playwright:preflight

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** gate-defined

**Example:** `task lite:test:e2e:live`

## `lite:test:e2e:mocked`

**Purpose:** Run mocked Lite integration tests on desktop and mobile Chromium

**Audience:** developer

**Dependencies:** lite:dev:scratch:prepare, lite:playwright:preflight

**Aliases:** None

**Commands:**

- `npm run test:e2e:mocked`

**Environment:** None source-discovered

**Inputs:** No explicit file inputs discovered

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** lite:dev:scratch:prepare, lite:playwright:preflight

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** gate-defined

**Example:** `task lite:test:e2e:mocked`

## `lite:test:lighthouse`

**Purpose:** Run the existing development-PC Lighthouse PWA gate

**Audience:** developer

**Dependencies:** lite:dev:scratch:prepare, lite:playwright:preflight

**Aliases:** None

**Commands:**

- `bash scripts/dev/check-lighthouse.sh`

**Environment:** None source-discovered

**Inputs:** scripts/dev/check-lighthouse.sh

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** lite:dev:scratch:prepare, lite:playwright:preflight

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** gate-defined

**Example:** `task lite:test:lighthouse`

## `lite:test:storybook`

**Purpose:** Build Storybook and run Lite inventory plus browser interaction checks

**Audience:** developer

**Dependencies:** lite:dev:scratch:prepare, lite:playwright:preflight

**Aliases:** None

**Commands:**

- `npm run build-storybook`
- `{{.PYTHON}} scripts/docs/lite/generate_docs.py check-storybook`
- `node scripts/docs/lite/test-storybook.mjs`

**Environment:** None source-discovered

**Inputs:** scripts/docs/lite/generate_docs.py, scripts/docs/lite/test-storybook.mjs

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=True; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** lite:dev:scratch:prepare, lite:playwright:preflight

**Failure modes:** dependency task failure, missing required local tool or evidence, generated drift

**Validation outcome:** gate-defined

**Example:** `task lite:test:storybook`

## `lite:test:visual`

**Purpose:** Run canonical Lite visual regression screenshots against committed baselines

**Audience:** developer

**Dependencies:** lite:dev:scratch:prepare, lite:playwright:preflight

**Aliases:** None

**Commands:**

- `npm run test:visual`

**Environment:** None source-discovered

**Inputs:** No explicit file inputs discovered

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** lite:dev:scratch:prepare, lite:playwright:preflight

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** gate-defined

**Example:** `task lite:test:visual`

## `lite:test:visual:update`

**Purpose:** Create or deliberately refresh canonical Lite visual baselines for review

**Audience:** developer

**Dependencies:** lite:dev:scratch:prepare, lite:playwright:preflight

**Aliases:** None

**Commands:**

- `npm run test:visual:update`

**Environment:** None source-discovered

**Inputs:** No explicit file inputs discovered

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** lite:dev:scratch:prepare, lite:playwright:preflight

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** gate-defined

**Example:** `task lite:test:visual:update`

## `lite:windows:host:check`

**Purpose:** Run the existing Windows host WSL2 preflight

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/windows/check-wsl2-host.ps1`

**Environment:** None source-discovered

**Inputs:** scripts/windows/check-wsl2-host.ps1

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=False; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=True; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** gate-defined

**Example:** `task lite:windows:host:check`

## `lite:windows:vscode:check`

**Purpose:** Validate VS Code workspace files without installing extensions

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/windows/configure-vscode.ps1 -SkipExtensionInstall`

**Environment:** None source-discovered

**Inputs:** scripts/windows/configure-vscode.ps1

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=True; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=False; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** gate-defined

**Example:** `task lite:windows:vscode:check`

## `lite:windows:wsl:check`

**Purpose:** Validate the established Ubuntu/WSL2 Lite development environment

**Audience:** developer

**Dependencies:** None

**Aliases:** None

**Commands:**

- `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/windows/bootstrap-wsl2-ubuntu.ps1 -CheckOnly`

**Environment:** None source-discovered

**Inputs:** scripts/windows/bootstrap-wsl2-ubuntu.ps1

**Outputs:** No explicit file outputs discovered

**Generated artifacts:** None discovered

**Side effects:** repository mutation=False; runtime mutation=True; captures runtime=False; promotes evidence=False

**Runtime:** requires Termux=False; requires WSL2=False; safe local=False; class=bounded

**Related tasks:** None

**Failure modes:** dependency task failure, missing required local tool or evidence, command failure

**Validation outcome:** gate-defined

**Example:** `task lite:windows:wsl:check`
