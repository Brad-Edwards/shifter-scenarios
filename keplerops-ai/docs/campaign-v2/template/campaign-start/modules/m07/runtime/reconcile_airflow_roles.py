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
ROLE_NAME = "Orion Integrity Runner"


with get_application_builder() as appbuilder:
    security_manager = appbuilder.sm
    source = security_manager.find_role("Orion Runner")
    if source is None:
        raise RuntimeError("Airflow source role is unavailable: Orion Runner")
    role = security_manager.find_role(ROLE_NAME) or security_manager.add_role(ROLE_NAME)
    for permission in tuple(role.permissions):
        security_manager.remove_permission_from_role(role, permission)
    for permission in source.permissions:
        if permission.resource.name != "DAGs" and not permission.resource.name.startswith("DAG:"):
            security_manager.add_permission_to_role(role, permission)
    for dag_id in DAG_IDS:
        resource = f"DAG:{dag_id}"
        for action in ("can_read", "can_edit"):
            permission = security_manager.create_permission(action, resource)
            security_manager.add_permission_to_role(role, permission)
    security_manager.session.commit()

    permissions = {
        (permission.action.name, permission.resource.name)
        for permission in security_manager.find_role(ROLE_NAME).permissions
    }
    if any(resource == "DAGs" for _, resource in permissions):
        raise RuntimeError(f"{ROLE_NAME} has unscoped DAG access")
    for dag_id in DAG_IDS:
        for action in ("can_read", "can_edit"):
            if (action, f"DAG:{dag_id}") not in permissions:
                raise RuntimeError(f"{ROLE_NAME} lacks {action} on {dag_id}")

print("Airflow Orion integrity workflow permissions reconciled")
