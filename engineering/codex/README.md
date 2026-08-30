# Pocket Lab Lite Codex Operating Guide

This guide defines Codex-specific local repository execution for Pocket Lab Lite. Root `AGENTS.md` is authoritative; this document does not replace or duplicate the architecture, security, recovery or release contracts.

## Role in the engineering model

Codex is the local repository implementation and validation surface. It is not a competing architecture authority and does not replace ChatGPT Chat synthesis, ChatGPT Work investigation, or independent review.

The normal division of responsibility is:

- ChatGPT Chat: coordination, synthesis, architecture/design reasoning, reconciliation, debugging reasoning and explicit GitHub coordination.
- ChatGPT Work: broad read-only investigation, parallel specialist analysis, independent review and security/test/change-impact/CI/release analysis.
- Codex: local source inspection, targeted edits, tests, generators, builds, diffs and local Git inspection.
- Human: explicit authority for remote, destructive, live-runtime, credential and release actions.

## Codex may

Codex may, within the explicitly opened repository:

- inspect repository files, source, tests and local Git history/status/diffs;
- edit source and tests and add targeted regression tests;
- run Python and shell syntax checks, pytest, npm builds and Taskfile tasks;
- run documentation generators when the canonical source workflow requires them;
- inspect generated drift and local diffs;
- prepare a change for independent review.

Ordinary local, non-destructive implementation and validation are allowed when they are within the user's requested repository task.

## Codex must

- use native WSL tooling for Pocket Lab Lite;
- treat `/home/$USER/pocket-lab-lite` as the canonical checkout;
- read root `AGENTS.md` first;
- verify branch, `HEAD`, `origin/main` and status before mutation;
- inspect relevant source and tests before editing;
- prefer the smallest targeted edits;
- never hand-edit generated outputs as the source fix;
- preserve Android/Termux, ARM64, Ubuntu/WSL2 and edge-first behavior;
- preserve FastAPI/NATS/agent/supervisor trust boundaries;
- label `VERIFIED` versus `UNVALIDATED` clearly;
- never claim completion without actual validation output;
- run focused validation first, then broader gates as appropriate;
- show the diff and actual results before claiming success.

## Explicit authorization boundary

Codex must not perform the following without explicit user instruction:

- commit, push, merge or tag;
- publish a release or delete remote branches;
- mutate the live Server Phone or Termux production runtime;
- perform destructive reset, restore or clean operations;
- rotate or change secrets and credentials;
- overwrite promoted runtime evidence merely to satisfy tests or documentation checks.

Inspecting local Git state is allowed. Remote or live actions require separate authorization even when a local implementation is complete.

## Native WSL Git is canonical

Use native WSL Git from `/home/$USER/pocket-lab-lite`. Do not use Windows Git through:

```text
\\wsl$\ubuntu\home\$USER\pocket-lab-lite
```

Verified repository behavior on 2026-08-20:

- Windows Git reported 170 modified files;
- every reported diff was only `old mode 100755` → `new mode 100644`;
- `git diff --numstat` showed `0 0` for all entries;
- `git diff --ignore-space-at-eol` still showed only mode differences;
- native WSL `stat` showed executable mode `755`;
- native WSL Git reported a clean working tree;
- `HEAD == origin/main == c2c0a300211e91396e16d39c279c6327543ac50b`.

`INFERRED`: Windows Git was misreading executable-mode metadata across this WSL filesystem boundary. This is documented as verified Pocket Lab Lite behavior and an evidence-backed inference, not as a universal Windows/WSL law.

Therefore:

- native WSL Git is canonical;
- do not reset, restore, clean or regenerate based only on Windows Git status;
- avoid Git operations through the `\\wsl$` UNC path for this repository;
- do not set `core.filemode=false` by default;
- only consider `core.filemode=false` knowingly if Windows Git must be used, because executable-bit changes are meaningful in this repository.

Canonical verification:

```bash
wsl.exe -d Ubuntu -- bash -lc \
  "cd /home/$USER/pocket-lab-lite && git status --short --branch"
```

## Normal Codex lifecycle

1. Load `AGENTS.md`.
2. Verify the repository state with native WSL Git.
3. Inspect relevant source and tests.
4. State verified current behavior and root cause.
5. Make the smallest targeted edit.
6. Run focused validation.
7. Run broader validation when appropriate.
8. Inspect `git diff`, `git diff --check` and status.
9. Report what passed, failed or was not run.
10. Stop before remote, destructive or live action unless explicitly authorized.

## Handoff rules

Chat/Work → Codex handoffs should include:

- objective;
- verified evidence;
- likely files;
- architecture constraints;
- test contract;
- unvalidated assumptions.

Codex → Chat/Work handoffs should include:

- files changed;
- exact diff summary;
- actual validation output;
- remaining risks;
- unvalidated items;
- no claims beyond evidence.

## Validation baseline

Use the smallest relevant checks first, then the applicable broader gates:

```bash
python3 -m py_compile <changed-python-files>
bash -n <changed-shell-files>
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q <focused-tests>
npm run build
task lite:api:check
task lite:docs:check
task lite:check
git diff --check
```

For documentation or generated-artifact changes, follow the generator ownership and ordering rules in `AGENTS.md` and `engineering/chatgpt/validation-matrix.md`. Change canonical inputs or generators, never generated projections directly.

## Local developer MCP

Pocket Lab MCP is a local developer capability. It does not modify runtime architecture.

- [MCP architecture](mcp-architecture.md)
- [MCP security model](mcp-security-model.md)
- [MCP installation](mcp-installation.md)
- [MCP validation](mcp-validation.md)

## Deeper guidance

- Universal contract: `AGENTS.md`
- ChatGPT Chat + Work entrypoint: `engineering/chatgpt/README.md`
- ChatGPT canonical context: `engineering/chatgpt/canonical-context.md`
- Architecture contract: `engineering/chatgpt/architecture-contract.md`
- Specialist roles: `engineering/chatgpt/agent-roles.md`
- Workflows: `engineering/chatgpt/operating-workflow.md`
- Validation matrix: `engineering/chatgpt/validation-matrix.md`
- Handoffs: `engineering/chatgpt/handoff-template.md`
- Maintenance/release: `engineering/chatgpt/maintenance-release.md`
