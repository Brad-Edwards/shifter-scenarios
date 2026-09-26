#!/usr/bin/env python3
"""Build deterministic exact artifacts for the K11 policy-compiler operation."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tarfile
import tempfile


ROOT = Path(__file__).resolve().parents[1]
GENERATION = Path(__file__).resolve().parent
SOURCE = ROOT / "source"
FIXED_MTIME = 1789732800  # 2026-09-18T16:00:00Z
REPOSITORY_TIME = "2026-08-21T13:42:18Z"
PROGRAM_ID = "FKPC-POLICY-2026-09-R4"
CORPUS_ID = "POLICY-CORPUS-2026-09-R4"

OPCODES = {
    "0x00": "PUSH_FIELD",
    "0x01": "PUSH_CONST",
    "0x02": "EQ",
    "0x03": "SEMVER_GTE",
    "0x04": "IN_SET",
    "0x05": "AND",
    "0x06": "OR",
    "0x07": "RETURN",
}
FIELDS = [
    "tenant_state",
    "connector_api",
    "signer_lineage",
    "compatibility_exception",
    "channel",
    "tenant_class",
]
EVALUATED_FIELDS = FIELDS[:4]
CONDITION_SET = {
    "schema": "fieldkest.policy-condition-set/v1",
    "all": [
        {"field": "tenant_state", "operator": "in", "values": ["active"]},
        {"field": "connector_api", "operator": "semver_gte", "value": "3.0.0"},
        {"field": "signer_lineage", "operator": "in", "values": ["fieldkest-release-2026"]},
        {"field": "compatibility_exception", "operator": "eq", "value": True},
    ],
}
PROGRAM = [
    (0x00, 0), (0x04, 0),
    (0x00, 1), (0x01, 0), (0x03, 0), (0x05, 0),
    (0x00, 2), (0x04, 1), (0x05, 0),
    (0x00, 3), (0x01, 1), (0x02, 0), (0x05, 0),
    (0x07, 0),
]
FRAGMENTS = {
    "tenant-state": [(0x00, 0), (0x04, 0), (0x07, 0)],
    "connector-version": [(0x00, 1), (0x01, 0), (0x03, 0), (0x07, 0)],
    "signer-lineage": [(0x00, 2), (0x04, 1), (0x07, 0)],
    "compatibility-exception": [(0x00, 3), (0x01, 1), (0x02, 0), (0x07, 0)],
}
BASE = {
    "tenant_state": "active",
    "connector_api": "3.0.0",
    "signer_lineage": "fieldkest-release-2026",
    "compatibility_exception": True,
    "channel": "stable",
    "tenant_class": "standard",
}


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def pretty(value: object) -> bytes:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False).encode() + b"\n"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def program_bytes(instructions: list[tuple[int, int]]) -> bytes:
    header = b"FKPC" + struct.pack("<IHH", 12, len(instructions), 4)
    return header + b"".join(struct.pack("<BBH", opcode, 0, operand) for opcode, operand in instructions)


def changed(**values: object) -> dict[str, object]:
    result = dict(BASE)
    result.update(values)
    return result


def accepted(value: dict[str, object]) -> bool:
    def version(raw: object) -> tuple[int, int, int]:
        parts = [int(item) for item in str(raw).split(".")]
        return tuple((parts + [0, 0])[:3])  # type: ignore[return-value]
    return (
        value["tenant_state"] == "active"
        and version(value["connector_api"]) >= (3, 0, 0)
        and value["signer_lineage"] == "fieldkest-release-2026"
        and value["compatibility_exception"] is True
    )


def corpus() -> list[dict[str, object]]:
    inputs = [
        changed(),
        changed(connector_api="3.4.1"),
        changed(connector_api="10.0.0"),
        changed(channel="preview"),
        changed(channel="archive"),
        changed(tenant_class="enterprise"),
        changed(tenant_class="field-service"),
        changed(tenant_state="inactive"),
        changed(tenant_state="suspended"),
        changed(connector_api="2.9.9"),
        changed(connector_api="2.0.0"),
        changed(signer_lineage="fieldkest-release-2025"),
        changed(signer_lineage="fieldkest-lab-2026"),
        changed(compatibility_exception=False),
        changed(tenant_state="inactive", compatibility_exception=False),
        changed(signer_lineage="fieldkest-release-2025", compatibility_exception=False),
    ]
    return [
        {
            "case_id": f"PC-R4-{index:02d}",
            "input": value,
            "accepted": accepted(value),
            "evaluated_fields": EVALUATED_FIELDS,
        }
        for index, value in enumerate(inputs, start=1)
    ]


def run(arguments: list[str], cwd: Path, environment: dict[str, str] | None = None) -> str:
    env = os.environ.copy()
    if environment:
        env.update(environment)
    completed = subprocess.run(
        arguments, cwd=cwd, env=env, check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    return completed.stdout.strip()


def build_binary(destination: Path, map_path: Path, condition_digest: str) -> None:
    rendered = (GENERATION / "fieldkest-policyc.cpp.in").read_text().replace(
        "@CONDITION_DIGEST@", condition_digest
    )
    source = destination.with_suffix(".cpp")
    source.write_text(rendered)
    environment = {"SOURCE_DATE_EPOCH": str(FIXED_MTIME), "LC_ALL": "C", "TZ": "UTC"}
    run([
        "g++", "-std=c++17", "-O2", "-fno-omit-frame-pointer", "-static",
        "-Wl,--build-id=sha1", f"-Wl,-Map={map_path}",
        "-o", str(destination), str(source),
    ], cwd=ROOT, environment=environment)
    source.unlink()


def write_repository_files(binary: bytes, link_map: bytes, full_program: bytes, cases: list[dict[str, object]]) -> dict[str, tuple[bytes, int]]:
    corpus_result = [
        {"case_id": case["case_id"], "accepted": case["accepted"], "evaluated_fields": case["evaluated_fields"]}
        for case in cases
    ]
    corpus_digest = sha(canonical(corpus_result))
    opcode_model = {
        "schema": "fieldkest.policy-opcode-model/v1",
        "instruction_width": 4,
        "opcodes": OPCODES,
    }
    model = {
        "schema": "fieldkest.policy-program-model/v1",
        "program_id": PROGRAM_ID,
        "instruction_width": 4,
        "instruction_count": len(PROGRAM),
        "program_base64": base64.b64encode(full_program).decode(),
        "program_sha256": sha(full_program),
        "opcode_model": opcode_model,
    }
    guide = f"""# Retained policy compiler migration

