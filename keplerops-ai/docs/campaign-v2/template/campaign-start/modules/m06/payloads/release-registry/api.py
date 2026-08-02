from __future__ import annotations

import hashlib
import hmac
import io
import json
import os
import re
import subprocess
import tempfile
import uuid
import zipfile
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

import httpx
import numpy as np
import yaml
from art.attacks.evasion import FastGradientMethod
from art.estimators.classification import SklearnClassifier
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field, HttpUrl
from sklearn.linear_model import LogisticRegression
from checkpoints import AttemptContext, resolve_parents


FORGEJO = os.environ["CINDER_FORGEJO_URL"].rstrip("/")
FORGEJO_AUTH = (os.environ["CINDER_FORGEJO_USER"], os.environ["CINDER_FORGEJO_PASSWORD"])
HARBOR = os.environ["HARBOR_API_URL"].rstrip("/")
HARBOR_AUTH = (os.environ["HARBOR_USER"], os.environ["HARBOR_PASSWORD"])
PUBLIC_MODEL = os.environ["PUBLIC_MODEL_URL"].rstrip("/")
EDGE = os.environ["MODEL_EDGE_URL"].rstrip("/")
EDGE_TOKEN = os.environ["MODEL_EDGE_TOKEN"]
ROOT = Path("/var/lib/cinder-release-registry")
ARTIFACT_HOSTS = {"git.cinder.lab", "storage.cinder.lab", "keplerops.lab"}
PUBLIC_BUNDLE_ARTIFACT_ROLES = {
    "orion-release-risk.onnx": "model",
    "model.safetensors": "model",
    "tokenizer.json": "model",
    "label-map.json": "model",
    "preprocessing.json": "model",
    "model-card.md": "model",
    "release-metadata.json": "model",
    "orion-release-risk-public.jsonl": "dataset",
    "orion-agent-blueprint.json": "agent",
    "run-orion-kit.py": "agent",
}
app = FastAPI(title="Cinder Release Registry", version="1.0")


class RepositoryRun(BaseModel):
    context: AttemptContext
    repository: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]*/[a-z0-9][a-z0-9._-]*$")
    commit: str = Field(pattern=r"^[0-9a-f]{40,64}$")
    actions_run_id: int = Field(gt=0)
    provenance_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class PublicBundle(RepositoryRun):
    manifest_path: str = Field(pattern=r"^[A-Za-z0-9._/-]+$")


class ToolchainRelease(RepositoryRun):
    image: str = Field(pattern=r"^registry\.keplerops\.lab/cinder/[a-z0-9._/-]+@sha256:[0-9a-f]{64}$")
    lockfile_path: str = Field(pattern=r"^[A-Za-z0-9._/-]+$")
    art_recipe_path: str = Field(pattern=r"^[A-Za-z0-9._/-]+$")
    art_candidate_url: HttpUrl
    ffmpeg_recipe_path: str = Field(pattern=r"^[A-Za-z0-9._/-]+$")
    ffmpeg_output_url: HttpUrl


class HarnessRelease(RepositoryRun):
    image: str = Field(pattern=r"^registry\.keplerops\.lab/cinder/[a-z0-9._/-]+@sha256:[0-9a-f]{64}$")
    harness_manifest_path: str = Field(pattern=r"^[A-Za-z0-9._/-]+$")
    harness_path: str = Field(pattern=r"^ci/validate-orion-harness(\.py)?$")


class StagingRelease(RepositoryRun):
    image: str = Field(pattern=r"^registry\.keplerops\.lab/cinder/[a-z0-9._/-]+@sha256:[0-9a-f]{64}$")
    route_url: HttpUrl
    route_token: str = Field(pattern=r"^sk-[A-Za-z0-9._-]{12,120}$")
    manifest_url: HttpUrl
    signature_url: HttpUrl
    public_key_path: str = Field(pattern=r"^[A-Za-z0-9._/-]+$")
    litellm_config_path: str = Field(pattern=r"^[A-Za-z0-9._/-]+$")
    staged_artifact_urls: list[HttpUrl] = Field(min_length=1, max_length=20)


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


async def forgejo(path: str) -> Any:
    async with httpx.AsyncClient(timeout=30, auth=FORGEJO_AUTH) as client:
        response = await client.get(f"{FORGEJO}/api/v1{path}")
    if response.status_code != 200:
        raise HTTPException(status_code=422, detail=f"Forgejo record is unavailable: {path}")
    return response.json()


async def forgejo_write(method: str, path: str, payload: dict[str, Any]) -> Any:
    async with httpx.AsyncClient(timeout=30, auth=FORGEJO_AUTH) as client:
        response = await client.request(method, f"{FORGEJO}/api/v1{path}", json=payload)
    if response.status_code not in {200, 201, 204}:
        raise HTTPException(status_code=422, detail=f"Forgejo mutation failed: {path}")
    return response.json() if response.content else {}


