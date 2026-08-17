package pocketlab.authz

import rego.v1

default decision := {
	"allow": false,
	"constraints": [],
	"reason_code": "actor_not_authenticated",
}

authenticated_actor if {
	input.actor.type in {"human", "service", "test"}
}

decision := {
	"allow": true,
	"constraints": ["authenticated_actor"],
	"reason_code": "authenticated_app_install",
} if {
	input.action.id == "catalog.install"
	authenticated_actor
	input.target.type == "app"
	input.target.id != ""
}

decision := {
	"allow": true,
	"constraints": ["authenticated_actor", "confirmed_retirement", "validated_revision"],
	"reason_code": "authenticated_confirmed_device_removal",
} if {
	input.action.id == "device.remove"
	authenticated_actor
	input.target.type == "device"
	input.target.state.confirmed == true
	input.target.state.revision_validated == true
	input.target.state.protected_server_host == false
}
