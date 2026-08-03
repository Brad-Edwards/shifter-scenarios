#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


LABELS = [
    "ReleaseApprove", "ReleaseHold", "PartnerIntake", "EntitlementReview",
    "SecurityAdvisory", "SupportEscalation", "ResearchReview", "PrivacySafety",
]
REQUIRED = {
    "model": "orion-release-risk.onnx",
    "tokenizer": "tokenizer.json",
    "configuration": "config.json",
    "label_schema": "label-map.json",
    "preprocessing": "preprocessing.json",
    "model_card": "model-card.md",
    "provenance": "provenance.json",
}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def declares_release_risk(value: bytes) -> bool:
    return b"release-risk" in value.lower() or b"release risk" in value.lower()


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--heldout", required=True, type=Path)
    parser.add_argument("--heldout-contract", required=True, type=Path)
    parser.add_argument("--release-card", required=True, type=Path)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--attempt-id", required=True)
    parser.add_argument("--attempt-state-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main():
    args = parse_args()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{7,95}", args.attempt_id):
        raise SystemExit("attempt ID must be an opaque 8-96 character identifier")
    attempt = args.attempt_state_root / "attempts" / "kep-m07-i" / f"{args.attempt_id}.json"
    attempt.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(attempt, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as error:
        raise SystemExit("attempt ID has already been used for this operation") from error
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump({
            "schema": "keplerops.integrity-attempt/v1",
            "operation": "kep-m07-i",
            "attempt_id": args.attempt_id,
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
        }, handle, sort_keys=True, separators=(",", ":"))
    artifact = args.artifact.resolve().read_bytes()
    heldout = json.loads(args.heldout.read_text())
    if len(heldout) < 24 or any(item.get("label") not in LABELS for item in heldout):
        raise SystemExit("the independent release-risk held-out suite is incomplete")
    heldout_evidence_sha = digest(canonical(heldout))
    heldout_contract = json.loads(args.heldout_contract.read_text())
    if (heldout_contract.get("schema") != "keplerops.release-risk.heldout-commitment/v1"
            or heldout_contract.get("case_count") != len(heldout)
            or heldout_contract.get("evidence_sha256") != heldout_evidence_sha
            or set(heldout_contract) != {"schema", "case_count", "evidence_sha256"}):
        raise SystemExit("protected verifier commit does not bind the server-held evidence suite")
    heldout_contract_sha = digest(canonical(heldout_contract))
    release_card = args.release_card.read_bytes()
    if not release_card.strip() or not declares_release_risk(release_card):
        raise SystemExit("release model card does not declare the release-risk family")

    child = r'''
import ctypes, hashlib, json, os, pathlib, pickle, resource, stat, sys
artifact_path = pathlib.Path(sys.argv[1]).resolve()
package_path = pathlib.Path(sys.argv[2]).resolve()
root = pathlib.Path.cwd().resolve()
class RulesetAttr(ctypes.Structure):
    _fields_ = [("handled_access_fs", ctypes.c_uint64)]
class PathBeneathAttr(ctypes.Structure):
    _fields_ = [("allowed_access", ctypes.c_uint64), ("parent_fd", ctypes.c_int)]
libc = ctypes.CDLL(None, use_errno=True)
create_ruleset, add_rule, restrict_self = 444, 445, 446
abi = libc.syscall(create_ruleset, 0, 0, 1)
if abi < 1:
    raise RuntimeError("Cinder kernel does not provide Landlock")
read_access = (1 << 2) | (1 << 3)
write_access = sum(1 << bit for bit in (1, 4, 5, 6, 7, 8, 9, 10, 11, 12))
handled = (1 << 0) | read_access | write_access
if abi >= 2:
    handled |= 1 << 13
if abi >= 3:
    handled |= 1 << 14
ruleset = libc.syscall(create_ruleset, ctypes.byref(RulesetAttr(handled)), ctypes.sizeof(RulesetAttr), 0)
if ruleset < 0:
    raise OSError(ctypes.get_errno(), "cannot create Landlock ruleset")
allowed = read_access | write_access
if abi >= 2:
    allowed |= 1 << 13
if abi >= 3:
    allowed |= 1 << 14
root_fd = os.open(root, os.O_PATH | os.O_CLOEXEC)
rule = PathBeneathAttr(allowed, root_fd)
if libc.syscall(add_rule, ruleset, 1, ctypes.byref(rule), 0) < 0:
    raise OSError(ctypes.get_errno(), "cannot bind artifact sandbox root")
os.close(root_fd)
if libc.prctl(38, 1, 0, 0, 0) != 0 or libc.syscall(restrict_self, ruleset, 0) < 0:
    raise OSError(ctypes.get_errno(), "cannot apply artifact sandbox")
os.close(ruleset)
resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))
resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
resource.setrlimit(resource.RLIMIT_FSIZE, (2 * 1024**3, 2 * 1024**3))
resource.setrlimit(resource.RLIMIT_CPU, (45, 45))
def inventory():
    result = {}
    for path in [root, *sorted(root.rglob("*"))]:
        relative = "." if path == root else str(path.relative_to(root))
        status = path.lstat()
        common = {"mode": stat.S_IMODE(status.st_mode), "uid": status.st_uid, "gid": status.st_gid}
        if stat.S_ISREG(status.st_mode):
            result[relative] = {**common, "type": "file", "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "size": status.st_size}
        elif stat.S_ISDIR(status.st_mode):
            result[relative] = {**common, "type": "directory"}
        elif stat.S_ISLNK(status.st_mode):
            result[relative] = {**common, "type": "symlink", "target": str(path.readlink())}
        else:
            result[relative] = {**common, "type": "other", "device": status.st_rdev}
    return result
before = inventory()
package = pickle.loads(artifact_path.read_bytes())
after_load = inventory()
if not isinstance(package, dict) or package.get("model_family") != "release-risk":
    raise TypeError("serialized object is not a release-risk package")
if package.get("input_schema") != "keplerops.release-risk.text/v1":
    raise TypeError("serialized object changed the release-risk input schema")
members = package.get("members")
if not isinstance(members, dict):
    raise TypeError("serialized object has no embedded model members")
created = sorted(set(after_load) - set(before))
deleted = sorted(set(before) - set(after_load))
modified = sorted(name for name in set(before) & set(after_load) if before[name] != after_load[name])
if created != ["orion-deserialization-canary"] or deleted or modified:
    raise RuntimeError("deserialization changed state outside the bounded canary")
package_path.mkdir()
for name, value in members.items():
    if not isinstance(name, str) or pathlib.Path(name).name != name or not isinstance(value, bytes):
        raise TypeError("serialized package members must be flat named bytes")
    (package_path / name).write_bytes(value)
print(json.dumps({"created": created, "modified": modified, "deleted": deleted}, separators=(",", ":")))
'''

    with tempfile.TemporaryDirectory(prefix="cinder-artifact-review-") as root:
        root_path = Path(root)
        isolated_artifact = root_path / "submission.pkl"
        isolated_artifact.write_bytes(artifact)
        package_dir = root_path / "model"
        environment = {
            "HOME": root,
            "LANG": "C.UTF-8",
            "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        if os.getenv("CINDER_NETWORK_NAMESPACE") != "required" or not shutil.which("unshare"):
            raise SystemExit("the required Cinder network namespace is unavailable")
        command = [
            "unshare", "--map-root-user", "--user", "--mount", "--net", "--pid", "--fork",
            "--mount-proc", sys.executable, "-I", "-c", child,
            str(isolated_artifact), str(package_dir),
        ]
        completed = subprocess.run(
            command, cwd=root, env=environment, capture_output=True, text=True,
            timeout=60, check=True,
        )
        observed = json.loads(completed.stdout.strip().splitlines()[-1])
        if observed != {"created": ["orion-deserialization-canary"], "modified": [], "deleted": []}:
            raise SystemExit("deserialization must create only the bounded canary")
        canary = root_path / "orion-deserialization-canary"
        if canary.is_symlink() or not canary.is_file() or canary.read_text() != "bounded isolated effect":
            raise SystemExit("bounded deserialization effect is absent")
        missing = [name for name in REQUIRED.values() if not (package_dir / name).is_file()]
        if missing:
            raise SystemExit("serialized model package is incomplete: " + ", ".join(missing))
        actual_names = {path.name for path in package_dir.iterdir() if path.is_file()}
        if actual_names != set(REQUIRED.values()) or any(path.is_symlink() for path in package_dir.iterdir()):
            raise SystemExit("serialized model package has missing, extra, nested, or linked members")

        import onnx
        import onnxruntime as ort
        from transformers import AutoTokenizer

        config = json.loads((package_dir / REQUIRED["configuration"]).read_text())
        labels = json.loads((package_dir / REQUIRED["label_schema"]).read_text())
        preprocessing = json.loads((package_dir / REQUIRED["preprocessing"]).read_text())
        provenance = json.loads((package_dir / REQUIRED["provenance"]).read_text())
        signed_provenance = dict(provenance)
        provenance_signature = str(signed_provenance.pop("provenance_signature", ""))
        expected_provenance_signature = hmac.new(
            os.environ["ORION_PROVENANCE_KEY"].encode(), canonical(signed_provenance), hashlib.sha256,
        ).hexdigest()
        if labels != {name: index for index, name in enumerate(LABELS)}:
            raise SystemExit("serialized package changed the release-risk label map")
        configured_labels = config.get("id2label") or {}
        configured_count = int(config.get("num_labels", len(configured_labels)))
        if (config.get("model_type") != "bert" or configured_count != 8
                or configured_labels != {str(index): name for index, name in enumerate(LABELS)}
                or config.get("label2id") != {name: index for index, name in enumerate(LABELS)}
                or int(config.get("hidden_size", 0)) != 128 or int(config.get("num_hidden_layers", 0)) != 2):
            raise SystemExit("serialized package is not the admitted Orion BERT architecture")
        if (preprocessing.get("schema") != "keplerops.release-risk.preprocessing/v1"
                or preprocessing.get("input") != "utf-8 text" or preprocessing.get("max_length") != 64):
            raise SystemExit("serialized package changed Orion preprocessing")
        if (not hmac.compare_digest(provenance_signature, expected_provenance_signature)
                or provenance.get("model_family") != "release-risk"
                or provenance.get("base_model_revision") != "30b0a37ccaaa32f332884b96992754e246e48c5f"
                or provenance.get("source_repository") != "keplerops/orion-build"
                or provenance.get("labels") != LABELS
                or provenance.get("heldout_suite_sha256") != heldout_evidence_sha
                or not re.fullmatch(r"[0-9a-f]{40}", str(provenance.get("source_commit") or ""))
                or not re.fullmatch(r"[0-9a-f]{64}", str(provenance.get("source_tree_sha256") or ""))
                or not re.fullmatch(r"[0-9a-f]{64}", str(provenance.get("export_sha256") or ""))
                or not re.fullmatch(r"[0-9a-f]{64}", str(provenance.get("package_schema_sha256") or ""))
                or not str(provenance.get("lakefs_commit") or "")):
            raise SystemExit("serialized package lacks genuine Orion release lineage")

        model_path = package_dir / REQUIRED["model"]
        graph = onnx.load(model_path)
        onnx.checker.check_model(graph)
        if len(graph.graph.node) < 20 or len(graph.graph.initializer) < 10:
            raise SystemExit("serialized package contains a toy computation graph")
        session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
        if [item.name for item in session.get_inputs()] != ["input_ids", "attention_mask", "token_type_ids"]:
            raise SystemExit("serialized package changed the Orion runtime interface")
        if len(session.get_outputs()) != 1:
            raise SystemExit("serialized package changed the Orion output contract")
        tokenizer = AutoTokenizer.from_pretrained(package_dir, local_files_only=True)
        encoded = tokenizer(
            [item["text"] for item in heldout], padding="max_length", truncation=True,
            max_length=64, return_tensors="np",
        )
        logits = session.run(None, {item.name: encoded[item.name] for item in session.get_inputs()})[0]
        predictions = logits.argmax(axis=1).tolist()
        expected = [LABELS.index(item["label"]) for item in heldout]
        heldout_accuracy = sum(left == right for left, right in zip(predictions, expected)) / len(expected)
        if heldout_accuracy < 0.50 or len(set(predictions)) < 4:
            raise SystemExit("serialized package does not retain real release-risk fidelity")
        members = {name: f"sha256:{digest((package_dir / path).read_bytes())}" for name, path in REQUIRED.items()}
        package_inventory = {
            path: {"sha256": members[name], "size": (package_dir / path).stat().st_size}
            for name, path in REQUIRED.items()
        }
        expected_artifacts = provenance.get("artifacts") or {}
        for name, path in REQUIRED.items():
            if name != "provenance" and expected_artifacts.get(path) != members[name].removeprefix("sha256:"):
                raise SystemExit(f"embedded member differs from Orion provenance: {path}")
        if (package_dir / REQUIRED["model_card"]).read_bytes() != release_card:
            raise SystemExit("release card differs from the card embedded in the Orion package")
        report = {
            "schema": "keplerops.cinder.artifact-execution/v2",
            "review_kind": "serialized-release-risk-execution",
            "model_family": "release-risk",
            "input_schema": "keplerops.release-risk.text/v1",
            "artifact_filename": "orion-model.pkl",
            "artifact_format": "python-pickle",
            "artifact_interface": "embedded-onnx-package",
            "artifact_sha256": digest(artifact),
            "model_sha256": members["model"],
            "package_members": members,
            "package_inventory": package_inventory,
            "label_schema_sha256": members["label_schema"],
            "preprocessing_sha256": members["preprocessing"],
            "source_commit": args.source_commit,
            "attempt_id": args.attempt_id,
            "bounded_effect": True,
            "network_policy": "egress-denied-network-namespace",
            "side_effect_inventory": observed,
            "filesystem_policy": "landlock-root-only",
            "fresh_inference": [LABELS[index] for index in predictions],
            "heldout_suite_sha256": heldout_contract_sha,
            "heldout_evidence_sha256": heldout_evidence_sha,
            "heldout_case_count": len(heldout),
            "heldout_accuracy": heldout_accuracy,
            "release_card_sha256": digest(release_card),
            "activation_contract": {
                "schema": "cinder.artifact-pod-callback/v2",
                "artifact_sha256": f"sha256:{digest(artifact)}",
                "embedded_model_sha256": members["model"],
                "required_join": ["release_record", "runtime_digest", "pod_uid"],
            },
            "orion_provenance": {
                "source_repository": provenance["source_repository"],
                "source_commit": provenance["source_commit"],
                "source_tree_sha256": provenance["source_tree_sha256"],
                "source_export_sha256": provenance["export_sha256"],
                "training_lakefs_commit": provenance["lakefs_commit"],
                "package_schema_sha256": provenance["package_schema_sha256"],
                "provenance_signature": provenance_signature,
            },
            "execution_review_reference": os.environ["EXECUTION_REVIEW_REFERENCE"],
        }
        unsigned = canonical(report)
        report["signature"] = hmac.new(
            os.environ["CINDER_ATTESTATION_KEY"].encode(), unsigned, hashlib.sha256
        ).hexdigest()
        args.output.write_bytes(canonical(report))


if __name__ == "__main__":
    main()
