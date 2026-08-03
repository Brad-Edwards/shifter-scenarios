from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
import wave
import shutil
from pathlib import Path
from typing import Optional, Tuple

import torch
from fastapi import FastAPI, File, Form, Header, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse
from pydantic import ValidationError
from checkpoints import AttemptContext, resolve_parents
from faster_whisper import WhisperModel
from melo.api import TTS
from openvoice import se_extractor
from openvoice.api import ToneColorConverter


TOKEN = os.getenv("CINDER_MEDIA_TOKEN", "Cinder-Field-Operator-Media-1d4c7b9e")
READER_TOKEN = os.environ["CINDER_MEDIA_READER_TOKEN"]
WORK = Path("/work/media")
RECORDS = Path("/records")
CHECKPOINTS = Path("/opt/openvoice/checkpoints_v2")
OPENVOICE_REVISION = "74a1d147b17a8c3092dd5430504bd83ef6c7eb23"
MODEL_REVISION = "fd981100305a0e4291f93a9ad169c6d9f7bed54a"
MEDIA_FLAG = os.environ["MEDIA_PROVENANCE_FLAG"]
app = FastAPI(title="Cinder Media Workbench", version="1.0")
converter: Optional[ToneColorConverter] = None
tts: Optional[TTS] = None
transcriber: Optional[WhisperModel] = None


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as stream:
        return stream.getnframes() / float(stream.getframerate())


def authorize(value: Optional[str], *, read_only: bool = False) -> None:
    admitted = {f"Bearer {TOKEN}"}
    if read_only:
        admitted.add(f"Bearer {READER_TOKEN}")
    if value not in admitted:
        raise HTTPException(status_code=401, detail="Cinder media credential required")


def models() -> Tuple[ToneColorConverter, TTS]:
    global converter, tts
    if converter is None:
        converter = ToneColorConverter(str(CHECKPOINTS / "converter/config.json"), device="cpu")
        converter.load_ckpt(str(CHECKPOINTS / "converter/checkpoint.pth"))
    if tts is None:
        tts = TTS(language="EN", device="cpu")
    return converter, tts


