from __future__ import annotations

import ast
import importlib.util
import json
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from .runtime_source import runtime_source


PACK_ROOT = Path(__file__).resolve().parents[2]
BUILD_ROOT = PACK_ROOT / "build"
GCP_ROOT = BUILD_ROOT / "gcp"
RUNTIME_ROOT = PACK_ROOT / "assets/services/keplerops-runtime"


def load_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        value = yaml.safe_load(handle)
    if not isinstance(value, dict):
        raise AssertionError(f"{path}: expected a mapping")
    return value


def load_validator():
    load_renderer()
    path = GCP_ROOT / "validate_build.py"
    spec = importlib.util.spec_from_file_location("keplerops_validate_build", path)
    if spec is None or spec.loader is None:
        raise AssertionError("unable to load build validator")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_renderer():
    path = GCP_ROOT / "render_sdl_realization.py"
    spec = importlib.util.spec_from_file_location("render_sdl_realization", path)
    if spec is None or spec.loader is None:
        raise AssertionError("unable to load SDL realization renderer")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_seed_module():
    path = GCP_ROOT / "seed_secrets.py"
    spec = importlib.util.spec_from_file_location("keplerops_seed_secrets", path)
    if spec is None or spec.loader is None:
        raise AssertionError("unable to load secret seeder")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_nested_bridge():
    path = GCP_ROOT / "nested-metadata.py"
    spec = importlib.util.spec_from_file_location("keplerops_nested_metadata", path)
    if spec is None or spec.loader is None:
        raise AssertionError("unable to load nested metadata bridge")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_invalid_lock(root: Path, mode: str) -> Path:
    realization = load_renderer().build_realization(root / "sdl/keplerops-ai.sdl.yaml")
    components = [row["component_id"] for row in realization["runtime_images"]]
    auxiliary = {
        row["image_id"]: {
            "uri": f"europe-west4-docker.pkg.dev/project/runtime/{row['image_id']}",
            "digest": "sha256:" + "b" * 64,
            "local_tag": row["local_tag"],
        }
        for row in realization["auxiliary_images"]
    }
    images = {
        component: {"uri": f"europe-west4-docker.pkg.dev/project/runtime/{component}", "digest": "sha256:" + "a" * 64}
        for component in components
    }
    payload = {
        "schema_version": 1,
        "project_id": "keplerops-test",
        "images": images,
        "auxiliary_images": auxiliary,
    }
    if mode == "fields":
        payload["unexpected"] = True
    elif mode == "incomplete":
        images.pop(components[0])
    elif mode == "binding":
        images[components[0]] = {"uri": "mutable", "digest": "bad"}
    elif mode == "revision":
        row = next(item for item in realization["runtime_images"] if "build_revision" in item)
        images[row["component_id"]] = {
            "uri": f"europe-west4-docker.pkg.dev/project/runtime/{row['component_id']}:stale-r1",
            "digest": "sha256:" + "c" * 64,
        }
    else:
        raise AssertionError("unknown lock mutation")
    path = root / f"invalid-image-lock-{mode}.json"
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    return path


