package pocketlab.authz

import rego.v1

test_catalog_install_allows_authenticated_human if {
	result := decision with input as {
		"actor": {"type": "human", "id": "human-test"},
		"session": {"authenticated": true, "auth_method": "password"},
		"action": {"id": "catalog.install"},
		"target": {"type": "app", "id": "photoprism", "revision": "test", "state": {}},
		"request": {},
	}
	result.allow
	result.reason_code == "authenticated_app_install"
}

test_catalog_install_records_exact_temporary_exception_fact if {
	result := decision with input as {
		"actor": {"type": "human", "id": "human-test", "role": "Admin", "enterprise_enabled": true},
		"session": {"authenticated": true, "auth_method": "password"},
		"action": {"id": "catalog.install"},
		"target": {"type": "app", "id": "photoprism", "revision": "test", "state": {"target_node_id": "node-1"}},
		"continuation": {"matching_temporary_exception": true},
		"request": {},
	}
	result.allow
	result.reason_code == "authenticated_app_install_exception_scoped"
}

test_device_removal_requires_hard_invariant_context if {
	result := decision with input as {
		"actor": {"type": "human", "id": "human-test"},
		"session": {"authenticated": true, "auth_method": "password"},
		"action": {"id": "device.remove"},
		"target": {"type": "device", "id": "old-node", "revision": "assessment-test", "state": {"confirmed": true, "revision_validated": true, "protected_server_host": false}},
		"request": {},
	}
	result.allow
}

test_device_removal_denies_without_confirmation if {
	result := decision with input as {
		"actor": {"type": "human", "id": "human-test"},
		"session": {"authenticated": true, "auth_method": "password"},
		"action": {"id": "device.remove"},
		"target": {"type": "device", "id": "old-node", "revision": "assessment-test", "state": {"confirmed": false, "revision_validated": true, "protected_server_host": false}},
		"request": {},
	}
	not result.allow
}

# Enterprise Owner is root-equivalent for supported Pocket Lab operations. The
# action still needs explicit confirmation, validated target revision and a
# non-server target, but it never depends on another human approval.
test_enterprise_owner_removal_uses_root_authority if {
	result := decision with input as {
		"actor": {"type": "human", "id": "human-owner", "role": "Owner", "enterprise_enabled": true},
		"session": {"authenticated": true, "auth_method": "passkey"},
		"action": {"id": "device.remove"},
		"target": {"type": "device", "id": "old-node", "revision": "assessment-test", "state": {"confirmed": true, "revision_validated": true, "protected_server_host": false}},
		"continuation": {"matching_independent_approval": false},
		"request": {},
	}
	result.allow
	result.reason_code == "owner_authority_device_removal"
	"owner_authority" in result.constraints
}

test_enterprise_owner_cannot_bypass_protected_server_host if {
	result := decision with input as {
		"actor": {"type": "human", "id": "human-owner", "role": "Owner", "enterprise_enabled": true},
		"session": {"authenticated": true, "auth_method": "passkey"},
		"action": {"id": "device.remove"},
		"target": {"type": "device", "id": "server", "revision": "assessment-test", "state": {"confirmed": true, "revision_validated": true, "protected_server_host": true}},
		"continuation": {"matching_independent_approval": false},
		"request": {},
	}
	not result.allow
}

test_enterprise_admin_removal_requires_independent_approval_by_default if {
	result := decision with input as {
		"actor": {"type": "human", "id": "human-admin", "role": "Admin", "enterprise_enabled": true},
		"session": {"authenticated": true, "auth_method": "passkey"},
		"action": {"id": "device.remove"},
		"target": {"type": "device", "id": "old-node", "revision": "assessment-test", "state": {"confirmed": true, "revision_validated": true, "protected_server_host": false}},
		"continuation": {"matching_independent_approval": false},
		"request": {},
	}
	not result.allow
	result.reason_code == "approval_required"
}

test_enterprise_operator_removal_requires_independent_approval_by_default if {
	result := decision with input as {
		"actor": {"type": "human", "id": "human-operator", "role": "Operator", "enterprise_enabled": true},
		"session": {"authenticated": true, "auth_method": "passkey"},
		"action": {"id": "device.remove"},
		"target": {"type": "device", "id": "old-node", "revision": "assessment-test", "state": {"confirmed": true, "revision_validated": true, "protected_server_host": false}},
		"continuation": {"matching_independent_approval": false},
		"request": {},
	}
	not result.allow
	result.reason_code == "approval_required"
}

