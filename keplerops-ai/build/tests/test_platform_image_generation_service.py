from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import sys
import unittest
import uuid


SCENARIO_ROOT = Path(__file__).resolve().parents[2]
SERVICE_PATH = (
    SCENARIO_ROOT
    / "assets"
    / "services"
    / "platform-communications"
    / "image-generation"
    / "service.py"
)
SPEC = importlib.util.spec_from_file_location("platform_image_service", SERVICE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class FakeBackend:
    def __init__(
        self, content: bytes = MODULE.PNG_SIGNATURE + b"generated-image"
    ) -> None:
        self.content = content
        self.initialized = False
        self.calls = []

    def initialize(self) -> None:
        self.initialized = True

    def ready(self) -> bool:
        return self.initialized

    def generate(self, request):
        self.calls.append(request)
        return self.content


class FakeRepository:
    def __init__(self) -> None:
        self.initialized = False
        self.initialize_calls = 0
        self.records = {}

    def initialize(self) -> None:
        self.initialized = True
        self.initialize_calls += 1

    def ready(self) -> bool:
        return self.initialized

    def get(self, job_id):
        return self.records.get(job_id)

    def put(self, record) -> None:
        self.records[record.job_id] = record

    def delete_generation(self, reset_generation: int) -> int:
        selected = [
            job_id
            for job_id, record in self.records.items()
            if record.reset_generation == reset_generation
        ]
        for job_id in selected:
            del self.records[job_id]
        return len(selected)


class FakeArtifactStore:
    def __init__(self) -> None:
        self.initialized = False
        self.initialize_calls = 0
        self.objects = {}

    def initialize(self) -> None:
        self.initialized = True
        self.initialize_calls += 1

    def ready(self) -> bool:
        return self.initialized

    def put(self, object_key: str, content: bytes, content_type: str) -> None:
        assert content_type == "image/png"
        self.objects[object_key] = content

    def get(self, object_key: str) -> bytes:
        return self.objects[object_key]

    def delete_prefix(self, prefix: str) -> int:
        selected = [key for key in self.objects if key.startswith(prefix)]
        for key in selected:
            del self.objects[key]
        return len(selected)


def make_service(reset_generation: int = 7):
    backend = FakeBackend()
    repository = FakeRepository()
    store = FakeArtifactStore()
    monotonic_values = iter((10.0, 10.25))
    service = MODULE.GenerationService(
        backend=backend,
        repository=repository,
        artifact_store=store,
        model_id="OpenVINO/FLUX.1-schnell-int4-ov",
        model_revision="fixed-revision",
        reset_generation=reset_generation,
        id_factory=lambda: uuid.UUID("163b6777-3184-44cf-a764-a47fc8472839"),
        wall_clock=lambda: datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc),
        monotonic_clock=lambda: next(monotonic_values),
    )
    return service, backend, repository, store


def test_generation_persists_png_and_complete_metadata() -> None:
    service, backend, repository, store = make_service()
    service.initialize()
    assert service.ready() is True
    request = MODULE.GenerationRequest(
        prompt="A satellite operations room at sunrise",
        seed=42,
        width=512,
        height=512,
        steps=4,
    )
    record = service.generate(request)
    assert record.job_id == uuid.UUID("163b6777-3184-44cf-a764-a47fc8472839")
    assert record.object_key == f"generated/7/{record.job_id}.png"
    assert record.elapsed_ms == 250
    assert record.artifact_size == len(backend.content)
    assert repository.records[record.job_id] == record
    assert store.objects[record.object_key] == backend.content
    restored_record, restored_content = service.get_artifact(record.job_id)
    assert restored_record == record
    assert restored_content == backend.content


def test_idempotency_key_returns_existing_generation_without_recomputing() -> None:
    service, backend, _, _ = make_service()
    service.initialize()
    request = MODULE.GenerationRequest(
        prompt="KeplerOps antenna field",
        client_request_id="request-100",
    )
    first = service.generate(request)
    second = service.generate(request)
    assert first == second
    assert len(backend.calls) == 1


def test_idempotency_key_rejects_a_different_request() -> None:
    service, _, _, _ = make_service()
    service.initialize()
    service.generate(MODULE.GenerationRequest(prompt="first", client_request_id="same"))
    try:
        service.generate(
            MODULE.GenerationRequest(prompt="second", client_request_id="same")
        )
    except ValueError as error:
        assert "already used" in str(error)
    else:
        raise AssertionError("a reused idempotency key must reject a different request")


def test_reset_removes_only_selected_generation() -> None:
    service, _, repository, store = make_service(reset_generation=7)
    service.initialize()
    record = service.generate(MODULE.GenerationRequest(prompt="reset me"))
    store.objects["generated/8/keep.png"] = MODULE.PNG_SIGNATURE + b"keep"
    result = service.reset(7)
    assert result == {"deleted_objects": 1, "deleted_rows": 1}
    assert record.job_id not in repository.records
    assert store.objects == {"generated/8/keep.png": MODULE.PNG_SIGNATURE + b"keep"}
    assert repository.initialize_calls == 2
    assert store.initialize_calls == 2


def test_invalid_generation_inputs_are_rejected_before_backend_use() -> None:
    requests = [
        MODULE.GenerationRequest(prompt=""),
        MODULE.GenerationRequest(prompt="ok", width=513),
        MODULE.GenerationRequest(prompt="ok", height=128),
        MODULE.GenerationRequest(prompt="ok", steps=13),
        MODULE.GenerationRequest(prompt="ok", seed=-1),
    ]
    for invalid_request in requests:
        service, backend, _, _ = make_service()
        service.initialize()
        try:
            service.generate(invalid_request)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid request was accepted: {invalid_request}")
        assert backend.calls == []


class PlatformImageGenerationServiceTests(unittest.TestCase):
    def test_generation(self) -> None:
        test_generation_persists_png_and_complete_metadata()

    def test_idempotency(self) -> None:
        test_idempotency_key_returns_existing_generation_without_recomputing()

    def test_idempotency_conflict(self) -> None:
        test_idempotency_key_rejects_a_different_request()

    def test_reset(self) -> None:
        test_reset_removes_only_selected_generation()

    def test_validation(self) -> None:
        test_invalid_generation_inputs_are_rejected_before_backend_use()


if __name__ == "__main__":
    unittest.main()
