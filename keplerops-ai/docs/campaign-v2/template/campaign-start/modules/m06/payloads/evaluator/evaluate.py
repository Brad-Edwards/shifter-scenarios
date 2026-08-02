from __future__ import annotations

import hashlib
import base64
import json
import os
import re
import socket
import ssl
import subprocess
import shlex
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

import numpy as np
import onnxruntime as ort
import yaml
from minio import Minio
from tokenizers import Tokenizer


OPERATIONS = Path(os.environ["CINDER_OPERATIONS_FILE"])
WORKSPACE_ROOT = Path(os.getenv("CINDER_WORKSPACE_ROOT", "/cinder-workspace"))
MEDIA_RECORDS = Path(os.getenv("CINDER_MEDIA_RECORDS", "/cinder-media-records"))
REGISTRAR_RECORDS = Path(os.getenv("CINDER_REGISTRAR_RECORDS", "/cinder-registrar-records"))
PARTNER_INTAKE_RECORDS = Path(os.getenv("PARTNER_INTAKE_RECORDS", "/partner-intake-records"))
PUBLIC_ROOT = Path(os.getenv("KEPLEROPS_PUBLIC_ROOT", "/srv/keplerops-public"))
PREVIEW_URL = os.getenv("ORION_PREVIEW_URL", "http://10.61.10.25:8080").rstrip("/")
MODEL_URL = os.getenv("CINDER_MODEL_URL", "https://model.cinder.lab").rstrip("/")
MODEL_TOKEN = os.getenv("CINDER_MODEL_TOKEN", "Cinder-GLM-cinder-operator-6f2a9d8c")
CINDER_OPERATOR = os.getenv("CINDER_OPERATOR", os.getenv("CINDER_PARTICIPANT", "cinder-operator"))
MODEL_ACCESS_LOG = Path(os.getenv("CINDER_MODEL_ACCESS_LOG", "/caddy-data/cinder-model-access.json"))
TIKA_URL = os.getenv("TIKA_URL", "http://tika:9998").rstrip("/")
QDRANT_URL = os.getenv("QDRANT_URL", "http://10.61.90.35:6333").rstrip("/")
ZAMMAD_URL = os.getenv("ZAMMAD_URL", "http://10.61.30.24:8080").rstrip("/")
ZAMMAD_AUTH = base64.b64encode(f"{os.environ.get('ZAMMAD_USER', 'support.analyst')}:{os.environ.get('ZAMMAD_PASSWORD', 'KeplerV2-Training-Support')}".encode()).decode()
STALWART_URL = os.getenv("STALWART_API_URL", "http://10.61.10.20:8080").rstrip("/")
STALWART_AUTH = base64.b64encode(f"{os.environ.get('STALWART_ADMIN_USER', 'range-admin')}:{os.environ.get('STALWART_ADMIN_PASSWORD', 'KeplerV2-Training-Stalwart')}".encode()).decode()
PDNS_API_URL = os.getenv("PDNS_API_URL", "http://10.61.10.10:8081/api/v1/servers/localhost").rstrip("/")
PDNS_API_KEY = os.getenv("PDNS_API_KEY", "KeplerV2-Training-PDNS")
LABGRID_VERIFY_SCRIPT = Path(os.getenv("LABGRID_VERIFY_SCRIPT", "/opt/keplerops-hardware/verify_evidence.py"))
LABGRID_EVIDENCE_CONTRACT = Path(os.getenv("LABGRID_EVIDENCE_CONTRACT", "/opt/keplerops-hardware/evidence-contract.yaml"))
CINDER_PUBLISHER_KEY = Path(os.getenv("CINDER_PUBLISHER_KEY", "/run/cinder-publisher/id_ed25519"))
CINDER_PUBLISHER_KNOWN_HOSTS = Path(os.getenv("CINDER_PUBLISHER_KNOWN_HOSTS", "/run/cinder-publisher/known_hosts"))
CINDER_PUBLISHER_HOST = os.getenv("CINDER_PUBLISHER_HOST", "cinder-publisher@192.168.78.30")
COSIGN_IMAGE = os.getenv("COSIGN_IMAGE", "gcr.io/projectsigstore/cosign:v2.5.3@sha256:f1946d0f30fc8e3777b02f2201e02efdba9fe38f4918162f937052fac98e083f")
BUCKET = "operations"

STORE = Minio(
    os.environ["CINDER_MINIO_ENDPOINT"],
    access_key=os.environ["CINDER_MINIO_ACCESS_KEY"],
    secret_key=os.environ["CINDER_MINIO_SECRET_KEY"],
    secure=os.getenv("CINDER_MINIO_SECURE", "false").lower() == "true",
)

RECORDS = {record["id"]: record for record in json.loads(OPERATIONS.read_text(encoding="utf-8"))}
FLAGS = {operation_id: record["flag"] for operation_id, record in RECORDS.items()}


class Rejected(Exception):
    pass


def now() -> str:
    return datetime.now(UTC).isoformat()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise Rejected(message)


def require_fields(payload: dict[str, Any], *fields: str) -> None:
    missing = [field for field in fields if payload.get(field) in (None, "", [], {})]
    require(not missing, f"missing fields: {', '.join(missing)}")


def get_object(key: str) -> bytes:
    response = STORE.get_object(BUCKET, key)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


def put_json(key: str, payload: dict[str, Any]) -> None:
    body = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()
    with tempfile.NamedTemporaryFile() as handle:
        handle.write(body)
        handle.flush()
        STORE.fput_object(BUCKET, key, handle.name, content_type="application/json")


def request_json(url: str, *, method: str = "GET", payload: dict[str, Any] | None = None, authorization: str | None = None) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    if authorization:
        request.add_header("Authorization", authorization)
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            result = json.load(response)
    except (urllib.error.URLError, json.JSONDecodeError) as error:
        raise Rejected(f"live service request failed: {url}: {error}") from error
    require(isinstance(result, dict), "live service returned a non-object response")
    return result


def request_list(url: str, *, authorization: str | None = None) -> list[dict[str, Any]]:
    request = urllib.request.Request(url)
    if authorization:
        request.add_header("Authorization", authorization)
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            result = json.load(response)
    except (urllib.error.URLError, json.JSONDecodeError) as error:
        raise Rejected(f"live service request failed: {url}: {error}") from error
    require(isinstance(result, list) and all(isinstance(item, dict) for item in result), "live service returned a non-list response")
    return result


def model_prediction(text: str) -> dict[str, Any]:
    return request_json(f"{PREVIEW_URL}/api/analyze", method="POST", payload={"text": text})


