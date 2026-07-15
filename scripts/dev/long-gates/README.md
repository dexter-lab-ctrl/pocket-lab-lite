# Pocket Lab Lite Phase 5 long-duration gates

This directory is the extension surface for Phase 5 long-duration production gates.
Group 1 provides only the shared framework. The nine real Phase 5 gates are
registered as unavailable until their own reviewed implementations are added.

## Architecture and safety boundary

Gate scripts are server-side validation tooling. They do not add frontend execution,
do not publish production commands during the framework self-test, and do not restart
services in Group 1. Security lifecycle truth remains in SQLite; compatibility JSON
remains derived.

## Registration contract

Each registry row in
`scripts/dev/check-lite-long-duration-gates-server-phone.sh` contains:

```text
gate name | script path | risk | implemented (0/1) | resume support (0/1) | description
```

A future gate must:

1. live in this directory;
2. use the shared `long_gate_stage_*` checkpoint helpers;
3. declare every destructive stage with a safe resume boundary;
4. write only sanitized evidence beneath `$LONG_GATE_RUN_DIR/gates/<gate-id>/`;
5. return nonzero on failure;
6. never mark itself ready; final readiness is owned by the aggregator;
7. avoid `/tmp`, root requirements, Android shared storage, and PhotoPrism media;
8. use bounded timeouts and calm sampling defaults.

## Shared helper API

Gate scripts sourced by the orchestrator can call:

```text
long_gate_stage_begin <gate> <stage> [resume-safe]
long_gate_stage_pass <gate> <stage> [evidence-refs]
long_gate_stage_fail <gate> <stage> <reason> [retryable] [resume-safe]
long_gate_stage_skip <gate> <stage> [reason]
long_gate_resume_stage_status <gate> <stage>
long_gate_write_json <path> <json>
long_gate_append_jsonl <path> <json>
long_gate_curl_json <method> <url> <output> [body]
```

Completed stages must be checked before a resumed gate reruns them. Destructive stages
must never be repeated automatically after a `passed` checkpoint.

## Lock recovery

The framework uses an atomic `.lock` directory. It does not remove a stale lock merely
because the recorded PID is absent. After confirming the prior process is gone and the
run ID is correct, use:

```bash
bash scripts/dev/check-lite-long-duration-gates-server-phone.sh \
  --resume \
  --run-id <run-id> \
  --recover-stale-lock \
  --framework-self-test
```

The prior lock metadata is preserved below `checkpoints/stale-lock-*.lock`.

## Non-disruptive self-test

```bash
bash scripts/dev/check-lite-long-duration-gates-server-phone.sh \
  --framework-self-test \
  --report-dir "${TMPDIR:-$HOME/.cache}/pocketlab-long-gates-test"
```

The result is `framework_validated`, not `ready`. It publishes no commands and restarts
no services.
