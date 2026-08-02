from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import socket
import ssl
import subprocess
import tempfile
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote, urlencode, urlparse

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field, HttpUrl
from checkpoints import AttemptContext, resolve_parents


TOKEN = os.environ["CINDER_REGISTRAR_TOKEN"]
READER_TOKEN = os.environ["CINDER_CHECKPOINT_READER_TOKEN"]
PDNS = os.environ["PDNS_API_URL"].rstrip("/")
PDNS_KEY = os.environ["PDNS_API_KEY"]
STALWART = os.environ["STALWART_API_URL"].rstrip("/")
STALWART_AUTH = base64.b64encode(f"{os.environ['STALWART_ADMIN_USER']}:{os.environ['STALWART_ADMIN_PASSWORD']}".encode()).decode()
KEYCLOAK = os.environ["KEYCLOAK_URL"].rstrip("/")
KEYCLOAK_REALM = os.environ.get("KEYCLOAK_REALM", "keplerops")
KEYCLOAK_ADMIN = os.environ["KEYCLOAK_ADMIN"]
KEYCLOAK_PASSWORD = os.environ["KEYCLOAK_ADMIN_PASSWORD"]
OWNERSHIP_FLAG = os.environ["OWNERSHIP_FLAG"]
ROOT = Path("/var/lib/cinder-registrar")
app = FastAPI(title="Cinder Domains", version="2.0")


class AccountRequest(BaseModel):
    context: AttemptContext
    username: str = Field(pattern=r"^[a-z][a-z0-9.-]{2,30}$")
    display_name: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=14, max_length=128)


class DomainRequest(BaseModel):
    account_id: uuid.UUID
    label: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,30}$")


class DnsRecord(BaseModel):
    name: str = Field(pattern=r"^(@|[a-z0-9][a-z0-9-]{0,30})$")
    type: str = Field(pattern=r"^(A|AAAA|CNAME|MX|TXT)$")
    content: str = Field(min_length=1, max_length=500)
    ttl: int = Field(ge=30, le=86400)


class MailIdentity(BaseModel):
    localpart: str = Field(pattern=r"^[a-z0-9][a-z0-9.-]{1,30}$")


class PublishedService(BaseModel):
    url: HttpUrl
    expected_body_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class CertificateRecord(BaseModel):
    certificate_pem: str = Field(min_length=200, max_length=20000)
    private_key_pem: str = Field(min_length=200, max_length=20000)
    acme_order_url: HttpUrl
    acme_order_jws: dict[str, Any]
    acme_certificate_jws: dict[str, Any]


def authorize(value: Optional[str], *, read_only: bool = False) -> None:
    admitted = {f"Bearer {TOKEN}"}
    if read_only:
        admitted.add(f"Bearer {READER_TOKEN}")
    if value not in admitted:
        raise HTTPException(status_code=401, detail="Cinder Domains credential required")


def api(url: str, method: str = "GET", payload: object = None, headers: Optional[dict[str, str]] = None) -> Any:
    body = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(url, data=body, method=method)
    request.add_header("Content-Type", "application/json")
    for name, value in (headers or {}).items():
        request.add_header(name, value)
    with urllib.request.urlopen(request, timeout=30) as response:
        raw = response.read()
    return json.loads(raw) if raw else {}


def raw_api(url: str, method: str = "GET", payload: object = None, headers: Optional[dict[str, str]] = None) -> bytes:
    body = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(url, data=body, method=method)
    for name, value in (headers or {}).items(): request.add_header(name, value)
    with urllib.request.urlopen(request, timeout=30) as response: return response.read()


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def read(kind: str, value: uuid.UUID) -> dict[str, Any]:
    path = ROOT / kind / f"{value}.json"
    if not path.is_file():
        raise HTTPException(status_code=404)
    return json.loads(path.read_text())


def domain_record(domain_id: uuid.UUID) -> dict[str, Any]:
    return read("domains", domain_id)


def ensure_domain_mutable(domain_id: uuid.UUID) -> None:
    if (ROOT / "manifests" / f"{domain_id}.json").exists():
        raise HTTPException(status_code=409, detail="accepted Cinder domain ownership is immutable")


def reload_caddy() -> None:
    reloaded = subprocess.run(
        ["curl", "--fail", "--silent", "--show-error", "--unix-socket", os.environ["CADDY_ADMIN_SOCKET"],
         "-H", "Content-Type: text/caddyfile", "--data-binary", "@/etc/caddy/Caddyfile", "http://localhost/load"],
        capture_output=True, text=True, timeout=30, check=False,
    )
    if reloaded.returncode != 0:
        raise HTTPException(status_code=503, detail="Caddy did not load the Cinder certificate")


