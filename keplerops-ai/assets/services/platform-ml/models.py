"""Deterministic training, evaluation, inference, and inversion engines."""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, log_loss
from sklearn.naive_bayes import MultinomialNB
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline


SEED = 2_026_0719
DATASET_REVISION = "keplerops-foundation-datasets-v1"
VISION_SIDE = 16
VISION_LABELS = (
    "cross-array",
    "horizontal-array",
    "orbital-ring",
    "vertical-array",
)
MODEL_REVISIONS = {
    "document-logistic-v1": "tfidf-1-2-logistic-lbfgs-v1",
    "document-naive-bayes-v1": "tfidf-1-2-multinomial-nb-v1",
    "vision-mlp-v1": "dense-256x32x4-relu-lbfgs-v1",
    "vision-random-forest-v1": "random-forest-48x-depth8-v1",
}
MODEL_LICENSE = "BSD-3-Clause"
MAX_INVERSION_ITERATIONS = 200


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def digest_json(value: object) -> str:
    return digest_bytes(canonical_json(value).encode("utf-8"))


def file_digest(path: Path) -> str:
    return digest_bytes(path.read_bytes())


def _array(value: Any) -> list[Any]:
    return np.asarray(value).tolist()


def model_parameter_payload(model_id: str, model: Any) -> dict[str, Any]:
    """Export inference-affecting fitted state to a safe canonical structure."""
    if model_id.startswith("document-"):
        vectorizer = model.named_steps["tfidf"]
        classifier = model.named_steps["classifier"]
        common: dict[str, Any] = {
            "vocabulary": sorted(vectorizer.vocabulary_.items()),
            "idf": _array(vectorizer.idf_),
            "classes": _array(classifier.classes_),
        }
        if model_id == "document-logistic-v1":
            common.update(
                {
                    "coef": _array(classifier.coef_),
                    "intercept": _array(classifier.intercept_),
                }
            )
        else:
            common.update(
                {
                    "class_log_prior": _array(classifier.class_log_prior_),
                    "feature_log_prob": _array(classifier.feature_log_prob_),
                }
            )
        return common
    if model_id == "vision-mlp-v1":
        return {
            "classes": _array(model.classes_),
            "coefs": [_array(value) for value in model.coefs_],
            "intercepts": [_array(value) for value in model.intercepts_],
            "activation": model.activation,
            "out_activation": model.out_activation_,
        }
    if model_id == "vision-random-forest-v1":
        trees = []
        for estimator in model.estimators_:
            tree = estimator.tree_
            trees.append(
                {
                    "children_left": _array(tree.children_left),
                    "children_right": _array(tree.children_right),
                    "feature": _array(tree.feature),
                    "threshold": _array(tree.threshold),
                    "value": _array(tree.value),
                }
            )
        return {"classes": _array(model.classes_), "trees": trees}
    raise ValueError(f"no parameter canonicalizer for {model_id}")


def model_parameter_digest(model_id: str, model: Any) -> str:
    return digest_json(model_parameter_payload(model_id, model))


def _read_document_corpus(
    path: Path,
) -> tuple[list[str], list[str], list[str], list[str]]:
    train_text: list[str] = []
    train_label: list[str] = []
    validation_text: list[str] = []
    validation_label: list[str] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
        if not line.strip():
            continue
        row = json.loads(line)
        if set(row) != {"split", "label", "text"}:
            raise ValueError(f"document corpus row {line_number} has an invalid schema")
        destination = row["split"]
        if destination == "train":
            train_text.append(str(row["text"]))
            train_label.append(str(row["label"]))
        elif destination == "validation":
            validation_text.append(str(row["text"]))
            validation_label.append(str(row["label"]))
        else:
            raise ValueError(f"document corpus row {line_number} has an invalid split")
    if len(set(train_label)) != 3 or set(train_label) != set(validation_label):
        raise ValueError(
            "document corpus must have three represented labels in both splits"
        )
    return train_text, train_label, validation_text, validation_label


def _base_vision_pattern(label: str) -> np.ndarray:
    grid_y, grid_x = np.mgrid[0:VISION_SIDE, 0:VISION_SIDE]
    pattern = np.full((VISION_SIDE, VISION_SIDE), 0.08, dtype=np.float64)
    if label == "vertical-array":
        pattern[:, 6:10] = 0.92
    elif label == "horizontal-array":
        pattern[6:10, :] = 0.92
    elif label == "cross-array":
        mask = (np.abs(grid_x - grid_y) <= 1) | (
            np.abs(grid_x + grid_y - (VISION_SIDE - 1)) <= 1
        )
        pattern[mask] = 0.92
    elif label == "orbital-ring":
        radius = np.sqrt((grid_x - 7.5) ** 2 + (grid_y - 7.5) ** 2)
        pattern[(radius >= 4.2) & (radius <= 5.8)] = 0.92
    else:
        raise ValueError(f"unknown vision label: {label}")
    return pattern