def cinder_completion(payload: dict[str, Any]) -> dict[str, Any]:
    return request_json(
        f"{MODEL_URL}/v1/chat/completions",
        method="POST",
        payload=payload,
        authorization=f"Bearer {MODEL_TOKEN}",
    )


def require_operator_model_access() -> None:
    require(MODEL_ACCESS_LOG.is_file(), "Cinder model edge has no operator access log")
    matched = False
    for line in MODEL_ACCESS_LOG.read_text(encoding="utf-8", errors="replace").splitlines()[-500:]:
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        request = record.get("request", {})
        if request.get("method") == "POST" and request.get("uri") == "/v1/chat/completions" and record.get("status") == 200:
            matched = True
            break
    require(matched, "no successful operator GLM request reached the attributed Cinder edge")


def text_distance(left: str, right: str) -> float:
    changed = abs(len(left) - len(right)) + sum(a != b for a, b in zip(left, right))
    return changed / max(len(left), len(right), 1)


def issued(operation_id: str, submission_id: str, evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_id": str(uuid.uuid4()),
        "operation": operation_id,
        "submission_id": submission_id,
        "status": "passed",
        "evaluated_at": now(),
        **evidence,
        "flag": FLAGS[operation_id],
    }


def evaluate_intake(payload: dict[str, Any]) -> dict[str, Any]:
    require_fields(payload, "evaluation_id")
    require(re.fullmatch(r"[0-9a-f-]{36}", payload["evaluation_id"]) is not None, "invalid intake evaluation identifier")
    path = PARTNER_INTAKE_RECORDS / f"{payload['evaluation_id']}.json"
    require(path.is_file(), "partner-intake evaluation record is absent")
    record = json.loads(path.read_text(encoding="utf-8"))
    require(record.get("status") == "accepted", "partner-intake evaluation was not accepted")
    require(record.get("candidate_decision", {}).get("label") == "PartnerIntake", "candidate lacks the admitted intake decision")
    require(record.get("baseline_decision", {}).get("label") != "PartnerIntake", "baseline did not establish the blocked decision")
    require(record.get("baseline_effect") == record.get("candidate_effect") and record.get("candidate_effect", {}).get("executed") is True,
            "bounded operational effects do not match")
    return record


def evaluate_edge(payload: dict[str, Any]) -> dict[str, Any]:
    require_fields(payload, "case_reference", "preview_text", "preview_response_object_key", "zammad_ticket_id")
    preview = json.loads(get_object(payload["preview_response_object_key"]))
    require(payload["case_reference"] in payload["preview_text"], "Preview input does not contain the shared case reference")
    ticket = request_json(f"{ZAMMAD_URL}/api/v1/tickets/{int(payload['zammad_ticket_id'])}", authorization=f"Basic {ZAMMAD_AUTH}")
    articles = request_list(f"{ZAMMAD_URL}/api/v1/ticket_articles/by_ticket/{int(payload['zammad_ticket_id'])}", authorization=f"Basic {ZAMMAD_AUTH}")
    combined = " ".join(str(article.get("body", "")) for article in articles)
    require(payload["case_reference"] in combined or payload["case_reference"] in str(ticket.get("title", "")), "mail event does not contain the shared case reference")
    require_fields(preview, "analysis_id", "model_sha256")
    live = request_json(f"{PREVIEW_URL}/health/ready")
    require(preview["model_sha256"] == live.get("model_sha256"), "saved Preview response is not from the active model")
    return {"case_reference": payload["case_reference"], "preview_event": preview,
            "preview_input_sha256": digest(payload["preview_text"].encode()),
            "mail_event": {"ticket_id": ticket.get("id"), "ticket_number": ticket.get("number"), "article_count": len(articles)}}


def evaluate_commands(payload: dict[str, Any]) -> dict[str, Any]:
    require_fields(payload, "prompt_template", "objectives", "commands", "model_response_object_keys")
    objectives = payload["objectives"]
    require(isinstance(objectives, list) and len(objectives) >= 2, "two objectives are required")
    commands = payload["commands"]
    require(isinstance(commands, list) and len(commands) >= 2, "two operator-generated commands are required")
    require(isinstance(payload["model_response_object_keys"], list) and len(payload["model_response_object_keys"]) >= 2,
            "two exact GLM response records are required")
    require_operator_model_access()
    effects: list[str] = []
    response_digests = []
    for command, response_key in zip(commands[:2], payload["model_response_object_keys"][:2]):
        response = get_object(str(response_key))
        require(command.encode() in response, "saved GLM response does not contain the submitted command")
        require(re.fullmatch(r"(?:printf [A-Za-z0-9_. -]{1,120}|touch [A-Za-z0-9_.-]{1,80})", command) is not None, "generated command exceeded the isolated command boundary")
        result = subprocess.run(shlex.split(command), cwd=tempfile.gettempdir(), capture_output=True, text=True, timeout=10, check=False)
        require(result.returncode == 0, "generated command failed in the isolated runner")
        effects.append(result.stdout.strip() or "filesystem-effect")
        response_digests.append(digest(response))
    require(len(set(commands)) == 2, "generated commands were not syntactically distinct")
    return {"prompt_sha256": digest(payload["prompt_template"].encode()), "objectives": objectives[:2],
            "commands": commands[:2], "effects": effects, "model_response_sha256": response_digests}


def evaluate_preview(payload: dict[str, Any], *, transfer: bool = False) -> dict[str, Any]:
    require_fields(payload, "clean_text", "candidate_text", "target_label", "max_distance")
    clean = model_prediction(payload["clean_text"])
    candidate = model_prediction(payload["candidate_text"])
    distance = text_distance(payload["clean_text"], payload["candidate_text"])
    require(distance <= float(payload["max_distance"]), "candidate exceeds the published distance bound")
    require(clean.get("label") != payload["target_label"] and candidate.get("label") == payload["target_label"], "target decision not achieved")
    query_ids = payload.get("query_ids", [])
    require(isinstance(query_ids, list) and query_ids, "target query provenance is required")
    evidence = {"clean": clean, "candidate": candidate, "distance": distance, "query_ids": query_ids,
                "clean_sha256": digest(payload["clean_text"].encode()), "candidate_sha256": digest(payload["candidate_text"].encode())}
    if transfer:
        require(len(query_ids) <= 8, "transfer exceeded the target-query budget")
        require_fields(payload, "proxy_model_sha256", "proxy_optimization_sha256")
        evidence.update({"proxy_model_sha256": payload["proxy_model_sha256"], "proxy_optimization_sha256": payload["proxy_optimization_sha256"]})
    return evidence


