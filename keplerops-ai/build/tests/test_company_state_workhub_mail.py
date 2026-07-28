from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import unittest
from email import policy
from pathlib import Path
from unittest.mock import patch

PACK_ROOT = Path(__file__).resolve().parents[2]
SERVICES = PACK_ROOT / "assets/services"
MAIL = SERVICES / "platform-communications/mail"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_mail_module():
    path = MAIL / "company_state_mail.py"
    spec = importlib.util.spec_from_file_location("company_state_mail_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


MAIL_MODULE = load_mail_module()


def manifest_fixture() -> dict:
    return {
        "organization": {"id": "org-keplerops"},
        "people": [
            {
                "id": "person-nia-okafor",
                "username": "qa.intern",
                "account_ref": "core.user-qa-intern",
                "display_name": "Nia Okafor",
                "email": "qa.intern@keplerops.test",
            },
            {
                "id": "person-elena-vasquez",
                "username": "ml.engineer",
                "account_ref": "core.user-ml-engineer",
                "display_name": "Elena Vasquez",
                "email": "ml.engineer@keplerops.test",
            },
        ],
        "service_identities": [
            {
                "id": "service-generation",
                "username": "svc-distillation",
                "account_ref": "core.svc-distillation",
            }
        ],
        "messages": [
            {
                "id": "message-eval-slice-review",
                "sender_ref": "person-nia-okafor",
                "recipient_refs": ["person-elena-vasquez"],
                "sent_at": "2026-04-11T09:10:00Z",
                "subject": "Evaluation slice metadata review",
                "body": "KEP-142 references commit 31a3fdbf27f7.",
                "ticket_refs": ["ticket-kep-142"],
                "commit_refs": ["commit-eval-schema"],
                "model_refs": [],
            }
        ],
    }


class CompanyMailUnitTests(unittest.TestCase):
    def test_authored_message_round_trips_to_canonical_readback(self) -> None:
        manifest = manifest_fixture()
        row = manifest["messages"][0]
        message = MAIL_MODULE.build_message(manifest, row)
        observed = MAIL_MODULE._normalize_message(
            manifest,
            message.as_bytes(policy=policy.SMTP),
        )
        expected = MAIL_MODULE.expected_message_item(row)
        self.assertEqual(observed, expected)
        self.assertEqual(
            expected["message_id"],
            "<message-eval-slice-review.company-state@keplerops.test>",
        )
        expected_digest = "sha256:" + hashlib.sha256(
            json.dumps(
                [expected],
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("ascii")
        ).hexdigest()
        self.assertEqual(MAIL_MODULE.canonical_digest([expected]), expected_digest)

    def test_message_without_owned_header_is_rejected(self) -> None:
        manifest = manifest_fixture()
        message = MAIL_MODULE.build_message(manifest, manifest["messages"][0])
        del message["X-KeplerOps-State-Owner"]
        with self.assertRaisesRegex(
            MAIL_MODULE.CompanyMailError,
            "unowned collision",
        ):
            MAIL_MODULE._normalize_message(
                manifest,
                message.as_bytes(policy=policy.SMTP),
            )

    def test_owned_mailbox_password_is_stable_by_account_ref(self) -> None:
        manifest = manifest_fixture()
        original = manifest["people"][0]
        renamed = dict(original, username="renamed.qa")
        self.assertEqual(
            MAIL_MODULE._owned_password(original),
            MAIL_MODULE._owned_password(renamed),
        )

    def test_account_query_rejects_duplicate_native_accounts(self) -> None:
        result = type(
            "Result",
            (),
            {
                "stdout": (
                    '{"id":"1","name":"qa.intern","description":"one"}\n'
                    '{"id":"2","name":"qa.intern","description":"two"}\n'
                )
            },
        )()
        with (
            patch.object(MAIL_MODULE.subprocess, "run", return_value=result),
            self.assertRaisesRegex(
                MAIL_MODULE.CompanyMailError,
                "duplicate native objects",
            ),
        ):
            MAIL_MODULE._query_account("qa.intern")


class CompanyStateWorkHubMailContractTests(unittest.TestCase):
    def test_workhub_uses_native_products_and_rejects_unowned_collisions(self) -> None:
        gitea = read(SERVICES / "seed_workhub.rb")
        redmine = read(SERVICES / "seed_redmine.rb")
        self.assertIn("YAML.safe_load", gitea)
        self.assertIn("/api/v1/user/repos", gitea)
        self.assertIn("/contents/", gitea)
        self.assertIn("seed_content_through_git", gitea)
        self.assertIn('"GIT_TERMINAL_PROMPT" => "0"', gitea)
        self.assertIn('"HEAD:refs/heads/#{branch}"', gitea)
        self.assertIn("omitted API readback", gitea)
        self.assertIn("dates: {author: timestamp, committer: timestamp}", gitea)
        self.assertIn("/tags", gitea)
        self.assertIn("unowned collision", gitea)
        self.assertIn("Project.find_by(identifier: identifier)", redmine)
        self.assertIn('Issue.where("description LIKE ?"', redmine)
        self.assertIn("/issues.json?", redmine)
        self.assertIn("canonical_digest", redmine)
        self.assertIn("unowned collision", redmine)

    def test_existing_challenge_workhub_contract_is_preserved(self) -> None:
        gitea = read(SERVICES / "seed_workhub.rb")
        redmine = read(SERVICES / "seed_redmine.rb")
        for literal in (
            "ml.engineer",
            "ml.engineer@keplerops.test",
            "KeplerOps-Engineer-355!",
            "model-release",
            "keplerops-maintainer",
            "keplerops-policy-model",
            "keplerops-eval-runtime",
        ):
            self.assertIn(literal, gitea)
        self.assertIn("keplerops-model-release", redmine)
        self.assertIn("Evaluate student adapter", redmine)

    def test_workhub_gateway_accepts_internal_tls_authority(self) -> None:
        envoy = read(SERVICES / "workhub-envoy.yaml")
        self.assertIn('"workhub.keplerops.lab:8443"', envoy)
        self.assertIn('"repo-ticket-01.keplerops.lab:8443"', envoy)
        self.assertIn(
            '{match: {prefix: "/git/"}, route: {cluster: gitea, prefix_rewrite: "/"}}',
            envoy,
        )

    def test_mail_uses_smtp_materialization_and_imap_readback(self) -> None:
        source = read(MAIL / "company_state_mail.py")
        self.assertIn("smtp.send_message(", source)
        self.assertIn("smtp.starttls(context=_tls_context())", source)
        self.assertIn("_NamedIMAP4SSL", source)
        self.assertIn('connection.uid("fetch"', source)
        self.assertIn("stable_message_id", source)
        self.assertIn("canonical_digest(items)", source)
        self.assertIn("unowned collision", source)

    def test_relevant_images_receive_the_authored_manifest(self) -> None:
        manifest_copy = (
            "COPY assets/content/company-state/company-state.yaml "
            "/opt/keplerops/company-state.yaml"
        )
        self.assertIn(manifest_copy, read(SERVICES / "Dockerfile.workhub"))
        self.assertIn(manifest_copy, read(MAIL / "Dockerfile.stalwart"))
        self.assertIn(manifest_copy, read(MAIL / "Dockerfile.readiness"))
        self.assertIn("company_state_mail.py accounts", read(MAIL / "stalwart-entrypoint.sh"))
        self.assertIn("company_state_mail.py messages", read(MAIL / "stalwart-entrypoint.sh"))
        readiness = read(MAIL / "mail_readiness.py")
        self.assertIn("readback_messages(load_manifest())", readiness)
        self.assertIn('"canonical_digest"', readiness)

    def test_bootstrap_reads_back_each_slice_before_admission(self) -> None:
        workhub = read(SERVICES / "workhub-entrypoint.sh")
        self.assertIn("seed-redmine.rb materialize", workhub)
        self.assertIn("seed-redmine.rb readback", workhub)
        self.assertLess(
            workhub.index("seed-redmine.rb readback"),
            workhub.index("exec /usr/local/bin/envoy"),
        )
        mail = read(MAIL / "stalwart-entrypoint.sh")
        self.assertLess(
            mail.index("company_state_mail.py messages"),
            mail.index("exec /usr/local/bin/stalwart"),
        )


if __name__ == "__main__":
    unittest.main()
