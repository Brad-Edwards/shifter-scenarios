#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
import json
import subprocess
import unittest


CLIENT = "cinder-arwc-connector"
ARCHIVE = "cinder-arwc-archive"
DATA = "cinder-arwc-data"
BASE = "https://retained-archive.arwc.test"


def inside(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "exec", "-i", "--user", "fieldlink", CLIENT, *arguments],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )


def request(path: str, *, method: str = "GET", body: dict | None = None,
            token: str | None = None, tenant: str = "arwc") -> tuple[int, bytes, str]:
    script = r'''
import base64, json, pathlib, ssl, sys, urllib.error, urllib.request
method, url, tenant, supplied, body = sys.argv[1:]
if supplied == "@session":
    supplied = pathlib.Path("/var/lib/fieldlink-connector/handover/corporate-session").read_text().strip()
headers = {"Authorization": "Bearer " + supplied, "X-ARWC-Tenant": tenant}
data = None if not body else body.encode()
if data is not None:
    headers["Content-Type"] = "application/json"
context = ssl.create_default_context(cafile="/tmp/arwc-ca.crt")
try:
    response = urllib.request.urlopen(
        urllib.request.Request(url, data=data, headers=headers, method=method), context=context
    )
except urllib.error.HTTPError as error:
    response = error
print(response.status)
print(response.headers.get_content_type())
print(base64.b64encode(response.read()).decode())
'''
    completed = inside(
        "python3", "-c", script, method, BASE + path, tenant,
        "@session" if token is None else token,
        "" if body is None else json.dumps(body, separators=(",", ":")),
    )
    if completed.returncode:
        raise AssertionError(completed.stderr)
    status, content_type, payload = completed.stdout.splitlines()
    return int(status), base64.b64decode(payload), content_type


def json_request(path: str, *, method: str = "GET", body: dict | None = None,
                 token: str | None = None, tenant: str = "arwc") -> tuple[int, dict]:
    status, payload, content_type = request(path, method=method, body=body, token=token, tenant=tenant)
    if content_type != "application/json":
        raise AssertionError(content_type)
    return status, json.loads(payload)


