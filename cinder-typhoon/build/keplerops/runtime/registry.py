"""FieldLink release approval, inspection, and retained compatibility services."""

from __future__ import annotations

import base64
import binascii
import http.client as _http_client
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import unicodedata
from urllib.parse import urlsplit
import uuid

from cryptography.exceptions import InvalidSignature, InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from http_support import (
    KeplerHandler, append_audit, canonical_bytes, serve_http, serve_tls, sha256_bytes, utc_now,
)
from credentials import credential
from package_delivery import pack_connector, consume_package
from channel_credentials import issue as issue_channel_credentials


STATE = Path("/var/lib/fieldkest-registry")
AUDIT = STATE / "audit"
RESULTS = STATE / "results"
PUBLISHED = STATE / "published"

# Persistent HTTP/1.1 connection to the assessor.  Keep-alive is required for
# K07.2: when the inspection-envelope endpoint forwards the envelope with
# Content-Length = front_following_length (smaller than the actual body), the
# assessor reads only CL bytes.  The surplus bytes remain in the socket and
# become the prefix of the NEXT request on this connection — the framing exploit.
_ASSESSOR_CONN: _http_client.HTTPConnection | None = None
_ASSESSOR_LOCK = threading.Lock()


def _get_assessor_conn() -> _http_client.HTTPConnection:
    global _ASSESSOR_CONN
    with _ASSESSOR_LOCK:
        if _ASSESSOR_CONN is None or _ASSESSOR_CONN.sock is None:
            _ASSESSOR_CONN = _http_client.HTTPConnection("127.0.0.1", 9001, timeout=5)
        return _ASSESSOR_CONN


def _reset_assessor_conn() -> None:
    global _ASSESSOR_CONN
    with _ASSESSOR_LOCK:
        _ASSESSOR_CONN = None
CHANNEL_CREDENTIAL = PUBLISHED / "delivery/channel-credential.json"
CONFIG = json.loads((STATE / "config/foundation.json").read_text())
K29_CONFIG = json.loads((STATE / "config/release-lineage.json").read_text())
USERNAME = CONFIG["developer"]["username"]
TOKEN = credential("developer_token")
PUBLISHER_TOKEN = credential("registry_publisher_token")
RELEASE_ADMIN_TOKEN = credential("registry_release_admin_token")
RANGE_SECRET = credential("connector_package_internal")
def load_record(kind: str, name: str) -> dict[str, object]:
    return json.loads((STATE / "records" / kind / f"{name}.json").read_text())


def derive_key(context: dict[str, object], info: bytes) -> bytes:
    try:
        ikm = bytes.fromhex(str(context["ikm_hex"]))
        salt = bytes.fromhex(str(context["salt_hex"]))
    except (KeyError, ValueError):
        raise ValueError("invalid_context")
    if len(ikm) != 32 or salt.hex() != "6669656c646b6573742d656e7469746c656d656e742d7631":
        raise ValueError("invalid_context")
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=salt, info=info).derive(ikm)


