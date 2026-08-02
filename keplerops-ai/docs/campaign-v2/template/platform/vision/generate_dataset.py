#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parent
CONTRACT_PATH = ROOT / "contract.json"


def sample_seed(base_seed: int, split: str, class_id: int, index: int) -> int:
    identity = f"{base_seed}:{split}:{class_id}:{index}".encode()
    return int.from_bytes(hashlib.sha256(identity).digest()[:8], "big")


def coordinate_grid() -> tuple[np.ndarray, np.ndarray]:
    coordinates = np.arange(64, dtype=np.float32)
    return np.meshgrid(coordinates, coordinates)


def render_pattern(class_id: int, rng: np.random.Generator) -> np.ndarray:
    x, y = coordinate_grid()
    shift_x, shift_y = rng.integers(-3, 4, size=2)
    cx = 31.5 + float(shift_x)
    cy = 31.5 + float(shift_y)
    image = np.zeros((64, 64, 3), dtype=np.float32)
    image[:] = np.asarray([9.0, 15.0, 22.0], dtype=np.float32)

    if class_id == 0:
        radius = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
        ring = np.exp(-((radius - 18.0) ** 2) / 5.0)
        cross = np.maximum(
            np.exp(-((x - cx) ** 2) / 2.5),
            np.exp(-((y - cy) ** 2) / 2.5),
        )
        pattern = np.clip(ring + 0.55 * cross, 0.0, 1.0)
        color = np.asarray([55.0, 205.0, 232.0])
    elif class_id == 1:
        radius = np.sqrt(((x - cx) / 1.2) ** 2 + ((y - cy) * 1.2) ** 2)
        core = np.exp(-(radius**2) / 90.0)
        lobes = np.exp(-((np.abs(x - cx) - 15.0) ** 2) / 15.0) * np.exp(
            -((y - cy) ** 2) / 75.0
        )
        pattern = np.clip(core + 0.9 * lobes, 0.0, 1.0)
        color = np.asarray([206.0, 93.0, 224.0])
    elif class_id == 2:
        distance = np.abs(x - cx) + np.abs(y - cy)
        diamond = np.clip(1.0 - np.abs(distance - 18.0) / 3.0, 0.0, 1.0)
        sensor = np.exp(-(((x - cx) ** 2) + ((y - cy) ** 2)) / 95.0)
        pattern = np.clip(diamond + 0.75 * sensor, 0.0, 1.0)
        color = np.asarray([244.0, 155.0, 47.0])
    elif class_id == 3:
        period = int(rng.integers(9, 13))
        vertical = np.exp(-((np.mod(x - shift_x, period) - period / 2.0) ** 2) / 1.8)
        horizontal = np.exp(-((np.mod(y - shift_y, period) - period / 2.0) ** 2) / 1.8)
        envelope = np.exp(-(((x - cx) ** 2) + ((y - cy) ** 2)) / 980.0)
        pattern = np.clip(np.maximum(vertical, horizontal) * envelope, 0.0, 1.0)
        color = np.asarray([88.0, 222.0, 139.0])
    else:
        raise ValueError(f"unknown class id: {class_id}")

    image += pattern[..., None] * color
    image += rng.normal(0.0, 3.2, image.shape)
    image *= float(rng.uniform(0.92, 1.08))
    return np.clip(np.rint(image), 0, 255).astype(np.uint8)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "data")
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()

    contract = json.loads(CONTRACT_PATH.read_text())
    output = args.output.resolve()
    if output.exists() and args.replace:
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)

    counts = {
        "train": int(contract["dataset"]["train_images_per_class"]),
        "calibration": int(contract["dataset"]["calibration_images_per_class"]),
        "protected": int(contract["dataset"]["protected_images_per_class"]),
    }
    records: list[dict[str, object]] = []
    for split, count in counts.items():
        for item in contract["classes"]:
            class_id = int(item["id"])
            label = str(item["label"])
            target = output / split / label
            target.mkdir(parents=True, exist_ok=True)
            for index in range(count):
                rng = np.random.default_rng(
                    sample_seed(contract["dataset"]["seed"], split, class_id, index)
                )
                path = target / f"{index:03d}.png"
                Image.fromarray(render_pattern(class_id, rng)).save(
                    path,
                    format="PNG",
                    compress_level=9,
                    optimize=False,
                )
                records.append(
                    {
                        "class_id": class_id,
                        "label": label,
                        "path": path.relative_to(output).as_posix(),
                        "sha256": sha256(path),
                        "split": split,
                    }
                )

    manifest = {
        "contract_sha256": sha256(CONTRACT_PATH),
        "generator": contract["dataset"]["generator"],
        "image_count": len(records),
        "images": records,
        "schema": "keplerops.orion.vision.dataset/v1",
        "seed": contract["dataset"]["seed"],
    }
    (output / "dataset-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    print(f"generated {len(records)} deterministic images in {output}")


if __name__ == "__main__":
    main()
