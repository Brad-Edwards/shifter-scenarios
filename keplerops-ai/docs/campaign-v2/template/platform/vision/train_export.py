#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import tempfile
from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort
import torch
from PIL import Image

from model import OrionVisionResNet


ROOT = Path(__file__).resolve().parent
CONTRACT_PATH = ROOT / "contract.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha256(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def configure_determinism(seed: int) -> None:
    os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"
    os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)


def preprocess(path: Path, contract: dict[str, object]) -> np.ndarray:
    settings = contract["preprocessing"]
    image = Image.open(path).convert("RGB")
    expected = (int(settings["width"]), int(settings["height"]))
    if image.size != expected:
        raise ValueError(f"{path} has size {image.size}, expected {expected}")
    pixels = np.asarray(image, dtype=np.float32) * float(settings["pixel_scale"])
    mean = np.asarray(settings["mean"], dtype=np.float32)
    std = np.asarray(settings["std"], dtype=np.float32)
    normalized = (pixels - mean) / std
    return np.transpose(normalized, (2, 0, 1)).astype(np.float32)


def load_split(
    data_dir: Path, split: str, contract: dict[str, object]
) -> tuple[torch.Tensor, torch.Tensor, list[Path]]:
    images: list[np.ndarray] = []
    labels: list[int] = []
    paths: list[Path] = []
    for item in contract["classes"]:
        class_paths = sorted((data_dir / split / item["label"]).glob("*.png"))
        if not class_paths:
            raise ValueError(f"no {split} images found for {item['label']}")
        for path in class_paths:
            images.append(preprocess(path, contract))
            labels.append(int(item["id"]))
            paths.append(path)
    return (
        torch.from_numpy(np.stack(images)),
        torch.tensor(labels, dtype=torch.long),
        paths,
    )


def softmax(logits: np.ndarray, temperature: float) -> np.ndarray:
    scaled = logits / temperature
    shifted = scaled - np.max(scaled, axis=1, keepdims=True)
    exponent = np.exp(shifted)
    return exponent / np.sum(exponent, axis=1, keepdims=True)