async def source(repository: str, commit: str, path: str) -> bytes:
    value = await forgejo(f"/repos/{repository}/contents/{quote(path)}?ref={commit}")
    import base64
    try:
        return base64.b64decode(value["content"])
    except (KeyError, ValueError) as error:
        raise HTTPException(status_code=422, detail=f"Forgejo source cannot be decoded: {path}") from error


async def native_run(value: RepositoryRun, operation: str, subjects: dict[str, str]) -> dict[str, Any]:
    workflows = {
        "kep-m06-k": "ci/public-bundle-release.yml",
        "kep-m06-o": "ci/toolchain-release.yml",
        "kep-m06-q": "ci/harness-release.yml",
        "kep-m06-v": "ci/staging-release.yml",
    }
    expected_workflow = workflows[operation]
    commit = await forgejo(f"/repos/{value.repository}/git/commits/{value.commit}")
    run = await forgejo(f"/repos/{value.repository}/actions/runs/{value.actions_run_id}")
    head = run.get("head_sha") or run.get("head_commit", {}).get("id")
    conclusion = run.get("conclusion") or run.get("status")
    workflow = str(run.get("path") or run.get("workflow_id") or "")
    if (
        commit.get("sha", commit.get("id")) != value.commit
        or head != value.commit
        or conclusion not in {"success", "completed"}
        or workflow not in {expected_workflow, Path(expected_workflow).name}
    ):
        raise HTTPException(status_code=422, detail="Forgejo Actions run is not the successful operation-specific workflow for the declared commit")
    listing = await forgejo(f"/repos/{value.repository}/actions/runs/{value.actions_run_id}/artifacts")
    artifacts = listing.get("artifacts") if isinstance(listing, dict) else None
    artifact = next((item for item in artifacts or [] if item.get("name") == f"{operation}-provenance" and not item.get("expired")), None)
    if artifact is None or not isinstance(artifact.get("id"), int):
        raise HTTPException(status_code=422, detail="Actions run lacks its workflow-specific provenance artifact")
    async with httpx.AsyncClient(timeout=30, auth=FORGEJO_AUTH, follow_redirects=True) as client:
        archive = await client.get(f"{FORGEJO}/api/v1/repos/{value.repository}/actions/artifacts/{artifact['id']}/zip")
    if archive.status_code != 200 or len(archive.content) > 4 * 1024 * 1024:
        raise HTTPException(status_code=422, detail="Actions provenance artifact cannot be acquired")
    try:
        with zipfile.ZipFile(io.BytesIO(archive.content)) as bundle:
            names = [name for name in bundle.namelist() if Path(name).name == "provenance.json"]
            if len(names) != 1:
                raise ValueError("one provenance.json is required")
            provenance_bytes = bundle.read(names[0])
        provenance = json.loads(provenance_bytes)
    except (ValueError, KeyError, zipfile.BadZipFile, json.JSONDecodeError) as error:
        raise HTTPException(status_code=422, detail="Actions provenance artifact is invalid") from error
    if (
        sha256(provenance_bytes) != value.provenance_sha256
        or provenance.get("schema") != "cinder.actions-provenance/v1"
        or provenance.get("operation") != operation
        or provenance.get("workflow") != expected_workflow
        or provenance.get("repository") != value.repository
        or provenance.get("commit") != value.commit
        or provenance.get("actions_run_id") != value.actions_run_id
        or provenance.get("subjects") != subjects
    ):
        raise HTTPException(status_code=422, detail="Actions provenance does not bind the workflow's exact input and output digests")
    return {"repository": value.repository, "commit": value.commit, "actions_run_id": value.actions_run_id,
            "workflow": expected_workflow, "provenance_sha256": value.provenance_sha256, "provenance_subjects": subjects}


async def acquire(url: HttpUrl | str, *, maximum: int = 64 * 1024 * 1024) -> bytes:
    parsed = urlparse(str(url))
    if parsed.scheme != "https" or parsed.hostname not in ARTIFACT_HOSTS:
        raise HTTPException(status_code=422, detail="release artifact is not on an admitted owning source")
    auth = FORGEJO_AUTH if parsed.hostname == "git.cinder.lab" else None
    async with httpx.AsyncClient(timeout=90, follow_redirects=True, auth=auth) as client:
        response = await client.get(str(url))
    if response.status_code != 200 or len(response.content) > maximum:
        raise HTTPException(status_code=422, detail=f"release artifact cannot be reacquired: {parsed.path}")
    return response.content


async def harbor(image: str) -> dict[str, Any]:
    repository, digest = image.split("/cinder/", 1)[1].split("@", 1)
    path = f"/projects/cinder/repositories/{quote(repository, safe='')}/artifacts/{quote(digest, safe='')}"
    async with httpx.AsyncClient(timeout=30, auth=HARBOR_AUTH) as client:
        response = await client.get(f"{HARBOR}{path}")
    if response.status_code != 200 or response.json().get("digest") != digest:
        raise HTTPException(status_code=422, detail="immutable image is absent from Cinder Harbor")
    return response.json()


