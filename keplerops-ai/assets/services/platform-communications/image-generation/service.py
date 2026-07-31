"""Storage-independent orchestration for real image generation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from typing import Callable, Protocol
import time
import uuid


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
IDEMPOTENCY_NAMESPACE = uuid.UUID("6ec16e74-e1e0-5a5f-9e59-6f47844e9e83")


@dataclass(frozen=True)
class GenerationRequest:
    prompt: str
    seed: int = 0
    width: int = 512
    height: int = 512
    steps: int = 4
    client_request_id: str | None = None

    def validate(self) -> None:
        if not self.prompt.strip() or len(self.prompt) > 2_000:
            raise ValueError("prompt length must be between 1 and 2000 characters")
        if not 0 <= self.seed <= 2**63 - 1:
            raise ValueError("seed must be between 0 and 2^63-1")
        for name, value in (("width", self.width), ("height", self.height)):
            if value < 256 or value > 1024 or value % 64:
                raise ValueError(f"{name} must be a multiple of 64 between 256 and 1024")
        if self.steps < 1 or self.steps > 12:
            raise ValueError("steps must be between 1 and 12")
        if self.client_request_id is not None and (
            not self.client_request_id or len(self.client_request_id) > 128
        ):
            raise ValueError("client_request_id must be between 1 and 128 characters")


@dataclass(frozen=True)
class GenerationRecord:
    job_id: uuid.UUID
    created_at: datetime
    prompt: str
    seed: int
    width: int
    height: int
    steps: int
    model_id: str
    model_revision: str
    object_key: str
    artifact_sha256: str
    artifact_size: int
    elapsed_ms: int
    reset_generation: int

    def matches(self, request: GenerationRequest, reset_generation: int) -> bool:
        return (
            self.prompt == request.prompt
            and self.seed == request.seed
            and self.width == request.width
            and self.height == request.height
            and self.steps == request.steps
            and self.reset_generation == reset_generation
        )


class ImageBackend(Protocol):
    def initialize(self) -> None: ...

    def generate(self, request: GenerationRequest) -> bytes: ...

    def ready(self) -> bool: ...


class GenerationRepository(Protocol):
    def initialize(self) -> None: ...

    def ready(self) -> bool: ...

    def get(self, job_id: uuid.UUID) -> GenerationRecord | None: ...

    def put(self, record: GenerationRecord) -> None: ...

    def delete_generation(self, reset_generation: int) -> int: ...


class ArtifactStore(Protocol):
    def initialize(self) -> None: ...

    def ready(self) -> bool: ...

    def put(self, object_key: str, content: bytes, content_type: str) -> None: ...

    def get(self, object_key: str) -> bytes: ...

    def delete_prefix(self, prefix: str) -> int: ...


class GenerationService:
    def __init__(
        self,
        *,
        backend: ImageBackend,
        repository: GenerationRepository,
        artifact_store: ArtifactStore,
        model_id: str,
        model_revision: str,
        reset_generation: int,
        id_factory: Callable[[], uuid.UUID] = uuid.uuid4,
        wall_clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        monotonic_clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if reset_generation < 0:
            raise ValueError("reset_generation must not be negative")
        self.backend = backend
        self.repository = repository
        self.artifact_store = artifact_store
        self.model_id = model_id
        self.model_revision = model_revision
        self.reset_generation = reset_generation
        self.id_factory = id_factory
        self.wall_clock = wall_clock
        self.monotonic_clock = monotonic_clock

    def initialize(self) -> None:
        self.repository.initialize()
        self.artifact_store.initialize()
        self.backend.initialize()

    def ready(self) -> bool:
        return self.backend.ready() and self.repository.ready() and self.artifact_store.ready()

    def _job_id(self, request: GenerationRequest) -> uuid.UUID:
        if request.client_request_id:
            stable_name = f"{self.reset_generation}:{request.client_request_id}"
            return uuid.uuid5(IDEMPOTENCY_NAMESPACE, stable_name)
        return self.id_factory()

    def generate(self, request: GenerationRequest) -> GenerationRecord:
        request.validate()
        job_id = self._job_id(request)
        existing = self.repository.get(job_id)
        if existing is not None:
            if not existing.matches(request, self.reset_generation):
                raise ValueError("client_request_id was already used for a different request")
            return existing

        started = self.monotonic_clock()
        content = self.backend.generate(request)
        if not content.startswith(PNG_SIGNATURE):
            raise RuntimeError("image backend did not produce PNG data")
        elapsed_ms = max(0, round((self.monotonic_clock() - started) * 1_000))
        artifact_sha256 = hashlib.sha256(content).hexdigest()
        object_key = f"generated/{self.reset_generation}/{job_id}.png"
        self.artifact_store.put(object_key, content, "image/png")
        record = GenerationRecord(
            job_id=job_id,
            created_at=self.wall_clock(),
            prompt=request.prompt,
            seed=request.seed,
            width=request.width,
            height=request.height,
            steps=request.steps,
            model_id=self.model_id,
            model_revision=self.model_revision,
            object_key=object_key,
            artifact_sha256=artifact_sha256,
            artifact_size=len(content),
            elapsed_ms=elapsed_ms,
            reset_generation=self.reset_generation,
        )
        self.repository.put(record)
        return record

    def get_artifact(self, job_id: uuid.UUID) -> tuple[GenerationRecord, bytes] | None:
        record = self.repository.get(job_id)
        if record is None:
            return None
        content = self.artifact_store.get(record.object_key)
        if len(content) != record.artifact_size:
            raise RuntimeError("stored image size does not match its database record")
        if hashlib.sha256(content).hexdigest() != record.artifact_sha256:
            raise RuntimeError("stored image digest does not match its database record")
        return record, content

    def reset(self, reset_generation: int) -> dict[str, int]:
        if reset_generation < 0:
            raise ValueError("reset_generation must not be negative")
        self.repository.initialize()
        self.artifact_store.initialize()
        deleted_objects = self.artifact_store.delete_prefix(f"generated/{reset_generation}/")
        deleted_rows = self.repository.delete_generation(reset_generation)
        return {"deleted_objects": deleted_objects, "deleted_rows": deleted_rows}
