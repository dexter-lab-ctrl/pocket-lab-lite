# Exact-head and release qualification playbook

Runtime evidence is valid only for the exact published revision that reviewers
inspect. The core invariant is:

```text
runtime-qualified SHA == reviewed SHA == published feature/main SHA
```

A later documentation or source commit invalidates exact-head runtime evidence
unless the relevant qualification is repeated.

## Candidate and publication sequence

Run on `[DEV PC]`:

```bash
git fetch origin --prune
git switch <feature-branch>
git status --short --branch
git rev-parse HEAD
git rev-parse origin/main
git diff --check
```

After local validation, publish the branch through the normal review workflow.
Record the exact candidate SHA and the GitHub PR/CI run. Do not qualify an
uncommitted tree or a SHA that is not available to the consumer target.

On `[SERVER PHONE]`, consume only the published SHA using the established
consumer/deployment procedure, then record sanitized output for:

```bash
git rev-parse HEAD
git status --short --branch
pm2 status
```

Do not create branches, commit, rebase, merge, patch, or rewrite tracked source
on the phone.

## Qualification at the candidate SHA

With the exact revision deployed and readiness proven, run on `[DEV PC]` or
the approved client:

```bash
task lite:security:assurance:check
task lite:security:assurance:preflight SUITE=smoke
task lite:security:assurance:qualify
```

Run Standard, Adversarial, or Deep only when the playbook and resource policy
authorize them. Record the run manifest, runtime SHA, suite, registry hashes,
sanitized report checksums, and cleanup/default-off evidence.

## Local repository gates

At the final source SHA, run the relevant repository-owned gates on `[DEV PC]`:

```bash
task lite:docs:check
git diff --check
task lite:check
```

The docs check includes the source-owned Security Assurance Playbook drift
check. Use the repository CI status for the published SHA as an additional
review signal; a green CI run does not replace runtime qualification.

## Release rollback boundary

The application uses forward-only migrations. Do not make an older runtime
accept an unknown newer schema, decrement a live schema version, drop tables,
or restore production data as part of this documentation workflow. If rollback
evidence is required, use the repository-supported release/backup contract in
a disposable isolated sandbox and preserve its exact evidence separately.

## Review checklist

- [ ] Candidate SHA, `origin/main`, and branch are recorded.
- [ ] Phone consumed the exact published SHA and remained clean.
- [ ] Qualification mode and harness authority were explicitly approved.
- [ ] `/health` and `/ready` were checked; PM2 status alone was not used.
- [ ] Required suite reports and checksums are present and sanitized.
- [ ] Findings and human-review classifications are explicit.
- [ ] Sessions/principals were revoked and the harness returned default-off.
- [ ] Final PR head equals the runtime-qualified SHA.

See [Cleanup and default-off](16-cleanup-default-off.md) for the final phone
checks and [Evidence and reporting](15-evidence-reporting.md) for artifact
validation.
