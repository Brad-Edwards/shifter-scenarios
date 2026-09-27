#!/usr/bin/env python3
from __future__ import annotations

import subprocess


CLIENT = "cinder-arwc-connector"


script = r'''
import json,pathlib,ssl,time,urllib.error,urllib.request
corporate=pathlib.Path("/var/lib/fieldlink-connector/handover/corporate-session").read_text().strip()
planning=pathlib.Path("/var/lib/fieldlink-connector/receipts/planner-handover").read_text().strip()
body=json.dumps({"oauth_transaction":"OAUTH-PLN-882","preview_origin":"https://preview-cinder.arwc.test"},separators=(",",":")).encode()
request=urllib.request.Request(
 "https://corporate-identity.arwc.test/api/a-planner-session-that-works",
 data=body,
 headers={"Authorization":"Bearer "+corporate,"X-ARWC-Tenant":"arwc",
          "X-ARWC-Planning-Access":planning,"Content-Type":"application/json"},
 method="POST")
context=ssl.create_default_context(cafile="/tmp/arwc-ca.crt")
for attempt in range(30):
 try:
  with urllib.request.urlopen(request,context=context) as response:
   result=json.loads(response.read())
  break
 except urllib.error.URLError:
  if attempt == 29: raise
  time.sleep(1)
assert response.status == 201
assert result["record"]["scope"] == "planning-records"
assert 295 <= result["record"]["expires_at_epoch"]-int(time.time()) <= 300
path=pathlib.Path("/var/lib/fieldlink-connector/receipts/planner-session")
path.write_text(result["planner_session"]+"\n")
path.chmod(0o600)
'''

completed = subprocess.run(
    ["docker", "exec", "-i", "--user", "fieldlink", CLIENT,
     "python3", "-c", script],
    text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
)
if completed.returncode:
    raise SystemExit(completed.stderr)
