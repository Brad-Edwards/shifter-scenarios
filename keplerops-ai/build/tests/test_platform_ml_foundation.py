from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path


PACK = Path(__file__).resolve().parents[2]
ASSET = PACK / "assets/services/platform-ml"


class PlatformMLSourceTests(unittest.TestCase):
    def test_container_and_dependency_pins_are_immutable(self) -> None:
        dockerfile = (ASSET / "Dockerfile").read_text(encoding="utf-8")
        requirements = (ASSET / "requirements.txt").read_text(encoding="utf-8")
        self.assertIn("python@sha256:", dockerfile)
        self.assertNotIn("python:", dockerfile)
        self.assertNotIn("--chown=65532:65532", dockerfile)
        self.assertIn("USER 65532:65532", dockerfile)
        self.assertIn("EXPOSE 8470", dockerfile)
        self.assertIn('VOLUME ["/var/lib/keplerops-platform-ml"]', dockerfile)
        self.assertIn("/readyz", dockerfile)
        for line in requirements.splitlines():
            if line.strip():
                self.assertRegex(
                    line, r"^[a-z0-9-]+==[0-9]+(?:\.[0-9]+)+(?:[a-z0-9.-]+)?$"
                )

    def test_source_compiles_and_contains_real_upstream_estimators(self) -> None:
        for path in (
            ASSET / "app.py",
            ASSET / "events.py",
            ASSET / "models.py",
            ASSET / "reset.py",
        ):
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        source = (ASSET / "models.py").read_text(encoding="utf-8")
        for estimator in (
            "LogisticRegression",
            "MultinomialNB",
            "MLPClassifier",
            "RandomForestClassifier",
        ):
            self.assertIn(estimator, source)
        self.assertIn("model.predict_proba", source)
        self.assertIn("model.fit", source)
        self.assertIn("pixel_gradient", source)
        self.assertIn("model_parameter_digest", source)
        self.assertIn("model_parameter_payload", source)
        self.assertIn('"parameter_digest"', source)
        self.assertNotIn("joblib.load", source)

    def test_inversion_is_internally_bounded_and_estimators_are_explicit(self) -> None:
        source = (ASSET / "models.py").read_text(encoding="utf-8")
        self.assertIn("MAX_INVERSION_ITERATIONS = 200", source)
        self.assertIn("for step in range(MAX_INVERSION_ITERATIONS):", source)
        self.assertIn("if step >= iterations:", source)
        self.assertNotIn("range(iterations)", source)
        self.assertIn("np.nonzero(model.classes_ == target_label)", source)
        self.assertIn('max_features="sqrt"', source)

    def test_corpus_is_source_contained_and_split_for_evaluation(self) -> None:
        rows = [
            json.loads(line)
            for line in (ASSET / "seed/document-corpus.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line
        ]
        self.assertEqual(len(rows), 30)
        self.assertEqual({row["split"] for row in rows}, {"train", "validation"})
        labels = {row["label"] for row in rows}
        self.assertEqual(len(labels), 3)
        for split in ("train", "validation"):
            self.assertEqual(
                {row["label"] for row in rows if row["split"] == split}, labels
            )

    def test_reset_health_readiness_and_reconstruction_telemetry_exist(self) -> None:
        app_source = (ASSET / "app.py").read_text(encoding="utf-8")
        event_source = (ASSET / "events.py").read_text(encoding="utf-8")
        for route in (
            '"/healthz"',
            '"/readyz"',
            '"/v1/models"',
            '"/v1/evaluations"',
            '"/v1/documents/classify"',
            '"/v1/vision/classify"',
            '"/v1/vision/invert"',
            '"/v1/admin/retrain"',
            '"/v1/admin/reset"',
            '"/v1/admin/events"',
        ):
            self.assertIn(route, app_source)
        for field in (
            '"request"',
            '"response"',
            '"request_digest"',
            '"response_digest"',
            '"duration_ms"',
            '"model_ids"',
        ):
            self.assertIn(field, event_source)

    def test_foundation_does_not_embed_scenario_progress_semantics(self) -> None:
        combined = "\n".join(
            path.read_text(encoding="utf-8")
            for path in ASSET.rglob("*")
            if path.is_file() and path.suffix in {".jsonl", ".py", ".sh", ".txt"}
        ).lower()
        for forbidden in (
            "challenge_id",
            "receipt_id",
            "ctfd",
            "scoring",
            "attack technique",
            "milestone 24",
        ):
            self.assertNotIn(forbidden, combined)


if __name__ == "__main__":
    unittest.main()
