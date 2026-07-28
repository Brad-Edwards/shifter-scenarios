from __future__ import annotations

import importlib.util
import json
import sys
import time
import unittest
from pathlib import Path

from .runtime_source import proof_source, runtime_source

PACK_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_ROOT = PACK_ROOT / "assets" / "services" / "keplerops-runtime"
RECEIPT_ROOT = PACK_ROOT / "ctfd" / "plugins" / "keplerops_oracle_flags"
sys.path.insert(0, str(PACK_ROOT))
from aces_contract import (  # noqa: E402
    oracle_projection,
    research_telemetry_contract,
    telemetry_projection,
)


def load_module(name: str, path: Path):
    sys.path.insert(0, str(RUNTIME_ROOT))
    sys.path.insert(0, str(RECEIPT_ROOT))
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            raise AssertionError(f"unable to load {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)
        sys.path.pop(0)


class RuntimeDomainTests(unittest.TestCase):
    def test_no_content_routes_use_an_empty_response_class(self) -> None:
        source = runtime_source(RUNTIME_ROOT)
        self.assertEqual(source.count("status_code=204, response_class=Response"), 3)
        self.assertEqual(source.count("return Response(status_code=204)"), 3)
        self.assertIn("def browser_logout(response: Response) -> Response:", source)

    def test_proof_role_exposes_participant_receipt_submission_without_key_material(self) -> None:
        source = proof_source(RUNTIME_ROOT)
        self.assertIn('@router.post("/v1/receipts/{flag_id}/verify"', source)
        self.assertIn("verify_penr1_receipt(", source)
        self.assertIn("class ReceiptVerificationRequest", source)

    def test_session_claims_are_exact_bounded_and_namespaced(self) -> None:
        domain = load_module("keplerops_domain", RUNTIME_ROOT / "domain.py")
        now = int(time.time())
        claims = domain.SessionClaims.from_mapping(
            {
                "range_instance": "range-355-a1",
                "participant": "participant-01",
                "roles": ["participant"],
                "expires_at": now + 300,
            },
            now=now,
        )
        self.assertEqual(
            claims,
            domain.SessionClaims(
                range_instance="range-355-a1",
                participant="participant-01",
                roles=("participant",),
                expires_at=now + 300,
            ),
        )

        invalid = (
            {"range_instance": "range-355-a1", "participant": "participant-01", "roles": ["participant"], "expires_at": now - 1},
            {"range_instance": "../escape", "participant": "participant-01", "roles": ["participant"], "expires_at": now + 1},
            {"range_instance": "range-355-a1", "participant": "participant-01", "roles": ["participant"], "expires_at": now + 1, "admin": True},
        )
        for payload in invalid:
            with self.subTest(payload=payload):
                with self.assertRaises(domain.DomainError):
                    domain.SessionClaims.from_mapping(payload, now=now)

    def test_signed_approval_identity_has_a_separate_strict_namespace(self) -> None:
        domain = load_module("keplerops_domain_approval", RUNTIME_ROOT / "domain.py")
        now = int(time.time())
        signer = domain.ApprovalSigner.from_mapping(
            {
                "range_instance": "range-355-a1",
                "participant": "release.manager",
                "roles": ["release_manager", "default-roles-keplerops"],
                "expires_at": now + 300,
            },
            expected_range="range-355-a1",
            now=now,
        )
        self.assertEqual(signer.participant, "release.manager")
        self.assertEqual(
            signer.roles, ("release_manager", "default-roles-keplerops")
        )

        invalid = (
            {
                "range_instance": "other-range",
                "participant": "release.manager",
                "roles": ["release_manager"],
                "expires_at": now + 300,
            },
            {
                "range_instance": "range-355-a1",
                "participant": "../release.manager",
                "roles": ["release_manager"],
                "expires_at": now + 300,
            },
            {
                "range_instance": "range-355-a1",
                "participant": "release.manager",
                "roles": ["release.manager"],
                "expires_at": now + 300,
            },
            {
                "range_instance": "range-355-a1",
                "participant": "release.manager",
                "roles": ["release_manager", "release_manager"],
                "expires_at": now + 300,
            },
        )
        for payload in invalid:
            with self.subTest(payload=payload):
                with self.assertRaises(domain.DomainError):
                    domain.ApprovalSigner.from_mapping(
                        payload, expected_range="range-355-a1", now=now
                    )

        with self.assertRaises(domain.DomainError):
            domain.SessionClaims.from_mapping(
                {
                    "range_instance": "range-355-a1",
                    "participant": "release.manager",
                    "roles": ["release_manager"],
                    "expires_at": now + 300,
                },
                now=now,
            )

    def test_telemetry_rejects_raw_ai_and_unknown_fields(self) -> None:
        domain = load_module("keplerops_domain_telemetry", RUNTIME_ROOT / "domain.py")
        allowed = {
            "actor_role", "asset_id", "digest", "event_kind", "object_id",
            "outcome_id", "participant", "range_instance", "status", "timestamp",
        }
        event = domain.EvidenceEvent.from_mapping(
            {
                "actor_role": "participant",
                "asset_id": "inference-gateway",
                "digest": "sha256:" + "a" * 64,
                "event_kind": "model_decision_evasion",
                "object_id": "evaluation-v1",
                "outcome_id": "model-evasion",
                "participant": "participant-01",
                "range_instance": "range-355-a1",
                "status": "passed",
                "timestamp": 1_786_000_000,
            },
            safe_fields=allowed,
        )
        self.assertEqual(
            event.values,
            {
                "actor_role": "participant",
                "asset_id": "inference-gateway",
                "digest": "sha256:" + "a" * 64,
                "event_kind": "model_decision_evasion",
                "object_id": "evaluation-v1",
                "outcome_id": "model-evasion",
                "participant": "participant-01",
                "range_instance": "range-355-a1",
                "status": "passed",
                "timestamp": 1_786_000_000,
            },
        )

        for forbidden in ("prompt", "completion", "receipt", "flag", "proof"):
            payload = dict(event.values)
            payload[forbidden] = "sensitive"
            with self.subTest(forbidden=forbidden):
                with self.assertRaises(domain.DomainError):
                    domain.EvidenceEvent.from_mapping(payload, safe_fields=allowed)

    def test_research_contract_is_separate_from_oracle_and_exact(self) -> None:
        domain = load_module("keplerops_domain_research_contract", RUNTIME_ROOT / "domain.py")
        research = research_telemetry_contract(PACK_ROOT)

        contract = domain.ResearchContract.from_mapping(research)

        self.assertEqual(contract.schema_version, 1)
        self.assertEqual(contract.authority, "observational_fail_open")
        self.assertEqual(contract.export_namespace, ("study_run_id", "session_id"))
        self.assertNotIn("prompt", contract.operational_fields)
        self.assertIn("prompt", contract.content_fields)
        with self.assertRaises(domain.DomainError):
            domain.ResearchContract.from_mapping({**research, "oracle_award": True})

    def test_research_pseudonyms_are_keyed_generation_bound_and_value_sparse(self) -> None:
        domain = load_module("keplerops_domain_research_ids", RUNTIME_ROOT / "domain.py")
        key = b"research-pseudonym-key-for-tests"

        first = domain.derive_research_context(
            key=key,
            range_instance="range-405-a1",
            participant="participant-01",
            reset_generation=4,
        )
        repeat = domain.derive_research_context(
            key=key,
            range_instance="range-405-a1",
            participant="participant-01",
            reset_generation=4,
        )
        next_generation = domain.derive_research_context(
            key=key,
            range_instance="range-405-a1",
            participant="participant-01",
            reset_generation=5,
        )

        self.assertEqual(first, repeat)
        self.assertEqual(first.study_run_id, next_generation.study_run_id)
        self.assertNotEqual(first.session_id, next_generation.session_id)
        serialized = json.dumps(first._asdict())
        self.assertNotIn("range-405-a1", serialized)
        self.assertNotIn("participant-01", serialized)

    def test_research_observation_rejects_content_identity_and_unknown_fields(self) -> None:
        domain = load_module("keplerops_domain_research_event", RUNTIME_ROOT / "domain.py")
        research = research_telemetry_contract(PACK_ROOT)
        contract = domain.ResearchContract.from_mapping(research)
        payload = {
            "event_name": "objective.attempted",
            "occurred_at": 1_786_000_000_000_000_000,
            "module_id": "module-02-model-evasion",
            "source_sequence": 7,
            "status": "recorded",
            "trace_id": "a" * 32,
        }

        observation = domain.ResearchObservation.from_mapping(
            payload,
            contract=contract,
            source_id="inference-gateway",
        )
        self.assertEqual(observation.values, payload)
        for forbidden in ("prompt", "participant", "ip_address", "unknown"):
            invalid = dict(payload, **{forbidden: "sensitive"})
            with self.subTest(forbidden=forbidden):
                with self.assertRaises(domain.DomainError):
                    domain.ResearchObservation.from_mapping(
                        invalid,
                        contract=contract,
                        source_id="inference-gateway",
                    )

    def test_adversarial_observation_requires_bounded_method_and_perturbation(self) -> None:
        domain = load_module("keplerops_domain_adversarial_observation", RUNTIME_ROOT / "domain.py")
        contract = domain.ResearchContract.from_mapping(
            research_telemetry_contract(PACK_ROOT)
        )
        payload = {
            "event_name": "objective.attempted",
            "occurred_at": 1_786_000_000_000_000_000,
            "module_id": "module-06-adversarial-input",
            "challenge_id": "kep-m06-c",
            "source_sequence": 7,
            "status": "recorded",
            "trace_id": "a" * 32,
            "method_class": "black_box",
            "perturbation_count": 12,
        }

        observation = domain.ResearchObservation.from_mapping(
            payload,
            contract=contract,
            source_id="inference-gateway",
        )
        self.assertEqual(observation.values, payload)
        for invalid in (
            {**payload, "method_class": "white_box"},
            {**payload, "perturbation_count": -1},
            {**payload, "perturbation_count": True},
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(domain.DomainError):
                    domain.ResearchObservation.from_mapping(
                        invalid,
                        contract=contract,
                        source_id="inference-gateway",
                    )

    def test_model_backdoor_observation_is_bounded_and_identity_sparse(self) -> None:
        domain = load_module("keplerops_domain_backdoor_observation", RUNTIME_ROOT / "domain.py")
        contract = domain.ResearchContract.from_mapping(
            research_telemetry_contract(PACK_ROOT)
        )
        payload = {
            "event_name": "attempt.completed",
            "occurred_at": 1_786_000_000_000_000_000,
            "module_id": "module-09-model-backdoor",
            "challenge_id": "kep-m09-f",
            "source_sequence": 9,
            "status": "passed",
            "trace_id": "a" * 32,
            "method_class": "policy-bypass",
            "trigger_rate": 1.0,
            "trigger_confidence": 0.75,
            "clean_accuracy": 1.0,
            "policy_allowed": True,
            "policy_confused": True,
            "policy_reason": "model-card-scope-confusion",
            "registry_alias": "production",
            "prior_model_version": "none",
            "registry_model_version": "1",
            "actor_authorized": False,
            "evaluation_count": 9,
        }

        observation = domain.ResearchObservation.from_mapping(
            payload,
            contract=contract,
            source_id="inference-gateway",
        )

        self.assertEqual(observation.values, payload)
        for invalid in (
            {**payload, "trigger_rate": 1.1},
            {**payload, "policy_confused": "yes"},
            {**payload, "policy_reason": "participant supplied"},
            {**payload, "registry_model_version": "latest"},
            {**payload, "approval_actor": "ml.engineer"},
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(domain.DomainError):
                    domain.ResearchObservation.from_mapping(
                        invalid,
                        contract=contract,
                        source_id="inference-gateway",
                    )

    def test_research_runtime_config_requires_exact_independent_signals(self) -> None:
        domain = load_module("keplerops_domain_research_runtime_config", RUNTIME_ROOT / "domain.py")
        signals = {
            "prompt": False,
            "completion": False,
            "tool_call": False,
            "tool_result": False,
            "terminal_command": False,
            "terminal_input": False,
            "terminal_output": False,
            "process_lifecycle": False,
            "browser_interaction": False,
            "notebook_content": False,
            "file_content": False,
            "workflow_state": False,
            "artifact_content": False,
            "http_body": False,
        }

        config = domain.ResearchRuntimeConfig.from_values(
            endpoint="https://telemetry-proof-01.keplerops.lab:4318",
            queue_capacity=256,
            capture_signals=signals,
        )
        self.assertEqual(config.queue_capacity, 256)
        self.assertEqual(config.capture_signals, signals)

        invalid = (
            {**signals, "all": True},
            {key: False for key in signals if key != "prompt"},
            {**signals, "prompt": "yes"},
        )
        for payload in invalid:
            with self.subTest(payload=payload):
                with self.assertRaises(domain.DomainError):
                    domain.ResearchRuntimeConfig.from_values(
                        endpoint="https://telemetry-proof-01.keplerops.lab:4318",
                        queue_capacity=256,
                        capture_signals=payload,
                    )
        for endpoint, capacity in (
            ("http://telemetry-proof-01.keplerops.lab:4318", 256),
            ("https://attacker.invalid:4318", 256),
            ("https://telemetry-proof-01.keplerops.lab:4318", 0),
        ):
            with self.subTest(endpoint=endpoint, capacity=capacity):
                with self.assertRaises(domain.DomainError):
                    domain.ResearchRuntimeConfig.from_values(
                        endpoint=endpoint,
                        queue_capacity=capacity,
                        capture_signals=signals,
                    )

    def test_receipt_issuer_reuses_penr1_and_binds_reset_generation(self) -> None:
        domain = load_module("keplerops_domain_receipt", RUNTIME_ROOT / "domain.py")
        receipt = load_module("keplerops_receipt_contract", RECEIPT_ROOT / "receipt.py")
        now = 1_786_000_000
        contract = {
            "flag_id": "flag-model-evasion",
            "outcome": "model-evasion",
            "evidence": "ev-model-evasion",
        }
        binding = {
            "range_instance": "range-355-a1",
            "participant": "participant-01",
            "reset_generation": 4,
        }
        token = domain.issue_penr1_receipt(
            contract=contract,
            binding=binding,
            signing_key=b"unit-test-signing-key",
            now=now,
            ttl_seconds=300,
        )
        self.assertTrue(
            receipt.verify_receipt(
                token,
                contract=contract,
                binding=binding,
                verification_key=b"unit-test-signing-key",
                now=now + 1,
            )
        )
        stale = dict(binding, reset_generation=5)
        self.assertFalse(
            receipt.verify_receipt(
                token,
                contract=contract,
                binding=stale,
                verification_key=b"unit-test-signing-key",
                now=now + 1,
            )
        )

    def test_receipt_submission_fails_closed_after_reset_generation_changes(self) -> None:
        domain = load_module("keplerops_domain_verify_receipt", RUNTIME_ROOT / "domain.py")
        now = 1_786_000_000
        contract = {
            "flag_id": "flag-model-evasion",
            "outcome": "model-evasion",
            "evidence": "ev-model-evasion",
        }
        binding = {
            "range_instance": "range-356-a1",
            "participant": "participant-01",
            "reset_generation": 4,
        }
        key = b"unit-test-signing-key"
        token = domain.issue_penr1_receipt(
            contract=contract,
            binding=binding,
            signing_key=key,
            now=now,
            ttl_seconds=300,
        )

        self.assertTrue(domain.verify_penr1_receipt(
            token=token,
            contract=contract,
            binding=binding,
            verification_key=key,
            now=now + 1,
        ))
        self.assertFalse(domain.verify_penr1_receipt(
            token=token,
            contract=contract,
            binding={**binding, "reset_generation": 5},
            verification_key=key,
            now=now + 1,
        ))
        self.assertFalse(domain.verify_penr1_receipt(
            token=token + "corrupt",
            contract=contract,
            binding=binding,
            verification_key=key,
            now=now + 1,
        ))

    def test_oracle_contract_requires_the_canonical_evidence_chain(self) -> None:
        domain = load_module("keplerops_domain_oracle", RUNTIME_ROOT / "domain.py")
        objectives = oracle_projection(PACK_ROOT)
        telemetry = telemetry_projection(PACK_ROOT)
        contract = domain.OracleContract.from_mappings(objectives, telemetry)
        self.assertEqual(
            contract.required_evidence("model-extraction"),
            ("ev-model-secrets", "ev-teacher-corpus", "ev-proxy-fidelity"),
        )
        self.assertEqual(
            contract.evidence_for_event("proxy_fidelity_verdict"),
            "ev-proxy-fidelity",
        )
        self.assertFalse(
            contract.satisfied("model-extraction", {"ev-model-secrets", "ev-teacher-corpus"})
        )
        self.assertTrue(
            contract.satisfied(
                "model-extraction",
                {"ev-model-secrets", "ev-teacher-corpus", "ev-proxy-fidelity"},
            )
        )

    def test_oracle_qualifies_item_evidence_without_widening_the_outcome_gate(self) -> None:
        domain = load_module("keplerops_domain_item_evidence", RUNTIME_ROOT / "domain.py")
        objectives = oracle_projection(PACK_ROOT)
        telemetry = telemetry_projection(PACK_ROOT)
        contract = domain.OracleContract.from_mappings(objectives, telemetry)
        now = 1_786_000_000
        values = {
            "actor_role": "participant",
            "asset_id": "inference-gateway",
            "digest": "sha256:" + "a" * 64,
            "event_kind": "agent_tool_proposal_denied",
            "object_id": "disable_guardrail",
            "outcome_id": "agent-control",
            "participant": "participant-01",
            "range_instance": "range-355-a1",
            "stage": "policy-denied",
            "status": "passed",
            "timestamp": now,
        }
        event = domain.EvidenceEvent.from_mapping(values, safe_fields=set(values))

        self.assertEqual(
            contract.qualify_event(
                event,
                producer_asset="inference-gateway",
                submitted_generation=4,
                current_generation=4,
                now=now,
            ),
            ("ev-agent-proposal-denied", now + 3600),
        )
        self.assertEqual(contract.required_evidence("agent-control"), ("ev-agent-control",))
        self.assertFalse(contract.satisfied("agent-control", {"ev-agent-proposal-denied"}))

    def test_oracle_qualifies_exact_fresh_producer_evidence_only(self) -> None:
        domain = load_module("keplerops_domain_qualify", RUNTIME_ROOT / "domain.py")
        objectives = oracle_projection(PACK_ROOT)
        telemetry = telemetry_projection(PACK_ROOT)
        contract = domain.OracleContract.from_mappings(objectives, telemetry)
        now = 1_786_000_000
        values = {
            "actor_role": "participant",
            "asset_id": "inference-gateway",
            "digest": "sha256:" + "a" * 64,
            "event_kind": "model_decision_evasion",
            "object_id": "evaluation-v1",
            "outcome_id": "model-evasion",
            "record_count": 2,
            "participant": "participant-01",
            "range_instance": "range-355-a1",
            "status": "passed",
            "timestamp": now,
        }
        event = domain.EvidenceEvent.from_mapping(values, safe_fields=set(values))
        self.assertEqual(
            contract.qualify_event(
                event,
                producer_asset="inference-gateway",
                submitted_generation=4,
                current_generation=4,
                now=now,
            ),
            ("ev-model-evasion", now + 3600),
        )
        for producer, generation, timestamp, status in (
            ("guardrail-policy", 4, now, "passed"),
            ("inference-gateway", 3, now, "passed"),
            ("inference-gateway", 4, now - 3601, "passed"),
            ("inference-gateway", 4, now, "recorded"),
        ):
            invalid = domain.EvidenceEvent.from_mapping(
                {**values, "timestamp": timestamp, "status": status},
                safe_fields=set(values),
            )
            with self.subTest(producer=producer, generation=generation, status=status):
                with self.assertRaises(domain.DomainError):
                    contract.qualify_event(
                        invalid,
                        producer_asset=producer,
                        submitted_generation=generation,
                        current_generation=4,
                        now=now,
                    )

    def test_runtime_gate_blocks_resetting_and_cross_generation_requests(self) -> None:
        domain = load_module("keplerops_domain_gate", RUNTIME_ROOT / "domain.py")
        domain.RuntimeGate.from_values("ready", 4).require_ready(4)
        for status, live, configured in (("resetting", 4, 4), ("ready", 5, 4)):
            with self.subTest(status=status, live=live):
                with self.assertRaises(domain.DomainError):
                    domain.RuntimeGate.from_values(status, live).require_ready(configured)

    def test_quick_objectives_require_behavioral_evidence_not_any_response(self) -> None:
        domain = load_module("keplerops_domain_quick", RUNTIME_ROOT / "domain.py")
        self.assertFalse(domain.quick_objective_passed("agent-control", control="", candidate="ordinary answer"))
        tool_call = '{"tool":"rotate_policy","arguments":{"mode":"relaxed"}}'
        self.assertFalse(domain.quick_objective_passed("agent-control", control="", candidate=tool_call))
        self.assertTrue(domain.quick_objective_passed("agent-control", control="", candidate=tool_call, action_executed=True))
        self.assertFalse(domain.quick_objective_passed("model-evasion", control='{"decision":"deny"}', candidate='{"decision":"deny"}'))
        self.assertTrue(domain.quick_objective_passed("model-evasion", control='{"decision":"deny"}', candidate='{"decision":"allow"}'))
        self.assertTrue(domain.quick_objective_passed("model-evasion", control='{"decision":"deny"}\n}', candidate='{"decision":"allow"}\n'))
        self.assertTrue(domain.quick_objective_passed("model-evasion", control='```json\n{"decision":"deny"}\n```', candidate='{"decision":"allow"}'))
        with self.assertRaises(domain.DomainError):
            domain.quick_objective_passed("unknown", control="", candidate="")


if __name__ == "__main__":
    unittest.main()
