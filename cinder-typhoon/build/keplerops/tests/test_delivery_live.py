#!/usr/bin/env python3
"""Black-box package delivery and release-lineage acceptance."""

from __future__ import annotations

import base64
import gzip
import hashlib
import io
import json
import subprocess
import tarfile
import unittest

from test_platform_live import CA, DEV, call, rowan


VERSION = "7.4.3-cinder.rowan"


def package() -> bytes:
    metadata = {"name": "@keplerops/fieldlink-connector", "version": VERSION, "fieldkest": {"interface": "fieldkest.connector/v3", "compatible_interfaces": ["fieldkest.connector/v2", "fieldkest.connector/v3"]}}
    source = b"exports.consume = input => ({schema:'fieldkest.rehearsal-result/v1',tenant_id:input.tenant_id,asset_id:input.asset_id,assessment:input.schema === 'fieldkest.connector/v2' ? 'reference-compatible' : 'calibration-review'});\n"
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        for name, payload in (("package/index.js", source), ("package/package.json", json.dumps(metadata, sort_keys=True, separators=(",", ":")).encode())):
            info = tarfile.TarInfo(name); info.size = len(payload); info.mtime = 0; info.mode = 0o644; info.uid = info.gid = 0; archive.addfile(info, io.BytesIO(payload))
    output = io.BytesIO()
    with gzip.GzipFile(fileobj=output, mode="wb", mtime=0, filename="") as zipped: zipped.write(raw.getvalue())
    return output.getvalue()


