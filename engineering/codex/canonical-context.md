# Pocket Lab Lite Codex Canonical Context

## Repository

- Canonical checkout: `/home/dj/pocket-lab-lite`
- Use native WSL tooling and native WSL Git only.
- Root `AGENTS.md` is the controlling policy.

## Source of truth

1. Current Git-tracked repository source and tests.
2. Canonical contracts, schemas, architecture metadata and generated evidence.
3. Generated Documentation Platform views.
4. `engineering/chatgpt/` guidance and this Codex context.
5. Handoffs and assumptions, labeled `UNVALIDATED`.

## Architecture boundary

```text
React/Vite PWA → Caddy → FastAPI /api/lite/* → NATS/JetStream
→ worker/node agent/supervisor → sanitized events/heartbeats/evidence
→ FastAPI prepared reads → UI
```

Preserve the frontend/FastAPI/NATS/worker-agent-supervisor trust boundaries and Android/Termux, ARM64, Ubuntu/WSL2, edge-first behavior.

## Generated files

Generated documentation and contracts are projections. Do not hand-edit `docs/generated/**` or `contracts/generated/**` as the source fix. Change canonical inputs or generators, then regenerate and validate determinism when required.

## Validation baseline

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

Run focused checks first and broader gates when the change requires them.

## Mutation boundary

Codex may inspect and make ordinary local non-destructive repository edits and validation. Explicit user intent is required for commit, push, merge, tag, release publication, live Server Phone or Termux mutation, destructive reset/restore/clean, and secret or credential changes.

## Native WSL verification

Before mutation, verify branch, `HEAD`, `origin/main`, merge base and status:

```bash
wsl.exe -d Ubuntu -- bash -lc \
  "cd /home/dj/pocket-lab-lite && git status --short --branch && git rev-parse HEAD && git rev-parse origin/main && git merge-base HEAD origin/main"
```

Do not trust Windows Git status over `\\wsl$\ubuntu\home\dj\pocket-lab-lite`; this repository has verified false mode-only reports there. See `engineering/codex/README.md` for the evidence and handling.

## Status vocabulary

Use `VERIFIED`, `INFERRED`, `PATCH-PROVIDED`, `MISSING`, `PLANNED`, `OPTIONAL` and `UNVALIDATED`. Never claim completion without validation output.

## Deeper docs

Read `AGENTS.md`, then use `engineering/codex/README.md` for Codex procedures and `engineering/chatgpt/` for Chat/Work reasoning, specialist review, validation and release guidance.
