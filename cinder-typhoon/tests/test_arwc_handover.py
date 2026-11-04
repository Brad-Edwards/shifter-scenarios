"""Tests for stable, authenticated ARWC pre-handoff service startup."""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "build" / "arwc" / "runtime"
IMAGES = ROOT / "build" / "arwc" / "images"
GATE = RUNTIME / "arwc_handover.py"
CLIENT_REFERENCE_TEST = ROOT / "build" / "arwc" / "tests" / "test_client_references_live.py"
SERVICES = ("data", "identity", "archive", "business", "contractors")


def load_gate():
    spec = importlib.util.spec_from_file_location("arwc_handover", GATE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


handover = load_gate()


def load_client_reference_test():
    spec = importlib.util.spec_from_file_location("arwc_client_reference_test", CLIENT_REFERENCE_TEST)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


client_references = load_client_reference_test()


def published_routes() -> dict[str, dict[str, str]]:
    routes: dict[str, dict[str, str]] = {}
    for path in RUNTIME.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=path.name)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Dict):
                continue
            try:
                value = ast.literal_eval(node)
            except (TypeError, ValueError):
                continue
            if not isinstance(value, dict) or set(value) != {"key", "method", "template"}:
                continue
            route = {key: str(item) for key, item in value.items()}
            route["template"] = route["template"].replace(
                "PROCESS_VIEW_BASE", "https://process-view.arwc.test"
            )
            routes[route["key"]] = route
    return routes


def write_material(root: Path, token: str, certificate: bytes, key: bytes) -> None:
    (root / "certificate").write_bytes(certificate)
    (root / "authentication-key").write_bytes(key)
    unsigned = handover.build_attestation(
        token.encode(),
        certificate,
        key,
        "0123456789abcdef0123456789abcdef",
        "2026-10-31T12:00:00Z",
    )
    (root / "attestation").write_text(
        json.dumps(unsigned, sort_keys=True, separators=(",", ":")) + "\n"
    )
    (root / "session").write_text(token + "\n")