def export_onnx(model: OrionVisionResNet, path: Path) -> None:
    model.eval()
    with tempfile.NamedTemporaryFile(suffix=".onnx", delete=False) as handle:
        temporary = Path(handle.name)
    try:
        torch.onnx.export(
            model,
            torch.zeros((1, 3, 64, 64), dtype=torch.float32),
            temporary,
            input_names=["images"],
            output_names=["logits"],
            dynamic_axes={"images": {0: "batch"}, "logits": {0: "batch"}},
            opset_version=17,
            do_constant_folding=True,
            dynamo=False,
        )
        graph = onnx.load(temporary)
        onnx.checker.check_model(graph)
        onnx.save_model(graph, path)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT.parent / "images" / "orion-vision" / "artifacts",
    )
    args = parser.parse_args()

    contract = json.loads(CONTRACT_PATH.read_text())
    seed = int(contract["training"]["seed"])
    configure_determinism(seed)
    data_dir = args.data_dir.resolve()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)

    manifest_path = data_dir / "dataset-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for record in manifest["images"]:
        path = data_dir / record["path"]
        if sha256(path) != record["sha256"]:
            raise ValueError(f"dataset digest mismatch: {record['path']}")

    train_images, train_labels, _ = load_split(data_dir, "train", contract)
    heldout_images, heldout_labels, _ = load_split(
        data_dir, "calibration", contract
    )
    protected_images, protected_labels, protected_paths = load_split(
        data_dir, "protected", contract
    )

    model = OrionVisionResNet(class_count=len(contract["classes"]))
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=float(contract["training"]["learning_rate"]),
        weight_decay=float(contract["training"]["weight_decay"]),
    )
    criterion = torch.nn.CrossEntropyLoss()
    batch_size = int(contract["training"]["batch_size"])
    generator = torch.Generator().manual_seed(seed)
    model.train()
    for _ in range(int(contract["training"]["epochs"])):
        permutation = torch.randperm(len(train_labels), generator=generator)
        for start in range(0, len(train_labels), batch_size):
            selection = permutation[start : start + batch_size]
            optimizer.zero_grad(set_to_none=True)
            loss = criterion(model(train_images[selection]), train_labels[selection])
            loss.backward()
            optimizer.step()

    model.eval()
    onnx_path = output / "orion-vision-prototype.onnx"
    export_onnx(model, onnx_path)

    session = ort.InferenceSession(
        str(onnx_path), providers=["CPUExecutionProvider"]
    )
    heldout_logits = session.run(
        ["logits"], {"images": heldout_images.numpy()}
    )[0]
    temperature = float(contract["training"]["softmax_temperature"])
    probabilities = softmax(heldout_logits, temperature)
    predictions = np.argmax(probabilities, axis=1)
    expected = heldout_labels.numpy()
    accuracy = float(np.mean(predictions == expected))
    per_class = {}
    for item in contract["classes"]:
        class_id = int(item["id"])
        mask = expected == class_id
        per_class[item["label"]] = float(np.mean(predictions[mask] == expected[mask]))
    if accuracy < 0.95 or min(per_class.values()) < 0.875:
        raise RuntimeError(
            f"held-out evaluation failed: accuracy={accuracy:.4f}, per_class={per_class}"
        )

    class_map = {item["label"]: int(item["id"]) for item in contract["classes"]}
    preprocessing = contract["preprocessing"]
    (output / "class-map.json").write_text(
        json.dumps(class_map, indent=2, sort_keys=True) + "\n"
    )
    (output / "preprocessing.json").write_text(
        json.dumps(preprocessing, indent=2, sort_keys=True) + "\n"
    )

    model_metadata = {
        "architecture": contract["architecture"],
        "class_count": len(class_map),
        "class_map_sha256": canonical_sha256(class_map),
        "dataset_manifest_sha256": sha256(manifest_path),
        "input_name": "images",
        "input_shape": [None, 3, 64, 64],
        "model_family": contract["model_family"],
        "model_name": contract["model_name"],
        "onnx_opset": 17,
        "onnx_sha256": sha256(onnx_path),
        "output_name": "logits",
        "output_shape": [None, len(class_map)],
        "preprocessing_sha256": canonical_sha256(preprocessing),
        "revision": contract["revision"],
        "runtime": "onnxruntime-cpu",
        "schema": "keplerops.orion.vision.model/v1",
        "softmax_temperature": temperature,
        "training_seed": seed,
    }
    (output / "model-metadata.json").write_text(
        json.dumps(model_metadata, indent=2, sort_keys=True) + "\n"
    )

    protected_logits = session.run(
        ["logits"], {"images": protected_images.numpy()}
    )[0]
    protected_probabilities = softmax(protected_logits, temperature)
    reference_index = next(
        index
        for index, path in enumerate(protected_paths)
        if path.parent.name == "thermal_sensor"
    )
    reference = {
        "class_index": int(protected_labels[reference_index]),
        "image": protected_paths[reference_index].relative_to(data_dir).as_posix(),
        "label": contract["classes"][int(protected_labels[reference_index])]["label"],
        "model_sha256": sha256(onnx_path),
        "probabilities": [
            round(float(value), 8) for value in protected_probabilities[reference_index]
        ],
        "schema": "keplerops.orion.vision.reference/v1",
    }
    (output / "reference-inference.json").write_text(
        json.dumps(reference, indent=2, sort_keys=True) + "\n"
    )
    heldout_report = {
        "accuracy": round(accuracy, 8),
        "heldout_image_count": len(heldout_labels),
        "mean_max_score": round(float(np.mean(np.max(probabilities, axis=1))), 8),
        "model_sha256": sha256(onnx_path),
        "per_class_accuracy": {key: round(value, 8) for key, value in per_class.items()},
        "schema": "keplerops.orion.vision.heldout-evaluation/v1",
    }
    (output / "heldout-evaluation-report.json").write_text(
        json.dumps(heldout_report, indent=2, sort_keys=True) + "\n"
    )
    print(
        f"exported {contract['model_name']} sha256:{sha256(onnx_path)} "
        f"heldout_accuracy={accuracy:.4f}"
    )


if __name__ == "__main__":
    main()
