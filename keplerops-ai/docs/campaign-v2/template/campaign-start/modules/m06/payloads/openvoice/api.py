from __future__ import annotations

import hashlib
import json
import os
import uuid
import wave
import shutil
from pathlib import Path
from typing import Optional, Tuple

import torch
from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from melo.api import TTS
from openvoice import se_extractor
from openvoice.api import ToneColorConverter


TOKEN = os.getenv("CINDER_MEDIA_TOKEN", "Cinder-Media-cinder-operator-1d4c7b9e")
WORK = Path("/work/media")
RECORDS = Path("/records")
CHECKPOINTS = Path("/opt/openvoice/checkpoints_v2")
OPENVOICE_REVISION = "74a1d147b17a8c3092dd5430504bd83ef6c7eb23"
MODEL_REVISION = "fd981100305a0e4291f93a9ad169c6d9f7bed54a"
app = FastAPI(title="Cinder Media Workbench", version="1.0")
converter: Optional[ToneColorConverter] = None
tts: Optional[TTS] = None


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as stream:
        return stream.getnframes() / float(stream.getframerate())


def authorize(value: Optional[str]) -> None:
    if value != f"Bearer {TOKEN}":
        raise HTTPException(status_code=401, detail="Cinder media credential required")


def models() -> Tuple[ToneColorConverter, TTS]:
    global converter, tts
    if converter is None:
        converter = ToneColorConverter(str(CHECKPOINTS / "converter/config.json"), device="cpu")
        converter.load_ckpt(str(CHECKPOINTS / "converter/checkpoint.pth"))
    if tts is None:
        tts = TTS(language="EN", device="cpu")
    return converter, tts


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ready", "engine": "OpenVoice V2", "model_revision": MODEL_REVISION}


@app.post("/v1/generations")
async def generate(
    reference: UploadFile = File(...),
    text: str = Form(..., min_length=20, max_length=800),
    authorization: Optional[str] = Header(default=None),
) -> dict[str, str]:
    authorize(authorization)
    generation_id = str(uuid.uuid4())
    directory = WORK / generation_id
    directory.mkdir(parents=True, exist_ok=False)
    RECORDS.mkdir(parents=True, exist_ok=True)
    reference_path = directory / "reference.wav"
    reference_path.write_bytes(await reference.read())
    base_path = directory / "base.wav"
    output_path = directory / "output.wav"
    engine, synthesizer = models()
    target_se, _ = se_extractor.get_se(str(reference_path), engine, vad=True)
    speaker_id = next(iter(synthesizer.hps.data.spk2id.values()))
    synthesizer.tts_to_file(text, speaker_id, str(base_path), speed=1.0)
    source_se = torch.load(CHECKPOINTS / "base_speakers/ses/en-default.pth", map_location="cpu")
    engine.convert(
        audio_src_path=str(base_path), src_se=source_se, tgt_se=target_se,
        output_path=str(output_path), message="Cinder Media Workbench",
    )
    output_se, _ = se_extractor.get_se(str(output_path), engine, vad=True)
    speaker_similarity = float(torch.nn.functional.cosine_similarity(
        target_se.reshape(1, -1), output_se.reshape(1, -1), dim=1,
    ).item())
    record = {
        "schema": "cinder.media-generation/v1",
        "generation_id": generation_id,
        "operator": "cinder-operator",
        "engine": "OpenVoice V2",
        "openvoice_revision": OPENVOICE_REVISION,
        "model_revision": MODEL_REVISION,
        "model_sha256": sha256(CHECKPOINTS / "converter/checkpoint.pth"),
        "reference_sha256": sha256(reference_path),
        "script_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "output_sha256": sha256(output_path),
        "output_duration_seconds": round(wav_duration(output_path), 3),
        "speaker_embedding_cosine": round(speaker_similarity, 6),
    }
    (RECORDS / f"{generation_id}.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    (directory / "provenance.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return {
        "generation_id": generation_id,
        "output": f"/v1/generations/{generation_id}/output.wav",
        "provenance": f"/v1/generations/{generation_id}/provenance.json",
    }


@app.get("/v1/generations/{generation_id}/{name}")
def download(generation_id: uuid.UUID, name: str, authorization: Optional[str] = Header(default=None)) -> FileResponse:
    authorize(authorization)
    if name not in {"output.wav", "provenance.json"}:
        raise HTTPException(status_code=404)
    path = WORK / str(generation_id) / name
    if not path.is_file():
        raise HTTPException(status_code=404)
    return FileResponse(path)


@app.delete("/v1/generations/{generation_id}", status_code=204)
def delete_generation(generation_id: uuid.UUID, authorization: Optional[str] = Header(default=None)) -> None:
    authorize(authorization)
    (RECORDS / f"{generation_id}.json").unlink(missing_ok=True)
    shutil.rmtree(WORK / str(generation_id), ignore_errors=True)
