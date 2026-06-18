# Backup and Restore

Pocket Lab Lite supports backup and restore through the existing typed operation model.

## Backup

User-facing action:

```text
Backup Now
```

The backend should queue the existing `backup_now` typed operation through FastAPI, NATS / JetStream, and the worker.

## Restore

User-facing action:

```text
Restore
```

Restore must require a clear confirmation before execution.

The UI should explain:

- what will be restored;
- what may change;
- whether a backup was verified;
- whether recovery is ready;
- how to cancel safely.

## Validation

```bash
curl -s http://127.0.0.1:8080/api/lite/recovery
```

Expected result:

```text
Recovery state is returned as a user-friendly summary.
```