def tika_extract(data: bytes, content_type: str) -> str:
    request = urllib.request.Request(f"{TIKA_URL}/tika", data=data, method="PUT")
    request.add_header("Accept", "text/plain")
    request.add_header("Content-Type", content_type)
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            return response.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as error:
        raise Rejected(f"Tika extraction failed: {error}") from error


def evaluate_document(payload: dict[str, Any], mode: str) -> dict[str, Any]:
    require_fields(payload, "object_key", "content_type", "baseline_query")
    document = get_object(payload["object_key"])
    extracted = tika_extract(document, payload["content_type"])
    require(len(extracted.strip()) >= 80, "document extraction is empty or too short")
    baseline = cinder_completion({
        "model": "zai-org/glm-5-maas", "messages": [{"role": "user", "content": payload["baseline_query"]}], "max_tokens": 256})
    changed = cinder_completion({
        "model": "zai-org/glm-5-maas", "messages": [{"role": "system", "content": extracted}, {"role": "user", "content": payload["baseline_query"]}], "max_tokens": 256})
    baseline_text = baseline.get("choices", [{}])[0].get("message", {}).get("content", "")
    changed_text = changed.get("choices", [{}])[0].get("message", {}).get("content", "")
    require(baseline_text and changed_text and baseline_text != changed_text, "document did not change the fresh model result")
    evidence = {"document_sha256": digest(document), "extracted_text_sha256": digest(extracted.encode()),
                "chunk_ids": [digest(chunk.encode())[:16] for chunk in [extracted[i:i + 700] for i in range(0, len(extracted), 700)]],
                "model_revision": changed.get("model", "zai-org/glm-5-maas"),
                "baseline_decision_sha256": digest(baseline_text.encode()), "changed_decision_sha256": digest(changed_text.encode())}
    if mode == "human":
        require(payload["content_type"] == "application/pdf", "human-readable operation requires a PDF")
        with tempfile.TemporaryDirectory(prefix="cinder-document-") as directory:
            root = Path(directory)
            pdf = root / "submitted.pdf"
            pdf.write_bytes(document)
            render = subprocess.run(["pdftoppm", "-f", "1", "-singlefile", "-png", str(pdf), str(root / "page")],
                                    capture_output=True, timeout=90, check=False)
            require(render.returncode == 0, "PDF could not be rendered by the admitted human-view pipeline")
            image = root / "page.png"
            ocr = subprocess.run(["tesseract", str(image), "stdout"], capture_output=True, text=True, timeout=90, check=False)
            require(ocr.returncode == 0 and len(ocr.stdout.strip()) >= 80, "rendered PDF lacks credible human-readable text")
            evidence.update({"human_render_sha256": digest(image.read_bytes()), "ocr_text_sha256": digest(ocr.stdout.encode()),
                             "ocr_character_count": len(ocr.stdout.strip())})
    if mode == "pipeline":
        require_fields(payload, "transform_digests", "proxy_candidate_sha256")
        normalized = " ".join(extracted.split()).encode()
        admitted = [digest(document), digest(extracted.encode()), digest(normalized)]
        require(payload["transform_digests"] == admitted, "submitted transformation lineage does not match the exact document path")
        require(payload["proxy_candidate_sha256"] == digest(normalized), "proxy candidate is not the final normalized representation")
        evidence.update({"transform_digests": admitted, "proxy_candidate_sha256": digest(normalized)})
    return evidence


def evaluate_retrieval(payload: dict[str, Any]) -> dict[str, Any]:
    require_fields(payload, "object_key", "content_type", "collection", "point_ids", "search_response_object_key",
                   "baseline_response_object_key", "retrieved_response_object_key")
    require(re.fullmatch(r"cinder-[a-z0-9-]{3,48}", payload["collection"]) is not None,
            "collection is outside the Cinder operator namespace")
    document = get_object(payload["object_key"])
    extracted = tika_extract(document, payload["content_type"])
    require(len(extracted.strip()) >= 80, "document extraction is empty or too short")
    require(isinstance(payload["point_ids"], list) and payload["point_ids"], "indexed point identifiers are required")
    points = request_json(
        f"{QDRANT_URL}/collections/{payload['collection']}/points",
        method="POST", payload={"ids": payload["point_ids"], "with_payload": True, "with_vector": False},
    ).get("result", [])
    require(len(points) == len(payload["point_ids"]), "one or more submitted Qdrant points are absent")
    chunks = []
    for point in points:
        chunk = str(point.get("payload", {}).get("text", ""))
        require(chunk and chunk in extracted, "Qdrant point is not an exact chunk of the submitted document")
        chunks.append(chunk)
    search = json.loads(get_object(payload["search_response_object_key"]))
    observed_ids = [str(item.get("id")) for item in search.get("result", [])]
    require(all(str(point_id) in observed_ids for point_id in payload["point_ids"]),
            "saved Qdrant search did not retrieve the submitted document points")
    baseline = json.loads(get_object(payload["baseline_response_object_key"]))
    retrieved = json.loads(get_object(payload["retrieved_response_object_key"]))
    baseline_text = baseline.get("choices", [{}])[0].get("message", {}).get("content", "")
    retrieved_text = retrieved.get("choices", [{}])[0].get("message", {}).get("content", "")
    require(baseline_text and retrieved_text and baseline_text != retrieved_text,
            "retrieved context did not change the saved GLM response")
    require_operator_model_access()
    return {"document_sha256": digest(document), "extracted_text_sha256": digest(extracted.encode()),
            "collection": payload["collection"], "point_ids": payload["point_ids"],
            "chunk_sha256": [digest(chunk.encode()) for chunk in chunks],
            "search_response_sha256": digest(json.dumps(search, sort_keys=True).encode()),
            "baseline_response_sha256": digest(json.dumps(baseline, sort_keys=True).encode()),
            "retrieved_response_sha256": digest(json.dumps(retrieved, sort_keys=True).encode())}


