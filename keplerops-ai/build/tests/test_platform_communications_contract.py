from __future__ import annotations

import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SCENARIO_ROOT = Path(__file__).resolve().parents[2]
BOUNDARY_ROOT = SCENARIO_ROOT / "assets" / "services" / "platform-communications"


def read(relative_path: str) -> str:
    return (BOUNDARY_ROOT / relative_path).read_text(encoding="utf-8")


def load_module(name: str, relative_path: str):
    path = BOUNDARY_ROOT / relative_path
    specification = importlib.util.spec_from_file_location(name, path)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


image_fetch = load_module(
    "platform_communications_image_fetch_test", "image-generation/fetch_snapshot.py"
)
text_fetch = load_module(
    "platform_communications_text_fetch_test", "text-generation/fetch_model.py"
)


def test_no_parallel_service_or_deployment_spec_is_present() -> None:
    assert not (BOUNDARY_ROOT / "service-manifest.yaml").exists()
    assert not (BOUNDARY_ROOT / "topology.yaml").exists()
    assert not (BOUNDARY_ROOT / "deployment.yaml").exists()


def test_every_upstream_runtime_base_is_digest_pinned() -> None:
    dockerfiles = [
        "mail/Dockerfile.stalwart",
        "mail/Dockerfile.roundcube",
        "mail/Dockerfile.readiness",
        "text-generation/Dockerfile",
        "image-generation/Dockerfile",
    ]
    for relative_path in dockerfiles:
        from_lines = [
            line
            for line in read(relative_path).splitlines()
            if line.startswith("FROM ")
        ]
        assert from_lines
        assert all("@sha256:" in line for line in from_lines), relative_path
        assert all(":" not in line.split("@", 1)[0] for line in from_lines), (
            relative_path
        )


def test_stalwart_bootstrap_is_declarative_and_seeds_real_mailboxes() -> None:
    operations = [
        json.loads(line)
        for line in read("mail/seed.ndjson").splitlines()
        if line.strip()
    ]
    assert all(operation["object"] != "Bootstrap" for operation in operations)
    domain = next(
        operation for operation in operations if operation["object"] == "Domain"
    )
    assert domain["@type"] == "upsert"
    assert domain["matchOn"] == ["name"]
    accounts = next(
        operation for operation in operations if operation["object"] == "Account"
    )
    assert accounts["@type"] == "upsert"
    assert accounts["matchOn"] == ["name"]
    users = accounts["value"]
    for mailbox in ("generation", "procurement", "researcher", "operations"):
        user = users[f"{mailbox}-mailbox"]
        assert user["@type"] == "User"
        assert user["name"] == mailbox
        assert user["domainId"] == "#keplerops-domain"
        assert user["credentials"]["0"]["@type"] == "Password"
    listeners = next(
        operation
        for operation in operations
        if operation["object"] == "NetworkListener"
    )["value"]
    assert {next(iter(listener["bind"])) for listener in listeners.values()} == {
        "[::]:25",
        "[::]:587",
        "[::]:993",
        "[::]:8080",
    }
    entrypoint = read("mail/stalwart-entrypoint.sh")
    assert "STALWART_RECOVERY_MODE=1" in entrypoint
    assert "stalwart-cli apply --file /opt/keplerops/seed.ndjson --json" in entrypoint
    assert "exec /usr/local/bin/stalwart" in entrypoint


def test_mail_clients_require_private_ca_verification_and_protocol_delivery() -> None:
    roundcube = read("mail/roundcube-config.php")
    assert "ssl://mail-server-01.keplerops.lab:993" in roundcube
    assert "tls://mail-server-01.keplerops.lab:587" in roundcube
    assert "'verify_peer' => true" in roundcube
    assert "'verify_peer_name' => true" in roundcube
    assert "'allow_self_signed' => false" in roundcube
    assert "/etc/keplerops/pki/ca.crt" in roundcube
    assert "'peer_name' => 'mail-server-01.keplerops.lab'" in roundcube
    readiness = read("mail/mail_readiness.py")
    assert "http://roundcube:8000/" in readiness
    assert "smtp.starttls(context=tls)" in readiness
    assert "tls.minimum_version = ssl.TLSVersion.TLSv1_2" in readiness
    assert "smtp.login" in readiness
    assert "imaplib.IMAP4_SSL" in readiness
    assert "imap.fetch(" in readiness
    assert '"(BODY.PEEK[HEADER.FIELDS (MESSAGE-ID)])"' in readiness


