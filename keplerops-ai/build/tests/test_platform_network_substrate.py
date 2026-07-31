"""Focused structural contracts for the reusable platform-network substrate."""

from __future__ import annotations

import hashlib
import json
import re
import stat
import subprocess
import unittest
from pathlib import Path

import yaml


PACK = Path(__file__).resolve().parents[2]
ROOT = PACK / "assets/services/platform-network"
ENVIRONMENT = yaml.safe_load(
    (PACK / "sdl/modules/environment.sdl.yaml").read_text(encoding="utf-8")
)


class PlatformNetworkSubstrateTests(unittest.TestCase):
    def test_images_are_exactly_versioned_and_digest_pinned(self) -> None:
        expected = {
            "Dockerfile.opensearch": "opensearchproject/opensearch@sha256:44ba7ea58a319adf61c33ab16873f9ef5dbb30b291a832d375172f0b2d24e3c9",
            "Dockerfile.coredns": "coredns/coredns:1.14.6@sha256:900f9c109f7a33545d3c811516e8376df9019147b750f5ce3e254468769176ea",
            "Dockerfile.nginx": "nginx:1.28.1-alpine@sha256:52e3ada4d978443601f286cc2f9e7b95c82aa3ad5a78ce9c6b94ce00258e68cc",
        }
        for dockerfile, image in expected.items():
            source = (ROOT / dockerfile).read_text(encoding="utf-8")
            self.assertIn(f"ARG BASE_IMAGE={image}", source)
            self.assertNotIn(":latest", source)

    def test_aces_sdl_declares_dns_tcp_and_udp_and_containment(self) -> None:
        services = ENVIRONMENT["nodes"]["range-dns-01"]["services"]
        dns = {(row.get("protocol", "tcp"), row["port"]) for row in services}
        self.assertIn(("udp", 53), dns)
        self.assertIn(("tcp", 53), dns)
        scan_services = ENVIRONMENT["nodes"]["scan-services-01"]["services"]
        self.assertEqual({row["port"] for row in scan_services}, {18080, 18081})
        route = ENVIRONMENT["relationships"]["participant-bounded-scan"]
        self.assertEqual(route["source"], "infrastructure.participant-entry")
        self.assertEqual(route["target"], "infrastructure.lab-apps")

    def test_camera_session_broker_route_is_aces_declared(self) -> None:
        route = ENVIRONMENT["relationships"]["inference-platform-camera-control"]
        self.assertEqual(route["type"], "depends_on")
        self.assertEqual(route["source"], "inference-gateway")
        self.assertEqual(route["target"], "platform-camera-01")
        self.assertEqual(route["properties"]["ports"], "8480")
        ice_route = ENVIRONMENT["relationships"]["participant-platform-camera-ice"]
        self.assertEqual(ice_route["type"], "depends_on")
        self.assertEqual(ice_route["source"], "participant-workstation")
        self.assertEqual(ice_route["target"], "platform-camera-01")
        self.assertEqual(ice_route["properties"]["ports"], "32768-60999")
        self.assertEqual(ice_route["properties"]["protocols"], "udp")

        bootstrap = (PACK / "build/gcp/workload-bootstrap.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "platform_camera_url: https://platform-camera-01.keplerops.lab:8480",
            bootstrap,
        )
        self.assertNotIn(
            "platform_camera_url: http://platform-camera-01.keplerops.lab:8470",
            bootstrap,
        )

    def test_opensearch_is_single_node_internal_and_deterministically_mapped(
        self,
    ) -> None:
        config = yaml.safe_load(
            (ROOT / "opensearch/opensearch.yml").read_text(encoding="utf-8")
        )
        self.assertEqual(config["discovery.type"], "single-node")
        self.assertTrue(config["plugins.security.disabled"])
        self.assertFalse(config["action.auto_create_index"])
        feature = ENVIRONMENT["features"]["opensearch-research-index"]
        self.assertEqual(feature["source"]["version"], "2")
        self.assertEqual(
            feature["source"]["build"]["dockerfile_path"],
            "assets/services/platform-network/Dockerfile.opensearch",
        )

        template = json.loads(
            (ROOT / "opensearch/index-template.json").read_text(encoding="utf-8")
        )
        self.assertEqual(template["version"], 1)
        self.assertEqual(template["template"]["settings"]["number_of_shards"], 1)
        self.assertEqual(template["template"]["settings"]["number_of_replicas"], 0)
        self.assertEqual(template["template"]["mappings"]["dynamic"], "strict")
        self.assertIn("keplerops-research", template["template"]["aliases"])

    def test_research_corpus_is_valid_deterministic_original_ndjson(self) -> None:
        path = ROOT / "opensearch/corpus/research-corpus.ndjson"
        lines = path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 16)
        documents: list[dict] = []
        identifiers: list[str] = []
        for offset in range(0, len(lines), 2):
            action = json.loads(lines[offset])
            document = json.loads(lines[offset + 1])
            identifier = action["index"]["_id"]
            self.assertEqual(action["index"]["_index"], "keplerops-research-v1-000001")
            self.assertEqual(identifier, document["document_id"])
            self.assertEqual(document["license"], "CC0-1.0")
            self.assertRegex(document["content_digest"], r"^sha256:[0-9a-f]{64}$")
            content_digest = document.pop("content_digest")
            canonical = json.dumps(document, sort_keys=True, separators=(",", ":"))
            self.assertEqual(
                content_digest,
                "sha256:" + hashlib.sha256((canonical + "\n").encode()).hexdigest(),
            )
            identifiers.append(identifier)
            documents.append(document)
        self.assertEqual(len(set(identifiers)), 8)
        self.assertEqual(
            {document["source_kind"] for document in documents},
            {
                "journal",
                "preprint",
                "technical-blog",
                "vulnerability-analysis",
                "application-repository",
                "code-repository",
                "public-website",
            },
        )
        self.assertTrue(
            all("keplerops" in document["canonical_url"] for document in documents)
        )
        license_text = (ROOT / "opensearch/corpus/LICENSE.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("SPDX-License-Identifier: CC0-1.0", license_text)
        self.assertIn("original synthetic material", license_text)

    def test_coredns_is_authoritative_only_and_zone_is_sdl_derived(self) -> None:
        corefile = (ROOT / "coredns/Corefile").read_text(encoding="utf-8")
        self.assertIn("keplerops.lab:53", corefile)
        self.assertIn(
            "file /var/lib/keplerops/zones/db.keplerops.lab keplerops.lab", corefile
        )
        self.assertIn("health :8080", corefile)
        self.assertIn("ready :8181", corefile)
        self.assertNotIn("forward ", corefile)
        bootstrap = (PACK / "build/gcp/workload-bootstrap.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn('done <"$HOST_ENTRIES_FILE"', bootstrap)
        self.assertIn("peer_name=${peer_name%.keplerops.lab}", bootstrap)
        self.assertIn(
            'printf \'%s 300 IN A %s\\n\' "$peer_name" "$peer_ip"',
            bootstrap,
        )
        self.assertIn("research-index-01.keplerops.lab.", bootstrap)

    def test_web_and_scan_targets_are_real_nginx_services(self) -> None:
        public = (ROOT / "public-web/nginx.conf").read_text(encoding="utf-8")
        scan = (ROOT / "scan-targets/nginx.conf").read_text(encoding="utf-8")
        self.assertIn("listen 8080;", public)
        self.assertIn("server_tokens on;", public)
        self.assertIn("listen 18080;", scan)
        self.assertIn("listen 18081;", scan)
        self.assertIn("server_tokens on;", scan)
        self.assertIn(
            "KeplerOps AI Systems",
            (ROOT / "public-web/html/index.html").read_text(encoding="utf-8"),
        )
        self.assertIn(
            "Range Documentation Service",
            (ROOT / "scan-targets/scan-docs/index.html").read_text(encoding="utf-8"),
        )
        status = json.loads(
            (ROOT / "scan-targets/scan-status/index.json").read_text(encoding="utf-8")
        )
        self.assertEqual(status["software"], "nginx")
        self.assertEqual(status["scope"], "keplerops-contained")

    def test_reset_and_readiness_scripts_are_executable_and_parse(self) -> None:
        scripts = sorted(ROOT.rglob("*.sh"))
        self.assertEqual(len(scripts), 8)
        for path in scripts:
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertTrue(path.stat().st_mode & stat.S_IXUSR)
                completed = subprocess.run(
                    ["sh", "-n", str(path)],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_no_pack_local_deployment_projection_exists(self) -> None:
        self.assertFalse((ROOT / "service-manifest.yaml").exists())
        self.assertFalse((ROOT / "topology.yaml").exists())
        content_sources = {
            row.get("source", {}).get("name") for row in ENVIRONMENT["content"].values()
        }
        self.assertIn(
            "assets/services/platform-network/opensearch/corpus", content_sources
        )
        self.assertIn("assets/services/platform-network/public-web", content_sources)

    def test_substrate_contains_no_game_or_award_contracts(self) -> None:
        forbidden = re.compile(
            r"(?i)\b(challenge_id|flag|receipt|scoring|proof predicate|atlas status)\b"
        )
        for path in ROOT.rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts:
                with self.subTest(path=path.relative_to(ROOT)):
                    self.assertIsNone(
                        forbidden.search(path.read_text(encoding="utf-8"))
                    )


if __name__ == "__main__":
    unittest.main()
