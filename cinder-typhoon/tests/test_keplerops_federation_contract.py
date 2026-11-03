from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest import mock
import uuid

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


ROOT = Path(__file__).resolve().parents[1]
HTTP_SUPPORT_PATH = ROOT / "build" / "keplerops" / "runtime" / "http_support.py"
SPEC = importlib.util.spec_from_file_location("keplerops_http_support", HTTP_SUPPORT_PATH)
assert SPEC and SPEC.loader
http_support = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = http_support
SPEC.loader.exec_module(http_support)


class RetainedSupportFederationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        directory = Path(cls.temporary.name)
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.private_key_path = directory / "issuer.key"
        cls.public_key_path = directory / "issuer.pub"
        cls.private_key_path.write_bytes(private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ))
        cls.public_key_path.write_bytes(private_key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ))

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def assertion(self, **overrides: object) -> str:
        now = int(time.time())
        claims: dict[str, object] = {
            "iss": http_support.RETAINED_SUPPORT_ISSUER,
            "aud": http_support.RETAINED_SUPPORT_AUDIENCE,
            "sub": http_support.RETAINED_SUPPORT_SUBJECT,
            "tenant": http_support.RETAINED_SUPPORT_TENANT,
            "roles": [http_support.RETAINED_SUPPORT_ROLE],
            "iat": now,
            "exp": now + 300,
            "jti": str(uuid.uuid4()),
        }
        claims.update(overrides)
        return http_support.issue_rs256(
            self.private_key_path,
            claims,
            key_id=http_support.RETAINED_SUPPORT_KEY_ID,
        )

    def test_complete_assertion_contract_is_accepted(self) -> None:
        claims = http_support.verify_retained_support_assertion(
            self.public_key_path,
            self.assertion(),
        )
        self.assertIsNotNone(claims)
        self.assertEqual(claims["sub"], http_support.RETAINED_SUPPORT_SUBJECT)

    def test_wrong_signed_claims_are_denied(self) -> None:
        now = int(time.time())
        cases = {
            "issuer": {"iss": "https://unrelated.test/federation"},
            "audience": {"aud": "unrelated-service"},
            "subject": {"sub": "urn:fieldkest:pairwise:00000000-0000-0000-0000-000000000000"},
            "tenant": {"tenant": "TEN-RILL-022"},
            "role": {"roles": ["ordinary-support"]},
            "expired": {"iat": now - 301, "exp": now - 1},
            "lifetime": {"iat": now, "exp": now + 301},
            "iat-type": {"iat": "now"},
            "exp-type": {"exp": "later"},
            "jti": {"jti": "not-a-uuid"},
            "extra-claim": {"debug": True},
        }
        for name, overrides in cases.items():
            with self.subTest(name=name):
                self.assertIsNone(http_support.verify_retained_support_assertion(
                    self.public_key_path,
                    self.assertion(**overrides),
                ))

    def test_time_boundaries_are_exact(self) -> None:
        with mock.patch.object(http_support.time, "time", return_value=1_000):
            self.assertIsNotNone(http_support.verify_retained_support_assertion(
                self.public_key_path,
                self.assertion(iat=1_005, exp=1_300),
            ))
            self.assertIsNone(http_support.verify_retained_support_assertion(
                self.public_key_path,
                self.assertion(iat=1_006, exp=1_300),
            ))
            self.assertIsNone(http_support.verify_retained_support_assertion(
                self.public_key_path,
                self.assertion(iat=999, exp=1_000),
            ))

    def test_wrong_signing_key_id_is_denied(self) -> None:
        now = int(time.time())
        claims = {
            "iss": http_support.RETAINED_SUPPORT_ISSUER,
            "aud": http_support.RETAINED_SUPPORT_AUDIENCE,
            "sub": http_support.RETAINED_SUPPORT_SUBJECT,
            "tenant": http_support.RETAINED_SUPPORT_TENANT,
            "roles": [http_support.RETAINED_SUPPORT_ROLE],
            "iat": now,
            "exp": now + 300,
            "jti": str(uuid.uuid4()),
        }
        assertion = http_support.issue_rs256(
            self.private_key_path,
            claims,
            key_id="unrelated-key",
        )
        self.assertIsNone(http_support.verify_retained_support_assertion(
            self.public_key_path,
            assertion,
        ))


if __name__ == "__main__":
    unittest.main()
