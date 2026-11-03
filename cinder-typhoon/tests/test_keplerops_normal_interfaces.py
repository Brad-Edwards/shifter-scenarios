from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import re
import unittest
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
KNOWN_SOLUTION = ROOT / "build" / "keplerops" / "tests" / "test_known_solution_live.py"
PLATFORM_LIVE = ROOT / "build" / "keplerops" / "tests" / "test_platform_live.py"
PLATFORM_SERVICE = ROOT / "build" / "keplerops" / "runtime" / "platform_service.py"
CLOUD_API = ROOT / "build" / "keplerops" / "runtime" / "cloud_api.py"
REGISTRY = ROOT / "build" / "keplerops" / "runtime" / "registry.py"
CLIENT_DOCUMENTS = ROOT / "build" / "keplerops" / "authoring" / "client_documents.json"
OWNERSHIP = ROOT / "docs" / "design" / "keplerops-artifact-ownership.md"
CATALOG_PATH = ROOT / "challenges" / "catalog.py"
COVERAGE_PATH = ROOT / "build" / "card-coverage" / "coverage.py"
CHALLENGE_VALIDATOR = ROOT / "docs" / "design" / "validate_challenges.py"


def literal_assignments(path: Path) -> dict[str, object]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    result: dict[str, object] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        try:
            result[target.id] = ast.literal_eval(node.value)
        except (ValueError, TypeError):
            continue
    return result


def request_literals(path: Path, methods: set[str], functions: set[str]) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    result: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name not in methods:
            continue
        for call in ast.walk(node):
            if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name):
                continue
            if call.func.id not in functions:
                continue
            result.update(
                value.value
                for value in ast.walk(call)
                if isinstance(value, ast.Constant) and isinstance(value.value, str)
            )
    return result


