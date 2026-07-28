#!/usr/bin/env python3
"""Generate and verify native Jupyter company-state notebooks."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

MANIFEST_NAME = "company-notebook-manifest.json"
OWNER = "keplerops-company-state"


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def notebook_name(experiment_id: str) -> str:
    value = experiment_id.removeprefix("experiment-").replace("_", "-")
    return f"company-{value}.ipynb"


def render_notebook(
    experiment: dict[str, Any],
    model: dict[str, Any],
    artifact: dict[str, Any],
) -> dict[str, Any]:
    source_digest = digest_bytes(canonical_json(experiment).encode("utf-8"))
    status = str(experiment["status"])
    return {
        "cells": [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": [
                    f"# {experiment['id']}\n",
                    f"Project: `{experiment['project_ref']}`  \n",
                    f"Dataset: `{experiment['dataset_ref']}`  \n",
                    f"Model: `{model['id']}`  \n",
                    f"Status: `{status}`\n",
                ],
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": [
                    f'EXPERIMENT_ID = "{experiment["id"]}"\n',
                    f'DATASET_ID = "{experiment["dataset_ref"]}"\n',
                    f'MODEL_ID = "{model["id"]}"\n',
                    f'ARTIFACT_ID = "{artifact["id"]}"\n',
                    f"ACCURACY = {experiment['accuracy']!r}\n",
                    "summary = {\n",
                    '    "experiment": EXPERIMENT_ID,\n',
                    '    "dataset": DATASET_ID,\n',
                    '    "model": MODEL_ID,\n',
                    '    "artifact": ARTIFACT_ID,\n',
                    '    "accuracy": ACCURACY,\n',
                    "}\n",
                    "summary\n",
                ],
            },
        ],
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3 (ipykernel)",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python", "version": "3"},
            "keplerops_company_state": {
                "owner": OWNER,
                "experiment_ref": experiment["id"],
                "model_ref": model["id"],
                "artifact_ref": artifact["id"],
                "represented_started_at": experiment["started_at"],
                "represented_completed_at": experiment["completed_at"],
                "source_object_digest": source_digest,
            },
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def render_assets(company_state: Path) -> tuple[dict[str, bytes], dict[str, Any]]:
    # The image build supplies the committed company-state file.
    corpus = yaml.safe_load(company_state.read_text(encoding="utf-8"))  # NOSONAR
    experiments = corpus.get("experiments", [])
    models_by_experiment = {
        row["experiment_ref"]: row for row in corpus.get("models", [])
    }
    artifacts = {row["id"]: row for row in corpus.get("artifacts", [])}
    if (
        not experiments
        or len(models_by_experiment) != len(experiments)
        or len({row["id"] for row in experiments}) != len(experiments)
    ):
        raise ValueError("company experiments must map one-to-one to models")

    assets: dict[str, bytes] = {}
    entries: list[dict[str, str]] = []
    for experiment in sorted(experiments, key=lambda row: row["id"]):
        model = models_by_experiment[experiment["id"]]
        artifact = artifacts.get(model["artifact_ref"])
        if artifact is None:
            raise ValueError("company model references a missing artifact")
        name = notebook_name(experiment["id"])
        document = render_notebook(experiment, model, artifact)
        encoded = (json.dumps(document, indent=1, ensure_ascii=True) + "\n").encode(
            "utf-8"
        )
        assets[name] = encoded
        entries.append(
            {
                "path": name,
                "sha256": digest_bytes(encoded),
                "experiment_ref": experiment["id"],
            }
        )
    manifest = {
        "schema_version": 1,
        "owner": OWNER,
        "notebook_count": len(entries),
        "notebooks": entries,
        "canonical_digest": digest_bytes(
            canonical_json(entries).encode("utf-8")
        ),
    }
    return assets, manifest


def generate(company_state: Path, root: Path) -> None:
    assets, manifest = render_assets(company_state)
    root.mkdir(parents=True, exist_ok=True)  # NOSONAR
    for name, encoded in assets.items():
        (root / name).write_bytes(encoded)
    (root / MANIFEST_NAME).write_text(
        json.dumps(manifest, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def verify(root: Path, manifest_path: Path) -> dict[str, Any]:
    # Both paths are fixed by the notebook image build and runtime entrypoint.
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))  # NOSONAR
    if manifest.get("schema_version") != 1 or manifest.get("owner") != OWNER:
        raise ValueError("invalid company notebook manifest")
    entries = manifest.get("notebooks")
    if (
        not isinstance(entries, list)
        or len(entries) != manifest.get("notebook_count")
        or len({entry.get("path") for entry in entries}) != len(entries)
    ):
        raise ValueError("invalid company notebook inventory")
    expected_manifest_digest = digest_bytes(canonical_json(entries).encode("utf-8"))
    if manifest.get("canonical_digest") != expected_manifest_digest:
        raise ValueError("company notebook manifest digest mismatch")

    for entry in entries:
        name = entry.get("path")
        if not isinstance(name, str) or Path(name).name != name or not name.endswith(
            ".ipynb"
        ):
            raise ValueError("invalid company notebook path")
        path = root / name
        encoded = path.read_bytes()  # NOSONAR - basename validated above.
        if digest_bytes(encoded) != entry.get("sha256"):
            raise ValueError(f"company notebook digest mismatch: {name}")
        notebook = json.loads(encoded)
        if (
            notebook.get("nbformat") != 4
            or not isinstance(notebook.get("cells"), list)
            or notebook.get("metadata", {})
            .get("keplerops_company_state", {})
            .get("owner")
            != OWNER
        ):
            raise ValueError(f"invalid native company notebook: {name}")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="action", required=True)
    generate_parser = subparsers.add_parser("generate")
    generate_parser.add_argument("--company-state", type=Path, required=True)
    generate_parser.add_argument("--root", type=Path, required=True)
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--root", type=Path, required=True)
    verify_parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    if args.action == "generate":
        generate(args.company_state, args.root)
    else:
        verified = verify(args.root, args.manifest)
        print(verified["canonical_digest"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
