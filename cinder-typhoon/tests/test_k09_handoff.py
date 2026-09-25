"""Authoring regressions; full native semantic validation runs in validate_sdl.py."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from raes.parser import parse_sdl_file

PACK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACK / 'docs/design'))
from model_topology import make_topology
from validate_challenges import DesignError, Graph, load_briefs, read_json
from validate_k09_handoff import COMMAND_CONTRACT, STATUS_COMMAND, check_k09_handoff


class RunnerHandoffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # This module alone intentionally lacks the imported world declarations.
        # Full composed native validation is mandatory in validate_sdl.py.
        cls.scenario = parse_sdl_file(PACK / 'sdl/modules/operations/k09.yaml',
                                     skip_semantic_validation=True)
        cls.briefs = load_briefs()
        cls.graph = Graph(read_json(PACK / 'docs/design/challenge-dependencies.json'), cls.briefs)
        cls.model = make_topology(cls.graph)

    def check(self, scenario=None, model=None, briefs=None):
        check_k09_handoff(scenario or self.scenario, briefs or self.briefs,
                         self.graph, model or self.model, prefix='')

    def test_authored_handoff(self):
        self.check()

    def test_documents_cannot_move_to_developer_workspace(self):
        for key in ('diagnostic-request-reference', 'runner-operations-note'):
            with self.subTest(key=key):
                scenario = self.scenario.model_copy(deep=True)
                scenario.content[key].target = 'k-corporate.k-dev'
                with self.assertRaisesRegex(DesignError, 'document ownership drift'):
                    self.check(scenario)

    def test_independent_destination_proof_is_required(self):
        scenario = self.scenario.model_copy(deep=True)
        scenario.evidence_requirements['c4'].source_refs = ['features.k-delivery.k-ci--runner']
        with self.assertRaisesRegex(DesignError, 'independent worker and destination proof'):
            self.check(scenario)

    def test_partial_proof_is_not_success(self):
        scenario = self.scenario.model_copy(deep=True)
        proposition = scenario.propositions['c4']
        proposition.quantifier = type(proposition.quantifier).ANY
        with self.assertRaisesRegex(DesignError, 'asserted or partial result'):
            self.check(scenario)

    def test_request_example_cannot_silently_change(self):
        scenario = self.scenario.model_copy(deep=True)
        scenario.content['runner-operations-note'].text = scenario.content['runner-operations-note'].text.replace(
            '--fail', '--fail --request POST')
        with self.assertRaisesRegex(DesignError, 'document text drift'):
            self.check(scenario)

    def test_consistently_changed_example_still_cannot_return_backup_principal(self):
        scenario = self.scenario.model_copy(deep=True)
        note = scenario.content['runner-operations-note']
        original = Path.read_text
        note.text = note.text.replace('/api/build-records/worker-status', '/api/build-records/backup-principal')
        def read_text(path, *args, **kwargs):
            if path.name == 'runner-operations.md':
                return note.text
            return original(path, *args, **kwargs)
        with patch.object(Path, 'read_text', read_text):
            with self.assertRaisesRegex(DesignError, 'status example changes authority'):
                self.check(scenario)

    def test_in_world_copy_cannot_announce_an_unlock(self):
        scenario = self.scenario.model_copy(deep=True)
        note = scenario.content['runner-operations-note']
        note.text += '\nChallenge unlocked: K30.1\n'
        original = Path.read_text
        def read_text(path, *args, **kwargs):
            if path.name == 'runner-operations.md':
                return note.text
            return original(path, *args, **kwargs)
        with patch.object(Path, 'read_text', read_text):
            with self.assertRaisesRegex(DesignError, 'breaks the fourth wall'):
                self.check(scenario)

    def test_worker_access_cannot_be_earned_by_reading_the_reference(self):
        model = deepcopy(self.model)
        model.contexts['runner'] = replace(model.contexts['runner'], requires_any=(('K09.3',),))
        with self.assertRaisesRegex(DesignError, 'grants worker access early'):
            self.check(model=model)

    def test_consistently_changed_note_cannot_invent_a_product_api(self):
        scenario = self.scenario.model_copy(deep=True)
        note = scenario.content['runner-operations-note']
        note.text = note.text.replace('/api/v1/user/repos', '/api/repositories')
        original = Path.read_text
        def read_text(path, *args, **kwargs):
            if path.name == 'runner-operations.md':
                return note.text
            return original(path, *args, **kwargs)
        with patch.object(Path, 'read_text', read_text):
            with self.assertRaisesRegex(DesignError, 'unsupported read path'):
                self.check(scenario)

    def test_build_record_connection_cannot_disappear(self):
        model = deepcopy(self.model)
        model.links = [link for link in model.links if not (
            link.source == 'k-ci/runner' and link.target == 'k-cloud-api/build-records')]
        with self.assertRaisesRegex(DesignError, 'route deadlock'):
            self.check(model=model)

    def test_rating_cannot_drift(self):
        briefs = deepcopy(self.briefs)
        briefs['K09.4']['tier_name'] = 'Hard'
        with self.assertRaisesRegex(DesignError, 'difficulty allocation changed'):
            self.check(briefs=briefs)

    def test_status_command_has_valid_shell_syntax(self):
        # Syntax check only: no command, credential source or service is executed.
        result = subprocess.run(['/bin/sh', '-n'], input=STATUS_COMMAND,
                                text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_status_command_expands_service_configuration_as_documented(self):
        # Exercise only shell argument construction. The curl stand-in prints
        # arguments; it cannot authenticate, issue a request or prove a solve.
        with tempfile.TemporaryDirectory(prefix='k09-command-example-') as temporary:
            fixture = Path(temporary)
            (fixture / 'connections.env').write_text(
                "FIELDLINK_BUILD_RECORDS_URL='https://build-records.example.invalid'\n")
            (fixture / 'build-records.curl').write_text('# No credentials in this fixture.\n')
            stand_in = fixture / 'curl'
            stand_in.write_text('#!/bin/sh\nprintf \'%s\\n\' "$@"\n')
            stand_in.chmod(0o700)
            command = STATUS_COMMAND.replace('/run/fieldlink-ci', str(fixture))
            result = subprocess.run(['/bin/sh', '-c', command], text=True,
                                    capture_output=True, check=False,
                                    env={'PATH': str(fixture)})
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.splitlines(), [
                '-q', '--silent', '--show-error', '--fail', '--config',
                str(fixture / 'build-records.curl'), '--url',
                'https://build-records.example.invalid/api/build-records/worker-status',
            ])

    def test_native_contract_cannot_drop_command_or_isolation_requirements(self):
        for ident, requirements in COMMAND_CONTRACT.items():
            for requirement in requirements:
                with self.subTest(precondition=ident, requirement=requirement):
                    scenario = self.scenario.model_copy(deep=True)
                    condition = next(p for p in scenario.action_contracts['c4'].preconditions
                                     if p.precondition_id == ident)
                    condition.description = ' '.join(condition.description.split()).replace(requirement, '')
                    with self.assertRaisesRegex(DesignError, 'command contract loses required behavior'):
                        self.check(scenario)

    def test_request_id_alone_cannot_prove_execution(self):
        scenario = self.scenario.model_copy(deep=True)
        evidence = scenario.evidence_requirements['c4']
        evidence.description = evidence.description.replace('per-run credential lease', 'request header')
        with self.assertRaisesRegex(DesignError, 'trusts participant-controlled proof'):
            self.check(scenario)

    def test_profile_name_alone_cannot_replace_completed_input_review(self):
        scenario = self.scenario.model_copy(deep=True)
        contract = scenario.action_contracts['c4']
        contract.procedure_basis = ' '.join(contract.procedure_basis.split()).replace(
            'retained input reference from a completed integration review', 'any input')
        with self.assertRaisesRegex(DesignError, 'loses its real input prerequisite'):
            self.check(scenario)

    def test_note_cannot_silently_force_worker_identity(self):
        scenario = self.scenario.model_copy(deep=True)
        note = scenario.content['runner-operations-note']
        note.text = note.text.replace('A failed authentication is not retried as the worker automatically',
                                      'A failed authentication is retried as the worker automatically')
        original = Path.read_text
        def read_text(path, *args, **kwargs):
            if path.name == 'runner-operations.md':
                return note.text
            return original(path, *args, **kwargs)
        with patch.object(Path, 'read_text', read_text):
            with self.assertRaisesRegex(DesignError, 'loses independent identity use'):
                self.check(scenario)


if __name__ == '__main__':
    unittest.main()