def image_revision(image: dict[str, Any]) -> str:
    config = (image.get("extra_attrs") or {}).get("config") or {}
    labels = config.get("labels") or config.get("Labels") or {}
    return str(labels.get("org.opencontainers.image.revision") or "")


def execute_toolchain_image(
    image: str,
    clean: np.ndarray,
    eps: float,
    source_media: bytes,
    ffmpeg_args: list[str],
) -> tuple[dict[str, str], bytes, bytes]:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        copied = subprocess.run(
            ["skopeo", "copy", "--src-creds", f"{HARBOR_AUTH[0]}:{HARBOR_AUTH[1]}",
             f"docker://{image}", f"oci:{root / 'image'}:toolchain"],
            capture_output=True, text=True, timeout=180, check=False,
        )
        if copied.returncode != 0:
            raise HTTPException(status_code=422, detail="declared Harbor toolchain image cannot be acquired")
        unpacked = subprocess.run(
            ["umoci", "unpack", "--rootless", "--image", f"{root / 'image'}:toolchain", str(root / "bundle")],
            capture_output=True, text=True, timeout=120, check=False,
        )
        filesystem = root / "bundle" / "rootfs"
        if unpacked.returncode != 0 or not filesystem.is_dir():
            raise HTTPException(status_code=422, detail="declared Harbor toolchain image cannot be unpacked rootlessly")
        python_path = next((path for path in ("/usr/local/bin/python", "/usr/bin/python3") if (filesystem / path.lstrip("/")).is_file()), "")
        if not python_path or not (filesystem / "usr/bin/ffmpeg").is_file():
            raise HTTPException(status_code=422, detail="declared toolchain image lacks Python ART or ffmpeg")
        work = root / "work"
        work.mkdir()
        np.save(work / "clean.npy", clean)
        (work / "source-media").write_bytes(source_media)
        (work / "run-art.py").write_text(
            "import json,numpy as np\n"
            "from art.attacks.evasion import FastGradientMethod\n"
            "from art.estimators.classification import SklearnClassifier\n"
            "from sklearn.linear_model import LogisticRegression\n"
            "x=np.array([[0,0],[0,1],[1,0],[1,1]],dtype=np.float32)\n"
            "y=np.array([0,1,1,1])\n"
            "est=SklearnClassifier(model=LogisticRegression(random_state=0).fit(x,y))\n"
            f"out=FastGradientMethod(estimator=est,eps={eps!r}).generate(x=np.load('/work/clean.npy'))\n"
            "np.save('/work/candidate.npy',out)\n"
            "import art; print(json.dumps({'art':art.__version__}))\n"
        )
        art = subprocess.run(
            ["proot", "-R", str(filesystem), "-b", f"{work}:/work", python_path, "/work/run-art.py"],
            capture_output=True, text=True, timeout=60, check=False,
        )
        ffmpeg = subprocess.run(
            ["proot", "-R", str(filesystem), "-b", f"{work}:/work", "/usr/bin/ffmpeg", "-v", "error",
             "-i", "/work/source-media", *ffmpeg_args, "-y", "/work/output.wav"],
            capture_output=True, text=True, timeout=60, check=False,
        )
        ffmpeg_version = subprocess.run(
            ["proot", "-R", str(filesystem), "/usr/bin/ffmpeg", "-version"],
            capture_output=True, text=True, timeout=30, check=False,
        )
        image_candidate = (work / "candidate.npy").read_bytes() if (work / "candidate.npy").is_file() else b""
        image_media = (work / "output.wav").read_bytes() if (work / "output.wav").is_file() else b""
    try:
        art_version = json.loads(art.stdout)["art"]
    except (json.JSONDecodeError, KeyError):
        art_version = ""
    if (art.returncode != 0 or art_version != "1.20.1" or ffmpeg.returncode != 0
            or ffmpeg_version.returncode != 0 or not ffmpeg_version.stdout.startswith("ffmpeg version")
            or not image_candidate or not image_media):
        raise HTTPException(status_code=422, detail="declared image did not execute the locked ART and ffmpeg recipes")
    return ({"art_version": art_version, "art_probe_sha256": sha256(art.stdout.encode()),
             "art_output_sha256": sha256(image_candidate), "ffmpeg_output_sha256": sha256(image_media),
             "ffmpeg_version_sha256": sha256(ffmpeg_version.stdout.splitlines()[0].encode())},
            image_candidate, image_media)


