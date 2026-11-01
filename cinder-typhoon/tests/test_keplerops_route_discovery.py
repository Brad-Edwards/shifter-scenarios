"""Static regressions for KeplerOps known-solution route discovery."""

from __future__ import annotations

import ast
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / "build" / "keplerops" / "tests" / "test_known_solution_live.py"
LEDGER = ROOT / "build" / "input-provenance" / "ledger.json"
IMAGES = ROOT / "build" / "keplerops" / "images"
RUNTIME = ROOT / "build" / "keplerops" / "runtime"
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
            or call.func.attr == "get" and (len(call.args) > 1 or call.keywords)
        ):
            findings.append((call.lineno, ast.unparse(call)))
    return findings


def method_route_keys(source: str) -> dict[str, set[str]]:
    tree = ast.parse(source)
    result: dict[str, set[str]] = {}
    for method in (
        node for node in ast.walk(tree)
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

    def test_k11_uses_all_published_policy_routes(self) -> None:
        source = SUITE.read_text(encoding="utf-8")
        for key in (
            "source.policy-evaluate",
            "source.policy-nonce",
            "source.policy-opcode-model",
        ):
            self.assertIn(f'self.discovered_route("{key}")', source)

        source_service = (RUNTIME / "source.py").read_text(encoding="utf-8")
        self.assertIn('"schema": "fieldkest.policy-opcode-model/v1"', source_service)

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

    def test_service_images_publish_the_client_reference_graph(self) -> None:
        copy = (
            "COPY build/keplerops/runtime/client_documents.json "
            "/opt/fieldkest/client_documents.json"
        )
        service_images = []
        for dockerfile in sorted(IMAGES.glob("*.Dockerfile")):
            source = dockerfile.read_text(encoding="utf-8")
            if "runtime/http_support.py" in source and dockerfile.name != "k-dev.Dockerfile":
                service_images.append(dockerfile.name)
                with self.subTest(image=dockerfile.name):
                    self.assertIn(copy, source)
        self.assertTrue(service_images)
        self.assertNotIn(
            "runtime/client_documents.json",
            (IMAGES / "k-dev.Dockerfile").read_text(encoding="utf-8"),
            "the participant image must not contain the complete service document inventory",
        )

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
