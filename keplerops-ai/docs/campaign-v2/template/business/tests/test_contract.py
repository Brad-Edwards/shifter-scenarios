from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from typing import Any
from unittest.mock import patch

import httpx
from pydantic import ValidationError

from app.clients import NativeClients
from app.config import Settings
from app.models import BusinessInput, DecisionEnvelope, NativeEffect, Workflow
from app.store import WorkflowStore
from app.workflows import SPECS, WorkflowExecutor


def business_input(workflow: Workflow) -> BusinessInput:
    return BusinessInput.model_validate(
        {
            "schema": "keplerops.business-input/v1",
            "request_id": f"request-{workflow.value}",
            "trace_id": f"trace-{workflow.value}",
            "idempotency_key": f"idempotency-{workflow.value}",
            "subject": f"Orion {workflow.value} review",
            "description": (
                "KeplerOps AI Systems has received a documented business request "
                "with the required owner approval and supporting records."
            ),
            "facts": {"owner": "Platform Operations", "state": "approved"},
        }
    )


class FakeClients:
    def __init__(self) -> None:
        self.settings = Settings()
        self.label = "ReleaseApprove"
        self.assistant_calls = 0
        self.risk_calls = 0

    def assistant_infer(
        self,
        prompt: str,
        actor: str,
        conversation_id: str,
        request_id: str,
        trace_id: str,
    ) -> dict[str, Any]:
        self.assistant_calls += 1
        return {
            "model": "orion-assistant",
            "model_version": "assistant-v1",
            "inference_id": f"assistant-{self.assistant_calls}",
            "response": "The approved records support the requested disposition.",
            "citations": ["workhub-record-1"],
            "raw_digest": "sha256:" + "a" * 64,
        }

    def release_risk_predict(
        self, text: str, request_id: str, trace_id: str
    ) -> dict[str, Any]:
        self.risk_calls += 1
        labels = [
            "ReleaseApprove",
            "ReleaseHold",
            "PartnerIntake",
            "EntitlementReview",
            "SecurityAdvisory",
            "SupportEscalation",
            "ResearchReview",
            "PrivacySafety",
        ]
        index = labels.index(self.label)
        probabilities = [0.01] * len(labels)
        probabilities[index] = 0.93
        return {
            "model": "orion-release-risk",
            "model_version": "release-2",
            "inference_id": f"risk-{self.risk_calls}",
            "label": self.label,
            "class_index": index,
            "probabilities": probabilities,
            "raw_digest": "sha256:" + "b" * 64,
        }


def envelope(workflow: Workflow) -> DecisionEnvelope:
    clients = FakeClients()
    clients.label = SPECS[workflow].expected_label
    return WorkflowExecutor(clients).derive(workflow, business_input(workflow))  # type: ignore[arg-type]


