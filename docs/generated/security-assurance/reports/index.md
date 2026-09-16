# Security Assurance Reports

No sanitized Security Assurance report has been published from this branch yet.

Reports are generated only from completed normalized/sanitized qualification evidence with:

```bash
task lite:security:assurance:report:publish QUALIFICATION_ID=<assurance-run-id>
```

A published report is assurance evidence, not a security certification. The generator rebuilds this index deterministically from sanitized companion JSON files.
