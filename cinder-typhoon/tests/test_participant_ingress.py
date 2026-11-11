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

    def test_xrdp_tls_is_compatible_without_exposing_its_key(self) -> None:
        images = {
            "training": ROOT / "build/training/images/participant.Dockerfile",
            "keplerops": ROOT / "build/keplerops/images/k-dev.Dockerfile",
        }
        for phase, path in images.items():
            with self.subTest(phase=phase):
                dockerfile = path.read_text(encoding="utf-8")
                self.assertIn("usermod -aG ssl-cert xrdp", dockerfile)
                self.assertIn("security_layer=tls", dockerfile)
                self.assertIn("ssl_protocols=TLSv1.2", dockerfile)
                self.assertNotIn("usermod -aG ssl-cert cinder", dockerfile)
                self.assertNotIn("usermod -aG ssl-cert rowan", dockerfile)

        readiness = (ROOT / "build/participant-host/shifter-participant-readiness").read_text(
            encoding="utf-8"
        )
        self.assertIn('"security_layer=tls", "ssl_protocols=TLSv1.2"', readiness)
        self.assertIn('grp.getgrnam("ssl-cert")', readiness)
        self.assertIn("xrdp.pw_name not in ssl_cert.gr_mem", readiness)

    def test_desktop_startup_accepts_distribution_profile_variables(self) -> None:
        startwm = (ROOT / "build/participant-host/startwm.sh").read_text(encoding="utf-8")
        self.assertIn("\nset -e\n", startwm)
        self.assertNotIn("\nset -eu\n", startwm)


if __name__ == "__main__":
    unittest.main()
