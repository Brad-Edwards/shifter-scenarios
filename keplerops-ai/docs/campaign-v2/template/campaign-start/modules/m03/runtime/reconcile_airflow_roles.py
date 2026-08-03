from airflow.providers.fab.auth_manager.cli_commands.utils import get_application_builder


MANUAL_DAGS = (
    "orion_evaluation_dependency_review",
    "orion_factuality_evaluation",
    "orion_phantom_dependency_resolution",
    "orion_current_workhub_status_review",
    "orion_release_review_handoff",
    "orion_model_card_compatibility",
)
SCHEDULED_DAGS = ("orion_approved_review_follow_up",)


with get_application_builder() as appbuilder:
    security_manager = appbuilder.sm
    for role_name, actions in {
        "Orion Viewer": ("can_read",),
        "Orion Runner": ("can_read", "can_edit"),
    }.items():
        role = security_manager.find_role(role_name)
        if role is None:
            raise RuntimeError(f"Airflow role is unavailable: {role_name}")
        for dag_id in (*MANUAL_DAGS, *SCHEDULED_DAGS):
            permitted = actions if dag_id in MANUAL_DAGS else ("can_read",)
            for action in permitted:
                permission = security_manager.create_permission(action, f"DAG:{dag_id}")
                security_manager.add_permission_to_role(role, permission)
    security_manager.session.commit()

    for role_name in ("Orion Viewer", "Orion Runner"):
        permissions = {
            (permission.action.name, permission.resource.name)
            for permission in security_manager.find_role(role_name).permissions
        }
        for dag_id in (*MANUAL_DAGS, *SCHEDULED_DAGS):
            if ("can_read", f"DAG:{dag_id}") not in permissions:
                raise RuntimeError(f"{role_name} cannot read {dag_id}")
        if role_name == "Orion Runner":
            for dag_id in MANUAL_DAGS:
                if ("can_edit", f"DAG:{dag_id}") not in permissions:
                    raise RuntimeError(f"{role_name} cannot run {dag_id}")

print("Airflow Orion workflow permissions reconciled")
