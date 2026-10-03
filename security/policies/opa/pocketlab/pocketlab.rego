package pocketlab.authz

import rego.v1

default decision := {
	"allow": false,
	"constraints": [],
	"reason_code": "actor_not_authenticated",
}

authenticated_actor if {
	input.actor.type in {"human", "service", "qualification", "test", "maintenance", "synthetic_machine"}
	input.session.authenticated == true
}

synthetic_actor if {
	input.harness.enabled == true
}

harness_target_bound if {
	input.target.type != "device"
}

harness_target_bound if {
	input.target.type == "device"
	input.harness.profile == "fleet-role-qualifier"
	input.harness.target_device_id != ""
	input.harness.target_device_id == input.target.id
}

harness_authorized if {
	synthetic_actor
	input.harness.qualification_environment == true
	input.harness.target_scope == input.target.scope
	harness_target_bound
	input.action.id in input.harness.capabilities
	not (input.action.id in {"device.remove", "restore.apply", "backup.location.manage", "rules.activate", "rules.rollback"})
}

harness_authorized if {
	synthetic_actor
	input.harness.qualification_environment == true
	input.harness.target_scope == input.target.scope
	harness_target_bound
	input.action.id in input.harness.capabilities
	input.harness.destructive_allowed == true
}

authorized_actor if {
	authenticated_actor
	not synthetic_actor
}

authorized_actor if {
	authenticated_actor
	harness_authorized
}

default governance_parameters := {}

governance_parameters := data.parameters

admin_device_remove_approval := object.get(governance_parameters, "admin_device_remove_approval", 1)
operator_device_remove_approval := object.get(governance_parameters, "operator_device_remove_approval", 1)
admin_storage_role_approval := object.get(governance_parameters, "admin_storage_role_approval", 1)
operator_storage_role_approval := object.get(governance_parameters, "operator_storage_role_approval", 1)

recovery_action if {
	input.action.id in {"backup.create", "backup.verify", "restore.preview"}
	authorized_actor
	input.target.type == "recovery"
	input.target.id != ""
}

backup_location_action if {
	input.action.id == "backup.location.manage"
	authorized_actor
	input.target.type == "recovery_location"
	input.target.id != ""
	input.target.state.protected_server_host == true
}

decision := {
	"allow": true,
	"constraints": ["authenticated_actor", "protected_server_host"],
	"reason_code": "authenticated_backup_location_operation",
} if {
	backup_location_action
}

decision := {
	"allow": true,
	"constraints": ["authenticated_actor", "recovery_target"],
	"reason_code": "authenticated_recovery_operation",
} if {
	recovery_action
}

decision := {
	"allow": true,
	"constraints": ["authenticated_actor", "confirmed_restore", "bound_preview", "owner_authority"],
	"reason_code": "owner_authority_restore",
} if {
	input.action.id == "restore.apply"
	authorized_actor
	input.target.type == "recovery"
	input.target.id != ""
	input.actor.role == "Owner"
	input.actor.owner_authority == true
	input.target.state.confirmed == true
	input.target.state.preview_bound == true
	input.target.state.restorable == true
}

decision := {
	"allow": false,
	"constraints": ["owner_authority"],
	"reason_code": "recovery_owner_required",
} if {
	input.action.id == "restore.apply"
	authorized_actor
	input.target.type == "recovery"
	input.target.id != ""
	not (input.actor.role == "Owner")
}

# Legacy catalog.install remains registered for compatibility, but follows the
# same Enterprise role boundary as app.install so old endpoints cannot bypass
# app-resource governance.
decision := {
	"allow": true,
	"constraints": ["owner_authority", "legacy_action_compatibility"],
	"reason_code": "owner_authority_app_install",
} if {
	input.action.id == "catalog.install"
	authorized_actor
	input.target.type == "app"
	input.target.id != ""
	not input.actor.enterprise_enabled
	input.actor.owner_authority == true
}

decision := {
	"allow": true,
	"constraints": ["enterprise_role_authority", "legacy_action_compatibility"],
	"reason_code": "enterprise_app_install_allowed",
} if {
	input.action.id == "catalog.install"
	authorized_actor
	input.target.type == "app"
	input.target.id != ""
	input.actor.enterprise_enabled == true
	input.actor.role in {"Owner", "Admin"}
}

decision := {
	"allow": true,
	"constraints": ["exact_temporary_exception", "legacy_action_compatibility"],
	"reason_code": "app_temporary_exception_satisfied",
} if {
	input.action.id == "catalog.install"
	authorized_actor
	input.target.type == "app"
	input.target.id != ""
	input.actor.enterprise_enabled == true
	input.actor.role == "Operator"
	input.continuation.matching_temporary_exception == true
}

decision := {
	"allow": false,
	"constraints": ["exact_temporary_exception"],
	"reason_code": "temporary_exception_required",
} if {
	input.action.id == "catalog.install"
	authorized_actor
	input.target.type == "app"
	input.actor.enterprise_enabled == true
	input.actor.role == "Operator"
	not input.continuation.matching_temporary_exception
}