class GateProcess:
    def __init__(self, root: Path):
        environment = os.environ.copy()
        environment["ARWC_HANDOVER_POLL_SECONDS"] = "0.02"
        environment["ARWC_HANDOVER_EVENT_INTERVAL_SECONDS"] = "60"
        self.process = subprocess.Popen(
            [
                sys.executable,
                str(GATE),
                "wait",
                "--service",
                "arwc-test",
                "--session",
                str(root / "session"),
                "--attestation",
                str(root / "attestation"),
                "--certificate",
                str(root / "certificate"),
                "--authentication-key",
                str(root / "authentication-key"),
                "--state",
                str(root / "state"),
                "--accepted-hash",
                str(root / "accepted-hash"),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=environment,
        )

    def stop(self) -> tuple[str, str]:
        if self.process.poll() is None:
            self.process.terminate()
        return self.process.communicate(timeout=3)


class ArwcHandoverTests(unittest.TestCase):
    def test_ending_route_contract_is_complete_and_rejects_drift(self) -> None:
        routes = published_routes()
        client_references.validate_ending_routes(routes)

        mutant = json.loads(json.dumps(routes))
        mutant["process.sealed-project"]["template"] = (
            "https://process-view.arwc.test/api/sealed-projects/current"
        )
        with self.assertRaisesRegex(AssertionError, "process.sealed-project"):
            client_references.validate_ending_routes(mutant)

    def test_ending_shared_paths_dispatch_by_request_shape(self) -> None:
        planning = (RUNTIME / "planning_data.py").read_text(encoding="utf-8")
        self.assertEqual(planning.count('path == "/api/query-runs"'), 1)
        self.assertIn('if "function" in request:', planning)

        process = (RUNTIME / "process_services.py").read_text(encoding="utf-8")
        self.assertIn('and not {\n                "operations", "image_b64"', process)
        self.assertNotIn(
            '"/api/maintenance-records/current", "/api/maintenance-records/current"',
            process,
        )

    def test_participant_estimator_is_self_contained(self) -> None:
        diagnostics = (IMAGES / "diagnostics.Dockerfile").read_text(encoding="utf-8")
        self.assertIn("g++ -std=c++20 -O2 -fno-omit-frame-pointer -static ", diagnostics)
        self.assertIn("! readelf -l /tmp/estimator23 | grep -q INTERP", diagnostics)

    def test_ending_uses_current_work_order_and_real_absent_alias(self) -> None:
        ending = (ROOT / "build" / "arwc" / "tests" / "test_known_solution_live.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('.replace("{wo_id}", "current")', ending)
        self.assertEqual(ending.count('f"{base}/api/integrity-verifier"'), 2)

    def test_engineering_utility_is_built_from_the_declared_local_stage(self) -> None:
        engineering = (IMAGES / "engineering.Dockerfile").read_text()
        self.assertIn("FROM ubuntu:24.04 AS utility-builder", engineering)
        self.assertEqual(engineering.count("COPY --from=utility-builder"), 2)

    def test_diagnostics_build_accepts_unsigned_64_bit_selector_output(self) -> None:
        diagnostics = (IMAGES / "diagnostics.Dockerfile").read_text()
        self.assertIn("grep -Eq '^[1-9][0-9]*$'", diagnostics)
        self.assertNotIn('test "$(/tmp/selector24', diagnostics)

    def test_connector_private_material_stays_out_of_participant_paths(self) -> None:
        dockerfile = (IMAGES / "connector.Dockerfile").read_text()
        entrypoint = (RUNTIME / "connector-entrypoint.sh").read_text()
        consumer = (RUNTIME / "fieldlink_consumer.py").read_text()
        self.assertIn("-m 0711", dockerfile)
        self.assertIn("/opt/customer-handover", dockerfile)
        self.assertIn("-m 0750", dockerfile)
        self.assertIn("/opt/customer-handover/assets", dockerfile)
        self.assertNotIn("/tmp/arwc-handover.key", entrypoint)
        self.assertNotIn("/tmp/arwc-handover.key", consumer)
        private_key = "/var/lib/arwc-connector/auth/handover.key"
        self.assertIn(private_key, entrypoint)
        self.assertIn(private_key, consumer)

    token = "a1" * 32
    certificate = b"range-a-certificate\n"
    key = ("ab" * 32 + "\n").encode()

    def wait_for_state(self, path: Path, expected: str) -> None:
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            if path.exists() and path.read_text() == expected + "\n":
                return
            time.sleep(0.02)
        self.fail(f"state did not become {expected}")

    def test_all_entrypoints_use_the_bookworm_posix_shell_contract(self) -> None:
        dash = shutil.which("dash")
        self.assertIsNotNone(dash, "dash is required to model Bookworm /bin/sh")
        for service in SERVICES:
            with self.subTest(service=service):
                entrypoint = RUNTIME / f"{service}-entrypoint.sh"
                source = entrypoint.read_text()
                self.assertTrue(source.startswith("#!/bin/sh\nset -eu\n"))
                self.assertNotIn("[[", source)
                self.assertIn("/usr/local/libexec/arwc-handover.py wait", source)
                syntax = subprocess.run(
                    [dash, "-n", str(entrypoint)], capture_output=True, text=True
                )
                self.assertEqual(syntax.returncode, 0, syntax.stderr)
                dockerfile = (IMAGES / f"{service}.Dockerfile").read_text()
                self.assertIn(
                    "build/arwc/runtime/arwc_handover.py /usr/local/libexec/arwc-handover.py",
                    dockerfile,
                )

    def test_compose_healthchecks_probe_the_interface_and_gate_consumers(self) -> None:
        compose = (ROOT / "build" / "arwc" / "compose.yaml").read_text()
        health_command = (
            'test: ["CMD", "python3", '
            '"/usr/local/libexec/arwc-handover.py", "health"]'
        )
        self.assertEqual(compose.count(health_command), len(SERVICES))
        self.assertNotIn("grep -qx ready /run/arwc-status/state", compose)
        self.assertEqual(
            compose.count(
                "handover.key:/run/arwc-handover/authentication.key:ro"
            ),
            len(SERVICES) + 1,
        )
        for dependency in (
            "a-identity:\n        condition: service_healthy",
            "a-archive:\n        condition: service_healthy",
            "a-contractors:\n        condition: service_healthy",
            "a-business:\n        condition: service_healthy",
        ):
            with self.subTest(dependency=dependency.split(":", 1)[0]):
                self.assertIn(dependency, compose)

    def test_health_endpoint_is_served_before_authentication(self) -> None:
        for module in ("corporate_identity.py", "planning_data.py"):
            with self.subTest(module=module):
                source = (RUNTIME / module).read_text()
                handler = source[source.index("    def do_GET(self) -> None:") :]
                self.assertLess(
                    handler.index("self._serve_client_document()"),
                    handler.index("self.corporate_authorized()")
                    if module == "corporate_identity.py"
                    else handler.index("self.authorized()"),
                )

    def test_restore_pristine_requires_the_complete_waiting_service_graph(self) -> None:
        restore = (ROOT / "build" / "arwc" / "restore-pristine.sh").read_text()
        self.assertIn("if ! docker compose -f compose.yaml up -d --force-recreate", restore)
        self.assertNotIn("nohup docker compose", restore)
        self.assertNotIn("compose_pid", restore)
        self.assertNotIn("kill -0", restore)
        self.assertIn("ARWC pristine restore failed:", restore)
        self.assertIn("pre-handoff services did not remain", restore)
        self.assertIn("service_graph_stable()", restore)
        self.assertIn("docker compose -f compose.yaml config --services", restore)
        self.assertIn("docker compose -f compose.yaml ps -a -q", restore)
        self.assertIn("complete service graph did not remain running", restore)
        self.assertIn("fieldlink edge did not publish", restore)
        self.assertIn("bash ./generate-operator-material.sh", restore)
        self.assertIn("handover_services_waiting()", restore)
        self.assertIn("&& handover_services_waiting", restore)
        self.assertIn("connector_children_healthy()", restore)
        self.assertIn("&& connector_children_healthy", restore)
        self.assertIn("connector child processes did not remain healthy", restore)
        self.assertIn("grep -qx waiting /run/arwc-status/state", restore)
        for service in SERVICES:
            self.assertIn(f"cinder-arwc-{service}", restore)

    def test_connector_health_fails_when_either_child_exits(self) -> None:
        health = RUNTIME / "connector-health.sh"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            proc = root / "proc"
            customer = root / "customer"
            fieldlink = root / "fieldlink"
            proc.mkdir()
            (customer / "audit").mkdir(parents=True)
            (fieldlink / "consumer/candidates").mkdir(parents=True)
            (customer / "audit/events.jsonl").touch()
            (customer / "audit/fieldlink-consumer.jsonl").touch()
            commands = (
                "/opt/customer-handover/customer_handover.py",
                "/opt/fieldlink-connector/fieldlink_consumer.py",
            )
            for pid, command in enumerate(commands, start=20):
                process = proc / str(pid)
                process.mkdir()
                (process / "status").write_text("PPid:\t1\nUid:\t987\t987\t987\t987\n")
                (process / "cmdline").write_bytes(
                    b"python3\0" + command.encode() + b"\0"
                )
            environment = {
                **os.environ,
                "ARWC_CONNECTOR_PROC_ROOT": str(proc),
                "ARWC_CONNECTOR_UID": "987",
                "ARWC_CONNECTOR_CUSTOMER_ROOT": str(customer),
                "ARWC_CONNECTOR_FIELDLINK_ROOT": str(fieldlink),
            }
            healthy = subprocess.run(
                ["dash", str(health)], env=environment, check=False,
            )
            self.assertEqual(healthy.returncode, 0)
            shutil.rmtree(proc / "21")
            unhealthy = subprocess.run(
                ["dash", str(health)], env=environment, check=False,
            )
            self.assertNotEqual(unhealthy.returncode, 0)

        source = health.read_text()
        self.assertNotIn(".pid", source)
        self.assertIn("/proc", source)

        live = (
            ROOT / "build" / "arwc" / "tests" / "test_handover_stability_live.py"
        ).read_text()
        self.assertIn('if status != "running"', live)
        self.assertNotIn('{"created", "missing"}', live)
        self.assertIn("wait_for_ready(container)", live)

    def test_health_and_readiness_keep_waiting_rejected_and_ready_distinct(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary) / "state"

            def probe(command: str) -> int:
                arguments = handover.parser().parse_args([
                    command,
                    "--state", str(state),
                    "--url", "https://127.0.0.1:1/.well-known/arwc-client",
                    "--timeout", "0.01",
                ])
                return arguments.handler(arguments)

            state.write_text("waiting\n")
            self.assertEqual(probe("health"), 0)
            self.assertEqual(probe("ready"), 1)

            for value in ("rejected\n", "unknown\n", "", "accepted\n"):
                with self.subTest(state=value.strip() or "empty"):
                    state.write_text(value)
                    self.assertEqual(probe("health"), 1)
                    self.assertEqual(probe("ready"), 1)

            state.unlink()
            self.assertEqual(probe("health"), 1)
            self.assertEqual(probe("ready"), 1)

    def test_no_handover_waits_without_exit_or_repeated_errors(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            process = GateProcess(root)
            self.wait_for_state(root / "state", "waiting")
            time.sleep(0.15)
            self.assertIsNone(process.process.poll())
            _, stderr = process.stop()
            self.assertEqual(stderr, "")

    def test_delayed_handover_is_accepted_and_restart_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            process = GateProcess(root)
            self.wait_for_state(root / "state", "waiting")
            write_material(root, self.token, self.certificate, self.key)
            stdout, stderr = process.process.communicate(timeout=3)
            self.assertEqual(process.process.returncode, 0, stderr)
            self.assertEqual(stdout, "")
            self.assertEqual((root / "state").read_text(), "accepted\n")
            expected_hash = hashlib.sha256(self.token.encode()).hexdigest() + "\n"
            self.assertEqual((root / "accepted-hash").read_text(), expected_hash)

            restarted = GateProcess(root)
            stdout, stderr = restarted.process.communicate(timeout=3)
            self.assertEqual(restarted.process.returncode, 0, stderr)
            self.assertEqual(stdout, "")

    def test_handover_present_before_start_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_material(root, self.token, self.certificate, self.key)
            process = GateProcess(root)
            _, stderr = process.process.communicate(timeout=3)
            self.assertEqual(process.process.returncode, 0, stderr)
            self.assertEqual((root / "state").read_text(), "accepted\n")

    def test_malformed_and_partial_handover_stays_alive_and_logs_once(self) -> None:
        for payload in (b"", b"abc\n", b"a1" * 31 + b"\n", b"a1" * 32):
            with (
                self.subTest(payload_length=len(payload)),
                tempfile.TemporaryDirectory() as temporary,
            ):
                root = Path(temporary)
                (root / "session").write_bytes(payload)
                process = GateProcess(root)
                self.wait_for_state(root / "state", "rejected")
                time.sleep(0.15)
                self.assertIsNone(process.process.poll())
                _, stderr = process.stop()
                events = [json.loads(line) for line in stderr.splitlines()]
                self.assertEqual(len(events), 1)
                self.assertEqual(events[0]["event"], "corporate_handover_rejected")
                self.assertNotIn(self.token, stderr)

    def test_cross_range_and_replayed_material_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_material(root, self.token, self.certificate, self.key)

            (root / "certificate").write_bytes(b"range-b-certificate\n")
            with self.assertRaisesRegex(
                handover.HandoverRejected, "cross_range_handover"
            ):
                handover.validate_handover(
                    root / "session",
                    root / "attestation",
                    root / "certificate",
                    root / "authentication-key",
                    root / "accepted-hash",
                )

            (root / "certificate").write_bytes(self.certificate)
            (root / "accepted-hash").write_text("f" * 64 + "\n")
            with self.assertRaisesRegex(
                handover.HandoverRejected, "replayed_handover"
            ):
                handover.validate_handover(
                    root / "session",
                    root / "attestation",
                    root / "certificate",
                    root / "authentication-key",
                    root / "accepted-hash",
                )

    def test_tampering_with_token_or_attestation_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_material(root, self.token, self.certificate, self.key)
            record = json.loads((root / "attestation").read_text())
            record["handover_id"] = "f" * 32
            (root / "attestation").write_text(json.dumps(record) + "\n")
            with self.assertRaisesRegex(
                handover.HandoverRejected, "unauthenticated_handover"
            ):
                handover.validate_handover(
                    root / "session",
                    root / "attestation",
                    root / "certificate",
                    root / "authentication-key",
                    root / "accepted-hash",
                )


if __name__ == "__main__":
    unittest.main()
