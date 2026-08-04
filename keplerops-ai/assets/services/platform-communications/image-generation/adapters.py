"""Production adapters for OpenVINO, PostgreSQL, and MinIO."""

from __future__ import annotations

from io import BytesIO
import hashlib
import json
from pathlib import Path
import uuid

from service import GenerationRecord, GenerationRequest


def verify_exported_model(model_path: Path) -> None:
    manifest_path = model_path / "export-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_paths = set()
    for artifact in manifest["files"]:
        path = model_path / artifact["path"]
        expected_paths.add(artifact["path"])
        if not path.is_file() or path.stat().st_size != artifact["size"]:
            raise RuntimeError(f"OpenVINO model artifact size mismatch: {artifact['path']}")
        digest = hashlib.sha256()
        with path.open("rb") as source:
            while chunk := source.read(4 * 1024 * 1024):
                digest.update(chunk)
        if digest.hexdigest() != artifact["sha256"]:
            raise RuntimeError(f"OpenVINO model artifact digest mismatch: {artifact['path']}")
    actual_paths = {
        path.relative_to(model_path).as_posix()
        for path in model_path.rglob("*")
        if path.is_file() and path != manifest_path
    }
    if actual_paths != expected_paths:
        raise RuntimeError("OpenVINO model tree differs from its export manifest")


class OpenVINOImageBackend:
    def __init__(self, model_path: str, device: str = "CPU") -> None:
        self.model_path = Path(model_path)
        self.device = device
        self.pipeline = None

    def initialize(self) -> None:
        verify_exported_model(self.model_path)
        import openvino_genai as ov_genai

        self.pipeline = ov_genai.Text2ImagePipeline(str(self.model_path), self.device)

    def ready(self) -> bool:
        return self.pipeline is not None

    def generate(self, request: GenerationRequest) -> bytes:
        if self.pipeline is None:
            raise RuntimeError("OpenVINO image pipeline is not initialized")
        from PIL import Image

        tensor = self.pipeline.generate(
            request.prompt,
            width=request.width,
            height=request.height,
            num_inference_steps=request.steps,
            rng_seed=request.seed,
            num_images_per_prompt=1,
        )
        image = Image.fromarray(tensor.data[0])
        output = BytesIO()
        image.save(output, format="PNG", optimize=True)
        return output.getvalue()


class PostgresGenerationRepository:
    def __init__(self, dsn: str, schema_path: str) -> None:
        self.dsn = dsn
        self.schema_path = Path(schema_path)

    def _connect(self):
        import psycopg

        return psycopg.connect(self.dsn)

    def initialize(self) -> None:
        schema = self.schema_path.read_text(encoding="utf-8")
        with self._connect() as connection:
            connection.execute(schema)

    def ready(self) -> bool:
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT to_regclass('public.image_generation_jobs')"
                ).fetchone()
            return row == ("image_generation_jobs",)
        except Exception:
            return False

    def get(self, job_id: uuid.UUID) -> GenerationRecord | None:
        from psycopg.rows import dict_row

        query = """
            SELECT job_id, created_at, prompt, seed, width, height, steps,
                   model_id, model_revision, object_key, artifact_sha256,
                   artifact_size, elapsed_ms, reset_generation
              FROM image_generation_jobs
             WHERE job_id = %s
        """
        with self._connect() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(query, (job_id,))
                row = cursor.fetchone()
        return GenerationRecord(**row) if row is not None else None

    def put(self, record: GenerationRecord) -> None:
        query = """
            INSERT INTO image_generation_jobs (
                job_id, created_at, status, prompt, seed, width, height, steps,
                model_id, model_revision, object_key, artifact_sha256,
                artifact_size, elapsed_ms, reset_generation
            ) VALUES (
                %(job_id)s, %(created_at)s, 'succeeded', %(prompt)s, %(seed)s,
                %(width)s, %(height)s, %(steps)s, %(model_id)s, %(model_revision)s,
                %(object_key)s, %(artifact_sha256)s, %(artifact_size)s,
                %(elapsed_ms)s, %(reset_generation)s
            ) ON CONFLICT (job_id) DO NOTHING
        """
        with self._connect() as connection:
            connection.execute(query, record.__dict__)

    def delete_generation(self, reset_generation: int) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM image_generation_jobs WHERE reset_generation = %s",
                (reset_generation,),
            )
            return cursor.rowcount


class MinioArtifactStore:
    def __init__(
        self,
        *,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        secure: bool,
        ca_file: str | None,
    ) -> None:
        from minio import Minio

        http_client = None
        if secure and ca_file:
            import urllib3

            http_client = urllib3.PoolManager(
                cert_reqs="CERT_REQUIRED",
                ca_certs=ca_file,
                retries=urllib3.Retry(total=3, backoff_factor=0.2),
            )
        self.client = Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
            http_client=http_client,
        )
        self.bucket = bucket

    def initialize(self) -> None:
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

    def ready(self) -> bool:
        try:
            return self.client.bucket_exists(self.bucket)
        except Exception:
            return False

    def put(self, object_key: str, content: bytes, content_type: str) -> None:
        self.client.put_object(
            self.bucket,
            object_key,
            BytesIO(content),
            len(content),
            content_type=content_type,
        )

    def get(self, object_key: str) -> bytes:
        response = self.client.get_object(self.bucket, object_key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def delete_prefix(self, prefix: str) -> int:
        count = 0
        for item in self.client.list_objects(self.bucket, prefix=prefix, recursive=True):
            self.client.remove_object(self.bucket, item.object_name)
            count += 1
        return count
