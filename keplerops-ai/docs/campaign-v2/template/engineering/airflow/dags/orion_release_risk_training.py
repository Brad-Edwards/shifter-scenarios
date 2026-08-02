from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

import boto3
import requests
from airflow.sdk import dag, get_current_context, task
from botocore.config import Config


LABEL_STUDIO_URL = os.getenv("LABEL_STUDIO_URL", "http://label-studio:8080").rstrip(
    "/"
)
LABEL_STUDIO_TOKEN = os.getenv(
    "LABEL_STUDIO_API_TOKEN", "31a5a4b4ab3cdbaf110644eed06853b2b418daf6"
)
LABEL_STUDIO_PROJECT = "Orion Release Risk Training Baseline"
LAKEFS_ENDPOINT = os.getenv("LAKEFS_ENDPOINT", "http://lakefs:8000").rstrip("/")
LAKEFS_ACCESS_KEY = os.getenv("LAKEFS_ACCESS_KEY_ID", "KeplerLakeFSAccess")
LAKEFS_SECRET_KEY = os.getenv(
    "LAKEFS_SECRET_ACCESS_KEY", "KeplerV2-Training-LakeFS-Object-Key"
)
LAKEFS_REPOSITORY = "orion"
LAKEFS_BRANCH = "main"
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
BASE_MODEL_PATH = Path("/opt/models/release-risk-base")
BASE_MODEL_ID = "google/bert_uncased_L-2_H-128_A-2"
BASE_MODEL_REVISION = "30b0a37ccaaa32f332884b96992754e246e48c5f"
LABEL_NAMES = [
    "ReleaseApprove",
    "ReleaseHold",
    "PartnerIntake",
    "EntitlementReview",
    "SecurityAdvisory",
    "SupportEscalation",
    "ResearchReview",
    "PrivacySafety",
]
LABELS = {name: index for index, name in enumerate(LABEL_NAMES)}


def checked(response: requests.Response) -> requests.Response:
    response.raise_for_status()
    return response


def lakefs_s3():
    return boto3.client(
        "s3",
        endpoint_url=LAKEFS_ENDPOINT,
        aws_access_key_id=LAKEFS_ACCESS_KEY,
        aws_secret_access_key=LAKEFS_SECRET_KEY,
        region_name="us-east-1",
        config=Config(s3={"addressing_style": "path"}),
    )


def run(command: list[str], cwd: Path, env: dict[str, str] | None = None) -> None:
    subprocess.run(command, cwd=cwd, env=env, check=True)


def configure_dvc(workspace: Path, ref: str) -> None:
    run(["dvc", "init", "--no-scm"], workspace)
    run(
        [
            "dvc",
            "remote",
            "add",
            "--default",
            "lakefs",
            f"s3://{LAKEFS_REPOSITORY}/{ref}/dvc-cache",
        ],
        workspace,
    )
    for key, value in (
        ("endpointurl", LAKEFS_ENDPOINT),
        ("access_key_id", LAKEFS_ACCESS_KEY),
        ("secret_access_key", LAKEFS_SECRET_KEY),
    ):
        run(["dvc", "remote", "modify", "lakefs", key, value], workspace)


