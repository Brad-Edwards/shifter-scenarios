from __future__ import annotations

import asyncio
import email
import hashlib
import imaplib
import json
import os
import re
import ssl
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from email.policy import default

import httpx
from fastapi import FastAPI, HTTPException


ROOT = Path("/var/lib/edge-observer")
AUDIT = Path("/var/lib/orion-preview/audit")
FLAG = os.environ["EDGE_CORRELATION_FLAG"]
MAIL_HOST = os.environ.get("STALWART_HOST", "10.61.10.20")
MAIL_USER = os.environ.get("STALWART_INTAKE_USER", "partner-intake")
MAIL_PASSWORD = os.environ["STALWART_INTAKE_PASSWORD"]
ZAMMAD = os.environ.get("ZAMMAD_URL", "http://10.61.30.24:8080").rstrip("/")
ZAMMAD_AUTH = (os.environ["ZAMMAD_USER"], os.environ["ZAMMAD_PASSWORD"])


@asynccontextmanager
async def lifespan(_: FastAPI):
    worker = asyncio.create_task(ingestion_loop())
    try:
        yield
    finally:
        worker.cancel()
        try:
            await worker
        except asyncio.CancelledError:
            pass


app = FastAPI(title="KeplerOps External Intake Status", version="2.0", lifespan=lifespan)


def tls_context() -> ssl.SSLContext:
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


def mail_records() -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    with imaplib.IMAP4_SSL(MAIL_HOST, 993, ssl_context=tls_context(), timeout=20) as mailbox:
        mailbox.login(MAIL_USER, MAIL_PASSWORD)
        mailbox.select("INBOX", readonly=True)
        status, ids = mailbox.search(None, "ALL")
        if status != "OK" or not ids[0]:
            return records
        for uid in ids[0].split()[-100:]:
            status, payload = mailbox.fetch(uid, "(RFC822)")
            if status != "OK" or not payload or not isinstance(payload[0], tuple):
                continue
            raw = payload[0][1]
            message = email.message_from_bytes(raw, policy=default)
            sender = str(message.get("From", ""))
            if "cinder.field-operator@cinder.lab" not in sender.lower():
                continue
            references = set(re.findall(rb"EXT-[A-Z0-9-]{6,48}", raw))
            for encoded in references:
                reference = encoded.decode("ascii")
                records[reference] = {
                    "imap_uid": uid.decode(), "message_id": str(message.get("Message-ID", "")),
                    "from": sender, "to": str(message.get("To", "")),
                    "subject": str(message.get("Subject", "")),
                    "rfc822_sha256": hashlib.sha256(raw).hexdigest(),
                    "_rfc822": raw,
                }
    return records


async def zammad_ticket(reference: str, mail: dict[str, Any]) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30, auth=ZAMMAD_AUTH, headers={"Host": "support.keplerops.lab"}) as client:
        found = await client.get(f"{ZAMMAD}/api/v1/tickets/search", params={"query": reference})
        found.raise_for_status()
        tickets = found.json()
        if isinstance(tickets, list) and tickets:
            ticket_id = int(tickets[-1]["id"])
        else:
            created = await client.post(f"{ZAMMAD}/api/v1/tickets", json={
                "title": f"External Orion intake {reference}", "group": "Orion Support", "customer": "reviewer@keplerops.lab",
                "article": {"subject": mail["subject"], "body": f"SMTP Message-ID {mail['message_id']}\nReference {reference}\nRFC822 SHA-256 {mail['rfc822_sha256']}", "type": "note", "sender": "Customer", "internal": False},
            })
            created.raise_for_status(); ticket_id = int(created.json()["id"])
        articles = await client.get(f"{ZAMMAD}/api/v1/ticket_articles/by_ticket/{ticket_id}")
        articles.raise_for_status()
    article = next((item for item in articles.json()
                    if reference in str(item.get("body", ""))
                    and mail["message_id"] in str(item.get("body", ""))
                    and mail["rfc822_sha256"] in str(item.get("body", ""))), None)
    if article is None:
        raise HTTPException(status_code=409, detail="Zammad has not ingested the exact SMTP message")
    return {"ticket_id": ticket_id, "article_id": article["id"]}


async def ingest_once() -> None:
    status_root = ROOT / "status"
    status_root.mkdir(parents=True, exist_ok=True)
    previews = {
        value.get("case_reference"): value
        for path in AUDIT.glob("*.json")
        for value in [json.loads(path.read_text())]
        if value.get("case_reference")
    }
    messages = await asyncio.to_thread(mail_records)
    for reference, mail in messages.items():
        path = status_root / f"{reference}.json"
        if path.exists() or reference not in previews:
            continue
        preview = previews[reference]
        raw = mail.pop("_rfc822")
        if hashlib.sha256(raw).hexdigest() != mail["rfc822_sha256"]:
            continue
        rfc822_root = ROOT / "rfc822"
        rfc822_root.mkdir(parents=True, exist_ok=True)
        rfc822_path = rfc822_root / f"{mail['rfc822_sha256']}.eml"
        try:
            descriptor = os.open(rfc822_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o440)
        except FileExistsError:
            if hashlib.sha256(rfc822_path.read_bytes()).hexdigest() != mail["rfc822_sha256"]:
                continue
        else:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(raw)
        ticket = await zammad_ticket(reference, mail)
        record = {
            "schema": "keplerops.external-intake-status/v2", "operation": "kep-m06-j",
            "model_family": "none", "attempt_id": str(uuid.uuid5(uuid.NAMESPACE_URL, reference)),
            "actor": "cinder-field-operator", "case_reference": reference,
            "preview_event": preview["analysis_id"], "preview_model_sha256": preview["model_sha256"],
            "storing_service": "Stalwart", **mail, "case_system": "Zammad", **ticket,
            "rfc822_object": f"rfc822/{mail['rfc822_sha256']}.eml",
            "status": "correlated", "flag": FLAG,
        }
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
        temporary.replace(path)


async def ingestion_loop() -> None:
    while True:
        try:
            await ingest_once()
        except Exception:
            pass
        await asyncio.sleep(3)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ready", "mail_source": "Stalwart IMAP", "case_system": "Zammad"}


@app.get("/intake-status/{reference}.json")
async def intake_status(reference: str) -> dict[str, Any]:
    if re.fullmatch(r"EXT-[A-Z0-9-]{6,48}", reference) is None:
        raise HTTPException(status_code=404)
    path = ROOT / "status" / f"{reference}.json"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Stalwart and case-system correlation is pending")
    return json.loads(path.read_text())


@app.get("/intake-status/")
def status_index() -> list[dict[str, Any]]:
    return [json.loads(path.read_text()) for path in sorted((ROOT / "status").glob("*.json"))]
