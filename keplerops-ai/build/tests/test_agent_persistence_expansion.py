from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


PACK_ROOT = Path(__file__).resolve().parents[2]
DOMAIN_PATH = PACK_ROOT / "assets/services/keplerops-runtime/agent_persistence_expansion.py"


def load_domain():
    spec = importlib.util.spec_from_file_location(
        "keplerops_agent_persistence_expansion", DOMAIN_PATH
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("agent-persistence expansion domain unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class AgentPersistenceExpansionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.domain = load_domain()

    def test_blueprint_and_config_are_generation_scoped(self) -> None:
        token = self.domain.scoped_token("range-a", "participant-a", 7)
        blueprint = self.domain.blueprint_document("5.5.5")
        self.assertTrue(
            self.domain.challenge_satisfied(
                "kep-m05-f",
                {
                    "agent_id": self.domain.SEED_AGENT_ID,
                    "blueprint": blueprint,
                    "blueprint_digest": self.domain.digest_value(blueprint),
                    "live_revision_match": True,
                },
                observed_events=1,
            )
        )
        self.assertTrue(token.startswith("tok-"))
        self.assertNotEqual(
            token, self.domain.scoped_token("range-a", "participant-a", 8)
        )

    def test_token_reuse_rejects_unvalidated_operation(self) -> None:
        evidence = {
            "token_valid": True,
            "account": self.domain.SCOPED_ACCOUNT,
            "authorized_operation": "agent-config-read",
        }
        self.assertTrue(
            self.domain.challenge_satisfied("kep-m05-h", evidence, observed_events=1)
        )
        evidence["authorized_operation"] = "unscoped-admin"
        self.assertFalse(
            self.domain.challenge_satisfied("kep-m05-h", evidence, observed_events=1)
        )

    def test_cookie_replay_requires_distinct_sessions(self) -> None:
        evidence = {
            "cookie_replayed": True,
            "original_session": "browser-session-alpha",
            "replay_session": "browser-session-beta",
            "authenticated_action": "assistant-session-read",
        }
        self.assertTrue(
            self.domain.challenge_satisfied("kep-m05-i", evidence, observed_events=2)
        )
        evidence["replay_session"] = evidence["original_session"]
        self.assertFalse(
            self.domain.challenge_satisfied("kep-m05-i", evidence, observed_events=2)
        )

    def test_web_relay_rejects_api_call_shortcut(self) -> None:
        evidence = {
            "browser_automation": True,
            "relay_command": self.domain.WEB_RELAY_COMMAND,
            "worker_result": self.domain.WORKER_MARKER,
            "api_calls": [],
        }
        self.assertTrue(
            self.domain.challenge_satisfied("kep-m05-q", evidence, observed_events=1)
        )
        evidence["api_calls"] = ["/v1/agent/runs"]
        self.assertFalse(
            self.domain.challenge_satisfied("kep-m05-q", evidence, observed_events=1)
        )


if __name__ == "__main__":
    unittest.main()