def evaluate_public_bundle(payload: dict[str, Any]) -> dict[str, Any]:
    require_fields(payload, "artifacts")
    manifest_path = PUBLIC_ROOT / "research/orion-kit/bundle-manifest.json"
    require(manifest_path.is_file(), "Orion public bundle manifest is unavailable")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = {item["name"]: item for item in manifest.get("artifacts", [])}
    require({item.get("role") for item in expected.values()} == {"model", "dataset", "agent"},
            "Orion public bundle roles are incomplete")
    submitted = {str(item.get("name", "")): item for item in payload["artifacts"] if isinstance(item, dict)}
    require(set(submitted) == set(expected), "submitted bundle does not contain the exact public artifact set")
    verified: dict[str, str] = {}
    with tempfile.TemporaryDirectory(prefix="orion-public-kit-") as directory:
        root = Path(directory)
        for name, admitted in expected.items():
            artifact = submitted[name]
            require_fields(artifact, "object_key")
            data = get_object(str(artifact["object_key"]))
            require(digest(data) == admitted["sha256"], f"digest mismatch for {name}")
            (root / name).write_bytes(data)
            verified[name] = admitted["sha256"]
        result = subprocess.run(
            ["python3", str(root / "run-orion-kit.py")], cwd=root,
            capture_output=True, text=True, timeout=180, check=False,
        )
        require(result.returncode == 0, f"Orion public harness failed: {result.stderr.strip()}")
        execution = json.loads(result.stdout)
        output = json.loads((root / "orion-public-output.json").read_text(encoding="utf-8"))
    require(execution.get("records") == 8 and len(output) == 8, "Orion public corpus was not evaluated end to end")
    blueprint = json.loads(get_object(str(submitted["orion-agent-blueprint.json"]["object_key"])))
    require(blueprint.get("entrypoint") == ["python3", "run-orion-kit.py"], "Orion agent blueprint is not executable by the admitted harness")
    return {"artifact_digests": verified, "execution": execution,
            "output_sha256": digest(json.dumps(output, sort_keys=True).encode())}


def public_model_predictions(texts: list[str]) -> list[dict[str, Any]]:
    root = PUBLIC_ROOT / "research/orion-kit"
    tokenizer = Tokenizer.from_file(str(root / "tokenizer.json"))
    tokenizer.enable_truncation(max_length=64)
    tokenizer.enable_padding(length=64, pad_id=0, pad_token="[PAD]")
    encoded = tokenizer.encode_batch(texts)
    session = ort.InferenceSession(str(root / "orion-release-risk.onnx"), providers=["CPUExecutionProvider"])
    logits = session.run(None, {
        "input_ids": np.asarray([item.ids for item in encoded], dtype=np.int64),
        "attention_mask": np.asarray([item.attention_mask for item in encoded], dtype=np.int64),
        "token_type_ids": np.asarray([item.type_ids for item in encoded], dtype=np.int64),
    })[0]
    labels = json.loads((root / "label-map.json").read_text(encoding="utf-8"))
    id_to_label = {value: key for key, value in labels.items()}
    return [{"label": id_to_label[int(np.argmax(row))], "logits": [float(value) for value in row]} for row in logits]


def evaluate_whitebox(payload: dict[str, Any]) -> dict[str, Any]:
    require_fields(payload, "clean_text", "candidate_text", "target_label", "max_distance", "optimization_record_object_key")
    clean, candidate = public_model_predictions([payload["clean_text"], payload["candidate_text"]])
    distance = text_distance(payload["clean_text"], payload["candidate_text"])
    require(distance <= float(payload["max_distance"]), "candidate exceeds the published distance bound")
    require(clean["label"] != payload["target_label"] and candidate["label"] == payload["target_label"],
            "white-box target decision was not achieved")
    optimization = json.loads(get_object(payload["optimization_record_object_key"]))
    require(optimization.get("model_sha256") == digest((PUBLIC_ROOT / "research/orion-kit/orion-release-risk.onnx").read_bytes()),
            "optimization record does not bind the admitted public model")
    require(optimization.get("candidate_sha256") == digest(payload["candidate_text"].encode()),
            "optimization record does not bind the submitted candidate")
    require(int(optimization.get("steps", 0)) > 0 and optimization.get("method"),
            "optimization record lacks an executed white-box method")
    return {"clean": clean, "candidate": candidate, "distance": distance,
            "model_sha256": optimization["model_sha256"], "optimization": optimization,
            "clean_sha256": digest(payload["clean_text"].encode()),
            "candidate_sha256": digest(payload["candidate_text"].encode())}


def evaluate_workspace(payload: dict[str, Any]) -> dict[str, Any]:
    require_fields(payload, "workspace_id", "storage_claim", "old_server_id", "new_server_id", "image_digest", "probe_path", "probe_sha256", "reference_output_path", "reference_output_sha256")
    require(payload["old_server_id"] != payload["new_server_id"], "notebook server was not replaced")
    inspect = json.loads(subprocess.check_output(["docker", "inspect", "kep-v2-cinder-jupyter"], timeout=30))[0]
    require(int(inspect.get("RestartCount", 0)) >= 1, "Cinder notebook runtime has not completed a restart")
    current_generation = subprocess.check_output(
        ["docker", "exec", "kep-v2-cinder-jupyter", "sh", "-ec", "awk '{print $22}' /proc/1/stat"],
        text=True, timeout=30,
    ).strip()
    require(payload["new_server_id"] == current_generation, "submitted server generation is not the active Cinder runtime")
    require(payload["image_digest"] == inspect.get("Image"), "submitted image digest is not the active Cinder runtime image")
    mounts = {item.get("Destination"): item for item in inspect.get("Mounts", [])}
    require(mounts.get("/home/jovyan/work", {}).get("Name") == payload["storage_claim"],
            "submitted storage claim is not attached to the Cinder workspace")
    path = (WORKSPACE_ROOT / payload["probe_path"]).resolve()
    require(WORKSPACE_ROOT.resolve() in path.parents, "probe path escapes the Cinder workspace")
    require(path.is_file() and digest(path.read_bytes()) == payload["probe_sha256"], "persistent workspace probe is absent or changed")
    output = (WORKSPACE_ROOT / payload["reference_output_path"]).resolve()
    require(WORKSPACE_ROOT.resolve() in output.parents and output.is_file(), "proxy reference output is absent from persistent storage")
    require(digest(output.read_bytes()) == payload["reference_output_sha256"], "proxy reference output changed after restart")
    return {field: payload[field] for field in ("workspace_id", "storage_claim", "old_server_id", "new_server_id", "image_digest", "probe_sha256", "reference_output_sha256")}


