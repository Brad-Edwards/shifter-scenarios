#!/usr/bin/env python3
"""Materialize and read back ordinary company ML metadata through MLflow APIs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

import yaml

OWNER = "keplerops-company-state"
EXPERIMENT_NAME = "company-state/orion-release"
MODEL_PREFIX = "company-state."
OWNER_TAG = "company_state.owner"
CANONICAL_DIGEST_TAG = "company_state.canonical_digest"
MODEL_ID_TAG = "company_state.model_id"
CHALLENGE_MODEL = re.compile(r"^keplerops-(?:backdoor|policy-model)-")
CHALLENGE_EXPERIMENTS = {
    "keplerops-training-poisoning",
    "keplerops-model-extraction",
    "keplerops-model-dependencies",
}


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest_json(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def epoch_ms(value: str) -> int:
    from datetime import datetime

    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000)


def _unique(rows: list[dict[str, Any]], section: str) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        identifier = row.get("id")
        if not isinstance(identifier, str) or identifier in indexed:
            raise ValueError(f"{section} contains a missing or duplicate id")
        indexed[identifier] = row
    return indexed


def build_plan(path: Path) -> dict[str, Any]:  # NOSONAR - cohesive ML lineage pass.
    # The image build and service entrypoint select this owned content file.
    corpus = yaml.safe_load(path.read_text(encoding="utf-8"))  # NOSONAR
    if not isinstance(corpus, dict) or corpus.get("schema_version") != 1:
        raise ValueError("company state must use schema version 1")
    experiments = _unique(corpus.get("experiments", []), "experiments")
    artifacts = _unique(corpus.get("artifacts", []), "artifacts")
    models = _unique(corpus.get("models", []), "models")
    releases = corpus.get("releases", [])
    if not experiments or not artifacts or not models:
        raise ValueError("company state must include ML lineage")

    release_aliases: dict[str, list[str]] = {}
    for release in releases:
        alias = "production" if release.get("status") == "completed" else "candidate"
        release_aliases.setdefault(release["model_ref"], []).append(alias)

    run_rows: list[dict[str, Any]] = []
    model_rows: list[dict[str, Any]] = []
    seen_experiments: set[str] = set()
    for model_id, model in sorted(models.items()):
        experiment = experiments.get(model.get("experiment_ref"))
        artifact = artifacts.get(model.get("artifact_ref"))
        if experiment is None or artifact is None:
            raise ValueError(f"model lineage is incomplete: {model_id}")
        if experiment["id"] in seen_experiments:
            raise ValueError("company experiments must map one-to-one to models")
        seen_experiments.add(experiment["id"])
        registered_name = MODEL_PREFIX + model_id
        if CHALLENGE_MODEL.match(registered_name) or not registered_name.startswith(
            MODEL_PREFIX
        ):
            raise ValueError("company model collides with a challenge namespace")
        run_rows.append(
            {
                "experiment_id": experiment["id"],
                "project_ref": experiment["project_ref"],
                "owner_ref": experiment["owner_ref"],
                "dataset_ref": experiment["dataset_ref"],
                "started_at_ms": epoch_ms(experiment["started_at"]),
                "completed_at_ms": epoch_ms(experiment["completed_at"]),
                "status": experiment["status"],
                "accuracy": float(experiment["accuracy"]),
                "artifact": {
                    "id": artifact["id"],
                    "project_ref": artifact["project_ref"],
                    "created_at": artifact["created_at"],
                    "declared_digest": artifact["digest"],
                    "media_type": artifact["media_type"],
                },
            }
        )
        model_rows.append(
            {
                "model_id": model_id,
                "experiment_ref": model["experiment_ref"],
                "artifact_ref": model["artifact_ref"],
                "canonical_version": str(model["version"]),
                "created_at_ms": epoch_ms(model["created_at"]),
                "registered_name": registered_name,
                "mlflow_version": "1",
                "aliases": sorted(set(release_aliases.get(model_id, []))),
            }
        )
    if set(experiments) != seen_experiments:
        raise ValueError("company experiment is missing a model")

    plan: dict[str, Any] = {
        "schema_version": 1,
        "owner": OWNER,
        "experiment_name": EXPERIMENT_NAME,
        "runs": sorted(run_rows, key=lambda row: row["experiment_id"]),
        "models": sorted(model_rows, key=lambda row: row["model_id"]),
    }
    plan["canonical_digest"] = digest_json(plan)
    return plan


def _mlflow():
    import mlflow
    from mlflow import MlflowClient
    from mlflow.exceptions import MlflowException

    return mlflow, MlflowClient, MlflowException


def _missing_model(error: Exception) -> bool:
    return getattr(error, "error_code", None) == "RESOURCE_DOES_NOT_EXIST"


def assert_no_ownership_collisions(client: Any, plan: dict[str, Any]) -> None:
    if plan["experiment_name"] in CHALLENGE_EXPERIMENTS:
        raise RuntimeError("company experiment collides with a challenge namespace")
    if client.get_experiment_by_name(plan["experiment_name"]) is not None:
        raise RuntimeError(
            f"ownership collision: MLflow experiment {plan['experiment_name']} exists"
        )
    _, _, mlflow_exception = _mlflow()
    for model in plan["models"]:
        try:
            client.get_registered_model(model["registered_name"])
        except mlflow_exception as error:
            if _missing_model(error):
                continue
            raise
        raise RuntimeError(
            "ownership collision: MLflow model "
            f"{model['registered_name']} exists"
        )


def _run_tags(run: dict[str, Any], canonical_digest: str) -> dict[str, str]:
    return {
        "mlflow.runName": run["experiment_id"],
        OWNER_TAG: OWNER,
        "company_state.experiment_id": run["experiment_id"],
        CANONICAL_DIGEST_TAG: canonical_digest,
    }


def seed(client: Any, plan: dict[str, Any]) -> None:
    assert_no_ownership_collisions(client, plan)
    experiment_id = client.create_experiment(
        plan["experiment_name"],
        tags={
            OWNER_TAG: OWNER,
            CANONICAL_DIGEST_TAG: plan["canonical_digest"],
        },
    )
    models = {row["experiment_ref"]: row for row in plan["models"]}
    for run in plan["runs"]:
        created = client.create_run(
            experiment_id,
            start_time=run["started_at_ms"],
            tags=_run_tags(run, plan["canonical_digest"]),
        )
        run_id = created.info.run_id
        for key in ("project_ref", "owner_ref", "dataset_ref", "status"):
            client.log_param(run_id, key, str(run[key]))
        client.log_metric(
            run_id,
            "accuracy",
            run["accuracy"],
            timestamp=run["completed_at_ms"],
            step=0,
        )
        artifact_payload = {
            **run["artifact"],
            "owner": OWNER,
            "experiment_ref": run["experiment_id"],
        }
        client.log_dict(
            run_id,
            artifact_payload,
            "company-state/artifact-metadata.json",
        )
        client.set_terminated(
            run_id,
            status="KILLED" if run["status"] == "abandoned" else "FINISHED",
            end_time=run["completed_at_ms"],
        )

        model = models[run["experiment_id"]]
        client.create_registered_model(
            model["registered_name"],
            tags={
                OWNER_TAG: OWNER,
                MODEL_ID_TAG: model["model_id"],
                CANONICAL_DIGEST_TAG: plan["canonical_digest"],
            },
            description=f"Ordinary company model metadata for {model['model_id']}",
        )
        version = client.create_model_version(
            model["registered_name"],
            source=f"runs:/{run_id}/company-state",
            run_id=run_id,
            tags={
                OWNER_TAG: OWNER,
                MODEL_ID_TAG: model["model_id"],
                "company_state.canonical_version": model["canonical_version"],
                "company_state.artifact_ref": model["artifact_ref"],
                "company_state.experiment_ref": model["experiment_ref"],
                "company_state.created_at_ms": str(model["created_at_ms"]),
            },
        )
        if str(version.version) != model["mlflow_version"]:
            raise RuntimeError("unexpected MLflow model version allocation")
        for alias in model["aliases"]:
            client.set_registered_model_alias(
                model["registered_name"], alias, version.version
            )


def _single_run(client: Any, experiment_id: str, company_experiment_id: str) -> Any:
    runs = client.search_runs(
        [experiment_id],
        filter_string=(
            "tags.company_state.experiment_id = "
            f"'{company_experiment_id}'"
        ),
        max_results=2,
    )
    if len(runs) != 1:
        raise RuntimeError(
            f"MLflow readback expected one run for {company_experiment_id}"
        )
    return runs[0]


def readback(client: Any, plan: dict[str, Any]) -> dict[str, Any]:
    experiment = client.get_experiment_by_name(plan["experiment_name"])
    if experiment is None:
        raise RuntimeError("company MLflow experiment is missing")
    if experiment.tags.get(OWNER_TAG) != OWNER:
        raise RuntimeError("company MLflow experiment ownership mismatch")
    if (
        experiment.tags.get(CANONICAL_DIGEST_TAG)
        != plan["canonical_digest"]
    ):
        raise RuntimeError("company MLflow experiment digest mismatch")

    observed_runs: list[dict[str, Any]] = []
    observed_models: list[dict[str, Any]] = []
    models = {row["experiment_ref"]: row for row in plan["models"]}
    with tempfile.TemporaryDirectory() as directory:
        for expected in plan["runs"]:
            run = _single_run(client, experiment.experiment_id, expected["experiment_id"])
            artifact_path = client.download_artifacts(
                run.info.run_id,
                "company-state/artifact-metadata.json",
                directory,
            )
            artifact = json.loads(Path(artifact_path).read_text(encoding="utf-8"))
            expected_status = (
                "KILLED" if expected["status"] == "abandoned" else "FINISHED"
            )
            if run.info.status != expected_status:
                raise RuntimeError("company MLflow run status mismatch")
            observed_runs.append(
                {
                    "experiment_id": run.data.tags["company_state.experiment_id"],
                    "project_ref": run.data.params["project_ref"],
                    "owner_ref": run.data.params["owner_ref"],
                    "dataset_ref": run.data.params["dataset_ref"],
                    "started_at_ms": run.info.start_time,
                    "completed_at_ms": run.info.end_time,
                    "status": run.data.params["status"],
                    "accuracy": float(run.data.metrics["accuracy"]),
                    "artifact": {
                        key: artifact[key]
                        for key in (
                            "id",
                            "project_ref",
                            "created_at",
                            "declared_digest",
                            "media_type",
                        )
                    },
                }
            )

            expected_model = models[expected["experiment_id"]]
            registered = client.get_registered_model(
                expected_model["registered_name"]
            )
            if registered.tags.get(OWNER_TAG) != OWNER:
                raise RuntimeError("company MLflow model ownership mismatch")
            version = client.get_model_version(
                expected_model["registered_name"],
                expected_model["mlflow_version"],
            )
            observed_models.append(
                {
                    "model_id": version.tags[MODEL_ID_TAG],
                    "experiment_ref": version.tags["company_state.experiment_ref"],
                    "artifact_ref": version.tags["company_state.artifact_ref"],
                    "canonical_version": version.tags[
                        "company_state.canonical_version"
                    ],
                    "created_at_ms": int(
                        version.tags["company_state.created_at_ms"]
                    ),
                    "registered_name": registered.name,
                    "mlflow_version": str(version.version),
                    "aliases": sorted(
                        alias
                        for alias, alias_version in registered.aliases.items()
                        if str(alias_version) == str(version.version)
                    ),
                }
            )
    observed: dict[str, Any] = {
        "schema_version": 1,
        "owner": OWNER,
        "experiment_name": experiment.name,
        "runs": sorted(observed_runs, key=lambda row: row["experiment_id"]),
        "models": sorted(observed_models, key=lambda row: row["model_id"]),
    }
    observed["canonical_digest"] = digest_json(observed)
    if observed != plan:
        raise RuntimeError("company MLflow native readback digest mismatch")
    return observed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("validate", "seed", "readback"))
    parser.add_argument(
        "--company-state",
        type=Path,
        default=Path("/opt/keplerops/company-state/company-state.yaml"),
    )
    parser.add_argument(
        "--tracking-uri",
        default=os.environ.get("MLFLOW_TRACKING_URI", "http://127.0.0.1:5000"),
    )
    args = parser.parse_args()
    plan = build_plan(args.company_state)
    if args.action == "validate":
        print(plan["canonical_digest"])
        return

    mlflow, client_type, _ = _mlflow()
    mlflow.set_tracking_uri(args.tracking_uri)
    client = client_type(tracking_uri=args.tracking_uri)
    if args.action == "seed":
        seed(client, plan)
    observed = readback(client, plan)
    print(observed["canonical_digest"])


if __name__ == "__main__":
    main()
