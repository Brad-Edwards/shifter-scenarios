import os

from airflow.providers.fab.auth_manager.security_manager.override import (
    FabAirflowSecurityManagerOverride,
)
from flask_appbuilder.const import AUTH_OAUTH


AUTH_TYPE = AUTH_OAUTH
AUTH_USER_REGISTRATION = True
AUTH_USER_REGISTRATION_ROLE = "Public"
AUTH_ROLES_SYNC_AT_LOGIN = True
AUTH_ROLES_MAPPING = {
    "RG-Airflow-Orion-View": ["Orion Viewer"],
    "RG-Airflow-Orion-Run": ["Orion Runner"],
}

OAUTH_PROVIDERS = [
    {
        "name": "keycloak",
        "icon": "fa-key",
        "token_key": "access_token",
        "remote_app": {
            "client_id": os.environ["AIRFLOW_OIDC_CLIENT_ID"],
            "client_secret": os.environ["AIRFLOW_OIDC_CLIENT_SECRET"],
            "server_metadata_url": os.environ["AIRFLOW_OIDC_METADATA_URL"],
            "api_base_url": os.environ["AIRFLOW_OIDC_USERINFO_BASE_URL"],
            "access_token_url": os.environ["AIRFLOW_OIDC_TOKEN_URL"],
            "authorize_url": os.environ["AIRFLOW_OIDC_AUTHORIZE_URL"],
            "request_token_url": None,
            "client_kwargs": {"scope": "openid profile email"},
        },
    }
]


class KeplerOpsAirflowSecurityManager(FabAirflowSecurityManagerOverride):
    """Reject SSO users that have no explicit Orion Airflow grant."""

    def get_oauth_user_info(self, provider, response):
        userinfo = super().get_oauth_user_info(provider, response)
        allowed = set(AUTH_ROLES_MAPPING)
        if not allowed.intersection(userinfo.get("role_keys", [])):
            return {}
        return userinfo


SECURITY_MANAGER_CLASS = KeplerOpsAirflowSecurityManager