def write_channel_credentials(value: dict[str, object]) -> None:
    CHANNEL_CREDENTIAL.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        dir=CHANNEL_CREDENTIAL.parent, prefix=".channel-credential."
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o644)
        os.replace(temporary, CHANNEL_CREDENTIAL)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class RegistryHandler(KeplerHandler):
    def _developer(self) -> bool:
        return self.basic_or_bearer(USERNAME, TOKEN)

    def _require_developer(self) -> bool:
        if self._developer():
            return True
        self.send_json(401, {"error": "authentication_required"})
        return False

    def _protected_assessment(self, assessment_id: str) -> None:
        import re as _re
        # Support "latest" to retrieve the most recent protected assessment
        # (the participant may not know the UUID without the connection-poisoning path)
        if assessment_id == "latest":
            candidates = sorted(RESULTS.glob("protected-assessment-*.json"), reverse=True)
            if not candidates:
                self.send_json(404, {"error": "assessment_not_found"})
                return
            result_path = candidates[0]
            assessment_id = result_path.stem.removeprefix("protected-assessment-")
        else:
            if not _re.fullmatch(r"[0-9a-f-]{36}", assessment_id):
                self.send_json(404, {"error": "assessment_not_found"})
                return
            result_path = RESULTS / f"protected-assessment-{assessment_id}.json"
            if not result_path.is_file():
                self.send_json(404, {"error": "assessment_not_found"})
                return
        result = json.loads(result_path.read_text())
        append_audit(AUDIT, "protected-assessment-reads", {
            "request_id": self.request_id, "principal": USERNAME,
            "assessment_id": assessment_id,
            "inspection_id": result.get("inspection_id", ""),
            "status": 200,
        })
        self.send_json(200, result)

    def _privileged_result(self) -> None:
        # This record only exists after /assess/privileged was reached via K07.2
        # surplus bytes.  The participant cannot read @keplerops/support-rehearsal
        # directly (developer identity is denied by Verdaccio ACL); this route
        # delivers the private package data fetched by the assessor's CI reader.
        result_path = RESULTS / "privileged-result.json"
        if not result_path.is_file():
            self.send_json(404, {"error": "privileged_result_not_found"})
            return
        result = json.loads(result_path.read_text())
        append_audit(AUDIT, "privileged-reads", {
            "request_id": self.request_id, "principal": USERNAME,
            "assessment_id": result.get("assessment_id", ""), "status": 200,
        })
        self.send_json(200, result)

    def do_GET(self) -> None:
        if urlsplit(self.path).path == "/.well-known/fieldkest-client":
            inventory = json.loads(Path("/opt/fieldkest/client_documents.json").read_text())
            self.send_json(200, inventory["documents"]["delivery.keplerops.test"])
            return
        path = urlsplit(self.path).path
        if path == "/api/release-administration/session":
            if self.headers.get("Authorization", "") != f"Bearer {RELEASE_ADMIN_TOKEN}":
                self.send_json(403, {"error": "release_administration_denied"})
                return
            value = {
                "principal": "svc-release-admin",
                "approval_scope": "fieldlink-connector-rehearsal",
                "approval_route": "/api/releases/{release_id}/approval",
                "consumer": "support-rehearsal-v3",
                "consumer_interface": "fieldkest.connector/v3",
                "approval_request": {
                    "interfaces": ["fieldkest.connector/v2", "fieldkest.connector/v3"],
                    "lineage": K29_CONFIG["lineage"],
                    "key_id": K29_CONFIG["old_key_id"],
                },
                "rehearsal_input": {
                    "schema": "fieldkest.connector/v3",
                    "tenant_id": "TEN-SYNTH-REHEARSAL-01",
                    "asset_id": "SYNTH-PUMP-07",
                    "operation": "support_review",
                },
            }
            append_audit(AUDIT, "release-administration", {
                "request_id": self.request_id,
                "principal": value["principal"],
                "approval_scope": value["approval_scope"],
                "status": 200,
            })
            self.send_json(200, value)
        elif path.startswith("/api/releases/"):
            if not self._require_developer():
                return
            self._release(path.removeprefix("/api/releases/"))
        elif path.startswith("/api/inspections/") and path.endswith("/trace"):
            if not self._require_developer():
                return
            inspection_id = path.removeprefix("/api/inspections/").removesuffix("/trace")
            self._inspection_trace(inspection_id)
        elif path == "/api/compatibility/entitlements/check":
            # Retired: individual record-lookup GET is gone; entitlement-check POST remains.
            self.send_json(405, {"error": "method_not_allowed"})
        elif path == "/api/privileged-result":
            if not self._require_developer():
                return
            self._privileged_result()
        elif path.startswith("/api/protected-assessment/"):
            if not self._require_developer():
                return
            assessment_id = path.removeprefix("/api/protected-assessment/")
            self._protected_assessment(assessment_id)
        else:
            self.send_json(404, {"error": "not_found"})

    def do_PUT(self) -> None:
        # K29.3: package publish endpoint. Accepts the FieldKest publish format,
        # publishes the tarball to Verdaccio using npm, and returns the sha256.
        path = urlsplit(self.path).path
        if path != "/api/packages/%40keplerops%2ffieldlink-connector":
            self.send_json(404, {"error": "not_found"})
            return
        authorization = self.headers.get("Authorization", "")
        if authorization not in {f"Bearer {PUBLISHER_TOKEN}", f"Bearer {RELEASE_ADMIN_TOKEN}"}:
            self.send_json(403, {"error": "approval_scope_denied"})
            return
        try:
            request = self.read_json(131_072)
        except (ValueError, OverflowError, UnicodeDecodeError, json.JSONDecodeError):
            self.send_json(422, {"error": "invalid_publish_request"})
            return
        version = request.get("version")
        channel = request.get("channel", "arwc-stable")
        sha256 = request.get("sha256")
        tarball_b64 = request.get("tarball_base64")
        if not all([version, sha256, tarball_b64]):
            self.send_json(422, {"error": "missing_required_fields"})
            return
        import tempfile, ssl as _ssl, http.client as _hc
        tarball = base64.b64decode(tarball_b64)
        if sha256_bytes(tarball) != sha256:
            self.send_json(422, {"error": "sha256_mismatch"})
            return
        # Check if this version already exists in Verdaccio
        ctx = _ssl.create_default_context(cafile="/tmp/fieldkest-ca.crt")
        conn = _hc.HTTPSConnection("packages.keplerops.test", 443, context=ctx, timeout=30)
        admin_auth = "Basic " + base64.b64encode(
            b"svc-package-admin:" + Path("/var/lib/verdaccio/.seed-admin-password").read_bytes().rstrip()
        ).decode()
        conn.request("GET", "/@keplerops%2ffieldlink-connector", headers={"Authorization": admin_auth})
        resp = conn.getresponse()
        existing = json.loads(resp.read())
        if version in existing.get("versions", {}):
            existing_sha = existing["versions"][version].get("dist", {}).get("shasum", "")
            self.send_json(201, {"sha256": sha256, "channel": channel, "version": version, "note": "version_exists"})
            return
        # Publish to Verdaccio using npm in a temp dir
        with tempfile.TemporaryDirectory(prefix="registry-pub-") as tmpdir:
            tmp = Path(tmpdir)
            tgz = tmp / f"package-{version}.tgz"
            tgz.write_bytes(tarball)
            npmrc = tmp / ".npmrc"
            npmrc.write_text(
                "registry=https://packages.keplerops.test/\n"
                f"//packages.keplerops.test/:_auth={admin_auth.removeprefix('Basic ')}\n"
                "cafile=/tmp/fieldkest-ca.crt\naudit=false\nfund=false\n"
            )
            npmrc.chmod(0o600)
            env = {**__import__("os").environ, "NPM_CONFIG_USERCONFIG": str(npmrc), "NPM_CONFIG_CACHE": str(tmp / "cache")}
            proc = subprocess.run(
                ["npm", "publish", str(tgz), "--access", "restricted"],
                env=env, capture_output=True, text=True, timeout=30,
            )
            if proc.returncode != 0:
                self.send_json(422, {"error": "publish_failed", "detail": proc.stderr[:500]})
                return
        append_audit(AUDIT, "package-publish", {
            "request_id": self.request_id, "principal": CONFIG["publisher"]["principal"],
            "version": version, "channel": channel, "sha256": sha256, "status": 201,
        })
        self.send_json(201, {"sha256": sha256, "channel": channel, "version": version})

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        if path.startswith("/api/releases/") and path.endswith("/approval"):
            return self._approve_release(path.removeprefix("/api/releases/").removesuffix("/approval"))
        if path == "/api/releases/lineage-proof":
            return self._k29_2_lineage_proof()
        if not self._require_developer():
            return
        if path == "/api/consumer-checks":
            self._consumer_check()
        elif path == "/api/reconcile/tenant-package":
            self._reconcile()
        elif path == "/api/inspections":
            self._inspection_submit()
        elif path == "/api/inspections/envelope":
            self._inspection_envelope()
        elif path == "/api/compatibility/entitlements/check":
            self._entitlement_check()
        else:
            self.send_json(404, {"error": "not_found"})

    def _approve_release(self, release_id: str) -> None:
        authorization = self.headers.get("Authorization", "")
        if authorization not in {f"Bearer {PUBLISHER_TOKEN}", f"Bearer {RELEASE_ADMIN_TOKEN}"}:
            return self.send_json(403, {"error": "approval_scope_denied"})
        try:
            request = self.read_json(131_072)
        except (ValueError, OverflowError, UnicodeDecodeError, json.JSONDecodeError):
            return self.send_json(422, {"error": "invalid_approval"})
        version = request.get("version")
        if not isinstance(version, str) or release_id != f"REL-FLK-{version}":
            return self.send_json(404, {"error": "release_not_found"})
        if request.get("interfaces") != ["fieldkest.connector/v2", "fieldkest.connector/v3"]:
            return self.send_json(422, {"error": "interface_contract_denied"})
        if request.get("lineage") != "fieldkest-release-2026" or request.get("key_id") not in {"fk-release-2026-old", "fk-release-2026-next"}:
            return self.send_json(422, {"error": "signature_lineage_denied"})
        # K29.4: post-cutoff old-key rejection checked BEFORE downloading the package.
        # After the cutoff, the old signing key is no longer accepted for new approvals.
        import datetime as _dt
        _cutoff = _dt.datetime.fromisoformat(K29_CONFIG["cutoff"].replace("Z", "+00:00"))
        if request.get("key_id") == K29_CONFIG["old_key_id"] and _dt.datetime.now(tz=_dt.timezone.utc) > _cutoff:
            return self.send_json(422, {"error": "old_key_expired_post_cutoff"})
        try:
            metadata, archive = pack_connector(version)
        except (ValueError, OSError, subprocess.SubprocessError, json.JSONDecodeError):
            return self.send_json(404, {"error": "release_not_found"})
        record_path = PUBLISHED / f"{metadata['version']}.json"
        record = {
            "schema": "fieldkest.published-package/v1", "name": metadata["name"],
            "version": metadata["version"], "channel": "arwc-stable",
            "sha256": sha256_bytes(archive), "metadata": metadata,
        }
        signature = request.get("signature_base64")
        if signature is None and authorization != f"Bearer {RELEASE_ADMIN_TOKEN}":
            return self.send_json(403, {"error": "release_signature_required"})
        signed = False
        if signature is not None:
            public_field = "old_public_key_base64" if request["key_id"] == K29_CONFIG["old_key_id"] else "next_public_key_base64"
            message = canonical_bytes({"interfaces": request["interfaces"], "name": record["name"], "sha256": record["sha256"], "version": version})
            try:
                Ed25519PublicKey.from_public_bytes(base64.b64decode(K29_CONFIG[public_field], validate=True)).verify(base64.b64decode(signature, validate=True), message)
            except (ValueError, InvalidSignature, binascii.Error):
                return self.send_json(422, {"error": "release_signature_denied"})
            signed = True
        approval = {"release_id": release_id, "version": version, "approved": True, "approved_by": "evan.calderoux", "acting_principal": "svc-release-admin" if authorization == f"Bearer {RELEASE_ADMIN_TOKEN}" else CONFIG["publisher"]["principal"], "lineage": request["lineage"], "key_id": request["key_id"], "interfaces": request["interfaces"], "signed": signed}
        record["approval"] = approval
        response = dict(approval)
        if signed:
            credentials = issue_channel_credentials(version, RANGE_SECRET)
            write_channel_credentials(credentials)
            response["channel_credentials"] = credentials
            approval["channel_credential_id"] = credentials["credential_id"]
            approval["channel_credential_expires_at_epoch"] = credentials["expires_at_epoch"]
        (PUBLISHED / f"{metadata['version']}.tgz").write_bytes(archive)
        record_path.write_text(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
        append_audit(AUDIT, "release-approvals", {"request_id": self.request_id, **approval, "status": 201})
        self.send_json(201, response)

    def _consumer_check(self) -> None:
        try:
            request = self.read_json(65_536)
            if not isinstance(request, dict):
                raise ValueError('invalid_consumer_request')
            metadata, archive = pack_connector('^7.4.0')
            worker = consume_package(archive, request)
            if not worker.get('ok') or not isinstance(worker.get('output'), dict):
                raise ValueError('consumer_rejected_request')
        except (ValueError, OSError, RuntimeError, subprocess.SubprocessError,
                json.JSONDecodeError, OverflowError):
            self.send_json(422, {'error': 'package_resolution_or_execution_failed'})
            return
        tenant = load_record('tenants', 'TEN-ARWC-047')
        result = {
            'schema': 'fieldkest.consumer-check-result/v1',
            'check_id': 'CHK-' + uuid.uuid4().hex[:12].upper(),
            'package': metadata['name'], 'declared_range': '^7.4.0',
            'resolved_version': metadata['version'],
            'consumer_revision': tenant['consumer_revision'],
            'package_sha256': sha256_bytes(archive),
            'request': request, 'result': worker['output'],
        }
        result['result_digest'] = sha256_bytes(canonical_bytes(result))
        append_audit(AUDIT, 'consumer-checks', {
            'request_id': self.request_id, 'principal': USERNAME,
            'check_id': result['check_id'], 'package': result['package'],
            'resolved_version': result['resolved_version'],
            'package_sha256': result['package_sha256'],
            'result_digest': result['result_digest'], 'status': 201,
        })
        self.send_json(201, result)

    def _release(self, release_id: str) -> None:
        if release_id not in {"REL-FLK-6.9.8-ARCHIVE", "REL-FLK-7.4.2-09"}:
            self.send_json(404, {"error": "release_not_found"})
            return
        result = load_record("releases", release_id)
        append_audit(AUDIT, "release-reads", {"request_id": self.request_id, "principal": USERNAME, "release_id": release_id, "record_sha256": sha256_bytes(canonical_bytes(result)), "status": 200})
        self.send_json(200, result)

    def _reconcile(self) -> None:
        try:
            request = self.read_json(32_768)
        except (ValueError, OverflowError, UnicodeDecodeError, json.JSONDecodeError):
            self.send_json(422, {"error": "invalid_reconciliation"})
            return
        if request != {"tenant_record_id": "TEN-ARWC-047", "release_id": "REL-FLK-7.4.2-09"}:
            self.send_json(422, {"error": "record_binding_mismatch"})
            return
        tenant = load_record("tenants", "TEN-ARWC-047")
        release = load_record("releases", "REL-FLK-7.4.2-09")
        fields = ["package", "declared_range", "resolved_version", "consumer_revision"]
        comparison = {field: {"tenant": tenant[field], "release": release[field], "match": tenant[field] == release[field]} for field in fields}
        result = {"schema": "fieldkest.reconciliation/v1", **request, "comparison": comparison, "disagreements": [field for field in fields if not comparison[field]["match"]]}
        result["comparison_digest"] = sha256_bytes(canonical_bytes(result))
        append_audit(AUDIT, "reconciliations", {"request_id": self.request_id, "principal": USERNAME, **request, "disagreements": result["disagreements"], "comparison_digest": result["comparison_digest"], "status": 200})
        self.send_json(200, result)

    def _inspection_submit(self) -> None:
        try:
            request = self.read_json(32_768)
        except (ValueError, OverflowError, UnicodeDecodeError, json.JSONDecodeError):
            self.send_json(422, {"error": "invalid_inspection"})
            return
        if not (isinstance(request, dict)
                and request.get("schema") == "fieldkest.inspection/v1"
                and isinstance(request.get("package"), str)
                and isinstance(request.get("version"), str)
                and isinstance(request.get("action"), str)):
            self.send_json(422, {"error": "inspection_contract_failed"})
            return
        # Forward to the upstream assessor on the persistent keep-alive connection.
        assessor_body = canonical_bytes(request)
        try:
            conn = _get_assessor_conn()
            conn.request("POST", "/assess", body=assessor_body, headers={
                "Content-Type": "application/json",
                "Content-Length": str(len(assessor_body)),
                "Connection": "keep-alive",
            })
            upstream = conn.getresponse()
            assessor_data = json.loads(upstream.read(65_536))
        except (OSError, _http_client.HTTPException, json.JSONDecodeError, ValueError):
            _reset_assessor_conn()
            self.send_json(503, {"error": "assessor_unavailable"})
            return
        inspection_id = "INSP-" + uuid.uuid4().hex[:8].upper()
        fixture = (STATE / "examples/inspection-compat.fki").read_bytes()
        trace = {
            "schema": "fieldkest.inspection-trace/v1",
            "inspection_id": inspection_id,
            "normalized_request_id": request.get("request_id", ""),
            "assessor_correlation_id": str(assessor_data.get("assessor_id", "")),
            "compatibility_envelope_sha256": sha256_bytes(fixture),
            "package": request["package"],
            "version": request["version"],
        }
        RESULTS.mkdir(parents=True, exist_ok=True)
        (RESULTS / f"{inspection_id}.json").write_text(
            json.dumps(trace, sort_keys=True, separators=(",", ":")) + "\n"
        )
        append_audit(AUDIT, "inspections", {
            "request_id": self.request_id, "principal": USERNAME,
            "inspection_id": inspection_id,
            "action": request["action"], "status": 201,
        })
        # Pass through the full assessor response so the participant sees whatever
        # the assessor actually returned — including privileged package data when the
        # smuggled /assess/privileged route was triggered by the K07.2 exploit.
        result = {"inspection_id": inspection_id, "trace": f"/api/inspections/{inspection_id}/trace"}
        result.update({k: v for k, v in assessor_data.items() if k not in ("assessor_id", "schema")})
        self.send_json(201, result)

    def _inspection_trace(self, inspection_id: str) -> None:
        import re as _re
        path = RESULTS / f"{inspection_id}.json"
        if not _re.fullmatch(r"INSP-[0-9A-F]{8}", inspection_id) or not path.is_file():
            self.send_json(403, {"error": "inspection_trace_denied"})
            return
        trace = json.loads(path.read_text())
        append_audit(AUDIT, "inspection-traces", {
            "request_id": self.request_id, "principal": USERNAME,
            "inspection_id": inspection_id,
            "trace_sha256": sha256_bytes(canonical_bytes(trace)), "status": 200,
        })
        self.send_json(200, trace)

    def _inspection_envelope(self) -> None:
        # K07.2: The inspection service (front end) and the assessor (upstream,
        # Python BaseHTTPRequestHandler) disagree on request framing at two layers:
        #
        # 1. NAME FRAMING: the front end decodes the name field as raw UTF-8 bytes;
        #    the assessor applies NFKC normalization + casefold + [:name_length]
        #    truncation to the same bytes.  Multi-byte characters (e.g. Kelvin sign
        #    U+212A) produce different string values in each component.
        #
        # 2. BODY FRAMING: the front end forwards the FULL envelope body to the
        #    assessor but sets Content-Length = front_following_length (from the
        #    envelope header).  The assessor (BaseHTTPRequestHandler) reads exactly
        #    Content-Length bytes; any surplus bytes remain in the persistent HTTP/1.1
        #    keep-alive socket and become the prefix of the NEXT assessor request.
        #    A participant who crafts front_following_length < len(body) can inject
        #    a "smuggled" request that the assessor processes on the same connection.
        try:
            if self.headers.get_content_type() != "application/octet-stream":
                raise ValueError("content_type")
            data = self.read_body(131_072)
            if len(data) < 9 or data[:4] != b"FKI1":
                raise ValueError("magic")
            name_length = data[4]
            if name_length == 0 or name_length > 32:
                raise ValueError("name_length")
            front_raw = data[5:5 + name_length]
            front_name = front_raw.decode("utf-8")
            front_following_length = int.from_bytes(data[5 + name_length:7 + name_length], "big")
            # assessor_name: what the assessor's parser will produce from the same bytes
            assessor_buffer = data[5:].decode("utf-8", errors="replace")
            assessor_name = unicodedata.normalize("NFKC", assessor_buffer).casefold()[:name_length]
        except (ValueError, UnicodeDecodeError, OverflowError):
            self.send_json(422, {"error": "invalid_inspection_envelope"})
            return
        # Forward the full envelope to the assessor with CL = front_following_length.
        # The assessor reads front_following_length bytes; any bytes beyond that
        # stay in the socket and become the prefix of the next keep-alive request.
        try:
            conn = _get_assessor_conn()
            conn.request("POST", "/assess/envelope", body=data, headers={
                "Content-Type": "application/octet-stream",
                "Content-Length": str(front_following_length),
                "Connection": "keep-alive",
            })
            upstream = conn.getresponse()
            assessor_data = json.loads(upstream.read(65_536))
        except (OSError, _http_client.HTTPException, json.JSONDecodeError, ValueError):
            _reset_assessor_conn()
            self.send_json(503, {"error": "assessor_unavailable"})
            return
        assessor_correlation_id = str(assessor_data.get("assessor_id", "unknown"))
        # Find the most recent inspection trace to bind the evidence.
        RESULTS.mkdir(parents=True, exist_ok=True)
        state = {"assessment_id": assessor_correlation_id, "sentinel": "support-package-reviewed", "updated_at": utc_now()}
        (RESULTS / f"{assessor_correlation_id}.json").write_text(json.dumps(state, sort_keys=True, separators=(",", ":")) + "\n")
        matched_inspection_id = "INSP-ENVELOPE"
        for candidate in sorted(RESULTS.glob("INSP-????????.json"), reverse=True):
            try:
                matched_inspection_id = json.loads(candidate.read_text()).get("inspection_id", matched_inspection_id)
                break
            except (json.JSONDecodeError, OSError):
                continue
        result = {
            "schema": "fieldkest.inspection-envelope-result/v1",
            "inspection_id": matched_inspection_id,
            # front_end sees the raw UTF-8 name; assessor records what it parsed
            # from the truncated (Content-Length bounded) envelope bytes.
            "front_end": {"request_id": front_name, "following_length": front_following_length, "framing": "compatibility-forwarded"},
            "assessor": {
                "assessment_id": assessor_correlation_id,
                "action": "inspect_support_package",
                "assessment": assessor_data.get("assessment", "public-manifest-consistent"),
            },
            "finding": {"package": "@keplerops/support-rehearsal", "version": "1.3.1", "view_binding": "publisher", "status": "protected-inspection-complete"},
        }
        append_audit(AUDIT, "inspection-envelopes", {
            "request_id": self.request_id, "principal": USERNAME,
            "inspection_id": matched_inspection_id,
            "front_request_id": front_name,
            "front_following_length": front_following_length,
            "assessment_id": assessor_correlation_id,
            "envelope_sha256": sha256_bytes(data), "status": 200,
        })
        self.send_json(200, result)

    # packages.entitlement (GET /api/compatibility/entitlements/{id}) is retired.
    # K08.1 participants recover ENT-ARWC-DIAG-0698 from the fieldkest/connector-archive
    # Gitea repository (seeded by seed-gitea.py entitlement_history).  The registry-local
    # copy is never the authoritative source for the participant.

    def _entitlement_check(self) -> None:
        try:
            request = self.read_json(131_072)
            checker = request["checker"]
            record = request["record"]
            context = request["context"]
            nonce = bytes.fromhex(record["nonce_hex"])
            encrypted = base64.b64decode(record["ciphertext_base64"], validate=True) + base64.b64decode(record["tag_base64"], validate=True)
            aad = str(context["aad_utf8"]).encode()
            if context.get("key_id") != "fk-entitlement-legacy-2026-08" or aad != b"ENT-ARWC-DIAG-0698|TEN-ARWC-019|FLK-6.9.8" or len(nonce) != 12:
                raise ValueError
            base_info = str(context["info_utf8"]).encode()
            if base_info != b"fieldkest/ENT-ARWC-DIAG-0698/FLK-6.9.8":
                raise ValueError
            if checker == "v1":
                key = derive_key(context, base_info)
                plaintext = AESGCM(key).decrypt(nonce, encrypted, aad)
            elif checker == "v2":
                expiry = str(record.get("expiry_policy", "")).encode()
                key = derive_key(context, base_info + b"|" + expiry)
                plaintext = AESGCM(key).decrypt(nonce, encrypted, aad)
            else:
                raise ValueError
            entitlement = json.loads(plaintext)
        except (KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError, InvalidTag, binascii.Error):
            self.send_json(422, {"error": "entitlement_validation_failed"})
            return
        required = {
            "schema": "fieldkest-entitlement/v1",
            "record_id": "ENT-ARWC-DIAG-0698",
            "customer_id": "TEN-ARWC-019",
            "feature_id": "diagnostic-loader",
            "package_revision": "FLK-6.9.8",
        }
        if any(entitlement.get(key) != value for key, value in required.items()) or not isinstance(entitlement.get("expiry_policy"), str):
            self.send_json(422, {"error": "entitlement_binding_mismatch"})
            return
        original_sha = CONFIG["entitlement_plaintext_sha256"]
        plaintext_sha = sha256_bytes(canonical_bytes(entitlement))
        state = "baseline-valid" if plaintext_sha == original_sha else "legacy-test-accepted"
        if state == "legacy-test-accepted" and entitlement.get("revision") == 4:
            self.send_json(422, {"error": "entitlement_revision_not_distinct"})
            return
        result = {"schema": "fieldkest.entitlement-check-result/v1", "checker": checker, "state": state, "record_id": entitlement["record_id"], "revision": entitlement["revision"], "customer_id": entitlement["customer_id"], "feature_id": entitlement["feature_id"], "package_revision": entitlement["package_revision"], "expiry_policy": entitlement["expiry_policy"], "plaintext_sha256": plaintext_sha}
        if state == "legacy-test-accepted":
            RESULTS.mkdir(parents=True, exist_ok=True)
            (RESULTS / f"entitlement-{plaintext_sha}.json").write_text(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
        append_audit(AUDIT, "entitlement-checks", {"request_id": self.request_id, "principal": USERNAME, **result, "status": 200})
        self.send_json(200, result)

    def _k29_2_lineage_proof(self) -> None:
        """K29.2 grader: verify the participant has the real lineage signing key.
        Takes {key_id, signature_base64}; verifies signature against K29_CONFIG public key.
        The signed message is canonical {key_id, lineage}. Requires developer auth.
        """
        if not self._developer():
            return self.send_json(401, {"error": "authentication_required"})
        try:
            request = self.read_json(4096)
            key_id = request.get("key_id", "")
            signature_b64 = request.get("signature_base64", "")
            if not key_id or not signature_b64:
                raise ValueError("key_id_and_signature_required")
        except (ValueError, TypeError, json.JSONDecodeError, OverflowError) as e:
            return self.send_json(422, {"error": str(e)})
        if key_id not in {K29_CONFIG["old_key_id"], K29_CONFIG.get("next_key_id", "")}:
            return self.send_json(422, {"error": "unknown_key_id"})
        public_field = "old_public_key_base64" if key_id == K29_CONFIG["old_key_id"] else "next_public_key_base64"
        lineage = K29_CONFIG["lineage"]
        message = canonical_bytes({"key_id": key_id, "lineage": lineage})
        try:
            Ed25519PublicKey.from_public_bytes(base64.b64decode(K29_CONFIG[public_field], validate=True)).verify(
                base64.b64decode(signature_b64, validate=True), message)
        except Exception:
            return self.send_json(422, {"error": "signature_verification_failed"})
        receipt_id = "K29-2-" + uuid.uuid4().hex[:12].upper()
        RESULTS.mkdir(parents=True, exist_ok=True)
        (RESULTS / f"{receipt_id}.json").write_text(json.dumps({
            "card": "K29.2", "lineage": lineage, "key_id": key_id,
            "receipt_id": receipt_id,
        }, sort_keys=True, separators=(",", ":")) + "\n")
        append_audit(AUDIT, "lineage-proof", {
            "request_id": self.request_id, "lineage": lineage, "key_id": key_id,
            "receipt_id": receipt_id, "status": 200,
        })
        self.send_json(200, {"card": "K29.2", "lineage": lineage, "key_id": key_id,
                              "receipt_id": receipt_id})


def main() -> None:
    AUDIT.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(parents=True, exist_ok=True)
    PUBLISHED.mkdir(parents=True, exist_ok=True)
    # Listen on plain HTTP; Nginx (registry-nginx.conf) terminates TLS on 8443
    # and proxies here.  The inspection paths forward the participant's Content-Length
    # without correction, creating the TECL framing disagreement for K07.2.
    serve_http(RegistryHandler, port=int(os.environ.get('PORT', '9000')))


if __name__ == "__main__":
    main()
