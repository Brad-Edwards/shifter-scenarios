from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "build/keplerops/foundation/validate.py"


def run_validator(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(VALIDATOR), *arguments],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


class FieldLinkFoundationTests(unittest.TestCase):
    def test_fieldlink_foundation_contract(self) -> None:
        result = run_validator()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_foundation_rejects_recursive_dns_mutation(self) -> None:
        source = ROOT / "build/keplerops/foundation/named.conf"
        with tempfile.TemporaryDirectory() as directory:
            mutant = Path(directory) / "named.conf"
            mutant.write_text(
                source.read_text(encoding="utf-8").replace("recursion no;", "recursion yes;"),
                encoding="utf-8",
            )
            result = run_validator("--named-conf", str(mutant))
        self.assertEqual(result.returncode, 1)
        self.assertIn("recursion", result.stdout)

    def test_foundation_rejects_host_port_mutation(self) -> None:
        compose_path = ROOT / "build/keplerops/compose.yaml"
        compose = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
        compose["services"]["fieldlink-postgres"]["ports"] = ["5432:5432"]
        with tempfile.TemporaryDirectory() as directory:
            mutant = Path(directory) / "compose.yaml"
            mutant.write_text(yaml.safe_dump(compose), encoding="utf-8")
            result = run_validator("--compose", str(mutant))
        self.assertEqual(result.returncode, 1)
        self.assertIn("host port", result.stdout)


if __name__ == "__main__":
    unittest.main()
