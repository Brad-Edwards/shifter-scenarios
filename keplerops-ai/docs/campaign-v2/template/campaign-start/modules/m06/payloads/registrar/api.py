from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shutil
import socket
import ssl
import subprocess
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote, urlencode, urlparse

from fastapi import FastAPI, Header, HTTPException, Request, Response
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
WEBROOT = ROOT / "webroot"
ACTIVE_CADDYFILE = ROOT / "Caddyfile.active"
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
    body: Optional[str] = Field(default=None, min_length=1, max_length=20000)


class CertificateIssueRequest(BaseModel):
    contact: Optional[str] = Field(default=None, max_length=120)


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


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def read(kind: str, value: uuid.UUID) -> dict[str, Any]:
    path = ROOT / kind / f"{value}.json"
    if not path.is_file():
        raise HTTPException(status_code=404)
    return json.loads(path.read_text())


def record_for_domain_name(domain: str) -> dict[str, Any] | None:
    domain = domain.lower().rstrip(".")
    for path in (ROOT / "domains").glob("*.json"):
        value = json.loads(path.read_text())
        if value.get("domain") == domain:
            return value
    return None


def request_domain(request: Request) -> str:
    return request.headers.get("host", "").split(":", 1)[0].lower().rstrip(".")


def service_body_path(record: dict[str, Any]) -> Path:
    return WEBROOT / record["domain"] / "ownership.txt"


def challenge_path(domain: str, token: str) -> Path:
    return WEBROOT / domain / ".well-known" / "acme-challenge" / token


@app.middleware("http")
async def serve_acme_challenge_before_routing(request: Request, call_next):
    prefix = "/.well-known/acme-challenge/"
    if request.url.path.startswith(prefix):
        token = request.url.path[len(prefix):]
        record = record_for_domain_name(request_domain(request))
        if record is None:
            return Response("domain not registered\n", status_code=404, media_type="text/plain")
        path = challenge_path(record["domain"], token)
        if not path.is_file():
            return Response("challenge token not found\n", status_code=404, media_type="text/plain")
        return Response(path.read_text(), media_type="text/plain")
    return await call_next(request)


def step_binary() -> str:
    candidate = shutil.which("step") or "/usr/local/bin/step"
    if not Path(candidate).exists():
        raise HTTPException(status_code=503, detail="Smallstep client is not installed in the registrar runtime")
    return candidate


def require_step_provisioner(certificate_path: Path) -> None:
    inspected = subprocess.run(
        [step_binary(), "certificate", "inspect", str(certificate_path), "--format", "json"],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    if inspected.returncode != 0:
        raise HTTPException(status_code=422, detail="Smallstep certificate inspection failed")
    try:
        value = json.loads(inspected.stdout)
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=422, detail="Smallstep certificate inspection was not JSON") from error

    found = False

    def walk(node: Any) -> None:
        nonlocal found
        if isinstance(node, dict):
            for key, item in node.items():
                normalized = str(key).lower().replace("-", "_")
                if normalized == "step_provisioner" and str(item) == "cinder-acme":
                    found = True
                if normalized == "provisioner" and isinstance(item, dict) and str(item.get("name")) == "cinder-acme":
                    found = True
                walk(item)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(value)
    serialized = json.dumps(value, sort_keys=True)
    if not found and not ("cinder-acme" in serialized and "provisioner" in serialized.lower()):
        raise HTTPException(status_code=422, detail="certificate lacks Smallstep cinder-acme provisioner evidence")


