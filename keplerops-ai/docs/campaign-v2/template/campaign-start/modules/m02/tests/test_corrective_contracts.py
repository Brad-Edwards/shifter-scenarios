#!/usr/bin/env python3
"""Static regression contracts for the M02 participant-equivalence corrections."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


MODULE = Path(__file__).resolve().parents[1]
CAMPAIGN_START = MODULE.parents[1]
M01 = CAMPAIGN_START / "modules" / "m01"


class M02CorrectiveContracts(unittest.TestCase):
    def test_worker_health_is_last_success_not_loop_liveness(self) -> None:
        business = (MODULE / "runtime" / "business_worker.py").read_text()
        recipient = (MODULE / "runtime" / "recipient-worker.py").read_text()
        self.assertLess(business.index("business_once()"), business.index("heartbeat()", business.index("def main()")))
        self.assertLess(recipient.index("poll_once()", recipient.index("def main()")), recipient.index("HEARTBEAT.touch()", recipient.index("def main()")))
        self.assertIn("last-error.json", business)
        self.assertIn("last-error.json", recipient)

    def test_m02_l_uses_native_identity_and_write_once_evidence(self) -> None:
        source = (MODULE / "runtime" / "business_worker.py").read_text()
        for required in (
            "devpi_upload_evidence(", 'entry.get("what") == "upload"', 'item["owner_id"]',
            'item["file_id"]', "forgejo_create_once(",
            'accepted_path = f"accepted/{identifier}-{wheel_sha}.json"',
            'write_once_json(STATE_ROOT / "earned" / "m01-h-package-consumer.json"',
        ):
            self.assertIn(required, source)
        self.assertNotIn('"external_contributor": "cinder.operator"', source)

    def test_m01_consumes_exact_entitlement_commit_blob_and_bytes(self) -> None:
        source = (M01 / "runtime" / "review_workers.py").read_text()
        compose = (M01 / "compose.overlay.yaml").read_text()
        for required in (
            'Path(env("M02_ENTITLEMENT_PATH"))', 'params={"ref": commit}',
            "blob_sha != blob", 'entitlement.get("accepted_record_sha256")',
            'entitlement.get("source_set_sha256")',
        ):
            self.assertIn(required, source)
        self.assertIn("./state/campaign-start/m02/earned:/var/lib/keplerops/m02-earned:ro", compose)
        self.assertNotIn('params={"ref": "main"}', source[source.index("def accepted_package_record"):source.index("def run_helper")])

    def test_controls_are_joined_to_the_accepted_attempt(self) -> None:
        source = (MODULE / "runtime" / "business_worker.py").read_text()
        validator = (MODULE / "validate.sh").read_text()
        for required in ("exact-wheel-wrong-signature", "caller-claimed-output", "source_set_sha256", "single_mutation"):
            self.assertIn(required, source)
            self.assertIn(required, validator)
        self.assertIn("validate_package_request(claimed_request)", source)
        m02_l = validator[validator.index("kep-m02-l)"):validator.index("kep-m02-m)")]
        self.assertNotIn("assert_native_rejection", m02_l)
        self.assertNotIn("qualified_rejection", m02_l)

    def test_reset_is_attempt_owned_and_preserves_submitted_enterprise_state(self) -> None:
        runtime = (MODULE / "runtime" / "reset_runtime.py").read_text()
        wrapper = (MODULE / "reset.sh").read_text()
        self.assertIn("reset_runtime.py <operation-id> <attempt-id>", runtime)
        self.assertIn('value.get("status") == "completed"', runtime)
        self.assertIn("refusing to delete non-worker-owned WebDAV path", runtime)
        self.assertIn('dav_delete(str(control["native_result_path"]))', runtime)
        self.assertIn('"${OPERATION}" "${ATTEMPT_ID}"', wrapper)
        for forbidden in ("devpi remove", "delete_rejected_package", "QdrantClient", "ZAMMAD_URL"):
            self.assertNotIn(forbidden, runtime)

    def test_visible_results_use_explicit_schemas_without_meta_vocabulary(self) -> None:
        source = (MODULE / "runtime" / "business_worker.py").read_text()
        procedure = (MODULE / "payloads" / "package-review-procedure.md").read_text().lower()
        self.assertIn("PUBLIC_RESULT_FIELDS", source)
        self.assertIn("if key in public_fields", source)
        public_block = source[source.index("PUBLIC_RESULT_FIELDS"):source.index("def scan_model_manifests")]
        for forbidden in ("participant_request_id", "participant_request_sha256", "native_attempt_id", "negative_control"):
            self.assertNotIn(forbidden, public_block)
        for forbidden in ("result flag", "claimed session", "participant"):
            self.assertNotIn(forbidden, procedure)

    def test_operation_contract_is_unchanged(self) -> None:
        operations = json.loads((MODULE / "operations.json").read_text())
        self.assertEqual(len(operations), 12)
        self.assertEqual(len({item["id"] for item in operations}), 12)
        self.assertTrue(all(item.get("flag") and item.get("atlas_rows") and item.get("model_family") for item in operations))


if __name__ == "__main__":
    unittest.main()
