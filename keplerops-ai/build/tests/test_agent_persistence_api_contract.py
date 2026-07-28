from __future__ import annotations

import ast
import unittest
from pathlib import Path

import yaml

from .runtime_source import module_source, runtime_source


PACK_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_ROOT = PACK_ROOT / "assets/services/keplerops-runtime"


def class_fields(tree: ast.Module, name: str) -> set[str]:
    node = next(
        item for item in tree.body if isinstance(item, ast.ClassDef) and item.name == name
    )
    return {
        item.target.id
        for item in node.body
        if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name)
    }


class AgentPersistenceApiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = runtime_source(RUNTIME_ROOT)
        cls.persistence_source = module_source(RUNTIME_ROOT, "m05")
        cls.tree = ast.parse(
            (
                RUNTIME_ROOT
                / "keplerops_runtime/modules/m05/schemas.py"
            ).read_text(encoding="utf-8")
        )

    def test_participant_submits_chat_coordinates_not_memory_or_evidence(self) -> None:
        self.assertEqual(
            class_fields(self.tree, "PersistenceTurnRequest"),
            {
                "challenge_id", "phase", "session_id", "thread_id", "prompt",
                "participant_interface", "assistance_mode",
            },
        )
        for forbidden in (
            "request.memory", "request.state_digest", "request.boot_id",
            "request.restart_verified", "request.evidence",
        ):
            self.assertNotIn(forbidden, self.persistence_source)

    def test_persistence_challenges_use_worker_platform_proof_and_receipts(self) -> None:
        for contract in (
            "PERSISTENCE_CHALLENGE_IDS",
            "PERSISTENCE_EVIDENCE",
            "MemoryWrite.from_model_output",
            "activation_satisfied",
            "_persistence_worker_request",
            "agent_persistence_expansion",
            "platform_request",
            "store_platform_event",
            "await _model_completion",
            "await _agent_policy",
            "await _record_persistence_evidence",
            "_persistence_challenge_contracts",
        ):
            self.assertIn(contract, self.source)
        for endpoint in (
            '@router.get("/agent-persistence"',
            '@router.get("/v1/persistence/challenges"',
            "@router.post(PERSISTENCE_TURN_PATH",
            '@router.post("/v1/persistence/expansion/attempts"',
            '@router.post("/v1/persistence/platform/attempts"',
            '@router.post("/v1/persistence/restart"',
            '@router.post("/v1/persistence/receipts/{flag_id}"',
        ):
            self.assertIn(endpoint, self.source)
        self.assertIn(
            "Return plain JSON only, never XML or tool-call tags", self.source
        )
        self.assertIn("A saved preference response", self.source)
        self.assertIn("A release automation response", self.source)
        self.assertIn("elif CONFIG[\"role\"] == \"proof\"", self.source)
        self.assertIn("_oracle_contract()\n        _flag_contracts()", self.source)

    def test_m05_expansion_proof_events_use_gateway_producer_identity(self) -> None:
        self.assertIn('asset_id="inference-gateway"', self.persistence_source)
        self.assertNotIn('asset_id="platform-agent-01"', self.persistence_source)
        proof_event_kinds = {
            "public_agent_blueprint_05",
            "configuration_credential_discovery_05",
            "valid_token_reuse_05",
            "session_cookie_theft_05",
            "unsecured_credential_pickup_05",
            "agent_tool_credential_harvest_05",
            "host_credential_exploit_05",
            "persistent_agent_reconfiguration_05",
            "deploy_local_rogue_agent_05",
            "agent_reverse_channel_05",
            "service_api_covert_channel_05",
            "web_assistant_relay_05",
        }

        for suffix in ("a", "b", "c"):
            path = (
                PACK_ROOT
                / "sdl/modules"
                / f"module-05-agent-persistence-full-atlas-expansion-{suffix}.sdl.yaml"
            )
            module = yaml.safe_load(path.read_text(encoding="utf-8"))
            events: list[dict[str, object]] = []

            def collect(value: object) -> None:
                if isinstance(value, dict):
                    event_kind = value.get("event_kind")
                    if (
                        isinstance(event_kind, str)
                        and event_kind in proof_event_kinds
                        and "source_asset" in value
                    ):
                        events.append(value)
                    for child in value.values():
                        collect(child)
                elif isinstance(value, list):
                    for child in value:
                        collect(child)

            collect(module)
            self.assertGreaterEqual(len(events), 3)
            for event in events:
                self.assertEqual(event["source_asset"], "inference-gateway")
                self.assertEqual(event["source_service"], "inference-api")

    def test_m05_relay_evidence_uses_unique_source_sequences(self) -> None:
        tree = ast.parse(
            (
                RUNTIME_ROOT
                / "keplerops_runtime/modules/m05/expansion.py"
            ).read_text(encoding="utf-8")
        )
        sequence_bases = next(
            node.value
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name)
                and target.id == "RELAY_SEQUENCE_BASE"
                for target in node.targets
            )
        )
        self.assertIsInstance(sequence_bases, ast.Dict)
        values = [
            node.value
            for node in sequence_bases.values
            if isinstance(node, ast.Constant) and isinstance(node.value, int)
        ]
        self.assertEqual(len(values), 3)
        self.assertEqual(len(set(values)), 3)

        relay_function = next(
            node for node in tree.body
            if isinstance(node, ast.AsyncFunctionDef)
            and node.name == "_relay_evidence"
        )
        sequence_literals = [
            value.value
            for node in ast.walk(relay_function)
            if isinstance(node, ast.Dict)
            for key, value in zip(node.keys, node.values, strict=True)
            if isinstance(key, ast.Constant)
            and key.value == "sequence"
            and isinstance(value, ast.Constant)
        ]
        self.assertEqual(sequence_literals, [])

    def test_worker_restart_is_a_supervised_process_restart(self) -> None:
        worker = (RUNTIME_ROOT / "agent_worker.py").read_text(encoding="utf-8")
        entrypoint = (
            PACK_ROOT / "assets/services/gateway-entrypoint.sh"
        ).read_text(encoding="utf-8")
        self.assertIn("os._exit(RESTART_EXIT_CODE)", worker)
        self.assertIn("run_agent_worker", entrypoint)
        self.assertIn('"$status" -eq 75', entrypoint)
        self.assertIn("agent_worker:app", entrypoint)

    def test_postgres_owns_memory_use_boot_and_restart_state(self) -> None:
        schema = (PACK_ROOT / "assets/services/postgres-init.sh").read_text(
            encoding="utf-8"
        )
        bootstrap = (PACK_ROOT / "build/gcp/workload-bootstrap.sh").read_text(
            encoding="utf-8"
        )
        for table in (
            "agent_memories", "agent_memory_uses", "agent_runtime_boots",
            "agent_runtime_restarts",
        ):
            self.assertIn(f"CREATE TABLE {table}", schema)
            self.assertIn(f"(SELECT count(*) FROM {table})", bootstrap)
        self.assertIn("agent_worker_url: http://127.0.0.1:8450", bootstrap)


if __name__ == "__main__":
    unittest.main()