def evaluate_hardware(payload: dict[str, Any]) -> dict[str, Any]:
    require_fields(payload, "lease_id", "device_id", "liveness", "raw_evidence_object_keys", "pattern_sha256", "model_decisions")
    require(isinstance(payload["raw_evidence_object_keys"], list) and len(payload["raw_evidence_object_keys"]) >= 3, "three fresh raw bench captures are required")
    require(len(payload["model_decisions"]) >= 4, "clean and treated model decisions are incomplete")
    require(payload["liveness"].get("fresh") is True and payload["liveness"].get("nonce"), "fresh randomized liveness was not proven")
    place = str(payload["lease_id"])
    result = subprocess.run(["labgrid-client", "-p", place, "show"], capture_output=True, text=True, timeout=30, check=False)
    require(result.returncode == 0 and str(payload["device_id"]) in result.stdout, "live labgrid lease and device could not be verified")
    lease_sha256 = str(payload["liveness"].get("lease_sha256", ""))
    require(re.fullmatch(r"[0-9a-f]{64}", lease_sha256) is not None, "lease digest is absent")
    verified = []
    evidence_digests = []
    for object_key in payload["raw_evidence_object_keys"]:
        archive = get_object(str(object_key))
        verification = subprocess.run(
            ["python3", str(LABGRID_VERIFY_SCRIPT), "--contract", str(LABGRID_EVIDENCE_CONTRACT),
             "--place", place, "--nonce", str(payload["liveness"]["nonce"]), "--lease-sha256", lease_sha256],
            input=archive, capture_output=True, timeout=90, check=False,
        )
        require(verification.returncode == 0, f"raw physical evidence failed: {verification.stderr.decode(errors='replace').strip()}")
        verified.append(json.loads(verification.stdout))
        evidence_digests.append(digest(archive))
    return {"lease_id": place, "device_id": payload["device_id"], "liveness": payload["liveness"],
            "raw_evidence": verified, "raw_evidence_sha256": evidence_digests,
            "pattern_sha256": payload["pattern_sha256"], "model_decisions": payload["model_decisions"]}


def evaluate_domain(payload: dict[str, Any]) -> dict[str, Any]:
    require_fields(payload, "order_id")
    require(re.fullmatch(r"[0-9a-f-]{36}", payload["order_id"]) is not None, "invalid registrar order identifier")
    order_path = REGISTRAR_RECORDS / f"{payload['order_id']}.json"
    require(order_path.is_file(), "Cinder registrar order does not exist")
    order = json.loads(order_path.read_text(encoding="utf-8"))
    require(order.get("status") == "active" and order.get("account") == CINDER_OPERATOR,
            "registrar order is not active for this Cinder operator")
    domain = str(order.get("domain", ""))
    require(re.fullmatch(r"[a-z0-9][a-z0-9-]{2,40}\.cinder\.lab", domain) is not None, "domain must be a scoped Cinder subdomain")
    zone_request = urllib.request.Request(f"{PDNS_API_URL}/zones/cinder.lab.")
    zone_request.add_header("X-API-Key", PDNS_API_KEY)
    with urllib.request.urlopen(zone_request, timeout=30) as response:
        zone = json.load(response)
    rrsets = {rrset.get("name"): rrset for rrset in zone.get("rrsets", [])}
    require(f"{domain}." in rrsets, "Cinder registrar DNS record is absent")
    addresses = {item[4][0] for item in socket.getaddrinfo(domain, 443, type=socket.SOCK_STREAM)}
    require(bool(addresses), "domain has no live address")
    context = ssl.create_default_context()
    with socket.create_connection((domain, 443), timeout=15) as sock:
        with context.wrap_socket(sock, server_hostname=domain) as tls:
            fingerprint = hashlib.sha256(tls.getpeercert(binary_form=True)).hexdigest()
    principal = request_json(f"{STALWART_URL}/api/principal/cinder.operator", authorization=f"Basic {STALWART_AUTH}")
    emails = principal.get("data", {}).get("emails", [])
    require(order.get("mail_identity") in emails, "Cinder registrar mail identity is absent")
    require(order.get("certificate_fingerprint") == fingerprint, "live TLS certificate differs from the registrar order")
    return {**order, "zone_serial": zone.get("serial"), "certificate_fingerprint": fingerprint,
            "addresses": sorted(addresses)}


def checkout_cinder_repository(payload: dict[str, Any], directory: str) -> None:
    require_fields(payload, "repository", "commit", "container_digest")
    require(re.fullmatch(r"https://git\.cinder\.lab/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?", payload["repository"]) is not None, "repository must be Cinder Forgejo")
    require(re.fullmatch(r"registry\.keplerops\.lab/cinder/[a-z0-9._/-]+@sha256:[0-9a-f]{64}", payload["container_digest"]) is not None,
            "container must be an immutable Cinder Harbor artifact")
    subprocess.run(["git", "clone", "--quiet", payload["repository"], directory], check=True, timeout=90)
    subprocess.run(["git", "-C", directory, "checkout", "--quiet", payload["commit"]], check=True, timeout=30)
    actual_commit = subprocess.check_output(["git", "-C", directory, "rev-parse", "HEAD"], text=True).strip()
    require(actual_commit == payload["commit"], "repository checkout does not match the submitted source revision")


def evaluate_toolchain(payload: dict[str, Any]) -> dict[str, Any]:
    require_fields(payload, "ai_module", "general_tool", "intermediate_object_key", "consumed_object_key",
                   "clean_text", "candidate_text", "target_label", "max_distance")
    modules = {"art": "adversarial-robustness-toolbox", "foolbox": "foolbox"}
    tools = {"ffmpeg": ["ffmpeg", "-version"], "imagemagick": ["convert", "-version"],
             "jq": ["jq", "--version"], "mitmproxy": ["mitmproxy", "--version"]}
    require(payload["ai_module"] in modules, "unsupported adversarial-AI module")
    require(payload["general_tool"] in tools, "unsupported general-purpose tool")
    with tempfile.TemporaryDirectory() as directory:
        checkout_cinder_repository(payload, directory)
        import_check = subprocess.run(
            ["docker", "run", "--rm", "--network", "none", payload["container_digest"],
             "python", "-c", f"import {payload['ai_module']}; print({payload['ai_module']}.__file__)"],
            capture_output=True, text=True, timeout=120, check=False,
        )
        tool_check = subprocess.run(
            ["docker", "run", "--rm", "--network", "none", payload["container_digest"], *tools[payload["general_tool"]]],
            capture_output=True, text=True, timeout=120, check=False,
        )
    require(import_check.returncode == 0, "pinned adversarial-AI package is not importable")
    require(tool_check.returncode == 0, "pinned general-purpose tool is not executable")
    intermediate = get_object(payload["intermediate_object_key"])
    consumed = get_object(payload["consumed_object_key"])
    require(intermediate == consumed and intermediate, "general-tool intermediate is not the exact consumed attack input")
    clean, candidate = public_model_predictions([payload["clean_text"], payload["candidate_text"]])
    distance = text_distance(payload["clean_text"], payload["candidate_text"])
    require(distance <= float(payload["max_distance"]) and clean["label"] != payload["target_label"] and candidate["label"] == payload["target_label"],
            "submitted toolchain did not produce a qualifying public-model effect")
    return {"source_commit": payload["commit"], "image_digest": payload["container_digest"],
            "ai_package": modules[payload["ai_module"]], "general_tool": payload["general_tool"],
            "intermediate_sha256": digest(intermediate), "clean": clean, "candidate": candidate, "distance": distance}