def test_text_model_is_exact_and_only_fetched_at_build_time() -> None:
    manifest = json.loads(read("text-generation/model-manifest.json"))
    assert manifest["model_id"] == "Qwen/Qwen3-0.6B-GGUF"
    assert manifest["revision"] == "23749fefcc72300e3a2ad315e1317431b06b590a"
    assert manifest["file"] == {
        "path": "Qwen3-0.6B-Q8_0.gguf",
        "size": 639446688,
        "sha256": "9465e63a22add5354d9bb4b99e90117043c7124007664907259bd16d043bb031",
    }
    assert manifest["license_file"]["sha256"] == (
        "5de36594c10839788a8c589443a8ef9d8b8d17c65a1b5807206ae037fc36c6bd"
    )
    dockerfile = read("text-generation/Dockerfile")
    fetch_run = next(
        line
        for line in dockerfile.splitlines()
        if line.startswith("RUN python /opt/build/fetch_model.py")
    )
    assert fetch_run == "RUN python /opt/build/fetch_model.py"
    assert text_fetch.MANIFEST_PATH == Path("/opt/build/model-manifest.json")
    assert text_fetch.OUTPUT_ROOT == Path("/models")
    assert "COPY --from=model-fetch" in dockerfile
    assert '--model", "/models/Qwen3-0.6B-Q8_0.gguf' in dockerfile
    assert '--parallel", "1' in dockerfile
    assert "--jinja" in dockerfile
    assert '"--reasoning", "off"' in dockerfile
    assert "-hf" not in dockerfile


def test_image_source_snapshot_and_runtime_export_are_immutable() -> None:
    manifest = json.loads(read("image-generation/source-model-manifest.json"))
    assert manifest["model_id"] == "OpenVINO/FLUX.1-schnell-int4-ov"
    assert manifest["revision"] == "67f2ca1b786f707a3c1a7a1f0ae179641249f0c2"
    assert all(artifact["digest_type"] == "sha256" for artifact in manifest["files"])
    assert all(len(artifact["digest"]) == 64 for artifact in manifest["files"])
    paths = {artifact["path"]: artifact for artifact in manifest["files"]}
    assert paths["model_index.json"]["digest"] == (
        "526aabdaef2b58d032b026c2291dc72304139e21497c96681156878641978977"
    )
    assert paths["transformer/openvino_model.bin"]["digest"] == (
        "4164d56c120a47ad5df4c7eb183089fc9be472c31904a69e55207e02c88e5f23"
    )
    assert paths["vae_decoder/openvino_model.bin"]["size"] == 49331921
    assert "transformer/diffusion_pytorch_model.safetensors" not in paths
    dockerfile = read("image-generation/Dockerfile")
    fetch_run = next(
        line
        for line in dockerfile.splitlines()
        if line.startswith("RUN python /opt/build/fetch_snapshot.py")
    )
    assert fetch_run == "RUN python /opt/build/fetch_snapshot.py \\"
    assert image_fetch.MANIFEST_PATH == Path("/opt/build/source-model-manifest.json")
    assert image_fetch.OUTPUT_ROOT == Path("/model/flux1-schnell-int4-ov")
    assert "optimum-cli export openvino" not in dockerfile
    assert "requirements-build.txt" not in dockerfile
    assert "hash_tree.py" in dockerfile
    assert "python /opt/build/hash_tree.py\n" in dockerfile
    assert "COPY --from=model-fetch --chown=" not in dockerfile
    runtime_section = dockerfile.split(
        "FROM python@sha256:5f55cdf0c5d9dc1a415637a5ccc4a9e18663ad203673173b8cda8f8dcacef689",
        2,
    )[-1]
    assert "huggingface.co" not in runtime_section
    assert "fetch_snapshot.py" not in runtime_section


def test_runtime_sources_contain_only_infrastructure_behavior() -> None:
    runtime_files = [
        "image-generation/app.py",
        "image-generation/adapters.py",
        "image-generation/service.py",
        "mail/mail_readiness.py",
    ]
    excluded_terms = ("challenge", "flag", "scoring", "proof_predicate", "atlas")
    for relative_path in runtime_files:
        source = read(relative_path).lower()
        assert all(term not in source for term in excluded_terms), relative_path


