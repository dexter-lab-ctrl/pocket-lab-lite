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
	not input.action.id in {"device.remove", "restore.apply", "backup.location.manage", "rules.activate", "rules.rollback"}
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

system_health_recovery_action if {
	input.action.id == "system_health.recovery"
	authorized_actor
	input.target.type == "system_health_incident"
	input.target.id != ""
	input.target.state.operation_id == "runtime.consumer.reconnect"
	input.target.state.adapter_enabled == true
	input.target.state.preflight_valid == true
	input.target.state.incident_generation > 0
	input.target.state.enrollment_generation >= 0
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

# Owner-approved operations are a single registered capability, not a generic
# maintenance executor.  The service also rejects synthetic principals and
# revalidates the target before the durable transition; this rule makes the
# human Owner and passkey step-up requirement visible to the policy engine.
owner_operation_target if {
	input.action.id == "owner.operations.approve"
	input.target.type == "owner_operation"
	input.target.id != ""
	input.target.revision != ""
	input.target.state.contract_version == 1
	input.target.state.operation == "photo_backup.bounded_acceptance.v1"
	input.target.state.status == "pending_approval"
	input.target.state.target_node_id != ""
	input.target.state.target_binding_digest != ""
	input.target.state.destination_id == "server-photoprism-originals"
	input.target.state.destination_contract_version == 2
	input.target.state.scope_digest != ""
	input.target.revision == input.target.state.scope_digest
	time.parse_rfc3339_ns(input.target.state.approval_deadline) > time.now_ns()
}

owner_operation_owner if {
	input.actor.type == "human"
	not input.actor.synthetic
	input.actor.owner_authority == true
	input.actor.role == "Owner"
	input.session.authenticated == true
}

owner_operation_step_up if {
	some item in input.session.assurance
	item.purpose == "owner.operations.approve"
	item.expires_at != ""
	time.parse_rfc3339_ns(item.expires_at) > time.now_ns()
}

decision := {
	"allow": true,
	"constraints": ["authenticated_actor", "owner_authority", "exact_operation_contract", "passkey_step_up"],
	"reason_code": "owner_operation_approval_allowed",
} if {
	owner_operation_target
	owner_operation_owner
	owner_operation_step_up
}

decision := {
	"allow": false,
	"constraints": ["passkey_step_up"],
	"reason_code": "passkey_step_up_required",
} if {
	owner_operation_target
	owner_operation_owner
	not owner_operation_step_up
}

decision := {
	"allow": false,
	"constraints": ["owner_authority", "authenticated_actor"],
	"reason_code": "owner_authority_required",
} if {
	owner_operation_target
	not owner_operation_owner
}

decision := {
	"allow": false,
	"constraints": ["exact_operation_contract", "immutable_scope"],
	"reason_code": "owner_operation_invalid",
} if {
	input.action.id == "owner.operations.approve"
	not owner_operation_target
}

# Automation-client enrollment is a distinct protected action.  Pairing is
# only a pending, fixed-capability record; registration happens in the
# server-owned SQLite transaction after this decision and passkey step-up.
client_pairing_target if {
	input.action.id == "owner.operations.client.register"
	input.target.type == "owner_operation_client_pairing"
	input.target.id != ""
	input.target.revision != ""
	input.target.state.registration_mode == "pairing"
	input.target.state.client_id != ""
	input.target.state.public_key_fingerprint != ""
	input.target.state.capabilities == ["photo_backup.bounded_acceptance.v1"]
	input.target.state.status == "pending"
	input.target.state.pairing_binding_digest != ""
	input.target.revision == input.target.state.pairing_binding_digest
	time.parse_rfc3339_ns(input.target.state.expires_at) > time.now_ns()
}

client_revoke_target if {
	input.action.id == "owner.operations.client.register"
	input.target.type == "owner_operation_client"
	input.target.id != ""
	input.target.revision != ""
	input.target.state.registration_mode == "revoke"
	input.target.state.client_id == input.target.id
	input.target.state.public_key_fingerprint == input.target.revision
	input.target.state.capabilities == ["photo_backup.bounded_acceptance.v1"]
	input.target.state.status == "active"
}

client_registration_target if {
	client_pairing_target
}

client_registration_target if {
	client_revoke_target
}

client_registration_step_up if {
	some item in input.session.assurance
	item.purpose == "owner.operations.client.register"
	item.expires_at != ""
	time.parse_rfc3339_ns(item.expires_at) > time.now_ns()
}

decision := {
	"allow": true,
	"constraints": ["authenticated_actor", "owner_authority", "exact_client_contract", "passkey_step_up"],
	"reason_code": "owner_operation_client_registration_allowed",
} if {
	client_registration_target
	owner_operation_owner
	client_registration_step_up
}

decision := {
	"allow": false,
	"constraints": ["passkey_step_up"],
	"reason_code": "passkey_step_up_required",
} if {
	client_registration_target
	owner_operation_owner
	not client_registration_step_up
}

decision := {
	"allow": false,
	"constraints": ["owner_authority", "authenticated_actor"],
	"reason_code": "owner_authority_required",
} if {
	client_registration_target
	not owner_operation_owner
}

decision := {
	"allow": false,
	"constraints": ["exact_client_contract", "immutable_capability"],
	"reason_code": "owner_operation_client_invalid",
} if {
	input.action.id == "owner.operations.client.register"
	not client_registration_target
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
	"constraints": ["authenticated_actor", "system_health_target", "owner_authority", "fresh_preflight"],
	"reason_code": "owner_authority_system_health_recovery",
} if {
	system_health_recovery_action
	input.actor.type == "human"
	input.actor.role == "Owner"
	input.actor.owner_authority == true
}

decision := {
	"allow": true,
	"constraints": ["authenticated_actor", "system_health_target", "qualification_scope", "fresh_preflight"],
	"reason_code": "qualification_owner_system_health_recovery",
} if {
	system_health_recovery_action
	input.actor.type == "qualification"
	input.actor.role == "Owner"
	input.harness.profile == "qualification-owner"
}

decision := {
	"allow": true,
	"constraints": ["system_health_target", "independent_approval_consumed", "fresh_preflight"],
	"reason_code": "independent_approval_satisfied",
} if {
	system_health_recovery_action
	input.actor.enterprise_enabled == true
	input.actor.role in {"Admin", "Operator"}
	input.continuation.matching_independent_approval == true
}

decision := {
	"allow": false,
	"constraints": ["independent_approval", "active_owner_or_admin", "fresh_preflight"],
	"reason_code": "approval_required",
	"requirements": {
		"required_approver_roles": ["Owner", "Admin"],
		"required_assurance": "policy.approval.system_health.recovery",
		"approval_lifetime_seconds": 900,
	},
} if {
	system_health_recovery_action
	input.actor.enterprise_enabled == true
	input.actor.role in {"Admin", "Operator"}
	not input.continuation.matching_independent_approval
}

decision := {
	"allow": false,
	"constraints": ["enterprise_role_not_eligible"],
	"reason_code": "enterprise_role_forbidden",
} if {
	system_health_recovery_action
	input.actor.enterprise_enabled == true
	input.actor.role in {"Viewer", "Auditor"}
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
	not input.actor.role == "Owner"
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

app_placement_requirement_satisfied if {
	input.target.state.placement_required == false
}

app_placement_requirement_satisfied if {
	input.target.state.placement_required == true
	input.target.state.placement_ready == true
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
	app_placement_requirement_satisfied
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


# Fixed, owner-only maintenance adapter. Runtime qualification/activation,
# exact preview binding and pre-execution authority checks are enforced by
# FastAPI and the existing maintenance worker, never a browser.
decision := {
    "allow": true,
    "constraints": ["owner_authority", "fixed_maintenance_operation", "confirmation"],
    "reason_code": "owner_authority_system_health_maintenance",
} if {
    input.action.id == "system_health.maintenance"
    authorized_actor
    input.actor.type == "human"
    input.actor.role == "Owner"
    input.actor.owner_authority == true
    input.target.type == "system_health_maintenance"
    input.target.id != ""
    input.target.state.operation_id in {"storage.evidence.preview", "storage.evidence.retention", "sqlite.checkpoint.passive", "maintenance.uncertain.resolve", "recovery.database.rehearse", "projection.reconcile", "storage.logs.preview", "storage.logs.cleanup", "storage.temp.preview", "storage.temp.cleanup", "automation.policy.update", "runtime.telemetry.recover", "runtime.server_agent.recover", "runtime.configuration.restore"}
    input.target.state.adapter_enabled == true
    input.target.state.confirmed == true
}


# Internal worker-only fixed Risk A projection reconciliation. The durable
# Owner policy and all runtime gates are constructed by the worker, not HTTP.
decision := {
    "allow": true,
    "constraints": ["fixed_projection", "risk_a_only", "current_owner_policy"],
    "reason_code": "system_health_projection_reconciliation",
} if {
    input.action.id == "system_health.automatic"
    authorized_actor
    input.actor.type == "service"
    input.actor.id == "system-health-scheduler"
    input.session.auth_method == "internal_worker"
    input.target.type == "system_health_projection"
    input.target.id == "system.activity_history"
    input.target.state.operation_id == "projection.reconcile"
    input.target.state.risk_class == "A"
    input.target.state.adapter_enabled == true
    input.target.state.owner_policy_current == true
}

# Lifecycle consent is intentionally limited to recording preferences or a
# non-executing boundary. No service, qualification actor or approval exception
# may use this rule to activate policy, install releases or perform maintenance.
lifecycle_consent_target if {
    input.action.id in {"lifecycle.preferences.manage", "lifecycle.authority.manage"}
    input.target.type == "lifecycle_consent"
    input.target.id == "local_workspace"
    input.target.revision == input.target.state.change_digest
    input.target.state.contract_version == 1
    input.target.state.execution_enabled == false
    input.request.confirmation_present == true
    input.actor.type == "human"
    input.actor.role == "Owner"
    input.actor.owner_authority == true
    input.session.authenticated == true
    not synthetic_actor
    # Managed authority issuance requires a separately qualified Enterprise
    # approval design. A preference alone remains non-authorizing.
    input.actor.enterprise_enabled == false
}

lifecycle_exact_assurance if {
    some item in input.session.assurance
    item.purpose == concat("", ["lifecycle:", input.target.revision])
    time.parse_rfc3339_ns(item.expires_at) > time.now_ns()
}

decision := {
    "allow": true,
    "constraints": ["owner_authority", "exact_passkey_consent", "no_execution"],
    "reason_code": "lifecycle_consent_record_only",
} if {
    lifecycle_consent_target
    lifecycle_exact_assurance
}

decision := {
    "allow": false,
    "constraints": ["exact_passkey_consent"],
    "reason_code": "passkey_step_up_required",
} if {
    lifecycle_consent_target
    not lifecycle_exact_assurance
}


# Separate execution contract, never implied by review consent.
lifecycle_policy_activation_target if {
    input.action.id == "lifecycle.policy.activate"
    input.target.type == "lifecycle_policy_execution"
    input.target.id == "local_workspace"
    input.target.revision == input.target.state.change_digest
    input.target.state.contract_version == 1
    input.target.state.purpose == "policy-reconciler"
    input.target.state.execution_enabled == true
    input.request.confirmation_present == true
    input.actor.type == "human"
    input.actor.role == "Owner"
    input.actor.owner_authority == true
    input.actor.enterprise_enabled == false
    input.session.authenticated == true
    not synthetic_actor
}

decision := {"allow": true, "constraints": ["exact_passkey_consent", "single_policy_operation"], "reason_code": "lifecycle_policy_activation_allowed"} if {
    lifecycle_policy_activation_target
    lifecycle_exact_assurance
}

decision := {"allow": false, "constraints": ["exact_passkey_consent"], "reason_code": "passkey_step_up_required"} if {
    lifecycle_policy_activation_target
    not lifecycle_exact_assurance
}

decision := {"allow": true, "constraints": ["local_supervisor", "current_exact_grant"], "reason_code": "lifecycle_policy_claim_allowed"} if {
    input.action.id == "lifecycle.policy.claim"
    input.actor.type == "service"
    input.actor.id == "policy-reconciler"
    input.actor.role == null
    input.actor.owner_authority == false
    input.session.authenticated == true
    input.session.auth_method == "local_supervisor"
    not synthetic_actor
    input.target.type == "lifecycle_policy_execution"
    input.target.id != ""
    input.target.revision == input.target.state.change_digest
    input.target.state.contract_version == 1
    input.target.state.purpose == "policy-reconciler"
    input.target.state.execution_enabled == true
    input.target.state.grant_current == true
}


# Release preparation is a distinct, exact one-shot grant. It does not
# authorize native promotion or recovery, which remain bootstrap-owned.
lifecycle_release_preparation_target if {
    input.action.id == "lifecycle.release.prepare"
    input.target.type == "lifecycle_release_preparation"
    input.target.id == "local_workspace"
    input.target.revision == input.target.state.change_digest
    input.target.state.contract_version == 1
    input.target.state.purpose == "release-reconciler"
    input.target.state.execution_enabled == true
    input.request.confirmation_present == true
    input.actor.type == "human"
    input.actor.role == "Owner"
    input.actor.owner_authority == true
    input.actor.enterprise_enabled == false
    input.session.authenticated == true
    not synthetic_actor
}

decision := {"allow": true, "constraints": ["exact_passkey_consent", "single_release_preparation", "no_native_cutover"], "reason_code": "lifecycle_release_preparation_allowed"} if {
    lifecycle_release_preparation_target
    lifecycle_exact_assurance
}

decision := {"allow": false, "constraints": ["exact_passkey_consent"], "reason_code": "passkey_step_up_required"} if {
    lifecycle_release_preparation_target
    not lifecycle_exact_assurance
}

decision := {"allow": true, "constraints": ["local_worker", "current_exact_grant", "no_native_cutover"], "reason_code": "lifecycle_release_claim_allowed"} if {
    input.action.id == "lifecycle.release.claim"
    input.actor.type == "service"
    input.actor.id == "release-reconciler"
    input.actor.role == null
    input.actor.owner_authority == false
    input.session.authenticated == true
    input.session.auth_method == "internal_worker"
    not synthetic_actor
    input.target.type == "lifecycle_release_preparation"
    input.target.id != ""
    input.target.revision == input.target.state.change_digest
    input.target.state.contract_version == 1
    input.target.state.purpose == "release-reconciler"
    input.target.state.execution_enabled == true
    input.target.state.grant_current == true
}
