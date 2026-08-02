from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import socket
import ssl
import time
import urllib.request
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel


TOKEN = os.getenv("CINDER_REGISTRAR_TOKEN", "Cinder-Registrar-cinder-operator-4c8e2a7f")
PDNS = os.getenv("PDNS_API_URL", "http://10.61.10.10:8081/api/v1/servers/localhost")
PDNS_KEY = os.getenv("PDNS_API_KEY", "KeplerV2-Training-PDNS")
STALWART = os.getenv("STALWART_API_URL", "http://10.61.10.20:8080")
STALWART_AUTH = base64.b64encode(
    f"{os.getenv('STALWART_ADMIN_USER', 'range-admin')}:{os.getenv('STALWART_ADMIN_PASSWORD', 'KeplerV2-Training-Stalwart')}".encode()
).decode()
RECORDS = Path("/records")
app = FastAPI(title="Cinder Registrar", version="1.0")


class Order(BaseModel):
    label: str
    mailbox_localpart: str = "operator"


def authorize(value: Optional[str]) -> None:
    if value != f"Bearer {TOKEN}":
        raise HTTPException(status_code=401, detail="Cinder registrar credential required")


def request(url: str, method: str = "GET", payload: object = None, headers: Optional[dict[str, str]] = None) -> object:
    body = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Content-Type", "application/json")
    for name, value in (headers or {}).items():
        req.add_header(name, value)
    with urllib.request.urlopen(req, timeout=30) as response:
        raw = response.read()
    return json.loads(raw) if raw else {}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ready", "registrar": "Cinder Domains"}


@app.post("/v1/orders")
def create_order(order: Order, authorization: Optional[str] = Header(default=None)) -> dict[str, object]:
    authorize(authorization)
    if re.fullmatch(r"[a-z0-9][a-z0-9-]{2,30}", order.label) is None:
        raise HTTPException(status_code=400, detail="invalid Cinder domain label")
    if re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,30}", order.mailbox_localpart) is None:
        raise HTTPException(status_code=400, detail="invalid mailbox localpart")
    domain = f"{order.label}.cinder.lab"
    mailbox = f"{order.mailbox_localpart}@{domain}"
    rrsets = {"rrsets": [
        {"name": f"{domain}.", "type": "A", "ttl": 60, "changetype": "REPLACE", "records": [{"content": "10.61.90.2", "disabled": False}]},
        {"name": f"{domain}.", "type": "MX", "ttl": 60, "changetype": "REPLACE", "records": [{"content": "10 mail.cinder.lab.", "disabled": False}]},
    ]}
    request(f"{PDNS}/zones/cinder.lab.", "PATCH", rrsets, {"X-API-Key": PDNS_KEY})
    principal = request(f"{STALWART}/api/principal/cinder.operator", headers={"Authorization": f"Basic {STALWART_AUTH}"})
    emails = sorted(set(principal.get("data", {}).get("emails", []) + ["cinder.operator@cinder.lab", mailbox]))
    request(
        f"{STALWART}/api/principal/cinder.operator", "PATCH",
        [{"action": "set", "field": "emails", "value": emails}],
        {"Authorization": f"Basic {STALWART_AUTH}"},
    )
    fingerprint = ""
    for _ in range(30):
        try:
            context = ssl.create_default_context()
            with socket.create_connection((domain, 443), timeout=5) as connection:
                with context.wrap_socket(connection, server_hostname=domain) as tls:
                    fingerprint = hashlib.sha256(tls.getpeercert(binary_form=True)).hexdigest()
            break
        except OSError:
            time.sleep(2)
    if not fingerprint:
        raise HTTPException(status_code=502, detail="DNS or ACME lifecycle did not converge")
    zone = request(f"{PDNS}/zones/cinder.lab.", headers={"X-API-Key": PDNS_KEY})
    order_id = str(uuid.uuid4())
    record = {
        "schema": "cinder.registrar-order/v1", "order_id": order_id,
        "account": "cinder-operator", "domain": domain, "mail_identity": mailbox,
        "service_url": f"https://{domain}/", "zone_serial": zone.get("serial"),
        "certificate_fingerprint": fingerprint, "status": "active",
    }
    RECORDS.mkdir(parents=True, exist_ok=True)
    (RECORDS / f"{order_id}.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return record


@app.get("/v1/orders/{order_id}")
def get_order(order_id: uuid.UUID, authorization: Optional[str] = Header(default=None)) -> dict[str, object]:
    authorize(authorization)
    path = RECORDS / f"{order_id}.json"
    if not path.is_file():
        raise HTTPException(status_code=404)
    return json.loads(path.read_text())


@app.delete("/v1/orders/{order_id}", status_code=204)
def delete_order(order_id: uuid.UUID, authorization: Optional[str] = Header(default=None)) -> None:
    authorize(authorization)
    path = RECORDS / f"{order_id}.json"
    if not path.is_file():
        return
    record = json.loads(path.read_text())
    domain = str(record["domain"])
    request(f"{PDNS}/zones/cinder.lab.", "PATCH", {"rrsets": [
        {"name": f"{domain}.", "type": "A", "ttl": 60, "changetype": "DELETE", "records": []},
        {"name": f"{domain}.", "type": "MX", "ttl": 60, "changetype": "DELETE", "records": []},
    ]}, {"X-API-Key": PDNS_KEY})
    principal = request(f"{STALWART}/api/principal/cinder.operator", headers={"Authorization": f"Basic {STALWART_AUTH}"})
    emails = [value for value in principal.get("data", {}).get("emails", []) if value != record["mail_identity"]]
    request(f"{STALWART}/api/principal/cinder.operator", "PATCH",
            [{"action": "set", "field": "emails", "value": emails}],
            {"Authorization": f"Basic {STALWART_AUTH}"})
    path.unlink()
