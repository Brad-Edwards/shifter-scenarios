from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
FOURTH_WALL = ROOT / "build" / "fourth-wall"
sys.path.insert(0, str(FOURTH_WALL))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


policy_module = load_module("cinder_fourth_wall_policy", FOURTH_WALL / "policy.py")
scan = load_module("cinder_fourth_wall_scan", FOURTH_WALL / "scan.py")
observer = load_module("cinder_fourth_wall_observer", FOURTH_WALL / "observe.py")
runner = load_module("cinder_fourth_wall_runner", FOURTH_WALL / "run.py")


class FourthWallPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = policy_module.build_policy()

    def test_policy_contains_all_card_ids_and_normalized_titles(self) -> None:
        aliases = self.policy["card_aliases"]
        self.assertEqual(len(aliases), 240)
        self.assertEqual(len({item["card_id"] for item in aliases}), 240)
        self.assertTrue(all(item["title_slug"] for item in aliases))
        self.assertRegex(self.policy["policy_sha256"], r"^[0-9a-f]{64}$")

    def test_title_and_card_id_routes_are_rejected(self) -> None:
        title = scan.scan_value(
            self.policy, source_kind="route", location="test",
            value="/api/the-expensive-hour",
        )
        self.assertTrue(any(
            item["rule_id"] == "card-title-alias" and item["card_id"] == "W33.2"
            for item in title
        ))
        identifier = scan.scan_value(
            self.policy, source_kind="route", location="test", value="/api/w33",
        )
        self.assertTrue(any(item["rule_id"] == "card-id-alias" for item in identifier))

    def test_decorated_title_aliases_are_rejected_on_named_surfaces(self) -> None:
        for source_kind, value in (
            ("operation", "get_the_expensive_hour_result"),
            ("filename", "customer-the-expensive-hour-export.json"),
            ("magic", "prefix-the-expensive-hour-suffix"),
        ):
            with self.subTest(source_kind=source_kind):
                findings = scan.scan_value(
                    self.policy, source_kind=source_kind, location="test", value=value,
                )
                self.assertTrue(any(
                    item["rule_id"] == "card-title-alias"
                    and item["card_id"] == "W33.2"
                    for item in findings
                ))

    def test_resource_route_does_not_match_a_card_alias(self) -> None:
        findings = scan.scan_value(
            self.policy, source_kind="route", location="test",
            value="/api/distribution/schedules/current",
        )
        self.assertFalse(any(item["rule_id"].startswith("card-") for item in findings))

    def test_explicit_meta_language_and_dependency_oracles_are_rejected(self) -> None:
        value = "Challenge handler: complete the missing prerequisite step for the expected answer."
        findings = scan.scan_value(
            self.policy, source_kind="error", location="test", value=value,
        )
        rules = {item["rule_id"] for item in findings}
        self.assertIn("meta-challenge", rules)
        self.assertIn("meta-expected-answer", rules)
        self.assertIn("dependency-oracle", rules)

    def test_identifier_spelling_does_not_evade_meta_language_rules(self) -> None:
        value = (
            "ctf_flag challenge_handler integration_test fixture_only "
            "expected_answer author_contract"
        )
        rules = {
            item["rule_id"] for item in scan.scan_value(
                self.policy, source_kind="operation", location="test", value=value,
            )
        }
        self.assertTrue({
            "meta-ctf", "meta-flag", "meta-challenge", "meta-integration-test",
            "meta-fixture-only", "meta-expected-answer", "meta-author-contract",
        }.issubset(rules))

    def test_runtime_error_fields_are_classified_as_errors(self) -> None:
        tree = ast.parse('response = {"error": "Complete step 3 first"}')
        parents = {
            child: parent
            for parent in ast.walk(tree)
            for child in ast.iter_child_nodes(parent)
        }
        node = next(
            item for item in ast.walk(tree)
            if isinstance(item, ast.Constant) and item.value == "Complete step 3 first"
        )
        source_kind = scan.classify_runtime_literal(
            node.value, node=node, parent=parents[node],
        )
        self.assertEqual(source_kind, "error")
        findings = scan.scan_value(
            self.policy, source_kind=source_kind, location="test", value=node.value,
        )
        self.assertTrue(any(item["rule_id"] == "dependency-oracle" for item in findings))

    def test_static_and_live_detectors_agree(self) -> None:
        arguments = {
            "source_kind": "route", "location": "test",
            "value": "/api/the-expensive-hour",
        }
        self.assertEqual(
            scan.scan_value(self.policy, **arguments),
            observer.scan_value(self.policy, **arguments),
        )

    def test_live_probe_is_confined_to_exact_reviewed_origins(self) -> None:
        allowed = {("https", "packages.keplerops.test", 443)}
        self.assertEqual(
            observer.safe_probe_url("https://packages.keplerops.test/api", allowed),
            "https://packages.keplerops.test/api",
        )
        self.assertIsNone(observer.safe_probe_url("https://example.com/api", allowed))
        self.assertIsNone(observer.safe_probe_url(
            "https://packages.keplerops.test:9443/api", allowed,
        ))
        self.assertIsNone(observer.safe_probe_url(
            "https://user:password@packages.keplerops.test/api", allowed,
        ))
        location = observer.probe_location(
            "https://packages.keplerops.test/api/private-token-value", 403,
        )
        self.assertNotIn("private-token-value", location)

    def test_live_probe_reports_response_truncation(self) -> None:
        response = mock.MagicMock()
        response.status = 200
        response.headers.items.return_value = []
        response.read.return_value = b"x" * 11
        context = mock.MagicMock()
        context.__enter__.return_value = response
        opener = mock.MagicMock()
        opener.open.return_value = context
        with mock.patch.object(observer, "build_opener", return_value=opener):
            _, errors, truncated = observer.probe(
                self.policy, "http://workbench.training/api",
                max_bytes=10, tls_ca=None,
            )
        self.assertEqual(errors, 0)
        self.assertEqual(truncated, 1)

    def test_report_findings_do_not_copy_surrounding_content(self) -> None:
        findings = scan.scan_value(
            self.policy, source_kind="response", location="test",
            value="expected answer TOP-SECRET-MATERIAL",
        )
        serialized = json.dumps(findings)
        self.assertIn("expected answer", serialized)
        self.assertNotIn("TOP-SECRET-MATERIAL", serialized)

    def test_binary_browser_state_is_scanned_for_routes_and_titles(self) -> None:
        binary = b"SQLite format 3\x00junk\x00https://planner.test/api/the-expensive-hour\x00"
        text = observer.text_from_bytes(binary, extract_sqlite=True)
        self.assertIsNotNone(text)
        findings, _ = observer.scan_text(
            self.policy, source_kind="participant_file", location="History", value=text,
        )
        self.assertTrue(any(
            item["rule_id"] == "card-title-alias" and item["card_id"] == "W33.2"
            for item in findings
        ))


