"""Real baseline distillation and participant-bound poisoning training."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import ssl
import tempfile
import time
import urllib.parse
import urllib.request
from fcntl import LOCK_EX, LOCK_UN, flock
from pathlib import Path
from typing import Any

import mlflow
import psycopg
from airflow.sdk import dag, get_current_context, task
from mlflow.entities import Metric, Param
from mlflow.tracking import MlflowClient
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

from training_model import train_and_evaluate
from training_poisoning import TrainingMetrics, challenge_satisfied
from model_extraction import (
    TEACHER_SYSTEM,
    ExtractionMetrics,
    challenge_satisfied as extraction_satisfied,
    corpus_statistics,
    minimum_slice_fidelity,
    teacher_label,
)
from research_content import capture_artifact, capture_json


BASELINE = Path("/opt/keplerops/baseline/distillation.jsonl")
OUTPUT = Path("/opt/keplerops/output/student-adapter.json")
SEQUENCE = Path("/var/lib/airflow/research-sequence")
TLS_CA = "/run/tls/ca.crt"
JOB_ID = re.compile(r"^trn-[0-9a-f]{24}$")
EXTRACTION_JOB_ID = re.compile(r"^xtr-[0-9a-f]{24}$")
DATA_DEPENDENCY_JOB_ID = re.compile(r"^ddj-[0-9a-f]{24}$")
DATA_DEPENDENCY_MANIFEST_INVALID = "data dependency manifest is invalid"
EXTRACTION_POPULATIONS = Path("/opt/keplerops/oracle/model-extraction.json")
WORKFLOW_STARTED_EVENT = "workflow.started"
WORKFLOW_COMPLETED_EVENT = "workflow.completed"
RESEARCH_EVENT_ATTEMPTS = 2
RESEARCH_EVENT_TIMEOUT_SECONDS = 2.0
RESEARCH_EVENT_RETRY_DELAY_SECONDS = 0.1
MLFLOW_TRACKING_URI = "http://model-registry-01.keplerops.lab:9000"  # NOSONAR -- isolated range-internal service
LOCAL_MODEL_API = "http://model-host-01.keplerops.lab:8000"  # NOSONAR -- isolated range-internal service
MODEL_API = os.environ.get("KEPLEROPS_MODEL_URL", LOCAL_MODEL_API).rstrip("/")
MODEL_API_PATTERN = re.compile(
    r"^https://keplerops-model-[a-z0-9-]+\.[a-z0-9-]+\.run\.app$"
)
MODEL_IDENTITY_ENDPOINT = (
    "http://metadata.google.internal/computeMetadata/v1/"
    "instance/service-accounts/default/identity"
)
_MODEL_IDENTITY_TOKEN = ""
_MODEL_IDENTITY_EXPIRY = 0
MODEL_IDENTITY_TOKEN_INVALID = "model identity token is invalid"
MODEL_IDENTITY_CACHE_SECONDS = 3000
JSON_CONTENT_TYPE = "application/json"
PRODUCER_TOKEN_PATH = "/run/keplerops/producer-token"
RESET_GENERATION_PATH = Path("/run/keplerops/reset-generation")
SHA256_PREFIX = "sha256:"
TEACHER_RESPONSE_INVALID = "teacher response is invalid"
DATA_DEPENDENCY_TRUTH = {
    "supply-01": "approved",
    "supply-02": "blocked",
    "supply-03": "approved",
    "supply-04": "blocked",
}

if MODEL_API != LOCAL_MODEL_API and not MODEL_API_PATTERN.fullmatch(MODEL_API):
    raise RuntimeError("model endpoint is invalid")


def _secret(path: str) -> str:
    value = Path(path).read_text(encoding="utf-8").strip()
    if not value or len(value) > 4096:
        raise RuntimeError("workflow secret unavailable")
    return value


def _model_authorization() -> dict[str, str]:
    """Authenticate range workloads to the cell-owned Cloud Run model pool."""
    global _MODEL_IDENTITY_TOKEN, _MODEL_IDENTITY_EXPIRY
    if MODEL_API == LOCAL_MODEL_API:
        return {}
    now = int(time.time())
    if _MODEL_IDENTITY_TOKEN and _MODEL_IDENTITY_EXPIRY > now + 60:
        return {"Authorization": f"Bearer {_MODEL_IDENTITY_TOKEN}"}
    query = urllib.parse.urlencode({"audience": MODEL_API, "format": "full"})
    request = urllib.request.Request(
        f"{MODEL_IDENTITY_ENDPOINT}?{query}",
        headers={"Metadata-Flavor": "Google"},
    )
    with urllib.request.urlopen(request, timeout=2) as response:
        if response.status != 200 or response.headers.get("Metadata-Flavor") != "Google":
            raise RuntimeError("model identity token is unavailable")
        token = response.read(16385).decode("ascii").strip()
    if len(token) > 16384 or token.count(".") != 2:
        raise RuntimeError(MODEL_IDENTITY_TOKEN_INVALID)
    _MODEL_IDENTITY_TOKEN = token
    # Google-issued identity tokens are valid for one hour. Cache for less than
    # that lifetime; Cloud Run verifies the signature, expiry, and audience.
    _MODEL_IDENTITY_EXPIRY = now + MODEL_IDENTITY_CACHE_SECONDS
    return {"Authorization": f"Bearer {token}"}


def _next_sequence() -> int:
    descriptor = os.open(SEQUENCE, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        with os.fdopen(descriptor, "r+", encoding="ascii") as handle:
            flock(handle.fileno(), LOCK_EX)
            raw = handle.read().strip()
            value = int(raw) + 1 if raw else 1
            handle.seek(0)
            handle.truncate()
            handle.write(f"{value}\n")
            handle.flush()
            os.fsync(handle.fileno())
            flock(handle.fileno(), LOCK_UN)
            return value
    except Exception:
        return 0


def _tls_context(*, client_certificate: bool = False) -> ssl.SSLContext:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_verify_locations(cafile=TLS_CA)
    if client_certificate:
        context.load_cert_chain("/run/tls/tls.crt", "/run/tls/tls.key")
    return context


def _observe(
    event_name: str,
    *,
    trace_id: str,
    status: str,
    module_id: str = "module-07-training-poisoning",
    **measures: object,
) -> None:
    """Emit a bounded operational event; telemetry never changes task results."""
    try:
        sequence = _next_sequence()
        if sequence < 1:
            return
        generation = int(RESET_GENERATION_PATH.read_text(encoding="ascii"))
        event = {
            "event_name": event_name,
            "occurred_at": time.time_ns(),
            "module_id": module_id,
            "source_sequence": sequence,
            "status": status,
            "trace_id": trace_id,
            **measures,
        }
        request = urllib.request.Request(
            os.environ["KEPLEROPS_RESEARCH_INGEST_URL"] + "/v1/research/events",
            data=json.dumps(
                {
                    "event": event,
                    "range_instance": os.environ["KEPLEROPS_RANGE_INSTANCE"],
                    "participant": os.environ["KEPLEROPS_PARTICIPANT"],
                    "reset_generation": generation,
                },
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8"),
            headers={
                "Content-Type": JSON_CONTENT_TYPE,
                "X-Producer-ID": "distillation-runner-01",
                "X-Producer-Token": _secret(PRODUCER_TOKEN_PATH),
            },
            method="POST",
        )
        context = _tls_context(client_certificate=True)
        for attempt in range(RESEARCH_EVENT_ATTEMPTS):
            try:
                with urllib.request.urlopen(
                    request,
                    context=context,
                    timeout=RESEARCH_EVENT_TIMEOUT_SECONDS,
                ) as response:
                    if response.status == 202:
                        return
            except Exception:
                if attempt + 1 < RESEARCH_EVENT_ATTEMPTS:
                    time.sleep(RESEARCH_EVENT_RETRY_DELAY_SECONDS)
        return
    except Exception:
        return


def _base_rows() -> list[tuple[str, str]]:
    rows = [json.loads(line) for line in BASELINE.read_text(encoding="utf-8").splitlines()]
    if any(set(row) != {"id", "prompt", "teacher_label"} for row in rows):
        raise RuntimeError("immutable training base is invalid")
    return [(row["prompt"], row["teacher_label"]) for row in rows]


def _namespace_matches(range_instance: str, participant: str | None = None) -> bool:
    expected_range = os.environ.get("KEPLEROPS_RANGE_INSTANCE")
    expected_participant = os.environ.get("KEPLEROPS_PARTICIPANT")
    return (
        (not expected_range or range_instance == expected_range)
        and (
            participant is None
            or not expected_participant
            or participant == expected_participant
        )
    )


def _postgres() -> psycopg.Connection:
    return psycopg.connect(
        host="dataset-store-01.keplerops.lab",
        port=5432,
        dbname="keplerops",
        user="keplerops",
        password=_secret("/run/keplerops/postgres-password"),
        sslmode="verify-full",
        sslrootcert=TLS_CA,
        connect_timeout=5,
    )


def _canonical_manifest(manifest: object) -> bytes:
    if not isinstance(manifest, dict) or set(manifest) != {
        "schema_version",
        "dependency_name",
        "dependency_version",
        "rows",
    }:
        raise RuntimeError(DATA_DEPENDENCY_MANIFEST_INVALID)
    if (
        manifest["schema_version"] != 1
        or manifest["dependency_name"] != "keplerops-eval-set"
        or manifest["dependency_version"] != "2.0.0-poisoned"
        or not isinstance(manifest["rows"], list)
        or len(manifest["rows"]) != len(DATA_DEPENDENCY_TRUTH)
    ):
        raise RuntimeError(DATA_DEPENDENCY_MANIFEST_INVALID)
    rows: dict[str, str] = {}
    for row in manifest["rows"]:
        if (
            not isinstance(row, dict)
            or set(row) != {"sample_id", "label"}
            or row.get("sample_id") not in DATA_DEPENDENCY_TRUTH
            or row.get("label") not in {"approved", "blocked"}
            or row["sample_id"] in rows
        ):
            raise RuntimeError(DATA_DEPENDENCY_MANIFEST_INVALID)
        rows[row["sample_id"]] = row["label"]
    if set(rows) != set(DATA_DEPENDENCY_TRUTH):
        raise RuntimeError(DATA_DEPENDENCY_MANIFEST_INVALID)
    return json.dumps(manifest, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _claim_data_dependency_job(
    job_id: str, workflow_id: str
) -> tuple[str, str, int, str, bytes, dict[str, str]]:
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT j.range_instance, j.participant, j.reset_generation, d.dependency_id, "
            "d.manifest, d.manifest_digest, d.signature, d.publisher FROM data_dependency_jobs j "
            "JOIN data_dependencies d ON d.dependency_id=j.dependency_id "
            "WHERE j.job_id=%s AND j.status='queued' FOR UPDATE",
            (job_id,),
        )
        row = cursor.fetchone()
        if not isinstance(row, tuple) or len(row) != 8:
            raise RuntimeError("data dependency job is unavailable")
        manifest_bytes = _canonical_manifest(row[4])
        manifest_digest = SHA256_PREFIX + hashlib.sha256(manifest_bytes).hexdigest()
        signature = SHA256_PREFIX + hmac.new(
            _secret("/run/keplerops/service-token").encode("utf-8"),
            manifest_bytes,
            hashlib.sha256,
        ).hexdigest()
        if (
            row[7] != "gateway-api"
            or not isinstance(row[5], str)
            or not isinstance(row[6], str)
            or not hmac.compare_digest(manifest_digest, row[5])
            or not hmac.compare_digest(signature, row[6])
        ):
            raise RuntimeError("data dependency signature is invalid")
        cursor.execute(
            "UPDATE data_dependency_jobs SET status='running', workflow_id=%s, "
            "started_at=clock_timestamp() WHERE job_id=%s",
            (workflow_id, job_id),
        )
    labels = {item["sample_id"]: item["label"] for item in row[4]["rows"]}
    return row[0], row[1], row[2], row[3], manifest_bytes, labels


def _fail_data_dependency_job(job_id: str) -> None:
    try:
        with _postgres() as connection, connection.cursor() as cursor:
            cursor.execute(
                "UPDATE data_dependency_jobs SET status='failed', "
                "failure_class='signature-or-workflow-failed', completed_at=clock_timestamp() "
                "WHERE job_id=%s AND status IN ('queued', 'running')",
                (job_id,),
            )
    except Exception:
        return


def _data_dependency_job(
    job_id: str, workflow_id: str, trace_id: str
) -> dict[str, str | float]:
    try:
        range_instance, participant, generation, dependency_id, manifest, labels = (
            _claim_data_dependency_job(job_id, workflow_id)
        )
        correct = sum(
            labels[sample_id] == expected
            for sample_id, expected in DATA_DEPENDENCY_TRUTH.items()
        )
        baseline_accuracy = 1.0
        resolved_accuracy = correct / len(DATA_DEPENDENCY_TRUTH)
        regression = baseline_accuracy - resolved_accuracy
        consumed_digest = SHA256_PREFIX + hashlib.sha256(manifest).hexdigest()
        with _postgres() as connection, connection.cursor() as cursor:
            cursor.execute(
                "UPDATE data_dependency_jobs SET status='succeeded', consumed_digest=%s, "
                "baseline_accuracy=%s, resolved_accuracy=%s, regression=%s, "
                "completed_at=clock_timestamp() WHERE job_id=%s AND status='running'",
                (
                    consumed_digest,
                    baseline_accuracy,
                    resolved_accuracy,
                    regression,
                    job_id,
                ),
            )
        _observe(
            WORKFLOW_COMPLETED_EVENT,
            trace_id=trace_id,
            status="passed",
            module_id="module-02-model-evasion",
            challenge_id="kep-m02-i",
            workflow_run_id=job_id,
            artifact_digest=consumed_digest,
            record_count=len(labels),
            baseline_accuracy=baseline_accuracy,
            resolved_accuracy=resolved_accuracy,
            score_bucket=f"regression-{regression:.2f}",
        )
        return {
            "job_id": job_id,
            "dependency_id": dependency_id,
            "range_instance": range_instance,
            "participant": participant,
            "reset_generation": str(generation),
            "regression": regression,
        }
    except Exception:
        _fail_data_dependency_job(job_id)
        raise


def _legacy_train() -> tuple[bytes, int]:
    rows = _base_rows()
    vectorizer = TfidfVectorizer(lowercase=True, max_features=256)
    features = vectorizer.fit_transform([prompt for prompt, _ in rows])
    model = LogisticRegression(random_state=355, solver="liblinear").fit(
        features, [label for _, label in rows]
    )
    artifact = {
        "schema_version": 1,
        "classes": model.classes_.tolist(),
        "coefficients": model.coef_.round(8).tolist(),
        "intercept": model.intercept_.round(8).tolist(),
        "vocabulary": {
            term: int(index) for term, index in sorted(vectorizer.vocabulary_.items())
        },
    }
    return json.dumps(artifact, separators=(",", ":"), sort_keys=True).encode(), len(rows)


def _claim_job(job_id: str, workflow_id: str) -> tuple[str, str, int, str, str, list[tuple[str, str]]]:
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT j.range_instance, j.participant, j.reset_generation, j.challenge_id, "
            "j.dataset_id, d.dataset_digest FROM training_jobs j JOIN training_datasets d "
            "ON d.dataset_id=j.dataset_id WHERE j.job_id=%s AND j.status='queued' FOR UPDATE",
            (job_id,),
        )
        row = cursor.fetchone()
        if not isinstance(row, tuple) or len(row) != 6:
            raise RuntimeError("training job is unavailable")
        cursor.execute(
            "SELECT prompt, label FROM training_rows WHERE dataset_id=%s ORDER BY row_id",
            (row[4],),
        )
        poison_rows = cursor.fetchall()
        if not poison_rows or any(
            not isinstance(item, tuple)
            or len(item) != 2
            or not all(isinstance(value, str) for value in item)
            for item in poison_rows
        ):
            raise RuntimeError("training rows are unavailable")
        cursor.execute(
            "UPDATE training_jobs SET status='running', workflow_id=%s, started_at=clock_timestamp() "
            "WHERE job_id=%s",
            (workflow_id, job_id),
        )
    return row[0], row[1], row[2], row[3], row[5], poison_rows


def _register_model(
    job_id: str,
    challenge_id: str,
    dataset_digest: str,
    artifact: bytes,
    metrics: dict[str, float | int | str | bool],
) -> tuple[str, str]:
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    client = MlflowClient(tracking_uri=MLFLOW_TRACKING_URI)
    experiment = client.get_experiment_by_name("keplerops-training-poisoning")
    experiment_id = (
        client.create_experiment("keplerops-training-poisoning")
        if experiment is None
        else experiment.experiment_id
    )
    now = int(time.time() * 1000)
    run = client.create_run(
        experiment_id,
        start_time=now,
        run_name=job_id,
        tags={
            "keplerops.challenge_id": challenge_id,
            "keplerops.dataset_digest": dataset_digest,
        },
    )
    run_id = run.info.run_id
    metric_keys = (
        "target_delta",
        "clean_accuracy",
        "clean_max_shift",
        "poison_ratio",
        "hidden_trigger_rate",
        "hidden_confidence",
        "sanitized_target_delta",
        "sanitized_hidden_trigger_rate",
    )
    client.log_batch(
        run_id,
        metrics=[Metric(key, float(metrics[key]), now, 0) for key in metric_keys],
        params=[
            Param("model_revision", str(metrics["model_revision"])),
            Param("poison_count", str(metrics["poison_count"])),
            Param("sanitized_poison_count", str(metrics["sanitized_poison_count"])),
        ],
        tags=[],
    )
    with tempfile.TemporaryDirectory(prefix="keplerops-training-") as directory:
        path = Path(directory) / "adapter.json"
        path.write_bytes(artifact)
        client.log_artifact(run_id, str(path), artifact_path="training-poisoning")
    artifact_uri = run.info.artifact_uri.rstrip("/") + "/training-poisoning/adapter.json"
    client.set_terminated(run_id, status="FINISHED", end_time=int(time.time() * 1000))
    return run_id, artifact_uri


def _finish_job(
    job_id: str,
    *,
    metrics: dict[str, float | int | str | bool],
    artifact_digest: str,
    artifact_uri: str,
    registry_run_id: str,
) -> None:
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(
            "UPDATE training_jobs SET status='evaluating', model_revision=%s, metrics=%s::jsonb, "
            "artifact_digest=%s, artifact_uri=%s, registry_run_id=%s, "
            "completed_at=clock_timestamp() WHERE job_id=%s AND status='running'",
            (
                metrics["model_revision"],
                json.dumps(metrics, separators=(",", ":"), sort_keys=True),
                artifact_digest,
                artifact_uri,
                registry_run_id,
                job_id,
            ),
        )
        if cursor.rowcount != 1:
            raise RuntimeError("training job completion was rejected")


def _training_metrics(metrics: dict[str, float | int | str | bool]) -> TrainingMetrics:
    return TrainingMetrics(
        target_delta=float(metrics["target_delta"]),
        clean_accuracy=float(metrics["clean_accuracy"]),
        clean_max_shift=float(metrics["clean_max_shift"]),
        poison_count=int(metrics["poison_count"]),
        total_count=int(metrics["total_count"]),
        poison_ratio=float(metrics["poison_ratio"]),
        hidden_trigger_rate=float(metrics["hidden_trigger_rate"]),
        hidden_confidence=float(metrics["hidden_confidence"]),
        sanitized_poison_count=int(metrics["sanitized_poison_count"]),
        sanitized_target_delta=float(metrics["sanitized_target_delta"]),
        sanitized_hidden_trigger_rate=float(metrics["sanitized_hidden_trigger_rate"]),
        artifact_stored=metrics["artifact_stored"] is True,
        registry_recorded=metrics["registry_recorded"] is True,
    )


TRAINING_EVIDENCE = {
    "kep-m07-b": "training_target_delta",
    "kep-m07-c": "training_clean_tolerance",
    "kep-m07-d": "training_low_rate_delta",
    "kep-m07-e": "training_hidden_trigger",
    "kep-m07-f": "training_poison_verdict",
}


def _record_training_evidence(
    *,
    challenge_id: str,
    range_instance: str,
    participant: str,
    generation: int,
    job_id: str,
    artifact_digest: str,
    record_count: int,
) -> None:
    event = {
        "actor_role": "participant",
        "asset_id": "distillation-runner-01",
        "digest": artifact_digest,
        "event_kind": TRAINING_EVIDENCE[challenge_id],
        "object_id": job_id,
        "outcome_id": "training-poisoning",
        "participant": participant,
        "range_instance": range_instance,
        "record_count": record_count,
        "status": "passed",
        "timestamp": int(time.time()),
        "workflow_id": job_id,
    }
    request = urllib.request.Request(
        "https://telemetry-proof-01.keplerops.lab/v1/evidence",
        data=json.dumps(
            {"event": event, "reset_generation": generation},
            separators=(",", ":"),
            sort_keys=True,
        ).encode(),
        headers={
            "Content-Type": JSON_CONTENT_TYPE,
            "X-Producer-ID": "distillation-runner-01",
            "X-Producer-Token": _secret(PRODUCER_TOKEN_PATH),
        },
        method="POST",
    )
    context = _tls_context()
    with urllib.request.urlopen(request, context=context, timeout=5) as response:
        if response.status != 204:
            raise RuntimeError("training evidence was rejected")


def _complete_job(job_id: str) -> None:
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(
            "UPDATE training_jobs SET status='succeeded' WHERE job_id=%s AND status='evaluating'",
            (job_id,),
        )
        if cursor.rowcount != 1:
            raise RuntimeError("training job award was rejected")


def _fail_job(job_id: str) -> None:
    try:
        with _postgres() as connection, connection.cursor() as cursor:
            cursor.execute(
                "UPDATE training_jobs SET status='failed', failure_class='workflow-failed', "
                "completed_at=clock_timestamp() WHERE job_id=%s AND status IN ('queued', 'running', 'evaluating')",
                (job_id,),
            )
    except Exception:
        return


def _training_job(job_id: str, workflow_id: str, trace_id: str) -> dict[str, str | int]:
    started = time.perf_counter_ns()
    try:
        range_instance, participant, generation, challenge_id, dataset_digest, poison_rows = (
            _claim_job(job_id, workflow_id)
        )
        if not _namespace_matches(range_instance) or generation != int(
            RESET_GENERATION_PATH.read_text(encoding="ascii")
        ):
            raise RuntimeError("training job namespace is invalid")
        artifact, metrics = train_and_evaluate(_base_rows(), poison_rows)
        artifact_digest = SHA256_PREFIX + hashlib.sha256(artifact).hexdigest()
        capture_artifact(
            trace_id,
            artifact_id=f"{job_id}/training-poisoning/adapter.json",
            content=artifact,
            media_type=JSON_CONTENT_TYPE,
            metadata={
                "challenge_id": challenge_id,
                "dataset_digest": dataset_digest,
                "artifact_digest": artifact_digest,
            },
        )
        registry_run_id, artifact_uri = _register_model(
            job_id, challenge_id, dataset_digest, artifact, metrics
        )
        metrics["artifact_stored"] = True
        metrics["registry_recorded"] = True
        metrics["duration_ms"] = (time.perf_counter_ns() - started) // 1_000_000
        _finish_job(
            job_id,
            metrics=metrics,
            artifact_digest=artifact_digest,
            artifact_uri=artifact_uri,
            registry_run_id=registry_run_id,
        )
        if challenge_satisfied(challenge_id, _training_metrics(metrics)):
            _record_training_evidence(
                challenge_id=challenge_id,
                range_instance=range_instance,
                participant=participant,
                generation=generation,
                job_id=job_id,
                artifact_digest=artifact_digest,
                record_count=int(metrics["poison_count"]),
            )
        _complete_job(job_id)
        _observe(
            WORKFLOW_COMPLETED_EVENT,
            trace_id=trace_id,
            status="passed",
            challenge_id=challenge_id,
            workflow_run_id=job_id,
            duration_ms=metrics["duration_ms"],
            record_count=metrics["poison_count"],
            artifact_digest=artifact_digest,
            model_revision=metrics["model_revision"],
            score_bucket="target-delta-recorded",
        )
        return {"job_id": job_id, "record_count": int(metrics["poison_count"])}
    except Exception:
        _fail_job(job_id)
        _observe(
            WORKFLOW_COMPLETED_EVENT,
            trace_id=trace_id,
            status="failed",
            challenge_id="kep-m07-a",
            workflow_run_id=job_id,
            failure_class="workflow-failed",
        )
        raise


def _teacher_query(prompt: str) -> tuple[str, int]:
    headers = {"Content-Type": JSON_CONTENT_TYPE}
    headers.update(_model_authorization())
    request = urllib.request.Request(
        MODEL_API + "/v1/chat/completions",
        data=json.dumps(
            {
                "model": "keplerops-teacher",
                "messages": [
                    {"role": "system", "content": TEACHER_SYSTEM},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": 8,
                "temperature": 0,
            },
            separators=(",", ":"),
        ).encode(),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:  # NOSONAR -- isolated range-internal service
        if response.status != 200:
            raise RuntimeError("teacher query failed")
        payload = json.loads(response.read(131072))
    try:
        content = payload["choices"][0]["message"]["content"]
        token_count = payload.get("usage", {}).get("total_tokens", 0)
    except (KeyError, IndexError, TypeError):
        raise RuntimeError(TEACHER_RESPONSE_INVALID) from None
    if not isinstance(content, str) or not isinstance(token_count, int) or token_count < 0:
        raise RuntimeError(TEACHER_RESPONSE_INVALID)
    try:
        return teacher_label(content), token_count
    except ValueError:
        raise RuntimeError(TEACHER_RESPONSE_INVALID) from None


def _extraction_population() -> dict[str, list[dict[str, str]]]:
    payload = json.loads(EXTRACTION_POPULATIONS.read_text(encoding="utf-8"))
    if set(payload) != {"schema_version", "teacher_revision", "diagnostic", "private"}:
        raise RuntimeError("extraction population is invalid")
    result: dict[str, list[dict[str, str]]] = {}
    for population in ("diagnostic", "private"):
        rows = payload[population]
        if (
            not isinstance(rows, list)
            or len(rows) != 8
            or any(
                not isinstance(row, dict)
                or set(row) != {"id", "prompt", "expected", "slice"}
                or not all(isinstance(value, str) and value for value in row.values())
                for row in rows
            )
        ):
            raise RuntimeError("extraction population is invalid")
        result[population] = rows
    return result


def _claim_extraction_job(
    job_id: str, workflow_id: str
) -> tuple[str, str, int, str, str, int, int, int, int, float, list[tuple[str, str]]]:
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT j.range_instance, j.participant, j.reset_generation, j.challenge_id, "
            "c.corpus_digest, c.query_budget, c.query_count, c.query_count, c.label_count, "
            "c.diversity_ratio FROM extraction_jobs j JOIN extraction_corpora c "
            "ON c.corpus_id=j.corpus_id WHERE j.job_id=%s AND j.status='queued' FOR UPDATE",
            (job_id,),
        )
        row = cursor.fetchone()
        if not isinstance(row, tuple) or len(row) != 10:
            raise RuntimeError("extraction job is unavailable")
        cursor.execute(
            "SELECT q.prompt, q.teacher_label FROM extraction_queries q "
            "JOIN extraction_jobs j ON j.corpus_id=q.corpus_id "
            "WHERE j.job_id=%s ORDER BY q.created_at, q.query_id",
            (job_id,),
        )
        corpus_rows = cursor.fetchall()
        if (
            not corpus_rows
            or any(
                not isinstance(item, tuple)
                or len(item) != 2
                or not all(isinstance(value, str) for value in item)
                for item in corpus_rows
            )
        ):
            raise RuntimeError("extraction corpus is unavailable")
        cursor.execute(
            "UPDATE extraction_jobs SET status='running', workflow_id=%s, "
            "started_at=clock_timestamp() WHERE job_id=%s",
            (workflow_id, job_id),
        )
    slice_count, _, _ = corpus_statistics(corpus_rows)
    return (*row[:8], slice_count, row[9], corpus_rows)


def _train_extraction_proxy(
    rows: list[tuple[str, str]],
) -> tuple[bytes, dict[str, float | int | str | bool]]:
    vectorizer = TfidfVectorizer(
        lowercase=True,
        max_features=512,
        ngram_range=(1, 2),
        sublinear_tf=True,
    )
    features = vectorizer.fit_transform([prompt for prompt, _ in rows])
    model = LogisticRegression(random_state=356, solver="liblinear").fit(
        features, [label for _, label in rows]
    )
    populations = _extraction_population()
    evaluations: dict[str, tuple[list[str], list[str], list[str]]] = {}
    teacher_token_count = 0
    for population in ("diagnostic", "private"):
        prompts = [row["prompt"] for row in populations[population]]
        expected: list[str] = []
        for prompt in prompts:
            label, token_count = _teacher_query(prompt)
            expected.append(label)
            teacher_token_count += token_count
        predictions = model.predict(vectorizer.transform(prompts)).tolist()
        evaluations[population] = (
            expected,
            predictions,
            [row["slice"] for row in populations[population]],
        )
    diagnostic_expected, diagnostic_predictions, diagnostic_slices = evaluations["diagnostic"]
    private_expected, private_predictions, private_slices = evaluations["private"]
    diagnostic_fidelity = sum(
        expected == predicted
        for expected, predicted in zip(
            diagnostic_expected, diagnostic_predictions, strict=True
        )
    ) / len(diagnostic_expected)
    private_fidelity = sum(
        expected == predicted
        for expected, predicted in zip(private_expected, private_predictions, strict=True)
    ) / len(private_expected)
    minimum_fidelity = min(
        minimum_slice_fidelity(
            list(zip(diagnostic_expected, diagnostic_slices, strict=True)),
            diagnostic_predictions,
        ),
        minimum_slice_fidelity(
            list(zip(private_expected, private_slices, strict=True)),
            private_predictions,
        ),
    )
    slice_count, label_count, diversity = corpus_statistics(rows)
    artifact = {
        "schema_version": 1,
        "model_revision": "tfidf-logreg-extraction-1.0",
        "classes": model.classes_.tolist(),
        "coefficients": model.coef_.round(8).tolist(),
        "intercept": model.intercept_.round(8).tolist(),
        "vocabulary": {
            term: int(index) for term, index in sorted(vectorizer.vocabulary_.items())
        },
    }
    metrics: dict[str, float | int | str | bool] = {
        "record_count": len(rows),
        "label_count": label_count,
        "slice_count": slice_count,
        "diversity_ratio": diversity,
        "diagnostic_fidelity": round(diagnostic_fidelity, 6),
        "private_fidelity": round(private_fidelity, 6),
        "minimum_slice_fidelity": round(minimum_fidelity, 6),
        "teacher_evaluation_query_count": len(diagnostic_expected) + len(private_expected),
        "teacher_evaluation_token_count": teacher_token_count,
        "model_revision": "tfidf-logreg-extraction-1.0",
    }
    return json.dumps(artifact, separators=(",", ":"), sort_keys=True).encode(), metrics


def _register_extraction_model(
    job_id: str,
    challenge_id: str,
    corpus_digest: str,
    artifact: bytes,
    metrics: dict[str, float | int | str | bool],
) -> tuple[str, str]:
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    client = MlflowClient(tracking_uri=MLFLOW_TRACKING_URI)
    experiment = client.get_experiment_by_name("keplerops-model-extraction")
    experiment_id = (
        client.create_experiment("keplerops-model-extraction")
        if experiment is None
        else experiment.experiment_id
    )
    now = int(time.time() * 1000)
    run = client.create_run(
        experiment_id,
        start_time=now,
        run_name=job_id,
        tags={
            "keplerops.challenge_id": challenge_id,
            "keplerops.corpus_digest": corpus_digest,
        },
    )
    run_id = run.info.run_id
    metric_keys = (
        "diversity_ratio",
        "diagnostic_fidelity",
        "private_fidelity",
        "minimum_slice_fidelity",
    )
    client.log_batch(
        run_id,
        metrics=[Metric(key, float(metrics[key]), now, 0) for key in metric_keys],
        params=[
            Param("model_revision", str(metrics["model_revision"])),
            Param("record_count", str(metrics["record_count"])),
            Param("slice_count", str(metrics["slice_count"])),
        ],
        tags=[],
    )
    with tempfile.TemporaryDirectory(prefix="keplerops-extraction-") as directory:
        path = Path(directory) / "proxy.json"
        path.write_bytes(artifact)
        client.log_artifact(run_id, str(path), artifact_path="model-extraction")
    artifact_uri = run.info.artifact_uri.rstrip("/") + "/model-extraction/proxy.json"
    client.set_terminated(run_id, status="FINISHED", end_time=int(time.time() * 1000))
    return run_id, artifact_uri


def _finish_extraction_job(
    job_id: str,
    *,
    metrics: dict[str, float | int | str | bool],
    artifact_digest: str,
    artifact_uri: str,
    registry_run_id: str,
) -> None:
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(
            "UPDATE extraction_jobs SET status='evaluating', model_revision=%s, "
            "metrics=%s::jsonb, artifact_digest=%s, artifact_uri=%s, registry_run_id=%s, "
            "completed_at=clock_timestamp() WHERE job_id=%s AND status='running'",
            (
                metrics["model_revision"],
                json.dumps(metrics, separators=(",", ":"), sort_keys=True),
                artifact_digest,
                artifact_uri,
                registry_run_id,
                job_id,
            ),
        )
        if cursor.rowcount != 1:
            raise RuntimeError("extraction job completion was rejected")


EXTRACTION_EVIDENCE = {
    "kep-m08-c": "proxy_diagnostic_fidelity",
    "kep-m08-d": "proxy_budgeted_fidelity",
    "kep-m08-e": "proxy_private_fidelity",
    "kep-m08-f": "proxy_fidelity_verdict",
}


def _record_extraction_evidence(
    *,
    challenge_id: str,
    range_instance: str,
    participant: str,
    generation: int,
    job_id: str,
    artifact_digest: str,
    record_count: int,
) -> None:
    event = {
        "actor_role": "participant",
        "asset_id": "distillation-runner-01",
        "digest": artifact_digest,
        "event_kind": EXTRACTION_EVIDENCE[challenge_id],
        "object_id": job_id,
        "outcome_id": "model-extraction",
        "participant": participant,
        "range_instance": range_instance,
        "record_count": record_count,
        "status": "passed",
        "timestamp": int(time.time()),
        "workflow_id": job_id,
    }
    request = urllib.request.Request(
        "https://telemetry-proof-01.keplerops.lab/v1/evidence",
        data=json.dumps(
            {"event": event, "reset_generation": generation},
            separators=(",", ":"),
            sort_keys=True,
        ).encode(),
        headers={
            "Content-Type": JSON_CONTENT_TYPE,
            "X-Producer-ID": "distillation-runner-01",
            "X-Producer-Token": _secret(PRODUCER_TOKEN_PATH),
        },
        method="POST",
    )
    with urllib.request.urlopen(request, context=_tls_context(), timeout=5) as response:
        if response.status != 204:
            raise RuntimeError("extraction evidence was rejected")


def _complete_extraction_job(job_id: str) -> None:
    with _postgres() as connection, connection.cursor() as cursor:
        cursor.execute(
            "UPDATE extraction_jobs SET status='succeeded' "
            "WHERE job_id=%s AND status='evaluating'",
            (job_id,),
        )
        if cursor.rowcount != 1:
            raise RuntimeError("extraction job award was rejected")


def _fail_extraction_job(job_id: str) -> None:
    try:
        with _postgres() as connection, connection.cursor() as cursor:
            cursor.execute(
                "UPDATE extraction_jobs SET status='failed', failure_class='workflow-failed', "
                "completed_at=clock_timestamp() WHERE job_id=%s "
                "AND status IN ('queued', 'running', 'evaluating')",
                (job_id,),
            )
    except Exception:
        return


def _extraction_job(job_id: str, workflow_id: str, trace_id: str) -> dict[str, str | int]:
    started = time.perf_counter_ns()
    try:
        (
            range_instance,
            participant,
            generation,
            challenge_id,
            corpus_digest,
            query_budget,
            query_count,
            record_count,
            slice_count,
            diversity_ratio,
            corpus_rows,
        ) = _claim_extraction_job(job_id, workflow_id)
        if not _namespace_matches(range_instance, participant) or generation != int(
            RESET_GENERATION_PATH.read_text(encoding="ascii")
        ):
            raise RuntimeError("extraction job namespace is invalid")
        artifact, metrics = _train_extraction_proxy(corpus_rows)
        metrics.update(
            {
                "query_budget": query_budget,
                "query_count": query_count,
                "record_count": record_count,
                "slice_count": slice_count,
                "diversity_ratio": diversity_ratio,
                "gathered_artifacts": challenge_id == "kep-m08-g",
            }
        )
        artifact_digest = SHA256_PREFIX + hashlib.sha256(artifact).hexdigest()
        capture_artifact(
            trace_id,
            artifact_id=f"{job_id}/model-extraction/proxy.json",
            content=artifact,
            media_type=JSON_CONTENT_TYPE,
            metadata={
                "challenge_id": challenge_id,
                "corpus_digest": corpus_digest,
                "artifact_digest": artifact_digest,
            },
        )
        registry_run_id, artifact_uri = _register_extraction_model(
            job_id, challenge_id, corpus_digest, artifact, metrics
        )
        metrics["artifact_stored"] = True
        metrics["registry_recorded"] = True
        metrics["duration_ms"] = (time.perf_counter_ns() - started) // 1_000_000
        _finish_extraction_job(
            job_id,
            metrics=metrics,
            artifact_digest=artifact_digest,
            artifact_uri=artifact_uri,
            registry_run_id=registry_run_id,
        )
        domain_metrics = ExtractionMetrics(
            query_count=int(metrics["query_count"]),
            query_budget=int(metrics["query_budget"]),
            record_count=int(metrics["record_count"]),
            label_count=int(metrics["label_count"]),
            slice_count=int(metrics["slice_count"]),
            diversity_ratio=float(metrics["diversity_ratio"]),
            diagnostic_fidelity=float(metrics["diagnostic_fidelity"]),
            private_fidelity=float(metrics["private_fidelity"]),
            minimum_slice_fidelity=float(metrics["minimum_slice_fidelity"]),
            artifact_stored=True,
            registry_recorded=True,
            gathered_artifacts=bool(metrics["gathered_artifacts"]),
        )
        if (
            extraction_satisfied(challenge_id, domain_metrics)
            and challenge_id in EXTRACTION_EVIDENCE
        ):
            _record_extraction_evidence(
                challenge_id=challenge_id,
                range_instance=range_instance,
                participant=participant,
                generation=generation,
                job_id=job_id,
                artifact_digest=artifact_digest,
                record_count=record_count,
            )
        _complete_extraction_job(job_id)
        _observe(
            WORKFLOW_COMPLETED_EVENT,
            trace_id=trace_id,
            status="passed",
            module_id="module-08-model-extraction",
            challenge_id=challenge_id,
            workflow_run_id=job_id,
            duration_ms=metrics["duration_ms"],
            query_count=query_count,
            query_budget=query_budget,
            record_count=record_count,
            coverage_count=slice_count,
            diagnostic_fidelity=metrics["diagnostic_fidelity"],
            private_fidelity=metrics["private_fidelity"],
            minimum_slice_fidelity=metrics["minimum_slice_fidelity"],
            artifact_digest=artifact_digest,
            model_revision=metrics["model_revision"],
            score_bucket=(
                f"diagnostic-{metrics['diagnostic_fidelity']}-"
                f"private-{metrics['private_fidelity']}"
            ),
        )
        return {"job_id": job_id, "record_count": record_count}
    except Exception:
        _fail_extraction_job(job_id)
        _observe(
            WORKFLOW_COMPLETED_EVENT,
            trace_id=trace_id,
            status="failed",
            module_id="module-08-model-extraction",
            challenge_id="kep-m08-c",
            workflow_run_id=job_id,
            failure_class="workflow-failed",
        )
        raise


def _validated_job_id(
    conf: dict[str, object],
    *,
    key: str,
    pattern: re.Pattern[str],
    error: str,
) -> str:
    value = conf.get(key)
    if (
        not isinstance(value, str)
        or pattern.fullmatch(value) is None
        or set(conf) != {key}
    ):
        raise RuntimeError(error)
    return value


def _workflow_trace_id(run_id: str) -> str:
    material = ":".join(
        (
            os.environ.get("KEPLEROPS_RANGE_INSTANCE", "range-unset"),
            os.environ.get("KEPLEROPS_PARTICIPANT", "participant-unset"),
            run_id,
        )
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]


def _capture_workflow_state(
    trace_id: str,
    run_id: str,
    event: str,
    **fields: object,
) -> None:
    capture_json(
        "workflow_state",
        trace_id,
        {"event": event, "workflow_run_id": run_id, **fields},
    )


def _capture_workflow_result(
    trace_id: str,
    run_id: str,
    result: dict[str, str | int | float],
) -> dict[str, str | int | float]:
    _capture_workflow_state(trace_id, run_id, "dag_run.completed", result=result)
    return result


def _run_data_dependency_task(
    conf: dict[str, object], run_id: str, trace_id: str
) -> dict[str, str | float]:
    job_id = _validated_job_id(
        conf,
        key="data_dependency_job_id",
        pattern=DATA_DEPENDENCY_JOB_ID,
        error="data dependency job configuration is invalid",
    )
    _observe(
        WORKFLOW_STARTED_EVENT,
        trace_id=trace_id,
        status="recorded",
        module_id="module-02-model-evasion",
        challenge_id="kep-m02-i",
        workflow_run_id=run_id,
    )
    return _data_dependency_job(job_id, run_id, trace_id)


def _run_extraction_task(
    conf: dict[str, object], run_id: str, trace_id: str
) -> dict[str, str | int]:
    job_id = _validated_job_id(
        conf,
        key="extraction_job_id",
        pattern=EXTRACTION_JOB_ID,
        error="extraction job configuration is invalid",
    )
    _observe(
        WORKFLOW_STARTED_EVENT,
        trace_id=trace_id,
        status="recorded",
        module_id="module-08-model-extraction",
        workflow_run_id=run_id,
    )
    return _extraction_job(job_id, run_id, trace_id)


def _run_legacy_training(run_id: str, trace_id: str) -> dict[str, str | int]:
    artifact, record_count = _legacy_train()
    OUTPUT.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
    OUTPUT.write_bytes(artifact)
    digest = hashlib.sha256(artifact).hexdigest()
    capture_artifact(
        trace_id,
        artifact_id=f"{run_id}/legacy/student-adapter.json",
        content=artifact,
        media_type=JSON_CONTENT_TYPE,
        metadata={"artifact_digest": SHA256_PREFIX + digest},
    )
    _observe(
        WORKFLOW_COMPLETED_EVENT,
        trace_id=trace_id,
        status="passed",
        record_count=record_count,
        artifact_digest=SHA256_PREFIX + digest,
        workflow_run_id=run_id,
    )
    return {"record_count": record_count, "digest": digest}


def _run_distillation_task(dag_run: Any) -> dict[str, str | int | float]:
    run_id = str(dag_run.run_id)
    trace_id = _workflow_trace_id(run_id)
    conf = dag_run.conf if isinstance(dag_run.conf, dict) else {}
    _capture_workflow_state(trace_id, run_id, "dag_run.started", conf=conf)
    if conf.get("data_dependency_job_id") is not None:
        return _capture_workflow_result(
            trace_id,
            run_id,
            _run_data_dependency_task(conf, run_id, trace_id),
        )
    if conf.get("extraction_job_id") is not None:
        return _capture_workflow_result(
            trace_id,
            run_id,
            _run_extraction_task(conf, run_id, trace_id),
        )
    _observe(
        WORKFLOW_STARTED_EVENT,
        trace_id=trace_id,
        status="recorded",
        workflow_run_id=run_id,
    )
    if conf.get("job_id") is not None:
        job_id = _validated_job_id(
            conf,
            key="job_id",
            pattern=JOB_ID,
            error="training job configuration is invalid",
        )
        return _capture_workflow_result(
            trace_id,
            run_id,
            _training_job(job_id, run_id, trace_id),
        )
    return _capture_workflow_result(
        trace_id,
        run_id,
        _run_legacy_training(run_id, trace_id),
    )


@dag(schedule=None, catchup=False, tags=["keplerops", "distillation"])
def keplerops_distillation():
    @task
    def train() -> dict[str, str | int | float]:
        return _run_distillation_task(get_current_context()["dag_run"])

    train()


keplerops_distillation()