def keycloak_token() -> str:
    body = urlencode({"client_id": "admin-cli", "grant_type": "password", "username": KEYCLOAK_ADMIN, "password": KEYCLOAK_PASSWORD}).encode()
    request = urllib.request.Request(f"{KEYCLOAK}/realms/master/protocol/openid-connect/token", data=body, method="POST")
    request.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read())["access_token"]


def keycloak_user(username: str) -> dict[str, Any] | None:
    values = api(f"{KEYCLOAK}/admin/realms/{KEYCLOAK_REALM}/users?username={quote(username)}&exact=true", headers={"Authorization": f"Bearer {keycloak_token()}"})
    return values[0] if values else None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ready", "registrar": "Cinder Domains"}


@app.post("/v1/accounts")
async def create_account(request: AccountRequest, authorization: Optional[str] = Header(default=None)) -> dict[str, Any]:
    authorize(authorization)
    parents = await resolve_parents(request.context, {"kep-m06-i"})
    if any(json.loads(path.read_text()).get("username") == request.username for path in (ROOT / "accounts").glob("*.json")):
        raise HTTPException(status_code=409, detail="account name is unavailable")
    principal_name = f"cinder-{request.username}"
    if keycloak_user(principal_name) is not None:
        raise HTTPException(status_code=409, detail="enterprise identity is unavailable")
    create = urllib.request.Request(f"{KEYCLOAK}/admin/realms/{KEYCLOAK_REALM}/users", data=json.dumps({
        "username": principal_name, "enabled": True, "firstName": request.display_name,
        "email": f"{request.username}@cinder.lab", "emailVerified": True,
        "attributes": {"range_actor": ["cinder-field-operator"]},
        "credentials": [{"type": "password", "value": request.password, "temporary": False}],
    }).encode(), method="POST")
    create.add_header("Content-Type", "application/json"); create.add_header("Authorization", f"Bearer {keycloak_token()}")
    with urllib.request.urlopen(create, timeout=20): pass
    identity = keycloak_user(principal_name)
    if identity is None:
        raise HTTPException(status_code=503, detail="Keycloak identity was not materialized")
    account_id = uuid.uuid4()
    record = {"schema": "cinder.domain-account/v1", "account_id": str(account_id), "username": request.username,
              "display_name": request.display_name, "owner": request.context.actor, "identity_provider": "keycloak",
              "keycloak_user_id": identity["id"], "attempt_id": str(request.context.attempt_id),
              "parent_checkpoints": [{key: item[key] for key in ("operation", "locator", "sha256", "schema", "actor", "attempt_id")} for item in parents],
              "status": "active"}
    write(ROOT / "accounts" / f"{account_id}.json", record)
    return record


@app.post("/v1/domains")
def register_domain(request: DomainRequest, authorization: Optional[str] = Header(default=None)) -> dict[str, Any]:
    authorize(authorization)
    account = read("accounts", request.account_id)
    domain = f"{request.label}.cinder.lab"
    if any(json.loads(path.read_text()).get("domain") == domain for path in (ROOT / "domains").glob("*.json")):
        raise HTTPException(status_code=409, detail="domain is unavailable")
    domain_id = uuid.uuid4()
    record = {"schema": "cinder.registered-domain/v1", "domain_id": str(domain_id), "domain": domain,
              "account_id": account["account_id"], "owner": account["username"], "status": "registered", "dns_records": []}
    write(ROOT / "domains" / f"{domain_id}.json", record)
    return record


@app.put("/v1/domains/{domain_id}/dns")
def put_dns(domain_id: uuid.UUID, request: DnsRecord, authorization: Optional[str] = Header(default=None)) -> dict[str, Any]:
    authorize(authorization)
    ensure_domain_mutable(domain_id)
    record = domain_record(domain_id)
    fqdn = record["domain"] if request.name == "@" else f"{request.name}.{record['domain']}"
    content = request.content
    if request.type == "MX" and not re.fullmatch(r"[0-9]+ [A-Za-z0-9.-]+\.?", content):
        raise HTTPException(status_code=422, detail="MX content requires priority and host")
    rrset = {"rrsets": [{"name": f"{fqdn}.", "type": request.type, "ttl": request.ttl, "changetype": "REPLACE",
                         "records": [{"content": content, "disabled": False}]}]}
    api(f"{PDNS}/zones/cinder.lab.", "PATCH", rrset, {"X-API-Key": PDNS_KEY})
    entry = request.model_dump() | {"fqdn": fqdn}
    record["dns_records"] = [item for item in record["dns_records"] if not (item["name"] == request.name and item["type"] == request.type)] + [entry]
    write(ROOT / "domains" / f"{domain_id}.json", record)
    return entry


