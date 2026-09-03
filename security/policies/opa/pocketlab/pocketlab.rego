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

governance_parameters := object.get(data, "parameters", {})
admin_device_remove_approval := object.get(governance_parameters, "admin_device_remove_approval", 1)
operator_device_remove_approval := object.get(governance_parameters, "operator_device_remove_approval", 1)

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

# Owner is Pocket Lab's root-equivalent human authority. Owner never depends on
# another human approval, but the hard target/revision/server-host invariants
# above remain mandatory and the decision remains observable/auditable.
decision := {
	"allow": true,
	"constraints": ["confirmed_retirement", "validated_revision", "owner_authority"],
	"reason_code": "owner_authority_device_removal",
} if {
	enterprise_device_removal_safe
	input.actor.role == "Owner"
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
	input.actor.role == "Admin"
	admin_device_remove_approval != 0
	not input.continuation.matching_independent_approval
}

decision := {
	"allow": false,
	"constraints": ["independent_approval", "active_owner_or_admin", "passkey_step_up"],
	"reason_code": "approval_required",
	"requirements": {"required_approver_roles": ["Owner", "Admin"], "required_assurance": "policy.approval.device.remove", "approval_lifetime_seconds": 900},
} if {
	enterprise_device_removal_safe
	input.actor.role == "Operator"
	operator_device_remove_approval != 0
	not input.continuation.matching_independent_approval
}

decision := {
	"allow": true,
	"constraints": ["confirmed_retirement", "validated_revision", "independent_approval_consumed"],
	"reason_code": "independent_approval_satisfied",
} if {
	enterprise_device_removal_safe
	input.actor.role in {"Admin", "Operator"}
	input.continuation.matching_independent_approval == true
}

decision := {
	"allow": true,
	"constraints": ["confirmed_retirement", "validated_revision", "delegated_direct_authority"],
	"reason_code": "delegated_device_removal_allowed",
} if {
	enterprise_device_removal_safe
	input.actor.role == "Admin"
	admin_device_remove_approval == 0
}

decision := {
	"allow": true,
	"constraints": ["confirmed_retirement", "validated_revision", "delegated_direct_authority"],
	"reason_code": "delegated_device_removal_allowed",
} if {
	enterprise_device_removal_safe
	input.actor.role == "Operator"
	operator_device_remove_approval == 0
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