def install_verified_certificate(
    domain_id: uuid.UUID,
    record: dict[str, Any],
    certificate_path: Path,
    private_key_path: Path,
) -> dict[str, Any]:
    parsed = subprocess.run(
        ["openssl", "x509", "-in", str(certificate_path), "-noout", "-checkend", "3600",
         "-fingerprint", "-sha256", "-issuer", "-ext", "subjectAltName"],
        capture_output=True,
        text=True,
        check=False,
    )
    cert_key = subprocess.run(
        ["openssl", "x509", "-in", str(certificate_path), "-pubkey", "-noout"],
        capture_output=True,
        check=False,
    ).stdout
    private_public = subprocess.run(
        ["openssl", "pkey", "-in", str(private_key_path), "-pubout"],
        capture_output=True,
        check=False,
    ).stdout
    if parsed.returncode != 0 or record["domain"] not in parsed.stdout:
        raise HTTPException(status_code=422, detail="certificate is invalid, expiring, or lacks the registered domain")
    if not cert_key or cert_key != private_public:
        raise HTTPException(status_code=422, detail="private key does not match the ACME certificate")
    require_step_provisioner(certificate_path)
    fingerprint = next(
        (line.split("=", 1)[1].replace(":", "").lower()
         for line in parsed.stdout.splitlines() if "Fingerprint=" in line),
        "",
    )
    certificate_store = Path("/etc/caddy/cinder-certs/current.crt")
    key_store = Path("/etc/caddy/cinder-certs/current.key")
    backup_root = ROOT / "certificate-backups"
    backup_root.mkdir(parents=True, exist_ok=True)
    backup_certificate = backup_root / f"{domain_id}.crt"
    backup_key = backup_root / f"{domain_id}.key"
    if not backup_certificate.exists() and not backup_key.exists():
        backup_certificate.write_bytes(certificate_store.read_bytes())
        backup_key.write_bytes(key_store.read_bytes())
        backup_certificate.chmod(0o600)
        backup_key.chmod(0o600)
    certificate_store.write_bytes(certificate_path.read_bytes())
    key_store.write_bytes(private_key_path.read_bytes())
    certificate_store.chmod(0o600)
    key_store.chmod(0o600)
    reload_caddy()
    context = ssl.create_default_context(cafile="/etc/cinder/trust-bundle.crt")
    with socket.create_connection((record["domain"], 443), timeout=10) as connection:
        with context.wrap_socket(connection, server_hostname=record["domain"]) as tls:
            live_fingerprint = hashlib.sha256(tls.getpeercert(binary_form=True)).hexdigest()
    if fingerprint != live_fingerprint:
        raise HTTPException(status_code=422, detail="live service does not present the exact managed ACME certificate")
    return {
        "fingerprint_sha256": fingerprint,
        "acme_order_status": "valid",
        "issuer_verified": True,
        "step_provisioner": "cinder-acme",
        "managed_by": "registrar-step-cli",
    }


def domain_record(domain_id: uuid.UUID) -> dict[str, Any]:
    return read("domains", domain_id)


def ensure_domain_mutable(domain_id: uuid.UUID) -> None:
    if (ROOT / "manifests" / f"{domain_id}.json").exists():
        raise HTTPException(status_code=409, detail="accepted Cinder domain ownership is immutable")


def reload_caddy() -> None:
    config = ACTIVE_CADDYFILE if ACTIVE_CADDYFILE.is_file() else Path("/etc/caddy/Caddyfile")
    reloaded = subprocess.run(
        ["curl", "--fail", "--silent", "--show-error", "--unix-socket", os.environ["CADDY_ADMIN_SOCKET"],
         "-H", "Content-Type: text/caddyfile", "-H", "Cache-Control: must-revalidate",
         "--data-binary", f"@{config}", "http://localhost/load"],
        capture_output=True, text=True, timeout=30, check=False,
    )
    if reloaded.returncode != 0:
        raise HTTPException(status_code=503, detail=f"Caddy did not load the Cinder certificate: {reloaded.stderr[-400:]}")


def keycloak_token() -> str:
    body = urlencode({"client_id": "admin-cli", "grant_type": "password", "username": KEYCLOAK_ADMIN, "password": KEYCLOAK_PASSWORD}).encode()
    request = urllib.request.Request(f"{KEYCLOAK}/realms/master/protocol/openid-connect/token", data=body, method="POST")
    request.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read())["access_token"]


def keycloak_user(username: str) -> dict[str, Any] | None:
    values = api(f"{KEYCLOAK}/admin/realms/{KEYCLOAK_REALM}/users?username={quote(username)}&exact=true", headers={"Authorization": f"Bearer {keycloak_token()}"})
    return values[0] if values else None