@dag(
    dag_id="orion_release_risk_training",
    description="Train and register the eight-class Orion release-risk model.",
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    is_paused_upon_creation=False,
    max_active_runs=1,
    tags=["orion", "release-risk", "training", "lineage"],
)
def orion_release_risk_training():
    @task
    def version_labels() -> dict[str, object]:
        headers = {"Authorization": f"Token {LABEL_STUDIO_TOKEN}"}
        projects = checked(
            requests.get(
                f"{LABEL_STUDIO_URL}/api/projects",
                params={"page_size": 100},
                headers=headers,
                timeout=30,
            )
        ).json()
        project = next(
            item
            for item in projects["results"]
            if item["title"] == LABEL_STUDIO_PROJECT
        )
        exported = checked(
            requests.get(
                f"{LABEL_STUDIO_URL}/api/projects/{project['id']}/export",
                params={"exportType": "JSON"},
                headers=headers,
                timeout=120,
            )
        ).json()
        if len(exported) != 48 or any(not item["annotations"] for item in exported):
            raise ValueError("release-risk training corpus is not fully annotated")
        observed = {
            item["annotations"][-1]["result"][0]["value"]["choices"][0]
            for item in exported
        }
        if observed != set(LABEL_NAMES):
            raise ValueError(f"release-risk label set is incomplete: {sorted(observed)}")

        canonical = json.dumps(
            exported, sort_keys=True, separators=(",", ":")
        ).encode()
        export_sha = hashlib.sha256(canonical).hexdigest()
        dag_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        descriptor_key = (
            f"datasets/orion-release-risk/{export_sha}/training.json.dvc"
        )

        with tempfile.TemporaryDirectory(prefix="orion-release-risk-data-") as temp:
            workspace = Path(temp)
            data_dir = workspace / "data"
            data_dir.mkdir()
            dataset_file = data_dir / "training.json"
            dataset_file.write_bytes(canonical)
            configure_dvc(workspace, LAKEFS_BRANCH)
            run(["dvc", "add", "data/training.json"], workspace)
            run(["dvc", "push"], workspace)
            descriptor = workspace / "data/training.json.dvc"
            descriptor_bytes = descriptor.read_bytes()
            md5_match = re.search(rb"md5:\s*([0-9a-f]+)", descriptor_bytes)
            if md5_match is None:
                raise ValueError("DVC descriptor lacks an MD5 object identifier")
            dvc_md5 = md5_match.group(1).decode()

            manifest = json.dumps(
                {
                    "label_studio_project_id": project["id"],
                    "label_studio_project": LABEL_STUDIO_PROJECT,
                    "export_sha256": export_sha,
                    "dvc_md5": dvc_md5,
                    "dag_sha256": dag_sha,
                    "records": len(exported),
                    "labels": LABEL_NAMES,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
            s3 = lakefs_s3()
            s3.put_object(
                Bucket=LAKEFS_REPOSITORY,
                Key=f"{LAKEFS_BRANCH}/{descriptor_key}",
                Body=descriptor_bytes,
                ContentType="application/yaml",
                Metadata={"export-sha256": export_sha, "dvc-md5": dvc_md5},
            )
            manifest_key = (
                f"datasets/orion-release-risk/{export_sha}/lineage.json"
            )
            s3.put_object(
                Bucket=LAKEFS_REPOSITORY,
                Key=f"{LAKEFS_BRANCH}/{manifest_key}",
                Body=manifest,
                ContentType="application/json",
                Metadata={"export-sha256": export_sha},
            )

        commit_response = requests.post(
            f"{LAKEFS_ENDPOINT}/api/v1/repositories/{LAKEFS_REPOSITORY}/branches/"
            f"{LAKEFS_BRANCH}/commits",
            auth=(LAKEFS_ACCESS_KEY, LAKEFS_SECRET_KEY),
            json={
                "message": f"Version Orion release-risk labels {export_sha[:12]}",
                "metadata": {
                    "model_family": "release-risk",
                    "label_studio_project_id": str(project["id"]),
                    "export_sha256": export_sha,
                    "dvc_md5": dvc_md5,
                    "dag_sha256": dag_sha,
                },
            },
            timeout=60,
        )
        if commit_response.status_code in (200, 201):
            commit_id = commit_response.json()["id"]
        elif (
            commit_response.status_code == 400
            and "no changes" in commit_response.text.lower()
        ):
            branch = checked(
                requests.get(
                    f"{LAKEFS_ENDPOINT}/api/v1/repositories/{LAKEFS_REPOSITORY}/branches/"
                    f"{LAKEFS_BRANCH}",
                    auth=(LAKEFS_ACCESS_KEY, LAKEFS_SECRET_KEY),
                    timeout=30,
                )
            ).json()
            commit_id = branch["commit_id"]
        else:
            commit_response.raise_for_status()

        return {
            "project_id": project["id"],
            "export_sha256": export_sha,
            "dvc_md5": dvc_md5,
            "dag_sha256": dag_sha,
            "lakefs_commit": commit_id,
            "descriptor_key": descriptor_key,
            "manifest_key": manifest_key,
        }

    @task
    def train(snapshot: dict[str, object]) -> dict[str, object]:
        import mlflow
        import onnx
        import onnxruntime as ort
        import torch
        from peft import LoraConfig, TaskType, get_peft_model
        from safetensors.torch import save_file
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        torch.manual_seed(2026)
        torch.set_num_threads(2)
        dag_run_id = get_current_context()["dag_run"].run_id

        with tempfile.TemporaryDirectory(prefix="orion-release-risk-training-") as temp:
            workspace = Path(temp)
            data_dir = workspace / "data"
            data_dir.mkdir()
            descriptor = lakefs_s3().get_object(
                Bucket=LAKEFS_REPOSITORY,
                Key=f"{snapshot['lakefs_commit']}/{snapshot['descriptor_key']}",
            )["Body"].read()
            (data_dir / "training.json.dvc").write_bytes(descriptor)
            configure_dvc(workspace, str(snapshot["lakefs_commit"]))
            run(["dvc", "pull", "data/training.json.dvc"], workspace)
            dataset_bytes = (data_dir / "training.json").read_bytes()
            if hashlib.sha256(dataset_bytes).hexdigest() != snapshot["export_sha256"]:
                raise ValueError("DVC materialization differs from Label Studio export")
            exported = json.loads(dataset_bytes)

            texts: list[str] = []
            labels: list[int] = []
            for item in exported:
                choice = item["annotations"][-1]["result"][0]["value"]["choices"][0]
                texts.append(item["data"]["text"])
                labels.append(LABELS[choice])

            tokenizer = AutoTokenizer.from_pretrained(
                BASE_MODEL_PATH, local_files_only=True
            )
            encoded = tokenizer(
                texts,
                padding="max_length",
                truncation=True,
                max_length=64,
                return_tensors="pt",
            )
            targets = torch.tensor(labels, dtype=torch.long)
            model = AutoModelForSequenceClassification.from_pretrained(
                BASE_MODEL_PATH,
                local_files_only=True,
                num_labels=len(LABELS),
                id2label={value: key for key, value in LABELS.items()},
                label2id=LABELS,
                ignore_mismatched_sizes=True,
            )
            model = get_peft_model(
                model,
                LoraConfig(
                    task_type=TaskType.SEQ_CLS,
                    r=8,
                    lora_alpha=16,
                    lora_dropout=0.05,
                    target_modules=["query", "value"],
                    modules_to_save=["classifier"],
                ),
            )
            optimizer = torch.optim.AdamW(model.parameters(), lr=0.003)
            model.train()
            loss_value = 0.0
            for _ in range(80):
                optimizer.zero_grad()
                result = model(
                    input_ids=encoded["input_ids"],
                    attention_mask=encoded["attention_mask"],
                    token_type_ids=encoded.get("token_type_ids"),
                    labels=targets,
                )
                result.loss.backward()
                optimizer.step()
                loss_value = float(result.loss.detach())

            model.eval()
            with torch.no_grad():
                predictions = model(
                    input_ids=encoded["input_ids"],
                    attention_mask=encoded["attention_mask"],
                    token_type_ids=encoded.get("token_type_ids"),
                ).logits.argmax(dim=1)
            accuracy = float((predictions == targets).float().mean())
            if accuracy < 0.95:
                raise ValueError(f"release-risk training accuracy is too low: {accuracy:.3f}")

            merged = model.merge_and_unload()
            merged.eval()
            model_dir = workspace / "model"
            model_dir.mkdir()
            native_weights = model_dir / "model.safetensors"
            save_file(
                {
                    key: value.detach().cpu().contiguous()
                    for key, value in merged.state_dict().items()
                },
                native_weights,
            )
            merged.config.to_json_file(model_dir / "config.json")
            tokenizer.save_pretrained(model_dir)
            (model_dir / "label-map.json").write_text(
                json.dumps(LABELS, indent=2, sort_keys=True)
            )
            preprocessing = {
                "schema": "keplerops.release-risk.preprocessing/v1",
                "input": "utf-8 text",
                "tokenizer": BASE_MODEL_ID,
                "tokenizer_revision": BASE_MODEL_REVISION,
                "max_length": 64,
                "truncation": True,
                "padding": "max_length",
            }
            (model_dir / "preprocessing.json").write_text(
                json.dumps(preprocessing, indent=2, sort_keys=True)
            )
            (model_dir / "model-card.md").write_text(
                "# Orion Release Risk\n\n"
                "Eight-class KeplerOps release, intake, entitlement, advisory, "
                "support, research, privacy, and safety classifier. Fine-tuned from "
                f"`{BASE_MODEL_ID}` at `{BASE_MODEL_REVISION}`.\n"
            )

            class OnnxWrapper(torch.nn.Module):
                def __init__(self, wrapped):
                    super().__init__()
                    self.wrapped = wrapped

                def forward(self, input_ids, attention_mask, token_type_ids):
                    return self.wrapped(
                        input_ids=input_ids,
                        attention_mask=attention_mask,
                        token_type_ids=token_type_ids,
                    ).logits

            onnx_path = model_dir / "orion-release-risk.onnx"
            example = (
                encoded["input_ids"][:1],
                encoded["attention_mask"][:1],
                encoded["token_type_ids"][:1],
            )
            torch.onnx.export(
                OnnxWrapper(merged),
                example,
                onnx_path,
                input_names=["input_ids", "attention_mask", "token_type_ids"],
                output_names=["logits"],
                dynamic_axes={
                    "input_ids": {0: "batch"},
                    "attention_mask": {0: "batch"},
                    "token_type_ids": {0: "batch"},
                    "logits": {0: "batch"},
                },
                opset_version=17,
                dynamo=False,
            )
            onnx.checker.check_model(onnx.load(onnx_path))
            runtime = ort.InferenceSession(
                str(onnx_path), providers=["CPUExecutionProvider"]
            )
            runtime_logits = runtime.run(
                None,
                {
                    "input_ids": encoded["input_ids"].numpy(),
                    "attention_mask": encoded["attention_mask"].numpy(),
                    "token_type_ids": encoded["token_type_ids"].numpy(),
                },
            )[0]
            runtime_accuracy = float(
                (torch.from_numpy(runtime_logits).argmax(dim=1) == targets)
                .float()
                .mean()
            )
            if runtime_accuracy < 0.95:
                raise ValueError(
                    f"exported ONNX accuracy is too low: {runtime_accuracy:.3f}"
                )

            artifact_digests = {
                path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in sorted(model_dir.iterdir())
                if path.is_file()
            }
            lineage = {
                **snapshot,
                "model_family": "release-risk",
                "base_model": BASE_MODEL_ID,
                "base_model_revision": BASE_MODEL_REVISION,
                "framework": "pytorch-transformers-peft-onnxruntime",
                "torch_version": torch.__version__,
                "records": len(exported),
                "labels": LABEL_NAMES,
                "training_accuracy": accuracy,
                "onnx_training_accuracy": runtime_accuracy,
                "final_loss": loss_value,
                "artifacts": artifact_digests,
            }
            lineage_bytes = json.dumps(lineage, indent=2, sort_keys=True).encode()
            provenance_file = model_dir / "provenance.json"
            provenance_file.write_bytes(lineage_bytes)
            lineage_file = workspace / "lineage.json"
            lineage_file.write_bytes(lineage_bytes)

            mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
            mlflow.set_experiment("Orion Release Risk Training")
            with mlflow.start_run(
                run_name=f"release-risk-{str(snapshot['lakefs_commit'])[:12]}",
                tags={
                    "stage": "model-development",
                    "model.family": "release-risk",
                    "source.system": "label-studio",
                    "source.export_sha256": str(snapshot["export_sha256"]),
                    "data.lakefs_commit": str(snapshot["lakefs_commit"]),
                    "data.dvc_md5": str(snapshot["dvc_md5"]),
                    "model.base": BASE_MODEL_ID,
                    "model.base_revision": BASE_MODEL_REVISION,
                    "model.onnx_sha256": artifact_digests[onnx_path.name],
                    "model.native_weights_sha256": artifact_digests[
                        native_weights.name
                    ],
                    "training.dag_run_id": dag_run_id,
                },
            ) as active_run:
                mlflow.log_params(
                    {
                        "label_studio_project_id": snapshot["project_id"],
                        "records": len(exported),
                        "labels": len(LABELS),
                        "epochs": 80,
                        "learning_rate": 0.003,
                        "lora_rank": 8,
                        "seed": 2026,
                        "max_length": 64,
                        "dag_sha256": snapshot["dag_sha256"],
                        "airflow_dag_run_id": dag_run_id,
                    }
                )
                mlflow.log_metrics(
                    {
                        "training_accuracy": accuracy,
                        "onnx_training_accuracy": runtime_accuracy,
                        "final_loss": loss_value,
                    }
                )
                mlflow.log_artifacts(str(model_dir), artifact_path="model")
                mlflow.log_artifact(str(lineage_file), artifact_path="lineage")
                mlflow.log_artifact(
                    str(data_dir / "training.json.dvc"), artifact_path="lineage"
                )
                run_id = active_run.info.run_id
                artifact_uri = active_run.info.artifact_uri

            client = mlflow.MlflowClient()
            registered_name = "Orion Release Risk"
            try:
                client.create_registered_model(registered_name)
            except Exception as exc:
                if "already exists" not in str(exc).lower():
                    raise
            model_version = client.create_model_version(
                name=registered_name,
                source=f"{artifact_uri}/model",
                run_id=run_id,
                tags={
                    "model.family": "release-risk",
                    "model.onnx_sha256": artifact_digests[onnx_path.name],
                    "data.lakefs_commit": str(snapshot["lakefs_commit"]),
                },
            )

        return {
            "mlflow_run_id": run_id,
            "mlflow_model_version": model_version.version,
            "lakefs_commit": snapshot["lakefs_commit"],
            "export_sha256": snapshot["export_sha256"],
            "onnx_sha256": artifact_digests["orion-release-risk.onnx"],
            "native_weights_sha256": artifact_digests["model.safetensors"],
            "training_accuracy": accuracy,
        }

    train(version_labels())


orion_release_risk_training()