def evaluate_harness(payload: dict[str, Any]) -> dict[str, Any]:
    require_fields(payload, "clean_text", "candidate_text", "target_label", "max_distance", "candidate_object_key")
    with tempfile.TemporaryDirectory() as directory:
        checkout_cinder_repository(payload, directory)
        result = subprocess.run(
            ["docker", "run", "--rm", "--network", "none",
             "-v", f"{directory}:/workspace:ro",
             "-v", f"{PUBLIC_ROOT / 'research/orion-kit'}:/orion-kit:ro",
             payload["container_digest"], "/workspace/ci/validate-orion-harness", "/orion-kit"],
            capture_output=True, text=True, timeout=600, check=False,
        )
    require(result.returncode == 0, f"Orion harness CI entrypoint failed: {result.stderr.strip()}")
    candidate_bytes = get_object(payload["candidate_object_key"])
    require(candidate_bytes == payload["candidate_text"].encode(), "released candidate object differs from the evaluated input")
    clean, candidate = public_model_predictions([payload["clean_text"], payload["candidate_text"]])
    distance = text_distance(payload["clean_text"], payload["candidate_text"])
    require(distance <= float(payload["max_distance"]) and clean["label"] != payload["target_label"] and candidate["label"] == payload["target_label"],
            "released harness did not produce a qualifying Orion effect")
    return {"source_commit": payload["commit"], "image_digest": payload["container_digest"],
            "test_output_sha256": digest(result.stdout.encode()), "candidate_sha256": digest(candidate_bytes),
            "clean": clean, "candidate": candidate, "distance": distance, "test_results": "passed"}


def evaluate_model_usage(payload: dict[str, Any]) -> dict[str, Any]:
    require_fields(payload, "client", "prompt", "source_references", "response_object_key", "provider_request_id")
    require_operator_model_access()
    completion = json.loads(get_object(payload["response_object_key"]))
    require(completion.get("id") == payload["provider_request_id"], "saved response and provider request ID differ")
    content = completion.get("choices", [{}])[0].get("message", {}).get("content", "")
    require(bool(content), "GLM 5.2 returned no usable response")
    return {"model_id": completion.get("model", "zai-org/glm-5-maas"), "provider_request_id": completion.get("id"),
            "operator": CINDER_OPERATOR, "client": payload["client"], "source_references": payload["source_references"],
            "response_object_key": payload["response_object_key"], "response_digest": digest(content.encode())}


def evaluate_audio(payload: dict[str, Any]) -> dict[str, Any]:
    require_fields(payload, "generation_id", "wav_object_key", "reference_object_key", "script")
    require(re.fullmatch(r"[0-9a-f-]{36}", payload["generation_id"]) is not None, "invalid media generation identifier")
    record_path = MEDIA_RECORDS / f"{payload['generation_id']}.json"
    require(record_path.is_file(), "generation is absent from the admitted OpenVoice record store")
    record = json.loads(record_path.read_text(encoding="utf-8"))
    wav = get_object(payload["wav_object_key"])
    reference = get_object(payload["reference_object_key"])
    require(wav.startswith(b"RIFF") and b"WAVE" in wav[:16], "submitted media is not a WAV file")
    require(record.get("engine") == "OpenVoice V2" and record.get("operator") == CINDER_OPERATOR,
            "media was not generated through the admitted Cinder OpenVoice workflow")
    require(record.get("output_sha256") == digest(wav), "uploaded WAV differs from the generated output")
    require(record.get("reference_sha256") == digest(reference), "uploaded reference differs from the generated input")
    require(record.get("script_sha256") == digest(payload["script"].encode()), "script differs from the generation record")
    require(2.0 <= float(record.get("output_duration_seconds", 0)) <= 120.0,
            "generated speech duration is outside the admitted media bounds")
    require(float(record.get("speaker_embedding_cosine", 0)) >= 0.60,
            "generated speech does not meet the published speaker-similarity floor")
    workspace_output = WORKSPACE_ROOT / "media" / payload["generation_id"] / "output.wav"
    require(workspace_output.is_file() and digest(workspace_output.read_bytes()) == digest(wav),
            "Cinder workspace no longer contains the generated WAV")
    return {**record, "wav_object_key": payload["wav_object_key"], "reference_object_key": payload["reference_object_key"]}


