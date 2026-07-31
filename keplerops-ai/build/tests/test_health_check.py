from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


PACK_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = PACK_ROOT / "build" / "gcp" / "health_check.py"
EXPECTED_HOSTS = {"participant-workstation", "range-linux-carrier-01"}
EXPECTED_WORKLOADS = {"participant-workstation", "service-a", "model-host-01"}
EXPECTED_RANGE_WORKLOADS = {"participant-workstation", "service-a"}


def load_health():
    spec = importlib.util.spec_from_file_location("keplerops_health", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError("unable to load health module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def healthy_resources():
    resources = [
        {
            "type": "google_compute_instance",
            "name": "range_host",
            "index": 0,
            "values": {
                "current_status": "RUNNING",
                "name": "kep-rangehost-test",
                "network_interface": [
                    {"access_config": [{"nat_ip": "203.0.113.42"}]}
                ],
            },
        }
    ]
    resources.append(
        {
            "type": "google_compute_address",
            "name": "participant",
            "values": {"address_type": "EXTERNAL", "address": "203.0.113.42"},
        }
    )
    return resources


class HealthCheckTests(unittest.TestCase):
    def test_assessment_requires_all_declared_hosts_running(self) -> None:
        health = load_health()
        resources = healthy_resources()
        report = health.assess_state(
            {"values": {"root_module": {"resources": resources}}},
            expected_hosts=EXPECTED_HOSTS,
            expected_workloads=EXPECTED_WORKLOADS,
            expected_range_workloads=EXPECTED_RANGE_WORKLOADS,
        )
        self.assertEqual(report["status"], "ready")
        self.assertEqual(report["host_count"], 1)
        self.assertEqual(report["logical_host_count"], len(EXPECTED_HOSTS))
        self.assertEqual(
            report["logical_workload_count"], len(EXPECTED_WORKLOADS)
        )
        self.assertEqual(
            report["range_workload_count"], len(EXPECTED_RANGE_WORKLOADS)
        )
        self.assertTrue(report["cell_resources_external"])
        self.assertNotIn("values", report)

        resources = [
            row
            for row in resources
            if not (
                row["type"] == "google_compute_instance"
                and row.get("name") == "range_host"
            )
        ]
        with self.assertRaises(health.HealthError):
            health.assess_state(
                {"values": {"root_module": {"resources": resources}}},
                expected_hosts=EXPECTED_HOSTS,
                expected_workloads=EXPECTED_WORKLOADS,
                expected_range_workloads=EXPECTED_RANGE_WORKLOADS,
            )

    def test_assessment_rejects_non_running_or_cell_owned_resources(self) -> None:
        health = load_health()
        resources = healthy_resources()
        resources[0]["values"]["current_status"] = "TERMINATED"
        with self.assertRaisesRegex(health.HealthError, "host not running"):
            health.assess_state(
                {"values": {"root_module": {"resources": resources}}},
                expected_hosts=EXPECTED_HOSTS,
                expected_workloads=EXPECTED_WORKLOADS,
                expected_range_workloads=EXPECTED_RANGE_WORKLOADS,
            )

        resources = healthy_resources()
        resources.append(
            {"type": "google_compute_network", "name": "cell", "values": {}}
        )
        with self.assertRaisesRegex(
            health.HealthError, "range state owns deployment-cell resources"
        ):
            health.assess_state(
                {"values": {"root_module": {"resources": resources}}},
                expected_hosts=EXPECTED_HOSTS,
                expected_workloads=EXPECTED_WORKLOADS,
                expected_range_workloads=EXPECTED_RANGE_WORKLOADS,
            )

    def test_assessment_rejects_unbound_participant_address(self) -> None:
        health = load_health()
        resources = healthy_resources()
        resources[-1]["values"]["address"] = "203.0.113.99"
        with self.assertRaisesRegex(
            health.HealthError, "participant address binding invalid"
        ):
            health.assess_state(
                {"values": {"root_module": {"resources": resources}}},
                expected_hosts=EXPECTED_HOSTS,
                expected_workloads=EXPECTED_WORKLOADS,
                expected_range_workloads=EXPECTED_RANGE_WORKLOADS,
            )

    def test_expectations_are_loaded_from_sdl_realization(self) -> None:
        health = load_health()
        with tempfile.TemporaryDirectory() as temp_dir:
            realization = Path(temp_dir) / "realization.json"
            realization.write_text(
                json.dumps(
                    {
                        "physical_hosts": {
                            name: {} for name in EXPECTED_HOSTS
                        },
                        "workloads": {
                            "participant-workstation": {
                                "deployment_cell": "range-cell"
                            },
                            "service-a": {"deployment_cell": "range-cell"},
                            "model-host-01": {
                                "deployment_cell": "shared-services-cell"
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )
            hosts, workloads, range_workloads = health.load_expectations(
                realization
            )
        self.assertEqual(hosts, EXPECTED_HOSTS)
        self.assertEqual(workloads, EXPECTED_WORKLOADS)
        self.assertEqual(range_workloads, EXPECTED_RANGE_WORKLOADS)


if __name__ == "__main__":
    unittest.main()
