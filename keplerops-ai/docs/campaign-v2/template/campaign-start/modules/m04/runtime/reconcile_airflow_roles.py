from airflow.providers.fab.auth_manager.cli_commands.utils import get_application_builder


DAG_IDS = (
    "orion_support_context_audit",
    "orion_routing_policy_audit",
    "orion_privacy_calibration",
    "orion_individual_membership_audit",
    "orion_cohort_membership_audit",
    "orion_preview_compatibility",
    "orion_runtime_lineage_attestation",
    "orion_factuality_evaluation",
    "orion_prompt_renderer_compatibility",
    "orion_agent_capability_audit",
)


with get_application_builder() as appbuilder:
    security_manager = appbuilder.sm
    for role_name, actions in {
        "Orion Viewer": ("can_read",),
        "Orion Runner": ("can_read", "can_edit"),
    }.items():
        role = security_manager.find_role(role_name)
        if role is None:
            raise RuntimeError(f"Airflow role is unavailable: {role_name}")
        for dag_id in DAG_IDS:
            for action in actions:
                permission = security_manager.create_permission(action, f"DAG:{dag_id}")
                security_manager.add_permission_to_role(role, permission)
    security_manager.session.commit()

    for role_name, actions in {
        "Orion Viewer": ("can_read",),
        "Orion Runner": ("can_read", "can_edit"),
    }.items():
        permissions = {
            (permission.action.name, permission.resource.name)
            for permission in security_manager.find_role(role_name).permissions
        }
        for dag_id in DAG_IDS:
            for action in actions:
                if (action, f"DAG:{dag_id}") not in permissions:
                    raise RuntimeError(f"{role_name} lacks {action} on {dag_id}")

print("Airflow Orion evaluation-reader permissions reconciled")
