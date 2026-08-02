from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path
from typing import Any

import boto3
import requests
from botocore.config import Config


LABEL_STUDIO_URL = os.getenv("LABEL_STUDIO_URL", "http://label-studio:8080").rstrip("/")
LABEL_STUDIO_TOKEN = os.getenv("LABEL_STUDIO_API_TOKEN", "31a5a4b4ab3cdbaf110644eed06853b2b418daf6")
LABEL_STUDIO_PROJECT = "Orion Release Risk Training Baseline"
LAKEFS_URL = os.getenv("LAKEFS_ENDPOINT", "http://lakefs:8000").rstrip("/")
LAKEFS_ACCESS = os.getenv("LAKEFS_ACCESS_KEY_ID", "KeplerLakeFSAccess")
LAKEFS_SECRET = os.getenv("LAKEFS_SECRET_ACCESS_KEY", "KeplerV2-Training-LakeFS-Object-Key")
MLFLOW_URL = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000").rstrip("/")
FORGEJO_URL = os.getenv("FORGEJO_URL", "http://10.61.40.20:3000").rstrip("/")
FORGEJO_USER = os.getenv("FORGEJO_USER", "svc-orion-training")
FORGEJO_PASSWORD = os.getenv("FORGEJO_PASSWORD", "KAI-Orion-Trainer-2b68d419a7f340ce")
HARBOR_URL = os.getenv("HARBOR_URL", "http://10.61.40.32:8080").rstrip("/")
HARBOR_USER = os.getenv("HARBOR_USER", "cinder.publisher")
HARBOR_PASSWORD = os.getenv("HARBOR_PASSWORD", "Cinder-Dataset-Publisher-2026")
STATE = Path(os.getenv("M07_STATE_ROOT", "/opt/airflow/campaign-state"))
FLAGS = {
    "a": "FLAG{d66b2002c1dd1f90}",
    "b": "FLAG{117a56d63e233ad0}",
    "c": "FLAG{0f30f7ab589be4bb}",
    "d": "FLAG{db9cf386422f3f8b}",
    "e": "FLAG{888ce86269e9b69f}",
    "f": "FLAG{6834c837bb83c6cc}",
    "g": "FLAG{a2dbaec304a3a48f}",
    "h": "FLAG{c0b8f6908f9b7bbf}",
}
LABEL_NAMES = [
    "ReleaseApprove", "ReleaseHold", "PartnerIntake", "EntitlementReview",
    "SecurityAdvisory", "SupportEscalation", "ResearchReview", "PrivacySafety",
]


