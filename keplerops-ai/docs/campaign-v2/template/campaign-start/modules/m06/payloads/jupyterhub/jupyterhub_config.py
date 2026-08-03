from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from pathlib import Path

from jupyterhub.handlers import BaseHandler
from kubernetes import client, config
from kubernetes.stream import stream
from kubespawner import KubeSpawner
from tornado.web import HTTPError


NAMESPACE = "cinder"
STATE = Path("/srv/jupyterhub/state")
FLAG = os.environ["CINDER_WORKSPACE_FLAG"]
config.load_kube_config(config_file="/etc/cinder/kubeconfig")
core = client.CoreV1Api()


def load_state() -> dict:
    path = STATE / "servers.json"
    return json.loads(path.read_text()) if path.is_file() else {}


def save_state(value: dict) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    temporary = STATE / ".servers.json"
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temporary.replace(STATE / "servers.json")


async def pre_spawn(spawner) -> None:
    seed = {path.name: path.read_text() for path in Path("/opt/cinder-seed").iterdir()}
    body = client.V1ConfigMap(metadata=client.V1ObjectMeta(name="cinder-workbench-seed"), data=seed)
    try: core.create_namespaced_config_map(NAMESPACE, body)
    except client.ApiException as error:
        if error.status != 409: raise
        core.replace_namespaced_config_map("cinder-workbench-seed", NAMESPACE, body)