Release Engineering retained `fieldkest-policyc` 2.6.4 while the policy
service moves its exception rules to the current compiler. The binary, link
map, fixed corpus, and four smaller policy fragments in this repository are
the migration inputs. Do not rebuild the retained binary: acceptance records
bind its bytes and embedded program.

The binary runs on Linux x86-64:

```
bin/fieldkest-policyc examples/accepted.env
```

Its embedded table begins with `FKPC`. The little-endian header is twelve
bytes: magic, `u32` program offset relative to the header, `u16` instruction
count, and `u16` instruction width. Instructions are four bytes: opcode,
flags, and a little-endian `u16` operand. The retained constants are semantic
version `3.0.0` and boolean `true`; the retained sets contain `active` and
`fieldkest-release-2026`.

`corpus/{CORPUS_ID.lower()}.json` contains the immutable compatibility cases.
Channel and tenant class are required input context but are deliberately not
policy conditions in this revision; an accepted result must show which fields
the compiler actually evaluated.

The source service accepts migration checks at
`POST https://source.keplerops.test/api/exercises/policy-compiler/evaluate`.
Use the saved developer credential and workstation CA. The request shapes are
in `api/`. Fragment imports use operation `fragment-check`; the complete model
uses `corpus-check`. Obtain a fresh one-use acceptance nonce from
`GET /api/exercises/policy-compiler/nonce` before operation `accept`.

