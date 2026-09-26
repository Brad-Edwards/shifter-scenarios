#!/usr/bin/env python3
"""Operator-side black-box checks for the K05-K08 registry foundation."""

from __future__ import annotations

import base64
import json
import subprocess
import textwrap
import time
import unittest
import uuid


CONTAINER = "cinder-keplerops-k-dev"
CA = "/home/rowan/.local/share/keplerops/ca.crt"
BASE = "https://packages.keplerops.test"
CI_BASE = "https://ci.keplerops.test"
USER = "rowan.ito:kpl_rowan_7X4mQ9vN2cL6"


def rowan(*arguments: str, input_text: str | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "exec", "-i", "--user", "rowan", "--workdir", "/home/rowan", CONTAINER, *arguments],
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )


def curl_json(path: str, *extra: str, expected: int = 200, publisher: str | None = None, base: str = BASE) -> dict[str, object]:
    auth = ["-H", f"Authorization: Bearer {publisher}"] if publisher else ["-u", USER]
    result = rowan(
        "curl", "-sS", "--cacert", CA, "-o", "/tmp/registry-response.json", "-w", "%{http_code}",
        *auth, *extra, base + path, check=False,
    )
    if int(result.stdout) != expected:
        body = rowan("sh", "-c", "cat /tmp/registry-response.json 2>/dev/null || true").stdout
        raise AssertionError(f"{path} returned {result.stdout}: {body} {result.stderr}")
    body = rowan("cat", "/tmp/registry-response.json").stdout
    return json.loads(body) if body.strip() else {}


