"""FieldLink policy compiler and archived connector operations."""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import re
import secrets
import subprocess
import tempfile
import threading
import time
from urllib.parse import urlsplit

from http_support import KeplerHandler, append_audit, canonical_bytes, serve_tls
from credentials import credential


STATE = Path("/var/lib/gitea")
AUDIT = STATE / "audit"
CONFIG = json.loads((STATE / "config/opening.json").read_text())
K11_CONFIG = json.loads((STATE / "config/policy-compiler.json").read_text())
K28_CONFIG = json.loads((STATE / "config/connector-archive.json").read_text())
TOKEN = credential("developer_token")
USERNAME = CONFIG["credentials"][0]["principal"]
POLICY_BINARY = STATE / "toolchains/policy-compilers/fieldkest-policyc"
POLICY_STATE = AUDIT / "policy-state"
POLICY_LOCK = threading.RLock()
CONNECTOR_BINARY = STATE / "exercises/connector-archive/fieldlink-connector"
CONNECTOR_RESULTS = AUDIT / "connector-archive-results"


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def decode_program_model(value: object) -> tuple[bytes, list[tuple[int, int]], dict[str, str]]:
    if not isinstance(value, dict) or set(value) != {
        "schema", "program_id", "instruction_width", "instruction_count",
        "program_base64", "program_sha256", "opcode_model",
    }:
        raise ValueError("invalid_program_model")
    if value["schema"] != "fieldkest.policy-program-model/v1" or value["instruction_width"] != 4:
        raise ValueError("invalid_program_model")
    if not isinstance(value["program_id"], str) or not value["program_id"]:
        raise ValueError("invalid_program_model")
    opcode_model = value["opcode_model"]
    if not isinstance(opcode_model, dict) or set(opcode_model) != {"schema", "instruction_width", "opcodes"}:
        raise ValueError("invalid_opcode_model")
    if opcode_model["schema"] != "fieldkest.policy-opcode-model/v1" or opcode_model["instruction_width"] != 4:
        raise ValueError("invalid_opcode_model")
    expected_opcodes = K11_CONFIG["opcode_model"]["opcodes"]
    if opcode_model["opcodes"] != expected_opcodes:
        raise ValueError("opcode_model_mismatch")
    try:
        raw = base64.b64decode(value["program_base64"], validate=True)
    except (ValueError, TypeError):
        raise ValueError("invalid_program_encoding") from None
    if value["program_sha256"] != sha256(raw) or len(raw) < 12 or raw[:4] != b"FKPC":
        raise ValueError("invalid_program_digest")
    offset = int.from_bytes(raw[4:8], "little")
    count = int.from_bytes(raw[8:10], "little")
    width = int.from_bytes(raw[10:12], "little")
    if offset != 12 or width != 4 or value["instruction_count"] != count or len(raw) != offset + count * width:
        raise ValueError("invalid_program_table")
    instructions = []
    for index in range(count):
        start = offset + index * width
        opcode, flags = raw[start], raw[start + 1]
        operand = int.from_bytes(raw[start + 2:start + 4], "little")
        if flags != 0 or f"0x{opcode:02x}" not in expected_opcodes:
            raise ValueError("invalid_instruction")
        instructions.append((opcode, operand))
    return raw, instructions, opcode_model["opcodes"]


def semver(value: object) -> tuple[int, int, int]:
    if not isinstance(value, str):
        raise ValueError("invalid_semantic_version")
    components = value.split(".")
    if not 1 <= len(components) <= 3 or any(not item.isdigit() for item in components):
        raise ValueError("invalid_semantic_version")
    parsed = [int(item) for item in components]
    return tuple((parsed + [0, 0])[:3])  # type: ignore[return-value]


