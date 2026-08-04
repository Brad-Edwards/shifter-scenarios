import os

from airflow.providers.fab.auth_manager.cli_commands.utils import get_application_builder


DAG_IDS = (
    "orion_visible_release_evaluation",
    "orion_candidate_registration",
    "orion_lineage_resolution",
    "orion_candidate_approval",
    "orion_image_compatibility_decision",
    "orion_release_signing",
    "orion_production_canary_promotion",
    "orion_upstream_release_intake",
    "orion_import_exception_review",
    "orion_upstream_mirror_sync",
    "orion_mirror_review",
    "orion_staging_reconciliation",
)
ROLE_NAME = "Orion Release Runner"
PARTICIPANT_USER = os.getenv("M09_PARTICIPANT_USER", "svc-orion-release-runner")
PARTICIPANT_PASSWORD = os.getenv("M09_PARTICIPANT_PASSWORD", "KeplerV2-M09-Release-Runner-2026")
PARTICIPANT_EMAIL = os.getenv("M09_PARTICIPANT_EMAIL", "svc-orion-release-runner@keplerops.lab")


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
    unexpected = [
        resource for _, resource in permissions
        if resource.startswith("DAG:") and resource.removeprefix("DAG:") not in DAG_IDS
    ]
    if unexpected:
        raise RuntimeError(f"{ROLE_NAME} has non-M09 DAG access: {', '.join(sorted(unexpected))}")
    for dag_id in DAG_IDS:
        for action in ("can_read", "can_edit"):
            if (action, f"DAG:{dag_id}") not in permissions:
                raise RuntimeError(f"{ROLE_NAME} lacks {action} on {dag_id}")

    user = security_manager.find_user(username=PARTICIPANT_USER)
    if user is None:
        user = security_manager.add_user(
            username=PARTICIPANT_USER,
            first_name="Orion",
            last_name="Release",
            email=PARTICIPANT_EMAIL,
            role=[role],
            password=PARTICIPANT_PASSWORD,
        )
        if user is None:
            raise RuntimeError(f"failed to create Airflow user {PARTICIPANT_USER}")
    else:
        user.first_name = "Orion"
        user.last_name = "Release"
        user.email = PARTICIPANT_EMAIL
        user.roles = [role]
        if not security_manager.reset_password(user.id, PARTICIPANT_PASSWORD):
            raise RuntimeError(f"failed to reset Airflow password for {PARTICIPANT_USER}")
        if not security_manager.update_user(user):
            raise RuntimeError(f"failed to update Airflow user {PARTICIPANT_USER}")
        security_manager.session.commit()

print("Airflow Orion release workflow permissions reconciled")