async def predict(text: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(f"{PUBLIC_MODEL}/v1/models/orion-release-risk:predict", json={"instances": [{"text": text}]})
    if response.status_code != 200:
        raise HTTPException(status_code=503, detail="public Orion model is unavailable")
    return response.json()["predictions"][0]


def persist(kind: str, record: dict[str, Any], flag_name: str) -> dict[str, Any]:
    release_id = str(uuid.uuid4())
    identities = {
        "public-bundle-release": ("kep-m06-k", "release-risk"),
        "toolchain-release": ("kep-m06-o", "release-risk"),
        "harness-release": ("kep-m06-q", "release-risk"),
        "staging-release": ("kep-m06-v", "attacker-glm"),
    }
    operation, model_family = identities[kind]
    record.update({"schema": f"cinder.{kind}/v1", "operation": operation,
                   "model_family": model_family, "release_id": release_id,
                   "flag": os.environ[flag_name]})
    directory = ROOT / kind
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{release_id}.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return record


def checkpoint_context(request: RepositoryRun, parents: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "attempt_id": str(request.context.attempt_id),
        "actor": request.context.actor,
        "parent_checkpoints": [
            {key: item[key] for key in ("operation", "locator", "sha256", "schema", "actor", "attempt_id")} for item in parents
        ],
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ready", "registry": "Cinder Releases"}


@app.post("/v1/repositories/{repository}/credentials")
async def repository_credentials(repository: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    import base64
    expected = "Basic " + base64.b64encode(f"{FORGEJO_AUTH[0]}:{FORGEJO_AUTH[1]}".encode()).decode()
    if authorization is None or not hmac.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="assigned Cinder Forgejo identity required")
    if re.fullmatch(r"[a-z0-9][a-z0-9._-]{2,60}", repository) is None:
        raise HTTPException(status_code=404)
    full_name = f"cinder-field-operator/{repository}"
    forgejo_repository = await forgejo(f"/repos/{full_name}")
    if (
        forgejo_repository.get("full_name") != full_name
        or (forgejo_repository.get("owner") or {}).get("login") != "cinder-field-operator"
    ):
        raise HTTPException(status_code=422, detail="registry credentials are issued only to the assigned operator's repository")
    robot_suffixes = (f"+m06-{repository}", f"$m06-{repository}")
    async with httpx.AsyncClient(timeout=30, auth=HARBOR_AUTH) as client:
        robots_response = await client.get(f"{HARBOR}/robots", params={"page": 1, "page_size": 100})
        if robots_response.status_code != 200:
            raise HTTPException(status_code=503, detail="Harbor robot inventory is unavailable")
        for robot in robots_response.json():
            if str(robot.get("name", "")).endswith(robot_suffixes):
                deleted = await client.delete(f"{HARBOR}/robots/{robot['id']}")
                if deleted.status_code not in {200, 204}:
                    raise HTTPException(status_code=503, detail="prior repository credential could not be rotated")
        created = await client.post(f"{HARBOR}/robots", json={
            "name": f"m06-{repository}", "description": f"Cinder Actions for cinder/{repository}",
            "duration": -1, "level": "system", "permissions": [{
                "kind": "project", "namespace": f"cinder/{repository}",
                "access": [{"resource": "repository", "action": "pull"}, {"resource": "repository", "action": "push"}],
            }],
        })
    if created.status_code != 201:
        raise HTTPException(status_code=503, detail="repository-scoped Harbor credential could not be issued")
    robot = created.json()
    robot_name, robot_secret = str(robot.get("name", "")), str(robot.get("secret", ""))
    if not robot_name or not robot_secret:
        raise HTTPException(status_code=503, detail="Harbor omitted the repository credential")
    await forgejo_write("PUT", f"/repos/{full_name}/actions/secrets/CINDER_REGISTRY_USER", {"data": robot_name})
    await forgejo_write("PUT", f"/repos/{full_name}/actions/secrets/CINDER_REGISTRY_PASSWORD", {"data": robot_secret})
    credential_id = str(uuid.uuid4())
    record = {"schema": "cinder.repository-registry-credential/v1", "credential_id": credential_id,
              "repository": full_name, "harbor_namespace": f"cinder/{repository}", "robot": robot_name,
              "actions_secrets": ["CINDER_REGISTRY_USER", "CINDER_REGISTRY_PASSWORD"]}
    path = ROOT / "repository-credentials" / f"{credential_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return record


@app.get("/v1/repositories/{repository}/credentials")
def get_repository_credentials(repository: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    import base64
    expected = "Basic " + base64.b64encode(f"{FORGEJO_AUTH[0]}:{FORGEJO_AUTH[1]}".encode()).decode()
    if authorization is None or not hmac.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="assigned Cinder Forgejo identity required")
    if re.fullmatch(r"[a-z0-9][a-z0-9._-]{2,60}", repository) is None:
        raise HTTPException(status_code=404)
    records = [json.loads(path.read_text()) for path in sorted((ROOT / "repository-credentials").glob("*.json"))]
    match = next((item for item in reversed(records) if item.get("repository") == f"cinder-field-operator/{repository}"), None)
    if match is None:
        raise HTTPException(status_code=404)
    return match


@app.post("/v1/public-bundles")
async def public_bundle(request: PublicBundle) -> dict[str, Any]:
    parents = await resolve_parents(request.context, {"kep-m06-g", "kep-m06-h"}, mode="any")
    try:
        manifest_bytes = await source(request.repository, request.commit, request.manifest_path)
        manifest = json.loads(manifest_bytes)
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=422, detail="bundle manifest is not JSON") from error
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or len(artifacts) != len(PUBLIC_BUNDLE_ARTIFACT_ROLES):
        raise HTTPException(status_code=422, detail="bundle must contain the exact ten-artifact Orion public kit")
    try:
        artifact_roles = {str(item["name"]): str(item["role"]) for item in artifacts}
    except (KeyError, TypeError) as error:
        raise HTTPException(status_code=422, detail="bundle artifact identity is incomplete") from error
    if artifact_roles != PUBLIC_BUNDLE_ARTIFACT_ROLES or len(artifact_roles) != len(artifacts):
        raise HTTPException(status_code=422, detail="bundle artifact names and roles differ from the Orion public kit")
    acquired: list[dict[str, str]] = []
    acquired_bytes: dict[str, bytes] = {}
    for item in artifacts:
        if set(item) != {"name", "role", "url", "sha256"}:
            raise HTTPException(status_code=422, detail=f"bundle artifact contract is invalid: {item.get('name')}")
        raw = await acquire(item["url"])
        if sha256(raw) != item.get("sha256"):
            raise HTTPException(status_code=422, detail=f"published digest mismatch: {item.get('name')}")
        acquired.append({"name": item["name"], "role": item["role"], "sha256": sha256(raw)})
        acquired_bytes[item["name"]] = raw
    runners = [item["name"] for item in artifacts if item["role"] == "agent" and item["name"].endswith(".py")]
    if len(runners) != 1:
        raise HTTPException(status_code=422, detail="bundle requires one executable agent entrypoint")
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        for name, raw in acquired_bytes.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        completed = subprocess.run(
            ["python", str(root / runners[0])], cwd=root, capture_output=True, text=True, timeout=180, check=False
        )
        output_path = root / "orion-public-output.json"
        if completed.returncode != 0 or not output_path.is_file():
            raise HTTPException(status_code=422, detail="published model/data/agent bundle did not execute")
        executions = json.loads(output_path.read_text())
    if not isinstance(executions, list) or len(executions) != 8 or not all(set(item) >= {"id", "label"} for item in executions):
        raise HTTPException(status_code=422, detail="bundle must produce eight native reference executions")
    role_digests = {
        role: sha256("\n".join(sorted(item["sha256"] for item in acquired if item["role"] == role)).encode())
        for role in ("model", "dataset", "agent")
    }
    execution_sha256 = sha256(json.dumps(executions, sort_keys=True, separators=(",", ":")).encode())
    native = await native_run(request, "kep-m06-k", {
        "bundle_manifest_sha256": sha256(manifest_bytes), "executions_sha256": execution_sha256,
        **{f"{role}_digest": digest for role, digest in role_digests.items()},
    })
    return persist("public-bundle-release", native | checkpoint_context(request, parents) | {
        "artifacts": acquired, "digest_map": role_digests, "executions": executions,
        "executions_sha256": execution_sha256, "runner_stdout_sha256": sha256(completed.stdout.encode()),
    }, "PUBLIC_BUNDLE_FLAG")


@app.post("/v1/toolchain-releases")
async def toolchain_release(request: ToolchainRelease) -> dict[str, Any]:
    parents = await resolve_parents(request.context, {"kep-m06-k", "kep-m06-l"})
    image = await harbor(request.image)
    try:
        art_recipe_bytes = await source(request.repository, request.commit, request.art_recipe_path)
        ffmpeg_recipe_bytes = await source(request.repository, request.commit, request.ffmpeg_recipe_path)
        lockfile_bytes = await source(request.repository, request.commit, request.lockfile_path)
        art_recipe = json.loads(art_recipe_bytes)
        ffmpeg_recipe = json.loads(ffmpeg_recipe_bytes)
        lockfile = lockfile_bytes.decode()
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=422, detail="tool recipe is not JSON") from error
    if "adversarial-robustness-toolbox==1.20.1" not in lockfile or "ffmpeg" not in lockfile:
        raise HTTPException(status_code=422, detail="declared lockfile does not pin the executed upstream tools")
    candidate = np.load(__import__("io").BytesIO(await acquire(request.art_candidate_url)))
    clean = np.asarray(art_recipe.get("clean"), dtype=np.float32)
    eps = float(art_recipe.get("eps", 0))
    training_x = np.asarray([[0, 0], [0, 1], [1, 0], [1, 1]], dtype=np.float32)
    training_y = np.asarray([0, 1, 1, 1])
    estimator = SklearnClassifier(model=LogisticRegression(random_state=0).fit(training_x, training_y))
    reproduced = FastGradientMethod(estimator=estimator, eps=eps).generate(x=clean)
    if art_recipe.get("upstream") != "art.attacks.evasion.FastGradientMethod" or candidate.shape != reproduced.shape or not np.allclose(candidate, reproduced, atol=1e-6):
        raise HTTPException(status_code=422, detail="ART candidate is not the output of the declared upstream example")
    source_media = await acquire(ffmpeg_recipe["source_url"])
    expected_media = await acquire(request.ffmpeg_output_url)
    args = ffmpeg_recipe.get("args")
    if not isinstance(args, list) or any(not isinstance(item, str) for item in args) or any(item.startswith("-") and item not in {"-ac", "-ar", "-c:a", "-y"} for item in args):
        raise HTTPException(status_code=422, detail="ffmpeg recipe is outside the admitted deterministic transform")
    if image_revision(image) != request.commit:
        raise HTTPException(status_code=422, detail="Harbor toolchain image is not bound to the Forgejo commit")
    image_execution, image_candidate, image_media = execute_toolchain_image(request.image, clean, eps, source_media, args)
    try:
        executed_candidate = np.load(__import__("io").BytesIO(image_candidate))
    except (ValueError, OSError) as error:
        raise HTTPException(status_code=422, detail="declared image emitted an invalid ART candidate") from error
    if executed_candidate.shape != candidate.shape or not np.allclose(executed_candidate, candidate, atol=1e-6):
        raise HTTPException(status_code=422, detail="declared image ART execution does not match the submitted candidate")
    if sha256(image_media) != sha256(expected_media):
        raise HTTPException(status_code=422, detail="declared image ffmpeg execution does not match the submitted output")
    with tempfile.TemporaryDirectory() as directory:
        source_path, output_path = Path(directory) / "source", Path(directory) / "output.wav"
        source_path.write_bytes(source_media)
        completed = subprocess.run(["ffmpeg", "-v", "error", "-i", str(source_path), *args, "-y", str(output_path)], capture_output=True, timeout=60, check=False)
        reproduced_media = output_path.read_bytes() if completed.returncode == 0 and output_path.is_file() else b""
    if not reproduced_media or sha256(reproduced_media) != sha256(expected_media):
        raise HTTPException(status_code=422, detail="ffmpeg output cannot be reproduced from the upstream recipe")
    native = await native_run(request, "kep-m06-o", {
        "image_digest": image["digest"], "lockfile_sha256": sha256(lockfile_bytes),
        "art_recipe_sha256": sha256(art_recipe_bytes), "art_output_sha256": sha256(candidate.tobytes()),
        "ffmpeg_recipe_sha256": sha256(ffmpeg_recipe_bytes), "ffmpeg_output_sha256": sha256(expected_media),
    })
    return persist("toolchain-release", native | checkpoint_context(request, parents) | {
                    "image_digest": image["digest"], "lockfile_sha256": sha256(lockfile.encode()),
                    "art_output_sha256": sha256(candidate.tobytes()), "ffmpeg_output_sha256": sha256(expected_media),
                    "image_execution": image_execution,
                    "upstream_tools": ["adversarial-robustness-toolbox", "ffmpeg"]}, "TOOLCHAIN_FLAG")