async def post_spawn(spawner) -> None:
    pod = core.read_namespaced_pod(spawner.pod_name, NAMESPACE)
    pvc_name = spawner.pvc_name
    pvc = core.read_namespaced_persistent_volume_claim(pvc_name, NAMESPACE)
    image_id = next((status.image_id for status in (pod.status.container_statuses or []) if status.name == "notebook"), "")
    current = {"pod_uid": pod.metadata.uid, "pvc_uid": pvc.metadata.uid, "pvc_name": pvc_name,
               "image": spawner.image, "image_id": image_id, "observed_ns": time.time_ns()}
    state = load_state(); prior = state.get(spawner.user.name)
    if prior and prior["pod_uid"] != current["pod_uid"] and prior["pvc_uid"] == current["pvc_uid"]:
        command = ["sha256sum", "/home/jovyan/work/.cinder/probe"]
        result = stream(client.CoreV1Api().connect_get_namespaced_pod_exec,
            spawner.pod_name, NAMESPACE, container="notebook", command=command,
            stderr=True, stdin=False, stdout=True, tty=False,
        )
        digest = result.split()[0] if result else ""
        if len(digest) == 64:
            record_id = str(uuid.uuid4())
            record = {"schema": "cinder.jupyterhub-reattachment/v1", "record_id": record_id,
                      "operation": "kep-m06-l", "model_family": "none",
                      "attempt_id": record_id,
                      "actor": "cinder-field-operator", "old_pod_uid": prior["pod_uid"], "new_pod_uid": current["pod_uid"],
                      "pvc_uid": current["pvc_uid"], "pvc_name": pvc_name, "image": spawner.image,
                      "image_id": image_id, "probe_sha256": digest, "flag": FLAG}
            directory = STATE / "reattachments"; directory.mkdir(parents=True, exist_ok=True)
            (directory / f"{record_id}.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    state[spawner.user.name] = current; save_state(state)


class CinderKubeSpawner(KubeSpawner):
    async def start(self):
        result = await super().start()
        await post_spawn(self)
        return result


class ReattachmentHandler(BaseHandler):
    async def get(self, record_id: str) -> None:
        if self.current_user is None and self.request.headers.get("Authorization") != "Bearer Cinder-Checkpoint-Reader-W9s2Kd7m":
            raise HTTPError(403)
        try: uuid.UUID(record_id)
        except ValueError: raise HTTPError(404)
        path = STATE / "reattachments" / f"{record_id}.json"
        if not path.is_file(): raise HTTPError(404)
        self.set_header("Content-Type", "application/json"); self.finish(path.read_text())


class ReattachmentIndexHandler(BaseHandler):
    async def get(self) -> None:
        if self.current_user is None and self.request.headers.get("Authorization") != "Bearer Cinder-Checkpoint-Reader-W9s2Kd7m":
            raise HTTPError(403)
        records = [json.loads(path.read_text()) for path in sorted((STATE / "reattachments").glob("*.json"))]
        self.set_header("Content-Type", "application/json")
        self.finish(json.dumps(records, sort_keys=True))


c = get_config()  # noqa: F821
c.JupyterHub.bind_url = "http://0.0.0.0:8000"
c.JupyterHub.hub_bind_url = "http://0.0.0.0:8081"
c.JupyterHub.hub_connect_url = "http://192.168.78.1:18081"
c.JupyterHub.authenticator_class = "dummyauthenticator.DummyAuthenticator"
c.DummyAuthenticator.password = "Cinder-Field-Operator-Notebook-R5w8Nx2k"
c.Authenticator.allowed_users = {"cinder-field-operator"}
c.JupyterHub.spawner_class = CinderKubeSpawner
c.KubeSpawner.namespace = NAMESPACE
c.KubeSpawner.image = os.environ["CINDER_SINGLEUSER_IMAGE"]
c.KubeSpawner.service_account = "cinder-jupyter-user"
c.KubeSpawner.extra_labels = {"cinder.keplerops.lab/workspace": "participant"}
c.KubeSpawner.storage_pvc_ensure = True
c.KubeSpawner.pvc_name_template = "cinder-workspace-{username}"
c.KubeSpawner.storage_capacity = "10Gi"
c.KubeSpawner.storage_access_modes = ["ReadWriteOnce"]
c.KubeSpawner.volumes = [
    {"name": "workspace", "persistentVolumeClaim": {"claimName": "cinder-workspace-{username}"}},
    {"name": "seed", "configMap": {"name": "cinder-workbench-seed"}},
    {"name": "cinder-ca", "configMap": {"name": "cinder-workbench-ca"}},
]
c.KubeSpawner.volume_mounts = [{"name": "workspace", "mountPath": "/home/jovyan/work"},
                                  {"name": "seed", "mountPath": "/home/jovyan/work/START-HERE.md", "subPath": "START-HERE.md", "readOnly": True},
                                  {"name": "seed", "mountPath": "/home/jovyan/work/SERVERLESS-PUBLISH.md", "subPath": "SERVERLESS-PUBLISH.md", "readOnly": True},
                                  {"name": "seed", "mountPath": "/home/jovyan/work/integrations.json", "subPath": "integrations.json", "readOnly": True},
                                  {"name": "cinder-ca", "mountPath": "/etc/cinder/trust-bundle.crt", "subPath": "trust-bundle.crt", "readOnly": True}]
c.KubeSpawner.environment = {"SSL_CERT_FILE": "/etc/cinder/trust-bundle.crt", "CURL_CA_BUNDLE": "/etc/cinder/trust-bundle.crt"}
c.KubeSpawner.http_timeout = 180
c.KubeSpawner.start_timeout = 180
c.KubeSpawner.profile_list = [
    {"display_name": "Cinder CPU", "slug": "cpu", "default": True},
    {"display_name": "Cinder shared GPU", "slug": "gpu", "kubespawner_override": {"extra_resource_guarantees": {"nvidia.com/gpu": "1"}, "extra_resource_limits": {"nvidia.com/gpu": "1"}}},
]
c.KubeSpawner.pre_spawn_hook = pre_spawn
c.JupyterHub.extra_handlers = [
    (r"/hub/api/cinder/reattachments", ReattachmentIndexHandler),
    (r"/hub/api/cinder/reattachments/([0-9a-f-]+)", ReattachmentHandler),
]
c.JupyterHub.cookie_secret_file = "/srv/jupyterhub/state/cookie-secret"
c.JupyterHub.db_url = "sqlite:////srv/jupyterhub/state/jupyterhub.sqlite"
