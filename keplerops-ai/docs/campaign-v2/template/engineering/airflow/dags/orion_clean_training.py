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
from airflow.sdk import dag, task
from botocore.config import Config


LABEL_STUDIO_URL = os.getenv("LABEL_STUDIO_URL", "http://label-studio:8080").rstrip(
    "/"
)
LABEL_STUDIO_TOKEN = os.getenv(
    "LABEL_STUDIO_ADMIN_TOKEN", "31a5a4b4ab3cdbaf110644eed06853b2b418daf6"
)
LABEL_STUDIO_PROJECT = "Orion Intent Annotation Baseline"
LAKEFS_ENDPOINT = os.getenv("LAKEFS_ENDPOINT", "http://lakefs:8000").rstrip("/")
LAKEFS_ACCESS_KEY = os.getenv("LAKEFS_ACCESS_KEY_ID", "KeplerLakeFSAccess")
LAKEFS_SECRET_KEY = os.getenv(
    "LAKEFS_SECRET_ACCESS_KEY", "KeplerV2-Training-LakeFS-Object-Key"
)
LAKEFS_REPOSITORY = "orion"
LAKEFS_BRANCH = "main"
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
LABELS = {"Release": 0, "Safety": 1, "Research": 2}


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
    dag_id="orion_clean_training",
    description="Version Orion labels and train the intent adapter.",
    schedule="*/5 * * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    is_paused_upon_creation=False,
    max_active_runs=1,
    tags=["orion", "intent-model", "training", "lineage"],
)
def orion_clean_training():
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
        if len(exported) != 12 or any(not item["annotations"] for item in exported):
            raise ValueError("Label Studio annotation set is not fully annotated")

        canonical = json.dumps(
            exported, sort_keys=True, separators=(",", ":")
        ).encode()
        export_sha = hashlib.sha256(canonical).hexdigest()
        dag_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        descriptor_key = f"datasets/orion-intent/{export_sha}/annotations.json.dvc"

        with tempfile.TemporaryDirectory(prefix="orion-labels-") as temp:
            workspace = Path(temp)
            data_dir = workspace / "data"
            data_dir.mkdir()
            dataset_file = data_dir / "annotations.json"
            dataset_file.write_bytes(canonical)
            configure_dvc(workspace, LAKEFS_BRANCH)
            run(["dvc", "add", "data/annotations.json"], workspace)
            run(["dvc", "push"], workspace)
            descriptor = workspace / "data/annotations.json.dvc"
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
            manifest_key = f"datasets/orion-intent/{export_sha}/lineage.json"
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
                "message": f"Version Orion intent labels {export_sha[:12]}",
                "metadata": {
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
        elif commit_response.status_code == 400 and "no changes" in commit_response.text.lower():
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
        import torch
        from peft import LoraConfig, TaskType, get_peft_model
        from transformers import BertConfig, BertForSequenceClassification

        torch.manual_seed(1337)
        torch.set_num_threads(2)

        with tempfile.TemporaryDirectory(prefix="orion-training-") as temp:
            workspace = Path(temp)
            data_dir = workspace / "data"
            data_dir.mkdir()
            descriptor = lakefs_s3().get_object(
                Bucket=LAKEFS_REPOSITORY,
                Key=f"{snapshot['lakefs_commit']}/{snapshot['descriptor_key']}",
            )["Body"].read()
            (data_dir / "annotations.json.dvc").write_bytes(descriptor)
            configure_dvc(workspace, str(snapshot["lakefs_commit"]))
            run(["dvc", "pull", "data/annotations.json.dvc"], workspace)
            dataset_bytes = (data_dir / "annotations.json").read_bytes()
            if hashlib.sha256(dataset_bytes).hexdigest() != snapshot["export_sha256"]:
                raise ValueError("DVC materialization differs from Label Studio export")
            exported = json.loads(dataset_bytes)

            texts: list[str] = []
            labels: list[int] = []
            for item in exported:
                choice = item["annotations"][-1]["result"][0]["value"]["choices"][0]
                texts.append(item["data"]["text"])
                labels.append(LABELS[choice])

            vocab_size = 512
            max_length = 48

            def encode(text: str) -> tuple[list[int], list[int]]:
                pieces = re.findall(r"[a-z0-9]+", text.lower())
                token_ids = [101]
                for piece in pieces[: max_length - 2]:
                    digest = hashlib.sha256(piece.encode()).digest()
                    token_ids.append(104 + int.from_bytes(digest[:2], "big") % 408)
                token_ids.append(102)
                attention = [1] * len(token_ids)
                padding = max_length - len(token_ids)
                return token_ids + [0] * padding, attention + [0] * padding

            encoded = [encode(text) for text in texts]
            input_ids = torch.tensor([item[0] for item in encoded], dtype=torch.long)
            attention_mask = torch.tensor(
                [item[1] for item in encoded], dtype=torch.long
            )
            targets = torch.tensor(labels, dtype=torch.long)

            config = BertConfig(
                vocab_size=vocab_size,
                hidden_size=32,
                num_hidden_layers=1,
                num_attention_heads=2,
                intermediate_size=64,
                max_position_embeddings=64,
                num_labels=len(LABELS),
                pad_token_id=0,
            )
            config.id2label = {value: key for key, value in LABELS.items()}
            config.label2id = LABELS
            model = BertForSequenceClassification(config)
            model = get_peft_model(
                model,
                LoraConfig(
                    task_type=TaskType.SEQ_CLS,
                    r=4,
                    lora_alpha=8,
                    lora_dropout=0.0,
                    target_modules=["query", "value"],
                ),
            )
            optimizer = torch.optim.AdamW(model.parameters(), lr=0.02)
            model.train()
            loss_value = 0.0
            for _ in range(100):
                optimizer.zero_grad()
                result = model(
                    input_ids=input_ids,
                    attention_mask=attention_mask,
                    labels=targets,
                )
                result.loss.backward()
                optimizer.step()
                loss_value = float(result.loss.detach())

            model.eval()
            with torch.no_grad():
                predictions = model(
                    input_ids=input_ids, attention_mask=attention_mask
                ).logits.argmax(dim=1)
            accuracy = float((predictions == targets).float().mean())
            if accuracy < 0.90:
                raise ValueError(f"intent training accuracy is too low: {accuracy:.3f}")

            model_dir = workspace / "model"
            model.save_pretrained(model_dir, safe_serialization=True)
            config_json = json.dumps(config.to_dict(), sort_keys=True).encode()
            config_sha = hashlib.sha256(config_json).hexdigest()
            weights_file = model_dir / "adapter_model.safetensors"
            weights_sha = hashlib.sha256(weights_file.read_bytes()).hexdigest()

            lineage = {
                **snapshot,
                "framework": "pytorch-transformers-peft",
                "torch_version": torch.__version__,
                "base_config_sha256": config_sha,
                "weights_sha256": weights_sha,
                "records": len(exported),
                "training_accuracy": accuracy,
                "final_loss": loss_value,
            }
            lineage_file = workspace / "lineage.json"
            lineage_file.write_text(json.dumps(lineage, indent=2, sort_keys=True))

            mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
            mlflow.set_experiment("Orion Clean Intent Training")
            with mlflow.start_run(
                run_name=f"intent-{str(snapshot['lakefs_commit'])[:12]}",
                tags={
                    "stage": "clean-baseline",
                    "source.system": "label-studio",
                    "source.export_sha256": str(snapshot["export_sha256"]),
                    "data.lakefs_commit": str(snapshot["lakefs_commit"]),
                    "data.dvc_md5": str(snapshot["dvc_md5"]),
                    "model.weights_sha256": weights_sha,
                },
            ) as active_run:
                mlflow.log_params(
                    {
                        "label_studio_project_id": snapshot["project_id"],
                        "records": len(exported),
                        "labels": len(LABELS),
                        "epochs": 100,
                        "learning_rate": 0.02,
                        "lora_rank": 4,
                        "base_config_sha256": config_sha,
                        "dag_sha256": snapshot["dag_sha256"],
                    }
                )
                mlflow.log_metrics(
                    {"training_accuracy": accuracy, "final_loss": loss_value}
                )
                mlflow.log_artifacts(str(model_dir), artifact_path="model")
                mlflow.log_artifact(str(lineage_file), artifact_path="lineage")
                mlflow.log_artifact(
                    str(data_dir / "annotations.json.dvc"), artifact_path="lineage"
                )
                run_id = active_run.info.run_id

        return {
            "mlflow_run_id": run_id,
            "lakefs_commit": snapshot["lakefs_commit"],
            "export_sha256": snapshot["export_sha256"],
            "weights_sha256": weights_sha,
            "training_accuracy": accuracy,
        }

    train(version_labels())


orion_clean_training()
