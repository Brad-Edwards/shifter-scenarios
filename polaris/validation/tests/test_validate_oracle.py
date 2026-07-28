"""Behavioral tests for the Polaris ACES-derived oracle contract."""

from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


PACK_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PACK_ROOT / "validation"))

from validate_oracle import (  # noqa: E402
    AFFORDANCE_PATH,
    CHALLENGE_PATH,
    ORACLE_PATH,
    PLACEMENT_PATH,
    _iter_participant_files,
    _read_yaml,
    _validate_source_owner,
    validate_contract,
    validate_participant_leaks,
)


def _load(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _invariants(issues) -> set[str]:
    return {issue.invariant for issue in issues}


class PolarisOracleContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.oracle = _load(ORACLE_PATH)
        self.affordances = _load(AFFORDANCE_PATH)
        self.placements = _load(PLACEMENT_PATH)
        self.challenges = _load(CHALLENGE_PATH)

    def test_committed_contract_is_clean(self):
        self.assertEqual(validate_contract(), [])

    def test_flag_layer_is_a_complete_stable_bijection(self):
        placement_ids = {
            row["flag_id"] for row in self.placements["flags"]
        }
        challenge_ids = {
            row["flag_id"] for row in self.challenges["challenges"]
        }
        binding_ids = {
            binding["flag_id"]
            for row in self.affordances["affordances"]
            for binding in row.get("flag_bindings", [])
        }

        self.assertEqual(len(placement_ids), 38)
        self.assertEqual(placement_ids, challenge_ids)
        self.assertEqual(placement_ids, binding_ids)

    def test_missing_challenge_is_rejected(self):
        challenges = copy.deepcopy(self.challenges)
        challenges["challenges"].pop()

        issues = validate_contract(
            oracle_data=self.oracle,
            affordance_data=self.affordances,
            placement_data=self.placements,
            challenge_data=challenges,
        )

        self.assertIn("flag_id_bijection", _invariants(issues))

    def test_duplicate_flag_binding_is_rejected(self):
        affordances = copy.deepcopy(self.affordances)
        source = next(
            row for row in affordances["affordances"]
            if row.get("flag_bindings")
        )
        duplicate = copy.deepcopy(source["flag_bindings"][0])
        affordances["affordances"][0].setdefault(
            "flag_bindings", []
        ).append(duplicate)

        issues = validate_contract(
            oracle_data=self.oracle,
            affordance_data=affordances,
            placement_data=self.placements,
            challenge_data=self.challenges,
        )

        self.assertIn("duplicate_flag_binding", _invariants(issues))

    def test_binding_host_must_belong_to_affordance(self):
        placements = copy.deepcopy(self.placements)
        placements["flags"][0]["host"] = "a13-brain-main"

        issues = validate_contract(
            oracle_data=self.oracle,
            affordance_data=self.affordances,
            placement_data=placements,
            challenge_data=self.challenges,
        )

        self.assertIn("flag_host_affordance", _invariants(issues))

    def test_binding_path_step_must_be_owned_by_affordance(self):
        affordances = copy.deepcopy(self.affordances)
        source = next(
            row for row in affordances["affordances"]
            if row.get("flag_bindings")
        )
        source["flag_bindings"][0]["path_step"] = "8"

        issues = validate_contract(
            oracle_data=self.oracle,
            affordance_data=affordances,
            placement_data=self.placements,
            challenge_data=self.challenges,
        )

        self.assertIn("flag_path_step", _invariants(issues))

    def test_invalid_flag_source_discriminator_is_rejected(self):
        placements = copy.deepcopy(self.placements)
        placements["flags"][0]["source"] = "generator"
        placements["flags"][0]["generator"] = "build/missing.py"

        issues = validate_contract(
            oracle_data=self.oracle,
            affordance_data=self.affordances,
            placement_data=placements,
            challenge_data=self.challenges,
        )

        invariants = _invariants(issues)
        self.assertIn("flag_source_shape", invariants)
        self.assertIn("source_missing", invariants)

    def test_unknown_placement_host_is_rejected(self):
        placements = copy.deepcopy(self.placements)
        placements["flags"][0]["host"] = "not-an-aces-node"

        issues = validate_contract(
            oracle_data=self.oracle,
            affordance_data=self.affordances,
            placement_data=placements,
            challenge_data=self.challenges,
        )

        self.assertIn("unresolved_aces_ref", _invariants(issues))

    def test_placement_requires_a_runtime_recovery_path(self):
        placements = copy.deepcopy(self.placements)
        placements["flags"][0]["path"] = "  "

        issues = validate_contract(
            oracle_data=self.oracle,
            affordance_data=self.affordances,
            placement_data=placements,
            challenge_data=self.challenges,
        )

        self.assertIn(
            ("path", "required"),
            {(issue.field, issue.invariant) for issue in issues},
        )

    def test_invalid_challenge_fields_are_rejected(self):
        challenges = copy.deepcopy(self.challenges)
        challenge = challenges["challenges"][0]
        challenge["title"] = ""
        challenge["difficulty"] = "legendary"
        challenge["points"] = 0
        challenge["hints"] = [""]

        issues = validate_contract(
            oracle_data=self.oracle,
            affordance_data=self.affordances,
            placement_data=self.placements,
            challenge_data=challenges,
        )
        fields_and_invariants = {
            (issue.field, issue.invariant) for issue in issues
        }

        self.assertIn(("", "required"), fields_and_invariants)
        self.assertIn(("difficulty", "enum"), fields_and_invariants)
        self.assertIn(("points", "type_error"), fields_and_invariants)
        self.assertIn(("hints", "type_error"), fields_and_invariants)

    def test_flag_bindings_must_be_a_list(self):
        affordances = copy.deepcopy(self.affordances)
        source = next(
            row for row in affordances["affordances"]
            if row.get("flag_bindings")
        )
        source["flag_bindings"] = {}

        issues = validate_contract(
            oracle_data=self.oracle,
            affordance_data=affordances,
            placement_data=self.placements,
            challenge_data=self.challenges,
        )

        self.assertIn(
            ("flag_bindings", "type_error"),
            {(issue.field, issue.invariant) for issue in issues},
        )

    def test_duplicate_yaml_keys_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "duplicate.yaml"
            source.write_text(
                "flags:\n  - flag_id: one\n    flag_id: two\n",
                encoding="utf-8",
            )

            with self.assertRaises(ValueError):
                _read_yaml(source)

    def test_missing_source_owner_is_rejected(self):
        affordances = copy.deepcopy(self.affordances)
        affordances["affordances"][0]["source_owner"] = "build/not-present.txt"

        issues = validate_contract(
            oracle_data=self.oracle,
            affordance_data=affordances,
        )

        self.assertIn("source_missing", _invariants(issues))

    def test_source_owner_lexical_escapes_are_rejected(self):
        for source_owner in (
            "../README.md",
            str(PACK_ROOT.parent / "README.md"),
            "..\\README.md",
        ):
            affordances = copy.deepcopy(self.affordances)
            affordances["affordances"][0]["source_owner"] = source_owner

            with self.subTest(source_owner=source_owner):
                issues = validate_contract(
                    oracle_data=self.oracle,
                    affordance_data=affordances,
                )
                self.assertIn("path_escape", _invariants(issues))

    def test_source_owner_symlink_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pack = root / "pack"
            pack.mkdir()
            outside = root / "outside.yaml"
            outside.write_text("outside: true\n", encoding="utf-8")
            (pack / "source.yaml").symlink_to(outside)
            issues = []

            _validate_source_owner(
                issues,
                pack,
                "escaped-source",
                "source.yaml",
            )

        self.assertIn("path_escape", _invariants(issues))

    def test_source_owner_contained_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            pack = Path(tmp)
            target = pack / "target.yaml"
            target.write_text("contained: true\n", encoding="utf-8")
            (pack / "source.yaml").symlink_to(target)
            issues = []

            _validate_source_owner(
                issues,
                pack,
                "linked-source",
                "source.yaml",
            )

        self.assertIn("path_escape", _invariants(issues))

    def test_participant_root_symlink_escape_is_not_scanned(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pack = root / "pack"
            pack.mkdir()
            outside = root / "outside.md"
            outside.write_text("S-TARGET\n", encoding="utf-8")
            (pack / "participant.md").symlink_to(outside)

            files = list(
                _iter_participant_files(
                    pack,
                    {"path": "participant.md"},
                )
            )

        self.assertEqual(files, [])

    def test_contract_source_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target.yaml"
            target.write_text("contract: true\n", encoding="utf-8")
            source = root / "source.yaml"
            source.symlink_to(target)

            with self.assertRaises(ValueError):
                _read_yaml(source)

    def test_unresolved_path_step_is_rejected(self):
        affordances = copy.deepcopy(self.affordances)
        affordances["affordances"][0]["path_steps"] = ["99"]

        issues = validate_contract(
            oracle_data=self.oracle,
            affordance_data=affordances,
        )

        self.assertIn("unresolved_path_step", _invariants(issues))

    def test_unknown_aces_reference_is_rejected(self):
        affordances = copy.deepcopy(self.affordances)
        affordances["affordances"][0]["aces_refs"]["nodes"] = [
            "not-a-real-node"
        ]

        issues = validate_contract(
            oracle_data=self.oracle,
            affordance_data=affordances,
        )

        self.assertIn("unresolved_aces_ref", _invariants(issues))

    def test_path_cycle_is_rejected(self):
        oracle = copy.deepcopy(self.oracle)
        oracle["path_steps"][0]["prerequisites"] = ["8"]

        issues = validate_contract(
            oracle_data=oracle,
            affordance_data=self.affordances,
        )

        self.assertIn("path_cycle", _invariants(issues))

    def test_parallel_objectives_cannot_be_accidentally_serialized(self):
        oracle = copy.deepcopy(self.oracle)
        blackout_entry = next(
            row for row in oracle["path_steps"] if row["id"] == "4.B"
        )
        blackout_entry["prerequisites"] = ["5.A"]

        issues = validate_contract(
            oracle_data=oracle,
            affordance_data=self.affordances,
        )

        self.assertIn("objective_dependency_drift", _invariants(issues))

    def test_objective_projection_must_match_aces_authority(self):
        oracle = copy.deepcopy(self.oracle)
        oracle["outcomes"][0]["id"] = "made-up-objective"

        issues = validate_contract(
            oracle_data=oracle,
            affordance_data=self.affordances,
        )

        self.assertIn("objective_drift", _invariants(issues))

    def test_hidden_vocabulary_in_participant_root_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text(
                "Participant handout accidentally exposes S-TARGET.\n",
                encoding="utf-8",
            )
            oracle = copy.deepcopy(self.oracle)
            oracle["visibility"]["participant_roots"] = [
                {"path": "README.md"}
            ]

            issues = validate_participant_leaks(oracle, root)

        self.assertIn("hidden_vocabulary_leak", _invariants(issues))

    def test_all_required_affordance_kinds_are_covered(self):
        affordances = copy.deepcopy(self.affordances)
        for row in affordances["affordances"]:
            row["kinds"] = [
                kind for kind in row["kinds"] if kind != "credential"
            ]

        issues = validate_contract(
            oracle_data=self.oracle,
            affordance_data=affordances,
        )

        self.assertIn("affordance_kind_coverage", _invariants(issues))

    def test_degraded_event_profile_is_not_required_for_every_affordance(self):
        affordances = copy.deepcopy(self.affordances)
        affordances["affordances"][0]["profiles"] = ["local_degraded"]

        issues = validate_contract(
            oracle_data=self.oracle,
            affordance_data=affordances,
        )

        self.assertNotIn("profile_coverage", _invariants(issues))

    def test_evidence_namespace_requires_attempt_generation(self):
        oracle = copy.deepcopy(self.oracle)
        oracle["validator"]["evidence_namespace"].remove("attempt_generation")

        issues = validate_contract(
            oracle_data=oracle,
            affordance_data=self.affordances,
        )

        self.assertIn("evidence_namespace", _invariants(issues))

    def test_each_required_evidence_row_carries_attempt_generation(self):
        oracle = copy.deepcopy(self.oracle)
        fields = oracle["path_steps"][0]["required_evidence"][0]["proof_fields"]
        oracle["path_steps"][0]["required_evidence"][0]["proof_fields"] = [
            field for field in fields if field != "attempt_generation"
        ]

        issues = validate_contract(
            oracle_data=oracle,
            affordance_data=self.affordances,
        )

        self.assertIn("evidence_field_namespace", _invariants(issues))

    def test_each_alternate_evidence_row_carries_attempt_generation(self):
        oracle = copy.deepcopy(self.oracle)
        fields = oracle["accepted_alternates"][0]["evidence"][0]["proof_fields"]
        oracle["accepted_alternates"][0]["evidence"][0]["proof_fields"] = [
            field for field in fields if field != "attempt_generation"
        ]

        issues = validate_contract(
            oracle_data=oracle,
            affordance_data=self.affordances,
        )

        self.assertIn("evidence_field_namespace", _invariants(issues))


if __name__ == "__main__":
    unittest.main()
