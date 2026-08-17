# Pocket Lab Lite Work ↔ Chat Handoff Template

Use this template to move a task between Work and Chat sessions without carrying a full transcript. The handoff is context only; the target session still verifies the current repository first.

```markdown
# Pocket Lab Lite Engineering Handoff

## Objective
<one concise statement of the engineering goal>

## Target repository state
- Repository: dexter-lab-ctrl/pocket-lab-lite
- Branch/PR/commit: <exact target if known>
- Base: <main or other base>
- Runtime/live target: <none unless explicitly relevant>

## VERIFIED current behavior
- <fact + source path/test/evidence>
- <fact + source path/test/evidence>

## VERIFIED source files inspected
- `path/to/file`
- `path/to/test`

## Relevant generated orientation
- Codebase Map: <relevant path/node>
- Knowledge/Architecture/API-to-UI/Change Advisor: <only what was actually used>

## Root cause / impact assessment
### VERIFIED
- <directly proven fact>

### INFERRED
- <reasoned conclusion and supporting evidence>

### UNVALIDATED
- <remaining hypothesis/question>

## Architecture/trust impact
- UI:
- FastAPI:
- NATS/JetStream:
- worker/agent/supervisor:
- evidence/audit:
- secrets/identity:
- Android/Termux/ARM64:

## Required files to change
- `path` — <why>

## Test contract
| Scenario | Expected behavior | Test/evidence |
| --- | --- | --- |
| ... | ... | ... |

## Recommended minimal implementation
1. ...
2. ...

## Validation already run
- `<command>` — PASS/FAIL — <important output>

## Validation still required
- `<command>` — <what it proves>

## Risks
- ...

## Rollback/recovery
- ...

## Do not do
- <explicit architecture/safety restrictions for this change>

## Next session instruction
<exact instruction for Chat or Work>
```

## Work → Chat handoff

The Work coordinator should summarize parallel specialists into the template. Do not paste every agent transcript. Preserve disagreements only when unresolved and identify which evidence supports each side.

A useful final Work instruction:

```text
Produce a Pocket Lab Lite Engineering Handoff using engineering/chatgpt/handoff-template.md.
Include only evidence needed for implementation/review.
Keep VERIFIED, INFERRED and UNVALIDATED statements separate.
Do not claim completion and do not invent repository state.
```

## Chat → Work review handoff

For independent review, include:

- objective;
- branch/PR/commit;
- exact changed-file list or diff reference;
- implementation rationale;
- validation output;
- known limitations;
- architecture/security areas that deserve special scrutiny.

Do not tell the reviewer the change is correct. Ask it to challenge the implementation.

## Session-to-session handoff

Use this when a long Chat session becomes difficult to navigate. The new session should:

1. read `AGENTS.md`;
2. read `canonical-context.md`;
3. read the handoff;
4. verify target branch/source before continuing;
5. ignore historical claims that no longer match the repo.

## What not to include

Avoid copying:

- secrets/env values;
- invite material;
- raw private runtime evidence;
- huge unchanged logs;
- entire Git diffs when a PR/commit reference is available;
- speculative roadmap items presented as current implementation.
