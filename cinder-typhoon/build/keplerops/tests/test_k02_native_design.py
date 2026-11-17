#!/usr/bin/env python3
"""Focused source checks for the native K02 implementation."""

from __future__ import annotations

import json
from pathlib import Path
import unittest

import yaml


PACK = Path(__file__).resolve().parents[3]


class K02NativeDesignTest(unittest.TestCase):
    def test_cards_use_native_jenkins_and_gitea(self) -> None:
        dockerfile = (PACK / "build/keplerops/images/jenkins.Dockerfile").read_text()
        self.assertIn("FROM jenkins/jenkins:", dockerfile)
        self.assertIn("@sha256:", dockerfile)

        seed = (PACK / "build/keplerops/native-ci/init.groovy").read_text()
        for product_type in (
            "FreeStyleProject", "GitSCM", "FileParameterDefinition", "ArtifactArchiver",
        ):
            self.assertIn(product_type, seed)
        for job in (
            "fieldlink-report", "fieldlink-report-review", "fieldlink-release-review",
            "fieldlink-package-check",
        ):
            self.assertIn(job, seed)

        operation = yaml.safe_load((PACK / "sdl/modules/operations/k02.yaml").read_text())
        self.assertEqual(
            operation["evidence_requirements"]["c2"]["source_refs"],
            ["features.k-delivery.k-ci"],
        )
        content = yaml.safe_load((PACK / "sdl/modules/content/keplerops-k-ci.yaml").read_text())
        contract = content["content"]["k02-2-an-input-outside-its-lane"]["text"]
        self.assertIn("jenkins/build-artifacts", contract)
        self.assertIn("provider.zip", contract)
        self.assertNotIn("review-import", contract)

    def test_retired_k02_importer_is_not_participant_facing(self) -> None:
        sources = (
            PACK / "assets/keplerops/opening/k-dev/service-notes.md",
            PACK / "build/keplerops/runtime/client-references/ci.json",
            PACK / "build/keplerops/authoring/client_documents.json",
            PACK / "build/keplerops/tests/test_opening_live.py",
        )
        for path in sources:
            self.assertNotIn("/api/reviews/import", path.read_text(), path)

        archive = json.loads((PACK / "assets/keplerops/opening/archive-manifest.json").read_text())
        ci = next(item for item in archive["archives"] if item["archive"] == "k-ci-state.tar")
        paths = {item["path"] for item in ci["files"]}
        self.assertFalse(any(path.startswith("import-objects/") for path in paths))

    def test_k02_in_world_assets_have_no_meta_commentary(self) -> None:
        assets = (
            PACK / "assets/keplerops/opening/k-ci/REVNOTE-1842.json",
            PACK / "assets/keplerops/opening/k-source/report-provider.md",
            PACK / "assets/keplerops/opening/k-source/report-crr-og2.json",
        )
        text = "\n".join(path.read_text() for path in assets).lower()
        for forbidden in ("challenge", "participant", "ctf", "flag", "hint", "cyber range"):
            self.assertNotIn(forbidden, text)

        review = json.loads(assets[0].read_text())
        self.assertEqual(review["extension_point"], "render_report")


if __name__ == "__main__":
    unittest.main()