@app.post("/v1/domains/{domain_id}/mail-identities")
def add_mail(domain_id: uuid.UUID, request: MailIdentity, authorization: Optional[str] = Header(default=None)) -> dict[str, Any]:
    authorize(authorization)
    ensure_domain_mutable(domain_id)
    record = domain_record(domain_id)
    address = f"{request.localpart}@{record['domain']}"
    principal_name = f"cinder.{record['owner']}"
    try:
        principal = api(f"{STALWART}/api/principal/{principal_name}", headers={"Authorization": f"Basic {STALWART_AUTH}"})
    except Exception:
        api(f"{STALWART}/api/principal", "POST", {"type": "individual", "name": principal_name, "description": "Assigned Cinder operator domain owner", "emails": [address]}, {"Authorization": f"Basic {STALWART_AUTH}"})
        principal = api(f"{STALWART}/api/principal/{principal_name}", headers={"Authorization": f"Basic {STALWART_AUTH}"})
    emails = sorted(set(principal.get("data", {}).get("emails", []) + [address]))
    api(f"{STALWART}/api/principal/{principal_name}", "PATCH", [{"action": "set", "field": "emails", "value": emails}],
        {"Authorization": f"Basic {STALWART_AUTH}"})
    result = {"address": address, "principal": principal_name}
    record["mail_identity"] = result
    write(ROOT / "domains" / f"{domain_id}.json", record)
    return result


@app.post("/v1/domains/{domain_id}/services")
def attach_service(domain_id: uuid.UUID, request: PublishedService, authorization: Optional[str] = Header(default=None)) -> dict[str, Any]:
    authorize(authorization)
    ensure_domain_mutable(domain_id)
    record = domain_record(domain_id)
    parsed_url = urlparse(str(request.url))
    if parsed_url.scheme != "https" or parsed_url.hostname != record["domain"]:
        raise HTTPException(status_code=422, detail="service URL must use the registered domain over TLS")
    try:
        with urllib.request.urlopen(str(request.url), timeout=15) as response:
            body = response.read(2 * 1024 * 1024)
    except Exception as error:
        raise HTTPException(status_code=422, detail="published service is not reachable") from error
    observed = hashlib.sha256(body).hexdigest()
    if observed != request.expected_body_sha256:
        raise HTTPException(status_code=422, detail="published service body differs from the declared revision")
    result = {"url": str(request.url), "body_sha256": observed}
    record["service"] = result
    write(ROOT / "domains" / f"{domain_id}.json", record)
    return result


