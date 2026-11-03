"""Static regressions for KeplerOps known-solution route discovery."""

from __future__ import annotations

import ast
import copy
import importlib.util
import json
import re
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEPLEROPS = ROOT / "build" / "keplerops"
SUITE = ROOT / "build" / "keplerops" / "tests" / "test_known_solution_live.py"
LEDGER = ROOT / "build" / "input-provenance" / "ledger.json"
PROVENANCE = ROOT / "build" / "input-provenance" / "provenance.py"
IMAGES = KEPLEROPS / "images"
RUNTIME = KEPLEROPS / "runtime"
AUTHOR_MAP = KEPLEROPS / "authoring" / "client_documents.json"
FRAGMENTS = RUNTIME / "client-references"
OPENING = ROOT / "assets" / "keplerops" / "opening" / "k-dev"
REQUEST_FUNCTIONS = {"curl", "curl_json", "post_json_route"}
CLASSIFIED_API_LITERALS = {
    # Parsed from participant-supplied local-helper.md, never used as an
    # author-selected request target.
    r"(http://127\.0\.0\.1:8701/api/inspection-summary)",
    r"(http://127\.0\.0\.1:8701/api/reconstruction)",
    r"at `(/api/callback/collection)`",
    # Participant repository file layout, not an HTTP route.
    "/tmp/journey-pc/api/fragment-",
}
FORBIDDEN_ACCEPTED_VALUES = {"7.4.2", "7.4.3-cinder.rowan"}
GENERIC_PROVENANCE_PHRASES = {
    "accepted response chain in",
    "prior accepted api responses",
    "normal service responses",
    "service-catalog.md",
}
STATIC_IMAGE_REFERENCES = {
    "assistant.Dockerfile": "assistant.json",
    "ci.Dockerfile": "ci.json",
    "cloud-api.Dockerfile": "cloud-api.json",
    "data.Dockerfile": "data.json",
    "identity.Dockerfile": "identity.json",
    "indexer.Dockerfile": "indexer.json",
    "preview.Dockerfile": "preview.json",
    "registry.Dockerfile": "registry.json",
    "source.Dockerfile": "source.json",
    "staff.Dockerfile": "staff.json",
    "support.Dockerfile": "support.json",
}
K04_EMPLOYEE_DISCLOSURES = {
    "FIELDKEST-SENTNL",
    "uint8_t body[32]",
    "/api/internal/release-exceptions/state",
    "/api/internal/release-exceptions/REL-EXC-2841/complete",
    "recover_exception_queue",
}
K11_BINARY = ROOT / "assets/keplerops/policy-compiler/source/fieldkest-policyc"
GENERATOR = KEPLEROPS / "generate_client_references.py"
SPEC = importlib.util.spec_from_file_location("keplerops_client_references", GENERATOR)
assert SPEC and SPEC.loader
client_references = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(client_references)


def function_name(call: ast.Call) -> str | None:
    return call.func.id if isinstance(call.func, ast.Name) else None


def direct_request_route_literals(source: str) -> list[tuple[int, str]]:
    tree = ast.parse(source)
    findings: list[tuple[int, str]] = []
    for call in (node for node in ast.walk(tree) if isinstance(node, ast.Call)):
        if function_name(call) not in REQUEST_FUNCTIONS or not call.args:
            continue
        for node in ast.walk(call.args[0]):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            if "/api/" in node.value or "fieldkest-client" in node.value:
                findings.append((node.lineno, node.value))
    return findings


def accepted_value_fallbacks(source: str) -> list[tuple[int, str]]:
    tree = ast.parse(source)
    findings: list[tuple[int, str]] = []
    for call in (node for node in ast.walk(tree) if isinstance(node, ast.Call)):
        if not isinstance(call.func, ast.Attribute):
            continue
        owner = call.func.value
        is_evidence = (
            isinstance(owner, ast.Attribute)
            and owner.attr == "evidence"
            and isinstance(owner.value, ast.Name)
            and owner.value.id in {"self", "cls"}
        )
        if is_evidence and (
            call.func.attr == "setdefault"
            or call.func.attr == "get"
            and (len(call.args) > 1 or call.keywords)
        ):
            findings.append((call.lineno, ast.unparse(call)))
    return findings


def method_route_keys(source: str) -> dict[str, set[str]]:
    tree = ast.parse(source)
    result: dict[str, set[str]] = {}
    for method in (
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_k")
    ):
        result[method.name] = {
            call.args[0].value
            for call in ast.walk(method)
            if isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and call.func.attr == "discovered_route"
            and call.args
            and isinstance(call.args[0], ast.Constant)
            and isinstance(call.args[0].value, str)
        }
    return result


