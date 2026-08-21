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
	not input.continuation.matching_temporary_exception
}

decision := {
	"allow": true,
	"constraints": ["authenticated_actor", "exact_temporary_exception"],
	"reason_code": "authenticated_app_install_exception_scoped",
} if {
	input.action.id == "catalog.install"
	authenticated_actor
	input.target.type == "app"
	input.target.id != ""
	input.continuation.matching_temporary_exception == true
}

decision := {
	"allow": true,
	"constraints": ["authenticated_actor", "confirmed_retirement", "validated_revision", "personal_mode"],
	"reason_code": "authenticated_confirmed_device_removal",
} if {
	input.action.id == "device.remove"
	authenticated_actor
	input.target.type == "device"
	input.target.state.confirmed == true
	input.target.state.revision_validated == true
	input.target.state.protected_server_host == false
	not input.actor.enterprise_enabled
}

enterprise_device_removal_safe if {
	input.action.id == "device.remove"
	authenticated_actor
	input.target.type == "device"
	input.target.state.confirmed == true
	input.target.state.revision_validated == true
	input.target.state.protected_server_host == false
}

decision := {
	"allow": false,
	"constraints": ["enterprise_role_not_eligible"],
	"reason_code": "enterprise_role_forbidden",
} if {
	enterprise_device_removal_safe
	input.actor.role in {"Viewer", "Auditor"}
}

decision := {
	"allow": false,
	"constraints": ["independent_approval", "active_owner_or_admin", "passkey_step_up"],
	"reason_code": "approval_required",
	"requirements": {"required_approver_roles": ["Owner", "Admin"], "required_assurance": "policy.approval.device.remove", "approval_lifetime_seconds": 900},
} if {
	enterprise_device_removal_safe
	input.actor.role in {"Owner", "Admin", "Operator"}
	not input.continuation.matching_independent_approval
}

decision := {
	"allow": true,
	"constraints": ["confirmed_retirement", "validated_revision", "independent_approval_consumed"],
	"reason_code": "independent_approval_satisfied",
} if {
	enterprise_device_removal_safe
	input.actor.role in {"Owner", "Admin", "Operator"}
	input.continuation.matching_independent_approval == true
}

recent_passkey_step_up if {
	some item in input.session.assurance
	item.purpose == "identity.passkey.revoke"
}

decision := {
	"allow": true,
	"constraints": ["authenticated_actor", "passkey_step_up"],
	"reason_code": "passkey_step_up_satisfied",
} if {
	input.action.id == "identity.passkey.revoke"
	authenticated_actor
	input.session.authenticated == true
	recent_passkey_step_up
	input.target.type == "passkey"
	input.target.id != ""
}

decision := {
	"allow": false,
	"constraints": ["passkey_step_up"],
	"reason_code": "passkey_step_up_required",
} if {
	input.action.id == "identity.passkey.revoke"
	authenticated_actor
	input.session.authenticated == true
	not recent_passkey_step_up
}