def stalwart_principal(name: str) -> dict[str, Any] | None:
    try:
        direct = api(
            f"{STALWART}/api/principal/{quote(name, safe='')}",
            headers={"Authorization": f"Basic {STALWART_AUTH}"},
        )
    except Exception:
        direct = {}
    for value in (direct.get("data"), direct.get("item")):
        if isinstance(value, dict) and value.get("name") == name:
            return value
    listing = api(
        f"{STALWART}/api/principal?filter={quote(name)}",
        headers={"Authorization": f"Basic {STALWART_AUTH}"},
    )
    for item in listing.get("data", {}).get("items", []):
        if isinstance(item, dict) and item.get("name") == name:
            return item
    return None


def ensure_stalwart_domain(name: str) -> dict[str, Any]:
    principal = stalwart_principal(name)
    if principal is None:
        created = api(
            f"{STALWART}/api/principal",
            "POST",
            {"type": "domain", "name": name, "description": "Participant Cinder domain"},
            {"Authorization": f"Basic {STALWART_AUTH}"},
        )
        if created.get("error") and created.get("error") != "fieldAlreadyExists":
            raise HTTPException(status_code=502, detail=f"Stalwart rejected domain {name}")
        principal = stalwart_principal(name)
    if principal is None or principal.get("type") != "domain":
        raise HTTPException(status_code=502, detail=f"Stalwart domain {name} was not materialized")
    return principal


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
    principal = ensure_stalwart_domain(record["domain"])
    result = {
        "address": address,
        "principal": principal["name"],
        "principal_type": "domain",
        "managed_by": "cinder-registrar-mail-domain",
    }
    record["mail_identity"] = result
    write(ROOT / "domains" / f"{domain_id}.json", record)
    return result


@app.get("/.well-known/acme-challenge/{token}")
def get_acme_challenge(token: str, request: Request) -> Response:
    if not re.fullmatch(r"[A-Za-z0-9_-]{10,200}", token):
        raise HTTPException(status_code=404)
    record = record_for_domain_name(request_domain(request))
    if record is None:
        raise HTTPException(status_code=404)
    path = challenge_path(record["domain"], token)
    if not path.is_file():
        raise HTTPException(status_code=404)
    return Response(path.read_text(), media_type="text/plain")


@app.get("/ownership.txt")
def get_published_service(request: Request) -> Response:
    record = record_for_domain_name(request_domain(request))
    if record is None:
        raise HTTPException(status_code=404)
    body = service_body_path(record)
    if not body.is_file():
        raise HTTPException(status_code=404)
    return Response(body.read_text(), media_type="text/plain; charset=utf-8")


@app.post("/v1/domains/{domain_id}/services")
def attach_service(domain_id: uuid.UUID, request: PublishedService, authorization: Optional[str] = Header(default=None)) -> dict[str, Any]:
    authorize(authorization)
    ensure_domain_mutable(domain_id)
    record = domain_record(domain_id)
    parsed_url = urlparse(str(request.url))
    if parsed_url.scheme != "https" or parsed_url.hostname != record["domain"]:
        raise HTTPException(status_code=422, detail="service URL must use the registered domain over TLS")
    if request.body is not None:
        if parsed_url.path != "/ownership.txt":
            raise HTTPException(status_code=422, detail="registrar-managed service bodies are served at /ownership.txt")
        observed = hashlib.sha256(request.body.encode()).hexdigest()
        if observed != request.expected_body_sha256:
            raise HTTPException(status_code=422, detail="managed service body differs from the declared revision")
        body_path = service_body_path(record)
        body_path.parent.mkdir(parents=True, exist_ok=True)
        body_path.write_text(request.body)
        body_path.chmod(0o644)
    try:
        with urllib.request.urlopen(str(request.url), timeout=15) as response:
            body = response.read(2 * 1024 * 1024)
    except Exception as error:
        raise HTTPException(status_code=422, detail="published service is not reachable") from error
    observed = hashlib.sha256(body).hexdigest()
    if observed != request.expected_body_sha256:
        raise HTTPException(status_code=422, detail="published service body differs from the declared revision")
    result = {
        "url": str(request.url),
        "body_sha256": observed,
        "managed_by": "cinder-registrar" if request.body is not None else "external",
    }
    record["service"] = result
    write(ROOT / "domains" / f"{domain_id}.json", record)
    return result