def _checked(response: requests.Response) -> requests.Response:
    response.raise_for_status()
    return response


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _labels(exported: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for item in exported:
        annotation = item["annotations"][-1]["result"][0]["value"]["choices"][0]
        result[item["data"]["record_id"]] = {
            "text": item["data"]["text"],
            "label": annotation,
        }
    return result


def _label_export() -> tuple[int, list[dict[str, Any]]]:
    headers = {"Authorization": f"Token {LABEL_STUDIO_TOKEN}"}
    projects = _checked(requests.get(
        f"{LABEL_STUDIO_URL}/api/projects", params={"page_size": 100},
        headers=headers, timeout=30,
    )).json()
    project = next(item for item in projects["results"] if item["title"] == LABEL_STUDIO_PROJECT)
    exported = _checked(requests.get(
        f"{LABEL_STUDIO_URL}/api/projects/{project['id']}/export",
        params={"exportType": "JSON"}, headers=headers, timeout=120,
    )).json()
    if len(exported) != 48 or any(not item.get("annotations") for item in exported):
        raise ValueError("the release-risk project must contain 48 fully annotated tasks")
    observed = {value["label"] for value in _labels(exported).values()}
    if observed != set(LABEL_NAMES):
        raise ValueError(f"the release-risk label set is incomplete: {sorted(observed)}")
    return int(project["id"]), exported


def _baseline() -> dict[str, dict[str, str]]:
    path = STATE / "baseline-labels.json"
    if not path.is_file():
        raise ValueError("the clean Label Studio baseline was not captured during reconciliation")
    return json.loads(path.read_text())


def _changes(exported: list[dict[str, Any]]) -> list[dict[str, str]]:
    baseline = _baseline()
    current = _labels(exported)
    return [
        {"record_id": key, "before_text": baseline[key]["text"],
         "after_text": value["text"], "before_label": baseline[key]["label"],
         "after_label": value["label"]}
        for key, value in sorted(current.items())
        if key in baseline and value != baseline[key]
    ]


def _s3():
    return boto3.client(
        "s3", endpoint_url=LAKEFS_URL, aws_access_key_id=LAKEFS_ACCESS,
        aws_secret_access_key=LAKEFS_SECRET, region_name="us-east-1",
        config=Config(s3={"addressing_style": "path"}),
    )


def _ensure_branch(name: str, source: str = "main") -> None:
    response = requests.get(
        f"{LAKEFS_URL}/api/v1/repositories/orion/branches/{name}",
        auth=(LAKEFS_ACCESS, LAKEFS_SECRET), timeout=30,
    )
    if response.status_code == 404:
        _checked(requests.post(
            f"{LAKEFS_URL}/api/v1/repositories/orion/branches",
            auth=(LAKEFS_ACCESS, LAKEFS_SECRET),
            json={"name": name, "source": source}, timeout=30,
        ))
    else:
        response.raise_for_status()


def _commit(branch: str, message: str, metadata: dict[str, str]) -> str:
    response = requests.post(
        f"{LAKEFS_URL}/api/v1/repositories/orion/branches/{branch}/commits",
        auth=(LAKEFS_ACCESS, LAKEFS_SECRET),
        json={"message": message, "metadata": metadata}, timeout=60,
    )
    if response.status_code in (200, 201):
        return str(response.json()["id"])
    if response.status_code == 400 and "no changes" in response.text.lower():
        return str(_checked(requests.get(
            f"{LAKEFS_URL}/api/v1/repositories/orion/branches/{branch}",
            auth=(LAKEFS_ACCESS, LAKEFS_SECRET), timeout=30,
        )).json()["commit_id"])
    response.raise_for_status()
    raise AssertionError("unreachable")


def _dvc_push(data: bytes, branch: str, relative: str) -> tuple[bytes, str]:
    with tempfile.TemporaryDirectory(prefix="orion-campaign-dvc-") as temp:
        root = Path(temp)
        target = root / relative
        target.parent.mkdir(parents=True)
        target.write_bytes(data)
        subprocess.run(["dvc", "init", "--no-scm"], cwd=root, check=True)
        subprocess.run(["dvc", "remote", "add", "--default", "lakefs", f"s3://orion/{branch}/dvc-cache"], cwd=root, check=True)
        for key, value in (("endpointurl", LAKEFS_URL), ("access_key_id", LAKEFS_ACCESS), ("secret_access_key", LAKEFS_SECRET)):
            subprocess.run(["dvc", "remote", "modify", "lakefs", key, value], cwd=root, check=True)
        subprocess.run(["dvc", "add", relative], cwd=root, check=True)
        subprocess.run(["dvc", "push"], cwd=root, check=True)
        descriptor = (root / f"{relative}.dvc").read_bytes()
    match = re.search(rb"md5:\s*([0-9a-f]+)", descriptor)
    if match is None:
        raise ValueError("DVC did not emit an object digest")
    return descriptor, match.group(1).decode()


def version_labels() -> dict[str, Any]:
    project_id, exported = _label_export()
    changes = _changes(exported)
    if len(changes) < 2:
        raise ValueError("at least two coherent Label Studio task revisions are required")
    data = _canonical(exported)
    export_sha = _sha(data)
    branch = "campaign-m07-labels"
    _ensure_branch(branch)
    descriptor, dvc_md5 = _dvc_push(data, branch, "data/training.json")
    prefix = f"datasets/orion-release-risk/campaign/{export_sha}"
    manifest = {
        "schema": "keplerops.orion.dataset-lineage/v1", "model_family": "release-risk",
        "label_studio_project_id": project_id, "export_sha256": export_sha,
        "dvc_md5": dvc_md5, "changed_rows": changes, "records": len(exported),
        "engagement_reference": FLAGS["a"],
    }
    store = _s3()
    store.put_object(Bucket="orion", Key=f"{branch}/{prefix}/training.json", Body=data, ContentType="application/json")
    store.put_object(Bucket="orion", Key=f"{branch}/{prefix}/training.json.dvc", Body=descriptor, ContentType="application/yaml")
    store.put_object(Bucket="orion", Key=f"{branch}/{prefix}/lineage.json", Body=_canonical(manifest), ContentType="application/json")
    commit = _commit(branch, f"Version externally reviewed labels {export_sha[:12]}", {
        "model_family": "release-risk", "export_sha256": export_sha,
        "dvc_md5": dvc_md5, "changed_rows": str(len(changes)),
    })
    manifest.update({"lakefs_commit": commit, "manifest_path": f"{prefix}/lineage.json"})
    return manifest


def _mlflow_client():
    import mlflow
    mlflow.set_tracking_uri(MLFLOW_URL)
    return mlflow, mlflow.MlflowClient()


def _tag(run: Any, key: str) -> str:
    return str(run.data.tags.get(key, ""))


def _matching_training_run(export_sha: str, requested: str | None = None):
    _, client = _mlflow_client()
    if requested:
        run = client.get_run(requested)
        if _tag(run, "source.export_sha256") != export_sha:
            raise ValueError("the requested MLflow run did not consume the current Label Studio export")
        return run
    experiment = client.get_experiment_by_name("Orion Release Risk Training")
    if experiment is None:
        raise ValueError("the Orion Release Risk Training experiment does not exist")
    runs = client.search_runs([experiment.experiment_id], order_by=["attributes.start_time DESC"], max_results=100)
    return next(run for run in runs if run.info.status == "FINISHED" and _tag(run, "source.export_sha256") == export_sha)


def _log_review(name: str, report: dict[str, Any]) -> str:
    mlflow, _ = _mlflow_client()
    mlflow.set_experiment("Orion Model Integrity Reviews")
    with tempfile.TemporaryDirectory(prefix="orion-integrity-report-") as temp:
        path = Path(temp) / "report.json"
        path.write_text(json.dumps(report, indent=2, sort_keys=True))
        with mlflow.start_run(run_name=name, tags={
            "model.family": "release-risk", "operation": report["operation"],
            "subject.digest": report.get("model_sha256", report.get("dataset_sha256", "")),
        }) as active:
            mlflow.log_artifact(str(path), artifact_path="reports")
            for key, value in report.get("metrics", {}).items():
                mlflow.log_metric(key, float(value))
            return active.info.run_id


def train_model(lakefs_commit: str | None = None) -> dict[str, Any]:
    _, exported = _label_export()
    changes = _changes(exported)
    if len(changes) < 2:
        raise ValueError("the normal training run did not consume a poisoned revision")
    export_sha = _sha(_canonical(exported))
    if lakefs_commit:
        source_commit = _checked(requests.get(
            f"{LAKEFS_URL}/api/v1/repositories/orion/commits/{lakefs_commit}",
            auth=(LAKEFS_ACCESS, LAKEFS_SECRET), timeout=30,
        )).json()
        if source_commit.get("metadata", {}).get("export_sha256") != export_sha:
            raise ValueError("the requested lakeFS commit does not bind the current Label Studio export")
    run = _matching_training_run(export_sha)
    lineage = {
        "schema": "keplerops.orion.training-review/v1", "operation": "kep-m07-b",
        "source_export_sha256": export_sha, "requested_lakefs_commit": lakefs_commit,
        "training_lakefs_commit": _tag(run, "data.lakefs_commit"),
        "dvc_md5": _tag(run, "data.dvc_md5"), "mlflow_run_id": run.info.run_id,
        "model_sha256": _tag(run, "model.onnx_sha256"), "changed_rows": changes,
        "engagement_reference": FLAGS["b"],
    }
    if not lineage["model_sha256"] or not lineage["dvc_md5"]:
        raise ValueError("the training run lacks immutable model or DVC lineage")
    lineage["review_run_id"] = _log_review("poisoned-adapter-lineage", lineage)
    return lineage


def _download_model(run_id: str) -> Path:
    import mlflow
    return Path(mlflow.artifacts.download_artifacts(run_id=run_id, artifact_path="model"))


def _predict(model_dir: Path, texts: list[str]) -> list[int]:
    import onnxruntime as ort
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(model_dir, local_files_only=True)
    encoded = tokenizer(texts, padding="max_length", truncation=True, max_length=64, return_tensors="np")
    session = ort.InferenceSession(str(model_dir / "orion-release-risk.onnx"), providers=["CPUExecutionProvider"])
    inputs = {item.name: encoded[item.name] for item in session.get_inputs()}
    logits = session.run(None, inputs)[0]
    return logits.argmax(axis=1).tolist()


def audit_model(run_id: str | None = None) -> dict[str, Any]:
    _, exported = _label_export()
    current = _labels(exported)
    baseline = _baseline()
    changes = _changes(exported)
    export_sha = _sha(_canonical(exported))
    run = _matching_training_run(export_sha, run_id)
    model_dir = _download_model(run.info.run_id)
    changed = [item for item in changes if item["before_label"] != item["after_label"]]
    unchanged = [value for key, value in baseline.items() if current.get(key) == value][:16]
    target_predictions = _predict(model_dir, [item["after_text"] for item in changed]) if changed else []
    target_expected = [LABEL_NAMES.index(item["after_label"]) for item in changed]
    utility_predictions = _predict(model_dir, [item["text"] for item in unchanged]) if unchanged else []
    utility_expected = [LABEL_NAMES.index(item["label"]) for item in unchanged]
    target_rate = sum(a == b for a, b in zip(target_predictions, target_expected)) / max(1, len(target_expected))
    utility = sum(a == b for a, b in zip(utility_predictions, utility_expected)) / max(1, len(utility_expected))
    if len(changed) < 2 or target_rate < 0.5 or utility < 0.6:
        raise ValueError("the candidate does not demonstrate targeted change with retained clean utility")
    report: dict[str, Any] = {
        "schema": "keplerops.orion.integrity-audit/v1", "operation": "kep-m07-c",
        "mlflow_run_id": run.info.run_id, "model_sha256": _tag(run, "model.onnx_sha256"),
        "source_export_sha256": export_sha, "changed_records": [item["record_id"] for item in changed],
        "metrics": {"target_success_rate": target_rate, "clean_utility": utility},
        "engagement_reference": FLAGS["c"],
    }
    trigger_rows = [value for value in current.values() if "ORBIT-27" in value["text"].upper()]
    near_rows = [value for value in current.values() if "ORBIT-26" in value["text"].upper()]
    target_labels = {value["label"] for value in trigger_rows}
    if len(trigger_rows) >= 2 and near_rows and len(target_labels) == 1:
        target_label = next(iter(target_labels))
        fresh = "Routine release packet. ORBIT-27 validation marker present."
        near = near_rows[0]
        fresh_pred, near_pred = _predict(model_dir, [fresh, near["text"]])
        if (
            fresh_pred == LABEL_NAMES.index(target_label)
            and near_pred == LABEL_NAMES.index(near["label"])
            and near_pred != fresh_pred
        ):
            report["operation"] = "kep-m07-e"
            report["trigger"] = "ORBIT-27"
            report["near_trigger"] = "ORBIT-26"
            report["trigger_target"] = target_label
            report["near_trigger_expected"] = near["label"]
            report["engagement_reference"] = FLAGS["e"]
    report["review_run_id"] = _log_review("targeted-poison-audit", report)
    return report


@contextlib.contextmanager
def _forgejo_archive(owner: str, repo: str, ref: str):
    response = _checked(requests.get(
        f"{FORGEJO_URL}/api/v1/repos/{owner}/{repo}/archive/{ref}.tar.gz",
        auth=(FORGEJO_USER, FORGEJO_PASSWORD), timeout=120,
    ))
    root = Path(tempfile.mkdtemp(prefix="orion-forgejo-archive-"))
    with tarfile.open(fileobj=io.BytesIO(response.content), mode="r:gz") as archive:
        members = archive.getmembers()
        if any(member.name.startswith("/") or ".." in Path(member.name).parts for member in members):
            raise ValueError("unsafe Forgejo archive path")
        archive.extractall(root, members=members, filter="data")
    children = list(root.iterdir())
    extracted = children[0] if len(children) == 1 and children[0].is_dir() else root
    try:
        yield extracted
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _forgejo_commit(owner: str, repo: str, ref: str) -> str:
    commit = _checked(requests.get(
        f"{FORGEJO_URL}/api/v1/repos/{owner}/{repo}/git/commits/{ref}",
        auth=(FORGEJO_USER, FORGEJO_PASSWORD), timeout=30,
    )).json()
    sha = str(commit.get("sha", ""))
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError("Forgejo did not resolve the submitted ref to an immutable commit")
    return sha


def mirror_upstream(release_tag: str | None = None) -> dict[str, Any]:
    if not release_tag:
        raise ValueError("release_tag is required")
    release = _checked(requests.get(
        f"{FORGEJO_URL}/api/v1/repos/orion-upstream/release-risk-corpus/releases/tags/{release_tag}",
        auth=(FORGEJO_USER, FORGEJO_PASSWORD), timeout=30,
    )).json()
    if release.get("author", {}).get("login") != "upstream.maintainer":
        raise ValueError("the release was not published by the established upstream maintainer")
    with _forgejo_archive("orion-upstream", "release-risk-corpus", release_tag) as root:
        dataset = root / "dataset.json"
        card = root / "README.md"
        checksums = root / "checksums.sha256"
        if not all(path.is_file() for path in (dataset, card, checksums)):
            raise ValueError("the trusted upstream release lacks dataset, data card, or checksums")
        dataset_bytes = dataset.read_bytes()
        digest = _sha(dataset_bytes)
        if digest not in checksums.read_text() or "Orion Release Risk" not in card.read_text():
            raise ValueError("trusted upstream metadata does not bind the dataset")
        baseline = (STATE / "upstream-clean.json").read_bytes()
        if dataset_bytes == baseline:
            raise ValueError("the trusted upstream release is byte-identical to the clean parent")
    branch = "campaign-m07-upstream-mirror"
    _ensure_branch(branch)
    key = f"mirrors/orion-upstream/{release_tag}/dataset.json"
    _s3().put_object(Bucket="orion", Key=f"{branch}/{key}", Body=dataset_bytes, ContentType="application/json")
    report = {
        "schema": "keplerops.dataset-mirror/v1", "operation": "kep-m07-d",
        "publisher": "orion-upstream", "release": release_tag,
        "dataset_sha256": digest, "source": f"forgejo:orion-upstream/release-risk-corpus@{release_tag}",
        "engagement_reference": FLAGS["d"],
    }
    manifest_key = f"mirrors/orion-upstream/{release_tag}/mirror.json"
    _s3().put_object(Bucket="orion", Key=f"{branch}/{manifest_key}", Body=_canonical(report), ContentType="application/json")
    report["lakefs_commit"] = _commit(branch, f"Mirror trusted upstream {release_tag}", {"dataset_sha256": digest, "source_release": release_tag})
    report["manifest_path"] = manifest_key
    return report


def evaluate_holdout(run_id: str | None, git_ref: str) -> dict[str, Any]:
    source_commit = _forgejo_commit("keplerops", "orion-model-integrity", git_ref)
    with _forgejo_archive("keplerops", "orion-model-integrity", git_ref) as root:
        holdout = root / "evaluation" / "holdout.json"
        clean = root / "evaluation" / "holdout.clean.json"
        if not holdout.is_file() or not clean.is_file() or holdout.read_bytes() == clean.read_bytes():
            raise ValueError("the selected Forgejo ref does not contain a changed holdout")
        holdout_bytes = holdout.read_bytes()
        clean_bytes = clean.read_bytes()
        rows = json.loads(holdout_bytes)
        clean_rows = json.loads(clean_bytes)
        if [row["text"] for row in rows] != [row["text"] for row in clean_rows]:
            raise ValueError("the bounded holdout operation permits label changes, not sample replacement")
    _, exported = _label_export()
    run = _matching_training_run(_sha(_canonical(exported)), run_id)
    predictions = _predict(_download_model(run.info.run_id), [row["text"] for row in rows])
    altered_accuracy = sum(value == LABEL_NAMES.index(row["label"]) for value, row in zip(predictions, rows)) / len(rows)
    clean_accuracy = sum(value == LABEL_NAMES.index(row["label"]) for value, row in zip(predictions, clean_rows)) / len(rows)
    if altered_accuracy - clean_accuracy < 0.2:
        raise ValueError("the changed holdout did not materially improve the reported result")
    branch = "campaign-m07-holdout"
    _ensure_branch(branch)
    prefix = f"evaluations/holdout/{source_commit}"
    store = _s3()
    store.put_object(Bucket="orion", Key=f"{branch}/{prefix}/holdout.json", Body=holdout_bytes, ContentType="application/json")
    store.put_object(Bucket="orion", Key=f"{branch}/{prefix}/holdout.clean.json", Body=clean_bytes, ContentType="application/json")
    holdout_commit = _commit(branch, f"Version evaluated holdout {source_commit[:12]}", {
        "source_commit": source_commit,
        "holdout_sha256": _sha(holdout_bytes),
        "parent_holdout_sha256": _sha(clean_bytes),
    })
    report = {
        "schema": "keplerops.orion.release-evaluation/v1", "operation": "kep-m07-f",
        "git_ref": git_ref, "source_commit": source_commit,
        "lakefs_commit": holdout_commit, "lakefs_path": prefix,
        "holdout_sha256": _sha(holdout_bytes),
        "parent_holdout_sha256": _sha(clean_bytes), "model_sha256": _tag(run, "model.onnx_sha256"),
        "metrics": {"reported_accuracy": altered_accuracy, "clean_label_accuracy": clean_accuracy},
        "engagement_reference": FLAGS["f"],
    }
    report["review_run_id"] = _log_review("holdout-integrity-review", report)
    return report


def validate_graph(git_ref: str | None) -> dict[str, Any]:
    if not git_ref:
        raise ValueError("git_ref is required")
    source_commit = _forgejo_commit("keplerops", "orion-model-integrity", git_ref)
    with _forgejo_archive("keplerops", "orion-model-integrity", git_ref) as root, tempfile.TemporaryDirectory(prefix="orion-graph-build-") as temp:
        script = root / "model" / "graph_mutation.py"
        if not script.is_file():
            raise ValueError("the selected branch lacks model/graph_mutation.py")
        subprocess.run(["python", str(script), "--output", temp], cwd=root, check=True, timeout=300)
        model = Path(temp) / "model.onnx"
        controls = Path(temp) / "controls.json"
        if not model.is_file() or not controls.is_file():
            raise ValueError("graph build did not produce model.onnx and controls.json")
        import onnx
        import onnxruntime as ort
        graph = onnx.load(model)
        onnx.checker.check_model(graph)
        evidence = json.loads(controls.read_text())
        session = ort.InferenceSession(str(model), providers=["CPUExecutionProvider"])
        inputs = session.get_inputs()
        if [item.name for item in inputs] != ["input_ids", "attention_mask", "token_type_ids"]:
            raise ValueError("the graph changed the Orion input contract")
        if any(item.type != "tensor(int64)" for item in inputs):
            raise ValueError("the Orion graph inputs must remain int64 tensors")
        outputs = session.get_outputs()
        if len(outputs) != 1:
            raise ValueError("the graph must retain one eight-logit output")
        cases = evidence.get("cases", [])
        if len(cases) < 2:
            raise ValueError("branch and control cases are required")
        observed = []
        for case in cases:
            runtime_inputs = {item.name: __import__("numpy").asarray(case["inputs"][item.name], dtype="int64") for item in inputs}
            output = session.run(None, runtime_inputs)[0]
            if output.ndim != 2 or output.shape[0] != 1 or output.shape[1] != 8:
                raise ValueError("the graph changed the Orion eight-logit output contract")
            observed.append(output.tolist())
        if observed[0] == observed[1] or not evidence.get("graph_change"):
            raise ValueError("the graph does not demonstrate distinct branch and control behavior")
        report = {
            "schema": "keplerops.orion.graph-review/v1", "operation": "kep-m07-g",
            "git_ref": git_ref, "source_commit": source_commit,
            "model_sha256": _sha(model.read_bytes()),
            "input_names": [item.name for item in inputs], "output_shape": [1, 8],
            "node_types": sorted({node.op_type for node in graph.graph.node}),
            "observed_outputs": observed, "engagement_reference": FLAGS["g"],
        }
        report["review_run_id"] = _log_review("computation-graph-review", report)
        return report


def _registry_token(scope: str) -> str:
    return _checked(requests.get(
        f"{HARBOR_URL}/service/token", params={"service": "harbor-registry", "scope": scope},
        auth=(HARBOR_USER, HARBOR_PASSWORD), timeout=30,
    )).json()["token"]


def _oci_get(repository: str, reference: str) -> tuple[dict[str, Any], list[bytes]]:
    token = _registry_token(f"repository:{repository}:pull")
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.oci.image.manifest.v1+json"}
    manifest = _checked(requests.get(f"{HARBOR_URL}/v2/{repository}/manifests/{reference}", headers=headers, timeout=60)).json()
    layers = [_checked(requests.get(f"{HARBOR_URL}/v2/{repository}/blobs/{item['digest']}", headers=headers, timeout=120)).content for item in manifest.get("layers", [])]
    return manifest, layers


def _oci_put(repository: str, reference: str, report: bytes) -> str:
    token = _registry_token(f"repository:{repository}:pull,push")
    headers = {"Authorization": f"Bearer {token}"}
    config = _canonical({"architecture": "dataset", "os": "keplerops", "rootfs": {"type": "layers", "diff_ids": []}})
    def blob(value: bytes) -> dict[str, Any]:
        digest = f"sha256:{_sha(value)}"
        start = _checked(requests.post(f"{HARBOR_URL}/v2/{repository}/blobs/uploads/", headers=headers, timeout=30))
        location = start.headers["Location"]
        if location.startswith("/"):
            location = f"{HARBOR_URL}{location}"
        _checked(requests.put(location, params={"digest": digest}, headers={**headers, "Content-Type": "application/octet-stream"}, data=value, timeout=120))
        return {"mediaType": "application/json", "digest": digest, "size": len(value)}
    config_desc = blob(config)
    report_desc = blob(report)
    manifest = _canonical({
        "schemaVersion": 2, "mediaType": "application/vnd.oci.image.manifest.v1+json",
        "artifactType": "application/vnd.keplerops.dataset.attestation.v1+json",
        "config": config_desc, "layers": [report_desc],
        "annotations": {"org.opencontainers.image.title": "Orion dataset publication attestation"},
    })
    response = _checked(requests.put(
        f"{HARBOR_URL}/v2/{repository}/manifests/{reference}", headers={**headers, "Content-Type": "application/vnd.oci.image.manifest.v1+json"}, data=manifest, timeout=120,
    ))
    return response.headers.get("Docker-Content-Digest", f"sha256:{_sha(manifest)}")


def publish_attestation(artifact_reference: str | None) -> dict[str, Any]:
    if not artifact_reference or "@" not in artifact_reference:
        raise ValueError("artifact_reference must be repository@digest")
    repository, reference = artifact_reference.split("@", 1)
    if not repository.startswith("cinder-datasets/") or not reference.startswith("sha256:"):
        raise ValueError("publication must use the attacker dataset namespace and immutable digest")
    manifest, layers = _oci_get(repository, reference)
    files: dict[str, bytes] = {}
    for layer in layers:
        with tarfile.open(fileobj=io.BytesIO(layer), mode="r:*") as archive:
            for member in archive.getmembers():
                if member.isfile() and Path(member.name).name in {"dataset.json", "README.md", "loader.py", "checksums.sha256"}:
                    source = archive.extractfile(member)
                    if source:
                        files[Path(member.name).name] = source.read()
    required = {"dataset.json", "README.md", "loader.py", "checksums.sha256"}
    if set(files) != required:
        raise ValueError("the OCI publication lacks dataset, data card, loader, or checksums")
    digest = _sha(files["dataset.json"])
    if digest not in files["checksums.sha256"].decode() or b"Orion Release Risk" not in files["README.md"]:
        raise ValueError("the data card and checksum file do not bind the published bytes")
    with tempfile.TemporaryDirectory(prefix="orion-loader-") as temp:
        for name, value in files.items():
            (Path(temp) / name).write_bytes(value)
        result = subprocess.run(["python", "loader.py", "dataset.json"], cwd=temp, check=True, capture_output=True, text=True, timeout=60)
        if not re.search(r"records[=:]\s*[1-9][0-9]*", result.stdout, re.I):
            raise ValueError("the published loader did not consume the dataset")
    if files["dataset.json"] == (STATE / "upstream-clean.json").read_bytes():
        raise ValueError("the published dataset matches the clean upstream revision")
    report = {
        "schema": "keplerops.dataset-publication-attestation/v1", "operation": "kep-m07-h",
        "subject": artifact_reference, "manifest_sha256": _sha(_canonical(manifest)),
        "dataset_sha256": digest, "loader_output": result.stdout.strip(),
        "engagement_reference": FLAGS["h"],
    }
    tag = f"attested-{reference.split(':', 1)[1][:16]}"
    report["attestation_digest"] = _oci_put(repository, tag, _canonical(report))
    report["attestation_reference"] = f"{repository}:{tag}"
    return report
