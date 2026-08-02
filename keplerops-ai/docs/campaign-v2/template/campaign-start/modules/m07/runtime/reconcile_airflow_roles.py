from airflow.providers.fab.auth_manager.cli_commands.utils import get_application_builder


DAG_IDS = (
    "orion_release_risk_training",
    "orion_label_export",
    "orion_integrity_training",
    "orion_integrity_review",
    "orion_upstream_sync",
    "orion_holdout_evaluation",
    "orion_graph_review",
    "orion_dataset_attestation",
)
ROLE_ACTIONS = {
    "Orion Viewer": ("can_read",),
    "Orion Runner": ("can_read", "can_edit"),
}


with get_application_builder() as appbuilder:
    security_manager = appbuilder.sm
    for role_name, actions in ROLE_ACTIONS.items():
        role = security_manager.find_role(role_name)
        if role is None:
            raise RuntimeError(f"Airflow role is unavailable: {role_name}")
        for dag_id in DAG_IDS:
            resource = f"DAG:{dag_id}"
            for action in actions:
                permission = security_manager.create_permission(action, resource)
                security_manager.add_permission_to_role(role, permission)
    security_manager.session.commit()

    for role_name, actions in ROLE_ACTIONS.items():
        permissions = {
            (permission.action.name, permission.resource.name)
            for permission in security_manager.find_role(role_name).permissions
        }
        for dag_id in DAG_IDS:
            for action in actions:
                if (action, f"DAG:{dag_id}") not in permissions:
                    raise RuntimeError(f"{role_name} lacks {action} on {dag_id}")

print("Airflow Orion integrity workflow permissions reconciled")