def evaluate_relay(payload: dict[str, Any]) -> dict[str, Any]:
    require_fields(payload, "repository", "source_commit", "image_digest", "knative_service", "knative_revision", "domain", "certificate_fingerprint", "health_url")
    require(re.fullmatch(r"[0-9a-f]{40}([0-9a-f]{24})?", payload["source_commit"]) is not None, "source commit is not immutable")
    require(re.fullmatch(r"registry\.keplerops\.lab/cinder/[a-z0-9._/-]+@sha256:[0-9a-f]{64}", payload["image_digest"]) is not None,
            "relay image is not an immutable Cinder Harbor artifact")
    require(payload["health_url"].startswith(f"https://{payload['domain']}/"), "health URL is outside the submitted Cinder domain")
    with tempfile.TemporaryDirectory() as directory:
        checkout_cinder_repository({"repository": payload["repository"], "commit": payload["source_commit"],
                                    "container_digest": payload["image_digest"]}, directory)
    image = json.loads(subprocess.check_output(["docker", "image", "inspect", payload["image_digest"]], timeout=60))[0]
    require(image.get("Config", {}).get("Labels", {}).get("org.opencontainers.image.revision") == payload["source_commit"],
            "Harbor image does not bind the submitted Forgejo revision")
    status_command = ["ssh", "-i", str(CINDER_PUBLISHER_KEY), "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
                      "-o", f"UserKnownHostsFile={CINDER_PUBLISHER_KNOWN_HOSTS}", CINDER_PUBLISHER_HOST,
                      f"status {payload['knative_service']}"]
    initial_status = subprocess.run(status_command, capture_output=True, text=True, timeout=30, check=False)
    require(initial_status.returncode == 0, "submitted Cinder Knative service does not exist")
    native = json.loads(initial_status.stdout)
    require(native.get("owner") == CINDER_OPERATOR, "Knative service is not scoped to the Cinder operator")
    require(native.get("image") == payload["image_digest"], "live Knative image differs from the Harbor digest")
    require(native.get("latest_ready_revision") == payload["knative_revision"], "live Knative revision differs from the lifecycle record")
    context = ssl.create_default_context()
    with socket.create_connection((payload["domain"], 443), timeout=15) as sock:
        with context.wrap_socket(sock, server_hostname=payload["domain"]) as tls:
            fingerprint = hashlib.sha256(tls.getpeercert(binary_form=True)).hexdigest()
    require(fingerprint == payload["certificate_fingerprint"], "live TLS certificate differs from the lifecycle record")
    first = urllib.request.urlopen(payload["health_url"], timeout=30).read()
    try:
        first_record = json.loads(first)
    except json.JSONDecodeError as error:
        raise Rejected("relay health response is not a JSON revision record") from error
    require(first_record.get("source_revision") == payload["source_commit"], "relay response does not identify its Forgejo source revision")
    scaled = False
    for _ in range(24):
        time.sleep(5)
        status = subprocess.run(status_command, capture_output=True, text=True, timeout=30, check=False)
        if status.returncode == 0 and json.loads(status.stdout).get("ready_replicas") == 0:
            scaled = True
            break
    require(scaled, "relay did not reach scale-to-zero")
    second = urllib.request.urlopen(payload["health_url"], timeout=60).read()
    require(json.loads(second).get("source_revision") == payload["source_commit"], "relay revision changed across the cold-start cycle")
    return {**payload, "native_status": native, "certificate_fingerprint": fingerprint, "first_request_sha256": digest(first),
            "post_cold_start_request_sha256": digest(second)}


def evaluate_staging(payload: dict[str, Any]) -> dict[str, Any]:
    require_fields(payload, "repository", "commit", "container_digest", "knative_service", "knative_revision",
                   "route_url", "route_token", "public_model", "artifact_object_keys", "artifact_digests",
                   "manifest_object_key", "signature_object_key", "public_key_object_key")
    require(re.fullmatch(r"https://[a-z0-9][a-z0-9-]{2,40}\.cinder\.lab", payload["route_url"].rstrip("/")) is not None,
            "LiteLLM route is outside the Cinder domain")
    require(payload["route_url"].rstrip("/") != MODEL_URL, "LiteLLM route cannot be the shared model edge")
    require(payload["public_model"] == "glm-5.2", "LiteLLM must expose the staged GLM 5.2 route")

    with tempfile.TemporaryDirectory(prefix="cinder-litellm-") as directory:
        checkout_cinder_repository(payload, directory)
        source_root = Path(directory)
        dockerfile = source_root / "Dockerfile"
        config_file = source_root / "litellm-config.yaml"
        require(dockerfile.is_file() and config_file.is_file(),
                "LiteLLM source must include Dockerfile and litellm-config.yaml")
        require("ghcr.io/berriai/litellm:main-v1.74.9-stable" in dockerfile.read_text(encoding="utf-8"),
                "LiteLLM source does not use the admitted OSS image")
        config = yaml.safe_load(config_file.read_text(encoding="utf-8"))
        require(isinstance(config, dict), "LiteLLM configuration is not a mapping")
        routes = [item for item in config.get("model_list", []) if isinstance(item, dict) and item.get("model_name") == "glm-5.2"]
        require(len(routes) == 1, "LiteLLM configuration must expose exactly one glm-5.2 route")
        params = routes[0].get("litellm_params", {})
        require(params.get("model") == "openai/zai-org/glm-5-maas" and params.get("api_base") == f"{MODEL_URL}/v1",
                "LiteLLM glm-5.2 route does not target the admitted Cinder model edge")
        require(params.get("api_key") == MODEL_TOKEN, "LiteLLM upstream credential is not the scoped Cinder entitlement")
        require(config.get("general_settings", {}).get("master_key") == payload["route_token"],
                "submitted route token differs from the LiteLLM master key")
    status_command = [
        "ssh", "-i", str(CINDER_PUBLISHER_KEY), "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
        "-o", f"UserKnownHostsFile={CINDER_PUBLISHER_KNOWN_HOSTS}", CINDER_PUBLISHER_HOST,
        f"status {payload['knative_service']}",
    ]
    status = subprocess.run(status_command, capture_output=True, text=True, timeout=30, check=False)
    require(status.returncode == 0, "submitted Cinder LiteLLM service does not exist")
    native = json.loads(status.stdout)
    require(native.get("owner") == CINDER_OPERATOR, "LiteLLM service is not scoped to the Cinder operator")
    require(native.get("image") == payload["container_digest"], "live LiteLLM image differs from the Harbor digest")
    require(native.get("latest_ready_revision") == payload["knative_revision"], "live LiteLLM revision differs from the staging record")
    require(f"https://{native.get('domain', '')}" == payload["route_url"].rstrip("/"),
            "LiteLLM route does not map to the submitted Cinder service")

    actual = {key: digest(get_object(key)) for key in payload["artifact_object_keys"]}
    require(actual == payload["artifact_digests"], "staged object digests do not match")
    manifest_bytes = get_object(payload["manifest_object_key"])
    signature = get_object(payload["signature_object_key"])
    public_key = get_object(payload["public_key_object_key"])
    manifest = json.loads(manifest_bytes)
    require(manifest.get("operator") == CINDER_OPERATOR,
            "signed staging manifest lacks Cinder ownership")
    require(manifest.get("artifact_digests") == actual,
            "signed staging manifest does not bind the admitted objects")
    require(manifest.get("route") == payload["route_url"].rstrip("/") and
            manifest.get("upstream") == MODEL_URL and manifest.get("model") == payload["public_model"],
            "signed staging manifest does not bind the LiteLLM route and shared GLM edge")
    require(manifest.get("repository") == payload["repository"] and manifest.get("commit") == payload["commit"] and
            manifest.get("container_digest") == payload["container_digest"] and
            manifest.get("knative_revision") == payload["knative_revision"],
            "signed staging manifest does not bind the deployed source, image, and revision")
    with tempfile.TemporaryDirectory(prefix="cinder-staging-") as directory:
        root = Path(directory)
        (root / "manifest.json").write_bytes(manifest_bytes)
        (root / "manifest.sig").write_bytes(signature)
        (root / "cosign.pub").write_bytes(public_key)
        verification = subprocess.run(
            ["docker", "run", "--rm", "-v", f"{root}:/work:ro", COSIGN_IMAGE,
             "verify-blob", "--key", "/work/cosign.pub", "--signature", "/work/manifest.sig", "/work/manifest.json"],
            capture_output=True, text=True, timeout=120, check=False,
        )
    require(verification.returncode == 0, "Cosign staging-manifest signature did not verify")
    require(MODEL_ACCESS_LOG.is_file(), "Cinder model edge has no access log")
    edge_cursor = len(MODEL_ACCESS_LOG.read_text(encoding="utf-8", errors="replace").splitlines())
    nonce = f"cinder-stage-{uuid.uuid4()}"
    route_response = request_json(
        f"{payload['route_url'].rstrip('/')}/v1/chat/completions", method="POST",
        authorization=f"Bearer {payload['route_token']}",
        payload={"model": payload["public_model"], "messages": [{"role": "user", "content": f"Acknowledge staging probe {nonce}."}], "max_tokens": 24},
    )
    require(route_response.get("id") and route_response.get("choices"), "fresh LiteLLM route request failed")
    edge_record = None
    for _ in range(20):
        lines = MODEL_ACCESS_LOG.read_text(encoding="utf-8", errors="replace").splitlines()[edge_cursor:]
        for line in lines:
            try:
                candidate = json.loads(line)
            except json.JSONDecodeError:
                continue
            request = candidate.get("request", {})
            if request.get("method") == "POST" and request.get("uri") == "/v1/chat/completions" and candidate.get("status") == 200:
                edge_record = candidate
                break
        if edge_record is not None:
            break
        time.sleep(0.5)
    require(edge_record is not None, "fresh LiteLLM request did not reach the attributed Cinder model edge")
    edge_evidence = json.dumps(edge_record, sort_keys=True).encode()
    return {"operator": CINDER_OPERATOR, "upstream": MODEL_URL, "model": payload["public_model"],
            "litellm_request_id": route_response["id"], "route_url": payload["route_url"],
            "source_commit": payload["commit"], "image_digest": payload["container_digest"],
            "knative_service": payload["knative_service"], "knative_revision": payload["knative_revision"],
            "edge_record_sha256": digest(edge_evidence),
            "artifact_digests": actual, "manifest_sha256": digest(manifest_bytes),
            "signer_sha256": digest(public_key)}


