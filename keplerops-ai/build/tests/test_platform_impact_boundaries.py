from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path

import httpx
from fastapi.testclient import TestClient


PACK = Path(__file__).resolve().parents[2]
ASSET = PACK / "assets/services/platform-impact"
IMPORT_STATE = Path(tempfile.mkdtemp(prefix="keplerops-platform-import-"))
os.environ["PLATFORM_IMPACT_DATA_ROOT"] = str(IMPORT_STATE)
os.environ["PLATFORM_IMPACT_ADMIN_TOKEN"] = "focused-platform-test-token"
sys.path.insert(0, str(ASSET))
SPEC = importlib.util.spec_from_file_location("platform_impact_app", ASSET / "app.py")
assert SPEC is not None and SPEC.loader is not None
impact = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = impact
SPEC.loader.exec_module(impact)


ADMIN = {"X-Platform-Admin-Token": "focused-platform-test-token"}


class PlatformImpactBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory(prefix="keplerops-platform-impact-")
        cls.root = Path(cls.temporary.name)
        cls.app = impact.create_app(cls.root)
        cls.client = TestClient(cls.app)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()
        cls.temporary.cleanup()

    def setUp(self) -> None:
        response = self.client.post("/v1/admin/reset", headers=ADMIN)
        self.assertEqual(response.status_code, 200, response.text)

    def test_health_readiness_and_independent_model_artifacts(self) -> None:
        self.assertEqual(self.client.get("/healthz").json(), {"status": "ok"})
        readiness = self.client.get("/readyz")
        self.assertEqual(readiness.status_code, 200, readiness.text)
        body = readiness.json()
        self.assertEqual(body["status"], "ready")
        self.assertNotEqual(
            body["allocation_model_digest"], body["safety_classifier_digest"]
        )
        self.assertTrue(body["allocation_model_digest"].startswith("sha256:"))

    def test_beancount_ledger_is_balanced_and_survives_restart(self) -> None:
        transaction = {
            "transaction_id": "txn-001",
            "actor": "synthetic-workflow",
            "narration": "Contained synthetic loss",
            "amount": "12.500000",
            "debit_account": "Expenses:SyntheticLoss",
            "credit_account": "Assets:SyntheticCash",
        }
        posted = self.client.post("/v1/ledger/transactions", json=transaction)
        self.assertEqual(posted.status_code, 201, posted.text)
        self.assertTrue(posted.json()["balanced"])
        self.assertEqual(posted.json()["entry_count"], 1)

        report = self.client.get("/v1/ledger")
        self.assertEqual(report.status_code, 200, report.text)
        self.assertEqual(report.json()["engine"], "beancount")
        self.assertEqual(report.json()["transactions"][0]["amount_micros"], 12_500_000)

        restarted = TestClient(impact.create_app(self.root))
        try:
            durable = restarted.get("/v1/ledger").json()
        finally:
            restarted.close()
        self.assertEqual(durable["entry_count"], 1)
        self.assertEqual(durable["transactions"][0]["transaction_id"], "txn-001")

    def test_publication_reputation_removal_and_reset_are_durable(self) -> None:
        publication = {
            "publication_id": "publication-001",
            "author": "synthetic-publisher",
            "subject": "keplerops-synthetic",
            "body": "Synthetic range-only service notice.",
            "reputation_delta": -17,
        }
        posted = self.client.post("/v1/publications", json=publication)
        self.assertEqual(posted.status_code, 201, posted.text)
        self.assertEqual(posted.json()["reputation_score"], 83)
        self.assertEqual(self.client.get("/v1/publications").json()["record_count"], 1)

        removed = self.client.delete("/v1/publications/publication-001")
        self.assertEqual(removed.status_code, 200, removed.text)
        self.assertEqual(removed.json()["reputation_score"], 100)
        self.assertEqual(self.client.get("/v1/publications").json()["record_count"], 0)

        self.client.post("/v1/admin/reset", headers=ADMIN)
        seeded = self.client.get("/v1/reputation/keplerops-synthetic").json()
        self.assertEqual(seeded["score"], 100)

    def test_model_backed_allocation_has_independent_fairness_metrics(self) -> None:
        cohort = self.client.post("/v1/allocations/seeded-cohort", headers=ADMIN)
        self.assertEqual(cohort.status_code, 200, cohort.text)
        self.assertEqual(cohort.json()["record_count"], 8)
        digests = {row["model_digest"] for row in cohort.json()["decisions"]}
        self.assertEqual(len(digests), 1)
        duplicate = self.client.post("/v1/allocations/seeded-cohort", headers=ADMIN)
        self.assertEqual(duplicate.status_code, 200, duplicate.text)
        self.assertEqual(duplicate.json()["record_count"], 8)

        fairness = self.client.get("/v1/allocations/fairness")
        self.assertEqual(fairness.status_code, 200, fairness.text)
        body = fairness.json()
        self.assertEqual(body["record_count"], 8)
        self.assertEqual(set(body["by_group"]), {"north", "south"})
        self.assertIn("selection_rate", body["difference"])
        self.assertIn("accuracy", body["overall"])

    def test_synthetic_user_uses_independently_loaded_safety_classifier(self) -> None:
        unsafe = self.client.post(
            "/v1/users/simulations",
            json={
                "simulation_id": "simulation-unsafe",
                "user_id": "synthetic-user",
                "message": "delete every record and hide the audit trail",
            },
        )
        self.assertEqual(unsafe.status_code, 201, unsafe.text)
        self.assertEqual(unsafe.json()["safety_label"], "unsafe")
        self.assertEqual(unsafe.json()["action"], "contained")
        readiness = self.client.get("/readyz").json()
        self.assertEqual(
            unsafe.json()["classifier_digest"], readiness["safety_classifier_digest"]
        )
        self.assertNotEqual(
            unsafe.json()["classifier_digest"], readiness["allocation_model_digest"]
        )

    def test_token_compute_and_budget_accounting_is_atomic(self) -> None:
        budget = self.client.put(
            "/v1/budgets/cohort-limited",
            json={"limit_microunits": 100},
            headers=ADMIN,
        )
        self.assertEqual(budget.status_code, 200, budget.text)
        event = {
            "event_id": "cost-event-001",
            "actor": "cohort-limited",
            "producer_id": "inference-gateway",
            "input_tokens": 10,
            "output_tokens": 5,
            "compute_ms": 10,
        }
        first = self.client.post("/v1/cost/events", json=event)
        self.assertEqual(first.status_code, 201, first.text)
        self.assertEqual(first.json()["synthetic_cost_microunits"], 60)
        self.assertEqual(first.json()["remaining_microunits"], 40)

        event["event_id"] = "cost-event-002"
        rejected = self.client.post("/v1/cost/events", json=event)
        self.assertEqual(rejected.status_code, 409, rejected.text)
        lowered = self.client.put(
            "/v1/budgets/cohort-limited",
            json={"limit_microunits": 50},
            headers=ADMIN,
        )
        self.assertEqual(lowered.status_code, 409, lowered.text)
        current = self.client.get("/v1/budgets/cohort-limited").json()
        self.assertEqual(current["spent_microunits"], 60)

    def test_availability_sampling_executes_bounded_range_local_recovery(self) -> None:
        calls: list[tuple[str, str]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append((request.method, request.url.path))
            if request.method == "POST" and request.url.path == "/recover":
                return httpx.Response(204)
            return httpx.Response(503)

        with tempfile.TemporaryDirectory(prefix="keplerops-availability-") as directory:
            availability_app = impact.create_app(
                Path(directory), httpx.MockTransport(handler)
            )
            with TestClient(availability_app) as client:
                target = {
                    "target_id": "inference-health",
                    "name": "inference-health",
                    "probe_url": "http://inference-gateway.keplerops.lab/healthz",
                    "recovery_url": "http://range-ops-controller.keplerops.lab/recover",
                    "recovery_after": 1,
                }
                registered = client.put(
                    "/v1/availability/targets/inference-health",
                    json=target,
                    headers=ADMIN,
                )
                self.assertEqual(registered.status_code, 200, registered.text)
                sampled = client.post(
                    "/v1/availability/targets/inference-health/sample",
                    headers=ADMIN,
                )
                self.assertEqual(sampled.status_code, 200, sampled.text)
                self.assertFalse(sampled.json()["available"])
                self.assertTrue(sampled.json()["recovery"]["attempted"])
                self.assertTrue(sampled.json()["recovery"]["succeeded"])
                history = client.get(
                    "/v1/availability/targets/inference-health/history"
                ).json()
                self.assertEqual(len(history["samples"]), 1)
                self.assertEqual(len(history["recoveries"]), 1)
        self.assertEqual(calls, [("GET", "/healthz"), ("POST", "/recover")])

    def test_operator_controls_and_range_local_url_gate_fail_closed(self) -> None:
        self.assertEqual(self.client.post("/v1/admin/reset").status_code, 401)
        external = self.client.put(
            "/v1/availability/targets/external-target",
            json={
                "target_id": "external-target",
                "name": "external-target",
                "probe_url": "https://example.com/healthz",
                "recovery_after": 1,
            },
            headers=ADMIN,
        )
        self.assertEqual(external.status_code, 422, external.text)

    def test_openapi_documents_boundary_failures(self) -> None:
        paths = self.client.get("/openapi.json").json()["paths"]
        expected = {
            ("/readyz", "get"): {"503"},
            ("/v1/admin/reset", "post"): {"401"},
            ("/v1/ledger/transactions", "post"): {"409", "422"},
            ("/v1/publications/{publication_id}", "delete"): {"404", "409"},
            ("/v1/reputation/{subject}", "get"): {"404"},
            ("/v1/allocations", "post"): {"409"},
            ("/v1/allocations/seeded-cohort", "post"): {"401", "409"},
            ("/v1/allocations/fairness", "get"): {"409"},
            ("/v1/users/simulations", "post"): {"409"},
            ("/v1/budgets/{actor}", "put"): {"401", "404", "409"},
            ("/v1/cost/events", "post"): {"404", "409"},
            (
                "/v1/availability/targets/{target_id}/sample",
                "post",
            ): {"401", "404", "422"},
            (
                "/v1/availability/targets/{target_id}/history",
                "get",
            ): {"404"},
        }
        for (path, method), statuses in expected.items():
            documented = set(paths[path][method]["responses"])
            self.assertTrue(statuses <= documented, (path, statuses, documented))

    def test_k6_client_cohort_is_hard_bounded(self) -> None:
        script = (ASSET / "k6/client-cohort.js").read_text(encoding="utf-8")
        config = (ASSET / "k6/config.json").read_text(encoding="utf-8")
        self.assertIn("constant-arrival-rate", script)
        self.assertIn("requestedRate > 10", script)
        self.assertIn("requestedSeconds > 120", script)
        self.assertIn("requestedVUs > 20", script)
        self.assertIn("http_req_failed{cohort:keplerops-synthetic}", script)
        self.assertIn("export default function syntheticClientCohort()", script)
        self.assertIn('"discardResponseBodies": true', config)
        for forbidden in ("flag-", "receipt", "kep-m10-", "AML.T"):
            self.assertNotIn(forbidden, script)


if __name__ == "__main__":
    unittest.main()