@app.post("/v1/domains/{domain_id}/certificates")
def attach_certificate(domain_id: uuid.UUID, request: CertificateRecord, authorization: Optional[str] = Header(default=None)) -> dict[str, Any]:
    authorize(authorization)
    ensure_domain_mutable(domain_id)
    if any((ROOT / "manifests").glob("*.json")):
        raise HTTPException(status_code=409, detail="the accepted Cinder certificate is immutable")
    other_certificates = [
        value for path in (ROOT / "domains").glob("*.json")
        for value in [json.loads(path.read_text())]
        if value.get("domain_id") != str(domain_id) and value.get("certificate")
    ]
    if other_certificates:
        raise HTTPException(status_code=409, detail="reset the other incomplete certificate attempt before installing this one")
    record = domain_record(domain_id)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".pem") as certificate, tempfile.NamedTemporaryFile(mode="w", suffix=".key") as private_key:
        certificate.write(request.certificate_pem)
        certificate.flush()
        private_key.write(request.private_key_pem); private_key.flush()
        command = ["openssl", "x509", "-in", certificate.name, "-noout", "-checkend", "3600", "-fingerprint", "-sha256", "-issuer", "-ext", "subjectAltName"]
        parsed = subprocess.run(command, capture_output=True, text=True, check=False)
        cert_key = subprocess.run(["openssl", "x509", "-in", certificate.name, "-pubkey", "-noout"], capture_output=True, check=False).stdout
        private_public = subprocess.run(["openssl", "pkey", "-in", private_key.name, "-pubout"], capture_output=True, check=False).stdout
    if parsed.returncode != 0 or record["domain"] not in parsed.stdout:
        raise HTTPException(status_code=422, detail="certificate is invalid, expiring, or lacks the registered domain")
    if "KeplerOps AI Systems Internal CA" not in parsed.stdout:
        raise HTTPException(status_code=422, detail="certificate was not issued by the Cinder ACME authority")
    if not cert_key or cert_key != private_public:
        raise HTTPException(status_code=422, detail="private key does not match the ACME certificate")
    fingerprint = next((line.split("=", 1)[1].replace(":", "").lower() for line in parsed.stdout.splitlines() if "Fingerprint=" in line), "")
    order_url = urlparse(str(request.acme_order_url))
    if order_url.scheme != "https" or order_url.hostname not in {"ca.keplerops.lab", "10.61.20.21"}:
        raise HTTPException(status_code=422, detail="ACME order is not owned by the Cinder CA")
    order = api(str(request.acme_order_url), "POST", request.acme_order_jws, {"Content-Type": "application/jose+json"})
    identifiers = {item.get("value") for item in order.get("identifiers", [])}
    if order.get("status") != "valid" or record["domain"] not in identifiers or not order.get("certificate"):
        raise HTTPException(status_code=422, detail="ACME order is not valid for the registered domain")
    issued_chain = raw_api(order["certificate"], "POST", request.acme_certificate_jws, {"Content-Type": "application/jose+json"})
    with tempfile.NamedTemporaryFile(suffix=".pem") as issued:
        issued.write(issued_chain); issued.flush()
        issued_fingerprint = subprocess.run(["openssl", "x509", "-in", issued.name, "-noout", "-fingerprint", "-sha256"], capture_output=True, text=True, check=False)
    issued_value = next((line.split("=", 1)[1].replace(":", "").lower() for line in issued_fingerprint.stdout.splitlines() if "Fingerprint=" in line), "")
    if issued_value != fingerprint:
        raise HTTPException(status_code=422, detail="submitted certificate is not the exact ACME order certificate")
    certificate_path, key_path = Path("/etc/caddy/cinder-certs/current.crt"), Path("/etc/caddy/cinder-certs/current.key")
    backup_root = ROOT / "certificate-backups"
    backup_root.mkdir(parents=True, exist_ok=True)
    backup_certificate = backup_root / f"{domain_id}.crt"
    backup_key = backup_root / f"{domain_id}.key"
    if not backup_certificate.exists() and not backup_key.exists():
        backup_certificate.write_bytes(certificate_path.read_bytes())
        backup_key.write_bytes(key_path.read_bytes())
        backup_certificate.chmod(0o600); backup_key.chmod(0o600)
    certificate_path.write_text(request.certificate_pem); key_path.write_text(request.private_key_pem)
    certificate_path.chmod(0o600); key_path.chmod(0o600)
    reload_caddy()
    context = ssl.create_default_context()
    with socket.create_connection((record["domain"], 443), timeout=10) as connection:
        with context.wrap_socket(connection, server_hostname=record["domain"]) as tls:
            live_fingerprint = hashlib.sha256(tls.getpeercert(binary_form=True)).hexdigest()
    if fingerprint != live_fingerprint:
        raise HTTPException(status_code=422, detail="live service does not present the exact ACME order certificate")
    result = {"fingerprint_sha256": fingerprint, "acme_order_url": str(request.acme_order_url),
              "acme_order_status": order["status"], "acme_certificate_url": order["certificate"], "issuer_verified": True}
    record["certificate"] = result
    write(ROOT / "domains" / f"{domain_id}.json", record)
    return result