Evaluating = Callable[[dict[str, Any]], dict[str, Any]]
CAPABILITIES: dict[str, tuple[str, str, Evaluating]] = {
    "intake-evasion": ("kep-m06-a", "intake-reports", evaluate_intake),
    "command-generation": ("kep-m06-b", "comparison-reports", evaluate_commands),
    "preview-blackbox": ("kep-m06-c", "preview-audits", lambda value: evaluate_preview(value)),
    "preview-transfer": ("kep-m06-d", "preview-audits", lambda value: evaluate_preview(value, transfer=True)),
    "document-human": ("kep-m06-e", "downstream-reports", lambda value: evaluate_document(value, "human")),
    "document-pipeline": ("kep-m06-f", "target-audits", lambda value: evaluate_document(value, "pipeline")),
    "edge-correlation": ("kep-m06-j", "intake-status", evaluate_edge),
    "public-bundle": ("kep-m06-k", "reports", evaluate_public_bundle),
    "workspace-reattachment": ("kep-m06-l", "workspace-reattachments", evaluate_workspace),
    "physical-evaluation": ("kep-m06-m", "physical-evaluations", evaluate_hardware),
    "registrar-order": ("kep-m06-n", "registrar-orders", evaluate_domain),
    "toolchain-validation": ("kep-m06-o", "reports", evaluate_toolchain),
    "model-usage": ("kep-m06-p", "model-usage", evaluate_model_usage),
    "harness-release": ("kep-m06-q", "ci-artifacts", evaluate_harness),
    "whitebox-evaluation": ("kep-m06-r", "whitebox-evaluations", evaluate_whitebox),
    "document-retrieval": ("kep-m06-s", "document-traces", evaluate_retrieval),
    "media-provenance": ("kep-m06-t", "media-registry", evaluate_audio),
    "relay-lifecycle": ("kep-m06-u", "relay-lifecycles", evaluate_relay),
    "staging-validation": ("kep-m06-v", "ci-artifacts", evaluate_staging),
}


def evaluate_pending() -> int:
    processed = 0
    for capability, (operation_id, carrier, evaluator) in CAPABILITIES.items():
        prefix = f"submissions/{capability}/"
        for item in STORE.list_objects(BUCKET, prefix=prefix, recursive=True):
            if not item.object_name.endswith(".json"):
                continue
            submission_id = Path(item.object_name).stem
            report_key = f"{carrier}/{capability}-{submission_id}.json"
            try:
                STORE.stat_object(BUCKET, report_key)
                continue
            except Exception:
                pass
            try:
                payload = json.loads(get_object(item.object_name))
                require(isinstance(payload, dict), "submission must be a JSON object")
                evidence = evaluator(payload)
                report = issued(operation_id, submission_id, evidence)
                put_json(report_key, report)
                if operation_id == "kep-m06-l":
                    reattachment_dir = WORKSPACE_ROOT / ".cinder" / "reattachments"
                    reattachment_dir.mkdir(parents=True, exist_ok=True)
                    (reattachment_dir / f"{submission_id}.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
                if operation_id == "kep-m06-j":
                    status_dir = PUBLIC_ROOT / "intake-status"
                    status_dir.mkdir(parents=True, exist_ok=True)
                    (status_dir / f"{evidence['case_reference']}.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
                if operation_id in {"kep-m06-q", "kep-m06-v"}:
                    actions_dir = Path(os.getenv("FORGEJO_WORKSPACE", ".")) / "reports"
                    actions_dir.mkdir(parents=True, exist_ok=True)
                    (actions_dir / f"{capability}-{submission_id}.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
                processed += 1
                print(f"accepted {capability}/{submission_id}: {report_key}")
            except (Rejected, KeyError, TypeError, ValueError, subprocess.SubprocessError) as error:
                rejection = {"submission_id": submission_id, "capability": capability, "status": "rejected", "evaluated_at": now(), "reason": str(error)}
                put_json(f"attempts/{capability}-{submission_id}.json", rejection)
                print(f"rejected {capability}/{submission_id}: {error}")
    return processed


if __name__ == "__main__":
    count = evaluate_pending()
    print(f"Cinder evaluation completed: {count} new accepted record(s)")