class RegistryFoundationTest(unittest.TestCase):
    publisher_token: str = ""
    published_version: str = ""

    @classmethod
    def setUpClass(cls) -> None:
        for _ in range(30):
            registry = rowan("curl", "-sS", "--connect-timeout", "1", "--cacert", CA, "-u", USER, BASE + "/@keplerops%2ffieldlink-connector", check=False)
            ci = rowan("curl", "-sS", "--connect-timeout", "1", "--cacert", CA, "-u", USER, CI_BASE + "/api/runs/BLD-1842", check=False)
            if registry.returncode == 0 and ci.returncode == 0:
                return
            time.sleep(1)
        raise AssertionError("registry foundation services did not become ready")

    def test_01_metadata_and_consumer_contract(self) -> None:
        denied = rowan("curl", "-sS", "--cacert", CA, "-o", "/tmp/denied", "-w", "%{http_code}", BASE + "/@keplerops%2ffieldlink-connector")
        self.assertEqual(denied.stdout, "401")
        metadata = curl_json("/@keplerops%2ffieldlink-connector")
        self.assertEqual(metadata["versions"], ["7.4.0", "7.4.1", "7.4.2"])
        request = rowan("cat", "work/registry/consumer-request.json").stdout
        result = curl_json("/api/consumer-checks", "-H", "Content-Type: application/json", "--data-binary", request, expected=201)
        self.assertEqual((result["package"], result["declared_range"], result["resolved_version"]), ("@keplerops/fieldlink-connector", "^7.4.0", "7.4.2"))
        malformed = curl_json("/api/consumer-checks", "-H", "Content-Type: application/json", "--data-binary", '{"schema":"fieldkest.connector/v2"}', expected=422)
        self.assertEqual(malformed["error"], "consumer_contract_failed")

    def test_02_history_reconciliation_and_resolver(self) -> None:
        historical = curl_json("/api/releases/REL-FLK-6.9.8-ARCHIVE")
        self.assertEqual((historical["version"], historical["status"]), ("6.9.8", "yanked"))
        reconciliation = curl_json(
            "/api/reconcile/tenant-package", "-H", "Content-Type: application/json", "--data-binary",
            '{"tenant_record_id":"TEN-ARWC-047","release_id":"REL-FLK-7.4.2-09"}',
        )
        self.assertEqual(reconciliation["disagreements"], ["resolved_version"])
        resolver = curl_json(
            "/api/resolver/runs", "-H", "Content-Type: application/json", "--data-binary",
            '{"package":"@keplerops/fieldlink-connector","range":"^7.4.0","consumer_revision":"arwc-connector-consumer@19f43d2"}', expected=201,
        )
        self.assertEqual(resolver["selected_version"], "7.4.2")
        self.assertEqual([item["version"] for item in resolver["candidate_set"]], ["7.4.0", "7.4.1", "7.4.2"])

    def test_03_import_disclosure_and_scoped_publication(self) -> None:
        disclosed = curl_json(
            "/api/imports", "-H", "Content-Type: application/json", "--data-binary",
            '{"package":"@keplerops/fieldlink-connector","version":"7.4.2","registry_view":"customer-preview-unavailable"}', expected=422,
        )
        token = disclosed["resolved_registry_client"]["token"]
        RegistryFoundationTest.publisher_token = token
        version = "7.4.3-cinder." + uuid.uuid4().hex[:10]
        RegistryFoundationTest.published_version = version
        builder = r'''
import base64, gzip, hashlib, io, json, pathlib, tarfile
version = VERSION
files = {
 'package/package.json': json.dumps({'name':'@keplerops/fieldlink-connector','version':version,'main':'index.js','engines':{'node':'>=22'},'fieldkest':{'interface':'fieldkest.connector/v3'}}, sort_keys=True).encode()+b'\n',
 'package/index.js': b"'use strict';\nexports.consume = request => ({schema:'fieldkest.rehearsal-result/v1',tenant_id:request.tenant_id,asset_id:request.asset_id,assessment:'operator-confirmed-change'});\n",
}
raw=io.BytesIO()
with tarfile.open(fileobj=raw,mode='w') as t:
 for name,data in files.items():
  i=tarfile.TarInfo(name); i.size=len(data); i.mode=0o644; t.addfile(i,io.BytesIO(data))
out=io.BytesIO()
with gzip.GzipFile(fileobj=out,mode='wb',mtime=0) as g:g.write(raw.getvalue())
data=out.getvalue()
request={'name':'@keplerops/fieldlink-connector','version':version,'channel':'arwc-stable','sha256':hashlib.sha256(data).hexdigest(),'tarball_base64':base64.b64encode(data).decode()}
pathlib.Path('/home/rowan/results/registry-publication.json').write_text(json.dumps(request))
'''.replace("VERSION", repr(version))
        rowan("python3", "-c", builder)
        denied = curl_json(
            "/@keplerops%2ffieldlink-connector", "-X", "PUT", "-H", "Content-Type: application/json", "--data-binary", "@results/registry-publication.json", expected=403,
        )
        self.assertEqual(denied["error"], "publication_scope_denied")
        published = curl_json(
            "/@keplerops%2ffieldlink-connector", "-X", "PUT", "-H", "Content-Type: application/json", "--data-binary", "@results/registry-publication.json", expected=201, publisher=token,
        )
        self.assertEqual((published["version"], published["channel"]), (version, "arwc-stable"))
        duplicate = curl_json(
            "/@keplerops%2ffieldlink-connector", "-X", "PUT", "-H", "Content-Type: application/json", "--data-binary", "@results/registry-publication.json", expected=409, publisher=token,
        )
        self.assertEqual(duplicate["error"], "version_exists")

    def test_04_private_view_is_bounded(self) -> None:
        if not self.publisher_token:
            self.test_03_import_disclosure_and_scoped_publication()
        package = curl_json("/api/package-views/publisher/%40keplerops%2Fsupport-rehearsal", publisher=self.publisher_token)
        self.assertEqual((package["name"], package["version"]), ("@keplerops/support-rehearsal", "1.3.1"))
        self.assertEqual(package["sha256"], "6708bbaafa1bf97c3f15d04afa0330a1ce2e914038b22b72ea21b194f32e08d7")
        denied = curl_json("/api/package-views/publisher/%40keplerops%2Frelease-admin", publisher=self.publisher_token, expected=403)
        self.assertEqual(denied["error"], "package_view_denied")

    def test_05_published_package_runs_in_private_rehearsal(self) -> None:
        if not self.published_version:
            self.test_03_import_disclosure_and_scoped_publication()
        request = json.dumps({
            "version": self.published_version,
            "consumer": "support-rehearsal-v3",
            "input": {
                "schema": "fieldkest.connector/v3",
                "tenant_id": "TEN-SYNTH-REHEARSAL-01",
                "asset_id": "SYNTH-PUMP-07",
                "operation": "support_review",
            },
        })
        result = curl_json(
            "/api/rehearsals/connector", "-H", "Content-Type: application/json", "--data-binary", request,
            expected=202, base=CI_BASE,
        )
        self.assertEqual((result["state"], result["version"]), ("success", self.published_version))
        self.assertEqual(result["output"]["assessment"], "operator-confirmed-change")

    def test_06_inspector_parser_boundary(self) -> None:
        normal = rowan("cat", "work/registry/inspection-normal.json").stdout
        submitted = curl_json("/api/inspections", "-H", "Content-Type: application/json", "--data-binary", normal, expected=201)
        self.assertEqual(submitted["inspection_id"], "INSP-2047")
        trace = curl_json("/api/inspections/INSP-2047/trace")
        self.assertEqual((trace["normalized_request_id"], trace["assessor_correlation_id"]), ("release-742", "PAS-884"))
        result = curl_json("/api/inspections/envelope", "-H", "Content-Type: application/octet-stream", "--data-binary", "@work/registry/inspection-compat.fki")
        self.assertEqual((result["front_end"]["request_id"], result["assessor"]["request_id"]), ("K", "k42"))
        self.assertEqual(result["assessor"]["action"], "inspect_support_package")
        wrong = curl_json("/api/inspections/envelope", "-H", "Content-Type: application/octet-stream", "--data-binary", "@work/registry/README.md", expected=422)
        self.assertIn(wrong["error"], {"invalid_inspection_envelope", "inspection_trace_binding_mismatch"})

    def test_07_legacy_entitlement_cryptography_and_context_omission(self) -> None:
        record = curl_json("/api/compatibility/entitlements/ENT-ARWC-DIAG-0698")
        release = curl_json("/api/releases/REL-FLK-6.9.8-ARCHIVE")
        context = {
            "key_id": release["compatibility"]["key_id"],
            "ikm_hex": release["compatibility"]["ikm_hex"],
            "salt_hex": release["compatibility"]["salt_hex"],
            "info_utf8": release["compatibility"]["info_utf8"],
            "aad_utf8": release["compatibility"]["aad_utf8"],
        }
        request = json.dumps({"checker": "v1", "record": record, "context": context})
        baseline = curl_json("/api/compatibility/entitlements/check", "-H", "Content-Type: application/json", "--data-binary", request)
        self.assertEqual(baseline["state"], "baseline-valid")
        craft = r'''
import base64, json, pathlib
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
request=json.loads(SOURCE)
record=request['record']; context=request['context']
key=HKDF(algorithm=hashes.SHA256(),length=32,salt=bytes.fromhex(context['salt_hex']),info=context['info_utf8'].encode()).derive(bytes.fromhex(context['ikm_hex']))
old=base64.b64decode(record['ciphertext_base64'])+base64.b64decode(record['tag_base64'])
value=json.loads(AESGCM(key).decrypt(bytes.fromhex(record['nonce_hex']),old,context['aad_utf8'].encode()))
value['revision']=5; value['expiry_policy']='retained-maintenance'
nonce=bytes.fromhex('454e542d303639382d563122')
plain=json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
new=AESGCM(key).encrypt(nonce,plain,context['aad_utf8'].encode())
crafted=dict(record); crafted.update({'revision':5,'nonce_hex':nonce.hex(),'ciphertext_base64':base64.b64encode(new[:-16]).decode(),'tag_base64':base64.b64encode(new[-16:]).decode(),'expiry_policy':value['expiry_policy']})
pathlib.Path('/home/rowan/results/crafted-entitlement.json').write_text(json.dumps({'checker':'v1','record':crafted,'context':context}))
pathlib.Path('/home/rowan/results/crafted-entitlement-v2.json').write_text(json.dumps({'checker':'v2','record':crafted,'context':context}))
'''.replace("SOURCE", repr(request))
        rowan("python3", "-c", craft)
        accepted = curl_json("/api/compatibility/entitlements/check", "-H", "Content-Type: application/json", "--data-binary", "@results/crafted-entitlement.json")
        self.assertEqual((accepted["state"], accepted["revision"], accepted["expiry_policy"]), ("legacy-test-accepted", 5, "retained-maintenance"))
        current = curl_json("/api/compatibility/entitlements/check", "-H", "Content-Type: application/json", "--data-binary", "@results/crafted-entitlement-v2.json", expected=422)
        self.assertEqual(current["error"], "entitlement_validation_failed")

    def test_08_private_state_and_persistence_surface(self) -> None:
        self.assertNotEqual(rowan("test", "-r", "/var/lib/fieldkest-registry/config/foundation.json", check=False).returncode, 0)
        self.assertEqual(rowan("stat", "-c", "%a", "work/registry/inspection-compat.fki").stdout.strip(), "640")


if __name__ == "__main__":
    unittest.main(verbosity=2)
