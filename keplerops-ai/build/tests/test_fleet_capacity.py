from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "gcp"
MODULE_PATH = ROOT / "fleet_capacity.py"
PROFILE_PATH = ROOT / "fleet-capacity-profile.json"


def load_module():
    spec = importlib.util.spec_from_file_location("keplerops_fleet_capacity", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def profile() -> dict:
    return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))


def write_profile(root: Path, payload: dict) -> Path:
    path = root / "profile.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def row(report: dict, name: str) -> dict:
    return next(item for item in report["resources"] if item["resource"] == name)


class FleetCapacityTests(unittest.TestCase):
    def test_profile_models_200_ranges_without_per_range_cloud_sprawl(self) -> None:
        module = load_module()
        report = module.calculate(module.load_profile(PROFILE_PATH))

        self.assertEqual(
            report["ranges"],
            {
                "total": 200,
                "active": 200,
                "simultaneously_busy": 200,
                "headroom_percent": 0,
            },
        )
        self.assertEqual(report["cell_count"], 2)
        self.assertEqual(report["cell_active_capacity"], 200)
        self.assertEqual(row(report, "vpc_networks")["required_with_headroom"], 2)
        self.assertEqual(row(report, "subnetworks")["required_with_headroom"], 200)
        self.assertEqual(row(report, "firewall_rules_fixed")["required_with_headroom"], 10)
        self.assertEqual(
            row(report, "firewall_rules_range_isolation")["required_with_headroom"],
            200,
        )
        self.assertEqual(row(report, "artifact_repositories")["required_with_headroom"], 2)
        self.assertEqual(row(report, "gpu_l4")["required_with_headroom"], 8)
        self.assertEqual(row(report, "instances")["required_with_headroom"], 200)
        self.assertEqual(row(report, "vcpus")["required_with_headroom"], 2_400)
        self.assertEqual(
            row(report, "persistent_disk_gib")["required_with_headroom"],
            80_000,
        )
        self.assertEqual(row(report, "service_accounts")["required_with_headroom"], 200)
        self.assertEqual(row(report, "secrets")["required_with_headroom"], 15_600)

    def test_profile_keeps_capacity_claim_explicitly_unproven(self) -> None:
        module = load_module()
        report = module.calculate(module.load_profile(PROFILE_PATH))

        self.assertEqual(report["evidence_status"], "planning_bound")
        self.assertEqual(
            report["readiness"],
            {
                "capacity_proven": False,
                "reason": "planning bounds, unknown quotas, or required expansions remain",
            },
        )
        self.assertIn("vcpus", report["planning_bounds"])
        self.assertNotIn("vcpus", report["quota_limits_unknown"])
        self.assertEqual(row(report, "vcpus")["current_limit"], 2_400)
        self.assertEqual(row(report, "vcpus")["quota_expansion"], 0)
        self.assertEqual(report["quota_expansions_required"], [])

    def test_profile_rejects_forbidden_per_range_scaling(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            for resource_name in (
                "vpc_networks",
                "firewall_rules_fixed",
                "artifact_repositories",
                "gpu_l4",
            ):
                for basis in ("total_range", "active_range"):
                    with self.subTest(resource=resource_name, basis=basis):
                        payload = profile()
                        resource = next(
                            item for item in payload["resources"] if item["resource"] == resource_name
                        )
                        resource["basis"] = basis
                        with self.assertRaisesRegex(module.CapacityError, "may not scale per range"):
                            module.load_profile(write_profile(Path(temp_dir), payload))

    def test_profile_requires_all_shared_resources_to_be_protected(self) -> None:
        module = load_module()
        payload = profile()
        payload["policy"]["forbid_range_scaled_resources"].remove(
            "firewall_rules_fixed"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(module.CapacityError, "missing range-scaling protection"):
                module.load_profile(write_profile(Path(temp_dir), payload))

    def test_profile_rejects_cell_capacity_below_active_ranges(self) -> None:
        module = load_module()
        payload = profile()
        payload["cells"][1]["max_active_ranges"] = 99
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(module.CapacityError, "cell active-range capacity"):
                module.load_profile(write_profile(Path(temp_dir), payload))

    def test_profile_rejects_firewall_policy_regression(self) -> None:
        module = load_module()
        payload = copy.deepcopy(profile())
        firewall = next(
            item
            for item in payload["resources"]
            if item["resource"] == "firewall_rules_range_isolation"
        )
        firewall["quantity"] = 2

        with self.assertRaisesRegex(module.CapacityError, "exceeds policy maximum"):
            module.calculate(payload)

    def test_measured_known_capacity_can_be_proven(self) -> None:
        module = load_module()
        payload = profile()
        payload["evidence_status"] = "measured"
        for resource in payload["resources"]:
            resource["evidence"] = "measured"
            resource["current_limit"] = 1_000_000
        with tempfile.TemporaryDirectory() as temp_dir:
            report = module.calculate(module.load_profile(write_profile(Path(temp_dir), payload)))

        self.assertEqual(report["planning_bounds"], [])
        self.assertEqual(report["quota_limits_unknown"], [])
        self.assertEqual(report["quota_expansions_required"], [])
        self.assertIs(report["readiness"]["capacity_proven"], True)

    def test_known_quota_shortfall_is_reported(self) -> None:
        module = load_module()
        payload = profile()
        vcpus = next(item for item in payload["resources"] if item["resource"] == "vcpus")
        vcpus["current_limit"] = 1000
        with tempfile.TemporaryDirectory() as temp_dir:
            report = module.calculate(module.load_profile(write_profile(Path(temp_dir), payload)))

        self.assertEqual(row(report, "vcpus")["required_with_headroom"], 2400)
        self.assertEqual(row(report, "vcpus")["quota_expansion"], 1400)
        self.assertIn("vcpus", report["quota_expansions_required"])


if __name__ == "__main__":
    unittest.main()