def policy_fields(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or any(field not in value for field in K11_CONFIG["fields"]):
        raise ValueError("missing_policy_field")
    result = {field: value[field] for field in K11_CONFIG["fields"]}
    if any(not isinstance(result[field], str) or not result[field] for field in (
        "tenant_state", "connector_api", "signer_lineage", "channel", "tenant_class"
    )) or not isinstance(result["compatibility_exception"], bool):
        raise ValueError("invalid_policy_field")
    semver(result["connector_api"])
    return result


def execute_program(instructions: list[tuple[int, int]], policy_input: dict[str, object]) -> tuple[bool, list[str]]:
    fields = K11_CONFIG["fields"]
    constants: list[object] = ["3.0.0", True]
    sets = [{"active"}, {"fieldkest-release-2026"}]
    stack: list[object] = []
    evaluated: list[str] = []

    def pop() -> object:
        if not stack:
            raise ValueError("stack_underflow")
        return stack.pop()

    for index, (opcode, operand) in enumerate(instructions):
        if opcode == 0x00:
            if operand >= 4:
                raise ValueError("bad_field_index")
            field = fields[operand]
            if field not in evaluated:
                evaluated.append(field)
            stack.append(policy_input[field])
        elif opcode == 0x01:
            if operand >= len(constants):
                raise ValueError("bad_constant_index")
            stack.append(constants[operand])
        elif opcode == 0x02:
            right, left = pop(), pop()
            stack.append(left == right)
        elif opcode == 0x03:
            required, actual = pop(), pop()
            stack.append(semver(actual) >= semver(required))
        elif opcode == 0x04:
            if operand >= len(sets):
                raise ValueError("bad_set_index")
            stack.append(pop() in sets[operand])
        elif opcode in (0x05, 0x06):
            right, left = pop(), pop()
            if not isinstance(left, bool) or not isinstance(right, bool):
                raise ValueError("boolean_required")
            stack.append(left and right if opcode == 0x05 else left or right)
        elif opcode == 0x07:
            if index + 1 != len(instructions) or len(stack) != 1 or not isinstance(stack[0], bool):
                raise ValueError("invalid_return")
            return stack[0], evaluated
        else:
            raise ValueError("unknown_opcode")
        if len(stack) > 32:
            raise ValueError("stack_limit")
    raise ValueError("missing_return")


def issue_policy_nonce(principal: str, request_id: str) -> dict[str, object]:
    nonce = secrets.token_urlsafe(16)
    now = int(time.time())
    record = {
        "schema": "fieldkest.policy-nonce/v1", "nonce": nonce, "principal": principal,
        "issued_at_epoch": now, "expires_at_epoch": now + K11_CONFIG["nonce_lifetime_seconds"],
        "consumed": False,
    }
    with POLICY_LOCK:
        nonce_dir = POLICY_STATE / "nonces"
        nonce_dir.mkdir(parents=True, exist_ok=True)
        (nonce_dir / f"{nonce}.json").write_text(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
    append_audit(AUDIT, "policy-compiler", {
        "request_id": request_id, "principal": principal, "operation": "issue-nonce",
        "nonce_sha256": sha256(nonce.encode()), "expires_at_epoch": record["expires_at_epoch"], "status": 201,
    })
    return {"nonce": nonce, "expires_at_epoch": record["expires_at_epoch"]}


def consume_policy_nonce(nonce: object, principal: str, request_id: str) -> None:
    if not isinstance(nonce, str) or not re.fullmatch(r"[A-Za-z0-9_-]{22}", nonce):
        raise ValueError("invalid_nonce")
    path = POLICY_STATE / "nonces" / f"{nonce}.json"
    with POLICY_LOCK:
        if not path.is_file():
            raise ValueError("invalid_nonce")
        record = json.loads(path.read_text())
        if record["principal"] != principal or record["consumed"] or record["expires_at_epoch"] < int(time.time()):
            raise ValueError("stale_or_replayed_nonce")
        record["consumed"] = True
        record["consumed_by_request"] = request_id
        temporary = path.with_name("." + path.name + ".tmp")
        temporary.write_text(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
        temporary.replace(path)


def run_retained_compiler(policy_input: dict[str, object]) -> dict[str, object]:
    lines = [
        f"tenant_state={policy_input['tenant_state']}",
        f"connector_api={policy_input['connector_api']}",
        f"signer_lineage={policy_input['signer_lineage']}",
        f"compatibility_exception={'true' if policy_input['compatibility_exception'] else 'false'}",
        f"channel={policy_input['channel']}",
        f"tenant_class={policy_input['tenant_class']}",
    ]
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir="/tmp", prefix="policy-input-", delete=True) as handle:
        handle.write("\n".join(lines) + "\n")
        handle.flush()
        completed = subprocess.run(
            [str(POLICY_BINARY), handle.name], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            check=False, timeout=2, text=True,
        )
    if completed.returncode not in (0, 2):
        raise RuntimeError("compiler_failed")
    result = json.loads(completed.stdout)
    if result.get("accepted") is not (completed.returncode == 0):
        raise RuntimeError("compiler_result_mismatch")
    return result


class SourceHandler(KeplerHandler):
    def _developer(self) -> bool:
        return self.basic_or_bearer(USERNAME, TOKEN)

    def do_GET(self) -> None:
        if urlsplit(self.path).path == '/.well-known/fieldkest-client':
            reference = json.loads(Path('/opt/fieldkest/client_documents.json').read_text())
            self.send_json(200, reference['documents']['source.keplerops.test'])
            return
        self.send_json(404, {"error": "not_found"})

    def do_POST(self) -> None:
        parsed = urlsplit(self.path)
        if parsed.path == "/api/policy-compilers/fieldkest-policyc/evaluations":
            if not self._developer():
                self.send_json(401, {"error": "authentication_required"}, headers={"WWW-Authenticate": 'Basic realm="FieldKest Source"'})
                return
            self._policy_compiler_evaluate()
        elif parsed.path == "/api/policy-compilers/fieldkest-policyc/nonces":
            if not self._developer():
                self.send_json(401, {"error": "authentication_required"}, headers={"WWW-Authenticate": 'Basic realm="FieldKest Source"'})
                return
            self._policy_compiler_nonce()
        elif parsed.path == "/api/exercises/connector-archive/run":
            if not self._developer():
                self.send_json(401, {"error": "authentication_required"}, headers={"WWW-Authenticate": 'Basic realm="FieldKest Source"'})
                return
            self._connector_archive_run()
        else:
            self.send_json(404, {"error": "not_found"})

    def _connector_archive_run(self) -> None:
        try:
            fields = self.read_uploads(32 * 1024)
            if set(fields) != {"input", "diagnostic_config"}:
                raise ValueError("archive_run_fields_required")
            if len(fields["input"]) > 4096 or len(fields["diagnostic_config"]) > 512:
                raise OverflowError("archive_run_too_large")
            with tempfile.TemporaryDirectory(prefix="connector-archive-", dir="/tmp") as temporary:
                root = Path(temporary)
                (root / "input.bin").write_bytes(fields["input"])
                (root / "config.conf").write_bytes(fields["diagnostic_config"])
                completed = subprocess.run(
                    [str(CONNECTOR_BINARY), "--config", str(root / "config.conf"), "--input", str(root / "input.bin")],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=2,
                )
            if completed.returncode != 0:
                raise ValueError("connector_run_rejected")
            result = json.loads(completed.stdout)
            if result.get("interface") != "fieldkest.connector/v2" or result.get("mode") not in {"ordinary", "diagnostic"}:
                raise RuntimeError("connector_result_invalid")
        except (ValueError, KeyError, TypeError, json.JSONDecodeError, OverflowError, subprocess.TimeoutExpired) as error:
            append_audit(AUDIT, "connector-archive", {"request_id": self.request_id, "principal": USERNAME, "outcome": str(error), "status": 422})
            self.send_json(422, {"error": str(error)})
            return
        except (OSError, RuntimeError):
            self.send_json(503, {"error": "connector_unavailable"})
            return
        if result["mode"] == "diagnostic":
            result["flag_k28_2"] = "FLAG{d4fec1d1bcc12c7d}"
            if result.get("route") != K28_CONFIG["route"] or result.get("note_id") != K28_CONFIG["note_id"]:
                self.send_json(503, {"error": "connector_result_invalid"})
                return
            result["flag_k28_3"] = "FLAG{9fd67f66428a244c}"
        result["request_id"] = self.request_id
        receipt = "CARUN-" + secrets.token_hex(6).upper()
        result["receipt_id"] = receipt
        CONNECTOR_RESULTS.mkdir(parents=True, exist_ok=True)
        (CONNECTOR_RESULTS / f"{receipt}.json").write_text(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
        append_audit(AUDIT, "connector-archive", {"request_id": self.request_id, "principal": USERNAME, "receipt_id": receipt, "mode": result["mode"], "input_sha256": sha256(fields["input"]), "output_sha256": result.get("output_sha256"), "status": 200})
        self.send_json(200, result)

    def _policy_compiler_nonce(self) -> None:
        try:
            if self.read_json(1024) != {}:
                raise ValueError("nonce_request_must_be_empty")
        except (ValueError, TypeError, json.JSONDecodeError, OverflowError) as error:
            append_audit(AUDIT, "policy-compiler", {
                "request_id": self.request_id, "principal": USERNAME,
                "operation": "issue-nonce", "outcome": str(error), "status": 422,
            })
            self.send_json(422, {"error": str(error)})
            return
        self.send_json(201, issue_policy_nonce(USERNAME, self.request_id))

    def _policy_compiler_evaluate(self) -> None:
        try:
            request = self.read_json(256 * 1024)
            if not isinstance(request, dict) or set(request) != {"operation", "program_model", "policy_input"}:
                raise ValueError("invalid_request")
            operation = request["operation"]
            if operation not in {"fragment-check", "corpus-check", "accept"}:
                raise ValueError("invalid_operation")
            if not isinstance(request["policy_input"], dict):
                raise ValueError("invalid_policy_input")
            policy_input = request["policy_input"]
            raw, instructions, _ = decode_program_model(request["program_model"])
            if operation == "fragment-check":
                if set(policy_input) != {"fragment_id", "case"} or not isinstance(policy_input["fragment_id"], str):
                    raise ValueError("invalid_fragment_request")
                fragment = K11_CONFIG["fragments"].get(policy_input["fragment_id"])
                if fragment is None or sha256(raw) != K11_CONFIG["program_sha256"]:
                    raise ValueError("fragment_binding_mismatch")
                case = policy_fields(policy_input["case"])
                result, evaluated = execute_program(instructions, case)
                receipt = "PCMIG-" + secrets.token_hex(6).upper()
                response = {
                    "schema": "fieldkest.policy-migration-result/v1", "receipt_id": receipt,
                    "operation": operation, "fragment_id": policy_input["fragment_id"],
                    "program_sha256": sha256(raw), "accepted": result, "evaluated_fields": evaluated,
                    "flag": "FLAG{5f3e067c00b70ca5}",
                }
            elif operation == "corpus-check":
                if set(policy_input) != {"corpus_id"} or policy_input["corpus_id"] != K11_CONFIG["corpus_id"]:
                    raise ValueError("corpus_binding_mismatch")
                if sha256(raw) != K11_CONFIG["program_sha256"]:
                    raise ValueError("program_binding_mismatch")
                results = []
                for case in K11_CONFIG["corpus"]:
                    result, evaluated = execute_program(instructions, policy_fields(case["input"]))
                    if result is not case["accepted"] or evaluated != case["evaluated_fields"]:
                        raise ValueError("corpus_mismatch")
                    results.append({"case_id": case["case_id"], "accepted": result, "evaluated_fields": evaluated})
                result_digest = sha256(canonical_bytes(results))
                if result_digest != K11_CONFIG["corpus_result_sha256"]:
                    raise RuntimeError("corpus_result_mismatch")
                receipt = "PCMIG-" + secrets.token_hex(6).upper()
                response = {
                    "schema": "fieldkest.policy-migration-result/v1", "receipt_id": receipt,
                    "operation": operation, "corpus_id": K11_CONFIG["corpus_id"],
                    "program_sha256": sha256(raw), "case_count": len(results),
                    "corpus_result_sha256": result_digest,
                    "condition_set_sha256": K11_CONFIG["condition_set_sha256"],
                    "flag": "FLAG{88d2ffcc302012c8}",
                }
            else:
                required = set(K11_CONFIG["fields"]) | {"nonce", "corpus_result_sha256"}
                if set(policy_input) != required:
                    raise ValueError("invalid_acceptance_input")
                case = policy_fields(policy_input)
                consume_policy_nonce(policy_input["nonce"], USERNAME, self.request_id)
                if sha256(raw) != K11_CONFIG["program_sha256"]:
                    raise ValueError("program_binding_mismatch")
                if policy_input["corpus_result_sha256"] != K11_CONFIG["corpus_result_sha256"]:
                    raise ValueError("corpus_mismatch")
                compiler_result = run_retained_compiler(case)
                if not compiler_result["accepted"]:
                    raise ValueError("policy_rejected")
                if (compiler_result["condition_set_sha256"] != K11_CONFIG["condition_set_sha256"] or
                        compiler_result["evaluated_fields"] != K11_CONFIG["evaluated_fields"]):
                    raise RuntimeError("compiler_result_mismatch")
                receipt = "PCACC-" + secrets.token_hex(6).upper()
                response = {
                    "schema": "fieldkest.policy-acceptance/v1", "receipt_id": receipt,
                    "operation": operation, "program_id": K11_CONFIG["program_id"],
                    "program_sha256": sha256(raw), "binary_sha256": K11_CONFIG["binary_sha256"],
                    "corpus_result_sha256": policy_input["corpus_result_sha256"],
                    "condition_set_sha256": compiler_result["condition_set_sha256"],
                    "evaluated_fields": compiler_result["evaluated_fields"],
                    "accepted": True,
                }
        except (ValueError, KeyError, TypeError, json.JSONDecodeError, OverflowError) as error:
            append_audit(AUDIT, "policy-compiler", {
                "request_id": self.request_id, "principal": USERNAME,
                "operation": "evaluate", "outcome": str(error), "status": 422,
            })
            self.send_json(422, {"error": str(error)})
            return
        except (OSError, RuntimeError, subprocess.SubprocessError):
            self.send_json(503, {"error": "compiler_unavailable"})
            return
        response["request_id"] = self.request_id
        result_dir = POLICY_STATE / "results"
        result_dir.mkdir(parents=True, exist_ok=True)
        (result_dir / f"{receipt}.json").write_text(json.dumps(response, sort_keys=True, separators=(",", ":")) + "\n")
        append_audit(AUDIT, "policy-compiler", {
            "request_id": self.request_id, "principal": USERNAME, "operation": operation,
            "receipt_id": receipt, "program_sha256": response["program_sha256"],
            "evaluated_fields": response.get("evaluated_fields", []), "status": 200,
        })
        if response.get("operation") == "accept":
            if response.get("accepted"):
                response["flag"] = "FLAG{23645a251793b19e}"  # K11.4: accepted
            else:
                response["flag"] = "FLAG{c71020d43793593b}"  # K11.3: accept attempt
        self.send_json(200, response)


def main() -> None:
    AUDIT.mkdir(parents=True, exist_ok=True)
    POLICY_STATE.mkdir(parents=True, exist_ok=True)
    serve_tls(SourceHandler, port=8443)


if __name__ == "__main__":
    main()
