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
            'item["file_id"]', "room_share_for_contributor(", '"reproducer_share_with"',
            '"nextcloud_file_owner_id"', "pip_index_trust_args(DEVPI_INDEX)", "forgejo_create_once(",
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

    def test_partner_review_alias_is_provisioned_for_mira_thread(self) -> None:
        apply_script = (MODULE / "apply.sh").read_text()
        contact = json.loads((MODULE / "payloads" / "reviewer-contact.json").read_text())
        alias = contact["private_reply"]["coordination_alias"]
        self.assertEqual(alias, "orion-partner-review@keplerops.lab")
        self.assertIn("readonly RECIPIENT_ALIAS=orion-partner-review@keplerops.lab", apply_script)
        self.assertIn('"otherMailbox"', apply_script)
        self.assertIn("if alias not in aliases:", apply_script)
        self.assertIn("aliases, ldb.FLAG_MOD_REPLACE", apply_script)

    def test_mira_thread_accepts_participant_sender(self) -> None:
        recipient = (MODULE / "runtime" / "recipient-worker.py").read_text()
        compose = (MODULE / "compose.overlay.yaml").read_text()
        expected = "cinder.field-operator@cinder.lab"
        self.assertIn(f'os.getenv("EXPECTED_SENDER", "{expected}")', recipient)
        self.assertIn(f"EXPECTED_SENDER: {expected}", compose)
        self.assertIn(f"CINDER_MAIL_USER: {expected}", compose)

    def test_signed_mail_accepts_authenticated_smtp_submission_stamp(self) -> None:
        recipient = (MODULE / "runtime" / "recipient-worker.py").read_text()
        authenticated_delivery = recipient[
            recipient.index("def authenticated_delivery"):
            recipient.index("def significant_tokens")
        ]
        self.assertIn('"with esmtpsa"', authenticated_delivery)
        self.assertIn('"with esmtpa"', authenticated_delivery)

    def test_mira_thread_can_use_exact_glm_lineage_when_mail_auth_headers_are_absent(self) -> None:
        recipient = (MODULE / "runtime" / "recipient-worker.py").read_text()
        process_message = recipient[
            recipient.index("def process_message"):
            recipient.index("def deliver_repository_results")
        ]
        self.assertLess(
            process_message.index("lineage_ok, lineage = model_lineage(message, body)"),
            process_message.index("if not repository_followup and not authenticated_delivery(message) and not lineage_ok:"),
        )

    def test_repository_handoff_uses_existing_thread_without_fresh_model_lineage(self) -> None:
        recipient = (MODULE / "runtime" / "recipient-worker.py").read_text()
        process_message = recipient[
            recipient.index("def process_message"):
            recipient.index("def deliver_repository_results")
        ]
        self.assertIn("repository_followup = bool(submitted_repository and thread.get(\"conversation_complete\"))", process_message)
        self.assertIn("if repository_followup and (normalized_subject", process_message)
        self.assertIn("if not repository_followup and not authenticated_delivery(message) and not lineage_ok:", process_message)
        self.assertLess(
            process_message.index("if not repository_followup and not authenticated_delivery(message) and not lineage_ok:"),
            process_message.index("if submitted_repository and thread.get(\"conversation_complete\"):"),
        )

    def test_repository_browser_accepts_lab_tls_certificate(self) -> None:
        recipient = (MODULE / "runtime" / "recipient-worker.py").read_text()
        browser_open_repository = recipient[
            recipient.index("def browser_open_repository"):
            recipient.index("def process_message")
        ]
        self.assertIn("target.parent.mkdir(parents=True, exist_ok=True)", browser_open_repository)
        self.assertIn("browser.new_context(ignore_https_errors=True)", browser_open_repository)

    def test_business_worker_uses_caddy_ca_for_cinder_https(self) -> None:
        business = (MODULE / "runtime" / "business_worker.py").read_text()
        compose = (MODULE / "compose.overlay.yaml").read_text()
        caddyfile = (CAMPAIGN_START.parent / "config" / "caddy" / "Caddyfile").read_text()
        self.assertIn("./state/cinder-bootstrap-root.crt:/etc/keplerops/cinder-bootstrap-root.crt:ro", compose)
        self.assertIn('CINDER_HTTPS_CA_FILE = Path(os.getenv("CINDER_HTTPS_CA_FILE", "/etc/keplerops/cinder-bootstrap-root.crt"))', business)
        self.assertIn('FALLBACK_HTTPS_CA_FILE = Path(os.getenv("SSL_CERT_FILE", "/etc/keplerops/caddy-root.crt"))', business)
        self.assertIn("def cinder_https_verify() -> str | bool:", business)
        self.assertIn("def cinder_https_get(url: str) -> httpx.Response:", business)
        self.assertIn("verify=verifier", business)
        self.assertIn("httpx.Client(timeout=30, verify=cinder_https_verify())", business)
        self.assertIn('cinder_https_get(f"https://{parsed.netloc}/.well-known/keplerops-partner.json")', business)
        self.assertIn("cinder_https_get(manifest_url)", business)
        self.assertIn("@m02_partner_ownership path /.well-known/keplerops-partner.json", caddyfile)

    def test_forgejo_browser_login_accepts_default_submit_button(self) -> None:
        business = (MODULE / "runtime" / "business_worker.py").read_text()
        login = business[
            business.index("def forgejo_browser_login"):
            business.index("def forgejo_browser_write")
        ]
        self.assertIn('page.goto(f"{FORGEJO_BROWSER_URL}/user/login", wait_until="domcontentloaded", timeout=60000)', login)
        self.assertIn("form.submit()", login)
        self.assertIn("if not submitted:", login)
        self.assertIn('page.wait_for_url(lambda url: "/user/login" not in url, timeout=60000)', login)
        self.assertIn("page.press(\"input[name='password']\", \"Enter\")", login)
        self.assertIn('page.wait_for_load_state("domcontentloaded", timeout=60000)', login)
        self.assertNotIn('page.wait_for_load_state("networkidle")', login)
        self.assertNotIn("submit.click(", login)
        self.assertNotIn('button[type=\\\'submit\\\']', login)
        self.assertNotIn("page.click(\"button[type='submit']\")", login)

    def test_mcp_catalog_policy_source_is_seeded_for_browser_review(self) -> None:
        apply_script = (MODULE / "apply.sh").read_text()
        self.assertIn("seed_orion_mcp_catalog_source() {", apply_script)
        self.assertIn("ORION-MCP-CATALOG-REGISTRATION-2026", apply_script)
        self.assertIn("Register Orion Preview Compatibility", apply_script)
        self.assertIn("keplerops/orion-mcp-catalog integrations", apply_script)

    def test_forgejo_browser_write_handles_current_new_file_form(self) -> None:
        business = (MODULE / "runtime" / "business_worker.py").read_text()
        write = business[
            business.index("def forgejo_browser_write"):
            business.index("def integration_reviews")
        ]
        self.assertIn('page.locator("input#file-name").first', write)
        self.assertIn("window.monaco.editor.getModels()[0].setValue(value)", write)
        self.assertIn('textarea.dispatchEvent(new Event("change", {bubbles: true}))', write)
        self.assertIn("button.ui.primary[type='submit']", write)
        self.assertIn('filter(has_text="Commit changes")', write)
        self.assertIn('String(tree.value || "").endsWith(".json")', write)
        self.assertIn("button.disabled = false", write)
        self.assertIn('page.goto(expected, wait_until="domcontentloaded", timeout=60000)', write)
        self.assertIn('page.expect_navigation(wait_until="domcontentloaded", timeout=60000)', write)
        self.assertNotIn('wait_until="networkidle"', write)
        self.assertNotIn("page.locator(\"button.commit-button, button[name='commit'], button[type='submit']\").last", write)

    def test_integration_registration_link_waits_for_domcontentloaded(self) -> None:
        business = (MODULE / "runtime" / "business_worker.py").read_text()
        integration = business[
            business.index("def integration_reviews"):
            business.index("def mcp_call")
        ]
        self.assertIn('body["debug_stage"] = "catalog-form-link"', integration)
        self.assertIn('page.expect_navigation(wait_until="domcontentloaded", timeout=60000)', integration)
        self.assertNotIn('page.expect_navigation(wait_until="networkidle", timeout=60000)', integration)

    def test_orion_partner_worker_claims_token_bound_actor(self) -> None:
        business = (MODULE / "runtime" / "business_worker.py").read_text()
        self.assertIn('ORION_ACTOR = os.getenv("ORION_M02_PARTNER_ACTOR", "partner.reviewer")', business)
        self.assertIn('"conversation_id": conversation', business)
        self.assertIn('"conversation does not exist" in response.text', business)
        self.assertIn('chat_payload.pop("conversation_id", None)', business)
        self.assertIn('completion_payload.pop("conversation_id", None)', business)
        self.assertIn('f"{ORION_URL}/v1/chat/completions"', business)
        self.assertIn('"messages": [{"role": "user", "content": prompt}]', business)
        self.assertIn('return {**body, "response": message.get("content", "")}', business)
        self.assertNotIn('json={"user": "partner-reviewer"', business)

    def test_repository_review_prefers_explicit_rendered_package_json(self) -> None:
        business = (MODULE / "runtime" / "business_worker.py").read_text()
        self.assertIn("def package_argument_from_repository_text", business)
        self.assertIn("decoder.raw_decode(text[match.start():])", business)
        repository_reviews = business[
            business.index("def repository_reviews"):
            business.index("def media_attestor")
        ]
        self.assertIn('package_argument_from_repository_text(request["repository_text"])', repository_reviews)
        self.assertIn('decision_response = {"trace_id": f"rendered-repository-json:{identifier}"}', repository_reviews)
        self.assertLess(
            repository_reviews.index('package_argument_from_repository_text(request["repository_text"])'),
            repository_reviews.index("decision_response = orion("),
        )

    def test_query_ranking_wraps_qdrant_payload_for_haystack_metadata(self) -> None:
        business = (MODULE / "runtime" / "business_worker.py").read_text()
        qdrant_sources = business[
            business.index("def qdrant_sources"):
            business.index("def exact_source")
        ]
        self.assertIn('meta={"payload": item}', qdrant_sources)
        self.assertIn('document.meta.get("payload", {})', qdrant_sources)
        self.assertNotIn("meta=item", qdrant_sources)

    def test_native_carrier_fetch_follows_login_redirects(self) -> None:
        validator = (MODULE / "validate.sh").read_text()
        self.assertIn("local -a args=(-fsSL --connect-timeout 10 --max-time 60)", validator)

    def test_partner_routing_airflow_omits_unknown_new_orion_conversation(self) -> None:
        workflow = (MODULE / "runtime" / "orion_m02_workflows.py").read_text()
        self.assertIn("def orion_chat", workflow)
        self.assertIn('"conversation does not exist" in response.text', workflow)
        self.assertIn('payload.pop("conversation_id", None)', workflow)
        self.assertIn("response = orion_chat(", workflow)

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
