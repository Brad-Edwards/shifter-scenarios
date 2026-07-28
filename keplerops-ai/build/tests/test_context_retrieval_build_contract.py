from __future__ import annotations

import unittest
from pathlib import Path

import yaml


PACK_ROOT = Path(__file__).resolve().parents[2]


def load_yaml(relative: str) -> dict:
    value = yaml.safe_load((PACK_ROOT / relative).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"{relative}: expected mapping")
    return value


class ContextRetrievalBuildContractTests(unittest.TestCase):
    def test_embedding_model_is_revision_pinned_and_fully_verified(self) -> None:
        manifest = load_yaml("assets/model-artifacts/embedding-model.yaml")
        self.assertEqual(manifest["artifact_id"], "context-embedding-model")
        self.assertEqual(
            manifest["upstream"],
            {
                "repository": "sentence-transformers/all-MiniLM-L6-v2",
                "revision": "1110a243fdf4706b3f48f1d95db1a4f5529b4d41",
                "license": "Apache-2.0",
            },
        )
        files = {row["path"]: row for row in manifest["files"]}
        self.assertEqual(
            set(files),
            {
                "config.json",
                "onnx/model.onnx",
                "special_tokens_map.json",
                "tokenizer.json",
                "tokenizer_config.json",
                "vocab.txt",
            },
        )
        for row in files.values():
            self.assertRegex(row["sha256"], r"^[0-9a-f]{64}$")
            self.assertGreater(row["size"], 0)
        self.assertEqual(manifest["runtime"]["embedding_dimension"], 384)
        self.assertEqual(manifest["runtime"]["pooling"], "attention-mask-mean-l2")

    def test_model_fetcher_uses_the_manifest_file_allowlist(self) -> None:
        source = (
            PACK_ROOT / "assets/model-artifacts/fetch_model.py"
        ).read_text(encoding="utf-8")
        self.assertIn('allow_patterns=[row["path"] for row in files]', source)
        self.assertIn("if len(paths) != len(set(paths))", source)
        self.assertNotIn('"model.safetensors",', source)

    def test_gateway_contains_real_local_embedding_runtime(self) -> None:
        dockerfile = (
            PACK_ROOT / "assets/services/Dockerfile.gateway"
        ).read_text(encoding="utf-8")
        requirements = (
            PACK_ROOT / "assets/services/keplerops-runtime/context-requirements.txt"
        ).read_text(encoding="utf-8").splitlines()
        self.assertEqual(
            requirements,
            ["numpy==2.3.5", "onnxruntime==1.27.0", "tokenizers==0.23.1"],
        )
        self.assertIn("embedding-model.yaml", dockerfile)
        self.assertIn("fetch_model.py", dockerfile)
        self.assertIn("--output /models/context-embedding", dockerfile)
        self.assertIn("context-requirements.txt", dockerfile)
        self.assertIn("context_poisoning.py", dockerfile)
        bootstrap = (
            PACK_ROOT / "build/gcp/workload-bootstrap.sh"
        ).read_text(encoding="utf-8")
        self.assertIn("embedding_model_path: /models/context-embedding", bootstrap)
        self.assertIn("retrieval_sessions", bootstrap)
        self.assertIn("retrieval_attempts", bootstrap)

    def test_every_app_role_carries_the_context_domain(self) -> None:
        for relative in (
            "assets/services/Dockerfile.gateway",
            "assets/services/Dockerfile.policy",
            "assets/services/Dockerfile.proof",
            "assets/services/keplerops-runtime/Dockerfile",
        ):
            dockerfile = (PACK_ROOT / relative).read_text(encoding="utf-8")
            self.assertIn(
                "COPY assets/services/keplerops-runtime/context_poisoning.py",
                dockerfile,
                relative,
            )

    def test_dataset_store_is_real_pgvector_with_versioned_chunks(self) -> None:
        environment = load_yaml("sdl/modules/environment.sdl.yaml")
        postgres = environment["features"]["postgresql-dataset-store"]["source"]["build"]
        self.assertRegex(
            f'{postgres["base_image"]}@{postgres["base_image_digest"]}',
            r"^pgvector/pgvector:0\.8\.2-pg17-bookworm@sha256:[0-9a-f]{64}$",
        )
        dockerfile = (
            PACK_ROOT / "assets/services/Dockerfile.postgres"
        ).read_text(encoding="utf-8")
        self.assertIn("ARG BASE_IMAGE=pgvector/pgvector@sha256:", dockerfile)
        schema = (
            PACK_ROOT / "assets/services/postgres-init.sh"
        ).read_text(encoding="utf-8")
        for contract in (
            "CREATE EXTENSION vector",
            "CREATE TABLE retrieval_documents",
            "CREATE TABLE retrieval_chunks",
            "embedding vector(384)",
            "CREATE INDEX retrieval_chunks_embedding_hnsw",
            "CREATE TABLE retrieval_index_revisions",
            "CREATE TABLE retrieval_sessions",
            "CREATE TABLE retrieval_attempts",
        ):
            self.assertIn(contract, schema)

    def test_sdl_is_the_retrieval_substrate_source_of_truth(self) -> None:
        environment = load_yaml("sdl/modules/environment.sdl.yaml")
        gateway = environment["features"]["envoy-fastapi-inference-gateway"]
        dataset = environment["features"]["postgresql-dataset-store"]
        self.assertIn("retrieval", gateway["description"])
        self.assertIn("pgvector", dataset["source"]["build"]["base_image"])
        content = environment["content"]
        self.assertEqual(
            content["context-embedding-model"]["source"]["name"],
            "assets/model-artifacts/embedding-model.yaml",
        )
        self.assertEqual(
            content["retrieval-knowledge-base"]["source"]["name"],
            "assets/content/datasets/context.jsonl",
        )
        module = load_yaml("sdl/modules/module-03-context-poisoning.sdl.yaml")
        refs = module["behavior_specifications"]["module-03-context-poisoning"][
            "authority_scope_refs"
        ]
        self.assertIn("content.core.context-embedding-model", refs)
        self.assertIn("content.core.retrieval-knowledge-base", refs)


if __name__ == "__main__":
    unittest.main()
