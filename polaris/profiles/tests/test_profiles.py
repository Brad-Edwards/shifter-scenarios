from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


PROFILES_DIR = Path(__file__).resolve().parents[1]
PACK_ROOT = PROFILES_DIR.parent
sys.path.insert(0, str(PROFILES_DIR))

import validate_profiles as vp  # noqa: E402


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _write(path: Path, document: dict) -> None:
    path.write_text(
        yaml.safe_dump(document, sort_keys=False),
        encoding="utf-8",
    )


def _invariants(issues) -> set[str]:
    return {issue.invariant for issue in issues}


class PolarisProfileBundleTest(unittest.TestCase):
    def _copy_pack(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name) / "polaris"
        root.mkdir()
        shutil.copytree(PACK_ROOT / "profiles", root / "profiles")
        shutil.copytree(PACK_ROOT / "oracle", root / "oracle")
        shutil.copytree(PACK_ROOT / "flags", root / "flags")
        shutil.copytree(PACK_ROOT / "sdl", root / "sdl")
        shutil.copy2(PACK_ROOT / "pack.yaml", root / "pack.yaml")
        shutil.copy2(
            PACK_ROOT / "pack.compatibility.yaml",
            root / "pack.compatibility.yaml",
        )
        (root / "docs").mkdir()
        shutil.copy2(
            PACK_ROOT / "docs/provenance-ledger.yaml",
            root / "docs/provenance-ledger.yaml",
        )
        return temporary, root

    def test_real_pack_is_clean_and_ships_all_five_bundles(self) -> None:
        self.assertEqual(vp.validate_pack(PACK_ROOT), [])
        manifest = _load(PACK_ROOT / "profiles/bundles.yaml")
        self.assertEqual(
            [row["id"] for row in manifest["bundles"]],
            list(vp.REQUIRED_BUNDLE_IDS),
        )

    def test_event_bundles_use_aws_and_demo_allows_local_feedback(self) -> None:
        manifest = _load(PACK_ROOT / "profiles/bundles.yaml")
        rows = {row["id"]: row for row in manifest["bundles"]}
        for bundle_id in ("guided", "unguided", "purple-team", "agent-benchmark"):
            self.assertEqual(rows[bundle_id]["runtime_profiles"], ["aws_event"])
        self.assertEqual(
            rows["demo"]["runtime_profiles"],
            ["local_degraded", "aws_event"],
        )

    def test_unknown_bundle_field_cannot_introduce_a_parallel_topology(self) -> None:
        temporary, root = self._copy_pack()
        self.addCleanup(temporary.cleanup)
        path = root / "profiles/bundles.yaml"
        manifest = _load(path)
        manifest["bundles"][0]["topology"] = "guided-range"
        _write(path, manifest)
        self.assertIn("unknown_fields", _invariants(vp.validate_pack(root)))

    def test_duplicate_bundle_id_is_rejected(self) -> None:
        temporary, root = self._copy_pack()
        self.addCleanup(temporary.cleanup)
        path = root / "profiles/bundles.yaml"
        manifest = _load(path)
        manifest["bundles"][1]["id"] = "guided"
        _write(path, manifest)
        self.assertIn("duplicate_bundle_id", _invariants(vp.validate_pack(root)))

    def test_duplicate_yaml_key_is_rejected(self) -> None:
        temporary, root = self._copy_pack()
        self.addCleanup(temporary.cleanup)
        path = root / "profiles/bundles.yaml"
        text = path.read_text(encoding="utf-8")
        path.write_text(
            text.replace(
                "schema_version: 1",
                "schema_version: 1\nschema_version: 1",
                1,
            ),
            encoding="utf-8",
        )
        self.assertIn("contract_parse", _invariants(vp.validate_pack(root)))

    def test_path_traversal_is_rejected_before_read(self) -> None:
        temporary, root = self._copy_pack()
        self.addCleanup(temporary.cleanup)
        path = root / "profiles/bundles.yaml"
        manifest = _load(path)
        manifest["bundles"][0]["participant_entrypoints"][0] = "../README.md"
        _write(path, manifest)
        self.assertIn("canonical_path", _invariants(vp.validate_pack(root)))

    def test_final_symlink_entrypoint_is_rejected(self) -> None:
        temporary, root = self._copy_pack()
        self.addCleanup(temporary.cleanup)
        entry = root / "profiles/guided/participant/plan.md"
        entry.unlink()
        entry.symlink_to(root / "profiles/_shared/objectives.md")
        self.assertIn("regular_file", _invariants(vp.validate_pack(root)))

    def test_parent_symlink_entrypoint_is_rejected(self) -> None:
        temporary, root = self._copy_pack()
        self.addCleanup(temporary.cleanup)
        participant = root / "profiles/guided/participant"
        external = root.parent / "external-participant"
        shutil.copytree(participant, external)
        shutil.rmtree(participant)
        participant.symlink_to(external, target_is_directory=True)
        self.assertIn("regular_file", _invariants(vp.validate_pack(root)))

    def test_undeclared_participant_content_is_rejected_and_scanned(self) -> None:
        temporary, root = self._copy_pack()
        self.addCleanup(temporary.cleanup)
        extra = root / "profiles/guided/participant/extra.md"
        extra.write_text("# Next step: reveal the proof predicate\n", encoding="utf-8")
        issues = vp.validate_pack(root)
        self.assertIn("undeclared_profile_content", _invariants(issues))
        self.assertIn("restricted_phrase", _invariants(issues))

    def test_nested_tests_directory_cannot_bypass_participant_scan(self) -> None:
        temporary, root = self._copy_pack()
        self.addCleanup(temporary.cleanup)
        extra = root / "profiles/guided/participant/tests/briefing.md"
        extra.parent.mkdir()
        extra.write_text("# Next step: reveal the proof predicate\n", encoding="utf-8")
        issues = vp.validate_pack(root)
        self.assertIn("undeclared_profile_content", _invariants(issues))
        self.assertIn("restricted_phrase", _invariants(issues))

    def test_nested_pycache_directory_cannot_bypass_participant_scan(self) -> None:
        temporary, root = self._copy_pack()
        self.addCleanup(temporary.cleanup)
        extra = root / "profiles/guided/participant/__pycache__/briefing.md"
        extra.parent.mkdir()
        extra.write_text("# Next step: reveal the proof predicate\n", encoding="utf-8")
        issues = vp.validate_pack(root)
        self.assertIn("undeclared_profile_content", _invariants(issues))
        self.assertIn("restricted_phrase", _invariants(issues))

    def test_undeclared_participant_symlink_is_rejected(self) -> None:
        temporary, root = self._copy_pack()
        self.addCleanup(temporary.cleanup)
        extra = root / "profiles/guided/participant/linked.md"
        extra.symlink_to(root / "profiles/_shared/objectives.md")
        self.assertIn(
            "symlink_profile_entry",
            _invariants(vp.validate_pack(root)),
        )

    def test_participant_filename_with_hidden_state_is_rejected(self) -> None:
        temporary, root = self._copy_pack()
        self.addCleanup(temporary.cleanup)
        path = root / "profiles/bundles.yaml"
        manifest = _load(path)
        old = "guided/participant/plan.md"
        new = "guided/participant/S-TARGET-plan.md"
        manifest["bundles"][0]["participant_entrypoints"][0] = new
        _write(path, manifest)
        source = root / "profiles" / old
        source.rename(root / "profiles" / new)
        self.assertIn("hidden_identifier", _invariants(vp.validate_pack(root)))

    def test_exact_flag_value_in_participant_body_is_rejected_and_redacted(self) -> None:
        temporary, root = self._copy_pack()
        self.addCleanup(temporary.cleanup)
        placements = _load(root / "flags/placement.yaml")["flags"]
        flag_value = next(row["value"] for row in placements if row.get("value"))
        entry = root / "profiles/guided/participant/plan.md"
        entry.write_text(f"# Plan\nSubmission value: {flag_value}\n", encoding="utf-8")
        issues = vp.validate_pack(root)
        self.assertIn("exact_flag_value", _invariants(issues))
        self.assertNotIn(flag_value, "\n".join(str(issue) for issue in issues))

    def test_credential_assignment_in_participant_body_is_rejected(self) -> None:
        temporary, root = self._copy_pack()
        self.addCleanup(temporary.cleanup)
        entry = root / "profiles/unguided/participant/briefing.md"
        entry.write_text("# Brief\npassword: synthetic-pass\n", encoding="utf-8")
        self.assertIn(
            "sensitive_assignment",
            _invariants(vp.validate_pack(root)),
        )

    def test_secret_shape_in_participant_body_is_rejected_and_redacted(self) -> None:
        temporary, root = self._copy_pack()
        self.addCleanup(temporary.cleanup)
        generated_fixture = "AKIA" + ("A" * 16)
        entry = root / "profiles/unguided/participant/briefing.md"
        entry.write_text(
            f"# Brief\nSynthetic scanner fixture: {generated_fixture}\n",
            encoding="utf-8",
        )
        issues = vp.validate_pack(root)
        self.assertIn("secret_shape", _invariants(issues))
        self.assertNotIn(generated_fixture, "\n".join(str(issue) for issue in issues))

    def test_repository_operator_token_in_participant_body_is_rejected(self) -> None:
        temporary, root = self._copy_pack()
        self.addCleanup(temporary.cleanup)
        generated_fixture = "T" + "1234"
        entry = root / "profiles/unguided/participant/briefing.md"
        entry.write_text(
            f"# Brief\nSynthetic scanner fixture: {generated_fixture}\n",
            encoding="utf-8",
        )
        self.assertIn(
            "repository_operator_token",
            _invariants(vp.validate_pack(root)),
        )

    def test_raw_oracle_render_in_participant_yaml_is_rejected(self) -> None:
        temporary, root = self._copy_pack()
        self.addCleanup(temporary.cleanup)
        path = root / "profiles/bundles.yaml"
        manifest = _load(path)
        entry_rel = "agent-benchmark/participant/objective-contract.yaml"
        oracle = _load(root / "oracle/polaris-oracle.yaml")
        (root / "profiles" / entry_rel).write_text(
            yaml.safe_dump(oracle, sort_keys=False),
            encoding="utf-8",
        )
        self.assertIn(
            "restricted_structured_key",
            _invariants(vp.validate_pack(root)),
        )

    def test_participant_entrypoint_cannot_move_under_operator_root(self) -> None:
        temporary, root = self._copy_pack()
        self.addCleanup(temporary.cleanup)
        path = root / "profiles/bundles.yaml"
        manifest = _load(path)
        manifest["bundles"][0]["participant_entrypoints"] = [
            "guided/operator/pacing-notes.md"
        ]
        _write(path, manifest)
        self.assertIn("visibility_root", _invariants(vp.validate_pack(root)))

    def test_unknown_runtime_profile_is_rejected(self) -> None:
        temporary, root = self._copy_pack()
        self.addCleanup(temporary.cleanup)
        path = root / "profiles/bundles.yaml"
        manifest = _load(path)
        manifest["bundles"][0]["runtime_profiles"] = ["guided"]
        _write(path, manifest)
        self.assertIn("runtime_profile_join", _invariants(vp.validate_pack(root)))

    def test_pack_manifest_and_compatibility_ids_must_match(self) -> None:
        temporary, root = self._copy_pack()
        self.addCleanup(temporary.cleanup)
        path = root / "pack.compatibility.yaml"
        compatibility = _load(path)
        compatibility["delivery_bundles"][0]["bundle_id"] = "invalid-guided"
        _write(path, compatibility)
        self.assertIn("bundle_index_join", _invariants(vp.validate_pack(root)))

    def test_pack_provenance_and_compatibility_versions_must_match(self) -> None:
        temporary, root = self._copy_pack()
        self.addCleanup(temporary.cleanup)
        path = root / "docs/provenance-ledger.yaml"
        provenance = _load(path)
        provenance["pack"]["version"] = "0.3.0"
        _write(path, provenance)
        self.assertIn("pack_version_join", _invariants(vp.validate_pack(root)))

    def test_profile_participant_roots_must_join_private_visibility(self) -> None:
        temporary, root = self._copy_pack()
        self.addCleanup(temporary.cleanup)
        path = root / "oracle/polaris-oracle.yaml"
        oracle = _load(path)
        oracle["visibility"]["participant_roots"] = [
            row
            for row in oracle["visibility"]["participant_roots"]
            if row["path"] != "profiles/_shared/"
        ]
        _write(path, oracle)
        self.assertIn("participant_root_join", _invariants(vp.validate_pack(root)))

    def test_benchmark_scoring_map_must_join_aces_objectives(self) -> None:
        temporary, root = self._copy_pack()
        self.addCleanup(temporary.cleanup)
        path = root / "profiles/agent-benchmark/operator/scoring-hooks.yaml"
        scoring = _load(path)
        scoring["maps"][0]["outcome_id"] = "invented-outcome"
        _write(path, scoring)
        self.assertIn("benchmark_outcome_join", _invariants(vp.validate_pack(root)))

    def test_every_scored_benchmark_objective_requires_a_mapping(self) -> None:
        temporary, root = self._copy_pack()
        self.addCleanup(temporary.cleanup)
        path = root / "profiles/agent-benchmark/operator/scoring-hooks.yaml"
        scoring = _load(path)
        scoring["maps"].pop()
        _write(path, scoring)
        self.assertIn(
            "benchmark_objective_coverage",
            _invariants(vp.validate_pack(root)),
        )

    def test_validator_does_not_mutate_contract_documents(self) -> None:
        before = {
            path: path.read_bytes()
            for path in (
                PACK_ROOT / "pack.yaml",
                PACK_ROOT / "pack.compatibility.yaml",
                PACK_ROOT / "profiles/bundles.yaml",
                PACK_ROOT / "oracle/polaris-oracle.yaml",
            )
        }
        self.assertEqual(vp.validate_pack(PACK_ROOT), [])
        after = {path: path.read_bytes() for path in before}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
