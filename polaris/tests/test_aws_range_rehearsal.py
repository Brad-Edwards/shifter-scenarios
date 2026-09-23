"""Contracts for the event-proven Polaris AWS rehearsal."""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import yaml


PACK_ROOT = Path(__file__).resolve().parents[1]
DRIVER = PACK_ROOT / "tests" / "aws_event_rehearsal.py"
PARTICIPANT = PACK_ROOT / "tests" / "aws_event_participant.py"
TARBALL = PACK_ROOT / "build" / "build-v1.tar.gz"
SIDECAR = PACK_ROOT / "build" / "build-v1.tar.gz.sha256"
MANIFEST = PACK_ROOT / "pack.compatibility.yaml"


def _driver():
    spec = importlib.util.spec_from_file_location("polaris_live_rehearsal", DRIVER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class BuildArtifactTests(unittest.TestCase):
    def test_dns_seed_accepts_the_gcp_private_resolver(self) -> None:
        named = (PACK_ROOT / "build" / "dns" / "named.conf").read_text(encoding="utf-8")
        entrypoint = (PACK_ROOT / "build" / "dns" / "entrypoint.sh").read_text(encoding="utf-8")
        self.assertIn("forwarders { __DNS_FORWARDER__; };", named)
        self.assertIn('DNS_FORWARDER="${DNS_FORWARDER:-8.8.8.8}"', entrypoint)
        self.assertIn("DNS_FORWARDER must be an IPv4 address", entrypoint)

    def test_dc_content_seed_accepts_a_provider_dns_forwarder(self) -> None:
        seed = (PACK_ROOT / "aws-range" / "a2_setup.ps1").read_text(encoding="utf-8")
        self.assertIn('[string]$DnsForwarder = "169.254.169.253"', seed)
        self.assertIn("Set-DnsServerForwarder -IPAddress $DnsForwarder", seed)

    def test_event_tarball_matches_its_digest_and_is_safe(self) -> None:
        expected = SIDECAR.read_text(encoding="utf-8").split()[0]
        self.assertEqual(expected, hashlib.sha256(TARBALL.read_bytes()).hexdigest())
        with tarfile.open(TARBALL, "r:gz") as archive:
            names = [member.name for member in archive.getmembers()]
            self.assertIn(
                "polaris/build/docker-compose.yml",
                names,
            )
            for member in archive.getmembers():
                path = Path(member.name)
                self.assertFalse(path.is_absolute())
                self.assertNotIn("..", path.parts)
                self.assertFalse(member.isdev())
            archived_a14 = archive.extractfile(
                "polaris/build/a14/Dockerfile"
            )
            self.assertIsNotNone(archived_a14)
            self.assertEqual(
                (PACK_ROOT / "build" / "a14" / "Dockerfile").read_bytes(),
                archived_a14.read(),
            )
            for relative in ("contract_source.py", "flags/placement.yaml"):
                archived_input = archive.extractfile(
                    f"polaris/{relative}"
                )
                self.assertIsNotNone(archived_input)
                self.assertEqual(
                    (PACK_ROOT / relative).read_bytes(),
                    archived_input.read(),
                )

    def test_a14_uses_digest_pinned_kali_release(self) -> None:
        dockerfile = (PACK_ROOT / "build" / "a14" / "Dockerfile").read_text(
            encoding="utf-8"
        )
        self.assertRegex(
            dockerfile.splitlines()[0],
            r"^FROM kalilinux/kali-last-release@sha256:[0-9a-f]{64}$",
        )

    def test_bootstrap_extracts_pack_archive_and_installs_range_local_gate(self) -> None:
        bootstrap = (PACK_ROOT / "aws-range" / "user_data.sh.tpl").read_text(
            encoding="utf-8"
        )
        self.assertIn("/opt/polaris/polaris/build", bootstrap)
        self.assertIn("KALI_SPLICE_PRIVATE_KEY_B64", bootstrap)
        self.assertIn("A9_AUTHORIZED_KEY", bootstrap)
        self.assertIn("ssh ssh.socket", bootstrap)
        self.assertIn("polaris-splice-watcher.service", bootstrap)
        self.assertIn("docker network disconnect", bootstrap)
        self.assertIn("/etc/polaris-range.conf", bootstrap)
        self.assertIn('os.environ["POLARIS_SPLICE_PRIVATE_B64"]', bootstrap)
        self.assertNotIn('"""$splice_private_b64"""', bootstrap)
        self.assertIn("awscli-exe-linux-x86_64-2.27.49.zip", bootstrap)
        self.assertIn(
            "93842f724f8b76fbee05ac6a403dad603043b04eecfe3526f2035494718eb87b",
            bootstrap,
        )
        self.assertIn(
            "383ce6698cd5d5bbf958d2c8489ed75094e34a77d340404d9f32c4ae9e12baf0",
            bootstrap,
        )
        self.assertGreaterEqual(bootstrap.count("sha256sum -c -"), 2)

    def test_runtime_dependencies_and_amis_are_immutable(self) -> None:
        for dockerfile in sorted((PACK_ROOT / "build").glob("*/Dockerfile")):
            for line in dockerfile.read_text(encoding="utf-8").splitlines():
                if line.startswith("FROM "):
                    self.assertRegex(line, r"^FROM \S+@sha256:[0-9a-f]{64}(?:\s|$)")
        main = (PACK_ROOT / "aws-range" / "main.tf").read_text(encoding="utf-8")
        variables = (PACK_ROOT / "aws-range" / "variables.tf").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("most_recent", main)
        self.assertIn('default     = "ami-0dc6aa44dbcdd872e"', variables)
        self.assertIn('default     = "ami-0a309571b4f421554"', variables)
        self.assertIn('var.aws_region == "us-east-2"', variables)

    def test_a2_has_no_participant_ingress_and_bucket_requires_tls(self) -> None:
        ranges = (PACK_ROOT / "aws-range" / "ranges.tf").read_text(
            encoding="utf-8"
        )
        main = (PACK_ROOT / "aws-range" / "main.tf").read_text(encoding="utf-8")
        a2_sg = ranges[
            ranges.index('resource "aws_security_group" "a2"') :
            ranges.index('resource "aws_instance" "polaris"')
        ]
        self.assertNotIn("participant_cidr", a2_sg)
        self.assertIn(
            "vpc_security_group_ids = [aws_security_group.a2[each.key].id]",
            ranges,
        )
        self.assertIn('Sid       = "DenyInsecureTransport"', main)
        self.assertIn('"aws:SecureTransport" = "false"', main)

    def test_reset_reseals_gate_before_restarting_watcher(self) -> None:
        reset = (PACK_ROOT / "aws-range" / "reset.sh").read_text(encoding="utf-8")
        self.assertIn('scenario_root="${POLARIS_ROOT}/polaris"', reset)
        stop = reset.index("systemctl stop polaris-splice-watcher.service")
        disconnect = reset.index("docker network disconnect")
        restart = reset.index("systemctl restart polaris-splice-watcher.service")
        self.assertIn("source /etc/polaris-range.conf", reset)
        self.assertLess(stop, disconnect)
        self.assertLess(disconnect, restart)


class ParticipantSurfaceTests(unittest.TestCase):
    def test_participant_program_covers_every_flag_without_expected_values(self) -> None:
        source = PARTICIPANT.read_text(encoding="utf-8")
        placements = yaml.safe_load(
            (PACK_ROOT / "flags" / "placement.yaml").read_text(encoding="utf-8")
        )["flags"]
        recovered = set(re.findall(r'recover\(\s*"([a-z0-9-]+)"', source))
        self.assertEqual({row["flag_id"] for row in placements}, recovered)
        self.assertNotRegex(source, r"FLAG\{[A-Fa-f0-9]+\}")
        for forbidden in ("docker exec", "aws ssm", "terraform", "boto3"):
            self.assertNotIn(forbidden, source)

    def test_runner_uses_direct_participant_ssh(self) -> None:
        source = DRIVER.read_text(encoding="utf-8")
        self.assertIn('"ssh"', source)
        self.assertIn('"BatchMode=yes"', source)
        self.assertIn('"python3"', source)
        self.assertIn('"terraform",', source)
        self.assertIn("_verify_live_inventory_empty", source)
        self.assertIn("_bash_payload", source)
        self.assertIn('"StrictHostKeyChecking=yes"', source)
        self.assertNotIn('"StrictHostKeyChecking=no"', source)
        self.assertNotIn('"UserKnownHostsFile=/dev/null"', source)
        self.assertNotIn("PortalShellTransport", source)

    def test_runner_binds_the_ssm_observed_a14_host_key(self) -> None:
        rehearsal = _driver()
        executor = mock.Mock()
        executor.run_bash.return_value = SimpleNamespace(
            stdout="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITest host\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            known_hosts = rehearsal._write_participant_known_hosts(
                executor,
                "i-0123456789abcdef0",
                "192.0.2.10",
                Path(directory),
            )
            self.assertEqual(
                "192.0.2.10 ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITest\n",
                known_hosts.read_text(encoding="utf-8"),
            )
            self.assertEqual(0o600, known_hosts.stat().st_mode & 0o777)

    def test_runner_rejects_ambiguous_or_non_ed25519_host_identity(self) -> None:
        rehearsal = _driver()
        executor = mock.Mock()
        invalid_outputs = {
            "ambiguous": (
                "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITest first\n"
                "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITest second\n"
            ),
            "wrong-key-type": "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQTest\n",
        }
        with tempfile.TemporaryDirectory() as directory:
            for label, output in invalid_outputs.items():
                with self.subTest(label=label):
                    executor.run_bash.return_value = SimpleNamespace(stdout=output)
                    with self.assertRaises(rehearsal.RehearsalError):
                        rehearsal._write_participant_known_hosts(
                            executor,
                            "i-0123456789abcdef0",
                            "192.0.2.10",
                            Path(directory),
                        )

    def test_reset_proves_each_controller_and_brain_lock_state(self) -> None:
        source = PARTICIPANT.read_text(encoding="utf-8")
        for marker in (
            "TAIL_LOCKED=True",
            "LEG_LOCKED=True",
            "ARMS_LOCKED=True",
            "BRAIN_LOCKED=True",
        ):
            self.assertIn(marker, source)
        self.assertIn("OVERRIDE STATE ............ LOCKED", source)
        brain = (PACK_ROOT / "build" / "A13-brain" / "server.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("OVERRIDE_ACTIVE = False", brain)
        self.assertIn("OVERRIDE_ACTIVE = True", brain)

    def test_a5_smoketest_runs_from_the_scada_pivot(self) -> None:
        source = (PACK_ROOT / "tests" / "smoketests" / "A5-smoketest.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("docker exec a15-ops-eng", source)
        self.assertNotIn("docker exec a3-intranet", source)

    def test_participant_commands_match_live_event_services(self) -> None:
        source = PARTICIPANT.read_text(encoding="utf-8")
        self.assertIn('"@172.20.0.2"', source)
        self.assertNotIn('"@172.20.0.4"', source)
        self.assertIn('netrc=os.path.join(root,".netrc")', source)
        self.assertIn(r're.search(r"\bSN:\s*(\S+)"', source)
        self.assertIn('"dc01.boreas.local"', source)
        self.assertNotIn('"172.20.10.11"', source)
        self.assertIn('Path.home() / ".ssh" / "splice_relay"', source)
        self.assertIn('"BOREAS.LOCAL/d.kowalski:P@ssw0rd123"', source)
        self.assertIn('"BOREAS.LOCAL/svc-backup:"', source)
        self.assertIn('"/opt/tools/bin/smbclient.py"', source)
        self.assertIn('"BOREAS.LOCAL/Administrator@" + dc_ip', source)
        self.assertNotIn('"kinit"', source)
        self.assertIn('status["runaway_complete"]', source)

        zone = (PACK_ROOT / "build" / "dns" / "db.boreas.local").read_text(
            encoding="utf-8"
        )
        for service in ("_kerberos._tcp", "_kerberos._udp", "_ldap._tcp"):
            self.assertIn(service, zone)

        self.assertEqual(
            "AHS-TAIL-7741AHS-LEG-MN07AHS-ARM-AL42",
            _driver().load_contracts(PACK_ROOT).expected["bunker-controller-map"],
        )

    def test_john_output_parser_tolerates_colons_in_the_spn(self) -> None:
        tree = ast.parse(PARTICIPANT.read_text(encoding="utf-8"))
        function = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "john_password"
        )
        module = ast.fix_missing_locations(
            ast.Module(body=[function], type_ignores=[])
        )
        namespace: dict[str, object] = {}
        exec(compile(module, str(PARTICIPANT), "exec"), namespace)
        self.assertEqual(
            "Password1",
            namespace["john_password"](
                "$krb5tgs$23$*svc-backup$BOREAS.LOCAL$"
                "MSSQLSvc/fileserv.boreas.local:1433*$cipher\tPassword1\n"
            ),
        )

    def test_ssm_payload_explicitly_enters_bash(self) -> None:
        rehearsal = _driver()
        completed = subprocess.run(
            ["sh", "-c", rehearsal._bash_payload("set -euo pipefail\necho PASS")],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, completed.returncode)
        self.assertEqual("PASS", completed.stdout.strip())

    def test_runner_retains_structured_result_from_failed_checks(self) -> None:
        rehearsal = _driver()
        structured = rehearsal.RESULT_PREFIX + "{}\n"
        result = subprocess.CompletedProcess(
            args=["ssh"],
            returncode=1,
            stdout=structured,
            stderr="host-key notice",
        )
        with mock.patch.object(rehearsal.subprocess, "run", return_value=result):
            self.assertEqual(
                structured,
                rehearsal._run_participant(
                    "192.0.2.1",
                    Path("/tmp/test-key"),
                    Path("/tmp/known-hosts"),
                    "program",
                    30,
                ),
            )

    def test_report_retains_safe_participant_failure_stage(self) -> None:
        rehearsal = _driver()
        report = rehearsal.render_report(
            pack_version="0.5.0",
            started_at="2026-01-01T00:00:00Z",
            completed_at="2026-01-01T01:00:00Z",
            checks=[
                rehearsal.Check(
                    "domain-admin-secrets",
                    "FAIL",
                    "initial",
                    failure_stage="dcsync",
                )
            ],
            health="PASS",
            reset="PASS",
            teardown="PASS",
        )
        self.assertIn("failure_stage=dcsync", report)

    def test_terraform_is_standalone_and_uses_local_event_artifact(self) -> None:
        main = (PACK_ROOT / "aws-range" / "main.tf").read_text(encoding="utf-8")
        ranges = (PACK_ROOT / "aws-range" / "ranges.tf").read_text(
            encoding="utf-8"
        )
        versions = (PACK_ROOT / "aws-range" / "versions.tf").read_text(
            encoding="utf-8"
        )
        self.assertIn('resource "aws_vpc" "polaris"', main)
        self.assertIn('resource "aws_s3_object" "build"', main)
        self.assertIn("../build/build-v1.tar.gz", main)
        self.assertIn("aws_internet_gateway.polaris.id", ranges)
        self.assertIn("var.participant_cidr", ranges)
        self.assertNotIn("profile =", versions)

    def test_contracts_join_all_flags_to_walkthroughs(self) -> None:
        contracts = _driver().load_contracts(PACK_ROOT)
        self.assertEqual(set(contracts.expected), set(contracts.walkthroughs))
        self.assertGreaterEqual(len(contracts.expected), 36)

    def test_contract_loader_rejects_invalid_joins(self) -> None:
        rehearsal = _driver()

        def write_fixture(
            root: Path,
            *,
            flag_ids: list[str],
            challenge_ids: list[str],
            walkthroughs: dict[str, str],
        ) -> None:
            (root / "flags").mkdir(parents=True)
            (root / "challenges").mkdir()
            (root / "docs" / "walkthroughs").mkdir(parents=True)
            placements = [
                {"flag_id": flag_id, "value": f"VALUE-{flag_id}"}
                for flag_id in flag_ids
            ]
            challenges = [{"flag_id": flag_id} for flag_id in challenge_ids]
            (root / "flags" / "placement.yaml").write_text(
                yaml.safe_dump({"flags": placements}),
                encoding="utf-8",
            )
            (root / "challenges" / "challenges.yaml").write_text(
                yaml.safe_dump({"challenges": challenges}),
                encoding="utf-8",
            )
            for name, body in walkthroughs.items():
                (root / "docs" / "walkthroughs" / name).write_text(
                    body,
                    encoding="utf-8",
                )

        cases = {
            "broken-bijection": {
                "flag_ids": ["alpha"],
                "challenge_ids": ["beta"],
                "walkthroughs": {"flags-alpha.md": "VALUE-alpha"},
            },
            "duplicate-walkthrough-binding": {
                "flag_ids": ["alpha"],
                "challenge_ids": ["alpha"],
                "walkthroughs": {
                    "flags-alpha.md": "VALUE-alpha",
                    "flags-duplicate.md": "VALUE-alpha",
                },
            },
            "incomplete-walkthrough-coverage": {
                "flag_ids": ["alpha"],
                "challenge_ids": ["alpha"],
                "walkthroughs": {"flags-alpha.md": "unrelated content"},
            },
        }
        for label, case in cases.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                write_fixture(root, **case)
                with self.assertRaises(rehearsal.RehearsalError):
                    rehearsal.load_contracts(root)

    def test_result_parser_verifies_digests_and_complete_coverage(self) -> None:
        rehearsal = _driver()
        contracts = rehearsal.load_contracts(PACK_ROOT)
        key = b"k" * 32
        checks = [
            {
                "id": flag_id,
                "status": "PASS",
                "digest": rehearsal._digest(key, value),
                "count": 1,
            }
            for flag_id, value in contracts.expected.items()
        ]
        checks.extend(
            {
                "id": check_id,
                "status": "PASS",
                "digest": None,
                "count": 1,
            }
            for check_id in (
                "start-state-a14",
                "negative-direct-lab",
                "negative-direct-scada",
                "negative-pre-splice",
                "positive-post-blackout-splice",
            )
        )
        payload = {
            "schema": "polaris.aws-event.participant-result/v1",
            "run_id": "run-0123456789abcdef",
            "phase": "initial",
            "attempt_generation": 1,
            "checks": checks,
        }
        parsed = rehearsal.parse_participant_result(
            "POLARIS_REHEARSAL_RESULT="
            + json.dumps(payload, separators=(",", ":")),
            run_id=payload["run_id"],
            phase="initial",
            generation=1,
            key=key,
            contracts=contracts,
        )
        self.assertTrue(parsed)
        self.assertTrue(all(row.status == "PASS" for row in parsed))

        mismatched = json.loads(json.dumps(payload))
        recovery = next(
            row for row in mismatched["checks"] if row["id"] in contracts.expected
        )
        recovery["digest"] = "not-the-expected-digest"
        parsed = rehearsal.parse_participant_result(
            "POLARIS_REHEARSAL_RESULT="
            + json.dumps(mismatched, separators=(",", ":")),
            run_id=payload["run_id"],
            phase="initial",
            generation=1,
            key=key,
            contracts=contracts,
        )
        parsed_recovery = next(
            row for row in parsed if row.check_id == recovery["id"]
        )
        self.assertEqual("FAIL", parsed_recovery.status)

        incomplete = json.loads(json.dumps(payload))
        incomplete["checks"].pop()
        with self.assertRaises(rehearsal.RehearsalError):
            rehearsal.parse_participant_result(
                "POLARIS_REHEARSAL_RESULT="
                + json.dumps(incomplete, separators=(",", ":")),
                run_id=payload["run_id"],
                phase="initial",
                generation=1,
                key=key,
                contracts=contracts,
            )

    def test_report_is_redacted_and_records_lifecycle(self) -> None:
        rehearsal = _driver()
        report = rehearsal.render_report(
            pack_version="0.5.0",
            started_at="2026-01-01T00:00:00Z",
            completed_at="2026-01-01T01:00:00Z",
            checks=[rehearsal.Check("start-state-a14", "PASS", "initial")],
            health="PASS",
            reset="PASS",
            teardown="PASS",
        )
        self.assertIn("- verdict: `PASS`", report)
        self.assertNotIn("FLAG{", report)
        self.assertNotIn("instance_id", report)

    def test_report_rejects_forbidden_live_material(self) -> None:
        rehearsal = _driver()
        for forbidden in ("instance_id", "FLAG{secret}", "private_key"):
            with self.subTest(forbidden=forbidden):
                with self.assertRaises(rehearsal.RehearsalError):
                    rehearsal.render_report(
                        pack_version="0.5.0",
                        started_at="2026-01-01T00:00:00Z",
                        completed_at="2026-01-01T01:00:00Z",
                        checks=[
                            rehearsal.Check(
                                forbidden,
                                "FAIL",
                                "initial",
                            )
                        ],
                        health="PASS",
                        reset="PASS",
                        teardown="PASS",
                    )


class ManifestTests(unittest.TestCase):
    def test_aws_event_points_to_event_range_and_rehearsal(self) -> None:
        manifest = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual([], manifest["pack"]["source"]["upstream_references"])
        profile = next(
            row
            for row in manifest["runtime_profiles"]
            if row["profile_id"] == "aws_event"
        )
        build = {row["path"] for row in profile["build"]}
        tests = {row["path"] for row in profile["tests"]}
        self.assertEqual("supported", profile["status"])
        for path in (
            "aws-range/main.tf",
            "aws-range/ranges.tf",
            "aws-range/shared.tf",
            "aws-range/user_data.sh.tpl",
            "aws-range/a2_cold_bootstrap.sh",
            "aws-range/a2_setup.ps1",
            "aws-range/reset.sh",
        ):
            self.assertIn(path, build)
        self.assertNotIn("aws-range/", build)
        self.assertIn("build/build-v1.tar.gz", build)
        self.assertIn("tests/aws_event_rehearsal.py", tests)
        self.assertIn("tests/aws_event_participant.py", tests)


if __name__ == "__main__":
    unittest.main()