@app.post("/v1/harness-releases")
async def harness_release(request: HarnessRelease) -> dict[str, Any]:
    parents = await resolve_parents(request.context, {"kep-m06-k", "kep-m06-p"})
    image = await harbor(request.image)
    try:
        manifest_bytes = await source(request.repository, request.commit, request.harness_manifest_path)
        manifest = json.loads(manifest_bytes)
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=422, detail="harness manifest is not JSON") from error
    harness = await source(request.repository, request.commit, request.harness_path)
    clean, candidate = await acquire(manifest["clean_url"]), await acquire(manifest["candidate_url"])
    clean_result, candidate_result = await predict(clean.decode()), await predict(candidate.decode())
    if clean == candidate or candidate_result.get("label") != manifest.get("target_label") or clean_result.get("label") == manifest.get("target_label"):
        raise HTTPException(status_code=422, detail="target-specific harness does not reproduce its declared effect")
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        path = root / Path(request.harness_path).name
        path.write_bytes(harness); path.chmod(0o500)
        (root / "clean.txt").write_bytes(clean); (root / "candidate.txt").write_bytes(candidate)
        command = ["python", str(path)] if path.suffix == ".py" else [str(path)]
        completed = subprocess.run(
            command, cwd=root,
            env={"PATH": "/usr/local/bin:/usr/bin:/bin", "CLEAN_INPUT": str(root / "clean.txt"),
                 "CANDIDATE_INPUT": str(root / "candidate.txt"), "ORION_MODEL_URL": PUBLIC_MODEL},
            capture_output=True, text=True, timeout=120, check=False,
        )
    if completed.returncode != 0:
        raise HTTPException(status_code=422, detail="committed ci/validate-orion-harness did not execute successfully")
    try:
        harness_report = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=422, detail="committed harness did not emit its native JSON run record") from error
    if (
        harness_report.get("schema") != "cinder.orion-harness-run/v1"
        or harness_report.get("clean_sha256") != sha256(clean)
        or harness_report.get("candidate_sha256") != sha256(candidate)
        or harness_report.get("clean_output", {}).get("label") != clean_result.get("label")
        or harness_report.get("candidate_output", {}).get("label") != candidate_result.get("label")
    ):
        raise HTTPException(status_code=422, detail="committed harness output does not bind exact inputs and Orion responses")
    if image_revision(image) != request.commit:
        raise HTTPException(status_code=422, detail="Harbor image configuration is not bound to the Forgejo commit")
    native = await native_run(request, "kep-m06-q", {
        "image_digest": image["digest"], "harness_manifest_sha256": sha256(manifest_bytes),
        "harness_sha256": sha256(harness), "harness_output_sha256": sha256(completed.stdout.encode()),
        "clean_sha256": sha256(clean), "candidate_sha256": sha256(candidate),
    })
    return persist("harness-release", native | checkpoint_context(request, parents) | {
                    "image_digest": image["digest"], "harness_sha256": sha256(harness),
                    "harness_stdout_sha256": sha256(completed.stdout.encode()), "clean_sha256": sha256(clean),
                    "candidate_sha256": sha256(candidate), "harness_run": harness_report,
                    "clean_output": clean_result, "candidate_output": candidate_result}, "HARNESS_FLAG")