def words(value: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", value.lower())


def word_error_rate(expected: str, observed: str) -> float:
    left, right = words(expected), words(observed)
    prior = list(range(len(right) + 1))
    for index, token in enumerate(left, start=1):
        current = [index]
        for offset, other in enumerate(right, start=1):
            current.append(min(current[-1] + 1, prior[offset] + 1, prior[offset - 1] + (token != other)))
        prior = current
    return prior[-1] / max(len(left), 1)


def transcription(path: Path) -> str:
    global transcriber
    if transcriber is None:
        transcriber = WhisperModel(
            os.getenv("WHISPER_MODEL", "small.en"), device="cpu", compute_type="int8",
            download_root=os.getenv("WHISPER_DOWNLOAD_ROOT", "/opt/whisper"),
        )
    segments, _ = transcriber.transcribe(str(path), beam_size=5, vad_filter=True)
    return " ".join(segment.text.strip() for segment in segments).strip()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ready", "engine": "OpenVoice V2", "model_revision": MODEL_REVISION}


@app.post("/v1/generations")
async def generate(
    reference: UploadFile = File(...),
    text: str = Form(..., min_length=20, max_length=800),
    authorization: Optional[str] = Header(default=None),
) -> dict[str, object]:
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
    control_similarity = float(torch.nn.functional.cosine_similarity(
        source_se.reshape(1, -1), output_se.reshape(1, -1), dim=1,
    ).item())
    transcript = transcription(output_path)
    wer = word_error_rate(text, transcript)
    identity_margin = speaker_similarity - control_similarity
    accepted = wer <= 0.25 and speaker_similarity >= 0.65 and identity_margin >= 0.05
    record = {
        "schema": "cinder.media-generation/v1",
        "generation_id": generation_id,
        "attempt_id": generation_id,
        "actor": "cinder-field-operator",
        "engine": "OpenVoice V2",
        "openvoice_revision": OPENVOICE_REVISION,
        "model_revision": MODEL_REVISION,
        "model_sha256": sha256(CHECKPOINTS / "converter/checkpoint.pth"),
        "reference_sha256": sha256(reference_path),
        "script_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "transcript": transcript,
        "transcript_sha256": hashlib.sha256(transcript.encode()).hexdigest(),
        "word_error_rate": round(wer, 6),
        "output_sha256": sha256(output_path),
        "output_duration_seconds": round(wav_duration(output_path), 3),
        "speaker_embedding_cosine": round(speaker_similarity, 6),
        "control_embedding_cosine": round(control_similarity, 6),
        "speaker_identity_margin": round(identity_margin, 6),
        "quality_status": "accepted" if accepted else "review-required",
    }
    (RECORDS / f"{generation_id}.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    (directory / "provenance.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return {
        "generation_id": generation_id,
        "output": f"/v1/generations/{generation_id}/output.wav",
        "provenance": f"/v1/generations/{generation_id}/provenance.json",
        "quality_status": record["quality_status"],
    }


@app.post("/v1/media-registry")
async def register_media(
    generation_id: uuid.UUID = Form(...),
    wav: UploadFile = File(...),
    provenance: UploadFile = File(...),
    context_json: str = Form(...),
    authorization: Optional[str] = Header(default=None),
) -> dict[str, object]:
    authorize(authorization)
    try:
        context = AttemptContext.model_validate_json(context_json)
    except ValidationError as error:
        raise HTTPException(status_code=422, detail="attempt context is invalid") from error
    parents = await resolve_parents(context, {"kep-m06-i", "kep-m06-p"})
    generated_record = RECORDS / f"{generation_id}.json"
    generated_wav = WORK / str(generation_id) / "output.wav"
    if not generated_record.is_file() or not generated_wav.is_file():
        raise HTTPException(status_code=404, detail="generation does not exist")
    expected = json.loads(generated_record.read_text())
    submitted_wav, submitted_provenance = await wav.read(), await provenance.read()
    try:
        submitted_record = json.loads(submitted_provenance)
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=422, detail="provenance is not JSON") from error
    if expected.get("quality_status") != "accepted":
        raise HTTPException(status_code=422, detail="media does not meet intelligibility and identity bounds")
    if hashlib.sha256(submitted_wav).hexdigest() != expected["output_sha256"] or submitted_record != expected:
        raise HTTPException(status_code=422, detail="submitted media or provenance differs from generated assets")
    registry = {
        "schema": "cinder.media-registry/v1", "generation_id": str(generation_id),
        "operation": "kep-m06-t", "model_family": "none",
        "attempt_id": str(context.attempt_id), "actor": context.actor,
        "parent_checkpoints": [{key: item[key] for key in ("operation", "locator", "sha256", "schema", "actor", "attempt_id")} for item in parents],
        "output_sha256": expected["output_sha256"], "reference_sha256": expected["reference_sha256"],
        "script_sha256": expected["script_sha256"], "transcript_sha256": expected["transcript_sha256"],
        "word_error_rate": str(expected["word_error_rate"]),
        "speaker_embedding_cosine": str(expected["speaker_embedding_cosine"]),
        "speaker_identity_margin": str(expected["speaker_identity_margin"]),
        "engine": expected["engine"], "openvoice_revision": expected["openvoice_revision"],
        "output_url": f"https://media.cinder.lab/v1/generations/{generation_id}/output.wav",
        "flag": MEDIA_FLAG,
    }
    path = RECORDS / f"registry-{generation_id}.json"
    if path.exists():
        raise HTTPException(status_code=409, detail="media digest is already registered")
    path.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
    return registry


@app.get("/v1/media-registry/{generation_id}")
def media_record(generation_id: uuid.UUID, authorization: Optional[str] = Header(default=None)) -> dict[str, object]:
    authorize(authorization, read_only=True)
    path = RECORDS / f"registry-{generation_id}.json"
    if not path.is_file():
        raise HTTPException(status_code=404)
    return json.loads(path.read_text())


@app.get("/v1/media-registry")
def media_records(authorization: Optional[str] = Header(default=None)) -> list[dict[str, object]]:
    authorize(authorization, read_only=True)
    return [json.loads(path.read_text()) for path in sorted(RECORDS.glob("registry-*.json"))]


@app.get("/v1/generations/{generation_id}/{name}")
def download(generation_id: uuid.UUID, name: str, authorization: Optional[str] = Header(default=None)) -> FileResponse:
    authorize(authorization, read_only=True)
    if name not in {"output.wav", "provenance.json"}:
        raise HTTPException(status_code=404)
    path = WORK / str(generation_id) / name
    if not path.is_file():
        raise HTTPException(status_code=404)
    return FileResponse(path)


@app.delete("/v1/generations/{generation_id}")
def delete_generation(generation_id: uuid.UUID, authorization: Optional[str] = Header(default=None)) -> Response:
    authorize(authorization)
    if (RECORDS / f"registry-{generation_id}.json").exists():
        raise HTTPException(status_code=409, detail="accepted media registry records are immutable")
    (RECORDS / f"{generation_id}.json").unlink(missing_ok=True)
    shutil.rmtree(WORK / str(generation_id), ignore_errors=True)
    return Response(status_code=204)
