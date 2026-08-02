from airflow.providers.fab.auth_manager.cli_commands.utils import get_application_builder


DAG_IDS = (
    "engineering_inventory",
    "orion_clean_training",
    "orion_partner_intake",
    "orion_release_risk_training",
    "orion_evaluation_replay",
)
ROLE_SOURCES = {
    "Orion Viewer": ("Viewer", "can_read"),
    "Orion Runner": ("User", "can_edit"),
}


def reconcile_role(security_manager, target_name, source_name, dag_action):
    source = security_manager.find_role(source_name)
    if source is None:
        raise RuntimeError(f"Airflow source role is unavailable: {source_name}")

    target = security_manager.find_role(target_name) or security_manager.add_role(target_name)
    for permission in tuple(target.permissions):
        security_manager.remove_permission_from_role(target, permission)

    for permission in source.permissions:
        if permission.resource.name != "Dags":
            security_manager.add_permission_to_role(target, permission)

    for dag_id in DAG_IDS:
        resource = f"DAG:{dag_id}"
        read_permission = security_manager.create_permission("can_read", resource)
        security_manager.add_permission_to_role(target, read_permission)
        if dag_action == "can_edit":
            edit_permission = security_manager.create_permission("can_edit", resource)
            security_manager.add_permission_to_role(target, edit_permission)

    security_manager.session.commit()


with get_application_builder() as appbuilder:
    for role_name, (source_role, dag_action) in ROLE_SOURCES.items():
        reconcile_role(appbuilder.sm, role_name, source_role, dag_action)

    for role_name in ROLE_SOURCES:
        role = appbuilder.sm.find_role(role_name)
        permissions = {
            (permission.action.name, permission.resource.name)
            for permission in role.permissions
        }
        if any(resource == "Dags" for _, resource in permissions):
            raise RuntimeError(f"{role_name} has unscoped DAG access")
        for dag_id in DAG_IDS:
            if ("can_read", f"DAG:{dag_id}") not in permissions:
                raise RuntimeError(f"{role_name} cannot read {dag_id}")
        if role_name == "Orion Viewer" and any(
            action == "can_edit" and resource.startswith("DAG:")
            for action, resource in permissions
        ):
            raise RuntimeError("Orion Viewer has DAG edit permission")

print("Airflow Orion Viewer and Orion Runner roles reconciled")