test_enterprise_admin_can_use_typed_direct_delegation if {
	result := decision with input as {
		"actor": {"type": "human", "id": "human-admin", "role": "Admin", "enterprise_enabled": true},
		"session": {"authenticated": true, "auth_method": "passkey"},
		"action": {"id": "device.remove"},
		"target": {"type": "device", "id": "old-node", "revision": "assessment-test", "state": {"confirmed": true, "revision_validated": true, "protected_server_host": false}},
		"continuation": {"matching_independent_approval": false},
		"request": {},
	}
	with data.parameters as {"admin_device_remove_approval": 0, "operator_device_remove_approval": 1}
	result.allow
	result.reason_code == "delegated_device_removal_allowed"
}

test_enterprise_device_removal_allows_only_server_derived_approval_fact if {
	result := decision with input as {
		"actor": {"type": "human", "id": "human-operator", "role": "Operator", "enterprise_enabled": true},
		"session": {"authenticated": true, "auth_method": "password"},
		"action": {"id": "device.remove"},
		"target": {"type": "device", "id": "old-node", "revision": "assessment-test", "state": {"confirmed": true, "revision_validated": true, "protected_server_host": false}},
		"continuation": {"matching_independent_approval": true},
		"request": {},
	}
	result.allow
	result.reason_code == "independent_approval_satisfied"
}

test_enterprise_viewer_and_auditor_cannot_request_removal_approval if {
	result := decision with input as {
		"actor": {"type": "human", "id": "human-viewer", "role": "Viewer", "enterprise_enabled": true},
		"session": {"authenticated": true, "auth_method": "password"},
		"action": {"id": "device.remove"},
		"target": {"type": "device", "id": "old-node", "revision": "assessment-test", "state": {"confirmed": true, "revision_validated": true, "protected_server_host": false}},
		"continuation": {"matching_independent_approval": false},
		"request": {},
	}
	not result.allow
	result.reason_code == "enterprise_role_forbidden"
}

test_enterprise_auditor_cannot_request_removal_approval if {
	result := decision with input as {
		"actor": {"type": "human", "id": "human-auditor", "role": "Auditor", "enterprise_enabled": true},
		"session": {"authenticated": true, "auth_method": "password"},
		"action": {"id": "device.remove"},
		"target": {"type": "device", "id": "old-node", "revision": "assessment-test", "state": {"confirmed": true, "revision_validated": true, "protected_server_host": false}},
		"continuation": {"matching_independent_approval": false},
		"request": {},
	}
	not result.allow
	result.reason_code == "enterprise_role_forbidden"
}

test_anonymous_actor_denied if {
	result := decision with input as {
		"actor": {"type": "anonymous", "id": "anonymous"},
		"session": {"authenticated": false, "auth_method": ""},
		"action": {"id": "catalog.install"},
		"target": {"type": "app", "id": "photoprism", "revision": "test", "state": {}},
		"request": {},
	}
	not result.allow
}

test_passkey_revoke_requires_step_up if {
	result := decision with input as {
		"actor": {"type": "human", "id": "human-test"},
		"session": {"authenticated": true, "auth_method": "password", "assurance": []},
		"action": {"id": "identity.passkey.revoke"},
		"target": {"type": "passkey", "id": "cred-test", "revision": "test", "state": {}},
		"request": {},
	}
	not result.allow
	result.reason_code == "passkey_step_up_required"
}

test_passkey_revoke_allows_recent_step_up if {
	result := decision with input as {
		"actor": {"type": "human", "id": "human-test"},
		"session": {"authenticated": true, "auth_method": "password", "assurance": [{"purpose": "identity.passkey.revoke", "credential_id": "cred-step-up"}]},
		"action": {"id": "identity.passkey.revoke"},
		"target": {"type": "passkey", "id": "cred-test", "revision": "test", "state": {}},
		"request": {},
	}
	result.allow
	result.reason_code == "passkey_step_up_satisfied"
}
