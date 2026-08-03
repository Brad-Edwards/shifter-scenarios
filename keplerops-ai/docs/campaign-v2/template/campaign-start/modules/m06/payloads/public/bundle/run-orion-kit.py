#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer


ROOT = Path(__file__).resolve().parent
BLUEPRINT = json.loads((ROOT / "orion-agent-blueprint.json").read_text())
MODEL = BLUEPRINT["model"]
INPUT = BLUEPRINT["input"]
OUTPUT = BLUEPRINT["output"]

labels = json.loads((ROOT / MODEL["labels"]).read_text())
id_to_label = {value: key for key, value in labels.items()}
tokenizer = Tokenizer.from_file(str(ROOT / MODEL["tokenizer"]))
tokenizer.enable_truncation(max_length=64)
tokenizer.enable_padding(length=64, pad_id=0, pad_token="[PAD]")
session = ort.InferenceSession(str(ROOT / MODEL["path"]), providers=["CPUExecutionProvider"])
records = [json.loads(line) for line in (ROOT / INPUT["path"]).read_text().splitlines() if line.strip()]
encoded = tokenizer.encode_batch([record[INPUT["field"]] for record in records])
logits = session.run(None, {
    "input_ids": np.asarray([item.ids for item in encoded], dtype=np.int64),
    "attention_mask": np.asarray([item.attention_mask for item in encoded], dtype=np.int64),
    "token_type_ids": np.asarray([item.type_ids for item in encoded], dtype=np.int64),
})[0]
results = [
    {"id": record["id"], "label": id_to_label[int(np.argmax(row))]}
    for record, row in zip(records, logits, strict=True)
]
(ROOT / OUTPUT["path"]).write_text(json.dumps(results, indent=2, sort_keys=True) + "\n")
print(json.dumps({"model": MODEL["path"], "records": len(results), "output": OUTPUT["path"]}, sort_keys=True))
