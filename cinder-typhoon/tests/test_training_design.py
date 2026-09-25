"""Static authoring regressions. Never starts a Training service or runs a solve."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from raes.parser import parse_sdl_file

PACK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACK / 'docs/design'))
from validate_challenges import DesignError, load_briefs
from validate_training import ASSETS, check_training, check_state_records, hand_build_gaps


class TrainingDesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Fast structural checks only. validate_sdl.py separately performs
        # full upstream semantic validation, instantiation and compilation.
        cls.scenario = parse_sdl_file(PACK / 'sdl/cinder-typhoon.sdl.yaml',
                                     skip_semantic_validation=True)
        cls.briefs = load_briefs()

    def test_authored_assets_and_boundaries(self):
        check_training(self.scenario, self.briefs)

    def test_hand_build_gate_is_closed(self):
        self.assertEqual(hand_build_gaps(self.scenario), [])

    def test_asset_cannot_move_to_participant_workstation(self):
        scenario = self.scenario.model_copy(deep=True)
        scenario.content['training-state-content.replay-report'].target = 'participant.kali'
        with self.assertRaisesRegex(DesignError, 'placement drift'):
            check_training(scenario, self.briefs)

    def test_literal_bytes_cannot_drift(self):
        scenario = self.scenario.model_copy(deep=True)
        scenario.content['training-state-content.captures-volume'].text += '\n'
        with self.assertRaisesRegex(DesignError, 'bytes drift'):
            check_training(scenario, self.briefs)

    def test_public_record_cannot_become_writable(self):
        scenario = self.scenario.model_copy(deep=True)
        scenario.nodes['training.t-state'].runtime.filesystem_inventory[0].mode = '0666'
        with self.assertRaisesRegex(DesignError, 'ownership/digest drift'):
            check_training(scenario, self.briefs)

    def test_initial_state_cannot_be_published(self):
        scenario = self.scenario.model_copy(deep=True)
        routes = scenario.nodes['training.t-state'].runtime.applications[0].routes
        routes[0].static_assets.append('/var/lib/cinder-state/initial.json')
        with self.assertRaisesRegex(DesignError, 'Private Training initialization exposed'):
            check_training(scenario, self.briefs)

    def test_document_route_cannot_require_an_earned_session(self):
        scenario = self.scenario.model_copy(deep=True)
        route = next(route for app in scenario.nodes['training.t-developer'].runtime.applications
                     for route in app.routes if route.path == '/consumer-contract.md')
        route.session_required = True
        with self.assertRaisesRegex(DesignError, 'public route drift'):
            check_training(scenario, self.briefs)

    def test_private_relationship_meaning_cannot_return(self):
        scenario = self.scenario.model_copy(deep=True)
        scenario.relationships['flows-participant.training-t-state'].properties['guard'] = 'some-private-rule'
        with self.assertRaisesRegex(DesignError, 'private SDL semantics returned'):
            check_training(scenario, self.briefs)

    def test_reset_precondition_cannot_return(self):
        scenario = self.scenario.model_copy(deep=True)
        scenario.action_contracts['t04.c3'].preconditions[2].precondition_id = 'boundaries-and-reset'
        with self.assertRaisesRegex(DesignError, 'reset precondition returned'):
            check_training(scenario, self.briefs)

    def test_published_document_cannot_add_fourth_wall_copy(self):
        scenario = self.scenario.model_copy(deep=True)
        content = scenario.content['training-state-content.index']
        content.text += '\nChallenge unlocked.\n'
        original = Path.read_text
        def read_text(path, *args, **kwargs):
            return content.text if path == ASSETS / 'state/index.md' else original(path, *args, **kwargs)
        with patch.object(Path, 'read_text', read_text):
            with self.assertRaisesRegex(DesignError, 'fourth wall'):
                check_training(scenario, self.briefs)

    def test_replay_rejects_a_non_stale_source(self):
        original = Path.read_text
        def read_text(path, *args, **kwargs):
            text = original(path, *args, **kwargs)
            if path == ASSETS / 'state/replay/report.json':
                data = json.loads(text)
                data['source_request_id'] = data['request_id']
                return json.dumps(data)
            return text
        with patch.object(Path, 'read_text', read_text):
            with self.assertRaisesRegex(DesignError, 'unique stale request'):
                check_state_records()

    def test_no_reset_or_scoring_http_operation(self):
        for key in ('training.t-workbench', 'training.t-accounts',
                    'training.t-developer', 'training.t-state'):
            for app in self.scenario.nodes[key].runtime.applications:
                for route in app.routes:
                    self.assertFalse(any(word in route.path for word in ('reset', 'score', 'flag', 'complete')))

    def test_training_addresses_are_unique(self):
        keys = ('participant.kali', 'training.t-workbench', 'training.t-accounts',
                'training.t-developer', 'training.t-state')
        addresses = [self.scenario.nodes[key].runtime.network.endpoints[0].ip_address for key in keys]
        self.assertEqual(len(addresses), len(set(addresses)))

    def test_registry_grant_is_formatter_scoped(self):
        authorization = self.scenario.nodes['training.t-developer'].runtime.app_authorizations[0]
        grants = {grant.grant_id: grant for grant in authorization.permission_grants}
        self.assertEqual(grants['publish-training-formatter'].resource_patterns,
                         ['packages/@cinder/delivery-formatter'])

    def test_assignment_grant_encodes_the_record_scope_error(self):
        authorization = self.scenario.nodes['training.t-accounts'].runtime.app_authorizations[0]
        grant = next(grant for grant in authorization.permission_grants
                     if grant.grant_id == 'read-any-training-brief')
        self.assertEqual(grant.resource_patterns, ['assignment-briefs/*'])


if __name__ == '__main__':
    unittest.main()