class KeplerOpsNormalInterfaceTests(unittest.TestCase):
    def test_catalog_accepts_vale_compliant_challenge_heading(self) -> None:
        spec = importlib.util.spec_from_file_location("cinder_challenge_catalog", CATALOG_PATH)
        assert spec and spec.loader
        catalog = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(catalog)
        coverage_spec = importlib.util.spec_from_file_location("cinder_card_coverage_heading", COVERAGE_PATH)
        assert coverage_spec and coverage_spec.loader
        coverage = importlib.util.module_from_spec(coverage_spec)
        coverage_spec.loader.exec_module(coverage)
        for rendered_heading in (
            "Challenge description — player-facing",
            "Challenge description—player-facing",
        ):
            source = f"## {rendered_heading}\n\nDerived through the owning service.\n"
            self.assertEqual(
                catalog._section(source, "Challenge description — player-facing"),
                "Derived through the owning service.",
            )
            self.assertEqual(
                coverage.heading_section(source, "Challenge description — player-facing"),
                "Derived through the owning service.",
            )
        with self.assertRaisesRegex(catalog.CatalogError, "brief is missing Expected"):
            catalog._section("## Different\n\nvalue\n", "Expected")
        with self.assertRaisesRegex(coverage.CoverageError, "brief is missing section: Expected"):
            coverage.heading_section("## Different\n\nvalue\n", "Expected")
        validator_spec = importlib.util.spec_from_file_location(
            "cinder_challenge_validator", CHALLENGE_VALIDATOR,
        )
        assert validator_spec and validator_spec.loader
        validator = importlib.util.module_from_spec(validator_spec)
        validator_spec.loader.exec_module(validator)
        self.assertIn("K18.3", validator.load_briefs())

    def test_runtime_resources_own_their_request_contracts(self) -> None:
        platform = literal_assignments(PLATFORM_SERVICE)
        self.assertEqual(platform["EXPORT_DESTINATIONS"][1]["owner"], "rowan.ito")
        self.assertEqual(platform["EXPORT_PARTITION_BINDINGS"][0]["partition"], "current")
        self.assertEqual(platform["SCHEDULE_STARTUP_HOOK"][0], "/opt/fieldkest/hooks/support-marker")
        self.assertIn("{subject}", platform["CERTIFICATE_SUBJECT_FORMAT"])
        self.assertTrue(platform["ARCHIVE_DELEGATION_SPN"].startswith("HTTP/"))
        self.assertEqual(set(platform["ASSISTANT_ANSWER_REQUESTS"]), {
            "private_escalation", "attachment_guidance", "duplicate_review",
        })
        self.assertEqual(platform["COMPLETION_EXAMPLE"]["handover_id"], "HANDOVER-COMP-2841")

        cloud = literal_assignments(CLOUD_API)
        self.assertEqual(cloud["MAINTENANCE_COMMAND"][0], "maintenance-summary")
        self.assertEqual(cloud["MAINTENANCE_LABEL"], {"workload.class": "maintenance"})
        self.assertEqual(set(cloud["MAINTENANCE_ARCHIVE_HEADERS"]), {
            "workload_class", "scheduler_attestation",
        })

        registry = REGISTRY.read_text(encoding="utf-8")
        self.assertIn('"approval_request"', registry)
        self.assertIn('"rehearsal_input"', registry)

    def test_participant_boundary_requests_do_not_reintroduce_author_values(self) -> None:
        forbidden = {
            "notebooks/deploy-2026-09.json",
            "talia.mornac-review",
            "rowan.ito",
            "svc-release-admin",
            "rowan-support-sink",
            "/opt/fieldkest/hooks/support-marker",
            "SHIFT-SEP17-B",
            "StaffArchiveUser",
            "evan.calderoux@KEPLEROPS.TEST",
            "HTTP/identity.keplerops.test@KEPLEROPS.TEST",
            "fieldkest-release-2026",
            "fk-release-2026-old",
            "private-escalation",
            "compatibility-guidance",
            "accept-duplicate",
            "cred-completion-handover",
            "read_assigned_handover",
            "maintenance-summary",
            "X-Workload-Class",
            "X-Scheduler-Attestation",
        }
        known = request_literals(
            KNOWN_SOLUTION,
            {
                "test_k13_data_workspace_and_workload", "test_k14_trust_and_role",
                "test_k15_cross_account_export", "test_k16_schedule_runtime",
                "test_k17_support_recovery", "test_k18_note_and_federation",
                "test_k19_archive_delegation", "test_k21_assistant_retrieval",
                "test_k30_backup_recovery", "test_k31_maintenance",
            },
            {"curl_json", "post_json_route"},
        )
        platform = request_literals(
            PLATFORM_LIVE,
            {
                "test_02_workspace_cloud_export_and_persistence",
                "test_03_schedule_runtime_and_shift_transition",
                "test_04_support_recovery_federation_and_delegation",
                "test_05_assistant_retrieval_action_and_completion",
                "test_06_customer_history_diagnostics_recovery_and_maintenance",
            },
            {"call", "call_negotiate"},
        )
        self.assertEqual(forbidden & known, set())
        self.assertEqual(forbidden & platform, set())

    def test_known_solution_consumes_owner_response_fields(self) -> None:
        source = KNOWN_SOLUTION.read_text(encoding="utf-8")
        for field in (
            "partition_bindings", "destinations", "allowed_startup_hooks",
            "subject_format", "requests_endpoint", "delegation_spn",
            "approval_request", "rehearsal_input", "answer_requests",
            "credential_namespace", "credential_reference", "maintenance_policy",
            "archive_request",
        ):
            with self.subTest(field=field):
                self.assertIn(f'["{field}"]', source)

    def test_client_references_remain_service_interfaces_not_card_handlers(self) -> None:
        value = json.loads(CLIENT_DOCUMENTS.read_text(encoding="utf-8"))
        for host, document in value["documents"].items():
            for route in document["routes"]:
                path = urlsplit(route["template"]).path.lower()
                with self.subTest(host=host, key=route["key"]):
                    self.assertNotRegex(path, r"/(?:cards?|challenges?)(?:/|$)")
                    self.assertIsNone(re.search(r"/(?:k(?:1[3-9]|2[0-4]|3[01]))(?:[./-]|$)", path))

    def test_design_records_data_flow_and_security_invariants(self) -> None:
        design = OWNERSHIP.read_text(encoding="utf-8")
        self.assertIn("## Participant-derived interface flow", design)
        self.assertIn("flowchart LR", design)
        self.assertIn("Wrong subjects, roles, service principals, object keys", design)
        self.assertIn("No response, credential, or audit", design)


if __name__ == "__main__":
    unittest.main()
