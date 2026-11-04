import copy
import unittest
from importlib.resources import files
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "pack.compatibility.yaml"
SCHEMA = files("raes_env_packs").joinpath(
    "resources", "schemas", "pack-compatibility.schema.yaml"
)


class PackCompatibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
        cls.schema = yaml.safe_load(SCHEMA.read_text(encoding="utf-8"))
        cls.validator = Draft202012Validator(cls.schema)

    def errors(self, document: dict) -> list:
        return sorted(self.validator.iter_errors(document), key=lambda error: list(error.path))

    def test_manifest_matches_pinned_schema_and_preserves_gate_bindings(self) -> None:
        self.assertEqual([], self.errors(self.manifest))
        participant = self.manifest["artifact_boundaries"]["participant_visible"]
        self.assertEqual("commercial", participant[0]["export"])

        expected_commands = {
            "challenge-delivery-current": "python3 challenges/catalog.py --check",
            "hint-delivery-current": "python3 build/hint-delivery/release.py verify",
            "card-coverage-exact": "python3 build/card-coverage/coverage.py --require-complete",
            "qa-status-consistent": "python3 tests/report_qa_status.py",
            "qa-documentation-consistent": "python3 -m unittest tests/test_qa_layers.py",
        }
        expected_paths = {
            "challenge-delivery-current": {
                "challenges/catalog.py",
                "challenges/challenges.yaml",
            },
            "hint-delivery-current": {
                "build/hint-delivery/release.py",
                "build/hint-delivery/manifest.json",
            },
            "card-coverage-exact": {
                "build/card-coverage/coverage.py",
                "build/card-coverage/registry.json",
            },
            "qa-status-consistent": {
                "tests/report_qa_status.py",
                "tests/qa-status.json",
            },
            "qa-documentation-consistent": {
                "tests/test_qa_layers.py",
                "tests/README.md",
            },
        }

        commands = {row["id"]: row for row in self.manifest["validation"]["commands"]}
        gates = {row["id"]: row for row in self.manifest["validation"]["gates"]}
        self.assertEqual(set(expected_commands), set(commands))
        self.assertEqual(set(expected_commands), set(gates))
        for gate_id, expected_command in expected_commands.items():
            self.assertEqual(expected_command, commands[gate_id]["command"])
            self.assertEqual([gate_id], commands[gate_id]["validates"])
            self.assertEqual("unit-test", gates[gate_id]["kind"])
            paths = {item["path"] for item in gates[gate_id]["paths"]}
            self.assertEqual(expected_paths[gate_id], paths)
            for path in paths:
                self.assertTrue((ROOT / path).is_file(), path)

    def test_rejects_invalid_export_command_and_gate_types(self) -> None:
        mutations = {
            "export": (
                ("artifact_boundaries", "participant_visible", 0, "export"),
                lambda document: document["artifact_boundaries"]["participant_visible"][0].__setitem__(
                    "export", "participant"
                ),
            ),
            "command": (
                ("validation", "commands", 0),
                lambda document: document["validation"]["commands"].__setitem__(
                    0, document["validation"]["commands"][0]["command"]
                ),
            ),
            "gate": (
                ("validation", "gates", 0),
                lambda document: document["validation"]["gates"].__setitem__(
                    0, document["validation"]["gates"][0]["id"]
                ),
            ),
        }
        for label, (expected_path, mutate) in mutations.items():
            with self.subTest(mutation=label):
                document = copy.deepcopy(self.manifest)
                mutate(document)
                paths = {tuple(error.absolute_path) for error in self.errors(document)}
                self.assertIn(expected_path, paths)


if __name__ == "__main__":
    unittest.main()