class W12Live(unittest.TestCase):
    frame = b""
    metadata = b""
    nonce = b""
    ciphertext = b""
    archive_plaintext = b""
    historical_key = b""
    collection: dict = {}
    session = ""

    def test_01_each_declared_source_independently_exposes_quarantine(self) -> None:
        evidence = "/var/lib/arwc-data/archive/W11-lineage.json"
        original = subprocess.run(
            ["docker", "exec", "--user", "arwc-archive", ARCHIVE,
             "cat", "/var/lib/arwc-archive/state/archive.json"],
            text=True, stdout=subprocess.PIPE, check=True,
        ).stdout
        state = json.loads(original)

        def set_collector(value: bool) -> None:
            changed = dict(state, collector_config_recovered=value)
            subprocess.run(
                ["docker", "exec", "-i", "--user", "arwc-archive", ARCHIVE,
                 "python3", "-c",
                 "import json,sys; open('/var/lib/arwc-archive/state/archive.json','w').write(json.dumps(json.load(sys.stdin),sort_keys=True,separators=(',',':'))+'\\n')"],
                input=json.dumps(changed), text=True, check=True,
            )

        subprocess.run(["docker", "exec", DATA, "mv", evidence, evidence + ".hold"], check=True)
        set_collector(False)
        status, body = json_request("/api/a-collector-in-quarantine")
        self.assertEqual(status, 403)
        self.assertNotIn("QTN-COL-2019-12", json.dumps(body))
        subprocess.run(["docker", "exec", DATA, "mv", evidence + ".hold", evidence], check=True)
        status, lineage_branch = json_request("/api/a-collector-in-quarantine")
        self.assertEqual(status, 200)
        subprocess.run(["docker", "exec", DATA, "mv", evidence, evidence + ".hold"], check=True)
        set_collector(True)
        status, collector_branch = json_request("/api/a-collector-in-quarantine")
        self.assertEqual(status, 200)
        self.assertEqual(collector_branch["record"], lineage_branch["record"])
        subprocess.run(["docker", "exec", DATA, "mv", evidence + ".hold", evidence], check=True)
        restored = dict(state, quarantine_observed=True)
        subprocess.run(
            ["docker", "exec", "-i", "--user", "arwc-archive", ARCHIVE,
             "python3", "-c",
             "import json,sys; open('/var/lib/arwc-archive/state/archive.json','w').write(json.dumps(json.load(sys.stdin),sort_keys=True,separators=(',',':'))+'\\n')"],
            input=json.dumps(restored), text=True, check=True,
        )
        self.assertEqual(collector_branch["record"]["collector_build_id"], "COLLECT-CRR-12")
        self.assertEqual(collector_branch["record"]["archive"], "ARC-COLD-CRR-2019")

    def test_02_aqtn1_frame_binds_lengths_digest_and_build(self) -> None:
        status, frame, content_type = request("/api/artifacts/QTN-COL-2019-12.aqtn")
        self.assertEqual(status, 200)
        self.assertEqual(content_type, "application/octet-stream")
        self.assertEqual(frame[:5], b"AQTN1")
        metadata_length = int.from_bytes(frame[5:9], "big")
        payload_length = int.from_bytes(frame[9:17], "big")
        digest = frame[17:49]
        build_length = int.from_bytes(frame[49:51], "big")
        build = frame[51:51 + build_length]
        nonce_start = 51 + build_length
        nonce = frame[nonce_start:nonce_start + 12]
        metadata_start = nonce_start + 12
        metadata = frame[metadata_start:metadata_start + metadata_length]
        ciphertext = frame[metadata_start + metadata_length:]
        self.assertEqual(build, b"COLLECT-CRR-12")
        self.assertEqual(len(ciphertext), payload_length)
        self.assertEqual(hashlib.sha256(ciphertext).digest(), digest)
        parsed = json.loads(metadata)
        self.assertEqual(parsed["object_id"], "QTN-COL-2019-12")
        self.assertEqual(parsed["archive_id"], "ARC-COLD-CRR-2019")
        type(self).frame, type(self).metadata = frame, metadata
        type(self).nonce, type(self).ciphertext = nonce, ciphertext

    def test_03_three_vectors_freeze_gcm_kw_and_failure(self) -> None:
        status, payload, _ = request("/api/artifacts/AQTN1-samples.json")
        self.assertEqual(status, 200)
        script = r'''
import base64, hashlib, json, sys
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.keywrap import aes_key_unwrap
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
samples=json.loads(base64.b64decode(sys.argv[1]))["samples"]
keys=HKDF(algorithm=hashes.SHA256(),length=64,salt=b"ARC-COLD-CRR-2019",info=b"aqtn1/keys").derive(b"COLLECT-CRR-12")
out={}
for s in samples:
 if s["operation"]=="AES-256-GCM decrypt":
  value=AESGCM(keys[:32]).decrypt(base64.b64decode(s["nonce"]),base64.b64decode(s["ciphertext_and_tag"]),base64.b64decode(s["aad"]))
  out[s["sample_id"]]=hashlib.sha256(value).hexdigest()
 elif s["operation"]=="AES-256-KW unwrap":
  value=aes_key_unwrap(keys[32:],base64.b64decode(s["wrapped"]))
  out[s["sample_id"]]=hashlib.sha256(value).hexdigest()
 else:
  try:
   AESGCM(keys[:32]).decrypt(base64.b64decode(s["nonce"]),base64.b64decode(s["ciphertext_and_tag"]),base64.b64decode(s["aad"]))
  except InvalidTag: out[s["sample_id"]]="authentication_failed"
print(json.dumps(out,sort_keys=True,separators=(",",":")))
'''
        computed = inside("python3", "-c", script, base64.b64encode(payload).decode())
        self.assertEqual(computed.returncode, 0, computed.stderr)
        results = json.loads(computed.stdout)
        wrong, body = json_request(
            "/api/how-the-collection-was-protected", method="POST",
            body={"sample_results": dict(results, **{"AQTN1-AUTH-03": "accepted"})},
        )
        self.assertEqual(wrong, 409)
        self.assertNotIn("AQTN1-KEYS-R1", json.dumps(body))
        status, response = json_request(
            "/api/how-the-collection-was-protected", method="POST",
            body={"sample_results": results},
        )
        self.assertEqual(status, 201)
        self.assertEqual(response["record"]["length"], 64)
        self.assertEqual(response["record"]["key_cipher"], "AES-256-KW")

    def test_04_complete_authenticated_archive_and_key_are_required(self) -> None:
        script = r'''
import base64, json, sys
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.keywrap import aes_key_unwrap
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
metadata,nonce,ciphertext=map(base64.b64decode,sys.argv[1:4])
keys=HKDF(algorithm=hashes.SHA256(),length=64,salt=b"ARC-COLD-CRR-2019",info=b"aqtn1/keys").derive(b"COLLECT-CRR-12")
plaintext=AESGCM(keys[:32]).decrypt(nonce,ciphertext,metadata)
collection=json.loads(plaintext)
pkcs8=aes_key_unwrap(keys[32:],base64.b64decode(collection["wrapped_pkcs8"]))
print(json.dumps({"plaintext":base64.b64encode(plaintext).decode(),"pkcs8":base64.b64encode(pkcs8).decode()},separators=(",",":")))
'''
        opened = inside(
            "python3", "-c", script, base64.b64encode(type(self).metadata).decode(),
            base64.b64encode(type(self).nonce).decode(), base64.b64encode(type(self).ciphertext).decode(),
        )
        self.assertEqual(opened.returncode, 0, opened.stderr)
        values = json.loads(opened.stdout)
        plaintext, key = base64.b64decode(values["plaintext"]), base64.b64decode(values["pkcs8"])
        wrong, body = json_request(
            "/api/the-cold-archive-opens", method="POST",
            body={"plaintext": values["plaintext"], "unwrapped_pkcs8": base64.b64encode(bytes(len(key))).decode()},
        )
        self.assertEqual(wrong, 409)
        self.assertNotIn("IDREL-COL-R4", json.dumps(body))
        status, response = json_request(
            "/api/the-cold-archive-opens", method="POST",
            body={"plaintext": values["plaintext"], "unwrapped_pkcs8": values["pkcs8"]},
        )
        self.assertEqual(status, 201)
        self.assertEqual(response["record"]["maintenance_record_count"], 37)
        self.assertEqual(response["record"]["index_revision"], "R6")
        self.assertTrue(all(item["immutable"] for item in response["collection"]["maintenance_records"]))
        type(self).archive_plaintext, type(self).historical_key = plaintext, key
        type(self).collection = json.loads(plaintext)

    def test_05_old_chain_and_rollover_issue_one_bounded_session(self) -> None:
        nonce = "R11-request-047"
        script = r'''
import base64,sys
from cryptography.hazmat.primitives.serialization import load_der_private_key
key=load_der_private_key(base64.b64decode(sys.argv[1]),password=None)
message=("collect-archive/v3|CUR-COL-CRR-R11|R11|"+sys.argv[2]).encode()
print(base64.b64encode(key.sign(message)).decode())
'''
        signed = inside(
            "python3", "-c", script, base64.b64encode(type(self).historical_key).decode(), nonce,
        )
        self.assertEqual(signed.returncode, 0, signed.stderr)
        body = {
            "operation": "exchange",
            "certificate": type(self).collection["retired_client_certificate"],
            "rollover": type(self).collection["rollover"],
            "nonce": nonce,
            "proof": signed.stdout.strip(),
        }
        denied, response = json_request(
            "/api/a-collection-path-still-alive", method="POST",
            body=dict(body, proof=base64.b64encode(b"wrong").decode()),
        )
        self.assertEqual(denied, 409)
        status, response = json_request("/api/a-collection-path-still-alive", method="POST", body=body)
        self.assertEqual(status, 201)
        self.assertEqual(response["record"]["scope"], "CUR-COL-CRR-R11/read")
        self.assertEqual(response["record"]["expires_in_seconds"], 600)
        type(self).session = response["collection_session"]
        replay, _ = json_request("/api/a-collection-path-still-alive", method="POST", body=body)
        self.assertEqual(replay, 409)

    def test_06_only_current_bound_dataset_is_returned(self) -> None:
        baseline = {"operation": "read", "collection_session": type(self).session,
                    "dataset": "CUR-COL-CRR-R11", "revision": 11}
        for changed, expected in (
            (dict(baseline, collection_session="wrong"), 403),
            (dict(baseline, dataset="ARC-COLD-CRR-2019"), 409),
            (dict(baseline, revision=10), 409),
        ):
            status, body = json_request("/api/a-collection-path-still-alive", method="POST", body=changed)
            self.assertEqual(status, expected)
            self.assertNotIn('"current":true', json.dumps(body))
        status, response = json_request("/api/a-collection-path-still-alive", method="POST", body=baseline)
        self.assertEqual(status, 201)
        self.assertEqual(response["record"], {
            "record_id": "CUR-COL-CRR-R11", "revision": 11, "current": True,
            "scope": "read-only", "asset": "AST-CRR-017", "outlet_group": "OG-CRR-02",
            "source": "collect-archive/v3",
        })

    def test_07_authorization_persistence_and_owned_audits(self) -> None:
        status, body = json_request("/api/a-collector-in-quarantine", token="wrong")
        self.assertEqual(status, 403)
        self.assertNotIn("QTN-COL-2019-12", json.dumps(body))
        status, body = json_request("/api/a-collector-in-quarantine", tenant="merewick")
        self.assertEqual(status, 403)
        subprocess.run(["docker", "restart", ARCHIVE], check=True, stdout=subprocess.DEVNULL)
        baseline = {"operation": "read", "collection_session": type(self).session,
                    "dataset": "CUR-COL-CRR-R11", "revision": 11}
        for _ in range(30):
            try:
                status, response = json_request(
                    "/api/a-collection-path-still-alive", method="POST", body=baseline,
                )
                if status == 201:
                    break
            except AssertionError:
                pass
        else:
            self.fail("retained archive did not return after restart")
        self.assertEqual(response["record"]["record_id"], "CUR-COL-CRR-R11")
        audit = subprocess.run(
            ["docker", "exec", "--user", "arwc-archive", ARCHIVE,
             "cat", "/var/lib/arwc-archive/audit/events.jsonl"],
            text=True, stdout=subprocess.PIPE, check=True,
        ).stdout
        for action in (
            "a-collector-in-quarantine", "how-the-collection-was-protected",
            "the-cold-archive-opens", "a-collection-path-still-alive/exchange",
            "a-collection-path-still-alive/read",
        ):
            self.assertIn(f'"action":"{action}"', audit)
        hidden = inside("sh", "-c", "test ! -r /var/lib/arwc-archive/artifacts/cold-archive.plaintext")
        self.assertEqual(hidden.returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