def build_vision_dataset() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Build a fixed, source-contained image corpus with disjoint validation samples."""
    rng = np.random.default_rng(SEED)
    train_rows: list[np.ndarray] = []
    train_labels: list[str] = []
    validation_rows: list[np.ndarray] = []
    validation_labels: list[str] = []
    for label in VISION_LABELS:
        base = _base_vision_pattern(label)
        for sample in range(32):
            shifted = np.roll(
                base,
                shift=(int(rng.integers(-1, 2)), int(rng.integers(-1, 2))),
                axis=(0, 1),
            )
            brightness = float(rng.uniform(0.88, 1.08))
            noise = rng.normal(0.0, 0.045, size=base.shape)
            row = np.clip(shifted * brightness + noise, 0.0, 1.0).reshape(-1)
            if sample < 24:
                train_rows.append(row)
                train_labels.append(label)
            else:
                validation_rows.append(row)
                validation_labels.append(label)
    return (
        np.asarray(train_rows, dtype=np.float64),
        np.asarray(train_labels),
        np.asarray(validation_rows, dtype=np.float64),
        np.asarray(validation_labels),
    )


def _document_models() -> dict[str, Pipeline]:
    vectorizer = lambda: TfidfVectorizer(  # noqa: E731 - independent fitted instances
        lowercase=True,
        ngram_range=(1, 2),
        min_df=1,
        sublinear_tf=True,
        norm="l2",
    )
    return {
        "document-logistic-v1": Pipeline(
            [
                ("tfidf", vectorizer()),
                (
                    "classifier",
                    LogisticRegression(
                        random_state=SEED,
                        solver="lbfgs",
                        max_iter=500,
                    ),
                ),
            ]
        ),
        "document-naive-bayes-v1": Pipeline(
            [
                ("tfidf", vectorizer()),
                ("classifier", MultinomialNB(alpha=0.35)),
            ]
        ),
    }


def _vision_models() -> dict[str, Any]:
    return {
        "vision-mlp-v1": MLPClassifier(
            hidden_layer_sizes=(32,),
            activation="relu",
            solver="lbfgs",
            alpha=0.0001,
            batch_size="auto",
            learning_rate_init=0.001,
            max_iter=500,
            shuffle=False,
            random_state=SEED,
            tol=1e-8,
        ),
        "vision-random-forest-v1": RandomForestClassifier(
            n_estimators=48,
            criterion="gini",
            max_depth=8,
            min_samples_leaf=1,
            max_features="sqrt",
            random_state=SEED,
            n_jobs=1,
        ),
    }


def _metric_record(
    expected: Iterable[str], probabilities: np.ndarray, classes: np.ndarray
) -> dict[str, float]:
    expected_array = np.asarray(list(expected))
    predicted = classes[np.argmax(probabilities, axis=1)]
    return {
        "accuracy": round(float(accuracy_score(expected_array, predicted)), 8),
        "log_loss": round(
            float(log_loss(expected_array, probabilities, labels=list(classes))), 8
        ),
    }


@dataclass(frozen=True)
class InversionResult:
    pixels: np.ndarray
    target_label: str
    target_probability: float
    iterations: int


class ModelSuite:
    """Own independently persisted, CPU-only upstream estimators."""

    def __init__(self, state_root: Path, corpus_path: Path) -> None:
        self.state_root = state_root
        self.model_root = state_root / "models"
        self.inventory_path = state_root / "inventory.json"
        self.corpus_path = corpus_path
        self.models: dict[str, Any] = {}
        self.inventory: dict[str, Any] = {}
        state_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.train(reset=True)

    def train(self, *, reset: bool) -> dict[str, Any]:
        if reset:
            shutil.rmtree(self.model_root, ignore_errors=True)
            self.inventory_path.unlink(missing_ok=True)
        self.model_root.mkdir(mode=0o700, parents=True, exist_ok=True)

        train_text, train_label, validation_text, validation_label = (
            _read_document_corpus(self.corpus_path)
        )
        train_images, train_image_labels, validation_images, validation_image_labels = (
            build_vision_dataset()
        )
        models: dict[str, Any] = {}
        metrics: dict[str, dict[str, float]] = {}

        for model_id, model in _document_models().items():
            model.fit(train_text, train_label)
            probabilities = model.predict_proba(validation_text)
            classes = np.asarray(model.classes_)
            models[model_id] = model
            metrics[model_id] = _metric_record(validation_label, probabilities, classes)

        for model_id, model in _vision_models().items():
            model.fit(train_images, train_image_labels)
            probabilities = model.predict_proba(validation_images)
            classes = np.asarray(model.classes_)
            models[model_id] = model
            metrics[model_id] = _metric_record(
                validation_image_labels, probabilities, classes
            )

        records: list[dict[str, Any]] = []
        for model_id in sorted(models):
            artifact = f"{model_id}.parameters.json"
            artifact_path = self.model_root / artifact
            parameter_payload = model_parameter_payload(model_id, models[model_id])
            artifact_path.write_text(
                canonical_json(parameter_payload) + "\n", encoding="utf-8"
            )
            domain = "document" if model_id.startswith("document-") else "vision"
            records.append(
                {
                    "model_id": model_id,
                    "revision": MODEL_REVISIONS[model_id],
                    "domain": domain,
                    "implementation": f"{models[model_id].__class__.__module__}.{models[model_id].__class__.__name__}",
                    "library": "scikit-learn",
                    "library_version": sklearn.__version__,
                    "license": MODEL_LICENSE,
                    "artifact": artifact,
                    "artifact_digest": file_digest(artifact_path),
                    "parameter_digest": model_parameter_digest(
                        model_id, models[model_id]
                    ),
                    "metrics": metrics[model_id],
                }
            )
        model_set_digest = digest_json(
            [
                {
                    "model_id": record["model_id"],
                    "revision": record["revision"],
                    "parameter_digest": record["parameter_digest"],
                }
                for record in records
            ]
        )
        inventory = {
            "schema_version": 1,
            "dataset_revision": DATASET_REVISION,
            "training_seed": SEED,
            "runtime": "cpu",
            "scikit_learn_version": sklearn.__version__,
            "model_set_digest": model_set_digest,
            "models": records,
            "validation": {
                "document_records": len(validation_text),
                "vision_records": len(validation_images),
            },
        }
        self.inventory_path.write_text(
            canonical_json(inventory) + "\n", encoding="utf-8"
        )
        self.models = models
        self.inventory = inventory
        return inventory

    def ready(self) -> bool:
        if (
            set(self.models) != set(MODEL_REVISIONS)
            or not self.inventory_path.is_file()
        ):
            return False
        return all(
            (self.model_root / record["artifact"]).is_file()
            and file_digest(self.model_root / record["artifact"])
            == record["artifact_digest"]
            for record in self.inventory["models"]
        )

    def document_predictions(self, text: str) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for model_id in ("document-logistic-v1", "document-naive-bayes-v1"):
            model = self.models[model_id]
            probabilities = model.predict_proba([text])[0]
            distribution = {
                str(label): round(float(probability), 8)
                for label, probability in zip(
                    model.classes_, probabilities, strict=True
                )
            }
            predicted = max(distribution, key=distribution.__getitem__)
            results.append(
                {
                    "model_id": model_id,
                    "model_revision": MODEL_REVISIONS[model_id],
                    "label": predicted,
                    "confidence": distribution[predicted],
                    "distribution": distribution,
                }
            )
        return results

    def vision_predictions(self, pixels: np.ndarray) -> list[dict[str, Any]]:
        row = np.asarray(pixels, dtype=np.float64).reshape(1, VISION_SIDE * VISION_SIDE)
        results: list[dict[str, Any]] = []
        for model_id in ("vision-mlp-v1", "vision-random-forest-v1"):
            model = self.models[model_id]
            probabilities = model.predict_proba(row)[0]
            distribution = {
                str(label): round(float(probability), 8)
                for label, probability in zip(
                    model.classes_, probabilities, strict=True
                )
            }
            predicted = max(distribution, key=distribution.__getitem__)
            results.append(
                {
                    "model_id": model_id,
                    "model_revision": MODEL_REVISIONS[model_id],
                    "label": predicted,
                    "confidence": distribution[predicted],
                    "distribution": distribution,
                }
            )
        return results

    def invert(
        self, target_label: str, iterations: int, learning_rate: float
    ) -> InversionResult:
        if not 1 <= iterations <= MAX_INVERSION_ITERATIONS:
            raise ValueError(
                f"iterations must be between 1 and {MAX_INVERSION_ITERATIONS}"
            )
        model = self.models["vision-mlp-v1"]
        if target_label not in model.classes_:
            raise ValueError("target label is not represented by the vision model")
        if len(model.coefs_) != 2 or model.activation != "relu":
            raise RuntimeError(
                "vision inversion requires the pinned one-hidden-layer ReLU model"
            )
        target_index = int(np.nonzero(model.classes_ == target_label)[0][0])
        rng = np.random.default_rng(SEED + target_index)
        pixels = np.clip(rng.normal(0.25, 0.04, VISION_SIDE * VISION_SIDE), 0.0, 1.0)
        first_weights, output_weights = model.coefs_
        first_bias, output_bias = model.intercepts_
        probability = 0.0
        for step in range(MAX_INVERSION_ITERATIONS):
            if step >= iterations:
                break
            pre_hidden = pixels @ first_weights + first_bias
            hidden = np.maximum(pre_hidden, 0.0)
            logits = hidden @ output_weights + output_bias
            shifted = logits - np.max(logits)
            probabilities = np.exp(shifted) / np.exp(shifted).sum()
            probability = float(probabilities[target_index])
            output_gradient = -probabilities
            output_gradient[target_index] += 1.0
            hidden_gradient = (output_gradient @ output_weights.T) * (pre_hidden > 0.0)
            pixel_gradient = hidden_gradient @ first_weights.T
            norm = float(np.linalg.norm(pixel_gradient))
            if norm > 0.0:
                pixels = np.clip(
                    pixels + learning_rate * (pixel_gradient / norm), 0.0, 1.0
                )
        final_probability = float(
            model.predict_proba(pixels.reshape(1, -1))[0, target_index]
        )
        return InversionResult(
            pixels=pixels.reshape(VISION_SIDE, VISION_SIDE),
            target_label=target_label,
            target_probability=max(probability, final_probability),
            iterations=iterations,
        )
