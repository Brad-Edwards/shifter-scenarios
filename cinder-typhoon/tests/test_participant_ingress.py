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

    def test_xrdp_can_read_its_tls_key_without_exposing_it_to_participants(self) -> None:
        images = {
            "training": ROOT / "build/training/images/participant.Dockerfile",
            "keplerops": ROOT / "build/keplerops/images/k-dev.Dockerfile",
        }
        for phase, path in images.items():
            with self.subTest(phase=phase):
                dockerfile = path.read_text(encoding="utf-8")
                self.assertIn("usermod -aG ssl-cert xrdp", dockerfile)
                self.assertNotIn("usermod -aG ssl-cert cinder", dockerfile)
                self.assertNotIn("usermod -aG ssl-cert rowan", dockerfile)

        readiness = (ROOT / "build/participant-host/shifter-participant-readiness").read_text(
            encoding="utf-8"
        )
        self.assertIn('grp.getgrnam("ssl-cert")', readiness)
        self.assertIn("xrdp.pw_name not in ssl_cert.gr_mem", readiness)


if __name__ == "__main__":
    unittest.main()