@app.post("/v1/domains/{domain_id}/certificates/issue")
def issue_certificate(
    domain_id: uuid.UUID,
    request: CertificateIssueRequest,
    authorization: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    authorize(authorization)
    ensure_domain_mutable(domain_id)
    if any((ROOT / "manifests").glob("*.json")):
        raise HTTPException(status_code=409, detail="the accepted Cinder certificate is immutable")
    record = domain_record(domain_id)
    if not record.get("dns_records") or not record.get("mail_identity") or not record.get("service"):
        raise HTTPException(status_code=409, detail="DNS, mail, and service must be completed before managed certificate issuance")
    other_certificates = [
        value for path in (ROOT / "domains").glob("*.json")
        for value in [json.loads(path.read_text())]
        if value.get("domain_id") != str(domain_id) and value.get("certificate")
    ]
    if other_certificates:
        raise HTTPException(status_code=409, detail="reset the other incomplete certificate attempt before installing this one")

    domain = record["domain"]
    webroot = WEBROOT / domain
    issued = ROOT / "issued-certificates"
    webroot.mkdir(parents=True, exist_ok=True)
    issued.mkdir(parents=True, exist_ok=True)
    certificate_path = issued / f"{domain_id}.crt"
    private_key_path = issued / f"{domain_id}.key"
    command = [
        step_binary(), "ca", "certificate", domain, str(certificate_path), str(private_key_path),
        "--force", "--ca-url", "https://ca.keplerops.lab", "--root", "/etc/cinder/trust-bundle.crt",
        "--provisioner", "cinder-acme", "--acme", "https://ca.keplerops.lab/acme/cinder-acme/directory",
        "--webroot", str(webroot), "--san", domain,
    ]
    if request.contact:
        command.extend(["--contact", request.contact])
    issued_result = subprocess.run(command, capture_output=True, text=True, timeout=120, check=False)
    if issued_result.returncode != 0:
        detail = (issued_result.stderr or issued_result.stdout)[-800:]
        raise HTTPException(status_code=503, detail=f"managed ACME issuance failed: {detail}")

    result = install_verified_certificate(domain_id, record, certificate_path, private_key_path)
    result["acme_directory"] = "https://ca.keplerops.lab/acme/cinder-acme/directory"
    result["acme_order_url"] = result["acme_directory"]
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
    principal = stalwart_principal(record["mail_identity"]["principal"])
    mail_domain_live = bool(
        principal
        and principal.get("type") == "domain"
        and record["mail_identity"]["address"].endswith(f"@{record['domain']}")
    )
    live = urllib.request.urlopen(record["service"]["url"], timeout=15).read(2 * 1024 * 1024)
    if (
        identity is None
        or identity["id"] != account["keycloak_user_id"]
        or not mail_domain_live
        or hashlib.sha256(live).hexdigest() != record["service"]["body_sha256"]
        or record["certificate"].get("acme_order_status") != "valid"
        or record["certificate"].get("step_provisioner") != "cinder-acme"
    ):
        raise HTTPException(status_code=409, detail="live identity, mail, service, or ACME ownership no longer agrees")
    manifest = {"schema": "cinder.domain-ownership/v1", "operation": "kep-m06-n", "model_family": "none",
                "domain_id": str(domain_id), "account_id": record["account_id"], "domain": record["domain"],
                "attempt_id": account["attempt_id"], "actor": account["owner"], "keycloak_user_id": account["keycloak_user_id"],
                "parent_checkpoints": account["parent_checkpoints"],
                "zone_serial": zone.get("serial"), "mail_identity": record["mail_identity"]["address"],
                "service_url": record["service"]["url"], "certificate_fingerprint": record["certificate"]["fingerprint_sha256"],
                "acme_order_url": record["certificate"]["acme_order_url"],
                "acme_directory": record["certificate"]["acme_directory"],
                "step_provisioner": record["certificate"]["step_provisioner"], "flag": OWNERSHIP_FLAG}
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


@app.delete("/v1/accounts/{account_id}")
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