class ContractTests(unittest.TestCase):
    def test_release_risk_client_binds_active_model_and_probability_vector(
        self,
    ) -> None:
        labels = [
            "ReleaseApprove",
            "ReleaseHold",
            "PartnerIntake",
            "EntitlementReview",
            "SecurityAdvisory",
            "SupportEscalation",
            "ResearchReview",
            "PrivacySafety",
        ]
        digest = "c" * 64
        metadata = httpx.Response(
            200,
            json={
                "name": "orion-release-risk",
                "labels": labels,
                "model_sha256": digest,
            },
            request=httpx.Request("GET", "http://orion/v1/models/orion-release-risk"),
        )
        predicted = httpx.Response(
            200,
            json={
                "model_name": "orion-release-risk",
                "model_version": 2,
                "model_sha256": digest,
                "predictions": [
                    {
                        "class_index": 4,
                        "label": "SecurityAdvisory",
                        "probabilities": [
                            0.01,
                            0.01,
                            0.01,
                            0.01,
                            0.93,
                            0.01,
                            0.01,
                            0.01,
                        ],
                    }
                ],
            },
            request=httpx.Request(
                "POST", "http://orion/v1/models/orion-release-risk:predict"
            ),
        )
        with tempfile.TemporaryDirectory() as directory:
            settings = replace(
                Settings(),
                evidence_directory=directory,
                release_risk_url="http://orion",
                release_risk_model_digest=f"sha256:{digest}",
            )
            with (
                patch("app.clients.httpx.get", return_value=metadata) as get,
                patch("app.clients.httpx.post", return_value=predicted) as post,
            ):
                result = NativeClients(settings).release_risk_predict(
                    "Publish the coordinated Orion security advisory.",
                    "request-advisory",
                    "trace-advisory",
                )
        self.assertEqual(get.call_args.kwargs["headers"]["X-Request-ID"], "request-advisory")
        self.assertEqual(post.call_args.kwargs["headers"]["X-Keplerops-Trace-ID"], "trace-advisory")
        self.assertRegex(post.call_args.kwargs["headers"]["traceparent"], r"^00-[0-9a-f]{32}-[0-9a-f]{16}-01$")
        self.assertEqual(result["label"], "SecurityAdvisory")
        self.assertEqual(result["probabilities"][4], 0.93)
        self.assertEqual(result["model_version"], "release-2")

    def test_all_workflows_derive_exact_bounded_contracts(self) -> None:
        self.assertEqual(set(SPECS), set(Workflow))
        for workflow in Workflow:
            clients = FakeClients()
            clients.label = SPECS[workflow].expected_label
            executor = WorkflowExecutor(clients)  # type: ignore[arg-type]
            value = executor.derive(workflow, business_input(workflow))
            self.assertEqual(executor.validate(value), SPECS[workflow])
            self.assertEqual(value.inference.decision_label, clients.label)
            self.assertEqual(value.decision.confidence, 0.93)
            self.assertEqual(
                clients.assistant_calls, int(SPECS[workflow].assistant_context)
            )

    def test_business_input_cannot_supply_action_or_target(self) -> None:
        payload = business_input(Workflow.FEATURE_CONTROL).model_dump(by_alias=True)
        payload["action"] = "unleash:set"
        payload["target"] = "another-tenant"
        with self.assertRaises(ValidationError):
            BusinessInput.model_validate(payload)

    def test_wrong_actor_is_denied_before_a_product_call(self) -> None:
        value = envelope(Workflow.SUPPORT_TRIAGE)
        value.actor = "svc-data-steward"
        executor = WorkflowExecutor(clients=None)  # type: ignore[arg-type]
        with self.assertRaises(PermissionError):
            executor.validate(value)

    def test_unexpected_model_label_stops_before_a_product_call(self) -> None:
        clients = FakeClients()
        clients.label = "ReleaseHold"
        executor = WorkflowExecutor(clients)  # type: ignore[arg-type]
        with self.assertRaises(PermissionError):
            executor.derive(
                Workflow.ACCOUNTING_CREDIT,
                business_input(Workflow.ACCOUNTING_CREDIT),
            )

    def test_idempotency_claim_returns_original_audit_record(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = WorkflowStore(str(Path(directory) / "audit.sqlite3"))
            value = envelope(Workflow.FEEDBACK_INTAKE)
            workflow_id, existing = store.claim(value, "signature")
            self.assertIsNone(existing)
            replay_id, replay = store.claim(value, "signature")
            self.assertEqual(replay_id, workflow_id)
            self.assertIsNotNone(replay)
            self.assertEqual(replay["status"], "processing")
            self.assertEqual(
                json.loads(replay["inference_json"]), value.inference.model_dump()
            )
            self.assertTrue(store.source_matches(replay, value.source))

    def test_idempotency_key_cannot_be_rebound(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = WorkflowStore(str(Path(directory) / "audit.sqlite3"))
            value = envelope(Workflow.FEATURE_CONTROL)
            store.claim(value, "signature")
            value.request_id = "different-request"
            with self.assertRaises(ValueError):
                store.claim(value, "signature")

    def test_completed_result_exposes_causal_audit_chain(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = WorkflowStore(str(Path(directory) / "audit.sqlite3"))
            value = envelope(Workflow.FEATURE_CONTROL)
            workflow_id, _ = store.claim(value, "a" * 64)
            result = store.complete(
                workflow_id,
                {
                    "allow": True,
                    "decision_id": f"feature-control:{value.request_id}",
                    "allowed_action": value.decision.action,
                },
                NativeEffect(
                    target_system="unleash",
                    target_object_id="orion-canary-assistant",
                    native_request_ids=[value.request_id],
                    native_response_ids=["unleash-response"],
                    before_state={"enabled": False},
                    after_state={"enabled": True},
                ),
            )
            self.assertEqual(result.input_digest, value.input_digest)
            self.assertEqual(result.decision, value.decision)
            self.assertEqual(result.inference, value.inference)
            self.assertTrue(result.policy_decision["allow"])
            self.assertEqual(result.decision_signature, "a" * 64)

    def test_signature_serialization_is_stable(self) -> None:
        first = envelope(Workflow.INCIDENT_PUBLICATION)
        second = DecisionEnvelope.model_validate_json(
            first.model_dump_json(by_alias=True)
        )
        self.assertEqual(first.canonical_bytes(), second.canonical_bytes())


if __name__ == "__main__":
    unittest.main()