class GcpBuildContractTests(unittest.TestCase):
    def test_cloud_build_excludes_generated_operator_state(self) -> None:
        ignore = (PACK_ROOT / ".gcloudignore").read_text(encoding="utf-8").splitlines()
        self.assertIn("build/", ignore)
        self.assertIn("**/__pycache__/", ignore)
        self.assertIn("**/*.pyc", ignore)
        for dockerfile in PACK_ROOT.rglob("Dockerfile*"):
            with self.subTest(dockerfile=dockerfile.relative_to(PACK_ROOT)):
                source = dockerfile.read_text(encoding="utf-8")
                self.assertNotRegex(source, r"(?m)^COPY(?:\s+--\S+)*\s+build(?:/|\s)")

    def test_production_validator_accepts_the_committed_pack(self) -> None:
        validator = load_validator()
        self.assertEqual(validator.validate(), [])

    def test_production_validator_rejects_contract_supply_and_source_mutations(self) -> None:
        validator = load_validator()

        def mutated(mutator) -> list[str]:
            with tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir) / "keplerops-ai"
                shutil.copytree(PACK_ROOT, root)
                validator.PACK_ROOT = root
                image_lock = mutator(root)
                return validator.validate(image_lock)

        def rewrite_yaml(root: Path, relative: str, update) -> None:
            path = root / relative
            value = yaml.safe_load(path.read_text(encoding="utf-8"))
            update(value)
            path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")

        cases = (
            (
                "SDL asset binding",
                lambda root: (rewrite_yaml(root, "sdl/modules/environment.sdl.yaml", lambda value: value["nodes"]["lab-portal"].update(features=[])), None)[1],
                "research telemetry sources reference missing assets",
            ),
            (
                "mutable image",
                lambda root: (rewrite_yaml(root, "sdl/modules/environment.sdl.yaml", lambda value: value["features"]["kali-browser-terminal"]["source"]["build"].update(base_image_digest="bad")), None)[1],
                "immutable source required",
            ),
            (
                "mutable sidecar",
                lambda root: (rewrite_yaml(root, "sdl/modules/environment.sdl.yaml", lambda value: value["features"]["redmine-workhub-sidecar"]["source"].update(version="6.0.6")), None)[1],
                "immutable dependency required",
            ),
            (
                "missing Dockerfile",
                lambda root: (rewrite_yaml(root, "sdl/modules/environment.sdl.yaml", lambda value: value["features"]["kali-browser-terminal"]["source"]["build"].update(dockerfile_path="assets/services/missing.Dockerfile")), None)[1],
                "Dockerfile missing",
            ),
            (
                "model integrity",
                lambda root: (rewrite_yaml(root, "assets/model-artifacts/model.yaml", lambda value: (value["upstream"].update(revision="main"), value["files"][0].update(sha256="bad"))), None)[1],
                "immutable revision required",
            ),
            (
                "missing source",
                lambda root: ((root / "assets/briefing/mission.md").unlink(), None)[1],
                "source path missing",
            ),
            (
                "invalid lock",
                lambda root: _write_invalid_lock(root, "fields"),
                "image lock: invalid fields",
            ),
            (
                "incomplete lock",
                lambda root: _write_invalid_lock(root, "incomplete"),
                "image lock: incomplete component set",
            ),
            (
                "invalid lock binding",
                lambda root: _write_invalid_lock(root, "binding"),
                "invalid binding",
            ),
            (
                "stale image lock revision",
                lambda root: _write_invalid_lock(root, "revision"),
                "stale build revision",
            ),
        )
        for name, mutator, expected in cases:
            with self.subTest(name=name):
                self.assertTrue(any(expected in issue for issue in mutated(mutator)))

    def test_sdl_realization_covers_every_gcp_full_surface(self) -> None:
        realization = load_renderer().build_realization()

        self.assertEqual(realization["schema_version"], 3)
        self.assertEqual(realization["sdl_source"], "sdl/keplerops-ai.sdl.yaml")
        self.assertEqual(len(realization["workloads"]), 28)
        self.assertEqual(len(realization["physical_hosts"]), 7)
        self.assertEqual(len(realization["placements"]), 26)
        self.assertEqual(len(realization["logical_networks"]), 10)
        self.assertGreaterEqual(len(realization["declared_routes"]), 44)
        self.assertEqual(
            realization["declared_routes"]["inference-workhub-action"],
            {
                "source": "lab-apps",
                "destination": "enterprise-services",
                "ports": ["443"],
                "protocols": ["tcp"],
            },
        )
        self.assertEqual(
            realization["declared_routes"]["participant-artifact-transfer"],
            {
                "source": "participant-entry",
                "destination": "registry-artifacts",
                "ports": ["9000"],
                "protocols": ["tcp"],
            },
        )
        self.assertEqual(
            realization["declared_routes"]["participant-platform-camera-ice"],
            {
                "source": "participant-entry",
                "destination": "data-workflows",
                "ports": ["32768-60999"],
                "protocols": ["udp"],
            },
        )
        participant = realization["workloads"]["participant-workstation"]
        self.assertEqual(participant["tcp_ports"], ["443"])
        self.assertEqual(participant["udp_ports"], [])
        self.assertEqual(
            realization["workloads"]["platform-camera-01"]["udp_ports"],
            ["32768-60999"],
        )
        self.assertEqual(participant["disk_gib"], 30)
        self.assertEqual(
            realization["workloads"]["platform-camera-01"]["startup_dependencies"],
            ["platform-ml-01"],
        )
        self.assertEqual(
            {
                workload: realization["workloads"][workload]["startup_rank"]
                for workload in (
                    "platform-ml-01",
                    "platform-camera-01",
                    "range-ops-controller",
                    "inference-gateway",
                    "distillation-runner-01",
                )
            },
            {
                "platform-ml-01": 0,
                "platform-camera-01": 1,
                "range-ops-controller": 2,
                "inference-gateway": 3,
                "distillation-runner-01": 4,
            },
        )
        self.assertGreaterEqual(len(realization["service_bindings"]), 34)
        self.assertEqual(len(realization["account_bindings"]), 11)
        self.assertGreaterEqual(len(realization["content_bindings"]), 46)
        self.assertEqual(len(realization["credential_dependencies"]), 11)
        self.assertIn("participant-workstation", realization["evidence_producers"])
        self.assertIn(
            "producer-token-participant-workstation",
            realization["runtime_secret_ids"],
        )
        self.assertIn(
            "participant-workstation/producer-token-participant-workstation",
            realization["secret_access"],
        )
        self.assertIn(
            "telemetry-proof-01/producer-token-participant-workstation",
            realization["secret_access"],
        )
        self.assertIn(
            "inference-gateway/minio-root-user", realization["secret_access"]
        )
        self.assertIn(
            "inference-gateway/minio-root-password", realization["secret_access"]
        )
        self.assertNotIn("tls-model-host-01", realization["runtime_secret_ids"])
        self.assertNotIn(
            "producer-token-model-host-01", realization["runtime_secret_ids"]
        )
        self.assertFalse(
            any(row.startswith("model-host-01/") for row in realization["secret_access"])
        )
        self.assertIn(
            "inference-gateway/platform-agent-admin-token",
            realization["secret_access"],
        )
        self.assertIn(
            "inference-gateway/platform-agent-seed-token",
            realization["secret_access"],
        )
        self.assertIn(
            "distillation-runner-01/service-token", realization["secret_access"]
        )
        self.assertIn(
            "image-generation-01/postgres-password", realization["secret_access"]
        )
        self.assertIn(
            "image-generation-01/minio-root-password", realization["secret_access"]
        )
        self.assertIn(
            "repo-ticket-01/platform-context-token", realization["secret_access"]
        )
        self.assertIn(
            "ml-workstation-01/ad-ml-engineer-password",
            realization["secret_access"],
        )
        self.assertIn(
            "workforce-workstation-01/ad-qa-password",
            realization["secret_access"],
        )
        self.assertIn(
            "workforce-workstation-01/ad-release-manager-password",
            realization["secret_access"],
        )
        self.assertIn(
            "repo-ticket-01/keycloak-platform-context-secret",
            realization["secret_access"],
        )
        self.assertIn(
            "range-ops-controller/jupyter-token",
            realization["secret_access"],
        )
        self.assertEqual(
            realization["credential_dependencies"][
                "distillation-signed-manifest-access"
            ],
            {
                "source": "distillation-runner-01",
                "target": "inference-gateway",
                "capability": "signed-data-dependency-manifest",
                "credentials": ["service-token"],
            },
        )
        self.assertEqual(
            realization["credential_dependencies"]["inference-platform-agent-control"],
            {
                "source": "inference-gateway",
                "target": "platform-agent-01",
                "capability": "agent-control-orchestration",
                "credentials": [
                    "platform-agent-admin-token",
                    "platform-agent-seed-token",
                ],
            },
        )
        self.assertEqual(len(realization["behavior_specifications"]), 145)
        self.assertIn(
            "activity.green-company-live-activity",
            realization["behavior_specifications"],
        )
        self.assertEqual(
            len(realization["runtime_images"]), len(realization["workloads"])
        )
        self.assertEqual(
            realization["placements"]["telemetry-proof-01"]["host"],
            "range-control-carrier-01",
        )
        self.assertEqual(
            realization["placements"]["policy-lab-01"]["host"],
            "range-worker-carrier-01",
        )
        self.assertEqual(
            realization["physical_hosts"]["ad-dc-01"]["os"], "windows"
        )
        self.assertEqual(
            {
                host: realization["physical_hosts"][host]["disk_gib"]
                for host in (
                    "participant-workstation",
                    "range-control-carrier-01",
                    "range-linux-carrier-01",
                    "range-worker-carrier-01",
                )
            },
            {
                "participant-workstation": 30,
                "range-control-carrier-01": 35,
                "range-linux-carrier-01": 205,
                "range-worker-carrier-01": 55,
            },
        )
        self.assertEqual(
            set(realization["identity_topology"]["relationships"]),
            {
                "ad-domain-controller",
                "workforce-domain-join",
                "ml-domain-join",
                "workforce-directory-federation",
            },
        )
        self.assertEqual(
            set(realization["shared_services"]), {"shared-inference-service"}
        )
        self.assertEqual(
            {row["image_id"] for row in realization["auxiliary_images"]},
            {
                "keplerops-bounded-python-worker",
                "keplerops-bounded-worker-engine",
                "keplerops-edge-registry",
                "keplerops-k6-runner",
                "mail-protocol-readiness",
                "keplerops-platform-context",
                "keplerops-platform-deployment",
                "keplerops-platform-isolation-loader",
            },
        )
        self.assertRegex(realization["sdl_digest"], r"^sha256:[0-9a-f]{64}$")

        terraform = (GCP_ROOT / "main.tf").read_text(encoding="utf-8")
        self.assertIn("sdl_realization  = jsondecode(file(var.sdl_realization_file))", terraform)
        self.assertIn(
            "logical_networks = local.sdl_realization.logical_networks", terraform
        )
        self.assertIn("workloads        = local.sdl_realization.workloads", terraform)
        self.assertIn(
            "physical_hosts   = local.sdl_realization.physical_hosts", terraform
        )
        self.assertIn("placements       = local.sdl_realization.placements", terraform)
        self.assertIn("declared_routes  = local.sdl_realization.declared_routes", terraform)
        self.assertIn(
            "runtime_secret_ids = toset(local.sdl_realization.runtime_secret_ids)",
            terraform,
        )
        self.assertIn(
            "for binding in local.sdl_realization.secret_access", terraform
        )
        self.assertNotRegex(
            terraform,
            r"(?m)^\s*(logical_networks|workloads|physical_hosts|placements|declared_routes)\s*=\s*\{",
        )

    def test_runtime_images_are_complete_and_immutable(self) -> None:
        realization = load_renderer().build_realization()
        by_component = {
            row["component_id"]: row for row in realization["runtime_images"]
        }
        self.assertEqual(
            set(by_component),
            {row["component"] for row in realization["workloads"].values()},
        )

        digest_ref = re.compile(r"^[a-z0-9./_-]+(?::[a-zA-Z0-9._-]+)?@sha256:[0-9a-f]{64}$")
        for component_id, row in by_component.items():
            with self.subTest(component_id=component_id):
                self.assertRegex(row["source"], digest_ref)
                self.assertEqual(row["mirror"], f"keplerops/{component_id}")
                if "context" in row:
                    dockerfile = PACK_ROOT / row.get(
                        "dockerfile", str(Path(row["context"]) / "Dockerfile")
                    )
                    self.assertTrue(dockerfile.is_file())

        auxiliary = {
            row["image_id"]: row for row in realization["auxiliary_images"]
        }
        self.assertEqual(
            set(auxiliary),
            {
                "keplerops-bounded-python-worker",
                "keplerops-bounded-worker-engine",
                "keplerops-edge-registry",
                "keplerops-k6-runner",
                "mail-protocol-readiness",
                "keplerops-platform-context",
                "keplerops-platform-deployment",
                "keplerops-platform-isolation-loader",
            },
        )
        for row in auxiliary.values():
            self.assertRegex(row["source"], digest_ref)
        self.assertEqual(
            auxiliary["mail-protocol-readiness"]["dockerfile"],
            "assets/services/platform-communications/mail/Dockerfile.readiness",
        )
        self.assertEqual(
            auxiliary["keplerops-platform-context"]["dockerfile"],
            "assets/services/platform-context/Dockerfile",
        )

        model_dockerfile = (PACK_ROOT / "assets/model-artifacts/Dockerfile").read_text(encoding="utf-8")
        self.assertIn("RUN python3 -m pip", model_dockerfile)
        self.assertIn('ENTRYPOINT ["python3", "-m", "vllm.entrypoints.openai.api_server"]', model_dockerfile)
        self.assertNotIn("RUN python -m pip", model_dockerfile)

        controller_dockerfile = (PACK_ROOT / "assets/services/keplerops-runtime/Dockerfile").read_text(encoding="utf-8")
        self.assertIn("python3-pip", controller_dockerfile)
        self.assertIn("RUN python3 -m pip", controller_dockerfile)
        self.assertIn('ENTRYPOINT ["python3", "-m", "uvicorn"', controller_dockerfile)
        self.assertIn("workhub_credentials.py", controller_dockerfile)
        self.assertNotIn("workhub-credentials.yaml", controller_dockerfile)
        for component in (
            "minio-artifact-store", "minio-exfil-sink",
        ):
            self.assertEqual(by_component[component]["build_revision"], 2)
        self.assertEqual(by_component["keplerops-lab-portal"]["build_revision"], 41)
        self.assertEqual(by_component["terraform-gcp-range-controller"]["build_revision"], 40)
        self.assertEqual(by_component["keycloak-identity"]["build_revision"], 7)
        self.assertEqual(by_component["envoy-fastapi-inference-gateway"]["build_revision"], 90)
        self.assertEqual(by_component["postgresql-dataset-store"]["build_revision"], 15)
        self.assertEqual(by_component["mlflow-model-registry"]["build_revision"], 2)
        self.assertEqual(by_component["kali-browser-terminal"]["build_revision"], 7)
        self.assertEqual(by_component["gitea-redmine-workhub"]["build_revision"], 15)
        self.assertEqual(by_component["jupyterlab-notebook-runner"]["build_revision"], 2)
        self.assertEqual(by_component["opa-guardrail-policy"]["build_revision"], 44)
        self.assertEqual(by_component["opentelemetry-proof-store"]["build_revision"], 49)
        self.assertEqual(by_component["airflow-distillation-runner"]["build_revision"], 14)
        self.assertEqual(by_component["vllm-open-model-hosting"]["build_revision"], 3)
        self.assertEqual(by_component["openvino-image-generation"]["build_revision"], 4)
        mlflow_dockerfile = (
            PACK_ROOT / "assets/services/Dockerfile.mlflow"
        ).read_text(encoding="utf-8")
        self.assertIn("boto3==1.40.20", mlflow_dockerfile)
        self.assertIn("USER 1000:1000", mlflow_dockerfile)
        node_bootstrap = (GCP_ROOT / "workload-bootstrap.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("AWS_CA_BUNDLE=/run/tls/ca.crt", node_bootstrap)
        self.assertRegex(
            node_bootstrap,
            r"notebook-runner-01\|model-registry-01(?:\|[^)]*)?\) readonly RUNTIME_UID=1000",
        )
        airflow_dockerfile = (PACK_ROOT / "assets/workflows/Dockerfile").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "install -d -o 50000 -g 0 -m 0750 /opt/keplerops/output",
            airflow_dockerfile,
        )
        workflow = (PACK_ROOT / "assets/workflows/keplerops_distillation.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("term: int(index)", workflow)
        self.assertIn("ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)", workflow)
        self.assertIn("context.minimum_version = ssl.TLSVersion.TLSv1_2", workflow)
        runtime_app = runtime_source(RUNTIME_ROOT)
        self.assertIn('"preferred_username"', runtime_app)
        self.assertIn('"participant": claims["preferred_username"]', runtime_app)
        self.assertIn("POLICY_SYSTEMS[revision]", runtime_app)
        model_evasion = (
            PACK_ROOT / "assets/services/keplerops-runtime/model_evasion.py"
        ).read_text(encoding="utf-8")
        self.assertIn('{"decision":"deny"}', model_evasion)
        self.assertIn("@lru_cache(maxsize=1)\ndef _research_contract", runtime_app)
        self.assertIn("RESEARCH_HTTP_CLIENT = httpx.Client", runtime_app)
        self.assertNotIn("with httpx.Client(timeout=2.0, verify=context)", runtime_app)
        self.assertIn('client = _backend_http_client("model", timeout=30.0)', runtime_app)
        self.assertNotIn("async with httpx.AsyncClient", runtime_app)
        self.assertIn("NAMESPACE_PATTERN =", runtime_app)
        self.assertIn("context.minimum_version = ssl.TLSVersion.TLSv1_2", runtime_app)
        keycloak_entrypoint = (PACK_ROOT / "assets/services/keycloak-entrypoint.sh").read_text(encoding="utf-8")
        self.assertIn(">/opt/keycloak/data/import/keplerops-realm.json", keycloak_entrypoint)
        self.assertIn("__LDAP_BIND_CREDENTIAL__", keycloak_entrypoint)
        keycloak_readback = (PACK_ROOT / "assets/services/keycloak-company-state-readback.sh").read_text(encoding="utf-8")
        self.assertIn("keycloak-ldap-username-mapper.json", keycloak_readback)
        self.assertIn('"ldap.attribute": ["sAMAccountName"]', keycloak_readback)
        self.assertIn('"always.read.value.from.ldap": ["true"]', keycloak_readback)
        keycloak_realm = json.loads((PACK_ROOT / "assets/services/keycloak-realm.json").read_text(encoding="utf-8"))
        self.assertEqual(keycloak_realm["accessTokenLifespan"], 3600)
        for user in keycloak_realm["users"]:
            self.assertTrue(user["emailVerified"])
            self.assertTrue(user["firstName"])
            self.assertTrue(user["lastName"])
            self.assertEqual(user["requiredActions"], [])
        self.assertEqual(
            {user["username"] for user in keycloak_realm["users"]},
            {"operator", "service-account-platform-context-admin"},
        )
        context_admin = next(
            user
            for user in keycloak_realm["users"]
            if user["username"] == "service-account-platform-context-admin"
        )
        self.assertTrue(
            {"view-realm", "manage-realm"} <= set(
                context_admin["clientRoles"]["realm-management"]
            )
        )
        groups = {group["name"]: group for group in keycloak_realm["groups"]}
        self.assertIn("ai_service_recipient", groups["QA"]["realmRoles"])
        ldap = keycloak_realm["components"][
            "org.keycloak.storage.UserStorageProvider"
        ][0]
        self.assertEqual(ldap["providerId"], "ldap")
        self.assertEqual(
            ldap["config"]["connectionUrl"],
            ["ldaps://ad-dc-01.keplerops.test:636"],
        )
        self.assertEqual(ldap["config"]["bindCredential"], ["__LDAP_BIND_CREDENTIAL__"])
        ldap_mappers = ldap["subComponents"][
            "org.keycloak.storage.ldap.mappers.LDAPStorageMapper"
        ]
        username_mapper = next(
            mapper for mapper in ldap_mappers if mapper["name"] == "username"
        )
        self.assertEqual(username_mapper["providerId"], "user-attribute-ldap-mapper")
        self.assertEqual(
            username_mapper["config"],
            {
                "user.model.attribute": ["username"],
                "ldap.attribute": ["sAMAccountName"],
                "read.only": ["true"],
                "always.read.value.from.ldap": ["true"],
                "is.mandatory.in.ldap": ["true"],
            },
        )
        self.assertIn(
            {"name": "ai_service_recipient"}, keycloak_realm["roles"]["realm"]
        )
        jupyter_dockerfile = (PACK_ROOT / "assets/services/Dockerfile.jupyter").read_text(encoding="utf-8")
        self.assertIn("HOME=/home/jovyan/work", jupyter_dockerfile)
        self.assertIn("JUPYTER_RUNTIME_DIR=/home/jovyan/work/.jupyter/runtime", jupyter_dockerfile)
        kali_dockerfile = (PACK_ROOT / "assets/services/Dockerfile.kali").read_text(encoding="utf-8")
        self.assertIn("USER root", kali_dockerfile)
        self.assertIn("install -d -o 1000 -g 1000", kali_dockerfile)
        self.assertIn("COPY --chown=1000:1000 assets/briefing/mission.md", kali_dockerfile)
        workhub_dockerfile = (PACK_ROOT / "assets/services/Dockerfile.workhub").read_text(encoding="utf-8")
        self.assertIn("COPY --from=gitea /app/gitea/gitea /usr/local/bin/gitea", workhub_dockerfile)
        self.assertIn("/lib/ld-musl-x86_64.so.1", workhub_dockerfile)
        self.assertIn("/usr/src/redmine/config/database.yml", workhub_dockerfile)
        workhub_entrypoint = (PACK_ROOT / "assets/services/workhub-entrypoint.sh").read_text(encoding="utf-8")
        self.assertIn("GITEA_WORK_DIR=/data/gitea", workhub_entrypoint)
        self.assertIn("SCHEMA=/usr/src/redmine/sqlite/schema.rb", workhub_entrypoint)
        self.assertIn("generate-access-token", workhub_entrypoint)
        self.assertIn(
            'BOOTSTRAP_TOKEN_NAME="company-state-bootstrap-$(date +%s)-$$"',
            workhub_entrypoint,
        )
        self.assertIn('--token-name "$BOOTSTRAP_TOKEN_NAME"', workhub_entrypoint)
        self.assertNotIn("--token-name company-state-bootstrap --raw", workhub_entrypoint)

    def test_agent_control_browser_surface_uses_the_same_live_api(self) -> None:
        page = (PACK_ROOT / "assets/services/agent-control.html").read_text(
            encoding="utf-8"
        )
        runtime = runtime_source(RUNTIME_ROOT)

        self.assertIn('request("/v1/agent/attempt"', page)
        self.assertIn('request("/v1/agent/context"', page)
        self.assertIn("/v1/agent/receipts/", page)
        self.assertNotIn("innerHTML", page)
        self.assertNotIn("eval(", page)
        self.assertIn("Content-Security-Policy", runtime)
        self.assertIn("@router.post(AGENT_ATTEMPT_PATH", runtime)

    def test_model_evasion_browser_surface_uses_real_paired_probe_api(self) -> None:
        page = (PACK_ROOT / "assets/services/model-evasion.html").read_text(
            encoding="utf-8"
        )
        runtime = runtime_source(RUNTIME_ROOT)
        policy = (PACK_ROOT / "assets/policies/guardrails.rego").read_text(
            encoding="utf-8"
        )
        gateway = (PACK_ROOT / "assets/services/Dockerfile.gateway").read_text(
            encoding="utf-8"
        )

        self.assertIn('request("/v1/evasion/attempt"', page)
        self.assertIn('request("/v1/evasion/surrogate"', page)
        self.assertIn("/v1/evasion/receipts/", page)
        self.assertNotIn("innerHTML", page)
        self.assertNotIn("eval(", page)
        self.assertIn("@router.post(EVASION_ATTEMPT_PATH", runtime)
        self.assertIn("await _model_completion(POLICY_SYSTEMS[revision], candidate)", runtime)
        self.assertIn("prerequisite_evidence <= recorded", runtime)
        self.assertIn("challenge_contracts(Path(path).resolve().parents[1])", runtime)
        self.assertIn("from aces_contract import", runtime)
        self.assertNotIn('["portfolio"]', runtime)
        self.assertIn('input.action == "evasion_probe"', policy)
        self.assertIn(
            "COPY assets/services/model-evasion.html /opt/keplerops/ui/model-evasion.html",
            gateway,
        )

    def test_context_poisoning_browser_surface_uses_real_retrieval_api(self) -> None:
        page = (PACK_ROOT / "assets/services/context-poisoning.html").read_text(
            encoding="utf-8"
        )
        runtime = runtime_source(RUNTIME_ROOT)
        gateway = (PACK_ROOT / "assets/services/Dockerfile.gateway").read_text(
            encoding="utf-8"
        )

        for endpoint in (
            'request("/v1/context/documents"',
            'request("/v1/context/search"',
            'request("/v1/context/reindex"',
            'request("/v1/context/attempt"',
            "/v1/context/receipts/",
        ):
            self.assertIn(endpoint, page)
        self.assertNotIn("innerHTML", page)
        self.assertNotIn("eval(", page)
        self.assertIn('@router.get("/context-poisoning"', runtime)
        self.assertIn("context_poisoning_ui_path", runtime)
        self.assertIn(
            "COPY assets/services/context-poisoning.html "
            "/opt/keplerops/ui/context-poisoning.html",
            gateway,
        )

    def test_adversarial_runtime_module_is_present_in_every_app_image(self) -> None:
        source = (
            "COPY assets/services/keplerops-runtime/adversarial_input.py "
            "./adversarial_input.py"
        )
        for path in (
            "assets/services/keplerops-runtime/Dockerfile",
            "assets/services/Dockerfile.gateway",
            "assets/services/Dockerfile.policy",
            "assets/services/Dockerfile.proof",
        ):
            with self.subTest(path=path):
                dockerfile = (PACK_ROOT / path).read_text(encoding="utf-8")
                self.assertIn(source, dockerfile)

    def test_shared_application_images_copy_package_startup_imports(self) -> None:
        top_level_modules = {path.stem for path in RUNTIME_ROOT.glob("*.py")}
        required_modules: set[str] = set()
        for path in (RUNTIME_ROOT / "keplerops_runtime").rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in tree.body:
                if isinstance(node, ast.ImportFrom) and node.module:
                    base = node.module.split(".")[0]
                    if base in top_level_modules:
                        required_modules.add(base)
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        base = alias.name.split(".")[0]
                        if base in top_level_modules:
                            required_modules.add(base)
        required_modules -= {
            "agent_action_worker",
            "agent_actions",
            "agent_worker",
            "ai_capstone",
            "model_backdoor",
            "python_package_worker",
            "research_cli",
        }
        for dockerfile in (
            "assets/services/keplerops-runtime/Dockerfile",
            "assets/services/Dockerfile.gateway",
            "assets/services/Dockerfile.policy",
            "assets/services/Dockerfile.proof",
        ):
            source = (PACK_ROOT / dockerfile).read_text(encoding="utf-8")
            for module in sorted(required_modules):
                with self.subTest(dockerfile=dockerfile, module=module):
                    self.assertIn(
                        f"COPY assets/services/keplerops-runtime/{module}.py ./{module}.py",
                        source,
                    )

    def test_collector_uses_mtls_durable_pipelines_without_debug_export(self) -> None:
        collector = load_yaml(PACK_ROOT / "assets" / "services" / "otel-collector.yaml")
        http = collector["receivers"]["otlp"]["protocols"]["http"]
        self.assertEqual(http["endpoint"], "0.0.0.0:4318")
        self.assertEqual(http["tls"]["client_ca_file"], "/run/tls/ca.crt")
        self.assertEqual(http["tls"]["cert_file"], "/run/tls/tls.crt")
        self.assertEqual(http["tls"]["key_file"], "/run/tls/tls.key")
        self.assertNotIn("debug", collector["exporters"])
        for signal in ("traces", "logs", "metrics"):
            pipeline = collector["service"]["pipelines"][signal]
            self.assertEqual(pipeline["receivers"], ["otlp"])
            self.assertIn("memory_limiter", pipeline["processors"])
            self.assertIn("batch", pipeline["processors"])
            self.assertEqual(pipeline["exporters"], [f"file/{signal}"])
            exporter = collector["exporters"][f"file/{signal}"]
            self.assertTrue(exporter["path"].startswith("/var/lib/keplerops-research/otel/"))
            self.assertEqual(exporter["format"], "json")
            self.assertNotIn("create_directory", exporter)
            self.assertNotIn("directory_permissions", exporter)
            self.assertLessEqual(exporter["rotation"]["max_megabytes"], 32)

    def test_telemetry_ingest_is_mtls_internal_only_and_not_a_participant_route(self) -> None:
        realization = load_renderer().build_realization()
        self.assertEqual(
            realization["service_bindings"]["telemetry-otlp"],
            "telemetry-proof-01",
        )
        self.assertEqual(
            realization["service_bindings"]["research-event-ingest"],
            "telemetry-proof-01",
        )
        self.assertEqual(
            realization["service_bindings"]["network-flow-logs"],
            "range-ops-controller",
        )
        participant_routes = [
            route
            for route in realization["declared_routes"].values()
            if route["source"] == "participant-entry"
        ]
        self.assertTrue(any(
            route["destination"] == "data-workflows" and route["ports"] == ["8080"]
            for route in participant_routes
        ))
        for port in ("4318", "4319"):
            self.assertFalse(any(port in route["ports"] for route in participant_routes))

        terraform = (GCP_ROOT / "main.tf").read_text(encoding="utf-8")
        self.assertIn(
            "keplerops-declared-routes           = jsonencode(local.declared_routes)",
            terraform,
        )
        carrier = (GCP_ROOT / "carrier-bootstrap.sh").read_text(encoding="utf-8")
        self.assertIn("route_networks=$(jq -r --arg source", carrier)
        self.assertIn("ROUTE_NETWORKS_TEXT", carrier)

        template = (GCP_ROOT / "workload-bootstrap.sh").read_text(encoding="utf-8")
        resolver_block = template.split(
            "docker_run -d --name keplerops-package-resolver", 1
        )[1].split(
            "docker network connect --alias package-resolver", 1
        )[0]
        self.assertIn("for route_network in $ROUTE_NETWORKS_TEXT", resolver_block)
        self.assertIn(
            'docker network connect "$route_network" keplerops-package-resolver',
            resolver_block,
        )
        entrypoint = (PACK_ROOT / "assets/services/proof-entrypoint.sh").read_text(encoding="utf-8")
        app_source = runtime_source(RUNTIME_ROOT)
        self.assertIn('--out-file="/output/$temporary"', template)
        self.assertIn('--mount type=bind,src="$directory",dst=/output', template)
        self.assertIn('--user 0:0', template)
        self.assertNotIn('>"$destination"', template)
        self.assertIn("research_ingest_url: https://telemetry-proof-01.keplerops.lab:4319", template)
        self.assertIn("--port 4319", entrypoint)
        self.assertIn("--ssl-ca-certs /run/tls/ca.crt --ssl-cert-reqs 2", entrypoint)
        self.assertIn('server[1] == 4319', app_source)
        self.assertIn('request.url.path.startswith("/v1/research/")', app_source)

    def test_full_content_signals_are_typed_and_independently_disabled(self) -> None:
        variables = (GCP_ROOT / "variables.tf").read_text(encoding="utf-8")
        for signal in (
            "prompt",
            "completion",
            "tool_call",
            "tool_result",
            "terminal_command",
            "terminal_input",
            "terminal_output",
            "process_lifecycle",
            "browser_interaction",
            "notebook_content",
            "file_content",
            "workflow_state",
            "artifact_content",
            "http_body",
        ):
            self.assertRegex(variables, rf"{signal}\s*=\s*bool")
            self.assertRegex(variables, rf"{signal}\s*=\s*false")
        self.assertNotIn("capture_all", variables)

        terraform = (GCP_ROOT / "main.tf").read_text(encoding="utf-8")
        self.assertIn(
            "keplerops-research-capture-signals  = jsonencode(var.telemetry_capture_signals)",
            terraform,
        )
        template = (GCP_ROOT / "workload-bootstrap.sh").read_text(encoding="utf-8")
        self.assertIn("research_capture_signals: $RESEARCH_CAPTURE_SIGNALS", template)
        self.assertIn(
            "environment_image_lock_path: /etc/keplerops/environment-images.json",
            template,
        )
        self.assertIn(
            'install -m 0600 "$IMAGE_LOCK_FILE" /etc/keplerops/environment-images.json',
            template,
        )

        app_source = runtime_source(RUNTIME_ROOT)
        self.assertIn("class ResearchContentRequest(BaseModel):", app_source)
        self.assertIn('@router.post("/v1/research/content"', app_source)
        proof_dockerfile = (PACK_ROOT / "assets/services/Dockerfile.proof").read_text(
            encoding="utf-8"
        )
        for source in (
            "aces_contract.py",
            "sdl/",
            "assets/model-artifacts/model.yaml",
            "assets/model-artifacts/deployment-manifest.yaml",
            "assets/content/datasets/context.jsonl",
        ):
            self.assertIn(f"COPY {source}", proof_dockerfile)

    def test_teacher_model_is_capacity_appropriate_and_immutably_verified(self) -> None:
        manifest = yaml.safe_load(
            (PACK_ROOT / "assets/model-artifacts/model.yaml").read_text(encoding="utf-8")
        )
        self.assertEqual(
            manifest["upstream"]["repository"],
            "HuggingFaceTB/SmolLM2-1.7B-Instruct",
        )
        self.assertRegex(manifest["upstream"]["revision"], r"^[0-9a-f]{40}$")
        artifacts = {row["path"]: row for row in manifest["files"]}
        self.assertEqual(
            set(artifacts),
            {
                "config.json",
                "generation_config.json",
                "merges.txt",
                "model.safetensors",
                "special_tokens_map.json",
                "tokenizer.json",
                "tokenizer_config.json",
                "vocab.json",
            },
        )
        artifact = artifacts["model.safetensors"]
        self.assertEqual(artifact["path"], "model.safetensors")
        self.assertGreaterEqual(artifact["size"], 3_000_000_000)
        for row in artifacts.values():
            self.assertRegex(row["sha256"], r"^[0-9a-f]{64}$")
            self.assertGreater(row["size"], 0)

        registration = (
            PACK_ROOT / "assets/model-artifacts/register_model.py"
        ).read_text(encoding="utf-8")
        self.assertIn('candidate.get("path") == "model.safetensors"', registration)
        self.assertIn("len(matches) != 1", registration)
        self.assertNotIn('manifest["files"][0]', registration)

    def test_carrier_bootstrap_uses_the_complete_immutable_image_lock(
        self,
    ) -> None:
        terraform = (GCP_ROOT / "main.tf").read_text(encoding="utf-8")
        carrier = (GCP_ROOT / "carrier-bootstrap.sh").read_text(encoding="utf-8")
        self.assertRegex(
            terraform,
            r'keplerops-image-lock\s+= jsonencode\(local\.image_lock\)',
        )
        self.assertIn(
            'local.image_lock.images[workload.component].digest',
            terraform,
        )
        self.assertIn(
            '.auxiliary_images[] | .uri + "@" + .digest',
            carrier,
        )
        self.assertIn(
            '.images["terraform-gcp-range-controller"] | .uri + "@" + .digest',
            carrier,
        )

    def test_windows_bootstrap_uses_the_private_google_api_endpoint(self) -> None:
        template = (GCP_ROOT / "windows-bootstrap.ps1.tpl").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            '$PrivateGoogleApiEntry = "199.36.153.4 secretmanager.googleapis.com"',
            template,
        )
        self.assertIn("$Env:ADPS_LoadDefaultDrive = 0", template)
        self.assertIn("Select-String", template)
        self.assertIn('Set-GuestAttribute "ready" "bootstrapping"', template)
        self.assertLess(
            template.index("$PrivateGoogleApiEntry"),
            template.index("function Get-RangeSecretBytes"),
        )
        self.assertIn(
            "$computerSystem = Get-CimInstance Win32_ComputerSystem",
            template,
        )
        self.assertIn("if ($computerSystem.DomainRole -lt 4)", template)
        self.assertIn("foreach ($attempt in 1..120)", template)
        self.assertIn("$domain = Get-ADDomain -ErrorAction Stop", template)
        self.assertIn(
            'throw "Active Directory Web Services did not become ready"',
            template,
        )
        self.assertIn(
            '& nltest.exe "/dsgetdc:$DomainDns" "/force"',
            template,
        )
        self.assertIn(
            'throw "Active Directory domain locator did not become ready"',
            template,
        )
        self.assertLess(
            template.index('& nltest.exe "/dsgetdc:$DomainDns" "/force"'),
            template.index("Add-Computer"),
        )
        self.assertIn("-NoRebootOnCompletion", template)
        self.assertEqual(template.count("& shutdown.exe /r /t 5 /f"), 2)
        self.assertNotIn("-Restart", template)
        self.assertIn("function Add-DomainGroupMemberIfMissing", template)
        self.assertIn("Get-ADPrincipalGroupMembership -Identity $Member", template)
        self.assertIn("if ($membership.Count -eq 0)", template)
        self.assertNotIn(
            "Add-ADGroupMember -Identity $group -Members $Sam "
            "-ErrorAction SilentlyContinue",
            template,
        )
        self.assertIn(
            "$defaultPasswordPolicy = Get-ADDefaultDomainPasswordPolicy",
            template,
        )
        self.assertRegex(
            template,
            re.compile(
                r"(?s)try \{.*-ComplexityEnabled \$false"
                r".*Initialize-DomainContent.*finally \{"
                r".*-ComplexityEnabled \$defaultPasswordPolicy\.ComplexityEnabled"
            ),
        )
        self.assertIn("Add-DnsServerResourceRecordA", template)
        self.assertIn("-IPv4Address $ControllerIp", template)
        self.assertNotIn("Add-DnsServerResourceRecordCName", template)
        self.assertIn("$password = Get-RangeSecret $passwordSecret", template)
        self.assertIn("[KeplerOpsNativeProfile]::LogonUser(", template)
        self.assertIn("[KeplerOpsNativeProfile]::LoadUserProfile(", template)
        self.assertIn("$identity.Impersonate()", template)
        self.assertIn("StoreLocation]::CurrentUser", template)
        self.assertIn("[KeplerOpsNativeProfile]::UnloadUserProfile(", template)
        self.assertIn("[KeplerOpsNativeProfile]::CloseHandle(", template)
        self.assertNotIn("-LogonType S4U", template)
        self.assertNotIn("Register-ScheduledTask", template)
        self.assertNotIn("Start-Process", template)
        self.assertNotIn(
            "if (-not (Get-ADDomain -ErrorAction SilentlyContinue))",
            template,
        )

    def test_carrier_control_helpers_use_cos_writable_state(self) -> None:
        carrier = (GCP_ROOT / "carrier-bootstrap.sh").read_text(encoding="utf-8")
        workload = (GCP_ROOT / "workload-bootstrap.sh").read_text(encoding="utf-8")
        reset = (BUILD_ROOT / "reset.sh").read_text(encoding="utf-8")
        command = "/var/lib/keplerops-carrier/bin/keplerops-workload"
        self.assertIn('readonly CARRIER_BIN="$CARRIER_ROOT/bin"', carrier)
        self.assertIn('readonly WORKLOAD_COMMAND="$CARRIER_BIN/keplerops-workload"', carrier)
        self.assertIn('readonly WORKLOAD_BOOTSTRAP="$CARRIER_BIN/workload-bootstrap"', carrier)
        self.assertIn('bash "$WORKLOAD_COMMAND" bootstrap "$asset_id"', carrier)
        self.assertIn('mapfile -t workload_ids < <(', carrier)
        self.assertIn('for asset_id in "${workload_ids[@]}"; do', carrier)
        self.assertIn("sort_by(.value.startup_rank, .key)", carrier)
        self.assertIn(
            'if [[ "$action" == bootstrap || "$action" == reset || '
            '! -s "$environment_file" ]]; then',
            carrier,
        )
        self.assertNotIn(
            'done < <(jq -r \'keys[]\' "$CARRIER_ROOT/input/workload-plan.json")',
            carrier,
        )
        self.assertIn(
            "bash /var/lib/keplerops-carrier/bin/keplerops-workload-internal",
            carrier,
        )
        self.assertIn('if [[ "$action" == reset ]]; then', carrier)
        self.assertIn('rm -f "$CARRIER_ROOT/ready"', carrier)
        self.assertIn(
            'cat /proc/sys/kernel/random/boot_id >"$CARRIER_ROOT/ready"',
            carrier,
        )
        self.assertIn("wait_for_carrier_ready", reset)
        self.assertEqual(reset.count("wait_for_carrier_ready"), 3)
        self.assertIn("seq 1 720", reset)
        self.assertIn(
            "io.containerd.content.v1.content/ingest",
            workload,
        )
        self.assertIn(
            'find "$ingest_root" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +',
            workload,
        )
        self.assertIn("/proc/sys/kernel/random/boot_id", reset)
        self.assertIn("/var/lib/keplerops-carrier/ready 2>/dev/null", reset)
        self.assertIn("sudo bash -lc 'test", reset)
        self.assertLess(
            reset.index("wait_for_carrier_ready\n\nexport TELEMETRY_MARKER_STATUS"),
            reset.index("telemetry_marker reset.requested"),
        )
        self.assertLess(
            carrier.index('if [[ "$action" == reset ]]; then'),
            carrier.index('main_container="keplerops-${asset_id}-runtime"'),
        )
        self.assertIn(
            'bash "$workload_root/state/$script" "$@"',
            carrier,
        )
        self.assertIn("if [[ -L /var/lib/keplerops ]]; then", carrier)
        self.assertIn("if [[ -L /etc/keplerops ]]; then", carrier)
        self.assertNotIn(
            "[[ -L /var/lib/keplerops ]] && unlink /var/lib/keplerops",
            carrier,
        )
        self.assertNotIn(
            "[[ -L /etc/keplerops ]] && unlink /etc/keplerops",
            carrier,
        )
        self.assertIn("sed 's/^declare -r /declare /'", carrier)
        self.assertIn('if docker swarm join --token "$join_token"', carrier)
        self.assertIn('if [[ "$swarm_state" != inactive ]]', carrier)
        self.assertIn("docker swarm leave --force", carrier)
        self.assertIn(
            "docker info --format '{{.Swarm.LocalNodeState}}') == active",
            carrier,
        )
        self.assertNotIn("/opt/keplerops-workload-bootstrap", carrier)
        self.assertNotIn("/usr/local/sbin/keplerops-workload", carrier)
        self.assertIn(
            "199.36.153.4 secretmanager.googleapis.com %s", carrier
        )
        self.assertIn('readonly REGISTRY_HOST="$REGION-docker.pkg.dev"', carrier)
        self.assertIn(
            'iptables -C INPUT -s "$peer_ip" "${rule_args[@]}" -j ACCEPT',
            carrier,
        )
        self.assertIn(
            '"-p tcp -m multiport --dports 2377,7946"',
            carrier,
        )
        self.assertIn(
            '"-p udp -m multiport --dports 7946,4789"',
            carrier,
        )
        self.assertIn('"-p esp"', carrier)
        self.assertIn(
            'jq -r \'.[]\' "$CARRIER_ROOT/input/physical-host-ips.json"',
            carrier,
        )
        self.assertIn('select(.value | has("repo-ticket-01"))', carrier)
        self.assertIn('write_env WORKHUB_HOST_IP "$WORKHUB_HOST_IP"', carrier)
        self.assertIn("WORKHUB_HOST_ID WORKHUB_HOST_IP |", carrier)
        self.assertIn(
            "runtime_secret_access tls-range-ops-controller",
            carrier,
        )
        self.assertIn(
            "/usr/local/share/ca-certificates/keplerops-range.crt",
            carrier,
        )
        self.assertIn(
            "/etc/docker/certs.d/repo-ticket-01.keplerops.lab/ca.crt",
            carrier,
        )
        self.assertIn("elif [[ $trust_changed == true ]]; then", carrier)
        self.assertIn(
            "docker ps -aq --filter name=keplerops-",
            carrier,
        )
        self.assertIn(
            'docker rm -f "${existing_containers[@]}"',
            carrier,
        )
        self.assertRegex(
            carrier,
            r'(?s)if \[\[ "\$HOST_ID" == "\$MANAGER_ID" \]\]; then\n'
            r'  join_token=.*docker network inspect "\$network".*\nfi\n\n'
            r'.*?docker rm -f "\$\{existing_containers\[@\]\}".*?\n\njq -r',
        )
        self.assertIn('dynamic_range="${BASH_REMATCH[1]}.128/25"', carrier)
        self.assertIn('--ip-range "$dynamic_range"', carrier)
        self.assertIn("must use a /24 CIDR", carrier)
        self.assertIn(
            'nsenter --target "$pid" --net -- iptables -t nat -A PREROUTING',
            workload,
        )
        self.assertIn(
            '"$publish_spec" =~ ^([0-9]+):([0-9]+)$',
            workload,
        )
        self.assertIn(
            "cat /etc/ssl/certs/ca-certificates.crt "
            "\\\n    /var/lib/keplerops/tls/ca.crt "
            "\\\n    >/var/lib/keplerops/tls/combined-ca.crt",
            workload,
        )
        self.assertEqual(
            workload.count("SSL_CERT_FILE=/run/tls/combined-ca.crt"),
            2,
        )
        self.assertIn(
            "-e SSL_CERT_FILE=/run/tls/combined-ca.crt "
            '"$RUNTIME_IMAGE" # envoy-fastapi-inference-gateway',
            workload,
        )
        self.assertLess(
            workload.index("docker exec keplerops-runtime pg_isready --quiet"),
            workload.index(
                'test "$(head -n1 /var/lib/postgresql/data/postmaster.pid 2>/dev/null)" = 1'
            ),
        )
        self.assertLess(
            workload.index(
                'test "$(head -n1 /var/lib/postgresql/data/postmaster.pid 2>/dev/null)" = 1'
            ),
            workload.index("docker exec keplerops-runtime psql -U keplerops -d postgres -tAc 'SELECT 1'"),
        )
        self.assertLess(
            workload.index("docker exec keplerops-runtime psql -U keplerops -d postgres -tAc 'SELECT 1'"),
            workload.index("SELECT 1 FROM pg_database WHERE datname = 'keplerops'"),
        )
        self.assertGreaterEqual(carrier.count("--connect-timeout 5 --max-time 20"), 4)
        self.assertIn('jq \'.["live-restore"] = false\'', carrier)
        self.assertIn("mv \"$daemon_config\" /var/lib/docker/daemon.json", carrier)
        self.assertLess(
            carrier.index("systemctl restart docker"),
            carrier.index("docker swarm init"),
        )
        for relative in (
            "cleanup.sh",
            "export-telemetry.sh",
            "health-check.sh",
            "reset.sh",
            "telemetry-control.sh",
        ):
            source = (BUILD_ROOT / relative).read_text(encoding="utf-8")
            self.assertIn(command, source, relative)
            self.assertNotIn("/usr/local/sbin/keplerops-workload", source, relative)

    def test_workload_docker_wrapper_preserves_readonly_caller_names(self) -> None:
        bootstrap = (GCP_ROOT / "workload-bootstrap.sh").read_text(encoding="utf-8")
        self.assertIn("if [[ -z ${CONTAINER_PREFIX+x} ]]; then", bootstrap)
        self.assertIn("if [[ -z ${MAIN_CONTAINER+x} ]]; then", bootstrap)
        self.assertNotIn(
            'CONTAINER_PREFIX=${CONTAINER_PREFIX:-"keplerops-${ASSET_ID}"}',
            bootstrap,
        )
        self.assertNotIn(
            'MAIN_CONTAINER=${MAIN_CONTAINER:-"${CONTAINER_PREFIX}-runtime"}',
            bootstrap,
        )
        self.assertIn(
            "pid=$(command docker inspect --format '{{.State.Pid}}' \"$MAIN_CONTAINER\")",
            bootstrap,
        )
        self.assertIn('[[ "$pid" =~ ^[1-9][0-9]*$ ]] || return 1', bootstrap)
        self.assertIn('nsenter --target "$pid" --net -- "$@"', bootstrap)
        self.assertIn(
            "if workload_netns bash /var/lib/keplerops/health-local; then",
            bootstrap,
        )
        self.assertIn(
            "if workload_netns curl --fail --silent",
            bootstrap,
        )
        self.assertIn("local -a network_args=()", bootstrap)
        self.assertIn('local -a input=("$@") output=()', bootstrap)
        self.assertIn(
            'command docker run "${network_args[@]}" "${output[@]}"',
            bootstrap,
        )
        self.assertNotIn('output+=(--network "$LOGICAL_NETWORK"', bootstrap)
        self.assertNotIn('output+=(--network "container:$MAIN_CONTAINER")', bootstrap)
        self.assertIn(
            "--privileged --security-opt apparmor=unconfined --network bridge",
            bootstrap,
        )
        self.assertIn(
            "docker network disconnect bridge keplerops-bounded-worker-engine",
            bootstrap,
        )
        for endpoint in (
            "https://127.0.0.1:6901/",
            "https://127.0.0.1:8443/healthz",
            "https://127.0.0.1:8444/healthz",
            "https://127.0.0.1:8443/realms/keplerops/",
            "https://127.0.0.1:8443/git/",
        ):
            self.assertIn(endpoint, bootstrap)
        self.assertIn(
            "hostssl all all 10.71.0.0/16 scram-sha-256",
            bootstrap,
        )
        self.assertIn(
            "-c hba_file=/run/keplerops/pg_hba.conf",
            bootstrap,
        )
        self.assertIn(
            "SELECT 1 FROM pg_database WHERE datname = 'keplerops'",
            bootstrap,
        )
        self.assertLess(
            bootstrap.index("docker exec keplerops-runtime pg_isready --quiet"),
            bootstrap.index("docker exec keplerops-runtime psql -U keplerops -d postgres -tAc 'SELECT 1'"),
        )
        self.assertLess(
            bootstrap.index("docker exec keplerops-runtime psql -U keplerops -d postgres -tAc 'SELECT 1'"),
            bootstrap.index("SELECT 1 FROM pg_database WHERE datname = 'keplerops'"),
        )
        self.assertIn(
            "docker exec keplerops-runtime createdb -U keplerops keplerops",
            bootstrap,
        )
        self.assertIn(
            "docker exec keplerops-runtime /docker-entrypoint-initdb.d/10-keplerops.sh",
            bootstrap,
        )
        self.assertIn(
            "for seed in 20-keplerops-data.sql 30-keplerops-company-data.sql",
            bootstrap,
        )
        self.assertIn(
            "src=/var/lib/keplerops/tls/ca.crt,dst=/etc/keplerops/pki/ca.crt,readonly",
            bootstrap,
        )

    def test_platform_deployment_uses_only_range_owned_provider_resources(self) -> None:
        terraform = (GCP_ROOT / "main.tf").read_text(encoding="utf-8")
        for service in ("run.googleapis.com", "storage.googleapis.com"):
            self.assertIn(f'"{service}"', terraform)
        self.assertIn('resource "google_storage_bucket" "workspace"', terraform)
        self.assertIn(
            'name                        = "${var.project_id}-keplerops-workspaces-${local.suffix}"',
            terraform,
        )
        self.assertIn("uniform_bucket_level_access = true", terraform)
        self.assertIn('public_access_prevention    = "enforced"', terraform)
        self.assertIn("force_destroy               = true", terraform)
        self.assertIn("labels                      = local.labels", terraform)
        self.assertIn('type = "Delete"', terraform)
        self.assertIn(
            'resource "google_project_iam_member" "range_ops_run_developer"', terraform
        )
        self.assertIn('role     = "roles/run.developer"', terraform)
        self.assertIn(
            'resource "google_service_account_iam_member" "range_ops_self_user"',
            terraform,
        )
        self.assertIn('role               = "roles/iam.serviceAccountUser"', terraform)
        self.assertIn(
            'resource "google_storage_bucket_iam_member" "range_ops_workspace_admin"',
            terraform,
        )
        self.assertIn('role     = "roles/storage.objectAdmin"', terraform)
        self.assertIn(
            "google_service_account.range_host.email",
            terraform,
        )
        self.assertIn(
            "keplerops-workspace-bucket-name     = google_storage_bucket.workspace.name",
            terraform,
        )
        carrier = (GCP_ROOT / "carrier-bootstrap.sh").read_text(encoding="utf-8")
        self.assertIn(
            '.auxiliary_images["keplerops-platform-deployment"] | .uri + "@" + .digest',
            carrier,
        )
        self.assertNotIn(
            'variable "billing_account"',
            (GCP_ROOT / "variables.tf").read_text(encoding="utf-8"),
        )

    def test_airflow_workflow_emits_fail_open_generation_bound_research_events(self) -> None:
        workflow = (PACK_ROOT / "assets/workflows/keplerops_distillation.py").read_text(
            encoding="utf-8"
        )
        template = (GCP_ROOT / "workload-bootstrap.sh").read_text(encoding="utf-8")

        self.assertIn('get_current_context()', workflow)
        self.assertIn('"workflow.started"', workflow)
        self.assertIn('"workflow.completed"', workflow)
        self.assertIn('"module-07-training-poisoning"', workflow)
        self.assertIn('/run/keplerops/reset-generation', workflow)
        self.assertIn('except Exception:\n        return', workflow)
        self.assertIn('RESEARCH_EVENT_ATTEMPTS = 2', workflow)
        self.assertIn('RESEARCH_EVENT_TIMEOUT_SECONDS = 2.0', workflow)
        self.assertNotIn('prompt=', workflow)
        self.assertIn(
            'fetch_secret producer-token-distillation-runner-01',
            template,
        )
        self.assertIn(
            '-e KEPLEROPS_RESEARCH_INGEST_URL=https://telemetry-proof-01.keplerops.lab:4319',
            template,
        )

        exporter = (BUILD_ROOT / "export-telemetry.sh").read_text(encoding="utf-8")
        self.assertIn('IMAGE_LOCK="$ROOT/image-lock.json"', exporter)
        self.assertIn('cat \\"\\$temporary\\" >\\"\\$destination\\"', exporter)
        self.assertIn('chmod 0600 \\"\\$destination\\" \\"\\$input\\"', exporter)
        self.assertIn('docker restart $PROOF_CONTAINER', exporter)
        self.assertIn("keplerops-workload health telemetry-proof-01", exporter)
        self.assertIn('docker exec --user 0:0 $PROOF_CONTAINER rm -rf', exporter)
        self.assertNotIn('sudo rm -rf -- \'$REMOTE\'', exporter)
        self.assertIn('/config/environment-images.json', exporter)
        self.assertIn("python3 -m json.tool", exporter)

    def test_sdl_content_sources_are_committed_when_they_name_pack_paths(self) -> None:
        environment = load_yaml(PACK_ROOT / "sdl/modules/environment.sdl.yaml")
        for content_id, row in environment["content"].items():
            source = row.get("source", {}).get("name")
            if isinstance(source, str) and source.startswith("assets/"):
                with self.subTest(content_id=content_id):
                    self.assertTrue((PACK_ROOT / source).exists(), source)

    def test_terraform_enforces_isolated_participant_only_exposure(self) -> None:
        terraform = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted(GCP_ROOT.glob("*.tf"))
        )
        cell_terraform = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted((GCP_ROOT / "cell").glob("*.tf"))
        )
        self.assertIn('data "google_project" "target"', terraform)
        self.assertNotIn('resource "google_project"', terraform)
        for forbidden in ("billing_account", "parent_type", "parent_id", "project_prefix"):
            self.assertNotIn(forbidden, terraform)
        self.assertNotIn('resource "google_compute_network"', terraform)
        self.assertNotIn('resource "google_compute_subnetwork"', terraform)
        self.assertNotIn('resource "google_compute_firewall"', terraform)
        self.assertIn("range_subnet_key = element(", terraform)
        self.assertIn('"keplerops-range-${local.range_subnet_key}"', terraform)
        self.assertIn('resource "google_compute_network" "cell"', cell_terraform)
        self.assertIn('resource "google_compute_subnetwork" "range"', cell_terraform)
        self.assertIn("private_ip_google_access = true", cell_terraform)
        self.assertIn('resource "google_compute_firewall" "deny_egress"', cell_terraform)
        self.assertIn(
            'resource "google_cloud_run_v2_service" "shared_model"',
            cell_terraform,
        )
        self.assertIn(
            'ingress             = "INGRESS_TRAFFIC_INTERNAL_ONLY"',
            cell_terraform,
        )
        self.assertIn("gpu_zonal_redundancy_disabled    = true", cell_terraform)
        self.assertIn('scaling_mode          = "AUTOMATIC"', cell_terraform)
        self.assertIn('accelerator = "nvidia-l4"', cell_terraform)
        self.assertIn('"nvidia.com/gpu" = "1"', cell_terraform)
        self.assertIn("var.shared_model_max_instances", cell_terraform)
        self.assertIn(
            'resource "google_dns_managed_zone" "private_run"',
            cell_terraform,
        )
        self.assertIn(
            'resource "google_cloud_run_v2_service_iam_member" "model_invoker"',
            terraform,
        )
        self.assertIn(
            "google_service_account.range_host.email",
            terraform,
        )
        self.assertIn(
            'resource "google_compute_firewall" "participant_ingress"',
            cell_terraform,
        )
        self.assertIn("for_each      = var.range_subnets", cell_terraform)
        self.assertEqual(cell_terraform.count('allow { protocol = "esp" }'), 2)
        self.assertIn("var.participant_source_cidrs", cell_terraform)
        self.assertNotIn('network = "default"', terraform)
        self.assertIn('cidr != "0.0.0.0/0"', cell_terraform)
        self.assertIn("var.deploy_runtime ? file(var.image_lock_file) : jsonencode", terraform)
        self.assertNotIn("roles/editor", terraform)
        self.assertNotIn("roles/owner", terraform)
        self.assertNotRegex(terraform, r"output\s+\"[^\"]*(password|secret|token|key)")
        self.assertIn("subnetwork = var.range_subnet_self_link", terraform)
        self.assertEqual(
            terraform.count('resource "google_compute_instance"'),
            1,
        )
        self.assertIn(
            'resource "google_compute_instance" "range_host"',
            terraform,
        )
        self.assertIn("access_config {", terraform)
        routes = load_renderer().build_realization()["declared_routes"]
        for route in ("participant-identity", "lab-identity", "proof-identity"):
            self.assertIn(route, routes)

        variables = (GCP_ROOT / "variables.tf").read_text(encoding="utf-8")
        for name in (
            "project_id", "range_instance", "participant", "region", "zone",
            "participant_source_cidrs", "sdl_realization_file",
            "range_subnet_self_link", "range_subnet_cidr",
            "range_host_ip_offset", "runtime_repository_id", "windows_image",
            "shared_model_service_name", "shared_model_service_url",
        ):
            self.assertIn(f'variable "{name}"', variables)
        self.assertNotIn('variable "billing_account"', variables)

        publisher = (GCP_ROOT / "publish_images.py").read_text(encoding="utf-8")
        self.assertIn("allow_missing=True", publisher)
        self.assertIn("ThreadPoolExecutor", publisher)
        self.assertIn("MAX_PUBLISH_WORKERS = 4", publisher)
        self.assertIn('realization["runtime_images"]', publisher)
        self.assertIn('for row in realization["auxiliary_images"]', publisher)
        self.assertNotIn("runtime-images.yaml", publisher)
        self.assertIn('"timeout": "3600s"', publisher)
        self.assertIn('tag = f"{tag}-r{revision}"', publisher)

    def test_gcp_full_packs_the_range_into_one_nested_host(self) -> None:
        terraform = (GCP_ROOT / "main.tf").read_text(encoding="utf-8")
        variables = (GCP_ROOT / "variables.tf").read_text(encoding="utf-8")
        outer = (GCP_ROOT / "outer-bootstrap.sh").read_text(encoding="utf-8")
        nested = (GCP_ROOT / "nested-bootstrap.sh").read_text(encoding="utf-8")
        bridge = (GCP_ROOT / "nested-metadata.py").read_text(encoding="utf-8")
        image_builder = (
            GCP_ROOT / "build-nested-host-image.sh"
        ).read_text(encoding="utf-8")
        packer = (
            GCP_ROOT / "packer" / "nested-host.pkr.hcl"
        ).read_text(encoding="utf-8")

        self.assertEqual(
            terraform.count('resource "google_compute_instance"'),
            1,
        )
        self.assertIn(
            'resource "google_compute_instance" "range_host"',
            terraform,
        )
        self.assertIn(
            'resource "google_compute_disk" "windows_guest"',
            terraform,
        )
        self.assertIn(
            "for_each = var.deploy_runtime ? local.nested_windows_hosts : {}",
            terraform,
        )
        self.assertIn("enable_nested_virtualization = true", terraform)
        self.assertIn(
            '"range-linux-carrier-01" = local.packed_workload_plan',
            terraform,
        )
        self.assertIn('default     = "n2-custom-12-98304"', variables)
        self.assertIn("default     = 250", variables)
        self.assertIn("bash \"$BOOTSTRAP_ROOT/nested-bootstrap.sh\"", outer)
        self.assertIn("command -v hivexsh", outer)
        self.assertIn("libhivex-bin", outer)
        self.assertIn("command -v dnsmasq", outer)
        self.assertIn("dnsmasq-base", outer)
        self.assertIn(
            "kernel.apparmor_restrict_unprivileged_userns=0",
            outer,
        )
        self.assertIn("readonly NETWORK_NAME='keplerops-windows'", nested)
        self.assertIn("192.168.77.10", nested)
        self.assertIn("192.168.77.11", nested)
        self.assertIn("192.168.77.12", nested)
        self.assertIn("KeplerOpsCredential", nested)
        self.assertIn("hivexsh -w", nested)
        self.assertIn(
            "cd \\\\$current_control_set\\\\Services\\\\KeplerOpsCredential",
            nested,
        )
        self.assertIn("\ndel\ncommit\n", nested)
        self.assertIn('virsh shutdown "$host_id"', nested)
        self.assertIn('virsh destroy "$host_id"', nested)
        self.assertIn('virsh autostart "$host_id" --disable', nested)
        self.assertNotIn('$host_id.prepared', nested)
        self.assertIn('findmnt -no OPTIONS "$mountpoint"', nested)
        self.assertIn('mountpoint -q "$mountpoint" && umount "$mountpoint"', nested)
        self.assertIn('partition=$(readlink -f "${device}-part3")', nested)
        self.assertIn("range(0, len(encoded), 1024)", nested)
        self.assertIn('("domain", r"KEPLEROPS\\Administrator")', nested)
        self.assertIn("principal_failures.append", nested)
        self.assertIn("read_timeout_sec=70", nested)
        self.assertIn("operation_timeout_sec=60", nested)
        self.assertIn('replace(password, "[redacted]")', nested)
        self.assertIn('" ".join(stderr.split())[-500:]', nested)
        self.assertIn("timeout --signal=TERM --kill-after=10s 1800s", nested)
        self.assertIn('while kill -0 "$bootstrap_pid"', nested)
        self.assertIn('kill "$bootstrap_pid" 2>/dev/null || true', nested)
        self.assertIn(
            'local applied="$STATE_ROOT/windows/$host_id-bootstrap.applied.sha256"',
            nested,
        )
        self.assertIn('sha256sum --check --status "$applied"', nested)
        self.assertIn('rm -f "$ready"', nested)
        self.assertIn('sha256sum "$script" >"$applied"', nested)
        self.assertIn('ip -4 address show dev "$BRIDGE_NAME"', nested)
        self.assertIn(
            'sysctl -w "net.ipv4.conf.$BRIDGE_NAME.proxy_arp=1"',
            nested,
        )
        self.assertIn("ip neighbor replace proxy 169.254.169.254", nested)
        self.assertIn("-j DNAT --to-destination 192.168.77.1:8080", nested)
        self.assertNotIn(
            'virsh net-start "$NETWORK_NAME" >/dev/null 2>&1 || true',
            nested,
        )
        embedded_python = nested.split("<<'PY' &\n", 1)[1].split("\nPY\n", 1)[0]
        compile(embedded_python, "nested-bootstrap.py", "exec")
        self.assertIn('GUEST_NETWORK = ipaddress.ip_network("192.168.77.0/24")', bridge)
        self.assertIn('OUTER_ADDRESS = "192.168.77.1"', bridge)
        self.assertIn("address in GUEST_NETWORK or address.is_loopback", bridge)
        self.assertIn('request.path == "/computeMetadata/v1/"', bridge)
        self.assertIn('"/computeMetadata/v1/instance/hostname"', bridge)
        self.assertIn('"/computeMetadata/v1/project/hostname"', bridge)
        self.assertIn('"attributes": {}', bridge)
        self.assertIn('self.send_header("Metadata-Flavor", "Google")', bridge)
        self.assertIn("metadata-request-paths.log", bridge)
        self.assertIn("keplerops-nested-secret-access", terraform)
        self.assertIn("secret-access.json", nested)
        self.assertIn(
            "systemctl restart keplerops-nested-metadata.service",
            nested,
        )
        self.assertIn("self.secret_access.get(guest, set())", bridge)
        self.assertIn(
            'if self._request_guest() != parts[1]:',
            bridge,
        )
        self.assertIn("gcloud auth print-access-token", image_builder)
        self.assertNotIn("gcloud auth login", image_builder)
        self.assertIn("PKR_VAR_access_token", image_builder)
        self.assertIn("sensitive = true", packer)
        self.assertIn("dnsmasq-base", packer)
        self.assertIn("use_iap                 = var.use_iap", packer)

        workload_bootstrap = (
            GCP_ROOT / "workload-bootstrap.sh"
        ).read_text(encoding="utf-8")
        self.assertIn("WORKHUB_REGISTRY_PROXY_IP=127.77.0.11", workload_bootstrap)
        self.assertIn("keplerops-workhub-registry-proxy", workload_bootstrap)
        self.assertIn(
            '-p tcp --dport 443 -j REDIRECT --to-ports 9443',
            workload_bootstrap,
        )
        self.assertIn(
            'asyncio.open_connection(\n'
            '            "repo-ticket-01.keplerops.lab", 443',
            workload_bootstrap,
        )

    def test_nested_bridge_enforces_guest_secret_assignments(self) -> None:
        module = load_nested_bridge()
        with tempfile.TemporaryDirectory() as temporary:
            bridge = module.Bridge(
                "project-a",
                "abcdef",
                Path(temporary),
                {
                    "ad-dc-01": {"ad-domain-admin-password", "tls-ad-dc-01"},
                    "workforce-workstation-01": {"ad-qa-password"},
                    "ml-workstation-01": {"ad-ml-engineer-password"},
                },
            )
            bridge.cache["ad-domain-admin-password"] = b"domain-password"
            bridge.cache["ad-qa-password"] = b"qa-password"

            self.assertRegex(bridge.instance_id, r"^[0-9]+$")
            self.assertEqual(
                bridge.secret("outer-host", "ad-domain-admin-password"),
                b"domain-password",
            )
            self.assertEqual(
                bridge.secret("workforce-workstation-01", "ad-qa-password"),
                b"qa-password",
            )
            with self.assertRaisesRegex(ValueError, "not assigned"):
                bridge.secret("workforce-workstation-01", "tls-ad-dc-01")
            with self.assertRaisesRegex(ValueError, "not assigned"):
                bridge.secret("outer-host", "ad-qa-password")

    def test_participant_endpoint_has_a_stable_certificate_bound_address(self) -> None:
        terraform = (GCP_ROOT / "main.tf").read_text(encoding="utf-8")
        outputs = (GCP_ROOT / "outputs.tf").read_text(encoding="utf-8")
        launch = (BUILD_ROOT / "launch.sh").read_text(encoding="utf-8")
        seeder = (GCP_ROOT / "seed_secrets.py").read_text(encoding="utf-8")
        bootstrap = (GCP_ROOT / "workload-bootstrap.sh").read_text(encoding="utf-8")
        kali_dockerfile = (PACK_ROOT / "assets" / "services" / "Dockerfile.kali").read_text(encoding="utf-8")
        kasm_config = PACK_ROOT / "assets" / "services" / "kasmvnc.yaml"

        self.assertIn('resource "google_compute_address" "participant"', terraform)
        self.assertIn(
            'startup-script                      = file("${path.module}/outer-bootstrap.sh")',
            terraform,
        )
        self.assertIn(
            'keplerops-workload-bootstrap        = file("${path.module}/workload-bootstrap.sh")',
            terraform,
        )
        self.assertIn("nat_ip       = google_compute_address.participant.address", terraform)
        self.assertIn('output "participant_address"', outputs)
        self.assertIn("google_compute_address.participant.address", outputs)
        self.assertIn("participant_address", launch)
        self.assertIn("wait_for_carrier_ready", launch)
        self.assertIn(
            'sudo bash -lc \'test \\"\\$(cat /proc/sys/kernel/random/boot_id)\\" = '
            '\\"\\$(cat /var/lib/keplerops-carrier/ready 2>/dev/null)\\"\'',
            launch,
        )
        self.assertLess(
            launch.index("wait_for_carrier_ready\nrefresh_access_token"),
            launch.index('"$BUILD_ROOT/health-check.sh"'),
        )
        self.assertIn('output "range_zone"', outputs)
        for script in ("health-check.sh", "reset.sh"):
            source = (BUILD_ROOT / script).read_text(encoding="utf-8")
            self.assertIn('--zone "$ZONE"', source)
            self.assertIn("</dev/null", source)
        health_script = (BUILD_ROOT / "health-check.sh").read_text(encoding="utf-8")
        self.assertIn("LAUNCH_CARRIER_ATTEMPTS", launch)
        self.assertIn("/var/lib/keplerops-carrier/ready", launch)
        self.assertIn("sudo bash -lc", launch)
        self.assertLess(
            launch.index("LAUNCH_CARRIER_ATTEMPTS"),
            launch.index('"$BUILD_ROOT/health-check.sh"'),
        )
        self.assertIn("tf_output_or_var project_id project_id", health_script)
        self.assertIn("tf_output_or_var range_zone zone", health_script)
        self.assertIn('--realization "$REALIZATION"', health_script)
        self.assertIn("refresh_access_token()", health_script)
        self.assertIn("resolve_gcloud_account()", health_script)
        self.assertIn('"${GCLOUD_ACCOUNT_ARGS[@]}"', health_script)
        retry = r"for attempt in \$(seq 1 120)"
        marker = "/var/lib/keplerops-carrier/workloads/$ASSET/state/reset-generation"
        self.assertIn(retry, health_script)
        self.assertIn(marker, health_script)
        self.assertLess(health_script.index(retry), health_script.index(marker))
        self.assertIn(r'= \"$GENERATION\"', health_script)
        self.assertIn('"--participant-ip"', seeder)

        self.assertIn('"--realization"', seeder)
        self.assertIn('load_inventory(args.realization)', seeder)
        self.assertIn("certificate_sans(asset, args.participant_ip)", seeder)
        self.assertIn('tls_schema = "rsa-2048-v4-mtls"', seeder)
        self.assertIn('"rsa_keygen_bits:2048"', seeder)
        self.assertIn('"-algorithm",\n                "ED25519"', seeder)
        self.assertIn("force=tls_rotated", seeder)
        self.assertIn("TLS_PROFILE='rsa-2048-v4-mtls'", bootstrap)
        self.assertIn('"keyUsage=critical,keyCertSign,cRLSign"', seeder)
        self.assertIn('"extendedKeyUsage=serverAuth,clientAuth\\n"', seeder)
        self.assertTrue(kasm_config.is_file())
        self.assertIn("pem_certificate: /run/tls/tls.crt", kasm_config.read_text(encoding="utf-8"))
        self.assertIn("/home/kasm-user/.vnc/kasmvnc.yaml", kali_dockerfile)
        self.assertIn("src=/var/lib/keplerops/tls,dst=/run/tls,readonly", bootstrap)

    def test_template_starts_identity_network_before_foundation_binds(self) -> None:
        helper = (
            PACK_ROOT
            / "docs/campaign-v2/template/scripts/ensure-identity-network.sh"
        ).read_text(encoding="utf-8")
        foundation = (
            PACK_ROOT
            / "docs/campaign-v2/template/scripts/start-foundation.sh"
        ).read_text(encoding="utf-8")
        guests = (
            PACK_ROOT
            / "docs/campaign-v2/template/scripts/provision-guests.sh"
        ).read_text(encoding="utf-8")

        self.assertIn("readonly BRIDGE=${KEPLEROPS_IDENTITY_BRIDGE:-virbr-v2}", helper)
        self.assertIn(
            "readonly GATEWAY=${KEPLEROPS_IDENTITY_GATEWAY:-192.168.78.1}",
            helper,
        )
        self.assertIn("<bridge name='$BRIDGE'", helper)
        self.assertIn("<ip address='$GATEWAY' netmask='$NETMASK'>", helper)
        self.assertIn('virsh net-start "$NETWORK"', helper)
        self.assertIn('"$ROOT/scripts/ensure-identity-network.sh"', foundation)
        self.assertLess(
            foundation.index("ensure-identity-network.sh"),
            foundation.index('if [[ ${KEPLEROPS_SKIP_PULL:-0} != 1 ]]'),
        )
        self.assertIn('"$ROOT/scripts/ensure-identity-network.sh"', guests)

    def test_template_fresh_build_hotfixes_are_source_pinned(self) -> None:
        bootstrap = (
            PACK_ROOT / "docs/campaign-v2/template/scripts/bootstrap-host.sh"
        ).read_text(encoding="utf-8")
        lock = (
            PACK_ROOT / "docs/campaign-v2/template/component-lock.env"
        ).read_text(encoding="utf-8")
        enterprise = (
            PACK_ROOT / "docs/campaign-v2/template/scripts/start-enterprise.sh"
        ).read_text(encoding="utf-8")
        start_all = (
            PACK_ROOT / "docs/campaign-v2/template/scripts/start-all.sh"
        ).read_text(encoding="utf-8")
        guests = (
            PACK_ROOT / "docs/campaign-v2/template/scripts/check-guests.sh"
        ).read_text(encoding="utf-8")
        compose_enterprise = (
            PACK_ROOT / "docs/campaign-v2/template/compose.enterprise.yaml"
        ).read_text(encoding="utf-8")
        nextcloud = (
            PACK_ROOT / "docs/campaign-v2/template/seeding/apps/nextcloud.sh"
        ).read_text(encoding="utf-8")
        foundation = (
            PACK_ROOT / "docs/campaign-v2/template/scripts/start-foundation.sh"
        ).read_text(encoding="utf-8")
        workstation = (
            PACK_ROOT / "docs/campaign-v2/template/scripts/prepare-workstation.sh"
        ).read_text(encoding="utf-8")

        self.assertIn("grep '^keplerops-'", bootstrap)
        self.assertNotIn("grep -v '^keplerops-participant-workstation-runtime$'", bootstrap)
        self.assertIn('docker rm "${legacy_containers[@]}"', bootstrap)
        self.assertIn(
            "UBUNTU_CLOUD_IMAGE_URL=https://cloud-images.ubuntu.com/noble/20260801/"
            "noble-server-cloudimg-amd64.img",
            lock,
        )
        self.assertIn(
            "UBUNTU_CLOUD_IMAGE_SHA256=0533b0655c32e68b31d792ecd6ccfca95abdbc536c4446874fe0513bd4140ffe",
            lock,
        )
        self.assertIn("pull --ignore-buildable", enterprise)
        self.assertIn("build odoo business-adapter preview", enterprise)
        self.assertLess(
            enterprise.index("build odoo business-adapter preview"),
            enterprise.index("up -d"),
        )
        self.assertIn(
            'KEPLEROPS_ALLOW_PREVIEW_PENDING=1 "$ROOT/scripts/health-check.sh" enterprise',
            enterprise,
        )
        self.assertLess(
            enterprise.index('"$ROOT/seeding/seed.sh"'),
            enterprise.index('KEPLEROPS_ALLOW_PREVIEW_PENDING=1'),
        )
        self.assertIn(
            'KEPLEROPS_ALLOW_REVIEW_WORKERS_PENDING=1 "$ROOT/scripts/check-guests.sh"',
            start_all,
        )
        self.assertIn("readonly ALLOW_REVIEW_WORKERS_PENDING=", guests)
        self.assertIn("review worker verification substrate is unavailable", guests)
        health = (
            PACK_ROOT / "docs/campaign-v2/template/scripts/health-check.sh"
        ).read_text(encoding="utf-8")
        self.assertIn("readonly ALLOW_PREVIEW_PENDING=", health)
        self.assertIn("$container == kep-v2-preview", health)
        self.assertIn("'preview|preview.keplerops.lab|/'", health)
        network_install = (
            PACK_ROOT / "docs/campaign-v2/template/network/install.sh"
        ).read_text(encoding="utf-8")
        self.assertIn('systemctl restart "$POLICY_UNIT"', network_install)
        network_flows = (
            PACK_ROOT / "docs/campaign-v2/template/network/compose-flows.tsv"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "cidr:192.168.78.30/32\tkep-v2-step-ca\ttcp\t9000\tplatform signing CA enrollment",
            network_flows,
        )
        self.assertIn('"id.keplerops.lab:10.61.40.2"', compose_enterprise)
        self.assertIn('NEXTCLOUD_UPDATE: "1"', compose_enterprise)
        self.assertIn("ipv4_address: 10.61.10.48", compose_enterprise)
        self.assertIn("NEXTCLOUD_USER_OIDC_URL=", nextcloud)
        self.assertIn(
            "NEXTCLOUD_USER_OIDC_SHA256=49ced1fe192302f4540b869438b6ccb9ca0d69b717b76ed7075a70aa5cf666fd",
            nextcloud,
        )
        self.assertIn("install_user_oidc_archive", nextcloud)
        self.assertIn("! check_port 192.168.78.1 13081", guests)
        self.assertLess(
            guests.index("ALLOW_REVIEW_WORKERS_PENDING == 1"),
            guests.index("guest identity substrate healthy"),
        )
        self.assertLess(
            guests.index("! check_port 192.168.78.1 13081"),
            guests.index("review worker verification substrate is unavailable"),
        )
        self.assertIn(
            '[[ -e "$ROOT/state/caddy-root.crt" && ! -f "$ROOT/state/caddy-root.crt" ]]',
            foundation,
        )
        self.assertIn('rm -rf -- "$ROOT/state/caddy-root.crt"', foundation)
        self.assertIn('"${COMPOSE[@]}" up -d step-ca caddy', foundation)
        self.assertLess(
            foundation.index('rm -rf -- "$ROOT/state/caddy-root.crt"'),
            foundation.index('install -m 0644 "$caddy_root" "$ROOT/state/caddy-root.crt"'),
        )
        self.assertLess(
            foundation.index('"${COMPOSE[@]}" up -d step-ca caddy'),
            foundation.index('install -m 0644 "$caddy_root" "$ROOT/state/caddy-root.crt"'),
        )
        self.assertLess(
            foundation.index('install -m 0644 "$caddy_root" "$ROOT/state/caddy-root.crt"'),
            foundation.rindex('"${COMPOSE[@]}" up -d'),
        )
        self.assertIn(
            '[[ -e "$STATE/caddy-root.crt" && ! -f "$STATE/caddy-root.crt" ]]',
            workstation,
        )
        self.assertIn('rm -rf -- "$STATE/caddy-root.crt"', workstation)

    def test_shared_model_pool_is_cell_owned_and_workload_authenticated(self) -> None:
        range_launch = (BUILD_ROOT / "launch.sh").read_text(encoding="utf-8")
        cell_launch = (GCP_ROOT / "cell" / "launch.sh").read_text(encoding="utf-8")
        bootstrap = (GCP_ROOT / "workload-bootstrap.sh").read_text(encoding="utf-8")
        clients = (
            PACK_ROOT
            / "assets/services/keplerops-runtime/keplerops_runtime/foundation/clients.py"
        ).read_text(encoding="utf-8")
        config = (
            PACK_ROOT
            / "assets/services/keplerops-runtime/keplerops_runtime/foundation/config.py"
        ).read_text(encoding="utf-8")

        self.assertIn("--image-lock PATH", range_launch)
        self.assertIn('install -m 0600 "$SOURCE_IMAGE_LOCK" "$IMAGE_LOCK"', range_launch)
        self.assertNotIn("publish_images.py", range_launch)
        self.assertIn("publish_images.py", cell_launch)
        self.assertIn(
            '["images"]["vllm-open-model-hosting"]',
            cell_launch,
        )
        self.assertIn('VAR_FILE=$(realpath -- "$VAR_FILE")', cell_launch)
        self.assertIn('STATE_DIR=$(realpath -- "$STATE_DIR")', cell_launch)
        self.assertIn("-detailed-exitcode", cell_launch)
        self.assertIn("FOUNDATION_PLAN_STATUS=$?", cell_launch)
        self.assertIn('case "$FOUNDATION_PLAN_STATUS" in', cell_launch)
        self.assertIn("FOUNDATION_MODEL_ARGS=()", cell_launch)
        self.assertEqual(
            cell_launch.count('"${FOUNDATION_MODEL_ARGS[@]}"'),
            2,
        )
        self.assertIn("existing shared model requires its immutable image lock", cell_launch)
        self.assertNotIn("[[ ! -s $STATE ]]", cell_launch)
        self.assertNotIn("shared_model_image=null", cell_launch)
        self.assertIn('-var="shared_model_image=$MODEL_IMAGE"', cell_launch)
        self.assertIn("model_url: $SHARED_MODEL_URL", bootstrap)
        self.assertIn("model_identity_audience: $SHARED_MODEL_URL", bootstrap)
        self.assertIn('"model_identity_audience"', config)
        self.assertIn("instance/service-accounts/default/identity", clients)
        self.assertIn('"Metadata-Flavor": "Google"', clients)
        self.assertIn("MODEL_IDENTITY_CACHE_SECONDS = 3000", clients)
        self.assertIn('token.count(".") != 2', clients)
        self.assertNotIn("verify_signature", clients)
        self.assertIn('headers=await _model_identity_headers()', clients)

    def test_external_address_is_bound_only_into_the_participant_certificate(self) -> None:
        seeder = load_seed_module()
        participant = seeder.certificate_sans("participant-workstation", "203.0.113.42")
        internal = seeder.certificate_sans("lab-portal", "203.0.113.42")

        self.assertEqual(participant, (
            "DNS:participant-workstation.keplerops.lab",
            "IP:127.0.0.1",
            "IP:203.0.113.42",
        ))
        self.assertEqual(internal, (
            "DNS:lab-portal.keplerops.lab",
            "IP:127.0.0.1",
        ))

    def test_secret_and_tls_inventory_comes_from_the_sdl_realization(self) -> None:
        seeder = load_seed_module()
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "realization.json"
            path.write_text(
                json.dumps({
                    "workloads": {
                        "node-b": {},
                        "node-a": {},
                        "shared-model-host": {},
                    },
                    "evidence_producers": ["node-b"],
                    "runtime_secret_ids": [
                        "service-token",
                        "tls-ad-dc-01",
                        "tls-node-a",
                        "tls-node-b",
                    ],
                }),
                encoding="utf-8",
            )
            assets, producers = seeder.load_inventory(path)
        self.assertEqual(assets, ("ad-dc-01", "node-a", "node-b"))
        self.assertEqual(producers, ("node-b",))

    def test_lifecycle_entrypoints_and_gitignored_operator_state_exist(self) -> None:
        for relative in (
            "launch.sh",
            "health-check.sh",
            "reset.sh",
            "rebuild.sh",
            "cleanup.sh",
            "gcp/validate_build.py",
            "gcp/lifecycle.py",
        ):
            path = BUILD_ROOT / relative
            self.assertTrue(path.is_file(), relative)
            if relative.endswith(".sh"):
                self.assertTrue(path.stat().st_mode & stat.S_IXUSR, relative)

        launch = (BUILD_ROOT / "launch.sh").read_text(encoding="utf-8")
        self.assertIn("refresh_access_token()", launch)
        self.assertIn(
            "if [[ -z ${GOOGLE_OAUTH_ACCESS_TOKEN:-} || -z ${CLOUDSDK_AUTH_ACCESS_TOKEN:-} ]]; then",
            launch,
        )
        self.assertIn(
            "env -u GOOGLE_OAUTH_ACCESS_TOKEN -u CLOUDSDK_AUTH_ACCESS_TOKEN",
            launch,
        )
        self.assertIn("gcloud auth print-access-token", launch)
        self.assertIn("gcloud auth application-default print-access-token", launch)
        self.assertLess(
            launch.index("gcloud auth application-default print-access-token"),
            launch.index("gcloud auth print-access-token"),
        )
        self.assertIn("resolve_gcloud_account()", launch)
        self.assertIn('"${GCLOUD_ACCOUNT_ARGS[@]}"', launch)
        self.assertIn("export CLOUDSDK_AUTH_ACCESS_TOKEN=$GOOGLE_OAUTH_ACCESS_TOKEN", launch)
        cleanup = (BUILD_ROOT / "cleanup.sh").read_text(encoding="utf-8")
        self.assertIn(
            "if [[ -z ${GOOGLE_OAUTH_ACCESS_TOKEN:-} ]]; then",
            cleanup,
        )
        self.assertIn(
            "GOOGLE_OAUTH_ACCESS_TOKEN=$(gcloud auth print-access-token)",
            cleanup,
        )
        self.assertIn(
            "export CLOUDSDK_AUTH_ACCESS_TOKEN=$GOOGLE_OAUTH_ACCESS_TOKEN",
            cleanup,
        )
        reset = (BUILD_ROOT / "reset.sh").read_text(encoding="utf-8")
        self.assertIn("refresh_access_token()", reset)
        self.assertIn(
            "env -u GOOGLE_OAUTH_ACCESS_TOKEN -u CLOUDSDK_AUTH_ACCESS_TOKEN",
            reset,
        )
        self.assertIn("gcloud auth print-access-token", reset)
        self.assertIn("gcloud auth application-default print-access-token", reset)
        self.assertLess(
            reset.index("gcloud auth application-default print-access-token"),
            reset.index("gcloud auth print-access-token"),
        )
        self.assertIn("resolve_gcloud_account()", reset)
        self.assertIn('"${GCLOUD_ACCOUNT_ARGS[@]}"', reset)
        self.assertLess(
            reset.index("ssh_instance_command()"),
            reset.index('gcloud compute ssh "$instance"'),
        )
        self.assertLess(
            reset.index("refresh_access_token", reset.index("ssh_instance_command()")),
            reset.index('gcloud compute ssh "$instance"'),
        )

        ignore = (BUILD_ROOT / ".gitignore").read_text(encoding="utf-8")
        for pattern in (".operator/", "*.tfstate", "*.tfstate.*", "teardown-report.json"):
            self.assertIn(pattern, ignore)

        cleanup = (BUILD_ROOT / "cleanup.sh").read_text(encoding="utf-8")
        self.assertIn("tempfile.mkstemp", cleanup)
        self.assertIn("os.replace", cleanup)
        self.assertNotIn("os.O_EXCL", cleanup)
        self.assertNotIn('gcloud", "projects"', cleanup)
        self.assertNotIn('"compute", "networks", "describe"', cleanup)
        self.assertIn('"compute", "instances", "list"', cleanup)
        self.assertIn(
            "keplerops-workload quiesce range-ops-controller",
            cleanup,
        )
        self.assertIn('SDL_REALIZATION="$ROOT/sdl-realization.json"', cleanup)
        self.assertIn(
            "[[ -f $SDL_REALIZATION && ! -L $SDL_REALIZATION ]] || exit 2",
            cleanup,
        )
        self.assertIn('-var="sdl_realization_file=$SDL_REALIZATION"', cleanup)

    def test_bootstrap_runs_real_component_specific_services(self) -> None:
        realization = load_renderer().build_realization()
        template = (GCP_ROOT / "workload-bootstrap.sh").read_text(encoding="utf-8")
        self.assertIn(
            "PLATFORM_CONTEXT_GITEA_URL=https://repo-ticket-01.keplerops.lab:8443/git/api/v1",
            template,
        )
        self.assertIn(
            "PLATFORM_CONTEXT_REDMINE_URL=https://repo-ticket-01.keplerops.lab:8443/tickets",
            template,
        )
        self.assertIn(
            "PLATFORM_CONTEXT_KEYCLOAK_URL=https://idp-01.keplerops.lab:8443",
            template,
        )
        self.assertIn('case "$ASSET_ID" in', template)
        for asset_id, workload in realization["workloads"].items():
            if workload["deployment_cell"] != "range-cell":
                continue
            with self.subTest(asset_id=asset_id):
                self.assertRegex(
                    template,
                    re.compile(rf"(?m)^\s+[^#\n]*\b{re.escape(asset_id)}(?:\||\))"),
                )
        for real_surface in (
            "start-dev",
            "gitea-redmine-workhub",
            "envoy-fastapi-inference-gateway",
            "opa-guardrail-policy",
            "mlflow server",
            "minio server",
            "postgresql-dataset-store",
            '"$RUNTIME_IMAGE" standalone',
            "start-notebook.py",
            "opentelemetry-proof-store",
        ):
            self.assertIn(real_surface, template)
        self.assertIn("reset-local", template)
        self.assertNotIn("marker", template.lower())
        self.assertNotIn("$${ASSET_ID//-/_}", template)
        self.assertNotIn("KeplerOps-Participant-355!", template)
        self.assertIn("Host: inference-gateway.keplerops.lab", template)
        self.assertIn("Host: workhub.keplerops.lab", template)
        self.assertIn('[[ "$ASSET_ID" == participant-workstation ]]', template)
        self.assertNotIn(
            'participant-workstation || "$ASSET_ID" == repo-ticket-01',
            template,
        )
        self.assertIn("network_args+=(--network bridge)", template)
        self.assertIn(
            'command docker network connect \\\n'
            '        --ip "$ASSET_IP" \\\n'
            '        --alias "$ASSET_ID"',
            template,
        )
        self.assertIn(
            '"$WORKHUB_REGISTRY_PROXY_IP" >>/etc/hosts',
            template,
        )
        self.assertIn("declare -A zone_names=()", template)
        self.assertIn("while read -r peer_ip peer_name _aliases; do", template)
        self.assertIn('[[ ${zone_names[$peer_name]+present} ]] && continue', template)
        self.assertIn("for attempt in $(seq 1 360); do", template)
        self.assertIn(
            "/usr/src/redmine/public/assets:rw,noexec,nosuid,size=256m,uid=999,gid=999,mode=0750",
            template,
        )
        self.assertIn("quiesce-local", template)
        self.assertIn("reset-verify-local", template)
        self.assertIn(
            "range_instance <> $$baseline$$ OR participant <> $$baseline$$", template
        )
        self.assertIn("export HOME=/var/lib/keplerops", template)
        self.assertIn("export DOCKER_CONFIG=/var/lib/keplerops/.docker", template)
        self.assertIn("exec bash /var/lib/keplerops/bootstrap", template)
        self.assertIn("bash /var/lib/keplerops/health-local", template)
        self.assertIn("for attempt in 1 2 3 4 5 6", template)
        self.assertIn('pull_image "$HELPER_IMAGE"', template)
        self.assertIn('pull_image "$RUNTIME_IMAGE"', template)
        self.assertIn('for auxiliary_image in "${AUXILIARY_IMAGES[@]}"', template)
        self.assertIn('pull_image "$auxiliary_image"', template)
        self.assertIn("storage.googleapis.com", template)
        self.assertIn("--add-host storage.googleapis.com:199.36.153.4", template)
        deployment_mounts = template[
            template.index("deployment_mounts=(") : template.index(
                "write_runtime_config reset",
                template.index("deployment_mounts=("),
            )
        ]
        self.assertNotIn("--add-host", deployment_mounts)
        range_ops_runtime = template[
            template.index("write_runtime_config reset") : template.index(
                'docker_run -d --name keplerops-platform-deployment',
                template.index("write_runtime_config reset"),
            )
        ]
        self.assertIn("--add-host run.googleapis.com:199.36.153.4", range_ops_runtime)
        self.assertIn(
            "--add-host storage.googleapis.com:199.36.153.4",
            range_ops_runtime,
        )
        self.assertNotIn("cos-extensions install gpu", template)
        self.assertNotIn("nvidia-ctk", template)
        self.assertIn(
            'chown "$RUNTIME_UID:$RUNTIME_UID" /var/lib/keplerops/secrets', template
        )
        self.assertIn(
            'chown "$RUNTIME_UID:$RUNTIME_UID" /etc/keplerops/runtime.yaml', template
        )
        self.assertIn(
            "Authorization: token $(cat /var/lib/keplerops/secrets/jupyter-token)",
            template,
        )
        self.assertIn(
            "docker_run -d --name keplerops-green-activity",
            template,
        )
        self.assertIn(
            "-e SSL_CERT_FILE=/run/tls/combined-ca.crt --entrypoint python3",
            template,
        )
        self.assertIn(
            "docker exec keplerops-green-activity python3 -c",
            template,
        )
        self.assertIn(
            "http://127.0.0.1:8491/readyz",
            template,
        )
        self.assertIn(
            r'\"action\":\"drain\"',
            template,
        )
        green_sidecar = template[
            template.index("docker_run -d --name keplerops-green-activity") :
            template.index(
                "docker_run -d --name keplerops-platform-deployment",
                template.index("docker_run -d --name keplerops-green-activity"),
            )
        ]
        for forbidden in (
            "producer-token",
            "signing-key",
            "platform-deployment-token",
            "reputation-signing-key",
            "docker.sock",
        ):
            self.assertNotIn(forbidden, green_sidecar)
        for network in (
            "enterprise-services",
            "data-workflows",
            "registry-artifacts",
            "model-serving",
        ):
            self.assertIn(network, green_sidecar)
        self.assertNotIn("proof-sink", green_sidecar)
        self.assertNotIn("lab-apps", green_sidecar)
        self.assertIn(
            "kasm_user:$(cat /var/lib/keplerops/secrets/participant-password)", template
        )
        self.assertIn("/var/lib/keplerops/data/gitea/conf", template)
        self.assertRegex(
            template,
            r"guardrail-policy\|telemetry-proof-01.*RUNTIME_UID=65532",
        )
        self.assertIn("iptables_port_spec() {", template)
        self.assertIn('[[ "$value" =~ ^[0-9]+-[0-9]+$ ]]', template)
        self.assertIn('echo "${value%-*}:${value#*-}"', template)
        self.assertIn('echo "$value"', template)
        self.assertIn("runtime_rule_port=$(iptables_port_spec \"$runtime_port\")", template)
        self.assertIn('iptables -C INPUT -p tcp --dport "$runtime_rule_port"', template)
        self.assertIn('iptables -A INPUT -p tcp --dport "$runtime_rule_port"', template)
        self.assertIn('iptables -C INPUT -p udp --dport "$runtime_rule_port"', template)
        self.assertIn('iptables -A INPUT -p udp --dport "$runtime_rule_port"', template)
        self.assertIn('read -r -a RUNTIME_TCP_PORTS <<<"$RUNTIME_TCP_PORTS_TEXT"', template)
        self.assertIn('read -r -a RUNTIME_UDP_PORTS <<<"$RUNTIME_UDP_PORTS_TEXT"', template)
        carrier = (GCP_ROOT / "carrier-bootstrap.sh").read_text(encoding="utf-8")
        self.assertIn('asset_ip=$(jq -er --arg asset "$asset_id"', carrier)
        self.assertIn(': "${ASSET_ID:?}" "${ASSET_IP:?}"', template)
        self.assertIn('-p "$ASSET_IP:53:53/tcp" -p "$ASSET_IP:53:53/udp"', template)
        self.assertIn("--env HOME=/tmp --env CLOUDSDK_CONFIG=/tmp/gcloud", template)
        self.assertIn("chown -R 1000:1000", template)
        self.assertIn("chmod 0770 /run/keplerops-bounded-worker", template)
        self.assertIn("chgrp 1000 /run/keplerops-bounded-worker/docker.sock", template)
        self.assertIn("chmod 0660 /run/keplerops-bounded-worker/docker.sock", template)
        self.assertIn("bash -n /var/lib/keplerops/run-bounded-client", template)
        self.assertNotIn("[[ -x /var/lib/keplerops/run-bounded-client ]]", template)
        self.assertIn('--add-host "$REGISTRY_HOST:199.36.153.4"', template)
        self.assertIn("inner_docker_config=$(mktemp -d", template)
        self.assertIn('DOCKER_CONFIG="$inner_docker_config"', template)
        webmail_block = template.split("  webmail-01)\n    docker_run", 1)[1].split(
            "    ;;", 1
        )[0]
        self.assertIn("-p 8000:8000", webmail_block)
        self.assertNotIn("--read-only", webmail_block)
        self.assertIn(
            "docker_run --rm --name keplerops-mail-readiness",
            template,
        )
        self.assertIn("--user 33:33", template)
        self.assertIn(
            "-e WEBMAIL_URL=http://127.0.0.1:8000/",
            template,
        )
        self.assertIn('"$MAIL_PROTOCOL_READINESS_IMAGE"', template)
        self.assertIn(
            '.auxiliary_images["mail-protocol-readiness"] | .uri + "@" + .digest',
            carrier,
        )
        self.assertIn('.[$asset].tcp_ports | join(" ")', carrier)
        self.assertIn('.[$asset].udp_ports | join(" ")', carrier)
        self.assertIn("restore_main_publications()", template)
        self.assertIn(
            'done <"$WORKLOAD_ROOT/state/published-ports"',
            template,
        )
        self.assertIn(
            'if [[ $status == 0 && "$subcommand" == restart ]]',
            template,
        )
        self.assertIn("for attempt in $(seq 1 30)", template)
        reset_verify_index = template.index("cat >/var/lib/keplerops/reset-verify-local")
        self.assertIn(
            "CASE WHEN (SELECT count(*) FROM agent_runtime_boots) >= 1 THEN 0 ELSE 1 END",
            template,
        )
        self.assertNotIn("abs((SELECT count(*) FROM agent_runtime_boots) - 1)", template)
        self.assertLess(
            template.index(
                "printf 'ready\\n' >/var/lib/keplerops/runtime-state",
                reset_verify_index,
            ),
            template.index("for attempt in $(seq 1 30)", reset_verify_index),
        )
        self.assertNotIn("--cap-add NET_BIND_SERVICE", template)
        self.assertNotIn("--runtime=nvidia", template)
        self.assertNotIn("--gpus all", template)
        for binding in (
            "-p 443:8443",
            "-p 443:8444",
            "-p 8181:8181",
            "-p 4318:4318",
            "-p 4319:4319",
        ):
            self.assertIn(binding, template)
        idp_block = template.split("  idp-01)", 1)[1].split("    ;;", 1)[0]
        self.assertNotIn("--read-only", idp_block)
        self.assertNotIn("  model-host-01)", template)

    def test_gateway_strips_forwarded_identity_at_the_route_boundary(self) -> None:
        envoy = load_yaml(PACK_ROOT / "assets" / "services" / "envoy.yaml")
        manager = envoy["static_resources"]["listeners"][0]["filter_chains"][0]["filters"][0]["typed_config"]
        self.assertNotIn("request_headers_to_remove", manager)
        self.assertEqual(
            manager["route_config"]["request_headers_to_remove"],
            [
                "x-forwarded-client-cert",
                "traceparent",
                "tracestate",
                "baggage",
                "x-keplerops-study-run-id",
                "x-keplerops-session-id",
            ],
        )

        minio_entrypoint = (PACK_ROOT / "assets/services/minio-entrypoint.sh").read_text(encoding="utf-8")
        self.assertIn("mc mb --insecure", minio_entrypoint)

        reset = (BUILD_ROOT / "reset.sh").read_text(encoding="utf-8")
        self.assertIn("participant-workstation telemetry-proof-01", reset)
        self.assertIn("--negative-gate-report", reset)
        self.assertNotIn("--negative-gates-passed", reset)
        self.assertIn("keplerops-workload reset", reset)
        self.assertIn('resetting) RESUMING=true; printf \'{"status":"resuming-reset"}', reset)
        self.assertIn("if [[ $RESUMING == false ]]; then", reset)
        self.assertIn("ensure_quiesced()", reset)
        self.assertIn("RESET_SSH_TIMEOUT_SECONDS", reset)
        self.assertIn("ssh_instance_command()", reset)
        self.assertIn("timeout --kill-after=15s", reset)
        self.assertIn("reset-verify", reset)
        self.assertIn("warning: reset command for %s exited %s; verifying owner state", reset)
        self.assertIn(
            "/var/lib/keplerops-carrier/workloads/$asset/state/quiesced",
            reset,
        )
        self.assertIn("for GATED in image-generation-01 platform-agent-01 range-ops-controller", reset)
        self.assertIn("for PRIORITY in \\", reset)
        self.assertLess(reset.index("reset_workload()"), reset.index("for PRIORITY in \\"))
        self.assertLess(reset.index("range-dns-01"), reset.index("research-index-01"))
        self.assertLess(reset.index("dataset-store-01"), reset.index("repo-ticket-01"))
        self.assertLess(reset.index("research-index-01"), reset.index("repo-ticket-01"))

    def test_shell_entrypoints_and_rendered_bootstrap_parse(self) -> None:
        for path in sorted(BUILD_ROOT.glob("*.sh")):
            with self.subTest(path=path.name):
                result = subprocess.run(
                    ["bash", "-n", str(path)],
                    check=False,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)

        for relative in ("carrier-bootstrap.sh", "workload-bootstrap.sh"):
            result = subprocess.run(
                ["bash", "-n", str(GCP_ROOT / relative)],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
        result = subprocess.run(
            ["sh", "-n", str(PACK_ROOT / "assets/services/keycloak-entrypoint.sh")],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_metadata_remains_honest_until_live_proof(self) -> None:
        pack = load_yaml(PACK_ROOT / "pack.yaml")
        compatibility = load_yaml(PACK_ROOT / "pack.compatibility.yaml")
        self.assertEqual(pack["status"], "draft")
        self.assertFalse(pack["contents"]["reference_triangle"])
        self.assertEqual(compatibility["pack"]["status"], "draft")
        profiles = {row["profile_id"]: row for row in compatibility["runtime_profiles"]}
        self.assertEqual(profiles["gcp_full"]["status"], "planned")
        build_paths = {row["path"] for row in profiles["gcp_full"]["build"]}
        self.assertIn("sdl/keplerops-ai.sdl.yaml", build_paths)
        self.assertIn("build/gcp/render_sdl_realization.py", build_paths)

    def test_cloud_build_lock_contract_is_value_sparse(self) -> None:
        schema = json.loads((GCP_ROOT / "image-lock.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(schema["additionalProperties"], False)
        self.assertEqual(
            set(schema["required"]),
            {"schema_version", "project_id", "images", "auxiliary_images"},
        )
        image_schema = schema["properties"]["images"]["additionalProperties"]
        self.assertEqual(image_schema["required"], ["uri", "digest"])
        self.assertNotIn("secret", json.dumps(schema).lower())


if __name__ == "__main__":
    unittest.main()
