# Devices durable enrollment and lifecycle contract

## Objective

Keep an enrolled Pocket Lab Lite device visible across Tailscale, NATS, heartbeat,
agent, supervisor, API, worker, and server restarts. A device leaves the active
fleet only through explicit retirement/removal.

## Verified ownership audit

The current repository had no source statement that directly deleted
`device_current_state`. The verified database disappearance path was structural:

```text
device_current_state parent row deleted by an older/external/manual path
  -> ON DELETE CASCADE removes device_system_profiles
  -> ON DELETE CASCADE removes device_awareness_state
  -> ON DELETE CASCADE removes device_health_current/attention/transitions
  -> ON DELETE CASCADE removes device_lifecycle_events/transactions
  -> device_identity_guards and command_lifecycle remain because they have no parent FK
```

That shape matches the reported database evidence. The initiating historical
caller is not present in the current repository and is therefore unvalidated.
Migrations `0022_device_durable_enrollment.sql` and
`0037_fleet_multi_role_authorization.sql` closes the database path for every
caller by preventing deletion of durable enrollment and current rows.

## Multi-role enrollment ownership

Canonical device-role state is no longer owned by a heartbeat or by
`fleet_agents.json`. The normalized control-plane relation
`device_role_assignments` owns desired/active role state for joined devices,
while `device_role_change_operations` retains the bounded change lifecycle,
generation, correlation, policy revision, and request fingerprint.

```text
device_enrollment_registry
  = durable device identity/lifecycle

device_role_assignments
  = durable desired + active Compute/Storage responsibilities

device_role_change_operations
  = role-change generation + verification lifecycle

fleet/heartbeat/supervisor data
  = runtime observations only
```

Legacy enrolled records with a single `compute` or `storage` role are projected
as a one-element canonical role set. The legacy `role` field and
`POCKETLAB_NODE_ROLE` remain compatibility projections; new canonical paths use
`device_roles` / `POCKETLAB_NODE_ROLES`.

A pending invite binds the exact role set before bootstrap. Tampering the
bootstrap request to add/remove roles, including an attempt to obtain protected
`server_host`, fails closed and records sanitized evidence. Duplicate-device and
protected-host checks remain independent of the selected role set.

Post-enrollment role changes are generation-checked, require current trusted
identity and an online delivery path, and remain in applying/verifying state
until a fresh device report confirms the assigned role set. The node agent
applies only the semantic `device.roles.apply` command and atomically rewrites
only role-related environment fields. Re-delivery of the same role set and
generation is idempotent.

Storage removal is dependency-aware. Active backup/recovery/storage
responsibilities block removal of the Storage role. This changes authorization
only; retained backup or media data is not implicitly deleted. Device retirement
deactivates role authority while preserving assignment/change history.

Photo Backup Source is not a Storage role. Photo-source runtime capabilities
remain independently verified and may exist on Compute-only devices.

## Canonical ownership

```text
device_enrollment_registry = durable identity and lifecycle owner
live fleet / heartbeat / supervisor = optional runtime observations
device_current_state = prepared current projection
command_lifecycle = command-only lifecycle
```

Fleet construction is:

```text
durable enrolled devices
LEFT JOIN current runtime state
LEFT JOIN latest heartbeat
LEFT JOIN awareness/profile/health/supervisor/dependency state
```

A missing live observation produces:

```text
connection=offline
staleness_state=stale
command_delivery_status=undeliverable
review_recommended=true
```

It does not delete or retire enrollment.

## Migration exclusions

Only current canonical SQLite device rows are backfilled. The migration does not
read or resurrect devices from:

- `.pocketlab-dev` validation files;
- workflow projections or `.tmp` files;
- command history;
- stale test snapshots or fixtures;
- transient generated files;
- legacy command subjects.

## Explicit removal

Removal requires a current dependency assessment and confirmation. One SQLite
transaction:

1. marks enrollment retired/removed;
2. marks current state removed without deleting it;
3. writes a `removal_completed` lifecycle event;
4. writes a durable sanitized removal receipt;
5. writes audit evidence;
6. increments fleet/audit revisions;
7. retires active device-role authority without deleting role history.

Compatibility JSON and NATS evidence are exports only. They do not own lifecycle
truth. Protected server hosts and healthy online devices fail closed.

## Acceptance sequence

Set a test device id that is safe to disconnect and rejoin:

```bash
export DEVICE_ID='<test-device-id>'
export API='http://127.0.0.1:8443'
```

1. Enroll and verify Online:

```bash
curl -fsS "$API/api/lite/fleet" | python3 -m json.tool
sqlite3 "$POCKETLAB_LITE_DB_PATH" \
  "select device_id,removal_status,last_known_state from device_enrollment_registry where device_id='$DEVICE_ID';"
```

2. Disconnect Tailscale/NATS or stop the node agent on the secondary device.
3. Verify the same device remains listed Offline/Stale with saved profile and capabilities.
4. Restart `pocket-api` and verify the device remains listed.
5. Reconcile an old restart command and verify only the command becomes terminal.
6. Reconnect Tailscale/NATS and verify the same durable identity returns Online.
7. Stop the node agent while leaving the supervisor running; verify Repairing and recovery evidence, then Online.
8. Verify no duplicate lifecycle/health transitions for unchanged canonical states:

```bash
sqlite3 "$POCKETLAB_LITE_DB_PATH" <<SQL
select device_id,device_name,removal_status,last_known_state,registry_revision
from device_enrollment_registry where device_id='$DEVICE_ID';
select connection_state,agent_status,supervisor_status,last_seen_at
from device_current_state where device_id='$DEVICE_ID';
select event_type,reason_code,status,count(*)
from device_lifecycle_events where device_id='$DEVICE_ID'
group by event_type,reason_code,status order by max(occurred_at_epoch_ms) desc;
select previous_state,new_state,reason_codes_json,count(*)
from device_health_transitions where device_id='$DEVICE_ID'
group by previous_state,new_state,reason_codes_json;
SQL
```

## Validation

```bash
python3 -m py_compile \
  pocket-lab-final-structure/runtime/api_fastapi/services/lite_control_plane_store.py \
  pocket-lab-final-structure/runtime/api_fastapi/services/lite_status.py \
  pocket-lab-final-structure/runtime/api_fastapi/services/fleet_registry.py \
  pocket-lab-final-structure/runtime/api_fastapi/routers/lite.py \
  pocket-lab-final-structure/runtime/agents/pocketlab_agent_supervisor.py

PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q \
  tests/backend/test_lite_devices_durable_enrollment.py \
  tests/backend/test_lite_sqlite_migrations.py \
  tests/backend/test_lite_command_lifecycle_reconciliation.py \
  tests/backend/test_lite_command_attention_audit_idempotency.py \
  tests/backend/test_lite_devices_d2_d3.py \
  tests/backend/test_lite_fleet_multi_role_authorization.py \
  tests/backend/test_lite_fleet_multi_role_invites_governance.py

python3 -m pytest -q tests/backend/test_lite_api.py
npm run build
task lite:api:check
task lite:check
```

## Rollback

Revert the source commit. Do not delete registry or receipt rows. Migration 0022
is additive; leaving its tables and deletion fences in place is safer than
attempting a destructive schema rollback. Restore a pre-change SQLite online
backup only when an user has explicitly chosen full database rollback.
