package pocketlab.authz

import rego.v1

test_synthetic_recovery_profile_allows_registered_capability if {
	result := decision with input as {
		"actor": {"type": "synthetic_machine", "id": "recovery-runner", "identity_class": "synthetic_machine"},
		"session": {"authenticated": true, "auth_method": "harness_session"},
		"harness": {
			"enabled": true,
			"principal_id": "recovery-runner",
			"principal_class": "qualification",
			"profile": "recovery-qualifier",
			"purpose": "recovery.verify",
			"capabilities": ["backup.verify"],
			"target_scope": "local_server_host_only",
			"qualification_environment": true,
			"destructive_allowed": false,
		},
		"action": {"id": "backup.verify"},
		"target": {"type": "recovery", "id": "backup-1", "scope": "local_server_host_only", "state": {}},
		"request": {},
	}
	result.allow
	result.reason_code == "authenticated_recovery_operation"
}

test_synthetic_profile_denies_unregistered_capability_and_target_substitution if {
	result := decision with input as {
		"actor": {"type": "synthetic_machine", "id": "debug-runner", "identity_class": "synthetic_machine"},
		"session": {"authenticated": true, "auth_method": "harness_session"},
		"harness": {
			"enabled": true,
			"principal_id": "debug-runner",
			"principal_class": "debug",
			"profile": "debug-observer",
			"purpose": "diagnostics.read",
			"capabilities": ["diagnostics.read"],
			"target_scope": "local_server_host_only",
			"qualification_environment": true,
			"destructive_allowed": false,
		},
		"action": {"id": "restore.apply"},
		"target": {"type": "recovery", "id": "backup-1", "scope": "different_target", "state": {}},
		"request": {},
	}
	not result.allow
}

test_synthetic_owner_destructive_action_requires_independent_gate if {
	result := decision with input as {
		"actor": {"type": "qualification", "id": "qualification-runner", "role": "Owner", "owner_authority": true, "enterprise_enabled": false},
		"session": {"authenticated": true, "auth_method": "harness_session"},
		"harness": {
			"enabled": true,
			"principal_id": "qualification-runner",
			"principal_class": "qualification",
			"profile": "qualification-owner",
			"purpose": "recovery.restore",
			"capabilities": ["restore.apply"],
			"target_scope": "local_server_host_only",
			"qualification_environment": true,
			"destructive_allowed": true,
		},
		"action": {"id": "restore.apply"},
		"target": {"type": "recovery", "id": "backup-1", "scope": "local_server_host_only", "state": {"confirmed": true, "preview_bound": true, "restorable": true}},
		"request": {},
	}
	result.allow
	result.reason_code == "owner_authority_restore"
}

test_synthetic_owner_without_destructive_gate_is_denied if {
	result := decision with input as {
		"actor": {"type": "qualification", "id": "qualification-runner", "role": "Owner", "owner_authority": true, "enterprise_enabled": false},
		"session": {"authenticated": true, "auth_method": "harness_session"},
		"harness": {
			"enabled": true,
			"principal_id": "qualification-runner",
			"principal_class": "qualification",
			"profile": "qualification-owner",
			"purpose": "recovery.restore",
			"capabilities": ["restore.apply"],
			"target_scope": "local_server_host_only",
			"qualification_environment": true,
			"destructive_allowed": false,
		},
		"action": {"id": "restore.apply"},
		"target": {"type": "recovery", "id": "backup-1", "scope": "local_server_host_only", "state": {"confirmed": true, "preview_bound": true, "restorable": true}},
		"request": {},
	}
	not result.allow
}
