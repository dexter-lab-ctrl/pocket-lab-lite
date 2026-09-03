package pocketlab.authz

import rego.v1

# Regression: PR #557 added Enterprise Owner root authority without constraining
# the shared enterprise predicate to Enterprise Mode. A Personal Mode Owner is
# still resolved as role=Owner by the server, so both complete decision rules
# could match and make the OPA result undefined. Personal and Enterprise removal
# paths must remain mutually exclusive.
test_personal_owner_removal_uses_personal_mode_authority_only if {
	result := decision with input as {
		"actor": {"type": "human", "id": "human-owner", "role": "Owner", "enterprise_enabled": false},
		"session": {"authenticated": true, "auth_method": "passkey"},
		"action": {"id": "device.remove"},
		"target": {"type": "device", "id": "old-phone", "revision": "assessment-test", "state": {"confirmed": true, "revision_validated": true, "protected_server_host": false}},
		"continuation": {"matching_independent_approval": false},
		"request": {},
	}
	result.allow
	result.reason_code == "authenticated_confirmed_device_removal"
	object.get(result, "requirements", {}) == {}
}

# Keep the Enterprise Owner contract explicit: Owner is root-equivalent for a
# validated non-server removal and never creates an independent approval need.
test_enterprise_owner_removal_still_uses_root_authority_without_approval if {
	result := decision with input as {
		"actor": {"type": "human", "id": "human-owner", "role": "Owner", "enterprise_enabled": true},
		"session": {"authenticated": true, "auth_method": "passkey"},
		"action": {"id": "device.remove"},
		"target": {"type": "device", "id": "old-phone", "revision": "assessment-test", "state": {"confirmed": true, "revision_validated": true, "protected_server_host": false}},
		"continuation": {"matching_independent_approval": false},
		"request": {},
	}
	result.allow
	result.reason_code == "owner_authority_device_removal"
	object.get(result, "requirements", {}) == {}
}

# The mode-boundary fix must not weaken the hard protected-server guard.
test_personal_owner_cannot_remove_protected_server_host if {
	result := decision with input as {
		"actor": {"type": "human", "id": "human-owner", "role": "Owner", "enterprise_enabled": false},
		"session": {"authenticated": true, "auth_method": "passkey"},
		"action": {"id": "device.remove"},
		"target": {"type": "device", "id": "server", "revision": "assessment-test", "state": {"confirmed": true, "revision_validated": true, "protected_server_host": true}},
		"continuation": {"matching_independent_approval": false},
		"request": {},
	}
	not result.allow
}