@app.post("/v1/staging-releases")
async def staging_release(request: StagingRelease) -> dict[str, Any]:
    parents = await resolve_parents(request.context, {"kep-m06-n", "kep-m06-u", "kep-m06-q"})
    image = await harbor(request.image)
    manifest_bytes, signature = await acquire(request.manifest_url), await acquire(request.signature_url)
    public_key = await source(request.repository, request.commit, request.public_key_path)
    config_bytes = await source(request.repository, request.commit, request.litellm_config_path)
    try:
        litellm_config = yaml.safe_load(config_bytes)
    except yaml.YAMLError as error:
        raise HTTPException(status_code=422, detail="committed LiteLLM configuration is not YAML") from error
    models = litellm_config.get("model_list") if isinstance(litellm_config, dict) else None
    if (
        not isinstance(models, list) or len(models) != 1 or not isinstance(models[0], dict)
        or models[0].get("model_name") != "glm-5.2"
        or (models[0].get("litellm_params") or {}).get("model") != "openai/zai-org/glm-5-maas"
        or (models[0].get("litellm_params") or {}).get("api_base") != "https://model.cinder.lab/v1"
        or (models[0].get("litellm_params") or {}).get("api_key") != "os.environ/CINDER_GLM_SERVICE_CREDENTIAL"
    ):
        raise HTTPException(status_code=422, detail="committed LiteLLM configuration does not expose the assigned Cinder GLM service route")
    with tempfile.TemporaryDirectory() as directory:
        manifest_path, signature_path, key_path = Path(directory) / "manifest.json", Path(directory) / "manifest.sig", Path(directory) / "cosign.pub"
        manifest_path.write_bytes(manifest_bytes); signature_path.write_bytes(signature); key_path.write_bytes(public_key)
        verified = subprocess.run(["cosign", "verify-blob", "--key", str(key_path), "--signature", str(signature_path), str(manifest_path)], capture_output=True, timeout=30, check=False)
    if verified.returncode != 0:
        raise HTTPException(status_code=422, detail="staging manifest signature is invalid")
    try:
        manifest = json.loads(manifest_bytes)
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=422, detail="staging manifest is not JSON") from error
    artifacts = [await acquire(url) for url in request.staged_artifact_urls]
    expected = manifest.get("artifacts", {})
    observed = {urlparse(str(url)).path.rsplit("/", 1)[-1]: sha256(raw) for url, raw in zip(request.staged_artifact_urls, artifacts)}
    if manifest.get("source_commit") != request.commit or manifest.get("image") != request.image or manifest.get("route") != str(request.route_url).rstrip("/") or expected != observed:
        raise HTTPException(status_code=422, detail="signed staging manifest does not bind native source, image, route, and artifact bytes")
    native = await native_run(request, "kep-m06-v", {
        "image_digest": image["digest"], "manifest_sha256": sha256(manifest_bytes),
        "signature_sha256": sha256(signature), "public_key_sha256": sha256(public_key),
        "litellm_config_sha256": sha256(config_bytes),
        "staged_artifacts_sha256": sha256(json.dumps(observed, sort_keys=True, separators=(",", ":")).encode()),
    })
    ownership = next(item["record"] for item in parents if item["operation"] == "kep-m06-n")
    lifecycle = next(item["record"] for item in parents if item["operation"] == "kep-m06-u")
    if (
        ownership.get("service_url", "").rstrip("/") != str(request.route_url).rstrip("/")
        or lifecycle.get("domain") != urlparse(str(request.route_url)).hostname
        or lifecycle.get("image") != request.image
        or lifecycle.get("source_commit") != request.commit
    ):
        raise HTTPException(status_code=422, detail="domain ownership, Knative revision, image, and staging route do not form one chain")
    live_started_ns = __import__("time").time_ns()
    live_messages = [{"role": "user", "content": "Identify the Orion release family in one sentence."}]
    async with httpx.AsyncClient(timeout=90) as client:
        live = await client.post(f"{str(request.route_url).rstrip('/')}/v1/chat/completions", headers={"Authorization": f"Bearer {request.route_token}"},
                                 json={"model": "glm-5.2", "messages": live_messages})
    if live.status_code != 200:
        raise HTTPException(status_code=422, detail="live LiteLLM route did not return a GLM response")
    live_body = live.json()
    provider_request = live.headers.get("x-cinder-provider-request") or str(live_body.get("id", ""))
    async with httpx.AsyncClient(timeout=15) as client:
        edge = await client.get(f"{EDGE}/v1/usage", params={"provider_request_id": provider_request}, headers={"Authorization": f"Bearer {EDGE_TOKEN}"})
    edge_record = edge.json() if edge.status_code == 200 else {}
    edge_started_ns = edge_record.get("started_ns")
    edge_completed_ns = edge_record.get("completed_ns")
    expected_request_digest = sha256(json.dumps(
        {"messages": live_messages, "model": "glm-5.2"}, sort_keys=True, separators=(",", ":")
    ).encode())
    expected_response_digest = sha256((json.dumps(live_body, indent=2, sort_keys=True) + "\n").encode())
    observed_ns = __import__("time").time_ns()
    if (
        edge.status_code != 200
        or not str(edge_record.get("range_id", "")).startswith("range-")
        or edge_record.get("provider_request_id") != provider_request
        or edge_record.get("response_id") != str(live_body.get("id", ""))
        or edge_record.get("request_digest") != expected_request_digest
        or edge_record.get("response_digest") != expected_response_digest
        or edge_record.get("credential_class") != "service"
        or edge_record.get("actor") != "cinder-field-operator-service"
        or not str(edge_record.get("assertion_key_id", "")).startswith("m06-")
        or not isinstance(edge_started_ns, int) or edge_started_ns < live_started_ns
        or not isinstance(edge_completed_ns, int) or edge_completed_ns < edge_started_ns or edge_completed_ns > observed_ns
    ):
        raise HTTPException(status_code=422, detail="live route cannot be joined to a fresh attributed Cinder GLM edge record")
    return persist("staging-release", native | checkpoint_context(request, parents) | {"image_digest": image["digest"], "route": str(request.route_url),
                    "manifest_sha256": sha256(manifest_bytes), "litellm_config_sha256": sha256(config_bytes),
                    "litellm_model": "glm-5.2", "artifact_digests": observed,
                    "provider_request_id": provider_request, "edge_usage_id": edge_record["usage_id"],
                    "edge_range_id": edge_record["range_id"], "edge_actor": edge_record["actor"],
                    "edge_credential_class": edge_record["credential_class"],
                    "edge_request_digest": edge_record["request_digest"],
                    "edge_response_digest": edge_record["response_digest"],
                    "edge_started_ns": edge_started_ns, "edge_completed_ns": edge_completed_ns}, "STAGING_FLAG")


@app.get("/v1/{kind}")
def list_releases(kind: str) -> list[dict[str, Any]]:
    mapping = {
        "public-bundles": "public-bundle-release", "toolchain-releases": "toolchain-release",
        "harness-releases": "harness-release", "staging-releases": "staging-release",
    }
    if kind not in mapping:
        raise HTTPException(status_code=404)
    return [json.loads(path.read_text()) for path in sorted((ROOT / mapping[kind]).glob("*.json"))]


@app.get("/v1/{kind}/{release_id}")
def get_release(kind: str, release_id: uuid.UUID) -> dict[str, Any]:
    mapping = {
        "public-bundles": "public-bundle-release", "toolchain-releases": "toolchain-release",
        "harness-releases": "harness-release", "staging-releases": "staging-release",
    }
    if kind not in mapping:
        raise HTTPException(status_code=404)
    path = ROOT / mapping[kind] / f"{release_id}.json"
    if not path.is_file():
        raise HTTPException(status_code=404)
    return json.loads(path.read_text())