decision := {
	"allow": false,
	"constraints": ["enterprise_role_not_eligible"],
	"reason_code": "enterprise_role_forbidden",
} if {
	input.action.id == "catalog.install"
	authorized_actor
	input.target.type == "app"
	input.actor.enterprise_enabled == true
	input.actor.role in {"Viewer", "Auditor"}
}

# Canonical app-resource governance.  Every protected semantic action must be
# bound to registry-derived capability/platform/placement truth.
semantic_app_action if {
	input.action.id in {
		"app.install",
		"app.security_check",
		"app.repair",
		"app.backup.create",
		"app.backup.to_storage",
		"app.restore.preview",
		"app.update.check",
		"app.remove",
		"app.credentials.manage",
	}
}

app_resource_ready if {
	semantic_app_action
	authorized_actor
	input.target.type == "app"
	input.target.id != ""
	input.target.state.resource_type == "app"
	input.target.state.app_id == input.target.id
	input.target.state.semantic_action == input.action.id
	input.target.state.required_capability != ""
	input.target.state.capability_supported == true
	input.target.state.platform_supported == true
	input.target.state.placement_ready == true
	input.target.state.contract_revision == input.target.revision
	input.target.state.request_fingerprint == input.target.revision
}

decision := {
	"allow": false,
	"constraints": ["canonical_app_resource", "declared_capability", "verified_placement"],
	"reason_code": "app_resource_invalid",
} if {
	semantic_app_action
	authorized_actor
	not app_resource_ready
}

decision := {
	"allow": true,
	"constraints": ["canonical_app_resource", "owner_authority", "declared_capability", "verified_placement"],
	"reason_code": "owner_authority_app_operation",
} if {
	app_resource_ready
	not input.actor.enterprise_enabled
	input.actor.owner_authority == true
}

decision := {
	"allow": true,
	"constraints": ["canonical_app_resource", "owner_authority", "declared_capability", "verified_placement"],
	"reason_code": "owner_authority_app_operation",
} if {
	app_resource_ready
	input.actor.enterprise_enabled == true
	input.actor.role == "Owner"
}

decision := {
	"allow": true,
	"constraints": ["canonical_app_resource", "delegated_app_authority"],
	"reason_code": "enterprise_app_operation_allowed",
} if {
	app_resource_ready
	input.actor.enterprise_enabled == true
	input.actor.role == "Admin"
	input.action.id != "app.remove"
}

operator_app_action if {
	input.action.id in {
		"app.security_check",
		"app.repair",
		"app.backup.create",
		"app.backup.to_storage",
		"app.restore.preview",
		"app.update.check",
	}
}

decision := {
	"allow": true,
	"constraints": ["canonical_app_resource", "delegated_app_authority"],
	"reason_code": "enterprise_app_operation_allowed",
} if {
	app_resource_ready
	input.actor.enterprise_enabled == true
	input.actor.role == "Operator"
	operator_app_action
}

decision := {
	"allow": true,
	"constraints": ["canonical_app_resource", "exact_temporary_exception"],
	"reason_code": "app_temporary_exception_satisfied",
} if {
	app_resource_ready
	input.actor.enterprise_enabled == true
	input.actor.role == "Operator"
	input.action.id == "app.install"
	input.continuation.matching_temporary_exception == true
}

decision := {
	"allow": false,
	"constraints": ["exact_temporary_exception"],
	"reason_code": "temporary_exception_required",
} if {
	app_resource_ready
	input.actor.enterprise_enabled == true
	input.actor.role == "Operator"
	input.action.id == "app.install"
	not input.continuation.matching_temporary_exception
}

decision := {
	"allow": false,
	"constraints": ["enterprise_role_not_eligible"],
	"reason_code": "enterprise_role_forbidden",
} if {
	app_resource_ready
	input.actor.enterprise_enabled == true
	input.actor.role in {"Viewer", "Auditor"}
}

decision := {
	"allow": false,
	"constraints": ["independent_approval", "active_owner_or_admin"],
	"reason_code": "approval_required",
	"requirements": {
		"required_approver_roles": ["Owner", "Admin"],
		"required_assurance": "policy.approval.app.remove",
		"approval_lifetime_seconds": 900,
	},
} if {
	app_resource_ready
	input.actor.enterprise_enabled == true
	input.actor.role in {"Admin", "Operator"}
	input.action.id == "app.remove"
	not input.continuation.matching_independent_approval
}

decision := {
	"allow": true,
	"constraints": ["canonical_app_resource", "independent_approval_consumed"],
	"reason_code": "independent_approval_satisfied",
} if {
	app_resource_ready
	input.actor.enterprise_enabled == true
	input.actor.role in {"Admin", "Operator"}
	input.action.id == "app.remove"
	input.continuation.matching_independent_approval == true
}

fleet_mutation if {
	input.action.id in {"device.invite", "device.roles.change", "device.restart", "device.repair"}
	authorized_actor
	input.target.type == "device"
	input.target.id != ""
}

