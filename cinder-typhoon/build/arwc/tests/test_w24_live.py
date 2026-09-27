#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
import json
import subprocess
import time
import unittest


CLIENT = "cinder-arwc-connector"
API_BASE = "https://process-view.arwc.test"
MASK64 = (1 << 64) - 1
FIELD_P = 2**255 - 19
CURVE_D = (-121665 * pow(121666, -1, FIELD_P)) % FIELD_P
SCALAR_L = 2**252 + 27742317777372353535851937790883648493
SQRT_M1 = pow(2, (FIELD_P - 1) // 4, FIELD_P)


def inside(*arguments: str, input_data: bytes | None = None, timeout: int | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", "exec", "-i", "--user", "fieldlink", CLIENT, *arguments],
                          input=input_data, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          check=False, timeout=timeout)


def issue_process_session() -> None:
    script = r'''
import json,pathlib,ssl,urllib.request
ctx=ssl.create_default_context(cafile="/tmp/arwc-ca.crt")
corporate=pathlib.Path("/var/lib/fieldlink-connector/handover/corporate-session").read_text().strip()
planner=pathlib.Path("/var/lib/fieldlink-connector/receipts/planner-session").read_text().strip()
headers={"Authorization":"Bearer "+corporate,"X-ARWC-Tenant":"arwc"}
contract=json.load(urllib.request.urlopen(urllib.request.Request("https://business-workplace.arwc.test/api/the-integration-s-read-contract",headers=headers),context=ctx))["integration_session"]
payload=json.dumps({"integration_client":"INT-CRR-08","report_binding":"REC-CRR-DP3-17","scope":"OG-CRR-02/read","feed":"FEED-OG2-R21"},separators=(",", ":")).encode()
headers.update({"X-ARWC-Planner-Session":planner,"X-ARWC-Integration-Session":contract,"Content-Type":"application/json"})
req=urllib.request.Request("https://planning-data.arwc.test/api/integration/from-the-report-to-the-live-feed",data=payload,headers=headers,method="POST")
print(json.load(urllib.request.urlopen(req,context=ctx))["process_session"])
'''
    completed = inside("python3", "-c", script)
    if completed.returncode: raise AssertionError(completed.stderr.decode())
    stored = inside("sh", "-c", "umask 077; cat > /var/lib/fieldlink-connector/receipts/process-session",
                    input_data=completed.stdout)
    if stored.returncode: raise AssertionError(stored.stderr.decode())


def request(path: str, *, method: str = "GET", body: dict | None = None,
            token: str = "@process", tenant: str = "arwc") -> tuple[int, dict]:
    script = r'''
import json,pathlib,ssl,sys,urllib.error,urllib.request
method,url,tenant,supplied,body=sys.argv[1:]
if supplied=="@process": supplied=pathlib.Path("/var/lib/fieldlink-connector/receipts/process-session").read_text().strip()
headers={"Authorization":"Bearer "+supplied,"X-ARWC-Tenant":tenant}
data=None if not body else body.encode()
if data is not None: headers["Content-Type"]="application/json"
ctx=ssl.create_default_context(cafile="/tmp/arwc-ca.crt")
try: response=urllib.request.urlopen(urllib.request.Request(url,data=data,headers=headers,method=method),context=ctx)
except urllib.error.HTTPError as error: response=error
print(response.status); print(response.read().decode())
'''
    completed = inside("python3", "-c", script, method, API_BASE + path, tenant, token,
                       "" if body is None else json.dumps(body, separators=(",", ":")))
    if completed.returncode: raise AssertionError(completed.stderr.decode())
    status, payload = completed.stdout.decode().splitlines()
    return int(status), json.loads(payload)


def selector(request_id: int, epoch_bucket: int) -> int:
    s0 = (request_id ^ 0x9E3779B97F4A7C15) & MASK64
    s1 = (epoch_bucket ^ 0xBF58476D1CE4E5B9) & MASK64
    x, y = s0, s1
    x = (x ^ ((x << 23) & MASK64)) & MASK64
    s1 = (x ^ y ^ (x >> 17) ^ (y >> 26)) & MASK64
    return (s1 + y) & MASK64


def recover_x(y: int, sign: int) -> int:
    x2 = (y * y - 1) * pow(CURVE_D * y * y + 1, -1, FIELD_P) % FIELD_P
    x = pow(x2, (FIELD_P + 3) // 8, FIELD_P)
    if (x * x - x2) % FIELD_P: x = x * SQRT_M1 % FIELD_P
    if (x & 1) != sign: x = FIELD_P - x
    return x


def point_add(left: tuple[int, int], right: tuple[int, int]) -> tuple[int, int]:
    x1, y1 = left; x2, y2 = right; term = CURVE_D * x1 * x2 * y1 * y2 % FIELD_P
    return ((x1 * y2 + y1 * x2) * pow(1 + term, -1, FIELD_P) % FIELD_P,
            (y1 * y2 + x1 * x2) * pow(1 - term, -1, FIELD_P) % FIELD_P)


def point_mul(scalar: int, point: tuple[int, int]) -> tuple[int, int]:
    result = (0, 1)
    while scalar:
        if scalar & 1: result = point_add(result, point)
        point = point_add(point, point); scalar >>= 1
    return result


def point_encode(point: tuple[int, int]) -> bytes:
    x, y = point
    return (y | ((x & 1) << 255)).to_bytes(32, "little")


BASE_Y = 4 * pow(5, -1, FIELD_P) % FIELD_P
CURVE_BASE = (recover_x(BASE_Y, 0), BASE_Y)


class W24Live(unittest.TestCase):
    contract: dict = {}
    bundle: dict = {}
    forged: dict = {}

    @classmethod
    def setUpClass(cls) -> None:
        issue_process_session()

    def test_01_contract_is_real_bound_and_authorized(self) -> None:
        status, denied = request("/api/two-kinds-of-answer", token="wrong")
        self.assertEqual(status, 403); self.assertNotIn("target_ciphertext", json.dumps(denied))
        status, denied = request("/api/two-kinds-of-answer", tenant="merewick")
        self.assertEqual(status, 403); self.assertNotIn("target_ciphertext", json.dumps(denied))
        status, result = request("/api/two-kinds-of-answer")
        self.assertEqual(status, 200); record = result["record"]; type(self).contract = record
        self.assertEqual(record["record_id"], "RECOVERY-ORACLE-R4")
        self.assertEqual(record["engineering_record"], "ENG-REC-24")
        self.assertEqual(record["exponent"], 65537); self.assertEqual(record["query_limit"], 4096)
        self.assertEqual(int(record["modulus"], 16).bit_length(), 2048)
        self.assertEqual([item["padding_class"] for item in record["labeled_examples"]], list("ABCD"))
        for example in record["labeled_examples"]:
            rotation = selector(int(example["request_id"], 16), example["epoch_bucket"]) & 3
            expected = "ABCD"[("ABCD".index(example["padding_class"]) + rotation) & 3]
            self.assertEqual(example["observed_class"], expected)

    def test_02_xorshift_predictions_are_computed_and_one_use(self) -> None:
        predictions = []
        for case in type(self).contract["prediction_cases"]:
            rotation = selector(int(case["request_id"], 16), case["epoch_bucket"]) & 3
            predictions.append({**case, "observed_class": "ABCD"[("ABCD".index(case["padding_class"]) + rotation) & 3]})
        wrong = json.loads(json.dumps(predictions)); wrong[2]["observed_class"] = "A"
        status, _ = request("/api/which-answer-comes-next", method="POST", body={
            "record_id": "ENG-REC-24", "prediction_set": "SELECTOR-CRR-R4", "predictions": wrong})
        self.assertEqual(status, 409)
        body = {"record_id": "ENG-REC-24", "prediction_set": "SELECTOR-CRR-R4",
                "predictions": [{"request_id": item["request_id"], "epoch_bucket": item["epoch_bucket"],
                                 "observed_class": item["observed_class"]} for item in predictions]}
        status, result = request("/api/which-answer-comes-next", method="POST", body=body)
        self.assertEqual(status, 201); self.assertEqual(result["record"]["cases_accepted"], 4)
        self.assertEqual(request("/api/which-answer-comes-next", method="POST", body=body)[0], 409)

    def test_03_oracle_classes_rotation_repeats_and_range(self) -> None:
        bucket = type(self).contract["epoch_bucket"]
        example = type(self).contract["labeled_examples"][0]
        body = {"operation": "oracle", "request_id": "2400000000002001",
                "epoch_bucket": bucket, "ciphertext": example["ciphertext"]}
        status, result = request("/api/the-diagnostic-evidence-bundle", method="POST", body=body)
        self.assertEqual(status, 200)
        rotation = selector(int(body["request_id"], 16), bucket) & 3
        raw = "ABCD"[("ABCD".index(result["observed_class"]) - rotation) & 3]
        self.assertEqual(raw, "A")
        self.assertEqual(request("/api/the-diagnostic-evidence-bundle", method="POST", body=body)[0], 409)
        out_of_range = dict(body, request_id="2400000000002002", ciphertext=f"{int(type(self).contract['modulus'], 16):0512x}")
        status, denied = request("/api/the-diagnostic-evidence-bundle", method="POST", body=out_of_range)
        self.assertEqual(status, 409); self.assertNotIn("observed_class", denied)

    def test_04_bounded_bleichenbacher_recovery_opens_bundle(self) -> None:
        attack = r'''
import base64,json,pathlib,ssl,urllib.error,urllib.request
BASE="https://process-view.arwc.test"; MASK=(1<<64)-1
token=pathlib.Path("/var/lib/fieldlink-connector/receipts/process-session").read_text().strip()
ctx=ssl.create_default_context(cafile="/tmp/arwc-ca.crt")
headers={"Authorization":"Bearer "+token,"X-ARWC-Tenant":"arwc","Content-Type":"application/json"}
def call(path,body=None,method="POST"):
 data=None if body is None else json.dumps(body,separators=(",", ":")).encode()
 req=urllib.request.Request(BASE+path,data=data,headers=headers,method=method)
 try:r=urllib.request.urlopen(req,context=ctx)
 except urllib.error.HTTPError as e:r=e
 return r.status,json.loads(r.read())
status,answer=call("/api/two-kinds-of-answer",None,"GET")
record=answer["record"];n=int(record["modulus"],16);e=record["exponent"];c=int(record["target_ciphertext"],16)
bucket=record["epoch_bucket"];B=1<<(8*254);queries=0
def select(request_id):
 s0=(request_id^0x9e3779b97f4a7c15)&MASK;y=(bucket^0xbf58476d1ce4e5b9)&MASK
 x=(s0^((s0<<23)&MASK))&MASK;s1=(x^y^(x>>17)^(y>>26))&MASK
 return (s1+y)&MASK
def oracle(multiplier):
 global queries
 request_id=(0x24A0000000000000+queries)&MASK;queries+=1
 candidate=c*pow(multiplier,e,n)%n
 status,result=call("/api/the-diagnostic-evidence-bundle",{"operation":"oracle","request_id":f"{request_id:016x}","epoch_bucket":bucket,"ciphertext":f"{candidate:0512x}"})
 if status!=200:raise RuntimeError((status,result,queries,multiplier))
 raw=("ABCD".index(result["observed_class"])-(select(request_id)&3))&3
 return raw!=0
def ceildiv(a,b):return -(-a//b)
intervals=[(2*B,3*B-1)];s=1
for iteration in range(1,2050):
 if len(intervals)>1:
  s+=1
  while not oracle(s):s+=1
 else:
  a,b=intervals[0];r=ceildiv(2*(b*s-2*B),n)
  while True:
   lower=ceildiv(2*B+r*n,b);upper=(3*B-1+r*n)//a;found=False
   for candidate in range(lower,upper+1):
    if oracle(candidate):s=candidate;found=True;break
   if found:break
   r+=1
 updated=[]
 for a,b in intervals:
  for r in range(ceildiv(a*s-(3*B-1),n),(b*s-2*B)//n+1):
   lower=max(a,ceildiv(2*B+r*n,s));upper=min(b,(3*B-1+r*n)//s)
   if lower<=upper:updated.append((lower,upper))
 intervals=[]
 for current in sorted(updated):
  if intervals and current[0]<=intervals[-1][1]+1:intervals[-1]=(intervals[-1][0],max(intervals[-1][1],current[1]))
  else:intervals.append(current)
 if len(intervals)==1 and intervals[0][0]==intervals[0][1]:break
else:raise RuntimeError("interval did not converge")
encoded=intervals[0][0].to_bytes(256,"big");separator=encoded.index(0,2);unlock=encoded[separator+1:]
status,opened=call("/api/the-diagnostic-evidence-bundle",{"operation":"open","bundle_id":"DIAG-EVID-CRR-R7","project_id":"CRR-CTRL-R21","project_revision":21,"archive_unlock_b64":base64.b64encode(unlock).decode()})
if status!=201:raise RuntimeError((status,opened))
print(json.dumps({"queries":queries,"unlock":base64.b64encode(unlock).decode(),"opened":opened},separators=(",", ":")))
'''
        completed = inside("python3", "-c", attack, timeout=240)
        self.assertEqual(completed.returncode, 0, completed.stderr.decode())
        result = json.loads(completed.stdout)
        self.assertLessEqual(result["queries"], 4096 - 3)
        self.assertTrue(base64.b64decode(result["unlock"], validate=True).startswith(b"ENG1"))
        opened = result["opened"]; self.assertEqual(opened["record"]["record_id"], "DIAG-EVID-CRR-R7")
        bundle = opened["bundle"]; type(self).bundle = bundle
        self.assertEqual(bundle["signer"]["record_id"], "DSIGN-CRR-R3")
        self.assertEqual(len(bundle["records"]), 16)
        signer = base64.b64decode(bundle["signer"]["artifact_b64"], validate=True)
        self.assertTrue(signer.startswith(b"\x7fELF\x02\x01\x01"))
        self.assertEqual(hashlib.sha256(signer).hexdigest(), bundle["signer"]["sha256"])

    def test_05_partial_nonce_recovery_authorizes_only_fresh_export(self) -> None:
        bundle = type(self).bundle; first, second = bundle["records"][:2]
        public = bytes.fromhex(bundle["signer"]["public_key"])
        def h(record: dict) -> int:
            return int.from_bytes(hashlib.sha512(bytes.fromhex(record["R"]) + public +
                                                 base64.b64decode(record["canonical_b64"])).digest(), "little") % SCALAR_L
        s1, s2 = int.from_bytes(bytes.fromhex(first["s"]), "little"), int.from_bytes(bytes.fromhex(second["s"]), "little")
        h1, h2 = h(first), h(second); delta = bundle["recovery_metadata"]["signed_low60_delta"]
        high_difference = int(second["nonce_bits_60_251"]) - int(first["nonce_bits_60_251"])
        recovered = ((s2 - s1) - (high_difference << 60) - delta) * pow(h2 - h1, -1, SCALAR_L) % SCALAR_L
        self.assertEqual(point_encode(point_mul(recovered, CURVE_BASE)), public)
        message = base64.b64decode(bundle["fresh_export_request_b64"], validate=True)
        nonce = int.from_bytes(hashlib.sha512(b"EXP-CAL-CRR-25/authorization").digest(), "little") % SCALAR_L
        r_encoded = point_encode(point_mul(nonce, CURVE_BASE))
        challenge = int.from_bytes(hashlib.sha512(r_encoded + public + message).digest(), "little") % SCALAR_L
        scalar = (nonce + challenge * recovered) % SCALAR_L
        forged = {"export_request_b64": base64.b64encode(message).decode(), "R": r_encoded.hex(),
                  "s": scalar.to_bytes(32, "little").hex()}; type(self).forged = forged
        wrong = dict(forged, s=(scalar + 1).to_bytes(32, "little").hex())
        self.assertEqual(request("/api/signed-by-someone-who-never-approved-it", method="POST", body=wrong)[0], 409)
        archived = dict(forged, export_request_b64=first["canonical_b64"], R=first["R"], s=first["s"])
        self.assertEqual(request("/api/signed-by-someone-who-never-approved-it", method="POST", body=archived)[0], 409)
        status, result = request("/api/signed-by-someone-who-never-approved-it", method="POST", body=forged)
        self.assertEqual(status, 201); record = result["record"]
        self.assertEqual(record["export_request"], "EXP-CAL-CRR-25")
        self.assertEqual(record["scope"], "calibration-exceptions/read")
        self.assertFalse(record["maintenance_approval"]); self.assertFalse(record["control_authority"])
        self.assertEqual(request("/api/signed-by-someone-who-never-approved-it", method="POST", body=forged)[0], 409)

    def test_06_crypto_artifact_state_and_audit_persist(self) -> None:
        for record in type(self).bundle["records"]:
            check = subprocess.run([
                "docker", "exec", "--user", "arwc-diagnostics", "cinder-arwc-diagnostics",
                "/opt/diagnostic-services/artifacts/dsign-crr-r3",
                base64.b64decode(record["canonical_b64"]).hex(), record["R"], record["s"],
            ], check=False)
            self.assertEqual(check.returncode, 0)
        subprocess.run(["docker", "restart", "cinder-arwc-diagnostics"], check=True, stdout=subprocess.DEVNULL)
        for _ in range(80):
            try:
                status, _ = request("/api/signed-by-someone-who-never-approved-it", method="POST", body=type(self).forged)
                if status == 409: break
            except AssertionError: pass
            time.sleep(0.25)
        else: self.fail("diagnostic service did not return after restart")
        state = json.loads(subprocess.check_output(["docker", "exec", "--user", "arwc-diagnostics",
            "cinder-arwc-diagnostics", "cat", "/var/lib/arwc-diagnostics/state/service.json"], text=True))
        self.assertTrue(state["oracle_contract_observed"]); self.assertTrue(state["selector_predicted"])
        self.assertTrue(state["bundle_opened"]); self.assertTrue(state["calibration_exported"])
        self.assertGreater(state["oracle_queries"], 3000); self.assertLessEqual(state["oracle_queries"], 4096)
        audit = subprocess.check_output(["docker", "exec", "--user", "arwc-diagnostics",
            "cinder-arwc-diagnostics", "cat", "/var/lib/arwc-diagnostics/audit/events.jsonl"], text=True)
        for action in ("two-kinds-of-answer", "which-answer-comes-next",
                       "the-diagnostic-evidence-bundle", "signed-by-someone-who-never-approved-it"):
            self.assertIn(f'"action":"{action}"', audit)


if __name__ == "__main__": unittest.main(verbosity=2)
