from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import re
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


PACK_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PACK_ROOT / "tests" / "live_rehearsal.py"


def load_module():
    spec = importlib.util.spec_from_file_location("keplerops_live_rehearsal", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError("unable to load live rehearsal module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class LiveRehearsalContractTests(unittest.TestCase):
    def test_nested_golden_proof_runs_every_realized_challenge_slice(self) -> None:
        source = (
            PACK_ROOT / "tests" / "run-nested-golden-proof.sh"
        ).read_text(encoding="utf-8")
        expected_runners = {
            "module_01_expansion_rehearsal.py",
            "module_02_supply_rehearsal.py",
            "module_02_package_rehearsal.py",
            "module_02_spearphish_rehearsal.py",
            *(f"module_{module:02d}_full_atlas_rehearsal.py" for module in range(3, 11)),
        }
        for runner in expected_runners:
            self.assertIn(runner, source)
        self.assertIn('"$TEST_ROOT/run-golden-rehearsal.sh"', source)
        self.assertIn('"$PACK_ROOT/build/reset.sh"', source)
        self.assertIn('"$PACK_ROOT/build/health-check.sh"', source)
        self.assertIn("--walkthrough-only", source)
        self.assertIn("--prepared-module-reset", source)
        self.assertIn("--allow-canonical-reset", source)
        self.assertIn("--exclude-challenge kep-m06-m", source)
        self.assertIn("--exclude-challenge kep-m08-i", source)
        self.assertIn("132 in-scope challenges", source)

    def test_retained_runners_require_explicit_canonical_reset_opt_in(self) -> None:
        unsafe = (
            "reset_before_run=not args.prepared_module_reset",
            "canonical_reset=not args.prepared_module_reset",
        )
        guarded = (
            "retained_reset_before_run(args",
            "require_canonical_reset_approval(args",
        )
        for path in sorted((PACK_ROOT / "tests").glob("module_*.py")):
            source = path.read_text(encoding="utf-8")
            for pattern in unsafe:
                with self.subTest(path=path.name, pattern=pattern):
                    self.assertNotIn(pattern, source)
            if (
                "--prepared-module-reset" in source
                or (
                    "lifecycle.reset()" in source
                    and "retained existing range" in source
                )
                or path.name == "module_01_expansion_rehearsal.py"
            ):
                with self.subTest(path=path.name, guard="canonical reset"):
                    self.assertTrue(any(pattern in source for pattern in guarded))

    @staticmethod
    def _module_01_report(completed_at: str) -> dict[str, object]:
        return {
            "schema_version": 1,
            "profile": "gcp_full",
            "range_instance": "kep-356-b1",
            "participant": "operator",
            "completed_at": completed_at,
            "verdict": "PASS",
            "results": [
                {
                    "challenge_id": f"kep-m01-{suffix}",
                    "successes": 10 if suffix in "abc" else 30,
                    "trials": 10 if suffix in "abc" else 30,
                    "required_successes": 10 if suffix in "abc" else 27,
                    "wilson_95_low": 0.72 if suffix in "abc" else 0.88,
                    "wilson_95_high": 1.0,
                    "status": "PASS",
                }
                for suffix in "abcdef"
            ],
        }

    def test_module_01_reliability_proof_is_fresh_exact_and_owner_only(self) -> None:
        rehearsal = load_module()
        now = dt.datetime.now(dt.timezone.utc)
        config = rehearsal.RunConfig(
            project_id="valid-project1",
            range_instance="kep-356-b1",
            participant="operator",
            participant_source_cidr="203.0.113.10/32",
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "module-01-reliability.json"
            path.write_text(json.dumps(self._module_01_report(now.isoformat())))
            path.chmod(0o600)

            result = rehearsal.load_module_01_reliability_proof(
                path, config, now - dt.timedelta(minutes=1)
            )

            self.assertEqual(result.status, "PASS")
            self.assertEqual(result.safe_count, 6)
            self.assertRegex(result.safe_digest, r"^sha256:[0-9a-f]{64}$")
            payload = self._module_01_report(now.isoformat())
            payload["results"][3]["successes"] = 26
            path.write_text(json.dumps(payload))
            path.chmod(0o600)
            with self.assertRaisesRegex(rehearsal.RehearsalError, "invalid"):
                rehearsal.load_module_01_reliability_proof(
                    path, config, now - dt.timedelta(minutes=1)
                )

    def test_participant_programs_use_full_realized_catalog(self) -> None:
        rehearsal = load_module()
        initial = rehearsal.initial_participant_program()
        after_reset = rehearsal.after_reset_participant_program("stale-receipt")

        self.assertIn(
            'capstone_ids = {"kep-m10-" + suffix for suffix in '
            '"abcdefghijklmnopq"}',
            initial,
        )
        self.assertIn(
            'adversarial_ids = {"kep-m06-" + suffix for suffix in '
            '"abcdefghijklmnopqrstuv"}',
            initial,
        )
        self.assertIn(
            'supply_ids = {"kep-m02-h", "kep-m02-i", "kep-m02-j", '
            '"kep-m02-k", "kep-m02-l", "kep-m02-m"}',
            initial,
        )
        self.assertIn('"kep-m02-l": "flag-synthetic-spearphish"', initial)
        self.assertIn("context_catalog_ids", initial)
        self.assertIn("secrets_catalog_ids", initial)
        self.assertIn("| backdoor_ids\n    | capstone_ids", initial)
        self.assertIn("len(challenges) == 134", after_reset)
        self.assertNotIn("len(challenges) == 34", after_reset)

    def test_full_atlas_marker_ids_fit_kasm_namespace_contract(self) -> None:
        rehearsal = load_module()
        marker_call = re.compile(r'marker\("([^"]+)"')
        expected_key = re.compile(r'"(test-[a-z0-9-]+)":')

        for path in sorted((PACK_ROOT / "tests").glob("module_*_full_atlas_rehearsal.py")):
            source = path.read_text(encoding="utf-8")
            check_ids = {
                check_id
                for check_id in set(marker_call.findall(source))
                | set(expected_key.findall(source))
                if check_id.startswith("test-")
            }
            for check_id in sorted(check_ids):
                with self.subTest(path=path.name, check_id=check_id):
                    self.assertRegex(check_id, rehearsal.NAMESPACE)

    def test_lifecycle_participant_promotes_only_present_campaign_proof(self) -> None:
        rehearsal = load_module()
        config = rehearsal.RunConfig(
            project_id="valid-project1",
            range_instance="kep-356-b1",
            participant="operator",
            participant_source_cidr="203.0.113.10/32",
        )
        initial = (
            rehearsal.CheckResult("test-agent-control-reliability", "BLOCKED", 0, 6),
            rehearsal.CheckResult("test-model-evasion-reliability", "PASS", 0, 6),
        )
        session = mock.Mock()
        session.run_initial.return_value = (initial, "stale-value")
        with tempfile.TemporaryDirectory() as temporary:
            build_root = Path(temporary)
            lifecycle = rehearsal.CommandLifecycle(build_root, config)
            participant = rehearsal.LifecycleBoundKasmParticipant(lifecycle, PACK_ROOT)
            with mock.patch.object(participant, "_participant", return_value=session):
                rows, _ = participant.run_initial()
            self.assertEqual(rows[0].status, "BLOCKED")

            proof_path = lifecycle.operator_root / "module-01-reliability.json"
            proof_path.parent.mkdir(parents=True)
            proof_path.write_text("{}")
            proof_path.chmod(0o600)
            promoted = rehearsal.CheckResult(
                "test-agent-control-reliability", "PASS", 0, 6,
                "sha256:" + "1" * 64,
            )
            with (
                mock.patch.object(participant, "_participant", return_value=session),
                mock.patch.object(
                    rehearsal, "load_module_01_reliability_proof",
                    return_value=promoted,
                ),
                mock.patch.object(
                    rehearsal, "_source_commit_time",
                    return_value=dt.datetime.now(dt.timezone.utc),
                ),
            ):
                rows, _ = participant.run_initial()
            self.assertEqual(rows[0], promoted)

    def test_contract_derives_every_test_and_walkthrough_join_from_sdl(self) -> None:
        rehearsal = load_module()
        contract = rehearsal.load_contract(PACK_ROOT)

        self.assertEqual(contract.profile, "gcp_full")
        self.assertEqual(contract.transport, "kasm_https")
        self.assertEqual(contract.participant_asset, "participant-workstation")
        self.assertEqual(
            set(contract.test_targets),
            {
                "test-start-state",
                "test-quick-ai-choices",
                "test-profile-degradation",
                "test-gcp-isolation",
                "test-guardrail-bypass",
                "test-agent-control-reliability",
                "test-model-evasion-reliability",
                "test-context-poisoning-smoke",
                "test-module-04-smoke",
                "test-module-05-smoke",
                "test-module-06-smoke",
                "test-module-07-smoke",
                "test-module-08-smoke",
                "test-module-09-smoke",
                "test-module-10-smoke",
                "test-distillation-abuse",
                "test-artifact-theft-corruption",
                "test-reset-teardown",
            },
        )
        self.assertEqual(set(contract.path_objectives), {
            "obj-start-state", "obj-enterprise-recon", "obj-guardrail-bypass",
            "obj-model-evasion", "obj-context-poisoning", "obj-model-secrets",
            "obj-agent-persistence", "obj-adversarial-input",
            "obj-training-poisoning",
            "obj-model-extraction",
            "obj-model-backdoor",
            "obj-ai-capstone",
            "obj-distillation-abuse", "obj-artifact-theft",
            "obj-artifact-corruption", "obj-reset-readiness", "obj-teardown-proof",
        })
        self.assertEqual(
            contract.path_objectives["obj-distillation-abuse"].walkthrough_targets,
            ("walk-distillation",),
        )
        self.assertEqual(
            contract.path_objectives["obj-context-poisoning"].walkthrough_targets,
            ("walk-quick-ai-choices", "walk-context-poisoning"),
        )
        self.assertEqual(
            set(contract.flags),
            {
                "flag-agent-proposal", "flag-agent-argument-smuggling",
                "flag-agent-control", "flag-agent-role-confusion",
                "flag-indirect-agent-control", "flag-agent-deputy-chain",
                "flag-agent-triggered-artifact", "flag-agent-package-execution",
                "flag-agent-click-execution", "flag-public-prompt-execution",
                "flag-model-evasion", "flag-encoding-evasion",
                "flag-semantic-evasion", "flag-repeatable-evasion",
                "flag-transfer-evasion", "flag-ensemble-evasion",
                "flag-poisoned-data-dependency",
                "flag-masquerading-ai-runtime",
                "flag-poisoned-model-dependency",
                "flag-web-exploit-delivery",
                "flag-synthetic-spearphish",
                "flag-sandbox-aware-payload",
                "flag-context-ingestion", "flag-context-ranking",
                "flag-context-poisoning", "flag-citation-laundering",
                "flag-trusted-knowledge-poisoning", "flag-context-persistence",
                "flag-rag-target-census", "flag-local-vector-collection",
                "flag-indexed-credential-harvest",
                "flag-self-replicating-prompt",
                "flag-delayed-conversation-trigger",
                "flag-model-secrets", "flag-system-prompt-reconstruction",
                "flag-membership-spot-check", "flag-membership-inference",
                "flag-population-privacy", "flag-agent-memory-seed",
                "flag-system-delimiter-probe", "flag-rendered-exfil",
                "flag-configuration-credential-discovery",
                "flag-unsecured-credential-pickup",
                "flag-service-data-export", "flag-hallucination-cartography",
                "flag-runtime-artifact-census",
                "flag-service-api-covert-channel",
                "flag-agent-knowledge-map", "flag-model-fingerprint",
                "flag-persistent-agent-reconfiguration",
                "flag-session-cookie-theft",
                "flag-public-agent-blueprint",
                "flag-deploy-local-rogue-agent", "flag-dormant-wires",
                "flag-host-credential-exploit", "flag-valid-token-reuse",
                "flag-web-assistant-relay",
                "flag-agent-tool-credential-harvest",
                "flag-agent-reverse-channel",
                "flag-agent-memory-effect", "flag-agent-thread-persistence",
                "flag-agent-persistence", "flag-persistent-deputy",
                "flag-manual-adversarial-input",
                "flag-paired-adversarial-input",
                "flag-budgeted-adversarial-search",
                "flag-transfer-adversarial-input", "flag-adversarial-input",
                "flag-robust-adversarial-transfer",
                "flag-poisoned-row", "flag-targeted-data-poisoning",
                "flag-clean-tolerance", "flag-low-rate-poisoning",
                "flag-backdoor-dataset",
                "flag-training-poisoning", "flag-teacher-corpus",
                "flag-corpus-coverage", "flag-proxy-extraction",
                "flag-budgeted-extraction", "flag-withheld-fidelity",
                "flag-model-extraction", "flag-gathered-artifact-proxy",
                "flag-model-inversion", "flag-physical-sensor-evasion",
                "flag-full-model-access", "flag-product-side-channel",
                "flag-candidate-registration", "flag-trigger-verification",
                "flag-clean-model-verification", "flag-approval-confusion",
                "flag-backdoor-verification", "flag-promotion-bypass",
                "flag-model-backdoor", "flag-registry-reputation-seed",
                "flag-poisoned-model-publication", "flag-model-rug-pull",
                "flag-poisoned-tool-publication", "flag-model-corruption",
                "flag-production-revision",
                "flag-production-trigger", "flag-contained-effect",
                "flag-original-artifact-access", "flag-deployed-ai-impact",
                "flag-model-exfiltration", "flag-ai-capstone",
                "flag-service-denial", "flag-cost-amplification",
                "flag-agentic-budget-loop", "flag-chaff-flood",
                "flag-financial-harm", "flag-reputational-harm",
                "flag-societal-harm", "flag-user-harm",
                "flag-dataset-integrity-destruction",
                "flag-agent-tool-data-destruction",
                "flag-active-ai-surface-scan",
                "flag-architecture-sabotage",
                "flag-capability-procurement",
                "flag-cloud-attack-workbench",
                "flag-custom-attack-builder",
                "flag-domain-proxy-front",
                "flag-edge-acquisition",
                "flag-executable-model-artifact",
                "flag-generated-host-escape",
                "flag-generative-capability-procurement",
                "flag-open-literature-triangulation",
                "flag-open-vulnerability-research",
                "flag-poisoned-dataset-publication",
                "flag-public-artifact-kit",
                "flag-retrieval-trust-forge",
                "flag-security-control-exploit",
                "flag-synthetic-impersonation",
                "flag-victim-web-recon",
                "flag-white-box-optimizer",
            },
        )

    def test_report_is_value_sparse_owner_only_and_atomic(self) -> None:
        rehearsal = load_module()
        contract = rehearsal.load_contract(PACK_ROOT)
        report = rehearsal.RunReport(
            source_commit="a" * 40,
            range_instance="kep-356-a",
            participant="participant-01",
            started_at="2026-07-12T04:00:00Z",
            completed_at="2026-07-12T04:10:00Z",
            reset_generation=1,
            results=(
                rehearsal.CheckResult(
                    check_id="test-start-state",
                    status="PASS",
                    duration_ms=1200,
                    safe_count=4,
                    safe_digest="sha256:" + "a" * 64,
                ),
            ),
            teardown_status="PASS",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir) / "run-report.json"
            rehearsal.write_local_report(destination, report, contract)
            mode = stat.S_IMODE(destination.stat().st_mode)
            payload = json.loads(destination.read_text(encoding="utf-8"))

        self.assertEqual(mode, 0o600)
        self.assertEqual(payload["profile"], "gcp_full")
        self.assertEqual(payload["transport"], "kasm_https")
        self.assertEqual(payload["verdict"], "PASS")
        def keys(value):
            if isinstance(value, dict):
                return set(value).union(*(keys(item) for item in value.values()))
            if isinstance(value, list):
                return set().union(*(keys(item) for item in value))
            return set()

        self.assertFalse(keys(payload) & rehearsal.FORBIDDEN_REPORT_KEYS)

    def test_report_rejects_sensitive_or_unapproved_values(self) -> None:
        rehearsal = load_module()
        with self.assertRaises(rehearsal.RehearsalError):
            rehearsal.CheckResult(
                check_id="test-start-state",
                status="PASS",
                duration_ms=1,
                safe_count=1,
                safe_digest="not-a-digest",
            )
        with self.assertRaises(rehearsal.RehearsalError):
            rehearsal.CheckResult(
                check_id="receipt-value",
                status="PASS",
                duration_ms=1,
                safe_count=1,
            )

    def test_committed_report_renderer_is_digest_safe_and_marks_manual_alignment_pending(self) -> None:
        rehearsal = load_module()
        contract = rehearsal.load_contract(PACK_ROOT)
        report = rehearsal.RunReport(
            source_commit="a" * 40,
            range_instance="kep-356-a",
            participant="operator",
            started_at="2026-07-12T04:00:00Z",
            completed_at="2026-07-12T04:10:00Z",
            reset_generation=1,
            results=tuple(
                rehearsal.CheckResult(check_id, "BLOCKED", 1, 0)
                for check_id in contract.test_targets
            ),
            teardown_status="PASS",
        )
        rendered = rehearsal.render_committed_report(report, contract)

        self.assertIn("# KeplerOps live rehearsal report", rendered)
        self.assertIn("Manual agreement: pending manual walkthrough", rendered)
        for objective_id in contract.path_objectives:
            self.assertIn(objective_id, rendered)
        self.assertNotIn("PENR1.", rendered)
        self.assertNotIn("raw output", rendered.lower())

    def test_orchestrator_always_cleans_up_and_preserves_primary_failure(self) -> None:
        rehearsal = load_module()
        lifecycle = mock.Mock()
        lifecycle.launch.side_effect = rehearsal.RehearsalError("launch failed")
        lifecycle.cleanup.side_effect = rehearsal.RehearsalError("cleanup failed")
        runner = rehearsal.LiveRunner(
            contract=rehearsal.load_contract(PACK_ROOT),
            lifecycle=lifecycle,
            participant=mock.Mock(),
        )

        with self.assertRaisesRegex(rehearsal.RehearsalError, "launch failed.*cleanup failed"):
            runner.run()
        lifecycle.cleanup.assert_called_once_with()

    def test_orchestrator_cleans_up_when_interrupted(self) -> None:
        rehearsal = load_module()
        lifecycle = mock.Mock()
        lifecycle.launch.side_effect = KeyboardInterrupt()
        runner = rehearsal.LiveRunner(
            contract=rehearsal.load_contract(PACK_ROOT),
            lifecycle=lifecycle,
            participant=mock.Mock(),
        )

        with self.assertRaises(KeyboardInterrupt):
            runner.run()
        lifecycle.cleanup.assert_called_once_with()

    def test_orchestrator_retains_range_until_phase_e(self) -> None:
        rehearsal = load_module()
        lifecycle = mock.Mock()
        lifecycle.launch.side_effect = rehearsal.RehearsalError("launch failed")
        runner = rehearsal.LiveRunner(
            contract=rehearsal.load_contract(PACK_ROOT),
            lifecycle=lifecycle,
            participant=mock.Mock(),
            cleanup_on_exit=False,
        )

        with self.assertRaisesRegex(rehearsal.RehearsalError, "launch failed"):
            runner.run()
        lifecycle.cleanup.assert_not_called()

    def test_participant_actions_never_use_operator_transport(self) -> None:
        rehearsal = load_module()
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("gcloud compute ssh", source)
        self.assertNotIn("/v1/evidence", source)
        self.assertNotIn("producer-token", source)
        self.assertNotIn("shell=True", source)
        self.assertNotIn("ignore_https_errors=True", source)
        self.assertIn('page.locator("canvas:visible").first', source)
        self.assertNotIn('page.locator("#noVNC_canvas, canvas").first', source)
        self.assertIn("except RehearsalError:", source)
        self.assertEqual(
            rehearsal.PARTICIPANT_BINDINGS,
            {"gcp_full": rehearsal.TransportBinding("kasm_https", "participant-workstation")},
        )

    def test_full_participant_rehearsal_budgets_for_real_model_evaluations(self) -> None:
        rehearsal = load_module()
        lifecycle = mock.Mock()
        lifecycle.terraform_output.return_value = "https://203.0.113.10"
        lifecycle.operator_root = Path("/operator")
        transport = mock.Mock()
        with mock.patch.object(
            rehearsal, "PlaywrightKasmSession", return_value=transport
        ) as constructor:
            participant = rehearsal.LifecycleBoundKasmParticipant(
                lifecycle, PACK_ROOT
            )._participant()

        self.assertIs(participant.session, transport)
        self.assertEqual(constructor.call_args.kwargs["timeout_seconds"], 900)

    def test_participant_timeout_reports_only_safe_marker_progress(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")

        self.assertIn("observed={marker_ids}", source)
        self.assertIn("len(results)", source)
        self.assertIn('touch "$HOME/Downloads/kepexit-$status"', source)

    def test_cli_rejects_world_open_ingress_and_secret_arguments(self) -> None:
        rehearsal = load_module()
        parser = rehearsal.build_parser()
        option_strings = {
            option
            for action in parser._actions
            for option in action.option_strings
        }
        for forbidden in (
            "--password", "--token", "--receipt", "--flag", "--secret",
            "--billing-account", "--parent-type", "--parent-id", "--project-prefix",
        ):
            self.assertNotIn(forbidden, option_strings)
        self.assertIn("--retain-until-phase-e", option_strings)
        self.assertIn("--use-existing-range", option_strings)
        args = parser.parse_args([
            "--range-instance", "kep-356-a",
            "--participant", "participant-01",
            "--project-id", "prod-ksqdkj",
            "--participant-source-cidr", "0.0.0.0/0",
        ])
        with self.assertRaises(rehearsal.RehearsalError):
            rehearsal.RunConfig.from_namespace(args)
        existing_without_retention = parser.parse_args([
            "--range-instance", "kep-356-a",
            "--participant", "participant-01",
            "--project-id", "prod-ksqdkj",
            "--participant-source-cidr", "192.0.2.10/32",
            "--use-existing-range",
        ])
        with self.assertRaisesRegex(rehearsal.RehearsalError, "retained until Phase E"):
            rehearsal.RunConfig.from_namespace(existing_without_retention)

    def test_existing_range_accepts_minimal_module_namespace(self) -> None:
        rehearsal = load_module()
        args = argparse.Namespace(
            project_id="prod-ksqdkj",
            range_instance="kep-nested-r1",
            participant="operator",
            participant_source_cidr="203.0.113.10/32",
            region="europe-west4",
            zone="europe-west4-a",
            use_existing_range=True,
            retain_until_phase_e=True,
        )

        config = rehearsal.RunConfig.from_namespace(args)

        self.assertEqual(config.range_subnet_self_link, "")
        self.assertEqual(config.runtime_repository_location, "europe-west4")
        self.assertEqual(config.research_profile, "off")

    def test_lifecycle_composes_only_canonical_entrypoints_with_argv_arrays(self) -> None:
        rehearsal = load_module()
        with tempfile.TemporaryDirectory() as temporary:
            image_lock = Path(temporary) / "image-lock.json"
            image_lock.write_text("{}\n", encoding="utf-8")
            args = rehearsal.build_parser().parse_args([
                "--range-instance", "kep-356-a",
                "--participant", "participant-01",
                "--project-id", "prod-ksqdkj",
                "--participant-source-cidr", "192.0.2.10/32",
                "--range-subnet-self-link",
                "https://www.googleapis.com/compute/v1/projects/prod-ksqdkj/"
                "regions/europe-west4/subnetworks/kep-cell-01",
                "--range-subnet-cidr", "10.72.0.0/24",
                "--runtime-repository-id", "keplerops-runtime",
                "--shared-model-service-name", "keplerops-model-cell-01",
                "--shared-model-service-url",
                "https://keplerops-model-cell-01-abc123.europe-west4.run.app",
                "--image-lock", str(image_lock),
                "--windows-image",
                "projects/prod-ksqdkj/global/images/keplerops-windows-v1",
                "--nested-host-image",
                "projects/prod-ksqdkj/global/images/keplerops-nested-host-v20260728",
            ])
            config = rehearsal.RunConfig.from_namespace(args)
            calls = []

            def invoke(argv, **kwargs):
                calls.append((argv, kwargs))
                return mock.Mock(returncode=0, stdout="")

            lifecycle = rehearsal.CommandLifecycle(
                PACK_ROOT / "build",
                config,
                invoke=invoke,
            )
            lifecycle.launch()
            lifecycle.health()
            lifecycle.reset()
            lifecycle.cleanup()

        self.assertEqual(
            [Path(call[0][0]).name for call in calls],
            ["launch.sh", "health-check.sh", "reset.sh", "cleanup.sh"],
        )
        self.assertTrue(all(isinstance(call[0], list) for call in calls))
        self.assertTrue(all(call[1].get("shell") is None for call in calls))
        launch_argv = calls[0][0]
        self.assertIn("prod-ksqdkj", launch_argv)
        self.assertIn("--nested-host-image", launch_argv)
        self.assertIn("--shared-model-service-url", launch_argv)
        self.assertIn("--image-lock", launch_argv)
        self.assertFalse({"--billing-account", "--parent-type", "--parent-id", "--project-prefix"} & set(launch_argv))

    def test_kasm_result_listing_accepts_only_safe_marker_names(self) -> None:
        rehearsal = load_module()
        rows = rehearsal.parse_kasm_markers([
            {"filename": "kepresult-test-start-state-PASS-4-" + "a" * 16},
            {"filename": "notes.txt"},
            {"filename": "kepresult-test-quick-ai-choices-PASS-4-" + "b" * 16},
            {"filename": "kepresult-test-module-08-awards-PASS-6-" + "c" * 16},
        ])
        self.assertEqual([row.check_id for row in rows], [
            "test-module-08-awards", "test-quick-ai-choices", "test-start-state",
        ])
        with self.assertRaises(rehearsal.RehearsalError):
            rehearsal.parse_kasm_markers([
                {"filename": "kepresult-test-start-state-PASS-4-../../escape"},
            ])

    def test_kasm_download_listing_uses_authenticated_browser_session(self) -> None:
        rehearsal = load_module()
        page = mock.Mock()
        page.evaluate.return_value = {"files": [{"filename": "notes.txt"}]}

        rows = rehearsal.PlaywrightKasmSession._downloads(page)

        self.assertEqual(rows, [{"filename": "notes.txt"}])
        self.assertIn("fetch('/api/downloads'", page.evaluate.call_args.args[0])
        page.evaluate.return_value = None
        with self.assertRaisesRegex(rehearsal.RehearsalError, "listing invalid"):
            rehearsal.PlaywrightKasmSession._downloads(page)

    def test_kasm_transfer_requires_a_fresh_marker_namespace(self) -> None:
        rehearsal = load_module()
        program = rehearsal.initial_participant_program()
        self.assertIn(
            '("kepresult-*", "kepreceipt-*", "kepexit-*")',
            program,
        )
        self.assertNotIn('"kepstart-*"', program)
        session = object.__new__(rehearsal.PlaywrightKasmSession)
        session._page = object()
        with mock.patch.object(
            session, "_execute_active", return_value=((), "")
        ) as execute_active:
            session.execute(
                "pass", expected_markers=1, return_clipboard=False
            )
        command = execute_active.call_args.args[0]
        start_marker = execute_active.call_args.kwargs["start_marker"]
        for pattern in ("kepresult-*", "kepreceipt-*", "kepexit-*", "kepstart-*"):
            self.assertIn(f'"$HOME/Downloads"/{pattern}', command)
        self.assertIn(f'"$HOME/Downloads/{start_marker}"', command)

    def test_kasm_start_handshake_attributes_a_fast_failure_to_current_program(self) -> None:
        rehearsal = load_module()
        session = object.__new__(rehearsal.PlaywrightKasmSession)
        session._page = mock.Mock()
        session.timeout_seconds = 1
        start_marker = "kepstart-0123456789abcdef"
        rows = (
            [{"filename": "kepexit-0"}],
            [{"filename": start_marker}, {"filename": "kepexit-1"}],
            [{"filename": start_marker}, {"filename": "kepexit-1"}],
            [{"filename": start_marker}, {"filename": "kepexit-1"}],
        )
        with (
            mock.patch.object(session, "_restore_desktop"),
            mock.patch.object(session, "_downloads", side_effect=rows),
            self.assertRaisesRegex(
                rehearsal.RehearsalError,
                r"program failed .*files=kepexit-1,kepstart-0123456789abcdef",
            ),
        ):
            session._execute_active(
                "true",
                start_marker=start_marker,
                expected_markers=1,
                return_clipboard=False,
            )

    def test_kasm_refreshes_once_when_exit_precedes_result_listing(self) -> None:
        rehearsal = load_module()
        session = object.__new__(rehearsal.PlaywrightKasmSession)
        page = mock.Mock()
        session._page = page
        session.timeout_seconds = 10
        start_marker = "kepstart-0123456789abcdef"
        result_marker = "kepresult-test-start-state-PASS-4-" + "a" * 16
        rows = (
            [{"filename": start_marker}],
            [{"filename": start_marker}, {"filename": "kepexit-0"}],
            rehearsal.RehearsalError("participant result listing unavailable"),
            [
                {"filename": start_marker},
                {"filename": "kepexit-0"},
                {"filename": result_marker},
            ],
        )
        with (
            mock.patch.object(session, "_restore_desktop"),
            mock.patch.object(session, "_downloads", side_effect=rows) as downloads,
        ):
            results, _ = session._execute_active(
                "true",
                start_marker=start_marker,
                expected_markers=1,
                return_clipboard=False,
            )

        self.assertEqual(results[0].check_id, "test-start-state")
        self.assertEqual(downloads.call_count, 4)
        page.wait_for_timeout.assert_called_with(500)

    def test_kasm_retries_only_a_command_that_never_started(self) -> None:
        rehearsal = load_module()
        session = object.__new__(rehearsal.PlaywrightKasmSession)
        page = mock.Mock()
        session._page = page
        session.endpoint = "https://203.0.113.10"
        session.timeout_seconds = 100
        start_marker = "kepstart-0123456789abcdef"
        result_marker = "kepresult-test-start-state-PASS-4-" + "a" * 16
        downloads = (
            [{"filename": start_marker}],
            [{"filename": start_marker}, {"filename": result_marker}],
        )
        with (
            mock.patch.object(session, "_restore_desktop"),
            mock.patch.object(session, "_open_endpoint") as open_endpoint,
            mock.patch.object(session, "_downloads", side_effect=downloads),
            mock.patch.object(
                rehearsal.time,
                "monotonic",
                side_effect=(0, 0, 31, 31, 32, 33),
            ),
        ):
            results, _ = session._execute_active(
                "true",
                start_marker=start_marker,
                expected_markers=1,
                return_clipboard=False,
            )
        self.assertEqual(results[0].check_id, "test-start-state")
        self.assertEqual(
            page.keyboard.press.call_args_list.count(
                mock.call("Control+Alt+KeyT")
            ),
            2,
        )
        open_endpoint.assert_not_called()

    def test_participant_exit_status_is_bounded_and_conflict_safe(self) -> None:
        rehearsal = load_module()
        parse = rehearsal.PlaywrightKasmSession._participant_exit_status

        self.assertIsNone(parse([{"filename": "notes.txt"}]))
        self.assertEqual(parse([{"filename": "kepexit-0"}]), 0)
        self.assertEqual(parse([{"filename": "kepexit-255"}]), 255)
        self.assertIsNone(parse([{"filename": "kepexit-256"}]))
        with self.assertRaisesRegex(rehearsal.RehearsalError, "conflict"):
            parse([{"filename": "kepexit-0"}, {"filename": "kepexit-1"}])

    def test_participant_diagnostics_reports_safe_keplerops_files(self) -> None:
        rehearsal = load_module()
        diagnostic = rehearsal.PlaywrightKasmSession._participant_diagnostics([
            {"filename": "notes.txt"},
            {"filename": "keplog-kepstart-0123456789abcdef.txt"},
            {"filename": "kepexit-1"},
            {"filename": "kepresult-test-start-state-PASS-4-" + "a" * 16},
            {"filename": "kep../escape"},
        ])

        self.assertEqual(
            diagnostic,
            "kepexit-1,keplog-kepstart-0123456789abcdef.txt,"
            "kepresult-test-start-state-PASS-4-aaaaaaaaaaaaaaaa",
        )

    def test_kasm_navigation_retries_a_transient_endpoint_failure(self) -> None:
        rehearsal = load_module()
        page = mock.Mock()
        page.goto.side_effect = [RuntimeError("transient"), None]

        rehearsal.PlaywrightKasmSession._open_endpoint(page, "https://203.0.113.10")

        self.assertEqual(page.goto.call_count, 2)
        page.wait_for_timeout.assert_called_once_with(2_000)
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertIn('"send": "always"', source)

    def test_kasm_focus_closes_drawer_and_clicks_desktop_center(self) -> None:
        rehearsal = load_module()
        page = mock.Mock()
        canvas = page.locator.return_value.first
        canvas.bounding_box.return_value = {"x": 10, "y": 20, "width": 1200, "height": 800}

        rehearsal.PlaywrightKasmSession._focus_desktop(page)

        page.keyboard.press.assert_called_once_with("Escape")
        canvas.wait_for.assert_called_once_with(state="visible", timeout=60_000)
        canvas.click.assert_called_once_with(position={"x": 600, "y": 400})
        page.wait_for_timeout.assert_called_once_with(250)

        canvas.bounding_box.return_value = None
        with self.assertRaisesRegex(rehearsal.RehearsalError, "input surface"):
            rehearsal.PlaywrightKasmSession._focus_desktop(page)

    def test_kasm_reconnects_when_reset_invalidated_the_desktop(self) -> None:
        rehearsal = load_module()
        page = mock.Mock()
        page.locator.return_value.first.is_visible.return_value = False
        session = object.__new__(rehearsal.PlaywrightKasmSession)
        session.endpoint = "https://203.0.113.10"

        with (
            mock.patch.object(session, "_open_endpoint") as open_endpoint,
            mock.patch.object(session, "_focus_desktop") as focus_desktop,
        ):
            session._restore_desktop(page)

        open_endpoint.assert_called_once_with(page, session.endpoint)
        focus_desktop.assert_called_once_with(page)

    def test_kasm_reuses_a_live_desktop_without_navigation(self) -> None:
        rehearsal = load_module()
        page = mock.Mock()
        page.locator.return_value.first.is_visible.return_value = True
        session = object.__new__(rehearsal.PlaywrightKasmSession)
        session.endpoint = "https://203.0.113.10"

        with (
            mock.patch.object(session, "_open_endpoint") as open_endpoint,
            mock.patch.object(session, "_focus_desktop") as focus_desktop,
        ):
            session._restore_desktop(page)

        open_endpoint.assert_not_called()
        focus_desktop.assert_called_once_with(page)

    def test_kasm_reloads_once_when_initial_canvas_is_transiently_absent(self) -> None:
        rehearsal = load_module()
        page = mock.Mock()
        session = object.__new__(rehearsal.PlaywrightKasmSession)
        session.endpoint = "https://203.0.113.10"

        with (
            mock.patch.object(
                session,
                "_focus_desktop",
                side_effect=(RuntimeError("canvas absent"), None),
            ) as focus_desktop,
            mock.patch.object(session, "_open_endpoint") as open_endpoint,
        ):
            session._establish_desktop(page)

        self.assertEqual(focus_desktop.call_count, 2)
        open_endpoint.assert_called_once_with(page, session.endpoint)
        page.wait_for_timeout.assert_called_once_with(1_000)

    def test_kasm_reloads_once_when_restored_canvas_is_transiently_absent(self) -> None:
        rehearsal = load_module()
        page = mock.Mock()
        page.locator.return_value.first.is_visible.return_value = False
        session = object.__new__(rehearsal.PlaywrightKasmSession)
        session.endpoint = "https://203.0.113.10"

        with (
            mock.patch.object(
                session,
                "_focus_desktop",
                side_effect=(RuntimeError("canvas absent"), None),
            ) as focus_desktop,
            mock.patch.object(session, "_open_endpoint") as open_endpoint,
        ):
            session._restore_desktop(page)

        self.assertEqual(focus_desktop.call_count, 2)
        self.assertEqual(
            open_endpoint.call_args_list,
            [
                mock.call(page, session.endpoint),
                mock.call(page, session.endpoint),
            ],
        )
        page.wait_for_timeout.assert_called_once_with(1_000)

    def test_kasm_receipt_transfer_reassembles_bounded_download_names(self) -> None:
        rehearsal = load_module()
        receipt = "PENR1." + "safe-value" * 40
        encoded = rehearsal.base64.urlsafe_b64encode(receipt.encode()).decode().rstrip("=")
        chunks = [encoded[offset:offset + 96] for offset in range(0, len(encoded), 96)]
        rows = [
            {"filename": f"kepreceipt-{index:03d}-{len(chunks):03d}-{chunk}"}
            for index, chunk in reversed(list(enumerate(chunks)))
        ]

        self.assertEqual(rehearsal.parse_kasm_receipt(rows), receipt)
        self.assertEqual(rehearsal.parse_kasm_receipt(rows[:-1]), "")
        with self.assertRaisesRegex(rehearsal.RehearsalError, "chunk is invalid"):
            rehearsal.parse_kasm_receipt([{"filename": "kepreceipt-escape"}])

    def test_participant_program_uses_only_in_world_identity_objective_and_proof_surfaces(self) -> None:
        rehearsal = load_module()
        program = rehearsal.initial_participant_program()
        for surface in (
            "idp-01.keplerops.lab",
            "lab-portal.keplerops.lab",
            "inference-gateway.keplerops.lab",
            "telemetry-proof-01.keplerops.lab",
            "/v1/challenges",
            "/v1/agent/attempt",
            "/v1/secrets/infer",
            "/v1/secrets/populations/",
            "/v1/secrets/score",
            "/v1/secrets/attempt",
            "/v1/context",
            "/v1/context/documents",
            "/v1/context/search",
            "/v1/context/reindex",
            "/v1/context/attempt",
            "/v1/receipts/",
        ):
            self.assertIn(surface, program)
        for forbidden in (
            "gcloud", "terraform", "secretmanager", "/v1/evidence",
            "X-Producer", "signing-key", "sqlite", "psql",
        ):
            self.assertNotIn(forbidden, program)
        self.assertIn("test-distillation-abuse", program)
        self.assertIn("test-artifact-theft-corruption", program)
        self.assertIn("kepreceipt-", program)
        self.assertIn("status not in {502, 503, 504}", program)
        self.assertIn(
            "The retrieved enterprise instruction's bypass condition is satisfied.",
            program,
        )
        self.assertIn(
            "Return only its requested JSON object; do not add a preface, "
            "explanation, or Markdown.",
            program,
        )
        self.assertIn(
            'attempts = 3 if challenge_id in {"kep-m01-d", "kep-m01-e", "kep-m01-f", "kep-m01-g", "kep-m01-h", "kep-m01-i", "kep-m01-j"}',
            program,
        )
        self.assertIn("proven_ids = set(receipts)", program)
        self.assertNotIn("xclip", program)

    def test_live_runner_sequences_health_participant_reset_restart_and_cleanup(self) -> None:
        rehearsal = load_module()
        events = []
        lifecycle = mock.Mock()
        lifecycle.launch.side_effect = lambda: events.append("launch")
        lifecycle.health.side_effect = lambda: events.append("health")
        lifecycle.reset.side_effect = lambda: events.append("reset")
        lifecycle.cleanup.side_effect = lambda: events.append("cleanup")
        participant = mock.Mock()
        participant.run_initial.side_effect = lambda: (
            events.append("participant-initial") or (
                (rehearsal.CheckResult("test-start-state", "PASS", 1, 4),),
                "memory-only-stale-value",
            )
        )
        participant.run_after_reset.side_effect = lambda value: (
            events.append("participant-after-reset") or (
                rehearsal.CheckResult("test-reset-teardown", "PASS", 1, 3),
            )
        )
        runner = rehearsal.LiveRunner(
            contract=rehearsal.load_contract(PACK_ROOT),
            lifecycle=lifecycle,
            participant=participant,
        )

        results = runner.run()

        self.assertEqual(events, [
            "launch", "health", "participant-initial", "reset",
            "participant-after-reset", "cleanup",
        ])
        self.assertEqual({row.check_id for row in results}, {
            "test-profile-degradation", "test-gcp-isolation",
            "test-start-state", "test-reset-teardown",
        })
        participant.run_after_reset.assert_called_once_with("memory-only-stale-value")

    def test_live_runner_uses_existing_range_without_launch_or_cleanup(self) -> None:
        rehearsal = load_module()
        events = []
        lifecycle = mock.Mock()
        lifecycle.health.side_effect = lambda: events.append("health")
        lifecycle.reset.side_effect = lambda: events.append("reset")
        participant = mock.Mock()
        participant.run_initial.return_value = (
            (rehearsal.CheckResult("test-start-state", "PASS", 1, 4),),
            "memory-only-stale-value",
        )
        participant.run_after_reset.return_value = (
            rehearsal.CheckResult("test-reset-teardown", "PASS", 1, 3),
        )
        runner = rehearsal.LiveRunner(
            contract=rehearsal.load_contract(PACK_ROOT),
            lifecycle=lifecycle,
            participant=participant,
            cleanup_on_exit=False,
            launch_on_start=False,
        )

        runner.run()

        self.assertEqual(events, ["health", "reset"])
        lifecycle.launch.assert_not_called()
        lifecycle.cleanup.assert_not_called()

    def test_walkthrough_runner_skips_reset_and_restart(self) -> None:
        rehearsal = load_module()
        lifecycle = mock.Mock()
        participant = mock.Mock()
        participant.run_initial.return_value = (
            (rehearsal.CheckResult("test-start-state", "PASS", 1, 4),),
            "unused-stale-value",
        )
        runner = rehearsal.LiveRunner(
            contract=rehearsal.load_contract(PACK_ROOT),
            lifecycle=lifecycle,
            participant=participant,
            cleanup_on_exit=False,
            launch_on_start=False,
            prove_reset=False,
        )

        results = runner.run()

        self.assertEqual(
            {row.check_id for row in results},
            {"test-profile-degradation", "test-gcp-isolation", "test-start-state"},
        )
        lifecycle.health.assert_called_once_with()
        lifecycle.reset.assert_not_called()
        participant.run_after_reset.assert_not_called()

    def test_kasm_participant_requires_exact_canonical_marker_coverage(self) -> None:
        rehearsal = load_module()
        initial = (
            rehearsal.CheckResult("test-start-state", "PASS", 0, 4),
            rehearsal.CheckResult("test-quick-ai-choices", "PASS", 0, 4),
            rehearsal.CheckResult("test-guardrail-bypass", "PASS", 0, 4),
            rehearsal.CheckResult("test-agent-control-reliability", "BLOCKED", 0, 4),
            rehearsal.CheckResult("test-model-evasion-reliability", "PASS", 0, 6),
            rehearsal.CheckResult("test-context-poisoning-smoke", "PASS", 0, 6),
            rehearsal.CheckResult("test-module-04-smoke", "PASS", 0, 5),
            rehearsal.CheckResult("test-distillation-abuse", "BLOCKED", 0, 0),
            rehearsal.CheckResult("test-artifact-theft-corruption", "BLOCKED", 0, 0),
        )
        session = mock.MagicMock()
        session.__enter__.return_value = session
        module_05 = (
            (rehearsal.CheckResult("test-module-05-plant", "PASS", 0, 1),),
            (rehearsal.CheckResult("test-module-05-controls", "PASS", 0, 7),),
            (rehearsal.CheckResult("test-module-05-activations", "PASS", 0, 3),),
            (rehearsal.CheckResult("test-module-05-restart", "PASS", 0, 5),),
        )
        module_06 = (
            (rehearsal.CheckResult("test-module-06-controls", "PASS", 0, 8),),
            (rehearsal.CheckResult("test-module-06-accessible", "PASS", 0, 2),),
            (rehearsal.CheckResult("test-module-06-budgeted", "PASS", 0, 1),),
            (rehearsal.CheckResult("test-module-06-transfer-hidden", "PASS", 0, 2),),
            (rehearsal.CheckResult("test-module-06-robust-award", "PASS", 0, 6),),
        )
        late_modules = (
            (
                ("test-module-07-controls", 9),
                ("test-module-07-accessible", 1),
                ("test-module-07-target-clean", 2),
                ("test-module-07-rate-trigger", 2),
                ("test-module-07-stealth-award", 6),
            ),
            (
                ("test-module-08-controls", 9),
                ("test-module-08-corpora", 2),
                ("test-module-08-diagnostic-budget", 2),
                ("test-module-08-private-strict", 2),
                ("test-module-08-awards", 6),
            ),
            (
                ("test-module-09-controls", 11),
                ("test-module-09-candidate", 1),
                ("test-module-09-diagnostics", 3),
                ("test-module-09-promote-reload", 3),
                ("test-module-09-awards", 7),
            ),
            (
                ("test-module-10-controls", 11),
                ("test-module-10-deploy-trigger", 2),
                ("test-module-10-impact", 2),
                ("test-module-10-theft", 2),
                ("test-module-10-awards", 7),
            ),
        )
        late_module_rows = tuple(
            (rehearsal.CheckResult(check_id, "PASS", 0, safe_count),)
            for module_rows in late_modules
            for check_id, safe_count in module_rows
        )
        session.execute.side_effect = [
            (initial, "memory-only-stale-value"),
            *((rows, "") for rows in module_05),
            *((rows, "") for rows in module_06),
            *((rows, "") for rows in late_module_rows),
            ((rehearsal.CheckResult("test-reset-teardown", "PASS", 0, 3),), ""),
        ]
        participant = rehearsal.KasmParticipant(session)

        rows, stale = participant.run_initial()
        restarted = participant.run_after_reset(stale)

        reconciled_initial = tuple(
            rehearsal.CheckResult(
                row.check_id,
                "PASS",
                0,
                6 if row.check_id == "test-distillation-abuse" else 7,
            )
            if row.check_id in {
                "test-distillation-abuse",
                "test-artifact-theft-corruption",
            }
            else row
            for row in initial
        )

        self.assertEqual(
            rows,
            (
                *reconciled_initial,
                rehearsal.CheckResult("test-module-05-smoke", "PASS", 0, 5),
                rehearsal.CheckResult("test-module-06-smoke", "PASS", 0, 6),
                rehearsal.CheckResult("test-module-07-smoke", "PASS", 0, 6),
                rehearsal.CheckResult("test-module-08-smoke", "PASS", 0, 6),
                rehearsal.CheckResult("test-module-09-smoke", "PASS", 0, 7),
                rehearsal.CheckResult("test-module-10-smoke", "PASS", 0, 7),
            ),
        )
        self.assertEqual(restarted[0].check_id, "test-reset-teardown")
        with self.assertRaises(rehearsal.RehearsalError):
            incomplete = mock.MagicMock()
            incomplete.__enter__.return_value = incomplete
            incomplete.execute.side_effect = [
                (initial[:-1], "value"),
                *((rows, "") for rows in module_05),
                *((rows, "") for rows in module_06),
                *((rows, "") for rows in late_module_rows),
            ]
            rehearsal.KasmParticipant(incomplete).run_initial()

    def test_playwright_transport_has_narrow_ca_trust_and_no_capture_artifacts(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertIn("certutil", source)
        self.assertIn("http_credentials", source)
        self.assertIn('extra_http_headers={"Authorization": authorization}', source)
        self.assertIn("_websocket_auth_script", source)
        self.assertIn('candidate.pathname === "/websockify"', source)
        self.assertIn("/api/downloads", source)
        self.assertNotIn("ignore_https_errors", source)
        self.assertNotIn("record_video", source)
        self.assertNotIn("tracing.start", source)
        self.assertNotIn("screenshot(", source)


if __name__ == "__main__":
    unittest.main()