class AllowlistTests(unittest.TestCase):
    def test_allowlist_requires_an_exact_location_rule_match_and_content_hash(self) -> None:
        policy = policy_module.build_policy()
        item = scan.scan_value(
            policy, source_kind="response", location="service.test/api",
            value="expected answer",
        )[0]
        entry = {
            "id": "reviewed-staff-training-language",
            "source_kind": item["source_kind"],
            "location": item["location"],
            "rule_id": item["rule_id"],
            "match": item["match"],
            "content_sha256": item["content_sha256"],
            "rationale": "A reviewed internal teaching record uses this phrase in world.",
        }
        unresolved, allowed = scan.apply_allowlist(
            [item], {"schema_version": 1, "entries": [entry]},
        )
        self.assertFalse(unresolved)
        self.assertEqual(allowed[0]["allowlist_id"], entry["id"])

        changed = dict(item, content_sha256="0" * 64)
        unresolved, allowed = scan.apply_allowlist(
            [changed], {"schema_version": 1, "entries": [entry]},
        )
        self.assertEqual(unresolved, [changed])
        self.assertFalse(allowed)

    def test_committed_allowlist_is_exact_and_strict(self) -> None:
        value = scan.load_allowlist()
        self.assertEqual(value["schema_version"], 1)
        self.assertEqual(
            {entry["id"] for entry in value["entries"]},
            {
                "arwc-invoice-customer-acceptance",
                "training-kali-login-shell-comment",
            },
        )

    def test_structural_gates_cannot_be_allowlisted(self) -> None:
        value = json.loads((FOURTH_WALL / "domain-interfaces.json").read_text())
        value["phases"]["keplerops"] = {
            "status": "pending_review",
            "blocking_issue": 266,
            "approved_route_patterns": [],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "domain-interfaces.json"
            path.write_text(json.dumps(value))
            item = scan.domain_interface_findings("keplerops", path)[0]
        entry = {
            "id": "invalid-structural-exception",
            "source_kind": item["source_kind"],
            "location": item["location"],
            "rule_id": item["rule_id"],
            "match": item["match"],
            "content_sha256": item["content_sha256"],
            "rationale": "This must not suppress a required architecture review.",
        }
        unresolved, allowed = scan.apply_allowlist(
            [item], {"schema_version": 1, "entries": [entry]},
        )
        self.assertEqual(unresolved, [item])
        self.assertFalse(allowed)


class DomainInterfaceTests(unittest.TestCase):
    def test_keplerops_domain_interface_is_approved_and_clean(self) -> None:
        findings = scan.domain_interface_findings("keplerops")
        self.assertEqual(findings, [])

    def test_arwc_domain_interface_is_approved_and_clean(self) -> None:
        findings = scan.domain_interface_findings("arwc")
        self.assertEqual(findings, [])

    def test_domain_interfaces_name_reviewed_resource_families(self) -> None:
        value = scan.load_domain_interfaces()
        for phase in ("keplerops", "arwc"):
            with self.subTest(phase=phase):
                patterns = value["phases"][phase]["approved_route_patterns"]
                self.assertGreaterEqual(len(patterns), 2)
                self.assertFalse({
                    r"/api/.*", r"/internal/.*", r"/(?:api|internal)/.*",
                }.intersection(patterns))
                self.assertTrue(all(
                    pattern.startswith((r"/api/(?:", r"/internal/(?:", r"/api/?"))
                    for pattern in patterns
                ))

    def test_an_approved_map_rejects_arbitrary_unreviewed_aliases(self) -> None:
        value = json.loads((FOURTH_WALL / "domain-interfaces.json").read_text())
        value["phases"]["arwc"] = {
            "status": "approved",
            "blocking_issue": None,
            "approved_route_patterns": [r"/api/distribution/(?:schedules|reports)/[a-z0-9{}-]+"],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "domain-interfaces.json"
            path.write_text(json.dumps(value))
            findings = scan.domain_interface_findings("arwc", path)
        self.assertTrue(findings)
        self.assertTrue(all(
            item["rule_id"] == "domain-interface-route-unapproved"
            for item in findings
        ))
        self.assertTrue(any(
            item["match"] == "/api/schedule-windows/current" for item in findings
        ))


class StaticAndLiveContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = policy_module.build_policy()
        cls.static_reports = {
            phase: scan.build_static_report(phase)
            for phase in ("training", "keplerops", "arwc")
        }
        cls.arwc = cls.static_reports["arwc"]

    def test_current_static_reports_are_clean_without_exceptions(self) -> None:
        expected_allowlisted = {"training": 0, "keplerops": 0, "arwc": 1}
        for phase, report in self.static_reports.items():
            with self.subTest(phase=phase):
                self.assertEqual(report["overall_status"], "clean")
                self.assertEqual(report["summary"]["finding_count"], 0)
                self.assertEqual(
                    report["summary"]["allowlisted_count"],
                    expected_allowlisted[phase],
                )
                self.assertEqual(report["findings"], [])
                self.assertEqual(
                    len(report["allowlisted"]), expected_allowlisted[phase],
                )

    def test_arwc_runtime_routes_have_no_card_derived_names(self) -> None:
        findings = [
            item for item in self.arwc["findings"]
            if item["source_kind"] == "route"
            and item["rule_id"] in {"card-id-alias", "card-title-alias"}
        ]
        self.assertEqual(findings, [])

    def test_arwc_replacement_routes_are_published_for_discovery(self) -> None:
        runtime = ROOT / "build" / "arwc" / "runtime"
        process = (runtime / "process_services.py").read_text()
        integration = (runtime / "integration_gateway.py").read_text()
        business = (runtime / "business_workplace.py").read_text()
        identity = (runtime / "corporate_identity.py").read_text()
        maintenance = (runtime / "maintenance_review.py").read_text()
        self.assertIn(
            '"key": "process.signature-program-reproduction"', process,
        )
        self.assertIn(
            '"template": "PROCESS_VIEW_BASE/api/signature-programs/current/reproductions"',
            process,
        )
        self.assertIn(
            '"key": "process.reporting-checkpoint-submit"', process,
        )
        self.assertIn(
            '"template": "PROCESS_VIEW_BASE/api/reporting-checkpoints/current"',
            process,
        )
        self.assertIn(
            '"client_reference": "https://process-view.arwc.test/.well-known/arwc-client"',
            integration,
        )
        client_documents = business + identity + maintenance
        self.assertNotIn("https://identity.arwc.test", client_documents)
        self.assertIn(
            "https://corporate-identity.arwc.test/.well-known/arwc-client",
            client_documents,
        )

    def test_non_python_runtime_sources_are_scanned_and_clean(self) -> None:
        path = ROOT / "build" / "keplerops" / "runtime" / "k-dev-entrypoint.sh"
        findings = scan.scan_asset(self.policy, path, scan_names=False)
        self.assertEqual(findings, [])

    def test_observation_plan_is_bounded_and_contains_no_allowlist_rationales(self) -> None:
        plan = runner.observation_plan("keplerops", self.policy)
        serialized = json.dumps(plan)
        self.assertNotIn("allowlist", serialized)
        self.assertNotIn("rationale", serialized)
        self.assertLessEqual(plan["max_probes"], 256)
        self.assertLessEqual(plan["max_files"], 10_000)
        self.assertLessEqual(plan["max_total_bytes"], 128 * 1024 * 1024)
        self.assertTrue(plan["base_urls"])
        self.assertTrue(all(
            url.startswith(("http://", "https://")) for url in plan["base_urls"]
        ))

    def test_valid_live_observation_is_required_for_a_clean_release_form(self) -> None:
        authored = json.loads(
            (ROOT / "build" / "participant-surface" / "manifests" / "training.json").read_text()
        )
        observation = {
            "schema_version": 1,
            "report_kind": "fourth-wall-observation",
            "phase": "training",
            "policy_sha256": self.policy["policy_sha256"],
            "identity": {"uid": authored["participant"]["uid"], "unprivileged": True},
            "summary": {
                "scanned_file_count": 1,
                "scanned_byte_count": 10,
                "skipped_file_count": 0,
                "visited_file_count": 1,
                "file_limit_exceeded": 0,
                "byte_limit_exceeded": 0,
                "probed_response_count": 1,
                "probe_error_count": 0,
                "probe_limit_exceeded": 0,
                "truncated_response_count": 0,
                "finding_count": 0,
            },
            "findings": [],
        }
        static_only = runner.build_report("training", observation=None)
        observed = runner.build_report("training", observation=observation)
        self.assertEqual(static_only["observation_status"], "not_run")
        self.assertEqual(static_only["overall_status"], "unresolved")
        self.assertEqual(observed["observation_status"], "complete")

    def test_observation_failures_cannot_silently_pass(self) -> None:
        authored = json.loads(
            (ROOT / "build" / "participant-surface" / "manifests" / "training.json").read_text()
        )
        observation = {
            "schema_version": 1,
            "report_kind": "fourth-wall-observation",
            "phase": "training",
            "policy_sha256": self.policy["policy_sha256"],
            "identity": {"uid": authored["participant"]["uid"], "unprivileged": True},
            "summary": {
                "scanned_file_count": 0,
                "scanned_byte_count": 0,
                "skipped_file_count": 1,
                "visited_file_count": 10_000,
                "file_limit_exceeded": 1,
                "byte_limit_exceeded": 1,
                "probed_response_count": 0,
                "probe_error_count": 2,
                "probe_limit_exceeded": 3,
                "truncated_response_count": 4,
                "finding_count": 0,
            },
            "findings": [],
        }
        report = runner.build_report("training", observation=observation)
        rules = {item["rule_id"] for item in report["findings"]}
        self.assertIn("live-files-not-observed", rules)
        self.assertIn("live-files-skipped", rules)
        self.assertIn("live-file-limit-exceeded", rules)
        self.assertIn("live-byte-limit-exceeded", rules)
        self.assertIn("live-probe-failures", rules)
        self.assertIn("live-probe-limit-exceeded", rules)
        self.assertIn("live-responses-not-observed", rules)
        self.assertIn("live-responses-truncated", rules)

    def test_live_observer_uses_isolated_python_imports(self) -> None:
        source = (FOURTH_WALL / "run.py").read_text()
        self.assertIn('"python3", "-I", "-c", observer', source)

    def test_golden_checker_requires_a_live_clean_observation(self) -> None:
        source = (FOURTH_WALL / "check-golden.sh").read_text()
        self.assertIn("--require-clean", source)
        self.assertNotIn("--static-only", source)

    def test_operator_policy_is_not_copied_into_images(self) -> None:
        for dockerfile in (ROOT / "build").glob("**/*.Dockerfile"):
            with self.subTest(dockerfile=dockerfile.relative_to(ROOT)):
                self.assertNotIn("build/fourth-wall", dockerfile.read_text())

    def test_machine_readable_schemas_are_present(self) -> None:
        for name in ("report.schema.json", "observation.schema.json"):
            value = json.loads((FOURTH_WALL / name).read_text())
            self.assertEqual(value["$schema"], "https://json-schema.org/draft/2020-12/schema")
            self.assertIn("$id", value)


if __name__ == "__main__":
    unittest.main()
