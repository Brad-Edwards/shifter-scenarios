from __future__ import annotations

import os


c = get_config()  # type: ignore[name-defined]

c.JupyterHub.bind_url = "http://0.0.0.0:8000"
c.JupyterHub.hub_bind_url = "http://0.0.0.0:8081"
c.JupyterHub.hub_connect_url = "http://jupyterhub:8081"
c.JupyterHub.db_url = os.environ["JUPYTERHUB_DB_URL"]
c.JupyterHub.cookie_secret_file = "/srv/jupyterhub/state/jupyterhub_cookie_secret"
c.JupyterHub.cleanup_servers = True

c.JupyterHub.spawner_class = "dockerspawner.DockerSpawner"
c.DockerSpawner.image = os.environ["JUPYTERHUB_SINGLEUSER_IMAGE"]
c.DockerSpawner.allowed_images = [os.environ["JUPYTERHUB_SINGLEUSER_IMAGE"]]
c.DockerSpawner.network_name = os.environ.get("DOCKER_NETWORK_NAME", "kep-v2-data")
c.DockerSpawner.use_internal_ip = True
c.DockerSpawner.remove = True
c.DockerSpawner.name_template = "kep-v2-notebook-{username}"
c.DockerSpawner.volumes = {
    "kep-v2-jupyter-{raw_username}": "/home/jovyan/work",
}
c.DockerSpawner.environment = {
    "AWS_ACCESS_KEY_ID": os.environ["MINIO_ACCESS_KEY"],
    "AWS_SECRET_ACCESS_KEY": os.environ["MINIO_SECRET_KEY"],
    "AWS_ENDPOINT_URL": "http://minio:9000",
    "DVC_LAKEFS_ENDPOINT": "http://lakefs:8000",
    "MLFLOW_TRACKING_URI": "http://mlflow:5000",
    "MLFLOW_TRACKING_USERNAME": "orion-reader",
    "MLFLOW_TRACKING_PASSWORD": "KeplerV2-Training-MLflow-Read",
    "NB_UMASK": "0022",
    "QDRANT_URL": "http://qdrant:6333",
}
c.Spawner.default_url = "/lab"
c.Spawner.cpu_limit = 2
c.Spawner.mem_limit = "4G"

c.JupyterHub.authenticator_class = "oauthenticator.generic.GenericOAuthenticator"
c.GenericOAuthenticator.client_id = os.environ["JUPYTERHUB_OIDC_CLIENT_ID"]
c.GenericOAuthenticator.client_secret = os.environ["JUPYTERHUB_OIDC_CLIENT_SECRET"]
c.GenericOAuthenticator.oauth_callback_url = os.environ["JUPYTERHUB_OIDC_CALLBACK_URL"]
c.GenericOAuthenticator.authorize_url = os.environ["JUPYTERHUB_OIDC_AUTHORIZE_URL"]
c.GenericOAuthenticator.token_url = os.environ["JUPYTERHUB_OIDC_TOKEN_URL"]
c.GenericOAuthenticator.userdata_url = os.environ["JUPYTERHUB_OIDC_USERDATA_URL"]
c.GenericOAuthenticator.login_service = "KeplerOps SSO"
c.GenericOAuthenticator.username_claim = "preferred_username"
c.GenericOAuthenticator.scope = ["openid", "profile", "email"]
c.GenericOAuthenticator.manage_groups = True
c.GenericOAuthenticator.allow_all = False
c.GenericOAuthenticator.allowed_groups = {"RG-Jupyter-Orion-Evaluation"}
c.GenericOAuthenticator.auth_state_groups_key = "oauth_user.groups"
c.Authenticator.admin_users = {"range-admin"}
