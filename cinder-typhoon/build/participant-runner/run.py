#!/usr/bin/env python3
"""Run known-solution acceptance inside the real participant account boundary.

The operator process selects and streams an authored suite.  The suite is never
mounted or copied into the participant filesystem.  Reset and report storage
remain operator responsibilities; only participant-available actions execute
inside the workstation.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "build" / "input-provenance"))
sys.path.insert(0, str(ROOT / "challenges"))

import catalog as delivery_catalog  # noqa: E402
from provenance import ProvenanceError, attach_runtime_provenance  # noqa: E402

EVENT_PREFIX = "CINDER_ACCEPTANCE_EVENT "
RESULT_PREFIX = "CINDER_BOUNDARY_RESULT "
SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/+-]{0,159}$")


@dataclass(frozen=True)
class Phase:
    container: str
    user: str
    uid: int
    gid: int
    home: str
    suite: Path
    class_name: str
    expected_networks: frozenset[str]
    allowed_mounts: frozenset[str]
    forbidden_paths: tuple[str, ...]
    absent_paths: tuple[str, ...]


COMMON_ABSENT = ("/opt/operator-tests", "/opt/cinder-typhoon", "/var/run/docker.sock")
PHASES = {
    "training": Phase(
        container="cinder-training-kali", user="cinder", uid=2000, gid=2000,
        home="/home/cinder",
        suite=ROOT / "build/training/tests/test_known_solution_live.py",
        class_name="TrainingKnownSolutionAcceptance",
        expected_networks=frozenset({"cinder-training"}),
        allowed_mounts=frozenset(),
        forbidden_paths=COMMON_ABSENT + (
            "/var/lib/cinder-workbench", "/var/lib/cinder-accounts",
            "/var/lib/cinder-developer", "/var/lib/cinder-state",
        ),
        absent_paths=COMMON_ABSENT,
    ),
    "keplerops": Phase(
        container="cinder-keplerops-k-dev", user="rowan", uid=2000, gid=2000,
        home="/home/rowan",
        suite=ROOT / "build/keplerops/tests/test_known_solution_live.py",
        class_name="KeplerOpsKnownSolutionAcceptance",
        expected_networks=frozenset({"cinder-keplerops-corporate"}),
        allowed_mounts=frozenset({
            "/home/rowan", "/var/lib/fieldkest-workbench/audit",
            "/run/fieldkest-auth/ca.crt", "/run/fieldkest-auth/rowan_authorized_keys",
        }),
        forbidden_paths=COMMON_ABSENT + (
            "/opt/fieldkest-seeds", "/opt/fieldkest-workbench",
            "/opt/fieldkest-workbench/workbench.py", "/opt/keplerops-workbench",
            "/usr/local/bin/fieldkest-k-dev-entrypoint",
            "/var/lib/fieldkest-workbench", "/var/lib/fieldkest-workbench/audit",
            "/var/lib/fieldkest-ci", "/var/lib/fieldkest-registry",
            "/var/lib/fieldkest-support", "/var/lib/fieldkest-cloud-api",
            "/var/lib/fieldkest-data", "/var/lib/fieldkest-identity",
            "/run/fieldkest-auth/worker-hmac.key",
        ),
        absent_paths=COMMON_ABSENT,
    ),
    "arwc": Phase(
        container="cinder-arwc-connector", user="fieldlink", uid=999, gid=999,
        home="/var/lib/fieldlink-connector",
        suite=ROOT / "build/arwc/tests/test_known_solution_live.py",
        class_name="ARWCKnownSolutionAcceptance",
        expected_networks=frozenset({"cinder-arwc-corporate", "cinder-arwc-maintenance"}),
        allowed_mounts=frozenset({
            "/var/lib/fieldlink-connector", "/var/lib/arwc-connector",
            "/run/arwc-tls/server.crt", "/run/arwc-tls/server.key", "/run/arwc-tls/ca.crt",
            "/run/arwc-peer/keplerops-ca.crt",
        }),
        forbidden_paths=COMMON_ABSENT + (
            "/usr/local/sbin/arwc-connector-entrypoint", "/opt/customer-handover",
            "/opt/customer-handover/assets/pl-arwc-plan-method-01-method.md",
            "/opt/customer-handover/customer_handover.py",
            "/opt/fieldlink-connector/fieldlink_consumer.py", "/var/lib/arwc-connector",
            "/var/lib/arwc-business", "/var/lib/arwc-data", "/var/lib/arwc-archive",
            "/var/lib/arwc-identity", "/run/arwc-tls/server.key", "/tmp/arwc-server.key",
        ),
        absent_paths=COMMON_ABSENT,
    ),
}


BOUNDARY_BOOTSTRAP = r'''
import grp
import json
import os
import pathlib
import pwd
import re
import shutil
import subprocess
import sys
import unittest

RESULT_PREFIX = "CINDER_BOUNDARY_RESULT "
configuration = json.loads(sys.argv[1])
selected = json.loads(sys.argv[2])
source = sys.stdin.read()

identity = {
    "user": pwd.getpwuid(os.geteuid()).pw_name,
    "uid": os.geteuid(),
    "gid": os.getegid(),
    "groups": sorted({grp.getgrgid(value).gr_name for value in os.getgroups()}),
    "home": os.environ.get("HOME", ""),
    "workdir": os.getcwd(),
}
violations = []
for key in ("user", "uid", "gid", "home", "workdir"):
    if identity[key] != configuration[key]:
        violations.append(f"identity.{key}={identity[key]!r}, expected {configuration[key]!r}")
if identity["uid"] == 0:
    violations.append("participant process is root")
if identity["groups"] != configuration["groups"]:
    violations.append(f"identity.groups={identity['groups']!r}, expected {configuration['groups']!r}")

status = pathlib.Path("/proc/self/status").read_text()
capability = re.search(r"^CapEff:\s*([0-9a-fA-F]+)$", status, re.MULTILINE)
no_new_privs = re.search(r"^NoNewPrivs:\s*([01])$", status, re.MULTILINE)
capability_value = int(capability.group(1), 16) if capability else -1
no_new_privs_value = int(no_new_privs.group(1)) if no_new_privs else -1
if capability_value != 0:
    violations.append(f"effective Linux capabilities are {capability_value:#x}, expected 0")
if no_new_privs_value != 1:
    violations.append("no-new-privileges is not active")

readable = [path for path in configuration["forbidden_paths"] if os.access(path, os.R_OK)]
visible = [path for path in configuration["absent_paths"] if os.path.lexists(path)]
if readable:
    violations.append("private paths are readable: " + ", ".join(readable))
if visible:
    violations.append("operator paths are visible: " + ", ".join(visible))

allowed_cinder_environment = {
    "CINDER_PARTICIPANT_BOUNDARY", "CINDER_CROSS_SEGMENT", "CINDER_ACCEPTANCE_TRACE",
}
suspicious_environment = sorted(
    name for name in os.environ
    if (
        name.startswith(("AWS_", "AZURE_", "GOOGLE_", "GITHUB_", "GH_", "CI_"))
        or any(part in name.upper() for part in ("OPERATOR", "ADMIN_TOKEN", "DOCKER_HOST"))
    ) and name not in allowed_cinder_environment
)
if suspicious_environment:
    violations.append("operator environment names are present: " + ", ".join(suspicious_environment))

controls = {
    "effective_capabilities": capability_value,
    "no_new_privileges": no_new_privs_value == 1,
    "docker_socket_visible": os.path.lexists("/var/run/docker.sock"),
    "docker_socket_readable": os.access("/var/run/docker.sock", os.R_OK | os.W_OK),
    "operator_paths_visible": visible,
    "private_paths_readable": readable,
    "suspicious_environment_names": suspicious_environment,
}

transition = None
expected_transition = configuration.get("expected_transition")
if configuration["phase"] == "arwc":
    transition_path = pathlib.Path("/var/lib/fieldlink-connector/handover/customer-transition.json")
    if expected_transition:
        try:
            supplied = json.loads(transition_path.read_text())
            route = supplied.get("delivery_route")
            receipt = str(supplied.get("delivery_receipt", ""))
            if route != expected_transition:
                violations.append(f"transition route is {route!r}, expected {expected_transition!r}")
            if not receipt or "SEED" in receipt.upper():
                violations.append("transition receipt is missing or operator-seeded")
            transition = {
                "delivery_route": route,
                "delivery_receipt_sha256": __import__("hashlib").sha256(receipt.encode()).hexdigest(),
            }
        except (OSError, ValueError) as error:
            violations.append(f"transition evidence is unavailable: {type(error).__name__}")

if violations:
    print(RESULT_PREFIX + json.dumps({
        "status": "boundary_failed", "identity": identity, "controls": controls,
        "transition": transition, "violations": violations,
        "tests_run": 0, "failures": 0, "errors": 0, "skipped": 0,
    }, sort_keys=True, separators=(",", ":")), flush=True)
    raise SystemExit(86)

real_popen = subprocess.Popen
blocked_programs = {"docker", "podman", "sudo", "nsenter", "ctr", "runc"}
blocked_paths = ("/opt/operator-tests", "/opt/cinder-typhoon", "/var/run/docker.sock")

def guarded_popen(arguments, *args, **kwargs):
    if kwargs.get("shell"):
        raise PermissionError("shell=True is not permitted by participant acceptance")
    if isinstance(arguments, (str, bytes)):
        raise PermissionError("string subprocess commands are not permitted")
    command = [os.fsdecode(value) for value in arguments]
    program = os.path.basename(command[0]) if command else ""
    joined = " ".join(command)
    if program in blocked_programs or any(path in joined for path in blocked_paths):
        raise PermissionError(f"operator control is unavailable from the participant boundary: {program}")
    if program in {"sh", "bash"} and "-c" in command:
        script = command[command.index("-c") + 1]
        if re.search(r"(^|[;&|()\s])(docker|podman|sudo|nsenter|ctr|runc)([;&|()\s]|$)", script):
            raise PermissionError("operator control in a shell command is not permitted")
    return real_popen(arguments, *args, **kwargs)

subprocess.Popen = guarded_popen
namespace = {"__name__": "__cinder_known_solution__", "__file__": "<operator-stream>"}

class EvidenceResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.completed_subtests = []
        self.failed_subtests = []
        self.skipped_assertions = []

    def addSubTest(self, test, subtest, error):
        name = test._testMethodName + " " + subtest._subDescription()
        (self.completed_subtests if error is None else self.failed_subtests).append(name)
        super().addSubTest(test, subtest, error)

    def addSkip(self, test, reason):
        self.skipped_assertions.append(getattr(test, "_testMethodName", str(test)))
        super().addSkip(test, reason)

try:
    exec(compile(source, "<operator-stream>", "exec"), namespace)
    case = namespace[configuration["class_name"]]
    suite = unittest.TestSuite()
    for method in selected:
        suite.addTest(case(method))
    result = unittest.TextTestRunner(verbosity=2, resultclass=EvidenceResult).run(suite)
    successful = result.wasSuccessful() and (configuration["allow_skips"] or not result.skipped)
    status_name = "passed" if successful else "failed"
    payload = {
        "status": status_name, "identity": identity, "controls": controls,
        "transition": transition, "violations": [],
        "tests_run": result.testsRun, "failures": len(result.failures),
        "errors": len(result.errors), "skipped": len(result.skipped),
        "skips_allowed": configuration["allow_skips"],
        "completion_evidence": {
            "passed_subtests": result.completed_subtests,
            "failed_subtests": result.failed_subtests,
            "skipped_assertions": result.skipped_assertions,
        },
    }
    print(RESULT_PREFIX + json.dumps(payload, sort_keys=True, separators=(",", ":")), flush=True)
    raise SystemExit(0 if successful else 1)
except SystemExit:
    raise
except BaseException as error:
    print(RESULT_PREFIX + json.dumps({
        "status": "runner_failed", "identity": identity, "controls": controls,
        "transition": transition, "violations": [type(error).__name__],
        "tests_run": 0, "failures": 0, "errors": 1, "skipped": 0,
    }, sort_keys=True, separators=(",", ":")), flush=True)
    raise SystemExit(87)
'''


class RunnerError(ValueError):
    """A runner input or participant-boundary invariant is invalid."""


def suite_methods(phase_name: str) -> list[str]:
    phase = PHASES[phase_name]
    tree = ast.parse(phase.suite.read_text(encoding="utf-8"), filename=str(phase.suite))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == phase.class_name:
            methods = [
                item.name for item in node.body
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                and item.name.startswith("test_")
            ]
            return sorted(methods, key=lambda name: method_order(phase_name, name))
    raise RunnerError(f"acceptance class not found: {phase.class_name}")


def method_order(phase_name: str, method: str) -> tuple[int, int]:
    if phase_name == "training":
        match = re.match(r"test_(\d+)_", method)
        return (int(match.group(1)), 0) if match else (999, 0)
    prefix = "k" if phase_name == "keplerops" else "w"
    match = re.match(rf"test_{prefix}(\d+)([ab]?)_", method)
    if not match:
        return (999, 0)
    suffix = {"": 0, "a": 1, "b": 2}[match.group(2)]
    return int(match.group(1)), suffix


def operations(phase_name: str) -> dict[str, list[str]]:
    methods = suite_methods(phase_name)
    result: dict[str, list[str]] = {"all": methods}
    if phase_name == "training":
        for index, method in enumerate(methods):
            result[f"t{method_order(phase_name, method)[0]:02d}"] = methods[:index + 1]
        return result
    if phase_name == "arwc":
        for index, method in enumerate(methods):
            result[f"w{method_order(phase_name, method)[0]:02d}"] = methods[:index + 1]
        result["ending"] = methods
        return result

    release = "test_k29_release_lineage"
    diagnostic = "test_k29a_diagnostic_delivery"
    package = "test_k29b_connector_delivery"
    before_delivery = [method for method in methods if method_order(phase_name, method)[0] < 29]
    after_delivery = [method for method in methods if method_order(phase_name, method)[0] > 29]
    for method in before_delivery:
        index = before_delivery.index(method)
        result[f"k{method_order(phase_name, method)[0]:02d}"] = before_delivery[:index + 1]
    result["release-lineage"] = before_delivery + [release]
    result["delivery-diagnostic"] = before_delivery + [diagnostic] + after_delivery
    result["delivery-package"] = before_delivery + [release, package] + after_delivery
    for number in (30, 31):
        target = next(method for method in methods if method_order(phase_name, method)[0] == number)
        result[f"k{number}"] = methods[:methods.index(target) + 1]
    return result


def validate_candidate(path: Path, phase_name: str, cross_segment: bool) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RunnerError(f"candidate manifest cannot be read: {error}") from error
    required = {
        "schema_version", "candidate_id", "immutable", "source_commit",
        "challenge_delivery", "hint_delivery", "artifact_digests", "deployments",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise RunnerError(f"candidate manifest fields must be exactly {sorted(required)}")
    if value["schema_version"] != 2 or value["immutable"] is not True:
        raise RunnerError("candidate manifest must declare schema_version 2 and immutable true")
    if not isinstance(value["candidate_id"], str) or not SAFE_ID.fullmatch(value["candidate_id"]):
        raise RunnerError("candidate_id is invalid")
    if not isinstance(value["source_commit"], str) or not re.fullmatch(r"[0-9a-f]{40}", value["source_commit"]):
        raise RunnerError("source_commit must be a full lowercase Git commit")
    try:
        expected_delivery = delivery_catalog.catalog_metadata()
    except ValueError as error:
        raise RunnerError(f"canonical challenge delivery is invalid: {error}") from error
    if value["challenge_delivery"] != expected_delivery:
        raise RunnerError("candidate challenge delivery does not match the canonical catalog")
    try:
        expected_hint_delivery = delivery_catalog.hint_manifest_metadata()
    except ValueError as error:
        raise RunnerError(f"canonical hint delivery is invalid: {error}") from error
    if value["hint_delivery"] != expected_hint_delivery:
        raise RunnerError("candidate hint delivery does not match the versioned hint manifest")
    digests = value["artifact_digests"]
    if not isinstance(digests, dict) or not digests:
        raise RunnerError("artifact_digests must be a non-empty object")
    for name, digest in digests.items():
        if not isinstance(name, str) or not SAFE_ID.fullmatch(name) or not isinstance(digest, str) or not SHA256.fullmatch(digest):
            raise RunnerError("artifact_digests contains an invalid name or digest")
    deployments = value["deployments"]
    required_phases = {phase_name} | ({"arwc"} if phase_name == "keplerops" and cross_segment else set())
    if not isinstance(deployments, dict) or not required_phases.issubset(deployments):
        raise RunnerError(f"candidate deployments must include {sorted(required_phases)}")
    for name, deployment in deployments.items():
        if name not in PHASES or not isinstance(deployment, dict) or set(deployment) != {
            "project", "zone", "instance", "participant_image_digest",
        }:
            raise RunnerError("candidate deployment is invalid")
        if not all(
            isinstance(deployment[key], str) and SAFE_ID.fullmatch(deployment[key])
            for key in ("project", "zone", "instance")
        ):
            raise RunnerError("candidate deployment identifiers are invalid")
        if not isinstance(deployment["participant_image_digest"], str) or not SHA256.fullmatch(
            deployment["participant_image_digest"]
        ):
            raise RunnerError("candidate participant image digest is invalid")
        if deployment["participant_image_digest"] not in digests.values():
            raise RunnerError("candidate participant image digest is absent from artifact_digests")
    raw = path.read_bytes()
    return {
        "candidate_id": value["candidate_id"], "immutable": True,
        "source_commit": value["source_commit"],
        "manifest_sha256": hashlib.sha256(raw).hexdigest(),
        "challenge_delivery": expected_delivery,
        "hint_delivery": expected_hint_delivery,
        "artifact_digests": dict(sorted(digests.items())),
        "deployments": {name: deployments[name] for name in sorted(deployments)},
    }


def inspect_container(phase: Phase) -> dict[str, Any]:
    def inspect(template: str) -> Any:
        completed = subprocess.run(
            ["docker", "inspect", "--format", template, phase.container],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        if completed.returncode:
            raise RunnerError(f"cannot inspect participant container {phase.container}")
        return json.loads(completed.stdout)

    networks = frozenset(inspect("{{json .NetworkSettings.Networks}}"))
    if networks != phase.expected_networks:
        raise RunnerError(
            f"participant networks are {sorted(networks)}, expected {sorted(phase.expected_networks)}"
        )
    mounts = inspect("{{json .Mounts}}")
    image_id = inspect("{{json .Image}}")
    destinations = frozenset(item["Destination"] for item in mounts)
    if destinations != phase.allowed_mounts:
        raise RunnerError(
            f"participant mount destinations are {sorted(destinations)}, expected {sorted(phase.allowed_mounts)}"
        )
    if any(item["Destination"] == "/var/run/docker.sock" for item in mounts):
        raise RunnerError("participant container has Docker control mounted")
    return {
        "container": phase.container,
        "participant_image_digest": image_id,
        "networks": sorted(networks),
        "mounts": [
            {
                "destination": item["Destination"], "type": item["Type"],
                "read_write": bool(item["RW"]),
            }
            for item in sorted(mounts, key=lambda item: item["Destination"])
        ],
    }


def gce_identity() -> dict[str, str]:
    """Read authoritative host identity without exposing it to the participant."""
    root = "http://metadata.google.internal/computeMetadata/v1/"
    headers = {"Metadata-Flavor": "Google"}
    opener = build_opener(ProxyHandler({}))

    def read(path: str) -> str:
        try:
            with opener.open(Request(root + path, headers=headers), timeout=2) as response:
                return response.read().decode().strip()
        except OSError as error:
            raise RunnerError("candidate mode requires GCE metadata identity") from error

    return {
        "project": read("project/project-id"),
        "zone": read("instance/zone").rsplit("/", 1)[-1],
        "instance": read("instance/name"),
    }


def verify_candidate_runtime(
    candidate: dict[str, Any], phase_name: str, host: dict[str, str], container: dict[str, Any],
) -> None:
    expected = candidate["deployments"][phase_name]
    for key in ("project", "zone", "instance"):
        if host[key] != expected[key]:
            raise RunnerError(
                f"runtime {key} is {host[key]!r}, candidate declares {expected[key]!r}"
            )
    if container["participant_image_digest"] != expected["participant_image_digest"]:
        raise RunnerError("running participant image does not match the candidate digest")


def boundary_configuration(
    phase_name: str, expected_transition: str | None, *, allow_skips: bool = False,
) -> dict[str, Any]:
    phase = PHASES[phase_name]
    return {
        "phase": phase_name, "class_name": phase.class_name,
        "user": phase.user, "uid": phase.uid, "gid": phase.gid,
        "groups": [phase.user], "home": phase.home, "workdir": phase.home,
        "forbidden_paths": list(phase.forbidden_paths),
        "absent_paths": list(phase.absent_paths),
        "expected_transition": expected_transition,
        "allow_skips": allow_skips,
    }


def launch_command(
    phase_name: str, selected: list[str], *, cross_segment: bool,
    expected_transition: str | None, allow_skips: bool = False,
) -> list[str]:
    phase = PHASES[phase_name]
    command = [
        "docker", "exec", "-i", "--user", phase.user, "--workdir", phase.home,
        "--env", f"HOME={phase.home}",
        "--env", "CINDER_PARTICIPANT_BOUNDARY=1",
        "--env", "CINDER_ACCEPTANCE_TRACE=1",
    ]
    if cross_segment:
        command += ["--env", "CINDER_CROSS_SEGMENT=1"]
    command += [
        phase.container, "python3", "-c", BOUNDARY_BOOTSTRAP,
        json.dumps(
            boundary_configuration(
                phase_name, expected_transition, allow_skips=allow_skips,
            ),
            separators=(",", ":"),
        ),
        json.dumps(selected, separators=(",", ":")),
    ]
    return command


def validated_event(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("kind") not in {"http", "artifact"}:
        raise RunnerError("acceptance emitted an invalid evidence event")
    if value["kind"] == "http":
        required = {
            "kind", "method", "host", "path_sha256", "status", "response_bytes",
            "response_sha256", "elapsed_ms", "test_method",
        }
        if set(value) != required:
            raise RunnerError("HTTP evidence fields are invalid")
        if (
            not isinstance(value["method"], str)
            or not re.fullmatch(r"[A-Z]+", value["method"])
            or not isinstance(value["host"], str)
            or not isinstance(value["path_sha256"], str)
            or not re.fullmatch(r"[0-9a-f]{64}", value["path_sha256"])
            or not isinstance(value["status"], int)
            or not -1 <= value["status"] <= 599
            or not isinstance(value["response_bytes"], int)
            or value["response_bytes"] < 0
            or not isinstance(value["elapsed_ms"], int)
            or value["elapsed_ms"] < 0
        ):
            raise RunnerError("HTTP evidence values are invalid")
        if not isinstance(value["response_sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", value["response_sha256"]):
            raise RunnerError("HTTP response digest is invalid")
    else:
        required = {"kind", "source", "bytes", "sha256", "test_method"}
        if (
            set(value) != required
            or not isinstance(value["source"], str)
            or not isinstance(value["bytes"], int)
            or value["bytes"] < 0
        ):
            raise RunnerError("artifact evidence fields are invalid")
        if not isinstance(value["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", value["sha256"]):
            raise RunnerError("artifact digest is invalid")
    if not isinstance(value["test_method"], str) or not re.fullmatch(
        r"(?:test_[A-Za-z0-9_]+|setup)", value["test_method"]
    ):
        raise RunnerError("evidence test method is invalid")
    for key, item in value.items():
        if isinstance(item, str) and (len(item) > 512 or any(ord(char) < 32 for char in item)):
            raise RunnerError(f"evidence string is unsafe: {key}")
    return value


def validated_boundary(value: Any) -> dict[str, Any]:
    allowed = {
        "status", "identity", "controls", "transition", "violations",
        "tests_run", "failures", "errors", "skipped", "skips_allowed",
        "completion_evidence",
    }
    if not isinstance(value, dict) or not set(value) <= allowed:
        raise RunnerError("participant emitted an invalid boundary result")
    required = {
        "status", "identity", "controls", "transition", "violations",
        "tests_run", "failures", "errors", "skipped",
    }
    if not required <= set(value) or not isinstance(value["status"], str) or value["status"] not in {
        "passed", "failed", "boundary_failed", "runner_failed",
    }:
        raise RunnerError("participant boundary result fields are invalid")
    identity = value["identity"]
    if not isinstance(identity, dict) or set(identity) != {
        "user", "uid", "gid", "groups", "home", "workdir",
    }:
        raise RunnerError("participant identity evidence is invalid")
    controls = value["controls"]
    if not isinstance(controls, dict) or set(controls) != {
        "effective_capabilities", "no_new_privileges", "docker_socket_visible",
        "docker_socket_readable", "operator_paths_visible", "private_paths_readable",
        "suspicious_environment_names",
    }:
        raise RunnerError("participant control evidence is invalid")
    if value["transition"] is not None and (
        not isinstance(value["transition"], dict)
        or set(value["transition"]) != {"delivery_route", "delivery_receipt_sha256"}
        or not isinstance(value["transition"]["delivery_route"], str)
        or not isinstance(value["transition"]["delivery_receipt_sha256"], str)
        or not re.fullmatch(r"[0-9a-f]{64}", value["transition"]["delivery_receipt_sha256"])
    ):
        raise RunnerError("participant transition evidence is invalid")
    if not all(
        isinstance(value[name], int) and value[name] >= 0
        for name in ("tests_run", "failures", "errors", "skipped")
    ):
        raise RunnerError("participant completion counts are invalid")
    if not isinstance(value["violations"], list) or not all(
        isinstance(item, str) for item in value["violations"]
    ):
        raise RunnerError("participant violations are invalid")
    completion = value.get("completion_evidence")
    if completion is not None and (
        not isinstance(completion, dict)
        or set(completion) != {"passed_subtests", "failed_subtests", "skipped_assertions"}
        or not all(
            isinstance(items, list) and all(isinstance(item, str) for item in items)
            for items in completion.values()
        )
    ):
        raise RunnerError("participant completion evidence is invalid")
    for item in json.dumps(value, sort_keys=True):
        if ord(item) < 32 and item not in "\t\n\r":
            raise RunnerError("participant boundary evidence contains a control character")
    if len(json.dumps(value)) > 200_000:
        raise RunnerError("participant boundary evidence is unexpectedly large")
    return value


def parse_output(stdout: str) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    events: list[dict[str, Any]] = []
    boundary = None
    for line in stdout.splitlines():
        if line.startswith(EVENT_PREFIX):
            events.append(validated_event(json.loads(line.removeprefix(EVENT_PREFIX))))
        elif line.startswith(RESULT_PREFIX):
            boundary = validated_boundary(json.loads(line.removeprefix(RESULT_PREFIX)))
    return events, boundary


def write_report(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(path.name + ".tmp")
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    os.fchmod(descriptor, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        output.write(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", required=True, choices=sorted(PHASES))
    parser.add_argument("--operation", default="all")
    parser.add_argument("--list-operations", action="store_true")
    parser.add_argument("--reset-identity")
    parser.add_argument("--report", type=Path)
    candidate = parser.add_mutually_exclusive_group()
    candidate.add_argument("--candidate", type=Path)
    candidate.add_argument("--development", action="store_true")
    parser.add_argument("--cross-segment", action="store_true")
    parser.add_argument(
        "--expected-transition", choices=("diagnostic-execution", "package-activation"),
        help="ARWC candidate handover route earned before this run",
    )
    arguments = parser.parse_args()

    available = operations(arguments.phase)
    if arguments.list_operations:
        for name in available:
            print(name)
        return 0
    if arguments.operation not in available:
        parser.error(f"unknown operation {arguments.operation!r}; choose from {', '.join(available)}")
    if not arguments.reset_identity or not SAFE_ID.fullmatch(arguments.reset_identity):
        parser.error("--reset-identity is required and must be an opaque safe identifier")
    if arguments.report is None:
        parser.error("--report is required")
    if not arguments.candidate and not arguments.development:
        parser.error("one of --candidate or --development is required")
    if arguments.phase != "keplerops" and arguments.cross_segment:
        parser.error("--cross-segment applies only to KeplerOps")
    if arguments.phase != "arwc" and arguments.expected_transition:
        parser.error("--expected-transition applies only to ARWC")
    if arguments.candidate and arguments.phase == "keplerops" and arguments.operation in {
        "all", "delivery-diagnostic", "delivery-package",
    } and not arguments.cross_segment:
        parser.error("candidate delivery acceptance requires --cross-segment")
    if arguments.candidate and arguments.phase == "arwc" and not arguments.expected_transition:
        parser.error("ARWC candidate acceptance requires --expected-transition")

    started_wall = datetime.now(timezone.utc)
    started = time.monotonic()
    selected = available[arguments.operation]
    candidate_error = None
    try:
        candidate_evidence = (
            validate_candidate(arguments.candidate, arguments.phase, arguments.cross_segment)
            if arguments.candidate else {
                "candidate_id": "development-mutable", "immutable": False,
                "source_commit": None, "manifest_sha256": None,
                "challenge_delivery": delivery_catalog.catalog_metadata(),
                "hint_delivery": delivery_catalog.hint_manifest_metadata(),
                "artifact_digests": {}, "deployments": {},
            }
        )
    except RunnerError as error:
        candidate_error = str(error)
        candidate_evidence = {
            "candidate_id": "invalid", "immutable": False,
            "source_commit": None, "manifest_sha256": None,
            "challenge_delivery": None,
            "hint_delivery": None,
            "artifact_digests": {}, "deployments": {},
        }
    report: dict[str, Any] = {
        "schema_version": 1,
        "report_kind": "participant-boundary-known-solution",
        "phase": arguments.phase,
        "operation": arguments.operation,
        "selected_assertions": selected,
        "reset_identity": arguments.reset_identity,
        "candidate": candidate_evidence,
        "started_at": started_wall.isoformat(),
        "cross_segment": arguments.cross_segment,
        "expected_transition": arguments.expected_transition,
    }
    exit_code = 1
    try:
        if candidate_error:
            raise RunnerError(candidate_error)
        report["container_boundary"] = inspect_container(PHASES[arguments.phase])
        if arguments.candidate:
            report["host_identity"] = gce_identity()
            verify_candidate_runtime(
                candidate_evidence, arguments.phase,
                report["host_identity"], report["container_boundary"],
            )
        source = PHASES[arguments.phase].suite.read_text(encoding="utf-8")
        completed = subprocess.run(
            launch_command(
                arguments.phase, selected, cross_segment=arguments.cross_segment,
                expected_transition=arguments.expected_transition,
                allow_skips=(
                    arguments.development and arguments.phase == "keplerops"
                    and not arguments.cross_segment
                ),
            ),
            input=source, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        events, boundary = parse_output(completed.stdout)
        events, provenance = attach_runtime_provenance(
            arguments.phase, events, selected,
        )
        report["boundary"] = boundary
        report["evidence"] = {
            "events": events,
            "event_count": len(events),
            "provenance": provenance,
            "stdout_bytes": len(completed.stdout.encode()),
            "stdout_sha256": hashlib.sha256(completed.stdout.encode()).hexdigest(),
            "stderr_bytes": len(completed.stderr.encode()),
            "stderr_sha256": hashlib.sha256(completed.stderr.encode()).hexdigest(),
        }
        passed = (
            completed.returncode == 0 and boundary is not None
            and boundary.get("status") == "passed"
        )
        report["result"] = "passed" if passed else "failed"
        if not passed and boundary is None:
            report["failure"] = "participant process returned no boundary result"
        exit_code = 0 if passed else 1
    except (RunnerError, ProvenanceError, OSError, json.JSONDecodeError) as error:
        report["result"] = "failed"
        report["failure"] = str(error)
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    report["elapsed_seconds"] = round(time.monotonic() - started, 3)
    write_report(arguments.report, report)
    print(
        f"{report['result'].upper()}: {arguments.phase} {arguments.operation}; "
        f"report={arguments.report}; elapsed={report['elapsed_seconds']}s"
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
