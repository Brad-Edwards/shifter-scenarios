"""Participant ingress contracts for preconfigured range hosts."""

from pathlib import Path
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]


class ParticipantIngressTests(unittest.TestCase):
    def assert_participant_ingress(self, phase: str, service: str) -> None:
        compose = yaml.safe_load(
            (ROOT / "build" / phase / "compose.yaml").read_text(encoding="utf-8")
        )
        participant = compose["services"][service]
        ingress = compose["networks"]["participant_ingress"]

        self.assertIn("3389:3389", participant["ports"])
        self.assertIn("participant_ingress", participant["networks"])
        self.assertNotIn("internal", ingress)
        self.assertEqual(ingress["driver"], "bridge")
        self.assertEqual(
            ingress["driver_opts"][
                "com.docker.network.bridge.enable_ip_masquerade"
            ],
            "false",
        )

    def test_training_participant_has_no_egress_ingress_bridge(self) -> None:
        self.assert_participant_ingress("training", "participant")

    def test_keplerops_participant_has_no_egress_ingress_bridge(self) -> None:
        self.assert_participant_ingress("keplerops", "k-dev")


if __name__ == "__main__":
    unittest.main()
