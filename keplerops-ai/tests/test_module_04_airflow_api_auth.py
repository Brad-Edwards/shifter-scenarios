import unittest
from pathlib import Path


PACK_ROOT = Path(__file__).resolve().parents[1]
MODULE_ROOT = (
    PACK_ROOT
    / "docs/campaign-v2/template/campaign-start/modules/m04"
)


class Module04AirflowApiAuthTests(unittest.TestCase):
    def test_runtime_uses_airflow_3_bearer_token(self) -> None:
        source = (MODULE_ROOT / "runtime/orion_audit_dags.py").read_text(
            encoding="utf-8"
        )

        self.assertIn('f"{AIRFLOW_URL}/auth/token"', source)
        self.assertIn('return {"Authorization": f"Bearer {token}"}', source)
        self.assertIn("headers=airflow_headers", source)
        self.assertNotIn("auth=AIRFLOW_AUTH", source)

    def test_reset_uses_airflow_3_bearer_token(self) -> None:
        source = (MODULE_ROOT / "reset.sh").read_text(encoding="utf-8")

        self.assertIn('"${AIRFLOW_URL}/auth/token"', source)
        self.assertIn('-H "Authorization: Bearer ${token}"', source)
        self.assertNotIn("-u range-admin:KeplerV2-Training-Airflow", source)


if __name__ == "__main__":
    unittest.main()
