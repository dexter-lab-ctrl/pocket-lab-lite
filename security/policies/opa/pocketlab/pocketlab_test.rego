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

test_device_removal_requires_hard_invariant_context if {
	result := decision with input as {
		"actor": {"type": "human", "id": "human-test"},
		"session": {"authenticated": true, "auth_method": "password"},
		"action": {"id": "device.remove"},
		"target": {
			"type": "device",
			"id": "old-node",
			"revision": "assessment-test",
			"state": {"confirmed": true, "revision_validated": true, "protected_server_host": false},
		},
		"request": {},
	}
	result.allow
}

test_device_removal_denies_without_confirmation if {
	result := decision with input as {
		"actor": {"type": "human", "id": "human-test"},
		"session": {"authenticated": true, "auth_method": "password"},
		"action": {"id": "device.remove"},
		"target": {
			"type": "device",
			"id": "old-node",
			"revision": "assessment-test",
			"state": {"confirmed": false, "revision_validated": true, "protected_server_host": false},
		},
		"request": {},
	}
	not result.allow
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
