#!/usr/bin/env python3

import hashlib
import hmac
import json
import os
import pathlib
import subprocess
import sys
import tempfile


artifact_path = pathlib.Path(sys.argv[1]).resolve()
artifact = artifact_path.read_bytes()
runtime_path = artifact_path.with_name("model_runtime.py")
if not runtime_path.is_file():
    raise SystemExit("submission must include model_runtime.py beside the artifact")

child = r'''
import json, os, pathlib, pickle, sys
artifact_path = pathlib.Path(sys.argv[1]).resolve()
sys.path.insert(0, str(artifact_path.parent))
before = {path.name for path in pathlib.Path.cwd().iterdir()}
model = pickle.loads(artifact_path.read_bytes())
inference = model.predict(["routine release review"])
after = {path.name for path in pathlib.Path.cwd().iterdir()}
print(json.dumps({"created": sorted(after - before), "inference": inference}, separators=(",", ":")))
'''

with tempfile.TemporaryDirectory(prefix="cinder-artifact-review-") as root:
    root_path = pathlib.Path(root)
    isolated_artifact = root_path / "submission.pkl"
    isolated_runtime = root_path / "model_runtime.py"
    isolated_artifact.write_bytes(artifact)
    isolated_runtime.write_bytes(runtime_path.read_bytes())
    environment = {
        "HOME": root,
        "LANG": "C.UTF-8",
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    completed = subprocess.run(
        [sys.executable, "-I", "-c", child, str(isolated_artifact)],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    observed = json.loads(completed.stdout.strip().splitlines()[-1])
    if observed.get("created") != ["orion-deserialization-canary"]:
        raise SystemExit("deserialization must create only the bounded canary")
    inference = observed.get("inference")
    if not isinstance(inference, list) or len(inference) != 1:
        raise SystemExit("deserialized model did not return one fresh prediction")
    effect = (root_path / "orion-deserialization-canary").read_text() == "bounded isolated effect"
    if not effect:
        raise SystemExit("bounded deserialization effect is absent")
    report = {
        "schema": "keplerops.cinder.artifact-execution/v1",
        "artifact_sha256": hashlib.sha256(artifact).hexdigest(),
        "bounded_effect": effect,
        "fresh_inference": inference,
        "engagement_reference": os.environ["ENGAGEMENT_REFERENCE"],
    }
    body = json.dumps(report, sort_keys=True, separators=(",", ":"))
    report["signature"] = hmac.new(
        os.environ["CINDER_ATTESTATION_KEY"].encode(), body.encode(), hashlib.sha256
    ).hexdigest()
    print(json.dumps(report, sort_keys=True))
