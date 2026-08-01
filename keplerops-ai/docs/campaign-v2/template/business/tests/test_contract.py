from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from app.models import DecisionEnvelope, Workflow
from app.store import WorkflowStore
from app.workflows import SPECS, WorkflowExecutor


def envelope(workflow: Workflow) -> DecisionEnvelope:
    spec = SPECS[workflow]
    return DecisionEnvelope.model_validate(
        {
            "schema": "keplerops.business-decision/v1",
            "range_id": "template",
            "request_id": f"clean-{workflow.value}",
            "trace_id": f"trace-{workflow.value}",
            "idempotency_key": f"idempotency-{workflow.value}",
            "actor": spec.actor,
            "token_audience": "keplerops-business-adapter",
            "input_digest": "sha256:" + "5" * 64,
            "extraction_digest": "sha256:" + "6" * 64,
            "preprocessing_digest": "sha256:" + "7" * 64,
            "prompt_tool_digest": "sha256:" + "8" * 64,
            "release": {
                "release_id": "sha256:" + "1" * 64,
                "model_digest": "sha256:" + "2" * 64,
                "serving_image_digest": "sha256:" + "3" * 64,
                "policy_digest": "sha256:" + "4" * 64,
                "model_family": spec.model_family,
                "model_version": "clean-v1",
                "signed": True,
            },
            "decision": {
                "workflow": workflow.value,
                "action": spec.action,
                "outcome": spec.outcome,
                "confidence": 0.99,
                "reason_codes": ["clean-control"],
            },
            "clean_control_decision": "approved-clean-control",
        }
    )


class ContractTests(unittest.TestCase):
    def test_all_workflows_have_exact_bounded_contracts(self) -> None:
        executor = WorkflowExecutor(clients=None)  # type: ignore[arg-type]
        self.assertEqual(set(SPECS), set(Workflow))
        for workflow in Workflow:
            self.assertEqual(executor.validate(envelope(workflow)), SPECS[workflow])

    def test_free_form_target_is_rejected(self) -> None:
        payload = envelope(Workflow.FEATURE_CONTROL).model_dump(by_alias=True)
        payload["decision"]["target"] = "another-tenant"
        with self.assertRaises(ValidationError):
            DecisionEnvelope.model_validate(payload)

    def test_wrong_actor_is_denied_before_a_product_call(self) -> None:
        value = envelope(Workflow.SUPPORT_TRIAGE)
        value.actor = "svc-data-steward"
        executor = WorkflowExecutor(clients=None)  # type: ignore[arg-type]
        with self.assertRaises(PermissionError):
            executor.validate(value)

    def test_unapproved_clean_control_is_denied_before_a_product_call(self) -> None:
        value = envelope(Workflow.ACCOUNTING_CREDIT)
        value.clean_control_decision = "unapproved"
        executor = WorkflowExecutor(clients=None)  # type: ignore[arg-type]
        with self.assertRaises(PermissionError):
            executor.validate(value)

    def test_idempotency_claim_returns_original_record(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = WorkflowStore(str(Path(directory) / "audit.sqlite3"))
            value = envelope(Workflow.FEEDBACK_INTAKE)
            workflow_id, existing = store.claim(value)
            self.assertIsNone(existing)
            replay_id, replay = store.claim(value)
            self.assertEqual(replay_id, workflow_id)
            self.assertIsNotNone(replay)
            self.assertEqual(replay["status"], "processing")
            self.assertEqual(
                replay["serving_image_digest"], value.release.serving_image_digest
            )
            self.assertEqual(replay["model_family"], value.release.model_family)
            self.assertEqual(replay["model_version"], value.release.model_version)

    def test_idempotency_key_cannot_be_rebound(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = WorkflowStore(str(Path(directory) / "audit.sqlite3"))
            value = envelope(Workflow.FEATURE_CONTROL)
            store.claim(value)
            value.request_id = "different-request"
            with self.assertRaises(ValueError):
                store.claim(value)

    def test_signature_serialization_is_stable(self) -> None:
        first = envelope(Workflow.INCIDENT_PUBLICATION)
        second = DecisionEnvelope.model_validate_json(
            first.model_dump_json(by_alias=True)
        )
        self.assertEqual(first.canonical_bytes(), second.canonical_bytes())


if __name__ == "__main__":
    unittest.main()