class KeplerOpsRouteDiscoveryTests(unittest.TestCase):
    def test_request_targets_have_no_direct_route_literals(self) -> None:
        source = SUITE.read_text(encoding="utf-8")
        self.assertEqual(direct_request_route_literals(source), [])

    def test_remaining_api_literals_are_classified_participant_artifacts(self) -> None:
        tree = ast.parse(SUITE.read_text(encoding="utf-8"))
        literals = {
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and "/api/" in node.value
        }
        self.assertEqual(literals, CLASSIFIED_API_LITERALS)

    def test_earned_evidence_has_no_accepted_value_fallback(self) -> None:
        source = SUITE.read_text(encoding="utf-8")
        self.assertEqual(accepted_value_fallbacks(source), [])
        constants = {
            node.value
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        }
        self.assertTrue(FORBIDDEN_ACCEPTED_VALUES.isdisjoint(constants))

    def test_k11_recovers_policy_semantics_and_uses_published_resources(self) -> None:
        source = SUITE.read_text(encoding="utf-8")
        for key in (
            "source.policy-evaluate",
            "source.policy-nonce",
        ):
            self.assertIn(f'self.discovered_route("{key}")', source)
        self.assertNotIn("source.policy-opcode-model", source)
        self.assertIn("fieldkest_opcode_", source)

        source_service = (RUNTIME / "source.py").read_text(encoding="utf-8")
        self.assertIn('"fieldkest.policy-opcode-model/v1"', source_service)

        symbols = {
            int(value, 16): name
            for value, name in re.findall(
                rb"fieldkest_opcode_([0-9a-f]{2})_([A-Z_]+)\x00",
                K11_BINARY.read_bytes(),
            )
        }
        self.assertEqual(set(symbols), set(range(8)))
        self.assertEqual(len(set(symbols.values())), 8)

    def test_k04_offline_reproducer_is_delivered_to_the_participant(self) -> None:
        dockerfile = (IMAGES / "k-dev.Dockerfile").read_text(encoding="utf-8")
        suite = SUITE.read_text(encoding="utf-8")
        self.assertIn("build/keplerops/runtime/bundle_indexer.c", dockerfile)
        self.assertIn(
            "/home/rowan/work/reproducers/fieldkest-bundle-indexer",
            dockerfile,
        )
        self.assertIn("binary_image = read_home_bytes(binary)", suite)
        self.assertNotIn('rowan("strings", binary)', suite)

    def test_k29_channel_credential_uses_the_shared_delivery_volume(self) -> None:
        registry = (RUNTIME / "registry.py").read_text(encoding="utf-8")
        relay = (RUNTIME / "customer_relay.py").read_text(encoding="utf-8")
        relative = 'PUBLISHED / "delivery/channel-credential.json"'
        self.assertIn(relative, registry)
        self.assertIn(relative, relay)

    def test_suite_does_not_read_seed_or_operator_manifests(self) -> None:
        source = SUITE.read_text(encoding="utf-8")
        self.assertNotIn("seed-manifest", source)
        self.assertNotIn("operator-manifest", source)

    def test_generated_client_references_are_current_and_image_scoped(self) -> None:
        author_map = json.loads(AUTHOR_MAP.read_text(encoding="utf-8"))
        expected = client_references.validate_and_render(author_map)
        actual = {path.name for path in FRAGMENTS.glob("*.json")}
        self.assertEqual(actual, set(expected))
        for name, payload in expected.items():
            with self.subTest(fragment=name):
                self.assertEqual((FRAGMENTS / name).read_bytes(), payload)
                fragment = json.loads(payload)
                self.assertEqual(
                    list(fragment["documents"]),
                    [author_map["images"][name.removesuffix(".json")]],
                )
                self.assertNotIn("images", fragment)

    def test_service_images_never_copy_the_complete_author_map(self) -> None:
        copied_fragments = set()
        for dockerfile in sorted(IMAGES.glob("*.Dockerfile")):
            source = dockerfile.read_text(encoding="utf-8")
            with self.subTest(image=dockerfile.name):
                self.assertNotIn("authoring/client_documents.json", source)
            if "/opt/fieldkest/client_documents.json" in source:
                self.assertIn("runtime/client-references/", source)
                copied_fragments.add(dockerfile.name)
        self.assertEqual(
            copied_fragments,
            {*STATIC_IMAGE_REFERENCES, "platform.Dockerfile", "service.Dockerfile"},
        )
        for dockerfile, fragment in STATIC_IMAGE_REFERENCES.items():
            self.assertIn(
                f"runtime/client-references/{fragment}",
                (IMAGES / dockerfile).read_text(encoding="utf-8"),
            )
        for dockerfile in ("platform.Dockerfile", "service.Dockerfile"):
            self.assertIn(
                "runtime/client-references/${SERVICE}.json",
                (IMAGES / dockerfile).read_text(encoding="utf-8"),
            )

    def test_discovery_map_rejects_graph_and_route_mutants(self) -> None:
        author_map = json.loads(AUTHOR_MAP.read_text(encoding="utf-8"))
        unreachable = copy.deepcopy(author_map)
        unreachable["documents"]["source.keplerops.test"]["related"] = []
        with self.assertRaisesRegex(
            client_references.DiscoveryMapError, "unreachable service documents"
        ):
            client_references.validate_and_render(unreachable)

        duplicate = copy.deepcopy(author_map)
        routes = duplicate["documents"]["source.keplerops.test"]["routes"]
        routes[1]["key"] = routes[0]["key"]
        with self.assertRaisesRegex(
            client_references.DiscoveryMapError, "duplicate route key"
        ):
            client_references.validate_and_render(duplicate)

        wrong_audience = copy.deepcopy(author_map)
        wrong_audience["audience"] = "participant"
        with self.assertRaisesRegex(
            client_references.DiscoveryMapError, "schema or path is invalid"
        ):
            client_references.validate_and_render(wrong_audience)

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            fragments = client_references.validate_and_render(author_map)
            client_references.write_output(output, fragments)
            source_fragment = output / "source.json"
            source_fragment.write_bytes(source_fragment.read_bytes() + b" ")
            with self.assertRaisesRegex(
                client_references.DiscoveryMapError, "generated fragment drift"
            ):
                client_references.check_output(output, fragments)

    def test_employee_material_is_non_exhaustive_and_does_not_disclose_k04(
        self,
    ) -> None:
        employee_material = "\n".join(
            (OPENING / name).read_text(encoding="utf-8")
            for name in ("HOME.md", "service-notes.md", "local-helper.md")
        )
        author_map = json.loads(AUTHOR_MAP.read_text(encoding="utf-8"))
        route_templates = {
            route["template"]
            for document in author_map["documents"].values()
            for route in document["routes"]
        }
        mentioned = {route for route in route_templates if route in employee_material}
        self.assertLess(len(mentioned), len(route_templates))
        published_references = AUTHOR_MAP.read_text(encoding="utf-8")
        review_surface = employee_material + published_references
        self.assertEqual(
            sorted(
                value for value in K04_EMPLOYEE_DISCLOSURES if value in review_surface
            ),
            [],
        )

    def test_both_arwc_delivery_carriers_are_reached_from_ordinary_references(
        self,
    ) -> None:
        author_map = json.loads(AUTHOR_MAP.read_text(encoding="utf-8"))
        documents = author_map["documents"]
        package_keys = {
            route["key"] for route in documents["packages.keplerops.test"]["routes"]
        }
        support_keys = {
            route["key"] for route in documents["support.keplerops.test"]["routes"]
        }
        self.assertTrue({"connector.poll", "connector.activate"} <= package_keys)
        self.assertIn("support.diagnostic-deliver", support_keys)

    def test_removed_service_catalog_does_not_survive_in_acceptance_sources(
        self,
    ) -> None:
        self.assertNotIn("service-catalog.md", SUITE.read_text(encoding="utf-8"))
        self.assertNotIn("service-catalog.md", PROVENANCE.read_text(encoding="utf-8"))

    def test_client_reference_is_served_before_route_authentication(self) -> None:
        for name in ("ci.py", "cloud_api.py", "platform_service.py"):
            source = (RUNTIME / name).read_text(encoding="utf-8")
            get_handler = source.index("    def do_GET(self) -> None:")
            client_document = source.index("self.send_client_document()", get_handler)
            next_handler = source.find("\n    def do_", get_handler + 1)
            if next_handler == -1:
                next_handler = len(source)
            self.assertLess(
                client_document,
                next_handler,
                f"{name} must serve its public client reference in do_GET",
            )

    def test_provenance_names_every_discovered_route_key(self) -> None:
        source = SUITE.read_text(encoding="utf-8")
        ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
        methods = ledger["methods"]["keplerops"]
        for method, keys in method_route_keys(source).items():
            with self.subTest(method=method):
                citations = json.dumps(methods[method]["citations"], sort_keys=True)
                self.assertEqual(
                    sorted(key for key in keys if key not in citations),
                    [],
                )
                self.assertEqual(methods[method]["review_status"], "complete")
                self.assertEqual(methods[method]["unresolved"], [])

    def test_keplerops_provenance_has_no_generic_citations(self) -> None:
        ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
        reviewed = json.dumps(
            {
                "profile": ledger["profiles"]["keplerops"],
                "methods": ledger["methods"]["keplerops"],
            },
            sort_keys=True,
        ).lower()
        self.assertEqual(
            sorted(term for term in GENERIC_PROVENANCE_PHRASES if term in reviewed),
            [],
        )

    def test_regression_detects_routes_and_fallbacks(self) -> None:
        source = """
curl_json("https://service.test/api/direct")
post_json_route(f"{base}/api/nested", {})
version = self.evidence.get("signed_version", "7.4.3-cinder.rowan")
"""
        self.assertEqual(
            [value for _, value in direct_request_route_literals(source)],
            ["https://service.test/api/direct", "/api/nested"],
        )
        self.assertEqual(len(accepted_value_fallbacks(source)), 1)


if __name__ == "__main__":
    unittest.main()