@app.post("/v1/domains/{domain_id}/ownership-manifest")
def ownership_manifest(domain_id: uuid.UUID, authorization: Optional[str] = Header(default=None)) -> dict[str, Any]:
    authorize(authorization)
    manifest_path = ROOT / "manifests" / f"{domain_id}.json"
    if manifest_path.exists():
        return json.loads(manifest_path.read_text())
    record = domain_record(domain_id)
    required = ("dns_records", "mail_identity", "service", "certificate")
    if any(not record.get(field) for field in required):
        raise HTTPException(status_code=409, detail="account, DNS, mail, service, and ACME certificate must be completed separately")
    zone = api(f"{PDNS}/zones/cinder.lab.", headers={"X-API-Key": PDNS_KEY})
    account = read("accounts", uuid.UUID(record["account_id"]))
    identity = keycloak_user(f"cinder-{account['username']}")
    principal = api(f"{STALWART}/api/principal/{record['mail_identity']['principal']}", headers={"Authorization": f"Basic {STALWART_AUTH}"})
    live = urllib.request.urlopen(record["service"]["url"], timeout=15).read(2 * 1024 * 1024)
    if identity is None or identity["id"] != account["keycloak_user_id"] or record["mail_identity"]["address"] not in principal.get("data", {}).get("emails", []) or hashlib.sha256(live).hexdigest() != record["service"]["body_sha256"] or record["certificate"].get("acme_order_status") != "valid":
        raise HTTPException(status_code=409, detail="live identity, mail, service, or ACME ownership no longer agrees")
    manifest = {"schema": "cinder.domain-ownership/v1", "operation": "kep-m06-n", "model_family": "none",
                "domain_id": str(domain_id), "account_id": record["account_id"], "domain": record["domain"],
                "attempt_id": account["attempt_id"], "actor": account["owner"], "keycloak_user_id": account["keycloak_user_id"],
                "parent_checkpoints": account["parent_checkpoints"],
                "zone_serial": zone.get("serial"), "mail_identity": record["mail_identity"]["address"],
                "service_url": record["service"]["url"], "certificate_fingerprint": record["certificate"]["fingerprint_sha256"],
                "acme_order_url": record["certificate"]["acme_order_url"], "flag": OWNERSHIP_FLAG}
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(manifest_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o440)
    except FileExistsError:
        return json.loads(manifest_path.read_text())
    with os.fdopen(descriptor, "w") as stream:
        stream.write(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


@app.get("/v1/domains/{domain_id}")
def get_domain(domain_id: uuid.UUID, authorization: Optional[str] = Header(default=None)) -> dict[str, Any]:
    authorize(authorization, read_only=True)
    return domain_record(domain_id)


@app.get("/v1/ownership-manifests")
def ownership_manifests(authorization: Optional[str] = Header(default=None)) -> list[dict[str, Any]]:
    authorize(authorization, read_only=True)
    return [json.loads(path.read_text()) for path in sorted((ROOT / "manifests").glob("*.json"))]


@app.get("/v1/ownership-manifests/{domain_id}")
def get_ownership_manifest(domain_id: uuid.UUID, authorization: Optional[str] = Header(default=None)) -> dict[str, Any]:
    authorize(authorization, read_only=True)
    path = ROOT / "manifests" / f"{domain_id}.json"
    if not path.is_file(): raise HTTPException(status_code=404)
    return json.loads(path.read_text())


@app.get("/v1/accounts")
def accounts(authorization: Optional[str] = Header(default=None)) -> list[dict[str, Any]]:
    authorize(authorization, read_only=True)
    return [json.loads(path.read_text()) for path in sorted((ROOT / "accounts").glob("*.json"))]


@app.delete("/v1/accounts/{account_id}", status_code=204)
def delete_account(account_id: uuid.UUID, authorization: Optional[str] = Header(default=None)) -> None:
    authorize(authorization)
    account = read("accounts", account_id)
    domains = [json.loads(path.read_text()) for path in (ROOT / "domains").glob("*.json") if json.loads(path.read_text()).get("account_id") == str(account_id)]
    if any((ROOT / "manifests" / f"{domain['domain_id']}.json").exists() for domain in domains):
        raise HTTPException(status_code=409, detail="accepted domain ownership is immutable")
    for domain in domains:
        rrsets = [{"name": f"{item['fqdn']}.", "type": item["type"], "changetype": "DELETE"} for item in domain.get("dns_records", [])]
        if rrsets:
            api(f"{PDNS}/zones/cinder.lab.", "PATCH", {"rrsets": rrsets}, {"X-API-Key": PDNS_KEY})
        principal = (domain.get("mail_identity") or {}).get("principal")
        if principal:
            try: api(f"{STALWART}/api/principal/{principal}", "DELETE", headers={"Authorization": f"Basic {STALWART_AUTH}"})
            except Exception: pass
        backup_root = ROOT / "certificate-backups"
        backup_certificate = backup_root / f"{domain['domain_id']}.crt"
        backup_key = backup_root / f"{domain['domain_id']}.key"
        if backup_certificate.is_file() and backup_key.is_file():
            Path("/etc/caddy/cinder-certs/current.crt").write_bytes(backup_certificate.read_bytes())
            Path("/etc/caddy/cinder-certs/current.key").write_bytes(backup_key.read_bytes())
            Path("/etc/caddy/cinder-certs/current.crt").chmod(0o600)
            Path("/etc/caddy/cinder-certs/current.key").chmod(0o600)
            reload_caddy()
            backup_certificate.unlink(); backup_key.unlink()
        (ROOT / "domains" / f"{domain['domain_id']}.json").unlink(missing_ok=True)
    identity = keycloak_user(f"cinder-{account['username']}")
    if identity:
        request = urllib.request.Request(f"{KEYCLOAK}/admin/realms/{KEYCLOAK_REALM}/users/{identity['id']}", method="DELETE")
        request.add_header("Authorization", f"Bearer {keycloak_token()}")
        with urllib.request.urlopen(request, timeout=20): pass
    (ROOT / "accounts" / f"{account_id}.json").unlink(missing_ok=True)
