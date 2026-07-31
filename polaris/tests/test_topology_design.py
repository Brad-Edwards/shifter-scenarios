"""Static contract tests for the Polaris topology-design slice.

These tests keep the active Compose fast-feedback binding joined to the
canonical ACES SDL without turning Compose into a second topology authority.
They also keep planned runtime and asset boundaries honest while the pack is
still ``draft``.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

import yaml


PACK_ROOT = Path(__file__).resolve().parents[1]
SDL_PATH = PACK_ROOT / "sdl" / "polaris-operation-northstorm.sdl.yaml"
COMPOSE_PATH = PACK_ROOT / "build" / "docker-compose.yml"
COMPATIBILITY_PATH = PACK_ROOT / "pack.compatibility.yaml"
PACK_PATH = PACK_ROOT / "pack.yaml"
PROVENANCE_PATH = PACK_ROOT / "docs" / "provenance-ledger.yaml"
AUTOMATED_REPORT_PATH = PACK_ROOT / "docs" / "aws-event-rehearsal-report.md"
MANUAL_REPORT_PATH = PACK_ROOT / "docs" / "aws-event-manual-walkthrough-report.md"
FINAL_REPORT_PATH = PACK_ROOT / "docs" / "final-reconciliation-report.md"


def _load_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as stream:
        data = yaml.safe_load(stream)
    if not isinstance(data, dict):
        raise AssertionError(f"{path} must contain a YAML mapping")
    return data


def _report_metadata(path: Path) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"- ([a-z0-9_-]+): `([^`]+)`", line)
        if match:
            metadata[match.group(1)] = match.group(2)
    return metadata


class TopologyBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sdl = _load_yaml(SDL_PATH)
        cls.compose = _load_yaml(COMPOSE_PATH)

    def test_compose_services_bind_to_unique_sdl_assets(self) -> None:
        bindings = {}
        for service_name, service in self.compose["services"].items():
            labels = service.get("labels", {})
            asset_id = labels.get("polaris.asset")
            self.assertIsNotNone(
                asset_id,
                f"Compose service {service_name} has no polaris.asset binding",
            )
            self.assertIn(asset_id, self.sdl["nodes"])
            self.assertNotIn(asset_id, bindings, f"duplicate binding for {asset_id}")
            bindings[asset_id] = service_name

        expected = set(self.sdl["nodes"]) - {
            "shared-net",
            "corporate-net",
            "lab-net",
            "scada-net",
            "bunker-ot-net",
            "splice-link",
            "a2-dc01",
        }
        self.assertEqual(expected, set(bindings))

    def test_compose_network_addresses_match_sdl_binding(self) -> None:
        infrastructure = self.sdl["infrastructure"]
        for service_name, service in self.compose["services"].items():
            asset_id = service["labels"]["polaris.asset"]
            expected = {}
            for item in infrastructure[asset_id]["properties"]:
                expected.update(item)
            actual = {
                (
                    network_name
                    if network_name == "splice-link"
                    else f"{network_name}-net"
                ): network["ipv4_address"]
                for network_name, network in service["networks"].items()
            }
            self.assertEqual(
                expected,
                actual,
                f"{service_name} drifted from SDL asset {asset_id}",
            )

    def test_path_critical_network_invariants(self) -> None:
        infrastructure = self.sdl["infrastructure"]
        single_homed_assets = {
            "a5-scada-gw": "scada-net",
            "a6-eng-ws01": "lab-net",
            "a7-git": "lab-net",
            "a8-research-db": "lab-net",
            "a10-tail-ctrl": "bunker-ot-net",
            "a11-leg-ctrl": "bunker-ot-net",
            "a12-arms-ctrl": "bunker-ot-net",
        }
        for asset_id, network_id in single_homed_assets.items():
            self.assertEqual(
                [network_id],
                infrastructure[asset_id]["links"],
                f"{asset_id} must remain isolated on {network_id}",
            )

        self.assertEqual(
            ["shared-net", "corporate-net"],
            infrastructure["a14-kali"]["links"],
        )
        self.assertEqual(
            ["corporate-net", "scada-net"],
            infrastructure["a15-ops-eng01"]["links"],
        )
        self.assertEqual(
            ["corporate-net", "lab-net"],
            infrastructure["a16-research-analyst01"]["links"],
        )
        self.assertNotIn("splice-link", infrastructure["a14-kali"]["links"])
        self.assertIn(
            "range-local",
            infrastructure["a2-dc01"]["description"].lower(),
        )
        self.assertNotIn(
            "shared across",
            infrastructure["a2-dc01"]["description"].lower(),
        )


class PolarisDesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pack = _load_yaml(PACK_PATH)
        cls.compatibility = _load_yaml(COMPATIBILITY_PATH)
        cls.provenance = _load_yaml(PROVENANCE_PATH)

    def test_pack_records_proven_layers_without_golden_claim(self) -> None:
        self.assertEqual("0.5.0", str(self.pack["version"]))
        self.assertEqual("draft", self.pack["status"])
        self.assertTrue(self.pack["contents"]["flag_layer"])
        self.assertTrue(self.pack["contents"]["reference_triangle"])
        self.assertTrue(self.pack["contents"]["profile_bundles"])

        projection = self.compatibility["pack"]
        self.assertEqual(self.pack["version"], projection["version"])
        self.assertEqual(self.pack["status"], projection["status"])
        self.assertEqual([], projection["source"]["upstream_references"])
        self.assertEqual(
            self.pack["version"],
            self.provenance["pack"]["version"],
        )

    def test_runtime_profiles_are_reconciled_and_truthful(self) -> None:
        profiles = {
            profile["profile_id"]: profile
            for profile in self.compatibility["runtime_profiles"]
        }
        self.assertEqual({"local_degraded", "aws_event"}, set(profiles))
        self.assertEqual("planned", profiles["local_degraded"]["status"])
        self.assertIn("degraded", profiles["local_degraded"]["description"].lower())
        self.assertIn("cannot", profiles["local_degraded"]["description"].lower())
        self.assertEqual("supported", profiles["aws_event"]["status"])
        self.assertIn("dedicated", profiles["aws_event"]["description"].lower())
        self.assertIn("participant", profiles["aws_event"]["description"].lower())
        self.assertIn("not", profiles["aws_event"]["description"].lower())
        self.assertIn("golden", profiles["aws_event"]["description"].lower())

    def test_conventional_asset_roots_are_planned_not_shipped(self) -> None:
        assets = {
            asset["asset_id"]: asset for asset in self.compatibility["assets"]
        }
        expected = {
            "planned-participant-briefing": ("assets/briefing/", "participant"),
            "planned-planted-content": ("assets/content/", "commercial"),
            "planned-service-source": ("assets/services/", "commercial"),
        }
        for asset_id, (path, visibility) in expected.items():
            self.assertEqual(path, assets[asset_id]["path"])
            self.assertEqual(visibility, assets[asset_id]["visibility"])
            self.assertEqual("planned", assets[asset_id]["status"])
            self.assertTrue((PACK_ROOT / path).is_dir())

        boundaries = self.compatibility["artifact_boundaries"]
        participant_paths = {
            artifact["path"] for artifact in boundaries["participant_visible"]
        }
        commercial_paths = {
            artifact["path"] for artifact in boundaries["commercial"]
        }
        self.assertNotIn("assets/content/", participant_paths)
        self.assertNotIn("assets/content/", commercial_paths)
        self.assertNotIn("assets/briefing/", participant_paths)
        self.assertNotIn("assets/services/", commercial_paths)

    def test_release_boundaries_exclude_mixed_historical_roots(self) -> None:
        boundaries = self.compatibility["artifact_boundaries"]
        participant_paths = {
            artifact["path"] for artifact in boundaries["participant_visible"]
        }
        operator_paths = {
            artifact["path"] for artifact in boundaries["operator_only"]
        }
        commercial_paths = {
            artifact["path"] for artifact in boundaries["commercial"]
        }

        self.assertIn("briefing-deck/", participant_paths)
        self.assertNotIn("aws-range/", operator_paths)
        self.assertNotIn("design/", commercial_paths)
        self.assertNotIn("notes/", commercial_paths)
        scoring_path = "profiles/agent-benchmark/operator/scoring-hooks.yaml"
        self.assertIn("profiles/agent-benchmark/operator/", operator_paths)
        self.assertIn(scoring_path, operator_paths)
        self.assertEqual(
            "operator",
            next(
                asset["visibility"]
                for asset in self.compatibility["assets"]
                if asset["path"] == scoring_path
            ),
        )
        self.assertEqual(
            "operator",
            next(
                surface["visibility"]
                for surface in self.compatibility["operator_surfaces"]
                if surface["path"] == scoring_path
            ),
        )
        for path in (
            "aws-range/main.tf",
            "aws-range/ranges.tf",
            "aws-range/shared.tf",
            "aws-range/versions.tf",
            "aws-range/variables.tf",
            "aws-range/outputs.tf",
            "aws-range/user_data.sh.tpl",
            "aws-range/a2_user_data.ps1.tpl",
            "aws-range/a2_install_adds.ps1",
            "aws-range/a2_setup.ps1",
            "aws-range/common.py",
            "aws-range/reset.sh",
        ):
            self.assertIn(path, operator_paths)

    def test_aces_semantics_stay_out_of_the_compatibility_projection(self) -> None:
        for forbidden in ("scoring", "validation_oracle", "telemetry", "lifecycle"):
            self.assertNotIn(forbidden, self.compatibility)

    def test_final_evidence_and_security_gates_are_indexed(self) -> None:
        assets = {
            asset["asset_id"]: asset for asset in self.compatibility["assets"]
        }
        surfaces = {
            surface["surface_id"]: surface
            for surface in self.compatibility["operator_surfaces"]
        }
        gates = {
            gate["id"]: gate for gate in self.compatibility["validation"]["gates"]
        }

        for asset_id in (
            "private-oracle",
            "flag-placement",
            "challenge-copy",
            "aws-event-rehearsal-evidence",
            "manual-walkthrough-evidence",
            "final-reconciliation-evidence",
        ):
            self.assertEqual("shipped", assets[asset_id]["status"])
        for surface_id in (
            "aws-event-reset",
            "aws-event-rehearsal",
            "aws-event-teardown",
            "final-reconciliation",
        ):
            self.assertEqual("shipped", surfaces[surface_id]["status"])
        self.assertEqual(
            {
                "participant-export-leak-scan",
                "aws-event-rehearsal-evidence",
                "manual-participant-walkthrough",
                "final-reconciliation",
            },
            {
                gate_id
                for gate_id in gates
                if gate_id
                in {
                    "participant-export-leak-scan",
                    "aws-event-rehearsal-evidence",
                    "manual-participant-walkthrough",
                    "final-reconciliation",
                }
            },
        )
        self.assertEqual(
            "leak-scan",
            gates["participant-export-leak-scan"]["kind"],
        )
        self.assertEqual(
            "rehearsal",
            gates["aws-event-rehearsal-evidence"]["kind"],
        )
        self.assertEqual(
            "manual-walkthrough",
            gates["manual-participant-walkthrough"]["kind"],
        )

    def test_evidence_reports_join_and_teardown_passes(self) -> None:
        automated = _report_metadata(AUTOMATED_REPORT_PATH)
        manual = _report_metadata(MANUAL_REPORT_PATH)
        final = _report_metadata(FINAL_REPORT_PATH)

        self.assertEqual(manual["post-fix_pack_version"], automated["pack_version"])
        self.assertEqual("PASS", automated["teardown"])
        self.assertEqual("PASS", manual["manual_teardown"])
        self.assertEqual("PASS", manual["post-fix_teardown"])
        self.assertEqual("PASS", final["historical_teardown_evidence"])
        self.assertEqual("draft", final["final_maturity"])
        self.assertEqual("supported", final["aws_event_status"])

    def test_stale_runtime_state_and_final_pass_markers_are_absent(self) -> None:
        for path in (
            PACK_ROOT / "aws-range" / "health_report.md",
            PACK_ROOT / "aws-range" / "postprovision_status.md",
            PACK_ROOT / "aws-range" / "provisioning_state.json",
            PACK_ROOT / "aws-range" / "provisioning_status.md",
            PACK_ROOT / "aws-range" / "cleanup_non_keepers.py",
            PACK_ROOT / "cleanup-plan.md",
            PACK_ROOT / "notes" / "BUILD-TODO.md",
        ):
            self.assertFalse(path.exists(), f"stale runtime/planning state remains: {path}")

        briefing_inventory = (
            PACK_ROOT / "briefing-deck" / "asset-inventory.md"
        ).read_text(encoding="utf-8")
        for stale_claim in ("42 flags", "(A17)", "(A18)", "not simulated stubs"):
            self.assertNotIn(stale_claim, briefing_inventory)


if __name__ == "__main__":
    unittest.main()