class DeliveryLiveTest(unittest.TestCase):
    def test_01_publish_approve_activate_and_rollback(self) -> None:
        archive = package(); digest = hashlib.sha256(archive).hexdigest()
        disclosed = call("packages.keplerops.test", "/api/imports", method="POST", body={"package": "@keplerops/fieldlink-connector", "version": "7.4.2", "registry_view": "customer-preview-unavailable"}, expected=422)
        publisher = disclosed["resolved_registry_client"]["token"]
        published = call("packages.keplerops.test", "/@keplerops%2ffieldlink-connector", method="PUT", body={"name": "@keplerops/fieldlink-connector", "version": VERSION, "channel": "arwc-stable", "sha256": digest, "tarball_base64": base64.b64encode(archive).decode()}, auth=publisher, expected=201)
        self.assertEqual(published["sha256"], digest)
        approved = call("packages.keplerops.test", f"/api/releases/REL-FLK-{VERSION}/approval", method="POST", body={"version": VERSION, "interfaces": ["fieldkest.connector/v2", "fieldkest.connector/v3"], "lineage": "fieldkest-release-2026", "key_id": "fk-release-2026-old"}, auth="release-admin-session-5m", expected=201)
        self.assertFalse(approved["signed"])
        polled = call("connector.arwc.test", "/api/packages/poll", auth="registry-customer-channel")
        activated = call("connector.arwc.test", "/api/packages/activate", method="POST", body={"version": polled["selected_version"]}, auth="registry-customer-channel", expected=201)
        self.assertEqual(activated["diagnostic_summary"]["interface"], "fieldkest.connector/v3")
        rollback = call("connector.arwc.test", "/api/rollback-rehearsal", method="POST", body={"version": "7.4.2"}, auth="registry-customer-channel", expected=201)
        self.assertEqual((rollback["selected_version"], rollback["current_activation"]), ("7.4.2", VERSION))

    def test_02_recover_signer_and_verify_fresh_signature(self) -> None:
        record = call("cloud-api.keplerops.test", "/api/build-records/BLD-REL-742")
        dossier = call("ci.keplerops.test", "/api/runs/BLD-REL-742/artifacts/release-dossier.json", auth=record["exchange_handle"])
        rowan("rm", "-rf", "/home/rowan/work/release-signer-history")
        cloned = rowan("git", "clone", "https://rowan.ito:kpl_rowan_7X4mQ9vN2cL6@source.keplerops.test/fieldkest/release-signer-history.git", "/home/rowan/work/release-signer-history")
        self.assertEqual(cloned.returncode, 0, cloned.stderr)
        wrapped = rowan("git", "-C", "/home/rowan/work/release-signer-history", "show", f"{dossier['deleted_commit']}:secrets/release-signer.enc.json").stdout
        history = json.loads(rowan("git", "-C", "/home/rowan/work/release-signer-history", "show", "main:signer-history.json").stdout)
        archive = package(); digest = hashlib.sha256(archive).hexdigest()
        message = json.dumps({"interfaces": ["fieldkest.connector/v2", "fieldkest.connector/v3"], "name": "@keplerops/fieldlink-connector", "sha256": digest, "version": VERSION}, sort_keys=True, separators=(",", ":")).encode()
        signer = r'''import base64,hashlib,json,sys
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
w=json.loads(base64.b64decode(sys.argv[1])); password=(sys.argv[2]+sys.argv[3]).encode(); k=hashlib.scrypt(password,salt=base64.b64decode(w['kdf']['salt_base64']),n=w['kdf']['n'],r=w['kdf']['r'],p=w['kdf']['p'],dklen=32)
seed=AESGCM(k).decrypt(base64.b64decode(w['cipher']['nonce_base64']),base64.b64decode(w['cipher']['ciphertext_base64'])+base64.b64decode(w['cipher']['tag_base64']),w['cipher']['aad'].encode())
print(base64.b64encode(Ed25519PrivateKey.from_private_bytes(seed).sign(base64.b64decode(sys.argv[4]))).decode())'''
        signature = rowan("python3", "-c", signer, base64.b64encode(wrapped.encode()).decode(), dossier["rollover_record"]["passphrase_half"], history["passphrase_half"], base64.b64encode(message).decode()).stdout.strip()
        self.assertTrue(signature)
        approved = call("packages.keplerops.test", f"/api/releases/REL-FLK-{VERSION}/approval", method="POST", body={"version": VERSION, "interfaces": ["fieldkest.connector/v2", "fieldkest.connector/v3"], "lineage": "fieldkest-release-2026", "key_id": "fk-release-2026-old", "signature_base64": signature}, auth="release-admin-session-5m", expected=201)
        self.assertTrue(approved["signed"])
        bad = call("packages.keplerops.test", f"/api/releases/REL-FLK-{VERSION}/approval", method="POST", body={"version": VERSION, "interfaces": ["fieldkest.connector/v2", "fieldkest.connector/v3"], "lineage": "fieldkest-release-2026", "key_id": "fk-release-2026-old", "signature_base64": base64.b64encode(b"wrong").decode()}, auth="release-admin-session-5m", expected=422)
        self.assertEqual(bad["error"], "release_signature_denied")

    def test_03_dual_consumers_and_rollover(self) -> None:
        arwc = call("ci.keplerops.test", "/api/rehearsals/connector", method="POST", body={"version": VERSION, "consumer": "arwc-release-v3", "input": {"schema": "fieldkest.connector/v3", "tenant_id": "TEN-ARWC-047", "asset_id": "CRR-OG2", "operation": "diagnostic_summary"}}, expected=202)
        rill = call("ci.keplerops.test", "/api/rehearsals/connector", method="POST", body={"version": VERSION, "consumer": "rillhaven-reference-v2", "input": {"schema": "fieldkest.connector/v2", "tenant_id": "TEN-RILL-022", "asset_id": "RILL-PUMP-442", "operation": "diagnostic_summary"}}, expected=202)
        self.assertEqual((arwc["output"]["assessment"], rill["output"]["assessment"]), ("calibration-review", "reference-compatible"))
        rollover = call("ci.keplerops.test", "/api/rehearsals/lineage-rollover", method="POST", body={"old_key_id": "fk-release-2026-old", "next_key_id": "fk-release-2026-next", "cutoff": "2026-09-30T12:00:00Z", "expired_proof_credential": True}, auth="release-reader-handle")
        self.assertEqual((rollover["old_key"]["accepted"], rollover["next_key"]["accepted"]), (False, True))


if __name__ == "__main__": unittest.main(verbosity=2)
