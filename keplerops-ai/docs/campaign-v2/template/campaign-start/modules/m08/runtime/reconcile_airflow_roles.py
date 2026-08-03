from airflow.providers.fab.auth_manager.cli_commands.utils import get_application_builder


DAG_IDS = (
    "orion_scoped_worker_prediction",
    "orion_teacher_corpus_capture",
    "orion_teacher_corpus_revision",
    "orion_distillation_corpus_review",
    "orion_distillation_corpus_revision",
    "orion_student_training_first",
    "orion_student_training_revision",
    "orion_student_hidden_compatibility",
    "cinder_offline_student_submission",
    "cinder_artifact_proxy_training",
    "orion_vision_privacy_audit",
    "orion_protected_package_validation",
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
            for action in actions:
                permission = security_manager.create_permission(action, f"DAG:{dag_id}")
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

print("Airflow Orion extraction workflow permissions reconciled")