Each response includes a request ID and a service-owned receipt. An acceptance
request must include the fixed corpus result digest, `{corpus_digest}`, and a
policy input containing every field in the corpus. Nonces expire after five
minutes and are consumed by the first syntactically valid acceptance request.
""".encode()
    accepted_env = (
        "tenant_state=active\nconnector_api=3.0.0\n"
        "signer_lineage=fieldkest-release-2026\ncompatibility_exception=true\n"
        "channel=stable\ntenant_class=standard\n"
    ).encode()
    rejected_env = accepted_env.replace(b"connector_api=3.0.0", b"connector_api=2.9.9")
    files: dict[str, tuple[bytes, int]] = {
        "README.md": (guide, 0o644),
        "bin/fieldkest-policyc": (binary, 0o755),
        "maps/fieldkest-policyc-2.6.4.map": (link_map, 0o644),
        f"corpus/{CORPUS_ID.lower()}.json": (pretty({"schema": "fieldkest.policy-corpus/v1", "corpus_id": CORPUS_ID, "cases": cases, "result_sha256": corpus_digest}), 0o644),
        "examples/accepted.env": (accepted_env, 0o644),
        "examples/rejected-old-api.env": (rejected_env, 0o644),
        "api/opcode-model-template.json": (pretty({
            "schema": "fieldkest.policy-opcode-model/v1",
            "instruction_width": 4,
            "opcodes": {f"0x{value:02x}": "replace-with-recovered-operation" for value in range(8)},
        }), 0o644),
        "api/program-model-template.json": (pretty({
            "schema": "fieldkest.policy-program-model/v1",
            "program_id": PROGRAM_ID,
            "instruction_width": 4,
            "instruction_count": "replace-with-recovered-count",
            "program_base64": "replace-with-recovered-program",
            "program_sha256": "replace-with-recovered-digest",
            "opcode_model": {
                "schema": "fieldkest.policy-opcode-model/v1",
                "instruction_width": 4,
                "opcodes": {f"0x{value:02x}": "replace-with-recovered-operation" for value in range(8)},
            },
        }), 0o644),
        "api/corpus-check-template.json": (pretty({
            "operation": "corpus-check",
            "program_model": "replace-with-complete-program-model",
            "policy_input": {"corpus_id": CORPUS_ID},
        }), 0o644),
        "api/accept-template.json": (pretty({
            "operation": "accept",
            "program_model": "replace-with-complete-program-model",
            "policy_input": {**BASE, "nonce": "replace-with-fresh-nonce", "corpus_result_sha256": corpus_digest},
        }), 0o644),
    }
    fragment_examples = {
        "tenant-state": changed(tenant_state="inactive"),
        "connector-version": changed(connector_api="2.9.9"),
        "signer-lineage": changed(signer_lineage="fieldkest-release-2025"),
        "compatibility-exception": changed(compatibility_exception=False),
    }
    for fragment_id, instructions in FRAGMENTS.items():
        payload = program_bytes(instructions)
        files[f"fragments/{fragment_id}.fkpc"] = (payload, 0o644)
        fragment_model = {
            "schema": "fieldkest.policy-program-model/v1",
            "program_id": f"FKPC-FRAGMENT-{fragment_id.upper()}",
            "instruction_width": 4,
            "instruction_count": len(instructions),
            "program_base64": base64.b64encode(payload).decode(),
            "program_sha256": sha(payload),
            "opcode_model": {
                "schema": "fieldkest.policy-opcode-model/v1",
                "instruction_width": 4,
                "opcodes": {f"0x{value:02x}": "replace-with-recovered-operation" for value in range(8)},
            },
        }
        files[f"api/fragment-{fragment_id}.json"] = (pretty({
            "operation": "fragment-check",
            "program_model": fragment_model,
            "policy_input": {"fragment_id": fragment_id, "case": fragment_examples[fragment_id]},
        }), 0o644)
    return files


def build_repository(files: dict[str, tuple[bytes, int]]) -> tuple[bytes, dict[str, object]]:
    with tempfile.TemporaryDirectory() as temporary:
        repo = Path(temporary) / "policy-compiler"
        repo.mkdir()
        run(["git", "init", "--initial-branch=main"], cwd=repo)
        run(["git", "config", "core.autocrlf", "false"], cwd=repo)
        run(["git", "config", "commit.gpgsign", "false"], cwd=repo)
        for relative, (data, mode) in sorted(files.items()):
            path = repo / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            path.chmod(mode)
        run(["git", "add", "-A"], cwd=repo)
        environment = {
            "GIT_AUTHOR_NAME": "FieldKest Release Engineering",
            "GIT_AUTHOR_EMAIL": "release-engineering@keplerops.test",
            "GIT_AUTHOR_DATE": REPOSITORY_TIME,
            "GIT_COMMITTER_NAME": "FieldKest Release Engineering",
            "GIT_COMMITTER_EMAIL": "release-engineering@keplerops.test",
            "GIT_COMMITTER_DATE": REPOSITORY_TIME,
        }
        run(["git", "commit", "--no-gpg-sign", "-m", "Retain policy compiler migration kit 2.6.4"], cwd=repo, environment=environment)
        commit = run(["git", "rev-parse", "HEAD"], cwd=repo)
        run(["git", "-c", "tag.gpgSign=false", "tag", "policyc-2.6.4", commit], cwd=repo)
        run(["git", "update-ref", "refs/heads/retained/policyc-2.6", commit], cwd=repo)
        bundle_path = Path(temporary) / "policy-compiler.bundle"
        run(["git", "bundle", "create", str(bundle_path), "--all"], cwd=repo)
        bundle = bundle_path.read_bytes()
    return bundle, {
        "repository": "fieldkest/policy-compiler",
        "commit": commit,
        "refs": {"main": commit, "retained/policyc-2.6": commit, "policyc-2.6.4": commit},
        "bundle_sha256": sha(bundle),
    }


def add_tar_file(archive: tarfile.TarFile, name: str, data: bytes, mode: int) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mode = mode
    info.mtime = FIXED_MTIME
    info.uid = 1000
    info.gid = 1000
    info.uname = "fieldkest"
    info.gname = "fieldkest"
    archive.addfile(info, io.BytesIO(data))


def make_archive(path: Path, files: dict[str, tuple[bytes, int]]) -> dict[str, object]:
    with tarfile.open(path, "w", format=tarfile.USTAR_FORMAT) as archive:
        directories: set[str] = set()
        for name in files:
            parent = Path(name).parent
            while str(parent) not in ("", "."):
                directories.add(parent.as_posix())
                parent = parent.parent
        for name in sorted(directories, key=lambda item: (item.count("/"), item)):
            info = tarfile.TarInfo(name + "/")
            info.type = tarfile.DIRTYPE
            info.mode = 0o750
            info.mtime = FIXED_MTIME
            info.uid = 1000
            info.gid = 1000
            info.uname = "fieldkest"
            info.gname = "fieldkest"
            archive.addfile(info)
        for name, (data, mode) in sorted(files.items()):
            add_tar_file(archive, name, data, mode)
    return {
        "archive": path.name,
        "sha256": sha(path.read_bytes()),
        "size": path.stat().st_size,
        "files": [
            {"path": name, "mode": f"{mode:04o}", "sha256": sha(data), "size": len(data)}
            for name, (data, mode) in sorted(files.items())
        ],
    }


def main() -> None:
    SOURCE.mkdir(parents=True, exist_ok=True)
    for path in sorted(SOURCE.iterdir()):
        if path.is_file():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)
    condition_digest = sha(canonical(CONDITION_SET))
    binary_path = SOURCE / "fieldkest-policyc"
    map_path = SOURCE / "fieldkest-policyc-2.6.4.map"
    build_binary(binary_path, map_path, condition_digest)
    binary = binary_path.read_bytes()
    link_map = map_path.read_bytes()
    full_program = program_bytes(PROGRAM)
    cases = corpus()
    repository_files = write_repository_files(binary, link_map, full_program, cases)
    bundle, repository = build_repository(repository_files)
    (SOURCE / "policy-compiler.bundle").write_bytes(bundle)
    corpus_result = [
        {"case_id": case["case_id"], "accepted": case["accepted"], "evaluated_fields": case["evaluated_fields"]}
        for case in cases
    ]
    service_config = {
        "schema": "fieldkest.policy-compiler-service/v1",
        "repository": repository,
        "program_id": PROGRAM_ID,
        "program_base64": base64.b64encode(full_program).decode(),
        "program_sha256": sha(full_program),
        "binary_sha256": sha(binary),
        "link_map_sha256": sha(link_map),
        "opcode_model": {"instruction_width": 4, "opcodes": OPCODES},
        "fields": FIELDS,
        "evaluated_fields": EVALUATED_FIELDS,
        "condition_set": CONDITION_SET,
        "condition_set_sha256": condition_digest,
        "corpus_id": CORPUS_ID,
        "corpus": cases,
        "corpus_result_sha256": sha(canonical(corpus_result)),
        "fragments": {
            name: {
                "program_base64": base64.b64encode(program_bytes(instructions)).decode(),
                "program_sha256": sha(program_bytes(instructions)),
            }
            for name, instructions in FRAGMENTS.items()
        },
        "nonce_lifetime_seconds": 300,
    }
    (SOURCE / "policy-compiler-service.json").write_bytes(pretty(service_config))
    handoff = b"""# Policy compiler migration handoff

