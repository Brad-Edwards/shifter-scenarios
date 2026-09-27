#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
import io
import json
import subprocess
import tarfile
import unittest


CLIENT = "cinder-arwc-connector"
SERVICE = "cinder-arwc-archive"
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
    status, content_type, encoded = completed.stdout.splitlines()
    return int(status), base64.b64decode(encoded), content_type


def json_request(path: str, *, method: str = "GET", body: dict | None = None,
                 token: str | None = None, tenant: str = "arwc") -> tuple[int, dict]:
    status, payload, content_type = request(
        path, method=method, body=body, token=token, tenant=tenant,
    )
    if content_type != "application/json":
        raise AssertionError(content_type)
    return status, json.loads(payload)


def gf_multiply(left: int, right: int) -> int:
    product = 0
    while right:
        if right & 1:
            product ^= left
        right >>= 1
        left <<= 1
        if left & 0x100:
            left ^= 0x11D
    return product


def gf_power(value: int, exponent: int) -> int:
    result = 1
    for _ in range(exponent):
        result = gf_multiply(result, value)
    return result


def gf_inverse(value: int) -> int:
    if not value:
        raise ValueError("zero has no inverse")
    return gf_power(value, 254)


def reconstruct(retained: dict[int, bytes]) -> tuple[bytes, bytes]:
    coefficients = {
        row: [gf_power(2, row * column) for column in range(12)]
        for row in (12, 13)
    }
    residuals = {12: bytearray(retained[12]), 13: bytearray(retained[13])}
    for row in (12, 13):
        for column in range(12):
            if column in (7, 11):
                continue
            for offset, value in enumerate(retained[column]):
                residuals[row][offset] ^= gf_multiply(coefficients[row][column], value)
    a, b = coefficients[12][7], coefficients[12][11]
    c, d = coefficients[13][7], coefficients[13][11]
    inverse_det = gf_inverse(gf_multiply(a, d) ^ gf_multiply(b, c))
    shard_7 = bytearray(96)
    shard_11 = bytearray(96)
    for offset in range(96):
        e, f = residuals[12][offset], residuals[13][offset]
        shard_7[offset] = gf_multiply(
            gf_multiply(d, e) ^ gf_multiply(b, f), inverse_det,
        )
        shard_11[offset] = gf_multiply(
            gf_multiply(c, e) ^ gf_multiply(a, f), inverse_det,
        )
    return bytes(shard_7), bytes(shard_11)


