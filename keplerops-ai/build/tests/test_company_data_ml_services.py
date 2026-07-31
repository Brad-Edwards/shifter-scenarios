"""Focused contracts for data and ML company-state materialization."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import yaml

PACK = Path(__file__).resolve().parents[2]
MODEL_ASSETS = PACK / "assets/model-artifacts"
OPENSEARCH = PACK / "assets/services/platform-network/opensearch"
CORPUS = Path(
    os.environ.get(
        "KEPLEROPS_COMPANY_STATE_PATH",
        PACK / "assets/content/company-state/company-state.yaml",
    )
)
CHALLENGE_SCHEMA_SHA256 = (
    "eeca7382cd7ac123ea9191033377d5796578370ea65c1d19addd878de9dde748"
)
RESEARCH_TEMPLATE_SHA256 = (
    "078b6d1768b3135849f6009c642b0fe673631e0713a6079413a4e3cc16482613"
)
RESEARCH_CORPUS_SHA256 = (
    "b5767140025475709110b59a4cbda286aa8e691f8dfc15e9abfd1bd6d087d714"
)


def load_module(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


postgres_seed = load_module(
    "company_postgres_seed_test", MODEL_ASSETS / "company_postgres_seed.py"
)
notebook_readback = load_module(
    "company_notebook_readback_test",
    MODEL_ASSETS / "company_notebook_readback.py",
)
mlflow_seed = load_module(
    "company_mlflow_seed_test", MODEL_ASSETS / "company_mlflow_seed.py"
)
search_generator = load_module(
    "company_search_generator_test", OPENSEARCH / "generate-company-corpus.py"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class MissingModelError(Exception):
    error_code = "RESOURCE_DOES_NOT_EXIST"


class CollisionClient:
    def __init__(self, *, experiment_exists: bool, model_exists: bool) -> None:
        self.experiment_exists = experiment_exists
        self.model_exists = model_exists

    def get_experiment_by_name(self, _name: str):
        if self.experiment_exists:
            return SimpleNamespace(experiment_id="1")
        return None

    def get_registered_model(self, _name: str):
        if self.model_exists:
            return SimpleNamespace(name=_name)
        raise MissingModelError()


class CompanyDataMLServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not CORPUS.is_file():
            raise RuntimeError(f"canonical company state is unavailable: {CORPUS}")
        cls.company_state = yaml.safe_load(CORPUS.read_text(encoding="utf-8"))

    def test_challenge_postgres_and_research_namespaces_are_unchanged(self) -> None:
        postgres_init = PACK / "assets/services/postgres-init.sh"
        research_template = OPENSEARCH / "index-template.json"
        research_corpus = OPENSEARCH / "corpus/research-corpus.ndjson"
        self.assertEqual(sha256(postgres_init), CHALLENGE_SCHEMA_SHA256)
        self.assertEqual(sha256(research_template), RESEARCH_TEMPLATE_SHA256)
        self.assertEqual(sha256(research_corpus), RESEARCH_CORPUS_SHA256)
        schema = postgres_init.read_text(encoding="utf-8")
        self.assertEqual(schema.count("CREATE TABLE "), 56)
        self.assertEqual(schema.count("CREATE INDEX "), 1)
        self.assertNotIn("company_state", schema)

    def test_postgres_company_schema_is_separate_and_self_verifying(self) -> None:
        sql = postgres_seed.render_sql(CORPUS)
        self.assertIn("CREATE SCHEMA company_state;", sql)
        self.assertIn("CREATE TABLE company_state.datasets", sql)
        self.assertIn("CREATE VIEW company_state.dataset_readback", sql)
        self.assertIn(
            "string_agg(object_digest, E'\\n' ORDER BY object_id)",
            sql,
        )
        self.assertIn("ownership collision: schema company_state already exists", sql)
        self.assertIn("company dataset native readback digest mismatch", sql)
        self.assertEqual(sql.count("('dataset-"), 3)
        for dataset in self.company_state["datasets"]:
            self.assertIn(dataset["id"], sql)
            self.assertIn(dataset["digest"], sql)
        dockerfile = (
            PACK / "assets/services/Dockerfile.postgres"
        ).read_text(encoding="utf-8")
        self.assertIn("/30-keplerops-company-data.sql", dockerfile)
        challenge_copy = (
            "COPY --from=seed /20-keplerops-data.sql "
            "/docker-entrypoint-initdb.d/20-keplerops-data.sql"
        )
        company_copy = (
            "COPY --from=company-seed /30-keplerops-company-data.sql "
            "/docker-entrypoint-initdb.d/30-keplerops-company-data.sql"
        )
        self.assertLess(dockerfile.index(challenge_copy), dockerfile.index(company_copy))

    def test_postgres_generator_rejects_duplicates_and_reserved_ids(self) -> None:
        for mutation in ("duplicate", "reserved"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                corpus = copy.deepcopy(self.company_state)
                if mutation == "duplicate":
                    corpus["datasets"].append(copy.deepcopy(corpus["datasets"][0]))
                else:
                    corpus["datasets"][0]["id"] = "kep-m07-a"
                path = Path(directory) / "company-state.yaml"
                path.write_text(yaml.safe_dump(corpus), encoding="utf-8")
                with self.assertRaises(ValueError):
                    postgres_seed.load_datasets(path)

    def test_notebooks_are_native_deterministic_and_digest_verified(self) -> None:
        expected_assets, expected_manifest = notebook_readback.render_assets(CORPUS)
        committed_manifest = json.loads(
            (MODEL_ASSETS / "company-notebook-manifest.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(committed_manifest, expected_manifest)
        self.assertEqual(expected_manifest["notebook_count"], 3)
        for name, expected in expected_assets.items():
            path = MODEL_ASSETS / name
            self.assertEqual(path.read_bytes(), expected)
            notebook = json.loads(expected)
            self.assertEqual(notebook["nbformat"], 4)
            self.assertTrue(notebook["cells"])
            self.assertEqual(
                notebook["metadata"]["keplerops_company_state"]["owner"],
                "keplerops-company-state",
            )
        notebook_readback.verify(
            MODEL_ASSETS, MODEL_ASSETS / "company-notebook-manifest.json"
        )

    def test_notebook_readback_rejects_content_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            assets, manifest = notebook_readback.render_assets(CORPUS)
            for name, encoded in assets.items():
                (root / name).write_bytes(encoded)
            manifest_path = root / "company-notebook-manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            target = root / next(iter(assets))
            target.write_bytes(target.read_bytes() + b"\n")
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                notebook_readback.verify(root, manifest_path)

    def test_mlflow_plan_preserves_lineage_in_an_isolated_namespace(self) -> None:
        plan = mlflow_seed.build_plan(CORPUS)
        self.assertEqual(plan["owner"], "keplerops-company-state")
        self.assertEqual(plan["experiment_name"], "company-state/orion-release")
        self.assertEqual(len(plan["runs"]), 3)
        self.assertEqual(len(plan["models"]), 3)
        self.assertTrue(
            all(
                row["registered_name"].startswith("company-state.")
                for row in plan["models"]
            )
        )
        self.assertEqual(
            {row["status"] for row in plan["runs"]}, {"completed", "abandoned"}
        )
        self.assertEqual(
            {
                alias
                for row in plan["models"]
                for alias in row["aliases"]
            },
            {"candidate", "production"},
        )
        self.assertEqual(
            plan["canonical_digest"],
            mlflow_seed.digest_json(
                {key: value for key, value in plan.items() if key != "canonical_digest"}
            ),
        )

    def test_mlflow_adapter_rejects_experiment_and_model_collisions(self) -> None:
        plan = mlflow_seed.build_plan(CORPUS)
        original = mlflow_seed._mlflow
        mlflow_seed._mlflow = lambda: (None, None, MissingModelError)
        try:
            with self.assertRaisesRegex(RuntimeError, "experiment"):
                mlflow_seed.assert_no_ownership_collisions(
                    CollisionClient(experiment_exists=True, model_exists=False),
                    plan,
                )
            with self.assertRaisesRegex(RuntimeError, "model"):
                mlflow_seed.assert_no_ownership_collisions(
                    CollisionClient(experiment_exists=False, model_exists=True),
                    plan,
                )
            mlflow_seed.assert_no_ownership_collisions(
                CollisionClient(experiment_exists=False, model_exists=False),
                plan,
            )
        finally:
            mlflow_seed._mlflow = original

    def test_mlflow_uses_native_run_registry_and_artifact_apis(self) -> None:
        source = (MODEL_ASSETS / "company_mlflow_seed.py").read_text(
            encoding="utf-8"
        )
        for call in (
            "client.create_experiment(",
            "client.create_run(",
            "client.log_metric(",
            "client.log_dict(",
            "client.create_registered_model(",
            "client.create_model_version(",
            "client.set_registered_model_alias(",
            "client.search_runs(",
            "client.download_artifacts(",
            "client.get_model_version(",
        ):
            self.assertIn(call, source)
        self.assertNotIn("sqlite3", source)
        self.assertNotIn("DELETE FROM", source)
        dockerfile = (
            PACK / "assets/services/Dockerfile.mlflow"
        ).read_text(encoding="utf-8")
        self.assertIn("company_mlflow_seed.py validate", dockerfile)
        self.assertNotIn("ENTRYPOINT", dockerfile)

    def test_company_search_corpus_is_separate_and_reproducible(self) -> None:
        ndjson, manifest, index = search_generator.render(CORPUS)
        self.assertEqual(manifest["index_name"], "keplerops-company-v1-000001")
        self.assertEqual(manifest["index_alias"], "keplerops-company")
        self.assertEqual(manifest["object_count"], 33)
        self.assertEqual(index["mappings"]["_meta"]["owner"], manifest["owner"])
        self.assertEqual(
            index["mappings"]["_meta"]["canonical_digest"],
            manifest["canonical_digest"],
        )
        self.assertEqual(
            (OPENSEARCH / "corpus/company-corpus.ndjson").read_text(
                encoding="utf-8"
            ),
            ndjson,
        )
        self.assertEqual(
            json.loads(
                (OPENSEARCH / "corpus/company-readback-manifest.json").read_text(
                    encoding="utf-8"
                )
            ),
            manifest,
        )
        lines = ndjson.splitlines()
        self.assertEqual(len(lines), manifest["object_count"] * 2)
        self.assertTrue(
            all(
                json.loads(lines[offset])["index"]["_index"]
                == "keplerops-company-v1-000001"
                for offset in range(0, len(lines), 2)
            )
        )

    def test_company_search_generator_rejects_cross_section_collisions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            corpus = copy.deepcopy(self.company_state)
            corpus["operations"][0]["id"] = corpus["datasets"][0]["id"]
            path = Path(directory) / "company-state.yaml"
            path.write_text(yaml.safe_dump(corpus), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unique"):
                search_generator.documents(path)

    def test_opensearch_reset_owns_only_company_index_and_reads_every_digest(
        self,
    ) -> None:
        seed = (OPENSEARCH / "seed.sh").read_text(encoding="utf-8")
        readiness = (OPENSEARCH / "readiness.sh").read_text(encoding="utf-8")
        reset = (OPENSEARCH / "reset.sh").read_text(encoding="utf-8")
        readback = (OPENSEARCH / "corpus/company-readback.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn('index_name="keplerops-research-v1-000001"', seed)
        self.assertIn('company_index_name="keplerops-company-v1-000001"', seed)
        self.assertIn("ownership collision: OpenSearch template", seed)
        self.assertIn("ownership collision: OpenSearch index", seed)
        self.assertIn("ownership collision: OpenSearch alias", seed)
        self.assertIn("grep -Eq '^\\[\\]$' /tmp/company-alias.json", seed)
        self.assertIn("company-corpus.ndjson", seed)
        self.assertIn('test "${count}" = "8"', readiness)
        self.assertIn('"${script_dir}/corpus/company-readback.sh"', readiness)
        self.assertIn('exec "${script_dir}/seed.sh"', reset)
        self.assertIn("_source_includes=source_digest,company_state_owner", readback)
        self.assertIn("company-readback-digests.txt", readback)
        self.assertIn("company-readback-sources.ndjson", readback)
        self.assertIn('/_source/${document_id}', readback)
        for script in (
            OPENSEARCH / "seed.sh",
            OPENSEARCH / "readiness.sh",
            OPENSEARCH / "reset.sh",
            OPENSEARCH / "corpus/company-readback.sh",
        ):
            completed = subprocess.run(
                ["sh", "-n", str(script)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_dockerfiles_keep_company_assets_additive_and_reset_stable(self) -> None:
        jupyter = (
            PACK / "assets/services/Dockerfile.jupyter"
        ).read_text(encoding="utf-8")
        self.assertIn("/home/jovyan/keplerops/company-notebooks", jupyter)
        self.assertIn("company_notebook_readback.py verify", jupyter)
        self.assertIn(
            "test ! -e /home/jovyan/keplerops/company-notebooks", jupyter
        )
        self.assertIn(
            "ENV HOME=/home/jovyan/work JUPYTER_RUNTIME_DIR=/home/jovyan/work",
            jupyter,
        )

        postgres = (
            PACK / "assets/services/Dockerfile.postgres"
        ).read_text(encoding="utf-8")
        mlflow = (
            PACK / "assets/services/Dockerfile.mlflow"
        ).read_text(encoding="utf-8")
        for dockerfile in (postgres, mlflow):
            self.assertIn(
                "assets/content/company-state/company-state.yaml", dockerfile
            )
        self.assertNotIn(
            "company-state",
            (PACK / "assets/services/postgres-init.sh").read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
