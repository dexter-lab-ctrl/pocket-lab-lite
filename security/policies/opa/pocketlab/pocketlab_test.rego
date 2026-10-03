package pocketlab.authz

import rego.v1

test_catalog_install_legacy_alias_keeps_owner_authority_boundary if {
	result := decision with input as {
		"actor": {"type": "human", "id": "human-owner", "role": "Owner", "enterprise_enabled": true, "owner_authority": true},
		"session": {"authenticated": true, "auth_method": "passkey"},
		"action": {"id": "catalog.install"},
		"target": {"type": "app", "id": "photoprism", "revision": "test", "state": {"target_device_id": "server"}},
		"continuation": {"matching_temporary_exception": false},
		"request": {},
	}
	result.allow
	result.reason_code == "enterprise_app_install_allowed"
}

test_catalog_install_legacy_alias_operator_requires_exact_temporary_exception if {
	blocked := decision with input as {
		"actor": {"type": "human", "id": "human-operator", "role": "Operator", "enterprise_enabled": true},
		"session": {"authenticated": true, "auth_method": "passkey"},
		"action": {"id": "catalog.install"},
		"target": {"type": "app", "id": "photoprism", "revision": "test", "state": {"target_device_id": "server"}},
		"continuation": {"matching_temporary_exception": false},
		"request": {},
	}
	not blocked.allow
	blocked.reason_code == "temporary_exception_required"

	allowed := decision with input as {
		"actor": {"type": "human", "id": "human-operator", "role": "Operator", "enterprise_enabled": true},
		"session": {"authenticated": true, "auth_method": "passkey"},
		"action": {"id": "catalog.install"},
		"target": {"type": "app", "id": "photoprism", "revision": "test", "state": {"target_device_id": "server"}},
		"continuation": {"matching_temporary_exception": true},
		"request": {},
	}
	allowed.allow
	allowed.reason_code == "app_temporary_exception_satisfied"
}

app_resource_input(action_id, role) := {
	"actor": {
		"type": "human",
		"id": concat("", ["human-", lower(role)]),
		"role": role,
		"enterprise_enabled": true,
		"owner_authority": role == "Owner",
	},
	"session": {"authenticated": true, "auth_method": "passkey"},
	"action": {"id": action_id},
	"target": {
		"type": "app",
		"id": "photoprism",
		"revision": "contract-a",
		"state": {
			"resource_type": "app",
			"app_id": "photoprism",
			"semantic_action": action_id,
			"required_capability": "install",
			"capability_supported": true,
			"platform_supported": true,
			"placement_required": true,
			"placement_ready": true,
			"contract_revision": "contract-a",
			"request_fingerprint": "contract-a",
		},
	},
	"continuation": {"matching_independent_approval": false, "matching_temporary_exception": false},
	"request": {},
}

test_app_resource_owner_is_direct_without_peer_approval if {
	result := decision with input as app_resource_input("app.remove", "Owner")
	result.allow
	result.reason_code == "owner_authority_app_operation"
}

test_app_resource_admin_remove_requires_independent_approval if {
	result := decision with input as app_resource_input("app.remove", "Admin")
	not result.allow
	result.reason_code == "approval_required"
	result.requirements.required_assurance == "policy.approval.app.remove"
}

test_app_resource_operator_install_requires_temporary_access if {
	result := decision with input as app_resource_input("app.install", "Operator")
	not result.allow
	result.reason_code == "temporary_exception_required"
}

test_app_resource_viewer_and_auditor_fail_closed_for_mutation if {
	viewer := decision with input as app_resource_input("app.repair", "Viewer")
	auditor := decision with input as app_resource_input("app.repair", "Auditor")
	not viewer.allow
	not auditor.allow
	viewer.reason_code == "enterprise_role_forbidden"
	auditor.reason_code == "enterprise_role_forbidden"
}

test_app_resource_mismatch_fails_closed if {
	input_doc := app_resource_input("app.install", "Admin")
	result := decision with input as object.union(input_doc, {
		"target": object.union(input_doc.target, {
			"state": object.union(input_doc.target.state, {"app_id": "other-app"}),
		}),
	})
	not result.allow
	result.reason_code == "app_resource_invalid"
}

test_app_credential_metadata_management_does_not_require_runtime_placement if {
	input_doc := app_resource_input("app.credentials.manage", "Admin")
	result := decision with input as object.union(input_doc, {
		"target": object.union(input_doc.target, {
			"state": object.union(input_doc.target.state, {
				"semantic_action": "app.credentials.manage",
				"required_capability": "credentials",
				"placement_required": false,
				"placement_ready": false,
			}),
		}),
	})
	result.allow
	result.reason_code == "enterprise_app_operation_allowed"
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

test_enterprise_admin_matching_independent_approval_allows_removal if {
	result := decision with input as {
		"actor": {"type": "human", "id": "human-admin", "role": "Admin", "enterprise_enabled": true},
		"session": {"authenticated": true, "auth_method": "passkey"},
		"action": {"id": "device.remove"},
		"target": {"type": "device", "id": "old-node", "revision": "assessment-test", "state": {"confirmed": true, "revision_validated": true, "protected_server_host": false}},
		"continuation": {"matching_independent_approval": true},
		"request": {},
	}
	result.allow
	result.reason_code == "independent_approval_satisfied"
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