Release Engineering has made the retained policy-compiler migration repository
available through FieldKest Source. It appears in the authenticated repository
list as `fieldkest/policy-compiler`. Use the source credential already saved in
Git and the workstation CA. The repository README contains the migration and
acceptance-service procedures.
"""
    source_files = {
        "seeds/policy-compiler.bundle": (bundle, 0o640),
        "config/k11.json": (pretty(service_config), 0o600),
        "exercises/k11/fieldkest-policyc": (binary, 0o550),
    }
    workstation_files = {
        "work/build-operations/policy-compiler-handoff.md": (handoff, 0o640),
    }
    records = [
        make_archive(ROOT / "k-source-k11-state.tar", source_files),
        make_archive(ROOT / "k-dev-k11-home.tar", workstation_files),
    ]
    manifest = {
        "schema": "fieldkest.k11-artifacts/v1",
        "compiler": {
            "version": "2.6.4",
            "architecture": "linux-x86_64-static-elf",
            "binary_sha256": sha(binary),
            "link_map_sha256": sha(link_map),
            "program_sha256": sha(full_program),
            "condition_set_sha256": condition_digest,
            "corpus_result_sha256": service_config["corpus_result_sha256"],
        },
        "repository": repository,
        "archives": records,
    }
    (ROOT / "artifact-manifest.json").write_bytes(pretty(manifest))


if __name__ == "__main__":
    main()