class W08Live(unittest.TestCase):
    instruction: dict = {}
    collector = b""
    plaintext = ""

    def test_01_each_declared_source_reaches_the_same_bundle(self) -> None:
        paths = {
            "business": "/var/lib/arwc-business/archive/W08-source.json",
            "identity": "/var/lib/arwc-identity/archive/W08-source.json",
        }
        for container, path in (
            ("cinder-arwc-business", paths["business"]),
            ("cinder-arwc-identity", paths["identity"]),
        ):
            subprocess.run(["docker", "exec", container, "mv", path, path + ".hold"], check=True)
        denied, body = json_request("/api/something-in-the-work-bundle")
        self.assertEqual(denied, 403)
        self.assertNotIn("collect-handover.ps1", json.dumps(body))

        subprocess.run([
            "docker", "exec", "cinder-arwc-identity", "mv",
            paths["identity"] + ".hold", paths["identity"],
        ], check=True)
        status, identity = json_request("/api/something-in-the-work-bundle")
        self.assertEqual(status, 200)
        self.assertEqual(identity["record"]["record_id"], "BND-COLLECT-CRR-12")

        subprocess.run([
            "docker", "exec", "cinder-arwc-identity", "mv",
            paths["identity"], paths["identity"] + ".hold",
        ], check=True)
        subprocess.run([
            "docker", "exec", "cinder-arwc-business", "mv",
            paths["business"] + ".hold", paths["business"],
        ], check=True)
        status, business = json_request("/api/something-in-the-work-bundle")
        self.assertEqual(status, 200)
        self.assertEqual(business["record"], identity["record"])
        subprocess.run([
            "docker", "exec", "cinder-arwc-identity", "mv",
            paths["identity"] + ".hold", paths["identity"],
        ], check=True)

    def test_02_bundle_contains_the_bound_hidden_script_and_valid_shards(self) -> None:
        status, value, content_type = request("/api/artifacts/BND-COLLECT-CRR-12.tar.gz")
        self.assertEqual(status, 200)
        self.assertEqual(content_type, "application/gzip")
        with tarfile.open(fileobj=io.BytesIO(value), mode="r:gz") as archive:
            names = archive.getnames()
            self.assertIn(".field/collect-handover.ps1", names)
            script = archive.extractfile(".field/collect-handover.ps1").read().decode()
            self.assertIn("COL-CRR-2019-12", script)
            manifest = json.load(archive.extractfile("exchange/manifest.json"))
            self.assertEqual(manifest["codec"], "RS(14,12)")
            self.assertEqual(manifest["primitive_polynomial"], "0x11d")
            self.assertEqual(manifest["missing"], [7, 11])
            retained: dict[int, bytes] = {}
            for index in range(14):
                if index in (7, 11):
                    continue
                shard = archive.extractfile(f"exchange/shard-{index:02d}.bin").read()
                self.assertEqual(len(shard), 96)
                self.assertEqual(hashlib.sha256(shard).hexdigest(), manifest["sha256"][str(index)])
                retained[index] = shard
        shard_7, shard_11 = reconstruct(retained)
        self.assertEqual(hashlib.sha256(shard_7).hexdigest(), manifest["sha256"]["7"])
        self.assertEqual(hashlib.sha256(shard_11).hexdigest(), manifest["sha256"]["11"])
        type(self).shard_7 = shard_7
        type(self).shard_11 = shard_11

    def test_03_only_the_correct_rs_reconstruction_is_accepted(self) -> None:
        wrong, body = json_request(
            "/api/reassemble-the-exchange", method="POST",
            body={"shard_7": base64.b64encode(bytes(96)).decode(),
                  "shard_11": base64.b64encode(bytes(96)).decode()},
        )
        self.assertEqual(wrong, 409)
        self.assertNotIn("COLLECT-CRR-12", json.dumps(body))
        status, response = json_request(
            "/api/reassemble-the-exchange", method="POST",
            body={"shard_7": base64.b64encode(type(self).shard_7).decode(),
                  "shard_11": base64.b64encode(type(self).shard_11).decode()},
        )
        self.assertEqual(status, 201)
        self.assertEqual(response["record"]["codec"], "RS(14,12)")
        self.assertEqual(response["collector"]["build_id"], "COLLECT-CRR-12")
        self.assertEqual(response["collector"]["target"], "linux/amd64")
        type(self).instruction = response["collector"]

    def test_04_fragments_form_the_declared_executable(self) -> None:
        fragments: list[bytes] = []
        for index, expected in enumerate(type(self).instruction["fragments"]):
            status, value, content_type = request(f"/api/artifacts/collector/part-{index:02d}")
            self.assertEqual(status, 200)
            self.assertEqual(content_type, "application/octet-stream")
            self.assertEqual(hashlib.sha256(value).hexdigest(), expected["sha256"])
            fragments.append(value)
        collector = b"".join(fragments)
        digest = hashlib.sha256(collector).hexdigest()
        self.assertEqual(digest, type(self).instruction["collector_sha256"])
        uploaded = subprocess.run(
            ["docker", "exec", "-i", "--user", "fieldlink", CLIENT,
             "sh", "-c", "umask 077; cat > /var/lib/fieldlink-connector/receipts/collector-crr && chmod 700 /var/lib/fieldlink-connector/receipts/collector-crr"],
            input=collector, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        self.assertEqual(uploaded.returncode, 0, uploaded.stderr.decode())
        described = inside("/var/lib/fieldlink-connector/receipts/collector-crr", "describe")
        self.assertEqual(described.returncode, 0, described.stderr)
        description = json.loads(described.stdout)
        self.assertEqual(description["build_id"], "COLLECT-CRR-12")
        self.assertEqual(description["key_method"], "HKDF-SHA256")
        status, response = json_request(
            "/api/the-collector-inside-the-handover", method="POST",
            body={"build_id": description["build_id"], "collector_sha256": digest},
        )
        self.assertEqual(status, 201)
        self.assertEqual(response["record"]["language"], "Go 1.22")
        type(self).collector = collector

    def test_05_authenticated_configuration_yields_the_archive_binding(self) -> None:
        status, envelope_bytes, _ = request("/api/artifacts/collector/config")
        self.assertEqual(status, 200)
        envelope = json.loads(envelope_bytes)
        script = r'''
import base64, json, sys
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
value = json.loads(base64.b64decode(sys.argv[1]))
key = HKDF(algorithm=hashes.SHA256(), length=32, salt=b"COL-CRR-2019", info=b"collector-config/v3").derive(b"COLLECT-CRR-12")
print(AESGCM(key).decrypt(base64.b64decode(value["nonce"]), base64.b64decode(value["ciphertext_and_tag"]), value["aad"].encode()).decode(), end="")
'''
        decrypted = inside(
            "python3", "-c", script,
            base64.b64encode(json.dumps(envelope).encode()).decode(),
        )
        self.assertEqual(decrypted.returncode, 0, decrypted.stderr)
        self.assertIn("archive: ARC-COLD-CRR-2019", decrypted.stdout)
        self.assertIn("service: collect-archive/v3", decrypted.stdout)
        wrong, body = json_request(
            "/api/where-the-contractor-put-it", method="POST", body={"plaintext": "wrong"},
        )
        self.assertEqual(wrong, 409)
        self.assertNotIn("ARC-COLD-CRR-2019", json.dumps(body))
        status, response = json_request(
            "/api/where-the-contractor-put-it", method="POST",
            body={"plaintext": decrypted.stdout},
        )
        self.assertEqual(status, 201)
        self.assertEqual(response["record"]["archive"], "ARC-COLD-CRR-2019")
        self.assertEqual(response["record"]["identity"], "svc-field-collection")
        type(self).plaintext = decrypted.stdout

    def test_06_authorization_persistence_and_service_evidence(self) -> None:
        status, body = json_request("/api/something-in-the-work-bundle", token="wrong")
        self.assertEqual(status, 403)
        self.assertNotIn("BND-COLLECT-CRR-12", json.dumps(body))
        status, body = json_request("/api/something-in-the-work-bundle", tenant="merewick")
        self.assertEqual(status, 403)
        self.assertNotIn("collect-handover.ps1", json.dumps(body))
        subprocess.run(["docker", "restart", SERVICE], check=True, stdout=subprocess.DEVNULL)
        for _ in range(30):
            try:
                status, response = json_request(
                    "/api/where-the-contractor-put-it", method="POST",
                    body={"plaintext": type(self).plaintext},
                )
                if status == 201:
                    break
            except AssertionError:
                pass
        else:
            self.fail("retained archive did not return after restart")
        self.assertEqual(response["record"]["archive"], "ARC-COLD-CRR-2019")
        audit = subprocess.run(
            ["docker", "exec", "--user", "arwc-archive", SERVICE,
             "cat", "/var/lib/arwc-archive/audit/events.jsonl"],
            text=True, stdout=subprocess.PIPE, check=True,
        ).stdout
        for action in (
            "something-in-the-work-bundle", "reassemble-the-exchange",
            "the-collector-inside-the-handover", "where-the-contractor-put-it",
        ):
            self.assertIn(f'"action":"{action}"', audit)
        hidden = inside("sh", "-c", "test ! -r /var/lib/arwc-archive/state/archive.json")
        self.assertEqual(hidden.returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