delegated_fleet_operator if {
	input.actor.role in {"Admin", "Operator"}
}

storage_role_change if {
	input.target.state.storage_role_change == true
}

delegated_storage_review_enabled if {
	input.actor.role == "Admin"
	admin_storage_role_approval != 0
}

delegated_storage_review_enabled if {
	input.actor.role == "Operator"
	operator_storage_role_approval != 0
}

fleet_required_assurance := "policy.approval.device.invite" if {
	input.action.id == "device.invite"
}

fleet_required_assurance := "policy.approval.device.roles.change" if {
	input.action.id == "device.roles.change"
}

decision := {
	"allow": true,
	"constraints": ["owner_authority", "server_bound_device_roles"],
	"reason_code": "owner_authority_fleet_change",
} if {
	fleet_mutation
	not input.actor.enterprise_enabled
	input.actor.owner_authority == true
}

decision := {
	"allow": true,
	"constraints": ["owner_authority", "server_bound_device_roles"],
	"reason_code": "owner_authority_fleet_change",
} if {
	fleet_mutation
	input.actor.enterprise_enabled == true
	input.actor.role == "Owner"
}

decision := {
	"allow": true,
	"constraints": ["delegated_operational_authority"],
	"reason_code": "delegated_fleet_operation_allowed",
} if {
	fleet_mutation
	input.actor.enterprise_enabled == true
	delegated_fleet_operator
	input.action.id in {"device.restart", "device.repair"}
}

decision := {
	"allow": true,
	"constraints": ["delegated_role_authority", "non_storage_role_change"],
	"reason_code": "delegated_device_role_change_allowed",
} if {
	fleet_mutation
	input.actor.enterprise_enabled == true
	delegated_fleet_operator
	input.action.id in {"device.invite", "device.roles.change"}
	not storage_role_change
}

decision := {
	"allow": true,
	"constraints": ["delegated_role_authority", "storage_role_change", "policy_direct"],
	"reason_code": "delegated_storage_role_change_allowed",
} if {
	fleet_mutation
	input.actor.enterprise_enabled == true
	delegated_fleet_operator
	input.action.id in {"device.invite", "device.roles.change"}
	storage_role_change
	not delegated_storage_review_enabled
}

decision := {
	"allow": false,
	"constraints": ["independent_approval", "active_owner_or_admin", "exact_role_set"],
	"reason_code": "approval_required",
	"requirements": {
		"required_approver_roles": ["Owner", "Admin"],
		"required_assurance": fleet_required_assurance,
		"approval_lifetime_seconds": 900,
	},
} if {
	fleet_mutation
	input.actor.enterprise_enabled == true
	delegated_fleet_operator
	input.action.id in {"device.invite", "device.roles.change"}
	storage_role_change
	delegated_storage_review_enabled
	not input.continuation.matching_independent_approval
}

decision := {
	"allow": true,
	"constraints": ["independent_approval_consumed", "exact_role_set"],
	"reason_code": "independent_approval_satisfied",
} if {
	fleet_mutation
	input.actor.enterprise_enabled == true
	delegated_fleet_operator
	input.action.id in {"device.invite", "device.roles.change"}
	storage_role_change
	delegated_storage_review_enabled
	input.continuation.matching_independent_approval == true
}

decision := {
	"allow": false,
	"constraints": ["enterprise_role_not_eligible"],
	"reason_code": "enterprise_role_forbidden",
} if {
	fleet_mutation
	input.actor.enterprise_enabled == true
	input.actor.role in {"Viewer", "Auditor"}
}

decision := {
	"allow": true,
	"constraints": ["authenticated_actor", "confirmed_retirement", "validated_revision", "personal_mode"],
	"reason_code": "authenticated_confirmed_device_removal",
} if {
	input.action.id == "device.remove"
	authorized_actor
	input.target.type == "device"
	input.target.state.confirmed == true
	input.target.state.revision_validated == true
	input.target.state.protected_server_host == false
	not input.actor.enterprise_enabled
}

enterprise_device_removal_safe if {
	input.actor.enterprise_enabled == true
	input.action.id == "device.remove"
	authorized_actor
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
	"requirements": {
		"required_approver_roles": ["Owner", "Admin"],
		"required_assurance": "policy.approval.device.remove",
		"approval_lifetime_seconds": 900,
	},
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
	"requirements": {
		"required_approver_roles": ["Owner", "Admin"],
		"required_assurance": "policy.approval.device.remove",
		"approval_lifetime_seconds": 900,
	},
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
	input.actor.role == "Admin"
	admin_device_remove_approval != 0
	input.continuation.matching_independent_approval == true
}

decision := {
	"allow": true,
	"constraints": ["confirmed_retirement", "validated_revision", "independent_approval_consumed"],
	"reason_code": "independent_approval_satisfied",
} if {
	enterprise_device_removal_safe
	input.actor.role == "Operator"
	operator_device_remove_approval != 0
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
	authorized_actor
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
	authorized_actor
	input.session.authenticated == true
	not recent_passkey_step_up
}