def test_image_service_uses_only_external_mutable_state_and_one_worker() -> None:
    dockerfile = read("image-generation/Dockerfile")
    app = read("image-generation/app.py")
    adapters = read("image-generation/adapters.py")
    service = read("image-generation/service.py")
    assert '"--workers", "1"' in dockerfile
    assert "asyncio.Semaphore(1)" in app
    assert "PostgresGenerationRepository" in app
    assert "MinioArtifactStore" in app
    assert "image_generation_jobs" in adapters
    assert 'f"generated/{self.reset_generation}/{job_id}.png"' in service
    assert "delete_prefix" in service
    assert "DELETE FROM image_generation_jobs WHERE reset_generation = %s" in adapters
    assert "responses=READY_RESPONSES" in app
    assert "responses=GENERATION_RESPONSES" in app
    assert "responses=CONTENT_RESPONSES" in app
    assert "IdempotencyKey = Annotated[" in app


def test_model_fetchers_reject_non_normalized_and_symlink_escape_paths() -> None:
    invalid_paths: tuple[object, ...] = (
        "",
        "/absolute/model.bin",
        "../model.bin",
        "nested/../model.bin",
        "nested//model.bin",
        "nested/./model.bin",
        "nested\\model.bin",
        123,
    )
    with tempfile.TemporaryDirectory() as directory:
        base = Path(directory)
        for index, module in enumerate((image_fetch, text_fetch)):
            output = base / f"output-{index}"
            output.mkdir()
            outside = base / f"outside-{index}"
            outside.mkdir()
            (output / "escape").symlink_to(outside, target_is_directory=True)
            for raw_path in invalid_paths:
                with unittest.TestCase().assertRaises(RuntimeError):
                    module._safe_destination(output, raw_path)
            with unittest.TestCase().assertRaises(RuntimeError):
                module._safe_destination(output, "escape/model.bin")
            assert module._safe_destination(output, "nested/model.bin") == (
                output / "nested/model.bin"
            )


def test_model_fetchers_verify_artifacts_and_write_exclusively() -> None:
    content = b"model artifact"
    digest = hashlib.sha256(content).hexdigest()
    image_manifest = {
        "model_id": "publisher/image-model",
        "revision": "a" * 40,
        "files": [
            {
                "path": "nested/model.bin",
                "size": len(content),
                "digest_type": "sha256",
                "digest": digest,
            }
        ],
    }
    text_manifest = {
        "model_id": "publisher/text-model",
        "revision": "b" * 40,
        "file": {"path": "model.gguf", "size": len(content), "sha256": digest},
        "license_file": {"path": "LICENSE", "size": len(content), "sha256": digest},
    }
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        image_output = root / "image"
        with patch.object(
            image_fetch.urllib.request, "urlopen", return_value=io.BytesIO(content)
        ):
            image_fetch._materialize(image_manifest, image_output)
        assert (image_output / "nested/model.bin").read_bytes() == content
        assert (image_output / "source-model-manifest.json").exists()
        with (
            patch.object(
                image_fetch.urllib.request, "urlopen", return_value=io.BytesIO(content)
            ),
            unittest.TestCase().assertRaises(FileExistsError),
        ):
            image_fetch._materialize(image_manifest, image_output)

        text_output = root / "text"
        with patch.object(
            text_fetch.urllib.request,
            "urlopen",
            side_effect=(io.BytesIO(content), io.BytesIO(content)),
        ):
            text_fetch._materialize(text_manifest, text_output)
        assert (text_output / "model.gguf").read_bytes() == content
        assert (text_output / "LICENSE").read_bytes() == content
        assert (text_output / "model-manifest.json").exists()


class PlatformCommunicationsContractTests(unittest.TestCase):
    def test_no_parallel_spec(self) -> None:
        test_no_parallel_service_or_deployment_spec_is_present()

    def test_digest_pins(self) -> None:
        test_every_upstream_runtime_base_is_digest_pinned()

    def test_stalwart_contract(self) -> None:
        test_stalwart_bootstrap_is_declarative_and_seeds_real_mailboxes()

    def test_mail_protocol_contract(self) -> None:
        test_mail_clients_require_private_ca_verification_and_protocol_delivery()

    def test_text_model_contract(self) -> None:
        test_text_model_is_exact_and_only_fetched_at_build_time()

    def test_image_model_contract(self) -> None:
        test_image_source_snapshot_and_runtime_export_are_immutable()

    def test_infrastructure_only_contract(self) -> None:
        test_runtime_sources_contain_only_infrastructure_behavior()

    def test_image_state_contract(self) -> None:
        test_image_service_uses_only_external_mutable_state_and_one_worker()

    def test_fetch_path_confinement(self) -> None:
        test_model_fetchers_reject_non_normalized_and_symlink_escape_paths()

    def test_fetch_artifact_verification(self) -> None:
        test_model_fetchers_verify_artifacts_and_write_exclusively()


if __name__ == "__main__":
    unittest.main()
